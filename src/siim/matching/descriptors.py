"""Configurable local descriptors for the EXP-003 representation comparison.

Two descriptors live here, both computed at keypoints supplied by the caller so
that an arm can share a detector with the baseline and differ *only* in how it
describes what was detected.

``describe_gradient_histogram``
    A SIFT-shaped descriptor -- 4x4 spatial bins, ``n_orientation_bins``
    orientation bins, Gaussian-weighted, L2-normalised, clipped, renormalised
    -- whose **orientation period is a parameter**. At ``2*pi`` it is a
    conventional gradient-orientation histogram; at ``pi`` corresponding
    orientations that differ by a polarity flip land in the *same* bin.

    That single parameter is the whole of hypothesis H-3.4. Running the same
    code at both periods is what makes the comparison a controlled one: any
    difference cannot be an artefact of this implementation, because both arms
    share it.

``describe_maximum_index``
    The RIFT-style descriptor: a spatial histogram of maximum-index-map values.

Upright by design, and why
--------------------------
Both descriptors are **upright**: they do not rotate the sampling patch to a
dominant orientation.

This is deliberate rather than lazy. A mod-pi descriptor has no way to assign a
dominant orientation without reintroducing the very ``[0, 2*pi)`` decision the
representation exists to avoid -- an orientation histogram over the full circle
would flip under polarity change and drag the descriptor frame with it. Making
both arms upright removes that confound entirely, at the cost of rotation
invariance.

**The limitation this creates, stated plainly:** these descriptors are valid
only for near-upright imagery. EXP-003's transform generator produces rotations
of at most 8 degrees, so the comparison is sound *within this stage*. It is not
evidence about rotation robustness, and must not be quoted as such. OpenCV's
SIFT arms are rotation-normalised and therefore differ from the custom arms in
this respect as well as in binning -- which is exactly why the 2*pi control arm
exists.

Nothing in this module consults ground truth.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import ndimage

__all__ = ["describe_gradient_histogram", "describe_maximum_index"]

_EPS = 1e-12


def _sample_grid(n_side: int) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Unit-square sample offsets in [-2, 2] bin units, ``n_side`` per axis."""
    t = (np.arange(n_side) + 0.5) / n_side * 4.0 - 2.0
    gx, gy = np.meshgrid(t, t)
    return gx.ravel(), gy.ravel()


def describe_gradient_histogram(
    image: ArrayLike,
    points: ArrayLike,
    scales: ArrayLike,
    *,
    orientation_period: float = 2.0 * np.pi,
    n_orientation_bins: int = 8,
    n_spatial: int = 4,
    samples_per_axis: int = 16,
    bin_scale_factor: float = 1.5,
    root: bool = True,
) -> NDArray[np.float32]:
    """SIFT-shaped gradient-orientation histogram with a configurable period.

    Parameters
    ----------
    orientation_period
        ``2*pi`` for a conventional descriptor; ``pi`` for a polarity-agnostic
        one, in which a gradient and its negation share a bin.
    scales
        Keypoint *diameters*, as OpenCV reports them in ``KeyPoint.size``.
    root
        Apply the RootSIFT transform (L1-normalise then element-wise sqrt), so
        the custom arms are on the same footing as baseline B1.
    """
    img = np.asarray(image, dtype=np.float64)
    finite = np.isfinite(img)
    if not finite.all():
        img = np.where(finite, img, float(img[finite].mean()) if finite.any() else 0.0)

    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    sc = np.asarray(scales, dtype=np.float64).reshape(-1)
    n_kp = pts.shape[0]
    dim = n_spatial * n_spatial * n_orientation_bins
    if n_kp == 0:
        return np.zeros((0, dim), dtype=np.float32)

    gy, gx = np.gradient(img)

    # Sample offsets, in units of one spatial bin, shared by every keypoint.
    ox, oy = _sample_grid(samples_per_axis)
    bin_width = np.maximum(sc, 1.0) * bin_scale_factor  # px per spatial bin

    # (n_kp, n_samples) sample coordinates in image space.
    sx = pts[:, 0:1] + ox[None, :] * bin_width[:, None]
    sy = pts[:, 1:2] + oy[None, :] * bin_width[:, None]

    # Interpolate the gradient components, not the angle: an angle cannot be
    # linearly interpolated across its wrap point.
    coords = np.stack([sy.ravel(), sx.ravel()])
    gxs = ndimage.map_coordinates(gx, coords, order=1, mode="nearest").reshape(sx.shape)
    gys = ndimage.map_coordinates(gy, coords, order=1, mode="nearest").reshape(sx.shape)

    mag = np.hypot(gxs, gys)
    ang = np.mod(np.arctan2(gys, gxs), orientation_period)

    # Gaussian spatial weighting, sigma = half the descriptor window.
    r2 = ox[None, :] ** 2 + oy[None, :] ** 2
    mag = mag * np.exp(-r2 / (2.0 * (0.5 * 4.0) ** 2))

    # Trilinear soft assignment, as in SIFT proper. Hard binning throws away
    # sub-bin position and makes the descriptor jitter under small geometric
    # change, which costs match yield for no principled reason. Both custom
    # arms share this code, so it cannot favour either orientation period.
    xbin = (ox + 2.0) / 4.0 * n_spatial - 0.5   # (n_samples,)
    ybin = (oy + 2.0) / 4.0 * n_spatial - 0.5
    obin_c = ang / orientation_period * n_orientation_bins  # (n_kp, n_samples)

    x0 = np.floor(xbin).astype(np.int64)
    y0 = np.floor(ybin).astype(np.int64)
    o0 = np.floor(obin_c).astype(np.int64)
    dx, dy = xbin - x0, ybin - y0
    do = obin_c - o0

    desc = np.zeros((n_kp, dim), dtype=np.float64)
    rows = np.repeat(np.arange(n_kp), mag.shape[1])

    for i in (0, 1):
        xi = x0 + i
        wx = dx if i else (1.0 - dx)
        okx = (xi >= 0) & (xi < n_spatial)
        for j in (0, 1):
            yj = y0 + j
            wy = dy if j else (1.0 - dy)
            oky = (yj >= 0) & (yj < n_spatial)
            spatial_ok = okx & oky
            if not spatial_ok.any():
                continue
            spatial_index = (np.clip(yj, 0, n_spatial - 1) * n_spatial
                             + np.clip(xi, 0, n_spatial - 1))
            sw = (wx * wy * spatial_ok)[None, :]
            for k in (0, 1):
                # Orientation wraps: bin n-1 is adjacent to bin 0.
                ok_idx = np.mod(o0 + k, n_orientation_bins)
                wo = do if k else (1.0 - do)
                contrib = mag * sw * wo
                flat = spatial_index[None, :] * n_orientation_bins + ok_idx
                np.add.at(desc, (rows, flat.ravel()), contrib.ravel())

    # SIFT's normalisation: L2, clip at 0.2 to blunt large gradients, L2 again.
    norm = np.linalg.norm(desc, axis=1, keepdims=True)
    desc = desc / np.maximum(norm, _EPS)
    desc = np.minimum(desc, 0.2)
    norm = np.linalg.norm(desc, axis=1, keepdims=True)
    desc = desc / np.maximum(norm, _EPS)

    if root:
        l1 = np.abs(desc).sum(axis=1, keepdims=True)
        desc = np.sqrt(desc / np.maximum(l1, _EPS))

    return desc.astype(np.float32)


def describe_maximum_index(
    mim: ArrayLike,
    points: ArrayLike,
    scales: ArrayLike,
    *,
    n_index: int = 6,
    n_spatial: int = 6,
    samples_per_axis: int = 18,
    bin_scale_factor: float = 1.5,
    root: bool = True,
) -> NDArray[np.float32]:
    """RIFT-style descriptor: spatial histogram of maximum-index-map values.

    The maximum index map records *which* log-Gabor orientation channel is
    strongest at each pixel, discarding amplitude. Histogramming it over a
    spatial grid gives a contrast-invariant description of local structure.

    ``mim`` is a label image, so it is sampled with nearest-neighbour
    interpolation: averaging orientation *indices* would be meaningless.
    """
    labels = np.asarray(mim)
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    sc = np.asarray(scales, dtype=np.float64).reshape(-1)
    n_kp = pts.shape[0]
    dim = n_spatial * n_spatial * n_index
    if n_kp == 0:
        return np.zeros((0, dim), dtype=np.float32)

    ox, oy = _sample_grid(samples_per_axis)
    bin_width = np.maximum(sc, 1.0) * bin_scale_factor

    sx = pts[:, 0:1] + ox[None, :] * bin_width[:, None]
    sy = pts[:, 1:2] + oy[None, :] * bin_width[:, None]

    coords = np.stack([sy.ravel(), sx.ravel()])
    vals = ndimage.map_coordinates(
        labels.astype(np.float64), coords, order=0, mode="nearest"
    ).reshape(sx.shape).astype(np.int64)
    vals = np.clip(vals, 0, n_index - 1)

    sxi = np.clip(((ox + 2.0) / 4.0 * n_spatial).astype(np.int64), 0, n_spatial - 1)
    syi = np.clip(((oy + 2.0) / 4.0 * n_spatial).astype(np.int64), 0, n_spatial - 1)
    spatial_index = (syi * n_spatial + sxi)[None, :]

    flat = spatial_index * n_index + vals

    desc = np.zeros((n_kp, dim), dtype=np.float64)
    rows = np.repeat(np.arange(n_kp), flat.shape[1])
    np.add.at(desc, (rows, flat.ravel()), 1.0)

    norm = np.linalg.norm(desc, axis=1, keepdims=True)
    desc = desc / np.maximum(norm, _EPS)

    if root:
        l1 = np.abs(desc).sum(axis=1, keepdims=True)
        desc = np.sqrt(desc / np.maximum(l1, _EPS))

    return desc.astype(np.float32)
