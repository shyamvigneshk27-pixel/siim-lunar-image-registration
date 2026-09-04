"""REAL-DATA-08 -- NAC <-> Mini-RF radar (15 m) and NAC <-> WAC (100 m) proxies.

Pre-registered in ``docs/stages/REAL-DATA-08_multimodal_proxies.md`` Part 1
(commit d475124). Engines B1, B7, B4L; rule ``n_inliers <= 8``; geometry bound
from the corner map (NAC) and the map product's own projection.

    python scripts/run_real_data_08.py
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siim.baselines import learned_available, run_baseline  # noqa: E402
from siim.evaluation.coverage import coverage_metrics  # noqa: E402
from siim.geometry import Transform, endpoint_error, estimate  # noqa: E402
from siim.ingest.lola_dem import _lonlat_grid  # noqa: E402
from siim.ingest.mapgrid import load_map_block  # noqa: E402
from siim.ingest.orientation import north_up  # noqa: E402

_spec = importlib.util.spec_from_file_location("_exp007", ROOT / "scripts" / "run_exp007.py")
_e7 = importlib.util.module_from_spec(_spec)
sys.modules["_exp007"] = _e7
_spec.loader.exec_module(_e7)

STAGE = "REAL-DATA-08"
DATA = ROOT / "data"
OUT = ROOT / "experiments" / STAGE
RULE = _e7.N_INLIERS_FAILURE_RULE
BASE = {"model": "affine", "ransac_threshold_px": 3.0, "seed": 0}
PROXIES = {
    "minirf": {"manifest": "minirf_lsz_02951_2s1_block_mare_serenitatis.json", "log": True},
    "wac": {"manifest": "wac_global_e300n0450_100m_block_mare_serenitatis.json", "log": False},
}
#: NAC sources: recorded tiles (k chosen to land near the proxy's sampling) and
#: the EXP-007 long windows where present.
SOURCES = [("real_triplet_geo_manifest.json", "RD03"), ("real_quad_d_geo_manifest.json", "RD04"),
           ("exp007_long_triplet_abc_manifest.json", "RD03-long"),
           ("exp007_long_triplet_abd_manifest.json", "RD04-long")]
ENGINES = {"b1": "B1", "b7": "B7", "lg": "B4L"}


def stretch(a):
    return _e7.stretch(a)


def predicted_map(ctx, k: int, block, margin_px: int):
    """Corner-map prediction NAC tile (decimated, north-up later) -> block pixels,
    plus the block window to cut. Returns (affine G, block crop origin, crop)."""
    t = ctx.tile
    w = ctx.window(k)
    h, wdt = w.shape
    gy, gx = np.mgrid[0:h:max(1, h // 8), 0:wdt:max(1, wdt // 8)]
    pts = np.column_stack([gx.ravel(), gy.ravel()]).astype(float)
    lines = np.array([w.to_frame(y, x)[0] for x, y in pts])
    samples = np.array([w.to_frame(y, x)[1] for x, y in pts])
    lon, lat = _lonlat_grid(ctx.corners, lines, samples)
    xy = block.block_xy_of_lonlat(lon, lat)
    x0 = int(np.floor(xy[:, 0].min())) - margin_px
    y0 = int(np.floor(xy[:, 1].min())) - margin_px
    x1 = int(np.ceil(xy[:, 0].max())) + margin_px + 1
    y1 = int(np.ceil(xy[:, 1].max())) + margin_px + 1
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(block.data.shape[1], x1), min(block.data.shape[0], y1)
    crop = block.data[y0:y1, x0:x1]
    res = estimate(pts, xy - np.array([x0, y0]), "affine")
    return (res.transform if res.ok else None), (x0, y0), crop


def run_pair(ctx, k: int, name: str, block, log: bool, engines: list[str]) -> list[dict]:
    img = ctx.img(k)
    t = ctx.tile
    nu = north_up(img, ctx.corners, line=t["line0"] + (t["n_lines"] - 1) / 2,
                  sample=t["sample0"] + (t["n_samples"] - 1) / 2)
    g, (x0, y0), crop = predicted_map(ctx, k, block, margin_px=40)
    if g is None or crop.size == 0:
        return [{"proxy": name, "frame": ctx.letter, "excluded": "no geometry prediction"}]
    ref = np.log10(np.clip(crop, 1e-6, None)) if log else crop
    ref = stretch(np.where(np.isfinite(ref), ref, np.nan))
    # prediction in NORTH-UP source pixels: G_nu = G o R^-1
    g_nu = g @ nu.inverse
    rows = []
    for eng in engines:
        t0 = time.perf_counter()
        try:
            res = run_baseline(ENGINES[eng], nu.image, ref, model=BASE["model"],
                               ransac_threshold=BASE["ransac_threshold_px"], seed=BASE["seed"])
        except Exception as exc:  # noqa: BLE001 -- an engine failure is a result here
            rows.append({"proxy": name, "frame": ctx.letter, "engine": eng, "error": repr(exc)[:200]})
            continue
        mask = np.asarray(res.inlier_mask, bool) if np.size(res.inlier_mask) else np.zeros(0, bool)
        n_in = int(mask.sum())
        rec = {"proxy": name, "frame": ctx.letter, "pdsid": ctx.pdsid, "engine": eng,
               "decimation": k, "src_gsd_m": k * ctx.scaled_pixel_m,
               "ref_gsd_m": float(np.mean(block.metres_per_pixel)),
               "src_shape": list(nu.image.shape), "ref_shape": list(ref.shape),
               "n_keypoints_src": int(len(res.src_features)), "n_keypoints_dst": int(len(res.dst_features)),
               "n_putative": int(res.matches.src_points.shape[0]), "n_inliers": n_in,
               "fit_rmse_px": float(res.ransac.inlier_rmse), "fit_rmse_is_not_accuracy": True,
               "pass": n_in > RULE, "wall_s": time.perf_counter() - t0,
               "nac_incidence_deg": ctx.incidence_published}
        if n_in >= 3:
            cov = coverage_metrics(res.matches.src_points[mask], nu.image.shape)
            rec["coverage_max_uncovered_disc_ratio"] = float(cov.max_uncovered_disc_ratio)
        if res.transform is not None:
            err = endpoint_error(res.transform, g_nu, nu.image.shape, step=16)
            floor_px = 150.0 / float(np.mean(block.metres_per_pixel)) + 0.012 * np.hypot(*nu.image.shape) / 2
            rec["geometry"] = {"disagreement_px_median": err.median, "p90": err.p90,
                               "floor_px": floor_px, "excess": err.median / floor_px,
                               "verdict": ("CONSISTENT" if err.median <= floor_px else
                                           "INCONSISTENT" if err.median > 3 * floor_px else "INCONCLUSIVE"),
                               "floor_note": "150 m corner quantisation in reference px + 1.2% bilinear term"}
            rec["transform_matrix_northup_to_block"] = np.asarray(res.transform.matrix).tolist()
        else:
            rec["geometry"] = {"verdict": "no transform"}
        rec["wrong_pass"] = bool(rec["pass"] and rec["geometry"]["verdict"] == "INCONSISTENT")
        rec["success"] = bool(rec["pass"] and not rec["wrong_pass"])
        rows.append(rec)
        print(f"  {name:6s} {ctx.letter} k={k:3d} {eng:3s} inl={n_in:5d} "
              f"{rec['geometry']['verdict']:12s} ({rec['wall_s']:.0f}s)", flush=True)
    return rows


def evaluate(rows):
    r = [x for x in rows if "engine" in x]
    radar = [x for x in r if x["proxy"] == "minirf"]
    wac = [x for x in r if x["proxy"] == "wac"]
    s1 = not any(x["success"] for x in radar if x["engine"] == "b1")
    s2 = any(x["success"] for x in radar if x["engine"] in ("b7", "lg"))
    wac_ok = {x["pdsid"] for x in wac if x["engine"] == "b1" and x["success"]}
    return {"S1_b1_fails_on_radar": {"met": s1},
            "S2_structure_engine_registers_radar": {"met": s2,
                                                    "successes": [(x["frame"], x["engine"], x["decimation"], x["n_inliers"])
                                                                  for x in radar if x["success"]]},
            "S3_wac_rung_b1_ge_2_frames": {"met": len(wac_ok) >= 2, "frames": sorted(wac_ok)},
            "H4_cost_of_modality": {"radar_success_rate_by_engine": {
                e: float(np.mean([x["success"] for x in radar if x["engine"] == e])) if any(x["engine"] == e for x in radar) else None
                for e in ENGINES}}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--engines", default="b1,b7,lg")
    ap.add_argument("--out", default="real_data_08_results.json")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / args.out
    if out.exists():
        raise SystemExit(f"{out.relative_to(ROOT)} exists (integrity rule 4)")
    engines = [e for e in args.engines.split(",") if e]
    if "lg" in engines and not learned_available():
        engines.remove("lg")
    products = _e7.load_products()
    blocks = {n: load_map_block(s["manifest"]) for n, s in PROXIES.items()}
    rows = []
    t0 = time.perf_counter()
    for man_name, label in SOURCES:
        p = DATA / "manifests" / man_name
        if not p.exists():
            print(f"{man_name} absent; skipped")
            continue
        man = json.loads(p.read_text(encoding="utf-8"))
        target = tuple(man["target_ground_point_lon_lat"])
        long = "long" in label
        for t in man["tiles"]:
            ctx = _e7.FrameContext(t["pdsid"], t, products, target)
            for name, spec in PROXIES.items():
                block = blocks[name]
                ref_m = float(np.mean(block.metres_per_pixel))
                ks = [8, 16] if name == "minirf" else ([64, 110] if long else [32])
                for k in ks:
                    if not long and k > 32:
                        continue
                    rows += [dict(r, source=label) for r in run_pair(ctx, k, name, block, spec["log"], engines)]
            ctx.release()
    verdict = evaluate(rows)
    out.write_text(json.dumps({
        "stage": STAGE, "preregistration": "docs/stages/REAL-DATA-08_multimodal_proxies.md Part 1 (commit d475124)",
        "proxies": {n: blocks[n].provenance for n in blocks}, "engines": engines,
        "failure_rule": f"n_inliers <= {RULE} (D-023)",
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "opencv": __import__("cv2").__version__, "platform": platform.platform()},
        "total_runtime_s": time.perf_counter() - t0, "criteria": verdict, "rows": rows,
        "claims_not_supported": ["PROXY data: not Chandrayaan-2, not IIRS.", "No ground truth; geometry bound only.",
                                 "Mare only; radar layover on relief untested."],
    }, indent=1, default=float), encoding="utf-8")
    print(json.dumps(verdict, indent=1, default=str))
    print(f"written: {out.relative_to(ROOT)} ({(time.perf_counter() - t0) / 60:.1f} min)")


if __name__ == "__main__":
    main()
