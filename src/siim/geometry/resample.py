"""Image warping and rescaling, with resampling safety (spec §41).

Two rules govern this module.

**Direction (contract C5).** :func:`warp` takes the **forward** transform
(source -> reference) and inverts it internally, because resampling iterates
over *output* pixels and asks where each came from. There is deliberately no
``warp_inverse``: offering both directions is how the direction gets confused.

**Anti-aliasing.** Downsampling without a low-pass prefilter aliases
high-frequency terrain texture into false low-frequency structure. On a
crater-saturated surface that is not a cosmetic issue -- aliased texture can
produce *correspondences that do not exist*, which is exactly the failure
spec §41 warns about. :func:`resize` therefore prefilters by default when
shrinking, and refuses to pretend otherwise.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import ndimage

from .conventions import as_points, corner_points, finite_mask
from .transforms import Transform, scale_transform

__all__ = ["warp", "resize", "warp_bounds", "antialias_sigma"]


def antialias_sigma(scale: float) -> float:
    """Gaussian sigma for prefiltering before a downsample by ``scale`` (<1).

    Returns ``0.0`` when enlarging, since upsampling introduces no aliasing.
    Uses the standard ``sigma = (1/scale - 1) / 2``, which matches the
    effective support of an area-average over the ``1/scale`` pixels that
    collapse into one.
    """
    if scale >= 1.0:
        return 0.0
    return ((1.0 / scale) - 1.0) / 2.0


def warp_bounds(
    shape: tuple[int, ...], transform: Transform
) -> tuple[float, float, float, float]:
    """Bounding box ``(x_min, x_max, y_min, y_max)`` of a warped image's corners.

    Uses true image extent (contract C3), so corners sit half a pixel beyond
    the outer pixel centres. Raises if the transform sends a corner to
    infinity, since no finite output canvas exists in that case.
    """
    corners = transform.apply(corner_points(shape))
    if not finite_mask(corners).all():
        raise ValueError(
            "transform maps an image corner to infinity; no finite output "
            "canvas exists for this warp"
        )
    return (
        float(corners[:, 0].min()),
        float(corners[:, 0].max()),
        float(corners[:, 1].min()),
        float(corners[:, 1].max()),
    )


def warp(
    image: ArrayLike,
    transform: Transform,
    out_shape: tuple[int, int] | None = None,
    order: int = 3,
    cval: float = np.nan,
) -> tuple[NDArray[np.float64], NDArray[np.bool_]]:
    """Warp ``image`` from source into reference frame under ``transform``.

    Parameters
    ----------
    image
        2-D source image.
    transform
        **Forward** transform, source -> reference (contract C5).
    out_shape
        ``(height, width)`` of the output. Defaults to the source shape,
        which is the right default when registering into a known reference
        frame; pass an explicit shape to capture the full warped extent.
    order
        Spline interpolation order. 3 (cubic) is the default: it is the
        lowest order that does not visibly soften terrain texture, and
        texture is the signal we match on. Use 1 for speed in coarse stages.
    cval
        Fill value outside the source. Defaults to ``NaN`` so that invalid
        regions are *unmistakable* downstream rather than being mistaken for
        genuinely black lunar shadow -- which, on this data, is a real and
        easy confusion to make.

    Returns
    -------
    warped, valid
        The resampled image, and a boolean mask of pixels that came from
        inside the source footprint.
    """
    img = np.asarray(image, dtype=np.float64)
    if img.ndim != 2:
        raise ValueError(f"warp expects a 2-D image; got shape {img.shape}")
    h_out, w_out = out_shape if out_shape is not None else img.shape[:2]

    # For each OUTPUT pixel centre, find where it came from in the source.
    ys, xs = np.meshgrid(
        np.arange(h_out, dtype=np.float64),
        np.arange(w_out, dtype=np.float64),
        indexing="ij",
    )
    dst_pts = np.column_stack([xs.ravel(), ys.ravel()])
    src_pts = transform.inverse().apply(dst_pts)

    finite = finite_mask(src_pts)
    src_x = np.where(finite, src_pts[:, 0], -1.0)
    src_y = np.where(finite, src_pts[:, 1], -1.0)

    # map_coordinates indexes (row, col) -- the axis swap made explicit.
    sampled = ndimage.map_coordinates(
        img,
        np.vstack([src_y, src_x]),
        order=order,
        mode="constant",
        cval=0.0,
        prefilter=True,
    )

    h_src, w_src = img.shape
    inside = (
        finite
        & (src_x >= -0.5)
        & (src_x <= w_src - 0.5)
        & (src_y >= -0.5)
        & (src_y <= h_src - 0.5)
    )
    out = np.where(inside, sampled, cval).reshape(h_out, w_out)
    return out, inside.reshape(h_out, w_out)


def resize(
    image: ArrayLike,
    scale: float,
    antialias: bool = True,
    order: int = 3,
) -> tuple[NDArray[np.float64], Transform]:
    """Rescale ``image`` by ``scale`` (>1 enlarges), returning the coordinate update.

    Returns
    -------
    resized, transform
        The resampled image, and the :class:`Transform` mapping original
        coordinates to resized coordinates. **Use the returned transform**
        rather than multiplying coordinates by ``scale`` by hand -- the naive
        version omits the ``(scale - 1) / 2`` offset and costs half a pixel
        (contract C4).

    Notes
    -----
    Setting ``antialias=False`` while shrinking is permitted but is almost
    always a mistake: it aliases terrain texture into structure that was never
    there, and can manufacture correspondences (spec §41).
    """
    img = np.asarray(image, dtype=np.float64)
    if img.ndim != 2:
        raise ValueError(f"resize expects a 2-D image; got shape {img.shape}")
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError(f"scale must be finite and positive; got {scale}")

    h, w = img.shape
    h_out = max(1, int(round(h * scale)))
    w_out = max(1, int(round(w * scale)))

    work = img
    if antialias and scale < 1.0:
        sigma = antialias_sigma(scale)
        if sigma > 0:
            work = ndimage.gaussian_filter(img, sigma=sigma, mode="nearest")

    tf = scale_transform(scale)
    inv = tf.inverse()

    ys, xs = np.meshgrid(
        np.arange(h_out, dtype=np.float64),
        np.arange(w_out, dtype=np.float64),
        indexing="ij",
    )
    src = inv.apply(np.column_stack([xs.ravel(), ys.ravel()]))
    sampled = ndimage.map_coordinates(
        work,
        np.vstack([src[:, 1], src[:, 0]]),
        order=order,
        mode="nearest",
        prefilter=True,
    )
    return sampled.reshape(h_out, w_out), tf
