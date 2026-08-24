"""Coordinate conventions for the SIIM lunar registration system.

This module is the single place where coordinate conventions are defined and
enforced. It exists because coordinate-convention errors are *silent*: they
produce plausible-looking imagery while corrupting every downstream number.
See ``docs/coordinate_contract.md`` (normative) and risk R8.

Summary of the contract, restated here so it travels with the code:

* Point arrays are ``(N, 2)`` float64, ordered ``(x, y)``.
* ``x`` is the column axis (rightward), ``y`` is the row axis (downward).
* Images are indexed ``img[row, col] == img[y, x]`` -- the opposite order.
  The swap is never implicit; use :func:`xy_to_rc` / :func:`rc_to_xy`.
* Integer coordinate ``(0, 0)`` is the **centre** of the top-left pixel.
* Resampling by factor ``s`` maps ``p -> s * (p + 0.5) - 0.5``.

Why hand-rolled rather than OpenCV: ADR-0007 rejects inheriting conventions
implicitly. Every rule above is visible in this file rather than assumed from
a dependency, and the property tests pin it down.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = [
    "PointArray",
    "as_points",
    "to_homogeneous",
    "from_homogeneous",
    "finite_mask",
    "xy_to_rc",
    "rc_to_xy",
    "image_extent",
    "image_centre",
    "pixel_grid",
    "corner_points",
    "scale_coords",
    "EPS_HOMOGENEOUS",
]

PointArray = NDArray[np.float64]

#: Below this |w|, a homogeneous point is treated as lying at infinity.
EPS_HOMOGENEOUS: float = 1e-12


def as_points(pts: ArrayLike) -> PointArray:
    """Coerce ``pts`` to a validated ``(N, 2)`` float64 array of ``(x, y)``.

    Raises rather than reshaping ambiguously. A ``(2, N)`` array is rejected
    even when ``N == 2`` is not the case, because silently transposing is
    exactly the class of bug this module exists to prevent.
    """
    arr = np.asarray(pts, dtype=np.float64)
    if arr.ndim == 1:
        if arr.size != 2:
            raise ValueError(
                f"1-D point must have exactly 2 elements (x, y); got {arr.size}"
            )
        arr = arr.reshape(1, 2)
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError(
            f"points must have shape (N, 2) in (x, y) order; got {arr.shape}. "
            "If you have a (2, N) array, transpose it explicitly at the call "
            "site so the conversion is visible."
        )
    return np.ascontiguousarray(arr)


def to_homogeneous(pts: ArrayLike) -> NDArray[np.float64]:
    """``(N, 2)`` -> ``(N, 3)`` by appending a column of ones."""
    p = as_points(pts)
    return np.hstack([p, np.ones((p.shape[0], 1), dtype=np.float64)])


def from_homogeneous(pts_h: ArrayLike, eps: float = EPS_HOMOGENEOUS) -> PointArray:
    """``(N, 3)`` -> ``(N, 2)`` by dividing through by ``w``.

    Points with ``|w| < eps`` lie on the vanishing line and are returned as
    ``NaN`` rather than raising: a projective transform may legitimately send
    a finite point to infinity, and that is information, not an error.
    Callers must filter with :func:`finite_mask`.
    """
    arr = np.asarray(pts_h, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError(f"homogeneous points must have shape (N, 3); got {arr.shape}")
    w = arr[:, 2]
    at_infinity = np.abs(w) < eps
    safe_w = np.where(at_infinity, 1.0, w)
    out = arr[:, :2] / safe_w[:, None]
    out[at_infinity] = np.nan
    return out


def finite_mask(pts: ArrayLike) -> NDArray[np.bool_]:
    """Boolean mask of points whose coordinates are all finite."""
    p = as_points(pts)
    return np.isfinite(p).all(axis=1)


def xy_to_rc(pts: ArrayLike) -> PointArray:
    """``(x, y)`` -> ``(row, col)``. Exists to make the axis swap visible."""
    p = as_points(pts)
    return np.column_stack([p[:, 1], p[:, 0]])


def rc_to_xy(pts: ArrayLike) -> PointArray:
    """``(row, col)`` -> ``(x, y)``. Exists to make the axis swap visible."""
    p = np.asarray(pts, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 2:
        raise ValueError(f"expected (N, 2) (row, col) array; got {p.shape}")
    return np.column_stack([p[:, 1], p[:, 0]])


def image_extent(shape: tuple[int, ...]) -> tuple[float, float, float, float]:
    """Continuous bounds ``(x_min, x_max, y_min, y_max)`` of an image.

    Under the pixel-centre convention (C3) an image of width ``W`` spans
    ``x in [-0.5, W - 0.5]`` -- not ``[0, W]``.
    """
    h, w = int(shape[0]), int(shape[1])
    return (-0.5, w - 0.5, -0.5, h - 0.5)


def image_centre(shape: tuple[int, ...]) -> PointArray:
    """Continuous centre of an image, as a ``(1, 2)`` ``(x, y)`` array.

    This is ``((W - 1) / 2, (H - 1) / 2)`` under the pixel-centre convention,
    **not** ``(W / 2, H / 2)``. The difference is half a pixel, which is our
    entire sub-pixel error budget.
    """
    h, w = int(shape[0]), int(shape[1])
    return np.array([[(w - 1) / 2.0, (h - 1) / 2.0]], dtype=np.float64)


def pixel_grid(shape: tuple[int, ...], step: int = 1) -> PointArray:
    """All pixel centres of an image as ``(N, 2)`` ``(x, y)``, row-major.

    ``step`` subsamples the grid, which is how dense ground-truth error fields
    are built without materialising every pixel of a 52k-line NAC image.
    """
    h, w = int(shape[0]), int(shape[1])
    if step < 1:
        raise ValueError(f"step must be >= 1; got {step}")
    ys, xs = np.meshgrid(
        np.arange(0, h, step, dtype=np.float64),
        np.arange(0, w, step, dtype=np.float64),
        indexing="ij",
    )
    return np.column_stack([xs.ravel(), ys.ravel()])


def corner_points(shape: tuple[int, ...]) -> PointArray:
    """The four continuous corners of an image, clockwise from top-left.

    Uses the true extent (C3), so the corners are at +/-0.5 beyond the outer
    pixel centres. Used for overlap estimation and for bounding the output
    canvas of a warp.
    """
    x0, x1, y0, y1 = image_extent(shape)
    return np.array(
        [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float64
    )


def scale_coords(pts: ArrayLike, scale: float) -> PointArray:
    """Update coordinates for a resampling by ``scale`` (>1 enlarges).

    Implements C4: ``p' = scale * (p + 0.5) - 0.5``.

    Prefer :func:`siim.geometry.transforms.scale_transform`, which puts the
    same operation into the transform chain where it cannot be forgotten.
    This function is for the rare case where a bare coordinate update is
    genuinely what is wanted.
    """
    p = as_points(pts)
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError(f"scale must be finite and positive; got {scale}")
    return scale * (p + 0.5) - 0.5
