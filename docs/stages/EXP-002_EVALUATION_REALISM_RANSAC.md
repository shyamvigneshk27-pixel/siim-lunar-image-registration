# EXP-002 — RANSAC defect, terrain realism, threshold validation, GT-free estimators

**Stage ID:** EXP-002 · **Status:** COMPLETE
**Date:** 2026-08-24 (the only date recorded in repository artefacts)
**Depends on:** EXP-001 · **Followed by:** EXP-003 (not started)

> **Reconstruction note.** Reconstructed from `experiments/EXP-002/README.md`, `objective1_ransac.json`, `objective2_terrain.json` + `_cases.csv`, `objective3_threshold.json` + `_cases.csv`, `objective4_gtfree.json` + `_partA.csv` / `_partB.csv`, the four `scripts/run_exp002_*.py`, `scripts/exp002_common.py`, `src/siim/evaluation/gtfree.py`, `src/siim/verification/ransac.py`, `src/siim/data/synthetic_terrain.py`, `tests/test_ransac_performance.py`, `tests/test_gtfree_and_terrain.py`, `docs/research_log.md` RL-015 – RL-021, ADR-0011/ADR-0012, `docs/sources.md` S7.
>
> **No git history exists.** The pre-fix source text of `ransac.py` and `estimate.py` is **not preserved in the repository**; only the measured pre-fix numbers and a deliberately-labelled non-faithful re-implementation (`_legacy_ransac` in `run_exp002_ransac.py`) survive.

EXP-002 is the stage that most changed the research direction. It is documented objective by objective.

---

# OBJECTIVE 1 — LO-RANSAC performance

## 1.1 The symptom

EXP-001 recorded one case at **59.06 s** against a **0.387 s** median — a ~150× outlier. `results_preEXP002.csv` shows `ransac_s = 58.86` for `A_model/truth=projective` (n = 2115 putative, ~100% inliers).

EXP-001's own diagnosis attributed this to local optimisation refitting the full consensus set. **That diagnosis was incomplete.**

## 1.2 Discovery: two independent defects

Profiling the real pre-fix code (`cProfile`, recorded in `objective1_ransac.json:before_measured_directly`):

- total **53.9 s**, of which **51.55 s inside `numpy.linalg.svd`**
- **298** `estimate` calls for 100 iterations

The dominant cost was numerical, not algorithmic. Both defects are documented below.

---

### BUG 1 — `np.linalg.svd(full_matrices=True)` in the DLT

**Problem:** `estimate_projective` called `np.linalg.svd(a)` with the numpy default `full_matrices=True`.

**Observed symptom:** 51.55 s of 53.9 s inside `svd`; a single projective fit on 2115 points cost **373.93 ms**.

**Root cause:** The DLT design matrix is `(2N × 9)`. With `full_matrices=True`, numpy also constructs `U` at `(2N × 2N)` — for N = 2115 that is **4230 × 4230 = 17,892,900 elements** — and the DLT then discards it, using only the last row of `Vt`.

**How it was discovered:** Profiling by cumulative time, which put `numpy.linalg._linalg.svd` at 51.533 s tottime across 596 calls; then isolating the two SVD modes on a synthetic matrix of the same shape.

**Fix:** `np.linalg.svd(a, full_matrices=False)`. One keyword.

**Validation** (`objective1_ransac.json:svd_defect.n_2115`):

| | `full_matrices=True` | `full_matrices=False` |
|---|---|---|
| time | 498.86 ms | **1.01 ms** |
| `U` elements | 17,892,900 | 38,070 |
| speedup | — | **492.8×** |
| singular values identical | — | **True** |
| `Vt` identical (up to sign) | — | **True** |

**This is a mathematically identical change**, not an approximation — the quantities the DLT consumes are bit-comparable.

**Regression test:** `test_dlt_uses_the_economy_svd` asserts on **output shapes**, so it is machine-independent; `test_large_projective_fit_is_fast` bounds the fit at 50 ms (two orders below the defect, two above the fixed cost).

**Impact:** ~493× on the dominant cost.

---

### BUG 2 — Local optimisation on every sufficient sample

**Problem:** LO ran on *every* sample whose consensus exceeded the minimal set, rather than only when a **new best** model was found.

**Observed symptom:** 298 `estimate` calls for 100 iterations (~198 large refits).

**Root cause:** Deviation from LO-RANSAC as published (Chum, Matas & Kittler, 2003), in which LO is triggered only on a new best — an O(log n) event.

**How it was discovered:** The `estimate` call count in the profile could not be explained by 100 minimal fits alone.

**Fix:** `if count <= best_count: continue` before the LO block (`ransac.py`), restoring the published algorithm. A `lo_max_points` cap (default 1000) was added on the LO **refit sample**.

**Validation:** LO refits **198 → 3** on the same case. Crucially, **scoring is never subsampled** — the consensus set that decides the winner always sees every correspondence; only the least-squares refit that *proposes* a candidate is capped. A 1000-point fit is already vastly over-determined for a model with at most 8 DOF.

**Regression tests:** `test_lo_runs_only_on_a_new_best` asserts **refit count ≤ 20** for 100 iterations (machine-independent); `test_scoring_is_never_subsampled` asserts all 3000 true inliers are found with `lo_max_points=50`; `test_lo_subsampling_does_not_degrade_accuracy` bounds the capped-vs-uncapped difference at 0.05 px.

**Impact:** Restores published behaviour and removes ~195 unnecessary large fits.

---

## 1.3 Combined before/after

`objective1_ransac.json:ransac_before_after`:

| | total | inliers | iterations | LO refits | true error |
|---|---|---|---|---|---|
| **before** (profiled, real pre-fix code) | **54.29 s** | 2115 | 100 | 198 | — |
| **before** (EXP-001 recorded `ransac_s`) | **58.86 s** | 2115 | — | — | — |
| **after** | **0.056 s** | 2115 | 100 | 3 | 0.0119 px |

**Speedup ≈ 968×** on the same case, same inlier set.

**Honesty note, recorded in the artefact itself.** `_legacy_ransac` in `run_exp002_ransac.py` is a re-implementation for the comparison and is **not bit-faithful**: it performs 27 LO refits where the real pre-fix code performed 198, and therefore reports only 5.12 s — **under-stating the defect**. The JSON labels the two sources separately (`before_measured_directly` vs `before_emulated`). The direct measurements are the ones quoted.

## 1.4 Stage timing (spec §37)

`RansacTiming` now records five stages plus refit counts on every run — this is what made the defect diagnosable at all.

| stage | after |
|---|---|
| sampling | 2.42 ms |
| minimal fit | 32.41 ms |
| scoring | 15.75 ms |
| local optimisation | 2.56 ms |
| final fit | 2.38 ms |

Scaling with correspondence count (projective, from `objective1_ransac.json:scaling`): n = 200 → 53.3 ms · 500 → 45.7 ms · 1000 → 50.8 ms · 2000 → 59.3 ms · 4000 → 73.1 ms.

## 1.5 Robustness unchanged

**Criterion set in advance:** robustness must not be traded for runtime.

| outliers | 0% | 30% | 50% | 60% | 70% | 80% |
|---|---|---|---|---|---|---|
| inlier recall | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| true error (px) | 0.027 | 0.038 | 0.037 | 0.049 | 0.054 | 0.050 |

**Criterion met.**

## 1.6 EXP-001 re-run

**Criterion set in advance:** no case may flip between correct and wrong.

| | before | after |
|---|---|---|
| success/failure flips | — | **0 / 45** ✅ |
| max \|Δ\| true error, correct cases | — | **0.5853 px** |
| max \|Δ\| inlier count, correct cases | — | 102 |
| total pipeline time | 86.7 s | **28.6 s** |
| slowest `ransac_s` | 58.86 s | **3.505 s** |

**Criterion met**, with an explicitly stated tolerance: results are **not bit-identical**, because changing when LO fires changes the search trajectory. Conclusions reproduce; individual transform errors move by up to **0.59 px**.

That tolerance is itself a finding (RL-016): it **exceeds** the 0.136 px RootSIFT-vs-SIFT difference EXP-001 flagged as possibly noise. It is noise.

---

# OBJECTIVE 2 — Terrain realism

## 2.1 The original problem

EXP-001's terrain was recorded in its own limitations as "too steep and too high-frequency": p99 |∂z/∂x| = 4.79, i.e. ~**78° slopes**, and 2000+ SIFT keypoints per 512² frame.

**Why this is a physical-realism problem, not a cosmetic one.** Published LOLA statistics (sources.md S7) give, at a 15 m baseline: highlands median **9.1°** (mean 11.0, sd 7.0); mare median **3.5°** (mean 4.9, sd 4.5). The slope-frequency distribution shows a **steep rollover at the ~33° angle of repose**, and slopes materially steeper are "almost absent" because the fractured megaregolith lacks the cohesion to hold them.

## 2.2 How realism is now controlled

Two controls, separating what the old single `relief` parameter conflated:

- **Geometry (amplitude):** `target_slope_median_deg` rescales heights so the median slope hits the target exactly — `k = tan(target)/tan(current_median)`, valid because arctan is monotonic. This is a **pure vertical rescale: it does not touch horizontal coordinates, so ground-truth geometry is preserved.** Pinned by `test_normalise_slope_is_a_pure_vertical_rescale`.
- **Feature density (spectrum):** `octaves`, `persistence`, `crater_density`.

`REFERENCE_BASELINE_M = 15.0` is recorded alongside every target, because slope statistics are strongly baseline-dependent and a median is meaningless without one. This also makes the OHRC caveat explicit: at 0.25 m/px the real surface is rougher than these 15 m figures.

## 2.3 Regimes measured (5 seeds, 512²)

`objective2_terrain.json:regime_statistics`:

| regime | median | mean | p90 | p99 | > repose | kp/Mpx | classification |
|---|---|---|---|---|---|---|---|
| **A_mare_moderate** | 3.50° | 3.75° | 6.41° | 9.32° | 0.00% | 312 | **realistic benchmark** |
| **A_highlands_moderate** | 9.10° | 9.62° | 16.34° | 22.64° | 0.00% | 22 119 | **realistic benchmark** |
| **B_highlands_challenging** | 18.00° | 18.58° | 30.71° | 40.05° | 6.36% | 32 582 | **challenging benchmark** |
| **C_extreme_diagnostic** | 58.53° | 55.01° | 71.50° | 76.76° | **89.55%** | 31 246 | **diagnostic stress test — NOT realistic** |

The A-regimes reproduce the published LOLA medians exactly (3.50 vs 3.5; 9.10 vs 9.1).

**The EXP-001 terrain has 89.55% of its surface steeper than the angle of repose** — physically impossible on the Moon.

The three classifications are kept distinct throughout, and `TerrainRegime.realistic` is a machine-readable flag so the distinction cannot be lost:

- **realistic benchmark** — conclusions about real lunar imagery may be drawn (subject to all other synthetic-data caveats).
- **challenging benchmark** — physically plausible but at the rough end of the real distribution.
- **diagnostic stress test** — physically impossible; used only to stress the algorithm and to reproduce EXP-001.

## 2.4 Why the old terrain was preserved rather than replaced

Silently replacing it would have been scientifically wrong for three reasons, all acted on:

1. **EXP-001's results would have become unreproducible.** `target_slope_median_deg=None` disables normalisation **bit-identically** (`test_none_target_disables_normalisation` asserts `np.array_equal`), so regime C reproduces EXP-001 exactly.
2. **The change to the conclusions would have been invisible.** Keeping C is what makes the comparison in §2.6 possible — the cliff moving from 30° to 15° is only demonstrable if both terrains exist.
3. **A stress test has independent value.** Extreme terrain probes algorithm behaviour outside the physical envelope.

Old numeric results are preserved at `experiments/EXP-001/results_preEXP002.csv`.

## 2.5 Density is separable from geometry

**Criterion set in advance:** vary one at a fixed value of the other.

`objective2_terrain.json:density_slope_separability`:

| persistence / octaves | 0.35 / 4 | 0.45 / 5 | 0.60 / 6 | 0.70 / 7 |
|---|---|---|---|---|
| slope median | **9.10°** | **9.10°** | **9.10°** | **9.10°** |
| slope p99 | 33.94° | 25.16° | 22.59° | 22.48° |
| kp/Mpx | 1 287 | 4 885 | 22 135 | 30 404 |

Median held to 2 d.p. while density varies **~24×**. **Criterion met.** Pinned by `test_feature_density_varies_at_fixed_slope`.

## 2.6 How the EXP-001 conclusions change

108 cases (4 regimes × 3 seeds × 9 conditions), images 384², `objective2_terrain_cases.csv`.

**Illumination — success rate by Δazimuth:**

| regime | 0° | 15° | 30° | 45° | 60° | 90° | last fully successful |
|---|---|---|---|---|---|---|---|
| A_mare_moderate | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | **15°** |
| A_highlands_moderate | 1.00 | 1.00 | 0.67 | 0.00 | 0.00 | 0.00 | **15°** |
| B_highlands_challenging | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 30° |
| C_extreme (EXP-001) | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 30° |

**On realistic terrain the cliff arrives EARLIER: 15–30°, not the 30–45° EXP-001 reported.** RootSIFT is *worse* on real-looking terrain than EXP-001 concluded (RL-017).

**Scale — success rate:**

| regime | 1.0× | 2.0× | 4.0× |
|---|---|---|---|
| A_mare_moderate | 1.00 | **0.33** | **0.00** |
| A_highlands_moderate | 1.00 | 1.00 | 1.00 |
| B / C | 1.00 | 1.00 | 1.00 |

**EXP-001's "scale survives to 4×" is false for realistic low-texture mare** (RL-018).

---

# OBJECTIVE 3 — Threshold validation

## 3.1 The original claim and why it was not evidence

EXP-001 (RL-011) observed: *wrong cases have at most 7 inliers, correct cases at least 8.* Two problems, both flagged in EXP-001's own README:

1. The threshold and its evaluation came from **the same 45 cases**.
2. The split sat exactly at the `min_inliers = 8` value `classify_failure` already used.

It had, moreover, already broken: after the objective-1 RANSAC fix, the re-run gave wrong max = 7 but correct **min = 6** — overlapping.

## 3.2 Protocol

- **192 calibration** cases, seeds `1001–1004`.
- **192 validation** cases, seeds `7001–7004` — **disjoint seeds building different terrain**.
- 4 regimes × 4 Δazimuth (0, 20, 40, 60°) × 3 transform models.
- Every threshold chosen by **Youden's J on calibration only**, reported **only** on validation.
- `fit_rmse` included as a deliberate **negative control**: RL-010 predicts it carries no failure information.

Calibration: 94/192 wrong. Validation: 103/192 wrong.

## 3.3 The mandatory distinction

Two statements were conflated in EXP-001, and they are **not** the same claim:

| | Statement | Status |
|---|---|---|
| **(a)** "the exact separation observed in the original sample" — *wrong ≤ 7 and correct ≥ 8, with no overlap* | a property of 45 specific cases | **REFUTED** |
| **(b)** "the operating rule independently validated on unseen cases" — *flag failure when `n_inliers < 8`* | a decision rule with a measured error rate | **VALIDATED** |

**(a) refuted** (`objective3_threshold.json:exp001_claim`): validation wrong max = 7, correct **min = 2**, `holds: false`. One *correct* case (mare, Δaz 20°) succeeded on **2 inliers** — with `coverage_max_gap = 0.520`, a fluke that the coverage metric independently flagged.

**(b) validated:** at threshold 8 — **recall 1.000, FPR 0.0112** on 192 unseen cases.

The distinction matters because (a) invites treating 8 as a law about the world, while (b) is an empirical decision rule with a stated false-alarm rate and a stated domain of validity. Only (b) is usable, and only (b) was earned.

## 3.4 Signal comparison (validation)

| signal | ROC AUC | PR AUC | recall | FPR | verdict |
|---|---|---|---|---|---|
| `n_inliers` | **0.993** | 0.991 | 1.000 | 0.011 | best genuinely informative signal |
| `split_consistency` | 0.994 | 0.990 | 1.000 | 0.011 | ⚠️ **artefact — §3.5** |
| `coverage_max_gap` | 0.983 | 0.985 | 0.951 | 0.112 | informative, higher false alarms |
| `inlier_ratio` | 0.982 | 0.991 | 0.913 | 0.000 | misses 8.7% of failures |
| `held_out_median` | 0.975 | 0.981 | 0.971 | 0.022 | ⚠️ **artefact — §3.5** |
| **`fit_rmse`** (negative control) | **0.495** | 0.704 | 0.388 | 0.045 | **chance** |

**`fit_rmse` scores ROC AUC 0.495 — indistinguishable from a coin flip.** As a failure detector it carries essentially no information, exactly as RL-010 predicted. This is independent support for ADR-0003 obtained from a pre-declared negative control rather than from re-examining the original data.

## 3.5 The `split_consistency` artefact

`objective3_threshold.json` records `best_deployable_signal: split_consistency` — the automated selection by ROC AUC. **Manual inspection showed this to be an artefact, and the report does not follow the automated choice.**

Measured on the validation cases:

- `split_consistency` is **non-finite in 104/192** cases, **103 of them wrong**.
- Among the **88** cases where it is finite, **zero** are wrong.
- `held_out_median` is non-finite in **100/192**, 99 of them wrong.

Both estimators return `inf` precisely when there are too few inliers to evaluate them. Their apparent 0.97–0.99 AUC is therefore **a proxy for low inlier count, not independent information**: the `inf` sentinel is doing all the work.

**Why the non-finite cases invalidate the AUC.** ROC AUC ranks a signal against a label. When a signal collapses to a single sentinel value on ~54% of cases, and that sentinel is almost perfectly aligned with the label, the AUC measures the *sentinel's* correlation with the label — i.e. "did this case have enough inliers to evaluate?" — not the estimator's discriminative content. The finite subset, where the estimator actually produces a value, contains **no wrong cases at all**, so the estimator was never asked to discriminate.

**Consequence:** objective 3 **never tested these estimators against the failure they exist for.** The failures the image pipeline produces here are illumination collapse to 3–7 inliers, which counting already catches. That gap is what objective 4 was built to close.

## 3.6 Sensitivity of `n_inliers` (validation)

| by regime | recall | FPR | AUC |
|---|---|---|---|
| A_mare_moderate | 1.000 | 0.059 | 0.971 |
| A_highlands_moderate | 1.000 | 0.000 | 1.000 |
| B_highlands_challenging | 1.000 | 0.000 | 1.000 |
| C_extreme_diagnostic | 1.000 | 0.000 | 1.000 |

By transform model: similarity 1.000 / 0.031 · affine 1.000 / 0.000 · projective 1.000 / 0.000.
By Δazimuth: 0° and 20° evaluable (recall 1.000, FPR ≤ 0.023). **40° and 60° are degenerate subsets — every case fails**, so discrimination is undefined there. That degeneracy is the objective-2 cliff restated.

---

# OBJECTIVE 4 — GT-free evaluation

## 4.1 Why this matters

On real lunar pairs there are no ground-truth correspondences, so all accuracy evidence must come from the correspondences and images themselves (ANALYSIS §F.1, ADR-0003). **None of these estimators may consult ground truth**; GT is used only to score how well they work.

Objective 3 established that the estimators had never actually been challenged (§3.5). Objective 4 therefore **constructs** adversarial cases with **300 correspondences each**, so that a failure cannot be detected simply by counting.

## 4.2 Part A — correspondence-level (96 validation cases, disjoint seeds)

`objective4_gtfree.json:part_a_correspondence_level`:

| case kind | wrong? | true error | `held_out` | flagged | `split` | flagged |
|---|---|---|---|---|---|---|
| correct | no | 0.00 | 0.483 | 0.00 | 0.148 | 0.00 |
| **correct_noisy** | no | 0.00 | **1.424** | 0.00 | **0.539** | 0.00 |
| clustered_correct | no | 0.00 | 0.476 | 0.00 | 0.293 | 0.00 |
| **lattice_shift** | **yes** | **64.00** | **0.468** | **0.00** | 0.172 | 0.00 |
| **repeated_texture** | **yes** | **64.00** | **0.470** | **0.00** | 0.223 | 0.00 |
| **coherent_affine** | **yes** | **52.71** | **0.477** | **0.00** | 0.155 | 0.00 |
| **partial_overlap** | **yes** | **21.14** | **0.474** | **0.00** | **0.523** | 0.00 |
| low_inlier_degenerate | yes | 275.65 | ∞ | 1.00 | ∞ | 1.00 |

**Detection rate 0.200 for both** (1 of 5 wrong kinds), false alarm 0.000.

**Counting cannot explain these results**, and that is the point: every case has 300 correspondences except the degenerate one, so `n_inliers` — the best signal from objective 3 — is uninformative here by construction.

**Held-out residual and spatial split consistency are completely blind to every coherent wrong solution.** A match set **64 px wrong** yields a held-out residual of **0.468 px** — *lower* than a genuinely **correct** but noisy set at **1.424 px**. The estimator would rank the catastrophic failure as the better result.

`partial_overlap` deserves separate note: split consistency gives **0.523** against **0.539** for a correct noisy set — indistinguishable. This was the case split consistency was most expected to catch. It does not.

**Mechanism:** both estimators measure **self-consistency**, and a uniformly wrong set is perfectly self-consistent. They detect only the degenerate `n ≈ DOF` case.

## 4.3 Part B — cycle consistency vs loop closure (48 validation cases)

| case kind | wrong? | true error | `cycle` | flagged | `loop` | flagged |
|---|---|---|---|---|---|---|
| correct | no | 0.38 | 0.325 | 1.00 | 0.622 | **0.00** |
| lattice_all_edges | yes | 64.00 | 0.000 | 1.00 | **190.08** | **1.00** |
| lattice_one_edge | yes | 64.00 | 0.000 | 1.00 | **62.75** | **1.00** |
| symmetric_wrong | yes | 64.00 | 0.000 | 1.00 | **62.75** | **1.00** |

| estimator | detection | false alarm |
|---|---|---|
| `cycle_error` | 1.000 | **1.000** |
| **`loop_error`** | **1.000** | **0.000** |

**Loop closure detects every constructed coherent wrong solution at zero false alarms.** A one-period (64 px) error on each of three edges accumulates to **190.08 px ≈ 3 × 64** around the loop, instead of cancelling. This is precisely the mechanism ANALYSIS §F.1.4 was designed around.

**Cycle consistency's false-alarm behaviour.** Its threshold was selected at 0.000, flagging everything, because in these constructions the wrong forward and backward transforms are **exact inverses** (cycle error 0.000) while the *correct* case carries 0.325 px of jitter. The signal is therefore **inverted**.

Two caveats, stated plainly and also recorded in ADR-0011:

1. **The construction deliberately targets cycle consistency's structural blind spot.** In a real pipeline the reverse pass is an *independent* estimate that would not cancel exactly.
2. The defensible claim is therefore **"cycle consistency cannot detect symmetric errors"** — not "cycle consistency is useless".

## 4.4 The claim, stated at exactly the strength the evidence supports

> **Loop closure is currently the strongest demonstrated GT-free estimator.**

**This must not be generalised beyond the tested constructions.** Parts A and B are **constructed transform- and correspondence-level cases**, not produced by the image pipeline. They demonstrate the estimators' *mathematics*. They do **not** establish:

- how often coherent wrong solutions arise on real lunar imagery — **Evidence insufficient.**
- how loop closure behaves when the three per-edge estimates come from a real matcher with correlated errors — **Evidence insufficient.**
- whether overlapping triplets will exist in the evaluation dataset — **Evidence insufficient** (ANALYSIS §F.1.4 already flagged this as unknown).

---

# Cross-cutting outcomes

## Hypotheses: outcome

| ID | Hypothesis | Outcome | Evidence |
|---|---|---|---|
| RL-011 | Inlier count separates wrong from correct cleanly | **REFUTED** | correct min = 2 on validation |
| RL-010 | Fit RMSE carries no failure information | **CONFIRMED** | ROC AUC 0.495, pre-declared negative control |
| ANALYSIS §F.1 | Held-out residual is the primary GT-free estimator | **REFUTED** | detection 0.200; blind to all coherent wrong cases |
| ANALYSIS §F.1.4 | Loop closure catches coherent wrong solutions | **CONFIRMED** | 1.000 / 0.000 on constructed cases |
| RL-009 | Cliff at Δaz 30–45° | **REFUTED (relocated)** | 15–30° on realistic terrain |
| EXP-001 §I.4 | Scale survives to 4× | **REFUTED in part** | mare fails at 2× |
| RL-014 | RootSIFT ≈ plain SIFT (no measurable difference) | **CONFIRMED** | 0.136 px difference < ±0.59 px run-to-run variation |
| RL-021 | Exact interpolation at "3–4 points" | **REFUTED (corrected)** | exact at minimal set (3); 4 points → 27.85 px |

## Acceptance criteria — verdict

| # | Criterion (set in advance) | Verdict |
|---|---|---|
| 1 | Speedup with mathematical correctness preserved | **PASS** — ~968×, identical inlier set, `Vt` provably identical |
| 1 | Robustness not weakened | **PASS** — recall 1.000 at 0–80% outliers |
| 1 | Stage-level timing | **PASS** — 5 stages + refit counts |
| 1 | Regression test | **PASS** — 12 tests, shape/count invariants where possible |
| 1 | EXP-001 unchanged within a stated tolerance | **PASS** — 0/45 flips; tolerance ±0.59 px |
| 2 | ≥ 3 regimes with controlled slope statistics | **PASS** — 4 regimes, LOLA medians hit exactly |
| 2 | Density controlled independently of geometry | **PASS** — 24× density range at fixed 9.10° |
| 2 | Extreme terrain retained, old results preserved | **PASS** — regime C + `results_preEXP002.csv` |
| 2 | Multiple seeds | **PASS** — 5 (stats), 3 (cases) |
| 3 | Threshold not selected on its evaluation data | **PASS** — disjoint seeds, different terrain |
| 3 | Report honestly if 8 is not stable | **PASS** — claim refuted; operating point validated separately |
| 4 | Estimators not tuned on reporting cases | **PASS** — calibration/validation split |
| 4 | Detection + false alarm per catastrophic kind | **PASS** — full tables |

## Decisions taken

| ADR | Subject | Status |
|---|---|---|
| ADR-0011 | Loop closure primary; held-out and split demoted to degeneracy detection | ACCEPTED (mathematics); real-data frequency open |
| ADR-0012 | Terrain realism via explicit slope target anchored to LOLA | ACCEPTED |
| ADR-0003 | Outstanding GT-free item **discharged**; primary/secondary ordering **reversed** by measurement | ACCEPTED |

## Effect on EXP-003

1. **The bar moved.** Success criterion is now stated against A-regimes: a representation earns its place only if it moves the last fully-successful Δazimuth **beyond 30°**.
2. **Report per regime, never pooled** — conclusions invert between regimes.
3. **Mare is the priority case**: earliest failure on both axes, 312 vs 22 119 kp/Mpx.
4. **Use `n_inliers < 8`** as the success/failure criterion; never `fit_rmse`.
5. **Carry loop closure forward** as the only trustworthy GT-free correctness check.
6. **Resolve the cliff edge** at 18/21/24/27° on A-regimes, ≥ 3 seeds.
7. Runtime is no longer a constraint (median 0.39 s, worst 3.64 s).

## Artefacts

| File | Contents |
|---|---|
| `objective1_ransac.json` | SVD benchmark, before/after, robustness, scaling |
| `objective2_terrain.json` / `_cases.csv` | Regime statistics, separability, 108 cases |
| `objective3_threshold.json` / `_cases.csv` | 384 cases, signal comparison, sensitivity |
| `objective4_gtfree.json` / `_partA.csv` / `_partB.csv` | Adversarial cases, detection rates |
| `../EXP-001/results_preEXP002.csv` | EXP-001 results before the RANSAC fix — preserved |
