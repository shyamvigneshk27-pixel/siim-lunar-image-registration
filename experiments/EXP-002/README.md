# EXP-002 — RANSAC defect, terrain realism, threshold validation, GT-free estimators

**Status:** complete. Four objectives, each with an explicit acceptance criterion and an honest verdict.

Terminology used throughout, per the brief:
**[OBSERVED]** measured in this experiment · **[HYPOTHESIS]** proposed, not yet tested · **[CRITERION]** the bar set in advance · **[DECISION]** what we changed as a result.

---

## Commands executed

```bash
python scripts/run_exp002_ransac.py       # objective 1     ~40 s
python scripts/run_exp002_terrain.py      # objective 2     ~7 min
python scripts/run_exp002_threshold.py    # objective 3    ~13 min
python scripts/run_exp002_gtfree.py       # objective 4     ~30 s
python scripts/run_exp001.py              # EXP-001 re-run  ~4.5 min
python -m pytest tests/                   # 168 passed, 2 skipped, 22 s
```

Old EXP-001 results preserved unmodified at `experiments/EXP-001/results_preEXP002.csv`.

---

## Objective 1 — LO-RANSAC scaling defect

### Diagnosis: two independent causes, not one

Profiling the pre-fix code on the offending case (n = 2115, projective, ~100% inliers) showed **51.55 s of 53.9 s inside `numpy.linalg.svd`**, across 298 `estimate` calls.

**Cause 1 — a numerical defect (dominant).** `estimate_projective` called `np.linalg.svd(a)` with the default `full_matrices=True`. The DLT design matrix is `(2N × 9)`, so the full SVD also builds `U` at `(2N × 2N)` — **4230 × 4230 = 17,892,900 elements** — which is then discarded. Only the last row of `Vt` is used.

| n | `full_matrices=True` | `full_matrices=False` | speedup | `U` elements |
|---|---|---|---|---|
| 2115 | 498.86 ms | **1.01 ms** | **493×** | 17,892,900 → 38,070 |

Singular values identical, `Vt` identical up to sign. **[OBSERVED]** This is a mathematically identical change, not an approximation.

**Cause 2 — an algorithmic defect.** Local optimisation ran on *every* sample whose consensus exceeded the minimal set, rather than only on a new best as in Chum, Matas & Kittler (2003). 298 fits for 100 iterations.

### Before / after

| | total | inliers | iterations | LO refits | true error |
|---|---|---|---|---|---|
| **before** (profiled, real pre-fix code) | **54.29 s** | 2115 | 100 | 198 | — |
| **before** (EXP-001 recorded `ransac_s`) | **58.86 s** | 2115 | — | — | — |
| **after** | **0.056 s** | 2115 | 100 | 3 | 0.0119 px |

**Speedup ≈ 970×**, same inlier set. **[OBSERVED]**

*Honesty note:* `scripts/run_exp002_ransac.py` contains a `_legacy_ransac` re-implementation for the comparison, but it is **not bit-faithful** — it performs 27 LO refits where the real pre-fix code performed 198, so it reports only 5.12 s and **under-states the defect**. The authoritative numbers are the two direct measurements of the real pre-fix code, above.

### Stage timing (spec §37 — required, and what made the diagnosis possible)

| stage | after |
|---|---|
| sampling | 2.42 ms |
| minimal fit | 32.41 ms |
| scoring | 15.75 ms |
| local optimisation | 2.56 ms |
| final fit | 2.38 ms |

Scaling with correspondence count (projective):

| n | 200 | 500 | 1000 | 2000 | 4000 |
|---|---|---|---|---|---|
| total | 54.3 ms | 50.9 ms | 50.2 ms | 56.1 ms | 89.2 ms |

### Robustness was not traded for speed **[CRITERION: recall and error must not degrade]**

| outliers | 0% | 30% | 50% | 60% | 70% | 80% |
|---|---|---|---|---|---|---|
| inlier recall | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| true error (px) | 0.027 | 0.038 | 0.037 | 0.049 | 0.054 | 0.050 |

**[OBSERVED] Criterion met.** A `lo_max_points` cap was added on the LO *refit* sample, but **scoring is never subsampled** — the consensus set that decides the winner always sees every correspondence, so the robustness criterion is untouched. Pinned by `test_scoring_is_never_subsampled` and `test_lo_subsampling_does_not_degrade_accuracy`.

### EXP-001 re-run: are the numbers unchanged? **[CRITERION stated in advance: no case may flip between correct and wrong]**

| | before | after |
|---|---|---|
| success/failure flips | — | **0 / 45** ✅ |
| max \|Δ\| true error, correct cases | — | **0.585 px** |
| max \|Δ\| inlier count, correct cases | — | 102 |
| total pipeline time | 86.7 s | **28.6 s** |
| slowest single case | 59.06 s | **3.64 s** |

**[OBSERVED]** Criterion met: every case kept its classification. Results are **not** bit-identical, because changing when LO fires changes RANSAC's search trajectory. The tolerance is therefore stated explicitly: **conclusions are reproduced; individual transform errors move by up to 0.59 px.**

That 0.59 px number is itself a finding. It **exceeds several differences EXP-001 reported**, including RootSIFT vs plain SIFT at Δaz = 0 (0.359 vs 0.223 px = 0.136 px). EXP-001 flagged that as possibly noise; it is now measured to be noise. See RL-014.

### Regression protection
`tests/test_ransac_performance.py` (12 tests). Where a machine-independent invariant exists it is asserted instead of a timing: SVD output shapes, and LO refit counts (≤ 20 for 100 iterations, vs 198 before).

---

## Objective 2 — Terrain realism

### How realism is controlled

Anchored to published LOLA slope statistics at a **15 m baseline** (sources.md S7): highlands median **9.1°** (mean 11.0, sd 7.0); mare median **3.5°** (mean 4.9, sd 4.5); slopes beyond the **~33° angle of repose** are "almost absent".

Two separate controls, which the old `relief` parameter conflated:

- **Geometry (amplitude):** `target_slope_median_deg` rescales heights so the median slope hits the target exactly. `k = tan(target)/tan(current_median)`. This is a **pure vertical rescale — it does not touch horizontal coordinates, so ground-truth geometry is untouched** (`test_normalise_slope_is_a_pure_vertical_rescale`).
- **Feature density (spectrum):** `octaves`, `persistence`, `crater_density` set high-frequency content.

Baseline dependence is stated rather than hidden: the Moon is rougher at shorter baselines, so these 15 m figures understate roughness at OHRC's 0.25 m/px.

### Measured regimes (5 seeds each, 512²)

| regime | median | mean | p90 | p99 | > repose | kp/Mpx | realistic |
|---|---|---|---|---|---|---|---|
| **A_mare_moderate** | 3.50° | 3.75° | 6.41° | 9.32° | 0.00% | 312 | ✅ |
| **A_highlands_moderate** | 9.10° | 9.62° | 16.34° | 22.64° | 0.00% | 22 119 | ✅ |
| **B_highlands_challenging** | 18.00° | 18.58° | 30.71° | 40.05° | 6.36% | 32 582 | ✅ |
| **C_extreme_diagnostic** | 58.53° | 55.01° | 71.50° | 76.76° | **89.55%** | 31 246 | ❌ |

**[OBSERVED]** A-regimes reproduce the LOLA medians exactly (3.50 vs 3.5; 9.10 vs 9.1). The EXP-001 terrain has **89.55% of its surface steeper than the angle of repose** — confirming it is physically impossible on the Moon.

**C is retained, not deleted**, as required: it is the diagnostic stress test and it keeps EXP-001 exactly reproducible (`target_slope_median_deg=None` disables normalisation bit-identically).

### Density and geometry are separable **[CRITERION: vary one at fixed other]**

| persistence / octaves | 0.35 / 4 | 0.45 / 5 | 0.60 / 6 | 0.70 / 7 |
|---|---|---|---|---|
| slope median | **9.10°** | **9.10°** | **9.10°** | **9.10°** |
| kp/Mpx | 1 287 | 4 885 | 22 135 | 30 404 |

**[OBSERVED]** Median slope held to 2 d.p. while feature density varies **24×**. Criterion met.

### How the EXP-001 conclusions change (108 cases, 4 regimes × 3 seeds)

**Illumination — success rate by Δazimuth:**

| regime | 0° | 15° | 30° | 45° | 60° | 90° | last fully-successful |
|---|---|---|---|---|---|---|---|
| A_mare_moderate | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | **15°** |
| A_highlands_moderate | 1.00 | 1.00 | 0.67 | 0.00 | 0.00 | 0.00 | **15°** |
| B_highlands_challenging | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 30° |
| C_extreme_diagnostic (EXP-001) | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 30° |

**[OBSERVED] On realistic terrain the cliff arrives EARLIER, not later: between 15° and 30°, versus 30°–45° reported in EXP-001.** EXP-001 was optimistic because its implausibly steep terrain produced abnormally strong shading gradients. RootSIFT is *worse* on real-looking terrain than EXP-001 suggested.

**Scale — success rate:**

| regime | 1.0× | 2.0× | 4.0× |
|---|---|---|---|
| A_mare_moderate | 1.00 | **0.33** | **0.00** |
| A_highlands_moderate | 1.00 | 1.00 | 1.00 |
| B_highlands_challenging | 1.00 | 1.00 | 1.00 |
| C_extreme_diagnostic | 1.00 | 1.00 | 1.00 |

**[OBSERVED] EXP-001's "scale survives to 4×" is false for realistic low-texture mare, which already fails at 2×.** It holds for textured terrain. The conclusion was terrain-dependent and was stated too generally.

---

## Objective 3 — Independent validation of the failure threshold

**Protocol.** 192 calibration cases (seeds 1001–1004) and 192 validation cases (seeds 7001–7004, **different terrain**). 4 regimes × 4 Δazimuth × 3 transform models. Every threshold is chosen by Youden's J on calibration and reported **only** on validation. `fit_rmse` is included as a **negative control**: RL-010 predicts it carries no failure information.

Calibration: 94/192 wrong. Validation: 103/192 wrong.

### EXP-001's claim, tested on data it never saw

> "wrong cases have ≤ 7 inliers, correct cases have ≥ 8"

| | validation |
|---|---|
| wrong, max inliers | 7 |
| correct, **min** inliers | **2** |
| **claim holds** | **❌ FALSE** |

**[OBSERVED] The perfect-separation claim is refuted.** One correct case (mare, Δaz = 20°) succeeded on **2 inliers** — with `coverage_max_gap = 0.520`, i.e. a fluke that the coverage metric independently flags as fragile.

**But the operating point itself generalises well.** Thresholding at `n_inliers < 8`:

| | validation |
|---|---|
| recall (failures detected) | **1.000** |
| false-positive rate | **0.011** |

So the correct statement is not "8 separates the classes" (false) but "**flag failure when inliers < 8** gives 100% recall at 1.1% false alarms on 192 unseen cases" — a validated operating point rather than a claimed law.

### Signal comparison (thresholds from calibration, scored on validation)

| signal | ROC AUC | PR AUC | recall | FPR | verdict |
|---|---|---|---|---|---|
| `n_inliers` | **0.993** | 0.991 | 1.000 | 0.011 | best genuinely informative signal |
| `split_consistency` | 0.994 | 0.990 | 1.000 | 0.011 | ⚠️ **inflated — see below** |
| `coverage_max_gap` | 0.983 | 0.985 | 0.951 | 0.112 | informative, higher false alarms |
| `inlier_ratio` | 0.982 | 0.991 | 0.913 | 0.000 | misses 8.7% of failures |
| `held_out_median` | 0.975 | 0.981 | 0.971 | 0.022 | ⚠️ **inflated — see below** |
| **`fit_rmse`** (negative control) | **0.495** | 0.704 | 0.388 | 0.045 | **chance. Confirms RL-010.** |

**`fit_rmse` scores ROC AUC 0.495 — indistinguishable from a coin flip.** **[OBSERVED]** The negative control behaved exactly as RL-010 predicted, which is meaningful independent support for ADR-0003.

### ⚠️ The inflated AUCs — an artefact I nearly reported as a result

`split_consistency` is **non-finite in 104/192 validation cases, 103 of them wrong**. Among the 88 cases where it *is* finite, **zero are wrong**. `held_out_median` is non-finite in 100/192, 99 of them wrong.

Both estimators return `inf` precisely when there are too few inliers to evaluate them — so their apparent 0.97–0.99 AUC is **a proxy for low inlier count, not independent information**. **[OBSERVED]**

This matters: it means objective 3 never actually tested these estimators against the failure they exist for. The failures the image pipeline produces here are *illumination collapse* (3–7 inliers), which counting already catches. That gap is what objective 4 was built to close.

### Sensitivity of `n_inliers` (validation)

| by regime | recall | FPR | AUC |
|---|---|---|---|
| A_mare_moderate | 1.000 | 0.059 | 0.971 |
| A_highlands_moderate | 1.000 | 0.000 | 1.000 |
| B_highlands_challenging | 1.000 | 0.000 | 1.000 |
| C_extreme_diagnostic | 1.000 | 0.000 | 1.000 |

By transform model: similarity 1.000/0.031, affine 1.000/0.000, projective 1.000/0.000.
By Δazimuth: 0° and 20° evaluable (recall 1.000, FPR ≤ 0.023); **40° and 60° are degenerate subsets — every case fails**, so discrimination is undefined there. That degeneracy is itself the objective-2 cliff restated.

---

## Objective 4 — Which GT-free estimator detects a coherent wrong answer?

Objective 3 showed the estimators were never challenged. So objective 4 **constructs** adversarial cases with **300 correspondences each**, so a failure cannot be caught by counting. Thresholds from calibration seeds, reported on disjoint validation seeds.

### Part A — correspondence-level (96 validation cases)

| case kind | wrong? | true error | `held_out` | flagged | `split` | flagged |
|---|---|---|---|---|---|---|
| correct | no | 0.00 | 0.48 | 0.00 | 0.15 | 0.00 |
| correct_noisy | no | 0.00 | 1.42 | 0.00 | 0.54 | 0.00 |
| clustered_correct | no | 0.00 | 0.48 | 0.00 | 0.29 | 0.00 |
| **lattice_shift** | **yes** | **64.00** | **0.47** | **0.00** | **0.17** | **0.00** |
| **repeated_texture** | **yes** | **64.00** | **0.47** | **0.00** | **0.22** | **0.00** |
| **coherent_affine** | **yes** | **52.71** | **0.48** | **0.00** | **0.16** | **0.00** |
| **partial_overlap** | **yes** | **21.14** | **0.47** | **0.00** | **0.52** | **0.00** |
| low_inlier_degenerate | yes | 275.65 | ∞ | 1.00 | ∞ | 1.00 |

**Detection rate: 0.200 for both** (1 of 5 wrong kinds), false alarm 0.000.

**[OBSERVED] Held-out residual and spatial split consistency are completely blind to every coherent wrong solution.** A match set 64 px wrong yields a held-out residual of **0.47 px** — *lower* than a genuinely correct but noisy set (1.42 px). They detect only the degenerate low-inlier case.

Note `partial_overlap`: split consistency gives **0.52** versus **0.54** for a correct noisy set — indistinguishable. I expected this estimator to catch that case; it does not.

### Part B — cycle consistency vs loop closure (48 validation cases)

| case kind | wrong? | true error | `cycle` | flagged | `loop` | flagged |
|---|---|---|---|---|---|---|
| correct | no | 0.38 | 0.32 | 1.00 | 0.62 | **0.00** |
| lattice_all_edges | yes | 64.00 | 0.00 | 1.00 | **190.08** | **1.00** |
| lattice_one_edge | yes | 64.00 | 0.00 | 1.00 | **62.75** | **1.00** |
| symmetric_wrong | yes | 64.00 | 0.00 | 1.00 | **62.75** | **1.00** |

| estimator | detection | false alarm |
|---|---|---|
| `cycle_error` | 1.000 | **1.000** |
| **`loop_error`** | **1.000** | **0.000** |

**[OBSERVED] Loop closure is the only estimator that detects coherent wrong solutions — 100% detection at 0% false alarm.** A one-period error on each edge accumulates to **190.08 px ≈ 3 × 64** around the loop instead of cancelling. This is exactly the mechanism ANALYSIS §F.1.4 was designed around, now measured.

**Cycle consistency is worse than useless here — and I built the case that way.** For the wrong cases the forward and backward transforms are exact inverses, so the round trip cancels to 0.00 while the *correct* case carries 0.32 px of jitter. The signal is therefore **inverted**, and thresholding flags everything. Two caveats stated plainly: this construction deliberately targets cycle consistency's structural blind spot, and in a real pipeline the reverse pass is an independent estimate that would not cancel exactly. The honest conclusion is narrower than the table looks: **cycle consistency cannot detect symmetric errors**, not "cycle consistency is useless".

### Scope limits of objective 4

Parts A and B are **constructed**, not produced by the image pipeline. That is deliberate — objective 3 established that the real pipeline's failures on this data are low-inlier collapse, so many-inlier coherent wrongness had to be built to be tested at all. These results demonstrate the estimators' *mathematics*, and do not yet establish how often such cases arise on real lunar imagery. **[HYPOTHESIS, untested]**

---

## Acceptance criteria — verdicts

| # | Criterion (set in advance) | Verdict |
|---|---|---|
| 1 | Speedup with mathematical correctness preserved | ✅ ~970×, identical inlier set, `Vt` provably identical |
| 1 | Robustness not weakened | ✅ recall 1.000 at 0–80% outliers |
| 1 | Stage-level timing | ✅ 5 stages + refit counts |
| 1 | Regression test | ✅ 12 tests, shape/count invariants where possible |
| 1 | EXP-001 unchanged within a stated tolerance | ✅ 0/45 flips; **tolerance: ±0.59 px** |
| 2 | ≥3 regimes with controlled slope statistics | ✅ 4 regimes, LOLA medians hit exactly |
| 2 | Density controlled independently of geometry | ✅ 24× density range at fixed 9.10° median |
| 2 | Extreme terrain retained, old results preserved | ✅ regime C + `results_preEXP002.csv` |
| 2 | Multiple seeds | ✅ 5 seeds (stats), 3 seeds (cases) |
| 3 | Threshold not selected on its evaluation data | ✅ disjoint seeds, different terrain |
| 3 | Report if 8 is not stable | ✅ **claim refuted**; operating point validated separately |
| 4 | Estimators not tuned on reporting cases | ✅ calibration/validation split |
| 4 | Detection + false-alarm per catastrophic kind | ✅ full tables |

---

## What EXP-003 should be

**[DECISION] EXP-003 remains the representation comparison, and objective 2 has sharpened its target.**

1. **The bar moved.** The cliff on realistic terrain is **15°–30°**, not 30°–45°. EXP-003's success criterion should be stated against `A_highlands_moderate` and `A_mare_moderate`, not the extreme regime. **[CRITERION for EXP-003: a representation earns its place only if it moves the last-fully-successful Δazimuth beyond 30° on A-regimes.]**
2. **Report per regime, never pooled.** Objective 2 showed conclusions invert between regimes (scale is easy on highlands, fails at 2× on mare).
3. **Mare is the priority case.** It fails earliest on both axes and has 70× fewer keypoints. A representation that only helps on textured terrain has not solved the problem.
4. **Use the validated failure signal.** `n_inliers < 8` (recall 1.000, FPR 0.011) is the success/failure criterion, not `fit_rmse` (AUC 0.495).
5. **Carry loop closure forward as the only trustworthy GT-free check.** Held-out residual and split consistency should be kept for *degeneracy* detection, where they work, and must not be described as safety nets against wrong-but-consistent answers.
6. **Resolve the 15°–30° cliff edge** at 18/21/24/27° on A-regimes, with ≥3 seeds.
7. Runtime is no longer a constraint: median pipeline 0.39 s, worst case 3.64 s.

---

## Files

| file | contents |
|---|---|
| `objective1_ransac.json` | SVD benchmark, before/after, robustness, scaling |
| `objective2_terrain.json` / `objective2_terrain_cases.csv` | regime statistics, separability, 108 cases |
| `objective3_threshold.json` / `objective3_threshold_cases.csv` | 384 cases, signal comparison, sensitivity |
| `objective4_gtfree.json` / `objective4_gtfree_partA.csv` / `..._partB.csv` | adversarial cases, detection rates |
| `../EXP-001/results_preEXP002.csv` | EXP-001 results before the RANSAC fix, preserved |
