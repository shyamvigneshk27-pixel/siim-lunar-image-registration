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
from siim.geometry import affine, transfer_residuals, warp  # noqa: E402
from siim.ingest.footprint import FrameCorners, TileWindow  # noqa: E402
from siim.ingest.pds4 import parse_display_direction  # noqa: E402

OUT = ROOT / "experiments" / "REAL-DATA-03"

# ---------------------------------------------------------------------------
# --emit-product: the two named PS deliverables, from RECORDED evidence only
# ---------------------------------------------------------------------------
#
# The problem statement lists four deliverables: software, a **registered
# product**, **corresponding match points**, and evaluation metrics. The first
# and last existed; the middle two did not. This mode produces them for the one
# real edge that passes the pre-registered inlier rule.
#
# **It runs no matcher and estimates nothing.** The transform is read from the
# recorded loop-closure artefact and the correspondences from the certified
# overlay asset, which `build_demo_assets.py` refuses to write unless a re-run
# reproduces every recorded statistic exactly. So this mode cannot produce a
# number that disagrees with what the stage recorded -- it has no way to compute
# one. It also never writes into `loop_closure_*.json` or any other existing
# artefact.

#: The mandated label. One constant, so the CSV header, the provenance JSON and
#: the tests cannot drift into three different statements of the same claim.
PRODUCT_CLASS_STATEMENT = (
    "a registered product; no ground truth exists for it; "
    "corroborated, not verified; class B."
)

#: No-data colour for both PNGs. Magenta, because E-003's lesson is that
#: zero-fill is indistinguishable from genuine lunar shadow: on this data
#: near-zero is a legal value, so "outside the source" must be a colour that
#: cannot occur in a greyscale render.
NODATA_RGB = (255, 0, 255)

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


def _sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _corners_for(pdsid: str, geometry: dict) -> FrameCorners:
    """Named archive corners, with the naming verified from the product's label.

    Identical discipline to ``check_transform_against_geometry.corners_for``:
    ``UPPER_*`` is read as line 0 only when that product's own PDS4
    ``disp:Display_Direction`` says so. A product whose label disagrees raises
    rather than falling back to convention -- the convention is exactly what
    was wrong in E-028.
    """
    rec = geometry.get(pdsid)
    if rec is None:
        raise SystemExit(f"{pdsid} has no archive corner geometry on disk")
    label = next((ROOT / "data" / "metadata").rglob(f"{pdsid}.xml"), None)
    if label is None:
        raise SystemExit(
            f"no stored PDS4 label for {pdsid}; the corner naming cannot be "
            "verified for it and is not assumed")
    disp = parse_display_direction(label.read_text(encoding="utf-8"))
    if (disp["vertical_axis"], disp["vertical_direction"]) != ("Line", "Top to Bottom"):
        raise SystemExit(f"{pdsid}: unexpected Display_Direction {disp}")
    if (disp["horizontal_axis"], disp["horizontal_direction"]) != ("Sample", "Left to Right"):
        raise SystemExit(f"{pdsid}: unexpected Display_Direction {disp}")
    f = rec["fields"]

    def c(corner: str) -> tuple[float, float]:
        return (float(f[corner + "_LONGITUDE"]), float(f[corner + "_LATITUDE"]))

    return FrameCorners(c("UPPER_LEFT"), c("UPPER_RIGHT"),
                        c("LOWER_LEFT"), c("LOWER_RIGHT"),
                        int(f["IMAGE_LINES"]), int(f["LINE_SAMPLES"]))


def _grey_png(values: np.ndarray, valid: np.ndarray, path: Path) -> dict:
    """Greyscale render with an unmistakable no-data colour. Returns statistics."""
    from PIL import Image
    rgb = np.empty(values.shape + (3,), dtype=np.uint8)
    v = np.clip(np.nan_to_num(values, nan=0.0), 0.0, 1.0)
    grey = (v * 255.0 + 0.5).astype(np.uint8)
    rgb[..., 0] = rgb[..., 1] = rgb[..., 2] = grey
    rgb[~valid] = NODATA_RGB
    Image.fromarray(rgb, mode="RGB").save(path)
    inside = values[valid]
    lo = float(np.nanmin(inside)) if inside.size else None
    hi = float(np.nanmax(inside)) if inside.size else None
    return {
        "shape_rows_cols": [int(values.shape[0]), int(values.shape[1])],
        "valid_fraction": float(valid.mean()),
        "nodata_pixels": int((~valid).sum()),
        "nodata_rgb": list(NODATA_RGB),
        "valid_min": lo,
        "valid_median": float(np.nanmedian(inside)) if inside.size else None,
        "valid_max": hi,
        "out_of_unit_range_fraction": float(
            ((inside < 0.0) | (inside > 1.0)).mean()) if inside.size else None,
        "why_values_can_fall_outside_0_1": (
            "The source is normalised to [0, 1] before warping, but `warp` "
            "resamples with a cubic spline (order=3), which overshoots at "
            "high-contrast edges -- crater rims and shadow boundaries here. "
            "Standard, expected, and NOT a defect: the overshoot is a property "
            "of the interpolator, not of the registration. The reported "
            "min/max are the TRUE resampled values; only the PNG render clips "
            "to [0, 255]. Use order=1 to remove it at the cost of softening "
            "the texture the matcher works on."),
    }


def _diff_png(diff: np.ndarray, valid: np.ndarray, path: Path) -> dict:
    """Diverging blue-white-red render of a signed difference, symmetric at 0."""
    from PIL import Image
    inside = diff[valid]
    span = float(np.nanpercentile(np.abs(inside), 99.0)) if inside.size else 1.0
    span = span if span > 0 else 1.0
    t = np.clip(np.nan_to_num(diff, nan=0.0) / span, -1.0, 1.0)
    rgb = np.empty(diff.shape + (3,), dtype=np.uint8)
    pos, neg = np.clip(t, 0, 1), np.clip(-t, 0, 1)
    rgb[..., 0] = (255 * (1.0 - neg)).astype(np.uint8)   # red channel
    rgb[..., 1] = (255 * (1.0 - np.maximum(pos, neg))).astype(np.uint8)
    rgb[..., 2] = (255 * (1.0 - pos)).astype(np.uint8)   # blue channel
    rgb[~valid] = NODATA_RGB
    Image.fromarray(rgb, mode="RGB").save(path)
    return {
        "shape_rows_cols": [int(diff.shape[0]), int(diff.shape[1])],
        "valid_fraction": float(valid.mean()),
        "nodata_pixels": int((~valid).sum()),
        "colour_span_plus_minus": span,
        "colour_span_basis": "99th percentile of |difference| over valid pixels",
        "valid_mean_abs_difference": float(np.nanmean(np.abs(inside)))
        if inside.size else None,
        "valid_median_signed_difference": float(np.nanmedian(inside))
        if inside.size else None,
    }


def emit_product(args) -> None:
    """Write the registered product and match points for ONE recorded edge.

    Reads only: the acquisition manifest, the recorded registration artefact,
    the certified overlay asset, the archive index geometry, and the tiles.
    Writes only into ``experiments/<outdir>/products/``. Nothing existing is
    read-modify-written.
    """
    from PIL import Image  # noqa: F401  - fail early if pillow is absent

    man = json.loads(
        (ROOT / "data" / "manifests" / args.manifest).read_text(encoding="utf-8"))
    reg_path = ROOT / args.registration
    rec = json.loads(reg_path.read_text(encoding="utf-8"))
    asset_path = ROOT / args.overlay_asset
    asset = json.loads(asset_path.read_text(encoding="utf-8"))

    edge_rec = next((e for e in rec["edges"] if e["edge"] == args.edge), None)
    if edge_rec is None:
        raise SystemExit(
            f"edge {args.edge!r} is not in {args.registration}; available: "
            + ", ".join(e["edge"] for e in rec["edges"]))
    edge_asset = next((e for e in asset["edges"] if e["edge"] == args.edge), None)
    if edge_asset is None:
        raise SystemExit(f"edge {args.edge!r} is not in {args.overlay_asset}")

    # -- refuse to emit a product for an edge the pre-registered rule REJECTED.
    # A registered product implies the registration was accepted; producing one
    # for a rejected edge would contradict the verdict beside it.
    if edge_rec["n_inliers_failure_flag"]:
        raise SystemExit(
            f"edge {args.edge} has {edge_rec['n_inliers']} inliers and FAILS the "
            f"pre-registered rule (n_inliers <= {N_INLIERS_FAILURE_RULE}, D-023). "
            "No registered product is emitted for a rejected edge.")
    if edge_rec.get("transform_matrix") is None:
        raise SystemExit(f"edge {args.edge} has no recorded transform")

    src_id, dst_id = args.edge.split(" -> ")
    tiles = {t["pdsid"]: t for t in man["tiles"]}
    for pid in (src_id, dst_id):
        if pid not in tiles:
            raise SystemExit(f"{pid} is not in {args.manifest}")

    geometry: dict = {}
    for name in args.geometry:
        p = ROOT / "data" / "manifests" / name
        if p.exists():
            geometry.update(json.loads(p.read_text(encoding="utf-8"))["products"])

    k = int(rec["baseline"]["downsample"])
    tf = affine(np.asarray(edge_rec["transform_matrix"], float)[:2, :])

    # -- images, through the pipeline's own preprocessing, in its own order ---
    def load(pid: str) -> np.ndarray:
        p = ROOT / tiles[pid]["tile_npy"].replace("\\", "/")
        if not p.exists():
            raise SystemExit(
                f"tile {p.relative_to(ROOT)} is not on disk. The decoded tiles "
                "are gitignored (~166 MB); re-fetch them with the byte ranges "
                "and SHA-256 in data/manifests/.")
        return normalise(decimate(np.load(p), k))

    img_src, img_dst = load(src_id), load(dst_id)

    out_dir = ROOT / "experiments" / args.outdir / "products"
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = args.product_tag
    paths = {
        "correspondences": out_dir / f"correspondences_{tag}.csv",
        "registered": out_dir / f"registered_{tag}.png",
        "difference": out_dir / f"difference_{tag}.png",
        "provenance": out_dir / f"PRODUCT_PROVENANCE_{tag}.json",
    }
    existing = [p.name for p in paths.values() if p.exists()]
    if existing and not args.overwrite_products:
        raise SystemExit(
            f"{existing} already exist under {out_dir.relative_to(ROOT)}; pass "
            "--overwrite-products to replace them (integrity rule 4)")

    # -- 1. match points, with ground coordinates from the archive corners ----
    src_pts = np.asarray(edge_asset["correspondences"]["src"], float)
    dst_pts = np.asarray(edge_asset["correspondences"]["dst"], float)
    inliers = np.asarray(edge_asset["correspondences"]["inlier"], bool)
    if not (len(src_pts) == len(dst_pts) == len(inliers)):
        raise SystemExit("overlay asset correspondence arrays disagree in length")
    if int(inliers.sum()) != int(edge_rec["n_inliers"]):
        raise SystemExit(
            f"overlay asset has {int(inliers.sum())} inliers but the recorded "
            f"artefact says {edge_rec['n_inliers']}; the two disagree and no "
            "product is emitted from them")

    residuals = transfer_residuals(tf, src_pts, dst_pts)

    win = {pid: TileWindow(line0=tiles[pid]["line0"],
                           sample0=tiles[pid]["sample0"],
                           n_lines=tiles[pid]["n_lines"],
                           n_samples=tiles[pid]["n_samples"],
                           decimation=k) for pid in (src_id, dst_id)}
    corners = {pid: _corners_for(pid, geometry) for pid in (src_id, dst_id)}

    import csv
    with paths["correspondences"].open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([f"# {PRODUCT_CLASS_STATEMENT}"])
        w.writerow([f"# edge: {args.edge}  (source -> reference)"])
        w.writerow([f"# transform: read from {args.registration}, model "
                    f"{rec['baseline']['model']}, NOT re-estimated here"])
        w.writerow([f"# points: read from {args.overlay_asset} "
                    f"(certified against the artefact)"])
        w.writerow(["# src/dst line,sample are FULL-FRAME 0-based pixel "
                    f"coordinates (decimation {k}x undone)"])
        w.writerow(["# ground lon/lat: FrameCorners.lonlat_at on each product's "
                    "own named archive corners, east-positive degrees"])
        w.writerow(["# residual_px: ||T(src) - dst|| in DECIMATED reference "
                    "pixels. A FIT residual, not an accuracy (D-003)"])
        w.writerow([
            "index", "is_inlier", "residual_px",
            "src_line", "src_sample", "src_lon_deg", "src_lat_deg",
            "dst_line", "dst_sample", "dst_lon_deg", "dst_lat_deg",
            "src_tile_x", "src_tile_y", "dst_tile_x", "dst_tile_y",
        ])
        for i in range(len(src_pts)):
            sx, sy = float(src_pts[i, 0]), float(src_pts[i, 1])
            dx, dy = float(dst_pts[i, 0]), float(dst_pts[i, 1])
            sl, ss = win[src_id].to_frame(sy, sx)   # (row, col) -> (line, sample)
            dl, ds = win[dst_id].to_frame(dy, dx)
            slon, slat = corners[src_id].lonlat_at(sl, ss)
            dlon, dlat = corners[dst_id].lonlat_at(dl, ds)
            w.writerow([i, int(bool(inliers[i])), f"{residuals[i]:.6f}",
                        f"{sl:.3f}", f"{ss:.3f}", f"{slon:.8f}", f"{slat:.8f}",
                        f"{dl:.3f}", f"{ds:.3f}", f"{dlon:.8f}", f"{dlat:.8f}",
                        f"{sx:.4f}", f"{sy:.4f}", f"{dx:.4f}", f"{dy:.4f}"])

    # -- 2. the registered product: source warped into the reference grid ----
    # `warp` takes the FORWARD transform (contract C5) and fills outside the
    # source with NaN by design, so the invalid region stays unmistakable.
    warped, valid = warp(img_src, tf, out_shape=img_dst.shape, cval=np.nan)
    if np.isfinite(warped[~valid]).any():
        raise SystemExit(
            "warp returned finite values outside the source footprint; the "
            "no-data region would be indistinguishable from lunar shadow (E-003)")
    reg_stats = _grey_png(warped, valid, paths["registered"])

    # -- an independent cross-check that costs nothing ----------------------
    # The fraction of the reference grid the warped source covers is a
    # PIXEL-domain quantity: it comes from the estimated transform and the tile
    # shapes. The archive's overlap artefact reports the same fraction from
    # CORNER GEOMETRY ALONE -- no pixel, no matcher. If the registration is
    # broadly right the two agree; if it is catastrophically wrong they need
    # not. Reported as a descriptive consistency check, NOT as a verdict input
    # and NOT as an accuracy: it discriminates coverage, not alignment.
    coverage_check: dict = {"available": False}
    ov_path = ROOT / args.overlap_artefact
    if ov_path.exists():
        ov = json.loads(ov_path.read_text(encoding="utf-8"))
        for case in ov.get("cases", []):
            prods = case.get("products", [])
            if set(prods) == {src_id, dst_id}:
                prim = case["primary"]
                key = ("fraction_of_a" if prods[0] == dst_id else "fraction_of_b")
                geom_fraction = float(prim[key])
                coverage_check = {
                    "available": True,
                    "warp_valid_fraction": reg_stats["valid_fraction"],
                    "archive_geometry_fraction_of_reference_tile": geom_fraction,
                    "absolute_difference": abs(reg_stats["valid_fraction"]
                                               - geom_fraction),
                    "source_case": case["case"],
                    "source_artefact": args.overlap_artefact,
                    "note": ("The warp coverage is a pixel-domain quantity from "
                             "the estimated transform; the archive fraction is "
                             "from corner geometry with no pixel read and no "
                             "matcher. Descriptive only -- it discriminates "
                             "COVERAGE, not alignment, and is not a verdict "
                             "input."),
                    "discriminating_power": (
                        "NONE on this edge, and that is stated rather than "
                        "counted as a confirmation. Both quantities are "
                        "SATURATED at 1.0 -- the reference tile lies wholly "
                        "inside the source footprint -- so no possible "
                        "disagreement could have shown up here and the "
                        "agreement to 1e-16 confirms nothing. This is E-027's "
                        "lesson applied to a check this script itself adds: "
                        "before calling an agreement a confirmation, ask what "
                        "result would have falsified it. The check becomes "
                        "informative only on an edge where the fraction is "
                        "strictly below 1."
                        if min(reg_stats["valid_fraction"], geom_fraction) > 0.999
                        else "The fraction is below saturation, so a "
                             "disagreement was possible and did not occur."),
                }
                break

    # -- 3. difference, over valid pixels only -------------------------------
    diff = np.where(valid, warped - img_dst, np.nan)
    diff_stats = _diff_png(diff, valid, paths["difference"])

    # -- 4. provenance -------------------------------------------------------
    prov = {
        "product_class": PRODUCT_CLASS_STATEMENT,
        "what_this_is": (
            "The problem statement's 'registered product' and 'corresponding "
            "match points' deliverables, for the one real edge that passes the "
            "pre-registered inlier rule."),
        "what_this_is_NOT": [
            "NOT evidence that the registration is correct. No ground truth "
            "exists for these products; REAL-DATA-04 section 15 Q3 classes this "
            "edge B (corroborated), not A (verified).",
            "NOT an accuracy measurement. residual_px is a FIT residual, "
            "measured on the points that determined the transform (D-003).",
            "The difference image is NOT a registration error map. The two "
            "frames differ by 11.73 deg of solar incidence, so real radiometric "
            "difference is EXPECTED and dominates. Do not read its magnitude as "
            "misalignment.",
            "NOT Chandrayaan-2 and NOT multi-modal. Both frames are LRO NAC.",
        ],
        "nothing_was_estimated_here": (
            "No matcher ran. The transform is read from the recorded artefact "
            "and the correspondences from the certified overlay asset, so this "
            "mode cannot produce a number that disagrees with the stage."),
        "edge": args.edge,
        "source_product": src_id,
        "reference_product": dst_id,
        "sources": {
            "registration_artefact": args.registration,
            "overlay_asset": args.overlay_asset,
            "acquisition_manifest": f"data/manifests/{args.manifest}",
            "index_geometry": [f"data/manifests/{n}" for n in args.geometry],
        },
        "source_sha256": {
            args.registration: _sha256(reg_path),
            args.overlay_asset: _sha256(asset_path),
        },
        "baseline_as_recorded": rec["baseline"],
        "transform_matrix": edge_rec["transform_matrix"],
        "recorded_statistics": {
            key: edge_rec[key] for key in
            ("n_keypoints_src", "n_keypoints_dst",
             "n_putative_mutual_ratio_matches", "n_inliers", "inlier_ratio",
             "fit_rmse_px", "coverage_max_uncovered_disc_ratio",
             "coverage_occupancy") if key in edge_rec
        },
        "match_points": {
            "n_rows": int(len(src_pts)),
            "n_inliers": int(inliers.sum()),
            "residual_px_definition":
                "||T(src) - dst|| in decimated reference pixels; a FIT residual",
            "inlier_residual_max_px": float(residuals[inliers].max())
            if inliers.any() else None,
            "ground_coordinates":
                "FrameCorners.lonlat_at on each product's own named archive "
                "corners; corner naming verified per product from its PDS4 "
                "disp:Display_Direction",
        },
        "registered_image": reg_stats,
        "difference_image": diff_stats,
        "coverage_cross_check": coverage_check,
        "nodata_convention": (
            "Magenta (255, 0, 255) marks pixels outside the warped source. "
            "Zero-fill is not used: near-zero is a legal lunar value and would "
            "be indistinguishable from shadow (E-003)."),
        "licence": man.get("licence"),
        "generated_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    paths["provenance"].write_text(json.dumps(prov, indent=2), encoding="utf-8")

    print(f"== registered product for {args.edge} ==")
    print(f"   {PRODUCT_CLASS_STATEMENT}")
    print(f"   NOTHING was estimated here: transform read from "
          f"{args.registration}")
    for name, p in paths.items():
        print(f"   {name:16s} {p.relative_to(ROOT)}")
    print(f"   match points     {len(src_pts)} rows, {int(inliers.sum())} inliers")
    print(f"   registered       {reg_stats['shape_rows_cols']}, "
          f"valid {reg_stats['valid_fraction']:.4f}, "
          f"nodata {reg_stats['nodata_pixels']} px")
    print(f"   difference       mean|d| {diff_stats['valid_mean_abs_difference']:.4f} "
          f"over valid pixels -- radiometric, NOT a registration error map")


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

    # -- --emit-product: deliverables from RECORDED evidence, no estimation --
    ap.add_argument("--emit-product", action="store_true",
                    help="emit the registered product and match points for one "
                         "already-recorded edge and exit. Runs NO matcher, "
                         "estimates nothing, and writes only into "
                         "experiments/<outdir>/products/")
    ap.add_argument("--edge",
                    default="nac.m1299958135lc -> nac.m1271742202lc",
                    help="edge to emit, as it appears in the registration "
                         "artefact. Default is REAL-DATA-04's D -> A, the one "
                         "real edge that passes the pre-registered inlier rule")
    ap.add_argument("--registration",
                    default="experiments/REAL-DATA-04/loop_closure_real_data_04.json",
                    help="recorded artefact supplying the transform. It is READ "
                         "ONLY and is never rewritten")
    ap.add_argument("--overlay-asset",
                    default="src/siim/demo/assets/real_data_04.json",
                    help="certified overlay asset supplying the correspondence "
                         "coordinates, which the registration artefact does not "
                         "store")
    ap.add_argument("--geometry", action="append", default=None,
                    help="index-geometry manifest name(s) for the archive "
                         "corners; repeatable")
    ap.add_argument("--product-tag", default="D_A",
                    help="suffix for the emitted filenames")
    ap.add_argument("--overwrite-products", action="store_true",
                    help="replace existing products rather than refusing "
                         "(integrity rule 4)")
    args = ap.parse_args()

    if args.emit_product:
        if args.geometry is None:
            args.geometry = ["real_pair_index_geometry.json",
                             "real_frame_d_selected_index_geometry.json",
                             "real_frame_d_candidates_index_geometry.json"]
        emit_product(args)
        return

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
