"""Baseline B1: RootSIFT + ratio test + mutual consistency + LO-RANSAC.

The reference classical pipeline (ANALYSIS §E.1). Deliberately implemented
well -- RootSIFT rather than plain SIFT, mutual-nearest consistency as well as
the ratio test, LO-RANSAC rather than vanilla RANSAC -- because spec §49
forbids sabotaging a baseline and §E.2 measures our eventual contribution as
a delta over it. A weak B1 would flatter us and prove nothing.

This is the "vanilla" arm of the §E.2 comparison: naive protocol, no scale
normalisation, no illumination-robust representation, no tiling, no coverage
selection. Those are the stages EXP-006 onward will add and measure.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..geometry import Transform
from ..matching.rootsift import Features, MatchSet, detect_and_describe, match_descriptors
from ..verification.ransac import RansacResult, ransac

__all__ = ["BaselineResult", "run_rootsift_baseline"]


@dataclass(frozen=True)
class BaselineResult:
    """Everything the baseline produced, including intermediate stages."""

    src_features: Features
    dst_features: Features
    matches: MatchSet
    ransac: RansacResult
    runtime: dict[str, float] = field(default_factory=dict)

    @property
    def transform(self) -> Transform | None:
        return self.ransac.transform

    @property
    def inlier_mask(self) -> NDArray[np.bool_]:
        return self.ransac.inlier_mask

    @property
    def inlier_points(self) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
        m = self.ransac.inlier_mask
        if m.size == 0:
            return np.zeros((0, 2)), np.zeros((0, 2))
        return self.matches.src_points[m], self.matches.dst_points[m]

    @property
    def success(self) -> bool:
        return self.ransac.success


def run_rootsift_baseline(
    source: ArrayLike,
    reference: ArrayLike,
    *,
    model: str = "affine",
    ratio: float = 0.8,
    mutual: bool = True,
    ransac_threshold: float = 3.0,
    root_sift: bool = True,
    seed: int = 0,
    contrast_threshold: float = 0.04,
) -> BaselineResult:
    """Run the classical baseline end to end and time each stage.

    ``model`` defaults to ``affine`` following the SAR-optical benchmark
    (sources.md S4), which measured affine beating homography on cross-modal
    satellite pairs (12.3 -> 9.7 px mean error). Whether that ordering holds
    for lunar data is an open question -- EXP-009 tests it. It is a
    provisional default, not a settled result.
    """
    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    f_src = detect_and_describe(
        source, root_sift=root_sift, contrast_threshold=contrast_threshold
    )
    f_dst = detect_and_describe(
        reference, root_sift=root_sift, contrast_threshold=contrast_threshold
    )
    timings["detect_describe_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    matches = match_descriptors(f_src, f_dst, ratio=ratio, mutual=mutual)
    timings["match_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    rres = ransac(
        matches.src_points,
        matches.dst_points,
        model=model,
        threshold=ransac_threshold,
        seed=seed,
    )
    timings["ransac_s"] = time.perf_counter() - t0
    timings["total_s"] = sum(timings.values())

    return BaselineResult(
        src_features=f_src,
        dst_features=f_dst,
        matches=matches,
        ransac=rres,
        runtime=timings,
    )
