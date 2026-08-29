"""Where does the unmodified baseline stop working as the scale ratio grows?

    python scripts/measure_scale_limit.py
    python scripts/measure_scale_limit.py --out scale_limit_probe.json

WHY THIS EXISTS
---------------
The problem statement names **scale variation** as one of three core
challenges, and the sensor ladder it implies is severe: OHRC at ~0.25 m
against IIRS at ~80 m is a ratio of about **320:1**. EXP-001 swept scale to
**4x** and stopped. Asked *"what happens at 320:1?"*, this repository could
previously answer only *"we tested to 4x"*, which is not an answer.

This measures the actual limit and, more usefully, **which stage fails**.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
**Not a pre-registered experiment, and not a stage.** It is a *measurement of a
known limit*, run during the pre-freeze hardening pass. It does not test a
hypothesis, it does not appear in the stage index, and it writes to a new file
rather than touching ``experiments/EXP-001/results.csv``, which is EXP-001's
recorded output and is not modified.

**Synthetic only.** No cross-modal data exists in this project (no
Chandrayaan-2, ISSDC authentication), so nothing here licenses a claim about
OHRC, TMC-2 or IIRS. It measures a property of the *matcher*, not of any
sensor pair.

**Illumination is held fixed** (both images rendered at identical Sun geometry)
so that the only variable is scale. Mixing illumination in would reproduce
EXP-003's confound.

THE DISTINCTION THAT MATTERS
----------------------------
A scale limit can arise two ways, and they have different fixes:

* **descriptor failure** -- SIFT's scale-space no longer relates the two
  images, so keypoints exist in both but do not match;
* **detector starvation** -- the downscaled image is simply too small to
  contain features, so there is nothing to match.

The second is not a matcher weakness at all: it is a sampling problem, and its
fix is to normalise both images to a common ground sampling distance before
matching (D-005 / the scale-normalisation stage, **designed and not
implemented**). This script records the keypoint count at every ratio so the
two can be told apart rather than conflated.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from siim.data import TERRAIN_REGIMES, height_field, render  # noqa: E402
from siim.geometry import resize  # noqa: E402
from siim.matching import detect_and_describe, match_descriptors  # noqa: E402
from siim.verification import ransac  # noqa: E402

#: D-023's operating point, applied exactly as every other stage applies it.
#: Restated, never re-derived.
N_INLIERS_FAILURE_RULE = 8

#: Ratios swept. Powers of two to 32, which brackets the 320:1 ladder's lower
#: half; beyond 32 the reference would have to grow past a size where a
#: brute-force matcher is tractable at all (measured: matching is O(keypoints^2)).
RATIOS = (1, 2, 4, 8, 16, 32)

#: Fixed illumination for BOTH images. Scale is the only variable.
SUN_AZIMUTH_DEG = 135.0
SUN_ELEVATION_DEG = 45.0

RANSAC_THRESHOLD_PX = 3.0
SEED = 0
#: A similarity model, not affine: pure scale change is a similarity, and
#: giving the estimator two extra degrees of freedom it does not need would
#: make degeneracy at low inlier counts more likely, not less.
MODEL = "similarity"

REFERENCE_PX = 1024


def one_case(regime_name: str, seed: int, ratio: int) -> dict:
    """One (regime, seed, ratio) measurement."""
    rng = np.random.default_rng(seed)
    regime = TERRAIN_REGIMES[regime_name]
    h = height_field((REFERENCE_PX, REFERENCE_PX), rng, scene=regime.scene,
                     target_slope_median_deg=regime.target_slope_median_deg,
                     crater_density=regime.crater_density)
    ref = render(h, sun_azimuth_deg=SUN_AZIMUTH_DEG,
                 sun_elevation_deg=SUN_ELEVATION_DEG, rng=np.random.default_rng(seed))

    if ratio == 1:
        src = ref
    else:
        src, _ = resize(ref, 1.0 / ratio)
    src = np.asarray(src)

    t0 = time.perf_counter()
    fa = detect_and_describe(src)
    fb = detect_and_describe(ref)
    n_put = n_in = 0
    if len(fa) >= 2 and len(fb) >= 2:
        m = match_descriptors(fa, fb)
        n_put = len(m)
        if n_put >= 3:
            res = ransac(m.src_points, m.dst_points, model=MODEL,
                         threshold=RANSAC_THRESHOLD_PX, seed=SEED)
            n_in = int(res.n_inliers)
    wall = time.perf_counter() - t0

    # WHY it failed, if it did. Stated as data, not inferred by a reader.
    if n_in > N_INLIERS_FAILURE_RULE:
        cause = None
    elif len(fa) < 20:
        cause = "detector_starvation"   # nothing to match: a sampling problem
    else:
        cause = "descriptor_or_matching"  # keypoints exist and do not match
    return {
        "regime": regime_name, "seed": seed, "ratio": ratio,
        "source_px": int(src.shape[0]), "reference_px": int(ref.shape[0]),
        "n_keypoints_src": len(fa), "n_keypoints_ref": len(fb),
        "n_putative": n_put, "n_inliers": n_in,
        "passes_inlier_rule": bool(n_in > N_INLIERS_FAILURE_RULE),
        "failure_cause": cause, "wall_s": wall,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--out", default=None,
                    help="filename under experiments/EXP-001/; omit to print only")
    args = ap.parse_args()

    regimes = ["A_mare_moderate", "A_highlands_moderate"]
    print("Scale limit of the UNMODIFIED baseline. Illumination held fixed; "
          "scale is the only variable.\nMeasurement of a known limit, NOT a "
          "pre-registered experiment. Synthetic only.\n")
    print(f"{'regime':22s} {'seed':>4s} {'ratio':>6s} {'src_px':>7s} "
          f"{'kp_src':>7s} {'putative':>9s} {'inliers':>8s} {'rule':>6s}  cause")

    rows = []
    for regime_name in regimes:
        for seed in range(args.seeds):
            for ratio in RATIOS:
                r = one_case(regime_name, seed, ratio)
                rows.append(r)
                print(f"{r['regime']:22s} {r['seed']:4d} {r['ratio']:6d} "
                      f"{r['source_px']:7d} {r['n_keypoints_src']:7d} "
                      f"{r['n_putative']:9d} {r['n_inliers']:8d} "
                      f"{('PASS' if r['passes_inlier_rule'] else 'FAIL'):>6s}  "
                      f"{r['failure_cause'] or ''}")

    # Last ratio that passes on EVERY seed, per regime.
    summary = {}
    for regime_name in regimes:
        last = 0
        for ratio in RATIOS:
            cells = [r for r in rows
                     if r["regime"] == regime_name and r["ratio"] == ratio]
            if cells and all(c["passes_inlier_rule"] for c in cells):
                last = ratio
            else:
                break
        first_fail = [r for r in rows
                      if r["regime"] == regime_name and not r["passes_inlier_rule"]]
        causes = sorted({r["failure_cause"] for r in first_fail if r["failure_cause"]})
        summary[regime_name] = {
            "last_ratio_passing_all_seeds": last,
            "failure_causes_observed": causes,
        }

    print("\nSUMMARY")
    for regime_name, s in summary.items():
        print(f"  {regime_name:22s} last fully-passing ratio: "
              f"{s['last_ratio_passing_all_seeds']}x   "
              f"causes beyond it: {', '.join(s['failure_causes_observed']) or 'none'}")

    starved = [r for r in rows
               if r["failure_cause"] == "detector_starvation"]
    print(f"\n  Of the failing cells, {len(starved)} failed by DETECTOR "
          "STARVATION -- the downscaled\n  image is too small to contain "
          "features, which is a sampling problem and not a\n  matcher weakness. "
          "Its fix is normalising both images to a common GSD before\n  matching "
          "(D-005), which is DESIGNED AND NOT IMPLEMENTED in this repository.")
    print("\n  NOTHING HERE LICENSES A CLAIM ABOUT OHRC / TMC-2 / IIRS. No "
          "cross-modal data\n  exists in this project; this is a property of "
          "the matcher, not of a sensor pair.")

    if args.out:
        out = ROOT / "experiments" / "EXP-001" / args.out
        payload = {
            "measurement": "scale limit of the unmodified baseline",
            "status": ("NOT a pre-registered experiment and NOT a stage. A "
                       "measurement of a known limit, run during pre-freeze "
                       "hardening. EXP-001/results.csv is NOT modified."),
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data": "SYNTHETIC. No real or cross-modal imagery is involved.",
            "configuration": {
                "reference_px": REFERENCE_PX, "ratios": list(RATIOS),
                "seeds": args.seeds, "model": MODEL,
                "ransac_threshold_px": RANSAC_THRESHOLD_PX, "seed": SEED,
                "sun_azimuth_deg": SUN_AZIMUTH_DEG,
                "sun_elevation_deg": SUN_ELEVATION_DEG,
                "illumination": "IDENTICAL in both images; scale is the only variable",
                "failure_rule": f"n_inliers <= {N_INLIERS_FAILURE_RULE} (D-023), applied",
            },
            "summary": summary,
            "cases": rows,
            "claims_not_supported": [
                "Nothing about OHRC, TMC-2 or IIRS. No cross-modal data exists here.",
                "Nothing about real lunar imagery: this is synthetic terrain.",
                "Nothing about scale under ILLUMINATION change: illumination is fixed.",
                "The PS's 320:1 ladder is NOT reached and is not claimed.",
            ],
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nwrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
