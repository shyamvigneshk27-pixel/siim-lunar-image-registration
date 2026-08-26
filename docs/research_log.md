# Research Log (spec §99)

Format per entry: **Observation → Hypothesis → Experiment → Result → Interpretation → Decision.**
Purpose: prevent circular experimentation. An entry with no Result is an open thread, not a finding.

---

## 2026-08-24 — Session 1: specification intake, environment survey, prior-art scan

### RL-001 — Development machine is CPU-only

**Observation.** Measured directly: AMD Ryzen 5 7520U (4 cores / 8 threads), 15.2 GB RAM, `torch 2.10.0+cpu`, `torch.cuda.is_available() == False`, integrated AMD Radeon (no CUDA), 118 GB free on D:. `nvidia-smi` absent.

**Interpretation.** Training a dense matcher locally is out. Inference with heavy dense matchers (RoMa class) is probably out but **not yet measured** — the published 5 s/pair figure is a GPU figure, and the CPU multiplier is unknown.

**Decision.** Architecture must place its engineering weight on CPU-cheap stages (normalisation, geometry, verification, coverage, sub-pixel, confidence). Learned engines remain admissible as inference-only components, ranked by measured CPU latency. **EXP-005 will measure this rather than assume it.** No engine is excluded on speculation.

**Status:** closed (observation); feeds open experiment EXP-005.

---

### RL-002 — Real sensor scale ratios far exceed the spec's illustrative ladder

**Observation.** From verified GSDs (S1, S2): OHRC 0.25 m, NAC 0.5 m, TMC-2 5 m, IIRS 80 m. Pairwise ratios: OHRC↔NAC 2:1, TMC-2↔NAC 10:1, TMC-2↔IIRS 16:1, OHRC↔TMC-2 20:1, IIRS↔NAC 160:1, OHRC↔IIRS **320:1**.

Spec §14 offers 1×, 1.5×, 2×, 4×, 8× as an illustrative ladder — and explicitly says not to hardcode it if the data suggests otherwise. It does.

**Interpretation.** Off-the-shelf matchers are reliable to roughly 2–4× scale difference. Four of six pairs exceed that; two exceed it by two orders of magnitude. This is a property of the mission hardware, not of any dataset, so it is certain independent of what the SIH dataset turns out to contain.

**Decision.** Scale normalisation is promoted from preprocessing convenience to a **required first-class pipeline stage** (ANALYSIS §D.3 stage [3]). The evaluation scale ladder is replaced with the real ratios (F.3). EXP-004 sweeps it.

**Status:** closed; drives EXP-004.

---

### RL-003 — Shadow polarity reversal is a descriptor-level failure, not a contrast problem

**Observation.** SIFT, ORB and AKAZE build descriptors from gradient orientation over [0, 2π). Under a ~180° Sun-azimuth change, illuminated and shadowed crater walls swap and the gradient across a rim reverses — corresponding gradients differ by π.

**Interpretation.** This is a *structural* incompatibility derived from the descriptor definition, not an empirical degradation that better parameters could fix. Histogram-equalising or CLAHE-ing the input cannot repair it, because the information destroyed is the sign, and normalisation preserves sign.

Independent empirical support: SIFT and AKAZE "perform well near the equator but degrade under polar lighting" on Chandrayaan-2 data (S3) — polar imaging is exactly the low-Sun, long-shadow, azimuth-variable regime where this predicts failure.

**Hypothesis (H-003).** A polarity-agnostic representation — gradient orientation modulo π, or phase congruency, which is invariant to both contrast and edge polarity — will show markedly smaller degradation than raw intensity or CLAHE as Δazimuth increases toward 180°.

**Experiment.** EXP-003: fix the matcher, vary only the representation {raw, CLAHE, gradient magnitude, orientation-mod-π, phase congruency, CFOG}, sweep controlled relighting including azimuth reversal. Measure inlier ratio and held-out residual vs Δazimuth.

**Status:** **OPEN** — hypothesis stated, experiment defined, not yet run. Do not cite as a finding.

---

### RL-004 — Protocol appears to dominate matcher choice in cross-modal remote sensing

**Observation.** A benchmark of 24 pretrained matcher configurations on SAR-optical satellite registration (S4) reports that **protocol choices change mean error by up to 33× for a single matcher, exceeding the difference between top-tier and mid-tier matchers**. Affine vs homography alone moved mean error 12.3 → 9.7 px. Their recommended protocol reaches <8 px mean error with no domain-specific training.

**Interpretation.** If this transfers, then effort spent selecting or finetuning a matcher is dominated by effort spent on the geometric protocol wrapped around it. That inverts the intuition most teams will follow, and — conveniently but not coincidentally — the protocol stages are all CPU-cheap, which fits RL-001.

**Hypothesis (H-004).** On lunar cross-modal pairs, varying protocol (tile size, overlap, transform model, RANSAC threshold, normalisation) with the matcher fixed produces a larger spread in held-out residual than varying the matcher with the protocol fixed.

**Experiment.** EXP-006: full factorial (or Latin-hypercube if the grid is too large) over protocol parameters × 3 matchers. The comparison of the two spreads is the test.

**Risk of over-reliance.** This is SAR-optical evidence, not lunar. Lunar differs in ways that could matter: no atmosphere, no vegetation/seasonal change, but far more extreme illumination geometry and much larger scale ratios. Transfer is plausible, **not established**. The project's headline thesis (ANALYSIS §D.4) currently rests on this hypothesis, so EXP-006 is on the critical path and must be run early and honestly — including reporting a refutation if that is what comes out.

**Status:** **OPEN** — critical path.

---

### RL-005 — The evidence gap: reported RMSE in this problem class is circular

**Observation.** No ground-truth correspondences are supplied by the problem statement. Standard practice — and the practice in the prior lunar work (S3) — is to report RMSE as the reprojection residual of RANSAC inliers under the fitted model.

**Interpretation.** That quantity measures how well the model fits points that were *selected for fitting the model*. It decreases monotonically as the RANSAC threshold tightens, while inlier count and coverage fall. It is therefore not an accuracy measurement and is trivially gameable. Worse, it is blind to the failure mode in ANALYSIS §B6: a match set shifted by one crater spacing is internally consistent and yields an excellent RMSE while being entirely wrong.

**Hypothesis (H-005).** Four estimators recover non-circular accuracy evidence without ground truth: (1) synthetic known-transform GT; (2) K-fold **cross-validated** residual, fit on 70% of inliers, evaluated on the held-out 30%; (3) forward/backward cycle consistency; (4) **loop closure** over overlapping triplets, where `T_AB ∘ T_BC ∘ T_CA` should be the identity.

Estimator (4) is the one that can catch the coherent-wrong-solution failure, because a consistent shift does not generally cancel around a loop.

**Experiment.** Build all four into the evaluation harness from EXP-000 onward, before any accuracy is reported. Validate (2) and (4) against (1) on synthetic data where truth is known — i.e. confirm the GT-free estimators actually track true error before trusting them on real pairs.

**Status:** **OPEN.** This is the project's main methodological bet. Note it is cheap in compute and expensive in nothing but care, which is why it is worth doing well.

---

### RL-006 — IIRS is not one modality

**Observation.** IIRS spans 800–5000 nm in ~256 bands (S1). Lunar radiance beyond roughly 3 µm carries a substantial thermal-emission component.

**Interpretation `[HYPOTHESIS]`.** Reflectance-dominated short bands (~0.8–1.5 µm) should retain albedo/shading structure comparable in kind to visible panchromatic imagery. Long bands approach a temperature map, whose spatial structure is driven by thermal inertia and illumination history rather than by the topographic shading a NAC image records. Appearance-based matching of long IIRS bands to visible imagery may be close to ill-posed.

**Decision (provisional).** Treat IIRS band selection as an explicit, configurable pipeline stage; default to reflectance-dominated bands for matching. **Test the wavelength dependence rather than assuming the 3 µm cut** — measure matching performance as a function of band index and let the data place the boundary.

**Status:** **OPEN.** Blocked on IIRS data access (S-unresolved).

---

### RL-007 — Relief displacement is first-order, not negligible

**Observation.** Relief displacement `Δr ≈ h·r/H`. For OHRC (H = 100 km, swath 3 km so r ≤ 1.5 km, GSD 0.25 m), a 500 m crater rim gives Δr ≈ 7.5 m ≈ **30 px**.

**Interpretation.** A single global homography cannot absorb a 30 px topography-correlated displacement while we target sub-pixel accuracy. The residual field will therefore contain *structure* correlated with terrain, not just noise.

**Consequence — and an opportunity.** Because the error is structured rather than random, plotting the residual vector field is diagnostic: spatially correlated residuals indicate relief (or a wrong model), whereas random residuals indicate matching noise. This gives a cheap, visual, defensible answer to judge question §84.19 ("what if the transformation is not a homography?"), and it feeds model selection in EXP-009.

**Status:** closed (derivation); drives EXP-009 and the residual-field diagnostic in the visualisation module.

---

### RL-008 — Geometry gate passed; the naive resampling update is wrong by up to a full pixel

**Observation.** EXP-000 run and recorded (`experiments/EXP-000/`). All five transform models recover from exact correspondences at ~1e-13 px true endpoint error against a 0.1 px gate. Hartley normalisation holds the homography condition number at ~3.4 across coordinate extents 512 → 60,000 px. 68 tests pass.

The measurement that matters most was not the gate itself. Comparing the two candidate resampling coordinate updates against *actual image resampling* of a Gaussian feature at a known sub-pixel position:

| Resample scale | Contract C4 `p' = s(p+0.5) − 0.5` | Naive `p' = s·p` |
|---|---|---|
| 0.25 | 0.0000 px | 0.3750 px |
| 0.5 | 0.0000 px | 0.2500 px |
| 2.0 | 0.0000 px | 0.5000 px |
| 3.0 | 0.0000 px | **1.0000 px** |

**Interpretation.** The naive update — the obvious implementation, and the one most codebases write — is wrong by exactly `(s−1)/2` px. Our accuracy target is sub-pixel, and scale normalisation across the real sensor ladder (RL-002) requires factors up to 320×. This error would therefore have exceeded the entire error budget before any matching happened, while every intermediate image still looked perfectly correct. It is a clean instance of the R8 failure mode: silent, plausible, and fatal to the numbers.

**Secondary observations.**
- Estimation costs 1–2.5 ms/fit — negligible. Runtime will be spent on matching and warping, not geometry. This supports concentrating effort on the protocol layers (H-004) without a compute penalty.
- A cubic warp of 256² takes 19.5 ms, extrapolating to roughly 5 s at 4096². First real datapoint against the ≤60 s/pair budget.
- NaN-fill for invalid warp regions is now enforced by test. Lunar shadow is genuinely near-zero, so a `0.0` fill would be indistinguishable from real terrain — a lunar-specific hazard a generic vision codebase would not consider.

**Decision.** ADR-0007 → `ACCEPTED`. Real-data experiments unblocked. Next is EXP-001 (RootSIFT against synthetic GT), which validates the *matching* harness the way this validated the geometry harness — and which needs a feature-detection dependency, the next open choice.

**Status:** closed.

---

## 2026-08-24 — Session 2: EXP-001, classical baseline and GT harness

### RL-009 — The illumination cliff is at Δazimuth ≈ 45°, not 180°

**Observation.** EXP-001 group B, exact ground truth. RootSIFT + ratio + mutual-NN + LO-RANSAC on physically re-illuminated terrain:

| Δaz | 0° | 15° | 30° | **45°** | 90° | 180° |
|---|---|---|---|---|---|---|
| inliers | 2023 | 1562 | 147 | **4** | 3 | 4 |
| true transform error | 0.36 px | 0.21 px | 0.29 px | **325 px** | 1000 px | 770 px |

Elevation, by contrast, is survivable: Δel = −30° still gave 60 inliers at 0.750 px.

**Interpretation.** H-003 predicted failure from shadow *polarity reversal*, a 180° phenomenon. The measured failure arrives at a quarter of that, so shadow *movement* alone is sufficient — reversal is not required. The failure is also a cliff, not a slope: 30° works at 0.29 px, 45° is catastrophic. **The problem is harder than ANALYSIS §B2 assumed, and I stated §B2 more narrowly than the evidence now supports.**

The azimuth/elevation asymmetry is the actionable part: an illumination-robust representation must prioritise invariance to shadow *direction* over shadow *length*.

**Decision.** EXP-003 (representations) is promoted ahead of the remaining classical baseline sweep — illumination is now demonstrably the dominant axis, while scale survived to 4× untouched. Cliff location to be resolved at 33/36/39/42°.

**Status:** closed; supersedes the framing in H-003, which remains open as to the *remedy*.

---

### RL-010 — Fit RMSE is anti-correlated with correctness in the degenerate regime

**Observation.** Of 17 EXP-001 cases that were wrong (true error > 3 px), **11 reported fit RMSE below 1e-12 px**:

| Case | Inliers | Fit RMSE | True error |
|---|---|---|---|
| Δaz=45 | 4 | 5.68e-14 px | 325.59 px |
| Δaz=90 | 3 | 2.46e-13 px | 1000.18 px |
| mixed/Δaz=60 | 4 | 9.10e-13 px | 2422.56 px |

**Interpretation.** Algebra, not noise. An affine model has 6 DOF; with 3–4 correspondences the least-squares fit *interpolates them exactly*, so the residual vanishes by construction. Fit RMSE therefore attains its best possible value precisely when the fit is most degenerate.

This is stronger than the ANALYSIS §A.3 claim. RMSE is not merely circular and gameable — in the failure regime it is **inverted**. An evaluation quoting inlier RMSE alone would rank these catastrophic failures as its best results.

**Decision.** ADR-0003 confirmed and strengthened. Reporting rule extended: any RMSE must be quoted alongside its inlier count, since RMSE is uninterpretable without knowing how close `n` is to the model DOF. Codified as `test_fit_rmse_collapses_when_inliers_approach_model_dof`.

**Status:** closed.

---

### RL-011 — Inlier count separates success from failure; inlier ratio does not

**Observation.** Across all 45 EXP-001 cases:

| | Wrong (n=17) | Correct (n=28) |
|---|---|---|
| inlier **count** | max 7 | min 8 |
| reported inlier **ratio** | max 0.400 | min 0.296 |

**Interpretation.** Absolute count separated the groups perfectly; the ratio ranges overlap and cannot. Also notable: the §B6 nightmare of *high* confidence on a wrong answer did not materialise — the largest confidence gap was +0.400. On this data a pipeline checking inlier count would have caught every failure.

**Qualifications, which matter.** n = 45; and the perfect split sits exactly at the `min_inliers = 8` threshold `classify_failure` already used, so it must be re-derived on independent data before being treated as an operating point.

**Status:** open — feeds EXP-010 (confidence calibration).

---

### RL-012 — The coherent-wrong-solution failure is real but needs near-perfect repetition

**Observation.** Repetitive crater lattice, shifted by exactly one 64-px period, with an `ambiguity` parameter controlling how much disambiguating context is removed:

| ambiguity | 0.0 | 0.4 | 0.7 | 0.9 | **1.0** |
|---|---|---|---|---|---|
| true transform error | 0.009 px | 0.009 px | 0.016 px | 0.006 px | **64.008 px** |

At full ambiguity the error is **exactly one lattice period** — the §B6 failure, reproduced.

**Interpretation.** But it required deliberately removing *all* context: no fractal base, no per-crater jitter. With even weak surrounding texture (ambiguity ≤ 0.9) RootSIFT was perfect. **The ratio test plus mutual-NN check is substantially more robust to repetition than ANALYSIS §B6 asserted.** I overstated that risk; the honest version is that it needs a genuinely feature-poor, near-perfectly periodic scene.

**Decision.** Keep loop closure (F.1.4) in the plan — it is cheap and it is the only estimator that catches this class — but downgrade §B6 from "the dangerous failure" to "a real failure in feature-poor periodic terrain". Risk R5 probability lowered from Med to Low-Med; impact unchanged.

**Status:** closed.

---

### RL-013 — Harness bug caught only by ground truth (the pad offset)

**Observation.** The first `make_pair` rendered the reference into a canvas padded by 40 px and cropped the padding off *without* composing that offset into the returned ground-truth transform. The declared GT was wrong by 40·√2 = 56.57 px. RANSAC reported **99.6% inlier ratio and 0.72 px fit RMSE**.

**Interpretation.** Every self-reported metric was excellent. Nothing but ground truth could have caught it, because a uniformly shifted match set is perfectly self-consistent. This is ANALYSIS §A.3/§F.1 demonstrated on our own harness, before it was ever pointed at lunar data — and a reminder that the evaluation code needs the same scepticism as the pipeline code.

**Decision.** Regression test `test_ground_truth_is_exact_regression` recovers the transform with the real pipeline and asserts agreement with declared GT below 1 px, naming the 56.6 px signature in its failure message.

**Status:** closed.

---

### RL-014 — RootSIFT showed no measurable advantage over plain SIFT (negative result)

**Observation.** EXP-001 group G, matched conditions:

| Δaz | RootSIFT | plain SIFT |
|---|---|---|
| 0° | 2023 inl / 0.359 px | 2024 inl / **0.223 px** |
| 45° | 4 inl / 326 px ✗ | 5 inl / 318 px ✗ |
| 90° | 3 inl / 1000 px ✗ | 4 inl / 410 px ✗ |

**Interpretation.** No advantage, marginally worse at Δaz = 0. The published justification is real but is **not supported by our measurement on our data**. Three comparison points with one seed each is weak evidence and the Δaz=0 difference may be run-to-run noise we have not characterised.

**Decision.** Retain RootSIFT (free, standard, harmless) but stop citing it as an advantage. ADR-0009. Recorded as a negative result rather than dropped, per spec §69 — a claim we cannot reproduce is not a claim we should make.

**Status:** closed.

---

## 2026-08-24 — Session 3: EXP-002

### RL-015 — The 59 s RANSAC case was two defects, and the dominant one was a discarded SVD

**Observation.** Profiling the pre-fix code: **51.55 s of 53.9 s inside `numpy.linalg.svd`**, 298 `estimate` calls. Two independent causes:

1. `estimate_projective` used `np.linalg.svd(a)` with default `full_matrices=True`. The DLT design matrix is (2N × 9), so the full SVD also builds **U at 4230 × 4230 = 17.9M elements** and discards it; only the last row of `Vt` is used. Measured **498.86 ms → 1.01 ms (493×)**, singular values and `Vt` identical.
2. Local optimisation ran on every sufficient sample rather than only on a new best (Chum et al. 2003).

**Result.** 54.29 s → **0.056 s**, ~970×, same 2115 inliers, true error 0.0119 px. Robustness unchanged: inlier recall 1.000 at 0–80% outliers.

**Interpretation.** Neither fix trades accuracy for speed — the first is mathematically identical, the second restores the published algorithm. Worth noting for its own sake: a 3-orders-of-magnitude cost sat inside a line that looked entirely idiomatic. Stage-level timing is what made it findable, and is now recorded on every run (spec §37).

**Decision.** Both fixed; `lo_max_points` caps the LO refit sample while **scoring always sees every correspondence**, so the robustness criterion is untouched. Pinned by 12 tests using shape and refit-count invariants where possible rather than wall-clock alone.

**Status:** closed.

---

### RL-016 — Run-to-run variation is ±0.59 px, which retires one EXP-001 comparison

**Observation.** Re-running EXP-001 after the RANSAC fix: **0 of 45 cases flipped** between correct and wrong. But on cases correct in both runs, the true transform error moved by up to **0.585 px** (e.g. scale=3.0: 1.277 → 0.692 px), and inlier counts by up to 102.

**Interpretation.** Changing when LO fires changes RANSAC's search trajectory, so results are reproducible in *conclusion* but not bit-identical. The tolerance must be stated whenever EXP-001 numbers are quoted.

This retires a specific earlier claim. EXP-001 compared RootSIFT with plain SIFT at Δaz = 0 (0.359 vs 0.223 px, a 0.136 px difference) and flagged it as possibly noise. **0.136 px is well inside ±0.59 px, so it is noise.** RL-014's conclusion — no measurable difference — is confirmed, and its wording "marginally worse" should be dropped.

**Decision.** Any future claim of a sub-pixel difference between methods requires multiple seeds and a variance estimate, not a single paired run.

**Status:** closed.

---

### RL-017 — The EXP-001 terrain is physically impossible; realistic terrain fails EARLIER

**Observation.** Terrain realism is now controlled explicitly by rescaling heights to a target median slope, anchored to LOLA statistics at a 15 m baseline (sources.md S7).

| regime | median | p99 | > repose | kp/Mpx |
|---|---|---|---|---|
| A_mare_moderate | 3.50° | 9.32° | 0.00% | 312 |
| A_highlands_moderate | 9.10° | 22.64° | 0.00% | 22 119 |
| B_highlands_challenging | 18.00° | 40.05° | 6.36% | 32 582 |
| C_extreme (EXP-001) | 58.53° | 76.76° | **89.55%** | 31 246 |

The A-regimes reproduce the published LOLA medians exactly. The EXP-001 terrain has **89.55% of its surface steeper than the angle of repose**.

Re-running the EXP-001 axes across regimes (108 cases, 3 seeds):

| regime | last Δazimuth with 100% success |
|---|---|
| A_mare_moderate | **15°** |
| A_highlands_moderate | **15°** |
| B_highlands_challenging | 30° |
| C_extreme (EXP-001) | 30° |

**Interpretation.** On realistic terrain the illumination cliff arrives **earlier**, at 15–30° rather than the 30–45° EXP-001 reported. The implausibly steep terrain produced abnormally strong shading gradients that flattered the descriptor. **RootSIFT is worse on real-looking terrain than EXP-001 concluded.**

**Decision.** RL-009's cliff location is superseded: **15–30°**, not 30–45°. All future conclusions are reported per regime and drawn from A-regimes; C is retained as a diagnostic only. EXP-003's success criterion is restated against A-regimes.

**Status:** closed; supersedes the numeric claim in RL-009 (the qualitative finding — a sharp cliff, azimuth dominant — stands).

---

### RL-018 — "Scale survives to 4×" was terrain-dependent and stated too generally

**Observation.** Success rate by scale ratio:

| regime | 1.0× | 2.0× | 4.0× |
|---|---|---|---|
| A_mare_moderate | 1.00 | **0.33** | **0.00** |
| A_highlands_moderate | 1.00 | 1.00 | 1.00 |
| B / C | 1.00 | 1.00 | 1.00 |

**Interpretation.** EXP-001's conclusion holds only for textured terrain. Realistic low-texture mare — 312 keypoints/Mpx against highlands' 22 119 — already fails at 2×. Scale tolerance is not a property of the descriptor alone; it is a property of the descriptor *and the available texture*.

**Decision.** EXP-001's "scale is a far smaller problem than illumination" is narrowed: true on textured terrain, false on mare. Mare becomes the priority case for EXP-003, since it fails earliest on both axes.

**Status:** closed.

---

### RL-019 — The inlier-count threshold: claim refuted, operating point validated

**Observation.** 192 calibration + 192 validation cases from disjoint seeds and different terrain. EXP-001's claim was "wrong cases ≤ 7 inliers, correct ≥ 8".

| | validation |
|---|---|
| wrong, max inliers | 7 |
| correct, **min** inliers | **2** |
| claim holds | **FALSE** |

One correct case (mare, Δaz 20°) succeeded on 2 inliers — with `coverage_max_gap = 0.520`, a fluke that coverage independently flagged.

But thresholding at `n_inliers < 8` gives **recall 1.000, FPR 0.011** on validation.

Signal comparison (validation ROC AUC): `n_inliers` 0.993 · `coverage_max_gap` 0.983 · `inlier_ratio` 0.982 · **`fit_rmse` 0.495**.

**Interpretation.** Two distinct statements were conflated in EXP-001. "8 separates the classes" is **false**. "Flag failure when inliers < 8" is a **validated operating point**. The distinction matters because the first invites treating 8 as a law and the second is an empirical threshold with a measured false-alarm rate.

`fit_rmse` at ROC AUC 0.495 is indistinguishable from chance. It was included as a deliberate negative control and behaved exactly as RL-010 predicted — independent support for ADR-0003.

**Status:** closed; feeds EXP-010.

---

### RL-020 — Only loop closure detects a coherent wrong answer; the other GT-free estimators are blind

**Observation, part 1 (an artefact I nearly reported as a result).** In objective 3, `split_consistency` was non-finite in **104/192** validation cases, 103 of them wrong; among the 88 finite cases, **zero** were wrong. `held_out_median` was non-finite in 100/192. Their 0.97–0.99 AUC is therefore **a proxy for low inlier count**, not independent information. The pipeline's real failures here are illumination collapse to 3–7 inliers, which counting already catches — so objective 3 never tested these estimators at all.

**Observation, part 2.** Constructed adversarial cases with **300 correspondences each**, so counting cannot help:

| case | true error | held-out | flagged | split | flagged |
|---|---|---|---|---|---|
| correct_noisy | 0.00 | 1.42 | 0.00 | 0.54 | 0.00 |
| lattice_shift | **64.00** | **0.47** | **0.00** | 0.17 | 0.00 |
| coherent_affine | **52.71** | **0.48** | **0.00** | 0.16 | 0.00 |
| partial_overlap | **21.14** | **0.47** | **0.00** | 0.52 | 0.00 |
| low_inlier_degenerate | 275.65 | ∞ | 1.00 | ∞ | 1.00 |

Detection rate **0.200** for both — only the degenerate case.

**Observation, part 3.** Loop closure vs cycle consistency:

| estimator | detection | false alarm |
|---|---|---|
| `cycle_error` | 1.000 | **1.000** |
| **`loop_error`** | **1.000** | **0.000** |

A one-period error on each edge accumulates to **190.08 px ≈ 3 × 64** around the loop.

**Interpretation.** A match set 64 px wrong produces a held-out residual of 0.47 px — *lower* than a correct-but-noisy set at 1.42 px. Held-out residual and spatial split consistency measure **self-consistency**, and a uniformly wrong set is perfectly self-consistent. They are not safety nets against wrong-but-consistent answers, and describing them as such would be exactly the false confidence this project exists to avoid.

**Loop closure works, and is the only one that does.** ANALYSIS §F.1.4's specific reasoning is vindicated.

Two caveats stated plainly. Cycle consistency's 1.000 false-alarm rate comes from a construction that deliberately targets its structural blind spot (forward and backward exact inverses); in a real pipeline the reverse pass is independent and would not cancel exactly. The honest claim is "cannot detect symmetric errors", not "useless". And parts A/B are **constructed**, not pipeline-produced — they demonstrate the mathematics, not the frequency of such cases on real lunar imagery.

**Decision.** ADR-0011. Loop closure is promoted to the primary GT-free correctness check; held-out residual and split consistency are retained for **degeneracy detection only**, with their blind spots pinned by tests.

**Status:** closed for the mathematics; **open** for real-data frequency.

---

### RL-021 — Correction: exact interpolation occurs at the minimal set, not at "3–4 points"

**Observation.** RL-010 stated that "with 3–4 correspondences the least-squares fit interpolates them exactly". Testing this directly: affine (6 DOF, minimal set **3** pairs) on 3 random pairs gives fit RMSE < 1e-9; on **4** random pairs it gives **27.85 px**.

**Interpretation.** The mechanism is exact only at `n = minimal set`. RL-010's empirical observation still holds — 11 of 17 EXP-001 failures reported fit RMSE below 1e-12 px at 3–4 inliers — because RANSAC *selects* mutually consistent points, so a 4th inlier is by construction near-consistent with the 3-point fit. The conclusion is unchanged; the stated mechanism was imprecise.

**Decision.** Wording corrected in ADR-0003 and pinned by `test_exact_interpolation_only_at_the_minimal_set`.

**Status:** closed.

---

### RL-022 — The `n_inliers` sensitivity table was never computed; and the documented rule form is the wrong one

**Observation.** `run_exp002_threshold.py:202` selects the signal for its sensitivity analysis by `max(deployable, key=validation roc_auc)`. On the recorded run that maximum was `split_consistency` (0.9944) over `n_inliers` (0.9935) — a margin of **0.0009**. EXP-002 §3.5 had already established that `split_consistency`'s AUC is an artefact of an `inf` sentinel (E-010) and overrode the pick (D-022), but the **sensitivity table was never re-computed to match the override**. Every block in `objective3_threshold.json:sensitivity` records `threshold_score_space: 1e12` — the sentinel. The stage documentation presents it under the heading "Sensitivity of `n_inliers`". It is not that. (Contradiction D2.)

Recomputed for `n_inliers` from the preserved 384 cases: `experiments/EXP-002/objective3_ninliers_sensitivity.json`.

**Two findings, one expected and one not.**

*Expected.* The rule holds across every non-degenerate subset. Validation recall **1.000** (103/103, Wilson 95% CI 0.964–1.000), FPR **0.0112** (1/89, CI 0.002–0.061), ROC AUC **0.9935**; recall 1.000 in all 4 regimes, all 3 transform models and all 4 validation seeds. Δaz 40° and 60° are degenerate — every case fails — so discrimination is undefined there.

*Not expected.* **The documented rule form `n_inliers < 8` is dominated by `n_inliers <= 8`.** Exactly one case in 384 discriminates between them: a *calibration* failure (A_mare_moderate, seed 1003, Δaz 20°, projective) with **exactly 8 inliers and 367.95 px true error**. The strict form misses it — calibration recall **0.9894**, not 1.000. The non-strict form catches it at an **identical** false-positive rate of 0.0612 (the same 6 false alarms either way). On validation the two forms are indistinguishable, because **no validation case has exactly 8 inliers**: the boundary was never tested by the data the error rate was reported on. Youden's J had in fact selected `<= 8`; the documentation quotes `< 8`.

**Why the mislabelled table nevertheless looked right.** `split_consistency`'s non-finite sentinel fires on **192/192** validation cases in exact agreement with `n_inliers < 8` — it is a near-perfect proxy for a low inlier count. So the recorded table's *confusion matrix* coincided with the correct one; only its *AUC* column was wrong (A_mare 0.9706 recorded vs **0.9877** measured; similarity 0.9844 vs **0.9834**). The table was not grossly wrong numerically — it was measuring the wrong quantity. **That is the more dangerous kind of error, because it does not look wrong.**

**Interpretation, kept separate from the measurement.** Two caveats bound EXP-003's use of this rule. First, **96 of 103 validation failures (93%) come from Δazimuth subsets in which every case fails** — total match collapse, which counting catches trivially. On the subsets where correct and wrong cases coexist the recall estimate rests on **7** failures. EXP-003 aims to operate precisely in that discriminable regime, so the headline recall overstates the evidence available for the use EXP-003 will make of it. Second, all 7 false alarms across both splits are correct-but-fragile registrations (coverage gap 0.392–0.605 against a median of 0.069 for correct cases), and **5 of 7 are in realistic mare** — the regime D-019 makes EXP-003's priority benchmark.

**Decision.** D-023: EXP-003 uses **`n_inliers <= 8`** (equivalently `n_inliers < 9`). This is a change of rule *form*, not of operating point — the validated validation error rate is unchanged — so no EXP-002 conclusion is weakened. ADR-0003's reporting rule is unaffected: `fit_rmse` remains excluded, and ground truth is used only to score the rule, never as an input.

**Status:** D2 closed. **Open:** the rule's behaviour in the discriminable regime rests on 7 failures; EXP-003 will generate more and should re-measure rather than inherit.

---

### RL-023 — EXP-003: every representation hypothesis refuted; the failure is orientation *assignment*, not binning

**Observation.** Six arms, 594 evaluations, 3 regimes × 3 seeds × 11 azimuths, one image pair shared by all arms. Pre-registered criterion S1 — last fully-successful Δazimuth **strictly > 30°** on both realistic A-regimes — was met by **no arm** (`exp003_representations.json:verdict.S1_MET_BY_ANY_ARM = false`).

Last fully-successful Δaz, per regime (mare first, D-019):

| arm | mare | highlands | B-challenging |
|---|---|---|---|
| `B1_rootsift` / `B1_sift` | **21°** | 27° | 27° |
| `A_orient_mod_pi` | **0°** | 21° | 27° |
| `A_orient_2pi_control` | 18° | 27° | **40°** |
| `B_phase_congruency` | void | 27° | 30° |
| `C_rift2_mim` | void | 0° | 27° |

**Mare — the priority case — defeats everything.** Best result is 21°, the baseline's. The two phase-congruency arms fail the Δaz = 0 positive control on mare, so their mare results are **void**, not merely poor: at 384² mare yields only **24 keypoints**.

**H-3.1 refuted, and in the opposite direction.** ADR-0004's polarity-agnostic mod-π descriptor is the *worst* arm. Head-to-head against its own 2π control on **identical keypoints**: mod-π **wins 0, loses 38, ties 61**. At Δaz 0 both yield ~770 putative matches, so this is not a distinctiveness deficit — mod-π degrades specifically under illumination change. **H-3.2 and H-3.3 refuted** likewise.

**The unexpected result, and it came from a control.** `A_orient_2pi_control` — included only to isolate H-3.4 — extends the cliff to **40°** on B and holds 1.00 success to 40° on highlands. Artefact checks both pass: it shares the detector with B1 so keypoint counts are **identical in 99/99 cases**, and median coverage gap is **0.129 vs B1's 0.130**. In the 18 cases where it succeeds and B1 fails at Δaz ≥ 30, true inlier precision is 0.93–1.00 at 0.11–1.82 px — genuinely correct, not lucky RANSAC.

The only remaining difference is that the custom descriptor is **upright**. A direct probe of SIFT's assigned dominant orientation, keypoints paired through ground truth by location:

| Δaz | median \|Δangle\| (highlands / B) | frac > 30° |
|---|---|---|
| 0° | 6.69° / 6.96° | 0.24 |
| 15° | 12.26° / 13.22° | 0.30 |
| 30° | 24.05° / 24.57° | 0.43 |
| 45° | **44.77° / 46.19°** | **0.67** |

**SIFT's orientation assignment drifts almost 1:1 with Sun azimuth.**

**Interpretation, kept separate.** Shadow motion rotates the local gradient field, which rotates the histogram SIFT uses to assign a keypoint reference angle, which rotates the descriptor sampling frame — a *systematic* mismatch no ratio threshold repairs. An upright descriptor has no frame to rotate. This **refines ADR-0004**: at these azimuths the dominant failure is orientation **assignment**, not orientation **binning** — and binning mod-π actively hurts.

**This is post-hoc and must not be promoted.** Not pre-registered, one stage, synthetic terrain, and confounded with the custom descriptor implementation. Uprightness also is not deployable: it survives only because this stage's transforms carry ≤ 8° rotation.

**Decision.** ADR-0004 → `SUPERSEDED` (it invited exactly this). D-024 records the mechanism as a pre-registration target for EXP-004, not as a method.

**Status:** H-3.1/H-3.2/H-3.3/H-3.4 closed (refuted). **Open:** RL-023b, the orientation-assignment mechanism, to be pre-registered and re-tested.

---

### RL-024 — `n_inliers <= 8` recall transfers to EXP-003; its false-alarm rate does not

**Observation.** Requirement 8 asked for the D-023 operating point to be re-measured in EXP-003's own mixed correct/wrong regime. Cells are (representation, regime, Δaz) across seeds; **mixed** means correct and wrong coexist — the only cells where the flag can discriminate.

| subset | n | wrong | recall | FPR |
|---|---|---|---|---|
| all EXP-003 cases | 594 | 259 | 0.9961 | 0.1672 |
| **MIXED cells only** | **135** | **70** | **0.9857** | **0.3692** |
| total-collapse cells | 189 | 189 | 1.0000 | n/a |
| all-correct cells | 270 | 0 | n/a | 0.1185 |

Per regime, mixed cells: mare FPR **0.4706** (recall 1.000) · highlands **0.3077** (1.000) · B **0.3636** (0.9565).

**Interpretation.** EXP-002 validated recall 1.000 / FPR 0.0112 on 192 unseen cases. **Recall transfers (0.986 ≥ 0.95). FPR does not: 0.369, a factor of 33 worse.** This is exactly the risk logged as RL-022b — EXP-002's FPR was earned where 93% of failures were total collapse, which counting catches trivially. In the discriminable regime the flag rejects more than a third of *correct* registrations.

**`n_inliers <= 8` is a sound failure detector and a poor success gate.** H-3.6 is refuted on FPR.

**Decision.** D-025. EXP-004 must re-fit the operating point on its own calibration seeds and validate on disjoint ones, and must not quote 0.0112.

**Status:** open — a new operating point is owed by EXP-004.

---

### RL-025 — Loop closure survives contact with the image pipeline, once the label is right

**Observation.** 108 loop cases (3 regimes × 3 seeds × 6 azimuths × 2 arms), three edges each, estimated independently by the real pipeline rather than from constructed transforms.

**A labelling error was found and fixed first.** Loops were initially labelled by the A→B edge alone, which scored loop closure at **detection 1.000 / false alarm 0.617**. The "false alarms" were loops in which a *different* edge was catastrophically wrong — loop closure was correctly refusing to close a broken loop and being penalised for it. With the loop-level label (wrong iff **any** edge is wrong):

| | detection | false alarm | correct median | wrong median |
|---|---|---|---|---|
| loop closure, loop-level | **1.000** | **0.000** | **0.258 px** | **1368.1 px** |
| loop closure, edge-level (mislabelled) | 1.000 | 0.617 | — | — |

**Interpretation.** ADR-0011 holds on pipeline-produced edges, not only on constructed transforms — a genuine strengthening. The mislabelled variant is retained in the artefact as `detection_edge_level_MISLABELLED`, because a 0.617 swing from a labelling choice is the single most transferable lesson here: **this is contradiction D2 recurring in a new place.** Held-out residual, split consistency and cycle consistency were deliberately not computed (ADR-0011 / E-011).

**Status:** closed for synthetic terrain. **Open:** real overlapping triplets.

---

## 2026-08-25 — Session 3: real LRO NAC ingestion and first real registration

Full stage report: [`stages/REAL-DATA_LRO_NAC.md`](stages/REAL-DATA_LRO_NAC.md). The entries
below record the *findings*; the report holds the method, commands, provenance and hashes.

---

### RL-026 — The archive told us which label was which, and the code did not read it

**Observation.** Four of six acquired PDS4 labels were `Product_Browse` — descriptions of a JPEG browse pyramid — rather than `Product_Observational`. Both halves of the then-best `mare_serenitatis` pair were affected. Decoding was impossible and nothing said why.

**Evidence.** Root elements of the six stored labels: 4 × `Product_Browse` (~2 KB), 2 × `Product_Observational` (~13 KB); grep for image-structure elements gives 0 hits in the former, 7 in the latter. The live ODE record lists both files with an explicit class — `Type=Product` for `DATA/.../M*.xml` and `Type=Browse` for `EXTRAS/BROWSE/...M*_pyr.xml` — and lists `Browse` *after* `Product`. The parser matched on `.xml` extension and assigned unconditionally, so the last one won. Products with 7 files were wrong; products with 5 files were right by accident. See E-022.

**Interpretation.** `[INTERPRETATION]` This was never a URL-pattern problem, and the fix is not a URL transformation. **The correct URL was in the response the whole time, correctly labelled, and was discarded.** The generalisable form: when a service classifies its own data, inferring the class from a filename throws away better information and fails silently, because both files are valid PDS4 XML served from the same host.

**Unresolved.** Two orphan `Product_Browse` labels (`nac.m1299958135lc`, `nac.m1323460176lc`) from the 2026-08-24 acquisition remain on disk, belong to no manifest, and have not been re-fetched. They block nothing.

**Status:** closed (E-022 FIXED, 5 regression tests).

---

### RL-027 — The decode is provably correct; the proof needed two corrections of its own

**Observation.** A PDS4 `Array_2D_Image` decoder was built and its correctness demonstrated intrinsically — without any reference image — via spatial-coherence comparisons against deliberately wrong decodes.

**Evidence.** `[MEASURED]` The label's `file_size` is declared independently of the array description, giving an exact structural identity: `5064 + 52224 × 5064 × 2 = 528 929 736` ✓ for all four products, which validates offset, both dimensions and element size *together*. Lag-1 autocorrelation, declared vs byte-swapped decode: **0.9590 / 0.5933**, **0.9415 / 0.6680**, **0.9759 / 0.6123**. Positive controls on real imagery: self-registration recovers identity to **1.14e-12** and **1.25e-12**; a known (+40, +25) px shift is recovered as **(40.142, 24.941)** — 0.14 px — with 11 521 inliers.

**Two corrections were required before those numbers meant anything.** `[MEASURED]` The coherence statistic first reported **0.9919 for two different frames**, identical to four decimals, with a vertical correlation of exactly 1.0000: it was measuring the constant `-32768` border columns, whose variance (~3664 DN) dwarfs the scene's (~19.6 DN) — **E-010 recurring**, logged as E-023. Then a **0.0022** margin between two ~0.35 values was reported as proof of a byte-order defect in correct code, logged as E-024 and fixed with an explicit 0.10 evidence margin and an `inconclusive` verdict.

**Interpretation.** `[INTERPRETATION]` The decode chain, preprocessing, detector, matcher, RANSAC and geometry are **sound on real lunar imagery**. This is what bounds the interpretation of RL-029: the registration failure there is not an ingestion or pipeline defect.

**Unresolved.** The 0.14 px shift-recovery figure is a **self-consistency control on a synthetically shifted copy of one real tile**, not a registration of two independent frames. It supports no accuracy claim. `MIN_PLAUSIBLE_AUTOCORR = 0.60` and `DECODE_EVIDENCE_MARGIN = 0.10` are provisional constants fitted to four tiles (D-032).

**Status:** closed for the decoder (61 tests). **Open:** the constants, pending more real products.

---

### RL-028 — Maximising illumination difference selects the terminator, where one frame carries no signal

**Observation.** The pair selector ranks candidates by incidence difference alone. Its top `mare_serenitatis` pick was 89.96° vs 24.64° — a Sun 0.04° above the horizon.

**Evidence.** `[MEASURED]` `nac.m1322281266lc`: DN median **29 ± 19.6** (I/F ≈ 0.00088), lag-1 autocorrelation **0.3553**, versus 1582 ± 133.6 and 0.9759 for its partner — a **55× brightness difference**. Keypoints 2 515 vs 9 706; the pair produced **5 putative matches**. The tile decodes perfectly (`file_size` identity exact, SHA-256 reproducible) and fails the sanity check on *data quality*. A survey bounding both incidences at ≤ 75° returned **32 usable pairs**, the best being `nac.m1271742202lc` × `nac.m1335207975rc` — Δinc 39.8°, footprint IoU **0.516**, resolution ratio 1.016.

**Interpretation.** `[INTERPRETATION]` A difference-maximising criterion with no bound on either operand necessarily selects the extreme of the range, and the extreme of incidence is the terminator. **"Most illumination difference" and "most *informative* illumination difference" are different objectives.** The selector was optimising the wrong one.

**Unresolved.** The 75° ceiling is a **provisional cut, not a validated threshold** — no sweep was run, and no evidence says 75° is where usability ends. `find_illumination_pairs()` is **not yet changed**; D-029 records the decision only.

**Status:** open — E-026 `DOCUMENTED`, D-029 recorded, implementation owed.

---

### RL-029 — The first real registration failed, and the fit residual said it was perfect

**Observation.** The unmodified B1 baseline was run on two real NAC tile pairs. Both failed.

**Evidence.** `[MEASURED]` `usable` pair (Δinc 39.8°): 12 707 / 11 412 keypoints, 35 putative, **3 inliers**, coverage gap 0.4629, **fit RMSE 1.575e-12 px**, verdict **REJECTED / none**, class **C**. `terminator` pair: 2 515 / 9 706 keypoints, 5 putative, **3 inliers**, fit RMSE 1.313e-13 px, REJECTED, class C. The `usable` transform:

```
 11.35236   -2.45232   -5801.51978
 17.88721   -3.07281   -9344.45726
```

— an 11–18× scale change and a ~10 000 px translation between two frames of the same region at nearly the same resolution.

**The line-direction ambiguity was tested and does not explain it.** `[MEASURED]` All four H1/H2 tile combinations, on tiles verified distinct by SHA-256 first (see E-025): **3, 4, 4, 5** inliers, all failing `n_inliers <= 8`; three of four again show near-zero fit RMSE (1.575e-12, 3.434e-13, 8.135e-13).

**Interpretation.** `[INTERPRETATION]` **This is E-008 reproduced on real lunar data for the first time.** A pipeline reporting inlier RMSE — as most of the registration literature does — would present a 1.6e-12 px result as picometre-accurate registration. It is catastrophically wrong, and the residual is at its *best* precisely because the solution collapsed to the affine minimal set of 3 correspondences. The project's founding claim now has a real-data instance.

**This is not a positive result about the matcher.** `[NOT VERIFIED]` The registration **failed**. What succeeded is the *rejection* of the failure, and the rejection rests on `n_inliers <= 8` and coverage — both applied, neither validated on real data.

**Unresolved — and this is the stage's central open question.** The cause is **not attributed**. Two hypotheses remain live and the data separates neither:
(a) **the tiles do not overlap** — the crop is a first-order latitude approximation with no camera model (D-030), and footprint IoU 0.516 is a whole-frame figure that says nothing about two 3.7 km tiles inside those frames;
(b) **the illumination difference defeats the matcher** — which EXP-003 would predict, except that Δ*azimuth* is unavailable for these products (E-020), so that expectation is not directly applicable either.
**Evidence insufficient.** The failure must not be attributed to illumination until overlap is established independently (D-031).

**Status:** open. Blocked on RL-030.

---

### RL-030 — Loop closure, the project's only trustworthy GT-free check, is absent from every real-data result

**Observation.** No real-data result in this stage carries loop-closure evidence.

**Evidence.** Loop closure requires three overlapping images with **independently estimated** edges (ADR-0011; E-021 records what happens when the closing edge is derived algebraically instead). Only two real products were acquired per pair, so the check was reported as *not run* rather than as a pass — in the registration summaries and in the demo response alike.

**Interpretation.** `[INTERPRETATION]` The project's strongest correctness argument is currently **synthetic-only**. D-011 was accepted on mathematics and validated on constructed transforms and pipeline-produced synthetic edges (RL-025); it has still never met real overlapping triplets, and ADR-0011's own reversal condition — *"real-data evidence that per-edge errors are correlated in a way that cancels around a loop; or that overlapping triplets are unavailable"* — remains untested.

**Unresolved.** Whether overlapping real triplets are even available at the required overlap in this archive region. Unknown since ANALYSIS §F.1.4 and still unknown.

**Status:** open — the highest-value real-data gap.

---

### RL-031 - The tiles behind the first real registration were 22.75 km apart

**Question.** RL-029b: why did the first real registration fail - overlap, or illumination? The data was said to separate neither.

**Evidence.** `[MEASURED]` `experiments/REAL-DATA-02/overlap_verification.json`. Tile ground footprints were computed from the PDS archive index table's **named** frame corners (`UPPER_LEFT_LATITUDE` ... `LOWER_RIGHT_LONGITUDE`), bilinearly interpolated to the integer tile windows already recorded in the REAL-DATA-01 manifests, projected onto a common local plane and intersected exactly. No pixel was read and no matcher component was used.

| tile pair | intersection | IoU | shared fraction of the worse-covered tile | classification |
|---|---|---|---|---|
| `usable_H1` - **the headline 3-inlier run** | **0.0000 km2** | 0.0000 | **0.0 %** (p5-p95 0.0-0.0) | **OVERLAP_INSUFFICIENT** |
| `usable_H2` | 4.9653 km2 | 0.5330 | **68.59 %** (p5-p95 62.9-74.1) | **OVERLAP_CONFIRMED** |
| `terminator_H1` | 2.2375 km2 | 0.1835 | 28.29 % (p5-p95 23.4-33.0) | **OVERLAP_UNKNOWN** |
| `usable_A@H1_B@H2` | 0.0000 km2 | 0.0000 | 0.0 % | OVERLAP_INSUFFICIENT |
| `usable_A@H2_B@H1` | 0.0000 km2 | 0.0000 | 0.0 % | OVERLAP_INSUFFICIENT |

The `usable_H1` tile centres are **22.75 km** apart - nearly six tile-lengths - against a 3.98 km tile.

**Interpretation.** `[INTERPRETATION]` **REAL-DATA-01's headline number measured nothing about the matcher.** 3 inliers from two disjoint tiles is the correct output of a correctly-working pipeline given inputs that share no ground. The E-008 observation drawn from that run *survives and strengthens*: a fit residual of **1.575e-12 px** was reported for a transform between tiles **22.75 km apart**. What does not survive is any reading of the 3 inliers as evidence about real-data matcher performance.

`registration_usableH2.json` is a different matter. Its tiles are independently confirmed to share **68.6 % / 70.5 %** of their ground, and the unmodified B1 baseline returned 43 putative matches and **5 inliers**, REJECTED. Overlap is excluded as the cause for *that* pair. **The failure is still not attributed** - illumination, mare texture poverty (D-026), the 2x decimation, the 1.6 % resolution ratio and real relief displacement are all untested.

**Cause of the disjoint crop.** Two design mistakes in `acquire_real_pair.py`, both now in the ledger. **E-028**: the line-direction hypothesis was applied globally to a pair, and it is a property of the individual frame - `LRO_FLIGHT_DIRECTION` is **-X** for both usable frames (line 0 at minimum latitude, i.e. H2) and **+X** for both terminator frames (H1). The usable pair was acquired at H1. **E-029**: cross-track position was never matched between frames, costing a further 1.1-1.7 km against a 1.8 km tile.

**A correction to REAL-DATA-01 section 4.5.** That section tested four H1/H2 combinations, saw 3/4/4/5 inliers, and concluded *"All four fail. The direction hypothesis is not the explanation."* Exactly **one** of the four rows has overlapping tiles; the other three are 11-23 km apart and could not have succeeded. The direction hypothesis was resolvable, was not resolved, and *was* the explanation for three of the four rows. The original text stands unedited (integrity rule 3).

**Status:** RL-029b **closed**. Successor thread **RL-031b**: why does `usable_H2` fail at 68.6 % overlap? Needs REAL-DATA-03.

---

### RL-032 - The geometry was in the archive index table, one directory above the data

**Question.** REAL-DATA-01 concluded that no exact pixel -> (lat, lon) mapping was available to this project without SPICE or a camera model (D-030). Was that true?

**Evidence.** `[MEASURED]` An audit of four sources:

| source | positional geometry? |
|---|---|
| PDS4 `Product_Observational` label | **none** - no `Cartography`, no `Geometry`, no coordinates of any kind |
| PDS3 attached header inside the `.IMG` (5064 B, fetched live) | **none** - no geometry keywords at all |
| ODE product record | `Footprint_geometry`, a 4-vertex WKT ring with an **undocumented vertex order** |
| **PDS archive index table** (`<VOLUME>/INDEX/INDEX.TAB` + `.LBL`) | **named corners**, plus `NORTH_AZIMUTH`, `SUB_SOLAR_AZIMUTH`, `ORBIT_NODE`, `LRO_FLIGHT_DIRECTION`, `SCALED_PIXEL_WIDTH`/`HEIGHT` |

ODE itself names the source it did not fully expose: `Footprint_souce = "PDS Archive Index Table"`. The tables are 18-54 MB but `FIXED_LENGTH` and sorted by `PRODUCT_ID`, so one row costs a binary search of 15-18 HTTP range requests of 901 bytes. Four products: **~130 KB, no image bytes**.

`[MEASURED]` Every ODE ring vertex matches a named index corner to machine precision, in the order **(UR, LR, LL, UL)** for all four products - fixed, and not the UL-first order anyone would guess.

**What makes the corner names usable.** Each product's own PDS4 label states `disp:Display_Direction` = `(Line, Top to Bottom)` and `(Sample, Left to Right)`, so the top row is the first line and `UPPER_*` is line 0. Corroborated two ways: corner-implied pixel scale agrees with the archive's SPICE-derived `SCALED_PIXEL_HEIGHT`/`WIDTH` within **1.2 % over 8 comparisons**, and the 2-2 split of `UPPER`-is-north follows `LRO_FLIGHT_DIRECTION` exactly - impossible if `UPPER` were a compass label.

**A closed loose end.** REAL-DATA-01 section 18 left an unexplained **1.05** ratio between footprint-implied m/line and ODE's `Map_resolution`, *"possibly a footprint-polygon convention, possibly real along-track scale."* Neither: `Map_resolution` is the index's `RESOLUTION` column, which is **not** the down-scan pixel scale. Against `SCALED_PIXEL_HEIGHT` the ratios are **1.002-1.012**. The 5 % was a comparison against the wrong field.

**A check that failed, recorded as E-027.** A `NORTH_AZIMUTH` cross-check of the corner naming was designed and implemented, and has **no discriminating power**: 268.59 / 274.77 / 267.72 / 272.94 for frames that split 2-2 on line direction. The column's own description says the angle is *"relative to the RDR products"* - the map-projected derivative, north-up by construction. E-024 recurring, caught before it was reported as a result.

**Unresolved, and deliberately not acted on.** `SUB_SOLAR_AZIMUTH` **exists** in this table (144.09 / 175.27 / 177.73 / 120.46 deg) - the first Sun-azimuth information this project has had access to (E-020). `[NOT VERIFIED]` It carries the same RDR-relative caveat, and it was **not used anywhere in REAL-DATA-02**. It also cannot make these pairs azimuth-*controlled*: they were selected on incidence, and a field discovered afterwards cannot retroactively control an experiment.

**Status:** open as **RL-032b** - verify the reference frame of `SUB_SOLAR_AZIMUTH` before any Delta-azimuth number is quoted.

---

### RL-033 - The first valid real-data experiment: the baseline fails at 40 deg of incidence difference and succeeds at 1 deg

**Question.** RL-031b: with shared ground independently confirmed, does the unmodified baseline register two real LRO NAC frames taken under different illumination?

**Design.** Three real NAC tiles of the same patch of Mare Serenitatis, every one cut on the **same ground point** (lon 22.033852, lat 20.035253) by inverting a bilinear ground map built from the archive index table's named frame corners. Overlap was CONFIRMED on all three edges **before** any registration was interpreted, by a gate that exits non-zero otherwise (D-035). Nothing in the matcher, RANSAC, descriptors, thresholds, model, decimation or preprocessing was changed.

**Evidence.** `[MEASURED]` `experiments/REAL-DATA-03/overlap_triplet.json`, `loop_closure_triplet.json`, `transform_vs_geometry.json`.

| edge | dIncidence | overlap (confirmed, matcher-independent) | putative | **inliers** | fit RMSE (px) | coverage gap |
|---|---|---|---|---|---|---|
| A -> B | **39.81 deg** | 97.12 % | 32 | **4** | **4.138e-13** | 0.477 |
| **B -> C** | **0.96 deg** | 85.00 % | 5392 | **5365** | 0.583 | **0.108** |
| C -> A | **38.85 deg** | 82.72 % | 49 | **4** | 0.885 | 0.441 |

A = `nac.m1271742202lc` (incidence 29.95 deg), B = `nac.m1335207975rc` (69.76 deg), C = `nac.m1452560468lc` (68.80 deg).

**What the evidence eliminates.** Every one of these is eliminated by a *measurement* against the succeeding edge, on the same ground, through the same code:

| candidate | eliminated because |
|---|---|
| tiles do not overlap | 97.12 % and 82.72 %, confirmed without the matcher |
| mare texture poverty (D-026) | B -> C found 5392 putative and 5365 inliers on **the same mare** |
| 2x decimation | identical on the succeeding edge |
| resolution mismatch | A<->B has the *smallest* ratio (1.016) and fails; B<->C has 1.074 and succeeds |
| relief displacement / parallax | the succeeding edge spans the *largest* emission difference (1.17->1.72 deg); the failing C->A spans the smallest (1.72->1.74 deg) |
| residual window uncertainty | the succeeding edge has *less* confirmed overlap (85.0 %) than the failing A<->B (97.1 %) |
| affine model limitation | same model on all three edges |
| a pipeline defect | B -> C is a successful **cross-frame** registration -- a stronger control than REAL-DATA-01's self-registration |

**Interpretation.** `[INTERPRETATION]` **Illumination difference is the only enumerated candidate left standing, and it is still not the established cause.** In a three-frame design, "large dIncidence" is **perfectly confounded** with "the pairing involves frame A" -- A is the only low-incidence frame and appears in both failing edges. dIncidence is separately confounded with dAzimuth, which was **not measured** (RL-032b). Recorded as **D-036**, which does not attribute the failure.

**A prediction, written down before the data exists.** REAL-DATA-04 acquires one more frame D at low incidence on the same ground point. If **D<->A succeeds and D<->B fails**, illumination is the driver. If the reverse, frame identity is, and the surviving candidate is refuted.

**E-008's cleanest instance.** A -> B reports a fit RMSE of **4.138e-13 px** for a transform whose independently measured error is **1614 px** (`transform_vs_geometry.json`), on a pair with 97 % confirmed shared ground. Not synthetic, and not on tiles that turned out to be disjoint.

**Status:** RL-031b **closed**. Successor **RL-033b**: is the driver illumination or frame identity? REAL-DATA-04.

---

### RL-034 - A real registration that a field the matcher never saw predicts to 0.04 %

**Question.** RL-030b asked whether overlapping real NAC triplets exist at all, so that loop closure -- the project's only GT-free estimator that detects a coherent wrong answer -- could meet real data. And if an edge succeeds, can anything corroborate it without ground truth?

**Availability.** `[MEASURED]` Answered cheaply, because REAL-DATA-02's corner geometry lets tile-level overlap be computed *before* anything is fetched. One ODE query over a box around the target returned 60 CDR products; 13 carried a usable four-vertex footprint; **8 frames contain the target ground point with a full 4096x2048 tile inside**. Overlapping real triplets are not scarce in this region. One product was acquired.

**Loop closure on real data, for the first time.** Three edges, each estimated independently from its own image pair; the closing edge was never derived as `(T_BC o T_AB)^-1`, and the independence is **asserted in code** (`_assert_independent`) rather than intended, because E-021 was exactly that derivation manufacturing a zero residual for a registration 64 px wrong.

```
edges with a transform: 3 / 3
LOOP CLOSURE RESIDUAL: 1201.04 px
```

`[INTERPRETATION]` ADR-0011's reversal condition -- *real-data evidence that per-edge errors cancel around a loop* -- is **not** triggered: two edges are independently confirmed catastrophically wrong and the loop reported 1201 px rather than closing. But a loop with two garbage legs **exercises** the estimator without measuring its power. That needs three *successful* real edges.

**Corroborating a success without ground truth.** A new check predicts where each pixel of one tile lands in another from archive corner geometry alone -- no image data, no matcher output (`scripts/check_transform_against_geometry.py`). It is a **bound, not a ground truth**: corner coordinates are quoted to 0.01 deg (~150 m ~ 165 full-frame px).

A second, sharper test uses `SCALED_PIXEL_WIDTH`/`HEIGHT`, which the archive derives from SPICE and which feeds neither the matcher nor the corner polygon. A transform mapping A's pixels onto B's must scale by the ratio of their ground samplings:

| edge | predicted scales | estimated singular values | relative error | tolerance | agrees |
|---|---|---|---|---|---|
| A -> B | 1.01053 / 1.02273 | 0.46759 / 2.06267 | **53.7 % / 101.7 %** | 1.70 % | no |
| **B -> C** | **1.06742 / 1.07317** | **1.06699 / 1.07851** | **0.04 % / 0.50 %** | 1.83 % | **yes** |
| C -> A | 0.91111 / 0.92708 | 0.34718 / 0.59103 | **61.9 % / 36.3 %** | 1.83 % | no |

`[INTERPRETATION]` The 5365-inlier edge recovers a scale an independent SPICE-derived archive field predicts to **0.04 %**, inside that field's own quantisation. The two failing edges miss by 36-102 %. This is the strongest corroboration available without ground truth -- and it is **corroboration, not verification**: the edge is **class B**, not class A. Calling it verified would be the over-claim this project exists to avoid.

**A caught design defect.** The check's first version compared a point estimate against a p95 floor with a bare `>` and labelled the succeeding edge INCONSISTENT at 1.55x the floor, while the disagreement's own p5-p95 straddled that floor. That is **E-024** exactly, caught before it was reported. The verdict is now three-valued with a stated margin, and INCONCLUSIVE is reported as a result.

**Status:** RL-030b **closed** on availability. Open as **RL-034b**: measure loop closure's discriminating power on three *successful* real edges.

---

---

### RL-035 — Illumination, not frame identity: the confound broken, and a rule broken with it

**Question.** RL-033b: REAL-DATA-03 left illumination as the only surviving candidate cause of real-data registration failure and refused to attribute it, because across three frames *large Δincidence* and *the pairing involves frame A* were **the same partition**. Can they be separated?

**The prediction, written down before the data existed.** *If D↔A succeeds and D↔B fails, illumination is the driver; if the reverse, frame identity is.* Recorded in REAL-DATA-03 §20, D-036 and RL-033b, and restated in REAL-DATA-04 §2 before frame D was screened.

**The pre-registered acquisition turned out to be impossible, and that is a measurement.** `[MEASURED]` `data/manifests/screen_frame_d.json`, `screen_frame_d_tightbox.json`. Of **17** CDR frames intersecting REAL-DATA-03's target ground point, **8** contain it with a full 4096×2048 tile inside, and their incidences are 29.95, 43.74, 44.44, 45.48, 47.11, 48.47, 52.40, 66.72, 66.88, 68.80, 69.76, 72.29, 74.65, 80.14, 83.63, 149.86, 149.98. **Frame A is the only low-incidence frame over that point.** Widening the ODE box from 60 to 261 to 1021 products changes nothing — a tight box at the target returns the same 8.

**Amendment 1, registered before one image byte was fetched.** A and B are 45 km strips whose *tile-admissible* footprints — the ground on which a whole tile fits, not merely where the frames overlap — intersect in **75.09 km²**. Only the target point had to move. **Frames A and B are unchanged**, so the frame-identity test survives intact; the decision table, the success criterion and the baseline are untouched. Recorded as **D-039** (`shared_tile_target()`), because the shared-*frame* centroid of D-033 can put a point within half a tile of an edge and clamp the window.

**Amendment 2, and E-032 with it.** `[MEASURED]` Authoritative corners for the five surviving candidates broke a rule this project had been quoting. REAL-DATA-02 recorded, and REAL-DATA-03 §10 called a *"fifth independent confirmation"* of, `LRO_FLIGHT_DIRECTION = −X` → line 0 at minimum latitude. Over the **10** frames with authoritative named corners it holds **8/10**: `nac.m1343417565rc` is −X with line 0 at *maximum* latitude and `nac.m124423514lc` is +X with line 0 at *minimum*. `NORTH_AZIMUTH`, quoted as its cross-check, was 267.7–276.8° for all five earlier frames and therefore **had no discriminating power over the line direction in the sample it was validated on**; what it does separate, 10/10, is the **cross-track** sense. No pipeline change was needed — `corners_from_index_geometry()` always read each product's own `disp:Display_Direction` — so the prose was corrected, not the code. The consequence for the experiment: a frame with the opposite orientation yields a tile rotated 180°, which would entangle this stage's causal question with **EXP-004's open orientation-assignment question**, so orientation match became hard filter 1c (**D-038**). **It rejected the stage's own top-ranked candidate** and left exactly one admissible frame.

**Frame D.** `nac.m1299958135lc`, incidence **18.22°**, `Map_resolution` 1.071 m — not chosen, but the only candidate left after the hard filters. Tiles A, B and D cut on one authoritative ground point (22.010350, 19.666255), **no window clamped on either axis**.

**The gate, before any registration was interpreted.** `[MEASURED]` `experiments/REAL-DATA-04/overlap_real_data_04.json`. All three edges `OVERLAP_CONFIRMED` from archive corner geometry alone — no pixel read, no matcher component — and, crucially, **the two decisive edges are overlap-matched to 0.95 percentage points**: D↔A 71.30 % (p5 68.01), D↔B 70.35 % (p5 67.38). The control A↔B is the *most*-overlapping edge at 97.87 %.

**Result.** `[MEASURED]` `experiments/REAL-DATA-04/loop_closure_real_data_04.json`. The unmodified baseline, three edges each estimated independently from its own image pair:

| edge | dIncidence | overlap (confirmed) | putative | **inliers** | ratio | fit RMSE (px) | coverage gap | occupancy |
|---|---|---|---|---|---|---|---|---|
| A -> B *(control)* | 39.81 deg | 97.87 % | 50 | **7** | 0.1400 | 1.1053 | 0.4604 | 0.062 |
| B -> D *(decisive)* | **51.54 deg** | 70.35 % | 29 | **3** | 0.1034 | **1.885e-13** | 0.4268 | 0.047 |
| **D -> A** *(decisive)* | **11.73 deg** | 71.30 % | **1759** | **1656** | **0.9414** | 0.8779 | **0.1033** | **1.000** |

**D↔A succeeds and D↔B fails — the first row of the pre-registered table, unmodified.** `[INTERPRETATION]` **Illumination is strongly supported and frame identity is refuted.** Recorded as **D-040**, superseding D-036.

**Why frame identity is refuted rather than merely unsupported.** Across the six real edges now measured, on five frames and two ground windows, **every frame appears in both a succeeding and a failing edge** — A in D→A and A→B, B in B→C and B→D, C in B→C and C→A, D in D→A and B→D. **No frame's presence predicts the outcome; Δincidence predicts all six**, separating successes at 0.96° and 11.73° from failures at 38.85°, 39.81°, 39.81° and 51.54°. The specific claim REAL-DATA-03 could not make is now available: **frame A is not defective.** Its keypoint count is comparable in both regimes (9538, 10794, 12593), so the **detector** is not failing — **descriptor matching across illumination** is.

**The mirror-image confound was checked, not assumed away.** Within REAL-DATA-04's triplet alone, B is the only high-incidence frame and sits in both failing edges — precisely the structure that blocked REAL-DATA-03. It does not survive the join, because REAL-DATA-03's succeeding edge B→C contains B. **Neither triplet alone settles this; the two together do.**

**What else the evidence eliminates**, each by a measurement, and each argued *across* both stages because a factor that predicts the outcome in one and anti-predicts it in the other predicts nothing:

| candidate | eliminated because |
|---|---|
| amount of overlap | the decisive edges are matched to 0.95 pp and diverge by 552x in inliers; across both stages the **most**-overlapping edges (97.9 %, 97.1 %) fail and the least-overlapping (71.3 %, 85.0 %) succeed |
| resolution mismatch | succeeding D->A 1.1479 vs failing B->D 1.1667 -- 1.6 % apart; and A<->B has the project's **smallest** ratio (1.0163) and fails at **two** windows |
| relief displacement (dEmission) | **anti-correlated across stages**: RD-04's succeeding edge has the smallest dEmission of its three (0.01 deg), RD-03's had the largest of its three (0.55 deg), and RD-03's failing C->A had the smallest (0.02 deg) |
| acquisition interval | RD-04 alone is monotonic (11 months succeeds, 14 and 24 fail) -- but RD-03's **45-month** B->C succeeds while its 24-month A->B fails |
| frame orientation / EXP-004 | excluded **by design before acquisition** (D-038); estimated rotation on the succeeding edge is +0.28 deg |
| mare texture poverty, decimation, window clamping, the affine model, a pipeline defect | as REAL-DATA-03, now at a second ground window |

**Corroboration from a field the matcher never saw.** `[MEASURED]` `transform_vs_geometry_real_data_04.json`. D→A's recovered scale matches SPICE-derived `SCALED_PIXEL` to **0.13 % / 0.04 %** inside a 1.67 % tolerance, and its corner-polygon disagreement is **56.3 px against a 105.6 px discrimination floor — 0.53×, the only edge in either stage to fall below that bound** (REAL-DATA-03's best was 1.55×). B→D misses by **78 % / 107 %** and is independently confirmed catastrophically wrong.

**E-008's cleanest instance yet, and it would have inverted the conclusion.** `B → D reports a fit RMSE of 1.885e-13 px` for the transform measured to be **797 px** wrong, while the **succeeding** edge D→A reports **0.878 px**. Had `fit_rmse` been the criterion rather than `n_inliers`, this stage would have concluded the exact opposite of what it concluded. D-003 measured that metric at ROC AUC 0.4947 on synthetic data; this is the second consecutive real stage where it is not merely uninformative but **inverted**.

**One number honestly close to its threshold.** The control A→B returned **7** inliers against a rule of `<= 8`. It is reported as close rather than rounded away — and it does not put the conclusion at risk, because the decisive comparison is 1656 against 3 and **no threshold between 4 and 1655 changes it**.

**Loop closure, a second time on real data.** 943.75 px with two broken legs — again no manufactured small residual, so ADR-0011's reversal condition is still not triggered. Its *discriminating power* remains unmeasured: that needs three **successful** real edges and this triplet has one.

**Scope, which is part of the finding.** This is Δ**incidence**, on **mare** terrain, in **one** region, with **one** instrument, over **five** frames and **two** ground windows. It is **not** an azimuth result — `SUB_SOLAR_AZIMUTH`'s frame is still unverified (RL-032b) — and it does **not** locate the cliff, which is now bracketed to **11.73°–38.85°**, narrowed from 38° but still 27° wide.

**Status:** RL-033b **closed — answered**. Frame identity and illumination *can* be separated, and the separation goes to illumination. **No successor research question is opened.** Under the standing constraint, REAL-DATA-04 is the final high-value causal experiment; the next action is **September 2 demo engineering**, not another stage. EXP-004 remains pre-registered and **not started** — for the first time pointed at a real question (the *mechanism* behind the Δincidence failure), and still not justified before the demo.


## Open threads summary

| ID | Thread | Experiment | Critical path? |
|---|---|---|---|
| ~~H-003~~ | ~~Polarity-agnostic representation pushes the cliff past Δaz 30° on A-regimes~~ | **CLOSED — REFUTED by EXP-003 (RL-023).** mod-π was the *worst* arm | — |
| RL-023b | Illumination-**stable orientation assignment** (not binning) is the dominant classical failure | **EXP-004** | **yes — post-hoc, needs pre-registration** |
| RL-023c | Is realistic mare at 384² too small to answer the question at all? | **EXP-004, first** | **yes — bounds every mare conclusion** |
| H-004 | Protocol dominates matcher choice on lunar data | EXP-006 | **yes — thesis rests on it** |
| RL-020b | How often coherent-wrong solutions arise on *real* imagery | needs real data | yes |
| ~~RL-029b~~ | ~~Why the first real registration failed — overlap, or illumination?~~ | **CLOSED by REAL-DATA-02 (RL-031).** The headline pair's tiles were **22.75 km apart** and share **0.0000 km2**; that run measured nothing about the matcher | — |
| ~~RL-031b~~ | ~~Why does a confirmed-overlap real pair fail?~~ | **CLOSED by REAL-DATA-03 (RL-033).** Seven candidates eliminated by measurement against a succeeding edge on the same ground; illumination is the only survivor | — |
| ~~RL-033b~~ | ~~Is the driver illumination, or frame identity?~~ | **CLOSED — ANSWERED by REAL-DATA-04 (RL-035).** Frame D at 18.22° registers against frame A (**1656** inliers, ratio 0.9414, occupancy 1.000) and fails against frame B (**3**), on edges overlap-matched to 0.95 pp. Across six real edges every frame appears on both sides and Δincidence separates all six. **Illumination supported (D-040); frame identity substantially weakened, NOT conclusively refuted** — see the D-040-N1 superseding note | — |
| **RL-036** | **Does the illumination result replicate on a second low-incidence frame?** REAL-DATA-04's conclusion rests on **one** succeeding edge; A and D each have n = 1 in the successful regime | **REAL-DATA-05 — UNRESOLVED, BY DATA AVAILABILITY.** Of 906 archive products, 8 can centre a full tile on ground shared with A, B and D; only 2 are in the required incidence band and **both are orientation-incompatible** with the incumbents. The screen returned zero admissible frames at every tier and rung; no image byte was fetched, no registration was run, and the decision table was never reached. **Open — a successor must change the design, pre-registered, not the criteria** | **yes — it is what would discharge D-040-N1** |
| **RL-034b** | **Loop closure's discriminating power on real data.** Exercised twice now — 1201.04 px and **943.75 px**, neither a false closure — but both loops had two broken legs | a later stage | **no — deferred behind the September 2 demo.** Needs three mutually low-Δincidence real frames |
| **RL-032b** | **What frame is `SUB_SOLAR_AZIMUTH` measured in?** It exists in the archive index table but carries the same "relative to the RDR products" caveat that made `NORTH_AZIMUTH` useless (E-027) | **REAL-DATA-03** | yes — it would be this project's first real Sun-azimuth information (E-020) |
| ~~RL-030b~~ | ~~Are overlapping real NAC triplets available at all?~~ | **CLOSED by REAL-DATA-03 (RL-034): 8 of 60 screened frames contain the target ground point with a full tile inside.** They are not scarce. One was acquired and a real loop was closed | — |
| **RL-028b** | Where does incidence actually stop being usable? The 75° ceiling is a provisional cut, unswept | a later real-data stage | no |
| RL-017b | Exact cliff edge between Δaz 15° and 30° on A-regimes | EXP-003 | no |
| ~~RL-022b~~ | ~~`n_inliers <= 8` in the discriminable regime~~ | **CLOSED by EXP-003 (RL-024): recall transfers, FPR does not (0.0112 → 0.369)** | — |
| RL-024b | A deployable operating point with an acceptable false-alarm rate in the mixed regime | **EXP-004** | yes |
| RL-006 | IIRS band-index vs matchability boundary | deferred, data-blocked | no |
| — | CPU latency of each learned engine | EXP-005 | yes |

**Closed by EXP-002:** H-005 (GT-free estimators built and scored — only loop closure works, RL-020) · RL-011 (threshold claim refuted, operating point validated, RL-019) · RL-009b (cliff relocated to 15–30°, RL-017).

### Debt carried out of EXP-001

| Item | Why it matters | When |
|---|---|---|
| ~~LO-RANSAC refits on the full consensus set every iteration~~ | | **DONE (RL-015)** — ~970× |
| ~~Synthetic terrain too steep and too feature-dense~~ | | **DONE (RL-017)** — 4 regimes, LOLA-anchored |
| ~~`classify_failure` thresholds asserted, not calibrated~~ | | **DONE (RL-019)** — validated on disjoint seeds |
| Cycle consistency untested against a *real* independent reverse pass | Its 1.000 false-alarm rate came from an adversarial construction | EXP-003+ |
| Loop closure needs real overlapping triplets | Only validated on constructed transforms so far | when data arrives |
| Terrain matches LOLA *medians* but distribution shape is unverified | Percentiles reported, but shape not fitted | low priority |
