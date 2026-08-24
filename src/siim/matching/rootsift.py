"""SIFT detection with RootSIFT descriptors, ratio test and mutual consistency.

This is baseline **B1** (ANALYSIS §E.1) -- the reference classical method that
everything else must beat, implemented properly rather than weakly. Spec §49
forbids sabotaging a baseline, and a strong B1 makes our protocol contribution
look *better*, not worse, because the improvement is measured as a delta over
it (§E.2).

RootSIFT
--------
L1-normalise the descriptor, then take the element-wise square root
(Arandjelovic & Zisserman, CVPR 2012). The Euclidean distance between two
RootSIFT vectors then equals the Hellinger distance between the original
histograms, which suits histogram data better than L2 does. It is a two-line
change with no runtime cost and it consistently helps, so using plain SIFT as
the baseline would be an artificially weak comparison.

The known limitation, stated up front
-------------------------------------
SIFT descriptors bin gradient orientation over [0, 2*pi). Under a ~180 degree
Sun-azimuth change the intensity gradient across a crater rim reverses, so
corresponding descriptors differ by pi and mismatch *systematically* rather
than noisily (ANALYSIS §B2). This is structural, not a tuning problem: no
ratio threshold repairs it. EXP-001 measures how far that goes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = ["Features", "MatchSet", "detect_and_describe", "match_descriptors"]


@dataclass(frozen=True)
class Features:
    """Keypoints and descriptors for one image."""

    #: (N, 2) keypoint locations in (x, y), obeying the coordinate contract.
    points: NDArray[np.float64]
    #: (N, 128) RootSIFT (or SIFT) descriptors, float32.
    descriptors: NDArray[np.float32]
    scales: NDArray[np.float64] = field(default_factory=lambda: np.zeros(0))
    angles: NDArray[np.float64] = field(default_factory=lambda: np.zeros(0))
    responses: NDArray[np.float64] = field(default_factory=lambda: np.zeros(0))

    def __len__(self) -> int:
        return int(self.points.shape[0])


@dataclass(frozen=True)
class MatchSet:
    """Putative correspondences between two feature sets."""

    #: (M,) indices into the source Features.
    idx_src: NDArray[np.int64]
    #: (M,) indices into the reference Features.
    idx_dst: NDArray[np.int64]
    #: (M, 2) source points, (x, y).
    src_points: NDArray[np.float64]
    #: (M, 2) reference points, (x, y).
    dst_points: NDArray[np.float64]
    #: (M,) Lowe ratio per match; lower is more distinctive.
    ratios: NDArray[np.float64]
    #: (M,) descriptor distance to the best neighbour.
    distances: NDArray[np.float64]

    def __len__(self) -> int:
        return int(self.idx_src.shape[0])


def _to_uint8(image: ArrayLike) -> NDArray[np.uint8]:
    """Convert a float image to the uint8 that OpenCV's SIFT requires.

    Images already in [0, 1] are scaled; anything else is min-max stretched.
    The stretch is recorded as a deliberate choice: SIFT is invariant to
    affine intensity change anyway, so this cannot alter which features are
    found, only their numerical representation.
    """
    img = np.asarray(image)
    if img.dtype == np.uint8:
        return img
    img = img.astype(np.float64)
    finite = img[np.isfinite(img)]
    if finite.size == 0:
        return np.zeros(img.shape, dtype=np.uint8)
    lo, hi = float(finite.min()), float(finite.max())
    if 0.0 <= lo and hi <= 1.0:
        scaled = img * 255.0
    elif hi - lo < 1e-12:
        scaled = np.zeros_like(img)
    else:
        scaled = (img - lo) / (hi - lo) * 255.0
    return np.clip(np.nan_to_num(scaled), 0, 255).astype(np.uint8)


def detect_and_describe(
    image: ArrayLike,
    *,
    root_sift: bool = True,
    n_features: int = 0,
    contrast_threshold: float = 0.04,
    edge_threshold: float = 10.0,
    sigma: float = 1.6,
    n_octave_layers: int = 3,
    mask: ArrayLike | None = None,
) -> Features:
    """Detect SIFT keypoints and compute (Root)SIFT descriptors.

    Parameters
    ----------
    n_features
        0 means unlimited. Capping it makes OpenCV retain the strongest
        responses, which concentrates keypoints in high-contrast terrain --
        precisely the spatial bias spec §15 forbids. Left uncapped here so
        that coverage is measured honestly rather than being pre-damaged.
    """
    img = _to_uint8(image)
    msk = None if mask is None else np.asarray(mask).astype(np.uint8) * 255

    sift = cv2.SIFT_create(
        nfeatures=n_features,
        nOctaveLayers=n_octave_layers,
        contrastThreshold=contrast_threshold,
        edgeThreshold=edge_threshold,
        sigma=sigma,
    )
    kps, desc = sift.detectAndCompute(img, msk)

    if desc is None or len(kps) == 0:
        return Features(
            points=np.zeros((0, 2)),
            descriptors=np.zeros((0, 128), dtype=np.float32),
        )

    desc = desc.astype(np.float32)
    if root_sift:
        # L1-normalise, then square-root: L2 on the result == Hellinger.
        l1 = np.abs(desc).sum(axis=1, keepdims=True)
        desc = np.sqrt(desc / np.maximum(l1, 1e-12))

    # OpenCV keypoints are already (x, y) -- matching contract C1.
    return Features(
        points=np.array([kp.pt for kp in kps], dtype=np.float64),
        descriptors=desc,
        scales=np.array([kp.size for kp in kps], dtype=np.float64),
        angles=np.array([kp.angle for kp in kps], dtype=np.float64),
        responses=np.array([kp.response for kp in kps], dtype=np.float64),
    )


def match_descriptors(
    src: Features,
    dst: Features,
    *,
    ratio: float = 0.8,
    mutual: bool = True,
) -> MatchSet:
    """Match descriptors with Lowe's ratio test and mutual-nearest consistency.

    Parameters
    ----------
    ratio
        Lowe's threshold on ``d1 / d2``. Rejects matches whose best neighbour
        is not much closer than the second-best, i.e. ambiguous ones. On
        repetitive crater terrain many genuinely ambiguous matches exist, and
        this test is the *only* defence before geometry -- which is why
        repetitive scenes are in the EXP-001 challenge set.
    mutual
        Require ``i -> j`` and ``j -> i`` to agree. This costs a second kNN
        pass and removes many-to-one matches. It is a cheap, independent
        consistency check, and unlike the ratio test it constrains the
        *reverse* direction, so the two catch different errors.
    """
    if len(src) == 0 or len(dst) == 0:
        empty_i = np.zeros(0, dtype=np.int64)
        empty_f = np.zeros(0, dtype=np.float64)
        return MatchSet(empty_i, empty_i, np.zeros((0, 2)), np.zeros((0, 2)), empty_f, empty_f)

    matcher = cv2.BFMatcher(cv2.NORM_L2)
    k = 2 if len(dst) >= 2 else 1
    knn = matcher.knnMatch(src.descriptors, dst.descriptors, k=k)

    idx_s, idx_d, ratios, dists = [], [], [], []
    for cand in knn:
        if len(cand) == 0:
            continue
        best = cand[0]
        if len(cand) >= 2:
            second = cand[1].distance
            r = best.distance / second if second > 1e-12 else 0.0
            if r >= ratio:
                continue
        else:
            r = 0.0
        idx_s.append(best.queryIdx)
        idx_d.append(best.trainIdx)
        ratios.append(r)
        dists.append(best.distance)

    if mutual and idx_s:
        rev = matcher.knnMatch(dst.descriptors, src.descriptors, k=1)
        back = {m[0].queryIdx: m[0].trainIdx for m in rev if len(m) > 0}
        keep = [n for n, (i, j) in enumerate(zip(idx_s, idx_d)) if back.get(j, -1) == i]
        idx_s = [idx_s[n] for n in keep]
        idx_d = [idx_d[n] for n in keep]
        ratios = [ratios[n] for n in keep]
        dists = [dists[n] for n in keep]

    ia = np.asarray(idx_s, dtype=np.int64)
    ib = np.asarray(idx_d, dtype=np.int64)
    return MatchSet(
        idx_src=ia,
        idx_dst=ib,
        src_points=src.points[ia] if ia.size else np.zeros((0, 2)),
        dst_points=dst.points[ib] if ib.size else np.zeros((0, 2)),
        ratios=np.asarray(ratios, dtype=np.float64),
        distances=np.asarray(dists, dtype=np.float64),
    )
