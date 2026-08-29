"""EXP-000: the geometry gate.

These tests are the gate described in ANALYSIS §I: nothing touches real lunar
data until they pass. Their job is to make coordinate-convention and numerical
errors *loud*, since their natural failure mode is silent (risk R8).

The test obligations table in ``docs/coordinate_contract.md`` maps one-to-one
onto the classes below.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import ndimage

from siim.geometry.estimate import COLLINEARITY_THRESHOLD
from siim.geometry import (
    MODEL_ORDER,
    as_points,
    affine,
    collinearity,
    corner_points,
    endpoint_error,
    estimate,
    finite_mask,
    from_homogeneous,
    identity,
    image_centre,
    image_extent,
    pixel_grid,
    projective,
    random_transform,
    rc_to_xy,
    resize,
    scale_coords,
    scale_transform,
    similarity,
    to_homogeneous,
    transfer_residuals,
    translation,
    warp,
    xy_to_rc,
)
from siim.geometry.transforms import Transform


# ---------------------------------------------------------------- conventions


class TestConventions:
    def test_homogeneous_round_trip(self, rng):
        pts = rng.uniform(-500, 500, size=(50, 2))
        assert np.allclose(from_homogeneous(to_homogeneous(pts)), pts, atol=1e-12)

    def test_as_points_rejects_wrong_shape(self):
        with pytest.raises(ValueError, match=r"shape \(N, 2\)"):
            as_points(np.zeros((3, 5)))

    def test_as_points_rejects_bad_1d(self):
        with pytest.raises(ValueError, match="exactly 2 elements"):
            as_points([1.0, 2.0, 3.0])

    def test_axis_swap_is_involutive(self, rng):
        pts = rng.uniform(0, 100, size=(20, 2))
        assert np.allclose(rc_to_xy(xy_to_rc(pts)), pts)

    def test_axis_swap_actually_swaps(self):
        # Guards against a "helpful" future edit that makes these identity.
        assert np.allclose(xy_to_rc([[3.0, 7.0]]), [[7.0, 3.0]])

    def test_image_extent_is_pixel_centre_convention(self):
        # An image of width 10 spans x in [-0.5, 9.5], NOT [0, 10].
        assert image_extent((6, 10)) == (-0.5, 9.5, -0.5, 5.5)

    def test_image_centre_is_not_half_the_width(self):
        # (W-1)/2, not W/2. The difference is exactly the sub-pixel budget.
        c = image_centre((6, 10))
        assert np.allclose(c, [[4.5, 2.5]])
        assert not np.allclose(c, [[5.0, 3.0]])

    def test_corner_points_use_true_extent(self):
        corners = corner_points((6, 10))
        assert np.allclose(corners[0], [-0.5, -0.5])
        assert np.allclose(corners[2], [9.5, 5.5])

    def test_pixel_grid_covers_every_pixel(self):
        grid = pixel_grid((4, 5))
        assert grid.shape == (20, 2)
        assert grid[:, 0].max() == 4.0 and grid[:, 1].max() == 3.0

    def test_point_at_infinity_becomes_nan_not_exception(self):
        # A homography may legitimately send a point to the vanishing line.
        h = projective([[1, 0, 0], [0, 1, 0], [1, 0, 0]])  # w = x
        out = h.apply([[0.0, 5.0]])
        assert np.isnan(out).all()
        assert not finite_mask(out)[0]


# ---------------------------------------------------------------- transforms


class TestTransforms:
    @pytest.mark.parametrize("model", MODEL_ORDER)
    def test_inverse_round_trip(self, rng, model):
        tf = random_transform(rng, model, (256, 256))
        pts = rng.uniform(0, 256, size=(40, 2))
        back = tf.inverse().apply(tf.apply(pts))
        assert np.allclose(back, pts, atol=1e-8)

    @pytest.mark.parametrize("model", MODEL_ORDER)
    def test_composition_matches_sequential_application(self, rng, model):
        a = random_transform(rng, model, (256, 256))
        b = random_transform(rng, model, (256, 256))
        pts = rng.uniform(0, 256, size=(40, 2))
        assert np.allclose((a @ b).apply(pts), a.apply(b.apply(pts)), atol=1e-8)

    def test_composition_takes_more_general_model(self):
        composed = similarity(1.5) @ translation(3, 4)
        assert composed.model == "similarity"
        composed2 = projective(np.eye(3)) @ similarity(1.5)
        assert composed2.model == "projective"

    def test_non_projective_model_rejects_perspective_row(self):
        with pytest.raises(ValueError, match=r"bottom row"):
            Transform(np.array([[1, 0, 0], [0, 1, 0], [0.01, 0, 1]]), "affine")

    def test_similarity_decomposition_recovers_parameters(self):
        tf = similarity(scale=1.7, angle_rad=0.35, tx=12.0, ty=-4.0)
        d = tf.decompose_similarity()
        assert d["scale"] == pytest.approx(1.7, abs=1e-12)
        assert d["rotation_rad"] == pytest.approx(0.35, abs=1e-12)
        assert (d["tx"], d["ty"]) == pytest.approx((12.0, -4.0))

    def test_dof_ordering_is_strictly_increasing(self):
        dofs = [identity(m).dof for m in MODEL_ORDER]
        assert dofs == sorted(dofs) and len(set(dofs)) == len(dofs)


# ------------------------------------------------- contract C4: scale offset


class TestScaleConvention:
    """The half-pixel bug that C4 exists to prevent.

    Verified against *actual image resampling*, not against the formula
    restated -- a test that only checks the formula against itself would pass
    for the wrong convention too.
    """

    @staticmethod
    def _blob(shape, x0, y0, sigma=4.0):
        yy, xx = np.mgrid[0 : shape[0], 0 : shape[1]].astype(float)
        return np.exp(-(((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * sigma**2)))

    @staticmethod
    def _centroid(img):
        yy, xx = np.mgrid[0 : img.shape[0], 0 : img.shape[1]].astype(float)
        total = img.sum()
        return np.array([[(xx * img).sum() / total, (yy * img).sum() / total]])

    @pytest.mark.parametrize("scale", [0.5, 2.0, 3.0, 0.25])
    def test_scale_transform_matches_real_resampling(self, scale):
        x0, y0 = 50.3, 61.7
        img = self._blob((128, 128), x0, y0)
        resized, tf = resize(img, scale)

        measured = self._centroid(resized)
        predicted = tf.apply([[x0, y0]])

        assert np.allclose(measured, predicted, atol=0.05), (
            f"scale={scale}: resampling put the feature at {measured.ravel()} "
            f"but scale_transform predicts {predicted.ravel()}"
        )

    @pytest.mark.parametrize("scale", [0.5, 2.0, 3.0])
    def test_naive_scaling_is_wrong_by_exactly_half_of_scale_minus_one(self, scale):
        """Documents *why* C4 exists, and pins the size of the error.

        If someone 'simplifies' scale_transform to ``p' = s * p``, this test
        fails and says by how much.
        """
        x0, y0 = 50.3, 61.7
        img = self._blob((128, 128), x0, y0)
        resized, _ = resize(img, scale)
        measured = self._centroid(resized).ravel()

        naive = np.array([scale * x0, scale * y0])
        expected_offset = (scale - 1.0) / 2.0

        assert np.allclose(measured - naive, expected_offset, atol=0.05)
        # And confirm it is a real error, not a rounding artefact.
        assert abs(expected_offset) > 0.2

    def test_scale_coords_agrees_with_scale_transform(self, rng):
        pts = rng.uniform(0, 200, size=(30, 2))
        for s in (0.4, 1.0, 2.5):
            assert np.allclose(scale_coords(pts, s), scale_transform(s).apply(pts))

    def test_scale_transform_is_invertible_round_trip(self, rng):
        pts = rng.uniform(0, 200, size=(30, 2))
        tf = scale_transform(0.3)
        assert np.allclose(tf.inverse().apply(tf.apply(pts)), pts, atol=1e-10)


# ---------------------------------------------------------------- estimation


class TestEstimation:
    @pytest.mark.parametrize("model", MODEL_ORDER)
    def test_exact_correspondences_recover_the_transform(self, rng, model):
        truth = random_transform(rng, model, (256, 256))
        src = rng.uniform(0, 256, size=(25, 2))
        dst = truth.apply(src)

        res = estimate(src, dst, model)
        assert res.ok, res.reason
        assert res.rmse < 1e-8, f"{model}: fit rmse {res.rmse}"

        # The real check: agreement of the MAPS on a dense grid, not just on
        # the points that were fitted (ANALYSIS §A.3).
        err = endpoint_error(res.transform, truth, (256, 256), step=8)
        assert err.max < 1e-6, f"{model}: max true endpoint error {err.max}"

    @pytest.mark.parametrize("model", MODEL_ORDER)
    def test_recovery_survives_a_simpler_truth(self, rng, model):
        """A general model must still fit data generated by a simpler one."""
        truth = random_transform(rng, "similarity", (256, 256))
        src = rng.uniform(0, 256, size=(30, 2))
        res = estimate(src, truth.apply(src), model)
        if model in ("translation", "euclidean"):
            pytest.skip(f"{model} cannot express a scale change")
        assert res.ok, res.reason
        assert endpoint_error(res.transform, truth, (256, 256), step=16).max < 1e-6

    @pytest.mark.parametrize(
        "model,n", [("affine", 2), ("projective", 3), ("euclidean", 1)]
    )
    def test_too_few_points_is_reported_not_raised(self, rng, model, n):
        src = rng.uniform(0, 256, size=(n, 2))
        res = estimate(src, src.copy(), model)
        assert not res.ok
        assert "need >=" in res.reason

    @pytest.mark.parametrize("model", ["affine", "projective"])
    def test_collinear_points_are_flagged_degenerate(self, model):
        t = np.linspace(0, 200, 12)
        src = np.column_stack([t, 0.5 * t + 3.0])  # exactly collinear
        dst = src + np.array([5.0, -2.0])
        res = estimate(src, dst, model)
        assert not res.ok
        assert "collinear" in res.reason

    def test_collinearity_metric_endpoints(self, rng):
        t = np.linspace(0, 100, 20)
        line = np.column_stack([t, 2 * t])
        assert collinearity(line) < 1e-12
        blob = rng.uniform(0, 100, size=(200, 2))
        assert collinearity(blob) > 0.5

    def test_the_collinearity_guard_fires_at_its_declared_threshold(self, rng):
        """The constant must actually be the boundary it is documented to be.

        Added by the 2026-08-29 audit: a mutation that changed
        ``COLLINEARITY_THRESHOLD`` from 1e-3 to 1e-12 -- effectively deleting
        the guard -- was **not caught by any test**. The threshold is a
        scientific constant (it decides which fits are reported at all), so it
        gets the same treatment as the other pre-registered constants.
        """
        t = np.linspace(0.0, 400.0, 40)
        for spread, expect_degenerate in ((0.2 * COLLINEARITY_THRESHOLD, True),
                                          (50.0 * COLLINEARITY_THRESHOLD, False)):
            src = np.column_stack([t, 200.0 + spread * 400.0 * np.sin(t)])
            dst = src + np.array([5.0, -2.0])
            res = estimate(src, dst, "affine")
            assert res.degenerate is expect_degenerate, (
                f"collinearity {collinearity(src):.3e} against a threshold of "
                f"{COLLINEARITY_THRESHOLD:.0e}: degenerate={res.degenerate}, "
                f"expected {expect_degenerate}")

    def test_a_near_collinear_fit_reports_a_tiny_rmse_while_being_very_wrong(self, rng):
        """MEASURED: the E-008 trap arising from GEOMETRY, not from texture.

        The project's fit-RMSE result is usually shown on repetitive terrain.
        It has a second, purely geometric source, and this pins it: a point set
        whose collinearity sits just ABOVE ``COLLINEARITY_THRESHOLD`` passes the
        degeneracy guard, fits its own points to a fraction of a pixel, and is
        badly wrong at any point off the line it was fitted along.

        This makes two things explicit that the docstring in
        ``siim.geometry.estimate`` only asserts: that 1e-3 is far more
        permissive than "fires only on real degeneracy" implies, and that the
        residual is silent about it. The defence is one layer up and is
        measured in ``test_coverage_rejects_the_near_collinear_fit_the_guard_admits``.
        """
        truth = np.array([[1.0, 0.0, 40.0], [0.0, 1.0, 25.0], [0.0, 0.0, 1.0]])
        t = rng.uniform(40.0, 470.0, 60)
        src = np.column_stack([t, 256.0 + rng.normal(0.0, 1.0, 60)])
        dst = (truth @ np.column_stack([src, np.ones(60)]).T).T[:, :2]
        dst = dst + rng.normal(0.0, 0.3, dst.shape)

        res = estimate(src, dst, "affine")
        assert res.ok, "the guard admits this configuration -- that is the point"
        assert collinearity(src) > COLLINEARITY_THRESHOLD

        far = np.array([[250.0, 60.0]])          # off the line the fit saw
        got = res.transform.apply(far)[0]
        want = (truth @ np.array([250.0, 60.0, 1.0]))[:2]
        error_far = float(np.linalg.norm(got - want))

        assert res.rmse < 1.0, "fit residual should look excellent"
        assert error_far > 3.0, (
            "the whole point is that a sub-pixel fit residual coexists with a "
            f"large true error off the fitted line; got {error_far:.2f} px")

    def test_noise_degrades_fit_gracefully_without_blowing_up(self, rng):
        truth = random_transform(rng, "affine", (256, 256))
        src = rng.uniform(0, 256, size=(200, 2))
        dst = truth.apply(src) + rng.normal(0, 0.5, size=(200, 2))
        res = estimate(src, dst, "affine")
        assert res.ok
        # With 200 points and sigma=0.5 noise, a 6-DOF fit should land close.
        assert endpoint_error(res.transform, truth, (256, 256), step=16).median < 0.2

    def test_transfer_residuals_report_infinity_not_nan_at_infinity(self):
        h = projective([[1, 0, 0], [0, 1, 0], [1, 0, 0]])
        res = transfer_residuals(h, [[0.0, 5.0]], [[1.0, 1.0]])
        assert np.isinf(res[0]), "points at infinity must sort as maximally bad"

    def test_hartley_normalisation_keeps_conditioning_sane(self, rng):
        """Large image coordinates must not wreck the DLT."""
        truth = random_transform(rng, "projective", (60000, 60000))
        src = rng.uniform(0, 60000, size=(40, 2))
        res = estimate(src, truth.apply(src), "projective")
        assert res.ok, res.reason
        assert res.condition < 1e8


# ---------------------------------------------------------------- resampling


class TestResampling:
    def test_identity_warp_is_a_no_op(self, terrain):
        out, valid = warp(terrain, identity())
        assert valid.all()
        assert np.allclose(out, terrain, atol=1e-8)

    def test_warp_round_trip_recovers_interior(self, terrain, rng):
        tf = similarity(1.0, np.deg2rad(11.0), 4.0, -3.0)
        tf = Transform(tf.matrix, "similarity")
        once, _ = warp(terrain, tf, cval=0.0)
        back, _ = warp(once, tf.inverse(), cval=0.0)

        interior = (slice(60, 196), slice(60, 196))
        diff = np.abs(back[interior] - terrain[interior])
        # Two cubic resamplings of a smooth image; this bounds interpolation
        # loss, and would blow up immediately if the direction were inverted.
        assert np.median(diff) < 0.01, f"median {np.median(diff)}"
        assert diff.max() < 0.06, f"max {diff.max()}"

    def test_warp_direction_is_forward_source_to_reference(self, rng):
        """A shifted feature must land where the FORWARD transform says."""
        img = np.zeros((128, 128))
        img[60, 40] = 1.0
        img = ndimage.gaussian_filter(img, 3.0)

        tf = translation(15.0, -8.0)
        out, _ = warp(img, tf, cval=0.0)

        yy, xx = np.mgrid[0:128, 0:128].astype(float)
        cx = (xx * out).sum() / out.sum()
        cy = (yy * out).sum() / out.sum()
        assert (cx, cy) == pytest.approx((40 + 15, 60 - 8), abs=0.05)

    def test_outside_source_is_marked_invalid_not_black(self):
        img = np.ones((64, 64))
        out, valid = warp(img, translation(20.0, 0.0))
        # Shifting right by 20 leaves the left 20 columns with no source.
        assert not valid[:, :19].any()
        assert np.isnan(out[:, :19]).all(), (
            "invalid regions must be NaN, not 0 -- lunar shadow is genuinely "
            "near-zero and the two must never be confusable"
        )
        assert valid[:, 25:].all()

    def test_antialias_sigma_only_applies_when_shrinking(self):
        assert antialias_sigma_value(2.0) == 0.0
        assert antialias_sigma_value(0.5) > 0.0
        assert antialias_sigma_value(0.25) > antialias_sigma_value(0.5)

    def test_downsampling_without_antialias_aliases(self, rng):
        """Justifies the antialias default: shows the artefact it prevents."""
        yy, xx = np.mgrid[0:256, 0:256].astype(float)
        fine = 0.5 + 0.5 * np.sin(2 * np.pi * xx / 3.0)  # near Nyquist

        clean, _ = resize(fine, 0.25, antialias=True)
        aliased, _ = resize(fine, 0.25, antialias=False)

        # Aliasing converts high-frequency texture into spurious low-frequency
        # structure, which shows up as much larger variance after downsampling.
        assert aliased.std() > 3 * clean.std()

    def test_resize_shape_and_transform_are_consistent(self):
        img = np.zeros((100, 60))
        out, tf = resize(img, 2.0)
        assert out.shape == (200, 120)
        assert tf.decompose_similarity()["scale"] == pytest.approx(2.0)


def antialias_sigma_value(scale: float) -> float:
    from siim.geometry import antialias_sigma

    return antialias_sigma(scale)


# ------------------------------------------------------ synthetic GT harness


class TestSyntheticHarness:
    def test_anchor_keeps_image_centre_fixed_under_rotation(self):
        from siim.geometry import anchor_at

        shape = (256, 256)
        c = image_centre(shape)
        rotated = anchor_at(similarity(1.0, np.deg2rad(30.0)), c)
        assert np.allclose(rotated.apply(c), c, atol=1e-9)

    def test_endpoint_error_is_zero_for_identical_transforms(self, rng):
        tf = random_transform(rng, "projective", (256, 256))
        err = endpoint_error(tf, tf, (256, 256), step=16)
        assert err.max < 1e-9

    def test_endpoint_error_detects_a_known_shift(self):
        err = endpoint_error(translation(3.0, 4.0), identity(), (128, 128), step=16)
        assert err.median == pytest.approx(5.0, abs=1e-9)  # 3-4-5 triangle
        assert err.max == pytest.approx(5.0, abs=1e-9)

    @pytest.mark.parametrize("model", MODEL_ORDER)
    def test_random_transforms_preserve_substantial_overlap(self, rng, model):
        """A synthetic pair with tiny overlap would test nothing useful."""
        shape = (256, 256)
        for _ in range(20):
            tf = random_transform(rng, model, shape)
            corners = tf.apply(corner_points(shape))
            assert finite_mask(corners).all()
            inside = (
                (corners[:, 0] > -256)
                & (corners[:, 0] < 512)
                & (corners[:, 1] > -256)
                & (corners[:, 1] < 512)
            )
            assert inside.all(), f"{model} produced an extreme warp: {corners}"

    def test_photometric_perturbation_stays_in_range(self, terrain, rng):
        from siim.geometry import photometric_perturb

        out = photometric_perturb(terrain, rng)
        assert out.min() >= 0.0 and out.max() <= 1.0
        assert out.shape == terrain.shape
        # It must actually change something, or the test above is vacuous.
        assert not np.allclose(out, terrain)


# ------------------------------------------------------------- the EXP-000 gate


class TestExp000Gate:
    """The gate: recover a known homography to well under a pixel.

    ANALYSIS §I -- if this fails, every number measured on real lunar data
    afterwards would be measuring this bug instead of the science.
    """

    def test_gate_homography_recovered_far_below_one_pixel(self, rng):
        shape = (512, 512)
        worst = 0.0
        for _ in range(50):
            truth = random_transform(rng, "projective", shape)
            src = rng.uniform(0, 512, size=(60, 2))
            res = estimate(src, truth.apply(src), "projective")
            assert res.ok, res.reason
            worst = max(worst, endpoint_error(res.transform, truth, shape, step=32).max)
        assert worst < 0.1, f"gate failed: worst true endpoint error {worst:.4f} px"

    def test_gate_full_image_cycle(self, terrain, rng):
        """Warp an image by a known transform, then recover it from the geometry.

        Closes the loop across all four modules at once: conventions,
        transforms, resampling and estimation.
        """
        shape = terrain.shape
        truth = random_transform(rng, "affine", shape, max_translation=10.0)
        warped, valid = warp(terrain, truth, cval=0.0)
        assert valid.mean() > 0.6, "synthetic pair lost too much overlap"

        # Correspondences taken directly from the known geometry: this checks
        # the geometry stack in isolation, with no matcher involved.
        src = pixel_grid(shape, step=32)
        res = estimate(src, truth.apply(src), "affine")
        assert res.ok
        assert endpoint_error(res.transform, truth, shape, step=16).max < 1e-6
