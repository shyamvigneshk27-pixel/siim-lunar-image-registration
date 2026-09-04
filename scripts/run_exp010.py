"""EXP-010 -- sub-pixel refinement: precision on real texture, bias under illumination.

Pre-registered in ``docs/stages/EXP-010_subpixel_refinement.md`` Part 1
(commit 84ee43d) before this script and ``siim.refinement`` existed.

    python scripts/run_exp010.py            # D1 + D2 (+ D3 if the long windows exist)
    python scripts/run_exp010.py --only d1

Every number is an endpoint error against EXACT ground truth (a known warp or
a rendered pair), in pixels of the coarser image. Fit residuals are not used.
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
sys.path.insert(0, str(ROOT / "scripts"))

from siim.baselines import run_rootsift_baseline  # noqa: E402
from siim.data import TERRAIN_REGIMES, make_pair  # noqa: E402
from siim.geometry import anchor_at, image_centre, similarity, translation, warp  # noqa: E402
from siim.refinement import refine_correspondences  # noqa: E402

STAGE = "EXP-010"
OUT = ROOT / "experiments" / STAGE
N_INLIERS_FAILURE_RULE = 8          # D-023, restated
BOOT_SEED = 20260904
N_BOOT = 1000
WINDOWS = (32, 48, 64)
METHODS = ("ecc", "phase")
MAX_POINTS_PER_PAIR = 400
BASE = {"model": "affine", "ransac_threshold_px": 3.0, "seed": 0}

_spec = importlib.util.spec_from_file_location("_exp007", ROOT / "scripts" / "run_exp007.py")
_e7 = importlib.util.module_from_spec(_spec)
sys.modules["_exp007"] = _e7
_spec.loader.exec_module(_e7)
from exp002_common import FIELD_MARGIN, SHAPE, SUN_REF, get_field, make_transform  # noqa: E402


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------

def bootstrap_median(x: np.ndarray, seed: int = BOOT_SEED, n: int = N_BOOT) -> dict:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {"n": 0, "median": None, "ci95": None}
    rng = np.random.default_rng(seed)
    meds = [float(np.median(rng.choice(x, size=x.size, replace=True))) for _ in range(n)]
    return {"n": int(x.size), "median": float(np.median(x)),
            "ci95": [float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))],
            "p90": float(np.percentile(x, 90))}


def auc(score: np.ndarray, label: np.ndarray) -> float | None:
    s, y = np.asarray(score, float), np.asarray(label, bool)
    m = np.isfinite(s)
    s, y = s[m], y[m]
    if y.sum() == 0 or (~y).sum() == 0:
        return None
    order = np.argsort(s)
    ranks = np.empty(len(s)); ranks[order] = np.arange(1, len(s) + 1)
    # AUC of "low confidence predicts harm": rank-sum on negated score
    r_pos = ranks[y]
    return float(1.0 - (r_pos.sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum()))


# --------------------------------------------------------------------------
# one pair
# --------------------------------------------------------------------------

def refine_pair(src: np.ndarray, ref: np.ndarray, truth, seed: int) -> list[dict]:
    """B1, then every (method, window) on a seeded subset of inliers. GT scores."""
    res = run_rootsift_baseline(src, ref, model=BASE["model"],
                                ransac_threshold=BASE["ransac_threshold_px"], seed=BASE["seed"])
    n_in = int(np.asarray(res.inlier_mask, bool).sum()) if np.size(res.inlier_mask) else 0
    if n_in <= N_INLIERS_FAILURE_RULE or res.transform is None:
        return [{"b1_pass": False, "n_inliers": n_in}]
    p_in, q_in = res.inlier_points
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(p_in), size=min(MAX_POINTS_PER_PAIR, len(p_in)), replace=False)
    p, q_kp = p_in[idx], q_in[idx]
    q_true = truth.apply(p)
    err_kp = np.hypot(*(q_kp - q_true).T)
    err_tf = np.hypot(*(res.transform.apply(p) - q_true).T)
    rows = []
    for method in METHODS:
        for w in WINDOWS:
            r = refine_correspondences(src, ref, res.transform, p, window=w, method=method)
            err_ref = np.hypot(*(r.dst_refined - q_true).T)
            worse = (err_ref - err_tf) > 0.5
            rows.append({
                "b1_pass": True, "n_inliers": n_in, "method": method, "window": w,
                "n_points": int(len(p)), "n_ok": int(r.ok.sum()),
                "err_keypoint": err_kp.tolist(), "err_transform": err_tf.tolist(),
                "err_refined": err_ref.tolist(), "ok": r.ok.tolist(),
                "confidence": np.where(np.isfinite(r.confidence), r.confidence, np.nan).tolist(),
                "made_worse": worse.tolist(),
                "shift_median_px": [float(np.nanmedian(r.shift[r.ok, 0])) if r.ok.any() else None,
                                    float(np.nanmedian(r.shift[r.ok, 1])) if r.ok.any() else None],
            })
    return rows


# --------------------------------------------------------------------------
# datasets
# --------------------------------------------------------------------------

def d1_self_warps() -> list[dict]:
    products = _e7.load_products()
    out = []
    frac = [(0.0, 0.0), (0.25, 0.0), (0.0, 0.25), (0.25, 0.25),
            (0.5, 0.5), (0.75, 0.75), (0.5, 0.25), (0.25, 0.75)]
    for stage, (man_name, art_rel) in _e7.TIER1.items():
        man = json.loads((_e7.DATA / "manifests" / man_name).read_text(encoding="utf-8"))
        rec = json.loads((_e7.EXPERIMENTS / art_rel).read_text(encoding="utf-8"))
        k = int(rec["baseline"]["downsample"])
        target = tuple(man["target_ground_point_lon_lat"])
        for t in man["tiles"]:
            if t["pdsid"] in {r["pdsid"] for r in out}:
                continue
            ctx = _e7.FrameContext(t["pdsid"], t, products, target)
            img = ctx.img(k)
            c = image_centre(img.shape)
            transforms = [(f"t{tx}_{ty}", translation(7.0 + tx, -5.0 + ty)) for tx, ty in frac]
            transforms += [(f"s{s}_r{a}", anchor_at(similarity(s, np.deg2rad(a), 3.25, -2.5), c))
                           for s in (0.9, 1.1) for a in (3.0, -3.0)]
            for name, tf in transforms:
                ref, valid = warp(img, tf, cval=np.nan)
                ref = np.where(valid, ref, np.nanmedian(ref))
                t0 = time.perf_counter()
                for row in refine_pair(img, ref, tf, seed=hash(name) % 10_000):
                    row.update({"dataset": "D1", "pdsid": t["pdsid"], "letter": ctx.letter,
                                "warp": name, "is_identity_gate": name == "t0.0_0.0",
                                "wall_s": time.perf_counter() - t0})
                    out.append(row)
                print(f"  D1 {ctx.letter} {name:12s} rows={len(out)}", flush=True)
            ctx.release()
    return out


def d2_synthetic_illumination() -> list[dict]:
    out = []
    for regime in ("A_mare_moderate", "A_highlands_moderate"):
        for seed in (3001, 3002, 3003):
            for d_el in (0.0, -10.0):
                for d_az in (0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0):
                    rng = np.random.default_rng(seed * 31 + int(d_az))
                    tf = make_transform("affine", rng)
                    pair = make_pair(np.random.default_rng(seed), tf,
                                     scene=TERRAIN_REGIMES[regime].scene, out_shape=SHAPE,
                                     sun_source=(SUN_REF[0], SUN_REF[1]),
                                     sun_reference=(SUN_REF[0] + d_az, SUN_REF[1] + d_el),
                                     base_field=get_field(regime, seed), field_margin=FIELD_MARGIN)
                    for row in refine_pair(pair.source, pair.reference, pair.transform,
                                           seed=seed + int(d_az) + int(d_el)):
                        row.update({"dataset": "D2", "regime": regime, "seed": seed,
                                    "delta_azimuth": d_az, "delta_elevation": d_el})
                        out.append(row)
            print(f"  D2 {regime} seed {seed} done", flush=True)
    return out


def d3_rendered_sldem() -> list[dict]:
    from siim.ingest.lola_dem import load_sldem_window
    man_path = _e7.DATA / "manifests" / "exp007_long_triplet_abd_manifest.json"
    if not man_path.exists():
        print("  D3 skipped: long-window manifest absent")
        return []
    dem = load_sldem_window()
    products = _e7.load_products()
    man = json.loads(man_path.read_text(encoding="utf-8"))
    target = tuple(man["target_ground_point_lon_lat"])
    ctx = {t["pdsid"]: _e7.FrameContext(t["pdsid"], t, products, target) for t in man["tiles"]}
    k = 32
    renders = {p: c.render(k, dem) for p, c in ctx.items()}
    out = []
    ids = list(ctx)
    for i in range(len(ids)):
        for j in range(len(ids)):
            if i == j:
                continue
            a, b = ids[i], ids[j]
            # ground truth between the two renders is the corner-geometry map
            g, _ = _e7._predict(ctx[a].corners, ctx[a].window(k), ctx[b].corners, ctx[b].window(k))
            if g is None:
                continue
            for row in refine_pair(renders[a].image, renders[b].image, g, seed=i * 7 + j):
                row.update({"dataset": "D3", "edge": f"{a} -> {b}",
                            "delta_incidence_deg": abs(ctx[a].incidence_published - ctx[b].incidence_published),
                            "note": "renders of one DEM under two Suns; GT = corner map (not pixel-exact)"})
                out.append(row)
    return out


# --------------------------------------------------------------------------
# criteria
# --------------------------------------------------------------------------

def _pool(rows, **cond):
    sel = [r for r in rows if r.get("b1_pass") and all(r.get(k) == v for k, v in cond.items())]
    before = np.concatenate([np.asarray(r["err_transform"])[np.asarray(r["ok"])] for r in sel]) if sel else np.zeros(0)
    after = np.concatenate([np.asarray(r["err_refined"])[np.asarray(r["ok"])] for r in sel]) if sel else np.zeros(0)
    return before, after, sel


def evaluate(rows: list[dict]) -> dict:
    d1 = [r for r in rows if r["dataset"] == "D1"]
    d2 = [r for r in rows if r["dataset"] == "D2"]
    out: dict = {}
    # gate: identity warp
    gate = [r for r in d1 if r.get("is_identity_gate") and r.get("b1_pass")]
    gate_shift = [abs(x) for r in gate for x in r["shift_median_px"] if x is not None]
    out["gate_identity_unbiased"] = {"met": bool(gate_shift) and max(gate_shift) < 0.05,
                                     "max_median_abs_shift_px": max(gate_shift) if gate_shift else None}
    # S1
    s1 = {}
    for m in METHODS:
        for w in WINDOWS:
            b, a, _ = _pool(d1, method=m, window=w)
            bs_a, bs_b = bootstrap_median(a), bootstrap_median(b)
            s1[f"{m}_w{w}"] = {"before": bs_b, "after": bs_a,
                               "met": bool(bs_a["median"] is not None and bs_a["median"] < 0.25
                                           and bs_a["ci95"][1] < 0.5
                                           and bs_b["median"] > 2 * bs_a["median"])}
    out["S1_precision_on_real_self_warps"] = {"met": any(v["met"] for v in s1.values()), "detail": s1}
    # choose the best method/window on D1 for S2-S4 (pre-registered prediction ecc_w48; report both)
    best = min(s1, key=lambda k: s1[k]["after"]["median"] if s1[k]["after"]["median"] is not None else 9e9)
    m_best, w_best = best.split("_w")[0], int(best.split("_w")[1])
    out["best_on_d1"] = best
    # S2, S3 per regime
    s2, s3 = {}, {}
    for regime in ("A_mare_moderate", "A_highlands_moderate"):
        by_az = {}
        for d_az in (0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0):
            _, a, sel = _pool(d2, method=m_best, window=w_best, regime=regime, delta_azimuth=d_az)
            by_az[str(d_az)] = {**bootstrap_median(a), "n_pairs_passing_b1": len(sel)}
        m0, m30 = by_az["0.0"]["median"], by_az["30.0"]["median"]
        s2[regime] = {"by_delta_azimuth": by_az,
                      "met": bool(m0 is not None and m0 < 0.5 and m30 is not None and m30 >= 2 * m0)}
        ok_az = [float(k) for k, v in by_az.items()
                 if v["median"] is not None and v["median"] < 0.5 and v["ci95"][1] < 1.0]
        s3[regime] = {"largest_ok_delta_azimuth": max(ok_az) if ok_az else None}
    out["S2_bias_grows_with_delta_azimuth"] = {"met": all(v["met"] for v in s2.values()), "detail": s2}
    out["S3_deployable_envelope"] = {"met": all((v["largest_ok_delta_azimuth"] or -1) >= 10 for v in s3.values()),
                                     "detail": s3}
    # S4: confidence predicts harm
    _, _, sel = _pool(d2, method=m_best, window=w_best)
    conf = np.concatenate([np.asarray(r["confidence"], float)[np.asarray(r["ok"])] for r in sel]) if sel else np.zeros(0)
    worse = np.concatenate([np.asarray(r["made_worse"])[np.asarray(r["ok"])] for r in sel]) if sel else np.zeros(0, bool)
    a_uc = auc(conf, worse) if len(conf) else None
    out["S4_confidence_predicts_harm"] = {"met": bool(a_uc is not None and a_uc >= 0.75), "auc": a_uc,
                                          "n_points": int(len(conf)), "fraction_made_worse": float(worse.mean()) if len(worse) else None}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default=None, choices=["d1", "d2", "d3"])
    ap.add_argument("--out", default="exp010_results.json")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / args.out
    if out.exists():
        raise SystemExit(f"{out.relative_to(ROOT)} exists (integrity rule 4)")
    t0 = time.perf_counter()
    rows: list[dict] = []
    if args.only in (None, "d1"):
        rows += d1_self_warps()
    if args.only in (None, "d2"):
        rows += d2_synthetic_illumination()
    if args.only in (None, "d3"):
        rows += d3_rendered_sldem()
    verdict = evaluate(rows) if args.only is None else {"note": f"partial run ({args.only}); criteria not evaluated"}
    payload = {
        "stage": STAGE,
        "preregistration": "docs/stages/EXP-010_subpixel_refinement.md Part 1 (commit 84ee43d)",
        "definition": "median endpoint error vs exact GT in coarser-image px < 0.5, bootstrap 95% CI upper < 1.0; fit residuals never used",
        "methods": list(METHODS), "windows": list(WINDOWS), "max_points_per_pair": MAX_POINTS_PER_PAIR,
        "bootstrap": {"n": N_BOOT, "seed": BOOT_SEED},
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "opencv": __import__("cv2").__version__, "platform": platform.platform()},
        "total_runtime_s": time.perf_counter() - t0,
        "criteria": verdict,
        "rows": rows,
        "claims_not_supported": ["No sub-pixel claim on a real cross-illumination pair (no ground truth exists).",
                                 "D1 is an upper bound on precision (shared texture and kernel).",
                                 "No Chandrayaan-2 data."],
    }
    out.write_text(json.dumps(payload, indent=1, default=float), encoding="utf-8")
    print(json.dumps(verdict, indent=1, default=str)[:3000])
    print(f"written: {out.relative_to(ROOT)}  ({payload['total_runtime_s'] / 60:.1f} min)")


if __name__ == "__main__":
    main()
