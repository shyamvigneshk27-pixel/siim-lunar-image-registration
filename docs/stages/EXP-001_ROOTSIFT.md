# EXP-001 — RootSIFT classical baseline against synthetic ground truth

**Stage ID:** EXP-001 · **Status:** COMPLETE
**Date:** 2026-08-24 (the only date recorded in repository artefacts)
**Depends on:** PHASE-0 · **Followed by:** EXP-002

> **Reconstruction note.** Reconstructed from `experiments/EXP-001/README.md`, `metrics.json`, `results_preEXP002.csv` (the numbers **as measured at the time**), `results.csv` (regenerated during EXP-002), `scripts/run_exp001.py`, `src/siim/{data,matching,verification,evaluation,baselines}/*`, `tests/test_synthetic_terrain.py`, `tests/test_matching_and_ransac.py`, `tests/test_evaluation.py`, and `docs/research_log.md` RL-009 – RL-014.
>
> **No git history exists**, so the order of edits within the stage is **not established from repository evidence**. Where this report quotes EXP-001 results it uses `results_preEXP002.csv` — the values as they stood when EXP-001's conclusions were drawn — and flags where EXP-002's re-run changed them.
>
> The EXP-001 figures under `experiments/EXP-001/figures/` were **regenerated** by the EXP-002 re-run. The original figure files are **not preserved**; the original numeric results are (`results_preEXP002.csv`).

---

## A. Objective

Establish a trustworthy classical baseline (B1) **and** a non-circular evaluation harness, before any learned matcher is considered (ANALYSIS §I; spec §20, §66).

The harness was the more important half. The baseline was expected to fail somewhere; the point was to be able to *tell* when it did, and by how much, without ground-truth correspondences of the kind the real problem will never supply.

## B. Experimental design

45 cases in seven groups (`scripts/run_exp001.py:build_cases`):

| Group | Varies | Cases |
|---|---|---|
| A_model | Transform model of the truth (5 models) | 5 |
| B_azimuth | Δ Sun azimuth: 0, 15, 30, 45, 60, 90, 135, 180° | 8 |
| B_elevation | Δ Sun elevation: −30, −15, +15° | 3 |
| C_scale | Scale ratio: 1.0, 1.25, 1.5, 2.0, 3.0, 4.0 | 6 |
| D_scene | 4 scene types × {same Sun, Δaz = 60°} | 8 |
| E_ambiguity | Repetitive lattice, `ambiguity` 0.0 → 1.0 | 5 |
| F_low_sun | Sun elevation 10, 20, 35, 60° (with Δaz = 45°) | 4 |
| G_rootsift | RootSIFT vs plain SIFT × Δaz ∈ {0, 45, 90} | 6 |

**Configuration** (`metrics.json:config`): 512×512 images from a 1024×1024 height field; seed `20260824`; RANSAC threshold 3.0 px; "correct match" threshold 3.0 px (deliberately the same yardstick, so `reported_inlier_ratio` and `true_inlier_precision` are like-for-like); ratio test 0.8; mutual NN on; default fit model affine. OpenCV 5.0.0.

**Data roles.** All data is synthetic with exact ground truth. There is **no train/calibration/validation split in EXP-001** — every case is both generated and reported from the same seed. This is a documented weakness that EXP-002 objective 3 exists to correct.

## C. Synthetic terrain and image-pair construction

The defining design choice (`src/siim/data/synthetic_terrain.py` module docstring): build a **2.5-D height field and physically shade it**, rather than photometrically perturbing one image.

The reason is stated in the code: gain, bias and gamma all *preserve the sign of a gradient*, so no perturbation of a single image can reproduce shadow reversal. Only re-illuminating an actual surface does.

- **Height field:** fractal noise (summed smoothed-noise octaves) plus parametric craters (parabolic bowl + raised rim). Four scene types: `highlands`, `mare`, `repetitive`, `mixed`.
- **Rendering:** Lambertian `n·l` shading plus **cast shadows** by ray-marching toward the Sun, with configurable azimuth/elevation, `pixel_scale`, ambient floor and noise.
- **Pair construction:** the *same* height field is rendered twice — once in the source frame, once warped into the reference frame — each under its own Sun geometry. Geometry stays exactly known while the appearance difference is physically produced.
- **Physical consistency under scale:** a scale change alters metres-per-pixel and therefore apparent slope, so `make_pair` recomputes `ref_pixel_scale`. Without this a "scale pair" would be a resized picture rather than a scale change.

**Verified, not assumed** (`tests/test_synthetic_terrain.py`): the difference of two renderings at azimuth 90° and 270° correlates with the predicted shading identity `−2cos(el)·gx/|n|` at **0.989**, and image x-gradients are **anti-correlated at −0.853** under reversal. Raw intensities remain correlated (R² ≈ 0.71) because both renderings share the slope-magnitude term — which is why a naive intensity-correlation check would miss the problem entirely.

**Stated limitations** (module docstring): Lambertian, not Hapke — the *geometry* of illumination is right, the radiometry approximate. Terrain is fractal noise plus parametric craters, without ejecta rays, secondary chains, lava flow fronts or mass wasting. Results measure algorithm behaviour under controlled conditions and are **not** evidence about real Chandrayaan-2 data.

## D. Known ground truth

`SyntheticPair.transform` is the exact source → reference transform, plus a `reference_valid` mask and `overlap_fraction`. Ground truth is used **only to score**, never as a pipeline input.

Accuracy is measured by `endpoint_error`, which compares the **estimated map against the true map on a dense grid** — including where no correspondences were found. This is what distinguishes it from the circular statistic of ANALYSIS §A.3.

## E. RootSIFT pipeline

`src/siim/matching/rootsift.py`, `src/siim/baselines/rootsift_pipeline.py`.

- OpenCV SIFT (contrast 0.04, edge 10, σ 1.6, 3 octave layers), **uncapped** `nfeatures` — deliberately, because capping makes OpenCV retain the strongest responses and concentrates keypoints in high-contrast terrain, pre-damaging the spatial coverage that spec §15 asks about.
- **RootSIFT**: L1-normalise the descriptor, then element-wise square root, so Euclidean distance equals the Hellinger distance between the original histograms.
- Chosen as a deliberately *strong* baseline: spec §49 forbids sabotaging a baseline, and §E.2 measures the eventual contribution as a delta over it.

The module docstring states the expected structural limitation up front: SIFT bins gradient orientation over `[0, 2π)`, so under azimuth change corresponding descriptors mismatch **systematically rather than noisily**, and no ratio threshold repairs that.

## F. Matching

Lowe ratio test (0.8) **plus** mutual-nearest-neighbour consistency. The two are kept separate because they catch different errors: the ratio test rejects locally ambiguous matches, while mutual NN constrains the *reverse* direction and removes many-to-one matches.

## G. RANSAC / geometric verification

`src/siim/verification/ransac.py` — LO-RANSAC written in-house so that all five models are supported uniformly and the geometry stack stays OpenCV-free (ADR-0007).

The module docstring states the limitation the module cannot fix: RANSAC **maximises consensus**, so a large mutually consistent *wrong* subset will be found and reported with a high inlier ratio. The inlier ratio measures self-consistency, never correctness.

*(The version used in EXP-001 contained two performance defects, fixed in EXP-002 — see §L and EXP-002 objective 1.)*

## H. Evaluation methodology

`src/siim/evaluation/metrics.py` computes, side by side:

| Circular (what the pipeline believes) | Non-circular (what is true) |
|---|---|
| `reported_inlier_ratio` | `true_inlier_precision` |
| `reported_inlier_rmse` (fit) | `true_error_median/p90/max` |
| — | `transform_error_median/p90/max` (map vs map, dense grid) |
| — | `confidence_gap` = reported ratio − true precision |

Plus `coverage_metrics` (primary: `max_uncovered_disc_radius`, ADR-0006) and `classify_failure` (spec §51 taxonomy). Coverage is scored over the estimated **overlap**, not the whole frame.

---

## I. Results (as measured at the time — `results_preEXP002.csv`)

### I.1 Fixed illumination — transform model recovery

| Truth model | Fitted | Inliers | True precision | True transform error (median) |
|---|---|---|---|---|
| translation | affine | 2454 | 1.000 | 0.009 px |
| euclidean | affine | 1863 | 1.000 | 0.033 px |
| similarity | affine | 1443 | 0.997 | 0.386 px |
| affine | affine | 1997 | 0.999 | 0.248 px |
| projective | projective | 2112 | 1.000 | 0.019 px |

**Under fixed illumination the classical baseline is genuinely strong** — all five models at or below 0.4 px with ≥ 99.7% true precision.

### I.2 Δazimuth — the headline

| Δaz | Putative | Inliers | Reported ratio | **True precision** | **True transform error** |
|---|---|---|---|---|---|
| 0° | 2027 | 2023 | 0.998 | 0.999 | 0.359 px |
| 15° | 1571 | 1562 | 0.994 | 0.999 | 0.208 px |
| 30° | 179 | 147 | 0.821 | 0.980 | 0.290 px |
| **45°** | **28** | **4** | 0.143 | **0.000** | **325.59 px** |
| 60° | 22 | 4 | 0.182 | 0.000 | 210.99 px |
| 90° | 17 | 3 | 0.176 | 0.000 | 1000.18 px |
| 135° | 29 | 4 | 0.138 | 0.000 | 332.62 px |
| 180° | 28 | 4 | 0.143 | 0.000 | 769.70 px |

**A cliff between 30° and 45°**, not a gradual decline. Putative matches collapse 179 → 28.

### I.3 Δelevation

| Δel | Inliers | True precision | True transform error |
|---|---|---|---|
| −30° | 60 | 0.983 | 0.750 px |
| −15° | 834 | 0.995 | 0.325 px |
| +15° | 1135 | 0.996 | 0.489 px |

**All succeeded.** Elevation change is survivable where azimuth change is not.

### I.4 Scale

| Scale | Inliers | True precision | True transform error |
|---|---|---|---|
| 1.0 | 2762 | 1.000 | 0.002 px |
| 1.25 | 1390 | 1.000 | 0.270 px |
| 1.5 | 955 | 1.000 | 0.178 px |
| 2.0 | 559 | 1.000 | 0.341 px |
| 3.0 | 205 | 0.995 | 1.277 px |
| 4.0 | 129 | 1.000 | 1.108 px |

No failure through 4×; error crosses 1 px near 3×. **(This conclusion did not survive EXP-002 — see §K.6.)**

### I.5 Scene type

| Scene | Same Sun | Δaz = 60° |
|---|---|---|
| highlands | 2023 inl, 0.359 px | 4 inl, 211 px ✗ |
| mare | 1101 inl, 0.020 px | **2 putative, 0 inliers** ✗✗ |
| repetitive | 352 inl, 0.118 px | 3 inl, 818 px ✗ |
| mixed | 1430 inl, 0.021 px | 4 inl, 2423 px ✗ |

Mare is the worst case: only **2 putative matches** survived at Δaz = 60°.

### I.6 Repetitive terrain — the coherent wrong solution

| ambiguity | Putative | Inliers | Reported ratio | True precision | True transform error |
|---|---|---|---|---|---|
| 0.0 | 570 | 567 | 0.995 | 1.000 | 0.009 px |
| 0.4 | 250 | 248 | 0.992 | 1.000 | 0.009 px |
| 0.7 | 104 | 100 | 0.962 | 1.000 | 0.016 px |
| 0.9 | 122 | 112 | 0.918 | 1.000 | 0.006 px |
| **1.0** | 40 | 7 | 0.175 | **0.000** | **64.008 px** |

At full ambiguity the estimate is wrong by **exactly 64.00 px — one lattice period** (period = 64 px, `synthetic_terrain.py`).

### I.7 Low Sun (with Δaz = 45° held)

| Elevation | Inliers | True precision | True error |
|---|---|---|---|
| 10° | 6 | 0.000 | 848 px ✗ |
| 20° | 4 | 0.000 | 355 px ✗ |
| 35° | 3 | 0.333 | 193 px ✗ |
| 60° | 8 | 1.000 | 0.291 px — flagged **poor coverage** |

The one success had 8 inliers and `max_uncovered_disc` = 0.392. Correct, but fragile — and **coverage caught a weakness the error metric reported as success**.

### I.8 Failure totals

**17 of 45 cases wrong** (true transform error > 3 px). Failure taxonomy at the time: `no_model_found` 16, `none` 27, `poor_spatial_coverage` 1, `too_few_putative_matches` 1.

### I.9 Fit RMSE — the decisive measurement

Among the 17 wrong cases:

| Case | Inliers | **Fit RMSE** | **True error** |
|---|---|---|---|
| Δaz = 45 | 4 | **5.68e-14 px** | 325.59 px |
| Δaz = 90 | 3 | **2.46e-13 px** | 1000.18 px |
| Δaz = 180 | 4 | **2.13e-13 px** | 769.70 px |
| mixed / Δaz = 60 | 4 | **9.10e-13 px** | 2422.56 px |
| repetitive / Δaz = 60 | 3 | **0.00e+00 px** | 818.10 px |
| low Sun 10° | 6 | **9.36e-14 px** | 848.24 px |

**11 of 17 failed cases reported a fit RMSE below 1e-12 px while being 190–2400 px wrong.**

### I.10 Runtime

| Stage | Median |
|---|---|
| SIFT detect + describe (both images) | 0.115 s |
| Descriptor matching | 0.085 s |
| LO-RANSAC | 0.184 s |
| **Total pipeline** | **0.387 s** |

With one outlier: the projective case took **59.06 s**, of which 58.86 s was RANSAC. See §L.

---

## J. Major discoveries

1. **Illumination is the dominant failure axis.** A cliff at Δaz 30→45°, while scale survived to 4× and elevation to −30° in the same suite.
2. **Azimuth is far more damaging than elevation.** Δel = −30° succeeded at 0.750 px; Δaz = 45° failed at 325.59 px. Design consequence: an illumination-robust representation must prioritise invariance to shadow *direction* over shadow *length*.
3. **Fit RMSE can be catastrophically misleading.** Not merely noisy — in the failure regime it attains its *best possible value*. An evaluation quoting inlier RMSE alone would have ranked these catastrophic failures as its best results.
4. **Coherent wrong solutions pass RANSAC.** The lattice case produced an error of exactly one crater spacing with a fit RMSE of 0.028 px.
5. **RootSIFT showed no reliable advantage over plain SIFT.** See §K.5.
6. **Scale behaviour was overestimated because of terrain characteristics.** See §K.6 — established later, in EXP-002.

---

## K. Errors in the original reasoning

Recorded as they were believed, not as they were later corrected.

### K.1 The shadow-reversal hypothesis was too narrow

**Original hypothesis:** ANALYSIS §B2 / RL-003 — classical descriptors fail because a ~**180°** azimuth change *reverses* gradient polarity, so descriptors differ by π.
**Evidence:** EXP-001 group B, exact ground truth.
**Observed result:** Failure at **45°**, not 180°. Δaz = 30° still registered at 0.290 px; 45° failed completely.
**Why the hypothesis failed:** Polarity reversal is a sufficient condition, not a necessary one. Shadow *movement* alone rotates gradient orientations enough to break `[0, 2π)` orientation binning; full reversal is not required.
**Updated conclusion (RL-009):** The mechanism (orientation binning) was right; the magnitude was wrong by a factor of four. **The problem is harder than the analysis assumed.**

### K.2 §B6 overstated the coherent-wrong-solution risk

**Original hypothesis:** ANALYSIS §B6 — repetitive crater terrain is a *primary* danger, producing self-consistent wrong solutions with high inlier ratios.
**Evidence:** EXP-001 group E, ambiguity sweep.
**Observed result:** At ambiguity ≤ 0.9 RootSIFT was **perfect** (0.006–0.016 px). The failure required deliberately removing *all* disambiguating context — no fractal base, no per-crater jitter.
**Why the hypothesis failed:** The ratio test plus mutual-NN check is substantially more robust to repetition than assumed; even weak surrounding texture disambiguates.
**Updated conclusion (RL-012):** The failure is real but needs a genuinely feature-poor, near-perfectly periodic scene. Risk R5 probability lowered from Med to Low-Med, impact unchanged. Recorded verbatim in `synthetic_terrain.py`: the `ambiguity` parameter exists *because* the first version of the scene did not fool RootSIFT at all.

### K.3 The predicted "high confidence + wrong" failure did not materialise

**Original hypothesis:** ANALYSIS §B6 — the dangerous case is a *high* reported inlier ratio on a wrong answer.
**Evidence:** `confidence_gap` across all 17 wrong cases.
**Observed result:** Largest confidence gap **+0.400**. Wrong cases had *low* reported ratios (0.087–0.400).
**Why the hypothesis failed:** On this data the failure mode was total match collapse, not confident wrongness.
**Updated conclusion:** Fit RMSE was the misleading metric; the inlier *ratio* degraded appropriately. Recorded honestly in `experiments/EXP-001/README.md`.

### K.4 "Inlier count separates cleanly" — a claim that was circular from the start

**Original hypothesis:** RL-011 — wrong cases have ≤ 7 inliers, correct cases ≥ 8; a clean separation.
**Evidence:** All 45 EXP-001 cases.
**Observed result:** True on those 45 cases.
**Why the hypothesis failed:** The threshold and its evaluation came from **the same 45 cases**, and the split sat exactly on the `min_inliers = 8` value that `classify_failure` already used. EXP-001's own README flagged both caveats.
**Updated conclusion (RL-019):** Refuted on independent data in EXP-002 — a *correct* case succeeded with **2** inliers. The separation claim is false; the operating point survives separately.

### K.5 RootSIFT's advantage was assumed from the literature, not measured

**Original hypothesis:** RootSIFT outperforms plain SIFT (Arandjelović & Zisserman), so B1 should use it.
**Evidence:** EXP-001 group G.
**Observed result:**

| Δaz | RootSIFT | plain SIFT |
|---|---|---|
| 0° | 2023 inl / 0.359 px | 2024 inl / **0.223 px** |
| 45° | 4 inl / 325.59 px ✗ | 5 inl / 318.25 px ✗ |
| 90° | 3 inl / 1000.18 px ✗ | 4 inl / 410.33 px ✗ |

**Why the hypothesis failed:** No measurable advantage on this data; three comparison points at one seed each is weak evidence either way.
**Updated conclusion (RL-014, ADR-0009):** Retain RootSIFT (free, standard) but **drop the claim**. Recorded as a negative result rather than quietly kept on the strength of a citation (spec §69). EXP-002 later measured run-to-run variation at **±0.59 px**, which is larger than the 0.136 px difference — confirming it as noise (RL-016).

### K.6 "Scale is a far smaller problem than illumination" was stated too generally

**Original hypothesis:** From §I.4 — SIFT's scale-space search handles the scale axis; scale is secondary to illumination.
**Evidence:** EXP-002 objective 2, four terrain regimes.
**Observed result:** True on textured terrain, **false on realistic mare**, which fails at 2× (success 0.33) and 4× (0.00).
**Why the hypothesis failed:** EXP-001 tested scale on a single, unrealistically texture-rich terrain. Scale tolerance is a property of the descriptor **and the available texture**, not the descriptor alone.
**Updated conclusion (RL-018):** Narrowed. Mare becomes the priority case for EXP-003.

### K.7 The synthetic terrain was assumed realistic enough

**Original hypothesis:** Implicit — the terrain, though acknowledged as "too steep and too high-frequency" in EXP-001's limitations, was assumed not to affect the qualitative conclusions.
**Evidence:** EXP-002 objective 2.
**Observed result:** **89.55% of the EXP-001 terrain is steeper than the lunar angle of repose.** On realistic terrain the illumination cliff moves *earlier* (15–30°), and the scale conclusion inverts.
**Why the hypothesis failed:** Partially correct — the qualitative findings (cliff exists, azimuth dominant, RMSE inverted) did survive. But two quantitative conclusions did not.
**Updated conclusion (RL-017):** Conclusions are drawn per regime, from realistic regimes only.

---

## L. Engineering failures during EXP-001

### L.1 Ground-truth `pad`-offset bug — caught only by ground truth

**Problem:** The first `make_pair` rendered the reference into a canvas padded by 40 px on each side, cropped the padding off, and did **not** compose that offset into the returned ground-truth transform.
**Symptom:** RANSAC reported a **99.6% inlier ratio with 0.72 px fit RMSE** while the recovered transform disagreed with the declared ground truth by **56.57 px = 40·√2**.
**Root cause:** Cropping shifts the origin; the transform chain was not updated.
**Why it was dangerous:** Every self-reported metric looked excellent. A uniformly shifted match set is perfectly self-consistent — this is ANALYSIS §B6 occurring inside our own *evaluation harness*, before it was ever pointed at lunar data.
**Detection:** Only by comparing against ground truth. No self-consistency check could have found it.
**Fix:** `translation(pad, pad)` composed into `big_to_ref`, with a comment in `synthetic_terrain.py` explaining why the term is load-bearing.
**Regression protection:** `test_ground_truth_is_exact_regression`, whose failure message names the 56.6 px signature explicitly.
**Impact:** RL-013. Reinforced that evaluation code needs the same scepticism as pipeline code.

### L.2 LO-RANSAC performance outlier

**Problem:** The projective case took **59.06 s** against a 0.387 s median — a 150× outlier.
**Symptom:** 58.86 s of the 59.06 s was inside RANSAC.
**Root cause (at the time, partially diagnosed):** EXP-001's README attributed it to LO refitting the entire ~2100-point consensus up to 4 times per iteration over 100 iterations. **This diagnosis was incomplete** — EXP-002 found the dominant cause was a separate SVD defect (ERROR_LEDGER E-007).
**Why it was dangerous:** Correctness unaffected, but it broke the runtime budget and would have corrupted every future runtime comparison.
**Detection:** Per-stage timing recorded per case in `results.csv`.
**Fix:** **Deferred to EXP-002** — deliberately not fixed during EXP-001, and recorded as debt.
**Regression protection:** Added in EXP-002 (`tests/test_ransac_performance.py`).

### L.3 Crater generation cost

**Problem:** Each crater was evaluated over the full array; pair generation took ~14.6 s.
**Fix:** Restrict evaluation to the crater's bounding box (~1.6 R), since the profile is negligible beyond it. Comment retained in `_crater`.
**Evidence:** The optimisation is present in `synthetic_terrain.py`; the specific before/after timings are **not recorded in a repository artefact** — established from the code comment only.

### L.4 Test-assertion errors (my reasoning, not the code)

Documented in test docstrings:

- `test_azimuth_reversal_anticorrelates_image_gradients` records that raw intensities stay correlated at R² ≈ 0.71 under reversal, "which is exactly why a naive intensity-correlation check would miss the problem entirely" — the corrected framing measures *gradients*, not intensities.
- The repetitive-terrain periodicity test samples row 96, not row 128: the 64-px lattice places crater centres on rows 32/96/160, so row 128 has zero variance.

*(The precise sequence in which these test corrections occurred is not established from repository evidence — only the corrected final state and its explanatory docstrings.)*

---

## M. Acceptance criteria — verdict

Criteria from ANALYSIS §L, verdicts from `experiments/EXP-001/README.md`.

| # | Criterion | Target | Measured | Verdict |
|---|---|---|---|---|
| 1 | Algorithmic correctness, synthetic GT at 1× | median < 0.3 px | 0.002–0.386 px; 4 of 5 models < 0.3 | **PARTIAL** |
| 2 | Coverage | max gap ≤ 0.15 D | 0.028–0.096 on successes | **PASS** |
| 3 | Challenge A — small illumination | ≥ 90% success | 100% at Δaz ≤ 30° | **PASS** |
| 4 | Challenge B — large illumination | ≥ 90% success | **0% at Δaz ≥ 45°** | **FAIL** (expected) |
| 5 | Challenge D — large scale | ≥ 90% success | 100% to 4× | **PASS in tested range** |
| 6 | Challenge F — cross-sensor | ≥ 90% success | — | **NOT TESTED** (no real modality difference exists in synthetic data) |
| 7 | Failure detection | ≥ 95% recall, ≤ 20% FA | 100% / 0% via inlier count ≥ 8 | **PARTIAL** — circular (see K.4); properly validated in EXP-002 |
| 8 | Efficiency | ≤ 60 s/pair | median 0.387 s; **max 59.06 s** | **PARTIAL** — met with a defect |
| 9 | Sub-pixel accuracy on real cross-modal pairs | median held-out < 1.0 px | — | **NOT TESTED** — no real data |
| 10 | Loop-closure coherence | < 2 px | — | **NOT TESTED** — estimator not built until EXP-002 |

Criterion 4 failing was the expected and desired outcome: it is the gap the rest of the project exists to close, now measured rather than asserted.

---

## N. What EXP-001 changed about the architecture

- **ADR-0003 upgraded** from a structural argument to a measured one, and *strengthened*: fit RMSE is not merely circular but **inverted** in the failure regime.
- **ADR-0009 created**: retain RootSIFT as B1, drop the advantage claim.
- **ADR-0010 created**: promote EXP-003 (representations) ahead of the remaining classical baseline sweep, because illumination is measurably the dominant axis.
- **Reporting rule extended**: every RMSE must be quoted with its inlier count, because RMSE is uninterpretable without knowing how close `n` is to the model DOF.
- **Modules added**: `data/`, `matching/`, `verification/`, `evaluation/`, `baselines/`.
- **`geometry/` remained OpenCV-free.** OpenCV entered for SIFT only.

## O. Why learned matchers were not introduced

Recorded in `experiments/EXP-001/README.md` and ADR-0010:

1. **Spec §36 and §75** — a component ships only if it earns its place against a measured deficiency. EXP-001 established *where* classical methods break but not yet whether a better **representation** fixes it with classical machinery.
2. The failure is structural in the descriptor's use of `[0, 2π)` orientation binning — which a different *representation* may address without a learned model.
3. **ADR-0002** — CPU-only delivery; learned engines must first be measured for CPU latency (EXP-005, still open).
4. **ADR-0008** — licence audit gates every pretrained weight; unresolved.
5. The harness needed to be trustworthy first. EXP-001 found a 56.57 px bug in its own ground-truth generator (§L.1); introducing a learned matcher before that would have attributed harness bugs to the model.

## P. What EXP-002 was designed to resolve

From `experiments/EXP-001/README.md` §"What EXP-002 should test next":

1. Fix the LO-RANSAC scaling defect — it corrupts every future runtime comparison.
2. Fix terrain realism — everything downstream is measured on it, and it is optimistic.
3. Validate the failure threshold non-circularly.
4. Build the GT-free estimators (ADR-0003's outstanding item).
5. Resolve the cliff edge between 30° and 45°.

Items 1–4 became EXP-002's four objectives. Item 5 was deferred to EXP-003 after EXP-002 relocated the cliff.

## Q. Artefacts

| File | Contents |
|---|---|
| `experiments/EXP-001/README.md` | Stage-contemporary report |
| `experiments/EXP-001/results_preEXP002.csv` | **Results as measured at the time** — preserved |
| `experiments/EXP-001/results.csv` | Re-run after the EXP-002 RANSAC fix |
| `experiments/EXP-001/metrics.json` | Config, environment, failure counts (regenerated) |
| `experiments/EXP-001/figures/*.png` | **Regenerated**; originals not preserved |
