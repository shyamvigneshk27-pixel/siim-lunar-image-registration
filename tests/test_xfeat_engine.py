"""B4X (XFeat) behind the identical harness: registered as optional, pinned
to a commit, recovers a known shift, and disagrees with nothing B4L finds on
the same easy pair (the agreement verifier's first use)."""

from __future__ import annotations

import numpy as np
import pytest

from siim.baselines import OPTIONAL_BASELINE_IDS, run_baseline
from siim.baselines.xfeat import XFEAT_HUB_REPO, xfeat_available

pytestmark = pytest.mark.skipif(not xfeat_available(), reason="torch not installed")


def test_b4x_is_registered_as_optional_and_pinned():
    assert "B4X" in OPTIONAL_BASELINE_IDS
    repo, ref = XFEAT_HUB_REPO.split(":")
    assert repo == "verlab/accelerated_features"
    assert len(ref) == 40 and all(c in "0123456789abcdef" for c in ref), "pin to a commit, not a branch"


def test_b4x_recovers_a_known_shift_on_terrain(terrain):
    from scipy import ndimage

    reference = ndimage.shift(terrain, shift=(-4.0, 6.0), order=3, mode="reflect")
    res = run_baseline("B4X", terrain, reference, seed=0)
    assert res.runtime["engine"].startswith("B4X")
    assert res.success, res.ransac.reason
    probe = np.array([[100.0, 120.0], [60.0, 200.0]])
    mapped = res.transform.apply(probe)
    # MEASURED 2026-09-05: XFeat's keypoints on this smooth 256^2 terrain sit
    # ~1.4 px off the true shift under the affine default (DISK: < 0.75 px).
    # Its detector works on an 8 px stride with a learned sub-pixel head, and
    # E-034's bias absorption applies. The raw engine is bounded here at 2 px;
    # the pipeline's refine-then-reselect is what repairs it (next test).
    np.testing.assert_allclose(mapped, probe + np.array([6.0, -4.0]), atol=2.0)
    assert res.src_features.descriptors.shape[1] == 64
    assert np.isnan(res.matches.ratios).all()


def test_the_pipeline_repairs_b4x_localisation_to_subpixel(terrain):
    """estimate -> refine -> re-estimate turns a ~1.4 px XFeat estimate into a
    sub-0.1 px translation (D-044, D-045 applied to the coarse engine)."""
    from siim.geometry import endpoint_error, translation, warp
    from siim.pipeline import register_pair

    truth = translation(6.0, -4.0)
    reference, valid = warp(terrain, truth, cval=np.nan)
    reference = np.where(valid, reference, np.nanmedian(reference))
    res = register_pair(terrain, reference, engine="B4X", seed=0, refine_window=32)
    assert res.verdict.status != "REJECTED"
    assert res.model_selected_by == "held_out_on_refined_points"
    err = endpoint_error(res.transform, truth, terrain.shape)
    err0 = endpoint_error(res.initial_transform, truth, terrain.shape)
    assert err.median < 0.1, (err.median, err0.median)
    assert err.median < err0.median


def test_b4x_is_deterministic_on_cpu(terrain):
    from scipy import ndimage

    reference = ndimage.shift(terrain, shift=(2.0, -3.0), order=3, mode="reflect")
    a = run_baseline("B4X", terrain, reference, seed=0)
    b = run_baseline("B4X", terrain, reference, seed=0)
    assert a.ransac.n_inliers == b.ransac.n_inliers
    np.testing.assert_allclose(a.transform.matrix, b.transform.matrix)


def test_two_learned_engines_agree_on_an_easy_pair(terrain):
    """R2 in its simplest form: B4L and B4X, which share nothing, agree within
    the provisional 2 px floor on a self-shift."""
    from scipy import ndimage

    from siim.pipeline import register_pair_two_engines

    reference = ndimage.shift(terrain, shift=(-3.0, 5.0), order=3, mode="reflect")
    prim, sec, agr = register_pair_two_engines(terrain, reference, engines=("B4L", "B4X"))
    assert agr.agree is True, agr.statement
    assert agr.median_px < 1.0
    assert prim.verdict.metrics["engine_agreement_px"] == pytest.approx(agr.median_px)
