# The Coordinate Contract (spec §40, §41, §60 · risk R8)

This document is **normative**. Every module in `src/siim/` obeys it. Violations are bugs even if the output looks correct — especially then, because coordinate bugs are silent: they produce plausible imagery and corrupt every number downstream.

Enforced by `src/siim/geometry/conventions.py` and the property tests in `tests/test_geometry_*.py`.

---

## C1 — Point arrays

- Shape `(N, 2)`, dtype `float64`, always.
- Column order is **`(x, y)`**. `x` is the **column** axis, increasing rightward. `y` is the **row** axis, increasing downward.
- Never pass `(2, N)`. Never pass integer dtype. `as_points()` enforces both.

## C2 — Image arrays

- Indexed `img[row, col]`, i.e. `img[y, x]`. This is the **opposite** order from C1.
- The transposition is the single most common source of silent error in this codebase. It is therefore **never implicit**: use `xy_to_rc()` / `rc_to_xy()`, which exist purely to make the swap visible at the call site.
- `img.shape[:2] == (height, width) == (n_rows, n_cols)`.

## C3 — Pixel-centre convention  ★ the sub-pixel-critical one

**Integer coordinate `(x, y) = (0, 0)` is the CENTRE of the top-left pixel.**

Consequences that must be respected everywhere:

- An image of width `W` spans continuous `x ∈ [-0.5, W - 0.5]`.
- The image's continuous centre is at `((W - 1) / 2, (H - 1) / 2)`, **not** `(W/2, H/2)`.
- This matches `scipy.ndimage.map_coordinates`, OpenCV `remap`, and standard photogrammetric practice.

The competing "pixel-corner" convention (integer coordinate at the top-left *corner* of a pixel) differs by exactly 0.5 px. Since our accuracy target is sub-pixel, mixing the two silently destroys the result while leaving every image looking fine.

## C4 — Resampling and coordinate update  ★ the second sub-pixel-critical one

When an image is resampled by factor `s` (`s > 1` enlarges), coordinates transform as:

```
p' = s · (p + 0.5) − 0.5        NOT   p' = s · p
```

**Derivation.** Convert pixel-centre coordinate `p` to edge-space `u = p + 0.5`; scale in edge space, `u' = s·u`; convert back, `p' = u' − 0.5`.

**Check.** Upsampling by `s = 2`: the original pixel 0 becomes new pixels 0 and 1, whose joint centre is 0.5. The formula gives `2·(0 + 0.5) − 0.5 = 0.5` ✓. The naive `s·p` gives `0` ✗ — a half-pixel error, which is the entire budget we are trying to defend.

This scaling is available as a first-class `Transform` via `scale_transform(s)`, so a resampling factor **lives in the transform chain** and cannot be forgotten. Never hand-multiply coordinates by a scale factor.

## C5 — Transform direction

- A `Transform` `T` maps **source → reference**: `q = T.apply(p)`.
- Warping the *source image* into the *reference frame* requires the **inverse** map, because resampling iterates over output pixels and asks where each came from.
- `warp()` therefore takes the **forward** transform and inverts it internally. Callers pass the forward transform, always. There is no `warp_inverse()`, deliberately — offering both is how the direction gets confused.

## C6 — Homogeneous coordinates

- Shape `(N, 3)`. `from_homogeneous` divides by `w`.
- Points with `|w| < eps` map to infinity. These are returned as `NaN` rather than raising, because a projective transform can legitimately send a point on the vanishing line to infinity. **Callers must filter `NaN`**; `finite_mask()` is provided for this.

## C7 — Residuals are reported in native pixels

If an image was resampled during processing, residuals are converted **back to the native pixel scale of the image being registered** before reporting. A 0.4 px residual measured on a 4× downsampled image is a **1.6 px** residual in native pixels. Reporting the former would be a form of the circularity described in ANALYSIS §A.3 — an accuracy claim inflated by a processing choice.

## C8 — Angles and rotation

- Angles in **radians**, counter-clockwise positive in a standard right-handed `(x, y)` frame.
- Because `y` increases *downward* in image space (C1), a positive angle appears **clockwise** on screen. This is stated so nobody "fixes" it later; the sign convention is consistent, and the visual direction is a consequence of the image axis, not an error.

## C9 — Numerical stability (spec §60)

- All estimators apply **Hartley normalisation** (translate the centroid to the origin, scale so mean distance is `√2`) before solving, and de-normalise afterwards. Skipping this makes the DLT design matrix badly conditioned for image-sized coordinates.
- Every estimator returns the design-matrix condition number. Degenerate configurations — collinear points, insufficient spread — are **detected and reported**, never silently fitted.

---

## Test obligations

Any change to this module must keep these passing:

| Property | Test |
|---|---|
| `from_homogeneous(to_homogeneous(p)) == p` | round-trip |
| `T.inverse().apply(T.apply(p)) == p` | round-trip, all 5 models |
| `(A @ B).apply(p) == A.apply(B.apply(p))` | composition associativity |
| Estimating from exact correspondences recovers the transform to ~machine precision | exactness, all 5 models |
| `scale_transform(s)` agrees with actual image resampling to sub-0.05 px | **C4 correctness** |
| `warp` with identity is a no-op | direction sanity |
| `warp(img, T)` then `warp(result, T.inverse())` recovers the original interior | direction round-trip |
| Collinear input is flagged degenerate, not fitted | degeneracy detection |
