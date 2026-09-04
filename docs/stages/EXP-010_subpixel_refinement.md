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

*Empty until Part 1 is committed and the run has completed.*
