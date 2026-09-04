"""EXP-011 -- transform model selection: fit-based vs refined re-estimation vs prior.

Pre-registered in ``docs/stages/EXP-011_model_selection.md`` Part 1 (commit
899a60a) before this script existed.

    python scripts/run_exp011.py

Every score is a dense endpoint error against an EXACT self-warp truth, in
pixels. Fit residuals are used only INSIDE the selection rules under test,
never as a score.
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

from siim.baselines import run_rootsift_baseline  # noqa: E402
from siim.evaluation.gtfree import held_out_residual  # noqa: E402
from siim.geometry import (  # noqa: E402
    Transform, affine, anchor_at, endpoint_error, estimate, identity, image_centre,
    projective, similarity, translation, warp,
)
from siim.refinement import refine_correspondences  # noqa: E402

_spec = importlib.util.spec_from_file_location("_exp007", ROOT / "scripts" / "run_exp007.py")
_e7 = importlib.util.module_from_spec(_spec)
sys.modules["_exp007"] = _e7
_spec.loader.exec_module(_e7)

STAGE = "EXP-011"
OUT = ROOT / "experiments" / STAGE
MODELS = ("translation", "similarity", "affine", "projective")
COMPLEXITY = {m: i for i, m in enumerate(MODELS)}
SEEDS = (0, 1, 2)
WITHIN = 0.10          # "simplest model within 10 % of the best" (Part 1 section 4.3)
TIE_FLOOR_PX = 0.005   # absolute tie floor; see select_by_heldout
REFINE_WINDOW = 48
BOOT_SEED = 20260904


def truths(shape):
    c = image_centre(shape)
    return {
        "identity": identity(),
        "translation": translation(7.25, -4.75),
        "similarity": anchor_at(similarity(1.05, np.deg2rad(2.0), 3.0, -2.0), c),
        "affine": anchor_at(affine([[0.98, 0.02, 4.0], [0.0, 1.03, -3.0]]), c),
        "projective": anchor_at(projective([[1.0, 0.0, 2.0], [0.0, 1.0, -1.5], [2e-5, -1e-5, 1.0]]), c),
    }


def select_by_heldout(src, dst, seed=0):
    """Rule A / B core: simplest model within WITHIN of the best held-out median."""
    scores = {}
    for m in MODELS:
        r = held_out_residual(src, dst, model=m, k_folds=5, seed=seed)
        scores[m] = float(r.median) if r.ok and np.isfinite(r.median) else float("inf")
    best = min(scores.values())
    # "within 10 % of the best" (Part 1 section 4.3) plus an ABSOLUTE tie floor of
    # 0.005 px: on an exact self-warp every model's held-out residual is ~1e-9
    # and a purely relative tolerance makes the choice depend on rounding noise.
    # Implementation clarification, recorded in Part 2; it cannot change any
    # selection where the models genuinely differ.
    cands = [m for m in MODELS if scores[m] <= max(best * (1 + WITHIN), best + TIE_FLOOR_PX)]
    chosen = min(cands, key=lambda m: COMPLEXITY[m])
    return chosen, scores


def dense_error(tf, truth, shape):
    e = endpoint_error(tf, truth, shape, step=16)
    return {"median": e.median, "p90": e.p90, "max": e.max}


def bootstrap(x, n=1000):
    x = np.asarray([v for v in x if np.isfinite(v)], float)
    if x.size == 0:
        return None
    rng = np.random.default_rng(BOOT_SEED)
    meds = [float(np.median(rng.choice(x, x.size))) for _ in range(n)]
    return {"median": float(np.median(x)), "ci95": [float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))], "n": int(x.size)}


def run_case(img, truth, truth_name, letter, seed, prior_model="similarity"):
    ref, valid = warp(img, truth, cval=np.nan)
    ref = np.where(valid, ref, np.nanmedian(ref))
    res = run_rootsift_baseline(img, ref, model="affine", ransac_threshold=3.0, seed=seed)
    n_in = int(np.asarray(res.inlier_mask, bool).sum()) if np.size(res.inlier_mask) else 0
    row = {"tile": letter, "truth": truth_name, "seed": seed, "n_inliers": n_in}
    if n_in <= 8 or res.transform is None:
        row["b1_pass"] = False
        return row
    row["b1_pass"] = True
    p, q = res.inlier_points
    shape = img.shape
    row["recorded_affine_error"] = dense_error(res.transform, truth, shape)

    # Rule A: held-out on RAW inliers
    m_a, sc_a = select_by_heldout(p, q, seed)
    tf_a = estimate(p, q, m_a).transform
    row["rule_A"] = {"selected": m_a, "heldout": sc_a, "error": dense_error(tf_a, truth, shape),
                     "truth_model_error": dense_error(estimate(p, q, truth_name if truth_name != "identity" else "translation").transform, truth, shape)}

    # Rule B: refine, then held-out on REFINED points
    r = refine_correspondences(img, ref, res.transform, p, window=REFINE_WINDOW, method="ecc")
    pr, qr = p[r.ok], r.dst_refined[r.ok]
    if len(pr) >= 12:
        m_b, sc_b = select_by_heldout(pr, qr, seed)
        tf_b = estimate(pr, qr, m_b).transform
        row["rule_B"] = {"selected": m_b, "heldout": sc_b, "n_refined": int(len(pr)),
                         "error": dense_error(tf_b, truth, shape)}
        # Rule C: geometry prior (similarity for near-nadir NAC pairs), re-estimated from refined points
        tf_c = estimate(pr, qr, prior_model).transform
        row["rule_C"] = {"selected": prior_model, "error": dense_error(tf_c, truth, shape)}
        # for reference: every model re-estimated from refined points
        row["refined_all_models"] = {m: dense_error(estimate(pr, qr, m).transform, truth, shape)["median"] for m in MODELS}
    else:
        row["rule_B"] = {"error": None, "note": f"only {len(pr)} refined points"}
    return row


def evaluate(rows):
    ok = [r for r in rows if r.get("b1_pass")]
    truth_of = lambda r: "translation" if r["truth"] == "identity" else r["truth"]
    # gate: identity -> rule B selects translation with < 0.01 px
    gate = [r for r in ok if r["truth"] == "identity"]
    gate_met = all(r.get("rule_B", {}).get("selected") == "translation" and r["rule_B"]["error"]["median"] < 0.01 for r in gate) and len(gate) >= 4
    # S1
    d_tr = [r for r in ok if r["tile"] == "D" and r["truth"] == "translation"]
    s1_hits = [r for r in d_tr if r["rule_A"]["selected"] != "translation"
               and r["rule_A"]["error"]["median"] >= 5 * r["rule_A"]["truth_model_error"]["median"]]
    # S2
    ts = [r for r in ok if r["truth"] in ("translation", "similarity") and r.get("rule_B", {}).get("error")]
    s2_err = all(r["rule_B"]["error"]["median"] < 0.05 for r in ts)
    sel = [r for r in ok if r.get("rule_B", {}).get("error") and r["truth"] != "identity"]
    s2_sel = np.mean([r["rule_B"]["selected"] == truth_of(r) for r in sel]) if sel else 0.0
    # S3
    s3 = all(r["rule_C"]["error"]["median"] < 0.05 for r in ts if "rule_C" in r)
    per_rule = {rule: bootstrap([r[rule]["error"]["median"] for r in ok if r.get(rule, {}).get("error")]) for rule in ("rule_A", "rule_B", "rule_C")}
    per_rule["recorded_affine"] = bootstrap([r["recorded_affine_error"]["median"] for r in ok])
    return {
        "gate_identity_rule_B": {"met": bool(gate_met), "n": len(gate)},
        "S1_fit_based_selection_refuted_on_D": {"met": len(s1_hits) >= 1, "n_hits": len(s1_hits),
                                                "detail": [{"seed": r["seed"], "selected": r["rule_A"]["selected"],
                                                            "error": r["rule_A"]["error"]["median"],
                                                            "truth_model_error": r["rule_A"]["truth_model_error"]["median"]} for r in d_tr]},
        "S2_refined_reestimation": {"met": bool(s2_err and s2_sel >= 0.9), "all_ts_below_0_05": bool(s2_err),
                                    "selection_accuracy": float(s2_sel), "n_cases": len(sel)},
        "S3_prior_rule": {"met": bool(s3)},
        "dense_median_error_by_rule": per_rule,
        "selection_confusion_rule_A": _confusion(ok, "rule_A", truth_of),
        "selection_confusion_rule_B": _confusion([r for r in ok if r.get("rule_B", {}).get("error")], "rule_B", truth_of),
    }


def _confusion(rows, rule, truth_of):
    out = {}
    for r in rows:
        if r["truth"] == "identity":
            continue
        key = f"{truth_of(r)} -> {r[rule]['selected']}"
        out[key] = out.get(key, 0) + 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="exp011_results.json")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / args.out
    if out.exists():
        raise SystemExit(f"{out.relative_to(ROOT)} exists (integrity rule 4)")
    products = _e7.load_products()
    rows = []
    t0 = time.perf_counter()
    seen = set()
    for stage, (man_name, art_rel) in _e7.TIER1.items():
        man = json.loads((_e7.DATA / "manifests" / man_name).read_text(encoding="utf-8"))
        rec = json.loads((_e7.EXPERIMENTS / art_rel).read_text(encoding="utf-8"))
        k = int(rec["baseline"]["downsample"])
        target = tuple(man["target_ground_point_lon_lat"])
        for t in man["tiles"]:
            if t["pdsid"] in seen:
                continue
            seen.add(t["pdsid"])
            ctx = _e7.FrameContext(t["pdsid"], t, products, target)
            img = ctx.img(k)
            for name, tf in truths(img.shape).items():
                for seed in (SEEDS if name != "identity" else (0,)):
                    row = run_case(img, tf, name, ctx.letter, seed)
                    rows.append(row)
                    if row.get("b1_pass"):
                        print(f"  {ctx.letter} {name:12s} seed {seed}  A->{row['rule_A']['selected']:11s} "
                              f"{row['rule_A']['error']['median']:.3f}  B->{row.get('rule_B', {}).get('selected', '-'):11s} "
                              f"{(row.get('rule_B', {}).get('error') or {}).get('median', float('nan')):.3f}  "
                              f"C {row.get('rule_C', {}).get('error', {}).get('median', float('nan')):.3f}  "
                              f"affine-default {row['recorded_affine_error']['median']:.3f}", flush=True)
            ctx.release()
    verdict = evaluate(rows)
    out.write_text(json.dumps({
        "stage": STAGE, "preregistration": "docs/stages/EXP-011_model_selection.md Part 1 (commit 899a60a)",
        "models": list(MODELS), "within": WITHIN, "refine_window": REFINE_WINDOW,
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "opencv": __import__("cv2").__version__, "platform": platform.platform()},
        "total_runtime_s": time.perf_counter() - t0, "criteria": verdict, "rows": rows,
        "claims_not_supported": ["Self-warps share texture with their originals: upper bounds.",
                                 "No recorded artefact is edited."],
    }, indent=1, default=float), encoding="utf-8")
    print(json.dumps(verdict, indent=1, default=str)[:3000])
    print(f"written: {out.relative_to(ROOT)} ({(time.perf_counter() - t0) / 60:.1f} min)")


if __name__ == "__main__":
    main()
