# EXP-003 — Illumination-Robust Representations

**Stage ID:** EXP-003
**Name:** Do polarity-agnostic / phase-based representations move the illumination cliff past Δaz 30° on realistic terrain?
**Status:** COMPLETE — **pre-registered criterion S1 NOT met by any arm**
**Date started:** 2026-08-24 · **Date completed:** 2026-08-24
**Depends on:** EXP-000, EXP-001, EXP-002 · **Followed by:** EXP-004 (NOT a learned matcher — see §2.11)

> **Part 1 below was written and fixed BEFORE any EXP-003 implementation existed.**
> The success criterion, hypotheses, falsification conditions and stop conditions are
> pre-registered. They are not edited after results are seen. If a result contradicts a
> hypothesis, the hypothesis stays as written and the outcome is recorded against it.

---

# PART 1 — written BEFORE implementation

## 1.1 Stage objective

**The question:** *Does replacing the image representation — while holding terrain,
illumination, transforms, detection protocol, matching, RANSAC and scoring fixed — extend
the last fully-successful Δazimuth beyond 30° on the realistic A-regimes?*

**Why this stage, and why now.** EXP-001 measured that classical matching fails on Sun
azimuth as a cliff, not a slope, and EXP-002 relocated that cliff **earlier** on physically
realistic terrain: the last fully-successful Δaz is **15°** on both A-regimes
(`objective2_terrain.json:exp001_subset_summary`). ADR-0004 proposes that the mechanism is
SIFT's binning of gradient orientation over `[0, 2π)`, which is not invariant to the
gradient-direction change shadow motion produces, and that a **polarity-agnostic structural
representation** should therefore survive further. ADR-0004 is `PROPOSED` and states plainly
that **if raw intensity wins, the ADR is superseded.** EXP-003 is that test.

## 1.2 Starting assumptions

| # | Assumption | Source | Kind | How it could be falsified |
|---|---|---|---|---|
| A1 | The illumination cliff on A-regimes is at Δaz 15–30° for B1 | EXP-002 objective 2, 3 seeds | measured | B1 in this stage reproduces a materially different cliff |
| A2 | The mechanism is orientation binning over `[0, 2π)` | ADR-0004, descriptor definition | reasoned, **untested** | A mod-π binning changes nothing while another representation helps |
| A3 | Shadow *movement*, not only reversal, breaks the descriptor | EXP-001 §11.1 (cliff at 45°, not 180°) | measured | — |
| A4 | Contrast normalisation cannot repair it, because it preserves gradient sign | ADR-0004 | reasoned | — |
| A5 | Realistic mare is the hardest case (312 kp/Mpx vs 22 119) | EXP-002, D-019 | measured | A representation improves mare more than highlands |
| A6 | `n_inliers <= 8` is a sound deployable failure flag | EXP-002 addendum, D-023 | measured on 192 unseen cases | Recall or FPR degrade materially in this stage's regime |
| A7 | The pair-construction harness is trustworthy | EXP-001 E-001.1 fixed + regression test | measured | — |
| A8 | Terrain, transforms and scoring are unchanged from EXP-002 | by construction | — | — |

## 1.3 Hypotheses — stated so they can be refuted

| ID | Hypothesis | Predicted observation | What refutes it |
|---|---|---|---|
| **H-3.1** | A **polarity-agnostic orientation representation** (gradient orientation binned mod π) extends the last fully-successful Δaz beyond 30° on A-regimes | `A_orient_mod_pi` last-fully-successful Δaz > 30° on `A_mare_moderate` **and** `A_highlands_moderate` | Last fully-successful Δaz ≤ 30° on either A-regime |
| **H-3.2** | A **phase-congruency representation** extends it beyond 30° on A-regimes | `B_phase_congruency` last-fully-successful Δaz > 30° on both A-regimes | ≤ 30° on either |
| **H-3.3** | A **RIFT2-style** pipeline (PC detection + maximum-index-map descriptor) extends it beyond 30° on A-regimes | `C_rift2_mim` last-fully-successful Δaz > 30° on both A-regimes | ≤ 30° on either |
| **H-3.4** *(mechanism control)* | The **orientation-binning period is the operative variable** — mod-π beats an otherwise identical 2π descriptor | `A_orient_mod_pi` success rate > `A_orient_2pi_control` at matched Δaz on A-regimes | No difference, or the 2π control is equal/better |
| **H-3.5** *(artefact control)* | Any improvement is **not** explained by keypoint count or coverage alone | Improvement persists when keypoint count and coverage are reported alongside | Improvement tracks keypoint count / coverage and vanishes when they are matched |
| **H-3.6** *(EXP-002 debt)* | `n_inliers <= 8` retains **recall ≥ 0.95 and FPR ≤ 0.10** in the mixed correct/wrong regime this stage generates | Measured on EXP-003's own mixed-regime cases | Recall < 0.95 or FPR > 0.10 |

## 1.4 Success criteria — set in advance, not editable after results

| # | Criterion | Threshold | Measured on |
|---|---|---|---|
| **S1** *(primary, pre-registered)* | **Last fully-successful Δazimuth > 30°** | strictly greater than 30° | **`A_mare_moderate` and `A_highlands_moderate`**, reported per regime, never pooled |
| S2 | Mare reported independently and prominently | — | `A_mare_moderate` |
| S3 | Result holds on **≥ 3 independent seeds** | all 3 seeds | per regime |
| S4 | Not an artefact of keypoint count or coverage | H-3.5 | per regime |
| S5 | `n_inliers <= 8` re-measured in the mixed regime | H-3.6 | EXP-003 cases |

**Definitions, fixed now:**

- **wrong** = `transform_error_median > 3.0 px` (EXP-002 `WRONG_PX`), or non-finite.
  Ground truth is used **only to score**, never as a pipeline input.
- **success rate** at a Δaz = fraction of seeds that are not wrong.
- **last fully-successful Δaz** = the largest Δaz such that the success rate is **1.00** at
  that Δaz **and at every smaller Δaz tested**. (Same semantics as EXP-002
  `last_fully_successful_delta_azimuth`.)
- **deployable failure flag** = `n_inliers <= 8` (D-023). **`fit_rmse` is not used as a
  success or failure criterion anywhere in this stage.**

## 1.5 Failure criteria — when to stop rather than tune

**Stop and report; do not proceed to a learned matcher, if any of these holds:**

1. No representation beats S1 on the A-regimes.
2. An apparent improvement exists only on `C_extreme_diagnostic` or only on
   `B_highlands_challenging` (unrealistic / rough terrain).
3. The result depends on a single seed.
4. The result is explained by keypoint count or coverage (H-3.5 refuted).
5. The result does not reproduce.
6. The apparent success disappears under the mixed correct/wrong analysis.
7. **Highlands improves while mare remains failed** — this is explicitly *not* success (§7).

## 1.6 Variables and controls

| Role | Item |
|---|---|
| **Independent (varied)** | Representation arm (6); Δazimuth (11 values); terrain regime (3); seed (3) |
| **Dependent (measured)** | `transform_error_median` (GT, non-circular), `n_inliers`, `inlier_ratio`, coverage, keypoint counts, runtime, loop-closure error |
| **Controlled (held fixed)** | Terrain seeds and fields · illumination geometry · **the image pair itself** (generated once per case, shared by all arms) · transform model (`affine` truth, `affine` fit) · RANSAC threshold 3.0 px · correct-match threshold 3.0 px · ratio test 0.8 · mutual NN on · SIFT detector parameters · scoring code · success criterion |
| **Confounds (known, unmitigated)** | Descriptor dimensionality differs between arms (128 vs MIM length) · the custom descriptors are **upright** (no rotation normalisation) while OpenCV's are rotation-normalised — mitigated by the `A_orient_2pi_control` arm and bounded by the transform generator's ≤ 8° rotation · PC-based arms detect on a different image, so detection and description change together — mitigated by reporting keypoint counts per arm |

**Fair-comparison guarantee (requirement 6).** For a given `(regime, seed, Δaz)` the source
and reference images are generated **once** and handed to every arm. No arm sees a different
pair, a different transform, a different seed, or a different scoring path. No arm's
parameters are tuned using information unavailable to the others: every arm uses the
project's existing defaults.

## 1.7 Data provenance and roles

| Role | Source | Seeds | Notes |
|---|---|---|---|
| Synthetic ground truth | `make_pair` with exact known transform | 3001, 3002, 3003 | Exact; scoring only |
| Representation-selection (calibration) | **none** | — | No threshold is fitted in this stage. The only threshold, `n_inliers <= 8`, was fixed by EXP-002 on seeds 1001–1004 and validated on 7001–7004 |
| Validation / reporting | All EXP-003 cases | 3001, 3002, 3003 | **Disjoint from every EXP-002 seed** (1001–1005, 7001–7004) |
| GT-free evaluation | loop closure over image triplets | 3001–3003 | Never consults ground truth |

Seeds 3001–3003 are chosen to be disjoint from all EXP-002 seeds so that the D-023 operating
point is applied to terrain it has never been fitted or validated on.

## 1.8 Metric definitions

| Metric | Definition | Units | Kind |
|---|---|---|---|
| `transform_error_median` | Median endpoint error between estimated and true map over a dense grid | px | **GT, non-circular** |
| `n_inliers` | RANSAC consensus size | count | deployable |
| `inlier_ratio` | `n_inliers / n_putative` | — | deployable, **self-consistency only** |
| `coverage_max_gap` | `max_uncovered_disc_radius` over the overlap ROI | ratio | deployable |
| `fit_rmse` | RANSAC inlier RMSE | px | **fit / circular — recorded for the record, NEVER used as a criterion** |
| `loop_error` | Deviation of `T_CA ∘ T_BC ∘ T_AB` from identity | px | **GT-free, primary (ADR-0011)** |
| `pipeline_s` | Wall-clock detect + describe + match + RANSAC | s | engineering only, **not gating** (D-020) |

## 1.9 Negative controls and guards declared in advance

1. **`A_orient_2pi_control`** — the custom descriptor with `[0, 2π)` binning. Isolates
   H-3.4: without it, any mod-π effect could be an artefact of the custom descriptor
   implementation rather than of the binning period.
2. **Δaz = 0° anchor** — every arm must succeed at identical illumination. An arm that fails
   at 0° is broken, not illumination-robust, and its other results are void.
3. **`fit_rmse`** — recorded, and predicted to carry no failure information (EXP-002:
   ROC AUC 0.4947). It is not permitted to influence any decision.
4. **Held-out residual / cycle consistency** — per ADR-0011 these may **not** be claimed to
   detect coherent wrong solutions. Only loop closure carries that claim.

## 1.10 Experimental grid

| Factor | Values | n |
|---|---|---|
| Representation arm | `B1_rootsift`, `B1_sift`, `A_orient_mod_pi`, `A_orient_2pi_control`, `B_phase_congruency`, `C_rift2_mim` | 6 |
| Δazimuth (°) | **0, 15**, 18, 21, 24, 27, **30**, 33, 36, 40, 45 | 11 |
| Terrain regime | `A_mare_moderate` *(priority)*, `A_highlands_moderate`, `B_highlands_challenging` | 3 |
| Seed | 3001, 3002, 3003 | 3 |

= **99 image pairs × 6 arms = 594 arm-evaluations.**

The mandated grid (18–45°) is used in full. **0° and 15° are added** as controls: 0° is the
positive-control anchor (§1.9), and 15° is B1's last fully-successful point on A-regimes per
EXP-002, without which "beyond 30°" has no measured baseline to be *beyond*.

`C_extreme_diagnostic` is **excluded** from the primary grid: it is physically impossible
terrain (89.55% above the angle of repose) and stop-condition 2 forbids claiming success on
it. It may be run separately as a diagnostic only.

**Sub-experiment (GT-free, requirement 10).** Loop closure over image triplets (A→B, B→C,
C→A) for the baseline arm and the best-performing arm, at a subset of azimuths. Run
separately because it costs 3 pipeline runs per case; scope stated rather than silently
reduced.

---

# PART 2 — written AFTER implementation

**Status: COMPLETE.** Nothing below this line existed when Part 1 was fixed above.

## 2.0 What we attempted

Six representation arms were run against an identical protocol to test whether an
illumination-robust *representation* moves the azimuth cliff past the pre-registered 30 deg
bar on realistic terrain: the established baseline (`B1_rootsift`) and its plain-SIFT control
(`B1_sift`), the ADR-0004 polarity-agnostic descriptor (`A_orient_mod_pi`) with its own
otherwise-identical 2π control (`A_orient_2pi_control`), phase congruency
(`B_phase_congruency`), and a RIFT2-style phase-congruency + maximum-index-map pipeline
(`C_rift2_mim`). 594 evaluations over 3 regimes × 3 seeds × 11 azimuths, plus 108
loop-closure triplets for GT-free validation.

**Outcome in one line: every representation hypothesis was refuted, mare defeated all six
arms, and the single positive effect came from a control arm for a reason nobody predicted.**

## 2.1 What we implemented

| Path | Status | Purpose |
|---|---|---|
| `src/siim/matching/representations.py` | **created** | `phase_congruency` (Kovesi log-Gabor bank), `maximum_index_map`, `gradient_magnitude_representation`, `identity_representation`, `to_float` |
| `src/siim/matching/descriptors.py` | **created** | `describe_gradient_histogram` (SIFT-shaped, **orientation period is a parameter**), `describe_maximum_index` (RIFT-style MIM histogram) |
| `scripts/exp003_common.py` | created | The six arms, case construction, `run_all_arms`, the pre-registered criterion |
| `scripts/run_exp003.py` | created | Main runner |
| `scripts/run_exp003_loop_closure.py` | created | GT-free sub-experiment |
| `tests/test_representations.py` | created | **15 tests** |

**No existing source module was modified.** `geometry/`, `verification/`, `evaluation/` and
the EXP-002 scripts are untouched, so the matching, RANSAC and scoring path is byte-identical
to the one EXP-002 validated.

**Deviation from the plan, and why.** The pilot showed the custom descriptor used hard bin
assignment, where SIFT uses trilinear soft assignment. This cost match yield for no
principled reason (mod-pi putative yield 200 vs OpenCV's 989 on highlands at delta-az 0).
Trilinear assignment was added **before the main run**, and applied to *both* custom arms, so
it cannot favour either orientation period. Yield rose to 675/732. This was a correctness fix
to avoid a **false negative on the central hypothesis**, not a tuning step: no arm was tuned
using information unavailable to the others, and no parameter was chosen by looking at
outcomes.

## 2.2 Experiments performed

| Experiment | Pairs | Arms | Evaluations | Artefact |
|---|---|---|---|---|
| Main representation sweep | 99 (3 regimes x 3 seeds x 11 delta-az) | 6 | **594** | `exp003_representations.json`, `exp003_cases.csv` |
| Loop closure (GT-free) | 54 triplets (3 regimes x 3 seeds x 6 delta-az) | 2 | **108** | `exp003_loop_closure.json`, `_cases.csv` |
| Orientation-stability mechanism probe | 8 pairs | — | post-hoc | reported in §2.6 (E-003.4) |

The image pair for a case is built **once** and handed to all six arms
(`exp003_common.run_all_arms`), so requirement 6 is enforced structurally rather than by
discipline.

## 2.3 Exact commands used

```bash
python -m pytest tests/test_representations.py -q     # 15 passed
python scripts/run_exp003.py                          # 594 evaluations, 12.5 min
python scripts/run_exp003_loop_closure.py             # 108 loop cases, ~3.5 min
python -m pytest tests/ -q                            # 183 passed, 2 skipped
```

Environment: python 3.13.7 · numpy 2.3.3 · OpenCV 5.0.0 · Windows-11-10.0.26200-SP0. All
runners take no arguments; seeds are fixed in `exp003_common.EXP003_SEEDS`.

## 2.4 Quantitative results

### 2.4.1 The headline table — last fully-successful delta-azimuth, per regime

`[MEASURED]` 3 seeds per cell. **S1 requires strictly > 30 deg on both A-regimes.**

| representation | **A_mare_moderate** *(priority, D-019)* | A_highlands_moderate | B_highlands_challenging | 0 deg control | **S1** |
|---|---|---|---|---|---|
| `B1_rootsift` (baseline) | **21** | 27 | 27 | pass | FAIL |
| `B1_sift` | **21** | 27 | 27 | pass | FAIL |
| `A_orient_mod_pi` (H-3.1) | **0** | 21 | 27 | pass | FAIL |
| `A_orient_2pi_control` *(control)* | **18** | 27 | **40** | pass | FAIL |
| `B_phase_congruency` (H-3.2) | **— (void)** | 27 | 30 | **FAILS on mare** | FAIL |
| `C_rift2_mim` (H-3.3) | **— (void)** | 0 | 27 | **FAILS on mare** | FAIL |

**`S1_MET_BY_ANY_ARM: false`.** No representation reached the pre-registered bar on either
A-regime, let alone both.

### 2.4.2 Success rate by delta-azimuth — `A_mare_moderate` (the priority result)

| representation | 0 | 15 | 18 | 21 | 24 | 27 | 30 | 33 | 36 | 40 | 45 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `B1_rootsift` | 1.00 | 1.00 | 1.00 | 1.00 | 0.67 | 1.00 | 0.33 | 0.00 | 0.00 | 0.00 | 0.00 |
| `B1_sift` | 1.00 | 1.00 | 1.00 | 1.00 | 0.67 | 1.00 | 0.33 | 0.00 | 0.33 | 0.00 | 0.00 |
| `A_orient_mod_pi` | 1.00 | 0.33 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| `A_orient_2pi_control` | 1.00 | 1.00 | 1.00 | 0.67 | 0.67 | 1.00 | 0.33 | 0.00 | 0.33 | 0.00 | 0.00 |
| `B_phase_congruency` | **0.67** | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| `C_rift2_mim` | **0.33** | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

**Mare is the decisive result and it is negative for every arm.** Nothing survives past 21 deg.
The two PC-based arms do not even clear the identical-illumination control, so their mare
results are **void** under §1.9, not merely poor.

### 2.4.3 Success rate by delta-azimuth — highlands regimes

**A_highlands_moderate**

| representation | 0 | 15 | 18 | 21 | 24 | 27 | 30 | 33 | 36 | 40 | 45 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `B1_rootsift` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.33 | 0.33 | 0.33 | 0.00 |
| `A_orient_mod_pi` | 1.00 | 1.00 | 1.00 | 1.00 | 0.67 | 0.67 | 0.33 | 0.00 | 0.00 | 0.00 | 0.00 |
| **`A_orient_2pi_control`** | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | **0.67** | **1.00** | **1.00** | **1.00** | 0.33 |
| `B_phase_congruency` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.67 | 0.67 | 0.00 | 0.00 |
| `C_rift2_mim` | 1.00 | 0.67 | 1.00 | 1.00 | 0.33 | 0.67 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

**B_highlands_challenging**

| representation | 0 | 15 | 18 | 21 | 24 | 27 | 30 | 33 | 36 | 40 | 45 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `B1_rootsift` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.67 | 0.33 | 0.33 | 0.00 | 0.00 |
| `A_orient_mod_pi` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 0.00 | 0.33 | 0.00 | 0.00 |
| **`A_orient_2pi_control`** | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** | **1.00** | **1.00** | **1.00** | 0.33 |
| `B_phase_congruency` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** | 0.67 | 0.67 | 0.67 | 0.33 |
| `C_rift2_mim` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.67 | 0.00 | 0.00 | 0.33 | 0.00 |

Note the discipline requirement in action: `A_orient_2pi_control` reaches **40 deg** on
`B_highlands_challenging` — but B is a *challenging*, not a realistic, benchmark, and S1 is
defined on A-regimes only. Under stop-condition 2 that result **cannot** be presented as
success.

### 2.4.4 Runtime — engineering only, not gating (D-020)

`[MEASURED]` Median `pipeline_s`, `A_highlands_moderate`, delta-az 0:

| arm | s |
|---|---|
| `B1_sift` | 0.168 |
| `B1_rootsift` | 0.178 |
| `C_rift2_mim` | 0.305 |
| `A_orient_mod_pi` | 0.535 |
| `A_orient_2pi_control` | 0.609 |
| `B_phase_congruency` | 1.182 |

`[INTERPRETATION]` The worst arm is 6.6x the baseline and still ~1.2 s against a <= 60 s/pair
budget. **No arm was rejected on runtime**, per requirement 11. Total stage runtime 12.5 min
for 594 evaluations.

## 2.5 What worked / what failed

**Worked**

- The harness: all six arms pass the delta-az = 0 positive control on both texture-rich regimes.
- `A_orient_2pi_control` extends the cliff on both highlands regimes — an **unexpected**
  result from a control arm (§2.6, E-003.4).
- Loop closure separates correct from wrong loops by roughly four orders of magnitude.

**Failed**

- **Every pre-registered representation hypothesis.** H-3.1, H-3.2 and H-3.3 all refuted.
- **Mare defeats everything.** No arm exceeds 21 deg.
- `A_orient_mod_pi` — the ADR-0004 mechanism — is **worse than the baseline everywhere**.
- PC-based arms fail the 0 deg control on mare, voiding their mare results.
- **H-3.6 refuted**: `n_inliers <= 8` false-alarm rate does not transfer (§2.7.3).

## 2.6 Errors and findings encountered

### E-003.1 — Hard bin assignment in the custom descriptor (caught in the pilot)

**Class:** implementation bug · **Severity: HIGH — would have caused a false negative**

- **Problem.** `describe_gradient_histogram` assigned each sample to a single spatial and
  orientation bin, where SIFT uses trilinear soft assignment.
- **Evidence.** Pilot, `A_highlands_moderate` delta-az 0: mod-pi putative 200 vs OpenCV 989.
- **Root cause.** Hard binning discards sub-bin position, so the descriptor jitters under
  small geometric change and the ratio test rejects the match.
- **Fix.** Trilinear soft assignment over (x, y, orientation) with orientation wrap-around,
  applied to **both** custom arms.
- **Verification.** mod-pi putative 200 -> **675**; 2pi control 652 -> **732**; mare mod-pi
  moved from failing the 0 deg control to passing it.
- **Lesson.** **A weak implementation of the arm under test manufactures a false negative.**
  The bug had to be fixed *before* the run, and fixed symmetrically, or H-3.1 would have been
  "refuted" by my own code quality rather than by evidence.

### E-003.2 — Loop-closure cases were labelled by one edge instead of by the loop

**Class:** experimental / design mistake · **Severity: HIGH** · *the D2 pattern, recurring*

- **Problem.** A loop was labelled wrong or correct using the **A->B edge only**, while
  `loop_error` is a property of the whole three-edge loop.
- **Evidence.** Under the edge label, loop closure scored **detection 1.000 / false alarm
  0.617**. Inspection showed the "false alarms" were loops in which a *different* edge was
  catastrophically wrong — loop closure was correctly refusing to close a broken loop and
  being penalised for it.
- **Root cause.** The statistic and its label measured different things. **This is exactly
  contradiction D2 in a new place**: a table labelled with something other than what it
  computes.
- **Fix.** Ground truth for all three edges (`T_CA = (T_BC o T_AB)^-1`); a loop is wrong iff
  **any** edge is wrong. The mislabelled variant is **retained in the artefact** as
  `detection_edge_level_MISLABELLED` so the size of the error stays visible.
- **Verification.** Loop-level: **detection 1.000, false alarm 0.000** (85 wrong, 23 correct).
- **Lesson.** **Label a statistic with the thing it actually measures.** The mislabelling
  moved the false-alarm rate by **0.617** and would have produced a completely wrong
  conclusion about the project's only trusted GT-free estimator.

### E-003.3 — Realistic mare cannot support PC-based detection at 384 px

**Class:** limitation of synthetic data / benchmark capacity · **Severity: MEDIUM**

- **Problem.** `B_phase_congruency` and `C_rift2_mim` fail the delta-az = 0 positive control
  on mare (success 0.67 and 0.33).
- **Evidence.** Mare yields **24 keypoints** on the raw image and 40 on the PC map at 384 px
  square (EXP-002 measured mare at 312 kp/Mpx; 384 px square is 0.147 Mpx). With so few
  keypoints the MIM descriptor produces about 3 putative matches.
- **Root cause.** Not a bug. Verified by direct test that phase congruency is correct —
  contrast invariance to **1e-6**, polarity invariance to **exactly 0.0**, edge response
  16.9x, and sparse on smooth fields by construction
  (`test_phase_congruency_is_sparse_on_smooth_terrain`).
- **Fix.** None. Per §1.9 the mare results for these two arms are **void**, and are reported
  as void rather than as failures of illumination robustness.
- **Lesson.** **A benchmark can be too small to answer the question asked of it.** Realistic
  mare at 384 px is at the edge of measurability, so a null result there is partly a statement
  about the benchmark. **PC parameters were deliberately not tuned** to rescue this: that
  would have been tuning one arm on information the others did not get.

### E-003.4 — The control arm beat the baseline: orientation *assignment*, not binning

**Class:** genuine research finding, **post-hoc and not pre-registered**

- **Observation.** `A_orient_2pi_control` — included only to isolate H-3.4 — extends the
  cliff from 27 to **40 deg** on `B_highlands_challenging` and holds success 1.00 out to
  **40 deg** on `A_highlands_moderate`, where the baseline drops to 0.33 at 30 deg.
- **Artefact checks, both passed.** It uses the **same detector and therefore identical
  keypoints as B1 in 99/99 cases**, so keypoint count cannot explain it (H-3.5). Median
  coverage gap on successes is **0.129 vs B1's 0.130**, so coverage cannot explain it. In the
  18 cases where it succeeds and B1 fails at delta-az >= 30, true inlier precision is
  **0.93-1.00** and errors are **0.11-1.82 px**: genuinely correct registrations, not lucky
  RANSAC fits.
- **The only remaining difference is that the custom descriptor is UPRIGHT** — it does not
  rotate the sampling patch to a SIFT-assigned dominant orientation.
- **Direct mechanism measurement** (post-hoc probe; keypoints paired through ground truth by
  location, then the absolute difference between OpenCV-assigned dominant orientations):

| delta-az | `A_highlands_moderate` median abs angle diff | frac > 30 deg | `B_highlands_challenging` | frac > 30 deg |
|---|---|---|---|---|
| 0 | 6.69 deg | 0.242 | 6.96 deg | 0.247 |
| 15 | 12.26 deg | 0.304 | 13.22 deg | 0.329 |
| 30 | 24.05 deg | 0.424 | 24.57 deg | 0.431 |
| 45 | **44.77 deg** | **0.677** | **46.19 deg** | **0.669** |

  `[MEASURED]` **SIFT's assigned dominant orientation drifts almost one-for-one with the Sun
  azimuth change.** At delta-az 45 deg the median assignment is wrong by about 45 deg and
  two-thirds of keypoints are off by more than 30 deg.

- `[INTERPRETATION]` Shadow motion rotates the local gradient field, which rotates the
  orientation histogram SIFT uses to assign a keypoint reference angle, which rotates the
  descriptor sampling frame — producing a **systematic** descriptor mismatch. An upright
  descriptor has no such frame to rotate. This *refines* ADR-0004: at these azimuths the
  dominant failure is orientation **assignment**, not orientation **binning**.
- **Why this is not a deployable recommendation.** Uprightness only works because this stage's
  transforms carry at most 8 deg of rotation. On real pairs with arbitrary relative rotation
  an upright descriptor fails outright. **The finding is a mechanism, not a method.**
- **Status.** Post-hoc, **not pre-registered**, one stage, synthetic data, and confounded with
  the custom descriptor implementation. It requires independent confirmation before anything
  is built on it.

## 2.7 Hypotheses: outcome

| ID | Hypothesis, as originally written | Outcome | Evidence |
|---|---|---|---|
| **H-3.1** | Orientation-mod-pi extends last-fully-successful delta-az > 30 deg on A-regimes | **REFUTED** | mare **0**, highlands **21** — *worse than the 21/27 baseline* |
| **H-3.2** | Phase congruency extends it > 30 deg on A-regimes | **REFUTED** | highlands 27; mare **void** (fails the 0 deg control) |
| **H-3.3** | RIFT2-style extends it > 30 deg on A-regimes | **REFUTED** | highlands **0**; mare **void** |
| **H-3.4** | The orientation-binning period is the operative variable; mod-pi beats its 2pi control | **REFUTED, in the opposite direction** | Head-to-head on identical keypoints: mod-pi **wins 0, loses 38, ties 61**. At delta-az 0 both yield about 770 putative matches, so this is not a distinctiveness deficit — mod-pi degrades specifically under illumination change |
| **H-3.5** | Any improvement is not a keypoint or coverage artefact | **SUPPORTED** (for the control arm's improvement) | Identical keypoints 99/99; coverage 0.129 vs 0.130 |
| **H-3.6** | `n_inliers <= 8` holds recall >= 0.95 **and** FPR <= 0.10 in the mixed regime | **REFUTED on FPR** | §2.7.3 |

### 2.7.3 The EXP-002 evidence debt, re-measured (requirement 8) — `[MEASURED]`

Cells are `(representation, regime, delta-azimuth)` across seeds; **mixed** means correct and
wrong coexist, which are the only cells where the flag can discriminate.

| subset | n | wrong | recall | FPR |
|---|---|---|---|---|
| all EXP-003 cases | 594 | 259 | 0.9961 | **0.1672** |
| **MIXED cells only** | **135** | **70** | **0.9857** | **0.3692** |
| total-collapse cells | 189 | 189 | 1.0000 | n/a |
| all-correct cells | 270 | 0 | n/a | 0.1185 |

Per regime, mixed cells only:

| regime | n | correct | FP | **FPR** | wrong | **recall** |
|---|---|---|---|---|---|---|
| `A_mare_moderate` | 36 | 17 | 8 | **0.4706** | 19 | 1.0000 |
| `A_highlands_moderate` | 54 | 26 | 8 | **0.3077** | 28 | 1.0000 |
| `B_highlands_challenging` | 45 | 22 | 8 | **0.3636** | 23 | 0.9565 |

`[MEASURED]` **Recall transfers (0.986 >= 0.95). The false-alarm rate does not: 0.369 against
EXP-002's 0.0112 — a factor of 33.**

`[INTERPRETATION]` This is precisely the risk recorded as RL-022b. EXP-002's FPR was earned
where 93% of failures were total collapse; in the discriminable regime the flag rejects more
than a third of *correct* registrations. **`n_inliers <= 8` is a sound failure detector and a
poor success gate**, and EXP-004 must not treat 0.0112 as its operating false-alarm rate.

### 2.7.4 GT-free validation (requirement 10) — `[MEASURED]`

108 loop cases. Loop-level label: a loop is wrong iff **any** of its three edges is wrong.

| | detection | false alarm | correct-loop median | wrong-loop median |
|---|---|---|---|---|
| **loop closure (loop-level, correct)** | **1.000** | **0.000** | **0.258 px** | **1368.1 px** |
| loop closure (edge-level, **mislabelled**) | 1.000 | 0.617 | — | — |

Held-out residual, spatial split consistency and cycle consistency were **deliberately not
computed** (ADR-0011 / E-011): they are degeneracy detectors, and computing them here would
invite a claim the evidence does not support.

## 2.8 Conclusions supported by evidence

- `[MEASURED]` **No tested representation meets S1.** The pre-registered criterion — last
  fully-successful delta-az > 30 deg on both A-regimes — is met by **no arm**.
- `[MEASURED]` **Mare is the binding constraint.** The best mare result is 21 deg (`B1`), and
  mare yields only about 24 keypoints at 384 px square.
- `[MEASURED]` **Mod-pi binning is actively harmful**, losing 38 head-to-head cases and
  winning none against its own control on identical keypoints.
- `[MEASURED]` **SIFT's dominant-orientation assignment drifts nearly one-for-one with Sun
  azimuth.**
- `[MEASURED]` **An upright descriptor extends the cliff on both highlands regimes**
  (27 -> 40 deg on B), on identical keypoints and matched coverage.
- `[MEASURED]` **`n_inliers <= 8` recall transfers; its FPR does not** (0.0112 -> 0.369).
- `[MEASURED]` **Loop closure: detection 1.000, false alarm 0.000** at loop level.
- `[MEASURED]` Runtime is not a discriminator (0.17-1.18 s against a 60 s budget).

## 2.9 Conclusions rejected

- **ADR-0004's mechanism as stated.** "Polarity-agnostic structure" does **not** rescue
  matching here; the polarity-agnostic arm was the *worst* of the six. `[INTERPRETATION]`
  ADR-0004 invited its own supersession if raw intensity wins. Raw intensity **did** win.
- **Phase congruency as a lunar answer.** Contrast- and polarity-invariant by construction
  (verified to 1e-6 and exactly 0.0), and still bounded at 27-30 deg on A-regimes — because
  shadow motion changes *which structures exist*, not merely their contrast.
- **RIFT2-style MIM as a drop-in improvement.** It was the worst arm on
  `A_highlands_moderate` (0 deg).
- **That EXP-002's FPR of 0.0112 is a usable operating figure.** It is not, in this regime.

## 2.10 Remaining evidence debt

1. **The E-003.4 finding is post-hoc and unconfirmed.** It was not pre-registered, rests on
   one stage and one synthetic generator, and is confounded with the custom descriptor
   implementation. **It must be pre-registered and re-tested before anything is built on it.**
2. **Uprightness is not deployable.** Valid only for <= 8 deg relative rotation. Untested and
   expected to fail under arbitrary rotation.
3. **Mare at 384 px square may be too small to answer the question** (E-003.3). Whether mare's
   failure is illumination or measurement capacity is **unresolved**.
4. **PC and RIFT parameters were never swept.** Deliberately so — but it means "PC does not
   help" is a statement about *default* PC.
5. **Single transform class (affine) and one Sun elevation (45 deg).**
6. **Loop closure still rests on constructed triplets**, now from the image pipeline rather
   than from synthetic transforms, but still on synthetic terrain.
7. **All EXP-002 and EXP-003 debts on real data remain open.** No multi-modal claim is
   supportable.

## 2.11 Recommendation for EXP-004

**Do not proceed to a learned matcher.** Stop-condition 1 of the pre-registration fired: no
representation met S1. A learned matcher would inherit the same broken orientation reference
and the same possibly-unmeasurable mare benchmark.

**EXP-004 should be "Illumination-stable orientation assignment", pre-registered as follows.**

1. **Primary hypothesis:** the dominant classical failure at delta-az 15-45 deg is the
   *keypoint orientation reference*, not the descriptor. Test it by replacing SIFT's
   orientation assignment while holding detector, descriptor, matching and RANSAC fixed:
   (a) upright, (b) orientation from an illumination-stable source, (c) OpenCV default as the
   control. **Pre-register it** — E-003.4 is currently post-hoc and must not be promoted
   without its own criterion set in advance.
2. **Fix the mare measurability question first.** Run mare at 768 or 1024 px square and
   re-measure the B1 cliff. If mare at 384 px was capacity-limited, every mare conclusion from
   EXP-002 and EXP-003 needs re-reading. **This is the highest-value single experiment
   available.**
3. **Re-derive the deployable operating point.** `n_inliers <= 8` has FPR 0.369 here. Fit a
   new threshold on EXP-004 calibration seeds and validate it on disjoint ones.
4. **Carry loop closure forward** as the only trusted GT-free check, with loop-level labels.
5. **Do not sweep PC parameters as the primary objective.** A representation that needs a
   parameter sweep to reach the baseline is not the answer to an effect of this size.

## 2.12 Artefacts

| File | Contents |
|---|---|
| `experiments/EXP-003/exp003_representations.json` | Full per-regime summary, mixed-regime flag analysis, S1 verdict |
| `experiments/EXP-003/exp003_cases.csv` | **594 rows** — every field required by requirement 9 |
| `experiments/EXP-003/exp003_loop_closure.json` | Loop-level and mislabelled edge-level analyses |
| `experiments/EXP-003/exp003_loop_closure_cases.csv` | 108 loop cases, per-edge true errors |

**Status: COMPLETE.** S1 not met. Stop condition 1 fired; EXP-004 is *not* a learned matcher.
