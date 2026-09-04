"""Frame orientation from archive corner geometry, and a deterministic north-up.

Why this exists
---------------
REAL-DATA-05 screened 906 archive products for a second low-incidence frame
over the recorded ground and found exactly two, both rejected by its
orientation filter H5: their tiles would be rotated 180 degrees relative to
the incumbents, and whether SIFT's orientation assignment survives that is the
project's own open question (EXP-004). The stage stopped rather than entangle
two causes.

That filter guards against an *estimated* rotation. The rotation between two
NAC frames over the same ground is not something a matcher has to estimate:
the archive's named corner columns say which way each frame's lines run, so
the tile can be turned to a common ground orientation **before** matching by a
rotation that is known, not inferred. That removes the confound the filter
existed for, and with it the reason to reject the frames.

What is done, precisely
-----------------------
:func:`orientation_signature` restates ``scripts/screen_frame_d.py``'s
``(along, cross)`` signs from the corner columns (E-032: no flight-direction
rule predicts them; they are read per frame). :func:`north_up` rotates a tile
by the multiple of 90 degrees that brings ground north closest to image up and
ground east closest to image right, using the corner map's local Jacobian, and
returns the rotation as a :class:`Transform` so every correspondence can be
mapped back to the original tile pixels exactly (contract C1-C4).

What is NOT done
----------------
No sub-90-degree rotation: NAC frames are within a few degrees of north-south
and the residual is left to the affine model, where it belongs. No resampling:
a multiple of 90 degrees is a pure index permutation, so no interpolation
error enters. Nothing here reads a pixel value.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..geometry import Transform
from .footprint import FrameCorners
from .lola_dem import _ground_jacobian

__all__ = ["orientation_signature", "NorthUp", "north_up", "north_up_rotation_k"]


def orientation_signature(c: FrameCorners) -> tuple[int, int]:
    """``(along_track, cross_track)`` signs, restated from screen_frame_d.py.

    ``along`` is +1 when latitude increases from the ``UPPER_*`` row to the
    ``LOWER_*`` row (line 0 at minimum latitude); ``cross`` is +1 when
    longitude increases from ``*_LEFT`` to ``*_RIGHT``.
    """
    along = 1 if (0.5 * (c.lower_left[1] + c.lower_right[1])
                  > 0.5 * (c.upper_left[1] + c.upper_right[1])) else -1
    cross = 1 if (0.5 * (c.upper_right[0] + c.lower_right[0])
                  > 0.5 * (c.upper_left[0] + c.lower_left[0])) else -1
    return along, cross


def north_up_rotation_k(corners: FrameCorners, line: float, sample: float) -> int:
    """Number of counter-clockwise 90-degree turns that bring north closest to up.

    Computed from the corner map's Jacobian at ``(line, sample)``: the pixel
    direction of ground north is rotated by ``k * 90`` degrees and the ``k``
    that lands it nearest to ``(0, -1)`` (image up) is returned. Ties cannot
    occur for a frame within 45 degrees of any cardinal direction.
    """
    jac = _ground_jacobian(corners, line, sample)     # d(E, N) / d(sample, line)
    inv = np.linalg.inv(jac)
    north = inv @ np.array([0.0, 1.0])                  # (dx, dy) of ground north
    north = north / np.linalg.norm(north)
    best_k, best_dot = 0, -2.0
    for k in range(4):
        # np.rot90(img, k) rotates the IMAGE counter-clockwise by k*90; a vector
        # (x, y) in image axes (y down) transforms as (x, y) -> (y, -x) per turn.
        v = north.copy()
        for _ in range(k):
            v = np.array([v[1], -v[0]])
        dot = float(-v[1])                              # agreement with "up"
        if dot > best_dot:
            best_k, best_dot = k, dot
    return best_k


@dataclass(frozen=True)
class NorthUp:
    """A tile rotated to north-up, with the exact map back to the original."""

    image: NDArray
    #: Counter-clockwise quarter turns applied (``np.rot90`` convention).
    k: int
    #: Maps ORIGINAL tile (x, y) to ROTATED tile (x, y). Exact.
    forward: Transform
    record: dict

    @property
    def inverse(self) -> Transform:
        return self.forward.inverse()


def _rot90_transform(shape: tuple[int, int], k: int) -> Transform:
    """The (x, y) map of ``np.rot90(a, k)`` for an array of ``shape``.

    Derived from the index permutation, then checked numerically in the test
    suite against ``np.rot90`` on a labelled array, because a sign error here
    would be a plausible, wrong, silent transform (E-001's class).
    """
    h, w = shape
    k %= 4
    if k == 0:
        m = np.eye(3)
    elif k == 1:      # out[r, c] = a[c, w-1-r]  ->  x' = y, y' = w-1-x
        m = np.array([[0.0, 1.0, 0.0], [-1.0, 0.0, w - 1.0], [0.0, 0.0, 1.0]])
    elif k == 2:      # out[r, c] = a[h-1-r, w-1-c]
        m = np.array([[-1.0, 0.0, w - 1.0], [0.0, -1.0, h - 1.0], [0.0, 0.0, 1.0]])
    else:             # k == 3: out[r, c] = a[h-1-c, r]  ->  x' = h-1-y, y' = x
        m = np.array([[0.0, -1.0, h - 1.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    return Transform(m, "euclidean")


def north_up(image: NDArray, corners: FrameCorners, *, line: float, sample: float) -> NorthUp:
    """Rotate ``image`` (a tile cut from ``corners``' frame) to north-up.

    ``line, sample`` locate the tile centre in the parent frame so the corner
    map's local orientation is evaluated where the tile actually is.
    """
    img = np.asarray(image)
    if img.ndim != 2:
        raise ValueError(f"expected a 2-D tile, got {img.shape}")
    k = north_up_rotation_k(corners, line, sample)
    rotated = np.ascontiguousarray(np.rot90(img, k)) if k else img
    tf = _rot90_transform(img.shape, k)
    along, cross = orientation_signature(corners)
    return NorthUp(image=rotated, k=k, forward=tf, record={
        "quarter_turns_ccw": int(k),
        "orientation_signature_along_cross": [along, cross],
        "evaluated_at_frame_pixel": [float(line), float(sample)],
        "source": "archive named corner columns via the bilinear frame map; "
                  "no pixel value read; no interpolation",
    })
