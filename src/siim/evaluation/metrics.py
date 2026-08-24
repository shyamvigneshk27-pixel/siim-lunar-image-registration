"""Correspondence and registration metrics, measured against ground truth.

The point of this module
------------------------
It computes two quantities side by side that are routinely confused:

``reported_inlier_ratio``
    What RANSAC says: the fraction of putative matches consistent with the
    model it found. This is the number almost every paper and demo quotes.
    It is a measure of **self-consistency**.

``true_inlier_precision``
    The fraction of those same inliers that are *actually correct*, judged
    against the known ground-truth transform. This is a measure of
    **correctness**.

When the correspondences contain a large, mutually consistent but wrong
subset -- repetitive crater terrain being the canonical generator (ANALYSIS
§B6) -- the first can be near 1.0 while the second is near 0.0. The system
then reports total confidence in a completely wrong registration.

Quantifying that gap is the whole reason EXP-001 exists before any learned
matcher is considered. A pipeline that cannot tell these apart will
eventually publish a wrong answer with a great-looking metric attached.

Availability
------------
``true_*`` fields require a ground-truth transform and are therefore
available on synthetic data only. On real pairs the substitutes are the
held-out, cycle-consistency and loop-closure estimators of ANALYSIS §F.1 --
which is exactly why those exist.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..geometry import Transform, as_points, endpoint_error, transfer_residuals

__all__ = [
    "CorrespondenceMetrics",
    "FailureMode",
    "correspondence_metrics",
    "classify_failure",
]


class FailureMode:
    """Failure taxonomy (spec §51). String constants, kept greppable."""

    NONE = "none"
    TOO_FEW_KEYPOINTS = "too_few_keypoints"
    TOO_FEW_PUTATIVE = "too_few_putative_matches"
    NO_MODEL = "no_model_found"
    COHERENT_WRONG = "coherent_wrong_solution"
    LOW_PRECISION = "low_inlier_precision"
    POOR_COVERAGE = "poor_spatial_coverage"
    HIGH_ERROR = "high_transform_error"


@dataclass(frozen=True)
class CorrespondenceMetrics:
    """Match-level and transform-level quality, with GT where available."""

    # -- counts ---------------------------------------------------------
    n_keypoints_src: int
    n_keypoints_dst: int
    n_putative: int
    n_inliers: int

    # -- what the pipeline reports about itself (circular) ---------------
    #: RANSAC's own inlier ratio. SELF-CONSISTENCY, NOT CORRECTNESS.
    reported_inlier_ratio: float
    #: RMSE of inliers under the fitted model. A fit residual (ANALYSIS §A.3).
    reported_inlier_rmse: float

    # -- ground truth (synthetic data only) -------------------------------
    #: Fraction of putative matches that are actually correct.
    true_putative_precision: float = float("nan")
    #: Fraction of RANSAC *inliers* that are actually correct. THE HONEST ONE.
    true_inlier_precision: float = float("nan")
    #: Of the truly-correct putative matches, the fraction RANSAC retained.
    true_inlier_recall: float = float("nan")
    n_true_correct_putative: int = -1
    n_true_correct_inliers: int = -1

    #: True correspondence error ||T_gt(p) - q|| over the inlier set, in px.
    true_error_median: float = float("nan")
    true_error_mean: float = float("nan")
    true_error_p90: float = float("nan")
    true_error_max: float = float("nan")

    #: Endpoint error between the estimated and true transform, on a grid.
    #: Measures the MAP, including where no correspondences were found.
    transform_error_median: float = float("nan")
    transform_error_p90: float = float("nan")
    transform_error_max: float = float("nan")

    #: reported_inlier_ratio - true_inlier_precision. Large and positive means
    #: the pipeline is confidently wrong.
    confidence_gap: float = float("nan")

    runtime: dict[str, float] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def __repr__(self) -> str:  # pragma: no cover - display only
        return (
            f"CorrespondenceMetrics(putative={self.n_putative}, "
            f"inliers={self.n_inliers}, reported_ratio={self.reported_inlier_ratio:.3f}, "
            f"true_precision={self.true_inlier_precision:.3f}, "
            f"transform_err_median={self.transform_error_median:.3f}px)"
        )


def correspondence_metrics(
    src_points: ArrayLike,
    dst_points: ArrayLike,
    inlier_mask: ArrayLike,
    *,
    gt_transform: Transform | None,
    estimated_transform: Transform | None,
    shape: tuple[int, int],
    n_keypoints_src: int,
    n_keypoints_dst: int,
    reported_inlier_rmse: float = float("nan"),
    correct_threshold: float = 3.0,
    grid_step: int = 16,
    runtime: dict[str, float] | None = None,
) -> CorrespondenceMetrics:
    """Score a correspondence set, using ground truth when it is available.

    Parameters
    ----------
    correct_threshold
        Distance in reference pixels within which a putative match counts as
        truly correct. Set it equal to the RANSAC threshold so that
        ``reported_inlier_ratio`` and ``true_inlier_precision`` are judged on
        the same yardstick -- otherwise the comparison between them, which is
        the point of this module, is not like-for-like.
    """
    p = as_points(src_points)
    q = as_points(dst_points)
    mask = np.asarray(inlier_mask, dtype=bool)
    n_put = int(p.shape[0])
    n_in = int(mask.sum()) if mask.size else 0

    base = dict(
        n_keypoints_src=int(n_keypoints_src),
        n_keypoints_dst=int(n_keypoints_dst),
        n_putative=n_put,
        n_inliers=n_in,
        reported_inlier_ratio=(n_in / n_put) if n_put else 0.0,
        reported_inlier_rmse=float(reported_inlier_rmse),
        runtime=dict(runtime or {}),
    )

    if gt_transform is None or n_put == 0:
        return CorrespondenceMetrics(**base)

    # Ground-truth correctness of every putative match.
    gt_err = transfer_residuals(gt_transform, p, q)
    correct = gt_err <= correct_threshold
    n_correct_put = int(correct.sum())
    n_correct_in = int((correct & mask).sum()) if mask.size else 0

    inlier_gt_err = gt_err[mask] if n_in else np.zeros(0)
    finite = inlier_gt_err[np.isfinite(inlier_gt_err)]

    if estimated_transform is not None:
        tf_err = endpoint_error(estimated_transform, gt_transform, shape, step=grid_step)
        tf_median, tf_p90, tf_max = tf_err.median, tf_err.p90, tf_err.max
    else:
        tf_median = tf_p90 = tf_max = float("inf")

    true_inlier_precision = (n_correct_in / n_in) if n_in else 0.0

    return CorrespondenceMetrics(
        **base,
        true_putative_precision=n_correct_put / n_put,
        true_inlier_precision=true_inlier_precision,
        true_inlier_recall=(n_correct_in / n_correct_put) if n_correct_put else 0.0,
        n_true_correct_putative=n_correct_put,
        n_true_correct_inliers=n_correct_in,
        true_error_median=float(np.median(finite)) if finite.size else float("inf"),
        true_error_mean=float(finite.mean()) if finite.size else float("inf"),
        true_error_p90=float(np.percentile(finite, 90)) if finite.size else float("inf"),
        true_error_max=float(finite.max()) if finite.size else float("inf"),
        transform_error_median=tf_median,
        transform_error_p90=tf_p90,
        transform_error_max=tf_max,
        confidence_gap=base["reported_inlier_ratio"] - true_inlier_precision,
    )


def classify_failure(
    m: CorrespondenceMetrics,
    *,
    min_keypoints: int = 30,
    min_putative: int = 10,
    min_inliers: int = 8,
    max_transform_error: float = 3.0,
    min_true_precision: float = 0.5,
    confidence_gap_threshold: float = 0.3,
    max_coverage_gap: float = 0.25,
    coverage: Any | None = None,
) -> str:
    """Assign a failure mode from the taxonomy (spec §51).

    Order matters: the most diagnostic cause is reported, not merely the first
    threshold crossed. ``COHERENT_WRONG`` is checked before ``HIGH_ERROR``
    because "confidently wrong" and "known to be wrong" are operationally very
    different failures -- the first is the dangerous one.
    """
    if min(m.n_keypoints_src, m.n_keypoints_dst) < min_keypoints:
        return FailureMode.TOO_FEW_KEYPOINTS
    if m.n_putative < min_putative:
        return FailureMode.TOO_FEW_PUTATIVE
    if m.n_inliers < min_inliers:
        return FailureMode.NO_MODEL

    if np.isfinite(m.confidence_gap):
        wrong = (
            not np.isfinite(m.transform_error_median)
            or m.transform_error_median > max_transform_error
        )
        if wrong and m.confidence_gap > confidence_gap_threshold:
            return FailureMode.COHERENT_WRONG
        if m.true_inlier_precision < min_true_precision:
            return FailureMode.LOW_PRECISION

    if coverage is not None and coverage.max_uncovered_disc_ratio > max_coverage_gap:
        return FailureMode.POOR_COVERAGE

    if (
        not np.isfinite(m.transform_error_median)
        or m.transform_error_median > max_transform_error
    ):
        return FailureMode.HIGH_ERROR

    return FailureMode.NONE
