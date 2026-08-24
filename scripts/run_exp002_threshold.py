"""EXP-002 objective 3 -- independent validation of the failure threshold.

EXP-001 observed that wrong cases had at most 7 inliers and correct cases at
least 8, and reported it as a clean separation. That observation was not
evidence: the threshold and its evaluation came from the same 45 cases, and it
had already broken when the RANSAC fix perturbed the search trajectory (wrong
max 7, correct min 6 -- overlapping).

Here every candidate signal gets a threshold chosen on **calibration** cases
and reported on **disjoint validation** cases built from different terrain
seeds. ``fit_rmse`` is included as a negative control: RL-010 predicts it is
anti-correlated with correctness, so it should score *worse than chance*.

Run:  python scripts/run_exp002_threshold.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from exp002_common import (  # noqa: E402
    CALIBRATION_SEEDS,
    VALIDATION_SEEDS,
    CaseSpec,
    run_case,
)

from siim.data import TERRAIN_REGIMES  # noqa: E402

OUT = ROOT / "experiments" / "EXP-002"

#: Candidate failure signals. ``higher_is_worse`` says which tail indicates a
#: failure, so each signal is oriented consistently before scoring.
SIGNALS = {
    "n_inliers": {"higher_is_worse": False, "kind": "deployable"},
    "inlier_ratio": {"higher_is_worse": False, "kind": "deployable"},
    "held_out_median": {"higher_is_worse": True, "kind": "deployable"},
    "split_consistency": {"higher_is_worse": True, "kind": "deployable"},
    "coverage_max_gap": {"higher_is_worse": True, "kind": "deployable"},
    "fit_rmse": {"higher_is_worse": True, "kind": "NEGATIVE CONTROL (RL-010)"},
}


def build_specs(seeds) -> list[CaseSpec]:
    specs = []
    for regime in TERRAIN_REGIMES:
        for seed in seeds:
            for d_az in (0, 20, 40, 60):
                for kind in ("similarity", "affine", "projective"):
                    specs.append(CaseSpec(
                        regime=regime, seed=seed, transform_kind=kind,
                        delta_azimuth=float(d_az), fit_model=kind,
                        label=f"{kind}/d_az={d_az}",
                    ))
    return specs


def _clean(rows, name):
    """Signal and label vectors, with non-finite signal values handled."""
    worse = SIGNALS[name]["higher_is_worse"]
    vals, labels = [], []
    for r in rows:
        v = r[name]
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            # inf means "maximally bad" for a higher-is-worse signal; for a
            # higher-is-better signal a non-finite value means no evidence.
            v = 1e12 if worse else -1e12
        vals.append(float(v))
        labels.append(1 if r["is_wrong"] else 0)
    v = np.asarray(vals)
    return (v if worse else -v), np.asarray(labels)


def pick_threshold(rows, name):
    """Choose the operating point on CALIBRATION data by Youden's J."""
    score, y = _clean(rows, name)
    if y.sum() == 0 or y.sum() == len(y):
        return None
    cands = np.unique(score)
    best_j, best_t = -2.0, None
    for t in cands:
        pred = score >= t  # predict "wrong"
        tp = float(((pred == 1) & (y == 1)).sum())
        fn = float(((pred == 0) & (y == 1)).sum())
        fp = float(((pred == 1) & (y == 0)).sum())
        tn = float(((pred == 0) & (y == 0)).sum())
        tpr = tp / max(tp + fn, 1)
        fpr = fp / max(fp + tn, 1)
        j = tpr - fpr
        if j > best_j:
            best_j, best_t = j, float(t)
    return best_t


def evaluate(rows, name, thresh):
    score, y = _clean(rows, name)
    pred = score >= thresh
    tp = float(((pred == 1) & (y == 1)).sum())
    fn = float(((pred == 0) & (y == 1)).sum())
    fp = float(((pred == 1) & (y == 0)).sum())
    tn = float(((pred == 0) & (y == 0)).sum())
    out = {
        "threshold_score_space": thresh,
        "n": int(len(y)),
        "n_wrong": int(y.sum()),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "recall_detect_failure": tp / max(tp + fn, 1),
        "false_positive_rate": fp / max(fp + tn, 1),
        "false_negative_rate": fn / max(tp + fn, 1),
        "precision": tp / max(tp + fp, 1),
    }
    if 0 < y.sum() < len(y):
        out["roc_auc"] = float(roc_auc_score(y, score))
        out["pr_auc"] = float(average_precision_score(y, score))
    return out


def overlap_report(rows, name):
    worse = SIGNALS[name]["higher_is_worse"]
    w = [r[name] for r in rows if r["is_wrong"] and np.isfinite(r[name] or np.inf)]
    c = [r[name] for r in rows if not r["is_wrong"] and np.isfinite(r[name] or np.inf)]
    if not w or not c:
        return {}
    return {
        "wrong_min": float(np.min(w)), "wrong_median": float(np.median(w)),
        "wrong_max": float(np.max(w)),
        "correct_min": float(np.min(c)), "correct_median": float(np.median(c)),
        "correct_max": float(np.max(c)),
        "separable": bool(max(c) < min(w)) if worse else bool(max(w) < min(c)),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    print("== Generating CALIBRATION cases ==")
    cal_specs = build_specs(CALIBRATION_SEEDS)
    cal = []
    for i, s in enumerate(cal_specs, 1):
        cal.append(run_case(s))
        if i % 32 == 0 or i == len(cal_specs):
            print(f"  [{i:3d}/{len(cal_specs)}]")

    print("== Generating VALIDATION cases (disjoint seeds, different terrain) ==")
    val_specs = build_specs(VALIDATION_SEEDS)
    val = []
    for i, s in enumerate(val_specs, 1):
        val.append(run_case(s))
        if i % 32 == 0 or i == len(val_specs):
            print(f"  [{i:3d}/{len(val_specs)}]")

    print(f"\ncalibration: {len(cal)} cases, {sum(r['is_wrong'] for r in cal)} wrong")
    print(f"validation : {len(val)} cases, {sum(r['is_wrong'] for r in val)} wrong")

    # -- EXP-001's specific claim, tested on data it never saw ---------------
    v_wrong = [r["n_inliers"] for r in val if r["is_wrong"]]
    v_ok = [r["n_inliers"] for r in val if not r["is_wrong"]]
    exp001_claim = {
        "claim": "wrong cases have <= 7 inliers, correct cases have >= 8",
        "validation_wrong_max_inliers": int(max(v_wrong)) if v_wrong else None,
        "validation_correct_min_inliers": int(min(v_ok)) if v_ok else None,
        "holds": bool(v_wrong and v_ok and max(v_wrong) < min(v_ok)),
        "threshold_8_recall": float(np.mean([r["n_inliers"] < 8 for r in val if r["is_wrong"]])),
        "threshold_8_fpr": float(np.mean([r["n_inliers"] < 8 for r in val if not r["is_wrong"]])),
    }

    results = {}
    print(f"\n{'signal':20s} {'cal_thr':>10s} {'ROC AUC':>8s} {'PR AUC':>8s} "
          f"{'recall':>7s} {'FPR':>7s} {'FNR':>7s} {'separable':>10s}")
    for name in SIGNALS:
        thr = pick_threshold(cal, name)
        if thr is None:
            continue
        val_eval = evaluate(val, name, thr)
        cal_eval = evaluate(cal, name, thr)
        ov = overlap_report(val, name)
        results[name] = {
            "kind": SIGNALS[name]["kind"],
            "higher_is_worse": SIGNALS[name]["higher_is_worse"],
            "threshold_selected_on_calibration": thr,
            "calibration": cal_eval,
            "validation": val_eval,
            "validation_overlap": ov,
        }
        sep = ov.get("separable", None)
        raw_thr = thr if SIGNALS[name]["higher_is_worse"] else -thr
        print(f"{name:20s} {raw_thr:10.3f} {val_eval.get('roc_auc', float('nan')):8.3f} "
              f"{val_eval.get('pr_auc', float('nan')):8.3f} "
              f"{val_eval['recall_detect_failure']:7.3f} {val_eval['false_positive_rate']:7.3f} "
              f"{val_eval['false_negative_rate']:7.3f} {str(sep):>10s}")

    # -- sensitivity of the best deployable signal --------------------------
    deployable = {k: v for k, v in results.items() if v["kind"] == "deployable"}
    best = max(deployable, key=lambda k: deployable[k]["validation"].get("roc_auc", 0.0))
    thr = deployable[best]["threshold_selected_on_calibration"]

    def subset_eval(rows, key, value):
        sub = [r for r in rows if r[key] == value]
        if not sub or not (0 < sum(r["is_wrong"] for r in sub) < len(sub)):
            return None
        return evaluate(sub, best, thr)

    sensitivity = {}
    for key, values in [
        ("regime", list(TERRAIN_REGIMES)),
        ("transform_kind", ["similarity", "affine", "projective"]),
        ("delta_azimuth", [0.0, 20.0, 40.0, 60.0]),
    ]:
        sensitivity[key] = {
            str(v): subset_eval(val, key, v) for v in values
        }

    print(f"\n== Sensitivity of best deployable signal ({best}) on validation ==")
    for key, d in sensitivity.items():
        print(f"  by {key}:")
        for v, e in d.items():
            if e is None:
                print(f"    {v:26s} (degenerate subset: all-correct or all-wrong)")
            else:
                print(f"    {v:26s} n={e['n']:3d} wrong={e['n_wrong']:3d} "
                      f"recall={e['recall_detect_failure']:.3f} FPR={e['false_positive_rate']:.3f} "
                      f"AUC={e.get('roc_auc', float('nan')):.3f}")

    print("\n== EXP-001 threshold claim, on unseen validation data ==")
    print(f"  wrong max inliers   = {exp001_claim['validation_wrong_max_inliers']}")
    print(f"  correct min inliers = {exp001_claim['validation_correct_min_inliers']}")
    print(f"  claim holds         = {exp001_claim['holds']}")
    print(f"  at threshold 8: recall={exp001_claim['threshold_8_recall']:.3f} "
          f"FPR={exp001_claim['threshold_8_fpr']:.3f}")

    all_rows = [{**r, "split": "calibration"} for r in cal] + [
        {**r, "split": "validation"} for r in val
    ]
    with open(OUT / "objective3_threshold_cases.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)
    (OUT / "objective3_threshold.json").write_text(json.dumps({
        "objective": "3 - independent failure-threshold validation",
        "protocol": "threshold chosen on calibration seeds; reported on disjoint validation seeds",
        "calibration_seeds": list(CALIBRATION_SEEDS),
        "validation_seeds": list(VALIDATION_SEEDS),
        "n_calibration": len(cal), "n_validation": len(val),
        "exp001_claim": exp001_claim,
        "signals": results,
        "best_deployable_signal": best,
        "sensitivity": sensitivity,
    }, indent=2, default=float))
    print(f"\nwritten: {OUT/'objective3_threshold.json'}")


if __name__ == "__main__":
    main()
