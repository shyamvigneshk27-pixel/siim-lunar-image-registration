# MASTER RESEARCH AND ARCHITECTURE PLAN — SIH26166

**Multi-modal, Sun-angle and scale-invariant image correspondence using Chandrayaan-2 optical images (OHRC, TMC-2, IIRS) against lunar reference imagery (LRO NAC).**

**Status:** Research reset. Written 2026-09-04 from first principles, after (a) a complete read of the repository at commit `059c1f9`, (b) a live literature search across arXiv, ADS, IEEE, ScienceDirect, MDPI, ISPRS, USGS, LROC, PDS, ISSDC/PRADAN and GitHub, and (c) a failure audit of the previous plan.

**Rule of this document.** Every claim is tagged: `[FACT]` sourced and verifiable · `[LIT]` literature evidence, cited · `[OURS]` measured in this repository · `[INFERENCE]` reasoned from facts · `[HYPOTHESIS]` testable, untested · `[UNKNOWN]`. Confidence is stated as HIGH / MEDIUM / LOW. Where evidence is missing the document says `EVIDENCE INSUFFICIENT`. Where a method should be abandoned it says `RECOMMENDATION: KILL`.

**Nothing in the repository was modified to produce this document.** No matcher was replaced, no frozen criterion changed, no artefact edited, no experiment deleted.

---

## 1. Executive summary

**The real problem is not building a better matcher.** On an airless, static body whose topography is mapped globally and whose acquisition geometry is recorded in SPICE kernels for every product, most of the appearance change the problem statement calls "Sun angle" is **physically predictable** from a digital elevation model and the archive's own illumination metadata. The previous plan treated illumination as an unknown nuisance to be made invariant to, at the descriptor level, and measured with great care that it could not do so. That measurement is correct and is the previous plan's one durable result. The conclusion it should have led to, and did not, is that the invariance should come from **physics that is already known**, and that the matcher's job is the residual.

**Central scientific hypothesis (H0).** *On lunar orbital imagery, conditioning correspondence on the known illumination geometry, by rendering a reference DEM under each image's own Sun vector and matching each image against its illumination-matched render rather than against the other image, extends the usable Sun-angle difference beyond what any invariant descriptor or zero-shot learned matcher achieves on the raw pair, and the gain is bounded by the ratio of DEM resolution to image GSD.* This is falsifiable in both directions and makes a scale-dependent prediction that the sensor ladder of the problem statement (OHRC 0.25 m → TMC-2 5 m → IIRS 80 m, against NAC 0.5–2 m) tests naturally.

**Recommended architecture: GAPC — Geometry-Anchored, Physics-Conditioned correspondence with pre-registered verification.** Five layers: (1) geometry from SPICE and archive footprints gives overlap, a prior transform and its uncertainty *before any pixel is read*; (2) a PSF-aware GSD ladder degrades the finer image to the coarser one and never the reverse; (3) illumination is handled in tiers — per-pixel photometric normalisation where the DEM resolves the shading, DEM-rendered illumination-matched intermediaries where it does not, and a replaceable robust matcher (phase-congruency or an Apache/MIT-licensed learned matcher) for the residual; (4) a locally valid geometric model with spatially balanced correspondences; (5) verification and rejection on independent evidence, with sub-pixel refinement by area-based methods at the coarser GSD and an honest uncertainty per correspondence.

**What is novel, honestly stated.** No component is new. DEM-rendered illumination matching exists in lunar terrain-relative navigation (JPL LIMA and LuNaMaps) and in Chinese NAC-to-SLDEM registration `[LIT]`. Photometric normalisation exists in ISIS `[FACT]`. Phase congruency, RIFT2, LightGlue and RoMa exist `[LIT]`. What does not exist in the literature found, and is therefore the defensible contribution *if verified*: (a) a quantified, pre-registered test of DEM-conditioned illumination invariance across the *cross-sensor* Chandrayaan-2/NAC scale ladder with the DEM-resolution bound stated as a prediction; (b) an evaluation protocol for lunar registration in which fit residuals are excluded by measurement, success is decided by a rule frozen before the data, and coherent-wrong answers are caught by geometric evidence independent of the matcher; (c) a leakage-controlled benchmark of real pairs with geometry-derived ground truth and stated uncertainty. Contribution (b) is partly built and validated in this repository `[OURS]`.

**Biggest risk.** At the finest rung (OHRC↔NAC at sub-metre GSD) the available DEMs (SLDEM2015 at 59 m; NAC DTMs at 2–5 m only where they exist) may not resolve the shading features the matcher relies on, so H0 predicts its own weakest regime there. The plan treats that as a measured boundary, not a defeat, and pairs it with the learned-matcher arm as the fallback engine.

**Single most important experiment.** EXP-007: the six recorded real NAC edges plus a new multi-illumination site with a NAC DTM, run through three illumination arms (none / photometric / DEM-render) at four GSD rungs, against the unchanged pre-registered failure rule. It reuses everything already built, runs on CPU in hours, and settles H0 at the coarse rungs within a week.

**What must happen first, today.** Register on PRADAN (free signup, `[FACT]`) so that Chandrayaan-2 products can be obtained. Every previous stage ran without a single Chandrayaan-2 pixel; that is the plan's largest exposure and it is administrative, not technical.

---

## 2. Official problem interpretation

### 2.1 Official wording `[FACT]` (from `SIH.md` at HEAD, ISRO PS 26166)

Register a source image (Chandrayaan-2 OHRC, TMC-2 or IIRS) to a reference image (LRO NAC or other) under **illumination variation** (Sun azimuth and elevation), **viewpoint variation**, and **scale variation**. Expected solution: *"a generic software solution for finding correspondence between Chandrayaan-2 acquired optical images and lunar reference images with sub-pixel accuracy of the source image while maintaining a uniform distribution of matching points across the images."* Deliverables: software, registered product, corresponding match points, evaluation metrics "such as RMSE, inlier match count, inlier ratio, other appropriate metrics". Data sources named: ISSDC chmapbrowse, LROC downloads, LROC QuickMap. *"The exact SIH dataset may be provided separately/TBD."*

### 2.2 Requirement decomposition

| Requirement | Scientific question | Engineering requirement | Measurable metric | Validation experiment | Acceptance criterion |
|---|---|---|---|---|---|
| Correspondence under Sun-angle change | What fraction of appearance change is predictable from DEM + ephemeris, and what residual remains? | Illumination-conditioned matching path with a stated operating envelope in Δincidence and Δazimuth | Success rate vs Δinc/Δaz on real pairs; endpoint error on rendered-GT pairs | EXP-007 (real), EXP-005 (rendered GT) | Envelope ≥ 40° Δinc at TMC/IIRS rungs; boundary *stated* at OHRC/NAC rung |
| Scale invariance (2:1 to 320:1) | Is the limit descriptor failure or sampling starvation? | PSF-aware degrade-to-coarser ladder; never upsample | Success rate per rung; error in coarser-image pixels | Scale probe extended to real pairs | Every rung ≤ 320:1 registers when overlap ≥ 50 % of the coarser tile |
| Viewpoint invariance | Where is a 2D model physically valid given relief and off-nadir angle? | Model class chosen by residual test; DEM orthorectification when relief × tan(e) > 0.5 px | Residual structure vs relief; local-vs-global model AIC | EXP-008 | Local model residuals white; no systematic relief signature |
| Multi-modality (OHRC/TMC ↔ IIRS bands) | What is physically shared between pan and NIR/thermal bands? | Band selection by physics (reflectance ≤ 2.5 µm; thermal ≥ 3.5 µm treated as a separate modality); structural descriptors for the thermal case | Success rate per band; cross-band consistency | EXP-009 | Reflectance bands: same envelope as pan; thermal: envelope stated |
| Sub-pixel accuracy "of the source image" | What does sub-pixel mean physically when the coarser sensor's pixel is 320× the finer one's? | Area-based refinement at the coarser GSD; uncertainty per correspondence | Error on independent check points, in coarser-image pixels, with CI | Rendered-GT and check-point validation | Median < 0.5 coarser-px with 95 % CI reported; never claimed from fit residual |
| Uniform distribution of match points | Uniform in what sense, and does enforcing it cost accuracy? | Coverage-constrained selection (ANMS/grid) and a coverage metric in the verdict | `max_uncovered_disc_ratio`, occupancy, entropy `[OURS]` | Existing coverage module | Gap ≤ 0.15 of image diagonal on accepted pairs |
| Registered product | — | Warp with NaN no-data (E-003), provenance | Valid fraction; no zero fill | Existing product tests `[OURS]` | Product emitted only for accepted pairs |
| Metrics incl. RMSE, inlier count, ratio | Which of these are evidence of correctness? | Report all; exclude fit RMSE from the verdict by measurement | AUC of each signal vs GT on calibration data | EXP-002 objective 3 `[OURS]` | Verdict never rests on a signal with AUC < 0.9 |
| "Generic software", dataset TBD | — | Ingestion for PDS4 (NAC, C2), GeoTIFF (TMC-2 L2), IIRS cube + geometry file | Clean load of each format | Ingest tests | All named formats load with geometry |

### 2.3 Explicit vs implied vs must-not-assume

- **Explicit:** three variations, three C2 sensors, NAC reference, sub-pixel, uniform distribution, four deliverables, metrics list.
- **Implied:** offline/CPU-friendly ("generic software"); the evaluation data are ISRO's and unknown; multi-modality is in the title but not defined; "sub-pixel accuracy of the source image" is ambiguous when source is coarser than reference.
- **Assumptions we may make:** SPICE/geometry metadata accompany every product (true for PDS4 C2 archive `[FACT]`); global DEMs are available; viewing is near-nadir except TMC-2 fore/aft (±25°) and slewed NAC/OHRC.
- **Must not assume:** that RMSE measures correctness (refuted `[OURS]`); that the evaluation set will contain overlapping pairs (RD-01 lesson); that ISRO's pairs will have metadata (the software must degrade gracefully); that "multimodal" means anything beyond different bands of reflected sunlight until IIRS thermal bands are involved.

---

## 3. Problem decomposition

The correspondence `q = proj_R(proj_S⁻¹(p))` is undefined without depth `[FACT]`. Every 2D model is an approximation whose error is `relief × tan(emission difference)` at first order. Decompose:

1. **Where is the ground?** (overlap, prior transform) — solvable from geometry alone `[FACT, OURS RD-02]`.
2. **What does the ground look like under this Sun?** — predictable from DEM + photometric model to the DEM's resolution `[LIT]`; residual is albedo and sub-DEM relief.
3. **What is the sampling relationship?** — PSF and GSD of each sensor, known `[FACT]`.
4. **What is the geometric relationship?** — pushbroom line-scan with attitude; locally affine; globally needs DEM orthorectification `[FACT]`.
5. **Which residual correspondence problem remains after 1–4 are removed?** — this is what the matcher solves. It is smaller than the raw problem by construction. `[INFERENCE, HIGH]`
6. **How do we know we are wrong?** — verification on evidence the matcher did not produce `[OURS]`.

---

## 4. Mathematical formulation

Let `X ∈ Ω ⊂ S²` be lunar surface points with height field `h(X)` (DEM). Image `I_k` has projection `π_k` (SPICE-defined line-scan model, uncertain by attitude/ephemeris error `ε_k`), Sun direction `s_k`, view direction `v_k`, PSF `ψ_k`, GSD `g_k`, spectral response `Λ_k`. Observed radiance:

`I_k(u) = ψ_k * [ A_Λ(X) · f(i(X,s_k), e(X,v_k), g(X,s_k,v_k); θ) · V(X,s_k) ] ∘ π_k(X) + n_k`

where `A_Λ` is albedo in band `Λ`, `f` the photometric function (Lommel-Seeliger, Hapke), `V` cast-shadow visibility, `n` noise. Correspondence: `p ∈ I_S`, `q ∈ I_R` with `π_S⁻¹(p) = π_R⁻¹(q) = X`.

**What the pipeline estimates.** `T_SR` locally (affine per tile, or a DEM-parameterised map when relief matters), plus per-correspondence covariance `Σ_i`.

**Illumination conditioning.** Given `h` and `s_k`, render `Î_k = ψ_k * [ f(i,e,g;θ) V ] ∘ π_k` with unit albedo. Then the pair `(I_k, Î_k)` shares `s_k` and differs only by albedo, sub-DEM relief and model error; the pair `(Î_S, Î_R)` shares `h` exactly and differs only by illumination on the *same* known surface, so correspondence between renders is known analytically through `X`. Image-to-image correspondence is the composition `I_S → Î_S → X → Î_R → I_R`. `[INFERENCE, HIGH]`

**Scale.** `I_fine ↓ g_coarse := ψ_coarse ∘ resample(I_fine)`; matching is done at `g_coarse`; sub-pixel is defined in units of `g_coarse`. Coordinates follow contract C4 (`p' = s(p+0.5)−0.5`) `[OURS]`.

**Verification.** Independent evidence `E = {geometry prior consistency, held-out check points, loop closure over ≥ 3 views, render consistency}`; a verdict `V ∈ {VERIFIED, REJECTED, INCONCLUSIVE}` from pre-registered rules on `E`, never on the fit residual.

---

## 5. Physical formulation

### 5.1 What actually changes between lunar acquisitions `[FACT unless marked]`

| Quantity | Modelable? | Source |
|---|---|---|
| Sun azimuth/elevation → incidence `i`, phase `g` at each pixel | Yes, per pixel, from SPICE + DEM | Archive geometry, SLDEM/LOLA/NAC DTM |
| Cast shadows | Yes, by ray-casting the DEM at DEM resolution; sub-DEM shadows not modelable | DEM |
| Photometric function (limb darkening, opposition surge, phase reddening) | Yes to first order (Lommel-Seeliger; Hapke with Sato 2014 parameter maps `[LIT]`); roughness term omitted at high `i` is a known error | ISIS `lronacpho` recommended below ~60° incidence `[LIT]` |
| Albedo / maturity contrast | Not modelable a priori; it is the signal that survives normalisation | — |
| Emission angle / off-nadir (NAC slews; TMC-2 ±25°) | Yes: parallax = relief × tan(e); needs DEM | SPICE |
| GSD, PSF/MTF | Yes: NAC MTF > 0.23 at Nyquist `[LIT]`; OHRC SNR ≈ 70 at 128 TDI `[LIT]`; TMC-2 SNR > 100 `[LIT]` | Instrument papers |
| Spectral response | Yes: OHRC 0.45–0.80 µm, TMC-2 0.4–0.9 µm pan, NAC ~0.4–0.75 µm, IIRS 0.8–5.0 µm in 250 bands `[LIT]` | Instrument papers |
| Thermal emission (IIRS ≥ ~3 µm) | Different physics: depends on temperature (incidence, thermal inertia), not reflectance | Chauhan et al. 2025; IIRS 4–5 µm used to correct 2–3.5 µm `[LIT]` |
| Temporal surface change | Negligible except new impacts and lander sites | `[FACT]` |
| Orbit/attitude error | Not predictable, but bounded: LRO NAC to LOLA registration accuracy ~18 px / 25 m reported `[LIT]`; OHRC anchoring to a NAC DTM achieved ~30 m horizontal `[LIT]`; TMC-2 ortho horizontal < 50 m `[LIT]` | — |

### 5.2 Consequences `[INFERENCE, HIGH]`

- Illumination is the one challenge for which the Moon offers a **known forward model**. Learning it from data throws away a prior that competitors will not have engineered.
- The geometry prior bounds the search to tens of metres, which is the strongest available defence against the coherent-wrong failure: a match set 64 px displaced is inside the prior's uncertainty only if the prior is worse than 64 px. At NAC scale (25 m ≈ 50 px undecimated) it usually is not.
- Handled by **modelling**: incidence/phase brightness, DEM-scale shading and shadows, parallax, GSD, PSF. Handled by **matching**: albedo structure, sub-DEM relief shading, residual model error. Handled by **rejection**: overlap < 20 %, terminator frames (incidence > 75°, D-029), thermal bands without a temperature model, missing geometry.

---

## 6. Systems formulation

Inputs: two products with labels (PDS4 XML, GeoTIFF, IIRS cube + geometry file), optional DEM, SPICE or archive corner geometry. Output: correspondence set with per-point covariance and inlier flags, local transform(s), registered product with NaN no-data, verdict with named evidence, provenance record, and the metrics the PS lists plus the ones the verdict actually uses. Constraints: CPU path mandatory, GPU optional; deterministic under a seed; offline; every number in a report traceable to an artefact file `[OURS, already enforced]`.

---

## 7. Existing research — the repository, verified

Read in full: all of `docs/`, `src/siim/`, `scripts/`, `tests/`, experiment READMEs, ledgers, git history (25 commits on `real-data-02-05-and-demo`). Verification was against artefact files and tests, not against the reports' prose.

| Stage | Claim in report | Verification against evidence | Classification |
|---|---|---|---|
| EXP-000 | Geometry layer exact to ~1e-13 px; C4 half-pixel bug pinned | `metrics.json` and `test_geometry.py` reproduce; contract tests present | **CONFIRMED** |
| EXP-001 | RootSIFT cliff at Δaz 30–45°; RMSE inverted in failure; count separates | Cliff location superseded by EXP-002 (terrain unrealistic, 89.55 % above repose); RMSE inversion holds; count separation was co-selected (n = 45) | **PARTIALLY CONFIRMED / OUTDATED** on cliff location |
| EXP-002 | 970× RANSAC fix; realistic terrain moves cliff to 15–30°; `n_inliers <= 8` validated on disjoint seeds; loop closure only GT-free detector of coherent wrong | Artefacts and addendum consistent; sensitivity table was mislabelled and corrected (D2, `objective3_ninliers_sensitivity.json`); fit RMSE AUC 0.4947 | **CONFIRMED** |
| EXP-003 | No representation met S1; mod-π worst; orientation assignment drifts ~1:1 with Δaz (post-hoc) | `exp003_representations.json` and loop-closure artefact consistent; the drift finding is post-hoc and held as D-024, not accepted | **CONFIRMED (null result)** |
| EXP-004 | Pre-registered | Part 1 frozen; no code | **UNRESOLVED (not started)** |
| RD-01 | First real pair | Tiles later shown 22.75 km apart, 0 km² shared (E-028/029) | **CONFIRMED as invalid acquisition** |
| RD-02 | Overlap from archive corners, no pixels | `verify_tile_overlap.py` pre-registered; MC over corner quantisation; bilinear error measured < 13.7 px in tests | **CONFIRMED** |
| RD-03 | Triplet A/B/C: 4 / 5365 / 4 inliers; loop 1201 px | Re-derivation script reproduces 54 quantities from tile bytes (`test_rederivation.py`, live on this machine) | **CONFIRMED** |
| RD-04 | Illumination attributed (D-040); frame identity weakened, not refuted (D-040-N1); six-edge separation by Δincidence | Artefacts reproduce; p = 0.0667 exact; azimuth does not order outcomes (post-hoc); phase collinear with incidence | **PARTIALLY CONFIRMED** — within the scope D-040 states, n = 6, not significant |
| RD-05 | Replication unresolved by data availability | Four empty screens preserved; zero admissible frames | **UNRESOLVED** |
| RD-06 | Photometric normalisation pre-registered | Part 1 frozen 2026-09-03; `normalise()` tested; no runner | **UNRESOLVED (not run)** |

Existing validated findings worth keeping (all `[OURS]`, HIGH): C1–C9 coordinate contract; fit RMSE excluded by measurement; `n_inliers <= 8` as an aggregate collapse detector (with its caveat that 93 % of its recall comes from total-collapse cells); loop closure detects per-edge coherent error and is blind to per-image gauge error (N1); coverage catches near-collinear fits the estimator admits; PDS4 byte-range ingestion with structural checks; matcher-independent overlap from archive corners; the 970× RANSAC fix; the scale probe (mare stops at 4×, highlands at 8×, all by detector starvation).

Existing refuted hypotheses (`HYPOTHESIS REFUTED`, `[OURS]`): polarity-agnostic (mod-π) representation as the illumination fix (ADR-0004); fit RMSE as correctness evidence; "8 separates the classes" as a law; held-out residual and split consistency as wrong-answer detectors; cycle consistency against symmetric error; "scale survives to 4×" in general (false on mare at 2×).

---

## 8. Required-paper analysis

For each: solves / does not solve / proven / claimed / reviewer attack / remaining gap. Confidence on each row is MEDIUM unless the full text was read; several papers were accessible only as abstracts and are marked.

**1. Comparative Evaluation of Traditional and DL Feature Matching using Chandrayaan-2 Data (arXiv 2509.04775, Sep 2025)** `[LIT]`
Solves: first side-by-side of SIFT, ASIFT, AKAZE, RIFT2, SuperGlue on real C2 cross-modality pairs (optical, IIRS, DFSAR; equatorial and polar), with a preprocessing pipeline (georeferencing, resolution alignment, intensity normalisation, CLAHE, PCA, shadow correction). Finding: SuperGlue lowest RMSE and fastest; classical methods degrade at the poles.
Does not solve: how correctness was established. **EVIDENCE INSUFFICIENT** — the abstract and indexing pages do not state what the RMSE is computed against, whether check points were independent of the matchers, or the pair count. Proven: relative ranking on their pairs. Claimed: generality. Reviewer attack: "RMSE against what?"; SuperGlue's non-commercial licence; pretrained weights on terrestrial data; no failure-detection analysis; polar results uncontrolled for incidence. Gap: no independent GT, no rejection, no scale-ladder analysis, no physics prior.

**2. SIFT-Based Automated Registration of C2 IIRS Hyperspectral Images (preprints.org 2025)** `[LIT]`
Solves: seleno-referencing IIRS (which lacks embedded map projection) to LRO WAC by SIFT after resampling; RMS < 1 IIRS pixel (80 m). Does not solve: illumination change (WAC mosaic is photometrically normalised, IIRS is not); sub-pixel; anything at OHRC/TMC scales. Attack: single-band choice; WAC 100 m ≈ IIRS 80 m so this is the easy rung; "RMS < 1 pixel" is a fit residual unless check points were independent (**EVIDENCE INSUFFICIENT**). Gap: IIRS→NAC (40:1 to 160:1) untouched.

**3. Deep Radiometric Normalization for Cross-Sensor Lunar Mosaics using TMC-2 (arXiv 2604.25208, Apr 2026)** `[LIT]`
Solves: cGAN (U-Net + PatchGAN) mapping TMC mosaics to a WAC-derived photometrically consistent reference; patch-based inference. Does not solve: registration (it assumes alignment); a learned normalisation can hallucinate structure. Attack: trained mapping is region- and illumination-specific; not a physical model; seams. Gap: radiometry for *matching* rather than mosaicking is untested; a physical normalisation with known geometry is the obvious control they do not report against (**EVIDENCE INSUFFICIENT** on baselines).

**4. Sub-metre Lunar DEM from C2 OHRC Multi-View (arXiv 2604.01032, 2026)** `[LIT]`
Solves: open-source ASP/ISIS pipeline for OHRC stereo from non-paired archives; DEMs at 24–54 cm; horizontal accuracy < 30 cm by planimetric feature matching against NAC hillshade; vertical RMSE 5.85 m vs NAC reference. Relevant facts: ALE 1.0 ships OHRC and TMC drivers; CSM models are required (legacy ISIS model failed) `[LIT]`. Does not solve: cross-sensor *image* correspondence; illumination change. Attack: 5.85 m vertical error at native resolution is large; "horizontal < 30 cm" rests on matching against a hillshade — exactly the DEM-render intermediary this plan proposes, so their validation method is our matching method. Gap: none of their matching is characterised vs Sun angle.

**5. Learning Illumination Invariant Features for Lunar South Pole (Georgakis, GaTech/JPL; Rothenberger et al., AIAA SciTech 2025-2073)** `[LIT]`
Solves: a training strategy for illumination-invariant matching under polar lighting, alongside LIMA, a correlation-based lighting-invariant matching algorithm for TRN; the 2026 follow-up stitches illumination-matched NAC mosaics (29 NAC images) that match a held-out image better than any single frame. Does not solve: cross-sensor, scale ladder; full text of the AIAA paper was not accessible (403) — **EVIDENCE INSUFFICIENT** on training data and metrics. Attack: TRN metrics (position error) are not registration metrics; polar-specific. Gap: the DEM-render intermediary is used, but no scale-dependence bound is stated.

**6. L2AMF-Net (Remote Sensing 2022, 14(20):5156)** `[LIT]`
Solves: patch descriptor for lunar TRN, 95.57 % matching accuracy on a lunar patch dataset; robustness to illumination, perspective, texture. Does not solve: detection, geometric verification, orbital cross-sensor. Attack: patch-classification accuracy is not registration accuracy; dataset construction and leakage unknown. Gap: no real orbital cross-sensor validation.

**7. Crater Neighborhood Structure Feature Matching (Remote Sensing 2025, 17(13):2302)** `[LIT]`
Solves: illumination-robust matching via detected craters and K-nearest-neighbour structure; new MiLOI dataset of 321 multi-illumination LROC pairs across latitudes; outperforms baselines on robustness. Does not solve: sub-pixel (crater centres are coarse); texture without craters; small tiles. Attack: depends on crater detector quality; accuracy limited to crater-centre localisation. Gap: no sub-pixel; but the *dataset* is the closest thing to a public multi-illumination lunar benchmark and should be requested/used.

**8. "Photometric-weighted invariant feature transform for planetary surface image registration under complex illumination"** — **EVIDENCE INSUFFICIENT.** No paper with this exact title was found in ADS, IEEE, ScienceDirect or arXiv searches. Nearest matches: Wu et al. 2018 (paper 10) and PhIT-Net (arXiv 1911.12641, photo-consistent image transform). Not cited as if it existed.

**9. Lunar Image Matching Based on FAST Features with Adaptive Threshold (CSPS 2018, Springer)** `[LIT]`
Solves: FAST + SURF + RANSAC homography; "errors < 0.2 px". Attack: the 0.2 px is a fit residual under a homography, which this repository has shown is not evidence of correctness; no illumination test. Gap: everything.

**10. Illumination Invariant Feature Point Matching for High-Resolution Planetary Images (Wu et al., P&SS 2018)** `[LIT]`
Solves: SIFT dominant-orientation histogram shows dual peaks under illumination change; adaptive Gaussian suppression levels it; cross-check + template refinement; 40–60 % more matches on Moon/Mars pairs with 20–180° illumination difference. Directly relevant to this repository's D-024 finding that orientation assignment drifts with azimuth `[OURS]`. Does not solve: total collapse regimes (their gain is relative); cross-sensor. Attack: "more matches" is not "correct registration". Gap: mechanism is consistent with EXP-003's post-hoc finding; a rendering-based prior would remove the cause rather than the symptom.

**11. MoonMetaSync (arXiv 2410.11118; IEEE 2024)** `[LIT]`
Solves: SIFT vs ORB vs IntFeat on TMC-2/OHRC patches from PRADAN; SyncVision package. Does not solve: illumination, scale ladder, GT. Attack: patch-level, metrics are match statistics. Gap: confirms that PRADAN data are obtainable by students, which removes the previous plan's excuse.

**12. Integrated Photogrammetric and Photoclinometric Approach (Liu & Wu, ISPRS JPRS 2019)** `[LIT]`
Solves: photoclinometry-assisted matching (PAM) producing pixel-wise matches under large illumination differences, using photometric stereo analysis; used at Chang'e-4/5 sites with NAC. Does not solve: cross-sensor; needs multiple images of the same site; heavy. Attack: accuracy "comparable to photogrammetry"; illumination invariance is via shape, which is exactly H0's mechanism but at DEM-refinement cost. Gap: this is the strongest prior art for H0 and must be cited as such.

**13. Multi-view LROC NAC SGM in Object Space (Ye et al., ISPRS 2020)** `[LIT]`
Solves: object-space SGM for multi-view NAC DEMs; alleviates orbiter positioning uncertainty. Relevance: object-space matching is the multi-view generalisation of "match through the ground". Gap: not a correspondence-under-illumination result.

**14–15. RIFT (TIP 2020) and RIFT2 (arXiv 2303.00319)** `[LIT]`
Solve: phase-congruency detection + maximum index map description, insensitive to nonlinear radiation distortion; RIFT2 ~3× faster with dominant-index rotation invariance. Do not solve: large scale differences (single scale by design); repetitive low-texture terrain; sub-pixel. Attack (from our own data): our PC-based arms starved on realistic mare `[OURS]`; paper 1 ranks RIFT2 below SuperGlue on C2. Gap: multimodal ≠ multi-illumination; RIFT's invariance targets radiometric mapping, not shadow migration.

**16. WSSF (IEEE 2024)** `[LIT]` — structure saliency via steerable second-order filters + edge confidence + phase; validated on 120 MRSI pairs; later applied to planetary DEM registration (paper 18). Gap: same as RIFT; no lunar illumination test.

**17. EPCFT (IEEE 2024/25)** `[LIT]` — phase congruency from Gaussian derivatives instead of log-Gabor for speed on large planetary images. Engineering contribution; useful if PC is retained as an engine.

**18. Multimodal Feature Matching for Multi-source DEM Registration (ISPRS Archives XLVIII-G-2025)** `[LIT]` — WSSF on rendered DEM products, Mars and Moon; preliminary. Relevance: shows DEM-as-image matching in planetary context. Gap: image-to-image via DEM not addressed.

**19. Feature-based MRSI Matching Benchmark (Jiang et al., ISPRS JPRS 2025)** `[LIT]` — benchmark of PSO-SIFT, LGHD, RIFT, RIFT2, HAPCG, COFSM, CMM-Net, RedFeat; taxonomy of learned strategies. No lunar data. Gap: lunar multi-illumination is absent from the benchmark landscape.

**20. SFA-Net (ISPRS JPRS 2025, code on GitHub)** `[LIT]` — SAM-guided edge structure + CNN local features with focused attention for MRSI. Attack: SAM on lunar terrain untested; compute. Gap: no planetary evaluation.

**21. "HOSSP"** — **EVIDENCE INSUFFICIENT.** No paper with that acronym located. Nearest: HOWP (ISPRS JPRS 2023, weighted phase orientation histogram, log-polar descriptor), RI-LPOH, HOMPC, MS-HLMO, MS-POFT (2025). Treated as the phase-orientation-histogram family.

**22. DeepSpace-ScaleNet (Remote Sensing 2022, 14(24):6339)** `[LIT]` — attention-based scale-ratio estimation for small-body images; trained on a virtual dataset. Relevance: scale ratio in our problem is *known from metadata*; estimating it is unnecessary except when metadata is missing (fallback only).

**23. Semantic-Aware Matching for Mars Rover Images (IEEE TGRS 2025)** `[LIT]` — Siamese transformer semantics to aid descriptors and outlier removal for rover images. Relevance: low; rover geometry differs.

---

## 9. Extended literature research (2024–2026, beyond the required list)

| Work | What it establishes | Use here |
|---|---|---|
| NAC-to-SLDEM registration via hillshade + ASIFT + RFM refinement + least-squares image matching `[LIT]` (Chinese lunar mapping group) | DEM rendered under image illumination, matched with ASIFT, refined to pixel-level LSM. Prior art for H0's mechanism. | Cite as prior art; our contribution must be the cross-sensor ladder test and the bound, not the mechanism |
| JPL LuNaMaps (NTRS 2022), LIMA (AIAA 2025-2073), LIMA mosaics (AIAA 2026-2244) | Reference maps rendered/selected for target Sun vector; correlation-based lighting-invariant matching; TRN metrics | Prior art; confirms rendering-based invariance works in practice on NAC |
| "A Robust DEM Registration Method via Physically Consistent Image Rendering" (Appl. Sci. 2026, 16(3):1238) | Irradiance-based rendering + template matching + elevation consistency for DEM-DEM registration (terrestrial) | Method pattern for consistency selection |
| Lunar-G2R (arXiv 2601.10449, 2026) | U-Net predicts spatially varying lunar BRDF from DEM via differentiable rendering; 38 % photometric error reduction on held-out Tycho region; CC BY 4.0 | Optional upgrade to the renderer's photometric model; evaluate, do not depend on |
| StereoLunar / LunarStereo (ICCV-W 2025, arXiv 2510.18172) | First open photorealistic ray-traced lunar stereo dataset from high-res topography and reflectance; MASt3R fine-tuned | Rendering-as-GT is accepted practice; MASt3R is CC BY-NC-SA (cannot ship) |
| Evaluation of open-source lunar image simulators (arXiv 2604.22296, 2026) | Compares simulators using OHRC/WAC/NAC-derived terrain | Choose renderer; full text needed |
| Cross-view geo-localization on planetary surfaces (arXiv 2606.29821, 2026) | Rendered lunar panorama/overhead benchmark, 10,438 views, CC BY 4.0 | Not orbital-orbital; skip |
| MINIMA (CVPR 2025), XoFTR, MatchAnything, RoMa; "Are Pretrained Matchers Good Enough for SAR-Optical?" (arXiv 2604.10217, CVPR-W 2026) | Zero-shot pretrained matchers reach ~3 px mean error on SAR-optical; protocol (tiling, robust filtering, tie-point metrics) matters | Learned engine arm; ADR-0001's 33× figure is from this SAR-optical preprint and does not transfer without EXP-006 |
| Licences `[FACT]`: LightGlue Apache-2.0; DISK Apache-2.0; ALIKED BSD-3; RoMa MIT (DINOv2 Apache-2); SuperPoint and SuperGlue non-commercial; MASt3R/DUSt3R CC BY-NC-SA | Which learned engines may ship | Ship LightGlue+DISK/ALIKED and RoMa only |
| Deep-learning crater TRN (arXiv 2606.14776, 2026) | Crater detection + Hungarian assignment + consensus outlier removal; recovers 5 km initial error to hundreds of metres; warns that detector must match training scale | Crater-graph as a coarse fallback engine |
| Wu et al. 2018 illumination-invariant SIFT; PhIT-Net | Orientation-histogram mechanism | Confirms D-024's mechanism; does not need EXP-004 to be re-derived |
| ISIS `lronacpho` (ISIS 7.1) `[FACT]`; Sato et al. 2014 Hapke maps; Hapke 2012 wavelength dependence; Hicks 2011 M3 photometric function | Physical normalisation with standard geometry i = 60°, e = 0°; recommended below ~60° incidence | Photometric tier; phase reddening means normalisation is band-dependent |
| IIRS Level-2 processing (Chauhan et al. 2025), IIRS photometric correction (Adv. Space Res. 2024), IIRS thermal correction (Icarus 2022) | Reflectance usable 0.8–2.0 µm with least thermal contamination; 2–3.5 µm needs thermal correction from 4–5 µm; geometry supplied as separate file | Multimodal band policy |
| Chandrayaan-2 PDS4 archive papers (LPSC 2022/2023) `[FACT]` | Raw and calibrated PDS4 for TMC2/OHRC/IIRS; derived DEM/ortho as GeoTIFF; ALE drivers for OHRC/TMC; ASP has a Chandrayaan-2 example | Ingestion design |
| TMC-2 DEM/ortho quality (JISRS 2023) `[LIT]` | DEM RMS < 25 m vs LOLA; ortho horizontal < 50 m | Prior uncertainty for TMC-2 rung |
| OHRC geodetic anchoring (arXiv 2602.14993) `[LIT]` | ~30 m horizontal after anchoring to NAC DTM; CSM required | Prior uncertainty for OHRC rung |
| LRO orbit error from multi-coverage NAC (Geo-spatial Inf. Sci. 2024); NAC-LOLA co-registration 18.3 px / 25 m `[LIT]` | Prior uncertainty for NAC | Search-window sizing |
| Uniform tie-point selection: ANMS (Bailo et al. 2018), stratified random selection in RANSAC (2020), block-based area matching `[LIT]` | Uniformity improves RANSAC and accuracy | Spatial balancing module |
| Sub-pixel phase correlation limits ~0.1 px with PSF-aware downsampling (Landsat, RS 2017); multi-scale phase correlation (2026) `[LIT]` | Achievable sub-pixel bound with area methods | Refinement tier |
| Kaguya TC (10 m), MI (20 m VIS / 62 m NIR, 9 bands), Diviner (150 m+) `[FACT]` | Open proxies for TMC-2, IIRS reflectance bands and thermal | Proxy data plan, explicitly labelled |

---

## 10. Research-gap matrix

Legend: S solved · P partially · W weakly · U untested · C contradictory · O open. Columns: Illum = illumination; Sc = scale; VP = viewpoint; MM = multimodality; Ter = low-texture terrain; SP = sub-pixel; GT = independent ground truth; SD = spatial distribution; FP = false-positive / coherent-wrong testing; IV = independent verification; Unc = uncertainty; RL = real lunar validation; C2 = Chandrayaan-2 validation; Cost; Lic = licence for shipping.

| Method / paper | Illum | Sc | VP | MM | Ter | SP | GT | SD | FP | IV | Unc | RL | C2 | Cost | Lic |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SIFT/RootSIFT (ours B1) | W (cliff 15–30° synth; 12–39° real) | P (4–8×) | P | U | W | W | — | W | O | O | U | S (6 edges) | U | low | OK |
| ASIFT/AKAZE/ORB (ours B2/B3) | W | P | P | U | W | W | — | W | O | O | U | U | P (paper 1) | low | OK |
| RIFT / RIFT2 | P (NRD) | W | P | P | W (starves on mare, ours) | W | — | W | U | U | U | P (paper 1) | P | med | OK (MATLAB/Py) |
| WSSF / HOWP / EPCFT family | P | W | P | P | U | W | — | W | U | U | U | U | U | med | mixed |
| Wu 2018 illum-SIFT | P (20–180°, more matches) | W | P | U | W | W | manual | U | U | U | U | S | U | low | n/a |
| CNSFM crater graph (2025) | S (robust) | P | P | U | needs craters | W | dataset | W | P | U | U | S (321 pairs) | U | med | n/a |
| PAM photoclinometry (2019) | S | U | S (via DEM) | U | S | P | photogrammetry | S | P | P | U | S | U | high | n/a |
| NAC→SLDEM hillshade+ASIFT+LSM | S | P | S | U | P | P | DEM | P | U | P | U | S | U | med | n/a |
| LIMA / LuNaMaps (JPL) | S (TRN) | P | P | U | P | U | TRN truth | U | P | P | P | S | U | med | n/a |
| SuperGlue / SuperPoint | P | P | P | P | P | W | — | W | U | U | P (scores) | P (paper 1) | P | GPU pref | **non-commercial** |
| LightGlue + DISK/ALIKED | P | P | P | U | U | W | — | W | U | U | P | U | U | CPU ok | Apache/BSD |
| RoMa / MINIMA-RoMa | P | P | S | P (VIS-SAR/IR) | U | P (dense) | — | S (dense) | U | U | P (certainty) | U | U | GPU | MIT |
| XoFTR / MatchAnything | P | P | P | P | U | P | — | S | U | U | P | U | U | GPU | check |
| MASt3R fine-tuned (StereoLunar) | P | P | S | U | P | P | rendered | S | U | U | P | P | U | GPU | **NC** |
| L2AMF-Net / Georgakis | S (claimed) | P | P | U | P | U | patch labels | U | U | U | U | P | U | GPU train | n/a |
| cGAN radiometric normalisation (TMC) | P (mosaic) | — | — | P | — | — | — | — | U | U | U | S | S | GPU | n/a |
| ISIS lronacpho / Hapke | P (< 60° i) | — | — | band-dep. | — | — | — | — | — | — | — | S | P (IIRS) | low | public domain |
| Our verification protocol (loop closure, coverage, rule) | — | — | — | — | — | — | synthetic GT | S | S (constructed) | P (geometry) | P | P | U | low | ours |

**Capability classification for SIH26166**

| Capability | Status | Basis |
|---|---|---|
| Overlap and prior transform from geometry | **SOLVED** | RD-02 `[OURS]`, standard in planetary practice `[LIT]` |
| Illumination invariance at coarse GSD with DEM support | **PARTIALLY SOLVED** (TRN, NAC-to-DEM) | `[LIT]`; not quantified for cross-sensor ladder |
| Illumination invariance at sub-metre GSD without a fine DEM | **OPEN PROBLEM** | our cliff `[OURS]`; learned methods claim, weakly validated `[LIT]` |
| Scale to 320:1 | **WEAKLY SOLVED** (starvation is the cause; degrade-to-coarse is standard) | scale probe `[OURS]`; paper 2 (IIRS↔WAC) |
| Viewpoint under relief | **PARTIALLY SOLVED** (DEM orthorectification standard) | `[LIT]` |
| Pan ↔ NIR reflectance bands | **PARTIALLY SOLVED** | shared shading structure `[INFERENCE]`; paper 2 |
| Pan ↔ thermal (IIRS > 3.5 µm) | **UNTESTED** | no lunar optical-thermal registration paper found |
| Sub-pixel under illumination change | **OPEN / CONTRADICTORY** (papers report fit residuals) | E-008 `[OURS]` |
| Spatial uniformity enforced with accuracy accounting | **WEAKLY SOLVED** | ANMS `[LIT]`; coverage metric `[OURS]` |
| Coherent-wrong detection without GT | **PARTIALLY SOLVED** (loop closure; geometry prior) with a known null space | `[OURS]` |
| Independent GT for real lunar pairs | **OPEN** (rendered GT accepted; real GT only at tens of metres) | `[LIT]` |
| Chandrayaan-2 validation of any of the above | **UNTESTED** here; two external papers with weak GT | `[LIT]` |

---

## 11. Old-plan failure audit

The previous plan is rated by its author as 3/10. That rating is fair for capability and unfair for methodology. Post-mortem, without politeness:

1. **The architecture was chosen before the gap was proven.** ADR-0001 ("the matcher is a replaceable part; the protocol is the contribution") rests on one SAR-optical preprint (arXiv 2604.10217) and was never tested on lunar data (EXP-006 unstarted). The thesis was a design rationale dressed as a hypothesis.
2. **The strongest lunar-specific prior was ignored.** Every product carries SPICE geometry and the Moon has global DEMs. The plan used geometry only to check overlap and to corroborate, never to *condition* the matcher. The JPL TRN literature and the Chinese NAC-to-SLDEM literature did this years ago `[LIT]`. Literature coverage was incomplete in exactly the direction that mattered.
3. **Illumination was attacked at the wrong layer.** EXP-003 tested two hand-built descriptors and one phase-congruency variant against a synthetic cliff. The literature's stronger classical candidates (RIFT2 proper, HOWP, Wu 2018 suppression, crater-graph) and any learned matcher were absent. A null result over weak arms is weak evidence.
4. **Confirmation bias in the real-data track.** Five stages, four frames, one region, one instrument, one matcher. Each stage refined the measurement of RootSIFT's failure instead of trying anything that might succeed. The replication stage (RD-05) failed on a filter (H5 orientation) whose necessity came from the matcher's own weakness.
5. **Chandrayaan-2 data were never obtained.** PRADAN signup is free `[FACT]`; MoonMetaSync's student authors used it `[LIT]`. "ISSDC auth" was an unforced blocker. The project's title contains the word Chandrayaan-2 and its evidence contains zero Chandrayaan-2 pixels.
6. **Multimodality was never defined or attempted.** All pairs are NAC↔NAC pan.
7. **Scale was measured, not handled.** D-005 (GSD normalisation) is designed and unbuilt despite being the cheapest requirement to satisfy.
8. **Sub-pixel was never claimed and never validated.** Correct, but the PS asks for it.
9. **Uniform distribution was measured, not enforced.**
10. **Over-investment in integrity tooling relative to capability.** Roughly a third of the test suite guards the demo's provenance. Necessary, but built before there was a capability to protect.
11. **The synthetic terrain generator is single-source** and tuned to LOLA slope medians; a physically rendered dataset from real DEMs (as StereoLunar does) would have been both more realistic and closer to the eventual method.
12. **Benchmark sufficiency:** n = 6 real edges; p = 0.0667. The plan knew one more failing edge would reach significance and did not acquire it.
13. **Metrics vulnerable to gaming?** No — this is the part that was done right. Fit RMSE exclusion, disjoint calibration/validation, pre-registration, and loop closure are all sound and survive review.
14. **Could a competitor produce the same system easily?** The verification layer, no. The matching capability, yes — it is RootSIFT.
15. **What would an ISRO reviewer reject?** The claim of illumination attribution at n = 6 without a physical model; the absence of Chandrayaan-2 data; the absence of any working method above 12° Δincidence.

**Verdict:** methodology 8/10, capability 2/10, strategic direction 3/10. Keep the methodology, replace the direction.

---

## 12–15. Existing repository findings, validated findings, refuted hypotheses, remaining unknowns

Sections 12–14 are the tables in §7. Remaining unknowns `[UNKNOWN]`:

- The location of the illumination cliff on real data between 11.73° and 38.85° Δincidence, and its dependence on Δazimuth (never controlled on real data).
- Whether any learned matcher (LightGlue/DISK, RoMa, MINIMA) succeeds on the four failing real edges zero-shot. *Never tried.*
- Whether DEM-conditioned matching succeeds on those edges at any GSD rung. *Never tried.*
- Whether NAC DTMs exist over the Mare Serenitatis window used so far (LROC RDR shapefile lists coverage `[FACT]`; not checked).
- OHRC/TMC-2/IIRS raw geolocation error on real products from PRADAN.
- The photometric residual after Lommel-Seeliger normalisation on real NAC at 70° incidence.
- The behaviour of any method on IIRS thermal bands.

---

## 16. Central scientific question

**Given that the Moon's topography and illumination geometry are known for every product, how much of the correspondence problem posed by SIH26166 is left once that knowledge is used, and can the remainder be solved to sub-pixel accuracy at the coarser sensor's GSD with a verifiable, rejectable output?**

Hypothesis H0 (§1) is its testable form. Sub-hypotheses:

- **H1 (rendering removes the cliff at coarse rungs).** At GSD ≥ 5 m with SLDEM2015/TMC-2 DEM support, the DEM-render arm registers the currently failing real edges (Δinc 39–52°) under the unchanged `n_inliers <= 8` rule. *Prediction: MET.* Confidence MEDIUM.
- **H2 (bound).** At GSD ≤ 1 m with only SLDEM support, the render arm fails and the failure is explained by the DEM's inability to resolve the matched features; supplying a NAC DTM (2–5 m) restores success at that rung. *Prediction: first half MET, second half MET at 2 m DTM, UNKNOWN at 0.25 m.* Confidence MEDIUM/LOW.
- **H3 (learned zero-shot is not enough alone).** LightGlue/DISK and RoMa zero-shot improve on RootSIFT but do not exceed the render arm at Δinc > 40°. *Prediction: uncertain; this is the experiment competitors will win if H3 is false.* Confidence LOW.
- **H4 (photometric normalisation alone is insufficient).** Per-frame Lommel-Seeliger normalisation (RD-06 as frozen) changes no real outcome, because it removes brightness, not shadow migration. *Prediction: S1 NOT MET, S3 MET.* Confidence HIGH. Run it anyway; it is the control.
- **H5 (sub-pixel is achievable only after illumination conditioning).** Area-based refinement on the raw pair at Δinc > 30° is biased by shading asymmetry by more than 0.5 px; on the render-conditioned pair it is not. Confidence MEDIUM.

---

## 17. Sensor analysis `[FACT/LIT]`

| Sensor | GSD | Swath | Band | Geometry | Notes for pairing |
|---|---|---|---|---|---|
| OHRC | 0.25 m (100 km), 0.16–0.18 m at 63–70 km | 3 km | 0.45–0.80 µm pan | 12k-px TDI CCD, RC telescope, f = 2046 mm; SNR ≈ 70 @128 TDI; up to 25° pitch stereo | Finest rung; raw/calibrated PDS4 only, no derived; CSM camera model needed; ~30 m absolute after anchoring |
| TMC-2 | 5 m | 20 km | 0.4–0.9 µm pan | fore/nadir/aft ±25°, three chains; SNR > 100; L2 DEM + ortho GeoTIFF | DEM RMS < 25 m vs LOLA; ortho horizontal < 50 m; its own DEM (~10 m) is a usable render source |
| IIRS | 80 m | 20 km | 0.8–5.0 µm, 250 bands, 20–25 nm | no embedded projection; separate geometry file; 0.8–2.0 µm least thermal; 2–3.5 µm needs thermal correction; ≥ 4 µm emission | Coarsest rung; band policy is a physics decision |
| LRO NAC | 0.5 m (50 km), ~1–2 m in later orbits | 2.5 km (L+R 5 km) | ~0.4–0.75 µm pan | 5064 px line-scan; MTF > 0.23 at Nyquist; slews to tens of degrees; 52,224 lines | Reference; NAC DTMs at 2–5 m where they exist; NAC-LOLA ~25 m |
| LRO WAC | 100 m | 60 km | 7 bands 0.32–0.69 µm | photometrically normalised global mosaic | IIRS-scale reference; paper 2 used it |
| Kaguya TC / MI | 10 m / 20 m VIS, 62 m NIR | — | pan / 9 bands to 1.55 µm | ortho and DEM products public | **Proxies** for TMC-2 and IIRS reflectance bands when C2 data are unavailable; labelled as proxies |
| Diviner | 150–1300 m | — | thermal IR | — | Proxy for the thermal modality |

**Scientifically sensible pairings and ratios:** OHRC↔NAC 2–8:1 (both fine, illumination is the problem); TMC-2↔NAC 5–10:1 (NAC degraded to 5 m; DEM support adequate); IIRS↔NAC 40–160:1 (NAC degraded to 80 m; SLDEM fully resolves; IIRS is the coarse image so "sub-pixel" means < 80 m); IIRS↔TMC-2 16:1; OHRC↔IIRS 320:1 (only meaningful as OHRC block-averaged to 80 m; an OHRC frame is ~40 × 150 IIRS pixels, so this is patch-in-image localisation, not general registration). **Not sensible:** matching at the finer GSD in any pairing.

---

## 18. Illumination analysis

`[FACT]` Incidence, emission, phase and sub-solar coordinates are published per product; per-pixel incidence follows from the DEM normal. `[OURS]` On six real NAC edges over mare, Δincidence separates success from failure perfectly (0.96°, 11.73° succeed; 38.85°–51.54° fail), p = 0.0667; Δazimuth does not order the outcomes; Δphase is collinear with Δincidence (near-nadir). `[LIT]` The literature's cures fall in three classes: (a) descriptor-level invariance (Wu 2018, RIFT family, learned) — partial; (b) shape-based (PAM, SfS, DEM rendering, LIMA) — effective where topography is known; (c) radiometric normalisation (lronacpho, cGAN) — removes brightness trends, not shadow geometry.

**Controlled experiment design (mandatory).** Separate illumination from frame identity, viewpoint and scale: use ≥ 3 frames per site so that every frame appears on both sides; hold emission < 5°; hold GSD by degrading; vary Δinc at two Δaz bins; report per site, never pooled; label outcomes with the frozen rule. Rendered-GT experiments vary Sun azimuth and elevation independently on the *same* DEM, which is the only way to get an azimuth-controlled result at all. An azimuth-controlled real pair does not exist in the current data `[OURS]`.

---

## 19. Scale analysis

`[OURS]` The unmodified baseline holds to 4× on mare and 8× on highlands; every failure beyond is detector starvation (mare yields zero keypoints at 128 px). `[INFERENCE, HIGH]` Therefore scale is a sampling problem: degrade the fine image with the coarse sensor's PSF to the coarse GSD, match there, express sub-pixel in coarse pixels. `[LIT]` PSF-aware downsampling improves sub-pixel registration (Landsat study). **Envelope:** every PS rung ≤ 320:1 is reachable by degradation; what is lost is that the fine image's *own* pixel accuracy cannot exceed the coarse image's, which the PS wording ("sub-pixel accuracy of the source image") makes ambiguous and the deliverable must define explicitly. `RECOMMENDATION: KILL` any scale-estimation network (DeepSpace-ScaleNet style): the ratio is metadata.

---

## 20. Viewpoint analysis

Parallax error of a global 2D model ≈ `Δh · tan(e)` where `Δh` is relief within the tile. NAC at 20° slew over 100 m relief: 36 m ≈ 72 px at 0.5 m. TMC-2 fore/aft at 25° over 100 m: 47 m ≈ 9 px at 5 m. OHRC stereo at 25°: same 47 m ≈ 190 px at 0.25 m. `[INFERENCE, HIGH]` Global similarity/affine/homography are valid only for near-nadir pairs over low relief or for small tiles; otherwise orthorectify both images onto the DEM (the map-projected "ortho" products TMC-2 L2 already are `[FACT]`) and match in map space, where the residual is the DEM's own error. The pipeline must select the model by residual structure, not by default.

---

## 21. Multimodal analysis

Define modality by the physics of the measured quantity. Pan (OHRC/TMC-2/NAC) and IIRS 0.8–2.5 µm all measure reflected sunlight; they differ by albedo spectrum (broad 1 and 2 µm pyroxene bands, red slope, maturity) and mild wavelength dependence of the phase function (phase reddening `[LIT]`). Shared structure: topographic shading, which is band-independent to first order. This is **weakly multimodal**: a locally monotonic intensity mapping plus albedo-contrast differences. IIRS ≥ 3.5 µm measures thermal emission whose spatial structure follows temperature (insolation history, thermal inertia, rock abundance): **genuinely multimodal**; shares topography through insolation but with a time lag and sign changes at shadow edges. Policy: reflectance bands are matched as pan after band averaging (SNR) and photometric normalisation; thermal bands require structural descriptors (phase congruency, gradient magnitude) and are reported as a separate envelope; 2–3.5 µm only after thermal correction using 4–5 µm `[LIT]`. `[UNKNOWN]` how well any method performs on thermal bands; EXP-009 measures it.

---

## 22. Terrain analysis

`[OURS]` Mare is information-poor: 70× fewer keypoints than highlands at equal slope statistics; it fails first on every axis. `[LIT]` MiLOI spans latitudes; polar terrain has long shadows. `[INFERENCE]` DEM rendering helps least on mare (little relief to render) and most on highlands and craters; on mare the surviving signal is albedo (rays, ejecta, maturity), which photometric normalisation preserves and rendering does not model. So the tiers are complementary: rendering for relief, normalisation for albedo. The benchmark must stratify by regime.

---

## 23. Sub-pixel analysis

**Definition adopted.** A registration is sub-pixel accurate if the error on *independent* check points (not the fitted correspondences), measured in the coarser image's pixels, has median < 0.5 px and the 95 % confidence interval excludes 1 px. `[OURS]` A fit residual of 1e-13 px accompanied a 797 px error; fit residuals are excluded. `[LIT]` Area-based methods (phase correlation with PSF-aware handling, ECC, least-squares matching) reach ~0.1 px under matched illumination. `[HYPOTHESIS H5]` Under illumination change, shading-edge migration biases area-based refinement; the bias is removed only when both sides share illumination (render-conditioned). Validation: rendered-GT pairs for the illumination axis; self-warp of real images for the interpolation axis; held-out manually verified points for the final claim.

---

## 24. Spatial distribution analysis

Uniformity serves two purposes: the transform is constrained everywhere (worst-case local error bound, ADR-0006 `[OURS]`) and RANSAC is more efficient (SRS `[LIT]`). Compare grid bucketing, ANMS (SSC), farthest-point, and confidence-aware selection. `[OURS]` Coverage metric `max_uncovered_disc_ratio` catches near-collinear fits the estimator admits. Decision: enforce ANMS-style selection *before* RANSAC, report coverage in the verdict, and measure the accuracy cost on rendered GT (expected small). Uniformity must not be enforced by lowering the match threshold in empty regions; empty regions are reported as such.

---

## 25. The coherent-wrong problem

Pattern: many matches, low residual, strong consensus, wrong place. `[OURS]` Constructed on synthetic data (lattice shift, 64 px); held-out residual and split consistency are blind; loop closure detects per-edge error at 1.000/0.000 and is exactly invariant to per-image gauge error (N1). Independent verifiers and whether the same failure fools them:

| Verifier | Fooled by a coherent shift? | Fooled by per-image gauge error? | Cost |
|---|---|---|---|
| Geometry prior (SPICE + corners) with its uncertainty | No, if shift > prior uncertainty (≈ 25–50 m on NAC; 30–50 m on C2) | Partly — it *is* the gauge, so it detects per-image error directly `[OURS verdict docstring]` | none |
| DEM-render consistency (does the registered image agree with the render at the claimed location?) | No | No | one render |
| Loop closure (≥ 3 views) | No | Yes | one extra edge |
| Held-out check points (independent feature family, e.g. crater centres vs SIFT) | Yes if both families lock onto the same repetition | Yes | low |
| Coverage | Only for clustered/collinear cases | Yes | none |
| Transform stability under subsampling | Yes | Yes | low |
| Physical plausibility (scale vs SCALED_PIXEL, rotation vs north azimuth) | Partly | No for scale | none |

Decision: the verdict requires at least one verifier from the first three; the rest are supporting. Rejection is a deliverable, not a failure.

---

## 26. Evaluation methodology

Reject as sole evidence: RMSE of the fit, inlier count, inlier ratio (all reported because the PS lists them; none decides). Adopt: endpoint error on dense grids vs rendered GT; error on independent check points on real pairs; success rate under the frozen rule; false-acceptance and false-rejection rates of the verdict on calibration/validation splits; robustness curves vs Δinc, Δaz, scale ratio, relief; uncertainty calibration (reported σ vs realised error); runtime. **Gap in evaluation itself:** no lunar registration paper found reports independent-GT accuracy together with a rejection rate; that gap is one of the three contributions.

---

## 27. Ground-truth strategy

| Source | Proves | Does not prove | Bias |
|---|---|---|---|
| Rendered pairs from real DEM under two Suns | Exact correspondence; illumination physics to the renderer's fidelity | That real images behave the same (simulator gap) | Renderer's photometric model; DEM resolution |
| Real image self-warp (known transform) | Interpolation/sub-pixel accuracy of the estimator | Anything about illumination or modality | Same texture both sides |
| Geometry-predicted correspondences (SPICE + DEM) | A bound: disagreement beyond the geometry budget is wrong | Sub-pixel correctness (budget is tens of metres) | Ephemeris/attitude error; corner quantisation |
| Loop closure over ≥ 3 views | Per-edge consistency | Per-image gauge error | Null space N1 |
| Manually verified tie points (crater rims, boulders) | Accuracy at ~0.5–1 px on a few dozen points | Distribution-wide accuracy | Human selection favours distinct features |
| Photogrammetric control (NAC DTM, LOLA, jigsaw) | Absolute geodetic accuracy to ~2–25 m | Sub-pixel | Reference's own error |
| Existing external datasets (MiLOI 321 pairs; LunarStereo) | Comparability with literature | GT quality unknown until inspected | Their construction |

Primary GT for illumination claims: rendered pairs, with the simulator gap **measured** (render vs real image agreement at the same geometry) and reported as a term. Primary GT for real-pair accuracy: manually verified held-out points plus geometry bound. Nothing else is called ground truth.

---

## 28. Dataset strategy

Splits by **site**, never by tile: calibration (thresholds), development, validation, held-out test (frozen, opened once), blind test (ISRO's set, whatever it is), adversarial (non-overlapping pairs, lattice terrain, terminator frames, corrupt labels, thermal bands). Leakage controls: no site within 50 km of another split's site; no repeat acquisitions of a split's ground in another split; illumination and latitude stratified; instrument families balanced. Sites: candidate list built from the LROC NAC DTM shapefile (multi-illumination NAC coverage + DTM), Chandrayaan-3 landing region (OHRC + NAC DTM exist `[LIT]`), Apollo/Chang'e sites (NAC DTMs, repeated coverage), plus mare and highland controls. Proxies (Kaguya TC/MI, WAC, Diviner) are a separate labelled tier and never reported as C2 results.

---

## 29. Candidate methods

Formulations A–R from the brief, assessed:

| Formulation | Assessment | Role |
|---|---|---|
| A classical features | Measured; fails above ~12–30° Δinc | Baseline B1 |
| B illumination-invariant structural (RIFT2, HOWP, PC) | Partial; starves on mare | Engine option for thermal modality |
| C multimodal structural | Same family | Same |
| D learned local features (LightGlue+DISK/ALIKED) | Licensable; untested on lunar | Engine option; H3 arm |
| E learned dense (RoMa, MINIMA-RoMa) | MIT; strong zero-shot elsewhere; GPU-heavy on CPU | Engine option; H3 arm |
| F hybrid | Yes — physics + any engine | GAPC |
| G coarse-to-fine | Yes — GSD ladder is coarse-to-fine by construction | GAPC |
| H geometry-assisted | Yes — prior transform and search bound | GAPC layer 1 |
| I DEM-assisted | Yes — render + orthorectify | GAPC layer 3 |
| J physics-conditioned | Yes — the hypothesis | GAPC core |
| K multi-view | Yes for verification (loop closure) | GAPC layer 5 |
| L uncertainty-aware | Yes — per-correspondence covariance from local correlation curvature and residual bootstrap | GAPC |
| M registration + rejection | Yes — existing verdict engine | GAPC |
| N adaptive selection | Limited: choose tier by DEM-resolution/GSD ratio and by band physics, deterministically | GAPC policy |
| O ensemble/fallback | Yes: crater-graph coarse fallback when both fine engines fail | GAPC |
| P graph-based | Crater neighbourhood structure (CNSFM) as fallback | Fallback |
| Q image-to-surface | Yes — it is the mechanism of layer 3 | GAPC |
| R probabilistic | Partially — uncertainty and verdict; full Bayesian registration not justified | — |

Answer to the brief's question: the contribution is **a better formulation** (physics-conditioned) **plus a verification system**; not a better matcher, not a benchmark alone, and not an adaptive selector.

---

## 30. Candidate architectures

**A1 — Pure learned zero-shot (LightGlue/DISK or RoMa) + robust estimation + our verdict.** Mechanism: pretrained invariance. Novelty: none (paper 1, MINIMA). Strength: fastest to build; likely wins at moderate Δinc. Weakness: no lunar training; unknown at > 40°; no physics; GPU preference. Evidence: paper 1's SuperGlue result. Difficulty: low. Licence: OK if LightGlue/DISK/RoMa. Failure modes: coherent-wrong on repetitive mare; scale ladder must still be handled outside. Competition risk: every team will have this.

**A2 — Classical structural (RIFT2/HOWP) + physics-free protocol (the old plan, upgraded).** Novelty: none. Evidence: our own null results. `RECOMMENDATION: KILL` as the primary line.

**A3 — GAPC: geometry-anchored, physics-conditioned, engine-agnostic, verified.** Mechanism: §4. Novelty: the ladder test and bound (potential research contribution); the verification (engineering, partly validated). Strength: uses what competitors will skip; every layer is independently testable; degrades gracefully to A1 when no DEM. Weakness: engineering breadth (SPICE, DEM, renderer); weakest at the OHRC rung. Evidence: TRN and NAC-to-SLDEM literature; RD-04 attribution. Difficulty: medium. Compute: CPU. Licence: all public-domain/Apache/MIT. Failure modes: DEM artefacts render false structure; photometric model error at high incidence; ephemeris error larger than expected.

**A4 — Lunar-specific learned matcher trained on rendered pairs (StereoLunar-style fine-tune of a licensable backbone).** Mechanism: learn the residual after physics. Novelty: adaptation. Strength: could close the OHRC rung. Weakness: training data must be rendered (so needs A3's renderer anyway); GPU; leakage risk; MASt3R is NC so backbone must be RoMa/LightGlue; evaluation must be on real held-out pairs. Difficulty: high. Timeline risk: high. Role: Phase-4 extension *after* A3's renderer exists.

**A5 — Image-to-DEM absolute georeferencing only (each image independently), correspondence by transitivity.** Mechanism: classical planetary practice (hillshade + ASIFT + LSM `[LIT]`). Novelty: none. Strength: absolute geolocation; coherent-wrong impossible at DEM scale. Weakness: image-to-image sub-pixel not guaranteed; fails where DEM is coarse relative to image. Role: it *is* A3's layer 3 without layers 2, 4, 5.

**A6 — Crater-graph structural matching (CNSFM).** Mechanism: topology of detected craters. Strength: illumination-robust by construction; works at IIRS/TMC scales. Weakness: coarse accuracy; crater-free mare; detector training. Role: fallback engine and independent feature family for held-out verification.

**A7 — Photoclinometry-assisted dense matching (PAM).** Mechanism: shape-and-albedo from shading between the images themselves. Strength: pixel-wise, illumination-invariant, published on NAC. Weakness: needs ≥ 2 views of the same site with usable stereo, heavy, not cross-sensor at 320:1. Role: upgrade path for the OHRC rung; not for the hackathon horizon.

---

## 31. Candidate comparison matrix

Scores 1–5 (5 best). Evidence level: A measured here or in strong literature; B literature claim; C inference.

| Candidate | Sci. validity | Novelty | Illum | Scale | VP | MM | Terrain | Sub-px | Verif. | Reject | Compute | Data need | Repro | Licence | Impl. risk | Comp. risk | Evidence | **Overall** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 learned zero-shot | 3 | 1 | 3 | 2 | 3 | 3 | 3 | 2 | 4 (ours) | 4 | 3 | 1 | 4 | 4 | 5 | 1 | B | 3.0 |
| A2 classical+protocol (old) | 3 | 1 | 1 | 2 | 2 | 2 | 1 | 2 | 5 | 5 | 5 | 1 | 5 | 5 | 5 | 2 | A | 2.6 |
| **A3 GAPC** | 5 | 3 | 4 | 5 | 5 | 3 | 3 | 4 | 5 | 5 | 4 | 3 | 4 | 5 | 3 | 4 | A/B | **4.2** |
| A4 lunar-trained learned | 3 | 3 | 4 | 3 | 3 | 3 | 3 | 3 | 4 | 4 | 1 | 5 | 2 | 3 | 1 | 3 | C | 2.9 |
| A5 image-to-DEM only | 4 | 1 | 4 | 4 | 5 | 2 | 2 | 2 | 4 | 5 | 4 | 3 | 4 | 5 | 3 | 3 | A | 3.4 |
| A6 crater graph | 3 | 2 | 5 | 3 | 3 | 3 | 1 | 1 | 3 | 3 | 3 | 3 | 3 | 4 | 3 | 3 | B | 2.9 |
| A7 PAM | 4 | 2 | 5 | 1 | 5 | 1 | 4 | 4 | 3 | 3 | 1 | 4 | 2 | 4 | 1 | 4 | B | 2.8 |

Weights used for the overall: scientific validity 2, illumination 2, verification 1.5, rejection 1.5, novelty 1, everything else 1. A3 leads because it is the only candidate that scores ≥ 4 on validity, scale, viewpoint, verification and rejection simultaneously; its novelty score is honest at 3.

---

## 32. Competitor simulation

- **Team A (elite classical/photogrammetry).** ISIS + ASP; jigsaw bundle adjustment to LOLA; orthorectified products matched by NCC/LSM; will report geodetic accuracy in metres. Strong on viewpoint and absolute georeferencing; weak on illumination at fine scale; unlikely to have a rejection rule or independent GT beyond LOLA.
- **Team B (elite deep learning).** LightGlue/LoFTR/RoMa/MINIMA, maybe fine-tuned on NAC crops with self-supervised warps; GPU demo; will report inlier counts and RMSE. Strong at moderate Δinc; brittle at 320:1 without a ladder; likely to show a coherent-wrong failure without knowing; licence exposure (SuperGlue).
- **Team C (elite planetary remote sensing).** Photometric normalisation, band selection, crater-based matching, careful IIRS handling; will know PRADAN and the archives; may use rendering for TRN-style coarse alignment. Closest to us; weaker on verification.
- **Team D (hybrid lab).** Physics preprocessing + learned matcher + bundle adjustment; the most dangerous.

**If they have a better matcher, what still gives us an advantage?** (1) The geometry prior and DEM conditioning make the matcher's job smaller, so "better matcher" gains shrink; (2) a verdict that can say REJECTED with named evidence, which no team will show on stage because it looks like failure and is in fact the deliverable a mission needs; (3) the pre-registered, leakage-controlled evaluation, which turns "our RMSE is lower" into a question the judge can ask them; (4) a working PDS4 byte-range ingestion of real archive products with structural checks. These are durable because they are not a matcher.

---

## 33. Novelty audit

| Proposed contribution | Nearest prior art | Classification | Defensibility (1–5) |
|---|---|---|---|
| DEM-rendered illumination-matched intermediary for correspondence | NAC→SLDEM hillshade+ASIFT+LSM; LIMA/LuNaMaps; PAM | **KNOWN** mechanism | 1 as a method |
| Cross-sensor scale-ladder test of DEM-conditioned invariance with the DEM-resolution bound as a pre-registered prediction | None found for OHRC/TMC/IIRS/NAC | **POTENTIAL RESEARCH CONTRIBUTION — GENUINELY NOVEL ONLY IF VERIFIED** | 3 (4 if EXP-007 confirms H1 and H2) |
| Fit-residual exclusion by measurement; frozen failure rule; loop closure with stated null space; coverage bound | Individual pieces known in SfM/photogrammetry | **ENGINEERING / EVALUATION CONTRIBUTION**, validated here | 4 |
| Geometry-prior-based coherent-wrong rejection with uncertainty budget | Standard in TRN as search bounds; not reported as a registration verdict | **ADAPTATION** | 3 |
| Leakage-controlled lunar cross-sensor benchmark with rendered GT + geometry bounds + manual check points | MiLOI (LROC only, 321 pairs); LunarStereo (stereo, rendered) | **COMBINATION**, useful | 3 |
| PSF-aware degrade-to-coarser ladder with sub-pixel defined at coarse GSD | Standard practice | **KNOWN** | 1 |
| Band policy for IIRS (reflectance vs thermal) in registration | IIRS L2 literature | **ADAPTATION** | 2 |

**Novelty defensibility score: 3/5.** Honest position for the write-up: "no new algorithm; a new, tested answer to how much of SIH26166 is physics and how much is matching, with the instrument to tell when the answer is wrong."

---

## 34. Breakthrough opportunities

1. If H2 holds and a NAC DTM restores the OHRC/NAC rung, the practical rule "illumination-robust registration needs a DEM at ≤ k × GSD" with measured k is a quotable result.
2. Using the render to *generate* training pairs for a licensable learned engine (A4) closes the loop physics → data → matcher without terrestrial bias.
3. A rejection-rate-reporting benchmark for lunar registration does not exist and would be adopted.

---

## 35. Kill list

| Idea | Why attractive | Why it fails | Evidence | To revive |
|---|---|---|---|---|
| Mod-π / polarity-agnostic descriptor as the illumination fix | Elegant; matches the shading-inversion physics | Loses half the orientation information; worst arm measured; the failure is orientation *assignment*, not binning | EXP-003 `[OURS]`; Wu 2018 `[LIT]` | A representation that fixes assignment and is tested against DEM rendering |
| Fit RMSE as a correctness metric | The PS lists it | AUC 0.4947; inverted in failure | EXP-002 `[OURS]` | Never |
| Global homography over relief tiles | Simple | Parallax error tens of px at OHRC/NAC; masks as RMSE | §20 | Only for flat near-nadir tiles after a residual test |
| Upsampling the coarse image to the fine GSD | "Preserves detail" | Invents nothing; detector starvation is on the coarse side anyway; sub-pixel becomes meaningless | Scale probe `[OURS]` | Never |
| Training a lunar matcher from scratch | "DL wins" | Data leakage, compute, deadline; backbone licences | §30 A4 | After A3's renderer exists; only fine-tuning a licensable backbone |
| Registering IIRS ≥ 3.5 µm bands as reflectance | "More bands" | Thermal emission; different physics | IIRS L2 `[LIT]` | Only with a temperature model and structural descriptors |
| Calling pan↔pan "multimodal" | Title of the PS | Reviewer will ask what changed physically | §21 | Only for IIRS bands or thermal |
| Cycle consistency as a verifier | Cheap | Blind to symmetric error | EXP-002 obj. 4 `[OURS]` | Never as decisive |
| SuperGlue/SuperPoint/MASt3R in the deliverable | Best zero-shot numbers | Non-commercial licences | `[FACT]` | Only as an un-shipped comparison arm |
| EXP-004 (orientation assignment) as the central research line | Explains the SIFT cliff mechanism | Fixing SIFT is not the goal; the mechanism is already published (Wu 2018); DEM conditioning removes the cause | §9 | Keep as a 1-day diagnostic if time allows; `RECOMMENDATION: DEMOTE` |
| EXP-006 as a stand-alone "protocol vs matcher" thesis | ADR-0001 needs it | The 33× figure is SAR-optical; the thesis is unfalsifiable as phrased | §11 | Reframe as the component ablation of GAPC (Phase 7) |
| Scale-ratio estimation networks | Handle unknown scale | Scale is metadata | §19 | Only as a no-metadata fallback |
| Per-frame photometric normalisation as the illumination fix (RD-06 as frozen) | Established planetary practice | Removes brightness, not shadow migration | §16 H4 | Run as the **control** arm; do not expect S1 |

---

## 36. Scientific hypotheses (register)

H0, H1–H5 as in §16. Each is falsifiable, has a control (the `none` arm reproducing recorded counts), a kill criterion, and an interpretation for each outcome. Registered here; frozen when EXP-007 Part 1 is committed.

---

## 37. Experiment roadmap

Priority = information gain / cost.

| ID | Hypothesis | Control | Variable | Data | Metric | Expected | Kill criterion | Decision |
|---|---|---|---|---|---|---|---|---|
| **EXP-007** (highest value) | H1, H2, H4 | `none` arm reproduces 5365/1656/4/4/7/3 exactly | Illumination arm ∈ {none, photometric, DEM-render(SLDEM), DEM-render(NAC DTM)} × GSD rung ∈ {native, 5, 20, 80 m} | Six recorded NAC edges (Mare Serenitatis) + one new NAC-DTM site with ≥ 3 illuminations | Success under frozen rule; inliers; coverage; geometry-bound disagreement; loop closure at the new site | H1 MET at 5–80 m; H2 first half MET | If `none` fails to reproduce: stop. If render arm fails at *every* rung: H0 REFUTED, fall back to A1 | Fix the tier policy |
| EXP-005 | H0 mechanism; azimuth vs elevation | Same DEM, same Sun | Sun azimuth × elevation grid on rendered pairs (real DEM, SLDEM + NAC DTM) | Rendered GT | Endpoint error vs GT | Cliff disappears for render-conditioned arm; simulator gap measured | Simulator-vs-real disagreement > matching gain | Trust bound for rendered GT |
| EXP-008 | H3 | B1 | Engine ∈ {B1, LightGlue+DISK, LightGlue+ALIKED, RoMa} on raw and on conditioned pairs | Same as EXP-007 | Same | Learned > B1; conditioned ≥ raw for every engine | If learned raw ≥ render-conditioned at Δinc > 40°: H0's *practical* value at that rung is refuted; adopt learned engine, keep physics for scale/verify | Engine choice |
| EXP-009 | Modality policy | Pan band | IIRS band groups (0.8–2.0; 2–3.5 corrected; ≥ 4) or Kaguya MI proxies vs NAC degraded to 80 m | PRADAN IIRS or MI proxy | Success; error in 80 m px | Reflectance ≈ pan; thermal envelope narrower | — | Band policy |
| EXP-010 | H5 sub-pixel | Same-Sun self-warp | Refinement ∈ {none, phase-corr, ECC, LSM} on raw vs conditioned | Rendered GT + manual check points | Error on independent points, CI | Conditioned < 0.5 px; raw biased | If conditioned ≥ raw: H5 REFUTED | Refinement tier |
| EXP-011 | Viewpoint model validity | Nadir pairs | Emission angle × relief; model ∈ {similarity, affine, homography, local affine, DEM-ortho} | TMC-2 fore/aft or slewed NAC | Residual structure vs relief | DEM-ortho needed above threshold | — | Model selection rule |
| EXP-012 | Verdict calibration | — | FA/FR of verdict on calibration vs validation sites; adversarial set | Benchmark | FA ≤ 5 %, FR ≤ 20 % | — | If FA > 10 % on validation: rules re-frozen only with new calibration data | Ship |
| EXP-013 | Significance | — | One more failing and one more succeeding real edge at the existing site | Archive | Exact p | p ≤ 0.05 | — | README claim |
| RD-06 | H4 | as frozen | as frozen | as frozen | as frozen | S1 NOT MET, S3 MET | as frozen | Becomes the photometric arm of EXP-007 |

**Single highest-value experiment: EXP-007.** Cost: one runner script, one renderer (hillshade with Lommel-Seeliger and cast shadows from SLDEM, which the existing `render()` almost is), one DEM fetch; days, CPU.

---

## 38. Verification architecture

Evidence hierarchy (decisive → supporting): geometry-prior consistency with budget; DEM-render consistency; loop closure (when ≥ 3 views); held-out independent family; coverage; stability. Excluded: fit RMSE, held-out residual, cycle consistency (documented reasons `[OURS]`). Output: `VERIFIED / REJECTED / INCONCLUSIVE` with ordinal confidence and named evidence. Rules frozen per stage; changed only with a new calibration set and a ledger entry.

## 39. Uncertainty / rejection architecture

Per-correspondence covariance from local correlation curvature (area methods) or descriptor-consensus bootstrap; transform covariance by propagation; reported error as median and 95 % CI on check points; verdict thresholds in units of the budget; explicit rejections for: overlap < 20 %; missing geometry with no fallback engine success; incidence > 75° on either frame; thermal band without correction; DEM absent where tier policy requires it (degrade to A1 with INCONCLUSIVE cap).

---

## 40. Final recommended architecture — GAPC

```
inputs ──► ingest+validate (PDS4/GeoTIFF/IIRS cube; structural checks)
       ──► geometry (SPICE/ALE if available; else archive corners) ──► overlap, prior T₀, Σ₀
       ──► GSD ladder: PSF-aware degrade finer→coarser; contract C4 coordinates
       ──► illumination tier policy:
             T-A photometric normalisation (per-pixel i from DEM where DEM ≤ 5×GSD; else per-frame)
             T-B DEM render under each image's Sun (SLDEM/TMC-2 DEM/NAC DTM) → match I_k ↔ Î_k
             T-C robust engine on the residual pair (B1 | PC/RIFT2 | LightGlue+DISK/ALIKED | RoMa)
       ──► correspondence via ground (T-B) or direct (T-C) ──► ANMS spatial balancing
       ──► model selection by residual structure (local affine / DEM-ortho) ──► LO-RANSAC
       ──► sub-pixel refinement (phase-corr/ECC/LSM) at coarse GSD, with covariance
       ──► verification (geometry, render consistency, loop, held-out family, coverage)
       ──► verdict + uncertainty ──► outputs (points CSV, registered product NaN no-data, metrics, provenance)
```

Why: it is the only candidate that turns the PS's three variations into two solved-by-physics problems (scale, viewpoint), one largely-solved-by-physics problem (illumination at coarse rungs), and one honest open boundary (illumination at sub-metre GSD without a fine DEM), with a verdict. Gap addressed: §10's open rows. Evidence: TRN and NAC-to-DEM literature `[LIT]`; RD-04 `[OURS]`. Novel: §33 row 2. Not novel: every module. Unproven: H1–H5. Competitors: will not build the geometry/DEM layer in a hackathon timeline. Biggest risk: DEM resolution at the OHRC rung. Next experiment: EXP-007.

---

## 41. Detailed module architecture (behavioural specification, not code)

| Module | Responsibility | Inputs | Outputs | Fails when |
|---|---|---|---|---|
| `ingest` | Decode NAC PDS4 (exists), C2 PDS4 raw/calibrated, TMC-2 L2 GeoTIFF, IIRS cube + geometry file; structural identities; sanity gate (exists) | files | image, geometry, sentinels, checks | any structural mismatch → refuse |
| `geometry` | Line-scan sensor model via ALE/CSM when kernels exist; else bilinear corner model (exists); overlap classification (exists); prior transform with covariance | labels, kernels, DEM | polygon, T₀, Σ₀ | overlap UNKNOWN → INCONCLUSIVE cap |
| `ladder` | PSF-aware resample to coarser GSD; record scale and PSF used | images, GSDs, PSF models | degraded image, transform | ratio > 512 → refuse |
| `photometry` | Per-pixel or per-frame normalisation (exists; extend to per-pixel from DEM) | image, i/e/g maps | corrected image, validity, record | thermal band → refuse |
| `render` | DEM under Sun vector with Lommel-Seeliger/Hapke and cast shadows; resampled to the target sensor's grid and PSF | DEM, s_k, π_k, ψ_k | Î_k, validity | DEM coarser than policy → tier downgrade |
| `engines` | B1, PC, learned (licensed) with identical harness (exists) | pair | matches | none |
| `balance` | ANMS/grid before estimation; coverage metrics (exists) | matches | balanced matches, coverage | — |
| `estimate` | Model selection; LO-RANSAC (exists); DEM-ortho path | matches, DEM | T, inliers, covariance | degenerate → REJECT |
| `refine` | Area-based sub-pixel at coarse GSD with per-point covariance | T, images | refined points, Σ_i | correlation peak ambiguous → drop point |
| `verify` | Evidence stack (exists + render consistency + geometry budget) | everything | verdict | — |
| `product` | Warp with NaN no-data (exists), CSV with residual disclaimers (exists) | T, images | files | rejected → no product |
| `provenance` | Hashes, versions, stage labels from outdir (exists) | — | JSON | — |

## 42. Data flow

Read-only archive → cached tiles (hash-keyed, window-keyed; exists) → geometry-first decisions → pixel processing → artefacts under `experiments/<STAGE>/` → demo reads artefacts only (exists).

## 43. Mathematical pipeline

§4, applied in the order of §40; every coordinate under C1–C9; every rendered or degraded image carries its transform to the source grid so correspondences compose exactly.

## 44. Engineering architecture

Python 3.13, numpy/scipy/OpenCV 5 (pinned range), rasterio/GDAL for GeoTIFF, `ale`/`csmapi` optional for line-scan models (documented fallback to corner model), PyTorch CPU optional for learned engines behind a feature flag, ISIS not required at runtime. FastAPI demo (exists). All learned weights vendored with licence files; SuperPoint/SuperGlue/MASt3R absent from the deliverable.

## 45. Runtime / memory strategy

Tiles ≤ 4096² decimated as today; DEM windows fetched by footprint; renders at target GSD only; learned engines on 1024² crops with overlap-aware stitching (as in 2604.10217's protocol); target ≤ 60 s per pair on 4-core CPU at TMC/IIRS rungs; ≤ 5 min at NAC/OHRC rung; GPU optional, never required.

## 46. Reproducibility

Seeds, frozen environments (exists), artefact re-derivation from bytes (exists), pre-registration Part 1/Part 2 (exists), stage labels derived from output directories (E-033, exists), no re-run may overwrite a recorded artefact (integrity rule 3).

## 47. Licensing

Ship: own code (choose Apache-2.0), OpenCV (Apache-2.0), LightGlue (Apache-2.0), DISK (Apache-2.0), ALIKED (BSD-3), RoMa (MIT; DINOv2 Apache-2.0), ISIS-derived photometric constants (public domain), SLDEM/LOLA/NAC (NASA, credit required), Chandrayaan-2 (ISRO terms per PRADAN acknowledgement page — wording recorded verbatim in `sources.md` S15 on 2026-09-05: the ISSDC acknowledgement sentence, "Chandrayaan-II" in the abstract, "© reserved ISRO" on any printed product), tifffile (BSD-3, GeoTIFF reader for TMC-2 L2). Do not ship: SuperPoint, SuperGlue, MASt3R/DUSt3R, any Kaguya-derived model beyond data use terms.

## 48. Testing strategy

Keep the existing 605-test discipline; add: renderer identity tests (render of a plane is flat; shadow of a step matches analytic length); ladder tests (PSF-degraded self-consistency; C4 under degradation); tier-policy tests (deterministic tier from DEM/GSD ratio); verdict calibration tests on frozen calibration artefacts; licence-manifest test (no forbidden weight file in the package).

## 49. Benchmark strategy

§28 splits; three tiers of data (real NAC, real C2 via PRADAN, proxies); rendered GT with measured simulator gap; report per site, per rung, per Δinc bin, per band; publish rejection rate alongside accuracy; release the manifest and the geometry so pairs are re-fetchable by byte range (as today).

---

## 50. Red-team analysis

| Attack | Effect on GAPC | Mitigation | Residual risk |
|---|---|---|---|
| Wrong tile / zero overlap | Geometry layer refuses before pixels (exists) | — | Corner metadata wrong → INCONCLUSIVE, not VERIFIED |
| Tiny overlap (20–50 %) | UNKNOWN class; matching allowed with cap | Coverage and budget | Accept fewer VERIFIED |
| Repeated craters / lattice | Geometry prior bounds the shift; loop closure if 3 views | Independent crater family | Shift < prior uncertainty *and* no third view: undetectable → INCONCLUSIVE cap when prior σ > half lattice |
| Low texture (mare) | Render adds nothing; photometric keeps albedo; learned engine may help | Report envelope honestly | Mare at high Δinc may remain REJECTED |
| Extreme illumination (> 75°) | Refused (D-029) | — | Loses polar pairs; state it |
| 320:1 | Ladder; patch-in-image localisation | — | Sub-pixel is 80 m |
| Strong viewpoint / relief | DEM-ortho path | EXP-011 | DEM error becomes the floor |
| Multimodal thermal | Structural engine only; narrower envelope | EXP-009 | May be REJECTED often |
| Missing metadata | Fall to A1 with INCONCLUSIVE cap | — | No absolute check |
| Corrupt archive | Structural identities (exists) | — | — |
| Wrong geometry (kernel error) | Render disagrees with image at claimed pose; budget exceeded | Render consistency verifier | If kernels wrong *and* no DEM: undetectable |
| Coherent-wrong beyond prior | Render consistency + loop | — | Per-image gauge with no DEM: N1 |
| False confidence from learned certainty maps | Never used as evidence | — | — |
| Sub-pixel interpolation artefacts | Refinement at coarse GSD with PSF; C4 | EXP-010 | — |
| Verifier blind spot: DEM itself wrong (artefacts render false structure) | Cross-check render against a second DEM source when available; SfS-refined DEM flagged | — | Single-DEM sites carry the DEM's errors |
| Photometric model wrong at 70° incidence | Lommel-Seeliger primary; Hapke with roughness caveat; measured residual reported | RD-06 records | Known and stated |

Redesign after attack: added the render-consistency verifier and the INCONCLUSIVE cap tied to prior uncertainty; both are in §38–39.

---

## 51. Implementation roadmap

Effort in person-days (pd) for a 3–4 person team; today is 2026-09-04.

| Phase | Objective | Inputs | Work | Experiments | Deliverables | Success | Kill | Depends | Effort | Risk |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 Research reset | This document; freeze EXP-007 Part 1 | repo, literature | Write Part 1; register PRADAN; fetch SLDEM window; list NAC DTM sites | — | Frozen Part 1; PRADAN account | Part 1 committed before any render | — | — | 2 pd | low |
| 1 Data foundation | Real data on disk for all rungs | PRADAN, PDS, LROC RDR | C2 ingest (PDS4 raw/cal, TMC-2 GeoTIFF, IIRS cube+geometry); DEM fetch; site selection; proxies | ingest tests | Manifests with hashes | Every format loads with geometry | PRADAN denied → proxies only, labelled | 0 | 8 pd | medium (PRADAN latency) |
| 2 Baselines | Engines on identical harness | 1 | LightGlue+DISK/ALIKED, RoMa CPU path; RIFT2 proper | EXP-008 raw arm | Baseline table on six edges | Runs on CPU | — | 1 | 5 pd | low |
| 3 Scientific experiments | H1, H2, H4 | 1, 2 | Renderer; ladder; RD-06 runner; EXP-007 runner | EXP-007, RD-06, EXP-005 | Part 2 reports | H1 MET or cleanly refuted | `none` arm fails to reproduce | 0–2 | 10 pd | medium |
| 4 Breakthrough component | Tier policy + render-through-ground correspondence + fine-DEM rung | 3 | Per-pixel photometry from DEM; NAC-DTM site; optional A4 fine-tune | EXP-007 fine rung | Working GAPC core | Success on ≥ 1 previously failing real edge | H0 refuted at all rungs → A1 + physics-for-scale | 3 | 10 pd | high |
| 5 Verification | Render consistency; geometry budget; calibration | 4 | Verdict extension; calibration sites | EXP-012 | Calibrated verdict | FA ≤ 5 % validation | — | 4 | 5 pd | low |
| 6 Real Chandrayaan-2 | OHRC/TMC-2/IIRS ↔ NAC | 1, 4 | Run ladder on real C2 pairs | EXP-009, EXP-011 | C2 result tables | ≥ 1 VERIFIED pair per sensor | none obtainable → proxies, stated | 4 | 8 pd | high (data) |
| 7 Ablation | Component contribution | 6 | Remove each layer | EXP-006 reframed | Ablation table | — | — | 6 | 3 pd | low |
| 8 Blind validation | Held-out sites opened once | 5, 6 | Freeze, run, report | — | Blind report | Verdict FA/FR within calibration | — | 7 | 2 pd | medium |
| 9 Hardening | Packaging, licences, CPU limits | 8 | Vendoring, tests, docs | — | Installable package | Fresh-clone install + tests pass | — | 8 | 4 pd | low |
| 10 Demo | Judge-facing | 9 | Real C2 case, one REJECTED case, one 320:1 case, provenance links (exists) | — | Demo | Every number traceable | — | 9 | 3 pd | low |
| 11 Final benchmark | Publishable tables | 8 | Aggregate, CIs, p-values | EXP-013 | Benchmark release | p ≤ 0.05 on illumination claim | — | 8 | 2 pd | low |
| 12 Documentation | Reports, ledgers, README | all | Update indexes; keep history | — | Docs | Consistency tests pass | — | 11 | 3 pd | low |

Total ≈ 65 pd. Critical path: 0 → 1 → 3 → 4 → 6. Phases 2 and 5 run in parallel with 3–4.

---

## 52. Demo strategy

Three beats, all from recorded artefacts: (1) a Chandrayaan-2 ↔ NAC pair at the TMC-2 or IIRS rung registered under > 40° Δincidence with the render arm, beside the raw-pair failure — the physics beat; (2) the B → D real edge REJECTED with its 1e-13 px residual — the honesty beat (exists); (3) a 320:1 OHRC-in-IIRS localisation with error in IIRS pixels and its CI — the scale beat. Every displayed number opens its artefact (exists).

## 53. Final success criteria

- H1 MET on real data at ≥ 2 rungs with the frozen rule; p ≤ 0.05 on the illumination separation with ≥ 8 edges.
- ≥ 1 VERIFIED Chandrayaan-2 pair per sensor against NAC, with check-point error and CI reported in coarse pixels.
- Verdict FA ≤ 5 %, FR ≤ 20 % on validation sites; zero VERIFIED on the adversarial set.
- Coverage gap ≤ 0.15 on every VERIFIED pair.
- Fresh-clone install, CPU-only, all tests pass, no non-commercial weights.

## 54. Final failure criteria

- `none` arm cannot reproduce recorded counts (harness broken): stop everything.
- Render arm fails at every rung on every site: H0 REFUTED; adopt A1 with physics for scale/verification; say so.
- No Chandrayaan-2 data by Phase 6 start: report proxies only, never as C2 results.
- Verdict FA > 10 % on validation: do not ship VERIFIED; ship INCONCLUSIVE/REJECTED only.

## 55. Remaining risks (top 10)

1. PRADAN access latency or denial. 2. DEM resolution at the OHRC rung. 3. Photometric model error at 70° incidence. 4. Ephemeris/attitude error larger than budget for C2 products (30–50 m). 5. Learned engines outperforming physics at the fine rung (H3 false) — a strategic, not scientific, risk. 6. IIRS geometry-file handling. 7. Time: 65 pd against the finale. 8. Simulator gap larger than matching gain (rendered GT untrustworthy). 9. Mare at high Δinc remaining unsolved by any tier. 10. ISRO's blind set lacking metadata, collapsing GAPC to A1.

## 56. Final recommendation

Build GAPC. Run EXP-007 first. Register on PRADAN today. Keep the verification discipline exactly as it is. Demote EXP-004, reframe EXP-006, run RD-06 as the control. Ship only licensable engines. Report the boundary where the physics stops helping as a result, not as an apology.

---

# FINAL DECISION MATRIX

| Candidate | Sci. validity | Novelty | Illum | Scale | VP | MM | Terrain | Sub-px | Verif. | Reject | Compute | Data | Repro | Licence | Impl. risk | Comp. risk | Evidence | **Overall /5** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **A3 GAPC** | 5 | 3 | 4 | 5 | 5 | 3 | 3 | 4 | 5 | 5 | 4 | 3 | 4 | 5 | 3 | 4 | A/B | **4.2** |
| A5 image-to-DEM only | 4 | 1 | 4 | 4 | 5 | 2 | 2 | 2 | 4 | 5 | 4 | 3 | 4 | 5 | 3 | 3 | A | 3.4 |
| A1 learned zero-shot | 3 | 1 | 3 | 2 | 3 | 3 | 3 | 2 | 4 | 4 | 3 | 1 | 4 | 4 | 5 | 1 | B | 3.0 |
| A4 lunar-trained learned | 3 | 3 | 4 | 3 | 3 | 3 | 3 | 3 | 4 | 4 | 1 | 5 | 2 | 3 | 1 | 3 | C | 2.9 |
| A6 crater graph | 3 | 2 | 5 | 3 | 3 | 3 | 1 | 1 | 3 | 3 | 3 | 3 | 3 | 4 | 3 | 3 | B | 2.9 |
| A7 PAM | 4 | 2 | 5 | 1 | 5 | 1 | 4 | 4 | 3 | 3 | 1 | 4 | 2 | 4 | 1 | 4 | B | 2.8 |
| A2 classical + protocol (old plan) | 3 | 1 | 1 | 2 | 2 | 2 | 1 | 2 | 5 | 5 | 5 | 1 | 5 | 5 | 5 | 2 | A | 2.6 |

**Scoring.** Weighted mean with weights: scientific validity 2, illumination 2, verification 1.5, rejection 1.5, novelty 1, all others 1 (impl./comp. risk and data need scored so that 5 = least risk/need). Evidence level A = measured here or in strong peer-reviewed lunar work; B = literature claim not on lunar data or without independent GT; C = inference. GAPC wins on breadth of ≥ 4 scores, not on any single axis; its novelty is scored honestly at 3 and would rise only if EXP-007 confirms H1–H2.

---

# FINAL EXECUTIVE CONCLUSION

## A. WHAT IS THE REAL PROBLEM?
Deciding how much of lunar cross-sensor correspondence is already determined by known topography and illumination geometry, solving the residual to sub-pixel at the coarser sensor's GSD, and knowing when the answer is wrong. Not "a better matcher".

## B. WHAT DID THE OLD 3/10 PLAN GET WRONG?
It chose an architecture (protocol over matcher) from one SAR-optical preprint before proving a gap; it ignored the DEM and SPICE prior that makes the Moon special; it tested illumination at the descriptor layer with weak arms; it never obtained Chandrayaan-2 data although access is free; it never tried a learned matcher on real data; it measured scale and uniformity instead of handling them; and it spent five real-data stages refining the measurement of one matcher's failure. Its methodology (pre-registration, RMSE exclusion, loop closure, provenance) was right and is kept.

## C. WHAT DOES THE LITERATURE ALREADY SOLVE?
Overlap and priors from geometry; DEM-rendered illumination matching for TRN and NAC-to-DEM registration; photometric normalisation below ~60° incidence; nonlinear-radiometric invariance for terrestrial multimodal pairs (RIFT2/HOWP/WSSF); strong zero-shot learned matchers (LightGlue, RoMa, MINIMA) with licensable variants; crater-graph matching robust to illumination; IIRS band physics; OHRC/TMC-2 geometric processing with ALE/CSM/ASP.

## D. WHAT REMAINS UNSOLVED?
Illumination-robust correspondence at sub-metre GSD without a fine DEM; sub-pixel accuracy *under* illumination change with independent validation; optical–thermal lunar registration; a lunar benchmark with independent GT and rejection rates; any Chandrayaan-2 ↔ NAC result with independent ground truth.

## E. STRONGEST RESEARCH GAP
No published work quantifies, across the Chandrayaan-2/NAC scale ladder, how far DEM-conditioned illumination invariance reaches and where DEM resolution stops it, with a verdict that rejects coherent-wrong answers on independent evidence.

## F. CENTRAL SCIENTIFIC HYPOTHESIS
H0: conditioning correspondence on known illumination geometry via DEM rendering extends the usable Sun-angle difference beyond raw invariant or zero-shot learned matching, with a gain bounded by DEM-resolution/GSD.

## G. TOP 5 POSSIBLE RESEARCH DIRECTIONS
1. Physics-conditioned correspondence with a scale-ladder bound (GAPC). 2. Zero-shot learned engines under a physics ladder. 3. Rendered-data fine-tuning of a licensable matcher. 4. Photoclinometry-assisted dense matching for the finest rung. 5. Rejection-rate-reporting lunar benchmark.

## H. TOP 3 ARCHITECTURES
A3 GAPC; A5 image-to-DEM absolute georeferencing; A1 learned zero-shot + our verdict.

## I. FINAL RECOMMENDED ARCHITECTURE
A3 GAPC (§40).

## J. WHY THIS ARCHITECTURE
It converts two of the PS's three variations into solved physics, addresses the third with the strongest lunar-specific prior, keeps the matcher replaceable, ships only licensable components, and carries the only validated verification layer in the field of candidates.

## K. STRONGEST DEFENSIBLE NOVELTY
The pre-registered, cross-sensor, scale-ladder measurement of DEM-conditioned illumination invariance and its resolution bound, delivered with a verdict engine whose exclusions are justified by measurement. Score 3/5 now; 4/5 if EXP-007 confirms.

## L. WHAT IS NOT NOVEL
Every module: DEM rendering, photometric normalisation, PSF-aware resampling, LO-RANSAC, ANMS, phase congruency, learned matchers, loop closure, area-based refinement.

## M. MOST DANGEROUS FAILURE MODE
A DEM artefact or wrong kernel rendering plausible structure at the wrong place, producing a VERIFIED coherent-wrong answer whose per-image gauge error loop closure cannot see (N1). Mitigation: render-consistency check and INCONCLUSIVE cap tied to prior uncertainty; second-DEM cross-check where available.

## N. SINGLE MOST IMPORTANT EXPERIMENT
EXP-007: six recorded real edges plus one NAC-DTM site, three illumination arms, four GSD rungs, frozen rule.

## O. SINGLE MOST IMPORTANT DATASET
Real Chandrayaan-2 products from PRADAN paired with NAC over sites that have NAC DTMs and multi-illumination coverage; until obtained, the recorded NAC edges plus SLDEM.

## P. SINGLE MOST IMPORTANT DEMO
A Chandrayaan-2 ↔ NAC pair at > 40° Δincidence: raw pair REJECTED beside render-conditioned pair VERIFIED, every number opening its artefact.

## Q. TOP 10 RISKS
§55.

## R. TOP 10 COMPETITOR ADVANTAGES WE MUST COUNTER
1. Better zero-shot matcher numbers. 2. GPU demos. 3. Bundle-adjusted geodetic accuracy in metres. 4. Larger pair counts. 5. Fine-tuned models on NAC crops. 6. Polished mosaics. 7. Use of SuperGlue regardless of licence. 8. Claims of sub-pixel from fit residuals that judges may accept. 9. Prior PRADAN familiarity. 10. Crater-detection pipelines.

## S. TOP 10 THINGS COMPETITORS MAY MISS
1. Fit RMSE is inverted in failure. 2. Scale is sampling, not descriptors. 3. Illumination is a forward model on the Moon. 4. Coherent-wrong answers. 5. The 320:1 rung is localisation, not registration. 6. IIRS thermal bands are not reflectance. 7. Global homographies fail under relief. 8. Licences. 9. Non-overlapping pairs in an evaluation set. 10. Reporting a rejection as a result.

## T. TOP 10 ISRO REVIEWER QUESTIONS
1. Against what ground truth is your sub-pixel claim measured? 2. What is your false-acceptance rate? 3. Why is RMSE not in your verdict? 4. Where does your method stop working, in degrees and metres? 5. What DEM did you use and what happens without it? 6. How do you treat IIRS bands above 3 µm? 7. What is your absolute geolocation accuracy vs LOLA? 8. Which components are yours? 9. Can it run on our machines without a GPU? 10. Show me a failure.

## U. WHAT WE SHOULD BUILD FIRST
PRADAN account; EXP-007 Part 1 frozen; renderer from SLDEM; EXP-007 runner reusing the recorded tiles; LightGlue+DISK baseline arm.

## V. WHAT WE SHOULD NOT BUILD
Anything in §35: mod-π descriptors, scale-estimation networks, a from-scratch lunar matcher, cycle-consistency verifiers, non-commercial engines in the deliverable, EXP-004 as a research line, EXP-006 as a stand-alone thesis.

## W. WHAT REMAINS UNPROVEN
H0–H5 in full; any Chandrayaan-2 result; sub-pixel under illumination change; thermal-band registration; the simulator gap; the DEM-resolution constant k.

## X. WHAT WOULD MAKE THIS PROJECT SCIENTIFICALLY HARD TO REJECT?
A pre-registered experiment whose control reproduces recorded numbers exactly, whose treatment moves a real outcome under an unchanged rule, whose ground truth is independent of the matcher, whose failure boundary is stated in physical units, whose false-acceptance rate is measured on held-out sites, and whose every number opens the file it came from. Most of that machinery already exists in this repository; what it lacks is the treatment. EXP-007 supplies it.

---

*Sources consulted (representative; full list in §8–9): arXiv 2509.04775, 2604.25208, 2604.01032, 2602.14993, 2604.17436, 2410.11118, 2412.19412, 2604.10217, 2601.10449, 2510.18172, 2606.29821, 2604.22296, 2606.14776, 2303.00319; Remote Sensing 14(20):5156, 14(24):6339, 17(13):2302; ISPRS JPRS 2019 (Liu & Wu), 2023 (HOWP), 2025 (Jiang; SFA-Net); IEEE TIP 2020 (RIFT); IEEE 10374089 (WSSF), 10781320 (EPCFT), 11105476; P&SS 2018 (Wu); ISPRS Archives 2020 (Ye), XLVIII-G-2025 (DEM registration); Appl. Sci. 2026 16(3):1238; AIAA 2025-2073, 2026-2244; NTRS 20210024816; USGS ISIS lronacpho docs; LROC NAC processing guide and RDR releases 62A–65C; Astropedia SLDEM2015/LOLA pages; ISSDC/PRADAN pages; LPSC 2021/2022/2023 abstracts on PRADAN and C2 PDS4; Current Science 118(3)/(4) instrument papers (OHRC, TMC-2, IIRS); JISRS 2023 (TMC-2 DEM quality), 2024 (IIRS seleno-referencing); Adv. Space Res. 2024 (IIRS photometric correction); Icarus 2022 (IIRS thermal); MAPS 2025 (IIRS L2); JGR 2012 (Hapke wavelength), 2014 (Sato Hapke maps); GitHub licence pages for LightGlue, DISK, ALIKED, RoMa, MASt3R, DUSt3R, SFA-Net, RIFT/RIFT2.*


---

# ADDENDUM — measured status, 2026-09-04 (evening)

Written after the reset above was executed for one day. Every number below is
from a committed artefact; stages still running are marked as such.

## A1. What changed in the evidence

| Item | Morning (plan as written) | Evening (measured) |
|---|---|---|
| Any method above 12° Δincidence on real data | none | **B4L (DISK + LightGlue, Apache-2.0)** registers C → A at 38.85° with 56 inliers, CONSISTENT with archive geometry (EXP-007 tier 1); at the 15 m rung on the long windows it registers A → B at 39.81° with **2042** geometry-consistent inliers (EXP-007 tier 2, running) |
| DEM-render conditioning (H0/H1) | hypothesis | legs return 0–3 inliers at 1.8, 3.6, 7 and 15 m on this mare window: the 59 m SLDEM carries no matchable shading here at any rung tested so far. **H2 MET (bound confirmed), H1 heading to NOT MET.** Final at 30 m pending |
| Photometric normalisation (RD-06) | pre-registered | per-frame Lommel-Seeliger and Hapke change **no** outcome (S5 MET); a per-frame scalar is invisible after a per-image stretch — a design finding about RD-06 |
| Sub-pixel accuracy | never measured | **0.003 px** median on real self-warps (ECC; upper bound); < 0.25 px under synthetic Sun-azimuth change to 30°; gate 7e-15 px (EXP-010) |
| Model selection | absent | E-034 found (affine default 0.19–0.94 px on frames A, D with zero residual); refine-then-reselect reaches **0.0018 px**, 48/48 correct models (EXP-011) |
| Sample size | 6 edges | 14 census frames located; 20 tiles acquired; **42 geometry-confirmed pairs** (23 + 19) across both windows; registration running (REAL-DATA-07) |
| Orientation obstacle (REAL-DATA-05) | blocking | removed: exact quarter-turn from corner columns (`siim.ingest.orientation`), no estimation |
| Multimodal data | none | Mini-RF S-band radar strip (14.8 m) and WAC 100 m mosaic blocks over the windows on disk, stage pre-registered (REAL-DATA-08, queued) |
| Chandrayaan-2 | none | none — PRADAN registration is the user's action (instructions given) |
| NAC DTM over the window | unknown | none exists (ODE SDNDTM/ASPDTM query); nearest is SERENRIDGE1 at 22.9–24.6 N, 24.4–24.9 E, 5 m posts |

## A2. Consequences for the architecture (§40)

1. **The illumination engine at the fine and mid rungs is B4L, not the DEM
   render**, on mare terrain with a 59 m DEM. H0 is kept only for sites with a
   fine DEM (SERENRIDGE1) and is demoted from "central" to "conditional".
2. **Pipeline order is estimate → refine → re-estimate with selection → verify**
   (EXP-010, EXP-011). The verdict gains `model_selected_by`.
3. **Physics keeps three jobs**: overlap and prior transform (unchanged), the
   scale ladder (unchanged), and verification by geometry (unchanged). Its
   fourth job, illumination conditioning, is now evidence-limited to fine-DEM
   sites and is stated as such.
4. The learned engine's licence and determinism are recorded; SuperGlue remains
   excluded.

## A3. Honest scoring after one day

Plan 6.5 / 10, demonstrated 6 / 10 (from 5 / 4 in the morning). The remaining
ceiling is the absence of Chandrayaan-2 data (user action) and the pending
replication and radar results (running).

## A4. Evening of 2026-09-05 — what the overnight results changed

| Item | A1 (evening of 09-04) | Measured on 09-05 |
|---|---|---|
| Learned engine's envelope | one converted edge, "running" | Native scale on 42 pairs: **same envelope as RootSIFT** (largest ≥ 0.8 bin 10–15° for both; 17 / 42 vs 20 / 42), yield inside it 5–25×; at 7–30 m three of four ~40° pairs converted (EXP-007). D-047 amended to D-047-N1 |
| Replication of the low-incidence success | "running" | **NOT MET.** E1 could not be tiled on the shared ground; E2 fails vs A (6, INCONSISTENT) and vs B (3), and against every partner. D-040-N1's debt stands |
| Δincidence as the variable | six edges, p = 0.0667 | 42 pairs: pooled **p = 0.0042** (RD-03 0.0040, RD-04 0.121); no success above 40°; **four frames fail against every partner irrespective of Δincidence** (E2 at 21°, three dark frames at 66.9–74.7°). Necessary, not sufficient (D-049) |
| Wrong passes | none measured | **0 / 37** at ≈ 2 m (RD-07); **1 / 6** for B4L at the 100 m rung (RD-08). The verdict's first measured false-acceptance bound, at a ~100 px floor |
| Multimodal | proxies on disk | **Radar registers under no engine** (0 / 48). The problem statement's multimodal claim is a measured negative on the best available proxy (D-050) |
| 100 m rung | queued | B1 1 / 4 frames; **B4L 3 / 4** with 34–99 consistent inliers from 111 × 46 px strips (D-050) |
| Photometric normalisation | "no outcome change" | **No-op by construction** (E-035): the per-frame scalar is removed by the stretch. Per-pixel from a 59 m DEM converts nothing |
| Pipeline | order decided | Built and tested: `siim.pipeline`, `siim register`, engine agreement (caps at INCONCLUSIVE), PSF-aware degradation, XFeat as B4X (pinned commit) |
| Chandrayaan-2 | none | none; REAL-DATA-09 pre-registered, acknowledgement wording recorded (S15); download is 2026-09-06 |

**Consequences for §40.** (1) The illumination engine at native scale on mare is
*neither* engine: the learned engine raises yield where RootSIFT already works
and converts nothing RootSIFT fails at ≈ 2 m; its conversion power is a
coarse-rung result. The tier policy therefore keys on **GSD**, not on the
engine. (2) Frame-level failures that Δincidence does not explain are the
open scientific question, ahead of illumination; A (E2 diagnostic) and B
(the 60–75° sweep) in `NEXT_SESSION_PLAN.md` come before any new arm.
(3) The multimodal line of the deliverable reads: *radar not registered by
any engine tried; spectral modality (IIRS) untested until REAL-DATA-09.*

**Honest scoring after two days.** Plan 6.5 / 10 unchanged; demonstrated
**6.5 / 10** (from 6): more is measured, and two of the things measured are
negatives the plan had counted on being positives (replication, the learned
envelope at native scale). The ceiling is still Chandrayaan-2 data.

## A5. 2026-09-06 — the replication negative was a data defect

The "four frames that fail against everyone" of A4 were, for two of them,
mirror-imaged tiles (E-037: positive corner-map Jacobian determinant on 5 of
14 census frames; a quarter-turn cannot undo a reflection). With a
reflection-aware orientation the stage was re-run on the same 42 pairs with
the same frozen criteria and a third engine (XFeat): **replication MET**
(E2 → A 2138 consistent inliers, E2 → B 4), pooled **p = 0.0012** with both
windows under 0.05, 0 wrong passes in 76, last ≥ 0.8 bin 20–25°, nothing
above 40°. D-040-N1 discharged (D-040-N2); D-049 withdrawn (D-049-N2); the
engine-agreement floor measured at 3 px on three engines (D-051). What
remains frame-level is two frames at 72–75° incidence — the ceiling, not
identity. Demonstrated score **7 / 10**: the illumination claim is now
replicated and per-window significant; the ceiling is still Chandrayaan-2
data (download 2026-09-06).
