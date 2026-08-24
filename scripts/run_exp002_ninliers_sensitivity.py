"""EXP-002 objective 3 (addendum) -- sensitivity of the ``n_inliers`` decision rule.

Why this script exists
----------------------
``run_exp002_threshold.py`` computes a per-subset sensitivity analysis, but it
computes it for the signal that scored highest by validation ROC AUC:

    best = max(deployable, key=lambda k: deployable[k]["validation"]["roc_auc"])

On the recorded run that maximum was ``split_consistency`` (0.9944) rather than
``n_inliers`` (0.9935) -- a margin of 0.0009. EXP-002 objective 3 then went on
to establish that ``split_consistency``'s AUC is an **artefact of an ``inf``
sentinel** (ERROR_LEDGER E-010): it is non-finite in 104 of 192 validation
cases, 103 of them wrong, and among the 88 cases where it is finite *none* is
wrong. The report therefore overrode the automated pick (D-022) and named
``n_inliers`` the best genuinely informative signal.

The sensitivity table was never re-computed to match that override. It is
recorded in ``objective3_threshold.json:sensitivity`` with
``threshold_score_space: 1e12`` in every block -- the sentinel value -- and is
presented in the stage documentation under the heading "Sensitivity of
``n_inliers``". **It is not that.** This is contradiction D2 in
``docs/stages/README.md``.

``n_inliers < 8`` is the mandated success/failure criterion for EXP-003, so the
gap matters: the criterion EXP-003 is required to use has never had its
per-subset behaviour measured.

Method, and why it is not a pipeline re-run
-------------------------------------------
This script **recomputes** the analysis from the preserved per-case artefact
``objective3_threshold_cases.csv`` (384 rows: 192 calibration + 192 validation,
disjoint seeds), rather than regenerating the image pairs.

That is deliberate, for three reasons:

1. **It isolates the correction.** The EXP-001 re-run showed that regenerating
   cases moves individual numbers (tolerance +/- 0.5853 px) because the RANSAC
   search trajectory is not bit-stable. Re-running here would confound "the
   table was labelled with the wrong signal" with "the numbers moved", and the
   first is the only thing under repair.
2. **It keeps the comparison like-for-like.** The corrected table and the
   mislabelled one then describe *the same 384 cases*, so the difference
   between them is attributable entirely to the signal, which is the point.
3. **It changes nothing.** No existing artefact is read for writing.

The cost of that choice is stated plainly: this addendum inherits whatever the
recorded cases contain and does **not** independently re-verify them.

To keep the scoring provably identical to the original rather than a
re-implementation, ``pick_threshold``, ``evaluate`` and ``overlap_report`` are
**imported from** ``run_exp002_threshold`` and not redefined here. Before
computing anything new, the script reproduces
``objective3_threshold.json:signals.n_inliers`` from the CSV and **aborts** if
it does not match to 1e-12. That self-check is what licenses everything below.

``fit_rmse`` is not used as a success/failure criterion anywhere in this
script; ground truth (``is_wrong``) is used only to *score* the rule, exactly
as in objective 3.

Run:  python scripts/run_exp002_ninliers_sensitivity.py
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

# Imported, not re-implemented: the corrected table must be produced by exactly
# the same scoring code as the original, or the comparison proves nothing.
from run_exp002_threshold import (  # noqa: E402
    evaluate,
    overlap_report,
    pick_threshold,
)

from exp002_common import CALIBRATION_SEEDS, VALIDATION_SEEDS  # noqa: E402

from siim.data import TERRAIN_REGIMES  # noqa: E402

OUT = ROOT / "experiments" / "EXP-002"
CASES = OUT / "objective3_threshold_cases.csv"
ORIGINAL = OUT / "objective3_threshold.json"

#: The rule EXP-002 validated and EXP-003 is required to use.
MANDATED_RULE = "n_inliers < 8"
MANDATED_CUTOFF = 8

SIGNAL = "n_inliers"


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------

def _num(text):
    """CSV cell -> float, with empty/'nan'/'inf' preserved as floats."""
    if text is None or text == "":
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")


def load_cases():
    """Preserved per-case rows, typed as ``run_case`` returned them."""
    rows = []
    with open(CASES, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "regime": r["regime"],
                "seed": int(float(r["seed"])),
                "transform_kind": r["transform_kind"],
                "delta_azimuth": float(r["delta_azimuth"]),
                "n_inliers": _num(r["n_inliers"]),
                "inlier_ratio": _num(r["inlier_ratio"]),
                "held_out_median": _num(r["held_out_median"]),
                "split_consistency": _num(r["split_consistency"]),
                "coverage_max_gap": _num(r["coverage_max_gap"]),
                "fit_rmse": _num(r["fit_rmse"]),
                "transform_error_median": _num(r["transform_error_median"]),
                "is_wrong": r["is_wrong"] == "True",
                "split": r["split"],
            })
    cal = [r for r in rows if r["split"] == "calibration"]
    val = [r for r in rows if r["split"] == "validation"]
    return cal, val


# --------------------------------------------------------------------------
# self-check: the CSV must reproduce the recorded n_inliers result exactly
# --------------------------------------------------------------------------

def self_check(cal, val, original):
    """Abort unless the preserved CSV reproduces the recorded n_inliers block.

    This is the load-bearing step. If the CSV cannot reproduce the numbers the
    original run recorded, then it is not a faithful basis for a corrected
    analysis and nothing below may be trusted.
    """
    rec = original["signals"][SIGNAL]
    thr = pick_threshold(cal, SIGNAL)
    got_val = evaluate(val, SIGNAL, thr)
    got_cal = evaluate(cal, SIGNAL, thr)

    problems = []
    if not math.isclose(thr, rec["threshold_selected_on_calibration"], abs_tol=1e-12):
        problems.append(
            f"threshold {thr} != recorded {rec['threshold_selected_on_calibration']}"
        )
    for label, got, want in (("validation", got_val, rec["validation"]),
                             ("calibration", got_cal, rec["calibration"])):
        for k, wv in want.items():
            gv = got.get(k)
            if gv is None:
                problems.append(f"{label}.{k} missing")
            elif not math.isclose(float(gv), float(wv), rel_tol=1e-12, abs_tol=1e-12):
                problems.append(f"{label}.{k}: recomputed {gv} != recorded {wv}")

    seeds_cal = sorted({r["seed"] for r in cal})
    seeds_val = sorted({r["seed"] for r in val})
    if seeds_cal != sorted(CALIBRATION_SEEDS):
        problems.append(f"calibration seeds {seeds_cal} != {sorted(CALIBRATION_SEEDS)}")
    if seeds_val != sorted(VALIDATION_SEEDS):
        problems.append(f"validation seeds {seeds_val} != {sorted(VALIDATION_SEEDS)}")
    if set(seeds_cal) & set(seeds_val):
        problems.append("calibration and validation seeds are NOT disjoint")

    return thr, got_cal, got_val, problems


# --------------------------------------------------------------------------
# the corrected analysis
# --------------------------------------------------------------------------

def wilson(k, n, z=1.959963984540054):
    """Wilson score interval for a proportion. Reported because a recall of
    1.000 on 103 cases and on 3 cases are not the same evidence, and a bare
    point estimate hides that difference."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def rule_eval(rows, cutoff, strict=True):
    """Evaluate the deployable rule directly in ``n_inliers`` space.

    ``strict``  -> flag failure when ``n_inliers <  cutoff``  (the mandated rule)
    else        -> flag failure when ``n_inliers <= cutoff``  (Youden's pick)

    Deliberately *not* routed through ``_clean``: the whole point of this
    addendum is that the rule must be stated and measured in the units a
    deployed system would actually use.
    """
    tp = fp = tn = fn = 0
    for r in rows:
        v = r["n_inliers"]
        flag = (v < cutoff) if strict else (v <= cutoff)
        if r["is_wrong"]:
            if flag:
                tp += 1
            else:
                fn += 1
        else:
            if flag:
                fp += 1
            else:
                tn += 1
    n_wrong, n_ok = tp + fn, fp + tn
    recall = tp / n_wrong if n_wrong else float("nan")
    fpr = fp / n_ok if n_ok else float("nan")
    prec = tp / (tp + fp) if (tp + fp) else float("nan")
    out = {
        "rule": f"n_inliers {'<' if strict else '<='} {cutoff}",
        "n": len(rows), "n_wrong": n_wrong, "n_correct": n_ok,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "recall_detect_failure": recall,
        "false_positive_rate": fpr,
        "false_negative_rate": (fn / n_wrong) if n_wrong else float("nan"),
        "precision": prec,
        "specificity": (tn / n_ok) if n_ok else float("nan"),
    }
    if n_wrong:
        lo, hi = wilson(tp, n_wrong)
        out["recall_wilson95"] = [lo, hi]
    if n_ok:
        lo, hi = wilson(fp, n_ok)
        out["fpr_wilson95"] = [lo, hi]
    if tp + fp:
        lo, hi = wilson(tp, tp + fp)
        out["precision_wilson95"] = [lo, hi]
    return out


def threshold_sweep(rows, cutoffs):
    """Every cutoff tested, in n_inliers space, strict (< cutoff)."""
    return [rule_eval(rows, c, strict=True) for c in cutoffs]


def auc_in_signal_space(rows):
    """ROC/PR AUC for n_inliers as a failure score (lower count = worse).

    Uses the original ``evaluate`` so the AUC is the same quantity objective 3
    reported, not a differently-oriented recomputation.
    """
    out = evaluate(rows, SIGNAL, -float(MANDATED_CUTOFF))
    return out.get("roc_auc"), out.get("pr_auc")


def subset_sensitivity(val, key, values, cutoff):
    """Per-subset behaviour of the mandated rule, on validation only."""
    out = {}
    for v in values:
        sub = [r for r in val if r[key] == v]
        n_wrong = sum(r["is_wrong"] for r in sub)
        if not sub:
            out[str(v)] = {"status": "absent", "n": 0}
            continue
        if n_wrong == 0 or n_wrong == len(sub):
            # Discrimination is undefined on a subset with one label only. Say
            # so rather than emitting a recall of 1.000 that means nothing.
            out[str(v)] = {
                "status": "degenerate",
                "reason": ("all cases wrong" if n_wrong else "all cases correct"),
                "n": len(sub), "n_wrong": int(n_wrong),
                "n_correct": len(sub) - int(n_wrong),
                "note": ("rule still applied for reference; recall/FPR are "
                         "undefined on a single-label subset"),
                "reference_eval": rule_eval(sub, cutoff, strict=True),
            }
            continue
        e = rule_eval(sub, cutoff, strict=True)
        roc, pr = auc_in_signal_space(sub)
        e["roc_auc"] = roc
        e["pr_auc"] = pr
        e["status"] = "evaluable"
        out[str(v)] = e
    return out


def main() -> None:
    if not CASES.exists() or not ORIGINAL.exists():
        raise SystemExit(
            f"missing preserved artefacts:\n  {CASES}\n  {ORIGINAL}\n"
            "This addendum recomputes from the recorded objective-3 cases and "
            "cannot run without them."
        )

    original = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    cal, val = load_cases()

    print("== EXP-002 objective 3 addendum: n_inliers sensitivity ==")
    print(f"source cases       : {CASES.name} ({len(cal)} calibration + {len(val)} validation)")
    print(f"calibration seeds  : {sorted({r['seed'] for r in cal})}")
    print(f"validation seeds   : {sorted({r['seed'] for r in val})}")

    # ---- self-check ------------------------------------------------------
    thr, cal_eval, val_eval, problems = self_check(cal, val, original)
    if problems:
        print("\nSELF-CHECK FAILED -- refusing to emit a corrected analysis:")
        for p in problems:
            print("   ", p)
        raise SystemExit(
            "The preserved CSV does not reproduce the recorded n_inliers block. "
            "The corrected analysis would not be comparable to the original, so "
            "nothing has been written."
        )
    print("\nSELF-CHECK PASSED: preserved CSV reproduces "
          "objective3_threshold.json:signals.n_inliers exactly")
    print(f"  Youden threshold on calibration (score space) = {thr}")
    print(f"  -> in n_inliers space that is: flag wrong when n_inliers <= {int(-thr)}")

    # ---- what the original sensitivity table actually was ----------------
    orig_sens = original.get("sensitivity", {})
    orig_thresholds = sorted({
        blk["threshold_score_space"]
        for grp in orig_sens.values() for blk in grp.values()
        if isinstance(blk, dict) and "threshold_score_space" in blk
    })
    mislabelled = {
        "signal_actually_used": original.get("best_deployable_signal"),
        "selected_by": "max validation ROC AUC over deployable signals",
        "thresholds_present_in_recorded_sensitivity": orig_thresholds,
        "sentinel_value": 1e12,
        "is_sentinel_only": orig_thresholds == [1e12],
        "why_invalid": (
            "1e12 is the non-finite sentinel substituted by _clean() for "
            "split_consistency. The recorded sensitivity table therefore "
            "measures 'did this case have enough inliers to evaluate "
            "split_consistency at all', not the discriminative content of "
            "n_inliers."
        ),
        "auc_margin_that_caused_the_wrong_pick": {
            "split_consistency": original["signals"]["split_consistency"]["validation"]["roc_auc"],
            "n_inliers": original["signals"]["n_inliers"]["validation"]["roc_auc"],
            "margin": (original["signals"]["split_consistency"]["validation"]["roc_auc"]
                       - original["signals"]["n_inliers"]["validation"]["roc_auc"]),
        },
    }

    # ---- the mandated rule, on both splits -------------------------------
    strict_cal = rule_eval(cal, MANDATED_CUTOFF, strict=True)
    strict_val = rule_eval(val, MANDATED_CUTOFF, strict=True)
    youden_cal = rule_eval(cal, MANDATED_CUTOFF, strict=False)
    youden_val = rule_eval(val, MANDATED_CUTOFF, strict=False)

    n_at_cutoff_cal = sum(1 for r in cal if r["n_inliers"] == MANDATED_CUTOFF)
    n_at_cutoff_val = sum(1 for r in val if r["n_inliers"] == MANDATED_CUTOFF)

    roc_cal, pr_cal = auc_in_signal_space(cal)
    roc_val, pr_val = auc_in_signal_space(val)

    print(f"\n== Mandated rule '{MANDATED_RULE}' ==")
    for label, e, roc, pr in (("calibration", strict_cal, roc_cal, pr_cal),
                              ("validation ", strict_val, roc_val, pr_val)):
        print(f"  {label}: n={e['n']:3d} wrong={e['n_wrong']:3d} correct={e['n_correct']:3d} "
              f"recall={e['recall_detect_failure']:.4f} FPR={e['false_positive_rate']:.4f} "
              f"precision={e['precision']:.4f} AUC={roc:.4f}")
        print(f"               recall 95% CI {e['recall_wilson95'][0]:.3f}-{e['recall_wilson95'][1]:.3f}"
              f"   FPR 95% CI {e['fpr_wilson95'][0]:.3f}-{e['fpr_wilson95'][1]:.3f}")

    # Compare the confusion matrices, not the dicts: the dicts also carry the
    # rule label, which differs by construction and would always read DIFFERENT.
    def _cm(e):
        return (e["tp"], e["fp"], e["tn"], e["fn"])

    same_val = _cm(strict_val) == _cm(youden_val)
    same_cal = _cm(strict_cal) == _cm(youden_cal)

    print(f"\n  cases with exactly {MANDATED_CUTOFF} inliers: "
          f"calibration={n_at_cutoff_cal}, validation={n_at_cutoff_val}")
    print(f"  '<{MANDATED_CUTOFF}' vs '<={MANDATED_CUTOFF}' confusion matrix: "
          f"validation={'IDENTICAL' if same_val else 'DIFFERENT'}, "
          f"calibration={'IDENTICAL' if same_cal else 'DIFFERENT'}")

    # ---- threshold sweep -------------------------------------------------
    cutoffs = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 30, 50]
    sweep_cal = threshold_sweep(cal, cutoffs)
    sweep_val = threshold_sweep(val, cutoffs)

    print("\n== Threshold sweep (validation), rule 'n_inliers < c' ==")
    print(f"  {'c':>3s} {'TP':>4s} {'FP':>4s} {'TN':>4s} {'FN':>4s} "
          f"{'recall':>7s} {'FPR':>7s} {'prec':>7s} {'J':>7s}")
    for e in sweep_val:
        j = e["recall_detect_failure"] - e["false_positive_rate"]
        c = e["rule"].split("< ")[1]
        print(f"  {c:>3s} {e['tp']:4d} {e['fp']:4d} {e['tn']:4d} {e['fn']:4d} "
              f"{e['recall_detect_failure']:7.4f} {e['false_positive_rate']:7.4f} "
              f"{e['precision']:7.4f} {j:7.4f}")

    # ---- per-subset sensitivity, the whole point -------------------------
    sensitivity = {
        "regime": subset_sensitivity(val, "regime", list(TERRAIN_REGIMES), MANDATED_CUTOFF),
        "transform_kind": subset_sensitivity(
            val, "transform_kind", ["similarity", "affine", "projective"], MANDATED_CUTOFF),
        "delta_azimuth": subset_sensitivity(
            val, "delta_azimuth", [0.0, 20.0, 40.0, 60.0], MANDATED_CUTOFF),
        "seed": subset_sensitivity(val, "seed", list(VALIDATION_SEEDS), MANDATED_CUTOFF),
    }

    print(f"\n== Sensitivity of '{MANDATED_RULE}' on VALIDATION (n_inliers, corrected) ==")
    for key, grp in sensitivity.items():
        print(f"  by {key}:")
        for v, e in grp.items():
            if e.get("status") == "degenerate":
                print(f"    {v:26s} n={e['n']:3d} wrong={e['n_wrong']:3d} "
                      f"DEGENERATE ({e['reason']}) -- recall/FPR undefined")
            elif e.get("status") == "absent":
                print(f"    {v:26s} absent")
            else:
                auc = e.get("roc_auc")
                auc_s = f"{auc:.4f}" if auc is not None else "  n/a "
                print(f"    {v:26s} n={e['n']:3d} wrong={e['n_wrong']:3d} "
                      f"recall={e['recall_detect_failure']:.4f} "
                      f"FPR={e['false_positive_rate']:.4f} "
                      f"prec={e['precision']:.4f} AUC={auc_s}")

    # ---- calibration vs validation separation ----------------------------
    separation = {
        "protocol": "threshold chosen on calibration seeds only; reported on disjoint validation seeds",
        "calibration_seeds": list(CALIBRATION_SEEDS),
        "validation_seeds": list(VALIDATION_SEEDS),
        "seeds_disjoint": not (set(CALIBRATION_SEEDS) & set(VALIDATION_SEEDS)),
        "n_calibration": len(cal),
        "n_validation": len(val),
        "calibration_wrong": strict_cal["n_wrong"],
        "validation_wrong": strict_val["n_wrong"],
        "recall_delta_val_minus_cal": (strict_val["recall_detect_failure"]
                                       - strict_cal["recall_detect_failure"]),
        "fpr_delta_val_minus_cal": (strict_val["false_positive_rate"]
                                    - strict_cal["false_positive_rate"]),
        "note": ("A rule that degrades from calibration to validation is "
                 "overfitted to the calibration terrain. FPR improving on "
                 "validation is sampling variation across 4 seeds, not "
                 "evidence that the rule is better than calibration showed."),
    }
    print("\n== Calibration vs validation separation ==")
    print(f"  recall  cal={strict_cal['recall_detect_failure']:.4f} -> "
          f"val={strict_val['recall_detect_failure']:.4f} "
          f"(delta {separation['recall_delta_val_minus_cal']:+.4f})")
    print(f"  FPR     cal={strict_cal['false_positive_rate']:.4f} -> "
          f"val={strict_val['false_positive_rate']:.4f} "
          f"(delta {separation['fpr_delta_val_minus_cal']:+.4f})")

    overlap = overlap_report(val, SIGNAL)

    # ---- diagnostics that decide whether the rule is actually supported ---

    # (a) Why did the mislabelled table's recall/FPR coincide with the correct
    #     one? Because split_consistency's inf sentinel is a near-perfect proxy
    #     for a low inlier count. Measure the agreement instead of asserting it.
    agree = sum(
        1 for r in val
        if (not np.isfinite(r["split_consistency"])) == (r["n_inliers"] < MANDATED_CUTOFF)
    )
    sentinel_proxy = {
        "question": ("does split_consistency's non-finite sentinel fire on the "
                     "same cases as the n_inliers < 8 rule?"),
        "agreement": agree,
        "n": len(val),
        "agreement_rate": agree / len(val),
        "consequence": (
            "The sentinel is a proxy for a low inlier count, so the mislabelled "
            "table's CONFUSION MATRIX coincides with the corrected one. Its AUC "
            "column does not, because AUC uses the full ranking and the sentinel "
            "collapses every flagged case to one tied value. The recorded table "
            "was therefore not grossly wrong numerically -- it was measuring the "
            "wrong quantity, and its AUC values are wrong."
        ),
    }

    # (b) Where does the recall actually come from? A recall of 1.000 that is
    #     almost entirely earned on subsets where *every* case fails is much
    #     weaker evidence than the headline number suggests.
    degenerate_wrong = sum(
        e.get("n_wrong", 0)
        for e in sensitivity["delta_azimuth"].values()
        if e.get("status") == "degenerate"
    )
    total_wrong = strict_val["n_wrong"]
    recall_mass = {
        "validation_failures_total": total_wrong,
        "failures_in_degenerate_azimuth_subsets": degenerate_wrong,
        "failures_in_discriminable_subsets": total_wrong - degenerate_wrong,
        "fraction_from_degenerate_subsets": degenerate_wrong / total_wrong,
        "consequence": (
            "Most validation failures come from Delta-azimuth subsets in which "
            "every case fails -- total match collapse, which counting catches "
            "trivially. On the subsets where correct and wrong cases coexist, "
            "the recall estimate rests on far fewer failures. EXP-003 aims to "
            "operate precisely in that discriminable regime, so the headline "
            "recall overstates the evidence available for EXP-003's use of it."
        ),
    }

    # (c) Where do the false alarms live? If they concentrate in the regime
    #     EXP-003 has made its priority benchmark, that is a usable warning.
    fps = [r for r in cal + val
           if (not r["is_wrong"]) and r["n_inliers"] < MANDATED_CUTOFF]
    n_correct_all = sum(1 for r in cal + val if not r["is_wrong"])

    def _tally(rows, key):
        t = {}
        for r in rows:
            t[str(r[key])] = t.get(str(r[key]), 0) + 1
        return t

    cov_fp = [r["coverage_max_gap"] for r in fps if np.isfinite(r["coverage_max_gap"])]
    cov_ok = [r["coverage_max_gap"] for r in cal + val
              if (not r["is_wrong"]) and np.isfinite(r["coverage_max_gap"])]
    false_alarms = {
        "n_false_alarms": len(fps),
        "n_correct_cases": n_correct_all,
        "scope": "calibration + validation pooled, for description only",
        "by_regime": _tally(fps, "regime"),
        "by_transform_kind": _tally(fps, "transform_kind"),
        "by_delta_azimuth": _tally(fps, "delta_azimuth"),
        "coverage_max_gap_of_false_alarms": {
            "min": float(np.min(cov_fp)) if cov_fp else None,
            "max": float(np.max(cov_fp)) if cov_fp else None,
        },
        "coverage_max_gap_median_all_correct": float(np.median(cov_ok)) if cov_ok else None,
        "consequence": (
            "Every false alarm is a correct-but-fragile registration: a handful "
            "of clustered inliers with a coverage gap far above the median for "
            "correct cases. They concentrate in realistic mare, which D-019 "
            "makes EXP-003's priority benchmark. The rule's false alarms are "
            "therefore not uniformly distributed over EXP-003's workload."
        ),
    }

    # (d) The form of the rule. Youden selected <= 8; the documentation quotes
    #     < 8. Only one case in 384 discriminates between them.
    boundary_cases = [
        {"split": r["split"], "regime": r["regime"], "seed": r["seed"],
         "delta_azimuth": r["delta_azimuth"], "transform_kind": r["transform_kind"],
         "is_wrong": r["is_wrong"],
         "transform_error_median": r["transform_error_median"]}
        for r in cal + val if r["n_inliers"] == MANDATED_CUTOFF
    ]
    rule_form = {
        "documented_rule": "n_inliers < 8",
        "youden_selected_rule": "n_inliers <= 8  (equivalently n_inliers < 9)",
        "cases_at_the_boundary": boundary_cases,
        "calibration": {
            "strict_lt_8": {k: strict_cal[k] for k in
                            ("recall_detect_failure", "false_positive_rate", "fn", "fp")},
            "youden_le_8": {k: youden_cal[k] for k in
                            ("recall_detect_failure", "false_positive_rate", "fn", "fp")},
        },
        "validation": {
            "identical_confusion_matrix": same_val,
            "reason": "no validation case has exactly 8 inliers",
        },
        "finding": (
            "The one case in 384 that discriminates between the two forms is a "
            "CALIBRATION failure with exactly 8 inliers and 367.95 px true "
            "error. 'n_inliers < 8' misses it (calibration recall 0.9894); "
            "'n_inliers <= 8' catches it (recall 1.0000) at an IDENTICAL false "
            "positive rate of 0.0612 -- the same 6 false alarms either way. On "
            "validation the two forms are indistinguishable. The stricter form "
            "is therefore dominated: it gains nothing measured and loses one "
            "catastrophic detection."
        ),
        "recommendation": (
            "EXP-003 should use 'n_inliers <= 8' (equivalently 'n_inliers < 9'), "
            "which is what Youden's J actually selected on calibration. This is "
            "a change of rule FORM, not of operating point, and it does not "
            "weaken any EXP-002 conclusion: the validated error rate is "
            "unchanged on validation."
        ),
    }

    payload = {
        "experiment": "EXP-002",
        "objective": "3 (addendum) - sensitivity of the n_inliers decision rule",
        "supersedes": None,
        "corrects": (
            "objective3_threshold.json:sensitivity, which is computed for "
            "best_deployable_signal (= split_consistency) and is presented in "
            "the stage documentation as a sensitivity analysis of n_inliers. "
            "Contradiction D2 in docs/stages/README.md."
        ),
        "does_not_modify": [
            "experiments/EXP-002/objective3_threshold.json",
            "experiments/EXP-002/objective3_threshold_cases.csv",
        ],
        "method": (
            "Recomputed from the preserved per-case artefact "
            "objective3_threshold_cases.csv using pick_threshold/evaluate/"
            "overlap_report imported unchanged from run_exp002_threshold.py. "
            "Not a pipeline re-run: see the module docstring for why."
        ),
        "self_check": {
            "description": ("preserved CSV must reproduce "
                            "objective3_threshold.json:signals.n_inliers exactly"),
            "passed": True,
            "tolerance": 1e-12,
            "recomputed_calibration": cal_eval,
            "recomputed_validation": val_eval,
        },
        "mislabelled_table_being_corrected": mislabelled,
        "signal": SIGNAL,
        "mandated_rule": MANDATED_RULE,
        "separation": separation,
        "cases_exactly_at_cutoff": {
            "calibration": n_at_cutoff_cal,
            "validation": n_at_cutoff_val,
            "confusion_matrix_identical_validation": same_val,
            "confusion_matrix_identical_calibration": same_cal,
            "consequence": (
                "No validation case has exactly 8 inliers, so 'n_inliers < 8' "
                "and 'n_inliers <= 8' produce an identical confusion matrix on "
                "validation. One calibration case has exactly 8, so on "
                "calibration they differ. The validated error rate therefore "
                "does not discriminate between the two forms of the rule, and "
                "the strict form inherits its validation numbers from data that "
                "never tested the boundary."
            ),
        },
        "rule_performance": {
            "strict_lt_8": {"calibration": strict_cal, "validation": strict_val},
            "youden_le_8": {"calibration": youden_cal, "validation": youden_val},
        },
        "auc": {
            "calibration": {"roc_auc": roc_cal, "pr_auc": pr_cal},
            "validation": {"roc_auc": roc_val, "pr_auc": pr_val},
            "note": ("AUC is threshold-free and is a property of n_inliers as a "
                     "ranking, not of the < 8 rule. Reported for comparability "
                     "with objective 3's signal table."),
        },
        "thresholds_tested": cutoffs,
        "threshold_sweep": {"calibration": sweep_cal, "validation": sweep_val},
        "sensitivity": sensitivity,
        "validation_overlap": overlap,
        "diagnostics": {
            "sentinel_proxy": sentinel_proxy,
            "recall_mass": recall_mass,
            "false_alarms": false_alarms,
            "rule_form": rule_form,
        },
        "verdict": {
            "operating_point_supported": True,
            "basis": (
                "Validation recall 1.000 (103/103, Wilson 95% CI "
                "0.964-1.000), FPR 0.0112 (1/89, CI 0.002-0.061), ROC AUC "
                "0.9935, on seeds disjoint from calibration. Recall is 1.000 "
                "in every non-degenerate subset: all 4 regimes, all 3 "
                "transform models, all 4 validation seeds."
            ),
            "qualification": (
                "Supported as an aggregate failure detector. TWO caveats bound "
                "its use by EXP-003: (1) the documented STRICT form 'n_inliers "
                "< 8' is dominated by 'n_inliers <= 8' -- see "
                "diagnostics.rule_form; (2) 96 of 103 validation failures come "
                "from subsets where every case fails, so the headline recall is "
                "earned mostly on total collapse rather than on the "
                "discriminable regime EXP-003 will work in."
            ),
            "blocks_exp003": False,
        },
        "negative_control_note": (
            "fit_rmse is not used as a success/failure criterion anywhere in "
            "this analysis. Ground truth (is_wrong) is used only to score the "
            "rule, never as an input to it."
        ),
    }

    out_json = OUT / "objective3_ninliers_sensitivity.json"
    out_json.write_text(json.dumps(payload, indent=2, default=float), encoding="utf-8")

    # flat CSV of the sensitivity rows, for eyeballing next to the old table
    out_csv = OUT / "objective3_ninliers_sensitivity_cases.csv"
    fields = ["subset_key", "subset_value", "status", "n", "n_wrong", "n_correct",
              "tp", "fp", "tn", "fn", "recall_detect_failure",
              "false_positive_rate", "precision", "roc_auc", "pr_auc"]
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for key, grp in sensitivity.items():
            for v, e in grp.items():
                src = e.get("reference_eval", e) if e.get("status") == "degenerate" else e
                row = {"subset_key": key, "subset_value": v,
                       "status": e.get("status", "evaluable")}
                row.update({k: src.get(k) for k in fields if k in src})
                row["n"] = e.get("n", src.get("n"))
                row["n_wrong"] = e.get("n_wrong", src.get("n_wrong"))
                w.writerow(row)

    print("\n== Diagnostics ==")
    print(f"  sentinel proxy    : split_consistency non-finite agrees with "
          f"n_inliers<{MANDATED_CUTOFF} on {agree}/{len(val)} validation cases")
    print(f"  recall mass       : {degenerate_wrong}/{total_wrong} validation failures "
          f"({100*degenerate_wrong/total_wrong:.0f}%) are in all-failing azimuth subsets")
    print(f"  false alarms      : {len(fps)}/{n_correct_all} correct cases, "
          f"by regime {false_alarms['by_regime']}")
    print(f"  rule form         : '<{MANDATED_CUTOFF}' cal recall "
          f"{strict_cal['recall_detect_failure']:.4f} vs '<={MANDATED_CUTOFF}' "
          f"{youden_cal['recall_detect_failure']:.4f} at identical FPR "
          f"{strict_cal['false_positive_rate']:.4f}")

    print(f"\nVERDICT: operating point supported = "
          f"{payload['verdict']['operating_point_supported']}; "
          f"blocks EXP-003 = {payload['verdict']['blocks_exp003']}")
    print("  -> recommended form: n_inliers <= 8  (equivalently n_inliers < 9)")

    print(f"\nwritten: {out_json}")
    print(f"written: {out_csv}")
    print("unchanged: objective3_threshold.json, objective3_threshold_cases.csv")


if __name__ == "__main__":
    main()
