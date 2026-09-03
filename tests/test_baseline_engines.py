"""Baselines B0, B2, B3, B5, B7 (ANALYSIS §E.1).

These tests establish three things, in order of how badly their absence would
hurt:

1. **Direction.** B5 is a direct method whose sign convention is not obvious.
   ``test_direct_recovers_known_translation_with_correct_sign`` pins it to a
   known synthetic shift. A silent direction flip is exactly the failure class
   of E-001 -- invisible in imagery, fatal in the number.
2. **Harness identity.** Every engine returns the same result record and runs
   through the same ratio test, mutual check and LO-RANSAC, so §E.2's
   vanilla/wrapped delta compares methods rather than harnesses.
3. **Honest absence.** B0 and B5 form no correspondences, so their inlier
   statistics must be NaN rather than a comfortable-looking number.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import ndimage

from siim.baselines import (
    akaze_available,
    BASELINE_IDS,
    BASELINE_ROLES,
    BaselineResult,
    run_baseline,
    run_direct_baseline,
    run_identity_baseline,
)
from siim.geometry import Transform, warp


def _shift_image(image: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """Translate content by (dx, dy) in the (x, y) convention of contract C1."""
    return ndimage.shift(image, shift=(dy, dx), order=3, mode="reflect")


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------


def test_registry_is_complete_and_documented():
    assert set(BASELINE_ROLES) == set(BASELINE_IDS)
    for role in BASELINE_ROLES.values():
        assert role.strip()


def test_learned_baselines_are_refused_not_silently_defaulted(terrain):
    """B4/B6 are gated on the ADR-0008 licence audit and must raise.

    A silent fallback would report a comparison that never ran, which is worse
    than no comparison at all.
    """
    with pytest.raises(KeyError, match="ADR-0008"):
        run_baseline("B4", terrain, terrain)


def test_unknown_identifier_raises(terrain):
    with pytest.raises(KeyError):
        run_baseline("nonsense", terrain, terrain)


# --------------------------------------------------------------------------
# B0 -- identity
# --------------------------------------------------------------------------


def test_identity_returns_identity_and_claims_nothing(terrain):
    res = run_identity_baseline(terrain, terrain)
    assert isinstance(res, BaselineResult)
    assert res.transform is not None
    np.testing.assert_allclose(res.transform.matrix, np.eye(3), atol=0)
    assert len(res.matches) == 0
    # The point of B0: it must not report an inlier statistic it never computed.
    assert np.isnan(res.ransac.inlier_ratio)
    assert np.isnan(res.ransac.inlier_rmse)
    assert "identity" in res.ransac.reason


# --------------------------------------------------------------------------
# B5 -- the direction convention, pinned
# --------------------------------------------------------------------------


def test_direct_recovers_known_translation_with_correct_sign(terrain):
    """A source point at x must map to x + shift in the reference.

    This is the test that would have caught E-001's class of error. If the ECC
    template/input roles are swapped, the recovered translation flips sign and
    every downstream number is wrong while looking entirely plausible.
    """
    dx, dy = 7.0, -4.0
    reference = _shift_image(terrain, dx, dy)

    res = run_direct_baseline(terrain, reference, model="affine")
    assert res.transform is not None, res.ransac.reason

    probe = np.array([[100.0, 120.0], [60.0, 200.0]])
    mapped = res.transform.apply(probe)
    expected = probe + np.array([dx, dy])
    np.testing.assert_allclose(mapped, expected, atol=0.5)


def test_direct_reports_no_inlier_statistics(terrain):
    res = run_direct_baseline(terrain, _shift_image(terrain, 3.0, 2.0))
    assert len(res.matches) == 0
    assert np.isnan(res.ransac.inlier_ratio)
    assert np.isnan(res.ransac.inlier_rmse)
    assert res.ransac.n_inliers == 0


def test_direct_fails_loudly_on_unrelated_images(rng, terrain):
    """Uncorrelated content must not produce a confident transform silently.

    Either ECC declines to converge, or it converges to something the caller
    can still interrogate -- but the reason field must never be empty.
    """
    noise = rng.normal(size=terrain.shape)
    res = run_direct_baseline(terrain, noise)
    assert res.ransac.reason  # something is always said about what happened


# --------------------------------------------------------------------------
# B2, B3, B7 -- keypoint engines
# --------------------------------------------------------------------------


@pytest.mark.parametrize("engine", ["B2", "B3", "B7"])
def test_keypoint_engines_recover_a_known_affine(engine, terrain):
    """Each engine must recover a modest known transform on easy data.

    Deliberately easy: same image, fixed illumination, small rotation and
    scale. An engine that cannot do this is broken, and any illumination
    result obtained from it would be measuring the breakage.
    """
    theta = np.deg2rad(6.0)
    scale = 1.08
    matrix = np.array(
        [
            [scale * np.cos(theta), -scale * np.sin(theta), 12.0],
            [scale * np.sin(theta), scale * np.cos(theta), -5.0],
            [0.0, 0.0, 1.0],
        ]
    )
    truth = Transform(matrix=matrix, model="affine")
    # warp fills outside the source with NaN so invalid regions are
    # unmistakable (contract C5). Detectors need finite pixels, so the invalid
    # border is zeroed here -- in the test, deliberately, rather than inside an
    # engine where it would silently become every caller's convention.
    reference, valid = warp(terrain, truth, out_shape=terrain.shape)
    reference = np.where(valid, np.nan_to_num(reference), 0.0)

    res = run_baseline(engine, terrain, reference, seed=0)
    assert res.success, f"{engine} failed: {res.ransac.reason}"

    probe = np.array([[80.0, 80.0], [160.0, 110.0], [110.0, 170.0]])
    err = np.linalg.norm(res.transform.apply(probe) - truth.apply(probe), axis=1)
    assert err.max() < 2.0, f"{engine} endpoint error {err.max():.3f} px"


_BINARY_ENGINES = ["B3"] + (["B2K"] if akaze_available() else [])


@pytest.mark.parametrize("engine", _BINARY_ENGINES)
def test_binary_engines_use_hamming_and_still_produce_matches(engine, terrain):
    """A binary descriptor matched under L2 yields near-garbage.

    This asserts the engines are wired to the Hamming path: if the norm were
    wrong the putative set would collapse, so a healthy match count is the
    observable consequence of the correct metric.
    """
    res = run_baseline(engine, terrain, _shift_image(terrain, 5.0, 3.0), seed=0)
    assert len(res.matches) >= 10
    assert res.src_features.descriptors.dtype == np.uint8


def test_akaze_is_refused_clearly_when_the_build_lacks_it(terrain):
    """B2K must explain its own absence, and must not be silently swapped.

    OpenCV 5 moved AKAZE to contrib. A build without it has to say so; the
    substitute (B2, ASIFT) is a separate registry entry precisely so that no
    result table can silently attribute ASIFT numbers to AKAZE.
    """
    if akaze_available():
        pytest.skip("this build provides AKAZE; the refusal path cannot be exercised")
    with pytest.raises(RuntimeError, match="opencv_contrib"):
        run_baseline("B2K", terrain, terrain)


def test_phase_congruency_engine_is_not_claimed_to_be_rift():
    """B7 is phase congruency + RootSIFT, and must be described as such.

    Naming it RIFT would overclaim a rotation-invariant descriptor this arm
    does not implement -- the kind of drift the integrity rules exist to stop.
    """
    from siim.baselines import run_phase_congruency_baseline

    doc = run_phase_congruency_baseline.__doc__ or ""
    assert "not** RIFT2" in doc or "not* RIFT2" in doc or "NOT RIFT2" in doc.upper()


# --------------------------------------------------------------------------
# harness identity -- the §E.2 requirement
# --------------------------------------------------------------------------


@pytest.mark.parametrize("engine", BASELINE_IDS)
def test_every_engine_returns_the_same_record(engine, terrain):
    """One result type across all engines, so a sweep can tabulate them.

    Without this, §E.2's vanilla/wrapped delta would compare result shapes
    rather than methods.
    """
    reference = _shift_image(terrain, 4.0, 2.0)
    res = run_baseline(engine, terrain, reference)
    assert isinstance(res, BaselineResult)
    assert set(res.runtime) >= {"detect_describe_s", "match_s", "ransac_s", "total_s"}
    assert res.runtime["total_s"] >= 0.0
    # transform may be None (a legitimate failure) but the field must exist.
    assert res.transform is None or isinstance(res.transform, Transform)


@pytest.mark.parametrize("engine", ["B1", "B2", "B3", "B7"])
def test_keypoint_engines_are_deterministic_under_a_fixed_seed(engine, terrain):
    """Reproducibility is a spec requirement (§33), not a nicety."""
    reference = _shift_image(terrain, 6.0, -3.0)
    a = run_baseline(engine, terrain, reference, seed=11)
    b = run_baseline(engine, terrain, reference, seed=11)
    assert a.ransac.n_inliers == b.ransac.n_inliers
    if a.transform is not None and b.transform is not None:
        np.testing.assert_allclose(a.transform.matrix, b.transform.matrix, atol=1e-12)


def test_engines_survive_a_blank_image(terrain):
    """A featureless tile must return a clean failure, not an exception.

    Texture-poor mare is a real regime for this project, and 'the detector
    found nothing' is a result the pipeline has to be able to report.
    """
    blank = np.zeros_like(terrain)
    for engine in ("B2", "B3", "B7"):
        res = run_baseline(engine, blank, blank)
        assert isinstance(res, BaselineResult)
        assert not res.success or res.ransac.n_inliers >= 0
