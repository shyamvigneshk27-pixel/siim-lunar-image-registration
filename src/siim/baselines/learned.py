"""B4L -- DISK + LightGlue, a licensable learned engine behind the same harness.

Licence (ADR-0008 audit, 2026-09-04)
------------------------------------
* DISK code and ``depth`` weights: Apache-2.0 (Tyszkiewicz et al., NeurIPS 2020).
* LightGlue code and ``disk`` weights: Apache-2.0 (Lindenberger et al., ICCV 2023).
* Delivered through ``kornia`` (Apache-2.0) on CPU via ``torch``.

SuperPoint and SuperGlue are **not** used: their weights are restricted to
non-commercial research use, which a deliverable to ISRO cannot carry.

Harness identity
----------------
The engine returns the same :class:`BaselineResult` as every other baseline and
ends in the same unmodified LO-RANSAC, so a comparison with B1 compares
matchers rather than harnesses (ANALYSIS section E.2). LightGlue performs its
own assignment with a learned confidence, so the ratio test and mutual check
of B1 do not apply; ``ratios`` are recorded as NaN and ``distances`` carry
``1 - confidence``.

Determinism
-----------
CPU inference at fixed inputs is deterministic for these models. EXP-007
records two runs of one edge to demonstrate it rather than assert it.
"""

from __future__ import annotations

import time
from functools import lru_cache

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..matching.rootsift import Features, MatchSet
from ..verification.ransac import RansacResult, ransac
from .rootsift_pipeline import BaselineResult

__all__ = ["learned_available", "run_disk_lightglue_baseline",
           "detect_disk", "match_lightglue"]


def learned_available() -> bool:
    try:
        import kornia  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def _models():
    import kornia.feature as KF
    import torch
    torch.set_grad_enabled(False)
    disk = KF.DISK.from_pretrained("depth").eval()
    glue = KF.LightGlueMatcher("disk").eval()
    return disk, glue


def _to_tensor(image: ArrayLike):
    import torch
    img = np.asarray(image, dtype=np.float64)
    if img.ndim != 2:
        raise ValueError(f"expected a 2-D image, got {img.shape}")
    finite = img[np.isfinite(img)]
    if finite.size == 0:
        img = np.zeros_like(img)
    else:
        lo, hi = float(finite.min()), float(finite.max())
        if not (0.0 <= lo and hi <= 1.0):
            img = (img - lo) / (hi - lo) if hi > lo else np.zeros_like(img)
        img = np.nan_to_num(img, nan=float(np.median(finite)))
    t = torch.from_numpy(img.astype(np.float32))[None, None]
    return t.repeat(1, 3, 1, 1)


def detect_disk(image: ArrayLike, *, max_keypoints: int = 4096) -> Features:
    """DISK keypoints and 128-d descriptors, as the project's ``Features``."""
    import torch
    disk, _ = _models()
    t = _to_tensor(image)
    h, w = t.shape[-2:]
    with torch.inference_mode():
        out = disk(t, n=max_keypoints, window_size=5, score_threshold=0.0,
                   pad_if_not_divisible=True)[0]
    pts = out.keypoints.cpu().numpy().astype(np.float64)
    desc = out.descriptors.cpu().numpy().astype(np.float32)
    score = out.detection_scores.cpu().numpy().astype(np.float64)
    inside = (pts[:, 0] >= 0) & (pts[:, 0] <= w - 1) & (pts[:, 1] >= 0) & (pts[:, 1] <= h - 1)
    pts, desc, score = pts[inside], desc[inside], score[inside]
    return Features(points=pts, descriptors=desc,
                    scales=np.ones(len(pts)), angles=np.zeros(len(pts)),
                    responses=score)


def match_lightglue(src: Features, dst: Features,
                    src_shape: tuple[int, int], dst_shape: tuple[int, int]) -> MatchSet:
    """LightGlue assignment between two DISK feature sets."""
    import kornia.feature as KF
    import torch
    _, glue = _models()
    if len(src) == 0 or len(dst) == 0:
        z = np.zeros(0)
        return MatchSet(np.zeros(0, np.int64), np.zeros(0, np.int64),
                        np.zeros((0, 2)), np.zeros((0, 2)), z, z)
    kp1 = torch.from_numpy(src.points.astype(np.float32))[None]
    kp2 = torch.from_numpy(dst.points.astype(np.float32))[None]
    d1 = torch.from_numpy(src.descriptors)
    d2 = torch.from_numpy(dst.descriptors)
    lafs1 = KF.laf_from_center_scale_ori(kp1, torch.ones(1, kp1.shape[1], 1, 1))
    lafs2 = KF.laf_from_center_scale_ori(kp2, torch.ones(1, kp2.shape[1], 1, 1))
    with torch.inference_mode():
        dists, idxs = glue(d1, d2, lafs1, lafs2,
                           hw1=torch.tensor(src_shape), hw2=torch.tensor(dst_shape))
    idxs = idxs.cpu().numpy().astype(np.int64)
    dists = dists.cpu().numpy().astype(np.float64).ravel()
    if idxs.ndim != 2 or idxs.shape[0] == 0:
        z = np.zeros(0)
        return MatchSet(np.zeros(0, np.int64), np.zeros(0, np.int64),
                        np.zeros((0, 2)), np.zeros((0, 2)), z, z)
    i, j = idxs[:, 0], idxs[:, 1]
    return MatchSet(idx_src=i, idx_dst=j,
                    src_points=src.points[i], dst_points=dst.points[j],
                    ratios=np.full(len(i), np.nan), distances=dists[: len(i)])


def run_disk_lightglue_baseline(source: ArrayLike, reference: ArrayLike, *,
                                model: str = "affine", ransac_threshold: float = 3.0,
                                seed: int = 0, max_keypoints: int = 4096,
                                **_ignored) -> BaselineResult:
    """DISK + LightGlue + the unmodified LO-RANSAC. Same record as B1."""
    if not learned_available():
        raise RuntimeError(
            "B4L needs kornia and torch (both Apache-2.0): pip install kornia torch")
    src = np.asarray(source, float)
    dst = np.asarray(reference, float)
    t0 = time.perf_counter()
    fa = detect_disk(src, max_keypoints=max_keypoints)
    fb = detect_disk(dst, max_keypoints=max_keypoints)
    t1 = time.perf_counter()
    matches = match_lightglue(fa, fb, src.shape, dst.shape)
    t2 = time.perf_counter()
    if len(matches) >= 3:
        rres = ransac(matches.src_points, matches.dst_points, model=model,
                      threshold=ransac_threshold, seed=seed)
    else:
        rres = RansacResult(transform=None, model=model, success=False,
                            reason=f"only {len(matches)} LightGlue matches")
    t3 = time.perf_counter()
    return BaselineResult(
        src_features=fa, dst_features=fb, matches=matches, ransac=rres,
        runtime={"detect_describe_s": t1 - t0, "match_s": t2 - t1,
                 "ransac_s": t3 - t2, "total_s": t3 - t0,
                 "engine": "B4L DISK+LightGlue (kornia, CPU)"},
    )
