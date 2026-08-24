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

## Unresolved / blocked

| Item | Status | Blocker | Plan |
|---|---|---|---|
| Chandrayaan-2 product formats, processing levels, metadata schema | `[UNKNOWN]` | ISSDC PRADAN product listing is behind an authenticated endpoint (`/ch2/protected/payload.xhtml`); public pages do not state formats | Resolve via authenticated access in parallel with Phase 2. **Do not invent** (spec §72). IO layer stays format-agnostic until known. |
| License terms of each candidate pretrained weight file | Open | Not yet audited | Audit before any weight enters the pipeline (risk R7). SuperGlue in particular is believed research-/non-commercial-restricted — **verify against the actual license text, do not rely on this recollection.** |
| Whether the SIH evaluation set supplies overlapping triplets | `[UNKNOWN]` | Dataset not in hand | Construct triplets from LRO NAC for development regardless (F.1.4). |
