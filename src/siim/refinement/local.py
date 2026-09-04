"""Per-correspondence sub-pixel refinement by local area matching (EXP-010).

What this is
------------
Given a source image, a reference image, an estimated transform ``T`` and a
set of source points, each point's reference location is refined by measuring
the residual translation between a source patch **warped by T into the
reference grid** and the reference patch at the predicted location. If ``T``
is exactly right the residual is zero; otherwise the refined reference point is
``T(p) + shift``.

Two estimators, both from OpenCV, both restricted to a pure translation so
that they cannot absorb what the global model already explains:

* ``ecc``   -- Evangelidis & Psarakis ECC, ``MOTION_TRANSLATION``; the returned
  correlation coefficient is the confidence.
* ``phase`` -- Fourier phase correlation with a Hanning window; the response
  value is the confidence.

What this is NOT
----------------
Not an accuracy. The shift is measured between two image patches, and a patch
under a different Sun carries shading edges that have *moved* on the ground;
the refiner will lock onto them (EXP-010 H2). A refined point is only as
correct as the patch content is geometric, and EXP-010 exists to measure that.

Conventions (contract C1-C5)
----------------------------
Points are ``(x, y)`` with integer values at pixel centres. The source patch
is produced by :func:`siim.geometry.warp` with the forward transform, so the
half-pixel bookkeeping is the geometry layer's, not re-derived here. ECC and
phase correlation are called in the same orientation as baseline B5
(``template = source patch, input = reference patch``), so a positive shift
means "the reference content lies further along +x/+y than T predicts".
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..geometry import Transform, translation, warp

__all__ = ["Refinement", "refine_correspondences"]


@dataclass(frozen=True)
class Refinement:
    """Refined reference points and how much each one moved."""

    dst_predicted: NDArray[np.float64]     # (N, 2)  T(p)
    dst_refined: NDArray[np.float64]       # (N, 2)  T(p) + shift, or T(p) where not ok
    shift: NDArray[np.float64]             # (N, 2)  measured residual, NaN where not ok
    confidence: NDArray[np.float64]        # (N,)   ECC coefficient / phase response
    ok: NDArray[np.bool_]                  # (N,)   converged on a fully valid patch
    method: str
    window: int


def _prep(patch: NDArray) -> NDArray[np.float32]:
    p = np.asarray(patch, dtype=np.float64)
    finite = np.isfinite(p)
    if not finite.all():
        p = np.where(finite, p, float(np.nanmean(p)) if finite.any() else 0.0)
    p = p - p.mean()
    s = p.std()
    return (p / s if s > 1e-12 else p).astype(np.float32)


def refine_correspondences(source: ArrayLike, reference: ArrayLike, transform: Transform,
                           src_points: ArrayLike, *, window: int = 48,
                           method: str = "ecc", max_iterations: int = 50,
                           epsilon: float = 1e-5, max_shift: float | None = None) -> Refinement:
    """Refine each ``src_points`` correspondence to sub-pixel in the reference.

    ``max_shift`` (default ``window / 4``) rejects a refinement whose measured
    residual is implausibly large for a point RANSAC already accepted; such a
    point is returned with ``ok = False`` and its predicted location unchanged.
    """
    if method not in ("ecc", "phase"):
        raise ValueError(f"unknown method {method!r}")
    if window < 8 or window % 2:
        raise ValueError("window must be an even integer >= 8")
    src = np.asarray(source, dtype=np.float64)
    ref = np.asarray(reference, dtype=np.float64)
    pts = np.asarray(src_points, dtype=np.float64).reshape(-1, 2)
    n = pts.shape[0]
    max_shift = window / 4.0 if max_shift is None else float(max_shift)

    predicted = transform.apply(pts) if n else np.zeros((0, 2))
    refined = predicted.copy()
    shift = np.full((n, 2), np.nan)
    conf = np.full(n, np.nan)
    ok = np.zeros(n, dtype=bool)
    h, w = ref.shape
    half = window // 2
    hann = cv2.createHanningWindow((window, window), cv2.CV_32F) if method == "phase" else None
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, max_iterations, epsilon)

    for i in range(n):
        qx, qy = predicted[i]
        if not (np.isfinite(qx) and np.isfinite(qy)):
            continue
        ox = int(round(qx)) - half
        oy = int(round(qy)) - half
        if ox < 0 or oy < 0 or ox + window > w or oy + window > h:
            continue
        ref_patch = ref[oy:oy + window, ox:ox + window]
        # Source patch on the reference patch's integer grid: patch (u, v) <->
        # reference (ox + u, oy + v) <-> source T^-1(...). The geometry layer's
        # warp takes the FORWARD map source -> patch, which is T then the shift
        # of the patch origin.
        to_patch = translation(-float(ox), -float(oy)) @ transform
        src_patch, valid = warp(src, to_patch, out_shape=(window, window), order=3, cval=np.nan)
        if valid.mean() < 0.98 or not np.isfinite(ref_patch).mean() > 0.98:
            continue
        a = _prep(src_patch)
        b = _prep(ref_patch)
        try:
            if method == "ecc":
                wm = np.eye(2, 3, dtype=np.float32)
                cc, wm = cv2.findTransformECC(a, b, wm, cv2.MOTION_TRANSLATION, criteria, None, 5)
                dx, dy, c = float(wm[0, 2]), float(wm[1, 2]), float(cc)
            else:
                (dx, dy), resp = cv2.phaseCorrelate(a.astype(np.float64), b.astype(np.float64),
                                                    hann.astype(np.float64))
                c = float(resp)
        except cv2.error:
            continue
        if not (np.isfinite(dx) and np.isfinite(dy)) or np.hypot(dx, dy) > max_shift:
            continue
        shift[i] = (dx, dy)
        conf[i] = c
        refined[i] = (qx + dx, qy + dy)
        ok[i] = True

    return Refinement(dst_predicted=predicted, dst_refined=refined, shift=shift,
                      confidence=conf, ok=ok, method=method, window=window)
