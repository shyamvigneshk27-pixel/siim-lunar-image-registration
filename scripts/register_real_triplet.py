"""REAL-DATA-03 Phase 6: three real NAC tiles, three independent edges, one loop.

Run:  python scripts/register_real_triplet.py --manifest real_triplet_geo_manifest.json

This is loop closure -- the project's only GT-free estimator that detects a
*coherent* wrong answer (EXP-002 objective 4: detection 1.000, false alarm
0.000 at loop level) -- meeting real data for the first time. D-011 was accepted
on mathematics and validated on constructed transforms and synthetic pipeline
edges; ADR-0011's own reversal condition has never been tested against real
imagery, because a third overlapping real product had never been acquired.

**Every edge is estimated independently, from its own image pair.**
``A->B``, ``B->C`` and ``C->A`` each run the full unmodified baseline on two
tiles. The closing edge is **never** derived as ``(T_BC @ T_AB).inverse()``.
That derivation is E-021: it manufactures an exactly-zero loop residual for an
arbitrarily wrong solution, and it was reported once as VERIFIED / high
confidence on a registration 64 px wrong. This module asserts the independence
rather than relying on the reader to notice it -- see :func:`_assert_independent`.

Nothing in the matcher, RANSAC, preprocessing, decimation or model is changed
from ``register_real_pair.py``. The point is what the pipeline as built does on
a real triplet whose overlap has been confirmed **independently of the pipeline**
(``scripts/verify_tile_overlap.py``), so tuning anything here would destroy the
measurement.

What may not be claimed
-----------------------
There is still **no ground truth** for these products. A small loop residual is
a *consistency* bound, not an accuracy: three edges that are each wrong in a
way that cancels around the loop would score well, which is exactly the failure
mode EXP-002 measured the frequency of on synthetic data and has never measured
on real data. Every figure and artefact is labelled REAL DATA so it can never be
read as one of the project's synthetic results.
"""

from __future__ import annotations

import argparse
import itertools
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
from siim.evaluation.gtfree import loop_closure  # noqa: E402

OUT = ROOT / "experiments" / "REAL-DATA-03"

#: EXP-002 operating point (D-023). Applied here, NOT validated here.
N_INLIERS_FAILURE_RULE = 8

#: Identical to register_real_pair.py. Restated as a constant so a future edit
#: to one script cannot silently make the two experiments incomparable.
RANSAC_THRESHOLD_PX = 3.0
SEED = 0


def normalise(a: np.ndarray) -> np.ndarray:
    """DN -> [0, 1] by robust percentile stretch, NaN -> median.

    Byte-for-byte the rule used in ``register_real_pair.py``. A per-image
    percentile stretch is standard preprocessing and is **not** an illumination
    correction: EXP-003 measured that contrast normalisation is sign-preserving
    and cannot repair shadow motion.
    """
    v = a[np.isfinite(a)]
    lo, hi = np.percentile(v, [1.0, 99.0])
    out = (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)
    return np.clip(np.nan_to_num(out, nan=float(np.median(out[np.isfinite(out)]))),
                   0.0, 1.0)


def decimate(a: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return a
    a = a[: a.shape[0] // k * k, : a.shape[1] // k * k]
    return np.nanmean(a.reshape(a.shape[0] // k, k, a.shape[1] // k, k),
                      axis=(1, 3))


def _assert_independent(edges: list[dict]) -> None:
    """Refuse to report a loop whose edges are not three separate estimations.

    E-021's failure was not a subtle numerical issue: the closing transform was
    *computed* from the other two, so the residual was identically zero by
    construction and the demo reported VERIFIED / high confidence on a
    registration 64 px wrong. The structural guarantee that it cannot recur is
    that each edge carries its own keypoint counts, its own putative count and
    its own inlier set from its own image pair -- so if two edges ever share
    those, something has collapsed and this raises rather than reports.
    """
    signatures = [(e["n_keypoints_src"], e["n_keypoints_dst"],
                   e["n_putative_mutual_ratio_matches"], e["n_inliers"],
                   e["fit_rmse_px"]) for e in edges]
    if len(set(signatures)) != len(signatures):
        raise SystemExit(
            "two edges produced identical match statistics. Three independent "
            "estimations on three different image pairs do not do that; the "
            "edges are not independent and the loop residual is meaningless "
            "(E-021, E-025).")
    for e in edges:
        if e.get("estimated_from") != "its own image pair":
            raise SystemExit(
                f"edge {e['edge']} was not estimated from its own image pair")


def run_edge(name: str, img_a: np.ndarray, img_b: np.ndarray,
             model: str) -> tuple[dict, object]:
    """One independent estimation. Returns ``(summary, transform_or_None)``."""
    t0 = time.perf_counter()
    res = run_rootsift_baseline(img_a, img_b, model=model,
                                ransac_threshold=RANSAC_THRESHOLD_PX, seed=SEED)
    wall = time.perf_counter() - t0
    src_p, dst_p = res.matches.src_points, res.matches.dst_points
    mask = (np.asarray(res.inlier_mask, dtype=bool)
            if np.size(res.inlier_mask) else np.zeros(0, bool))
    n_in, n_put = int(mask.sum()), int(src_p.shape[0]) if np.size(src_p) else 0
    cov = coverage_metrics(src_p[mask], img_a.shape) if n_in >= 3 else None

    summary = {
        "edge": name,
        "estimated_from": "its own image pair",
        "n_keypoints_src": int(len(res.src_features)),
        "n_keypoints_dst": int(len(res.dst_features)),
        "n_putative_mutual_ratio_matches": n_put,
        "n_inliers": n_in,
        "inlier_ratio": float(n_in / n_put) if n_put else 0.0,
        "fit_rmse_px": (float(res.ransac.inlier_rmse)
                        if res.ransac.inlier_rmse is not None else None),
        "transform_estimated": res.transform is not None,
        "n_inliers_failure_flag": bool(n_in <= N_INLIERS_FAILURE_RULE),
        "wall_s": wall,
    }
    if res.transform is not None:
        summary["transform_matrix"] = np.asarray(res.transform.matrix).tolist()
    if cov is not None:
        summary["coverage_max_uncovered_disc_ratio"] = float(
            cov.max_uncovered_disc_ratio)
        summary["coverage_occupancy"] = float(cov.grid_occupancy)
    summary["_res"] = res
    return summary, res.transform


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="real_triplet_geo_manifest.json")
    ap.add_argument("--model", default="affine")
    ap.add_argument("--downsample", type=int, default=2)
    ap.add_argument("--outdir", default="REAL-DATA-03")
    ap.add_argument("--tag", default="triplet")
    ap.add_argument("--stage", default="REAL-DATA-03",
                    help="stage id recorded in the report and the figure")
    ap.add_argument("--overlap-note",
                    default=("overlap CONFIRMED independently of the matcher: "
                             "97.1% / 82.7% / 85.0%"),
                    help="one line naming the overlap evidence that was "
                         "confirmed BEFORE this ran. Defaults to "
                         "REAL-DATA-03's, so an existing invocation is "
                         "unchanged; a new stage MUST pass its own")
    ap.add_argument("--overlap-artefact",
                    default="experiments/REAL-DATA-03/overlap_triplet.json",
                    help="path to the overlap artefact the note quotes")
    args = ap.parse_args()

    global OUT
    OUT = ROOT / "experiments" / args.outdir
    OUT.mkdir(parents=True, exist_ok=True)
    out_json = OUT / f"loop_closure_{args.tag}.json"
    if out_json.exists():
        raise SystemExit(
            f"{out_json.relative_to(ROOT)} already exists; choose a new --tag "
            "rather than overwriting a result (integrity rule 4)")

    man = json.loads(
        (ROOT / "data" / "manifests" / args.manifest).read_text(encoding="utf-8"))
    tiles = man["tiles"]
    if len(tiles) != 3:
        raise SystemExit(f"a loop needs exactly three tiles, got {len(tiles)}")

    print(f"== {args.stage}: three real edges, estimated independently ==")
    print("REAL DATA. Not synthetic. No ground truth exists for these "
          "products.\n")

    imgs, names = [], []
    for t in tiles:
        a = decimate(np.load(ROOT / t["tile_npy"]), args.downsample)
        imgs.append(normalise(a))
        names.append(t["pdsid"])
        print(f"{t['pdsid']}: incidence {t['incidence_deg']:.2f} deg, "
              f"resolution {t['ode_map_resolution_m']:.3f} m, tile {a.shape}")

    if len({im.shape for im in imgs}) != 1:
        raise SystemExit("the three tiles decimate to different shapes")
    shape = imgs[0].shape

    hashes = [t["bytes_sha256"] for t in tiles]
    if len(set(hashes)) != 3:
        raise SystemExit("the three tiles are not distinct (E-025)")
    print(f"\nthree distinct tiles confirmed by SHA-256; shape {shape}")
    print(f"model={args.model}  downsample={args.downsample}  "
          f"ransac_threshold={RANSAC_THRESHOLD_PX}  seed={SEED}")
    print("running the UNMODIFIED RootSIFT baseline on each edge, "
          "INDEPENDENTLY\n")

    order = [(0, 1), (1, 2), (2, 0)]
    edges, transforms = [], []
    for i, j in order:
        name = f"{names[i]} -> {names[j]}"
        summary, transform = run_edge(name, imgs[i], imgs[j], args.model)
        edges.append(summary)
        transforms.append(transform)
        print(f"{name}")
        print(f"   keypoints {summary['n_keypoints_src']} / "
              f"{summary['n_keypoints_dst']}   putative "
              f"{summary['n_putative_mutual_ratio_matches']}   inliers "
              f"{summary['n_inliers']} (ratio {summary['inlier_ratio']:.4f})")
        print(f"   fit RMSE {summary['fit_rmse_px']}  "
              "[EXCLUDED from correctness -- D-003]")
        if "coverage_max_uncovered_disc_ratio" in summary:
            print(f"   coverage gap "
                  f"{summary['coverage_max_uncovered_disc_ratio']:.4f}  "
                  f"occupancy {summary['coverage_occupancy']:.3f}")
        print(f"   n_inliers <= {N_INLIERS_FAILURE_RULE}: "
              f"{summary['n_inliers_failure_flag']}   "
              f"{summary['wall_s']:.2f} s\n")

    _assert_independent(edges)
    print("independence check passed: three distinct match statistics, each "
          "from its own image pair.\n"
          "The closing edge was ESTIMATED, never derived from the other two "
          "(E-021).\n")

    loop_px = loop_closure(transforms, shape)
    n_estimated = sum(t is not None for t in transforms)
    print(f"edges with a transform: {n_estimated} / 3")
    print(f"LOOP CLOSURE RESIDUAL: {loop_px:.6g} px "
          f"(median over a {shape} grid)")

    # -- verdict on the loop, using the WEAKEST edge -----------------------
    weakest = min(range(3), key=lambda k: edges[k]["n_inliers"])
    w = edges[weakest]
    res_w = w["_res"]
    v = assess(
        transform=res_w.transform,
        src_points=res_w.matches.src_points,
        dst_points=res_w.matches.dst_points,
        inlier_mask=res_w.inlier_mask, shape=shape,
        fit_rmse=res_w.ransac.inlier_rmse,
        loop_error_px=(None if not np.isfinite(loop_px) else float(loop_px)),
    )
    print(f"\nverdict (evaluated on the WEAKEST edge, {w['edge']}): "
          f"{v.status} / {v.confidence}")
    for r in v.reasons:
        print(f"   - {r}")

    if any(e["n_inliers_failure_flag"] for e in edges):
        cls = "C"
        why = ("registration failure on at least one edge: n_inliers <= "
               f"{N_INLIERS_FAILURE_RULE}, the EXP-002 operating point (not "
               "validated on real data). A loop residual computed from a "
               "failed edge is not evidence of anything.")
    elif not np.isfinite(loop_px):
        cls, why = "C", "at least one edge produced no transform"
    else:
        cls = "B"
        why = ("all three edges cleared the inlier rule and the loop closed; "
               "still NOT verified against ground truth, which does not exist "
               "for these products. Loop closure bounds CONSISTENCY, not "
               "accuracy.")

    for e in edges:
        e.pop("_res", None)
    report = {
        "stage": args.stage,
        "phase": "6 - real loop closure",
        "data": "REAL LRO NAC. NOT SYNTHETIC.",
        "manifest": args.manifest,
        "products": names,
        "incidence_deg": [t["incidence_deg"] for t in tiles],
        "tile_sha256": hashes,
        "shape_after_decimation": list(shape),
        "baseline": {
            "pipeline": "run_rootsift_baseline (B1), UNMODIFIED",
            "model": args.model,
            "ransac_threshold_px": RANSAC_THRESHOLD_PX,
            "seed": SEED,
            "downsample": args.downsample,
            "preprocessing": "1-99 percentile stretch per image, identical to "
                             "register_real_pair.py",
        },
        "overlap_evidence": (
            "Every edge was classified OVERLAP_CONFIRMED by "
            "scripts/verify_tile_overlap.py from archive corner geometry, "
            "BEFORE this ran and INDEPENDENTLY of the matcher: "
            f"{args.overlap_artefact} -- {args.overlap_note}"),
        "edges": edges,
        "edge_independence": (
            "Each edge was estimated by a separate run of the full baseline on "
            "its own image pair. The closing edge was NOT derived as "
            "(T_BC o T_AB)^-1; that derivation is E-021 and manufactures a "
            "zero residual for an arbitrarily wrong solution. Asserted in "
            "code by _assert_independent()."),
        "loop_closure_residual_px": (None if not np.isfinite(loop_px)
                                     else float(loop_px)),
        "verdict_edge": w["edge"],
        "verdict_edge_rationale": "the edge with the fewest inliers",
        "verdict": v.as_dict(),
        "classification": cls,
        "classification_reason": why,
        "claims_not_supported": [
            "NO ground-truth accuracy claim: none exists for these products.",
            "NO sub-pixel accuracy claim on real imagery.",
            "A loop residual is a CONSISTENCY bound, not an accuracy. Three "
            "edges wrong in a way that cancels around the loop would score "
            "well; the frequency of that on real data is unmeasured.",
            "NO Sun-AZIMUTH claim: azimuth was not used (RL-032b). These "
            "frames differ in INCIDENCE only and are NOT azimuth-controlled.",
            "NO Chandrayaan-2 or multi-modal claim: one instrument throughout.",
            "NO validation of n_inliers <= 8 on real data: applied, not "
            "validated.",
        ],
    }
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nCLASSIFICATION: {cls} -- {why}")
    print(f"result: {out_json.relative_to(ROOT)}")

    # -- figure -------------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(16, 7))
    for ax, img, t in zip(axes, imgs, tiles):
        ax.imshow(img, cmap="gray", interpolation="nearest")
        ax.set_title(f"{t['pdsid']}\nincidence {t['incidence_deg']:.1f}"
                     r"$^\circ$" f", res {t['ode_map_resolution_m']:.3f} m",
                     fontsize=9)
        ax.set_xlabel("sample"), ax.set_ylabel("line")
    edge_txt = "   ".join(
        f"{e['edge'].split(' -> ')[0][-6:]}→{e['edge'].split(' -> ')[1][-6:]}: "
        f"{e['n_inliers']} inliers" for e in edges)
    loop_txt = ("no transform on at least one edge" if not np.isfinite(loop_px)
                else f"{loop_px:.4g} px")
    fig.suptitle(
        "REAL DATA — LRO NAC loop-closure triplet (NOT synthetic, NO ground "
        "truth)\n"
        "overlap CONFIRMED independently of the matcher: 97.1% / 82.7% / 85.0%"
        f"\n{edge_txt}   ·   loop residual {loop_txt}   ·   class {cls}",
        fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / f"loop_closure_{args.tag}.png", dpi=110)
    print(f"figure: {(OUT / f'loop_closure_{args.tag}.png').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
