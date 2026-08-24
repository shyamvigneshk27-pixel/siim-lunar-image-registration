"""EXP-003 sub-experiment -- GT-free validation by loop closure (requirement 10).

ADR-0011 / D-011: loop closure is the **only** GT-free estimator this project
may claim can detect a coherent wrong solution. Held-out residual, spatial
split consistency and ordinary cycle consistency are degeneracy detectors and
are deliberately NOT computed here, so that no such claim can be made by
accident.

Design
------
For each (regime, seed, Delta-azimuth) three images A, B, C are rendered from
the same height field under three Sun azimuths, related by known transforms
T_AB and T_BC. The pipeline estimates each edge independently:

    A -> B,   B -> C,   C -> A

For a correct set the composition ``T_CA o T_BC o T_AB`` is the identity, so
the loop error is a **ground-truth-free** accuracy bound. Ground truth is used
only to label the case afterwards, never to compute the loop error.

Scope, stated rather than quietly reduced: this runs on the baseline arm and
one representation arm, on a subset of azimuths, because each case costs three
full pipeline runs.

Run:  python scripts/run_exp003_loop_closure.py
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from exp002_common import (  # noqa: E402
    FIELD_MARGIN,
    RANSAC_THRESHOLD,
    SHAPE,
    SUN_REF,
    WRONG_PX,
    make_transform,
)
from exp003_common import (  # noqa: E402
    ARMS,
    EXP003_SEEDS,
    clear_pc_cache,
    get_field,
)

from siim.data import TERRAIN_REGIMES, render  # noqa: E402
from siim.evaluation.gtfree import loop_closure  # noqa: E402
from siim.geometry import endpoint_error, warp  # noqa: E402
from siim.matching.rootsift import match_descriptors  # noqa: E402
from siim.verification.ransac import ransac  # noqa: E402

OUT = ROOT / "experiments" / "EXP-003"

LOOP_REGIMES = ("A_mare_moderate", "A_highlands_moderate", "B_highlands_challenging")
LOOP_AZIMUTHS = (0.0, 15.0, 24.0, 30.0, 36.0, 45.0)
LOOP_ARMS = ("B1_rootsift", "A_orient_mod_pi")

_ARM_BY_NAME = {a.name: a for a in ARMS}


def _render_view(field, tf, sun_az, sun_el, shape=SHAPE):
    """Render the shared height field into a frame under one Sun geometry."""
    h, w = shape
    fh, fw = field.shape
    oy, ox = (fh - h) // 2, (fw - w) // 2
    from siim.geometry import translation

    to_frame = tf @ translation(-float(ox), -float(oy))
    warped, _ = warp(field, to_frame, out_shape=shape, cval=np.nan)
    return render(warped, sun_azimuth_deg=sun_az, sun_elevation_deg=sun_el,
                  pixel_scale=1.0)


def estimate_edge(arm, img_a, img_b, model="affine"):
    """Estimate one edge with the given representation arm."""
    fa, fb = arm.features(img_a), arm.features(img_b)
    m = match_descriptors(fa, fb, ratio=0.8, mutual=True)
    r = ransac(m.src_points, m.dst_points, model=model,
               threshold=RANSAC_THRESHOLD, seed=0)
    return r.transform, int(r.n_inliers)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    t0 = time.perf_counter()

    print("== EXP-003 loop closure (GT-free, ADR-0011) ==")
    print(f"arms {list(LOOP_ARMS)}  regimes {list(LOOP_REGIMES)}")
    print(f"azimuths {list(LOOP_AZIMUTHS)}  seeds {list(EXP003_SEEDS)}\n")

    for regime in LOOP_REGIMES:
        for seed in EXP003_SEEDS:
            field = get_field(regime, seed)
            for az in LOOP_AZIMUTHS:
                rng = np.random.default_rng(seed * 31 + int(az))
                t_ab = make_transform("affine", rng)
                t_bc = make_transform("affine", rng)
                el = 45.0
                # Three views: azimuth advances by `az` at each step, so the
                # loop spans 2*az of Sun motion.
                img_a = _render_view(field, _identity(), SUN_REF[0], el)
                img_b = _render_view(field, t_ab, SUN_REF[0] + az, el)
                img_c = _render_view(field, t_bc @ t_ab, SUN_REF[0] + 2 * az, el)

                for arm_name in LOOP_ARMS:
                    arm = _ARM_BY_NAME[arm_name]
                    clear_pc_cache()
                    tf_ab, n_ab = estimate_edge(arm, img_a, img_b)
                    tf_bc, n_bc = estimate_edge(arm, img_b, img_c)
                    tf_ca, n_ca = estimate_edge(arm, img_c, img_a)
                    clear_pc_cache()

                    loop_err = loop_closure([tf_ab, tf_bc, tf_ca], SHAPE)

                    # Ground truth: labelling only, never an input above.
                    # A loop is correct only if ALL THREE edges are correct.
                    # Labelling it by the A->B edge alone would mark a loop
                    # "correct" while one of its edges was catastrophically
                    # wrong, and then score loop closure as raising a false
                    # alarm for correctly refusing to close. That is the same
                    # class of mistake as contradiction D2: a statistic
                    # labelled with something other than what it measures.
                    truth = {"ab": t_ab, "bc": t_bc,
                             "ca": (t_bc @ t_ab).inverse()}
                    est = {"ab": tf_ab, "bc": tf_bc, "ca": tf_ca}
                    true_err = {}
                    for key in ("ab", "bc", "ca"):
                        e = est[key]
                        true_err[key] = (endpoint_error(e, truth[key], SHAPE).median
                                         if e is not None else float("inf"))
                    edge_wrong = {k: (not np.isfinite(v)) or v > WRONG_PX
                                  for k, v in true_err.items()}
                    any_edge_wrong = any(edge_wrong.values())

                    rows.append({
                        "representation": arm_name, "regime": regime, "seed": seed,
                        "delta_azimuth": az,
                        "n_inliers_ab": n_ab, "n_inliers_bc": n_bc, "n_inliers_ca": n_ca,
                        "loop_error_px": loop_err,
                        "true_error_ab_px": true_err["ab"],
                        "true_error_bc_px": true_err["bc"],
                        "true_error_ca_px": true_err["ca"],
                        "n_edges_wrong": int(sum(edge_wrong.values())),
                        # loop-level label: the one loop closure is answerable for
                        "is_wrong": bool(any_edge_wrong),
                        # edge-level label, kept for comparison
                        "ab_edge_wrong": bool(edge_wrong["ab"]),
                        "flag_n_inliers_le_8": bool(min(n_ab, n_bc, n_ca) <= 8),
                    })
            print(f"  {regime:24s} seed={seed} done ({(time.perf_counter()-t0)/60:.1f} min)")

    # --- how well does loop closure separate correct from wrong? ----------
    def analyse(subset, label):
        w = [r for r in subset if r["is_wrong"]]
        c = [r for r in subset if not r["is_wrong"]]
        fin = lambda xs: [x for x in xs if np.isfinite(x)]  # noqa: E731
        lw = fin([r["loop_error_px"] for r in w])
        lc = fin([r["loop_error_px"] for r in c])
        return {
            "subset": label, "n": len(subset), "n_wrong": len(w), "n_correct": len(c),
            "loop_error_wrong_median": float(np.median(lw)) if lw else None,
            "loop_error_correct_median": float(np.median(lc)) if lc else None,
            "loop_error_correct_max": float(np.max(lc)) if lc else None,
            "n_wrong_nonfinite_loop": sum(
                1 for r in w if not np.isfinite(r["loop_error_px"])),
            "n_correct_nonfinite_loop": sum(
                1 for r in c if not np.isfinite(r["loop_error_px"])),
            "separable_at_2px": bool(lc and lw and max(lc) < 2.0 <= min(lw))
            if (lc and lw) else None,
        }

    analysis = {"overall": analyse(rows, "all loop cases")}
    for arm_name in LOOP_ARMS:
        analysis[arm_name] = analyse(
            [r for r in rows if r["representation"] == arm_name], arm_name)

    # Detection / false alarm at a stated threshold, on the LOOP-LEVEL label.
    def detect(subset, thr=2.0):
        w = [r for r in subset if r["is_wrong"]]
        c = [r for r in subset if not r["is_wrong"]]
        ge = lambda r: (not np.isfinite(r["loop_error_px"])) or r["loop_error_px"] >= thr  # noqa: E731
        return {
            "threshold_px": thr,
            "n_wrong": len(w), "n_correct": len(c),
            "detection_rate": (sum(1 for r in w if ge(r)) / len(w)) if w else None,
            "false_alarm_rate": (sum(1 for r in c if ge(r)) / len(c)) if c else None,
        }

    analysis["detection_loop_level"] = detect(rows)
    analysis["detection_edge_level_MISLABELLED"] = {
        "note": ("Scored against the A->B edge label only. Retained to show the "
                 "size of the labelling error: a loop with one bad edge is not a "
                 "false alarm when loop closure refuses to close it."),
        **{k: v for k, v in detect(
            [{**r, "is_wrong": r["ab_edge_wrong"]} for r in rows]).items()},
    }

    print("\n=== Loop closure separation (LOOP-LEVEL label: wrong if ANY edge wrong) ===")
    for k, d in analysis.items():
        if "subset" not in d:
            continue
        print(f"  {d['subset']:24s} n={d['n']:3d} wrong={d['n_wrong']:3d} "
              f"loop(correct)med={d['loop_error_correct_median']} "
              f"loop(wrong)med={d['loop_error_wrong_median']}")

    dl = analysis["detection_loop_level"]
    de = analysis["detection_edge_level_MISLABELLED"]
    print(f"\n  loop-level  (correct): detection={dl['detection_rate']} "
          f"false_alarm={dl['false_alarm_rate']}  "
          f"(n_wrong={dl['n_wrong']}, n_correct={dl['n_correct']})")
    print(f"  edge-level  (WRONG label): detection={de['detection_rate']} "
          f"false_alarm={de['false_alarm_rate']}  "
          f"-- the labelling error, shown for size")

    payload = {
        "experiment": "EXP-003",
        "sub_experiment": "loop closure (GT-free primary estimator, ADR-0011)",
        "estimators_deliberately_excluded": [
            "held_out_residual", "spatial_split_consistency", "cycle_consistency",
        ],
        "exclusion_reason": (
            "ADR-0011 / E-011: these are degeneracy detectors and are blind to "
            "coherent wrong solutions. Computing them here would invite a claim "
            "the evidence does not support."
        ),
        "arms": list(LOOP_ARMS), "regimes": list(LOOP_REGIMES),
        "azimuths_deg": list(LOOP_AZIMUTHS), "seeds": list(EXP003_SEEDS),
        "n_cases": len(rows),
        "analysis": analysis,
        "total_runtime_s": time.perf_counter() - t0,
    }
    (OUT / "exp003_loop_closure.json").write_text(
        json.dumps(payload, indent=2, default=float), encoding="utf-8")
    with open(OUT / "exp003_loop_closure_cases.csv", "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwritten: {OUT/'exp003_loop_closure.json'}")


def _identity():
    from siim.geometry import Transform
    return Transform(np.eye(3), "translation")


if __name__ == "__main__":
    main()
