# Source Traceability Register (spec §70, §71)

Rule: every architectural decision resting on an external fact records the source, the specific fact, and how it influenced the design. Primary sources preferred over secondary; no blogs where a primary source exists.

---

## S1 — Chandrayaan-2 payload specifications

**Source (primary):** ISRO / ISSDC PRADAN Chandrayaan-2 portal — https://pradan.issdc.gov.in/ch2/
**Supporting (primary):** ISRO, *Payloads Data & Science Handbook* — https://www.isro.gov.in/media_isro/pdf/science/hand_book_payloads_data_and_science.pdf
**Supporting:** ISRO Chandrayaan-2 payloads page — https://www.isro.gov.in/chandrayaan2-payloads.html
**Retrieved:** 2026-08-24

**Facts extracted:**
- OHRC: ground sampling distance **0.25 m**, swath **3 km**, nadir view, from 100 km altitude; visible panchromatic.
- TMC-2: **5 m** spatial resolution, **0.4–0.85 µm**, stereo triplets (fore / nadir / aft) from 100 km orbit, for DEM generation.
- IIRS: **800–5000 nm**, **~256 contiguous bands**, **80 m** GSD, **20 km** swath at nadir from 100 km.

**Influence on design:**
- Gave the exact scale ratios in ANALYSIS §C.3 (up to 320:1), which promoted scale normalisation from a preprocessing step to a required first-class pipeline stage, and corrected the spec §14 scale ladder.
- The IIRS 0.8–5.0 µm range drove the band-selection requirement (ANALYSIS §B1): beyond ~3 µm the signal becomes thermal-emission dominated, so only reflectance-dominated bands are admissible as a matching channel.
- TMC-2's stereo triplet capability drove the "DEM as illumination-invariant representation" hypothesis (ANALYSIS §C.2).

---

## S2 — LRO NAC specifications

**Source (primary):** LROC / ASU — https://www.lroc.asu.edu/about
**Supporting (primary):** *LROC NAC Processing Guide* — https://www.lroc.asu.edu/files/DOCS/LROC_NAC_Processing_Guide.pdf
**Supporting (peer-reviewed):** Robinson et al., *Lunar Reconnaissance Orbiter Camera (LROC) instrument overview* — https://pubs.usgs.gov/publication/70033784
**Retrieved:** 2026-08-24

**Facts extracted:**
- Pixel scale **0.5 m/px** (10 µrad IFOV); **5 km** swath from two NACs.
- Typical NAC pair ≈ **10,000 px** cross-track × **~52,000 px** along-track; footprints from ~5 × 26 km.
- Optics: f/3.59 Cassegrain (Ritchey-Chrétien), EFL **700 mm**, primary **195 mm**, FOV 2.85° per NAC.
- Data products organised as EDR (Experimental Data Record) and CDR (Calibrated Data Record).

**Influence on design:**
- The 10k × 52k image size makes **tiled processing mandatory**, not optional (ANALYSIS §J, EXP-006). A full-frame match is not an option at any compute budget.
- OHRC 0.25 m vs NAC 0.5 m gives the most favourable pair at 2:1 — designated the primary development pair.
- EDR vs CDR distinction feeds the radiometric normalisation stage (processing level affects statistics).

---

## S3 — Prior work on Chandrayaan-2 feature matching

**Source (peer-reviewed preprint):** *Comparative Evaluation of Traditional and Deep Learning Feature Matching Algorithms using Chandrayaan-2 Lunar Data* — https://arxiv.org/abs/2509.04775
**Retrieved:** 2026-08-24

**Facts extracted:**
- Compared **SIFT, ASIFT, AKAZE, RIFT2** (classical) against **SuperGlue** (learned), on OHRC, NAC/WAC, IIRS, DFSAR and Selene/Kaguya data, equatorial and polar regions, cross-modality pairs.
- Reported: SuperGlue "consistently yields the lowest root mean square error and fastest runtimes."
- Reported: "Classical methods such as SIFT and AKAZE perform well near the equator but degrade under polar lighting."
- Abstract does not publish per-method numeric tables (match counts, inlier ratios, exact RMSE). `[LIMITATION of this source]`

**Influence on design:**
- Direct empirical support for ANALYSIS §B2: classical gradient-orientation descriptors degrade specifically under difficult (polar, low-Sun) illumination — consistent with the shadow-polarity argument.
- Established RIFT2 as a credible lunar-relevant multimodal classical baseline → included as **B7**.
- Establishes the prior-art bar we must exceed. Note their reported RMSE is a fit residual and is subject to the circularity critique in ANALYSIS §A.3, so it is not directly comparable to our held-out numbers. Comparisons must be like-for-like.

---

## S4 — Pretrained matchers for cross-modal remote-sensing registration ★ most influential

**Source (preprint):** *Are Pretrained Image Matchers Good Enough for SAR–Optical Satellite Registration?* — https://arxiv.org/html/2604.10217v4
**Retrieved:** 2026-08-24

**Facts extracted:**
- Benchmarked **24 pretrained matcher configurations** across detector-based (XFeat, ALIKED-LG, DeDoDe-LG, SuperPoint-LG, DISK-LG, GIM-LG, OmniGlue, SIFT-LG), detector-free dense (LoFTR, XoFTR, RoMa, Tiny-RoMa, RoMaV2, MINIMA variants, MA-ELoFTR) and 3D-derived (MASt3R, DUSt3R).
- SpaceNet9: **XoFTR and RoMa tie at 3.0 px** mean tie-point error; MA-ELoFTR 3.4 px. **Success@10: RoMa 94.2%, XoFTR 90.5%**, zero failures among top matchers.
- SRIF (600 pairs): **MINIMA-RoMa lowest error at 47.0 px**, zero failures. SARptical retrieval: MINIMA-RoMa **0.57 AUROC**.
- **"Protocol choices can change mean error by up to 33× for a single matcher"** — exceeding the gap between top-tier and mid-tier models.
- Affine vs homography geometry: mean error **12.3 px → 9.7 px** (affine better).
- Recommended deployment baseline: affine geometry, **512×512 tiles with 256 px overlap**, per-matcher normalisation (Z-score or percentile), RANSAC threshold **3 px** dense / **≥5 px** sparse → **<8 px mean error with no domain-specific training**.
- Latency: **XoFTR 0.4 s/pair vs RoMa 5.0 s/pair** (GPU).
- RoMa's robustness to large appearance shifts attributed to **frozen DINOv2 features**.
- MASt3R/DUSt3R showed "substantial protocol sensitivity" and less stable performance.

**Influence on design:**
- **This is the single most influential source in the project.** The 33× protocol finding is the direct basis for the C5 pluggable-matcher architecture and for the core thesis "the matcher is a replaceable part; the protocol is the contribution" (ANALYSIS §D.2, §D.4).
- Supplied concrete starting protocol values for EXP-006 (tile 512 / overlap 256 / τ = 3 or 5 / affine-first) instead of arbitrary guesses.
- The XoFTR-vs-RoMa latency ratio makes XoFTR the leading candidate engine under our CPU constraint (ANALYSIS §B8, EXP-005).
- Ruled MASt3R/DUSt3R out of early consideration on protocol-sensitivity grounds.

**Transfer caveat `[HYPOTHESIS]`:** all of this is SAR-optical satellite imagery, not lunar cross-modal. Transfer is plausible — both are cross-modal remote sensing with large appearance gaps — but **unproven for our data**. EXP-006 exists specifically to test it. We must not cite these numbers as if they were our own results.

---

## S5 — Modality-invariant matching

**Source (peer-reviewed, CVPR 2025):** *MINIMA: Modality Invariant Image Matching* — https://arxiv.org/abs/2412.19412
**Code:** https://github.com/LSXI7/MINIMA
**Retrieved:** 2026-08-24

**Facts extracted:**
- Scales up modalities from RGB-only matching data using generative models, inheriting matching labels and diversity from the RGB dataset; produces the **MD-syn** dataset.
- Any advanced matching pipeline can be trained on randomly selected modality pairs to acquire cross-modal ability; demonstrated for **LightGlue, LoFTR and RoMa**.
- Evaluated on 19 cross-modal cases including VIS-NIR, VIS-SAR, CT-MRI; reported to surpass modality-specific methods in in-domain and zero-shot settings.

**Influence on design:**
- Establishes the *method* by which a cross-modal capability could be added to an existing engine without lunar training labels — the template for candidate **C6** if EXP-005 shows a specific deficiency.
- Combined with S4 (MINIMA-RoMa best on SRIF/SARptical), it identifies MINIMA-wrapped engines as the accuracy ceiling to aim at, subject to the CPU constraint.
- **Caution recorded:** the generative-modality-synthesis approach is exactly what spec §52 warns about — synthetic training producing false confidence in generalisation. Any use requires validation on real lunar pairs, not synthetic ones.

---

## S6 — Contemporary matcher landscape

**Sources:** RoMa v2 — https://arxiv.org/html/2511.15706v1 · CM-Bench cross-modal benchmark — https://arxiv.org/html/2603.12690v1 · *Mismatched: Evaluating the Limits of Image Matching Approaches and Benchmarks* — https://arxiv.org/pdf/2408.16445
**Retrieved:** 2026-08-24

**Facts extracted:**
- RoMa v2 leads MegaDepth, ScanNet and four further datasets on EPE and match accuracy; **1.7× higher throughput than RoMa** at near-identical GPU memory.
- Cross-modal ranking: dense RoMa-family methods dominate; **MINIMA-RoMa best overall accuracy**.
- Efficiency tiers: MINIMA-ELoFTR and ELoFTR best in the semi-dense family; **XFeat (dense) the most lightweight**; RoMa-family and MASt3R strongest but substantially more expensive.

**Influence on design:**
- Fixed the engine shortlist by compute tier: **XFeat** (lightest, CPU-viable) → **ELoFTR / XoFTR** (mid) → **RoMa / MINIMA-RoMa** (GPU-only, aspirational ceiling).
- *Mismatched* reinforces the ANALYSIS §A.3 position that benchmark numbers must be read against their protocol, not taken at face value.

---

## S7 — Lunar slope statistics (terrain realism)

**Source (peer-reviewed):** Rosenburg et al., *Global surface slopes and roughness of the Moon from the Lunar Orbiter Laser Altimeter*, JGR Planets — https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2010JE003716
**Supporting (peer-reviewed):** *The steepest slopes on the Moon from LOLA data: spatial distribution and correlation with geologic features* — https://www.sciencedirect.com/science/article/abs/pii/S0019103516001147
**Supporting (primary):** NASA PGDA, *Lunar slopes and Hurst exponent* — https://pgda.gsfc.nasa.gov/products/70
**Retrieved:** 2026-08-24

**Facts extracted:**
- LOLA slopes are computed at a **25 m baseline**, with along-track point-to-point slopes at 57 m, 225 m and 560 m. Slope statistics are strongly **baseline-dependent**.
- At a **15 m baseline**: highlands median **9.1°**, mean **11.0°**, sd **7.0°**; mare median **3.5°**, mean **4.9°**, sd **4.5°**.
- The slope-frequency distribution shows a **steep rollover near the angle of repose**. Slopes significantly steeper than repose are **almost absent** on the Moon, because the fractured megaregolith lacks cohesion and no recent geological process produces them.
- The majority of slopes steeper than **32–35°** are associated with relatively young large impact craters.

**Influence on design:**
- Supplied the explicit targets for the EXP-002 terrain regimes: `A_mare_moderate` (median 3.5°) and `A_highlands_moderate` (median 9.1°), both of which the generator now hits exactly.
- Set `ANGLE_OF_REPOSE_DEG = 33.0` as the physical plausibility ceiling, and made "fraction of surface above repose" a reported statistic.
- **Condemned the EXP-001 terrain.** Measured at 89.55% of its surface steeper than the angle of repose (p99 ≈ 77°), it is physically impossible on the Moon. It is retained only as regime `C_extreme_diagnostic`.
- The baseline dependence is why `REFERENCE_BASELINE_M` is recorded alongside every slope target: a median slope is meaningless without one, and OHRC's 0.25 m/px samples a rougher regime than these 15 m figures describe.

**Caveat:** our synthetic pixel is nominally 1 unit and we interpret it at the 15 m baseline. Matching the *median* does not guarantee the distribution *shape* matches, which is why full percentiles are reported rather than a single number.

---

## S8 — Illumination-invariant matching on planetary imagery ★ direct prior art for EXP-004

**Source (peer-reviewed):** Wu, B., Zeng, H. & Hu, H., *Illumination invariant feature point matching for high-resolution planetary remote sensing images*, Planetary and Space Science **152**: 45–54 (2018) — https://www.sciencedirect.com/science/article/abs/pii/S0032063317303173 · ADS: https://ui.adsabs.harvard.edu/abs/2018P&SS..152...45W/abstract
**Supporting (peer-reviewed):** Wu et al., integrated photogrammetric and photoclinometric approach for illumination-invariant pixel-resolution mapping, validated on LROC NAC at the Chang'E-4 and Chang'E-5 sites — https://www.researchgate.net/publication/337679696
**Supporting (peer-reviewed):** *Robust Feature Matching of Multi-Illumination Lunar Orbiter Images Based on Crater Neighborhood Structure*, Remote Sensing **17**(13): 2302 (2025) — https://doi.org/10.3390/rs17132302
**Retrieved:** 2026-09-03

**Facts extracted:**
- Wu et al. observe **dual peaks in the histogram of SIFT dominant orientations** under differing solar azimuth, and level them with an **adaptive suppression Gaussian** folded into the SIFT descriptor stage, plus cross-checking and template matching in the match stage.
- Tested on Moon **and** Mars high-resolution imagery at illumination differences of **20°–180°**; recovers **40–60 % more matches** than classical SIFT.
- The photoclinometry-assisted matching (PAM) line matches on **recovered terrain rather than image intensity**, so illumination differences do not drive the cost function; reported robust on LROC NAC where conventional matching fails on subtle texture.
- The crater-neighbourhood work matches on **structural configuration of craters** rather than appearance, and ships an evaluation set of multi-illumination lunar orbiter image pairs (MiLOI).
- All three report **match count or match success**. None reports an independent accuracy reference, a failure-detection rate, or performance on non-overlapping pairs. `[LIMITATION of these sources]`

**Influence on design:**
- **EXP-004 must be re-scoped from discovery to replication.** Its pre-registered hypothesis — that SIFT's dominant-orientation assignment is biased by solar geometry — is Wu et al.'s 2018 published result, arrived at here independently. The stage report must say so, with this citation, and the method enters as a **baseline**, not as a contribution.
- Confirms the terrain-space matching direction (ANALYSIS §C.2) has real lunar validation behind it, and that it is **not novel on its own**. What remains open is bounding it geodetically and carrying its uncertainty into a decision.
- MiLOI is the nearest existing public benchmark for this project's exact problem and should be treated as a comparison target rather than ignored.

**Caveat:** these sources were reachable in abstract only; the per-method numeric tables were not read. The 40–60 % figure is quoted as the abstract states it and must not be re-reported as if verified here.

---

## S9 — Lunar geodetic control ★ supersedes "no ground truth exists"

**Source (peer-reviewed):** Barker et al., *A new lunar digital elevation model from the Lunar Orbiter Laser Altimeter and SELENE Terrain Camera* (SLDEM2015), Icarus **273**: 346 — https://www.sciencedirect.com/science/article/pii/S0019103515003450
**Source (peer-reviewed):** *Photogrammetric Processing of Regional ShadowCam and LROC NAC Controlled Mosaics, Evaluation of Positional Accuracies, and Scientific Applications*, Remote Sensing **18**(3): 525 (2026) — https://doi.org/10.3390/rs18030525
**Supporting (primary):** USGS Astrogeology, LOLA–Kaguya TC merged DEM, 60N–60S, 59 m — https://astrogeology.usgs.gov/search/map/moon_lro_lola_selene_kaguya_tc_dem_merge_60n60s_59m
**Retrieved:** 2026-09-03

**Facts extracted:**
- SLDEM2015 covers ±60° latitude at **512 pixels/degree (~59 m at the equator)**, built from ~4.5×10⁹ LOLA heights with 43 200 SELENE TC stereo DEMs co-registered to them.
- **LOLA absolute accuracy: typically <10 m horizontally and <1 m vertically.** Merged product typical vertical accuracy **3–4 m**.
- After co-registration ~90 % of TC DEMs show <5 m RMS vertical residual against LOLA, against ~50 % before.
- **LROC NAC regional controlled mosaics**: median positional offsets **<12 m in latitude and <5 m in longitude**; average measured offset **<13 m** from true position, at 0.5–2 m/px.

**Influence on design:**
- **Forces a correction to a standing project claim.** "No ground truth exists for these products" is true for *correspondences* and false for *geodetic control*. At NAC resolution a 13 m controlled-mosaic offset is roughly **7–26 px** — far tighter than the ~105.6 px archive-geometry discrimination floor currently reported as the best available corroboration (REAL-DATA-04 §11.2).
- Makes an externally-referenced accuracy statement possible for the first time: disagreement against a controlled product whose own uncertainty is published, rather than a fit residual.
- Supplies the coarse tier of any geodetic anchoring design, and bounds it: 59 m control against 0.25–2 m imagery is a **30–120× resolution gap**, which is the quantity any anchoring cascade must actually close.

**Caveat:** SLDEM2015 stops at ±60°, so polar work needs a different control product. Controlled-mosaic coverage is regional, not global — availability over a chosen ground window must be checked before a stage depends on it.

---

## S10 — Photometric normalisation practice for lunar imagery

**Source (peer-reviewed):** Sato et al., *Resolved Hapke parameter maps of the Moon*, JGR Planets **119** (2014) — https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2013JE004580
**Supporting (primary):** USGS ISIS photometric applications (`photomet`, `lronacpho`) — https://isis.astrogeology.usgs.gov/
**Retrieved:** 2026-09-03

**Facts extracted:**
- Established practice for NAC: the **Moon Mean photometric correction** (`lronacpho`) below ~60° incidence; a **Hapke model with a Henyey–Greenstein single-particle phase function** above it.
- Sato et al. derive near-global resolved Hapke parameter maps from 21 months of WAC multispectral observations and normalise observed reflectance to **standard angles i = g = 60°, e = 0°**, tile by tile.
- Hapke-model limitations are a recognised source of residual photometric error in mosaics.

**Influence on design:**
- Identifies a **missing pipeline stage**. This project measured an illumination failure threshold using a pipeline with no photometric correction at all; the threshold is therefore a property of *uncorrected* RootSIFT until the stage exists. This must be stated wherever the illumination result is stated.
- Fixes the normalisation target as the community standard geometry, so outputs are comparable with published lunar photometric work rather than an internal convention.
- **Constrains the correction to be instrument-conditional.** Per S1, IIRS beyond ~3 µm is thermal-emission dominated, so a reflectance-domain photometric model is invalid there until thermal emission is separated; the panchromatic instruments need no such step. A uniform correction across all four instruments would be physically wrong.

---

## S11 — Registration accuracy estimation without ground truth ★ constrains our novelty claim

**Source (peer-reviewed):** *Multimodal Remote Sensing Image Registration with Accuracy Estimation at Local and Global Scales*, IEEE TGRS — https://arxiv.org/abs/1602.02720
**Supporting (peer-reviewed):** *Bootstrap Resampling for Image Registration Uncertainty Estimation Without Ground Truth* — https://www.researchgate.net/publication/224584494
**Supporting (peer-reviewed):** *Multi-Resolution SAR and Optical Remote Sensing Image Registration Methods: A Review, Datasets, and Future Perspectives* — https://arxiv.org/abs/2502.01002
**Retrieved:** 2026-09-03

**Facts extracted:**
- The **RAE** method estimates a **Cramér–Rao lower bound on registration error per local correspondence**, from local texture and noise properties, **without ground truth**, and uses it as an *input* to reject outliers rather than only as an output metric.
- **Bootstrap resampling** is an established alternative for estimating registration uncertainty without ground truth.
- The MultiResSAR review tested **16 state-of-the-art algorithms** on >10k multi-resolution SAR/optical pairs: **no algorithm achieves 100 % success, performance falls as resolution rises, and most fail on sub-metre data.** Best deep method **XoFTR 40.58 %**; best traditional **RIFT 66.51 %**.

**Influence on design:**
- **Withdraws a claim.** Ground-truth-free accuracy estimation is *not* an open gap; it has a literature. Any project statement claiming novelty for GT-free accuracy must be removed. What survives is narrower: a **geodetically traceable** budget anchored to S9's published bounds, combined with a calibrated decision.
- Strengthens the case for failure detection as the contribution rather than matching: at 40–67 % success on sub-metre cross-modal data, the operationally decisive quantity is knowing *which* outputs to believe.
- CRLB-per-correspondence is a candidate signal for the trust engine and should be evaluated against the existing signals rather than assumed better or worse.

---

## S12 — Uncertainty with finite-sample statistical guarantees

**Source (peer-reviewed, CVPR 2023):** *Object Pose Estimation with Statistical Guarantees: Conformal Keypoint Detection and Geometric Uncertainty Propagation* — https://arxiv.org/abs/2303.12246
**Retrieved:** 2026-09-03

**Facts extracted:**
- Inductive conformal prediction converts heuristic keypoint detections into **prediction sets covering the true keypoint with a user-specified marginal probability**.
- Those sets propagate to a **pose uncertainty set (PURSE)** containing the true pose at the same probability; semidefinite relaxation yields **computable worst-case error bounds**.
- Guarantees are finite-sample valid, conditional on an **exchangeable** calibration set.

**Influence on design:**
- The machinery the verdict engine's ordinal bands would need to become a decision with a stated error rate.
- **Records the blocker honestly:** exchangeability. Six real edges are not a calibration set, so calibration must be synthetic — and this project has already measured its synthetic illumination model mispredicting real behaviour in both directions (EXP-001/003 against REAL-DATA-03/04). Any bound reported on archive imagery is therefore *conditional on a transfer assumption that is itself under test*, and must be labelled so.
- No planetary or remote-sensing application of this machinery was found, which is what makes the transfer a candidate contribution rather than an application.

---

## S13 — Planetary bundle adjustment toolchain, licences and platform

**Source (primary):** NASA Ames Stereo Pipeline documentation — https://stereopipeline.readthedocs.io/ · repository https://github.com/NeoGeographyToolkit/StereoPipeline
**Supporting (peer-reviewed):** Beyer et al., *The Ames Stereo Pipeline: NASA's Open Source Software for Deriving and Processing Terrain Data*, Earth and Space Science (2018) — https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2018EA000409
**Supporting (primary):** USGS ISIS and the `jigsaw` bundle adjustment — https://isis.astrogeology.usgs.gov/
**Supporting (preprint):** *Sub-metre Lunar DEM Generation and Validation from Chandrayaan-2 OHRC Multi-View Imagery Using an Open-Source Pipeline* — https://arxiv.org/abs/2604.01032
**Retrieved:** 2026-09-03

**Facts extracted:**
- ISIS **jigsaw** and ASP **bundle_adjust** perform simultaneous least-squares adjustment of camera pointing over a **control network**; ASP reads and writes the ISIS jigsaw binary control-network format, so solutions are interoperable.
- **ASP is Apache-2.0.** ISIS is USGS open source. ASP 3.7.0 installs via conda together with ISIS 10.0.0.
- **Neither ships Windows binaries.** The supported route on Windows is **WSL** with the Linux build. `[PLATFORM CONSTRAINT — this project develops on Windows]`
- OHRC was processed by an external group using ASP + ISIS + ALE + Ceres, with a **custom PDS4 import template and Community Sensor Model configuration**, because **no stable ISIS release supports OHRC natively**. Validation against NAC DTMs gave 5.85 m vertical RMSE and ~30 cm horizontal agreement.
- Chandrayaan-2 products are distributed in **PDS4** via ISRO's Map Browse facility, with SPICE kernels from the PRADAN archive.

**Influence on design:**
- Establishes that rigorous network adjustment is available under a permissive licence and need not be reimplemented, and that the control-network format is the interoperability contract that lets an external photogrammetrist verify our solution.
- **Discharges part of the "Chandrayaan-2 formats unknown" entry below:** the format is PDS4 and the access path is public.
- Names the two costs to schedule rather than discover: a **WSL environment**, and an **OHRC sensor-model configuration** that does not exist in any stable release.

---

## S14 — Matcher and weight licensing ★ discharges the R7 audit for the sparse family

**Source (primary):** MINIMA repository, Apache-2.0 — https://github.com/LSXI7/MINIMA
**Supporting (primary):** OpenCV 5 feature module — `ALIKED_create`, `DISK_create`, `LightGlueMatcher_create`, `AffineFeature_create`
**Supporting:** SuperGlue / SuperPoint (Magic Leap) licence terms — academic / non-commercial use only
**Retrieved:** 2026-09-03

**Facts extracted:**
- **SuperGlue and the original SuperPoint weights are non-commercial only.** R2D2 carries a comparable restriction.
- **MINIMA is Apache-2.0.**
- **OpenCV 5 core ships DISK, ALIKED and LightGlue** as ONNX-loading detectors/matchers under OpenCV's own Apache-2.0 licence; the ONNX weight files are distributed separately and each needs its own licence check.
- OpenCV 5 **moved AKAZE, KAZE and BRISK out of core into `opencv_contrib`**; `AffineFeature` (ASIFT) remains in core.

**Influence on design:**
- **Rules SuperGlue and original SuperPoint out of the deliverable** under ADR-0008. A submission to a space agency cannot rest on non-commercial weights, and this is now verified rather than recalled — the standing "verify against the actual license text" note in the table below is discharged for these two.
- Names the admissible route to baselines B4/B6: OpenCV-native DISK/ALIKED with LightGlue, or MINIMA-wrapped engines, subject to a per-weight ONNX licence check.
- **Forced a recorded substitution in B2.** AKAZE, the §E.1 nomination, is unavailable on OpenCV core builds. B2 is implemented as **ASIFT** — which S3's incumbent Chandrayaan-2 comparison also benchmarks, making the arms directly comparable — and AKAZE is retained as a separate registry entry `B2K` that refuses with an explanatory error rather than being silently swapped.

---

## Unresolved / blocked

*(Updated 2026-09-03. Two entries below are **discharged** by S13 and S14 and are kept with
their original wording struck through rather than deleted, so the record shows what was
believed and when it changed.)*

| Item | Status | Blocker | Plan |
|---|---|---|---|
| ~~Chandrayaan-2 product formats, processing levels, metadata schema~~ | **DISCHARGED (S13)** | ~~ISSDC PRADAN product listing is behind an authenticated endpoint~~ | Products are distributed in **PDS4** via ISRO's Chandrayaan-2 Map Browse facility, with SPICE kernels from PRADAN; an external group has published a full OHRC pipeline built on that access path. What remains is not a format unknown but two scheduled costs: **no stable ISIS release supports OHRC natively** (a custom PDS4 import template and Community Sensor Model configuration are required), and the toolchain needs **WSL** on this project's Windows machine. |
| ~~License terms of each candidate pretrained weight file~~ | **PARTIALLY DISCHARGED (S14)** | ~~Not yet audited~~ | Verified: **SuperGlue and the original SuperPoint weights are non-commercial only** and are therefore inadmissible under ADR-0008 — the earlier "believed … verify against the actual license text" note is now resolved, and the belief was correct. **MINIMA is Apache-2.0.** OpenCV 5 ships DISK, ALIKED and LightGlue under Apache-2.0 code. **Still open:** the licence of each individual ONNX weight file, which must be checked per file before it enters the repository. |
| Whether the SIH evaluation set supplies overlapping triplets | `[UNKNOWN]` | Dataset not in hand | Construct triplets from LRO NAC for development regardless (F.1.4). |
| Availability of an LROC NAC **controlled mosaic** over the REAL-DATA ground windows | Open | Controlled-mosaic coverage is regional, not global (S9) | Check coverage before any stage depends on it. If present, it supplies the first externally-referenced accuracy check this project has had — at roughly 7–26 px at NAC resolution, against the ~105.6 px archive-geometry floor currently in use. |
| Whether the measured illumination threshold survives photometric correction | Open | The photometric normalisation stage does not exist (S10) | Until it does, every illumination result is a property of an **uncorrected** pipeline and must be stated that way. Register the criterion before running, so a null result is as reportable as a positive one. |
