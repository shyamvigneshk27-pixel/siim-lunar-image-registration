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

## Open threads summary

| ID | Thread | Experiment | Critical path? |
|---|---|---|---|
| ~~H-003~~ | ~~Polarity-agnostic representation pushes the cliff past Δaz 30° on A-regimes~~ | **CLOSED — REFUTED by EXP-003 (RL-023).** mod-π was the *worst* arm | — |
| RL-023b | Illumination-**stable orientation assignment** (not binning) is the dominant classical failure | **EXP-004** | **yes — post-hoc, needs pre-registration** |
| RL-023c | Is realistic mare at 384² too small to answer the question at all? | **EXP-004, first** | **yes — bounds every mare conclusion** |
| H-004 | Protocol dominates matcher choice on lunar data | EXP-006 | **yes — thesis rests on it** |
| RL-020b | How often coherent-wrong solutions arise on *real* imagery | needs real data | yes |
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
