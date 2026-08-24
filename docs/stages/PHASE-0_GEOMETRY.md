# PHASE-0 — Geometry gate (EXP-000)

**Stage ID:** PHASE-0 / EXP-000 · **Status:** COMPLETE — PASS
**Date:** 2026-08-24 (the only date recorded in repository artefacts)
**Supersedes:** — · **Enabled:** EXP-001

> **Reconstruction note.** This report is reconstructed from repository artefacts only: `experiments/EXP-000/metrics.json`, `experiments/EXP-000/README.md`, `docs/coordinate_contract.md`, `docs/research_log.md` (RL-001, RL-002, RL-007, RL-008), `docs/architecture_decisions.md` (ADR-0007), `scripts/run_exp000.py`, `src/siim/geometry/*`, `tests/test_geometry.py`.
>
> **The repository has no git history** (`git rev-parse` reports "not a repository"), so the ordering of individual edits within the phase, intermediate states, and per-run wall-clock timestamps are **not established from repository evidence**. Only the final state and the recorded metrics are evidence.

---

## A. Objective

Phase 0 existed to make every later measurement trustworthy.

The project's central methodological claim (ANALYSIS §A.3, ADR-0003) is that a *fit* residual is not an accuracy. That argument only has force if the geometry underneath is known-correct: if the transform algebra, the coordinate conventions, or the resampling arithmetic are wrong, then every number produced afterwards measures that bug rather than the science, and does so **silently** — coordinate errors produce plausible-looking imagery.

The stated gate (`experiments/EXP-000/README.md`, ANALYSIS §I) was therefore:

> A pipeline that cannot recover a known synthetic transform to well under a pixel has a bug. Nothing touches real lunar data until it can.

ADR-0007 records the ordering decision: `src/siim/geometry/` is built **first**, with tests, before any matching, representation or IO code.

## B. Initial assumptions (as recorded before the gate)

From ADR-0007, the coordinate contract, and RL-001/RL-002/RL-007:

| # | Assumption | Source | Later status |
|---|---|---|---|
| B1 | Coordinate-convention errors are high-probability and high-impact, and **silent** | Risk R8, ANALYSIS §G | Confirmed — RL-008 |
| B2 | Adopting a dependency's conventions implicitly (e.g. OpenCV) is how such bugs are born | ADR-0007 alternatives | Basis of the decision; not independently tested |
| B3 | The development machine is CPU-only (Ryzen 5 7520U, 4C/8T, 15.2 GB, `torch 2.10.0+cpu`, no CUDA) | RL-001 | Confirmed by direct measurement |
| B4 | Real sensor pairs mandate scale ratios up to **320:1** (OHRC 0.25 m ↔ IIRS 80 m) | RL-002, sources.md S1/S2 | Confirmed from published specs |
| B5 | LRO NAC frames reach ~52,000 lines, so estimators must stay conditioned at large coordinate magnitudes | sources.md S2 | Tested directly in EXP-000 |
| B6 | Relief displacement is first-order, not negligible: `Δr ≈ h·r/H` gives ~30 px for a 500 m rim at OHRC scale | RL-007 | Derivation only; **not experimentally tested in Phase 0** |

## C. Architecture built

### C.1 Module

`src/siim/geometry/` — five modules, in dependency order:

| File | Responsibility |
|---|---|
| `conventions.py` | Point arrays, homogeneous coordinates, axis-order helpers, pixel-centre convention, image extent |
| `transforms.py` | `Transform` (3×3 homogeneous + model class), five model constructors, composition, inversion |
| `estimate.py` | Model fitting with Hartley normalisation, condition reporting, degeneracy detection |
| `resample.py` | `warp`, `resize`, anti-alias prefiltering, validity masks |
| `synthetic.py` | Known-transform generation and true endpoint-error measurement |

### C.2 Explicit coordinate conventions

Normative in `docs/coordinate_contract.md`. The load-bearing rules:

- **C1** Point arrays are `(N, 2)` float64, ordered `(x, y)`.
- **C2** Images are indexed `img[row, col] == img[y, x]` — the opposite order. The swap is **never implicit**; `xy_to_rc()` / `rc_to_xy()` exist to make it visible at the call site.
- **C3** Integer coordinate `(0, 0)` is the **centre** of the top-left pixel. An image of width `W` spans `x ∈ [-0.5, W-0.5]`; its centre is `((W-1)/2, (H-1)/2)`, **not** `(W/2, H/2)`.
- **C4** Resampling by factor `s` maps `p' = s·(p + 0.5) − 0.5`, **not** `p' = s·p`.
- **C5** A `Transform` maps **source → reference**. `warp()` takes the *forward* transform and inverts internally. There is deliberately no `warp_inverse()` — offering both is how the direction gets confused.
- **C6** Points sent to infinity return `NaN` rather than raising, because a projective transform may legitimately do so.
- **C7** Residuals are converted back to the **native** pixel scale of the image being registered before reporting.
- **C8** Angles in radians, CCW-positive in `(x, y)`; because `y` points down, this reads clockwise on screen — stated so nobody "fixes" it.
- **C9** Hartley normalisation in every estimator; condition numbers reported; degeneracy detected, never silently fitted.

### C.3 Transform models

Five, with explicit degrees of freedom (`transforms.py`, `MODEL_DOF`):

| model | DOF | minimal set |
|---|---|---|
| translation | 2 | 1 |
| euclidean | 3 | 2 |
| similarity | 4 | 2 |
| affine | 6 | 3 |
| projective | 8 | 4 |

The DOF column is not decoration: model selection trades fit against complexity, and — per the module docstring — a projective fit can absorb topographic error into perspective parameters and *look* better while being physically wrong.

### C.4 Why geometry was kept independent of OpenCV

ADR-0007 rejected option (b), "adopt OpenCV conventions implicitly throughout", on the grounds that implicit conventions are precisely how silent coordinate bugs arise. The geometry layer is pure numpy/scipy so that **every convention has exactly one definition, visible in this repository**, pinned by property tests. OpenCV was introduced later, at EXP-001, and only for SIFT/RootSIFT feature extraction — never for geometry.

### C.5 Numerical design choices

- **Hartley normalisation** (centroid to origin, mean distance `√2`) before every solve, de-normalised after.
- **Condition number returned** by every estimator; `CONDITION_WARN = 1e8`.
- **Collinearity test** via the ratio of the second to first singular value of the centred point set; `COLLINEARITY_THRESHOLD = 1e-3`.
- **Immutable `Transform`** (frozen dataclass), so a recorded result cannot be mutated afterwards.
- **Non-projective models re-impose an exact `[0,0,1]` bottom row** after float inversion.
- **`NaN` fill** for out-of-footprint warp regions, with a separate boolean validity mask.

---

## D. EXP-000

### D.1 Purpose

Measure — not assert — that the geometry layer recovers known transforms, stays conditioned at lunar image scale, and implements the resampling convention correctly.

### D.2 Setup

From `scripts/run_exp000.py`:

- Seed `20260824`. Python 3.13.7, numpy 2.3.3 (`metrics.json:environment`).
- **Exact correspondences**: random points are mapped through a known transform with no noise, so any recovered error is algorithmic, not statistical.
- 50 trials per model, 60 points per trial, on a 512×512 frame.
- **Dense-grid evaluation**: error is measured between the *estimated map and the true map* on a grid over the image (`endpoint_error`, step 32), **not** as a residual on the points that were fitted. This is what makes it a genuine accuracy rather than the circular statistic of ANALYSIS §A.3, and it reports error *where there were no correspondences*.

### D.3 Acceptance criterion

**Recover a known synthetic transform to < 0.1 px true endpoint error.** (ANALYSIS §I; `tests/test_geometry.py::TestExp000Gate`.)

### D.4 Results — exact-correspondence recovery

Source: `experiments/EXP-000/metrics.json:model_recovery`. 50 trials each.

| Model | Worst max endpoint error | Max condition | ms / fit |
|---|---|---|---|
| translation | 8.039e-14 px | 1.00 | 1.25 |
| euclidean | 3.643e-13 px | 1.00 | 1.43 |
| similarity | 4.687e-13 px | 1.00 | 1.34 |
| affine | 4.567e-13 px | 1.52 | 1.45 |
| projective | 7.031e-13 px | 3.54 | 2.45 |

All five recover at **~1e-13 px**, against a **0.1 px** gate — roughly eleven orders of margin.

### D.5 Results — Hartley normalisation and coordinate extent

Source: `metrics.json:large_coordinate_stability`. Homography, 20 trials per extent.

| Coordinate extent | Worst error | Relative error | Max condition |
|---|---|---|---|
| 512 | 4.890e-13 px | 9.55e-16 | 3.26 |
| 10,000 | 1.281e-11 px | 1.28e-15 | 3.58 |
| **60,000** | 6.217e-11 px | 1.04e-15 | 3.44 |

**The condition number is flat (~3.3–3.6) across a 117× span of coordinate magnitude.** This is the direct evidence that Hartley normalisation works as intended. The extent range was chosen because NAC frames reach ~52,000 lines (sources.md S2), so 60,000 px is the operating regime, not an academic limit.

### D.6 Results — the resampling coordinate convention (contract C4)

Source: `metrics.json:scale_convention_c4`. Verified against **actual image resampling** of a Gaussian feature at a known sub-pixel location `(50.3, 61.7)`, σ = 4, measured by intensity-weighted centroid — not by restating the formula against itself.

| Resample scale | Contract C4 `p' = s(p+0.5) − 0.5` | Naive `p' = s·p` |
|---|---|---|
| 0.25 | **0.0000 px** | 0.3750 px |
| **0.5** | **0.0000 px** | **0.2500 px** |
| 2.0 | **0.0000 px** | 0.5000 px |
| **3.0** | **0.0000 px** | **1.0000 px** |

**Why the naive form is wrong.** Convert the pixel-centre coordinate `p` to edge space, `u = p + 0.5`; scale in edge space, `u' = s·u`; convert back, `p' = u' − 0.5 = s·p + (s−1)/2`. The naive version omits the `(s−1)/2` offset. Sanity check: upsampling by 2 turns original pixel 0 into new pixels 0 and 1, whose joint centre is 0.5 — the contract gives 0.5, the naive form gives 0.

The measured error is exactly `(s−1)/2`: 0.25 px at `s = 0.5`, and **a full pixel at `s = 3.0`**.

### D.7 Results — resampling fidelity, `NaN` handling, runtime

Source: `metrics.json:resampling`.

| Quantity | Value |
|---|---|
| Identity warp, max error | 5.55e-16 (exact) |
| Round-trip median error | 3.72e-06 |
| Round-trip p99 / max | 2.03e-05 / 3.50e-05 |
| Cubic warp, 256×256 | **19.476 ms** |

Invalid warp regions are filled with `NaN`, not `0.0`, with a separate validity mask (`resample.py:warp`). Total EXP-000 measurement runtime: **0.72 s**.

The 19.5 ms figure extrapolates to roughly 5 s for a 4096² warp on this CPU — the first datapoint against the ≤ 60 s/pair budget in ANALYSIS §L.

### D.8 Test count

`tests/test_geometry.py` contains **70 collected tests** (verified by `pytest --collect-only`). At the close of Phase 0 the suite reported **68 passed, 2 skipped** (`experiments/EXP-000/README.md`); the two skips are intentional — translation and euclidean models cannot express a scale change, so the "recover a similarity truth" case does not apply to them.

---

## E. Errors and traps discovered

### E.1 The naive scale-transform convention

**Problem:** The obvious coordinate update for a resampled image, `p' = s·p`, is wrong.
**Root cause:** It performs the scaling in pixel-*index* space rather than pixel-*edge* space, omitting the `(s−1)/2` offset implied by the pixel-centre convention (C3).
**Why it was dangerous:** The error is exactly `(s−1)/2` px — **1.0 px at 3× resampling** — while every intermediate image still looks perfectly correct. The project's target is sub-pixel accuracy, and scale normalisation across the real sensor ladder involves factors up to 320× (RL-002), so this would have consumed the entire error budget before any matching began, invisibly.
**Detection method:** Comparing both candidate formulas against *actual image resampling* of a Gaussian feature at a known sub-pixel position, rather than checking a formula against itself.
**Fix:** Contract C4; `scale_transform(s)` returns the correct update **as a `Transform`**, so a resampling factor lives in the transform chain and cannot be forgotten. `resize()` returns it alongside the resampled image.
**Regression protection:** `test_scale_transform_matches_real_resampling` (4 scales, tolerance 0.05 px) and `test_naive_scaling_is_wrong_by_exactly_half_of_scale_minus_one`, which exists specifically to fail loudly *with the size of the error* if anyone "simplifies" `scale_transform`.

### E.2 Numerical conditioning at lunar image scale

**Problem:** A DLT on raw image coordinates degrades as coordinate magnitude grows.
**Root cause:** The design matrix becomes badly conditioned when coordinates are large and uncentred.
**Why it was dangerous:** NAC frames reach ~52,000 lines, so this is the normal operating regime, not an edge case. The failure mode is a quietly worse fit, not an error.
**Detection method:** Sweeping coordinate extent 512 → 10,000 → 60,000 px and recording the condition number, rather than testing only at a convenient scale.
**Fix:** Hartley normalisation in every estimator (contract C9), de-normalised afterwards; condition number returned in `EstimationResult`.
**Regression protection:** `test_hartley_normalisation_keeps_conditioning_sane` (60,000 px extent, asserts condition < 1e8); the sweep is re-measured on every `run_exp000.py` run.

### E.3 Zero-filled invalid warp regions

**Problem:** Filling out-of-footprint warp output with `0.0` makes invalid data indistinguishable from real terrain.
**Root cause:** The conventional default for image warping is a zero or edge fill.
**Why it was dangerous:** **Lunar shadow is genuinely near-zero.** A `0.0` fill would be confusable with real shadowed terrain — a lunar-specific hazard that a generic computer-vision codebase would not consider, and one that could silently feed fabricated dark regions into a matcher.
**Detection method:** Reasoning from the domain during design, then pinned by test. Recorded as observation 3 in `experiments/EXP-000/README.md`.
**Fix:** `warp()` defaults to `cval = np.nan` and returns an explicit boolean validity mask.
**Regression protection:** `test_outside_source_is_marked_invalid_not_black`, whose assertion message states the reason.

### E.4 Aliasing when downsampling

**Problem:** Downsampling without a low-pass prefilter aliases high-frequency terrain texture into false low-frequency structure.
**Root cause:** Sampling below Nyquist.
**Why it was dangerous:** On crater-saturated terrain, aliased texture can **manufacture correspondences that do not exist** — the failure spec §41 warns about.
**Detection method:** Constructing a near-Nyquist sinusoid and comparing post-downsample variance with and without prefiltering.
**Fix:** `resize()` prefilters by default when shrinking, with `antialias_sigma(s) = (1/s − 1)/2`.
**Regression protection:** `test_downsampling_without_antialias_aliases` — a test whose purpose is to *demonstrate the artefact the default prevents* (aliased variance > 3× clean), so the default is justified rather than asserted.

No other Phase-0 failures are documented in the repository.

---

## F. What was proven vs. hypothesis

**Experimentally proven (measured, exact ground truth):**

1. All five transform models recover from exact correspondences at ~1e-13 px true endpoint error, against a 0.1 px gate.
2. Hartley normalisation holds the homography condition number flat (~3.4) from 512 to 60,000 px coordinate extent.
3. The contract-C4 resampling update is exact against real resampling; the naive form errs by exactly `(s−1)/2` px, reaching 1.0 px at `s = 3`.
4. Identity warp is exact (5.55e-16); cubic round-trip loss on smooth data is ≤ 3.5e-05.
5. Estimation costs 1.25–2.45 ms/fit; a 256² cubic warp costs 19.5 ms — on this CPU.

**Hypothesis, not tested in Phase 0:**

- That relief displacement (~30 px for a 500 m rim at OHRC scale) dominates residuals in real high-relief scenes — RL-007 is a geometric derivation, not a measurement.
- That keeping geometry OpenCV-independent prevents convention bugs — the rationale for ADR-0007, but no controlled comparison was run.
- That `max_uncovered_disc_radius` is the most meaningful coverage metric — argued in ADR-0006, still `PROPOSED`.

**Evidence insufficient:**

- Whether the resampling and conditioning behaviour holds on real lunar imagery. Phase 0 used synthetic data exclusively.

---

## G. What remained unknown

| Unknown | Why it could not be resolved in Phase 0 |
|---|---|
| Behaviour on real Chandrayaan-2 / LRO NAC imagery | No data in the repository; ISSDC product listings are behind an authenticated endpoint (ANALYSIS §B9, §K.2) |
| Whether relief breaks global models in practice | Requires real terrain with known geometry |
| Real cross-modal appearance gap | Requires actual multi-sensor pairs |
| Whether GT-free estimators track true error | Specified in ANALYSIS §F.1; not built until EXP-002 |
| CPU latency of learned engines | Deferred to EXP-005; still open |

---

## H. Architectural decisions

Recorded in `docs/architecture_decisions.md`; not restated here.

| ADR | Subject | Status at end of Phase 0 |
|---|---|---|
| ADR-0007 | `geometry/` built first, OpenCV-independent, with property tests | **ACCEPTED** (2026-08-24, EXP-000) |
| ADR-0001 | Pluggable matcher behind a fixed protocol | PROPOSED |
| ADR-0002 | CPU-first engine selection | PROPOSED |
| ADR-0003 | RMSE never stands alone | PROPOSED at this point |
| ADR-0005 | Scale normalisation is a pipeline stage | PROPOSED |
| ADR-0006 | `max_uncovered_disc_radius` primary coverage metric | PROPOSED |

ADR-0007's validation note records the decisive point: the decision "paid for itself immediately on one measurement", because the implicit-convention path would have burned the sub-pixel budget invisibly.

---

## I. Final status — PASS/FAIL per objective

| # | Objective | Verdict | Evidence |
|---|---|---|---|
| 1 | Recover known transforms below the 0.1 px gate | **PASS** | ~1e-13 px, all five models, 50 trials each |
| 2 | Stay conditioned at NAC-scale coordinates | **PASS** | condition ~3.4 flat, 512 → 60,000 px |
| 3 | Implement the resampling convention correctly | **PASS** | 0.0000 px vs 0.2500–1.0000 px for the naive form |
| 4 | Resample without introducing false structure | **PASS** | identity exact; antialias default justified by measurement |
| 5 | Make invalid regions unambiguous | **PASS** | `NaN` fill + validity mask, test-enforced |
| 6 | Establish a written, tested coordinate contract | **PASS** | `docs/coordinate_contract.md` + 70 tests |
| 7 | Measure baseline runtime | **PASS** | 1.25–2.45 ms/fit; 19.5 ms per 256² cubic warp |

**Phase 0: PASS.** Real-data experiments unblocked.

---

## J. Impact on EXP-001

Phase 0 enabled EXP-001 in four concrete ways:

1. **A trustworthy measuring instrument.** EXP-001's central claim — that fit RMSE is misleading — is only meaningful if the true-error measurement is sound. `endpoint_error` comparing *maps on a dense grid* came from Phase 0.
2. **A correct resampling chain.** EXP-001's synthetic pairs are built by warping a height field; without contract C4 the ground truth itself would have been wrong by up to a pixel per resampling step.
3. **Degeneracy and conditioning reporting**, which EXP-001's RANSAC consumed directly.
4. **The regression habit.** Phase 0 established that a hazard gets a test that *documents the hazard*, not just a test that the code works. EXP-001 and EXP-002 followed that pattern.

Phase 0 did **not** prevent every harness bug. EXP-001 shipped a ground-truth generator with a `pad`-offset error of 40·√2 = 56.57 px (RL-013, ERROR_LEDGER E-005) that Phase-0-style geometry tests could not catch, because the error was in how the *experiment* composed correct primitives, not in the primitives. That distinction is itself a Phase-0 lesson carried forward: a verified geometry layer is necessary but not sufficient.
