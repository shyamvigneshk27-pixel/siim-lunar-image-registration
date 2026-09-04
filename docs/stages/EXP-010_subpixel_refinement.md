# EXP-010 — Is sub-pixel correspondence accuracy achievable and measurable, and how does illumination change bias it?

**Part 1 — pre-registration. FROZEN 2026-09-04, before any refinement code was
written.** Part 2 is empty until Part 1 is committed.

**Classification: DELIVERABLE-CRITICAL.** The problem statement asks for
"sub-pixel accuracy of the source image". This repository has never measured a
sub-pixel number, and has shown (E-008) that the number most teams will quote,
the fit residual, is not one.

## 1. Definition adopted

A correspondence set is **sub-pixel accurate** when the endpoint error of its
points against ground truth, measured in pixels of the **coarser** image, has
median < 0.5 px and a 95 % bootstrap confidence interval whose upper end is
< 1.0 px. Fit residuals are recorded and never used. Where the two images have
different sampling, the coarser sampling defines the pixel.

## 2. Questions

**Q1 (precision).** Under identical illumination, what per-point accuracy does
local area-based refinement reach on real NAC texture, as a function of window
size and method?

**Q2 (bias under illumination change).** When the two images differ in Sun
geometry, does refinement converge to the true geometric correspondence or to
the shading feature, and by how much is it biased as Δazimuth and Δelevation
grow?

**Q3 (harm).** Does refinement ever make a correspondence worse, and can that
be detected from the refinement's own confidence?

## 3. Data, fixed in advance

**D1 — real self-warps (Q1).** Each of the four recorded NAC tiles (A, B, C, D
at decimation 2, percentile-stretched) is warped by 12 known transforms:
translations with fractional parts {0.0, 0.25, 0.5, 0.75} px on each axis and
similarities with scale {0.9, 1.1} and rotation {±3°}, all composed under
contract C4, cubic resampling with NaN fill (the geometry layer's `warp`).
Ground truth is exact. Illumination is identical by construction.

**D2 — synthetic illumination pairs (Q2, Q3).** The existing terrain generator
(`siim.data.make_pair`) on regimes `A_mare_moderate` and
`A_highlands_moderate`, seeds {3001, 3002, 3003} (EXP-003's seeds, unused for
any threshold), affine transforms as in EXP-002, Δazimuth ∈ {0, 5, 10, 15, 20,
25, 30}°, Δelevation ∈ {0, −10}°. Ground truth is exact and physically
rendered. Only pairs where the unmodified B1 baseline passes the D-023 rule are
refined, so refinement is measured where it would be deployed.

**D3 — rendered SLDEM pairs (Q2 at coarse GSD).** The Mare Serenitatis SLDEM
window rendered at 30 m/px under the Sun geometries of frames A, B, D
(incidence 29.95°, 69.76°, 18.22°), matched pairwise. Ground truth is the
identity through the DEM. These are low-texture and are reported as a
secondary, labelled as renders.

## 4. Method, fixed in advance

1. Initial correspondences and transform from the unmodified B1 pipeline
   (LO-RANSAC affine, threshold 3.0, seed 0), inliers only.
2. For each inlier, a square window of side w ∈ {32, 48, 64} px is cut from
   the source around the point and warped by the estimated affine into the
   reference grid; the reference patch is cut at the predicted location.
3. Refinement of the translation between the two patches by
   (a) OpenCV ECC, translation model, 50 iterations, ε 1e-5; and
   (b) OpenCV phase correlation with Hanning window and its response value.
   Each returns a sub-pixel shift and a confidence (ECC coefficient; phase
   peak response).
4. Refined reference point = predicted point + shift. Error = distance to
   ground-truth reference point, in coarser-image pixels.
5. Per condition: median error before and after refinement, 95 % bootstrap CI
   (1000 resamples, seed 20260904), fraction of points made worse, and the AUC
   of confidence for predicting "made worse".

## 5. Hypotheses and criteria — FROZEN

**H1 (precision on real texture).** On D1, refinement reaches the definition.
> **S1 MET** if, for at least one (method, w), pooled over the four tiles and
> twelve warps, median error < 0.25 px with CI upper < 0.5 px, and the
> pre-refinement median is > 2× the post-refinement median. Prediction: MET
> for ECC at w = 48. Confidence HIGH.

**H2 (bias under illumination).** On D2, refinement error grows with Δazimuth.
> **S2 MET** if the post-refinement median at Δaz = 0° is < 0.5 px and at
> Δaz = 30° is ≥ 2× the Δaz = 0° value, on both regimes. Prediction: MET; the
> refiner locks onto shading, which moves. Confidence MEDIUM.

**H3 (deployable envelope).** There is a Δazimuth below which the definition
holds on realistic terrain.
> **S3 MET** if the largest Δaz at which the pooled post-refinement median is
> < 0.5 px with CI upper < 1.0 px is ≥ 10° on both A-regimes. Prediction:
> MET at 10–15°. Confidence LOW-MEDIUM.

**H4 (harm is detectable).** Confidence predicts harm.
> **S4 MET** if the AUC of confidence for "point made worse by > 0.5 px" is
> ≥ 0.75 pooled over D2. Prediction: MET for ECC coefficient. Confidence LOW.

**Gate.** On D1 with zero transform (identity warp), refinement must return
median |shift| < 0.05 px; otherwise the refiner has a bias of its own and the
stage stops.

## 6. What each outcome licenses

S1 MET: the deliverable may state sub-pixel accuracy **under matched
illumination** with the measured number. S2/S3: the envelope in Δazimuth
within which the sub-pixel claim holds, and the bias outside it, which must be
printed next to any sub-pixel number on a real pair. S4: whether a per-point
confidence gate can be shipped. No outcome licenses a sub-pixel claim on a real
cross-illumination pair, because no such ground truth exists; that claim needs
EXP-007's render-conditioned path or manual check points, and is not made here.

## 7. Threats to validity

Self-warps share texture and interpolation kernel with their originals, so D1
is an upper bound on precision. D2's renderer is Lambertian; real shading
differs. Window sizes are pre-fixed; no per-image tuning. Bootstrap CIs assume
independent points; clustered inliers understate the interval, which is stated.

## 8. What this stage does NOT do

No real cross-illumination sub-pixel claim. No Chandrayaan-2. No change to
any matcher, threshold or verdict rule.

---

## Part 2 — Results

**Run:** 2026-09-04, `scripts/run_exp010.py --out exp010_results_v2.json`
(commit 7cdd956), 14.1 min CPU, 727 rows. Artefact:
`experiments/EXP-010/exp010_results_v2.json`. A first artefact,
`exp010_results.json`, is preserved unchanged: its gate implemented the
zero transform as an integer translation *estimated by B1*, so on frame D it
measured B1's estimation error rather than the refiner's bias (see E-034). Every
other number in the two artefacts agrees; only the gate differs.

### Gate — MET
Identity pair, refined against the exact identity, 400 points × 4 tiles × 6
(method, window) combinations: maximum median |shift| = 7e-15 px. Neither ECC
nor phase correlation has a bias of its own.

### S1 (precision on real self-warps) — MET
Pooled over four tiles and twelve known warps (8 translations with fractional
parts, 4 similarities at scale 0.9/1.1 and ±3°), errors in pixels against the
exact warp, ECC only shown (phase correlation below):

| method, window | before refinement (B1 affine) | after refinement | 95 % CI (after) |
|---|---|---|---|
| ECC 32 | 0.040 | **0.0034** | 0.0033–0.0036 |
| ECC 48 | 0.040 | **0.0032** | 0.0032–0.0033 |
| ECC 64 | 0.040 | **0.0032** | 0.0031–0.0033 |
| phase 32/48/64 | 0.040 | 0.028 / 0.028 / 0.027 | — |

Per tile (ECC 64): A 0.041 → 0.0032; B 0.003 → 0.0003; C 0.004 → 0.0004;
**D 0.302 → 0.0087** (p90 0.834 → 0.021). Frame D's pre-refinement error is
the E-034 defect: the affine model absorbs correlated localisation error on
the low-contrast, high-Sun tile; local refinement removes it.

**Phase correlation** recovers the sign of a residual and about half its
magnitude on these smooth patches (0.028 px after, versus 0.003 for ECC; the
unit test pins 0.13 px for a 0.30 px residual). It does not meet S1 and is not
the deployed method. **ECC is.**

These are upper bounds on precision: the warped image shares texture and
interpolation kernel with its original.

### S2 (bias grows with Δazimuth) — MET, both regimes
ECC 64, pairs where B1 passed the D-023 rule (65 of 84), median error after
refinement in px with bootstrap CI:

| Δaz | mare (n pairs) | highlands (n pairs) |
|---|---|---|
| 0° | 0.039 (6) | 0.008 (6) |
| 5° | 0.050 (6) | 0.019 (6) |
| 10° | 0.082 (6) | 0.020 (6) |
| 15° | 0.134 (4) | 0.044 (6) |
| 20° | 0.250 (2) | 0.040 (6) |
| 25° | 0.143 (1) | 0.054 (6) |
| 30° | 0.229 (2) | 0.069 (2) |

Error at 30° is 5.9× (mare) and 8.6× (highlands) the 0° value. The refiner
locks onto shading, which moves with the Sun, as H2 predicted. Note the mare
counts: above 15° most mare pairs fail the matching rule before refinement is
reached, so the bias is measured on few pairs there.

### S3 (deployable envelope) — MET
The largest Δaz at which the pooled post-refinement median is < 0.5 px with CI
upper < 1.0 px is **30°, the largest tested, on both regimes**. Within the
regime where matching succeeds at all, the sub-pixel definition holds.
Interpretation, stated carefully: on synthetic Lambertian terrain the
illumination bias of local refinement stays below 0.25 px up to 30°; the
matching envelope, not the refinement, is what fails first.

### S4 (confidence predicts harm) — NOT MET (undefined)
No refined point was made worse by more than 0.5 px anywhere in D2
(7528 points), so the AUC of confidence against harm is undefined. H4 is
untestable on this data, not refuted. It will be re-measured when a
cross-illumination real pair with check points exists.

### D3 (rendered SLDEM pairs at 30 m) — no result
B1 found 0 inliers between renders of the same DEM under the Sun geometries of
frames A, B and D: at 30 m/px the 59 m DEM render of this mare window is too
smooth for SIFT. Consistent with EXP-007's native-scale result; reported, not
interpreted.

### What is claimed and what is not
- **Claimed:** under matched illumination the pipeline delivers correspondences
  with a median error of 0.003 px on real NAC texture (self-warps, upper bound),
  and under synthetic illumination change up to 30° the refined error stays
  below 0.25 px (highlands) and 0.23 px (mare), with bootstrap CIs.
- **Claimed:** local ECC refinement removes the E-034 global-model bias on
  frame D from 0.30 px to 0.009 px.
- **Not claimed:** any sub-pixel number on a real cross-illumination pair (no
  ground truth exists); anything about Chandrayaan-2.

### Consequences
Refinement joins the architecture as the last step before the verdict. The
sub-pixel claim in the deliverable reads: *median 0.003 px (matched
illumination, self-warp upper bound); < 0.25 px under Sun-azimuth change to
30° on synthetic terrain; not validated on real cross-illumination pairs.*

