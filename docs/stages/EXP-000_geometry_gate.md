# EXP-000 — Geometry Gate

**Stage ID:** EXP-000 (also referred to as PHASE-0 in earlier documents)
**Name:** Geometry gate — verified transform algebra, coordinate contract, resampling
**Status:** COMPLETE — PASS
**Date:** 2026-08-24 — the only date recorded in any repository artefact
**Depends on:** — · **Followed by:** EXP-001

---

## 0. Provenance and what this report is

This is a **retrospective** stage report, written after the fact. It is reconstructed
**only** from repository artefacts:

`experiments/EXP-000/metrics.json` · `experiments/EXP-000/README.md` ·
`scripts/run_exp000.py` · `src/siim/geometry/*` · `tests/test_geometry.py` ·
`docs/coordinate_contract.md` · `docs/architecture_decisions.md` (ADR-0007) ·
`docs/research_log.md` · `docs/sources.md`.

**Three limits on this reconstruction, stated up front:**

1. **The repository is not a git repository.** `git rev-parse --is-inside-work-tree`
   returns `fatal: not a git repository`. Per-edit chronology, intermediate code states,
   the order in which bugs were found, and wall-clock timestamps are therefore
   **Not verified** and cannot be recovered. Only the final source state and the recorded
   metrics are evidence.
2. **All artefacts carry the single date 2026-08-24.** Elapsed time for the stage, number
   of working sessions, and calendar sequencing are **Not verified**.
3. **Pre-fix source text does not exist in the repository.** Where this report describes a
   defect, the *defect* is evidenced by a recorded measurement and by a regression test
   that still names it — not by a preserved diff.

Numbers are quoted as `value (artefact:key)`. Anything without such a reference is marked
`[NOT VERIFIED]`.

---

## 1. Stage objective

**The question:** *Can this codebase recover a known geometric transform to well under a
pixel, stay numerically conditioned at real lunar image scale, and resample without
introducing coordinate error — before any measurement of matching quality is attempted?*

The reasoning behind the gate, from `experiments/EXP-000/README.md` and ADR-0007:
the project's central methodological claim is that **a fit residual is not an accuracy**.
That claim only has force if the geometry underneath is known-correct. If the transform
algebra, coordinate conventions, or resampling arithmetic are wrong, every number produced
afterwards measures that bug instead of the science — and does so **silently**, because
coordinate errors produce imagery that still looks correct.

**The gate as stated:** a pipeline that cannot recover a known synthetic transform to well
under a pixel has a bug, and nothing touches real lunar data until it can.

**Acceptance criterion, set in advance:** true endpoint error **< 0.1 px**
(`tests/test_geometry.py::TestExp000Gate`).

---

## 2. Starting assumptions

Recorded in ADR-0007, `docs/coordinate_contract.md`, and `docs/research_log.md`
(RL-001, RL-002, RL-007).

| # | Assumption | Source | Kind | Later status |
|---|---|---|---|---|
| A1 | Coordinate-convention errors are high-probability, high-impact, and **silent** | Risk R8 | reasoned | **Confirmed by measurement** — see E-000.1 |
| A2 | Adopting a dependency's conventions implicitly (e.g. OpenCV's) is how such bugs are born | ADR-0007 alternatives | reasoned | Basis of the decision; **never independently tested** — no controlled comparison was run |
| A3 | The development machine is CPU-only (4C/8T, ~15.2 GB, no CUDA) | RL-001 | measured | Confirmed. `metrics.json:environment.processor` records `AMD64 Family 23 Model 160 Stepping 0, AuthenticAMD`; the retail name *Ryzen 5 7520U* appears in the READMEs and is **[NOT VERIFIED]** against a machine-readable artefact |
| A4 | Real sensor pairs mandate scale ratios up to **320:1** (OHRC 0.25 m ↔ IIRS 80 m) | RL-002, sources.md S1/S2 | published specs | Confirmed from published specifications; not tested in this stage |
| A5 | LRO NAC frames reach ~52,000 lines, so estimators must stay conditioned at large coordinate magnitude | sources.md S2 | published specs | **Tested directly** — §5.2 |
| A6 | Relief displacement is first-order, not negligible: `Δr ≈ h·r/H` gives ~30 px for a 500 m rim at OHRC scale | RL-007 | derivation | **Not tested in EXP-000.** Geometric derivation only; still untested at EXP-002 |

---

## 3. What we implemented

### 3.1 The module

`src/siim/geometry/` — pure numpy/scipy, **deliberately OpenCV-independent**, so that
every convention has exactly one definition visible inside this repository.

| File | Lines | Responsibility |
|---|---|---|
| `conventions.py` | 181 | Point arrays, homogeneous coordinates, axis-order helpers, pixel-centre convention, image extent |
| `transforms.py` | 280 | `Transform` (3×3 homogeneous + model class), five model constructors, composition, inversion |
| `estimate.py` | 343 | Model fitting with Hartley normalisation, condition reporting, degeneracy detection |
| `resample.py` | 196 | `warp`, `resize`, anti-alias prefiltering, validity masks |
| `synthetic.py` | 202 | Known-transform generation and true endpoint-error measurement |
| `__init__.py` | 107 | Public surface |

### 3.2 The coordinate contract

Normative in `docs/coordinate_contract.md` (87 lines). The load-bearing rules:

- **C1** Point arrays are `(N, 2)` float64, ordered `(x, y)`.
- **C2** Images are indexed `img[row, col] == img[y, x]` — the opposite order. The swap is
  **never implicit**; `xy_to_rc()` / `rc_to_xy()` make it visible at the call site.
- **C3** Integer coordinate `(0, 0)` is the **centre** of the top-left pixel. An image of
  width `W` spans `x ∈ [-0.5, W-0.5]`; its centre is `((W-1)/2, (H-1)/2)`, **not** `(W/2, H/2)`.
- **C4** Resampling by factor `s` maps `p' = s·(p + 0.5) − 0.5`, **not** `p' = s·p`.
- **C5** A `Transform` maps **source → reference**. `warp()` takes the *forward* transform
  and inverts internally. There is deliberately no `warp_inverse()` — offering both is how
  direction gets confused.
- **C6** Points sent to infinity return `NaN` rather than raising, because a projective
  transform may legitimately do so.
- **C7** Residuals are converted back to the **native** pixel scale of the image being
  registered before reporting.
- **C8** Angles in radians, CCW-positive in `(x, y)`; because `y` points down this reads
  clockwise on screen — stated so nobody "fixes" it.
- **C9** Hartley normalisation in every estimator; condition numbers reported; degeneracy
  detected, never silently fitted.

### 3.3 Transform models

Five, with explicit degrees of freedom (`transforms.py`, `MODEL_DOF`):

| model | DOF | minimal set (point pairs) |
|---|---|---|
| translation | 2 | 1 |
| euclidean | 3 | 2 |
| similarity | 4 | 2 |
| affine | 6 | 3 |
| projective | 8 | 4 |

`[INTERPRETATION]` The DOF column is not decoration. Model selection trades fit against
complexity, and — per the module docstring — a projective fit can absorb topographic error
into perspective parameters and *look* better while being physically wrong. This is the
same hazard that E-000.1 and, later, EXP-001's fit-RMSE finding both instantiate.

### 3.4 Numerical design choices

- **Hartley normalisation** (centroid to origin, mean distance `√2`) before every solve,
  de-normalised after.
- **Condition number returned** by every estimator; `CONDITION_WARN = 1e8`.
- **Collinearity test** via the ratio of second to first singular value of the centred
  point set; `COLLINEARITY_THRESHOLD = 1e-3`.
- **Immutable `Transform`** (frozen dataclass), so a recorded result cannot be mutated.
- **Non-projective models re-impose an exact `[0,0,1]` bottom row** after float inversion.
- **`NaN` fill** for out-of-footprint warp regions, plus a separate boolean validity mask.

### 3.5 `scale_transform` — the contract encoded as an object

`transforms.py:263` returns the C4 update **as a `Transform`**, not as a number, so a
resampling factor lives in the transform chain and cannot be dropped. The docstring
records the hazard in the source itself:

> *"The offset term `(scale - 1) / 2` is the part that the naive `p' = scale * p` omits.
> At `scale = 2` that omission is a half-pixel error — the whole sub-pixel budget."*

---

## 4. Experiments performed

One experiment, `scripts/run_exp000.py` (207 lines), with five measurement blocks.

| Block | What is varied | n | Artefact key |
|---|---|---|---|
| Model recovery | 5 transform models | 50 trials each, 60 points, 512×512 frame | `model_recovery` |
| Large-coordinate stability | coordinate extent 512 / 10,000 / 60,000 px | 20 trials per extent, homography | `large_coordinate_stability` |
| Scale convention C4 | resample scale 0.25 / 0.5 / 2.0 / 3.0 | Gaussian σ=4 at `(50.3, 61.7)` | `scale_convention_c4` |
| Resampling fidelity | identity warp, round trip, cubic cost | — | `resampling` |
| Runtime | ms/fit per model, ms/warp | — | `model_recovery.*.ms_per_estimate` |

**Design choices that make the measurement non-circular:**

- **Exact correspondences.** Points are mapped through a known transform with **no noise**,
  so any recovered error is algorithmic, not statistical.
- **Dense-grid evaluation.** Error is measured between the *estimated map and the true map*
  on a grid over the image (`endpoint_error`, step 32) — **not** as a residual on the points
  that were fitted. This reports error *where there were no correspondences*, and is what
  distinguishes it from the circular fit statistic the project exists to argue against.
- **Physical verification of C4.** The two candidate scale formulas are compared against
  **actual image resampling** of a Gaussian at a known sub-pixel position, measured by
  intensity-weighted centroid — not against a restatement of themselves.

**Data roles.** All data is synthetic with exact ground truth. There is no calibration /
validation split in EXP-000 and none is needed: no threshold is selected from the data.
The only threshold (0.1 px) was set in advance from the project's accuracy target.

---

## 5. Exact commands used

Recorded in `experiments/EXP-000/README.md` under **Reproduce**:

```bash
python scripts/run_exp000.py
python -m pytest tests/ -q
```

`scripts/run_exp000.py` takes **no arguments** — verified: the file contains no `argparse`
import and no `add_argument` call. Seed `20260824` is hard-coded.

**Environment** (`metrics.json:environment`):

| Field | Value |
|---|---|
| python | 3.13.7 |
| numpy | 2.3.3 |
| platform | Windows-11-10.0.26200-SP0 |
| processor | AMD64 Family 23 Model 160 Stepping 0, AuthenticAMD |

`experiments/EXP-000/README.md` additionally states **scipy 1.16.2** and **AMD Ryzen 5
7520U, 4C/8T, CPU-only**. Neither appears in `metrics.json`; both are **[NOT VERIFIED]**
against a machine-readable artefact.

---

## 6. Quantitative results

All values from `experiments/EXP-000/metrics.json`. Environment as §5. Acceptance criterion
throughout: **< 0.1 px true endpoint error**, set in advance.

### 6.1 Exact-correspondence model recovery — `[MEASURED]`

50 trials per model, 60 points per trial, 512×512 frame, seed 20260824.

| Model | Worst max endpoint error | Worst median endpoint error | Max condition | ms / fit |
|---|---|---|---|---|
| translation | 8.039e-14 px | 6.355e-14 px | 1.000 | 1.253 |
| euclidean | 3.643e-13 px | 1.979e-13 px | 1.000 | 1.432 |
| similarity | 4.687e-13 px | 2.329e-13 px | 1.000 | 1.337 |
| affine | 4.567e-13 px | 2.050e-13 px | 1.525 | 1.450 |
| projective | 7.031e-13 px | 2.050e-13 px | 3.543 | 2.449 |

`[MEASURED]` All five models recover at **~1e-13 px** against a **0.1 px** gate.

`[INTERPRETATION]` That is roughly eleven orders of magnitude of margin, i.e. the models
are recovering at float64 round-off. The result establishes that the *algebra* is correct;
it says nothing about behaviour under noise, outliers, or real imagery, none of which this
experiment contains.

### 6.2 Hartley normalisation and coordinate extent — `[MEASURED]`

Homography, 20 trials per extent (`large_coordinate_stability`).

| Coordinate extent | Worst max endpoint error | Relative error | Max condition |
|---|---|---|---|
| 512 | 4.890e-13 px | 9.550e-16 | 3.255 |
| 10,000 | 1.281e-11 px | 1.281e-15 | 3.584 |
| **60,000** | 6.217e-11 px | 1.036e-15 | 3.438 |

`[MEASURED]` The condition number is **flat at ~3.26–3.58 across a 117× span** of
coordinate magnitude. Absolute error grows with extent; **relative** error does not
(9.55e-16 → 1.04e-15).

`[INTERPRETATION]` This is Hartley normalisation doing what it is for. The extent range was
chosen because NAC frames reach ~52,000 lines (sources.md S2), so 60,000 px is the
*operating* regime, not an academic limit.

### 6.3 The resampling coordinate convention (contract C4) — `[MEASURED]`

Verified against **actual image resampling** of a Gaussian feature (σ = 4) at a known
sub-pixel location `(50.3, 61.7)`, measured by intensity-weighted centroid.

| Resample scale | Contract C4 `p' = s(p+0.5) − 0.5` | Naive `p' = s·p` | Predicted naive error `(s−1)/2` |
|---|---|---|---|
| 0.25 | 2.216e-09 px | **0.375000 px** | 0.375 |
| 0.5 | 3.553e-15 px | **0.250000 px** | 0.250 |
| 2.0 | 1.421e-14 px | **0.500000 px** | 0.500 |
| **3.0** | 5.684e-14 px | **1.000000 px** | **1.000** |

`[MEASURED]` The naive formula's error equals `(s−1)/2` to six decimal places at every
tested scale. The contract form is exact to float precision.

### 6.4 Resampling fidelity, `NaN` handling, runtime — `[MEASURED]`

| Quantity | Value |
|---|---|
| Identity warp, max error | 5.551e-16 (exact to round-off) |
| Round-trip median error | 3.717e-06 |
| Round-trip p99 error | 2.031e-05 |
| Round-trip max error | 3.500e-05 |
| Cubic warp, 256×256 | **19.476 ms** |
| **Total EXP-000 measurement runtime** | **0.723 s** |

`[INTERPRETATION]` The 19.5 ms figure extrapolates to roughly 5 s for a 4096² warp on this
CPU — the first datapoint against the ≤ 60 s/pair budget. The extrapolation assumes linear
scaling in pixel count and is **[NOT VERIFIED]**; no 4096² warp was measured.

`[MEASURED]` Estimation costs 1.25–2.45 ms/fit. `[INTERPRETATION]` Geometry is not where a
runtime budget will be spent; matching and warping are.

---

## 7. What worked

| Claim | Evidence | Scope of the claim |
|---|---|---|
| All five transform models recover known transforms at machine precision | ~1e-13 px, 50 trials each (`model_recovery`) | **Exact, noise-free correspondences only** |
| Hartley normalisation holds conditioning at NAC scale | condition 3.26–3.58 across 512 → 60,000 px | Homography, synthetic points |
| Contract C4 is exact where the naive form is wrong by up to 1.0 px | `scale_convention_c4`, verified against physical resampling | Scales 0.25–3.0 |
| Identity warp is exact; cubic round-trip loss is ≤ 3.5e-05 on smooth data | `resampling` | Smooth synthetic data only |
| Invalid warp regions are unambiguous | `NaN` fill + boolean mask, `test_outside_source_is_marked_invalid_not_black` | — |
| A written coordinate contract exists and is machine-enforced | `docs/coordinate_contract.md` + 70 tests in `tests/test_geometry.py` | — |

---

## 8. What failed

**No acceptance criterion failed.** EXP-000 passed all seven of its stated objectives (§14).

What *was found* were four latent hazards, three of which were live defects in the
obvious implementation and one of which was a domain-specific default. They are the
substance of this stage, and are documented in §9.

The single most important thing this stage failed to do is stated plainly here rather than
buried: **a verified geometry layer is necessary but not sufficient.** EXP-001 subsequently
shipped a ground-truth generator wrong by 56.57 px built entirely out of these correct
primitives (see `EXP-001_rootsift_baseline.md` §9, E-001.1). Phase-0-style tests could not
catch it, because the error was in how an *experiment* composed correct primitives, not in
the primitives.

---

## 9. Errors and bugs discovered

Each block follows **Problem → Evidence → Root Cause → Fix → Verification → Lesson**, and
carries a failure class from the five defined in `STAGE_REPORT_TEMPLATE.md` §2.7.

---

### E-000.1 — Naive resampling coordinate update is wrong by `(s−1)/2` px

**Class:** implementation bug (avoided before it shipped) · **Severity: CRITICAL**
**Cross-reference:** `ERROR_LEDGER.md` E-001

- **Problem.** The obvious coordinate update for a resampled image, `p' = s·p`, is wrong.
- **Evidence.** Both candidate formulas compared against *actual image resampling* of a
  Gaussian at a known sub-pixel position. Naive-form error: 0.375 / 0.250 / 0.500 /
  **1.000** px at s = 0.25 / 0.5 / 2.0 / 3.0 (`metrics.json:scale_convention_c4`). Contract
  form: ≤ 2.2e-09 px at every scale.
- **Root cause.** The naive form performs the scaling in pixel-**index** space instead of
  pixel-**edge** space, omitting the `(s−1)/2` offset implied by the pixel-centre
  convention (C3). Derivation: convert to edge space `u = p + 0.5`; scale, `u' = s·u`;
  convert back, `p' = u' − 0.5 = s·p + (s−1)/2`. Sanity check: upsampling by 2 turns
  original pixel 0 into new pixels 0 and 1, whose joint centre is 0.5 — the contract gives
  0.5, the naive form gives 0.
- **Fix.** Contract C4. `scale_transform(s)` (`transforms.py:263`) returns the correct
  update **as a `Transform`**, so the factor lives in the transform chain and cannot be
  dropped; `resize()` returns it alongside the resampled image.
- **Verification.** `test_scale_transform_matches_real_resampling` (4 scales, 0.05 px
  tolerance) and `test_naive_scaling_is_wrong_by_exactly_half_of_scale_minus_one` — the
  second exists **specifically to fail loudly with the size of the error** if anyone
  "simplifies" `scale_transform`. Both present in `tests/test_geometry.py`; suite green.
- **Lesson.** **Verify a convention against the physical operation it describes, not
  against its own restatement.** Every intermediate image looks perfectly correct under the
  naive form — the failure is invisible in imagery. Scale normalisation across the real
  sensor ladder needs factors up to 320× (A4), so this single error would have consumed the
  entire sub-pixel budget before any matching began.

| | naive `p' = s·p` | contract C4 |
|---|---|---|
| s = 0.25 | 0.375000 px | 2.216e-09 px |
| s = 0.5 | 0.250000 px | 3.553e-15 px |
| s = 2.0 | 0.500000 px | 1.421e-14 px |
| s = 3.0 | **1.000000 px** | 5.684e-14 px |

---

### E-000.2 — DLT conditioning degrades at large coordinate magnitude

**Class:** implementation bug (avoided) · **Severity: HIGH**
**Cross-reference:** `ERROR_LEDGER.md` E-002

- **Problem.** A DLT on raw, uncentred image coordinates becomes ill-conditioned as
  coordinate magnitude grows.
- **Evidence.** Coordinate extent swept 512 → 10,000 → 60,000 px with the condition number
  recorded (`metrics.json:large_coordinate_stability`), rather than testing at one
  convenient scale.
- **Root cause.** The design matrix becomes badly conditioned when coordinates are large
  and uncentred. `[INTERPRETATION]` The failure mode is a quietly worse fit, not an
  exception — so it would never announce itself.
- **Fix.** Hartley normalisation in every estimator (contract C9), de-normalised
  afterwards; condition number returned in `EstimationResult`; `CONDITION_WARN = 1e8`.
- **Verification.** Condition flat at 3.255 / 3.584 / 3.438 across the 117× span;
  relative error flat at ~1e-15. `test_hartley_normalisation_keeps_conditioning_sane`
  (60,000 px extent, asserts condition < 1e8). The sweep is re-measured on every
  `run_exp000.py` run.
- **Lesson.** **Test at the operating scale.** NAC frames reach ~52,000 lines, so 60,000 px
  is normal, not an edge case. A test at 512 px would have passed and proved nothing.

| Extent | condition (with Hartley) |
|---|---|
| 512 | 3.255 |
| 10,000 | 3.584 |
| 60,000 | 3.438 |

`[NOT VERIFIED]` The condition number **without** Hartley normalisation was not recorded in
any artefact. The claim that it degrades "roughly as the square of coordinate magnitude"
appears in `experiments/EXP-000/README.md` as an unmeasured assertion.

---

### E-000.3 — Zero-filled invalid warp regions are indistinguishable from real terrain

**Class:** synthetic-data / domain limitation converted into a design hazard · **Severity: HIGH**
**Cross-reference:** `ERROR_LEDGER.md` E-003

- **Problem.** Filling out-of-footprint warp output with `0.0` makes invalid data
  indistinguishable from real terrain.
- **Evidence.** Domain reasoning during design, recorded as observation 3 in
  `experiments/EXP-000/README.md`, then pinned by test. **This one was reasoned, not
  measured** — no experiment produced a number for it.
- **Root cause.** The conventional default for image warping in general-purpose CV
  libraries is a zero or edge fill. **Lunar shadow is genuinely near-zero**, so on this
  domain a `0.0` fill is confusable with real shadowed terrain.
- **Fix.** `warp()` defaults to `cval = np.nan` and returns an explicit boolean validity mask.
- **Verification.** `test_outside_source_is_marked_invalid_not_black`, whose assertion
  message states the reason. Present in `tests/test_geometry.py`; suite green.
- **Lesson.** **A generic CV default can be a domain hazard.** Defaults must be
  re-examined per domain rather than inherited. This is the same failure family as A2 —
  inheriting someone else's convention silently.

---

### E-000.4 — Downsampling without a prefilter aliases terrain texture into false structure

**Class:** implementation bug (avoided) · **Severity: MEDIUM**
**Cross-reference:** `ERROR_LEDGER.md` E-004

- **Problem.** Downsampling without a low-pass prefilter aliases high-frequency terrain
  texture into false low-frequency structure.
- **Evidence.** A near-Nyquist sinusoid was constructed and post-downsample variance
  compared with and without prefiltering; the aliased variance is > 3× the clean result
  (`test_downsampling_without_antialias_aliases`).
- **Root cause.** Sampling below Nyquist.
- **Fix.** `resize()` prefilters by default when shrinking, with
  `antialias_sigma(s) = (1/s − 1)/2`.
- **Verification.** `test_downsampling_without_antialias_aliases` — a test whose purpose is
  to **demonstrate the artefact the default prevents**, so the default is justified by
  measurement rather than asserted.
- **Lesson.** On crater-saturated terrain, aliasing can **manufacture correspondences that
  do not exist**. A test that demonstrates the artefact justifies the default; a test that
  merely exercises the code does not.

---

**No other EXP-000 failures are documented in the repository.** Whether others occurred and
went unrecorded is **[NOT VERIFIED]** — there is no git history to check.

---

## 10. Failure classification

| Class | Entries | Note |
|---|---|---|
| **Implementation bug** | E-000.1, E-000.2, E-000.4 | All three were caught *before* shipping, by a test designed to expose them. None corrupted a published number |
| **Experimental / design mistake** | — | None recorded |
| **Incorrect hypothesis** | — | None. EXP-000 tested no hypothesis about the world; it tested code against arithmetic |
| **Synthetic-data limitation** | E-000.3 (as a domain hazard); all of §14's results | Every EXP-000 result is on synthetic data |
| **Genuine research negative result** | — | None |

`[INTERPRETATION]` The absence of design mistakes and incorrect hypotheses in this stage is
itself informative: EXP-000 was an engineering gate, not a research experiment. Both
categories appear in force from EXP-001 onward.

---

## 11. Hypotheses that were disproved

**None.** EXP-000 did not state refutable hypotheses about the world; it stated an
acceptance criterion about the code and met it.

Two beliefs held at the start of the stage remain **untested rather than disproved**:

| Belief | Status |
|---|---|
| A2 — keeping geometry OpenCV-independent prevents convention bugs | **[HYPOTHESIS]** The rationale for ADR-0007. No controlled comparison was run and none is planned. E-000.1 is consistent with it but does not test it |
| A6 — relief displacement (~30 px for a 500 m rim at OHRC scale) dominates residuals in real high-relief scenes | **[HYPOTHESIS]** Geometric derivation (RL-007) only. Still untested as of EXP-002 |

---

## 12. Conclusions that survived

### `[MEASURED]` — proven, within the stated scope

1. All five transform models recover from **exact, noise-free** correspondences at
   ~1e-13 px true endpoint error, against a 0.1 px gate. (50 trials/model, synthetic.)
2. Hartley normalisation holds the homography condition number flat at ~3.3–3.6 from
   512 to 60,000 px coordinate extent.
3. The contract-C4 resampling update is exact against real resampling; the naive form errs
   by exactly `(s−1)/2` px, reaching **1.0 px at s = 3**.
4. Identity warp is exact (5.55e-16); cubic round-trip loss on smooth data is ≤ 3.5e-05.
5. Estimation costs 1.25–2.45 ms/fit; a 256² cubic warp costs 19.5 ms — **on this CPU**.

### `[INTERPRETATION]` — our reading, which could be wrong while the numbers stay right

- Geometry is not a runtime bottleneck; effort belongs in matching and warping.
- The eleven orders of margin mean the geometry layer will not be the limiting factor on
  accuracy — but only in the noise-free regime actually tested.

### `[NOT VERIFIED] / Evidence insufficient`

- Whether resampling and conditioning behaviour holds on **real lunar imagery**.
  EXP-000 used synthetic data exclusively. **Evidence insufficient.**
- Whether relief displacement breaks global transform models in practice (A6).
  **Evidence insufficient.**
- Whether OpenCV-independence prevents convention bugs (A2). **Evidence insufficient.**
- The extrapolated ~5 s cost for a 4096² warp. **Not verified** — no such warp was measured.
- Condition-number behaviour *without* Hartley normalisation. **Not verified** — not recorded.

**All EXP-000 results are on synthetic data with exact ground truth. Nothing here is
evidence about Chandrayaan-2 or LRO NAC imagery.**

---

## 13. Decisions / ADRs affected

Full arguments live in `docs/architecture_decisions.md`; they are not restated here.

| ADR | Subject | Status at end of EXP-000 |
|---|---|---|
| **ADR-0007** | `geometry/` built first, OpenCV-independent, with property tests | **ACCEPTED** (2026-08-24, EXP-000) |
| ADR-0001 | Pluggable matcher engine behind a fixed protocol | PROPOSED |
| ADR-0002 | CPU-first engine selection | PROPOSED |
| ADR-0003 | RMSE never stands alone | PROPOSED at this point (accepted at EXP-001) |
| ADR-0005 | Scale normalisation is a pipeline stage | PROPOSED |
| ADR-0006 | `max_uncovered_disc_radius` as primary coverage metric | PROPOSED |

`DECISION_LEDGER.md` row: **D-007**.

`[INTERPRETATION]` ADR-0007's validation note records that the decision "paid for itself
immediately on one measurement" — E-000.1. That is a reading of the evidence, not a
controlled comparison: it is possible the same bug would have been caught another way.

---

## 14. Verdict against the stated objectives

| # | Objective | Verdict | Evidence |
|---|---|---|---|
| 1 | Recover known transforms below the 0.1 px gate | **PASS** | ~1e-13 px, all five models, 50 trials each |
| 2 | Stay conditioned at NAC-scale coordinates | **PASS** | condition 3.26–3.58 flat, 512 → 60,000 px |
| 3 | Implement the resampling convention correctly | **PASS** | 0.000000 px vs 0.250000–1.000000 px for the naive form |
| 4 | Resample without introducing false structure | **PASS** | identity exact; antialias default justified by measurement |
| 5 | Make invalid regions unambiguous | **PASS** | `NaN` fill + validity mask, test-enforced |
| 6 | Establish a written, tested coordinate contract | **PASS** | `docs/coordinate_contract.md` + 70 tests |
| 7 | Measure baseline runtime | **PASS** | 1.25–2.45 ms/fit; 19.476 ms per 256² cubic warp |

**EXP-000: PASS on all seven.** Real-data experiments unblocked.

---

## 15. Tests and reproducibility status

| Item | Status |
|---|---|
| Tests in `tests/test_geometry.py` | **70 collected** — verified by `python -m pytest tests/test_geometry.py --collect-only -q` |
| Suite state **at the close of EXP-000** | **68 passed, 2 skipped** (`experiments/EXP-000/README.md`) |
| Suite state **now** (after EXP-001 and EXP-002 added modules) | **168 passed, 2 skipped in 23.02 s** — verified by running `python -m pytest tests/` |
| The 2 skips | Intentional. Translation and euclidean models cannot express a scale change, so the "recover a similarity truth" case does not apply to them |
| Seed | `20260824`, hard-coded in `scripts/run_exp000.py` |
| Determinism | `metrics.json` records fixed seeds and exact correspondences. **Bit-identical re-run is [NOT VERIFIED]** — no re-run comparison artefact exists for EXP-000 |
| Regression tests pinning EXP-000 hazards | `test_scale_transform_matches_real_resampling`, `test_naive_scaling_is_wrong_by_exactly_half_of_scale_minus_one`, `test_hartley_normalisation_keeps_conditioning_sane`, `test_outside_source_is_marked_invalid_not_black`, `test_downsampling_without_antialias_aliases` — all five verified present |
| Runtime figures | Wall-clock, machine-dependent. Not reproducible across hardware |

---

## 16. Files / modules created or changed

| Path | Status | Purpose |
|---|---|---|
| `src/siim/geometry/conventions.py` | created | Pixel-centre convention, axis-order helpers, homogeneous coords |
| `src/siim/geometry/transforms.py` | created | `Transform`, five models, composition, `scale_transform` (C4) |
| `src/siim/geometry/estimate.py` | created | Hartley-normalised fitting, condition reporting, degeneracy detection |
| `src/siim/geometry/resample.py` | created | `warp`, `resize`, antialias prefilter, `NaN` validity masks |
| `src/siim/geometry/synthetic.py` | created | Known-transform generation, `endpoint_error` |
| `src/siim/geometry/__init__.py` | created | Public surface |
| `tests/test_geometry.py` | created | 70 property tests pinning the contract |
| `tests/conftest.py` | created | Shared fixtures |
| `docs/coordinate_contract.md` | created | Normative conventions C1–C9 |
| `scripts/run_exp000.py` | created | Gate measurement runner |
| `experiments/EXP-000/metrics.json` | created | All recorded measurements |
| `experiments/EXP-000/README.md` | created | Stage-contemporary report |
| `pyproject.toml` | created | numpy / scipy / pyyaml / pillow; no OpenCV at this stage |

`[NOT VERIFIED]` Which of these files were created in EXP-000 versus adjusted later cannot
be established without git history. The attribution above is inferred from module content
and from ADR-0007's ordering decision.

---

## 17. Limitations and threats to validity

1. **Synthetic only.** Every number is from generated data with exact ground truth. Nothing
   in EXP-000 is evidence about real lunar imagery.
2. **Noise-free only.** Correspondences are exact. Behaviour under correspondence noise,
   outliers, or a real matcher's error distribution is untested here — EXP-001 and EXP-002
   cover it.
3. **No relief.** All transforms are global 2-D models on a plane. Terrain-induced
   parallax (A6) is absent by construction.
4. **Single machine, single seed.** Runtime figures are one CPU. The 0.1 px gate is
   comfortably met, so seed sensitivity is unlikely to matter here — but it was not measured.
5. **The C4 verification covers scales 0.25–3.0.** The real ladder reaches 320:1
   (A4). **Evidence insufficient** beyond 3×.
6. **Conditioning is verified for homography only** at extent. Other models were measured
   at 512 px extent only.
7. **A verified geometry layer does not verify experiments built on it.** Demonstrated
   directly by EXP-001's 56.57 px ground-truth bug.

---

## 18. Lessons learned

1. **Verify a convention against the physical operation it describes, not against its own
   restatement.** E-000.1 was found by resampling an actual image, not by re-reading a
   formula. This is the single most transferable lesson of the stage.
2. **Test at the operating scale, not the convenient one.** E-000.2 is invisible at 512 px.
3. **A library default is a domain assumption.** E-000.3: zero-fill is harmless in generic
   CV and hazardous on a body where real shadow is near-zero.
4. **Write tests that document a hazard, not tests that exercise a feature.**
   `test_naive_scaling_is_wrong_by_exactly_half_of_scale_minus_one` and
   `test_downsampling_without_antialias_aliases` both exist to make a *future*
   simplification fail loudly with the size of the error it would introduce. This habit
   propagated to every later stage.
5. **Silent errors are the expensive ones.** All four EXP-000 hazards produce
   correct-looking output. None would raise an exception.
6. **Necessary is not sufficient.** A correct primitive layer does not protect against
   incorrect *composition* of those primitives in an experiment.

---

## 19. What must NOT be repeated

| Prohibition | Earned by |
|---|---|
| **Never write a coordinate transformation without stating the pixel convention it assumes.** | E-000.1 |
| **Never validate a formula against a restatement of itself.** Validate against the physical operation. | E-000.1 |
| **Never test numerical conditioning only at a small, convenient coordinate extent.** | E-000.2 |
| **Never accept a library's fill/interpolation default without asking what it means in this domain.** | E-000.3 |
| **Never downsample without a prefilter** — aliasing manufactures correspondences that do not exist. | E-000.4 |
| **Never offer both a forward and an inverse warp entry point.** Contract C5 removes the class of direction bugs by removing the choice. | Design decision, C5 |
| **Never let a resampling factor exist as a bare number.** It must be a `Transform` in the chain. | E-000.1 fix design |
| **Never treat "the geometry layer is verified" as "the experiment is verified."** | EXP-001 E-001.1 |

---

## 20. What the next stage should do

As recorded in `experiments/EXP-000/README.md`:

1. **EXP-001 — RootSIFT baseline against synthetic ground truth**, which validates the
   *matching* harness the same way EXP-000 validated the geometry harness.
2. That requires a feature-detection dependency (OpenCV or equivalent) — **the next
   decision**. Resolved as D-014: OpenCV enters for SIFT/RootSIFT only; `geometry/` stays
   OpenCV-free.

**What EXP-000 handed forward:**

1. **A trustworthy measuring instrument.** `endpoint_error` comparing *maps on a dense
   grid* is what makes EXP-001's central claim — that fit RMSE is misleading — meaningful.
2. **A correct resampling chain.** EXP-001's synthetic pairs are built by warping a height
   field; without contract C4 the ground truth itself would have been wrong by up to a
   pixel per resampling step.
3. **Degeneracy and conditioning reporting**, consumed directly by EXP-001's RANSAC.
4. **The regression habit** — a hazard gets a test that documents the hazard.

---

## 21. Open questions / unresolved risks

| # | Question | Why unresolved | What would resolve it |
|---|---|---|---|
| Q1 | Does relief displacement break global transform models on real terrain? (A6) | Derivation only; no real terrain with known geometry available | Real high-relief imagery with independent geometry, or a 3-D-aware synthetic generator |
| Q2 | Does OpenCV-independence actually prevent convention bugs? (A2) | No controlled comparison run; none planned | A deliberate A/B, which would cost more than it is worth. Likely to remain open permanently |
| Q3 | Does conditioning behaviour hold on real imagery at NAC extent? | No real data in the repository; ISSDC product listings are behind an authenticated endpoint | Access to real NAC frames |
| Q4 | What is the actual cost of a 4096² warp? | Extrapolated, never measured | One measurement — cheap, not yet taken |
| Q5 | How badly does conditioning degrade *without* Hartley normalisation? | Not recorded; only the with-Hartley arm exists | Re-run the sweep with normalisation disabled |
| Q6 | Is contract C4 still exact at scale factors up to 320×? | Tested only to 3× | Extend `scale_convention_c4` to the real ladder — belongs to EXP-004 |

---

## 22. Artefacts

| File | Contents |
|---|---|
| `experiments/EXP-000/metrics.json` | Every recorded measurement, with environment block |
| `experiments/EXP-000/README.md` | Stage-contemporary report and observations |
| `scripts/run_exp000.py` | The runner. No arguments; seed 20260824 hard-coded |
| `docs/coordinate_contract.md` | Normative conventions C1–C9 |
| `tests/test_geometry.py` | 70 tests, including five that pin the hazards in §9 |

**Cross-stage records:** `ERROR_LEDGER.md` (E-001…E-004) · `DECISION_LEDGER.md` (D-007) ·
`STAGE-INDEX.md` · `../STAGE_HISTORY.md`.
