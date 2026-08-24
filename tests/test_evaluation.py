"""Tests for the evaluation harness: GT metrics, coverage, failure taxonomy.

This harness is the part of EXP-001 that outlives the baseline. If it is
wrong, every later comparison between matchers is wrong too -- and wrong in
the flattering direction, because a broken metric usually reports success.
"""

from __future__ import annotations

import numpy as np
import pytest

from siim.evaluation import (
    FailureMode,
    classify_failure,
    correspondence_metrics,
    coverage_metrics,
)
from siim.geometry import translation


def _metrics(src, dst, mask, gt, est, shape=(256, 256), **kw):
    return correspondence_metrics(
        src, dst, mask,
        gt_transform=gt, estimated_transform=est, shape=shape,
        n_keypoints_src=kw.pop("n_kp_src", 500),
        n_keypoints_dst=kw.pop("n_kp_dst", 500),
        **kw,
    )


class TestCorrespondenceMetrics:
    def test_perfect_matches_score_perfectly(self):
        rng = np.random.default_rng(1)
        gt = translation(5.0, -3.0)
        src = rng.uniform(0, 256, size=(100, 2))
        dst = gt.apply(src)
        m = _metrics(src, dst, np.ones(100, bool), gt, gt)
        assert m.true_putative_precision == 1.0
        assert m.true_inlier_precision == 1.0
        assert m.true_inlier_recall == 1.0
        assert m.transform_error_max < 1e-9
        assert m.confidence_gap == pytest.approx(0.0)

    def test_all_wrong_matches_are_caught_by_ground_truth(self):
        rng = np.random.default_rng(1)
        gt = translation(5.0, -3.0)
        wrong = translation(80.0, 0.0)
        src = rng.uniform(0, 256, size=(100, 2))
        dst = wrong.apply(src)
        m = _metrics(src, dst, np.ones(100, bool), gt, wrong)
        assert m.true_inlier_precision == 0.0
        # The pipeline reports total confidence in a completely wrong answer.
        assert m.reported_inlier_ratio == 1.0
        assert m.confidence_gap == pytest.approx(1.0)
        assert m.transform_error_median > 50

    def test_mixed_matches_give_intermediate_precision(self):
        rng = np.random.default_rng(1)
        gt = translation(5.0, -3.0)
        src = rng.uniform(0, 256, size=(100, 2))
        dst = gt.apply(src)
        dst[:30] += 40.0  # 30 wrong
        m = _metrics(src, dst, np.ones(100, bool), gt, gt)
        assert m.true_putative_precision == pytest.approx(0.70)
        assert m.n_true_correct_putative == 70

    def test_recall_counts_correct_matches_retained(self):
        rng = np.random.default_rng(1)
        gt = translation(5.0, -3.0)
        src = rng.uniform(0, 256, size=(100, 2))
        dst = gt.apply(src)
        mask = np.zeros(100, bool)
        mask[:40] = True  # RANSAC kept only 40 of 100 correct matches
        m = _metrics(src, dst, mask, gt, gt)
        assert m.true_inlier_recall == pytest.approx(0.40)
        assert m.true_inlier_precision == 1.0

    def test_no_ground_truth_leaves_true_fields_nan(self):
        rng = np.random.default_rng(1)
        src = rng.uniform(0, 256, size=(50, 2))
        m = _metrics(src, src, np.ones(50, bool), None, None)
        assert np.isnan(m.true_inlier_precision)
        assert np.isnan(m.confidence_gap)
        # ...but the self-reported quantities are still available.
        assert m.reported_inlier_ratio == 1.0

    def test_empty_match_set_is_handled(self):
        m = _metrics(np.zeros((0, 2)), np.zeros((0, 2)), np.zeros(0, bool),
                     translation(1.0, 1.0), None)
        assert m.n_putative == 0
        assert m.reported_inlier_ratio == 0.0

    def test_correct_threshold_is_respected(self):
        gt = translation(0.0, 0.0)
        src = np.array([[10.0, 10.0], [20.0, 20.0]])
        dst = np.array([[12.0, 10.0], [30.0, 20.0]])  # errors of 2 px and 10 px
        tight = _metrics(src, dst, np.ones(2, bool), gt, gt, correct_threshold=1.0)
        loose = _metrics(src, dst, np.ones(2, bool), gt, gt, correct_threshold=3.0)
        assert tight.true_putative_precision == 0.0
        assert loose.true_putative_precision == 0.5


class TestCoverage:
    def test_uniform_grid_has_small_largest_gap(self):
        xs, ys = np.meshgrid(np.arange(16, 256, 32), np.arange(16, 256, 32))
        pts = np.column_stack([xs.ravel(), ys.ravel()])
        cov = coverage_metrics(pts, (256, 256))
        assert cov.max_uncovered_disc_ratio < 0.12
        assert cov.grid_occupancy > 0.9
        assert cov.spatial_entropy > 0.9

    def test_clustered_points_have_a_large_gap_despite_many_points(self):
        """The exact case spec §27 and §29 warn about: many matches, bad coverage."""
        rng = np.random.default_rng(2)
        pts = rng.normal(loc=(40, 40), scale=8, size=(2000, 2))
        cov = coverage_metrics(pts, (256, 256))
        assert cov.n_points == 2000
        assert cov.max_uncovered_disc_ratio > 0.5
        assert cov.grid_occupancy < 0.2

    def test_entropy_can_look_fine_while_a_hole_remains(self):
        """Justifies ADR-0006: an average cannot bound a worst case."""
        rng = np.random.default_rng(3)
        pts = rng.uniform(0, 256, size=(600, 2))
        # Punch out one quadrant.
        pts = pts[~((pts[:, 0] > 128) & (pts[:, 1] > 128))]
        cov = coverage_metrics(pts, (256, 256))
        assert cov.spatial_entropy > 0.85, "entropy still looks healthy"
        assert cov.max_uncovered_disc_ratio > 0.2, "yet a large hole exists"

    def test_roi_restricts_scoring(self):
        pts = np.column_stack(
            [np.repeat(np.arange(8, 128, 16), 8), np.tile(np.arange(8, 128, 16), 8)]
        )
        roi = np.zeros((256, 256), bool)
        roi[:128, :128] = True
        inside = coverage_metrics(pts, (256, 256), roi=roi)
        whole = coverage_metrics(pts, (256, 256))
        # Same points score much better when only their own region is asked about.
        assert inside.max_uncovered_disc_ratio < whole.max_uncovered_disc_ratio

    def test_empty_point_set_is_worst_case(self):
        cov = coverage_metrics(np.zeros((0, 2)), (256, 256))
        assert cov.max_uncovered_disc_ratio == 1.0
        assert cov.grid_occupancy == 0.0

    def test_collinear_points_do_not_crash_hull(self):
        pts = np.column_stack([np.arange(10, 200, 10), np.full(19, 100.0)])
        cov = coverage_metrics(pts, (256, 256))
        assert cov.hull_ratio == 0.0
        assert np.isfinite(cov.max_uncovered_disc_ratio)

    def test_roi_shape_mismatch_rejected(self):
        with pytest.raises(ValueError, match="does not match"):
            coverage_metrics(np.zeros((5, 2)), (256, 256), roi=np.ones((10, 10), bool))


class TestFailureTaxonomy:
    def _m(self, **kw):
        defaults = dict(
            n_keypoints_src=500, n_keypoints_dst=500, n_putative=200, n_inliers=150,
            reported_inlier_ratio=0.75, reported_inlier_rmse=0.5,
            true_inlier_precision=0.99, transform_error_median=0.4, confidence_gap=0.0,
        )
        defaults.update(kw)
        from siim.evaluation.metrics import CorrespondenceMetrics

        return CorrespondenceMetrics(**defaults)

    def test_healthy_case_reports_no_failure(self):
        assert classify_failure(self._m()) == FailureMode.NONE

    def test_too_few_keypoints(self):
        assert (
            classify_failure(self._m(n_keypoints_src=5)) == FailureMode.TOO_FEW_KEYPOINTS
        )

    def test_too_few_putative(self):
        assert classify_failure(self._m(n_putative=3)) == FailureMode.TOO_FEW_PUTATIVE

    def test_no_model(self):
        assert classify_failure(self._m(n_inliers=4)) == FailureMode.NO_MODEL

    def test_coherent_wrong_solution_is_reported_before_high_error(self):
        """Confidently wrong and knowably wrong are different failures."""
        m = self._m(
            reported_inlier_ratio=0.95,
            true_inlier_precision=0.02,
            transform_error_median=64.0,
            confidence_gap=0.93,
        )
        assert classify_failure(m) == FailureMode.COHERENT_WRONG

    def test_high_error_without_false_confidence(self):
        m = self._m(
            reported_inlier_ratio=0.2,
            true_inlier_precision=0.9,
            transform_error_median=40.0,
            confidence_gap=-0.7,
        )
        assert classify_failure(m) == FailureMode.HIGH_ERROR

    def test_poor_coverage_is_detected(self):
        cov = coverage_metrics(
            np.random.default_rng(1).normal((30, 30), 5, size=(50, 2)), (256, 256)
        )
        assert classify_failure(self._m(), coverage=cov) == FailureMode.POOR_COVERAGE
