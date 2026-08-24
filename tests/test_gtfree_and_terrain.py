"""Tests for GT-free estimators and terrain realism controls (EXP-002).

Several tests here assert that an estimator **fails** in a specific way. That
is deliberate. EXP-002 measured that held-out residual and spatial split
consistency are blind to coherent wrong solutions, and that cycle consistency
is blind to symmetric ones. Pinning those blind spots stops a future reader
(or a future me) from quietly assuming the estimators are safety nets they are
not.
"""

from __future__ import annotations

import numpy as np
import pytest

from siim.data import (
    ANGLE_OF_REPOSE_DEG,
    TERRAIN_REGIMES,
    height_field,
    normalise_slope,
    render,
    slope_statistics,
)
from siim.evaluation import (
    compose_cycle,
    cycle_consistency,
    held_out_residual,
    loop_closure,
    spatial_split_consistency,
)
from siim.geometry import affine, estimate, identity, similarity, translation
from siim.matching import detect_and_describe

LATTICE = 64.0


# ------------------------------------------------------------- terrain


class TestSlopeControl:
    @pytest.mark.parametrize("target", [3.5, 9.1, 18.0, 25.0])
    def test_slope_target_is_hit_precisely(self, target):
        f = height_field(
            (256, 256), np.random.default_rng(3), scene="highlands",
            target_slope_median_deg=target, pixel_scale=1.0,
        )
        assert slope_statistics(f, 1.0)["median_deg"] == pytest.approx(target, abs=0.05)

    def test_normalise_slope_is_a_pure_vertical_rescale(self):
        """Ground-truth geometry must be untouched: heights scale, xy does not."""
        f = height_field((128, 128), np.random.default_rng(1), scene="highlands")
        g = normalise_slope(f, 9.1, 1.0)
        ratio = g[f != 0] / f[f != 0]
        assert np.allclose(ratio, ratio[0]), "not a uniform scaling"
        assert np.corrcoef(f.ravel(), g.ravel())[0, 1] == pytest.approx(1.0, abs=1e-9)

    def test_none_target_disables_normalisation(self):
        """Reproducibility of EXP-001 depends on this being exact."""
        a = height_field((128, 128), np.random.default_rng(5), scene="highlands")
        b = height_field(
            (128, 128), np.random.default_rng(5), scene="highlands",
            target_slope_median_deg=None,
        )
        assert np.array_equal(a, b)

    def test_realistic_regimes_respect_the_angle_of_repose(self):
        """Slopes far past ~33 deg are almost absent on the Moon (sources.md S7)."""
        for name, reg in TERRAIN_REGIMES.items():
            if not reg.realistic:
                continue
            f = height_field(
                (256, 256), np.random.default_rng(9), scene=reg.scene,
                target_slope_median_deg=reg.target_slope_median_deg,
                octaves=reg.octaves, persistence=reg.persistence,
                crater_density=reg.crater_density, pixel_scale=1.0,
            )
            frac = slope_statistics(f, 1.0)["frac_above_repose"]
            assert frac < 0.15, f"{name}: {frac:.1%} of the surface exceeds repose"

    def test_extreme_regime_is_retained_and_flagged_unrealistic(self):
        reg = TERRAIN_REGIMES["C_extreme_diagnostic"]
        assert reg.realistic is False
        assert reg.target_slope_median_deg is None
        f = height_field((256, 256), np.random.default_rng(9), scene=reg.scene)
        # It really is physically impossible, which is why it is diagnostic only.
        assert slope_statistics(f, 1.0)["p99_deg"] > 2 * ANGLE_OF_REPOSE_DEG

    def test_feature_density_varies_at_fixed_slope(self):
        """Geometry and feature density must be separately controllable."""
        dens, meds = [], []
        for pers, octv in [(0.35, 4), (0.70, 7)]:
            f = height_field(
                (256, 256), np.random.default_rng(4), scene="highlands",
                target_slope_median_deg=9.1, octaves=octv, persistence=pers,
                pixel_scale=1.0,
            )
            meds.append(slope_statistics(f, 1.0)["median_deg"])
            dens.append(len(detect_and_describe(render(f, 315.0, 45.0, noise_std=0.002))))
        assert meds[0] == pytest.approx(9.1, abs=0.05)
        assert meds[1] == pytest.approx(9.1, abs=0.05)
        assert dens[1] > 3 * max(dens[0], 1), f"density barely moved: {dens}"

    def test_mare_is_information_poor(self):
        reg = TERRAIN_REGIMES["A_mare_moderate"]
        f = height_field(
            (256, 256), np.random.default_rng(2), scene=reg.scene,
            target_slope_median_deg=reg.target_slope_median_deg,
            octaves=reg.octaves, persistence=reg.persistence, pixel_scale=1.0,
        )
        hi = height_field(
            (256, 256), np.random.default_rng(2), scene="highlands",
            target_slope_median_deg=9.1, pixel_scale=1.0,
        )
        n_mare = len(detect_and_describe(render(f, 315.0, 45.0, noise_std=0.002)))
        n_hi = len(detect_and_describe(render(hi, 315.0, 45.0, noise_std=0.002)))
        assert n_mare < 0.2 * n_hi


# ------------------------------------------------------- held-out residual


class TestHeldOutResidual:
    def test_correct_matches_give_a_small_held_out_residual(self):
        rng = np.random.default_rng(1)
        truth = affine([[1.02, 0.03, 7.0], [-0.02, 1.01, -5.0]])
        src = rng.uniform(0, 512, size=(200, 2))
        dst = truth.apply(src) + rng.normal(0, 0.4, size=(200, 2))
        r = held_out_residual(src, dst, "affine", seed=0)
        assert r.ok and r.median < 1.5

    def test_it_catches_the_degenerate_fit_that_fit_rmse_misses(self):
        """The RL-010 regime: n at the minimal set, fit RMSE ~ 0 regardless.

        Exact interpolation happens at n == the minimal sample size -- 3 pairs
        for a 6-DOF affine, not 4. (EXP-001's failed cases sat at 3-4 inliers,
        and RANSAC *selects* mutually consistent points, so even n slightly
        above the minimum keeps the residual near zero.)
        """
        rng = np.random.default_rng(2)
        src = rng.uniform(0, 512, size=(3, 2))
        dst = rng.uniform(0, 512, size=(3, 2))  # unrelated: the fit is meaningless

        assert estimate(src, dst, "affine").rmse < 1e-9  # fit RMSE says "perfect"
        r = held_out_residual(src, dst, "affine", seed=0)
        assert (not r.ok) or r.median > 20, "held-out residual failed to object"

    def test_exact_interpolation_only_at_the_minimal_set(self):
        """Pins the precise claim: 3 points interpolate, 4 generally do not."""
        rng = np.random.default_rng(2)
        dst4 = rng.uniform(0, 512, size=(4, 2))
        src4 = rng.uniform(0, 512, size=(4, 2))
        assert estimate(src4[:3], dst4[:3], "affine").rmse < 1e-9
        assert estimate(src4, dst4, "affine").rmse > 1.0

    def test_blind_to_a_coherent_wrong_solution(self):
        """MEASURED BLIND SPOT (EXP-002 objective 4).

        Every match displaced by one lattice period is 64 px wrong, yet the
        held-out residual is ~0.5 px -- indistinguishable from a correct set.
        Held-out residual tests self-consistency, and a uniformly wrong set is
        perfectly self-consistent.
        """
        rng = np.random.default_rng(3)
        truth = affine([[1.02, 0.03, 7.0], [-0.02, 1.01, -5.0]])
        wrong = translation(LATTICE, 0.0) @ truth
        src = rng.uniform(0, 512, size=(300, 2))
        dst = wrong.apply(src) + rng.normal(0, 0.4, size=(300, 2))

        r = held_out_residual(src, dst, "affine", seed=0)
        assert r.ok and r.median < 1.0, (
            "if this now detects the error, the blind spot has been fixed -- "
            "update EXP-002 and ADR-0011 rather than deleting this test"
        )

    def test_too_few_points_is_reported_not_raised(self):
        r = held_out_residual(np.zeros((3, 2)), np.zeros((3, 2)), "affine")
        assert not r.ok and "need >=" in r.reason


class TestSpatialSplitConsistency:
    def test_well_spread_correct_matches_agree_across_halves(self):
        rng = np.random.default_rng(1)
        truth = affine([[1.02, 0.03, 7.0], [-0.02, 1.01, -5.0]])
        src = rng.uniform(0, 512, size=(300, 2))
        dst = truth.apply(src) + rng.normal(0, 0.4, size=(300, 2))
        assert spatial_split_consistency(src, dst, "affine", (512, 512)) < 2.0

    def test_blind_to_a_coherent_wrong_solution(self):
        """MEASURED BLIND SPOT: both halves are wrong the same way, so agree."""
        rng = np.random.default_rng(3)
        truth = affine([[1.02, 0.03, 7.0], [-0.02, 1.01, -5.0]])
        wrong = translation(LATTICE, 0.0) @ truth
        src = rng.uniform(0, 512, size=(300, 2))
        dst = wrong.apply(src) + rng.normal(0, 0.4, size=(300, 2))
        assert spatial_split_consistency(src, dst, "affine", (512, 512)) < 2.0

    def test_too_few_points_returns_infinity(self):
        assert not np.isfinite(
            spatial_split_consistency(np.zeros((5, 2)), np.zeros((5, 2)), "affine")
        )


# --------------------------------------------------------- cycle and loop


class TestCycleAndLoop:
    def test_compose_cycle_applies_in_order(self):
        a, b = translation(3.0, 0.0), translation(0.0, 4.0)
        pts = np.array([[10.0, 10.0]])
        assert np.allclose(compose_cycle([a, b]).apply(pts), [[13.0, 14.0]])

    def test_correct_loop_closes(self):
        t_ab = similarity(1.02, np.deg2rad(3.0), 9.0, -6.0)
        t_bc = similarity(0.99, np.deg2rad(-2.0), -5.0, 7.0)
        t_ca = (t_bc @ t_ab).inverse()
        assert loop_closure([t_ab, t_bc, t_ca], (512, 512)) < 1e-6

    def test_loop_closure_detects_a_coherent_lattice_shift(self):
        """The estimator ANALYSIS §F.1.4 exists for -- and it works.

        A one-period error on each edge accumulates to three periods around
        the loop instead of cancelling.
        """
        shift = translation(LATTICE, 0.0)
        t_ab = similarity(1.02, np.deg2rad(3.0), 9.0, -6.0)
        t_bc = similarity(0.99, np.deg2rad(-2.0), -5.0, 7.0)
        t_ca = (t_bc @ t_ab).inverse()
        err = loop_closure([shift @ t_ab, shift @ t_bc, shift @ t_ca], (512, 512))
        assert err > 3 * LATTICE * 0.9, f"loop error only {err:.1f} px"

    def test_loop_closure_detects_a_single_wrong_edge(self):
        shift = translation(LATTICE, 0.0)
        t_ab = similarity(1.02, np.deg2rad(3.0), 9.0, -6.0)
        t_bc = similarity(0.99, np.deg2rad(-2.0), -5.0, 7.0)
        t_ca = (t_bc @ t_ab).inverse()
        assert loop_closure([shift @ t_ab, t_bc, t_ca], (512, 512)) > 0.9 * LATTICE

    def test_cycle_consistency_is_blind_to_a_symmetric_error(self):
        """MEASURED BLIND SPOT: forward +64, backward -64, cancels exactly.

        This is why loop closure, not cycle consistency, is the estimator that
        earns its place against coherent wrong solutions (EXP-002 objective 4).
        """
        t_ab = similarity(1.02, np.deg2rad(3.0), 9.0, -6.0)
        wrong = translation(LATTICE, 0.0) @ t_ab
        assert cycle_consistency(wrong, wrong.inverse(), (512, 512)) < 1e-6

    def test_missing_transform_is_maximally_bad(self):
        assert not np.isfinite(cycle_consistency(None, identity(), (64, 64)))
        assert not np.isfinite(loop_closure([identity(), None], (64, 64)))
