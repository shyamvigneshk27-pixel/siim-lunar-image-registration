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

## EXP-003 — Illumination-Invariant Representations

**Status: NOT STARTED.** No implementation, no results.

Planned objective: test whether a polarity-agnostic representation moves the illumination cliff **beyond Δazimuth 30° on realistic (A) terrain regimes** — the criterion EXP-002 set in advance.

ADR-0004 (polarity-agnostic structure as the default representation) remains `PROPOSED` and states plainly that **if raw intensity wins, the ADR is superseded.** This stage is that test.

Explicitly out of scope until this stage runs: RIFT2, phase congruency, orientation-mod-π, and every learned matcher.

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
