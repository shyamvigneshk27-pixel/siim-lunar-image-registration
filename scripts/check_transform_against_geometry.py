"""REAL-DATA-03: compare an estimated transform against archive geometry.

Run:  python scripts/check_transform_against_geometry.py \\
          --manifest real_triplet_geo_manifest.json \\
          --registration experiments/REAL-DATA-03/loop_closure_triplet.json

**This is a bound, not a ground truth, and the distinction is the whole point.**

The archive's named frame corners give an independent map from a pixel of one
tile to a pixel of another: tile A pixel -> ground -> tile B pixel. It reads no
image data and would return the same answer if both tiles were blank, so it is
independent of the matcher in exactly the way REAL-DATA-02's overlap evidence
is. What it is *not* is accurate: corner coordinates are quoted to 0.01 deg,
about 150 m, which is ~165 full-frame pixels at NAC scale. The prediction is
therefore usable at the scale of **hundreds of pixels** and no finer.

That resolution is still decisive for the failure mode this project exists to
catch. E-008 is a registration reported at a fit residual of 1e-12 px while
being hundreds of pixels wrong; a bound good to ~100 px separates that from a
plausible answer outright. It cannot, and does not, certify sub-pixel accuracy.

The uncertainty is propagated rather than asserted: the corner coordinates are
perturbed by their quantisation over many draws and the disagreement is
reported as an interval, exactly as in ``verify_tile_overlap.py``.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from siim.geometry import Transform, endpoint_error, estimate  # noqa: E402
from siim.ingest.footprint import (  # noqa: E402
    FrameCorners,
    TileWindow,
    predicted_correspondences,
)
from siim.ingest.pds4 import parse_display_direction  # noqa: E402

DATA = ROOT / "data"

#: Same quantisation model as REAL-DATA-02: corner coordinates are published to
#: two decimals, so each carries independent uniform rounding error.
CORNER_QUANTISATION_DEG = 0.005
N_MONTE_CARLO = 200
MC_SEED = 20260826
GRID = 9

#: How far beyond the archive's own uncertainty a disagreement must sit before
#: it is called INCONSISTENT rather than merely unexplained. A **provisional
#: cut, not a measured threshold** (the same status as D-029's 75 deg): the
#: quantisation model is itself approximate, and the bilinear ground map
#: carries a residual of its own. Between 1x and 3x the floor the answer is
#: INCONCLUSIVE, which is a result and is reported as one -- calling a 1.8x
#: excess "INCONSISTENT" would be E-024 all over again.
INCONSISTENT_MARGIN = 3.0

#: Residual of the bilinear ground map, as a fraction of frame extent. Measured
#: in REAL-DATA-02: corner-implied pixel scale agrees with the archive's
#: SPICE-derived SCALED_PIXEL_HEIGHT/WIDTH to within 1.2% over 8 comparisons.
#: Added to the discrimination floor so the floor is not purely a quantisation
#: figure while the prediction has a second error source.
BILINEAR_MODEL_RESIDUAL = 0.012


def load_geometry(names: list[str]) -> dict:
    products: dict = {}
    for name in names:
        path = DATA / "manifests" / name
        if not path.exists():
            raise SystemExit(f"missing index geometry {path}")
        products.update(
            json.loads(path.read_text(encoding="utf-8"))["products"])
    return products


def corners_for(pdsid: str, products: dict) -> FrameCorners:
    rec = products.get(pdsid)
    if rec is None:
        raise SystemExit(f"{pdsid} has no archive corner geometry")
    label = next((ROOT / "data" / "metadata").rglob(f"{pdsid}.xml"), None)
    if label is None:
        raise SystemExit(f"no stored PDS4 label for {pdsid}")
    disp = parse_display_direction(label.read_text(encoding="utf-8"))
    if (disp["vertical_axis"], disp["vertical_direction"]) != (
            "Line", "Top to Bottom"):
        raise SystemExit(f"{pdsid}: unexpected Display_Direction {disp}")
    f = rec["fields"]

    def c(corner: str) -> tuple[float, float]:
        return (float(f[corner + "_LONGITUDE"]), float(f[corner + "_LATITUDE"]))

    return FrameCorners(c("UPPER_LEFT"), c("UPPER_RIGHT"),
                        c("LOWER_LEFT"), c("LOWER_RIGHT"),
                        int(f["IMAGE_LINES"]), int(f["LINE_SAMPLES"]))


def jitter(corners: FrameCorners, rng: np.random.Generator) -> FrameCorners:
    q = CORNER_QUANTISATION_DEG

    def j(p):
        return (p[0] + rng.uniform(-q, q), p[1] + rng.uniform(-q, q))

    return FrameCorners(j(corners.upper_left), j(corners.upper_right),
                        j(corners.lower_left), j(corners.lower_right),
                        corners.lines, corners.samples)


def scaled_pixel_scales(pdsid: str, products: dict) -> tuple[float, float] | None:
    """``(cross_track, along_track)`` ground sampling in m/px, from the archive.

    ``SCALED_PIXEL_WIDTH`` is the cross-scan and ``SCALED_PIXEL_HEIGHT`` the
    down-scan resolution at the observation centre. Both are derived by the
    archive from SPICE and are **independent of the corner polygon** -- which
    is what makes them a second, sharper test than the corner-derived
    prediction. They are quoted to two decimals, so each carries ~0.6% of
    quantisation at these values.
    """
    f = products.get(pdsid, {}).get("fields", {})
    try:
        return float(f["SCALED_PIXEL_WIDTH"]), float(f["SCALED_PIXEL_HEIGHT"])
    except (KeyError, TypeError, ValueError):
        return None


def scale_cross_check(src_id: str, dst_id: str, products: dict,
                      est_matrix) -> dict:
    """Does the recovered scale match the archive's own pixel scales?

    A transform mapping A's pixels onto B's must scale by the ratio of their
    ground samplings: one A pixel covers ``res_a`` metres, which is
    ``res_a / res_b`` B pixels. The matcher never saw ``SCALED_PIXEL_*``.

    Reported as the two singular values of the linear part against the two
    predicted scales, sorted. That identification is exact only for a
    similarity, so the recovered rotation and anisotropy are reported beside it
    and a caller can see how far from a similarity the estimate is.
    """
    ra = scaled_pixel_scales(src_id, products)
    rb = scaled_pixel_scales(dst_id, products)
    out: dict = {"available": bool(ra and rb)}
    if not (ra and rb):
        out["note"] = "SCALED_PIXEL_WIDTH/HEIGHT absent for one product"
        return out
    predicted = sorted((ra[0] / rb[0], ra[1] / rb[1]))
    lin = np.asarray(est_matrix, float)[:2, :2]
    sv = sorted(float(x) for x in np.linalg.svd(lin, compute_uv=False))
    out.update({
        "src_scaled_pixel_m": list(ra),
        "dst_scaled_pixel_m": list(rb),
        "predicted_scales_sorted": predicted,
        "estimated_singular_values_sorted": sv,
        "relative_error": [abs(sv[i] - predicted[i]) / predicted[i]
                           for i in range(2)],
        "estimated_rotation_deg": float(np.degrees(
            np.arctan2(lin[1, 0], lin[0, 0]))),
        "estimated_anisotropy": float(sv[1] / sv[0]) if sv[0] else float("inf"),
        "predicted_anisotropy": float(predicted[1] / predicted[0]),
        "quantisation_relative": 0.005 / min(ra + rb),
        "note": (
            "SCALED_PIXEL_* are quoted to two decimals, so the predicted ratio "
            "carries roughly 0.8% of quantisation. Agreement below that is "
            "agreement; the test discriminates a wrong SCALE, not a wrong "
            "translation."),
    })
    tol = 3.0 * out["quantisation_relative"]
    out["agrees_within_quantisation"] = bool(
        max(out["relative_error"]) <= tol)
    out["tolerance_used"] = tol
    return out


def predict(ca, wa, cb, wb, model: str):
    src, dst = predicted_correspondences(ca, wa, cb, wb, grid=GRID)
    if len(src) < 6:
        return None, len(src)
    res = estimate(src, dst, model)
    return (res.transform if res.ok else None), len(src)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--registration", required=True,
                    help="a loop_closure_*.json (edges) or registration_*.json")
    ap.add_argument("--extra-geometry", action="append", default=[])
    ap.add_argument("--geometry", default="real_pair_index_geometry.json")
    ap.add_argument("--model", default="affine")
    ap.add_argument("--downsample", type=int, default=2)
    ap.add_argument("--outdir", default="REAL-DATA-03")
    ap.add_argument("--out", default="transform_vs_geometry.json")
    args = ap.parse_args()

    out_dir = ROOT / "experiments" / args.outdir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / args.out
    if out_path.exists():
        raise SystemExit(
            f"{out_path.relative_to(ROOT)} already exists; choose a new --out "
            "(integrity rule 4)")

    products = load_geometry([args.geometry, *args.extra_geometry])
    man = json.loads(
        (DATA / "manifests" / args.manifest).read_text(encoding="utf-8"))
    tiles = {t["pdsid"]: t for t in man["tiles"]}

    reg = json.loads((ROOT / args.registration).read_text(encoding="utf-8"))
    if "edges" in reg:
        estimated = {e["edge"]: e for e in reg["edges"]}
    else:
        a, b = man["pair"][0], man["pair"][1]
        estimated = {f"{a} -> {b}": reg}

    print("== estimated transform vs ARCHIVE GEOMETRY ==")
    print("A BOUND, NOT A GROUND TRUTH. Corner coordinates are quoted to "
          "0.01 deg (~150 m ~ 165 full-frame px),")
    print("so this separates a plausible answer from a catastrophically wrong "
          "one and certifies nothing finer.\n")

    rows = []
    for name, edge in estimated.items():
        src_id, dst_id = [x.strip() for x in name.split("->")]
        ta, tb = tiles[src_id], tiles[dst_id]
        wa = TileWindow(ta["line0"], ta["sample0"], ta["n_lines"],
                        ta["n_samples"], args.downsample)
        wb = TileWindow(tb["line0"], tb["sample0"], tb["n_lines"],
                        tb["n_samples"], args.downsample)
        ca, cb = corners_for(src_id, products), corners_for(dst_id, products)

        predicted, n_pts = predict(ca, wa, cb, wb, args.model)
        row = {
            "edge": name,
            "n_predicted_correspondences": n_pts,
            "n_inliers_reported": edge.get("n_inliers"),
        }
        if predicted is None:
            row["status"] = ("archive geometry does not constrain this edge: "
                             f"only {n_pts} of {GRID * GRID} grid points land "
                             "inside both frames")
            rows.append(row)
            print(f"{name}\n   {row['status']}\n")
            continue

        row["predicted_transform_matrix"] = np.asarray(
            predicted.matrix).tolist()
        mat = edge.get("transform_matrix")
        if mat is None:
            row["status"] = "no transform was estimated for this edge"
            rows.append(row)
            print(f"{name}\n   {row['status']}\n")
            continue
        est = Transform(np.asarray(mat, float), args.model)
        row["estimated_transform_matrix"] = np.asarray(est.matrix).tolist()

        err = endpoint_error(est, predicted, wa.shape, step=16)
        row["disagreement_px"] = {
            "median": err.median, "p90": err.p90, "max": err.max,
            "n_points": err.n_points,
        }

        # scale, compared against a number the matcher never saw
        def svals(m):
            return tuple(float(x) for x in np.linalg.svd(
                np.asarray(m)[:2, :2], compute_uv=False))

        row["singular_values_estimated"] = svals(est.matrix)
        row["singular_values_predicted"] = svals(predicted.matrix)

        rng = np.random.default_rng(MC_SEED)
        draws = []
        for _ in range(N_MONTE_CARLO):
            p_j, _ = predict(jitter(ca, rng), wa, jitter(cb, rng), wb,
                             args.model)
            if p_j is None:
                continue
            draws.append(endpoint_error(est, p_j, wa.shape, step=32).median)
        if draws:
            row["disagreement_px_p5_p95"] = [float(np.percentile(draws, 5)),
                                             float(np.percentile(draws, 95))]

        # The floor below which this comparison cannot discriminate: how far
        # the PREDICTION itself moves under the corner quantisation.
        rng2 = np.random.default_rng(MC_SEED + 1)
        spread = []
        for _ in range(N_MONTE_CARLO):
            p_j, _ = predict(jitter(ca, rng2), wa, jitter(cb, rng2), wb,
                             args.model)
            if p_j is not None:
                spread.append(endpoint_error(p_j, predicted, wa.shape,
                                             step=32).median)
        quant = float(np.percentile(spread, 95)) if spread else float("nan")
        diag = float(np.hypot(*wa.shape)) / 2.0
        model_term = BILINEAR_MODEL_RESIDUAL * diag
        floor = quant + model_term
        row["discrimination_floor_px"] = {
            "quantisation_p95": quant,
            "bilinear_model_term": model_term,
            "total": floor,
        }
        row["excess_over_floor"] = (float(err.median / floor)
                                    if floor > 0 else float("inf"))
        lo = (row.get("disagreement_px_p5_p95") or [err.median])[0]
        if err.median <= floor:
            verdict = ("CONSISTENT WITH ARCHIVE GEOMETRY: the disagreement is "
                       "fully explained by the archive's own uncertainty")
        elif lo > INCONSISTENT_MARGIN * floor:
            verdict = ("INCONSISTENT WITH ARCHIVE GEOMETRY: the disagreement "
                       "exceeds the archive's uncertainty by more than "
                       f"{INCONSISTENT_MARGIN:g}x even at its optimistic end")
        else:
            verdict = ("INCONCLUSIVE: the disagreement is larger than the "
                       "archive's uncertainty explains but within "
                       f"{INCONSISTENT_MARGIN:g}x of it. This bound cannot "
                       "decide the edge; it can only say the answer is not "
                       "catastrophically wrong")
        row["verdict"] = verdict
        row["scale_cross_check"] = scale_cross_check(
            src_id, dst_id, products, est.matrix)
        rows.append(row)

        print(f"{name}   ({edge.get('n_inliers')} inliers)")
        print(f"   predicted singular values "
              f"{row['singular_values_predicted'][0]:.5f} "
              f"{row['singular_values_predicted'][1]:.5f}")
        print(f"   estimated singular values "
              f"{row['singular_values_estimated'][0]:.5f} "
              f"{row['singular_values_estimated'][1]:.5f}")
        print(f"   disagreement median {err.median:12.3f} px   p90 "
              f"{err.p90:.3f}   max {err.max:.3f}")
        if "disagreement_px_p5_p95" in row:
            lo, hi = row["disagreement_px_p5_p95"]
            print(f"   p5-p95 over corner quantisation: {lo:.3f} .. {hi:.3f} px")
        print(f"   discrimination floor {floor:.3f} px "
              f"(quantisation p95 {quant:.1f} + bilinear model "
              f"{model_term:.1f})")
        print(f"   excess over floor: {row['excess_over_floor']:.2f}x")
        sc = row["scale_cross_check"]
        if sc.get("available"):
            print("   scale vs archive SCALED_PIXEL (a field the matcher never "
                  "saw):")
            print(f"      predicted {sc['predicted_scales_sorted'][0]:.5f} "
                  f"{sc['predicted_scales_sorted'][1]:.5f}   estimated "
                  f"{sc['estimated_singular_values_sorted'][0]:.5f} "
                  f"{sc['estimated_singular_values_sorted'][1]:.5f}")
            print(f"      relative error "
                  f"{sc['relative_error'][0] * 100:.2f}% / "
                  f"{sc['relative_error'][1] * 100:.2f}%   "
                  f"tolerance {sc['tolerance_used'] * 100:.2f}%   "
                  f"AGREES: {sc['agrees_within_quantisation']}")
        print(f"   -> {row['verdict']}\n")

    report = {
        "stage": "REAL-DATA-03",
        "check": "estimated transform vs archive corner geometry",
        "generated_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "status": (
            "INDEPENDENT BOUND, NOT GROUND TRUTH. The prediction reads no "
            "image data and uses no matcher output; it is limited by the "
            "0.01 deg quantisation of the archive corner coordinates (~150 m "
            "~ 165 full-frame px). It separates a plausible registration from "
            "a catastrophically wrong one. It certifies NO accuracy, and in "
            "particular NO sub-pixel accuracy."),
        "manifest": args.manifest,
        "registration": args.registration,
        "model": args.model,
        "downsample": args.downsample,
        "monte_carlo": {"n_draws": N_MONTE_CARLO, "seed": MC_SEED,
                        "corner_quantisation_deg": CORNER_QUANTISATION_DEG},
        "edges": rows,
    }
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"report: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
