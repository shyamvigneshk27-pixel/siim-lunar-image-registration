"""Spatial uniformity: U1, U2, U3, and the cases the specification names.

The test ids follow ``04_SPATIAL_UNIFORMITY_SPEC`` section 8 (T1..T12), so a
failure points at the design case it violates.
"""

from __future__ import annotations

import numpy as np
import pytest

from siim.geometry import affine, translation
from siim.benchmark.uniformity import coverage_curve, uniformity_metrics


def grid_points(n: int, size: int, margin: int = 10) -> np.ndarray:
    xs = np.linspace(margin, size - margin, n)
    return np.array([[x, y] for x in xs for y in xs], dtype=float)


# -- T1, T2, T3: the shape of the metric ------------------------------------

def test_T1_a_spread_grid_scores_better_than_a_single_cluster():
    spread = uniformity_metrics(grid_points(5, 100), (100, 100))
    cluster = uniformity_metrics(
        np.random.default_rng(0).normal(50, 2, size=(25, 2)), (100, 100)
    )
    assert spread.u1_largest_gap < cluster.u1_largest_gap


def test_T2_a_single_cluster_leaves_a_large_unconstrained_region():
    pts = np.random.default_rng(0).normal(20, 1.5, size=(30, 2))
    u = uniformity_metrics(pts, (200, 200))
    assert u.u1_largest_gap > 0.5
    assert u.u3_min_cell_count == 0


def test_T3_a_tight_regular_lattice_in_one_corner_must_score_badly():
    """The case that disqualifies nearest-neighbour dispersion.

    A corner lattice is maximally *regular* by local spacing, and is our worst
    case: it constrains one corner and extrapolates everywhere else. U1 must
    reflect that, so a metric rewarding local regularity is unusable here.
    """
    lattice = np.array([[x, y] for x in range(5, 30, 5) for y in range(5, 30, 5)],
                       dtype=float)
    corner = uniformity_metrics(lattice, (200, 200))
    spread = uniformity_metrics(grid_points(5, 200, margin=20), (200, 200))
    assert corner.u1_largest_gap > 0.6
    assert corner.u1_largest_gap > 2 * spread.u1_largest_gap


# -- T5, T6, T7: the region, and comparability ------------------------------

def test_T5_a_non_convex_overlap_is_respected():
    mask = np.zeros((100, 100), dtype=bool)
    mask[:50, :] = True           # an L-shape
    mask[:, :50] = True
    pts = np.array([[10.0, 10.0], [80.0, 10.0], [10.0, 80.0]])
    u = uniformity_metrics(pts, (100, 100), mask)
    assert u.roi_area_px == float(mask.sum())
    assert u.u1_largest_gap_px <= float(np.hypot(100, 100))


def test_T6_metrics_are_computed_over_the_overlap_not_the_frame():
    """Partial overlap must not be punished as if it were poor coverage."""
    mask = np.zeros((200, 200), dtype=bool)
    mask[:50, :50] = True
    pts = grid_points(4, 50, margin=6)
    over_roi = uniformity_metrics(pts, (200, 200), mask)
    over_frame = uniformity_metrics(pts, (200, 200))
    assert over_roi.u1_largest_gap < over_frame.u1_largest_gap


def test_T7_normalisation_makes_differently_shaped_regions_comparable():
    """A 2048x1024 tile and a 111x46 strip must not be compared by frame diagonal.

    Same relative geometry, very different frames: the normalised values should
    be close. This is a regression test against the defect the specification
    records in section 4.2.
    """
    def relative(shape):
        h, w = shape
        pts = np.array([[w * fx, h * fy]
                        for fx in (0.2, 0.5, 0.8) for fy in (0.2, 0.5, 0.8)])
        return uniformity_metrics(pts, shape).u1_largest_gap

    big = relative((1024, 2048))
    small = relative((46, 111))
    assert big == pytest.approx(small, rel=0.15)


# -- T8, T9, T11: degenerate inputs -----------------------------------------

def test_T8_collinear_points_leave_a_large_gap():
    pts = np.array([[float(x), 50.0] for x in range(5, 96, 5)])
    u = uniformity_metrics(pts, (100, 100))
    assert u.u1_largest_gap > 0.3


def test_T9_duplicate_points_do_not_manufacture_coverage():
    one = np.array([[50.0, 50.0]])
    many = np.repeat(one, 50, axis=0)
    assert (uniformity_metrics(one, (100, 100)).u1_largest_gap
            == pytest.approx(uniformity_metrics(many, (100, 100)).u1_largest_gap))


def test_T11_no_points_is_undefined_not_zero():
    u = uniformity_metrics(np.zeros((0, 2)), (100, 100))
    assert u.u1_largest_gap is None
    assert "no correspondences" in u.undefined["u1"]
    assert u.n_points == 0


def test_T11_a_single_point_is_defined():
    u = uniformity_metrics(np.array([[50.0, 50.0]]), (100, 100))
    assert u.u1_largest_gap is not None
    assert u.u1_largest_gap > 0


def test_an_empty_overlap_is_undefined_everywhere():
    mask = np.zeros((50, 50), dtype=bool)
    u = uniformity_metrics(np.array([[10.0, 10.0]]), (50, 50), mask)
    assert u.u1_largest_gap is None
    assert u.u3_min_cell_count is None
    assert u.roi_area_px == 0.0


def test_points_entirely_outside_the_image_are_reported_not_ignored():
    u = uniformity_metrics(np.array([[500.0, 500.0]]), (100, 100))
    assert u.u1_largest_gap is None
    assert "inside the image" in u.undefined["u1"]


def test_roi_shape_must_match():
    with pytest.raises(ValueError, match="does not match"):
        uniformity_metrics(np.zeros((1, 2)), (100, 100),
                           np.ones((50, 50), dtype=bool))


# -- T12: determinism -------------------------------------------------------

def test_T12_repeated_evaluation_is_identical():
    pts = grid_points(4, 100)
    a = uniformity_metrics(pts, (100, 100), seed=7)
    b = uniformity_metrics(pts, (100, 100), seed=7)
    assert a == b


# -- U2 ---------------------------------------------------------------------

def test_U2_is_undefined_without_transform_replicates():
    """U2 is a bootstrap spread; it cannot be inferred from one transform."""
    u = uniformity_metrics(grid_points(4, 100), (100, 100))
    assert u.u2_max_prediction_sd_px is None
    assert "replicates" in u.undefined["u2"]


def test_U2_needs_at_least_three_replicates():
    u = uniformity_metrics(grid_points(4, 100), (100, 100),
                           transform_samples=[translation(0, 0)] * 2)
    assert u.u2_max_prediction_sd_px is None
    assert "at least 3" in u.undefined["u2"]


def test_U2_is_zero_when_every_replicate_agrees():
    samples = [translation(1.0, 2.0) for _ in range(5)]
    u = uniformity_metrics(grid_points(4, 100), (100, 100),
                           transform_samples=samples)
    assert u.u2_max_prediction_sd_px == pytest.approx(0.0, abs=1e-9)


def test_U2_grows_when_replicates_disagree():
    tight = [translation(1.0 + 0.01 * i, 2.0) for i in range(6)]
    loose = [translation(1.0 + 1.0 * i, 2.0) for i in range(6)]
    a = uniformity_metrics(grid_points(4, 100), (100, 100),
                           transform_samples=tight).u2_max_prediction_sd_px
    b = uniformity_metrics(grid_points(4, 100), (100, 100),
                           transform_samples=loose).u2_max_prediction_sd_px
    assert b > a > 0


def test_U2_reflects_rotational_disagreement_growing_with_distance():
    """A small angular spread costs more far from the centre of rotation."""
    samples = []
    for i in range(6):
        eps = 1e-3 * i
        samples.append(affine(np.array([[1.0, -eps, 0.0], [eps, 1.0, 0.0]])))
    near = uniformity_metrics(np.array([[5.0, 5.0]]), (10, 10),
                              transform_samples=samples).u2_max_prediction_sd_px
    far = uniformity_metrics(np.array([[500.0, 500.0]]), (1000, 1000),
                             transform_samples=samples).u2_max_prediction_sd_px
    assert far > near


def test_U2_accepts_bare_matrices_as_replicates():
    mats = [np.eye(3) + np.array([[0, 0, 0.1 * i], [0, 0, 0], [0, 0, 0]])
            for i in range(5)]
    u = uniformity_metrics(grid_points(3, 50), (50, 50), transform_samples=mats)
    assert u.u2_max_prediction_sd_px is not None
    assert u.u2_max_prediction_sd_px > 0


# -- thresholds are never defaulted -----------------------------------------

def test_meets_passes_when_no_threshold_is_asked_for():
    u = uniformity_metrics(grid_points(4, 100), (100, 100))
    ok, reasons = u.meets()
    assert ok and reasons == []


def test_meets_reports_each_failing_threshold_with_a_reason():
    u = uniformity_metrics(np.array([[5.0, 5.0]]), (200, 200))
    ok, reasons = u.meets(u1_max=0.05, u3_min=3)
    assert not ok
    assert any("U1" in r for r in reasons)
    assert any("U3" in r for r in reasons)


def test_an_undefined_metric_cannot_pass_a_requested_threshold():
    """Silence must not be read as compliance."""
    u = uniformity_metrics(grid_points(4, 100), (100, 100))
    ok, reasons = u.meets(u2_max_px=0.5)
    assert not ok
    assert "undefined" in reasons[0]


def test_serialised_uniformity_says_u2_is_a_precision():
    u = uniformity_metrics(grid_points(3, 60), (60, 60))
    assert u.as_dict()["u2_is_precision_not_accuracy"] is True


# -- coverage curve ---------------------------------------------------------

def test_coverage_curve_is_monotone_and_reaches_one():
    radii, fracs = coverage_curve(grid_points(4, 100), (100, 100),
                                  radii_px=[0, 5, 10, 25, 200])
    assert list(fracs) == sorted(fracs)
    assert fracs[-1] == pytest.approx(1.0)


def test_coverage_curve_is_zero_without_points():
    _, fracs = coverage_curve(np.zeros((0, 2)), (50, 50), radii_px=[1, 10])
    assert all(f == 0.0 for f in fracs)
