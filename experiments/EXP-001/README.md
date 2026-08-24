# EXP-001 — RootSIFT classical baseline against synthetic ground truth

**Objective.** Establish a trustworthy classical baseline (B1) *and* a non-circular evaluation harness, before any learned matcher is considered (ANALYSIS §I, spec §20/§66).

**Status:** complete. 45 cases, exact ground truth throughout.

---

## Commands executed

```bash
python -m pip install opencv-contrib-python     # 5.0.0.93, SIFT only
python scripts/run_exp001.py                    # 45 cases, 332 s
python -m pytest tests/ -q                      # 132 passed, 2 skipped, 26 s
```

## Configuration

| | |
|---|---|
| Seed | `20260824` |
| Image size | 512×512, from a 1024×1024 height field |
| Detector | SIFT (OpenCV 5.0.0), contrast 0.04, edge 10, σ 1.6, **uncapped** |
| Descriptor | RootSIFT (L1-normalise → sqrt) |
| Matching | Lowe ratio 0.8 + mutual nearest neighbour |
| Robust fit | LO-RANSAC, affine, τ = 3.0 px, confidence 0.999 |
| "Correct match" | ‖T_gt(p) − q‖ ≤ 3.0 px (same yardstick as τ, so the comparison is like-for-like) |
| Illumination | Lambertian shading of a real height field + cast shadows |

Synthetic pairs are built by rendering **the same height field twice** — once in the source frame, once in the reference frame — each under its own Sun geometry. Geometry is exactly known while the appearance difference is physically produced. A 180° azimuth change genuinely swaps which crater wall is lit; verified analytically in `test_azimuth_reversal_inverts_the_shading_gradient` (correlation with the predicted shading identity = 0.989).

---

## Results

### A — Transform model recovery (illumination fixed)

| Truth model | Fitted | Inliers | True precision | True transform error (median) |
|---|---|---|---|---|
| translation | affine | 2454 | 1.000 | **0.009 px** |
| euclidean | affine | 1863 | 1.000 | **0.033 px** |
| similarity | affine | 1443 | 0.997 | 0.386 px |
| affine | affine | 1997 | 0.999 | 0.248 px |
| projective | projective | 2112 | 1.000 | **0.019 px** |

Under fixed illumination the baseline is genuinely strong: all five models recovered at or below 0.4 px with ≥99.7% true precision. **The classical pipeline is not the weak link when illumination is constant.**

### B — Illumination: the headline result

| Δ azimuth | Putative | Inliers | Reported ratio | **True precision** | **True transform error** |
|---|---|---|---|---|---|
| 0° | 2027 | 2023 | 0.998 | 0.999 | 0.359 px |
| 15° | 1571 | 1562 | 0.994 | 0.999 | 0.208 px |
| 30° | 179 | 147 | 0.821 | 0.980 | 0.290 px |
| **45°** | **28** | **4** | 0.143 | **0.000** | **325.59 px** |
| 60° | 22 | 4 | 0.182 | 0.000 | 210.99 px |
| 90° | 17 | 3 | 0.176 | 0.000 | 1000.18 px |
| 135° | 29 | 4 | 0.138 | 0.000 | 332.62 px |
| 180° | 28 | 4 | 0.143 | 0.000 | 769.70 px |

**RootSIFT falls off a cliff between Δazimuth 30° and 45°.** Putative matches collapse 179 → 28 and the registration goes from 0.29 px to catastrophically wrong. There is no graceful degradation: it works, then it does not.

Two things about this are more interesting than the failure itself:

1. **The cliff is at 45°, not 180°.** ANALYSIS §B2 predicted failure from shadow *polarity reversal*, which is a 180° phenomenon. The measured failure arrives at a quarter of that. Shadow *movement* is sufficient; reversal is not required. The problem is meaningfully harder than the analysis assumed.
2. **Elevation is not the same kind of problem.** A −30° elevation change still succeeded (60 inliers, 0.750 px), and −15°/+15° were comfortable (0.325 / 0.489 px). **Azimuth is the killer; elevation is survivable.** That has a direct design consequence — an illumination-robust representation must prioritise invariance to shadow *direction* over invariance to shadow *length*.

### C — Scale

| Scale ratio | Inliers | True precision | True transform error |
|---|---|---|---|
| 1.0 | 2762 | 1.000 | 0.002 px |
| 1.25 | 1390 | 1.000 | 0.270 px |
| 1.5 | 955 | 1.000 | 0.178 px |
| 2.0 | 559 | 1.000 | 0.341 px |
| 3.0 | 205 | 0.995 | 1.277 px |
| 4.0 | 129 | 1.000 | 1.108 px |

SIFT's scale-space search does its job: no failure through 4×, though error crosses 1 px around 3×. **Scale is a far smaller problem than illumination for classical features** — the opposite of the intuitive ordering, and it re-prioritises the work. Note this covers only the OHRC↔NAC (2:1) regime of the real ladder; 20:1 and 320:1 (ANALYSIS §C.3) are untested here and need the dedicated normalisation stage.

### D — Scene type

| Scene | Same Sun | Δaz = 60° |
|---|---|---|
| highlands | 2023 inl, 0.359 px | 4 inl, **211 px** ✗ |
| mare | 1101 inl, 0.020 px | **2 putative, 0 inliers** ✗✗ |
| repetitive | 352 inl, 0.118 px | 3 inl, **818 px** ✗ |
| mixed | 1430 inl, 0.021 px | 4 inl, **2423 px** ✗ |

Every scene type works under fixed illumination and every one fails at Δaz = 60°. **Mare is the worst case**: only 2 putative matches survived — low texture and illumination change compound rather than merely add.

### E — Repetitive terrain and the coherent wrong solution

| Ambiguity | Putative | Inliers | Reported ratio | True precision | True transform error |
|---|---|---|---|---|---|
| 0.0 | 570 | 567 | 0.995 | 1.000 | 0.009 px |
| 0.4 | 250 | 248 | 0.992 | 1.000 | 0.009 px |
| 0.7 | 104 | 100 | 0.962 | 1.000 | 0.016 px |
| 0.9 | 122 | 112 | 0.918 | 1.000 | 0.006 px |
| **1.0** | 40 | 7 | 0.175 | **0.000** | **64.008 px** |

At full ambiguity the estimate is wrong by **exactly 64.00 px — one lattice period.** RANSAC locked onto a match set shifted by one crater spacing, precisely the ANALYSIS §B6 failure.

**But the honest qualification matters:** this required deliberately removing all disambiguating context (no fractal base, no per-crater jitter). At ambiguity ≤ 0.9 — a lattice with even weak surrounding texture — RootSIFT was *perfect* (0.006–0.016 px). The ratio test plus mutual-NN check is more robust to repetition than §B6 assumed. **The §B6 danger is real but needs a genuinely feature-poor, near-perfectly periodic scene.** I should not have stated it as strongly as I did without this measurement.

### F — Low Sun (with Δaz = 45° held)

| Elevation | Inliers | True precision | True transform error |
|---|---|---|---|
| 10° | 6 | 0.000 | 848 px ✗ |
| 20° | 4 | 0.000 | 355 px ✗ |
| 35° | 3 | 0.333 | 193 px ✗ |
| 60° | 8 | 1.000 | 0.291 px (flagged **poor coverage**) |

Low Sun compounds with azimuth change. Even the one success at 60° had only 8 inliers with a `max_uncovered_disc` of 0.392 — correct, but on the strength of a handful of clustered points. Exactly the situation spec §29 warns about, and the coverage metric caught it while the error metric did not.

### G — RootSIFT vs plain SIFT (a negative result)

| Δaz | RootSIFT inliers / error | Plain SIFT inliers / error |
|---|---|---|
| 0° | 2023 / **0.359 px** | 2024 / **0.223 px** |
| 45° | 4 / 325.59 px ✗ | 5 / 318.25 px ✗ |
| 90° | 3 / 1000.18 px ✗ | 4 / 410.33 px ✗ |

**RootSIFT showed no measurable advantage over plain SIFT here, and was marginally worse at Δaz = 0.** The literature justification for RootSIFT is real, but it is not supported by *our* measurement on *this* data. Reported as a negative result rather than quietly retained on the strength of a citation (spec §69).

Caveat: three comparison points is weak evidence, and the differences at Δaz = 0 (0.359 vs 0.223 px) are within the range of run-to-run variation we have not yet characterised.

---

## The two findings that matter most

### 1. Fit RMSE is anti-correlated with correctness in the degenerate regime

Among the 17 cases where the pipeline was wrong (true transform error > 3 px):

| Case | Inliers | **Fit RMSE** | **True error** |
|---|---|---|---|
| B_azimuth Δaz=45 | 4 | **5.68e-14 px** | 325.59 px |
| B_azimuth Δaz=90 | 3 | **2.46e-13 px** | 1000.18 px |
| B_azimuth Δaz=180 | 4 | **2.13e-13 px** | 769.70 px |
| D_scene mixed Δaz=60 | 4 | **9.10e-13 px** | 2422.56 px |
| F_low_sun el=10° | 6 | **9.36e-14 px** | 848.24 px |

**11 of 17 failed cases reported a fit RMSE below 1e-12 px while being 190–2400 px wrong.**

The mechanism is not noise, it is algebra: an affine model has 6 DOF, so with 3–4 correspondences the least-squares fit **interpolates them exactly** and the residual vanishes by construction. Fit RMSE therefore approaches zero precisely when the fit is most degenerate.

This is the empirical core of ANALYSIS §A.3 and spec §28. RMSE is not merely a weak indicator here — in the failure regime it is *actively inverted*, reporting its best possible value at the moment of total failure. Any evaluation quoting inlier RMSE alone would rank these catastrophic failures as its best results. Codified as `test_fit_rmse_collapses_when_inliers_approach_model_dof`.

### 2. Inlier *count* separated success from failure; inlier *ratio* did not

Across all 45 cases:

| | Wrong cases (n=17) | Correct cases (n=28) |
|---|---|---|
| **Inlier count** | max = **7** | min = **8** |
| Reported inlier ratio | max = **0.400** | min = **0.296** |

Absolute inlier count separated the two groups perfectly; the ratio ranges **overlap** and cannot. This is a useful, concrete failure-detection signal for EXP-010 — and a caution against the common practice of thresholding on inlier ratio.

Two honest qualifications: 45 cases is a small sample, and the perfect split sits exactly at the `min_inliers = 8` threshold already used by `classify_failure`, so the separation should be re-derived on independent data rather than treated as a validated operating point.

Notably, the §B6 nightmare — *high* reported confidence on a wrong answer — did **not** materialise. The largest confidence gap observed was +0.400. On this data, a pipeline checking inlier count would have caught every failure.

---

## Coverage

On successful cases coverage was excellent and well within the ANALYSIS §L target of `max_uncovered_disc ≤ 0.15 D`:

| Case | Inliers | max gap | occupancy | entropy |
|---|---|---|---|---|
| scale=1.0 | 2762 | 0.028 | 1.000 | 0.997 |
| highlands/same_sun | 2023 | 0.047 | 1.000 | 0.990 |
| mare/same_sun | 1101 | 0.054 | 1.000 | 0.987 |
| repetitive/same_sun | 352 | 0.096 | 0.953 | 0.965 |
| **F_low_sun el=60°** | **8** | **0.392** ✗ | 0.125 | 0.500 |

The last row is the useful one: the registration was *correct* (0.291 px) yet coverage flagged it, because 8 clustered points cannot constrain the transform away from where they sit. Coverage caught a fragility that accuracy metrics reported as a success — which is the argument for ADR-0006, though not yet the proof (that needs EXP-007's correlation against local error).

## Runtime (CPU-only, Ryzen 5 7520U)

| Stage | Median |
|---|---|
| SIFT detect + describe (both images) | 0.115 s |
| Descriptor matching | 0.085 s |
| LO-RANSAC | 0.184 s |
| **Total pipeline** | **0.387 s** |

Comfortably inside the ≤60 s/pair budget at 512² — **with one defect**.

**Known defect (not fixed, see below):** the projective case took **59.06 s**, of which 58.86 s was RANSAC — a 150× outlier. Cause: LO-RANSAC refits on the entire consensus set up to 4 times per iteration, and with ~2100 inliers over 100 minimum iterations that is ~840 000-point least-squares solves. Correctness is unaffected, but it breaks the runtime budget and would corrupt every future runtime comparison. Fix for EXP-002: cap the LO consensus sample (standard LO-RANSAC practice) and lower `min_iterations` once consensus is already high.

---

## Limitations

These bound what EXP-001 can be claimed to show. Spec §13 and §72 require them stated, not buried.

1. **The synthetic terrain is too steep and too high-frequency.** Measured p99 |∂z/∂x| = 4.79, i.e. ~78° slopes; real lunar slopes at metre baselines are mostly under ~25°. It also yields 2000+ SIFT keypoints on a 512² frame, far denser than real mare. **Consequence: the same-illumination results are optimistic**, and the absolute cliff location (30°→45°) is specific to this terrain. The *qualitative* findings — the cliff exists, azimuth ≫ elevation, RMSE inverts, count separates — do not depend on it. Fix in EXP-002: retune `relief`/`pixel_scale` to a realistic slope distribution.
2. **Lambertian, not Hapke.** Real regolith backscatters strongly and shows an opposition surge. The geometry of illumination is right; the radiometry is approximate.
3. **This is not lunar data.** It is a controlled simulation with exact ground truth. It measures *algorithm behaviour under known conditions* and is evidence about the method, never about Chandrayaan-2 imagery.
4. **Single seed per case.** No run-to-run variance is characterised, so small differences (e.g. RootSIFT vs SIFT at Δaz = 0) are not resolvable.
5. **Scale tested only to 4×.** The real ladder goes to 320:1.
6. **`classify_failure` thresholds are asserted, not calibrated.** EXP-010's job.

---

## Against the acceptance criteria (ANALYSIS §L)

| Criterion | Target | Measured | Verdict |
|---|---|---|---|
| Algorithmic correctness, synthetic GT at 1× | median < 0.3 px | 0.002–0.386 px (4 of 5 models < 0.3) | **mostly met** — similarity/affine truths at 0.386/0.248 px |
| Coverage | max gap ≤ 0.15 D | 0.028–0.096 on successes | **met** (except the 8-inlier case, correctly flagged) |
| Robustness, Challenge A (small illumination) | ≥ 90% success | 100% at Δaz ≤ 30° | **met** |
| Robustness, Challenge B (large illumination) | ≥ 90% success | **0% at Δaz ≥ 45°** | **failed — as expected for B1** |
| Robustness, Challenge D (large scale) | ≥ 90% success | 100% to 4× | **met in tested range** |
| Failure detection | ≥95% recall, ≤20% FA | 100% / 0% via inlier count ≥ 8 | **met, but n=45 and threshold co-selected** |
| Efficiency | ≤ 60 s/pair | median 0.387 s; **max 59.06 s** | **met with a defect** |

Challenge B failing is the expected and desired outcome: it is the gap the rest of the project exists to close, now measured rather than asserted.

---

## Decision: should RootSIFT remain in the candidate pipeline?

**Yes, as baseline B1 — and no, not as a candidate for the final matcher.**

- **Keep as B1.** It is strong where it works (0.009–0.386 px, ≥99.7% precision), fast (0.387 s), fully explainable, needs no training and no GPU. It is the honest reference the §E.2 delta is measured against, and spec §66 wants a strong baseline precisely so its failure boundary is informative. It now has one, at Δaz ≈ 45°.
- **Do not promote it.** The Δaz ≥ 45° cliff is structural, not a tuning problem: SIFT bins gradient orientation over [0, 2π), and shadow motion changes those orientations. No threshold repairs that.
- **Drop the RootSIFT-vs-SIFT distinction as a claim.** Retain RootSIFT (it is free and standard) but stop citing it as an advantage until measured otherwise. ADR-0009.

---

## What EXP-002 should test next

Ordered by what the EXP-001 evidence makes most valuable:

1. **Fix the LO-RANSAC scaling defect first.** It corrupts every runtime comparison that follows. Small, well-understood fix.
2. **Fix the terrain realism** (slope distribution, feature density). Everything downstream is measured on it, and it is currently optimistic.
3. **Illumination-robust representations — promoted to the top priority.** EXP-001 makes this the dominant axis: illumination breaks the baseline at 45° while scale survives to 4×. This is EXP-003's content, and it should be pulled forward ahead of the rest of the classical baseline sweep. Concretely, compare raw / CLAHE / gradient-magnitude / **orientation-mod-π** / phase congruency / CFOG on the *same* pairs, and re-measure where the cliff moves. The specific prediction to test: a polarity-agnostic representation should push the cliff well past 45°, because ∇-orientation-mod-π is invariant to the sign flip that the shading identity in `test_azimuth_reversal_inverts_the_shading_gradient` demonstrates.
4. **The remaining classical baselines** (AKAZE, ORB, ECC/phase-correlation, and especially **RIFT2/phase-congruency**, the multimodal-remote-sensing method most teams omit). RIFT2 is the direct competitor to our representation hypothesis and must be measured, not assumed.
5. **Azimuth resolution between 30° and 45°.** The cliff is bracketed but not located; sample at 33/36/39/42° to find its edge, which becomes the number we quote for "where classical methods stop".

Explicitly **not** next: any learned matcher. EXP-001 established the harness; EXP-002/003 must establish what classical methods can do with a better *representation* before the added complexity of a learned engine is justified (spec §36, §75).
