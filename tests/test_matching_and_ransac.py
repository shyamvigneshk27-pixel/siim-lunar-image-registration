"""Tests for RootSIFT feature matching and LO-RANSAC verification.

Two tests here are not checking that the code works -- they are checking that
a *dangerous property* of the method is present and documented, so nobody
later mistakes it for reliability:

* ``test_inlier_ratio_is_self_consistency_not_correctness``
* ``test_fit_rmse_collapses_when_inliers_approach_model_dof``

Both encode the headline finding of EXP-001.
"""

from __future__ import annotations

import numpy as np
import pytest

from siim.data import height_field, render
from siim.geometry import (
    affine,
    endpoint_error,
    estimate,
    similarity,
    translation,
    transfer_residuals,
)
from siim.matching import detect_and_describe, match_descriptors
from siim.verification import ransac


@pytest.fixture(scope="module")
def lunar_image():
    fld = height_field((320, 320), np.random.default_rng(21), scene="highlands")
    return render(fld, 315.0, 45.0, noise_std=0.002)


# ------------------------------------------------------------------ RootSIFT


class TestFeatures:
    def test_detects_features_on_terrain(self, lunar_image):
        f = detect_and_describe(lunar_image)
        assert len(f) > 100
        assert f.descriptors.shape == (len(f), 128)
        assert f.points.shape == (len(f), 2)

    def test_keypoints_are_xy_within_bounds(self, lunar_image):
        f = detect_and_describe(lunar_image)
        h, w = lunar_image.shape
        assert (f.points[:, 0] >= -0.5).all() and (f.points[:, 0] <= w - 0.5).all()
        assert (f.points[:, 1] >= -0.5).all() and (f.points[:, 1] <= h - 0.5).all()

    def test_rootsift_descriptors_are_unit_l2(self, lunar_image):
        """L1-normalise then sqrt => sum of squares is 1 by construction."""
        f = detect_and_describe(lunar_image, root_sift=True)
        norms = np.linalg.norm(f.descriptors, axis=1)
        assert np.allclose(norms, 1.0, atol=1e-5)

    def test_plain_sift_descriptors_are_not_unit_l2(self, lunar_image):
        f = detect_and_describe(lunar_image, root_sift=False)
        norms = np.linalg.norm(f.descriptors, axis=1)
        assert not np.allclose(norms, 1.0, atol=1e-3)

    def test_empty_image_returns_empty_features(self):
        f = detect_and_describe(np.zeros((64, 64)))
        assert len(f) == 0
        assert f.descriptors.shape == (0, 128)

    def test_intensity_scaling_does_not_change_detections(self, lunar_image):
        """SIFT is invariant to affine intensity change; confirm our uint8
        conversion does not accidentally break that."""
        a = detect_and_describe(lunar_image)
        b = detect_and_describe(lunar_image * 0.5 + 0.2)
        assert abs(len(a) - len(b)) / max(len(a), 1) < 0.15


class TestMatching:
    def test_identical_images_match_almost_everything(self, lunar_image):
        f = detect_and_describe(lunar_image)
        m = match_descriptors(f, f, ratio=0.8, mutual=True)
        assert len(m) > 0.5 * len(f)
        # A descriptor's nearest neighbour in its own set is itself.
        assert (m.idx_src == m.idx_dst).mean() > 0.99

    def test_ratio_test_filters_matches(self, lunar_image):
        f1 = detect_and_describe(lunar_image)
        f2 = detect_and_describe(np.roll(lunar_image, 7, axis=1))
        loose = match_descriptors(f1, f2, ratio=0.99, mutual=False)
        tight = match_descriptors(f1, f2, ratio=0.6, mutual=False)
        assert len(tight) < len(loose)

    def test_mutual_consistency_filters_matches(self, lunar_image):
        f1 = detect_and_describe(lunar_image)
        f2 = detect_and_describe(np.roll(lunar_image, 7, axis=1))
        assert len(match_descriptors(f1, f2, mutual=True)) <= len(
            match_descriptors(f1, f2, mutual=False)
        )

    def test_empty_inputs_are_handled(self, lunar_image):
        f = detect_and_describe(lunar_image)
        empty = detect_and_describe(np.zeros((32, 32)))
        assert len(match_descriptors(f, empty)) == 0
        assert len(match_descriptors(empty, f)) == 0

    def test_match_points_correspond_to_indices(self, lunar_image):
        f1 = detect_and_describe(lunar_image)
        f2 = detect_and_describe(np.roll(lunar_image, 5, axis=0))
        m = match_descriptors(f1, f2)
        assert np.allclose(m.src_points, f1.points[m.idx_src])
        assert np.allclose(m.dst_points, f2.points[m.idx_dst])


# -------------------------------------------------------------------- RANSAC


class TestRansac:
    @staticmethod
    def _data(rng, truth, n=200, outlier_frac=0.5, noise=0.2):
        src = rng.uniform(0, 400, size=(n, 2))
        dst = truth.apply(src) + rng.normal(0, noise, size=(n, 2))
        n_out = int(n * outlier_frac)
        dst[:n_out] = rng.uniform(0, 400, size=(n_out, 2))
        return src, dst, n_out

    def test_recovers_transform_with_heavy_outliers(self):
        rng = np.random.default_rng(3)
        truth = affine([[1.04, 0.05, 12.0], [-0.03, 1.01, -7.0]])
        src, dst, n_out = self._data(rng, truth, n=300, outlier_frac=0.6)
        res = ransac(src, dst, model="affine", threshold=2.0, seed=1)
        assert res.success
        assert res.n_inliers > 0.35 * 300
        assert endpoint_error(res.transform, truth, (400, 400), step=25).median < 1.0

    def test_outliers_are_excluded_from_the_inlier_set(self):
        rng = np.random.default_rng(3)
        truth = translation(9.0, -4.0)
        src, dst, n_out = self._data(rng, truth, n=200, outlier_frac=0.5)
        res = ransac(src, dst, model="translation", threshold=2.0, seed=1)
        # The first n_out entries were replaced with random junk.
        assert res.inlier_mask[:n_out].mean() < 0.1
        assert res.inlier_mask[n_out:].mean() > 0.85

    def test_insufficient_points_reported_not_raised(self):
        res = ransac(np.zeros((2, 2)), np.zeros((2, 2)), model="projective")
        assert not res.success
        assert "need >=" in res.reason

    def test_pure_noise_does_not_yield_a_confident_model(self):
        rng = np.random.default_rng(8)
        src = rng.uniform(0, 400, size=(150, 2))
        dst = rng.uniform(0, 400, size=(150, 2))
        res = ransac(src, dst, model="affine", threshold=1.0, seed=1)
        assert res.inlier_ratio < 0.25

    def test_deterministic_for_a_fixed_seed(self):
        rng = np.random.default_rng(3)
        truth = similarity(1.1, 0.05, 5.0, 2.0)
        src, dst, _ = self._data(rng, truth)
        a = ransac(src, dst, model="similarity", seed=42)
        b = ransac(src, dst, model="similarity", seed=42)
        assert a.n_inliers == b.n_inliers
        assert np.allclose(a.transform.matrix, b.transform.matrix)

    def test_unknown_model_rejected(self):
        with pytest.raises(ValueError, match="unknown model"):
            ransac(np.zeros((10, 2)), np.zeros((10, 2)), model="thin_plate_spline")

    def test_local_optimization_does_not_reduce_consensus(self):
        rng = np.random.default_rng(3)
        truth = affine([[1.02, 0.03, 6.0], [-0.02, 1.0, -3.0]])
        src, dst, _ = self._data(rng, truth, n=250, outlier_frac=0.4)
        with_lo = ransac(src, dst, "affine", threshold=2.0, seed=5, local_optimization=True)
        without = ransac(src, dst, "affine", threshold=2.0, seed=5, local_optimization=False)
        assert with_lo.n_inliers >= without.n_inliers

    # -- the two dangerous-property tests -------------------------------

    def test_inlier_ratio_is_self_consistency_not_correctness(self):
        """A large, mutually consistent WRONG subset wins, and looks great.

        70% of the correspondences follow a wrong transform, 30% the right
        one. RANSAC maximises consensus, so it finds the wrong one and reports
        a high inlier ratio. Nothing inside RANSAC can tell the difference --
        which is why ANALYSIS §F.1 builds evidence from outside the fit.
        """
        rng = np.random.default_rng(12)
        right = translation(3.0, 2.0)
        wrong = translation(64.0, 0.0)  # e.g. one crater-lattice period
        src = rng.uniform(0, 400, size=(200, 2))
        dst = np.where(
            (np.arange(200) < 140)[:, None], wrong.apply(src), right.apply(src)
        )

        res = ransac(src, dst, model="translation", threshold=1.0, seed=1)
        assert res.success
        assert res.inlier_ratio >= 0.65, "expected the wrong majority to win"
        assert res.inlier_rmse < 0.01, "and to look numerically excellent"

        err = endpoint_error(res.transform, right, (400, 400), step=25)
        assert err.median > 50, "yet it is wrong by ~one lattice period"

    def test_fit_rmse_collapses_when_inliers_approach_model_dof(self):
        """RMSE goes to ZERO precisely when the fit is most degenerate.

        With 3 correspondences an affine model (6 DOF) interpolates them
        exactly, so the fit residual vanishes by construction -- regardless of
        whether the model is right. In EXP-001, 11 of 17 failed cases reported
        fit RMSE < 1e-12 px while being 190-2400 px wrong. Low RMSE can be a
        symptom of failure, not evidence of success (spec §28).
        """
        rng = np.random.default_rng(15)
        src = rng.uniform(0, 400, size=(3, 2))
        dst = rng.uniform(0, 400, size=(3, 2))  # arbitrary, unrelated
        res = estimate(src, dst, "affine")
        assert res.ok
        assert res.rmse < 1e-9, f"expected exact interpolation; got {res.rmse}"
        # The residual is zero on those 3 points and enormous elsewhere.
        far = rng.uniform(0, 400, size=(50, 2))
        assert transfer_residuals(res.transform, far, far).mean() > 10
