"""EXP-002 objective 4 -- can GT-free estimators detect a coherent wrong answer?

Objective 3 showed that the failures the image pipeline actually produces
(illumination collapse) are trivially caught by counting inliers: the
GT-free estimators returned ``inf`` in 104/192 cases, 103 of them wrong,
so their apparent skill was a proxy for "too few inliers to evaluate".

That means they were never tested against the failure they exist for: a
**large, mutually consistent, wrong** correspondence set. So this script
*constructs* those adversarial cases explicitly, with many correspondences,
and asks which estimator can see through them.

Three parts:

A. correspondence-level (constructed match sets, many points)
B. transform-level cycles and loops
C. image-level, the real pipeline on repetitive terrain

Calibration seeds pick each estimator's threshold; disjoint validation seeds
report its detection rate and false-alarm rate. Ground truth is used only to
score, never as an input.

Run:  python scripts/run_exp002_gtfree.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from exp002_common import CALIBRATION_SEEDS, VALIDATION_SEEDS  # noqa: E402

from siim.evaluation import (  # noqa: E402
    cycle_consistency,
    held_out_residual,
    loop_closure,
    spatial_split_consistency,
)
from siim.geometry import (  # noqa: E402
    affine,
    endpoint_error,
    identity,
    similarity,
    translation,
)

OUT = ROOT / "experiments" / "EXP-002"
SHAPE = (512, 512)
LATTICE_PERIOD = 64.0
NOISE = 0.4


# ------------------------------------------------- part A: constructed sets


def make_case(kind: str, seed: int) -> dict:
    """Build a correspondence set of a named kind, with ground truth attached.

    Every case has PLENTY of correspondences, so that a failure cannot be
    detected by simply counting them. That is the point.
    """
    rng = np.random.default_rng(seed)
    truth = affine([[1.02, 0.03, 7.0], [-0.02, 1.01, -5.0]])
    n = 300

    if kind == "correct":
        src = rng.uniform(0, 512, size=(n, 2))
        dst = truth.apply(src) + rng.normal(0, NOISE, size=(n, 2))
        est, wrong = truth, False

    elif kind == "correct_noisy":
        src = rng.uniform(0, 512, size=(n, 2))
        dst = truth.apply(src) + rng.normal(0, 1.2, size=(n, 2))
        est, wrong = truth, False

    elif kind == "lattice_shift":
        # Every match displaced by exactly one crater-lattice period.
        src = rng.uniform(0, 512, size=(n, 2))
        bad = translation(LATTICE_PERIOD, 0.0) @ truth
        dst = bad.apply(src) + rng.normal(0, NOISE, size=(n, 2))
        est, wrong = bad, True

    elif kind == "repeated_texture":
        # A mixture: 65% shifted by one period, 35% correct. RANSAC keeps the
        # majority, so the surviving set is coherent and wrong.
        src = rng.uniform(0, 512, size=(n, 2))
        bad = translation(LATTICE_PERIOD, 0.0) @ truth
        pick = rng.random(n) < 0.65
        dst = np.where(pick[:, None], bad.apply(src), truth.apply(src))
        dst = dst + rng.normal(0, NOISE, size=(n, 2))
        src, dst = src[pick], dst[pick]  # the consensus set RANSAC would keep
        est, wrong = bad, True

    elif kind == "coherent_affine":
        # A different affine entirely -- a plausible but wrong global fit.
        src = rng.uniform(0, 512, size=(n, 2))
        bad = affine([[1.10, 0.09, 22.0], [-0.07, 1.06, -18.0]])
        dst = bad.apply(src) + rng.normal(0, NOISE, size=(n, 2))
        est, wrong = bad, True

    elif kind == "partial_overlap":
        # Correspondences confined to one corner, fitted model wrong elsewhere.
        src = rng.uniform(0, 150, size=(n, 2))
        bad = affine([[1.06, 0.05, 12.0], [-0.05, 1.04, -9.0]])
        dst = bad.apply(src) + rng.normal(0, NOISE, size=(n, 2))
        est, wrong = bad, True

    elif kind == "low_inlier_degenerate":
        # n close to model DOF: the fit interpolates, fit RMSE ~ 0 (RL-010).
        src = rng.uniform(0, 512, size=(4, 2))
        dst = rng.uniform(0, 512, size=(4, 2))
        from siim.geometry import estimate

        r = estimate(src, dst, "affine")
        est, wrong = r.transform, True

    elif kind == "clustered_correct":
        # Correct matches, but all in one small region: correct yet fragile.
        src = rng.normal((256, 256), 40, size=(n, 2))
        dst = truth.apply(src) + rng.normal(0, NOISE, size=(n, 2))
        est, wrong = truth, False

    else:
        raise ValueError(kind)

    ho = held_out_residual(src, dst, model="affine", k_folds=5, seed=0)
    split = spatial_split_consistency(src, dst, model="affine", shape=SHAPE, seed=0)
    true_err = endpoint_error(est, truth, SHAPE, step=16).median if est else float("inf")

    return {
        "kind": kind,
        "seed": seed,
        "n_points": int(src.shape[0]),
        "held_out_median": ho.median,
        "held_out_p90": ho.p90,
        "held_out_ok": ho.ok,
        "split_consistency": split,
        "true_transform_error": true_err,
        "is_wrong": bool(wrong),
    }


KINDS = [
    "correct", "correct_noisy", "clustered_correct",
    "lattice_shift", "repeated_texture", "coherent_affine",
    "partial_overlap", "low_inlier_degenerate",
]


# ---------------------------------------------- part B: cycles and loops


def make_cycle_case(kind: str, seed: int) -> dict:
    """Transform-level: forward/backward cycle and a three-image loop."""
    rng = np.random.default_rng(seed)
    jitter = lambda s: translation(float(rng.normal(0, s)), float(rng.normal(0, s)))

    t_ab = similarity(1.02, np.deg2rad(3.0), 9.0, -6.0)
    t_bc = similarity(0.99, np.deg2rad(-2.0), -5.0, 7.0)
    t_ca = (t_bc @ t_ab).inverse()  # true loop closes exactly

    shift = translation(LATTICE_PERIOD, 0.0)

    if kind == "correct":
        e_ab, e_bc, e_ca = jitter(0.3) @ t_ab, jitter(0.3) @ t_bc, jitter(0.3) @ t_ca
        e_ba = e_ab.inverse() @ jitter(0.3)
        wrong = False
    elif kind == "lattice_all_edges":
        # Every edge wrong by the same period: cancels in a cycle, accumulates
        # in a loop. This is the discriminating case.
        e_ab, e_bc, e_ca = shift @ t_ab, shift @ t_bc, shift @ t_ca
        e_ba = (shift @ t_ab).inverse()
        wrong = True
    elif kind == "lattice_one_edge":
        e_ab, e_bc, e_ca = shift @ t_ab, t_bc, t_ca
        e_ba = (shift @ t_ab).inverse()
        wrong = True
    elif kind == "symmetric_wrong":
        # Forward and backward both wrong but mutually inverse: the blind spot
        # cycle consistency cannot see.
        e_ab = shift @ t_ab
        e_ba = e_ab.inverse()
        e_bc, e_ca = t_bc, t_ca
        wrong = True
    else:
        raise ValueError(kind)

    return {
        "kind": kind,
        "seed": seed,
        "cycle_error": cycle_consistency(e_ab, e_ba, SHAPE),
        "loop_error": loop_closure([e_ab, e_bc, e_ca], SHAPE),
        "true_transform_error": endpoint_error(e_ab, t_ab, SHAPE, step=16).median,
        "is_wrong": bool(wrong),
    }


CYCLE_KINDS = ["correct", "lattice_all_edges", "lattice_one_edge", "symmetric_wrong"]


# ------------------------------------------------------------- evaluation


def pick_threshold(rows, key):
    """Youden's J on calibration rows. Higher value = worse, for all these."""
    vals = np.array([_v(r[key]) for r in rows])
    y = np.array([1 if r["is_wrong"] else 0 for r in rows])
    if y.sum() in (0, len(y)):
        return None
    best_j, best_t = -2.0, None
    for t in np.unique(vals):
        pred = vals >= t
        tp = ((pred == 1) & (y == 1)).sum(); fn = ((pred == 0) & (y == 1)).sum()
        fp = ((pred == 1) & (y == 0)).sum(); tn = ((pred == 0) & (y == 0)).sum()
        j = tp / max(tp + fn, 1) - fp / max(fp + tn, 1)
        if j > best_j:
            best_j, best_t = j, float(t)
    return best_t


def _v(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return 1e12
    return f if np.isfinite(f) else 1e12


def evaluate(rows, key, thr):
    vals = np.array([_v(r[key]) for r in rows])
    y = np.array([1 if r["is_wrong"] else 0 for r in rows])
    pred = vals >= thr
    tp = float(((pred == 1) & (y == 1)).sum()); fn = float(((pred == 0) & (y == 1)).sum())
    fp = float(((pred == 1) & (y == 0)).sum()); tn = float(((pred == 0) & (y == 0)).sum())
    return {
        "threshold": thr, "n": int(len(y)), "n_wrong": int(y.sum()),
        "detection_rate": tp / max(tp + fn, 1),
        "false_alarm_rate": fp / max(fp + tn, 1),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
    }


def per_kind(rows, key, thr, kinds):
    out = {}
    for k in kinds:
        sub = [r for r in rows if r["kind"] == k]
        if not sub:
            continue
        vals = [_v(r[key]) for r in sub]
        flagged = float(np.mean([v >= thr for v in vals]))
        out[k] = {
            "n": len(sub),
            "is_wrong": bool(sub[0]["is_wrong"]),
            "median_signal": float(np.median(vals)),
            "flagged_rate": flagged,
            "median_true_error": float(np.median([r["true_transform_error"] for r in sub])),
        }
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    reps = 12

    # -- Part A ---------------------------------------------------------
    cal_a, val_a = [], []
    for i in range(reps):
        for k in KINDS:
            cal_a.append(make_case(k, CALIBRATION_SEEDS[0] + i * 17 + hash(k) % 100))
            val_a.append(make_case(k, VALIDATION_SEEDS[0] + i * 23 + hash(k) % 100))

    print("== Part A: constructed correspondence sets (300 points each) ==")
    print(f"   calibration {len(cal_a)} cases, validation {len(val_a)} cases\n")
    print(f"{'estimator':22s} {'thr':>10s} {'detect':>8s} {'false_alarm':>12s}")
    a_results = {}
    for key in ("held_out_median", "split_consistency"):
        thr = pick_threshold(cal_a, key)
        ev = evaluate(val_a, key, thr)
        a_results[key] = {
            "threshold_from_calibration": thr,
            "validation": ev,
            "per_kind": per_kind(val_a, key, thr, KINDS),
        }
        print(f"{key:22s} {thr:10.3f} {ev['detection_rate']:8.3f} {ev['false_alarm_rate']:12.3f}")

    print(f"\n{'case kind':24s} {'wrong?':>7s} {'true_err':>10s} "
          f"{'held_out':>10s} {'flagged':>8s} | {'split':>10s} {'flagged':>8s}")
    for k in KINDS:
        h = a_results["held_out_median"]["per_kind"][k]
        s = a_results["split_consistency"]["per_kind"][k]
        print(f"{k:24s} {str(h['is_wrong']):>7s} {h['median_true_error']:10.2f} "
              f"{h['median_signal']:10.2f} {h['flagged_rate']:8.2f} | "
              f"{s['median_signal']:10.2f} {s['flagged_rate']:8.2f}")

    # -- Part B ---------------------------------------------------------
    cal_b, val_b = [], []
    for i in range(reps):
        for k in CYCLE_KINDS:
            cal_b.append(make_cycle_case(k, CALIBRATION_SEEDS[0] + i * 13))
            val_b.append(make_cycle_case(k, VALIDATION_SEEDS[0] + i * 29))

    print("\n== Part B: cycle consistency vs loop closure ==")
    print(f"{'estimator':22s} {'thr':>10s} {'detect':>8s} {'false_alarm':>12s}")
    b_results = {}
    for key in ("cycle_error", "loop_error"):
        thr = pick_threshold(cal_b, key)
        ev = evaluate(val_b, key, thr)
        b_results[key] = {
            "threshold_from_calibration": thr,
            "validation": ev,
            "per_kind": per_kind(val_b, key, thr, CYCLE_KINDS),
        }
        print(f"{key:22s} {thr:10.3f} {ev['detection_rate']:8.3f} {ev['false_alarm_rate']:12.3f}")

    print(f"\n{'case kind':24s} {'wrong?':>7s} {'true_err':>10s} "
          f"{'cycle':>10s} {'flagged':>8s} | {'loop':>10s} {'flagged':>8s}")
    for k in CYCLE_KINDS:
        c = b_results["cycle_error"]["per_kind"][k]
        l = b_results["loop_error"]["per_kind"][k]
        print(f"{k:24s} {str(c['is_wrong']):>7s} {c['median_true_error']:10.2f} "
              f"{c['median_signal']:10.2f} {c['flagged_rate']:8.2f} | "
              f"{l['median_signal']:10.2f} {l['flagged_rate']:8.2f}")

    rows = [{**r, "part": "A", "split": "calibration"} for r in cal_a]
    rows += [{**r, "part": "A", "split": "validation"} for r in val_a]
    with open(OUT / "objective4_gtfree_partA.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    rows_b = [{**r, "part": "B", "split": "calibration"} for r in cal_b]
    rows_b += [{**r, "part": "B", "split": "validation"} for r in val_b]
    with open(OUT / "objective4_gtfree_partB.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_b[0].keys()))
        w.writeheader(); w.writerows(rows_b)

    (OUT / "objective4_gtfree.json").write_text(json.dumps({
        "objective": "4 - GT-free estimators vs coherent wrong solutions",
        "protocol": "thresholds from calibration seeds, reported on disjoint validation seeds",
        "calibration_seeds": list(CALIBRATION_SEEDS),
        "validation_seeds": list(VALIDATION_SEEDS),
        "part_a_correspondence_level": a_results,
        "part_b_cycle_and_loop": b_results,
    }, indent=2, default=float))
    print(f"\nwritten: {OUT/'objective4_gtfree.json'}")


if __name__ == "__main__":
    main()
