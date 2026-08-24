"""Tests for the synthetic terrain generator and its ground truth.

The most important test here is ``test_ground_truth_is_exact_regression``.
The first version of ``make_pair`` rendered the reference into a padded canvas
and cropped the padding off without composing that offset into the returned
transform. The "ground truth" was then wrong by ``pad * sqrt(2) = 56.57`` px --
and RANSAC still reported a **99.6% inlier ratio with 0.72 px fit RMSE**,
because a uniformly shifted match set is perfectly self-consistent.

Nothing except ground truth caught it. That is the entire argument of
ANALYSIS §A.3 and §F.1, demonstrated on our own harness before we ever pointed
it at lunar data.
"""

from __future__ import annotations

import numpy as np
import pytest

from siim.baselines import run_rootsift_baseline
from siim.data import height_field, make_pair, render
from siim.geometry import (
    anchor_at,
    endpoint_error,
    image_centre,
    similarity,
    translation,
)


@pytest.fixture(scope="module")
def field_small():
    return height_field((384, 384), np.random.default_rng(11), scene="highlands")


class TestHeightField:
    @pytest.mark.parametrize("scene", ["highlands", "mare", "repetitive", "mixed"])
    def test_shape_and_finiteness(self, scene):
        h = height_field((128, 160), np.random.default_rng(2), scene=scene)
        assert h.shape == (128, 160)
        assert np.isfinite(h).all()

    def test_mare_is_smoother_than_highlands(self):
        rng_a, rng_b = np.random.default_rng(5), np.random.default_rng(5)
        hi = height_field((256, 256), rng_a, scene="highlands")
        ma = height_field((256, 256), rng_b, scene="mare")
        # The low-texture case must actually be low-texture, or Challenge G
        # is not testing what it claims to test.
        assert ma.std() < 0.5 * hi.std()

    def test_repetitive_is_periodic(self):
        h = height_field((256, 256), np.random.default_rng(5), scene="repetitive", ambiguity=1.0)
        row = h[96] - h[96].mean()
        # Autocorrelation at the 64-px lattice period must be strongly positive.
        ac = np.correlate(row, row, mode="full")[len(row) - 1 :]
        ac /= ac[0]
        assert ac[64] > 0.5, f"lattice period not detected; ac[64]={ac[64]:.3f}"

    def test_ambiguity_suppresses_disambiguating_context(self):
        plain = height_field((256, 256), np.random.default_rng(5), scene="repetitive", ambiguity=0.0)
        amb = height_field((256, 256), np.random.default_rng(5), scene="repetitive", ambiguity=1.0)
        r_plain = plain[96] - plain[96].mean()
        r_amb = amb[96] - amb[96].mean()

        def periodicity(row):
            ac = np.correlate(row, row, mode="full")[len(row) - 1 :]
            return ac[64] / ac[0]

        assert periodicity(r_amb) > periodicity(r_plain)

    def test_unknown_scene_rejected(self):
        with pytest.raises(ValueError, match="unknown scene"):
            height_field((64, 64), np.random.default_rng(0), scene="lava_tube")


class TestRendering:
    def test_output_is_a_valid_image(self, field_small):
        img = render(field_small, 315.0, 45.0)
        assert img.shape == field_small.shape
        assert img.min() >= 0.0 and img.max() <= 1.0
        assert np.isfinite(img).all()

    def test_azimuth_reversal_inverts_the_shading_gradient(self, field_small):
        """The defining lunar difficulty (ANALYSIS §B2), verified analytically.

        With the Sun at azimuth 90 vs 270 the horizontal light component flips
        sign, so the difference of the two renderings must be proportional to
        the *negative* terrain x-gradient. This is the mechanism that breaks
        gradient-orientation descriptors.
        """
        a = render(field_small, 90.0, 30.0, cast_shadows=False, noise_std=0.0)
        b = render(field_small, 270.0, 30.0, cast_shadows=False, noise_std=0.0)
        gy, gx = np.gradient(field_small)
        norm = np.sqrt(gx**2 + gy**2 + 1.0)

        # Exact identity for Lambertian shading with only the horizontal light
        # component flipped:  a - b = -2 cos(el) * gx / |n|.
        corr = np.corrcoef((a - b).ravel(), (-gx / norm).ravel())[0, 1]
        assert corr > 0.95, f"shading model identity violated; corr={corr:.3f}"

    def test_azimuth_reversal_anticorrelates_image_gradients(self, field_small):
        """The mechanism that breaks gradient-orientation descriptors.

        SIFT/ORB/AKAZE bin gradient orientation over [0, 2*pi). Under azimuth
        reversal the image gradient does not merely change magnitude -- it
        flips sign, so corresponding descriptors differ by pi and mismatch
        systematically (ANALYSIS §B2).

        Note this is a statement about *gradients*, not intensities. Raw
        intensities stay fairly correlated (R^2 ~ 0.71 here) because both
        renderings share the slope-magnitude term, which is exactly why a
        naive intensity-correlation check would miss the problem entirely.
        """
        a = render(field_small, 90.0, 30.0, cast_shadows=False, noise_std=0.0)
        b = render(field_small, 270.0, 30.0, cast_shadows=False, noise_std=0.0)
        _, agx = np.gradient(a)
        _, bgx = np.gradient(b)
        corr = np.corrcoef(agx.ravel(), bgx.ravel())[0, 1]
        assert corr < -0.5, f"expected anti-correlated gradients; got {corr:.3f}"

        # Contrast normalisation cannot repair this: it preserves sign.
        an = (a - a.mean()) / a.std()
        bn = (b - b.mean()) / b.std()
        _, angx = np.gradient(an)
        _, bngx = np.gradient(bn)
        assert np.corrcoef(angx.ravel(), bngx.ravel())[0, 1] < -0.5

    def test_low_sun_casts_more_shadow(self, field_small):
        low = render(field_small, 315.0, 8.0, cast_shadows=True, noise_std=0.0)
        high = render(field_small, 315.0, 70.0, cast_shadows=True, noise_std=0.0)
        assert (low < 0.1).mean() > (high < 0.1).mean()

    def test_cast_shadows_can_be_disabled(self, field_small):
        on = render(field_small, 315.0, 10.0, cast_shadows=True, noise_std=0.0)
        off = render(field_small, 315.0, 10.0, cast_shadows=False, noise_std=0.0)
        assert (off < 0.1).mean() < (on < 0.1).mean()

    def test_pixel_scale_changes_apparent_slope(self, field_small):
        coarse = render(field_small, 315.0, 45.0, pixel_scale=4.0, noise_std=0.0)
        fine = render(field_small, 315.0, 45.0, pixel_scale=0.5, noise_std=0.0)
        # Smaller pixel_scale => steeper apparent slopes => more contrast.
        assert fine.std() > coarse.std()

    def test_rejects_bad_pixel_scale(self, field_small):
        with pytest.raises(ValueError, match="pixel_scale"):
            render(field_small, 0.0, 45.0, pixel_scale=0.0)


class TestPairGroundTruth:
    def test_identity_same_sun_reproduces_the_source(self):
        pair = make_pair(
            np.random.default_rng(4),
            translation(0.0, 0.0),
            scene="highlands",
            out_shape=(192, 192),
            sun_source=(315.0, 45.0),
        )
        interior = (slice(20, 172), slice(20, 172))
        diff = np.abs(pair.source[interior] - pair.reference[interior])
        assert np.median(diff) < 0.02, f"median {np.median(diff):.4f}"

    @pytest.mark.parametrize(
        "tf_name",
        ["translation", "similarity"],
    )
    def test_ground_truth_is_exact_regression(self, tf_name):
        """REGRESSION: the padded-crop offset bug (see module docstring).

        Recovers the transform from the rendered images with the real
        pipeline and checks it against the declared ground truth. The bug this
        guards produced a 56.57 px discrepancy while every self-reported
        metric looked excellent.
        """
        shape = (384, 384)
        c = image_centre(shape)
        tf = (
            translation(17.0, -11.0)
            if tf_name == "translation"
            else anchor_at(similarity(1.08, np.deg2rad(6.0), 12.0, -8.0), c)
        )
        pair = make_pair(
            np.random.default_rng(4),
            tf,
            scene="highlands",
            out_shape=shape,
            sun_source=(315.0, 45.0),
        )
        res = run_rootsift_baseline(pair.source, pair.reference, model="affine")
        assert res.success and res.ransac.n_inliers > 50

        err = endpoint_error(res.transform, pair.transform, shape, step=16)
        assert err.median < 1.0, (
            f"recovered transform disagrees with declared GT by "
            f"{err.median:.3f} px (median). If this is ~56.6 px the padded-crop "
            f"offset has regressed."
        )

    def test_reference_valid_mask_and_overlap(self):
        pair = make_pair(
            np.random.default_rng(4),
            translation(5.0, 5.0),
            scene="mare",
            out_shape=(128, 128),
        )
        assert pair.reference_valid.shape == (128, 128)
        assert 0.0 <= pair.overlap_fraction <= 1.0
        assert pair.overlap_fraction > 0.9

    def test_base_field_reuse_is_equivalent(self):
        fld = height_field((256, 256), np.random.default_rng(9), scene="highlands")
        a = make_pair(
            np.random.default_rng(4), translation(6.0, 3.0), out_shape=(128, 128),
            base_field=fld, sun_source=(315.0, 45.0),
        )
        b = make_pair(
            np.random.default_rng(4), translation(6.0, 3.0), out_shape=(128, 128),
            base_field=fld, sun_source=(315.0, 45.0),
        )
        assert np.allclose(a.source, b.source)
        assert np.allclose(a.reference, b.reference)

    def test_base_field_too_small_is_rejected(self):
        fld = height_field((64, 64), np.random.default_rng(9))
        with pytest.raises(ValueError, match="smaller than out_shape"):
            make_pair(np.random.default_rng(4), translation(0.0, 0.0),
                      out_shape=(128, 128), base_field=fld)

    def test_metadata_records_the_illumination_change(self):
        pair = make_pair(
            np.random.default_rng(4), translation(0.0, 0.0), out_shape=(96, 96),
            sun_source=(315.0, 45.0), sun_reference=(45.0, 30.0),
        )
        assert pair.meta["delta_azimuth_deg"] == pytest.approx(90.0)
        assert pair.meta["delta_elevation_deg"] == pytest.approx(-15.0)

    def test_scale_change_updates_reference_pixel_scale(self):
        """A resized picture is not a scale change; metres-per-pixel must move."""
        pair = make_pair(
            np.random.default_rng(4),
            anchor_at(similarity(2.0), image_centre((128, 128))),
            out_shape=(128, 128),
            pixel_scale=1.0,
        )
        assert pair.meta["pixel_scale_reference"] == pytest.approx(0.5, rel=1e-6)
