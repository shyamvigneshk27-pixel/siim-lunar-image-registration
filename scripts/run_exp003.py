"""EXP-003 -- do illumination-robust representations move the azimuth cliff?

Pre-registered in ``docs/stages/EXP-003_illumination_robust_representations.md``
Part 1 BEFORE this script existed. The success criterion (S1), the hypotheses
(H-3.1 ... H-3.6), the azimuth grid, the seeds and the stop conditions are all
fixed there and are not editable in the light of results.

    S1 (primary): a representation earns its place only if the last
    fully-successful Delta-azimuth is STRICTLY GREATER THAN 30 degrees on BOTH
    realistic A-regimes.

``fit_rmse`` is recorded and never used as a criterion. Ground truth scores the
run; no arm receives it. Results are reported per regime and never pooled.

Run:  python scripts/run_exp003.py
"""

from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from exp003_common import (  # noqa: E402
    ARMS,
    AZIMUTH_GRID,
    EXP003_SEEDS,
    PRIMARY_REGIMES,
    CaseSpec,
    last_fully_successful_azimuth,
    run_all_arms,
)

from siim.data import TERRAIN_REGIMES  # noqa: E402

OUT = ROOT / "experiments" / "EXP-003"

#: The bar EXP-002 set, in advance, for a representation to earn its place.
CRITERION_AZIMUTH = 30.0
#: The deployable failure flag fixed by D-023.
INLIER_CUTOFF = 8


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - h), min(1.0, c + h))


def summarise(rows: list[dict]) -> dict:
    """Per-regime, per-representation summary. Never pooled across regimes."""
    out: dict = {}
    for regime in PRIMARY_REGIMES:
        out[regime] = {}
        for arm in ARMS:
            sub = [r for r in rows
                   if r["regime"] == regime and r["representation"] == arm.name]
            by_az = {}
            for az in AZIMUTH_GRID:
                at = [r for r in sub if r["delta_azimuth"] == az]
                if not at:
                    continue
                ok = [r for r in at if not r["is_wrong"]]
                errs = [r["transform_error_median"] for r in at
                        if np.isfinite(r["transform_error_median"])]
                by_az[str(az)] = {
                    "n_seeds": len(at),
                    "n_success": len(ok),
                    "success_rate": len(ok) / len(at),
                    "median_true_error": float(np.median(errs)) if errs else None,
                    "median_n_inliers": float(np.median([r["n_inliers"] for r in at])),
                    "median_n_putative": float(np.median([r["n_putative"] for r in at])),
                    "median_n_kp_src": float(np.median([r["n_kp_src"] for r in at])),
                    "median_coverage_max_gap": float(np.median(
                        [r["coverage_max_gap"] for r in at
                         if np.isfinite(r["coverage_max_gap"])] or [float("nan")])),
                    "median_pipeline_s": float(np.median([r["pipeline_s"] for r in at])),
                }
            lfs = last_fully_successful_azimuth(sub)
            out[regime][arm.name] = {
                "last_fully_successful_delta_azimuth": lfs,
                "beats_criterion_30deg": bool(lfs is not None and lfs > CRITERION_AZIMUTH),
                "passes_zero_azimuth_control": bool(
                    by_az.get("0.0", {}).get("success_rate", 0.0) == 1.0),
                "by_azimuth": by_az,
            }
    return out


def mixed_regime_analysis(rows: list[dict]) -> dict:
    """Requirement 8: re-measure ``n_inliers <= 8`` where it can discriminate.

    EXP-002's recall 1.000 / FPR 0.0112 is supporting evidence, not a guarantee.
    That figure was earned with 93% of its failures in subsets where every case
    failed. Here we split EXP-003's own cases into:

    * total-collapse cells  -- every case in the cell is wrong;
    * all-correct cells     -- every case is correct;
    * MIXED cells           -- correct and wrong coexist. Only these test the
      flag's discrimination.

    A "cell" is (representation, regime, delta_azimuth) across seeds.
    """
    cells: dict[tuple, list[dict]] = {}
    for r in rows:
        cells.setdefault(
            (r["representation"], r["regime"], r["delta_azimuth"]), []).append(r)

    mixed, collapse, allok = [], [], []
    for _, group in cells.items():
        n_wrong = sum(g["is_wrong"] for g in group)
        if n_wrong == 0:
            allok.extend(group)
        elif n_wrong == len(group):
            collapse.extend(group)
        else:
            mixed.extend(group)

    def score(subset: list[dict], label: str) -> dict:
        tp = sum(1 for r in subset if r["is_wrong"] and r["flag_n_inliers_le_8"])
        fn = sum(1 for r in subset if r["is_wrong"] and not r["flag_n_inliers_le_8"])
        fp = sum(1 for r in subset if not r["is_wrong"] and r["flag_n_inliers_le_8"])
        tn = sum(1 for r in subset if not r["is_wrong"] and not r["flag_n_inliers_le_8"])
        nw, nc = tp + fn, fp + tn
        d = {
            "subset": label, "n": len(subset), "n_wrong": nw, "n_correct": nc,
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "recall_detect_failure": (tp / nw) if nw else None,
            "false_positive_rate": (fp / nc) if nc else None,
            "precision": (tp / (tp + fp)) if (tp + fp) else None,
        }
        if nw:
            d["recall_wilson95"] = list(wilson(tp, nw))
        if nc:
            d["fpr_wilson95"] = list(wilson(fp, nc))
        return d

    return {
        "rule": f"n_inliers <= {INLIER_CUTOFF}  (D-023)",
        "cell_definition": "(representation, regime, delta_azimuth) across seeds",
        "n_cells": len(cells),
        "all_cases": score(rows, "all EXP-003 cases"),
        "mixed_correct_wrong": score(mixed, "MIXED cells only (discriminable)"),
        "total_collapse": score(collapse, "total-collapse cells (all wrong)"),
        "all_correct": score(allok, "all-correct cells"),
        "exp002_reference": {
            "recall": 1.0, "fpr": 0.011235955056179775,
            "status": "supporting evidence only, not a guarantee (requirement 8)",
        },
    }


def verdict(summary: dict) -> dict:
    """Apply the pre-registered criterion S1. No post-hoc adjustment."""
    a_regimes = ("A_mare_moderate", "A_highlands_moderate")
    per_arm = {}
    for arm in ARMS:
        lfs = {reg: summary[reg][arm.name]["last_fully_successful_delta_azimuth"]
               for reg in PRIMARY_REGIMES}
        ctrl = {reg: summary[reg][arm.name]["passes_zero_azimuth_control"]
                for reg in PRIMARY_REGIMES}
        beats = {reg: bool(lfs[reg] is not None and lfs[reg] > CRITERION_AZIMUTH)
                 for reg in PRIMARY_REGIMES}
        per_arm[arm.name] = {
            "last_fully_successful": lfs,
            "passes_zero_azimuth_control": ctrl,
            "beats_30deg_per_regime": beats,
            "MEETS_S1": bool(all(beats[r] for r in a_regimes)),
            "void_on": [r for r in PRIMARY_REGIMES if not ctrl[r]],
        }
    any_pass = [k for k, v in per_arm.items() if v["MEETS_S1"]]
    return {
        "criterion": ("S1: last fully-successful Delta-azimuth STRICTLY > 30 deg on BOTH "
                      "A_mare_moderate and A_highlands_moderate"),
        "per_arm": per_arm,
        "arms_meeting_S1": any_pass,
        "S1_MET_BY_ANY_ARM": bool(any_pass),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    specs = [CaseSpec(regime=reg, seed=seed, delta_azimuth=az)
             for reg in PRIMARY_REGIMES
             for seed in EXP003_SEEDS
             for az in AZIMUTH_GRID]

    print("== EXP-003: illumination-robust representations ==")
    print(f"regimes {list(PRIMARY_REGIMES)}")
    print(f"seeds   {list(EXP003_SEEDS)}  (disjoint from all EXP-002 seeds)")
    print(f"azimuth {list(AZIMUTH_GRID)}")
    print(f"arms    {[a.name for a in ARMS]}")
    print(f"{len(specs)} pairs x {len(ARMS)} arms = {len(specs)*len(ARMS)} evaluations\n")

    rows: list[dict] = []
    t_start = time.perf_counter()
    for i, spec in enumerate(specs, 1):
        rows.extend(run_all_arms(spec))
        if i % 11 == 0 or i == len(specs):
            el = time.perf_counter() - t_start
            print(f"  [{i:3d}/{len(specs)}] {spec.regime:24s} seed={spec.seed} "
                  f"elapsed={el/60:.1f} min")

    summary = summarise(rows)
    mixed = mixed_regime_analysis(rows)
    vd = verdict(summary)

    # ---- report, mare first and prominently (requirement 7) ---------------
    for regime in PRIMARY_REGIMES:
        tag = "  <<< PRIORITY (D-019)" if regime == "A_mare_moderate" else ""
        print(f"\n=== {regime}{tag} ===")
        print(f"  {'representation':22s} {'0deg ctrl':>9s} {'last full success':>18s} "
              f"{'>30?':>5s}")
        for arm in ARMS:
            s = summary[regime][arm.name]
            lfs = s["last_fully_successful_delta_azimuth"]
            print(f"  {arm.name:22s} {str(s['passes_zero_azimuth_control']):>9s} "
                  f"{str(lfs):>18s} {str(s['beats_criterion_30deg']):>5s}")

    print("\n=== Success rate by azimuth, per regime (never pooled) ===")
    for regime in PRIMARY_REGIMES:
        print(f"\n  {regime}")
        hdr = "  ".join(f"{az:>5.0f}" for az in AZIMUTH_GRID)
        print(f"    {'representation':22s} {hdr}")
        for arm in ARMS:
            cells = []
            for az in AZIMUTH_GRID:
                d = summary[regime][arm.name]["by_azimuth"].get(str(az))
                cells.append(f"{d['success_rate']:5.2f}" if d else "    -")
            print(f"    {arm.name:22s} " + "  ".join(cells))

    print("\n=== n_inliers <= 8 in EXP-003's own regimes (requirement 8) ===")
    for key in ("all_cases", "mixed_correct_wrong", "total_collapse", "all_correct"):
        d = mixed[key]
        rc = d["recall_detect_failure"]
        fp = d["false_positive_rate"]
        print(f"  {d['subset']:36s} n={d['n']:4d} wrong={d['n_wrong']:4d} "
              f"recall={'n/a' if rc is None else f'{rc:.4f}'} "
              f"FPR={'n/a' if fp is None else f'{fp:.4f}'}")

    print(f"\n=== VERDICT against pre-registered S1 ===")
    print(f"  {vd['criterion']}")
    for name, v in vd["per_arm"].items():
        void = f"  VOID on {v['void_on']}" if v["void_on"] else ""
        print(f"    {name:22s} MEETS_S1={str(v['MEETS_S1']):5s}{void}")
    print(f"\n  S1 met by any arm: {vd['S1_MET_BY_ANY_ARM']}  {vd['arms_meeting_S1']}")

    elapsed = time.perf_counter() - t_start
    payload = {
        "experiment": "EXP-003",
        "objective": ("Do illumination-robust representations extend the last "
                      "fully-successful Delta-azimuth beyond 30 deg on realistic "
                      "A-regimes?"),
        "preregistration": "docs/stages/EXP-003_illumination_robust_representations.md Part 1",
        "criterion_S1": vd["criterion"],
        "criterion_azimuth_deg": CRITERION_AZIMUTH,
        "failure_flag": f"n_inliers <= {INLIER_CUTOFF} (D-023)",
        "fit_rmse_policy": "recorded only; never used as a success/failure criterion",
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "platform": sys.platform,
        },
        "seeds": list(EXP003_SEEDS),
        "azimuth_grid_deg": list(AZIMUTH_GRID),
        "regimes": {r: {"realistic": TERRAIN_REGIMES[r].realistic,
                        "target_slope_median_deg": TERRAIN_REGIMES[r].target_slope_median_deg}
                    for r in PRIMARY_REGIMES},
        "arms": [{"name": a.name, "kind": a.kind, "note": a.note} for a in ARMS],
        "n_pairs": len(specs),
        "n_evaluations": len(rows),
        "total_runtime_s": elapsed,
        "summary_per_regime": summary,
        "mixed_regime_flag_analysis": mixed,
        "verdict": vd,
    }
    (OUT / "exp003_representations.json").write_text(
        json.dumps(payload, indent=2, default=float), encoding="utf-8")

    with open(OUT / "exp003_cases.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nwritten: {OUT/'exp003_representations.json'}")
    print(f"written: {OUT/'exp003_cases.csv'}")
    print(f"total runtime {elapsed/60:.1f} min")


if __name__ == "__main__":
    main()
