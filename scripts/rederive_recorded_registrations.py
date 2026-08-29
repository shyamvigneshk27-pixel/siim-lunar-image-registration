"""Re-derive every recorded real-data registration number from the tile bytes.

    python scripts/rederive_recorded_registrations.py
    python scripts/rederive_recorded_registrations.py --stage REAL-DATA-04

THE QUESTION THIS ANSWERS
-------------------------
*"How do I know you did not simply type these numbers into a JSON file?"*

Every other integrity mechanism in this repository answers a weaker question.
The demo's asset certification checks that the overlay belongs to the same run
as the numbers; ``_check_asset_matches_artefact`` re-verifies that at load
time; ``tests/test_demo_real_data.py`` asserts the displayed numbers equal the
recorded ones. **All three compare a recorded number against another recorded
number.** None of them re-derives anything from an image.

This does. It loads the archive tile bytes, applies the stage's preprocessing,
runs the **unmodified** baseline, and compares 18 quantities per edge against
the recorded artefact: keypoint counts, putative count, inlier count, inlier
ratio, fit RMSE, both coverage metrics, and the full 3x3 transform matrix. It
exits non-zero on any disagreement.

WHY IT DOES NOT IMPORT ``register_real_triplet.py``
---------------------------------------------------
The preprocessing, decimation and edge loop are **restated here** rather than
imported. If this script reused the producing script's helpers, a defect in
those helpers would reproduce itself and the check would confirm nothing. The
only things shared with the producing run are the tile bytes, the baseline
under test, and the constants read out of the artefact itself.

WHAT A PASS DOES AND DOES NOT ESTABLISH
---------------------------------------
**Does:** the recorded numbers are genuine output of the pipeline in this
repository, on this environment, from these bytes. Not typed, not edited, not
produced by different code.

**Does NOT:** that the registration is *correct*. No ground truth exists for
these products (REAL-DATA-04 section 15 Q3: corroborated, not verified, class
B). Reproducing a wrong answer exactly is still reproducing a wrong answer --
which is the entire point of the B -> D edge, whose ``1.885e-13 px`` fit
residual reproduces here to every digit while the transform is independently
measured to be hundreds of pixels wrong.

REQUIRES THE TILES, WHICH ARE GITIGNORED
-----------------------------------------
~166 MB, re-fetchable by byte range from the PDS archive using the ranges and
SHA-256 in ``data/manifests/``. On a fresh clone this script reports which
tiles are missing and exits 2 -- a distinct code from a mismatch, because
"cannot check" and "checked and wrong" are different answers.

A LOAD-BEARING ORDERING, RECORDED HERE BECAUSE IT COST AN AUDIT AN HOUR
-----------------------------------------------------------------------
The pipeline **decimates first and normalises second**
(``normalise(decimate(tile, k))``). Doing it the other way round is not a
rounding difference: the percentile stretch is computed over a different
population, and the audit that first wrote this script with the order reversed
saw keypoint counts move by 2-3 %, inliers by up to 60, and every fit RMSE
change - enough to look exactly like an irreproducible result. The order is
asserted in :func:`preprocess` rather than left to be rediscovered.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from siim.baselines import run_rootsift_baseline  # noqa: E402
from siim.evaluation.coverage import coverage_metrics  # noqa: E402

DATA = ROOT / "data"
EXPERIMENTS = ROOT / "experiments"

#: Stage -> (acquisition manifest, recorded registration artefact).
STAGES: dict[str, tuple[str, str]] = {
    "REAL-DATA-03": ("real_triplet_geo_manifest.json",
                     "REAL-DATA-03/loop_closure_triplet.json"),
    "REAL-DATA-04": ("real_quad_d_geo_manifest.json",
                     "REAL-DATA-04/loop_closure_real_data_04.json"),
}

#: Integer fields must match exactly; floats to this relative tolerance.
#: 1e-9 is not a fudge factor -- the comparison is between two runs of the same
#: deterministic code, so the only permitted difference is JSON's decimal
#: round-trip. Anything larger is a real disagreement.
FLOAT_RTOL = 1e-9

INT_FIELDS = ("n_keypoints_src", "n_keypoints_dst",
              "n_putative_mutual_ratio_matches", "n_inliers")
FLOAT_FIELDS = ("inlier_ratio", "fit_rmse_px",
                "coverage_max_uncovered_disc_ratio", "coverage_occupancy")


def normalise(a: np.ndarray) -> np.ndarray:
    """DN -> [0, 1] by 1-99 percentile stretch, NaN -> median.

    Restated from the stage report, not imported (see the module docstring).
    """
    v = a[np.isfinite(a)]
    lo, hi = np.percentile(v, [1.0, 99.0])
    out = (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)
    return np.clip(np.nan_to_num(out, nan=float(np.median(out[np.isfinite(out)]))),
                   0.0, 1.0)


def decimate(a: np.ndarray, k: int) -> np.ndarray:
    """Block mean over ``k x k``, discarding any partial trailing block."""
    if k <= 1:
        return a
    a = a[: a.shape[0] // k * k, : a.shape[1] // k * k]
    return np.nanmean(a.reshape(a.shape[0] // k, k, a.shape[1] // k, k),
                      axis=(1, 3))


def preprocess(tile: np.ndarray, k: int) -> np.ndarray:
    """Decimate, THEN normalise. The order is load-bearing -- see the docstring."""
    return normalise(decimate(tile, k))


def missing_tiles(manifest_name: str) -> list[str]:
    man = json.loads((DATA / "manifests" / manifest_name).read_text(encoding="utf-8"))
    return [t["tile_npy"] for t in man["tiles"]
            if not (ROOT / t["tile_npy"].replace("\\", "/")).exists()]


def rederive_stage(stage: str, *, verbose: bool = True) -> dict:
    """Re-run one stage's edges from tile bytes. Returns a comparison report."""
    manifest_name, artefact_rel = STAGES[stage]
    man = json.loads((DATA / "manifests" / manifest_name).read_text(encoding="utf-8"))
    rec = json.loads((EXPERIMENTS / artefact_rel).read_text(encoding="utf-8"))

    # Baseline constants come from the ARTEFACT, never from a literal here, so
    # this cannot silently check a different configuration than was recorded.
    base = rec["baseline"]
    k = int(base["downsample"])
    model = base["model"]
    threshold = float(base["ransac_threshold_px"])
    seed = int(base["seed"])

    images: dict[str, np.ndarray] = {}
    for t in man["tiles"]:
        path = ROOT / t["tile_npy"].replace("\\", "/")
        if not path.exists():
            raise FileNotFoundError(path)
        images[t["pdsid"]] = preprocess(np.load(path), k)

    if verbose:
        print(f"\n=== {stage} ===")
        print(f"  artefact   {artefact_rel}")
        print(f"  baseline   model={model} threshold={threshold} seed={seed} "
              f"downsample={k}")
        print(f"  tiles      {len(images)} loaded, shape "
              f"{next(iter(images.values())).shape} after decimation")

    rows, mismatches = [], []
    for e in rec["edges"]:
        src, dst = e["edge"].split(" -> ")
        t0 = time.perf_counter()
        res = run_rootsift_baseline(images[src], images[dst], model=model,
                                    ransac_threshold=threshold, seed=seed)
        wall = time.perf_counter() - t0

        mask = (np.asarray(res.inlier_mask, dtype=bool)
                if np.size(res.inlier_mask) else np.zeros(0, bool))
        n_in = int(mask.sum())
        n_put = int(res.matches.src_points.shape[0])
        got: dict[str, object] = {
            "n_keypoints_src": int(len(res.src_features)),
            "n_keypoints_dst": int(len(res.dst_features)),
            "n_putative_mutual_ratio_matches": n_put,
            "n_inliers": n_in,
            "inlier_ratio": (n_in / n_put) if n_put else 0.0,
            "fit_rmse_px": float(res.ransac.inlier_rmse),
        }
        if n_in >= 3:
            cov = coverage_metrics(res.matches.src_points[mask], images[src].shape)
            got["coverage_max_uncovered_disc_ratio"] = float(cov.max_uncovered_disc_ratio)
            got["coverage_occupancy"] = float(cov.grid_occupancy)

        checked = 0
        for field in INT_FIELDS:
            if field not in e:
                continue
            checked += 1
            if got[field] != e[field]:
                mismatches.append((e["edge"], field, e[field], got[field]))
        for field in FLOAT_FIELDS:
            if field not in e or e[field] is None or field not in got:
                continue
            checked += 1
            r, v = float(e[field]), float(got[field])
            if abs(v - r) > max(1e-12, abs(r) * FLOAT_RTOL):
                mismatches.append((e["edge"], field, r, v))
        if e.get("transform_matrix") is not None and res.transform is not None:
            checked += 1
            d = float(np.abs(np.asarray(e["transform_matrix"], float)
                             - np.asarray(res.transform.matrix, float)).max())
            if d > 1e-9:
                mismatches.append((e["edge"], "transform_matrix", 0.0, d))

        rows.append({"edge": e["edge"], "fields_checked": checked,
                     "n_inliers": n_in, "fit_rmse_px": got["fit_rmse_px"],
                     "wall_s": wall})
        if verbose:
            bad = [m for m in mismatches if m[0] == e["edge"]]
            print(f"  {e['edge'][:46]:46s} {checked:2d} fields  "
                  f"inliers {n_in:5d}  rmse {got['fit_rmse_px']:.6g}  "
                  f"{'OK' if not bad else f'{len(bad)} MISMATCH'}  ({wall:.1f}s)")

    return {"stage": stage, "artefact": artefact_rel, "edges": rows,
            "fields_checked": sum(r["fields_checked"] for r in rows),
            "mismatches": mismatches}


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=sorted(STAGES), action="append",
                    help="stage to check; repeatable. Default: all")
    args = ap.parse_args()
    stages = args.stage or sorted(STAGES)

    print("Re-deriving recorded registration numbers from the archive tile "
          "bytes.\nThe baseline is UNMODIFIED and its configuration is read "
          "from each artefact.")

    absent = {s: missing_tiles(STAGES[s][0]) for s in stages}
    if any(absent.values()):
        print("\nCANNOT CHECK -- the decoded tiles are gitignored and not on disk:")
        for s, paths in absent.items():
            for p in paths:
                print(f"  {s}: {p}")
        print("\nRe-fetch them with the byte ranges and SHA-256 in "
              "data/manifests/ (~166 MB):\n"
              "  python scripts/acquire_real_pair.py --from-geometry ... "
              "(see README, 'Reproducing the experiments')")
        raise SystemExit(2)

    reports = [rederive_stage(s) for s in stages]
    total = sum(r["fields_checked"] for r in reports)
    bad = [m for r in reports for m in r["mismatches"]]

    print(f"\n{'-' * 72}")
    if bad:
        print(f"MISMATCH: {len(bad)} of {total} checked quantities disagree with "
              "the recorded artefacts.\n")
        for edge, field, recorded, got in bad:
            print(f"  {edge}\n    {field}: recorded {recorded!r}, re-derived {got!r}")
        print("\nA recorded artefact and the pipeline in this repository "
              "disagree. Either the artefact was edited, the pipeline changed, "
              "or the environment differs from the one in "
              "requirements-frozen.txt. This is not a tolerance to widen.")
        raise SystemExit(1)

    print(f"PASS -- all {total} recorded quantities re-derived from the tile "
          "bytes, exactly.")
    print("\nThis establishes that the recorded numbers are genuine pipeline "
          "output.\nIt does NOT establish that any registration is correct: no "
          "ground truth\nexists for these products, and the B -> D edge's "
          "1.885e-13 px fit residual\nreproduces to every digit while being "
          "independently measured hundreds of\npixels wrong. Reproducing a "
          "wrong answer exactly is still a wrong answer.")


if __name__ == "__main__":
    main()
