# Stage Index

Navigable list of every stage. For the chronological narrative see [`../STAGE_HISTORY.md`](../STAGE_HISTORY.md); for cross-stage failures and decisions see [`ERROR_LEDGER.md`](ERROR_LEDGER.md) and [`DECISION_LEDGER.md`](DECISION_LEDGER.md).

**A stage is added here only once it has actually run.** Planned stages appear with status `NOT STARTED` and no results.

---

| Stage ID | Name | Objective | Status | Key result | Major failure discovered | Next stage |
|---|---|---|---|---|---|---|
| **PHASE-0** / EXP-000 | [Geometry gate](PHASE-0_GEOMETRY.md) | Establish a verified geometry layer and coordinate contract before any measurement can be trusted | **COMPLETE — PASS** | All 5 transform models recover at **~1e-13 px** against a 0.1 px gate; Hartley holds condition ~3.4 across 512 → 60 000 px | **E-001**: naive resampling update `p' = s·p` wrong by `(s−1)/2` px — **1.0 px at s = 3**, invisible in imagery | EXP-001 |
| **EXP-001** | [RootSIFT classical baseline](EXP-001_ROOTSIFT.md) | Establish a trustworthy classical baseline **and** a non-circular evaluation harness before any learned matcher | **COMPLETE** | Illumination is the dominant failure axis — a **cliff**, not a slope. Strong under fixed illumination (0.009–0.386 px, ≥ 99.7% true precision) | **E-008**: 11 of 17 failures reported fit RMSE **< 1e-12 px while 190–2400 px wrong**. **E-005**: GT generator wrong by 56.57 px while reporting 99.6% inliers | EXP-002 |
| **EXP-002** | [Evaluation, realism and RANSAC](EXP-002_EVALUATION_REALISM_RANSAC.md) | Fix the RANSAC defect; make terrain physically realistic; validate the failure threshold non-circularly; build and score the GT-free estimators | **COMPLETE** | LO-RANSAC **54.29 s → 0.056 s (~968×)** with robustness unchanged; **loop closure is the only GT-free estimator that detects a coherent wrong answer** (1.000 / 0.000) | **E-007**: discarded 4230×4230 SVD `U` (17.9 M elements) — 493× waste. **E-009/E-013/E-014**: circular threshold claim, physically impossible terrain, and a cliff located too optimistically | EXP-003 |
| **EXP-003** | [Illumination-robust representations](EXP-003_illumination_robust_representations.md) | Test whether a polarity-agnostic representation moves the illumination cliff beyond Δaz 30° on realistic terrain | **COMPLETE — S1 NOT MET** | **No arm met the pre-registered bar.** Mare best 21° (baseline). mod-π was the *worst* arm: 0 wins / 38 losses vs its own 2π control on identical keypoints. Loop closure 1.000/0.000 at loop level | **E-003.4**: SIFT's dominant-orientation assignment drifts ~1:1 with Sun azimuth (6.7° → 44.8° as Δaz 0° → 45°) — the failure is orientation **assignment**, not binning. **E-003.2**: loop closure mislabelled edge-level, moving false alarm by 0.617 | EXP-004 (not a learned matcher) |
| **REAL-DATA-01** | [Real LRO NAC ingestion and first real registration](REAL-DATA_LRO_NAC.md) | Turn acquired LRO NAC metadata into decoded, provenance-tracked, sanity-checked real image tiles, and measure what the **unmodified** pipeline does with them | **COMPLETE — ingestion SUCCEEDED, registration FAILED (class C)** | **Ingestion, decoding and sanity validation all succeed; the first real registration does not.** 3 inliers / 35 putative at **fit RMSE 1.575e-12 px** → **REJECTED**. E-008 reproduced on real lunar data for the first time. **Cause unattributed** between the overlap and illumination hypotheses | **E-022**: a `Product_Browse` label accepted for 4 of 6 products, both halves of the best pair included. **E-023**: the decode statistic collapsed onto the `-32768` sentinel border — **E-010 recurring**. **E-025**: a second acquisition silently overwrote the first tile, making four conditions return identical results | **REAL-DATA-02** — establish real overlap independently of the matcher |
| **REAL-DATA-02** | [Independent real-image overlap verification](REAL-DATA-02_overlap_verification.md) | Establish, **independently of the feature matcher**, whether the REAL-DATA-01 tile pairs cover the same ground | **COMPLETE — question answered** | **The headline pair does NOT overlap.** Its two tiles are **22.75 km apart**, intersection **0.0000 km²** — so REAL-DATA-01's 3-inlier result measured nothing about the matcher. The same products cropped at H2 **do** overlap (**68.6 % / 70.5 %**, IoU 0.533) and still returned only 5 inliers, which is the project's **first interpretable real-data result**. Terminator pair **UNKNOWN** (28.3 %) | **E-028**: the line-direction hypothesis was applied globally to a pair and it is per-frame — `LRO_FLIGHT_DIRECTION` decides it, and the archive publishes it. **E-029**: cross-track tile position was never matched, costing 1.1–1.7 km against a 1.8 km tile. **E-027**: a `NORTH_AZIMUTH` cross-check with no discriminating power — E-024 recurring | **REAL-DATA-03** — geometry-driven re-acquisition + a third product for loop closure |
| **REAL-DATA-03** | [The first correctly controlled real-data registration experiment](REAL-DATA-03_real_overlap_registration.md) | Acquire a real NAC pair at geometry-derived windows, verify overlap independently **before** interpreting anything, run the **unmodified** baseline, and close a real three-image loop | **COMPLETE — the experiment is valid; 2 of 3 edges FAIL, 1 SUCCEEDS** | **Overlap CONFIRMED first: 97.12 % / 82.72 % / 85.00 %.** The unmodified baseline then gives **4 inliers** at Δincidence 39.8° and **5365 inliers** (ratio 0.9950) at Δincidence 0.96° — on the same mare, same code. **Seven candidate causes eliminated by measurement**; illumination is the only survivor and is **not** claimed as the cause. First real loop closure: **1201.04 px**, three independently estimated edges. The succeeding edge's scale matches a SPICE-derived archive field to **0.04 %** | **E-030**: the raw-tile cache was keyed by product, not window — **E-025 recurring in a second script**, feeding one tile's bytes into another's decode evidence. **E-031**: a figure crash destroyed a set of checks that had already passed, because the report was written after the plot | **REAL-DATA-04** — one low-incidence frame to break the Δincidence / frame-identity confound |
| **REAL-DATA-04** | [Can frame identity and illumination be separated?](REAL-DATA-04_illumination_vs_frame_identity.md) | Break the Δincidence / frame-identity confound with one more real low-incidence frame, against a decision table frozen before the data existed | **COMPLETE — ANSWERED. D↔A succeeds, D↔B fails** | **Overlap CONFIRMED first: 97.87 % / 71.30 % / 70.35 %**, with the two decisive edges matched to **0.95 pp**. The unmodified baseline then gives **1656 inliers** (ratio 0.9414, coverage occupancy **1.000**) at Δincidence **11.73°** and **3** at **51.54°** — **D↔A succeeds, D↔B fails: the first row of the pre-registered table.** Across **six** real edges, five frames and two ground windows, **every frame now appears in both a succeeding and a failing edge**, so frame identity predicts nothing and **Δincidence predicts all six**. The succeeding edge's scale matches SPICE-derived `SCALED_PIXEL` to **0.04 %** and is the only edge in either stage below the corner-polygon discrimination floor (0.53×). **Illumination attributed (D-040); frame identity refuted; frame A cleared.** | **E-032**: the `LRO_FLIGHT_DIRECTION` rule for which latitude line 0 sits at is **not a rule** — 8/10, two counterexamples; the `NORTH_AZIMUTH` cross-check quoted for it had **no discriminating power** in the sample it was validated on, and tracks the *cross-track* sense instead. Prose corrected, no code defect | **September 2 demo engineering.** The causal question is answered; scientific expansion stops here |

**Stage test counts.** Suite total after REAL-DATA-01: **260 passed, 2 skipped** (194 → 260; `src/siim/ingest` went from **0** tests to **61**, plus 5 demo-integration
tests). After **REAL-DATA-02**: **357 passed, 2 skipped** (260 → 357; +71 footprint geometry, +21 index table, +5 PDS4 display direction). After **REAL-DATA-04**: **398 passed, 2 skipped** (376 → 398; +12 frame-D screening including the orientation signature of E-032, +10 tile-admissible geometry). After **REAL-DATA-03**: **376 passed, 2 skipped** (357 → 376; +6 raw-tile cache, +13 tile-window and predicted-correspondence geometry).

---

## Stage detail

### PHASE-0 / EXP-000 — Geometry gate

**Objective.** Make every later measurement trustworthy. The project's central claim — that a fit residual is not an accuracy — only has force if the geometry underneath is known-correct, and coordinate errors fail *silently*.

**Acceptance criterion (set in advance):** recover a known synthetic transform to **< 0.1 px** true endpoint error.

**Key results.** ~1e-13 px across all five models (50 trials each) · condition number flat at ~3.4 from 512 to 60 000 px coordinate extent · contract C4 exact where the naive form errs by up to 1.0 px · identity warp exact (5.55e-16) · 1.25–2.45 ms/fit, 19.5 ms per 256² cubic warp.

**Failures found:** E-001 (scale convention), E-002 (conditioning), E-003 (zero-fill ambiguity), E-004 (aliasing).

**Verdict:** PASS on all seven objectives. **Decisions:** D-007 accepted.

---

### EXP-001 — RootSIFT classical baseline

**Objective.** A trustworthy classical baseline **and** a non-circular evaluation harness — the harness being the more important half.

**Design.** 45 cases in seven groups; 512² images from a 1024² height field; exact synthetic ground truth throughout. **No calibration/validation split** — a documented weakness EXP-002 corrected.

**Key results.** Fixed illumination: 0.009–0.386 px, ≥ 99.7% true precision, 0.387 s median. Illumination: cliff between Δaz 30° (0.290 px) and 45° (325.59 px). Elevation survivable (Δel −30° → 0.750 px). Scale to 4×. Mare worst case: **2 putative matches** at Δaz 60°. Repetitive lattice at full ambiguity: error **exactly 64.008 px = one lattice period**. **17 of 45 cases wrong.**

**Failures found:** E-005 (GT `pad` offset), E-006 + E-007 (RANSAC, deferred), E-008 (fit RMSE), E-016 (RootSIFT claim), E-018 (§B6 overstated).

**Refuted hypotheses:** shadow-reversal hypothesis too narrow (45°, not 180°) · §B6 overstated · "high confidence + wrong" did not materialise · RootSIFT advantage unestablished.

**Verdict:** 3 PASS, 3 PARTIAL, 1 FAIL (expected — Challenge B is the gap the project exists to close), 3 NOT TESTED. **Decisions:** D-003, D-009, D-010, D-013–D-016.

---

### EXP-002 — Evaluation, realism and RANSAC

**Objective 1 — RANSAC performance.** Two independent defects: a discarded `(2N × 2N)` SVD `U` (E-007, 493×) and LO firing on every sample rather than on a new best (E-006, 198 → 3 refits). **54.29 s → 0.056 s (~968×)**, same inlier set, robustness unchanged (recall 1.000 at 0–80% outliers). EXP-001 re-run: **0/45 flips**, tolerance **±0.59 px**.

**Objective 2 — Terrain realism.** Four regimes with explicit slope targets anchored to LOLA statistics. A-regimes hit the published medians exactly (3.50 / 9.10). **EXP-001's terrain: 89.55% above the angle of repose** — physically impossible. Density separable from geometry (24× range at fixed 9.10°). Old terrain **retained** as a diagnostic; old results preserved.

**Objective 3 — Threshold validation.** 192 calibration + 192 validation cases, disjoint seeds. EXP-001's separation claim **refuted** (correct min = 2 inliers); the operating rule `n_inliers < 8` **validated** (recall 1.000, FPR 0.0112). `fit_rmse` negative control: **ROC AUC 0.495 — chance**. `split_consistency`'s apparent 0.994 exposed as an `inf`-sentinel artefact (E-010).

**Objective 4 — GT-free estimators.** Constructed adversarial cases with 300 correspondences. Held-out residual and split consistency: **detection 0.200**, blind to every coherent wrong solution (64 px wrong → 0.468 px residual, *lower* than a correct noisy set). **Loop closure: 1.000 detection / 0.000 false alarm**, error accumulating to 190.08 px ≈ 3 × 64.

**Failures found:** E-006, E-007, E-009, E-010, E-011, E-012, E-013, E-014, E-015, E-017.

**Verdict:** all 13 stated acceptance criteria PASS. **Decisions:** D-011, D-012 accepted; D-017–D-022 recorded; ADR-0003 discharged with its primary/secondary ordering reversed.

---

### EXP-003 — Illumination-robust representations — **COMPLETE, S1 NOT MET**

**Pre-registered** (Part 1 fixed before implementation): a representation earns its place only if the last fully-successful Δazimuth is **strictly > 30°** on both realistic A-regimes. 6 arms × 3 regimes × 3 seeds × 11 azimuths = **594 evaluations**, one shared image pair per case; plus 108 loop-closure triplets.

**Verdict: `S1_MET_BY_ANY_ARM = false`.** Last fully-successful Δaz — mare / highlands / B: baseline **21/27/27** · mod-π **0/21/27** · 2π control **18/27/40** · phase congruency **void/27/30** · RIFT2-MIM **void/0/27**. The two PC arms fail the Δaz = 0 positive control on mare (24 keypoints at 384²), so their mare results are void.

**H-3.1, H-3.2, H-3.3 refuted. H-3.4 refuted in the opposite direction** — mod-π wins 0, loses 38, ties 61 against its own control. **H-3.6 refuted on FPR**: `n_inliers <= 8` recall transfers (0.9857) but FPR does not (0.0112 → **0.3692**).

**The one positive effect came from a control arm**, and a direct probe found why: SIFT's orientation assignment drifts ~1:1 with Sun azimuth. Post-hoc, not pre-registered, held as D-024 rather than accepted.

**Decisions:** ADR-0004 **SUPERSEDED**; D-024–D-028 recorded. **Stop-condition 1 fired — learned matchers remain deferred (D-028).**

*(Original planned scope, retained:)*

**Criterion to be set in advance:** a representation earns its place only if it moves the last fully-successful Δazimuth **beyond 30° on A-regimes**.

Planned: report per regime, never pooled · realistic mare as the priority case · `n_inliers < 8` as the success criterion, never `fit_rmse` · loop closure as the only trustworthy GT-free check · resolve the cliff edge at 18/21/24/27°, ≥ 3 seeds.

**Explicitly out of scope until this stage runs:** RIFT2, phase congruency, orientation-mod-π, and every learned matcher.

---

### REAL-DATA-01 — Real LRO NAC ingestion and first real registration — **COMPLETE; registration FAILED**

**Report:** [`REAL-DATA_LRO_NAC.md`](REAL-DATA_LRO_NAC.md) · **Date:** 2026-08-25 · **Artefacts:** `experiments/REAL-DATA/`, `data/manifests/real_pair_*_manifest.json`

**Not an EXP-numbered experiment.** No hypothesis was pre-registered, because this is an ingestion and instrumentation stage. Everything in it is reported as measurement, not as a validated claim.

**What this stage is NOT.** It is **not** completion of the Chandrayaan-2 objective. OHRC / TMC-2 / IIRS remain behind ISSDC authentication; no such data was obtained, simulated or implied. Both frames here are the **same instrument**, so **no multi-modal claim** is supported. Sub-solar azimuth is not published for these products (E-020), so **no Sun-azimuth claim** is supported either — the pairs are illumination-varied by *incidence* only.

**Objective.** Convert LRO NAC metadata into decoded real image tiles that can enter the registration pipeline, and run the existing RootSIFT baseline **unmodified**, so the first real-data result measures the pipeline as built rather than one tuned to the answer.

**Outcome, stated in the terms the stage must preserve:**

| | |
|---|---|
| acquisition | **SUCCESS** — 4 tiles, 166 MB byte-range fetched, SHA-256 recorded and shown reproducible |
| decoding | **SUCCESS** — PDS4 `Array_2D_Image`, `SignedLSB2`, `file_size` identity exact on all four products |
| sanity validation | **SUCCESS for the usable tiles** (autocorr 0.9590 / 0.9415); correctly FAILS the terminator tile on **data quality**, not on decoding |
| **registration** | **NOT SUCCESSFUL** |
| verdict | **class C / REJECTED** |
| ground truth | **unavailable** — none exists for these products |
| cause | **UNRESOLVED** between the overlap and illumination hypotheses |

**Key results.** Positive controls bound the interpretation: self-registration recovers identity to **1.14e-12**, and a known (+40, +25) px shift on real imagery is recovered as **(40.142, 24.941)** — so the failure is *not* an ingestion or pipeline defect. All four H1/H2 line-direction combinations fail (3, 4, 4, 5 inliers), so the direction ambiguity is not the explanation either. **Loop closure was not run** — it needs a third overlapping real product, which was not acquired.

**Failures found:** E-022, E-023, E-024, E-025 (all `FIXED`), E-026 (`DOCUMENTED`).
**Decisions:** D-029 (incidence ceiling, *recorded not implemented*), D-030 (overlap is approximate), D-031 (class C, cause unattributed), D-032 (sanity gate before the pipeline).
**Research log:** RL-026 … RL-030; open threads RL-028b, RL-029b, RL-030b.

**Next dependency.** **REAL-DATA-02** must establish real overlap **independently of the matcher** — otherwise every real registration failure remains uninterpretable. EXP-004 is unaffected and remains pre-registered and not started.
---

### REAL-DATA-02 - Independent real-image overlap verification

**Not an EXP-numbered experiment.** It measures the *data*, not a method. Criteria were nonetheless fixed in code before any pair was classified.

**Objective.** Answer one question and optimise nothing else until it is answered: **did we actually give the matcher two overlapping pieces of the Moon?**

**Why it was blocking.** REAL-DATA-01's only overlap evidence *was* the registration it was trying to explain (D-030, D-031, RL-029b). Overlap evidence derived from the matcher cannot adjudicate the matcher.

**Method, and its independence.** Ground footprints computed from the PDS archive index table's **named** frame corners (`UPPER_LEFT_LATITUDE` ... `LOWER_RIGHT_LONGITUDE`), bilinearly interpolated to the integer tile windows already in the REAL-DATA-01 manifests, projected onto one common local plane and intersected exactly. `src/siim/ingest/footprint.py` imports only `numpy`, **reads no pixel**, and would give identical numbers if `siim.matching` were deleted. Registration artefacts are opened only after every classification is fixed, in code.

**The geometry audit came first, and two of four sources are empty.** The PDS4 label carries no `Cartography` or `Geometry` at all; the 5064-byte PDS3 attached header inside the `.IMG` carries no geometry keywords either (both checked, the second fetched live). ODE's `Footprint_geometry` is a ring whose **vertex order is undocumented** - it cannot say which vertex is line 0, and getting that wrong mirrors a tile by up to a whole 48 km frame. The archive index table names its corners, which is the ingredient that makes the question answerable.

**Pre-registered criteria.** CONFIRMED if the pessimistic (p5) shared fraction of the worse-covered tile >= 0.50; INSUFFICIENT if the optimistic (p95) < 0.20; otherwise UNKNOWN. 0.50 is anchored below the measured **0.757** worst-case overlap of the only regime this project has ever tested its matcher in (`scripts/exp002_common.py`). Uncertainty: 4000 Monte Carlo draws (seed 20260826) over the +/-0.005 deg corner quantisation.

| tile pair | intersection | IoU | shared fraction (worse tile) | p5-p95 | class |
|---|---|---|---|---|---|
| `usable_H1` - **the headline run** | **0.0000 km2** | 0.0000 | **0.0 %** | 0.0-0.0 % | **INSUFFICIENT** |
| `usable_H2` | 4.9653 km2 | 0.5330 | **68.59 %** | 62.9-74.1 % | **CONFIRMED** |
| `terminator_H1` | 2.2375 km2 | 0.1835 | 28.29 % | 23.4-33.0 % | **UNKNOWN** |
| `usable_A@H1_B@H2` | 0.0000 km2 | 0.0000 | 0.0 % | 0.0-0.0 % | INSUFFICIENT |
| `usable_A@H2_B@H1` | 0.0000 km2 | 0.0000 | 0.0 % | 0.0-0.0 % | INSUFFICIENT |

**Key results.** The `usable_H1` tile centres are **22.75 km** apart against a 3.98 km tile - it would take a ~20 km systematic geolocation error to bring them into contact, ~130x the 152 m corner quantisation. REAL-DATA-01 section 4.5's conclusion that the direction hypothesis "is not the explanation" is corrected: exactly one of its four rows had overlapping tiles, and the other three could not have succeeded. Two corroborations support the corner naming - pixel scale agreeing with SPICE-derived `SCALED_PIXEL_HEIGHT`/`WIDTH` within **1.2 % over 8 comparisons**, and a 2-2 `LRO_FLIGHT_DIRECTION` partition that matches exactly. The unexplained **1.05** m/line ratio of REAL-DATA-01 section 18 is closed: it was a comparison against `Map_resolution`, which is not the down-scan pixel scale.

**What it does NOT establish.** No registration succeeded, none was run. The `usable_H2` failure is **not** attributed - illumination, mare texture poverty (D-026), decimation, resolution ratio and relief displacement are all live and untested. `SUB_SOLAR_AZIMUTH` was **found** in the index table and deliberately **not used**; these pairs remain illumination-varied by incidence only, **not azimuth-controlled**. No Chandrayaan-2, no multi-modal claim. Confirmed overlap is shared ground, not a known transform.

**Failures found:** E-027 (`FIXED`), E-028 and E-029 (`DOCUMENTED`, fix deferred to REAL-DATA-03). All three are **design mistakes, not code defects** - the 260-test suite was passing throughout and could not have caught any of them.
**Decisions:** D-033 (geometry-driven tile windows, *recorded not implemented*), D-034 (interval-based overlap criteria); **D-030 discharged**, D-031 transferred to `registration_usableH2.json`.
**Research log:** RL-031, RL-032; **RL-029b closed**; open threads RL-031b, RL-032b.

**Next dependency.** **REAL-DATA-03** - re-acquire the usable pair at the geometry-derived windows (projected **97.1 %** overlap; exact `line0`/`sample0` already computed), and acquire a **third overlapping product** so loop closure meets real data for the first time. No matcher change is justified until a real pair capable of succeeding has been supplied. EXP-004 remains pre-registered and not started.
---

### REAL-DATA-03 - The first correctly controlled real-data registration experiment

**Objective.** Not a search for a successful registration -- a search for a **valid** one. Give the unmodified baseline two real lunar images that are known, independently of the matcher, to show the same ground, and accept whatever comes out.

**The gate, enforced in code (D-035).** `verify_tile_overlap.py --require-confirmed` exits non-zero unless every edge is OVERLAP_CONFIRMED, and was run as a separate command **before** the baseline. REAL-DATA-01's headline was a 3-inlier failure on tiles later shown to be 22.75 km apart, and it could not tell.

**Acquisition.** Geometry-driven (D-033, now implemented): every tile centred on one ground point (lon 22.033852, lat 20.035253) by inverting a bilinear ground map from the archive's **named** frame corners, with the line direction read **per frame**. Windows: A `l17955 s1811`, B `l29822 s1227`, C `l9088 s717`, all 4096x2048. A and B reproduce REAL-DATA-02's projected windows exactly, by an independent code path.

| edge | overlap (worse tile) | IoU | p5-p95 | class |
|---|---|---|---|---|
| A <-> B | **97.12 %** | 0.9695 | 90.03-97.31 % | **CONFIRMED** |
| A <-> C | 82.72 % | 0.8272 | 78.57-86.38 % | **CONFIRMED** |
| B <-> C | 85.00 % | 0.8500 | 80.62-88.60 % | **CONFIRMED** |

Tile centres **1 metre** apart on the primary edge. All three tiles PASS sanity; none discarded.

**The result.** Baseline unmodified throughout -- detector, descriptor, matching, RANSAC, threshold 3.0, seed 0, affine, 2x decimation, identical preprocessing.

| edge | dIncidence | putative | **inliers** | ratio | fit RMSE (px) | coverage gap | verdict |
|---|---|---|---|---|---|---|---|
| A -> B | **39.81 deg** | 32 | **4** | 0.1250 | **4.138e-13** | 0.477 | REJECTED, class C |
| **B -> C** | **0.96 deg** | 5392 | **5365** | **0.9950** | 0.583 | **0.108** | passes the inlier rule |
| C -> A | **38.85 deg** | 49 | **4** | 0.0816 | 0.885 | 0.441 | REJECTED, class C |

**A failure on a valid pair is the deliverable, and this is one.** It is also E-008's cleanest instance: 4.138e-13 px of fit residual for a transform whose independently measured error is **1614 px**, on a pair with 97 % confirmed shared ground.

**What the evidence eliminates.** Seven candidates, each by a measurement against the succeeding edge on the same ground through the same code: overlap, mare texture poverty (D-026), decimation, resolution mismatch (A<->B has the *smallest* ratio and fails), relief displacement (the succeeding edge spans the *largest* emission difference), window uncertainty (the succeeding edge has *less* overlap), the affine model, and any pipeline defect. **Illumination difference is the only enumerated candidate left standing -- and it is not claimed as the cause** (D-036): across three frames, large dIncidence is perfectly confounded with "the pairing involves frame A", and separately with dAzimuth, which was not measured.

**Third image and real loop closure.** Screening found **8 of 60** frames containing the target ground point with a full tile inside -- overlapping real triplets are not scarce. One product was acquired, chosen on a **pre-stated** criterion (minimise the maximum resolution ratio; it won 1.091 against 1.179), not on illumination. Loop closure then met real data for the first time: three **independently estimated** edges, independence asserted in code because E-021 was exactly an algebraically derived closing edge manufacturing a zero residual. Residual **1201.04 px** -- ADR-0011's reversal condition is not triggered, but a loop with two garbage legs exercises the estimator without measuring its power.

**Corroborating the success without ground truth.** The succeeding edge recovers a scale that `SCALED_PIXEL_WIDTH`/`HEIGHT` -- derived by the archive from SPICE, seen by neither the matcher nor the corner polygon -- predicts to **0.04 % and 0.50 %**, inside that field's own 1.83 % quantisation. The failing edges miss by 36-102 %. **Corroboration, not verification: class B, not class A.**

**Failures found:** E-030, E-031 (both `FIXED`, both ordinary implementation bugs in existing code, both caught by this stage's data before reaching a reported result). The E-030 failure run is preserved at `experiments/REAL-DATA/tile_sanity_usable_geo_preE030.json`.
**Decisions:** D-035 (overlap gate before interpretation), D-036 (failure NOT attributed to illumination); **D-033 implemented and measured**, D-031 superseded.
**Research log:** RL-033, RL-034; **RL-031b and RL-030b closed**; open threads RL-033b, RL-034b.

**Next dependency — DISCHARGED by REAL-DATA-04 (see the row above).** The prediction below was recorded before the data existed and **its first branch is what happened**: D↔A succeeded (1656 inliers) and D↔B failed (3). Illumination is the driver; frame identity is refuted; D-036 is superseded by D-040. The original wording is kept as written:

> **REAL-DATA-04** -- one more frame D at low incidence on the same ground point. **If D<->A succeeds and D<->B fails, illumination is the driver; if the reverse, frame identity is.** The prediction is recorded before the data exists. No matcher change, tuning or learned component is justified until that confound is broken. EXP-004 remains pre-registered and not started.
