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
