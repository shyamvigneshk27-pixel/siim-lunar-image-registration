# EXP-001 — RootSIFT / Matching Baseline

**Stage ID:** EXP-001
**Name:** RootSIFT classical baseline (B1) and the non-circular evaluation harness
**Status:** COMPLETE
**Date:** 2026-08-24 — the only date recorded in any repository artefact
**Depends on:** EXP-000 · **Followed by:** EXP-002

---

## 0. Provenance and what this report is

Retrospective, reconstructed **only** from repository artefacts:

`experiments/EXP-001/README.md` · `metrics.json` · `results_preEXP002.csv` ·
`results.csv` · `figures/*.png` · `scripts/run_exp001.py` ·
`src/siim/{data,matching,verification,evaluation,baselines}/*` ·
`tests/test_synthetic_terrain.py` · `tests/test_matching_and_ransac.py` ·
`tests/test_evaluation.py` · `docs/research_log.md` · `docs/architecture_decisions.md`.

**Which numbers this report quotes.** Where it reports EXP-001 *results*, it uses
**`results_preEXP002.csv`** — the values as they stood when EXP-001's conclusions were
drawn. `results.csv` and `metrics.json` were **regenerated** by the EXP-002 re-run and
carry different numbers; where that matters it is flagged explicitly.

**Limits on this reconstruction:**

1. **No git history** (`git rev-parse` → `fatal: not a git repository`). The order of edits
   within the stage, intermediate code states, and the sequence in which bugs were found
   are **[NOT VERIFIED]**.
2. **All artefacts carry the single date 2026-08-24.** Stage duration is **[NOT VERIFIED]**.
3. **The EXP-001 figures under `experiments/EXP-001/figures/` were regenerated** by the
   EXP-002 re-run. The original figure files are **not preserved**. The original *numeric*
   results are (`results_preEXP002.csv`).
4. **Pre-fix source text is not preserved.** Defects are evidenced by recorded measurements
   and by regression tests that still name them, not by diffs.

---

## 1. Stage objective

**The question:** *Where exactly does a strong classical matcher break on Sun-angle and
scale variation — and can we build an evaluation harness that tells us it has broken,
without ground-truth correspondences of the kind the real problem will never supply?*

Two deliverables, and **the harness was the more important half**. The baseline was
expected to fail somewhere; the point was to be able to *tell* when it did, and by how much.

Baseline B1 was chosen to be deliberately **strong**, not a straw man: the eventual
contribution is measured as a delta over it, so sabotaging it would make every later result
meaningless.

---

## 2. Starting assumptions

| # | Assumption | Source | Kind | Later status |
|---|---|---|---|---|
| A1 | Classical descriptors fail on illumination because a ~**180°** azimuth change reverses gradient polarity | ANALYSIS §B2, RL-003 | reasoned | **REFUTED** — failure at 45°, not 180° (§11.1) |
| A2 | Repetitive crater terrain is a **primary** danger, producing self-consistent wrong solutions at high inlier ratios | ANALYSIS §B6 | reasoned | **Overstated** — needed all disambiguating context removed (§11.2) |
| A3 | The dangerous failure is a **high** reported inlier ratio on a wrong answer | ANALYSIS §B6 | reasoned | **Did not materialise on this data** (§11.3) |
| A4 | RootSIFT outperforms plain SIFT (Arandjelović & Zisserman) | literature | inherited citation | **Unestablished here** — negative result (§11.4) |
| A5 | Scale is a smaller problem than illumination for classical features | reasoned + EXP-001 §6.4 | measured, over-generalised | **Narrowed by EXP-002** (§11.6) |
| A6 | The synthetic terrain, though acknowledged as steep, is realistic *enough* not to change the qualitative conclusions | implicit | assumed | **Partly wrong** — two quantitative conclusions did not survive (§11.7) |
| A7 | Photometric perturbation (gain/bias/gamma) cannot reproduce shadow reversal, so terrain must be physically shaded | `synthetic_terrain.py` docstring | reasoned + verified | **Confirmed by measurement** — §3.2 |
| A8 | The geometry layer from EXP-000 is trustworthy | EXP-000 | measured | Confirmed — but **insufficient**, see E-001.1 |

---

## 3. What we implemented

### 3.1 New modules

| Path | Lines | Purpose |
|---|---|---|
| `src/siim/data/synthetic_terrain.py` | 689 | 2.5-D height field, physical shading with cast shadows, GT pair construction |
| `src/siim/matching/rootsift.py` | 222 | SIFT detection, RootSIFT descriptor transform, ratio test + mutual NN |
| `src/siim/verification/ransac.py` | 278 | In-house LO-RANSAC over all five transform models |
| `src/siim/evaluation/metrics.py` | 247 | Circular and non-circular metrics reported **side by side**; `classify_failure` |
| `src/siim/evaluation/coverage.py` | 164 | `max_uncovered_disc_radius` (primary), occupancy, entropy, hull ratio |
| `src/siim/baselines/rootsift_pipeline.py` | 111 | B1 end-to-end pipeline |
| `scripts/run_exp001.py` | 433 | 45-case experiment runner |

`geometry/` remained **OpenCV-free**. OpenCV entered for SIFT/RootSIFT only (D-014).

### 3.2 The defining design choice — physically shaded terrain

From the `synthetic_terrain.py` module docstring: build a **2.5-D height field and
physically shade it**, rather than photometrically perturbing one image.

The stated reason, in the code: **gain, bias and gamma all preserve the sign of a
gradient**, so no perturbation of a single image can reproduce shadow reversal. Only
re-illuminating an actual surface does.

- **Height field:** fractal noise (summed smoothed-noise octaves) plus parametric craters
  (parabolic bowl + raised rim). Four scene types: `highlands`, `mare`, `repetitive`, `mixed`.
- **Rendering:** Lambertian `n·l` shading plus **cast shadows** by ray-marching toward the
  Sun, with configurable azimuth/elevation, `pixel_scale`, ambient floor and noise.
- **Pair construction:** the *same* height field is rendered twice — once in the source
  frame, once warped into the reference frame — each under its own Sun geometry. **Geometry
  stays exactly known while the appearance difference is physically produced.**
- **Physical consistency under scale:** a scale change alters metres-per-pixel and
  therefore apparent slope, so `make_pair` recomputes `ref_pixel_scale`. Without this a
  "scale pair" would be a resized picture rather than a scale change.

**`[MEASURED]`, not assumed** (`tests/test_synthetic_terrain.py`):

| Quantity | Value |
|---|---|
| Correlation of the az-90°/az-270° difference with the predicted shading identity `−2cos(el)·gx/│n│` | **0.989** |
| Correlation of image x-gradients under azimuth reversal | **−0.853** |
| Correlation of raw intensities under reversal | R² ≈ **0.71** (still positive) |

`[INTERPRETATION]` The last row is the important one: raw intensities remain correlated
because both renderings share the slope-magnitude term. **A naive intensity-correlation
check would miss the polarity problem entirely** — which is exactly why the test measures
*gradients*.

### 3.3 RootSIFT

`src/siim/matching/rootsift.py`.

- OpenCV SIFT (contrast 0.04, edge 10, σ 1.6, 3 octave layers), **uncapped** `nfeatures`
  (D-015) — deliberately, because capping makes OpenCV retain the strongest responses and
  concentrates keypoints in high-contrast terrain, pre-damaging the spatial coverage the
  project is required to report on.
- **RootSIFT:** L1-normalise the descriptor, then element-wise square root, so Euclidean
  distance equals the Hellinger distance between the original histograms.

The module docstring states the expected structural limitation **up front, before the
measurement**: SIFT bins gradient orientation over `[0, 2π)`, so under azimuth change
corresponding descriptors mismatch **systematically rather than noisily**, and no ratio
threshold repairs that.

### 3.4 Matching

Lowe ratio test (0.8) **plus** mutual-nearest-neighbour consistency, kept as two separate
stages because they catch different errors: the ratio test rejects locally ambiguous
matches; mutual NN constrains the *reverse* direction and removes many-to-one matches.

### 3.5 LO-RANSAC

`src/siim/verification/ransac.py` — written in-house so all five models are supported
uniformly and the geometry stack stays OpenCV-free (ADR-0007).

The module docstring states the limitation the module **cannot** fix: RANSAC **maximises
consensus**, so a large mutually consistent *wrong* subset will be found and reported with
a high inlier ratio. The inlier ratio measures self-consistency, never correctness.

*The version used in EXP-001 contained two performance defects, both deferred to EXP-002 —
see §9, E-001.2.*

### 3.6 Evaluation — the harness

`src/siim/evaluation/metrics.py` computes circular and non-circular metrics **side by
side**, which is the whole design:

| Circular — what the pipeline believes | Non-circular — what is true |
|---|---|
| `reported_inlier_ratio` | `true_inlier_precision`, `true_inlier_recall` |
| `reported_fit_rmse` (**fit**) | `true_error_median` / `p90` |
| — | `transform_error_median` / `p90` / `max` (map vs map, dense grid) |
| — | `confidence_gap` = reported ratio − true precision |

Plus `coverage_metrics` (primary `max_uncovered_disc_radius`, ADR-0006) and
`classify_failure` (the failure taxonomy).

**Ground truth is used only to score, never as a pipeline input.** Accuracy is measured by
`endpoint_error` comparing the **estimated map against the true map on a dense grid**,
including where no correspondences were found.

**D-016:** the "correct match" threshold is set **equal to** the RANSAC threshold (both
3.0 px), so `reported_inlier_ratio` and `true_inlier_precision` are judged on the same
yardstick and the comparison between them — the point of the module — is like-for-like.

---

## 4. Experiments performed

45 cases in seven groups (`scripts/run_exp001.py:build_cases`):

| Group | Varies | Cases |
|---|---|---|
| A_model | Transform model of the truth (5 models) | 5 |
| B_azimuth | Δ Sun azimuth: 0, 15, 30, 45, 60, 90, 135, 180° | 8 |
| B_elevation | Δ Sun elevation: −30, −15, +15° | 3 |
| C_scale | Scale ratio: 1.0, 1.25, 1.5, 2.0, 3.0, 4.0 | 6 |
| D_scene | 4 scene types × {same Sun, Δaz = 60°} | 8 |
| E_ambiguity | Repetitive lattice, `ambiguity` 0.0 → 1.0 | 5 |
| F_low_sun | Sun elevation 10, 20, 35, 60° (with Δaz = 45° held) | 4 |
| G_rootsift | RootSIFT vs plain SIFT × Δaz ∈ {0, 45, 90} | 6 |

**Configuration** (`metrics.json:config`, verified): 512×512 images from a 1024×1024 height
field; seed `20260824`; RANSAC threshold 3.0 px; correct-match threshold 3.0 px; ratio test
0.8; mutual NN on; default fit model affine; Sun reference `(315°, 45°)`.

### Data roles — and the weakness

| Role | Source |
|---|---|
| Synthetic ground truth | Every case; exact, from `SyntheticPair.transform` |
| Calibration (threshold selection) | **None — this is the weakness** |
| Validation (performance reporting) | **Same 45 cases** |
| GT-free evaluation | Not built until EXP-002 |

**There is no calibration/validation split in EXP-001.** Every case is both generated from
and reported on the same seed. This is a documented design weakness, flagged in EXP-001's
own README at the time, and it directly produced E-001.4. EXP-002 objective 3 exists to
correct it.

---

## 5. Exact commands used

Recorded in `experiments/EXP-001/README.md`:

```bash
python scripts/run_exp001.py                    # 45 cases, 332 s
python -m pytest tests/ -q                      # 132 passed, 2 skipped, 26 s
```

`scripts/run_exp001.py` takes **no arguments** — verified: no `argparse` import, no
`add_argument` call. Seed `20260824` is hard-coded.

**Note on the two timing figures.** The README's `332 s` is the stage-contemporary
wall-clock. `metrics.json:total_runtime_s` now reads **273.53**, and the test line now
reads **168 passed, 2 skipped** — both because the file was regenerated during EXP-002.
Summing `pipeline_s` over `results_preEXP002.csv` gives **86.7 s** of pipeline time, the
remainder being terrain generation. The `132 passed` figure is the suite size at EXP-001
and cannot be re-verified today.

**Environment** (`metrics.json:environment`): python 3.13.7 · numpy 2.3.3 ·
**opencv 5.0.0** · Windows-11-10.0.26200-SP0.

---

## 6. Quantitative results

**All tables below are from `results_preEXP002.csv`** — the values as measured at the time.
n = 1 case per row, 1 seed (`20260824`), 512² images, RANSAC threshold 3.0 px,
correct-match threshold 3.0 px. Environment as §5. `[MEASURED]` throughout.

"True transform error" is `transform_error_median`: median endpoint error between the
estimated and true map on a dense grid — **non-circular**. "Fit RMSE" is
`reported_fit_rmse` — **circular**.

### 6.1 Fixed illumination — transform model recovery

| Truth model | Fitted | Putative | Inliers | Reported ratio | True precision | **True transform error** |
|---|---|---|---|---|---|---|
| translation | affine | 2454 | 2454 | 1.000 | 1.000 | **0.009 px** |
| euclidean | affine | 1875 | 1863 | 0.994 | 1.000 | 0.033 px |
| similarity | affine | 1452 | 1443 | 0.994 | 0.997 | 0.386 px |
| affine | affine | 2003 | 1997 | 0.997 | 0.999 | 0.248 px |
| projective | projective | 2115 | 2112 | 0.999 | 1.000 | 0.019 px |

`[MEASURED]` Under fixed illumination all five models recover at or below 0.386 px with
≥ 99.7% true inlier precision.

`[INTERPRETATION]` The classical baseline is not the weak link when illumination is
constant. `[LIMITATION]` This is on regime-C terrain, later shown to be physically
impossible (§11.7) — the fixed-illumination numbers are therefore **optimistic**.

### 6.2 Δ azimuth — the headline

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

`[MEASURED]` **A cliff between Δaz 30° and 45°, not a gradual decline.** Putative matches
collapse 179 → 28; true precision goes 0.980 → 0.000 in one step.

`[INTERPRETATION]` There is no graceful degradation regime to tune within. It works, then
it does not. **`[CORRECTED IN EXP-002]`** — this cliff location is a property of regime-C
terrain; on realistic terrain it arrives at 15–30° (see `EXP-002_ransac_terrain_gtfree.md`).

### 6.3 Δ elevation

| Δel | Putative | Inliers | Reported ratio | True precision | True transform error |
|---|---|---|---|---|---|
| −30° | 76 | 60 | 0.789 | 0.983 | 0.750 px |
| −15° | 859 | 834 | 0.971 | 0.995 | 0.325 px |
| +15° | 1163 | 1135 | 0.976 | 0.996 | 0.489 px |

`[MEASURED]` **All three succeeded.** `[INTERPRETATION]` Elevation change is survivable
where azimuth change is not. Design consequence: an illumination-robust representation must
prioritise invariance to shadow **direction** over shadow **length**.

### 6.4 Scale

| Scale | Putative | Inliers | True precision | True transform error |
|---|---|---|---|---|
| 1.0 | 2762 | 2762 | 1.000 | 0.002 px |
| 1.25 | 1397 | 1390 | 1.000 | 0.270 px |
| 1.5 | 961 | 955 | 1.000 | 0.178 px |
| 2.0 | 563 | 559 | 1.000 | 0.341 px |
| 3.0 | 218 | 205 | 0.995 | 1.277 px |
| 4.0 | 133 | 129 | 1.000 | 1.108 px |

`[MEASURED]` No failure through 4×; error crosses 1 px near 3×.
**`[REFUTED IN PART BY EXP-002]`** — false on realistic low-texture mare, which fails at 2×
(§11.6).

### 6.5 Scene type

| Scene | Same Sun | Δaz = 60° |
|---|---|---|
| highlands | 2023 inl, 0.359 px | 4 inl, **211.00 px** ✗ |
| mare | 1101 inl, 0.020 px | **2 putative, 0 inliers** ✗✗ |
| repetitive | 352 inl, 0.118 px | 3 inl, **818.10 px** ✗ |
| mixed | 1430 inl, 0.021 px | 4 inl, **2422.56 px** ✗ |

`[MEASURED]` Every scene type works under fixed illumination; every one fails at Δaz = 60°.
**Mare is the worst case: only 2 putative matches survived** — the case is classified
`too_few_putative_matches` and its `transform_error_median` is `inf`.

`[INTERPRETATION]` Low texture and illumination change **compound rather than merely add**.

### 6.6 Repetitive terrain — the coherent wrong solution

| ambiguity | Putative | Inliers | Reported ratio | True precision | **True transform error** | Fit RMSE |
|---|---|---|---|---|---|---|
| 0.0 | 570 | 567 | 0.995 | 1.000 | 0.009 px | 0.127 |
| 0.4 | 250 | 248 | 0.992 | 1.000 | 0.009 px | 0.133 |
| 0.7 | 104 | 100 | 0.962 | 1.000 | 0.016 px | 0.095 |
| 0.9 | 122 | 112 | 0.918 | 1.000 | 0.006 px | 0.039 |
| **1.0** | 40 | 7 | 0.175 | **0.000** | **64.008 px** | **0.028** |

`[MEASURED]` At full ambiguity the estimate is wrong by **exactly 64.008 px — one lattice
period** (period = 64 px, `synthetic_terrain.py`) — with a fit RMSE of **0.028 px**.

`[INTERPRETATION]` This is the coherent-wrong-solution failure mode, reproduced. But it
required deliberately removing *all* disambiguating context; at ambiguity ≤ 0.9 the
baseline was essentially perfect (0.006–0.016 px). See §11.2.

### 6.7 Low Sun (with Δaz = 45° held)

| Elevation | Putative | Inliers | True precision | True error | Coverage max gap |
|---|---|---|---|---|---|
| 10° | 49 | 6 | 0.000 | 848.24 px ✗ | — |
| 20° | 46 | 4 | 0.000 | 355.49 px ✗ | — |
| 35° | 26 | 3 | 0.333 | 192.84 px ✗ | — |
| 60° | 27 | 8 | 1.000 | **0.291 px** | **0.392** — flagged `poor_spatial_coverage` |

`[MEASURED]` The one success had 8 inliers and `coverage_max_gap_ratio = 0.392`, against a
target of ≤ 0.15.

`[INTERPRETATION]` **Coverage caught a fragility the error metric reported as a success.**
This is the supporting anecdote for ADR-0006 — and only an anecdote: it is one case, and
ADR-0006 remains `PROPOSED` pending EXP-007's correlation test.

### 6.8 RootSIFT vs plain SIFT (group G)

| Δaz | RootSIFT: inliers / error | Plain SIFT: inliers / error |
|---|---|---|
| 0° | 2023 / **0.359 px** | 2024 / **0.223 px** |
| 45° | 4 / 325.59 px ✗ | 5 / 318.25 px ✗ |
| 90° | 3 / 1000.18 px ✗ | 4 / 410.33 px ✗ |

`[MEASURED]` No advantage for RootSIFT on this data; it is marginally *worse* at Δaz = 0.
3 comparison points, 1 seed each.

### 6.9 Coverage on successful cases

| Case | Inliers | max gap | occupancy | entropy |
|---|---|---|---|---|
| scale = 1.0 | 2762 | 0.028 | 1.000 | 0.997 |
| highlands / same Sun | 2023 | 0.040–0.047 | 1.000 | 0.990 |
| mare / same Sun | 1101 | 0.054 | 1.000 | 0.987 |
| repetitive / same Sun | 352 | 0.096 | 0.953 | 0.965 |
| **F_low_sun el = 60°** | **8** | **0.392** ✗ | 0.125 | 0.500 |

`[MEASURED]` Coverage `max_gap` on correct cases ranges **0.028 – 0.392**, the top of that
range being the single 8-inlier case. Excluding it, all correct cases are within the
≤ 0.15 target.

### 6.10 Failure totals and the two separation statistics

`[MEASURED]` **17 of 45 cases wrong** (`transform_error_median` > 3 px) — verified by
direct recount of `results_preEXP002.csv`.

Failure taxonomy **as measured at the time**: `no_model_found` 16 · `none` 27 ·
`poor_spatial_coverage` 1 · `too_few_putative_matches` 1.

> **Discrepancy, recorded rather than smoothed over.** The regenerated
> `metrics.json:failure_counts` reads `no_model_found` **17** · `none` 27 ·
> `too_few_putative_matches` 1 — the `poor_spatial_coverage` case is reclassified. Both
> total 45. The pre-EXP-002 CSV is the authority for EXP-001's contemporaneous claims.

| Statistic | Wrong cases (n = 17) | Correct cases (n = 28) | Separates? |
|---|---|---|---|
| **Inlier count** | max = **7** | min = **8** | **Yes, perfectly — on these 45 cases** |
| Reported inlier ratio | max = **0.400** | min = **0.296** | **No — ranges overlap** |

`[INTERPRETATION]` Absolute inlier count separated the two groups perfectly; the ratio
cannot. This is a caution against the common practice of thresholding on inlier *ratio*.
**But the separation claim was circular from the start** — see §9, E-001.4.

### 6.11 Fit RMSE — the decisive measurement

Among the 17 wrong cases:

| Case | Inliers | **Fit RMSE** | **True error** |
|---|---|---|---|
| B_azimuth Δaz = 45 | 4 | **5.684e-14 px** | 325.59 px |
| B_azimuth Δaz = 90 | 3 | **2.456e-13 px** | 1000.18 px |
| B_azimuth Δaz = 180 | 4 | **2.132e-13 px** | 769.70 px |
| D_scene repetitive Δaz = 60 | 3 | **0.000e+00 px** | 818.10 px |
| D_scene mixed Δaz = 60 | 4 | **9.095e-13 px** | 2422.56 px |
| F_low_sun el = 10° | 6 | **9.355e-14 px** | 848.24 px |
| F_low_sun el = 20° | 4 | **1.974e-13 px** | 355.49 px |
| F_low_sun el = 35° | 3 | **1.659e-13 px** | 192.84 px |
| G_rootsift True / Δaz = 45 | 4 | **5.684e-14 px** | 325.59 px |
| G_rootsift True / Δaz = 90 | 3 | **2.456e-13 px** | 1000.18 px |

`[MEASURED]` **10 of the 17 wrong cases reported a fit RMSE strictly below 1e-12 px while
being 192.84 – 2422.56 px wrong** — verified by direct recount of `results_preEXP002.csv`.

> **Correction to the contemporaneous figure, recorded rather than silently adopted.**
> `experiments/EXP-001/README.md` and the earlier stage documents state **"11 of 17"**.
> A direct recount of `results_preEXP002.csv` with the predicate
> `reported_fit_rmse < 1e-12` yields **10**. The eleventh is most plausibly
> `D_scene mare/d_az=60`, whose `reported_fit_rmse` is **`nan`** (0 inliers) and which is
> therefore not "below 1e-12" but *undefined*. The count on the post-fix `results.csv` is
> **9**. **The finding is unaffected**; the arithmetic is corrected here. See §17.

### 6.12 Runtime

| Stage | Median (45 cases) |
|---|---|
| SIFT detect + describe (both images) | 0.115 s |
| Descriptor matching | 0.085 s |
| LO-RANSAC | 0.184 s |
| **Total pipeline** | **0.387 s** |

`[MEASURED]` Median 0.387 s against a ≤ 60 s/pair budget — **with one outlier**: the
`A_model/truth=projective` case took **59.057 s**, of which **58.856 s was RANSAC**. A
~150× outlier. See §9, E-001.2.

---

## 7. What worked

| Claim | Evidence | Scope |
|---|---|---|
| The classical baseline is genuinely strong under fixed illumination | 0.009–0.386 px, ≥ 99.7% true precision, all five models | Regime-C terrain, 1 seed |
| Physically-shaded terrain reproduces shadow polarity reversal | gradient correlation −0.853; shading identity 0.989 | Synthetic, Lambertian |
| The non-circular harness works: it detected failures every circular metric missed | §6.11 — 10 cases at fit RMSE < 1e-12 while catastrophically wrong | 45 cases |
| Elevation change is survivable | Δel −30° → 0.750 px, 0.983 precision | Δel ∈ [−30°, +15°] |
| Coverage caught a fragility the error metric called a success | F_low_sun el = 60°: 0.291 px error, 0.392 max gap | **One case only** |
| Ratio test + mutual NN is robust to moderate repetition | ambiguity ≤ 0.9 → 0.006–0.016 px | Synthetic lattice |
| Runtime is comfortable | median 0.387 s vs 60 s budget | 512² images |

---

## 8. What failed

| Failure | Evidence | Expected? |
|---|---|---|
| **Total collapse at Δaz ≥ 45°** | 0% success, 210.99–1000.18 px error | **Yes — this is the gap the project exists to close.** Measured rather than asserted |
| Mare at Δaz = 60° produced 2 putative matches | §6.5 | Partly — mare was expected hard, not *that* hard |
| Low Sun compounds with azimuth change | 3 of 4 cases wrong at Δaz = 45° | Yes |
| The GT generator was wrong by 56.57 px | E-001.1 | **No** |
| One RANSAC case took 59 s | E-001.2 | **No** |
| Fit RMSE was not merely weak but **inverted** | E-001.3 | Direction expected; magnitude not |
| The inlier-count separation claim was circular | E-001.4 | **No — this was a design error** |

**Acceptance criteria, verdict at the time** (criteria from ANALYSIS §L):

| # | Criterion | Target | Measured | Verdict |
|---|---|---|---|---|
| 1 | Algorithmic correctness, synthetic GT at 1× | median < 0.3 px | 0.002–0.386 px; 4 of 5 models < 0.3 | **PARTIAL** |
| 2 | Coverage | max gap ≤ 0.15 D | 0.028–0.096 on successes | **PASS** |
| 3 | Challenge A — small illumination | ≥ 90% success | 100% at Δaz ≤ 30° | **PASS** |
| 4 | Challenge B — large illumination | ≥ 90% success | **0% at Δaz ≥ 45°** | **FAIL — expected** |
| 5 | Challenge D — large scale | ≥ 90% success | 100% to 4× | **PASS in tested range** |
| 6 | Challenge F — cross-sensor | ≥ 90% success | — | **NOT TESTED** — no real modality difference exists in synthetic data |
| 7 | Failure detection | ≥ 95% recall, ≤ 20% FA | 100% / 0% via inlier count ≥ 8 | **PARTIAL — circular** (E-001.4) |
| 8 | Efficiency | ≤ 60 s/pair | median 0.387 s; **max 59.057 s** | **PARTIAL — met with a defect** |
| 9 | Sub-pixel accuracy on real cross-modal pairs | median held-out < 1.0 px | — | **NOT TESTED** — no real data |
| 10 | Loop-closure coherence | < 2 px | — | **NOT TESTED** — estimator not built until EXP-002 |

---

## 9. Errors and bugs discovered

Each block: **Problem → Evidence → Root Cause → Fix → Verification → Lesson**, with a
failure class.

---

### E-001.1 — Ground-truth generator wrong by 56.57 px while every self-reported metric looked excellent

**Class:** implementation bug **in the evaluation harness** · **Severity: CRITICAL**
**Cross-reference:** `ERROR_LEDGER.md` E-005 · RL-013

- **Problem.** `make_pair` rendered the reference into a canvas padded by 40 px on each
  side, cropped the padding off, and did **not** compose that offset into the returned
  ground-truth transform.
- **Evidence.** RANSAC reported a **99.6% inlier ratio with 0.72 px fit RMSE** while the
  recovered transform disagreed with the declared ground truth by **56.57 px = 40·√2**.
  `pad = 40` is verified at `synthetic_terrain.py:611`; 40·√2 = 56.5685.
- **Root cause.** Cropping shifts the origin. The transform chain was not updated to
  reflect it. The error was in how the *experiment composed* correct EXP-000 primitives —
  not in the primitives.
- **Fix.** `translation(pad, pad)` composed into `big_to_ref`
  (`synthetic_terrain.py:639`), with a comment at lines 630–638 marking the term
  load-bearing and stating the failure it prevents.
- **Verification.** `test_ground_truth_is_exact_regression` in
  `tests/test_synthetic_terrain.py` — verified present — whose failure message names the
  56.6 px signature explicitly.
- **Lesson.** **A uniformly shifted match set is perfectly self-consistent.** No
  self-consistency check could have found this; only comparison against ground truth did.
  **Evaluation code needs the same scepticism as pipeline code** — this was the
  coherent-wrong-solution hazard occurring *inside our own harness*, before it was ever
  pointed at lunar data.

| | before fix | after fix |
|---|---|---|
| GT transform error | **56.57 px** (= 40·√2) | exact (regression-tested) |
| Reported inlier ratio | 0.996 | — |
| Reported fit RMSE | 0.72 px | — |

`[INTERPRETATION]` The reported metrics were not merely uninformative here — they were
**maximally reassuring at the moment of a 56 px error**. That is the same inversion as
E-001.3, occurring in a different part of the system.

---

### E-001.2 — LO-RANSAC performance outlier, diagnosed **incorrectly** and deferred

**Class:** implementation bug (deferred) **+ an incorrect diagnosis** · **Severity: MEDIUM at the time**
**Cross-reference:** `ERROR_LEDGER.md` E-006, E-007

- **Problem.** The `A_model/truth=projective` case took **59.057 s** against a 0.387 s
  median — a ~150× outlier, of which **58.856 s** was inside RANSAC
  (`results_preEXP002.csv`).
- **Evidence.** Per-stage timing recorded per case in the results CSV. Without stage-level
  timing this would have read only as "RANSAC is slow", which is not a diagnosis.
- **Root cause — as diagnosed at the time, and it was wrong.** EXP-001's README attributed
  the cost to LO refitting the entire ~2100-point consensus up to 4 times per iteration
  over 100 iterations ("~840 000-point least-squares solves"). **This diagnosis was
  incomplete.** EXP-002 profiled the real pre-fix code and found the dominant cost was a
  *separate* numerical defect: `np.linalg.svd(full_matrices=True)` building and discarding
  a 4230 × 4230 `U`, accounting for **51.55 s of 53.9 s**.
- **Fix.** **Deliberately not fixed during EXP-001**, and recorded as debt with its reason:
  correctness was unaffected, but the defect would corrupt every future runtime comparison.
  Both defects were fixed in EXP-002 objective 1.
- **Verification.** In EXP-002: 54.29 s → 0.056 s (~968×), same inlier set. Regression
  tests `test_dlt_uses_the_economy_svd`, `test_large_projective_fit_is_fast`,
  `test_lo_runs_only_on_a_new_best` — all verified present in
  `tests/test_ransac_performance.py`.
- **Lesson.** **A plausible diagnosis is not a diagnosis.** The LO-refit story was
  *consistent* with the symptom and *partly true*, which is precisely why it was accepted
  without profiling. The real cost was 20× larger and lived in an entirely idiomatic line.
  Profile before attributing.

---

### E-001.3 — Fit RMSE is not merely circular; in the failure regime it is **inverted**

**Class:** genuine research negative result about a metric · **Severity: CRITICAL**
**Cross-reference:** `ERROR_LEDGER.md` E-008 · ADR-0003 · RL-010

- **Problem.** `reported_fit_rmse` attains its **best possible value** at the moment of
  total failure.
- **Evidence.** §6.11: 10 of 17 wrong cases reported fit RMSE < 1e-12 px while being
  192.84 – 2422.56 px wrong. One reported **exactly 0.0** while 818.10 px wrong.
- **Root cause.** Algebra, not noise. An affine model has 6 DOF, i.e. a minimal set of 3
  point pairs. At the minimal set the least-squares fit **interpolates exactly** and the
  residual vanishes *by construction*. RANSAC then *selects for mutual consistency*, which
  keeps the residual near zero just above the minimal set.
  *(The mechanism as first stated — "3–4 correspondences interpolate exactly" — was itself
  slightly wrong and was corrected in EXP-002; see `EXP-002_ransac_terrain_gtfree.md` §5,
  E-002.10.)*
- **Fix.** A **methodological rule**, not a code change: every RMSE is labelled `fit` or
  `held-out` and quoted **with its inlier count**, because RMSE is uninterpretable without
  knowing how close `n` is to the model DOF. Headline claims use the **worst applicable
  estimator**.
- **Verification.** `test_fit_rmse_collapses_when_inliers_approach_model_dof`
  (`tests/test_matching_and_ransac.py`) — verified present. Independently confirmed in
  EXP-002 by a **pre-declared negative control**: `fit_rmse` scores **ROC AUC 0.4947** on
  192 unseen cases — chance.
- **Lesson.** **An evaluation quoting inlier RMSE alone would rank these catastrophic
  failures as its best results.** A metric can be worse than uninformative: it can be
  actively anti-correlated with correctness in exactly the regime you need it.

---

### E-001.4 — The inlier-count separation claim was circular by construction

**Class:** experimental / design mistake · **Severity: HIGH**
**Cross-reference:** `ERROR_LEDGER.md` E-009 · RL-011, RL-019

- **Problem.** The claim *"wrong cases have ≤ 7 inliers, correct cases have ≥ 8"* was
  derived **and** evaluated on the same 45 cases, at a value `classify_failure` already used.
- **Evidence.** The split sits exactly on `min_inliers = 8`. §6.10 confirms the observation
  is true on those 45 cases (wrong max 7, correct min 8) — the observation is not in doubt;
  its **status as evidence** is.
- **Root cause.** **No calibration/validation separation existed in EXP-001** (§4). This is
  a design omission, not a coding error. EXP-001's own README flagged both caveats at the
  time, which is why it is classified as a known-and-accepted design weakness rather than
  an oversight.
- **Fix.** The claim was **withdrawn**, not repaired, and replaced in EXP-002 by a
  **validated operating point** measured on 192 unseen cases from disjoint seeds.
- **Verification.** EXP-002 objective 3, `objective3_threshold.json:exp001_claim`:
  validation wrong max = 7, correct **min = 2**, `holds: false`. One *correct* case
  succeeded on **2 inliers**. Separately, the *rule* `n_inliers < 8` validated at
  **recall 1.000, FPR 0.0112**.
- **Lesson.** **Distinguish "the separation observed in this sample" from "the rule
  validated on unseen data".** The first is a property of 45 cases; only the second is
  usable. They are different claims and were conflated.

---

### E-001.5 — Crater generation cost

**Class:** implementation inefficiency · **Severity: LOW**

- **Problem.** Each crater was evaluated over the full array; pair generation took ~14.6 s.
- **Evidence.** **[NOT VERIFIED]** — the ~14.6 s figure appears in narrative documentation
  only. No before/after timing artefact exists in the repository.
- **Root cause.** The crater profile was evaluated over every pixel although it is
  negligible beyond ~1.6 R.
- **Fix.** Restrict evaluation to the crater's bounding box (~1.6 R). The optimisation and
  its explanatory comment are present in `synthetic_terrain.py:_crater`.
- **Verification.** **[NOT VERIFIED]** — no recorded timing. The *fix* is verified by code
  inspection; the *speedup* is not.
- **Lesson.** Record before/after numbers for every optimisation, however obvious. This one
  is now unverifiable and therefore not quotable.

---

### E-001.6 — Test-assertion errors in our own reasoning

**Class:** experimental / design mistake (in the tests, not the code under test) · **Severity: LOW**

- **Problem.** Two test assertions were initially framed to measure the wrong quantity.
- **Evidence.** Documented in the test docstrings themselves:
  (a) `test_azimuth_reversal_anticorrelates_image_gradients` records that raw intensities
  stay correlated at R² ≈ 0.71 under reversal — so an intensity-correlation assertion
  would have passed while the polarity problem was fully present.
  (b) The repetitive-terrain periodicity test samples **row 96, not row 128**: the 64-px
  lattice places crater centres on rows 32/96/160, so row 128 has zero variance.
- **Root cause.** (a) confusing "the images differ" with "the *gradients* differ in sign";
  (b) assuming a lattice period aligns with a convenient round-number row.
- **Fix.** Assertions reframed to measure gradients (a) and to sample a row that actually
  contains structure (b).
- **Verification.** Both tests present and passing in `tests/test_synthetic_terrain.py`.
- **Lesson.** A passing test proves the assertion held, not that the assertion was the
  right one. The precise sequence in which these corrections occurred is **[NOT VERIFIED]**
  — only the corrected final state and its explanatory docstrings survive.

---

## 10. Failure classification

| Class | Entries |
|---|---|
| **Implementation bug** | E-001.1 (harness), E-001.2 (deferred), E-001.5 |
| **Experimental / design mistake** | E-001.4 (no calibration/validation split), E-001.6, and E-001.2's incorrect diagnosis |
| **Incorrect hypothesis** | A1 shadow-reversal magnitude (§11.1) · A2 §B6 overstated (§11.2) · A3 high-confidence-wrong (§11.3) · A5 scale over-generalised (§11.6) |
| **Synthetic-data limitation** | A6 — regime-C terrain, 89.55% above the angle of repose (§11.7). Lambertian not Hapke. No ejecta rays, secondary chains, lava flow fronts or mass wasting. **Not lunar data.** |
| **Genuine research negative result** | E-001.3 (fit RMSE inverted) · A4 RootSIFT ≈ SIFT (§11.4) · the Δaz ≥ 45° cliff itself |

`[INTERPRETATION]` **Four of the six numbered errors are failures of *evidence* rather than
of code.** That ratio is the stage's most transferable finding.

---

## 11. Hypotheses that were disproved

Recorded **as they were believed**, not as they were later corrected.

### 11.1 The shadow-reversal hypothesis was too narrow

- **Original hypothesis (A1).** Classical descriptors fail because a ~**180°** azimuth
  change *reverses* gradient polarity, so descriptors differ by π.
- **Evidence.** EXP-001 group B, exact ground truth, 8 azimuth deltas.
- **Observed.** Failure at **45°**, not 180°. Δaz = 30° still registered at 0.290 px; 45°
  failed at 325.59 px.
- **Why it failed.** Polarity reversal is a **sufficient** condition, not a necessary one.
  Shadow *movement* alone rotates gradient orientations enough to break `[0, 2π)`
  orientation binning; full reversal is not required.
- **Updated conclusion (RL-009).** The mechanism (orientation binning) was right; the
  magnitude was wrong by a factor of four. **The problem is harder than the analysis
  assumed.** *(Further relocated by EXP-002 to 15–30° on realistic terrain.)*

### 11.2 The repetitive-terrain risk was overstated

- **Original hypothesis (A2).** Repetitive crater terrain is a *primary* danger, producing
  self-consistent wrong solutions with high inlier ratios.
- **Evidence.** EXP-001 group E, ambiguity sweep 0.0 → 1.0.
- **Observed.** At ambiguity ≤ 0.9 the baseline was **essentially perfect** (0.006–0.016 px,
  true precision 1.000). The failure required deliberately removing *all* disambiguating
  context — no fractal base, no per-crater jitter.
- **Why it failed.** The ratio test plus mutual-NN check is substantially more robust to
  repetition than assumed; even weak surrounding texture disambiguates.
- **Updated conclusion (RL-012).** The failure is real but needs a genuinely feature-poor,
  near-perfectly periodic scene. Risk R5 probability lowered Med → Low-Med, impact
  unchanged. Recorded verbatim in `synthetic_terrain.py`: the `ambiguity` parameter exists
  *because* the first version of the scene did not fool RootSIFT at all.
- `[INTERPRETATION]` An adversarial scene that has to be built to order is weaker evidence
  than one that arises naturally.

### 11.3 The predicted "high confidence on a wrong answer" did not materialise

- **Original hypothesis (A3).** The dangerous case is a *high* reported inlier ratio on a
  wrong answer.
- **Evidence.** `confidence_gap` across all 17 wrong cases.
- **Observed.** Largest confidence gap **+0.400**. Wrong cases had *low* reported ratios,
  **0.000 – 0.400** (verified from `results_preEXP002.csv`).
- **Why it failed.** On this data the failure mode was **total match collapse**, not
  confident wrongness.
- **Updated conclusion.** The misleading metric was **fit RMSE**, not the inlier ratio; the
  ratio degraded appropriately. Recorded honestly in `experiments/EXP-001/README.md` at the
  time rather than quietly dropped.
- `[INTERPRETATION]` The hypothesis was not *wrong about the world* — EXP-002 constructed
  coherent wrong solutions and confirmed they are undetectable by self-consistency. It was
  wrong about **where they would show up in this experiment**: the image pipeline produces
  collapse, not coherent wrongness, in this regime.

### 11.4 RootSIFT's advantage was assumed from the literature, not measured

- **Original hypothesis (A4).** RootSIFT outperforms plain SIFT, so B1 should use it.
- **Evidence.** EXP-001 group G, §6.8.
- **Observed.** No measurable advantage; marginally worse at Δaz = 0 (0.359 vs 0.223 px).
- **Why it failed.** The literature claim may hold in general; it is **not supported by our
  measurement on our data**. Three comparison points at one seed each is weak evidence
  either way.
- **Updated conclusion (RL-014, ADR-0009).** Retain RootSIFT — it is free and standard —
  but **drop the claim**. Recorded as a negative result rather than quietly kept on the
  strength of a citation. EXP-002 later measured run-to-run variation at **±0.5853 px**,
  which **exceeds** the 0.136 px difference: it is noise (RL-016).

### 11.5 "Coherent wrong solutions will be caught by the inlier ratio"

Covered by 11.3 and E-001.4 — kept as a separate line because it is the belief that made
the circular threshold feel safe at the time.

### 11.6 "Scale is a far smaller problem than illumination" was stated too generally

- **Original hypothesis (A5).** From §6.4 — SIFT's scale-space search handles the scale
  axis; scale is secondary to illumination.
- **Evidence.** EXP-002 objective 2, four terrain regimes, 3 seeds.
- **Observed.** True on textured terrain; **false on realistic mare**, which fails at 2×
  (success 0.333) and 4× (0.000).
- **Why it failed.** Scale was tested on a single, unrealistically texture-rich terrain.
  **Scale tolerance is a property of the descriptor AND the available texture** — 312 vs
  22 119 keypoints/Mpx — not of the descriptor alone.
- **Updated conclusion (RL-018).** Claim narrowed to textured terrain. Realistic mare
  becomes the priority case for EXP-003 (D-019).

### 11.7 The synthetic terrain was assumed realistic enough

- **Original hypothesis (A6).** The terrain, though acknowledged in EXP-001's own
  limitations as "too steep and too high-frequency" (p99 |∂z/∂x| = 4.79, i.e. ~78° slopes),
  was assumed not to affect the qualitative conclusions.
- **Evidence.** EXP-002 objective 2, measured against published LOLA statistics
  (sources.md S7).
- **Observed.** **89.55% of the EXP-001 terrain is steeper than the lunar angle of repose**
  — physically impossible. On realistic terrain the illumination cliff moves *earlier*
  (15–30°) and the scale conclusion inverts.
- **Why it failed.** Partially correct: the **qualitative** findings — the cliff exists,
  azimuth dominates elevation, fit RMSE inverts, count separates better than ratio — did
  survive. Two **quantitative** conclusions did not.
- **Updated conclusion (RL-017, ADR-0012).** Conclusions are drawn **per regime**, from
  realistic regimes only. The old terrain is **retained** as `C_extreme_diagnostic` so
  EXP-001 stays reproducible and the change in conclusions stays visible.

---

## 12. Conclusions that survived

### `[MEASURED]` — proven, within the stated scope

| Conclusion | Scope it is proven within |
|---|---|
| Under fixed illumination the classical baseline reaches 0.009–0.386 px with ≥ 99.7% true precision | Regime-C terrain, 512², 1 seed, all 5 models |
| Illumination failure is a **cliff, not a slope** | Every regime tested in EXP-001 and EXP-002. The **cliff location** is regime-dependent |
| **Azimuth is far more damaging than elevation** | Δel −30° → 0.750 px vs Δaz 45° → 325.59 px, same suite |
| **Fit RMSE is inverted in the failure regime** | 10 of 17 wrong cases below 1e-12 px. Independently confirmed at ROC AUC 0.4947 on 192 unseen cases |
| Coherent wrong solutions pass RANSAC and are wrong by exactly one structure period | 64.008 px = one lattice period, fit RMSE 0.028 px |
| Inlier **count** separates better than inlier **ratio** | Count separated on 45 cases; ratio ranges overlapped. Validated as a *rule* in EXP-002 |
| Physically-shaded terrain is required to reproduce polarity reversal | gradient correlation −0.853 while intensity R² ≈ 0.71 |
| Median pipeline runtime 0.387 s | 512², this CPU |

### `[INTERPRETATION]`

- The Δaz cliff is **structural, not a tuning problem**: SIFT bins gradient orientation
  over `[0, 2π)` and shadow motion changes those orientations. No ratio threshold repairs
  that. *This is a mechanism claim, supported by the descriptor's definition and by the
  measured cliff — not directly measured as a mechanism.*
- Low texture and illumination change **compound rather than add** (mare at Δaz = 60°: 2
  putative matches).
- An illumination-robust representation must prioritise invariance to shadow **direction**
  over shadow **length**.

### `[NOT VERIFIED] / Evidence insufficient`

- **Cross-modal / multi-sensor robustness. Evidence insufficient.** No real modality
  difference exists in synthetic data. Criterion 6 NOT TESTED.
- **Sub-pixel accuracy on real cross-modal pairs. Evidence insufficient.** Criterion 9 NOT TESTED.
- **Loop-closure coherence.** Estimator not built until EXP-002. Criterion 10 NOT TESTED.
- **Scale beyond 4×. Evidence insufficient.** The real ladder reaches 320:1.
- **Run-to-run variance.** Single seed per case; small differences are not resolvable.
  *(Quantified at ±0.5853 px only in EXP-002.)*
- **Crater-generation speedup (E-001.5).** Not verified — no timing artefact.

**Nothing in EXP-001 is evidence about Chandrayaan-2 or LRO NAC imagery.**

---

## 13. Decisions / ADRs affected

| ID | Decision | Effect of EXP-001 |
|---|---|---|
| **ADR-0003** / D-003 | Accuracy from non-circular estimators; RMSE never stands alone | **Upgraded from a structural argument to a measured one, and strengthened**: fit RMSE is not merely circular but **inverted**. Status → `ACCEPTED` |
| **ADR-0009** / D-009 | Retain RootSIFT as B1; **drop** the claim it beats plain SIFT | **Created.** `ACCEPTED` |
| **ADR-0010** / D-010 | Promote EXP-003 (representations) ahead of the remaining classical baseline sweep | **Created.** `ACCEPTED` — because illumination is measurably the dominant axis |
| ADR-0006 / D-006 | `max_uncovered_disc_radius` primary coverage metric | Supporting **anecdote only** (the 8-inlier case). Remains `PROPOSED` |
| D-013 | Defer learned matchers | Recorded |
| D-014 | OpenCV for SIFT/RootSIFT only; `geometry/` stays OpenCV-free | Recorded |
| D-015 | `nfeatures = 0` (uncapped) | Recorded |
| D-016 | Correct-match threshold = RANSAC threshold (both 3.0 px) | Recorded |

### Why learned matchers were deliberately not introduced

Recorded in `experiments/EXP-001/README.md` and ADR-0010:

1. A component ships only against a **measured deficiency**. EXP-001 established *where*
   classical methods break, not yet whether a better **representation** fixes it with
   classical machinery.
2. The failure is **structural in the descriptor's `[0, 2π)` orientation binning** — which
   a different representation may address without a learned model.
3. **ADR-0002** — CPU-only delivery; learned engines must first be measured for CPU latency
   (EXP-005, still open).
4. **ADR-0008** — licence audit gates every pretrained weight; unresolved.
5. **The harness needed to be trustworthy first.** EXP-001 found a 56.57 px bug in its own
   ground-truth generator. Introducing a learned matcher before that would have attributed
   harness bugs to the model.

---

## 14. Tests and reproducibility status

| Item | Status |
|---|---|
| Suite **at the time** | `132 passed, 2 skipped, 26 s` (`experiments/EXP-001/README.md`) — **[NOT VERIFIED]** today, the suite has since grown |
| Suite **now** | **168 passed, 2 skipped in 23.02 s** — verified by running `python -m pytest tests/` |
| Tests attributable to EXP-001 modules | `test_synthetic_terrain.py` **23** · `test_matching_and_ransac.py` **20** · `test_evaluation.py` **21** — verified by `--collect-only` |
| Regression tests pinning EXP-001 hazards | `test_ground_truth_is_exact_regression` · `test_fit_rmse_collapses_when_inliers_approach_model_dof` · `test_azimuth_reversal_anticorrelates_image_gradients` — all verified present |
| Seed | `20260824`, hard-coded. **One seed per case** |
| Bit-identical re-run? | **No.** The EXP-002 re-run changed individual numbers. **Stated tolerance: ±0.5853 px** on true transform error for correct cases; max inlier-count delta 102; **0 of 45 success/failure flips** — all three verified by direct comparison of `results.csv` against `results_preEXP002.csv` |
| Superseded results preserved at | **`experiments/EXP-001/results_preEXP002.csv`** (D-018 — never overwrite) |
| Figures | **Regenerated by EXP-002; originals not preserved.** A reproducibility gap |

---

## 15. Files / modules created or changed

| Path | Status | Purpose |
|---|---|---|
| `src/siim/data/synthetic_terrain.py` | created | Height field, physical shading, cast shadows, GT pairs. Contains the E-001.1 fix at line 639 |
| `src/siim/data/__init__.py` | created | Public surface |
| `src/siim/matching/rootsift.py` | created | SIFT + RootSIFT, ratio test, mutual NN |
| `src/siim/matching/__init__.py` | created | — |
| `src/siim/verification/ransac.py` | created | LO-RANSAC, all five models. Carried two defects into EXP-002 |
| `src/siim/verification/__init__.py` | created | — |
| `src/siim/evaluation/metrics.py` | created | Circular vs non-circular metrics, `classify_failure` |
| `src/siim/evaluation/coverage.py` | created | `max_uncovered_disc_radius` and secondaries |
| `src/siim/evaluation/__init__.py` | created | — |
| `src/siim/baselines/rootsift_pipeline.py` | created | B1 end-to-end |
| `src/siim/baselines/__init__.py` | created | — |
| `scripts/run_exp001.py` | created | 45-case runner |
| `tests/test_synthetic_terrain.py` | created | 23 tests |
| `tests/test_matching_and_ransac.py` | created | 20 tests |
| `tests/test_evaluation.py` | created | 21 tests |
| `experiments/EXP-001/README.md`, `metrics.json`, `results.csv`, `results_preEXP002.csv`, `figures/*.png` | created | Artefacts. `metrics.json`, `results.csv`, figures later **regenerated** by EXP-002 |
| `pyproject.toml` | changed | `dev` extra added at EXP-001 when the feature-detection backend was chosen |
| `src/siim/geometry/*` | **unchanged** | Remained OpenCV-free |

`[NOT VERIFIED]` Precise per-file creation order — no git history.

---

## 16. Limitations and threats to validity

Stated at the time in `experiments/EXP-001/README.md`, and extended here with what EXP-002
later established.

1. **The synthetic terrain is too steep and too high-frequency.** p99 |∂z/∂x| = 4.79
   (~78° slopes); 2000+ SIFT keypoints per 512² frame. **EXP-002 quantified this: 89.55% of
   the surface exceeds the angle of repose.** Consequence: the fixed-illumination results
   are **optimistic** and the cliff location (30→45°) is specific to this terrain.
2. **Lambertian, not Hapke.** Real regolith backscatters strongly and shows an opposition
   surge. The *geometry* of illumination is right; the radiometry is approximate.
3. **This is not lunar data.** It is a controlled simulation with exact ground truth. It
   measures *algorithm behaviour under known conditions* and is evidence about the method,
   never about Chandrayaan-2 imagery.
4. **Single seed per case.** No run-to-run variance characterised, so differences like
   RootSIFT-vs-SIFT at Δaz = 0 are not resolvable. *(EXP-002: ±0.5853 px.)*
5. **Scale tested only to 4×.** The real ladder goes to 320:1.
6. **`classify_failure` thresholds are asserted, not calibrated.**
7. **No calibration/validation split** — the design flaw behind E-001.4.
8. **Terrain omits ejecta rays, secondary crater chains, lava flow fronts, mass wasting.**
   Stated in the `synthetic_terrain.py` docstring.
9. **Coverage's value rests on one case.** The el = 60° anecdote supports ADR-0006; it does
   not establish it.
10. **Original figures not preserved.**

---

## 17. Lessons learned

1. **Evaluation code needs the same scepticism as pipeline code.** A harness bug is more
   dangerous than a pipeline bug because it corrupts every conclusion at once — and it
   tends to *flatter*. E-001.1 reported 99.6% inliers while 56.57 px wrong.
2. **A uniformly wrong answer is perfectly self-consistent.** No self-consistency metric
   can detect it. This single fact links E-001.1, E-001.3, the lattice result, and
   everything EXP-002 objective 4 went on to measure.
3. **A metric can be worse than useless — it can be inverted.** Fit RMSE achieves its best
   value at total failure.
4. **A separation observed in a sample is not a validated rule.** They are different claims
   and must be written differently.
5. **A plausible diagnosis is not a diagnosis** (E-001.2). Profile first.
6. **Do not repeat a published claim you have not verified on your own data** (A4). Record
   the null as a negative result rather than keeping the claim quietly.
7. **State the mechanism you expect *before* measuring, so that being wrong is informative.**
   The shadow-reversal hypothesis was wrong by 4× — and that is a *result*, only because it
   had been written down first.
8. **Recount your own headline numbers.** The "11 of 17" figure is off by one (§6.11). The
   finding is unaffected, but an uncorrected arithmetic slip in a headline claim is exactly
   the kind of thing an external reviewer finds first.
9. **Record before/after for every optimisation** (E-001.5), or it becomes unquotable.

---

## 18. What must NOT be repeated

| Prohibition | Earned by |
|---|---|
| **Never derive a threshold and report its performance on the same data.** Calibration and validation seeds must be disjoint *and build different terrain*. | E-001.4 |
| **Never quote a fit residual as evidence of correctness** — alone, or as the headline. Always with its inlier count and its `fit`/`held-out` label. | E-001.3 |
| **Never trust the ground-truth generator without an independent exactness regression test.** | E-001.1 |
| **Never accept a plausible performance diagnosis without profiling.** | E-001.2 |
| **Never draw a quantitative conclusion from a single terrain** and state it without the regime it was measured on. | A6 / §11.7 |
| **Never carry a published claim into the design as a fact.** Measure it or drop it. | A4 / §11.4 |
| **Never run a single seed per case and then compare small differences.** | §11.4, ±0.5853 px |
| **Never overwrite superseded results.** `results_preEXP002.csv` is what makes the 0/45-flip comparison demonstrable. | D-018 |
| **Never delete original figures on regeneration.** Already violated once; do not repeat. | §14 |
| **Never state a risk as primary without measuring it** (§B6 was overstated) — and never dismiss one because a to-order adversarial case was needed to trigger it. | §11.2 |

---

## 19. What the next stage should do

From `experiments/EXP-001/README.md` §"What EXP-002 should test next", ordered by what the
evidence made most valuable:

1. **Fix the LO-RANSAC scaling defect first.** It corrupts every runtime comparison that
   follows. → became EXP-002 objective 1.
2. **Fix terrain realism** (slope distribution, feature density). Everything downstream is
   measured on it and it is optimistic. → objective 2.
3. **Validate the failure threshold non-circularly.** → objective 3.
4. **Build the GT-free estimators** (ADR-0003's outstanding item). → objective 4.
5. **Resolve the cliff edge between 30° and 45°** (sample 33/36/39/42°). → **deferred to
   EXP-003**, because EXP-002 relocated the cliff to 15–30° and made the old bracket obsolete.

Also listed and **not** done in EXP-002: the remaining classical baselines (AKAZE, ORB,
ECC/phase-correlation, RIFT2/phase-congruency). ADR-0010 deliberately promoted EXP-003
ahead of them.

**Explicitly not next:** any learned matcher (§13).

---

## 20. Open questions / unresolved risks

| # | Question | Why unresolved | What would resolve it |
|---|---|---|---|
| Q1 | Where exactly is the cliff edge? | Bracketed 30–45°, never resolved; then relocated by EXP-002 to 15–30° | EXP-003: sample 18/21/24/27° on A-regimes, ≥ 3 seeds |
| Q2 | Does a polarity-agnostic representation move the cliff? | Not built | EXP-003 — this is its whole content. ADR-0004 remains `PROPOSED` |
| Q3 | Does the cliff exist on real lunar imagery, and where? | No real data | Access to Chandrayaan-2 / LRO NAC pairs |
| Q4 | Is `max_uncovered_disc_radius` the right coverage metric? | One supporting anecdote | EXP-007 — correlate against local held-out error |
| Q5 | What is run-to-run variance? | Single seed per case | Answered in EXP-002: **±0.5853 px** |
| Q6 | How do classical alternatives (RIFT2, phase congruency, AKAZE, ORB) compare? | Deferred by ADR-0010 | The classical baseline sweep, after EXP-003 |
| Q7 | Does scale survive beyond 4×, up to 320:1? | Tested to 4× only | EXP-004 |
| Q8 | Is the ~14.6 s crater-generation cost claim real? | No timing artefact | Re-measure, or drop the claim |

---

## 21. Artefacts

| File | Contents |
|---|---|
| `experiments/EXP-001/README.md` | Stage-contemporary report |
| `experiments/EXP-001/results_preEXP002.csv` | **Results as measured at the time — preserved.** 45 rows, 33 columns. The authority for every EXP-001 claim |
| `experiments/EXP-001/results.csv` | Re-run after the EXP-002 RANSAC fix. 45 rows |
| `experiments/EXP-001/metrics.json` | Config, environment, failure counts — **regenerated by EXP-002** |
| `experiments/EXP-001/figures/illumination_curve.png`, `illumination_examples.png`, `scale_curve.png` | **Regenerated; originals not preserved** |

**Cross-stage records:** `ERROR_LEDGER.md` (E-005…E-009, E-016, E-018) ·
`DECISION_LEDGER.md` (D-003, D-009, D-010, D-013–D-016) · `STAGE-INDEX.md` ·
`../STAGE_HISTORY.md`.
