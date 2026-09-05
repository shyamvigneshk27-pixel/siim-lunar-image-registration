"""B4X -- XFeat (accelerated features), a second licensable learned engine.

Why a second learned engine (next-session plan R1, R2)
-------------------------------------------------------
One learned engine that agrees with itself is one opinion. Two engines that
share no detector, no descriptor and no assignment, and still agree on a
transform, are independent evidence -- the cheapest verifier available
against the per-image gauge error that loop closure cannot see (ADR-0011 N1,
``siim.pipeline.agreement``). XFeat is also 3-10x faster than DISK + LightGlue
on CPU, which is what makes a live registration in front of a judge feasible.

Licence (ADR-0008 audit, 2026-09-05)
------------------------------------
* Repository ``verlab/accelerated_features``: **Apache-2.0** (LICENSE file;
  Potje et al., CVPR 2024). The pretrained ``xfeat.pt`` is distributed from
  that repository under the same file tree; its README states no separate
  weight licence, which is recorded here as *inherits the repository licence,
  not separately asserted by the authors*.
* The model code is fetched by ``torch.hub`` from a **pinned commit**
  (``e92685f5``, 2025-01-15) rather than ``main``, so the engine cannot change
  underneath a recorded result, and cached under ``~/.cache/torch/hub``. This
  is executable code downloaded at first use -- stated, not hidden -- and the
  pin is what makes it the same code every time.

Matching
--------
XFeat's own sparse matcher is mutual-nearest-neighbour in descriptor cosine
similarity; ``min_cossim`` defaults to -1 (mutual only), matching the authors'
``match_xfeat`` default. The optional LighterGlue head is NOT used: it pulls a
second weight file from a GitHub release and adds a learned assignment whose
licence trail is one step longer, for no measured benefit here yet.

Harness identity
----------------
Same :class:`BaselineResult`, same unmodified LO-RANSAC, same rule downstream
as every other engine. ``ratios`` are NaN (no ratio test applies to a mutual
cosine matcher); ``distances`` carry ``1 - cosine``.
"""

from __future__ import annotations

import time
from functools import lru_cache

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..matching.rootsift import Features, MatchSet
from ..verification.ransac import RansacResult, ransac
from .rootsift_pipeline import BaselineResult

__all__ = ["XFEAT_HUB_REPO", "xfeat_available", "run_xfeat_baseline",
           "detect_xfeat", "match_xfeat"]

#: Pinned to a commit, never to ``main``.
XFEAT_HUB_REPO = "verlab/accelerated_features:e92685f57f8318b18725c5c8c0bd28c7fe188d9a"


def xfeat_available() -> bool:
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def _model(max_keypoints: int = 4096):
    import torch
    torch.set_grad_enabled(False)
    m = torch.hub.load(XFEAT_HUB_REPO, "XFeat", pretrained=True, top_k=max_keypoints,
                       trust_repo=True, verbose=False)
    return m.eval()


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
    # XFeat's first layer is an InstanceNorm, so the absolute scale is
    # immaterial; a single grey channel is accepted by its parser.
    return torch.from_numpy(img.astype(np.float32))[None, None]


def detect_xfeat(image: ArrayLike, *, max_keypoints: int = 4096) -> Features:
    """XFeat keypoints and 64-d descriptors as the project's ``Features``."""
    import torch
    model = _model(max_keypoints)
    t = _to_tensor(image)
    h, w = t.shape[-2:]
    with torch.inference_mode():
        out = model.detectAndCompute(t, top_k=max_keypoints)[0]
    pts = out["keypoints"].cpu().numpy().astype(np.float64)
    desc = out["descriptors"].cpu().numpy().astype(np.float32)
    score = out["scores"].cpu().numpy().astype(np.float64)
    inside = (pts[:, 0] >= 0) & (pts[:, 0] <= w - 1) & (pts[:, 1] >= 0) & (pts[:, 1] <= h - 1)
    pts, desc, score = pts[inside], desc[inside], score[inside]
    return Features(points=pts, descriptors=desc, scales=np.ones(len(pts)),
                    angles=np.zeros(len(pts)), responses=score)


def match_xfeat(src: Features, dst: Features, *, min_cossim: float = -1.0) -> MatchSet:
    """Mutual-nearest-neighbour cosine matching, XFeat's own sparse matcher."""
    import torch
    if len(src) == 0 or len(dst) == 0:
        z = np.zeros(0)
        return MatchSet(np.zeros(0, np.int64), np.zeros(0, np.int64),
                        np.zeros((0, 2)), np.zeros((0, 2)), z, z)
    model = _model()
    d1 = torch.from_numpy(src.descriptors)
    d2 = torch.from_numpy(dst.descriptors)
    with torch.inference_mode():
        i0, i1 = model.match(d1, d2, min_cossim=min_cossim)
        cos = (d1[i0] * d2[i1]).sum(dim=1)
    i0 = i0.cpu().numpy().astype(np.int64)
    i1 = i1.cpu().numpy().astype(np.int64)
    cos = cos.cpu().numpy().astype(np.float64)
    return MatchSet(idx_src=i0, idx_dst=i1, src_points=src.points[i0],
                    dst_points=dst.points[i1], ratios=np.full(len(i0), np.nan),
                    distances=1.0 - cos)


def run_xfeat_baseline(source: ArrayLike, reference: ArrayLike, *, model: str = "affine",
                       ransac_threshold: float = 3.0, seed: int = 0,
                       max_keypoints: int = 4096, min_cossim: float = -1.0,
                       **_ignored) -> BaselineResult:
    """B4X end to end: XFeat -> mutual cosine matching -> unmodified LO-RANSAC."""
    timings: dict[str, float | str] = {"engine": f"B4X XFeat(mnn, {XFEAT_HUB_REPO.split(':')[1][:8]})"}
    t0 = time.perf_counter()
    f_src = detect_xfeat(source, max_keypoints=max_keypoints)
    f_dst = detect_xfeat(reference, max_keypoints=max_keypoints)
    timings["detect_describe_s"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    matches = match_xfeat(f_src, f_dst, min_cossim=min_cossim)
    timings["match_s"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    if len(matches) >= 3:
        rres = ransac(matches.src_points, matches.dst_points, model=model,
                      threshold=ransac_threshold, seed=seed)
    else:
        rres = RansacResult(transform=None, model=model, success=False,
                            reason=f"only {len(matches)} mutual XFeat matches")
    timings["ransac_s"] = time.perf_counter() - t0
    timings["total_s"] = sum(v for k, v in timings.items() if k != "engine")
    return BaselineResult(src_features=f_src, dst_features=f_dst, matches=matches,
                          ransac=rres, runtime=timings)
