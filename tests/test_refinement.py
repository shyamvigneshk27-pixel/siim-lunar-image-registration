"""Local sub-pixel refinement: sign convention, precision, and honest failure."""

from __future__ import annotations

import numpy as np
import pytest

from siim.geometry import identity, translation, warp
from siim.refinement import refine_correspondences


@pytest.fixture
def pts(rng):
    return rng.uniform(60, 196, size=(40, 2))


@pytest.mark.parametrize("method", ["ecc", "phase"])
def test_identity_is_unbiased(terrain, pts, method):
    """The gate of EXP-010: refining an exact transform must move nothing."""
    r = refine_correspondences(terrain, terrain, identity(), pts, window=48, method=method)
    assert r.ok.mean() > 0.9
    assert np.nanmedian(np.hypot(*r.shift[r.ok].T)) < 0.05


def test_ecc_recovers_a_known_subpixel_residual_with_the_right_sign(terrain, pts):
    """Reference = source shifted by (+0.3, -0.7); the estimate is deliberately
    the identity, so the whole residual must appear in ``shift`` with that sign."""
    truth = translation(0.3, -0.7)
    reference, _ = warp(terrain, truth, cval=np.nan)
    r = refine_correspondences(terrain, reference, identity(), pts, window=48, method="ecc")
    assert r.ok.mean() > 0.9
    med = np.nanmedian(r.shift[r.ok], axis=0)
    assert med[0] == pytest.approx(0.3, abs=0.05)
    assert med[1] == pytest.approx(-0.7, abs=0.05)
    err = np.hypot(*(r.dst_refined[r.ok] - truth.apply(pts[r.ok])).T)
    assert np.median(err) < 0.05


def test_phase_correlation_has_the_right_sign_and_a_measured_underestimate(terrain, pts):
    """MEASURED: windowed phase correlation on a smooth 48 px patch recovers the
    residual's direction but only ~40-60 % of its magnitude (0.13 px for 0.30 px
    on this fixture). It is kept as EXP-010's second arm so the bias is
    reported next to ECC rather than assumed away; this test pins the sign and
    that refinement still reduces the error, not the magnitude."""
    truth = translation(0.3, -0.7)
    reference, _ = warp(terrain, truth, cval=np.nan)
    r = refine_correspondences(terrain, reference, identity(), pts, window=48, method="phase")
    assert r.ok.mean() > 0.9
    med = np.nanmedian(r.shift[r.ok], axis=0)
    assert med[0] > 0.05 and med[1] < -0.1
    before = np.hypot(*(r.dst_predicted[r.ok] - truth.apply(pts[r.ok])).T)
    after = np.hypot(*(r.dst_refined[r.ok] - truth.apply(pts[r.ok])).T)
    assert np.median(after) < np.median(before)


def test_points_near_the_border_are_reported_not_refined(terrain):
    pts = np.array([[5.0, 5.0], [128.0, 128.0], [250.0, 250.0]])
    r = refine_correspondences(terrain, terrain, identity(), pts, window=48)
    assert list(r.ok) == [False, True, False]
    np.testing.assert_allclose(r.dst_refined[~r.ok], r.dst_predicted[~r.ok])
    assert np.isnan(r.shift[0]).all()


def test_implausibly_large_residuals_are_rejected(terrain, pts):
    """A residual larger than window/4 is not a refinement of an inlier."""
    reference, _ = warp(terrain, translation(20.0, 0.0), cval=np.nan)
    r = refine_correspondences(terrain, reference, identity(), pts, window=48, method="ecc")
    assert r.ok.mean() < 0.5


def test_bad_arguments_are_refused(terrain, pts):
    with pytest.raises(ValueError):
        refine_correspondences(terrain, terrain, identity(), pts, window=47)
    with pytest.raises(ValueError):
        refine_correspondences(terrain, terrain, identity(), pts, method="lk")
