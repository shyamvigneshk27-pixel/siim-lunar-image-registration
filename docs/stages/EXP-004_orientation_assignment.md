# EXP-004 — Orientation Assignment under Illumination vs True Rotation

**Stage ID:** EXP-004
**Name:** Is illumination-induced failure driven by dominant-orientation *assignment* rather than descriptor binning — and can it be fixed without destroying true rotation invariance?
**Status:** PLANNED — Part 1 frozen, no implementation exists
**Date started:** 2026-08-24 · **Date completed:** —
**Depends on:** EXP-003 (E-003.4, D-024) · **Followed by:** TBD

**Classification: RESEARCH-CRITICAL.** Not demo-blocking. The Sept 2 demo proceeds in
parallel on the EXP-003 baseline and does not wait for this result. If EXP-004 produces a
validated improvement before freeze (2026-09-01) it may be adopted; if not, the demo ships
the baseline and reports EXP-004 honestly as in progress or refuted.

**Hard timebox: 48 hours from 2026-08-24.** At expiry the stage is written up with whatever
evidence exists — including "inconclusive" — and the team moves to demo work. Extending the
timebox requires an explicit decision recorded here, not silent drift.

> **Part 1 below is written and fixed BEFORE any EXP-004 implementation exists.**
> Success criteria, hypotheses, metrics, grid, seeds and stop conditions are pre-registered
> and are not edited after results are seen.

---

# PART 1 — written BEFORE implementation

## 1.1 Research objective

**The question:** *Is the classical illumination cliff caused substantially by instability in
the keypoint's assigned dominant orientation — and if so, can orientation be stabilised
against illumination WITHOUT losing invariance to true geometric rotation?*

The second clause is not optional. EXP-003's `A_orient_2pi_control` bought its improvement
by being **upright** — it has no orientation assignment to destabilise. That is not a method:
it survives only because EXP-003's transforms carried ≤ 8° rotation. An arm that "wins" by
discarding rotation invariance has moved the failure, not fixed it.

## 1.2 Demo objective

None directly. If an arm passes both criteria, it becomes a candidate representation for the
demo pipeline **after** validation on unseen seeds — not before.

## 1.3 Origin, and why this is not yet a result

EXP-003 §2.6 E-003.4 recorded a **post-hoc** observation: OpenCV SIFT's assigned dominant
orientation drifted with Sun azimuth at roughly 1:1 (median |Δangle| 6.69° → 44.77° as Δaz
went 0° → 45°; 67% of keypoints off by >30° at 45°). It was measured on 8 pairs, in two
regimes, with keypoints paired through ground truth by location.

That observation is **not pre-registered, not seed-replicated, and confounded**: the probe
compared orientations across pairs that also differ by a small geometric rotation (±8° from
the transform generator), so part of the measured drift is real rotation, not illumination.
D-024 holds it as a pre-registration target rather than an accepted decision. **EXP-004 is
that pre-registration.** Until it completes, no orientation claim may be made.

## 1.4 Starting assumptions

| # | Assumption | Source | Kind | How it could be falsified |
|---|---|---|---|---|
| A1 | The A-regime cliff for B1 is at Δaz 21–27° | EXP-003, 3 seeds | measured | B1 reproduces a materially different cliff here |
| A2 | Orientation assignment drifts with Sun azimuth | EXP-003 E-003.4 | **post-hoc, confounded** | Drift vanishes once true rotation is separated out |
| A3 | Uprightness fails under true rotation | reasoned, untested | reasoned | The upright arm survives large true rotation |
| A4 | A *global* rotation estimate is illumination-robust because it aggregates over the whole image | reasoned | **untested** | Global estimate degrades with Δaz as fast as per-keypoint assignment |
| A5 | The structure tensor is less polarity-sensitive than a gradient-orientation histogram | analytic — it is quadratic in gradient, so ∇I and −∇I give the same tensor | reasoned | Structure-tensor orientation drifts as much as SIFT's |
| A6 | Terrain, transforms, matching, RANSAC and scoring are unchanged from EXP-002/003 | by construction | — | — |

## 1.5 Hypotheses — stated so they can be refuted

| ID | Hypothesis | Predicted observation | What refutes it |
|---|---|---|---|
| **H-4.1** *(mechanism, the central one)* | Orientation-assignment error grows with **Δazimuth** independently of true rotation | With true rotation held at 0°, median assignment error rises monotonically with Δaz and exceeds 30° by Δaz 45° | Assignment error is flat in Δaz once rotation is controlled — which would mean E-003.4 was a rotation artefact |
| **H-4.2** *(specificity)* | The drift is **illumination-specific**, not a generic instability: at Δaz 0° the assignment error stays near its noise floor across all true rotations | Assignment error at Δaz 0° is ≈ constant in true rotation | Error grows with true rotation too, i.e. the estimator is simply noisy |
| **H-4.3** *(the cure)* | An illumination-stable orientation source extends the last fully-successful Δaz beyond 30° on A-regimes | Some arm meets S1 | No arm meets S1 |
| **H-4.4** *(the trap — pre-registered because we expect it)* | `upright` wins on Δaz but **loses under true rotation** | `upright` meets S1 and fails S2 | `upright` meets both |
| **H-4.5** *(no free lunch)* | An arm meeting S1 does so **without** sacrificing rotation invariance | Some arm meets S1 **and** S2 | Every arm meeting S1 fails S2 |
| **H-4.6** *(threshold transfer, carrying EXP-003 forward)* | `n_inliers <= 8` holds recall ≥ 0.95 and FPR ≤ 0.10 in EXP-004's mixed regime | measured on EXP-004 mixed cells | recall < 0.95 or FPR > 0.10 |

## 1.6 Success criteria — set in advance, BOTH required

| # | Criterion | Threshold | Measured on |
|---|---|---|---|
| **S1** *(illumination)* | Last fully-successful Δazimuth **strictly > 30°** | > 30° | `A_mare_moderate` **and** `A_highlands_moderate`, at true rotation 0°, per regime, never pooled |
| **S2** *(rotation, non-negotiable)* | Success rate across true rotation ∈ {0, 15, 45, 90, 180}° at Δaz 0° is **≥ the B1 baseline's at every rotation** | no regression vs baseline | same regimes |
| **S3** | Holds on **≥ 3 validation seeds**, disjoint from calibration | all 3 | per regime |
| **S4** | Not a keypoint-count or coverage artefact | reported alongside | per regime |
| **S5** | `n_inliers <= 8` re-measured in-regime | H-4.6 | EXP-004 mixed cells |

**An arm that meets S1 but fails S2 is recorded as REFUTED for deployment**, with its S1
result preserved. That outcome is explicitly anticipated for `upright` (H-4.4) and is a
result, not a disappointment.

**Definitions, fixed now:** `wrong` = `transform_error_median > 3.0 px` or non-finite ·
success rate = fraction of seeds not wrong · last fully-successful Δaz = largest Δaz whose
success rate is 1.00 at that Δaz and every smaller Δaz (EXP-002/003 semantics) ·
deployable failure flag = `n_inliers <= 8` (D-023) · **`fit_rmse` is never a criterion.**

## 1.7 Failure / stop conditions

**Stop, write up, and move to demo work if any holds:**

1. **48-hour timebox expires** — unconditional.
2. **H-4.1 refuted**: assignment error is flat in Δaz once rotation is controlled. Then
   E-003.4 was a rotation artefact, the orientation programme is dead, and D-024 is rejected.
3. No arm meets S1.
4. Every arm meeting S1 fails S2 (H-4.5 refuted) — orientation stabilisation costs rotation
   invariance, and the approach is not deployable.
5. Improvement is explained by keypoint count or coverage.
6. Result rests on a single seed or does not reproduce on validation seeds.

**Explicitly out of scope:** learned matchers (§21), real data (separate track), scale
sweeps, elevation sweeps. EXP-004 answers one question.

## 1.8 Method — arms

Every arm shares the detector (OpenCV SIFT on raw intensity) and therefore **identical
keypoint locations and scales**. Only the *orientation assigned to each keypoint* changes,
then the same descriptor is computed in that frame. This isolates orientation assignment as
the single independent variable — the confound EXP-003 could not remove.

| Arm | Orientation source | Rationale |
|---|---|---|
| `B1_rootsift` | OpenCV SIFT's own dominant orientation | Established baseline (unchanged code path) |
| `sift_orient_custom` | Gradient-orientation histogram, our implementation | **Control**: isolates our descriptor from our orientation. Without it, an effect could be either |
| `upright` | none (0° for every keypoint) | The EXP-003 post-hoc winner. Expected to fail S2 (H-4.4) |
| `structure_tensor` | Principal direction of the local second-moment matrix, mod π | Quadratic in gradient → invariant to polarity flip by construction (A5) |
| `global_rotation` | **One** image-pair-level rotation estimate (log-polar / Fourier-Mellin phase correlation), applied to every keypoint | **The candidate cure.** Aggregating over the whole image should resist local shadow motion while still recovering true rotation |

`global_rotation` is the scientifically interesting arm: it decouples *recovering the true
relative rotation* from *assigning a per-keypoint reference angle*, which is the distinction
§4 asks for.

## 1.9 Method — the factorial that separates illumination from rotation

The core design. A one-dimensional Δaz sweep **cannot** separate A from B, which is why
E-003.4 is confounded.

| Factor | Values | n |
|---|---|---|
| **Δazimuth** (illumination) | 0, 15, 24, 30, 36, 45° | 6 |
| **True geometric rotation** | 0, 15, 45, 90, 180° | 5 |
| Terrain regime | `A_mare_moderate`, `A_highlands_moderate` | 2 |
| Arm | 5 above | 5 |
| Seed | calibration 4001–4003 · validation 5001–5003 | 3 + 3 |

Grid: 6 × 5 × 2 = 60 conditions per arm per seed. The **S1 slice** is rotation = 0° (6 Δaz);
the **S2 slice** is Δaz = 0° (5 rotations); the full grid measures interaction.

To control cost the full 6×5 grid runs on **calibration** seeds; **validation** seeds run the
S1 and S2 slices plus the two interaction corners (Δaz 30°/45° × rotation 45°/90°).

**`B_highlands_challenging` is excluded** from the primary grid and may be run as a secondary
diagnostic. EXP-003 stop-condition 2 forbids claiming success on non-A regimes.

## 1.10 Method — the direct mechanism measurement

Match outcomes are an *indirect* test. EXP-004 additionally measures orientation assignment
error **directly**, and this is what settles H-4.1/H-4.2:

For each (regime, seed, Δaz, rotation): pair keypoints between source and reference through
the **known ground-truth transform** by location (≤ 2 px), then compute

```
assignment_error = wrap180( orientation_ref − orientation_src − true_rotation )
```

Subtracting `true_rotation` is the step E-003.4 omitted. What remains is
**illumination-induced** orientation error, isolated. Reported as median, p90, and fraction
> 30°, per arm, as a function of Δaz **and** rotation independently.

`[This measurement is the stage's primary scientific output, independent of whether any arm
meets S1.]`

## 1.11 Data provenance and roles

| Role | Seeds | Use |
|---|---|---|
| Calibration | 4001, 4002, 4003 | Full 6×5 grid; any parameter choice fixed here |
| Validation | 5001, 5002, 5003 | Reporting only; slices + corners |
| Synthetic ground truth | both | Scoring and keypoint pairing only — never a pipeline input |

Seeds are disjoint from EXP-002 (1001–1005, 7001–7004) and EXP-003 (3001–3003).
**No parameter is tuned on validation seeds.**

## 1.12 Metrics

| Metric | Definition | Kind |
|---|---|---|
| `assignment_error_deg` | wrap180(Δorientation − true_rotation), GT-paired keypoints | **primary, mechanism** |
| `transform_error_median` | median endpoint error, estimated vs true map, dense grid | **primary, GT** |
| success / `is_wrong` | `transform_error_median > 3 px` | GT |
| `n_inliers`, `inlier_ratio`, `coverage_max_gap`, `n_kp` | deployable signals | deployable |
| `fit_rmse` | recorded for the record | **circular — never a criterion** |
| `pipeline_s` | wall clock | engineering only (D-020) |

## 1.13 Negative controls declared in advance

1. **`sift_orient_custom`** — our orientation + our descriptor at 2π. Separates "our code" from "orientation assignment".
2. **Δaz = 0°, rotation = 0° anchor** — every arm must succeed. An arm failing here is broken and its other results are void.
3. **Rotation 180° at Δaz 0°** — pure geometric rotation, no illumination change. Any arm claiming rotation invariance must survive it.
4. **`fit_rmse`** — predicted uninformative (EXP-002: ROC AUC 0.4947). May not influence any decision.

---

# PART 2 — written AFTER implementation

*(Empty. Nothing below this line existed when Part 1 was fixed.)*
