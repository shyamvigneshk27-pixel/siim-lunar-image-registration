# SIIM — Stage History

The chronological master record of how this project's understanding evolved.

**SIH 2026 · Problem Statement 26166 (ISRO)** — Multi-modal, Sun-angle and scale invariant image correspondence, Chandrayaan-2 (OHRC, TMC-2, IIRS) ↔ LRO NAC.

| Where to look | For |
|---|---|
| This file | The chronological narrative — what happened, in order |
| [`stages/STAGE-INDEX.md`](stages/STAGE-INDEX.md) | Navigable per-stage summary table |
| [`stages/ERROR_LEDGER.md`](stages/ERROR_LEDGER.md) | Every significant failure, with root cause and fix |
| [`stages/DECISION_LEDGER.md`](stages/DECISION_LEDGER.md) | Every decision, its status, and what would reverse it |
| [`stages/STAGE_TEMPLATE.md`](stages/STAGE_TEMPLATE.md) | The mandatory template for every future stage |
| `stages/<STAGE>.md` | Full per-stage reports |

> **Reconstruction basis.** Stages before this document existed were reconstructed **from repository artefacts only** — experiment READMEs, metrics JSON/CSV, source, tests, `research_log.md`, `architecture_decisions.md`, `sources.md`.
>
> **The repository is not a git repository.** Per-edit chronology, intermediate states and wall-clock timestamps are therefore **not established from repository evidence**. Only the recorded metrics and final state are evidence. All artefacts carry the single date **2026-08-24**.
>
> **Scope of that limitation, added 2026-08-25.** The paragraph above is left as written and still applies **to EXP-000, EXP-001 and EXP-002**, which were reconstructed retrospectively. It no longer describes the repository as a whole: version control now exists from the `2ab0d77` baseline onward, so **EXP-003, the documentation audit, the EXP-004 pre-registration and REAL-DATA-01 have real commit chronology**, and REAL-DATA-01's artefacts carry **2026-08-25**, not the single 2026-08-24 date. Where a stage below states a duration or an ordering, it is evidenced by commits and artefacts, not inferred.

---

## Stage 0 — Geometry Gate (EXP-000)

**Status:** COMPLETE — PASS · [full report](stages/PHASE-0_GEOMETRY.md)

**Objective.** Establish a verified geometry layer and a written coordinate contract *before* any matching experiment, so that later measurements measure the science rather than a silent bug.

**What we built.** `src/siim/geometry/` in pure numpy/scipy — deliberately **OpenCV-independent**, so every convention has exactly one definition in this repository. Five transform models with explicit DOF; Hartley-normalised estimators reporting condition numbers and detecting degeneracy; resampling with anti-aliasing and validity masks; a synthetic known-transform harness. Conventions written normatively in `docs/coordinate_contract.md` and pinned by 70 property tests.

**Key result.** All five models recover from exact correspondences at **~1e-13 px** true endpoint error against a **0.1 px** gate — eleven orders of margin. Hartley normalisation holds the homography condition number **flat at ~3.4 from 512 to 60 000 px** coordinate extent, which matters because NAC frames reach ~52 000 lines.

**Major error.** The obvious resampling coordinate update, `p' = s·p`, is wrong by exactly `(s−1)/2` px — **0.25 px at s = 0.5 and a full pixel at s = 3** — while every intermediate image looks perfectly correct (E-001).

**Fix.** Contract C4, `p' = s(p + 0.5) − 0.5`, delivered as a `Transform` so a resampling factor lives in the transform chain and cannot be dropped. Two tests exist purely to document the hazard, one of which fails *with the size of the error* if anyone "simplifies" the function.

**What we learned.** Verify a convention against the physical operation it describes, not against its own restatement. Scale normalisation across the real sensor ladder needs factors up to 320×, so this single error would have consumed the entire sub-pixel budget before any matching began. Also: **lunar shadow is genuinely near-zero**, so zero-filling invalid warp regions is a domain hazard, not a harmless default (E-003).

**What changed next.** Real-data experiments unblocked; ADR-0007 accepted. EXP-001 inherited a trustworthy measuring instrument, a correct resampling chain, and the habit of writing tests that document hazards rather than merely exercising code.

---

## EXP-001 — RootSIFT Baseline

**Status:** COMPLETE · [full report](stages/EXP-001_ROOTSIFT.md)

**Objective.** Establish a strong classical baseline (B1) **and** a non-circular evaluation harness, before considering any learned matcher. The harness was the more important half.

**What we built.** A physically-shaded synthetic terrain generator — a 2.5-D height field rendered under controllable Sun geometry with cast shadows, because gain/bias/gamma all *preserve the sign of a gradient* and therefore cannot reproduce shadow reversal. RootSIFT detection and matching (ratio test + mutual NN), in-house LO-RANSAC, and an evaluation module that reports circular and non-circular metrics **side by side**. 45 cases across seven groups, exact ground truth throughout.

**Key result.** **Illumination is the dominant failure axis, and the failure is a cliff, not a slope.** Under fixed illumination the baseline is genuinely strong (0.009–0.386 px, ≥ 99.7% true precision, 0.387 s). At Δazimuth 30° it still registers at 0.290 px; at 45° it fails at 325.59 px. Sun *elevation* is survivable by comparison (Δel −30° → 0.750 px). Scale survived to 4×.

**Major error.** **Fit RMSE gives false confidence — and is *inverted* in the failure regime.** Of 17 wrong cases, **11 reported fit RMSE below 1e-12 px while being 190–2400 px wrong** (E-008). Separately, the ground-truth generator itself was wrong by **56.57 px** while RANSAC reported a 99.6% inlier ratio and 0.72 px fit RMSE (E-005).

**Fix.** For E-008, a methodological rule rather than a code change: every RMSE labelled `fit` or `held-out` and quoted with its inlier count; headline claims use the *worst* applicable estimator. For E-005, compose the crop offset into the transform chain, with a regression test whose failure message names the 56.6 px signature.

**What we learned.** Four things, three of which contradicted our own prior reasoning:

1. The shadow-reversal hypothesis was **too narrow** — failure arrives at 45°, not the predicted 180°, because shadow *movement* alone rotates gradient orientations. The mechanism was right, the magnitude wrong by 4×.
2. The §B6 repetitive-terrain risk was **overstated** — RootSIFT was perfect until *all* disambiguating context was removed.
3. The predicted "high confidence on a wrong answer" **did not materialise**; the misleading metric was fit RMSE, not the inlier ratio.
4. **RootSIFT showed no measurable advantage over plain SIFT** — recorded as a negative result rather than kept on the strength of a citation.

And a fifth, from E-005: **evaluation code needs the same scepticism as pipeline code.** A uniformly shifted match set is perfectly self-consistent, so only ground truth could catch it.

**What changed next.** ADR-0003 upgraded and strengthened; ADR-0009 and ADR-0010 created; EXP-003 (representations) promoted ahead of the remaining classical baseline sweep. Learned matchers deliberately **not** introduced: the failure is structural in orientation binning, which a different *representation* may fix without one — and the harness had just been shown to contain a 56 px bug of its own.

---

## EXP-002 — Evaluation, Realism and RANSAC

**Status:** COMPLETE · [full report](stages/EXP-002_EVALUATION_REALISM_RANSAC.md)

**Objective.** Four mandated objectives: fix the RANSAC performance defect; make the synthetic terrain physically realistic; validate the failure threshold **without circularity**; and build and score the GT-free estimators before any learned matcher.

**What we built.** A corrected LO-RANSAC with five-stage timing instrumentation; explicit slope-controlled terrain with four named regimes anchored to published LOLA statistics; a calibration/validation protocol on disjoint seeds; and `src/siim/evaluation/gtfree.py` — held-out residual, cycle consistency, loop closure, spatial split consistency. 36 new tests.

**Key results.**

- **LO-RANSAC: 54.29 s → 0.056 s (~968×)**, same inlier set, robustness unchanged (inlier recall 1.000 at 0–80% outliers).
- **Terrain now matches published lunar statistics exactly** (mare median 3.50° vs LOLA 3.5; highlands 9.10° vs 9.1).
- **`fit_rmse` scores ROC AUC 0.495 as a failure detector — chance** — from a negative control declared in advance.
- **Loop closure is the only GT-free estimator that detects a coherent wrong answer**: 1.000 detection at 0.000 false alarm, while held-out residual and split consistency manage 0.200.

**Major errors.** Four, of which only one is an ordinary code defect:

- **E-007** — the 59 s case was dominated not by the algorithm but by `np.linalg.svd(full_matrices=True)` building a **4230 × 4230 `U` (17.9 M elements)** and discarding it. EXP-001's own diagnosis of this symptom had been **incomplete**.
- **E-013** — the EXP-001 terrain had **89.55% of its surface steeper than the lunar angle of repose**: physically impossible.
- **E-009** — the inlier-count threshold claim was circular, and **refuted** on independent data: a *correct* case succeeded on **2** inliers.
- **E-010** — `split_consistency`'s apparent ROC AUC 0.994 was an artefact of an `inf` sentinel (non-finite in 104/192 cases, 103 of them wrong; finite in 88, **zero** wrong). The automated "best signal" selection was wrong and was overridden.

**Fixes.** `full_matrices=False` (mathematically identical, 493×) and LO-on-new-best (198 → 3 refits), with regression tests asserting **shapes and refit counts** rather than wall-clock where possible. Explicit `target_slope_median_deg`, with the old terrain **retained** as `C_extreme_diagnostic` and old results preserved. The threshold claim withdrawn and replaced by a validated operating point. The artefact documented rather than reported as a result.

**What we learned.**

1. **Two EXP-001 conclusions did not survive realistic terrain.** The illumination cliff is at **15–30°, not 30–45°** (RootSIFT is *worse* on real-looking terrain than we concluded), and **"scale survives to 4×" is false on realistic mare**, which fails at 2×. Scale tolerance is a property of the descriptor *and the available texture*.
2. **Distinguish "the separation observed in this sample" from "the rule validated on unseen data".** The first was refuted; the second — `n_inliers < 8`, recall 1.000, FPR 0.0112 — survives. Only the second was ever usable.
3. **ANALYSIS §F.1 named the wrong primary estimator.** A match set 64 px wrong yields a held-out residual of 0.468 px — *lower* than a correct-but-noisy set at 1.424 px. Self-consistency estimators cannot detect coherent wrongness, by construction. Loop closure can, because a per-edge error accumulates around a loop (190.08 px ≈ 3 × 64) instead of cancelling.
4. **Run-to-run variation is ±0.59 px**, which retired the RootSIFT-vs-SIFT comparison as noise.

**What changed next.** ADR-0011 and ADR-0012 accepted; ADR-0003's outstanding item discharged with its primary/secondary ordering **reversed by measurement**. EXP-003's success criterion restated against realistic regimes; realistic mare promoted to priority benchmark; runtime removed as a primary constraint.

---

## EXP-003 — Illumination-Invariant Representations *(plan, as recorded before the stage ran)*

> **Retained verbatim under integrity rule 3.** The four paragraphs below were written when
> EXP-003 had not started. They are **not** rewritten to match the outcome; the outcome is
> recorded in the section that follows. The pre-registered criterion is exactly the one the
> stage was then measured against, and it is worth being able to read what was expected.

**Status: NOT STARTED.** No implementation, no results.

Planned objective: test whether a polarity-agnostic representation moves the illumination cliff **beyond Δazimuth 30° on realistic (A) terrain regimes** — the criterion EXP-002 set in advance.

ADR-0004 (polarity-agnostic structure as the default representation) remains `PROPOSED` and states plainly that **if raw intensity wins, the ADR is superseded.** This stage is that test.

Explicitly out of scope until this stage runs: RIFT2, phase congruency, orientation-mod-π, and every learned matcher.

---

## Documentation audit and the `n_inliers` evidence debt

**Status:** COMPLETE · records: [`stages/README.md`](stages/README.md) · [`experiments/EXP-002/objective3_ninliers_sensitivity.json`](../experiments/EXP-002/objective3_ninliers_sensitivity.json)

Between EXP-002 and EXP-003 the whole documentation set was re-derived from the raw artefacts rather than from itself. **153 numeric claims were re-checked; all 153 reconciled.** Three bookkeeping discrepancies were found in the older narrative documents and were **recorded as discrepancies D1–D3 rather than silently corrected**, because quietly fixing your own numbers is not a history. None changed a conclusion.

The audit also closed an evidence debt it exposed. Discrepancy **D2** found that the table headed *"Sensitivity of `n_inliers`"* was in fact `split_consistency`'s, inheriting the E-010 `inf`-sentinel artefact — **the `n_inliers` sensitivity analysis had never been computed.** It was then computed properly, and two things came out of it:

- the operating rule changed form to **`n_inliers <= 8`** (**D-023**). Exactly one case in 384 discriminates — a calibration failure with **exactly 8 inliers and 367.95 px** of true error, which `< 8` misses at no false-alarm saving. On validation the two forms are indistinguishable, because **no validation case has 8 inliers**, so the boundary was never actually tested;
- the `inf` sentinel was quantified as a proxy for `n_inliers < 8` at **192/192** agreement.

**What we learned.** A documentation audit is not clerical work. It found a missing analysis, changed an operating rule, and produced the D1–D3 record that later made E-023 recognisable as E-010 recurring.

---

## EXP-003 — Illumination-Invariant Representations *(the stage as it actually ran)*

**Status:** COMPLETE — **pre-registered criterion S1 met by no arm** · [full report](stages/EXP-003_illumination_robust_representations.md)

**Objective.** The plan above, executed: 6 arms × 3 regimes × 3 seeds × 11 azimuths = **594 evaluations** on one shared image pair per case, plus 108 loop-closure triplets. Part 1 was frozen before implementation.

**Key results.** `S1_MET_BY_ANY_ARM = false`. Last fully-successful Δaz — mare / highlands / B: baseline **21/27/27** · mod-π **0/21/27** · 2π control **18/27/40** · phase congruency **void/27/30** · RIFT2-MIM **void/0/27**. The two phase-congruency arms fail the Δaz = 0 positive control on mare (24 keypoints at 384²), voiding their mare results.

**H-3.1, H-3.2 and H-3.3 refuted. H-3.4 refuted in the opposite direction** — polarity-agnostic mod-π was the *worst* of the six arms: **0 wins, 38 losses, 61 ties** against its own 2π control on identical keypoints. **H-3.6 refuted on FPR**: `n_inliers <= 8` transfers on recall (0.9857) but not on false alarm (0.0112 → **0.3692**, 33× worse).

**Major errors.** **E-003.2** — loop closure was labelled edge-level, scoring false alarm at **0.617**; with the correct loop-level label it is **0.000** at detection 1.000. A 0.617 swing from a labelling choice alone, and the mislabelled variant is retained in the artefact so the size of the error stays visible (**D-027**).

**What we learned.**

1. **The invariance was provable and was not enough.** Phase congruency is contrast- and polarity-invariant to 1e-6, and still stops at 27–30°, because shadow motion changes *which structures exist*, not merely their contrast.
2. **The one positive effect came from a control arm.** The upright 2π control extended the B-regime cliff 27° → 40°, and a direct probe found why: SIFT's assigned dominant orientation drifts ~1:1 with Sun azimuth (median |Δangle| 6.69° → 44.77° as Δaz goes 0° → 45°). **This was post-hoc, confounded with a small true rotation, and is held as D-024 — not accepted.**
3. **Uprightness is not a method.** It survives only because the transforms carried ≤ 8° rotation. An arm that "wins" by discarding rotation invariance has moved the failure, not fixed it.

**What changed next.** **ADR-0004 SUPERSEDED** — it met its own supersession condition, raw intensity won. D-024–D-028 recorded. Pre-registered stop-condition 1 fired, so **learned matchers remain deferred** (D-028).

---

## EXP-004 — Orientation Assignment — **PRE-REGISTERED, NOT IMPLEMENTED**

**Status:** Part 1 frozen; Part 2 empty; **no implementation exists** · [pre-registration](stages/EXP-004_orientation_assignment.md)

EXP-003's orientation observation is post-hoc and confounded, so D-024 holds it as a *pre-registration target* rather than a finding. EXP-004 is that pre-registration: hypotheses H-4.1–H-4.6, success criteria S1–S5 (**both** an illumination criterion and a non-negotiable rotation criterion), five arms sharing identical keypoints, a 6 × 5 factorial that separates Δazimuth from true rotation, disjoint calibration/validation seeds, and four negative controls declared in advance.

**Nothing has been run.** There is no `experiments/EXP-004/`, no runner script, and no arm implementation. The stage is recorded here because the pre-registration itself is a dated artefact — writing the criteria down before the result is the point of it.

---

## REAL-DATA-01 — Real LRO NAC Ingestion and First Real Registration

**Status:** COMPLETE — **ingestion succeeded, the first real registration FAILED (class C / REJECTED)** · [full report](stages/REAL-DATA_LRO_NAC.md)

**Not an EXP-numbered experiment.** No hypothesis was pre-registered, because this is an ingestion and instrumentation stage. Everything in it is reported as measurement.

**Objective.** Turn already-acquired LRO NAC metadata into decoded, provenance-tracked, sanity-checked real image tiles, and run the existing RootSIFT baseline **unmodified** — so the first real-data result measures the pipeline as built, not one tuned to the answer.

**What we built.** A PDS4 `Array_2D_Image` decoder with an explicit dtype table (`SignedLSB2 → <i2`, byte order never inferred); strict byte-range fetching that detects ignored `Range` headers, wrong ranges and short bodies; a quantitative tile-sanity layer; and reproducible acquisition, checking and registration scripts. **`src/siim/ingest` went from 0 tests to 61.**

**Key results.**

- **Decoding is provably correct.** The label's `file_size` is declared independently of the array description, giving an exact identity — `5064 + 52224 × 5064 × 2 = 528 929 736` ✓ on all four products — which validates offset, both dimensions and element size *together*.
- **The pipeline works on real lunar imagery.** Positive controls: self-registration recovers identity to **1.14e-12**; a known (+40, +25) px shift on a real tile is recovered as **(40.142, 24.941)**.
- **The first real registration failed.** 12 707 / 11 412 keypoints, 35 putative, **3 inliers**, **fit RMSE 1.575e-12 px**, a transform with 11–18× scale and ~10 000 px translation. Verdict **REJECTED**, class **C**.
- **The line-direction ambiguity does not explain it.** All four H1/H2 tile combinations fail (**3, 4, 4, 5** inliers).

**Major errors.** Five, of which two are ordinary code defects:

- **E-022** — a `Product_Browse` label was accepted for **4 of 6 products**, both halves of the best pair included. ODE returns both labels with an explicit `Type`; the parser matched on `.xml` extension and the last one won. The correct URL was in the response all along and was discarded.
- **E-023** — the decode-correctness statistic reported **0.9919 for two different frames**, identical to four decimals: it was measuring the constant `-32768` border columns, not the image. **This is E-010 recurring** in code written much later.
- **E-024** — a **0.0022** margin between two ~0.35 values was announced as a byte-order defect in correct code.
- **E-025** — a second acquisition of the same product silently overwrote the first tile, so four "different" conditions returned byte-identical results. An integrity rule 4 violation.
- **E-026** — maximising Δincidence selects the **terminator**: the top pick was 89.96° vs 24.64°, and the 89.96° frame decodes perfectly and is unusable (DN 29 ± 19.6, autocorrelation 0.3553 against 0.9759 for its partner).

**What we learned.**

1. **E-008 now has a real-data instance.** A fit RMSE of **1.575e-12 px** on a catastrophically wrong answer — a conventional pipeline reporting inlier RMSE would present that as picometre-accurate registration. The project's founding claim was measured on synthetic terrain; it is no longer only synthetic.
2. **The registration failed and that is the result.** What succeeded is the *rejection*, and the rejection rests on `n_inliers <= 8` and coverage — **both applied here, neither validated on real data**.
3. **The cause is not attributed.** Two hypotheses remain live and the data separates neither: the tiles may not overlap (the crop is a first-order latitude approximation with no camera model), or the illumination difference may defeat the matcher — though Δ*azimuth* is unavailable for these products (E-020), so even EXP-003's cliff is not directly applicable. **Evidence insufficient**, recorded as D-031.
4. **An optimisation criterion is a specification of what you will get.** "Most illumination difference" and "most *informative* illumination difference" are different objectives, and the archive has enough range to make the difference fatal.
5. **Loop closure — the project's only trustworthy GT-free check — has still never met real data.** It needs a third overlapping product, which was not acquired, so it is reported as *not run* rather than as a pass.

**What this stage is NOT.** It is **not** completion of the Chandrayaan-2 objective — OHRC / TMC-2 / IIRS remain behind ISSDC authentication and no such data was obtained, simulated or implied. Both frames are the **same instrument**, so **no multi-modal claim** is supported, and sub-solar azimuth is not published for these products, so **no Sun-azimuth claim** is either.

**What changed next.** D-029–D-032 recorded; RL-026–RL-030 logged; E-022–E-025 fixed with regression tests, E-026 documented. Suite **194 → 260 passed, 2 skipped**.

---

## REAL-DATA-02 - Independent Real-Image Overlap Verification

**Status: COMPLETE - the question is answered, and the answer invalidates REAL-DATA-01's headline pair.**

REAL-DATA-01 ended with a 3-inlier registration it could not interpret, because its only overlap evidence was the registration itself. This stage established overlap **independently of the matcher** - no pixel read, no detector, descriptor, RANSAC, residual or verdict involved - and found:

| tile pair | intersection | IoU | shared fraction of the worse tile | class |
|---|---|---|---|---|
| `usable_H1` - **the headline run** | **0.0000 km2** | 0.0000 | **0.0 %** (p5-p95 0.0-0.0) | **OVERLAP_INSUFFICIENT** |
| `usable_H2` | 4.9653 km2 | 0.5330 | **68.59 %** (p5-p95 62.9-74.1) | **OVERLAP_CONFIRMED** |
| `terminator_H1` | 2.2375 km2 | 0.1835 | 28.29 % (p5-p95 23.4-33.0) | **OVERLAP_UNKNOWN** |
| the two mixed H1/H2 grid rows | **0.0000 km2** each | 0.0000 | 0.0 % | **OVERLAP_INSUFFICIENT** |

**The tiles behind the first real registration were 22.75 km apart.** Nearly six tile-lengths, against a 3.98 km tile.

**Where the geometry came from, after two dead ends.** The PDS4 `Product_Observational` label carries no `Cartography` and no `Geometry` - none at all. The 5064-byte PDS3 attached header inside the `.IMG`, fetched live and read, carries no geometry keywords either. ODE's `Footprint_geometry` is a four-vertex ring whose **order is undocumented**, so it cannot say which vertex is image line 0 - and getting that wrong mirrors a tile by up to a whole 48 km frame. The answer is in the **PDS archive index table**, one directory above the data, which ODE itself cites as its footprint source and which names its corners: `UPPER_LEFT_LATITUDE` ... `LOWER_RIGHT_LONGITUDE`, plus `LRO_FLIGHT_DIRECTION`, `SCALED_PIXEL_WIDTH`/`HEIGHT` and `SUB_SOLAR_AZIMUTH`. The tables are 18-54 MB but fixed-length and sorted, so one row costs a binary search of ~16 range requests of 901 bytes. Four products: **~130 KB, no image bytes.**

**What made the corner names usable.** Each product's own PDS4 label states `disp:Display_Direction` = `(Line, Top to Bottom)`, so the top row is the first line and `UPPER_*` is line 0. Corroborated twice: corner-implied pixel scale agrees with the archive's SPICE-derived `SCALED_PIXEL_HEIGHT`/`WIDTH` within **1.2 % over 8 comparisons**, and the 2-2 split of which end is northward follows `LRO_FLIGHT_DIRECTION` exactly - impossible if `UPPER` were a compass label.

**Three failures, all design mistakes rather than code defects.**

1. **E-028** - the line-direction hypothesis was applied globally to a pair, and it is a property of the individual frame. The script's docstring reasoned "same camera, same processing pipeline, so the convention is the same for both": true, and irrelevant, because the readout direction is set by spacecraft attitude and LRO yaw-flips. Both usable frames are H2; the pair was acquired at H1.
2. **E-029** - cross-track position was never matched between frames, costing a further 1.1-1.7 km against a 1.8 km tile. This is what caps `usable_H2` at 68.6 % and leaves the terminator pair UNKNOWN.
3. **E-027** - a `NORTH_AZIMUTH` cross-check was designed, implemented, and has no discriminating power: ~270 deg for all four frames regardless of their line direction, because the column is "relative to the RDR products". **E-024 recurring**, caught before it was reported as a result.

The 260-test suite in place at the time was passing throughout and could not have caught any of the three.

**A correction to REAL-DATA-01 section 4.5, recorded rather than applied.** That section tested four H1/H2 combinations, saw 3/4/4/5 inliers, and concluded the direction hypothesis was not the explanation. Exactly one of the four rows has overlapping tiles; the other three are 11-23 km apart and could not have succeeded. The original text stands unedited (integrity rule 3).

**A loose end closed.** REAL-DATA-01 left an unexplained 1.05 ratio between footprint-implied m/line and ODE's `Map_resolution`. It was a comparison against the wrong field: `Map_resolution` is not the down-scan pixel scale. Against `SCALED_PIXEL_HEIGHT` the ratios are 1.002-1.012.

**What survives from REAL-DATA-01, and what does not.** Its ingestion, decoding, sanity validation and positive controls never depended on overlap and are untouched. Its **E-008 demonstration strengthens**: a fit residual of 1.575e-12 px was reported for a transform between tiles sharing *no ground at all*. What does not survive is any reading of the 3 inliers as evidence about real-data matcher performance.

**The one interpretable real-data result the project now has.** `registration_usableH2.json`: two NAC frames with **68.6 % / 70.5 %** independently confirmed shared ground, Delta-incidence 39.8 deg, and the unmodified baseline returns 43 putative matches and **5 inliers**, REJECTED. Overlap is excluded as the cause. **The failure is still not attributed** - illumination, mare texture poverty (D-026), the 2x decimation, the resolution ratio and real relief displacement are all live and untested. `SUB_SOLAR_AZIMUTH` was found in the index table and deliberately **not used**; these pairs remain illumination-varied by incidence only, **not azimuth-controlled**.

**What changed next.** D-033 and D-034 recorded; **D-030 discharged**, D-031 transferred to the `usableH2` run; RL-031 and RL-032 logged, **RL-029b closed**, RL-031b and RL-032b opened; E-027 fixed with regression tests, E-028 and E-029 documented with the fix deferred to REAL-DATA-03. Suite **260 -> 357 passed, 2 skipped**.

---

## REAL-DATA-03 - The First Correctly Controlled Real-Data Registration Experiment

**Status: COMPLETE - the experiment is valid. Two of three edges FAIL; one SUCCEEDS.**

This stage was not a search for a successful registration. It was a search for a **valid** one: give the unmodified baseline two real lunar images that are known, independently of the matcher, to show the same ground, and accept whatever comes out.

**The gate came first, and it is enforced in code.** `verify_tile_overlap.py --require-confirmed` exits non-zero unless every edge is OVERLAP_CONFIRMED, and it was run as a separate command before the baseline (D-035). REAL-DATA-01's headline was a 3-inlier failure on tiles later shown to be 22.75 km apart, and it had no way to tell.

**Acquisition.** Geometry-driven, implementing D-033: three tiles all centred on **one ground point** (lon 22.033852, lat 20.035253), each window derived by inverting a bilinear ground map built from the archive's **named** frame corners, with the line direction read **per frame** rather than assumed. Windows A `l17955 s1811`, B `l29822 s1227`, C `l9088 s717`, all 4096 x 2048. A and B reproduced REAL-DATA-02's projected windows exactly, by an independent code path, and the measured tile-centre separation on the primary edge is **1 metre**.

| edge | overlap of the worse tile | IoU | p5-p95 | class |
|---|---|---|---|---|
| A <-> B | **97.12 %** | 0.9695 | 90.03-97.31 % | **CONFIRMED** |
| A <-> C | 82.72 % | 0.8272 | 78.57-86.38 % | **CONFIRMED** |
| B <-> C | 85.00 % | 0.8500 | 80.62-88.60 % | **CONFIRMED** |

All three tiles passed sanity; none was discarded.

**The result.** Nothing in the detector, descriptor, matching, RANSAC, threshold, seed, model, decimation or preprocessing was changed.

| edge | dIncidence | putative | **inliers** | ratio | fit RMSE (px) | coverage gap |
|---|---|---|---|---|---|---|
| A -> B | **39.81 deg** | 32 | **4** | 0.1250 | **4.138e-13** | 0.477 |
| **B -> C** | **0.96 deg** | 5392 | **5365** | **0.9950** | 0.583 | **0.108** |
| C -> A | **38.85 deg** | 49 | **4** | 0.0816 | 0.885 | 0.441 |

**A failure on a valid pair is the deliverable, and this is one.** It is also E-008's cleanest instance yet: a fit residual of 4.138e-13 px - a quarter of a picometre - for a transform whose independently measured error is **1614 px**, on a pair with 97 % confirmed shared ground. Not synthetic, and not on tiles that turned out to be disjoint.

**Seven candidate causes eliminated by measurement.** Each falls to a comparison against the succeeding edge, on the same mare, through the same code: the tiles overlap; mare texture poverty cannot be sufficient (5392 putative matches on that same ground); the 2x decimation is identical; resolution mismatch is backwards (A<->B has the *smallest* ratio in the triplet, 1.016, and fails); relief displacement is backwards (the succeeding edge spans the *largest* emission difference); window uncertainty is backwards (the succeeding edge has *less* overlap); the affine model is common to all three; and the pipeline is proven by a successful **cross-frame** registration, a stronger control than REAL-DATA-01's self-registration.

**And illumination is still not claimed as the cause.** It is the only enumerated candidate left standing, and that is exactly how it is recorded (D-036). Across three frames, "large dIncidence" and "the pairing involves frame A" are the same partition - A is the only low-incidence frame and appears in both failing edges - and dIncidence is separately confounded with dAzimuth, which was not measured.

**A third image, and real loop closure.** Screening found **8 of 60** frames containing the target ground point with a full tile inside: overlapping real triplets are not scarce in this region. One product was acquired, chosen on a criterion **fixed before looking** - minimise the maximum resolution ratio, which it won at 1.091 against 1.179 - not on illumination. Loop closure, the project's only GT-free estimator that detects a coherent wrong answer, then met real data for the first time. Three edges, each estimated **independently from its own image pair**; the independence is asserted in code, because E-021 was precisely an algebraically derived closing edge manufacturing a zero residual for a registration 64 px wrong. Residual **1201.04 px**. ADR-0011's reversal condition is not triggered - but a loop with two garbage legs exercises the estimator without measuring its power.

**Corroborating the success without ground truth.** The 5365-inlier edge recovers a scale that `SCALED_PIXEL_WIDTH`/`HEIGHT` - derived by the archive from SPICE, and seen by neither the matcher nor the corner polygon - predicts to **0.04 % and 0.50 %**, inside that field's own 1.83 % quantisation. The two failing edges miss by 36-102 %. That is the strongest corroboration available without ground truth, and it is **corroboration, not verification**: class B, not class A.

**Two implementation defects, both caught before they reached a reported result.** **E-030**: the raw-tile byte cache was keyed by product and not by window, so the sanity check loaded REAL-DATA-01's bytes for a REAL-DATA-03 tile and computed its decode evidence from a window 22.75 km away - **E-025 recurring in a second script**, with the SHA check catching it and then misattributing it to the range fetch. The failed run is preserved. **E-031**: a figure crash on a three-tile manifest destroyed a set of checks that had already passed, because the report was written after the plot.

**What changed next.** D-035 and D-036 recorded; **D-033 implemented and measured**, D-031 superseded; RL-033 and RL-034 logged, **RL-031b and RL-030b closed**, RL-033b and RL-034b opened; E-030 and E-031 fixed with regression tests. Suite **357 -> 376 passed, 2 skipped**.

---

## 2026-09-04 — Four stages in one day: sub-pixel, model selection, the DEM render, and the learned engine

**Status: EXP-010 COMPLETE · EXP-011 COMPLETE · EXP-007 COMPLETE · REAL-DATA-06 CLOSED (null by construction).** REAL-DATA-07 (42 real pairs) and REAL-DATA-08 (radar and 100 m proxies) were pre-registered the same day and ran overnight; their Part 2s are written from their own artefacts.

The master plan (`MASTER_RESEARCH_AND_ARCHITECTURE_PLAN.md`) was written in the morning, and its central bet — H0, *carry the illumination difference in a DEM render rather than in the matcher* — was tested by the evening. Four things were established, each against a criterion frozen before its data existed.

**Sub-pixel is real and measured (EXP-010).** The project had never held a sub-pixel number on real texture. Local ECC refinement of each correspondence, restricted to a translation so it cannot absorb what the global model explains, reaches **0.003 px** median on real NAC self-warps of all four recorded tiles (an upper bound: the warp shares the original's texture and kernel), with a gate of 7e-15 px on the identity. Under synthetic Sun-azimuth change the refiner's shading bias grows from 0.04 to 0.23 px (mare) and 0.008 to 0.07 px (highlands) by 30°, and stays under 0.25 px throughout. Phase correlation recovers about half a residual and is not deployed. **D-044.**

**The affine default was quietly costing up to a pixel (E-034), and refine-then-reselect fixes it (EXP-011).** On frame D — high Sun, low contrast — a pure integer self-shift is recovered by the affine model to 0.99 px median with 11 849 inliers and a zero residual: correlated localisation error absorbed into the linear terms, invisible to the fit. Held-out residuals cannot see it either (translation 0.0338 vs affine 0.0336 px on D). Refining the points first and then selecting the simplest model within 10 % of the best held-out median picks the true model in **48 of 48** cases at **0.0018 px** dense error against 0.0975 px for the default. H1's predicted wrong selection did *not* occur — the tie-break, not the evidence, chose correctly — and that is recorded as a partial refutation. Pipeline order becomes **estimate → refine → re-estimate with selection → verify. D-045.**

**The DEM render carries nothing on this mare (EXP-007, S1 NOT MET).** SLDEM2015 at 59 m, sampled onto each tile through the archive corner map and rendered under each image's own Sun, yields **0–19 SIFT keypoints** on the high-Sun frames and 57–176 on the low-Sun ones, against 560–20 700 on the images, at every rung from 1.8 m to 30 m. Every image-to-render leg returns 0–7 inliers; 0 of 4 failing pairs convert at any rung, and the render arms fail the two succeeding pairs as well (S6 NOT MET, for those arms alone). The cause is not the corner offset and not the shading model: the height field contains none of the 10–100 m craters the images are made of. **H0 is demoted to conditional on a fine DEM (D-046)**; the SERENRIDGE1 NAC-DTM site is where it is tested next.

**A licensable learned engine crosses the threshold (EXP-007, S3 MET).** DISK + LightGlue (Apache-2.0, CPU, via kornia) registers **C → A at 38.85° with 56 inliers** and a transform CONSISTENT with archive geometry, where RootSIFT gives 4; at 7, 15 and 30 m it registers three of the four ~40° pairs with 447–2042 consistent inliers, and it does not cross 51.54°. It breaks neither succeeding pair at any rung. **B4L is admitted as an engine arm (D-047, superseding D-028)**; the physics layer keeps overlap, prior transform, scale and verification. A second finding rides along: RootSIFT itself passes two of the ~40° pairs *marginally* (9–10 inliers, geometry-consistent) at 3.6–15 m, which is reported and not called a conversion.

**REAL-DATA-06 was a no-op by design (E-035).** Its two photometric arms, run exactly as frozen, returned counts and matrices identical to the uncorrected run on all six edges, because one factor per frame is a scalar and the per-image stretch removes scalars. An exploratory per-pixel arm from the 59 m DEM changes counts (5365 → 2469, 1656 → 1197) and converts nothing. **Closed, D-048.** The lesson enters the ledger: assert that a treatment changed the input before measuring its effect on the output.

**What changed.** D-044 – D-048 recorded, D-028 superseded; E-034 fixed in the architecture, E-035 documented; RL-037 – RL-040 logged; stage-index rows for EXP-010, EXP-011, EXP-007, REAL-DATA-06. Sample size in flight: 14 census frames, 20 tiles, 42 geometry-confirmed pairs (REAL-DATA-07).

---

## 2026-09-05 — The envelope on 42 pairs, the proxies, and a mirror in the data

**Status: REAL-DATA-07 COMPLETE (amended the same day) · REAL-DATA-08 COMPLETE · REAL-DATA-09 PRE-REGISTERED.**

The two jobs left running on the evening of the 4th died with the machine at 22:16 and were re-run from scratch. What they returned was harder to read than the plan expected.

**REAL-DATA-07 (42 geometry-confirmed pairs, 14 frames, two engines).** The Δincidence separation reaches **p = 0.0042** pooled — the first sub-0.01 significance the project has held — with **0 wrong passes in 37** and nothing passing above 40°. And the replication did not happen: candidate E1 could not be tiled on the shared ground, and E2 failed both decisive edges and every other partner. Four frames failed against everyone regardless of Δincidence, which is the frame-identity question of D-040-N1 returning with n = 4 (D-049). The learned engine's native-scale envelope equalled RootSIFT's, with 5–25× the yield inside it (D-047-N1). North-up rotation moved one recorded edge from 7 to 9 inliers, across the rule (S6). The raw reproduction arm's first run compared two edges in the wrong direction and was caught by its own gate (E-036).

**Then the cause of the four frames was found in the data, not the Moon.** The corner map's Jacobian determinant has the opposite sign for **5 of the 14 census frames** — including E2 — meaning those tiles are **mirror images** of the incumbents' view, and a quarter-turn cannot undo a reflection (E-037). Flipping E2's tile turned 5 inliers into **2691** against D and 6 into **2138** against A. A reflection-aware orientation (`north_up_east_right`) was written, and the whole stage re-run with it as a labelled amendment (`rows_*_nue.json`, `real_data_07_results_nue.json`), with XFeat as a third engine; the original artefacts and Part 2 stand unchanged beside it. **The amended run met the replication criterion** — E2 → A 2138 inliers, geometry-consistent, E2 → B fails — discharging the debt D-040-N1 had carried since REAL-DATA-05 (D-040-N2); pooled p fell to **0.0012** with both windows under 0.05 (S5 MET); 0 wrong passes in 76; five failures became successes, all on mirrored frames, none the other way. What remains frame-level is two dark frames at 72–75°: the incidence ceiling, not identity (RL-042c).

**REAL-DATA-08 (126 rows).** NAC ↔ Mini-RF radar registers under **no** engine (0 / 48). At the 100 m rung RootSIFT passes one frame and DISK + LightGlue three of four, with 34–99 geometry-consistent inliers from 111 × 46 px strips — and one wrong pass, the engine's first (D-050). The runner used a box average where Part 1 named a PSF-aware operator; the deviation is recorded, the operator built (R9), and the rows re-run with it as a labelled artefact.

**Built the same day.** The deliverable pipeline (estimate → refine → re-estimate → verify), engine agreement as a verifier with its floor measured on the REAL-DATA-07 transforms (agreeing pairs ≤ 1.17 px, failing ones ≥ 49 px), `siim register`, XFeat as engine B4X pinned to a commit, the demo's two-engines panel and live registration card, and REAL-DATA-09 pre-registered before any Chandrayaan-2 byte exists with the PRADAN acknowledgement wording recorded (S15).

**What changed.** D-049, D-047-N1, D-050 recorded; E-036, E-037 logged; RL-042, RL-043 logged; stage-index rows for REAL-DATA-07, -08, -09. Suite 768 → see the index for the current count.

---

## Where the project stands

| Stage | Status |
|---|---|
| PHASE-0 / EXP-000 — geometry gate | **COMPLETE — PASS** |
| EXP-001 — RootSIFT baseline + GT harness | **COMPLETE** |
| EXP-002 — RANSAC, terrain realism, threshold, GT-free estimators | **COMPLETE** |
| Documentation audit + `n_inliers` evidence debt | **COMPLETE** (D1–D3 recorded, D-023) |
| EXP-003 — illumination-robust representations | **COMPLETE — criterion NOT met; ADR-0004 superseded** |
| **EXP-004** — orientation assignment | **PRE-REGISTERED, NOT IMPLEMENTED** |
| **REAL-DATA-01** — real LRO NAC ingestion | **COMPLETE — ingestion succeeded, registration FAILED (class C / REJECTED).** Its headline pair is now known not to overlap |
| **REAL-DATA-02** — establish real overlap independently of the matcher | **COMPLETE — question answered.** Headline pair **OVERLAP_INSUFFICIENT** (0.0000 km², 22.75 km apart); `usable_H2` **OVERLAP_CONFIRMED** (68.6 % / 70.5 %); terminator **OVERLAP_UNKNOWN** (28.3 %) |
| **REAL-DATA-03** — the first correctly controlled real-data registration experiment | **COMPLETE — the experiment is valid.** Overlap CONFIRMED 97.12 % / 82.72 % / 85.00 % **before** interpretation; unmodified baseline **4 inliers at Δinc 39.8°**, **5365 at Δinc 0.96°**; first real loop closure **1201.04 px** |
| **REAL-DATA-04** — can frame identity and illumination be separated? | **COMPLETE — ANSWERED. Illumination, not frame identity.** D↔A succeeds (1656 inliers, occupancy 1.000, Δinc 11.73°); D↔B fails (3, Δinc 51.54°) on overlap-matched edges. Six real edges now place every frame on both sides. **Frame identity is substantially weakened, NOT conclusively refuted** — A and D each have n = 1 in the successful regime |
| **REAL-DATA-05** — does the illumination result replicate on a second low-incidence frame? | **CLOSED — UNRESOLVED, BY DATA AVAILABILITY.** The pre-registered screen returned **zero** admissible frames at every tier and rung; the only two in-band frames over shared ground are orientation-incompatible. No image byte fetched, no registration run, decision table never reached |
| **EXP-010** — sub-pixel refinement | **COMPLETE — gate, S1, S2, S3 MET; S4 undefined.** 0.003 px median on real self-warps (ECC); < 0.25 px under synthetic Sun-azimuth change to 30° |
| **EXP-011** — transform model selection | **COMPLETE — gate, S2, S3 MET; S1 NOT MET.** Refine-then-reselect 0.0018 px vs 0.0975 px affine default, 48/48 correct models; E-034 fixed in the architecture |
| **EXP-007** — DEM-conditioned correspondence + learned engine | **COMPLETE — S2, S3, S4, S5 MET; S1 NOT MET; S6 NOT MET for the DEM-render arms.** The 59 m render carries no matchable structure at 1.8–30 m on this mare (H0 demoted, D-046); DISK + LightGlue registers C → A at 38.85° (56 consistent inliers) and three of four ~40° pairs at 7–30 m (D-047) |
| **REAL-DATA-06** — photometric normalisation | **CLOSED — null by construction (E-035).** Per-frame correction is a scalar the stretch removes; per-pixel from the 59 m DEM converts nothing (D-048) |
| **REAL-DATA-07** — replication and the illumination envelope on 42 real pairs | **COMPLETE, AMENDED (E-037).** Amended run: **replication MET**, pooled p = 0.0012 (both windows < 0.05), 0 wrong passes in 76, nothing above 40°, last ≥ 0.8 bin 20–25°; B4L widens nothing at native scale (D-047-N1); three engines agree to ≤ 2.2 px (D-051). Original run (p = 0.0042, replication NOT MET) preserved beside it |
| **REAL-DATA-08** — radar (Mini-RF) and 100 m (WAC) proxies | **COMPLETE — S1 MET; S2, S3 NOT MET.** Radar registers under **no** engine (0 / 48 rows); at 100 m B1 passes one frame and **B4L three of four** with 34–99 consistent inliers from 111 × 46 px strips, plus one wrong pass (D-050). PROXY, never a Chandrayaan-2 result |
| **September 2 demo** | **delivered** — scientific expansion resumed 2026-09-04 with the master plan |
| Chandrayaan-2 (OHRC / TMC-2 / IIRS) | **NOT OBTAINED** — PRADAN registration and download are the user's action (2026-09-06); ingestion pre-registered as REAL-DATA-09 |

**The next stage is the September 2 demo, not another experiment — and REAL-DATA-05 is the reason the science stops here rather than the reason it continues.** The pre-registered replication of REAL-DATA-04 ran its screen as written and returned **zero** admissible frames at every tier and rung. Of 906 archive products, exactly **8** can centre a full tile on ground shared with A, B and D; only **2** sit in the required incidence band, and **both are acquired in the opposite along-track sense**, rejected by the orientation filter REAL-DATA-04 itself introduced (D-038). The stage stopped rather than relax a criterion by 0.22°, and **no image byte was fetched, no registration was run, and the decision table was never reached**.

**What that changes about REAL-DATA-04's conclusion.** D-040 stands — Δ*incidence* remains the attributed cause in the scope it states — but its wording is corrected: **frame identity is substantially weakened, not conclusively refuted.** The argument joining every frame to both sides of the outcome is a **cross-stage join, not a within-experiment result**, and frames A and D each rest on **n = 1** observation in the successful regime. The replication debt is undischarged, and **EXP-004** is now the *measured* blocker on it rather than an open question: the two frames that could have replicated the result were unusable for exactly the reason EXP-004 exists to study. It remains pre-registered and not started.

*(Historical note, retained under integrity rule 3: the paragraph below was written after REAL-DATA-04 and before REAL-DATA-05 ran. Its "frame identity predicts nothing" and "frame A is cleared" are the wording D-040's superseding note corrects.)*

**The next stage is the September 2 demo, not another experiment.** REAL-DATA-04 answered the question REAL-DATA-03 could not: **illumination, not frame identity**. One low-incidence frame D registers against A (1656 inliers at Δinc 11.73°) and fails against B (3 at Δinc 51.54°), on edges whose independently confirmed overlap differs by 0.95 pp. Across six real edges, five frames and two ground windows, **every frame now appears in both a succeeding and a failing edge** — frame identity predicts nothing, Δincidence predicts all six, and **frame A is cleared**. D-036 is superseded by D-040, which states the scope: Δ*incidence*, mare terrain, one region, one instrument, and **not** an azimuth result. Two amendments were forced along the way — the pre-registered acquisition was impossible, and **E-032** demoted the flight-direction rule for line 0 to an 8/10 regularity with two counterexamples — both registered before any image byte of D was fetched. **Scientific expansion stops here.** No matcher change, tuning or learned component is justified; EXP-004 remains pre-registered and not started.

*(Historical note, retained under integrity rule 3: the sentence below was written before REAL-DATA-04 ran.)*

**The next stage is REAL-DATA-04.** REAL-DATA-03 produced the project's first valid real-data experiment and narrowed the cause of failure to a single surviving candidate. It could not go further, and the reason is structural: across three frames, *large Δincidence* and *the pairing involves frame A* are the same partition. **One frame settles it** — acquire D at low incidence on the same ground point and run the two edges that decide it. If **D↔A succeeds and D↔B fails**, illumination is the driver; if the reverse, frame identity is and the surviving candidate is refuted. The prediction is written down before the data exists, which is what makes it a test. Second: a triplet of three mutually illumination-similar frames, so loop closure's *discriminating power* on real data can be measured rather than merely exercised. **No matcher change, tuning or learned component is justified until the confound is broken.**

*(Historical note, retained under integrity rule 3: the sentence below was written before REAL-DATA-03 ran.)*

**The next stage is REAL-DATA-03.** REAL-DATA-02 answered the blocking question, and in answering it invalidated the *tiles* rather than the products: the two frames of the `usable` pair do share ground, and the crops taken out of them for the headline result did not. The corrected windows are already computed from archive geometry and project to **97.1 %** tile overlap — a specification, not a measurement, since no such tile has been cut (D-033). Re-acquire at those windows, verify the overlap through the same independent path *before* registering, and acquire a **third overlapping product** so loop closure can meet real data for the first time. **No matcher change, no tuning and no learned component is justified until a real pair capable of succeeding has been supplied.**

*(Historical note, retained under integrity rule 3: the sentence below was written before REAL-DATA-02 ran.)*

**The next stage is REAL-DATA-02.** Until real overlap is established independently of the matcher, every real registration failure is uninterpretable. Its highest-value item is acquiring a **third overlapping product**, so that loop closure can meet real data for the first time.

---

# The rule for every future stage

**Every experiment produces its own stage report**, from [`stages/STAGE_TEMPLATE.md`](stages/STAGE_TEMPLATE.md).

**Before implementing**, write Part 1: objective · hypotheses (stated so they can be refuted) · success criteria · failure criteria · variables and controls · data provenance · metric definitions.

**After implementing**, append Part 2: exact implementation · commands · results · failures · fixes · interpretation · decision · next action.

**A stage report is never rewritten to make a result look better.** Failed hypotheses stay in the document, stated as they were originally believed. **Negative results are first-class results** — E-016 (RootSIFT) and E-018 (§B6 overstated) are recorded precisely because they contradicted our own reasoning.

## Scientific integrity rules

Binding on all stage documentation.

1. Never convert a hypothesis into a fact without experimental evidence.
2. Never hide a failed experiment.
3. Never delete an old result because a newer benchmark is better.
4. Preserve old experiment outputs (e.g. `experiments/EXP-001/results_preEXP002.csv`).
5. Clearly distinguish **training · calibration · validation · test · synthetic ground truth · GT-free evaluation**.
6. Never tune a threshold on the data used to claim its performance.
7. Never use a fit residual alone to claim correctness.
8. Never claim illumination invariance except under controlled illumination variation.
9. Never claim scale invariance except across a defined, tested scale range.
10. Never claim multi-modal robustness until actual modality differences are tested.
11. Never claim sub-pixel accuracy merely because the fitted residual is sub-pixel.
12. Every major performance claim carries: dataset/regime · number of cases · random seeds · metric definition · acceptance criterion · runtime environment · known limitations.
13. Where evidence is insufficient, write **"Evidence insufficient."**

### Current standing under rule 10

**No multi-modal claim has been made or is currently supportable.** Every result to date is on synthetic single-modality data. The real cross-modal gap — OHRC/TMC-2/IIRS ↔ NAC, including IIRS's thermal-emission bands beyond ~3 µm — is untested. **Evidence insufficient.**

### Current standing under rules 8 and 9

Illumination results are measured under **controlled, physically-rendered** Sun-geometry variation with exact ground truth, so rule 8 is satisfied *for synthetic terrain* — and only for that. Scale results cover **1.0×–4.0× only**; the real sensor ladder extends to **320:1** and is untested. **Evidence insufficient** beyond 4×.
