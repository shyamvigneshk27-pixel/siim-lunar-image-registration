# EXP-002 — RANSAC, Terrain Realism, Threshold Validation, and GT-Free Verification

**Stage ID:** EXP-002
**Name:** Four objectives — LO-RANSAC defect · terrain realism · non-circular threshold validation · GT-free estimators
**Status:** COMPLETE
**Date:** 2026-08-24 — the only date recorded in any repository artefact
**Depends on:** EXP-001 · **Followed by:** EXP-003 (NOT STARTED)

> **This is the stage that most changed the research direction.** It corrected two EXP-001
> conclusions, refuted one EXP-001 claim, reversed the primary/secondary ordering of an
> accepted ADR, and demonstrated that the terrain every prior result had been measured on
> was physically impossible.

---

## 0. Provenance and what this report is

Retrospective, reconstructed **only** from repository artefacts:

`experiments/EXP-002/README.md` · `objective1_ransac.json` · `objective2_terrain.json` +
`_cases.csv` · `objective3_threshold.json` + `_cases.csv` · `objective4_gtfree.json` +
`_partA.csv` / `_partB.csv` · `scripts/run_exp002_{ransac,terrain,threshold,gtfree}.py` ·
`scripts/exp002_common.py` · `src/siim/evaluation/gtfree.py` ·
`src/siim/verification/ransac.py` · `src/siim/geometry/estimate.py` ·
`src/siim/data/synthetic_terrain.py` · `tests/test_ransac_performance.py` ·
`tests/test_gtfree_and_terrain.py` · `docs/research_log.md` · `docs/sources.md` S7 ·
ADR-0011 / ADR-0012.

**Limits on this reconstruction:**

1. **No git history.** The pre-fix source text of `ransac.py` and `estimate.py` is **not
   preserved**. What survives is (a) the measured pre-fix numbers, recorded before the
   change, and (b) a **deliberately-labelled non-faithful re-implementation**
   (`_legacy_ransac` in `run_exp002_ransac.py`).
2. **All artefacts carry the single date 2026-08-24.** Stage duration is **[NOT VERIFIED]**.
3. Per-edit ordering within the stage is **[NOT VERIFIED]**.

---

## 0.1 Where to find each mandated section

This report is organised **objective by objective**, because the four objectives are
methodologically independent and each carries its own criterion, evidence and verdict.
Pooling them into one results table would obscure exactly what this stage exists to
demonstrate. The mandated stage-report sections are therefore distributed as follows.

| Mandated section | Where |
|---|---|
| Stage objective | §1 |
| Starting assumptions | §2 |
| What we implemented | §3 |
| Experiments performed | §3 (modules) · §1.1, §2.3, §3.2, §4.1 (per-objective designs) |
| Exact commands used | §4 |
| Quantitative results | §1.4–1.6 · §2.3–2.5 · §3.4–3.6 · §4.2–4.4 |
| What worked / what failed | §7 (criteria verdict) · §9 (conclusions) · §10 (corrections) |
| Errors and bugs discovered | §1.2, §1.3, §2.3, §2.5, §3.3, §3.5, §3.7, §4.3, §4.5, §5 — **E-002.1 … E-002.12** |
| Root cause / fix / before-after per error | Inside each error block (six-part structure) |
| Failure classification | §8 |
| Hypotheses that were disproved | §6 (outcome table) · §10 (corrections to earlier stages) |
| Conclusions that survived | §9 |
| Decisions / ADRs affected | §11 |
| Tests and reproducibility status | §12 |
| Files / modules created or changed | §13 |
| Limitations and threats to validity | §14 |
| Lessons learned | §15 |
| What must NOT be repeated | §16 |
| What the next stage should do | §17 |
| Open questions / unresolved risks | §18 |
| Artefacts | §19 |

---

## 1. Stage objective

**The four questions, one per objective:**

1. **RANSAC.** *What actually caused the 59 s outlier, and can it be removed without
   trading away robustness?*
2. **Terrain realism.** *Is the synthetic terrain physically possible on the Moon, and do
   EXP-001's conclusions survive terrain that is?*
3. **Threshold validation.** *Does the inlier-count failure threshold hold on data it was
   not derived from?*
4. **GT-free verification.** *Which estimators can detect a wrong answer without ground
   truth — specifically, a wrong answer that is internally self-consistent?*

Objectives 1–4 are exactly EXP-001's own list of what EXP-002 should test. EXP-001's fifth
item (resolve the cliff edge between 30° and 45°) was **deferred to EXP-003** once
objective 2 relocated the cliff and made that bracket obsolete.

---

## 2. Starting assumptions

| # | Assumption | Source | Kind | Later status |
|---|---|---|---|---|
| A1 | The 59 s outlier is caused by LO refitting the full consensus set | EXP-001 README | reasoned | **Incomplete** — true but not dominant (E-002.1) |
| A2 | EXP-001's terrain is "too steep" but not conclusion-changing | EXP-001 limitations | assumed | **REFUTED** — two conclusions changed (E-002.4, E-002.5, E-002.6) |
| A3 | The `n_inliers ≥ 8` separation is real and will validate | RL-011 | measured circularly | **REFUTED as a separation**; **VALIDATED as a rule** (E-002.3) |
| A4 | `fit_rmse` carries no failure information | RL-010 | reasoned | **CONFIRMED** by pre-declared negative control |
| A5 | Held-out residual is the **primary** GT-free estimator | ANALYSIS §F.1 | reasoned | **REFUTED** — detection 0.200 (E-002.8) |
| A6 | Loop closure catches coherent wrong solutions | ANALYSIS §F.1.4 | reasoned | **CONFIRMED** on constructed cases |
| A7 | Published LOLA slope statistics are an authoritative realism target | sources.md S7 | published, peer-reviewed | Used as the anchor for ADR-0012 |
| A8 | A slope rescale preserves ground-truth geometry | reasoned | reasoned | **Verified by test** — pure vertical rescale |

---

## 3. What we implemented

| Path | Change | Purpose |
|---|---|---|
| `src/siim/geometry/estimate.py` | changed, line 319 | `np.linalg.svd(a, full_matrices=False)`, with a load-bearing comment at 314–318 |
| `src/siim/verification/ransac.py` | changed | `if count <= best_count: continue` (line 204) gating LO; `lo_max_points` (line 135, default 1000) capping the **refit sample only** (lines 214–215); `RansacTiming` (line 48) with 5 stages + `n_lo_refits` / `n_minimal_fits` |
| `src/siim/data/synthetic_terrain.py` | changed | `target_slope_median_deg`, `REFERENCE_BASELINE_M = 15.0`, four named `TerrainRegime`s with a machine-readable `realistic` flag |
| `src/siim/evaluation/gtfree.py` | **created**, 251 lines | `held_out_residual`, `cycle_consistency`, `loop_closure`, `spatial_split_consistency`, `compose_cycle` |
| `scripts/exp002_common.py` | created, 233 lines | Shared regime definitions, evaluation, threshold selection |
| `scripts/run_exp002_ransac.py` | created, 295 lines | Objective 1, including `_legacy_ransac` |
| `scripts/run_exp002_terrain.py` | created, 246 lines | Objective 2 |
| `scripts/run_exp002_threshold.py` | created, 263 lines | Objective 3 |
| `scripts/run_exp002_gtfree.py` | created, 356 lines | Objective 4 |
| `tests/test_ransac_performance.py` | created | **12 tests** |
| `tests/test_gtfree_and_terrain.py` | created | **24 tests** |

**36 new tests** — verified by `--collect-only`: 12 + 24.

---

## 4. Exact commands used

Recorded verbatim in `experiments/EXP-002/README.md`:

```bash
python scripts/run_exp002_ransac.py       # objective 1     ~40 s
python scripts/run_exp002_terrain.py      # objective 2     ~7 min
python scripts/run_exp002_threshold.py    # objective 3    ~13 min
python scripts/run_exp002_gtfree.py       # objective 4     ~30 s
python scripts/run_exp001.py              # EXP-001 re-run  ~4.5 min
python -m pytest tests/                   # 168 passed, 2 skipped, 22 s
```

All five scripts take **no arguments** — verified: none imports `argparse`.

**Environment** (`objective1_ransac.json:environment`): python 3.13.7 · numpy 2.3.3 ·
Windows-11-10.0.26200-SP0. OpenCV 5.0.0 per `EXP-001/metrics.json`.

**Preservation.** Old EXP-001 results preserved unmodified at
`experiments/EXP-001/results_preEXP002.csv` (D-018).

---

# OBJECTIVE 1 — LO-RANSAC performance

## 1.1 The symptom and the discovery

EXP-001 recorded `ransac_s = 58.856` for `A_model/truth=projective` (n = 2115 putative,
~100% inliers) against a 0.387 s median — verified in `results_preEXP002.csv`.

Profiling the **real pre-fix code** with `cProfile`
(`objective1_ransac.json:ransac_before_after.before_measured_directly`):

| Measurement | Value |
|---|---|
| Profiled pre-fix total | **54.29 s** |
| Of which inside `numpy.linalg.svd` | **51.55 s of 53.9 s** |
| `estimate` calls for 100 iterations | **298** |

`[MEASURED]` **The dominant cost was numerical, not algorithmic.** Two independent defects
were present. EXP-001's diagnosis had named only the second, and it was the smaller one.

---

## 1.2 E-002.1 — `np.linalg.svd(full_matrices=True)` in the DLT

**Class:** implementation bug · **Severity: HIGH** · **`ERROR_LEDGER.md` E-007**

- **Problem.** `estimate_projective` called `np.linalg.svd(a)` with numpy's default
  `full_matrices=True`.
- **Evidence.** `cProfile` by cumulative time put `numpy.linalg._linalg.svd` at **51.533 s
  tottime across 596 calls**. A single projective fit on 2115 points cost **373.93 ms**.
  Then the two SVD modes were isolated on a synthetic matrix of the same shape.
- **Root cause.** The DLT design matrix is `(2N × 9)`. With `full_matrices=True`, numpy
  also constructs `U` at `(2N × 2N)` — for N = 2115 that is **4230 × 4230 = 17,892,900
  elements** — and the DLT then **discards it**, using only the last row of `Vt`.
- **Fix.** `np.linalg.svd(a, full_matrices=False)`. One keyword
  (`src/siim/geometry/estimate.py:319`).
- **Verification** (`objective1_ransac.json:svd_defect`):

| n | `full_matrices=True` | `full_matrices=False` | speedup | `U` elements |
|---|---|---|---|---|
| 500 | 37.451 ms | 0.309 ms | **121.4×** | 1,000,000 → 9,000 |
| 1000 | 143.256 ms | 0.882 ms | **162.4×** | 4,000,000 → 18,000 |
| **2115** | **498.858 ms** | **1.012 ms** | **492.8×** | **17,892,900 → 38,070** |

  At every n: `singular_values_identical: true`, `vt_identical_up_to_sign: true`.
  **This is a mathematically identical change, not an approximation** — the quantities the
  DLT consumes are bit-comparable.

  Regression tests: `test_dlt_uses_the_economy_svd` asserts on **output shapes**, so it is
  machine-independent; `test_large_projective_fit_is_fast` bounds the fit at 50 ms — two
  orders below the defect and two above the fixed cost. Both verified present.

- **Lesson.** **A three-orders-of-magnitude cost hid inside an entirely idiomatic line.**
  Nothing about `np.linalg.svd(a)` looks wrong. **Stage-level timing is what made it
  findable** — "RANSAC is slow" is not a diagnosis. EXP-001's own diagnosis of this exact
  symptom was incomplete and blamed only E-002.2.

---

## 1.3 E-002.2 — Local optimisation on every sufficient sample

**Class:** implementation bug · **Severity: MEDIUM** · **`ERROR_LEDGER.md` E-006**

- **Problem.** LO ran on **every** sample whose consensus exceeded the minimal set, rather
  than only when a **new best** model was found.
- **Evidence.** **298 `estimate` calls for 100 iterations** (~198 large refits). The call
  count could not be explained by 100 minimal fits alone.
- **Root cause.** A deviation from LO-RANSAC **as published** (Chum, Matas & Kittler 2003),
  in which LO is triggered only on a new best — an O(log n) event.
- **Fix.** `if count <= best_count: continue` before the LO block
  (`ransac.py:204`), restoring the published algorithm. A `lo_max_points` cap (default 1000)
  was added on the LO **refit sample** (`ransac.py:135, 214–215`).
- **Verification.** LO refits **198 → 3** on the same case
  (`objective1_ransac.json:ransac_before_after`). Regression tests, all verified present:
  - `test_lo_runs_only_on_a_new_best` — asserts **refit count ≤ 20** for 100 iterations
    (machine-independent, not a wall-clock bound).
  - `test_scoring_is_never_subsampled` — asserts all 3000 true inliers are found with
    `lo_max_points = 50`.
  - `test_lo_subsampling_does_not_degrade_accuracy` — bounds the capped-vs-uncapped
    difference at 0.05 px.
- **Lesson.** **When re-implementing a published algorithm, re-check the trigger condition,
  not just the mathematics.** And: **cap the refit, never the scoring.** Robustness must not
  be traded for speed — D-017. The consensus set that decides the winner always sees every
  correspondence; only the least-squares refit that *proposes* a candidate is capped, and a
  1000-point fit is already vastly over-determined for a model with at most 8 DOF.

---

## 1.4 Combined before / after — `[MEASURED]`

`objective1_ransac.json:ransac_before_after`. Case: EXP-001 `A_model/truth=projective`,
n = 2115, ~100% inliers.

| | total | inliers | iterations | LO refits | true error |
|---|---|---|---|---|---|
| **before** — profiled, real pre-fix code | **54.29 s** | 2115 | 100 | 198 | — |
| **before** — EXP-001 recorded `ransac_s` | **58.86 s** | 2115 | — | — | — |
| **after** | **0.0561 s** | 2115 | 100 | **3** | **0.0119 px** |

`[MEASURED]` **Speedup 968.3× (`speedup_vs_measured`), same inlier set (2115 → 2115).**

> **Honesty note, recorded in the artefact itself.** `_legacy_ransac` in
> `run_exp002_ransac.py` is a re-implementation built for the comparison and is **not
> bit-faithful**: it performs **27** LO refits where the real pre-fix code performed **198**,
> and therefore reports only **5.118 s** — i.e. it **under-states** the defect
> (`speedup_vs_emulated = 91.3×`). The JSON labels the two sources separately as
> `before_measured_directly` and `before_emulated`. **The directly-measured values are the
> ones quoted.** This is exactly the kind of detail that flatters a result if left unstated.

### Stage timing after the fix

`RansacTiming` records five stages plus refit counts on **every** run — this is what made
the defect diagnosable at all.

| stage | after |
|---|---|
| sampling | 2.42 ms |
| minimal fit | 32.41 ms |
| scoring | 15.75 ms |
| local optimisation | 2.56 ms |
| final fit | 2.38 ms |
| **total** | **56.07 ms** |

Scaling with correspondence count (projective, `objective1_ransac.json:scaling`):

| n | 200 | 500 | 1000 | 2000 | 4000 |
|---|---|---|---|---|---|
| total | 53.3 ms | 45.7 ms | 50.8 ms | 59.3 ms | 73.1 ms |

`[INTERPRETATION]` Cost is now dominated by the fixed 100 minimal fits, not by n. The
pathological superlinear behaviour is gone.

### 1.5 Robustness unchanged — criterion set in advance

**Criterion:** robustness must not be traded for runtime.

| outlier fraction | 0% | 30% | 50% | 60% | 70% | 80% |
|---|---|---|---|---|---|---|
| **inlier recall** | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| true error (px) | 0.027 | 0.038 | 0.037 | 0.049 | 0.054 | 0.050 |
| total (s) | 0.049 | 0.048 | 0.053 | 0.048 | 0.127 | 0.393 |

`[MEASURED]` **Criterion met.** Recall 1.000 at every outlier fraction to 80%.

### 1.6 EXP-001 re-run — criterion set in advance

**Criterion:** no case may flip between correct and wrong.

All four rows below **independently re-verified** for this report by direct comparison of
`results.csv` against `results_preEXP002.csv`:

| | before | after |
|---|---|---|
| success/failure flips | — | **0 / 45** ✅ |
| max \|Δ\| true transform error, correct cases | — | **0.5853 px** |
| max \|Δ\| inlier count, correct cases | — | **102** |
| total pipeline time (Σ `pipeline_s`) | **86.7 s** | **28.6 s** |
| slowest `ransac_s` | **58.856 s** | **3.505 s** |
| median `pipeline_s` | 0.387 s | 0.262 s |
| max `pipeline_s` | 59.057 s | 3.640 s |

`[MEASURED]` **Criterion met**, with an explicitly stated tolerance: results are **not
bit-identical**, because changing *when* LO fires changes the search trajectory.
Conclusions reproduce; individual transform errors move by up to **0.5853 px**.

`[INTERPRETATION]` **That tolerance is itself a finding (RL-016):** it **exceeds** the
0.136 px RootSIFT-vs-plain-SIFT difference EXP-001 flagged as possibly noise. It is noise.

---

# OBJECTIVE 2 — Terrain realism

## 2.1 The original problem

EXP-001's terrain was recorded in its own limitations as "too steep and too
high-frequency": p99 |∂z/∂x| = 4.79, i.e. ~78° slopes, with 2000+ SIFT keypoints per 512²
frame.

**Why that is a physical-realism problem, not a cosmetic one.** Published LOLA statistics
(sources.md S7 — Rosenburg et al., *JGR Planets*; supporting: *Icarus* steepest-slopes
paper; NASA PGDA product 70), **at a 15 m baseline**:

| Terrain | median | mean | sd |
|---|---|---|---|
| highlands | **9.1°** | 11.0° | 7.0° |
| mare | **3.5°** | 4.9° | 4.5° |

The slope-frequency distribution shows a **steep rollover near the ~33° angle of repose**,
and slopes materially steeper are **"almost absent"**, because the fractured megaregolith
lacks the cohesion to hold them.

## 2.2 How realism is now controlled

Two controls, separating what the old single `relief` parameter conflated:

- **Geometry (amplitude):** `target_slope_median_deg` rescales heights so the median slope
  hits the target exactly — `k = tan(target)/tan(current_median)`, valid because arctan is
  monotonic. This is a **pure vertical rescale: it does not touch horizontal coordinates,
  so ground-truth geometry is preserved.** Pinned by
  `test_normalise_slope_is_a_pure_vertical_rescale`.
- **Feature density (spectrum):** `octaves`, `persistence`, `crater_density`.

`REFERENCE_BASELINE_M = 15.0` is recorded alongside every target, because slope statistics
are strongly baseline-dependent and **a median is meaningless without one**. This also makes
the OHRC caveat explicit: at 0.25 m/px the real surface is rougher than these 15 m figures.

## 2.3 E-002.4 — The EXP-001 terrain was physically impossible

**Class:** synthetic-data limitation (which propagated into two wrong conclusions)
**Severity: HIGH** · **`ERROR_LEDGER.md` E-013**

- **Problem.** 89.55% of the EXP-001 terrain surface is steeper than the lunar angle of
  repose.
- **Evidence.** `objective2_terrain.json:regime_statistics`, 5 seeds (1001–1005), 384²:

| regime | median | mean | p90 | p99 | > repose | kp/Mpx | classification |
|---|---|---|---|---|---|---|---|
| **A_mare_moderate** | **3.50°** | 3.75° | 6.41° | 9.32° | **0.00%** | **312** | **realistic benchmark** |
| **A_highlands_moderate** | **9.10°** | 9.62° | 16.34° | 22.64° | 0.002% | **22,119** | **realistic benchmark** |
| **B_highlands_challenging** | 18.00° | 18.58° | 30.71° | 40.05° | 6.36% | 32,582 | **challenging benchmark** |
| **C_extreme_diagnostic** (= EXP-001) | **58.53°** | 55.01° | 71.50° | 76.76° | **89.55%** | 31,246 | **diagnostic stress test — NOT realistic** |

  `[MEASURED]` The A-regimes reproduce the published LOLA medians **exactly** (3.50 vs 3.5;
  9.10 vs 9.1), with standard deviations across the 5 seeds of 5.0e-13 and 1.2e-11 degrees
  respectively — i.e. the normalisation is exact, not approximate.

- **Root cause.** The old `relief` parameter **conflated amplitude with spectral content**.
  There was no slope target and no comparison to published lunar statistics.
- **Fix.** Explicit `target_slope_median_deg`; four named regimes; `TerrainRegime.realistic`
  as a **machine-readable flag** so the classification cannot be lost in prose. The three
  classifications are kept distinct throughout:
  - **realistic benchmark** — conclusions about real lunar imagery may be drawn (subject to
    all other synthetic-data caveats);
  - **challenging benchmark** — physically plausible, at the rough end of the real distribution;
  - **diagnostic stress test** — physically impossible; used only to stress the algorithm
    and to reproduce EXP-001.
- **Verification.** `test_realistic_regimes_respect_the_angle_of_repose`;
  A-regimes hit the LOLA medians to 2 d.p.
- **Lesson.** **"Realistic" is a claim and must be checkable against an authoritative
  source.** "Looks lunar" is unfalsifiable.

### Why the old terrain was preserved rather than replaced

Silently replacing it would have been scientifically wrong for three reasons, all acted on:

1. **EXP-001 would have become unreproducible.** `target_slope_median_deg=None` disables
   normalisation **bit-identically** — `test_none_target_disables_normalisation` asserts
   `np.array_equal` — so regime C reproduces EXP-001 exactly.
2. **The change to the conclusions would have been invisible.** Keeping C is what makes
   §2.5 possible: the cliff moving from 30° to 15° is only *demonstrable* if both terrains
   exist.
3. **A stress test has independent value.** Extreme terrain probes algorithm behaviour
   outside the physical envelope.

Old numeric results preserved at `experiments/EXP-001/results_preEXP002.csv`.

## 2.4 Density is separable from geometry — criterion set in advance

**Criterion:** vary one at a fixed value of the other.

`objective2_terrain.json:density_slope_separability`:

| persistence / octaves | 0.35 / 4 | 0.45 / 5 | 0.60 / 6 | 0.70 / 7 |
|---|---|---|---|---|
| **slope median** | **9.10°** | **9.10°** | **9.10°** | **9.10°** |
| slope p99 | 33.94° | 25.16° | 22.59° | 22.48° |
| **kp/Mpx** | **1,287** | **4,885** | **22,135** | **30,404** |

`[MEASURED]` Median held to 2 d.p. (actually to ~1e-11°) while density varies **~23.6×**.
**Criterion met.** Pinned by `test_feature_density_varies_at_fixed_slope`.

## 2.5 E-002.5 / E-002.6 — Two EXP-001 conclusions did not survive

108 cases (4 regimes × 3 seeds × 9 conditions), 384² images,
`objective2_terrain.json:exp001_subset_summary` and `objective2_terrain_cases.csv`.

### The illumination cliff moved EARLIER — `[MEASURED]`

Success rate by Δazimuth (3 seeds per cell):

| regime | 0° | 15° | 30° | 45° | 60° | 90° | **last fully successful** |
|---|---|---|---|---|---|---|---|
| **A_mare_moderate** | 1.00 | 1.00 | **0.00** | 0.00 | 0.00 | 0.00 | **15°** |
| **A_highlands_moderate** | 1.00 | 1.00 | **0.67** | 0.00 | 0.00 | 0.00 | **15°** |
| B_highlands_challenging | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 30° |
| C_extreme (= EXP-001) | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 30° |

Median inlier counts at 0° show the texture gap starkly: mare **13**, highlands **1045**,
B **4119**, C **1850**.

**E-002.5** — **Class:** incorrect hypothesis, caused by a synthetic-data limitation ·
**Severity: HIGH** · `ERROR_LEDGER.md` E-014

- **Problem.** The illumination cliff was reported at Δaz 30–45°; on realistic terrain it
  is at **15–30°**.
- **Evidence.** The table above — the EXP-001 axes re-run across 4 regimes, 3 seeds.
- **Root cause.** The conclusion was drawn from a single, unrealistically steep terrain
  whose strong shading gradients **flattered the descriptor**.
- **Fix.** Cliff relocated; conclusions now reported **per regime** (D-021), drawn from
  realistic regimes only.
- **Verification.** A-regimes last fully successful at 15°; B/C at 30°.
- **Lesson.** **A conclusion measured on one dataset is a conclusion about that dataset.**
  **RootSIFT is *worse* on real-looking terrain than EXP-001 concluded.**

### "Scale survives to 4×" is false on realistic mare — `[MEASURED]`

| regime | 1.0× | 2.0× | 4.0× |
|---|---|---|---|
| **A_mare_moderate** | 1.00 | **0.33** | **0.00** |
| A_highlands_moderate | 1.00 | 1.00 | 1.00 |
| B_highlands_challenging | 1.00 | 1.00 | 1.00 |
| C_extreme | 1.00 | 1.00 | 1.00 |

**E-002.6** — **Class:** incorrect hypothesis (over-generalisation) · **Severity: MEDIUM** ·
`ERROR_LEDGER.md` E-015

- **Problem.** "Scale survives to 4×" was stated without the terrain it was measured on.
- **Evidence.** Realistic mare fails at 2× (success 0.333) and 4× (0.000).
- **Root cause.** Scale was tested only on texture-rich terrain.
- **Fix.** Claim narrowed to textured terrain; mare promoted to priority case for EXP-003 (D-019).
- **Verification.** `objective2_terrain.json:exp001_subset_summary`.
- **Lesson.** **Scale tolerance is a property of the descriptor AND the available texture**
  — 312 vs 22,119 kp/Mpx — not of the descriptor alone.

---

# OBJECTIVE 3 — Threshold validation

## 3.1 The original claim and why it was not evidence

EXP-001 (RL-011) observed: *wrong cases have at most 7 inliers, correct cases at least 8.*
Two problems, both flagged in EXP-001's own README at the time:

1. The threshold and its evaluation came from **the same 45 cases**.
2. The split sat exactly at the `min_inliers = 8` value `classify_failure` already used.

It had, moreover, **already broken** before objective 3 ran: after the objective-1 RANSAC
fix, the EXP-001 re-run gave wrong max = 7 but correct **min = 6** — overlapping.

## 3.2 Protocol

| Role | Seeds | n | Note |
|---|---|---|---|
| **Calibration** (threshold selection) | 1001–1004 | **192** | 94 wrong |
| **Validation** (performance reporting) | **7001–7004** | **192** | 103 wrong |

**Disjoint seeds building different terrain.** 4 regimes × 4 Δazimuth (0, 20, 40, 60°) ×
3 transform models. Every threshold chosen by **Youden's J on calibration only**, reported
**only** on validation. `fit_rmse` included as a deliberate **negative control** declared in
advance, because RL-010 predicted it carries no failure information.

## 3.3 E-002.3 — The separation claim refuted; the operating rule validated

**Class:** experimental / design mistake (inherited from EXP-001) · **Severity: HIGH** ·
`ERROR_LEDGER.md` E-009

Two statements were conflated in EXP-001. **They are not the same claim.**

| | Statement | Kind | Status |
|---|---|---|---|
| **(a)** *wrong ≤ 7 and correct ≥ 8, with no overlap* | a property of 45 specific cases | **REFUTED** |
| **(b)** *flag failure when `n_inliers < 8`* | a decision rule with a measured error rate | **VALIDATED** |

`[MEASURED]` **(a) refuted** (`objective3_threshold.json:exp001_claim`, independently
re-verified from `objective3_threshold_cases.csv`): validation wrong max = **7**, correct
**min = 2**, `holds: false`.

The offending case, verified from the CSV: **A_mare_moderate, Δaz = 20°, 2 inliers,
transform error 2.043 px** — genuinely correct — with **`coverage_max_gap = 0.520`**. A
fluke that the **coverage metric independently flagged** while the error metric called it a
success.

`[MEASURED]` **(b) validated:** at threshold 8 — **recall 1.000, FPR 0.01124** on 192 unseen
cases (calibration figures for comparison: recall 1.000, FPR 0.0612).

`[INTERPRETATION]` The distinction matters because (a) invites treating 8 as a law about the
world, while (b) is an empirical decision rule with a stated false-alarm rate and a stated
domain of validity. **Only (b) is usable, and only (b) was earned.**

## 3.4 Signal comparison (validation, n = 192, 103 wrong) — `[MEASURED]`

| signal | ROC AUC | PR AUC | recall | FPR | verdict |
|---|---|---|---|---|---|
| `split_consistency` | **0.9944** | 0.9904 | 1.000 | 0.0112 | ⚠️ **artefact — §3.5** |
| **`n_inliers`** | **0.9935** | 0.9910 | 1.000 | 0.0112 | **best genuinely informative signal** |
| `coverage_max_gap` | 0.9828 | 0.9854 | 0.951 | 0.1124 | informative, higher false alarms |
| `inlier_ratio` | 0.9820 | 0.9905 | 0.913 | 0.0000 | misses 8.7% of failures |
| `held_out_median` | 0.9749 | 0.9811 | 0.971 | 0.0225 | ⚠️ **artefact — §3.5** |
| **`fit_rmse`** *(negative control)* | **0.4947** | 0.7042 | 0.388 | 0.0449 | **chance** |

`[MEASURED]` **`fit_rmse` scores ROC AUC 0.4947 — indistinguishable from a coin flip.**

`[INTERPRETATION]` As a failure detector it carries essentially no information, exactly as
RL-010 predicted. **This is independent support for ADR-0003 obtained from a pre-declared
negative control**, not from re-examining the data that motivated the concern. That
distinction is what makes it evidence rather than confirmation.

## 3.5 E-002.7 — The `split_consistency` AUC artefact

**Class:** experimental / design mistake (an interpretation failure that was very nearly
reported as a result) · **Severity: HIGH** · `ERROR_LEDGER.md` E-010

- **Problem.** `objective3_threshold.json` records `best_deployable_signal:
  split_consistency` — the **automated** selection by ROC AUC. Manual inspection showed
  this to be an artefact, and the report **does not follow the automated choice**.
- **Evidence**, independently re-verified from `objective3_threshold_cases.csv` for this
  report:

| | non-finite | of which wrong | finite | of which wrong |
|---|---|---|---|---|
| `split_consistency` | **104 / 192** | **103** | **88** | **0** |
| `held_out_median` | **100 / 192** | **99** | 92 | 4 |

- **Root cause.** Both estimators return `inf` (recorded as the sentinel `1e12`) precisely
  when there are too few inliers to evaluate them. **The sentinel aligns almost perfectly
  with the label.** Their apparent 0.97–0.99 AUC is therefore a **proxy for low inlier
  count**, not independent information.
- **Why the non-finite cases invalidate the AUC.** ROC AUC ranks a signal against a label.
  When a signal collapses to a single sentinel on ~54% of cases, and that sentinel is nearly
  perfectly aligned with the label, **the AUC measures the sentinel's correlation with the
  label** — i.e. *"did this case have enough inliers to evaluate?"* — not the estimator's
  discriminative content. On the finite subset, where the estimator actually produces a
  value, **there are no wrong cases at all**: the estimator was **never asked to
  discriminate**.
- **Fix.** The automated `best_deployable_signal` selection was **overridden** in the report
  (D-022); `n_inliers` is reported as the best genuinely informative signal. The artefact is
  **documented rather than reported as a result** (`EXP-002/README.md` §3.5, RL-020).
- **Verification.** The finite/non-finite split above.
- **Lesson.** **A signal that collapses to a sentinel on half the data has its AUC measured
  on the sentinel. Always check the finite subset.** The automated pick was wrong, and the
  artefact was **nearly reported as this stage's best result**.

`[INTERPRETATION]` **Consequence: objective 3 never tested these estimators against the
failure they exist for.** The failures the image pipeline produces in this regime are
illumination collapse to 3–7 inliers — which counting already catches. **That gap is what
objective 4 was built to close.**

## 3.6 Sensitivity by subset — `[MEASURED]`, with a correction

`objective3_threshold.json:sensitivity`:

| by regime | recall | FPR | AUC |
|---|---|---|---|
| A_mare_moderate | 1.000 | 0.0588 | 0.9706 |
| A_highlands_moderate | 1.000 | 0.000 | 1.000 |
| B_highlands_challenging | 1.000 | 0.000 | 1.000 |
| C_extreme_diagnostic | 1.000 | 0.000 | 1.000 |

By transform model: similarity 1.000 / 0.031 · affine 1.000 / 0.000 · projective 1.000 / 0.000.
By Δazimuth: 0° and 20° evaluable (recall 1.000, FPR ≤ 0.023). **40° and 60° are degenerate
subsets — every case fails**, so discrimination is undefined there. That degeneracy is the
objective-2 cliff restated.

> **Correction, recorded rather than smoothed over.** Earlier stage documentation presents
> this table under the heading *"Sensitivity of `n_inliers`"*. **It is not.**
> `scripts/run_exp002_threshold.py:202–222` computes `sensitivity` for the **automatically
> selected `best` signal**, and the JSON records
> `threshold_score_space: 1000000000000.0` in every sensitivity block — the
> `split_consistency` `inf` sentinel. **This sensitivity table is therefore
> `split_consistency`'s, not `n_inliers`'s**, and inherits the E-002.7 artefact.
>
> **RESOLVED — 2026-08-24.** See §3.7. Contradiction **D2 is closed**.
> Evidence: **`experiments/EXP-002/objective3_ninliers_sensitivity.json`**
> (+ `_cases.csv`), produced by `scripts/run_exp002_ninliers_sensitivity.py`.
> The table above is retained unchanged as the record of what was originally computed.

---

## 3.7 D2 RESOLVED — the corrected `n_inliers` sensitivity analysis

**Evidence path:** `experiments/EXP-002/objective3_ninliers_sensitivity.json` ·
`experiments/EXP-002/objective3_ninliers_sensitivity_cases.csv` ·
`scripts/run_exp002_ninliers_sensitivity.py` · RL-022 · D-023.

**Method, and why it is not a pipeline re-run.** The analysis was **recomputed from the
preserved per-case artefact** `objective3_threshold_cases.csv` (192 calibration seeds
1001–1004 + 192 validation seeds 7001–7004, disjoint), using `pick_threshold`, `evaluate`
and `overlap_report` **imported unchanged** from `run_exp002_threshold.py` rather than
re-implemented. Re-running the image pipeline would have regenerated terrain and moved
individual numbers — the EXP-001 re-run's ±0.5853 px precedent — confounding *"the table was
labelled with the wrong signal"* with *"the numbers moved"*. Recomputation keeps the
corrected and mislabelled tables describing **the same 384 cases**, so the difference
between them is attributable entirely to the signal.

**Self-check, which is what licenses the result.** Before computing anything new the script
reproduces `objective3_threshold.json:signals.n_inliers` from the CSV and aborts if it does
not match to 1e-12. **It matched** — threshold, and every field of both the calibration and
validation blocks. `objective3_threshold.json` and `objective3_threshold_cases.csv` were
**not modified** (mtimes unchanged at 08:57).

### The mandated rule, measured — `[MEASURED]`

| split | n | wrong | correct | recall | recall 95% CI | FPR | FPR 95% CI | precision | ROC AUC |
|---|---|---|---|---|---|---|---|---|---|
| calibration | 192 | 94 | 98 | **0.9894** | 0.942–0.998 | 0.0612 | 0.028–0.127 | 0.9394 | 0.9889 |
| **validation** | 192 | 103 | 89 | **1.0000** | 0.964–1.000 | **0.0112** | 0.002–0.061 | 0.9904 | **0.9935** |

Wilson score intervals, because a recall of 1.000 on 103 cases and on 3 cases are not the
same evidence.

### Per-subset sensitivity on validation — the table that did not previously exist

| subset | n | wrong | recall | FPR | precision | ROC AUC |
|---|---|---|---|---|---|---|
| **A_mare_moderate** | 48 | 31 | 1.0000 | **0.0588** | 0.9688 | **0.9877** |
| A_highlands_moderate | 48 | 24 | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| B_highlands_challenging | 48 | 24 | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| C_extreme_diagnostic | 48 | 24 | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| similarity | 64 | 32 | 1.0000 | 0.0312 | 0.9697 | **0.9834** |
| affine | 64 | 33 | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| projective | 64 | 38 | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| Δaz 0° | 48 | 3 | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| Δaz 20° | 48 | 4 | 1.0000 | 0.0227 | 0.8000 | 0.9886 |
| Δaz 40° | 48 | 48 | **degenerate** — all cases wrong | | | |
| Δaz 60° | 48 | 48 | **degenerate** — all cases wrong | | | |
| seed 7001 / 7003 / 7004 | 48 ea. | 26/24/26 | 1.0000 | 0.0000 | 1.0000 | 1.0000 |
| seed 7002 | 48 | 27 | 1.0000 | 0.0476 | 0.9643 | 0.9753 |

Seed is now broken out as a fourth axis; the original table had only three.

### Thresholds tested — `[MEASURED]`

Rule `n_inliers < c` for c ∈ {2, 3, 4, 5, 6, 7, **8**, 9, 10, 12, 15, 20, 30, 50}, both
splits. Validation, around the operating point:

| c | TP | FP | TN | FN | recall | FPR | precision | Youden J |
|---|---|---|---|---|---|---|---|---|
| 6 | 100 | 1 | 88 | 3 | 0.9709 | 0.0112 | 0.9901 | 0.9596 |
| 7 | 102 | 1 | 88 | 1 | 0.9903 | 0.0112 | 0.9903 | 0.9791 |
| **8** | **103** | **1** | **88** | **0** | **1.0000** | **0.0112** | **0.9904** | **0.9888** |
| **9** | **103** | **1** | **88** | **0** | **1.0000** | **0.0112** | **0.9904** | **0.9888** |
| 10 | 103 | 2 | 87 | 0 | 1.0000 | 0.0225 | 0.9810 | 0.9775 |

`[MEASURED]` J is maximised on a **plateau at c = 8 and c = 9**, not at a cliff edge.

### How different is the corrected table from the mislabelled one? — `[MEASURED]`

Only **2 of 9** evaluable cells differ, and both are AUC:
A_mare **0.9706 → 0.9877**; similarity **0.9844 → 0.9834**. Every recall and FPR coincides.

**Why.** `split_consistency`'s non-finite sentinel fires in exact agreement with
`n_inliers < 8` on **192/192** validation cases — it is a near-perfect proxy for a low
inlier count. So the mislabelled table's *confusion matrix* was right; only its *AUC*
column, which uses the full ranking the sentinel collapses to a tie, was wrong.

`[INTERPRETATION]` **That makes the error more dangerous, not less.** A table that is
numerically almost right while measuring the wrong quantity gives a reviewer nothing to
notice. The defect was findable only by reading the selection code.

### E-002.11 — the metric override was not propagated to the derived table

**Class:** experimental / design mistake · **Severity: MEDIUM**

- **Problem.** D-022 overrode the automated `best_deployable_signal` pick in the *report*,
  but the *sensitivity table* generated from that same variable was never recomputed.
- **Evidence.** `run_exp002_threshold.py:202` — `best = max(deployable, key=… roc_auc)` —
  and `threshold_score_space: 1e12` in every recorded sensitivity block. The AUC margin
  that caused the wrong pick was **0.0009** (0.9944 vs 0.9935).
- **Root cause.** The override was applied as prose in the report, not as a change to the
  variable the artefact was generated from. A hand-written correction and a machine-written
  artefact drifted apart.
- **Fix.** A separate, clearly-named addendum artefact rather than an edit to the original
  (integrity rules 3 and 4). `run_exp002_threshold.py` is deliberately **left unmodified**:
  its output is the record of what was actually run.
- **Verification.** Self-check reproducing `signals.n_inliers` to 1e-12; corrected table in
  `objective3_ninliers_sensitivity.json`.
- **Lesson.** **An override recorded only in prose will not propagate to anything computed
  downstream.** When a metric selection is overruled, every table derived from that
  selection must be regenerated or explicitly marked as not regenerated.

### E-002.12 — the documented rule form is dominated by the one Youden selected

**Class:** experimental / design mistake · **Severity: MEDIUM** · **Decision: D-023**

- **Problem.** The documentation mandates `n_inliers < 8`. Youden's J selected `<= 8`.
- **Evidence.** Exactly **one case in 384** discriminates between the two: a **calibration**
  failure (A_mare_moderate, seed 1003, Δaz 20°, projective) with **exactly 8 inliers and
  367.95 px** true error. `< 8` misses it → calibration recall **0.9894**. `<= 8` catches it
  at an **identical** FPR of 0.0612 — the same 6 false alarms either way. **No validation
  case has exactly 8 inliers**, so on validation the two forms give an identical confusion
  matrix and the reported error rate never tested the boundary.
- **Root cause.** The score-space threshold `-8.0` means `n_inliers <= 8`; it was
  transcribed into prose as `< 8`. The coincidence on validation hid the difference.
- **Fix.** **D-023** — EXP-003 uses `n_inliers <= 8` (equivalently `< 9`). A change of rule
  *form*, not of operating point.
- **Verification.** `objective3_ninliers_sensitivity.json:diagnostics.rule_form`; the c = 9
  sweep row is identical to c = 8 on validation.
- **Lesson.** **A rule quoted in prose must be stated in the units it will be deployed in,
  and its boundary must be populated by the data that validates it.** An operating point
  whose boundary no validation case occupies is not fully validated at that boundary.

### What the corrected analysis does **not** establish — `[NOT VERIFIED]`

- **96 of 103 validation failures (93%) fall in the two Δazimuth subsets where every case
  fails.** On the subsets where correct and wrong cases coexist, the recall estimate rests
  on **7** failures. EXP-003 will operate in that discriminable regime, so the headline
  recall **overstates the evidence available for EXP-003's use of it.**
- All **7** false alarms across both splits are correct-but-fragile registrations (coverage
  gap 0.392–0.605 vs a median of 0.069 for correct cases), and **5 of 7 are in realistic
  mare** — the regime D-019 makes EXP-003's priority benchmark. **The rule's false alarms
  are not uniformly distributed over EXP-003's workload.**
- The addendum **inherits** the recorded cases and does not independently re-verify them.
- Δaz 40° and 60° discrimination: **undefined**, not measured. **Evidence insufficient.**

### Verdict

`[MEASURED]` The operating point **is** supported: validation recall 1.000 (103/103),
FPR 0.0112, AUC 0.9935, holding at recall 1.000 in all 4 regimes, all 3 transform models and
all 4 validation seeds, on seeds disjoint from calibration.

`[INTERPRETATION]` **D2 is resolved and EXP-003 is not blocked**, subject to D-023 (use
`<= 8`) and to the two caveats above being carried forward rather than forgotten.

---

# OBJECTIVE 4 — GT-free verification

## 4.1 Why this objective exists

On real lunar pairs **there are no ground-truth correspondences**, so all accuracy evidence
must come from the correspondences and images themselves (ANALYSIS §F.1, ADR-0003).
**None of these estimators may consult ground truth**; GT is used only to *score how well
they work*.

Objective 3 established that the estimators had never actually been challenged (§3.5).
Objective 4 therefore **constructs** adversarial cases with **300 correspondences each**, so
that a failure **cannot be detected simply by counting**.

**Protocol:** thresholds from calibration seeds 1001–1004, reported on disjoint validation
seeds 7001–7004.

## 4.2 Part A — correspondence-level, 96 validation cases — `[MEASURED]`

`objective4_gtfree.json:part_a_correspondence_level`. 12 cases per kind.

| case kind | wrong? | median true error | `held_out` | flagged | `split` | flagged |
|---|---|---|---|---|---|---|
| correct | no | 0.00 | 0.483 | 0.00 | 0.148 | 0.00 |
| **correct_noisy** | no | 0.00 | **1.424** | 0.00 | **0.539** | 0.00 |
| clustered_correct | no | 0.00 | 0.475 | 0.00 | 0.293 | 0.00 |
| **lattice_shift** | **yes** | **64.00** | **0.468** | **0.00** | 0.172 | 0.00 |
| **repeated_texture** | **yes** | **64.00** | **0.470** | **0.00** | 0.223 | 0.00 |
| **coherent_affine** | **yes** | **52.71** | **0.476** | **0.00** | 0.155 | 0.00 |
| **partial_overlap** | **yes** | **21.14** | **0.474** | **0.00** | **0.523** | 0.00 |
| low_inlier_degenerate | yes | 275.65 | ∞ | **1.00** | ∞ | **1.00** |

| estimator | detection rate | false alarm rate |
|---|---|---|
| `held_out_median` | **0.200** | 0.000 |
| `split_consistency` | **0.200** | 0.000 |

`[MEASURED]` **Both detect 1 of 5 wrong kinds — the degenerate one.**

`[MEASURED]` **A match set 64 px wrong yields a held-out residual of 0.468 px — *lower*
than a genuinely correct but noisy set at 1.424 px.** The estimator would rank the
catastrophic failure as the better result.

`[MEASURED]` `partial_overlap` — the case split consistency was *most* expected to catch —
gives **0.523** against **0.539** for a correct noisy set. Indistinguishable.

`[INTERPRETATION]` **Counting cannot explain these results, and that is the point:** every
case has 300 correspondences except the degenerate one, so `n_inliers` — objective 3's best
signal — is uninformative here **by construction**.

## 4.3 E-002.8 — Held-out residual and split consistency are blind to coherent wrongness

**Class:** incorrect hypothesis (ANALYSIS §F.1's ordering) · **Severity: HIGH** ·
`ERROR_LEDGER.md` E-011

- **Problem.** ANALYSIS §F.1 named held-out residual as the **primary** GT-free estimator.
- **Evidence.** Detection 0.200; blind to every coherent wrong case; the 64 px / 0.468 px
  inversion above.
- **Root cause.** **Both estimators measure self-consistency, and a uniformly wrong set is
  perfectly self-consistent.** This is not a tuning failure — it is a structural
  impossibility. They can detect only the degenerate `n ≈ DOF` case.
- **Fix.** Both **demoted to degeneracy detection only** (ADR-0011); loop closure promoted
  to primary.
- **Verification.** The Part A table.
- **Lesson.** **The register records the reversal rather than quietly rebalancing a combined
  score.** Averaging a working detector with two blind ones dilutes the signal and
  manufactures false confidence.

## 4.4 Part B — cycle consistency vs loop closure, 48 validation cases — `[MEASURED]`

`objective4_gtfree.json:part_b_cycle_and_loop`. 12 cases per kind.

| case kind | wrong? | median true error | `cycle` | flagged | `loop` | flagged |
|---|---|---|---|---|---|---|
| correct | no | 0.38 | 0.325 | **1.00** | 0.622 | **0.00** |
| lattice_all_edges | yes | 64.00 | **0.000** | 1.00 | **190.079** | 1.00 |
| lattice_one_edge | yes | 64.00 | **0.000** | 1.00 | **62.745** | 1.00 |
| symmetric_wrong | yes | 64.00 | **0.000** | 1.00 | **62.745** | 1.00 |

| estimator | threshold (from calibration) | detection | false alarm |
|---|---|---|---|
| `cycle_error` | 0.000 | 1.000 | **1.000** |
| **`loop_error`** | 62.745 | **1.000** | **0.000** |

`[MEASURED]` **Loop closure detects every constructed coherent wrong solution at zero false
alarms.**

`[MEASURED]` A one-period (64 px) error on **each of three edges accumulates to 190.079 px
≈ 3 × 64** around the loop, instead of cancelling.

`[INTERPRETATION]` This is precisely the mechanism ANALYSIS §F.1.4 was designed around: a
per-edge error **accumulates** around a loop, where a self-consistency check **cancels** it.

## 4.5 E-002.9 — Cycle consistency's blind spot, and its inverted signal

**Class:** genuine structural limitation, documented rather than fixed · **Severity: MEDIUM** ·
`ERROR_LEDGER.md` E-012

- **Problem.** Cycle consistency cannot detect symmetric errors, and on these constructions
  its signal is **inverted**.
- **Evidence.** Cycle error **0.000 on all three wrong kinds** vs **0.325 on the correct
  one**. Its threshold was therefore selected at 0.000, flagging everything — false alarm
  rate **1.000**.
- **Root cause.** In these constructions the wrong forward and backward transforms are
  **exact inverses**: forward +64 px and backward −64 px cancel exactly in the round trip.
  The *correct* case carries 0.325 px of genuine jitter, so it looks worse.
- **Fix.** **None.** Retained with the blind spot **documented and tested**, not treated as
  a safety net.
- **Verification.** `test_cycle_consistency_is_blind_to_a_symmetric_error` — verified present.
- **Lesson.** Two caveats stated plainly, and recorded in ADR-0011:
  1. **The construction deliberately targets cycle consistency's structural blind spot.** In
     a real pipeline the reverse pass is an *independent* estimate that would not cancel exactly.
  2. The defensible claim is therefore **"cycle consistency cannot detect symmetric
     errors"** — **not** "cycle consistency is useless".

## 4.6 The claim, stated at exactly the strength the evidence supports

> **Loop closure is currently the strongest demonstrated GT-free estimator.**

**This must not be generalised beyond the tested constructions.** Parts A and B are
**constructed transform- and correspondence-level cases**, not produced by the image
pipeline. They demonstrate the estimators' **mathematics**. They do **not** establish:

- how often coherent wrong solutions arise on real lunar imagery — **Evidence insufficient.**
- how loop closure behaves when the three per-edge estimates come from a real matcher with
  **correlated** errors — **Evidence insufficient.**
- whether overlapping triplets will exist in the evaluation dataset — **Evidence
  insufficient** (ANALYSIS §F.1.4 already flagged this as unknown).

---

# CROSS-CUTTING

## 5. E-002.10 — The mechanism behind fit-RMSE collapse was mis-stated

**Class:** incorrect hypothesis about a mechanism (the empirical finding was unaffected) ·
**Severity: LOW** · `ERROR_LEDGER.md` E-017

- **Problem.** RL-010 stated that exact interpolation occurs at "3–4 correspondences".
- **Evidence.** Direct test: 3 random pairs → fit RMSE < 1e-9 px; **4 random pairs →
  27.85 px**.
- **Root cause.** Confusing model **DOF (6)** with **minimal set size (3 point pairs)**.
- **Fix.** Wording corrected in ADR-0003 and RL-021. **The empirical finding is unaffected.**
- **Verification.** `test_exact_interpolation_only_at_the_minimal_set` — verified present.
- **Lesson.** **The empirical observation was right and the stated mechanism was wrong.
  Correct the mechanism rather than the conclusion.** The reason n slightly above the
  minimum still reads near zero is that **RANSAC *selects* mutually consistent points** —
  not that 4 points interpolate.

## 6. Hypotheses: outcome

| ID | Hypothesis (as originally stated) | Outcome | Evidence |
|---|---|---|---|
| RL-011 | Inlier count separates wrong from correct cleanly | **REFUTED** | correct min = 2 on validation |
| RL-010 | Fit RMSE carries no failure information | **CONFIRMED** | ROC AUC 0.4947, pre-declared negative control |
| ANALYSIS §F.1 | Held-out residual is the **primary** GT-free estimator | **REFUTED** | detection 0.200; blind to all coherent wrong cases |
| ANALYSIS §F.1.4 | Loop closure catches coherent wrong solutions | **CONFIRMED** | 1.000 / 0.000 on constructed cases |
| RL-009 | Cliff at Δaz 30–45° | **REFUTED (relocated)** | 15–30° on realistic terrain |
| EXP-001 §I.4 | Scale survives to 4× | **REFUTED in part** | mare fails at 2× (0.33) and 4× (0.00) |
| RL-014 | RootSIFT ≈ plain SIFT | **CONFIRMED** | 0.136 px difference < ±0.5853 px run-to-run variation |
| RL-021 | Exact interpolation at "3–4 points" | **REFUTED (corrected)** | exact at minimal set (3); 4 points → 27.85 px |
| A1 (EXP-002) | The 59 s outlier is caused by LO refitting | **INCOMPLETE** | 51.55 s of 53.9 s was in `svd`, not LO |
| A2 (EXP-002) | EXP-001 terrain is steep but not conclusion-changing | **REFUTED** | two conclusions changed |

## 7. Acceptance criteria — verdict

All 13 stated criteria were set in advance.

| # | Objective | Criterion | Verdict |
|---|---|---|---|
| 1 | 1 | Speedup with mathematical correctness preserved | **PASS** — ~968×, identical inlier set, `Vt` provably identical |
| 2 | 1 | Robustness not weakened | **PASS** — recall 1.000 at 0–80% outliers |
| 3 | 1 | Stage-level timing | **PASS** — 5 stages + refit counts |
| 4 | 1 | Regression test | **PASS** — 12 tests, shape/count invariants where possible |
| 5 | 1 | EXP-001 unchanged within a stated tolerance | **PASS** — 0/45 flips; tolerance ±0.5853 px |
| 6 | 2 | ≥ 3 regimes with controlled slope statistics | **PASS** — 4 regimes, LOLA medians hit exactly |
| 7 | 2 | Density controlled independently of geometry | **PASS** — 23.6× density range at fixed 9.10° |
| 8 | 2 | Extreme terrain retained, old results preserved | **PASS** — regime C + `results_preEXP002.csv` |
| 9 | 2 | Multiple seeds | **PASS** — 5 (statistics), 3 (cases) |
| 10 | 3 | Threshold not selected on its evaluation data | **PASS** — disjoint seeds, different terrain |
| 11 | 3 | Report honestly if 8 is not stable | **PASS** — claim refuted; operating point validated separately |
| 12 | 4 | Estimators not tuned on reporting cases | **PASS** — calibration/validation split |
| 13 | 4 | Detection + false alarm per catastrophic kind | **PASS** — full tables |

**All 13 PASS.**

`[INTERPRETATION]` Note what "all PASS" does **not** mean here: three of the four objectives
**refuted** something the project previously believed. Passing the criteria and confirming
the prior beliefs are different things, and this stage did the first while failing the second.

## 8. Failure classification

| Class | Entries |
|---|---|
| **Implementation bug** | **E-002.1** (SVD `full_matrices`) · **E-002.2** (LO trigger) — only two ordinary code defects in the whole stage |
| **Experimental / design mistake** | **E-002.3** (circular threshold, inherited) · **E-002.7** (`split_consistency` AUC artefact and the automated pick) · the §3.6 sensitivity-table mislabelling |
| **Incorrect hypothesis** | **E-002.5** (cliff location) · **E-002.6** (scale over-generalisation) · **E-002.8** (held-out as primary) · **E-002.10** (interpolation mechanism) · A1 (RANSAC diagnosis) |
| **Synthetic-data limitation** | **E-002.4** (89.55% above repose) — and everything downstream of it. Lambertian shading. Constructed adversarial cases in objective 4 are **not** pipeline output |
| **Genuine research negative result** | `fit_rmse` at ROC AUC 0.4947 · held-out and split at detection 0.200 · **E-002.9** (cycle consistency's structural blind spot) · RootSIFT ≈ SIFT confirmed as noise |

`[INTERPRETATION]` **Of the ten numbered failures, only two are ordinary software defects.**
The rest are failures of evidence, over-claims, or correctly-measured negative results.
That ratio is the project's central empirical finding about itself.

## 9. Conclusions that survived

### `[MEASURED]` — proven, within the stated scope

| Conclusion | Scope |
|---|---|
| LO-RANSAC **54.29 s → 0.0561 s (968×)** with the **same inlier set** and unchanged robustness | One case (n = 2115, projective); robustness over 0–80% outliers |
| `full_matrices=False` is **mathematically identical** — singular values and `Vt` identical up to sign | n = 500, 1000, 2115 |
| Terrain regimes hit published LOLA medians exactly (3.50 / 9.10) with 0.00% above repose | 5 seeds, 384², 15 m reference baseline |
| Feature density is separable from slope geometry over a **23.6×** range | Fixed 9.10° median |
| **The EXP-001 terrain is physically impossible** — 89.55% above the angle of repose | 5 seeds |
| **The illumination cliff is at 15–30° on realistic terrain**, not 30–45° | A-regimes, 3 seeds, 4 Δaz values |
| **Scale fails at 2× on realistic mare** | 3 seeds |
| `fit_rmse` is a **chance-level** failure detector (ROC AUC 0.4947) | 192 unseen cases, pre-declared negative control |
| The rule `n_inliers < 8` gives **recall 1.000, FPR 0.0112** | 192 unseen cases, disjoint seeds |
| Held-out residual and split consistency detect **0.200** of wrong kinds; blind to all coherent ones | 96 constructed cases |
| **Loop closure: detection 1.000, false alarm 0.000**; error accumulates to 190.079 px ≈ 3 × 64 | 48 constructed cases |
| Cycle consistency's signal is **inverted** on symmetric errors | 48 constructed cases |
| Run-to-run variation is **±0.5853 px** | 45 EXP-001 cases, before/after RANSAC fix |

### `[INTERPRETATION]`

- **Two EXP-001 conclusions did not survive realistic terrain.** RootSIFT is *worse* on
  real-looking terrain than EXP-001 concluded.
- **Self-consistency estimators cannot detect coherent wrongness, by construction.** Loop
  closure can, because a per-edge error accumulates around a loop instead of cancelling.
- **A signal that collapses to a sentinel has its AUC measured on the sentinel.**
- Runtime is no longer a primary constraint (D-020).

### `[NOT VERIFIED] / Evidence insufficient`

- **Frequency of coherent wrong solutions on real lunar imagery. Evidence insufficient.**
- **Loop closure with correlated per-edge errors from a real matcher. Evidence insufficient.**
- **Availability of overlapping triplets in a real evaluation dataset. Evidence insufficient.**
- **Multi-modal robustness. Evidence insufficient** — no real modality difference has been
  tested. **No multi-modal claim has been made or is currently supportable.**
- **Per-subset sensitivity of `n_inliers`** — **RESOLVED**, see §3.7 and
  `objective3_ninliers_sensitivity.json`. Recall 1.000 in every non-degenerate subset.
  *Still* **Evidence insufficient** for the discriminable regime specifically: 96 of 103
  validation failures are in all-failing Δazimuth subsets.
- **The pre-fix source of `ransac.py` / `estimate.py`. Not verified** — not preserved.
- **`_legacy_ransac` is explicitly not bit-faithful** and under-states the defect.
- **Scale beyond 4×. Evidence insufficient** — the real ladder reaches 320:1.
- **Relief displacement (RL-007). Still untested.**

## 10. Conclusions from earlier stages that this stage corrected

| Earlier claim | Stage | Status now | Evidence |
|---|---|---|---|
| Illumination cliff at Δaz 30–45° | EXP-001 | **Relocated to 15–30°** on realistic terrain | `objective2_terrain.json` |
| "Scale survives to 4×" | EXP-001 | **False on realistic mare** (2× → 0.33) | `objective2_terrain.json` |
| "Wrong ≤ 7, correct ≥ 8 — clean separation" | EXP-001 | **Refuted.** Correct min = 2 | `objective3_threshold.json` |
| "The 59 s case is LO refitting the consensus" | EXP-001 | **Incomplete.** 51.55 s of 53.9 s was `svd` | `objective1_ransac.json` |
| Held-out residual is the primary GT-free estimator | ANALYSIS §F.1 | **Reversed.** Loop closure is primary | `objective4_gtfree.json` |
| "Exact interpolation at 3–4 correspondences" | RL-010 | **Corrected.** Exact at the minimal set (3); 4 → 27.85 px | test |
| RootSIFT-vs-SIFT difference might be real | EXP-001 | **Confirmed noise** (0.136 px < ±0.5853 px) | EXP-001 re-run |
| The terrain is steep but not conclusion-changing | EXP-001 | **Refuted.** 89.55% above repose; two conclusions changed | `objective2_terrain.json` |

## 11. Decisions / ADRs affected

| ID | Decision | Effect of EXP-002 |
|---|---|---|
| **ADR-0011** / D-011 | **Loop closure is the primary GT-free correctness check**; held-out residual and split consistency demoted to degeneracy detection; cycle consistency retained with a documented blind spot | **Created. `ACCEPTED` for the mathematics only.** Real-data frequency remains open |
| **ADR-0012** / D-012 | **Terrain realism via an explicit slope target anchored to LOLA**; extreme terrain retained as a diagnostic; conclusions reported per regime | **Created. `ACCEPTED`** |
| **ADR-0003** / D-003 | RMSE never stands alone | **Outstanding GT-free item discharged**, with the **primary/secondary ordering reversed by measurement** |
| D-017 | `lo_max_points` caps the LO **refit sample**, never the consensus scoring | Recorded |
| D-018 | Preserve `results_preEXP002.csv`; never overwrite superseded results | Recorded |
| D-019 | **Realistic mare becomes the priority benchmark** for EXP-003 | Recorded |
| D-020 | **Runtime is no longer a primary constraint** (median 0.262 s, worst 3.640 s vs a ≤ 60 s budget) | Recorded |
| D-021 | **Report per regime, never pooled** | Recorded — pooling is what produced E-002.5 and E-002.6 |
| D-022 | **Override the automated `best_deployable_signal` selection** | Recorded |

## 12. Tests and reproducibility status

| Item | Status |
|---|---|
| Suite | **168 passed, 2 skipped in 23.02 s** — verified by running `python -m pytest tests/` |
| New tests this stage | **36** — `test_ransac_performance.py` **12** + `test_gtfree_and_terrain.py` **24**, verified by `--collect-only` |
| Regression style | **Shapes and counts, not wall-clock, wherever possible**: `test_dlt_uses_the_economy_svd` (shapes), `test_lo_runs_only_on_a_new_best` (≤ 20 refits), `test_scoring_is_never_subsampled` (3000 inliers found), `test_none_target_disables_normalisation` (`np.array_equal`) |
| Bit-identical terrain reproduction of EXP-001 | **Yes** — `target_slope_median_deg=None` disables normalisation bit-identically |
| Bit-identical EXP-001 result reproduction | **No.** Stated tolerance **±0.5853 px**; **0/45 flips** — both re-verified for this report |
| Seeds | Objective 2 statistics 1001–1005; objectives 3 & 4 calibration 1001–1004, **validation 7001–7004** |
| Superseded artefacts preserved at | `experiments/EXP-001/results_preEXP002.csv` |
| Not preserved | Pre-fix `ransac.py` / `estimate.py` source; original EXP-001 figures |

## 13. Files / modules created or changed

| Path | Status | Purpose |
|---|---|---|
| `src/siim/evaluation/gtfree.py` | **created** | `held_out_residual`, `cycle_consistency`, `loop_closure`, `spatial_split_consistency` |
| `src/siim/geometry/estimate.py` | changed | `full_matrices=False` + load-bearing comment |
| `src/siim/verification/ransac.py` | changed | LO trigger fix, `lo_max_points`, `RansacTiming` |
| `src/siim/data/synthetic_terrain.py` | changed | `target_slope_median_deg`, `REFERENCE_BASELINE_M`, four regimes, `realistic` flag |
| `src/siim/evaluation/__init__.py` | changed | Export the GT-free surface |
| `scripts/exp002_common.py` | created | Shared regimes, evaluation, threshold selection |
| `scripts/run_exp002_ransac.py` | created | Objective 1 + `_legacy_ransac` |
| `scripts/run_exp002_terrain.py` | created | Objective 2 |
| `scripts/run_exp002_threshold.py` | created | Objective 3 |
| `scripts/run_exp002_gtfree.py` | created | Objective 4 |
| `tests/test_ransac_performance.py` | created | 12 tests |
| `tests/test_gtfree_and_terrain.py` | created | 24 tests |
| `experiments/EXP-002/*` | created | 4 JSONs + 4 CSVs + README |
| `experiments/EXP-001/results.csv`, `metrics.json`, `figures/*` | **regenerated** | Old numeric results preserved as `results_preEXP002.csv`; **figures were not** |
| `docs/architecture_decisions.md` | changed | ADR-0011, ADR-0012 added; ADR-0003 updated |

## 14. Limitations and threats to validity

1. **Objective 4's cases are constructed, not pipeline output.** They demonstrate the
   estimators' *mathematics*. They say nothing about how often such failures occur.
2. **The cycle-consistency construction deliberately targets its blind spot.** A real
   reverse pass is independent and would not cancel exactly. The false-alarm rate of 1.000
   is an artefact of the construction, not a property of the estimator in deployment.
3. **Loop closure is validated on constructed transforms only.** Real per-edge errors may
   be correlated. Whether overlapping triplets exist in a real dataset is unknown.
4. **All terrain is synthetic and Lambertian.** Realistic *slope statistics* are not
   realistic *radiometry*. Real regolith backscatters strongly and shows an opposition surge.
5. **Slope statistics are baseline-dependent.** The 15 m reference is recorded with every
   target; at OHRC's 0.25 m/px the real surface is rougher than these figures.
6. **3 seeds per case in the regime sweep** (5 for the statistics). Small differences
   between regimes are not resolvable.
7. **Δaz sampled at 0/15/30/45/60/90° only.** The cliff is bracketed 15–30°, **not located**.
8. **40° and 60° Δaz validation subsets are degenerate** — every case fails, so
   discrimination is undefined there.
9. **`n_inliers` per-subset sensitivity** — computed in the §3.7 addendum. Its recall is
   earned mostly on total-collapse failures (93% of validation failures sit in subsets
   where every case fails), and 5 of 7 false alarms are in realistic mare.
10. **`_legacy_ransac` under-states the defect** and is labelled as such; only the directly
    profiled numbers are quoted.
11. **Pre-fix source is not preserved** — the defects cannot be re-run from source.
12. **No real modality difference has been tested. No multi-modal claim is supportable.**
13. **Runtime figures are one CPU, one machine.**

## 15. Lessons learned

1. **Stage-level instrumentation is what makes a defect findable.** "RANSAC is slow" is not
   a diagnosis; "51.55 s of 53.9 s inside `svd`" is. `RansacTiming` was added *because* of
   this, and it is what will catch the next one.
2. **A three-orders-of-magnitude cost can hide inside a completely idiomatic line.**
3. **When re-implementing a published algorithm, re-check the trigger condition** — the
   maths can be right while the control flow is not.
4. **Cap the refit, never the scoring.** Robustness must not be silently traded for speed.
5. **"Realistic" is a claim requiring an authoritative external anchor.** "Looks lunar" is
   unfalsifiable.
6. **Validate the generator before trusting anything measured on it.** E-002.4 → E-002.5 →
   E-002.6 is one causal chain: an unvalidated dataset assumption propagated into two wrong
   conclusions.
7. **Keep the superseded dataset.** The cliff moving from 30° to 15° is only *demonstrable*
   because regime C still exists.
8. **A signal that collapses to a sentinel has its AUC measured on the sentinel. Always
   check the finite subset.** The automated pick was wrong and was nearly reported.
9. **Never let an automated selection stand unexamined** just because it produced the
   highest number.
10. **Declare negative controls in advance.** `fit_rmse` at ROC AUC 0.4947 is evidence
    *because* it was declared before the run; the same number found afterwards would have
    been a rationalisation.
11. **Distinguish "the separation observed in this sample" from "the rule validated on
    unseen data".** Only the second is usable.
12. **Correct a wrong mechanism without discarding a right observation** (E-002.10).
13. **Report the tolerance, not just the agreement.** "0/45 flips" is only meaningful next
    to "±0.5853 px" — and that tolerance retired a separate comparison as noise.
14. **State clearly when a comparison artefact is not faithful.** The `_legacy_ransac` note
    makes the 968× figure trustworthy rather than suspicious.

## 16. What must NOT be repeated

| Prohibition | Earned by |
|---|---|
| **Never call `np.linalg.svd` on a tall design matrix without `full_matrices=False`.** | E-002.1 |
| **Never trigger LO-RANSAC's local optimisation on anything but a new best model.** | E-002.2 |
| **Never subsample the consensus scoring set.** Cap the refit only. | D-017 |
| **Never generate terrain without a slope target anchored to a published source, and never report a slope median without its baseline.** | E-002.4 |
| **Never pool results across terrain regimes.** Conclusions invert between them. | D-021, E-002.5, E-002.6 |
| **Never quote a cliff location, scale limit, or success rate without naming the regime.** | E-002.5, E-002.6 |
| **Never accept an automated "best signal" pick without inspecting the finite subset.** | E-002.7, D-022 |
| **Never report an AUC for a signal that is non-finite on a substantial fraction of cases** without stating that fraction and its correlation with the label. | E-002.7 |
| **Never use held-out residual, split consistency, or cycle consistency as a correctness check.** They are degeneracy detectors. | E-002.8, E-002.9 |
| **Never combine a working detector with blind ones into a single confidence score.** | ADR-0011 |
| **Never present an emulated "before" as a measured one.** Label the source. | §1.4 |
| **Never delete pre-fix source or original figures.** Both were lost this stage. | §12 |
| **Never diagnose a performance problem from plausibility.** Profile. | A1 / E-002.1 |
| **Never label a sensitivity table with a signal it was not computed for.** | §3.6 |

## 17. What the next stage (EXP-003) should do

From `experiments/EXP-002/README.md` and ADR-0011 / ADR-0012:

1. **The bar moved.** The success criterion is now stated against **A-regimes**: a
   representation earns its place only if it moves the last fully-successful Δazimuth
   **beyond 30°**.
2. **Report per regime, never pooled** (D-021) — conclusions invert between regimes.
3. **Realistic mare is the priority case** (D-019): earliest failure on both axes,
   **312 vs 22,119 kp/Mpx**.
4. **Use `n_inliers <= 8`** (equivalently `< 9`) as the success/failure criterion —
   **never `fit_rmse`**. The form changed at D-023; see §3.7, E-002.12.
5. **Carry loop closure forward** as the only trustworthy GT-free correctness check.
6. **Resolve the cliff edge** at **18 / 21 / 24 / 27°** on A-regimes, **≥ 3 seeds**.
7. **Runtime is no longer a constraint** (D-020).

**Explicitly out of scope until EXP-003 runs:** RIFT2, phase congruency, orientation-mod-π
as a shipped component, and every learned matcher.

**ADR-0004** (polarity-agnostic structure as the default representation) remains `PROPOSED`
and states plainly that **if raw intensity wins, the ADR is superseded.** EXP-003 is that test.

**Two documentation debts EXP-003 should discharge while it is in the area:**

- ~~Compute and record a per-subset sensitivity analysis for **`n_inliers`**~~ —
  **DONE**, §3.7 / `objective3_ninliers_sensitivity.json` (RL-022).
  **Carry D-023 forward: the rule is `n_inliers <= 8`, not `< 8`.**
- Decide whether to re-measure or drop EXP-001's unverified crater-generation timing claim.

## 18. Open questions / unresolved risks

| # | Question | Why unresolved | What would resolve it |
|---|---|---|---|
| Q1 | Does a polarity-agnostic representation move the cliff beyond Δaz 30° on A-regimes? | Not built | **EXP-003** — its entire content |
| Q2 | Where exactly is the cliff edge between 15° and 30°? | Sampled at 15/30 only | EXP-003: 18/21/24/27°, ≥ 3 seeds |
| Q3 | How often do coherent wrong solutions arise on **real** lunar imagery? | All cases were constructed | Real data |
| Q4 | Does loop closure survive **correlated** per-edge errors from a real matcher? | Validated on constructed transforms | Real pipeline output over triplets |
| Q5 | Will overlapping triplets exist in the evaluation dataset? | Unknown; flagged since ANALYSIS §F.1.4 | Dataset access |
| Q6 | Does `max_uncovered_disc_radius` correlate with local held-out error? | Two supporting anecdotes only (EXP-001 el=60°, EXP-002's 2-inlier case) | **EXP-007** |
| Q7 | Does scale normalisation rescue matching at 20× and 320×? | Tested to 4× only | **EXP-004** |
| Q8 | Does protocol choice dominate matcher choice on lunar data? | Evidence is SAR-optical (33×), not lunar | **EXP-006** — underwrites the project's headline thesis |
| Q9 | CPU latency of learned engines | Not measured | **EXP-005** |
| Q10 | Licence status of candidate pretrained weights | Audit table not populated | ADR-0008 |
| Q11 | Does relief displacement break global models? | Derivation only, since EXP-000 | Real high-relief data or a 3-D-aware generator |
| ~~Q12~~ | ~~What is `n_inliers`'s per-regime sensitivity?~~ | **RESOLVED** — §3.7, `objective3_ninliers_sensitivity.json` | Recall 1.000 in all 4 regimes; mare FPR 0.0588, others 0.000 |
| Q13 | Does `n_inliers <= 8` hold in the **discriminable** regime, where correct and wrong cases coexist? | 96 of 103 validation failures are total collapse; only 7 are discriminable | EXP-003 generates cases in that regime — re-measure there, do not inherit |

## 19. Artefacts

| File | Contents |
|---|---|
| `experiments/EXP-002/README.md` | Stage-contemporary report, with `[OBSERVED]` / `[HYPOTHESIS]` / `[CRITERION]` / `[DECISION]` markers |
| `experiments/EXP-002/objective1_ransac.json` | SVD benchmark (n = 500/1000/2115), before/after, robustness, scaling, stage timing |
| `experiments/EXP-002/objective2_terrain.json` | LOLA reference, 4 regime statistics (5 seeds), density separability, EXP-001 subset re-run |
| `experiments/EXP-002/objective2_terrain_cases.csv` | 108 cases |
| `experiments/EXP-002/objective3_threshold.json` | 6 signals, calibration + validation, EXP-001 claim test, sensitivity |
| `experiments/EXP-002/objective3_threshold_cases.csv` | **384 rows** — 192 calibration + 192 validation |
| `experiments/EXP-002/objective3_ninliers_sensitivity.json` | **Addendum (D2 resolution)** — corrected `n_inliers` sensitivity, threshold sweep, Wilson CIs, diagnostics, verdict |
| `experiments/EXP-002/objective3_ninliers_sensitivity_cases.csv` | Flat per-subset rows of the corrected table |
| `scripts/run_exp002_ninliers_sensitivity.py` | The addendum runner. Recomputes from preserved cases; self-checks against the original |
| `experiments/EXP-002/objective4_gtfree.json` | Part A (4 kinds × 2 estimators) + Part B (4 kinds × 2 estimators) |
| `experiments/EXP-002/objective4_gtfree_partA.csv` / `_partB.csv` | Per-case detail |
| `experiments/EXP-001/results_preEXP002.csv` | **EXP-001 results before the RANSAC fix — preserved** |

**Cross-stage records:** `ERROR_LEDGER.md` (E-006, E-007, E-009–E-015, E-017) ·
`DECISION_LEDGER.md` (D-011, D-012, D-017–D-022) · `STAGE-INDEX.md` · `../STAGE_HISTORY.md`.
