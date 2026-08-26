"""Phase 7: run the EXISTING RootSIFT baseline on a real LRO NAC tile pair.

Run:  python scripts/register_real_pair.py [--manifest ...] [--hypothesis H1|H2]

Nothing in the matcher, the RANSAC, or the metrics is modified for this. The
point is what the pipeline built on synthetic terrain does when it first meets
real lunar imagery, so changing it to improve the answer would destroy the
measurement.

What may and may not be claimed
-------------------------------
There is **no ground truth**. These are real products with no independent
geolocation available to this project, so:

* ``fit_rmse`` is reported and is **never** a correctness criterion (D-003:
  ROC AUC 0.4947 -- chance -- and inverted in the failure regime);
* ``n_inliers <= 8`` is applied as the EXP-002 operating point, and is quoted
  as **not validated on real data** (D-025 already withdrew its false-alarm
  rate once, on synthetic data);
* loop closure needs a third overlapping image. Where a third product is
  supplied, all three edges are estimated **independently** from image pairs.
  It is never closed algebraically -- that is E-021, and it is the one place
  this project claims to be strongest.

The outcome is classified A/B/C/D per the block's Phase 8 taxonomy.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from siim.baselines.rootsift_pipeline import run_rootsift_baseline  # noqa: E402
from siim.demo.verdict import assess  # noqa: E402
from siim.evaluation import coverage_metrics  # noqa: E402

OUT = ROOT / "experiments" / "REAL-DATA"

#: EXP-002 operating point (D-023). Applied here, NOT validated here.
N_INLIERS_FAILURE_RULE = 8


def normalise(a: np.ndarray) -> np.ndarray:
    """DN -> [0, 1] by robust percentile stretch, NaN -> local median.

    A single fixed rule applied identically to both images. Per-image
    percentile stretch is standard preprocessing and is *not* an illumination
    correction: EXP-003 measured that contrast normalisation is sign-preserving
    and cannot repair shadow motion (ADR-0004, superseded). It is here only to
    put two frames with very different exposure on a common numeric range, so
    that SIFT's contrast threshold means the same thing for both.
    """
    v = a[np.isfinite(a)]
    lo, hi = np.percentile(v, [1.0, 99.0])
    out = (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)
    return np.clip(np.nan_to_num(out, nan=float(np.median(out[np.isfinite(out)]))),
                   0.0, 1.0)


def summarise(res, shape, tag) -> dict:
    src_p = res.matches.src_points
    dst_p = res.matches.dst_points
    mask = np.asarray(res.inlier_mask, dtype=bool) if np.size(res.inlier_mask) \
        else np.zeros(0, bool)
    n_in = int(mask.sum())
    n_put = int(src_p.shape[0]) if np.size(src_p) else 0
    cov = coverage_metrics(src_p[mask], shape) if n_in >= 3 else None
    d = {
        "tag": tag,
        "n_keypoints_src": int(len(res.src_features)),
        "n_keypoints_dst": int(len(res.dst_features)),
        "n_putative_mutual_ratio_matches": n_put,
        "n_inliers": n_in,
        "inlier_ratio": float(n_in / n_put) if n_put else 0.0,
        "fit_rmse_px": (float(res.ransac.inlier_rmse)
                        if res.ransac.inlier_rmse is not None else None),
        "transform_estimated": res.transform is not None,
        "n_inliers_failure_flag": bool(n_in <= N_INLIERS_FAILURE_RULE),
        "runtime_s": dict(res.runtime),
    }
    if res.transform is not None:
        d["transform_matrix"] = np.asarray(res.transform.matrix).tolist()
    if cov is not None:
        d["coverage_max_uncovered_disc_ratio"] = float(cov.max_uncovered_disc_ratio)
        d["coverage_occupancy"] = float(cov.grid_occupancy)
    return d


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="real_pair_usable_manifest.json")
    ap.add_argument("--model", default="affine")
    ap.add_argument("--downsample", type=int, default=2,
                    help="integer decimation before matching (1 = none)")
    ap.add_argument("--outdir", default=None,
                    help="output directory under experiments/ (default "
                         "REAL-DATA)")
    args = ap.parse_args()

    global OUT
    if args.outdir:
        OUT = ROOT / "experiments" / args.outdir

    man_path = ROOT / "data" / "manifests" / args.manifest
    man = json.loads(man_path.read_text(encoding="utf-8"))
    tag = (args.manifest.replace("real_pair_", "").replace("real_", "")
           .replace("_manifest.json", ""))
    OUT.mkdir(parents=True, exist_ok=True)

    imgs, meta = [], []
    for t in man["tiles"]:
        a = np.load(ROOT / t["tile_npy"])
        if args.downsample > 1:
            k = args.downsample
            a = a[: a.shape[0] // k * k, : a.shape[1] // k * k]
            a = np.nanmean(a.reshape(a.shape[0] // k, k, a.shape[1] // k, k),
                           axis=(1, 3))
        imgs.append(normalise(a))
        meta.append(t)
        print(f"{t['pdsid']}: incidence {t['incidence_deg']:.2f} deg, "
              f"tile {a.shape}, normalised range "
              f"[{imgs[-1].min():.3f}, {imgs[-1].max():.3f}]")

    shape = imgs[0].shape
    print(f"\nmodel={args.model}  downsample={args.downsample}  shape={shape}")
    print("running the UNMODIFIED RootSIFT baseline (B1)...\n")

    t0 = time.perf_counter()
    res = run_rootsift_baseline(imgs[0], imgs[1], model=args.model,
                                ransac_threshold=3.0, seed=0)
    wall = time.perf_counter() - t0
    summary = summarise(res, shape, tag)
    summary["wall_s"] = wall
    summary["downsample"] = args.downsample
    summary["model"] = args.model

    print(f"keypoints      : {summary['n_keypoints_src']} / "
          f"{summary['n_keypoints_dst']}")
    print(f"putative       : {summary['n_putative_mutual_ratio_matches']} "
          "(mutual NN + ratio 0.8)")
    print(f"RANSAC inliers : {summary['n_inliers']}  "
          f"(ratio {summary['inlier_ratio']:.4f})")
    print(f"fit RMSE       : {summary['fit_rmse_px']}  "
          "[EXCLUDED from correctness -- D-003]")
    print(f"n_inliers <= {N_INLIERS_FAILURE_RULE} failure flag: "
          f"{summary['n_inliers_failure_flag']}")
    if "coverage_max_uncovered_disc_ratio" in summary:
        print(f"coverage gap   : "
              f"{summary['coverage_max_uncovered_disc_ratio']:.4f}  "
              f"occupancy {summary['coverage_occupancy']:.3f}")
    print(f"transform      : {'estimated' if summary['transform_estimated'] else 'NONE'}")
    if summary.get("transform_matrix"):
        for row in summary["transform_matrix"]:
            print("                 " + "  ".join(f"{x: .5f}" for x in row))
    print(f"runtime        : {wall:.2f} s  {summary['runtime_s']}")

    # -- verdict, with loop closure explicitly ABSENT ----------------------
    v = assess(
        transform=res.transform,
        src_points=res.matches.src_points, dst_points=res.matches.dst_points,
        inlier_mask=res.inlier_mask, shape=shape,
        fit_rmse=res.ransac.inlier_rmse,
        loop_error_px=None,   # no third overlapping real product acquired yet
    )
    summary["verdict"] = v.as_dict()
    print(f"\nverdict: {v.status} / {v.confidence}")
    for r in v.reasons:
        print(f"   - {r}")

    # -- classification, Phase 8 -------------------------------------------
    if not summary["transform_estimated"] or summary["n_inliers"] == 0:
        cls, why = "C", ("registration failure: no transform, or zero inliers, "
                         "from real imagery")
    elif summary["n_inliers_failure_flag"]:
        cls, why = "C", (f"registration failure: n_inliers "
                         f"{summary['n_inliers']} <= {N_INLIERS_FAILURE_RULE}, "
                         "the EXP-002 operating point (not validated on real data)")
    else:
        cls, why = "B", ("plausible registration, INSUFFICIENT INDEPENDENT "
                         "VERIFICATION: loop closure was not run (no third "
                         "overlapping real product), there is no ground truth, "
                         "and the overlap itself was selected approximately. "
                         "fit_rmse and inlier count cannot upgrade this.")
    summary["classification"] = cls
    summary["classification_reason"] = why
    summary["claims_not_supported"] = [
        "NO ground-truth accuracy claim: no independent geolocation exists here.",
        "NO sub-pixel accuracy claim on real imagery.",
        "NO comparison against synthetic ground truth.",
        "NO Sun-AZIMUTH invariance claim: azimuth is unavailable (E-020); this "
        "pair differs in INCIDENCE only.",
        "NO Chandrayaan-2 or multi-modal claim: no such data is present.",
        "NO validation of n_inliers <= 8 on real data: applied, not validated.",
        "Overlap is a PRE-REGISTRATION approximation from footprint latitude.",
    ]
    print(f"\nCLASSIFICATION: {cls} -- {why}")

    # -- figure -------------------------------------------------------------
    mask = np.asarray(res.inlier_mask, dtype=bool) if np.size(res.inlier_mask) \
        else np.zeros(0, bool)
    fig, axes = plt.subplots(1, 2, figsize=(14, 8))
    for ax, img, t in zip(axes, imgs, meta):
        ax.imshow(img, cmap="gray", interpolation="nearest")
        ax.set_title(f"{t['pdsid']}  incidence {t['incidence_deg']:.1f}"
                     r"$^\circ$", fontsize=10)
        ax.set_xlabel("sample"), ax.set_ylabel("line")
    if np.size(res.matches.src_points) and mask.any():
        axes[0].scatter(res.matches.src_points[mask, 0],
                        res.matches.src_points[mask, 1], s=6, c="#2ad", marker="o")
        axes[1].scatter(res.matches.dst_points[mask, 0],
                        res.matches.dst_points[mask, 1], s=6, c="#2ad", marker="o")
    fig.suptitle(
        f"First real LRO NAC registration attempt — {man['pair'][0]} x "
        f"{man['pair'][1]}\n"
        f"{summary['n_inliers']} inliers / "
        f"{summary['n_putative_mutual_ratio_matches']} putative · "
        f"class {cls} · NO ground truth, NO azimuth control", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / f"registration_{tag}.png", dpi=110)
    print(f"\nfigure: {(OUT / f'registration_{tag}.png').relative_to(ROOT)}")

    (OUT / f"registration_{tag}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"result: {(OUT / f'registration_{tag}.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
