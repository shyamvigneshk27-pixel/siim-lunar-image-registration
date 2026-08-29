"""Tests for the demo verdict logic.

The load-bearing one is
``test_loop_closure_edges_must_be_independent_estimates``, which pins a bug
made and caught while building the demonstrator: the closing edge of the loop
was derived algebraically from the first edge, so any error appeared in both
and cancelled exactly. Loop closure then reported 0.000 px on a registration
that was 64 px wrong, and the demo said VERIFIED / high confidence.

That is E-012's symmetric-error blind spot reintroduced by construction. It is
the exact failure the project exists to catch, so it gets a test that states
the hazard rather than merely exercising the code.
"""

from __future__ import annotations

import numpy as np
import pytest

from siim.demo.verdict import (
    COVERAGE_GAP_WARN,
    EXCLUDED_FROM_VERDICT,
    INLIER_CUTOFF,
    assess,
)
from siim.evaluation.gtfree import loop_closure
from siim.geometry import (
    affine,
    anchor_at,
    estimate,
    image_centre,
    translation,
)

SHAPE = (384, 384)


@pytest.fixture
def points():
    rng = np.random.default_rng(0)
    return rng.uniform(20, 360, size=(300, 2))


def _assess(tf, pts, *, n=None, **kw):
    n = len(pts) if n is None else n
    p = pts[:n]
    return assess(transform=tf, src_points=p, dst_points=tf.apply(p),
                  inlier_mask=np.ones(n, dtype=bool), shape=SHAPE, **kw)


# ---------------------------------------------------------------------------
# the bug this file exists for
# ---------------------------------------------------------------------------

def test_loop_closure_edges_must_be_independent_estimates():
    """A loop whose closing edge is derived from the first cannot detect error.

    If this ever passes with a *small* loop error, the demo has regressed to
    deriving the third edge instead of estimating it, and its headline
    verification claim is void.
    """
    c = image_centre(SHAPE)
    truth_ab = anchor_at(affine([[1.0, 0.0, 8.0], [0.0, 1.0, -5.0]]), c)
    t_bc = anchor_at(affine([[1.0, 0.0, -6.0], [0.0, 1.0, 7.0]]), c)

    # A registration wrong by exactly one crater spacing.
    wrong_ab = translation(64.0, 0.0) @ truth_ab

    # DERIVED closing edge -- the bug. The shift cancels around the loop.
    derived = loop_closure([wrong_ab, t_bc, (t_bc @ wrong_ab).inverse()], SHAPE)
    assert derived < 1e-6, (
        "a derived closing edge should close trivially; if it does not, this "
        "test no longer demonstrates the hazard")

    # INDEPENDENT closing edge, i.e. one that does not know about the error.
    independent = loop_closure([wrong_ab, t_bc, (t_bc @ truth_ab).inverse()], SHAPE)
    assert independent > 60.0, (
        "an independently estimated closing edge must expose the 64 px error")


def test_coherent_wrong_answer_is_rejected_despite_excellent_fit():
    """The project's headline claim, as an executable assertion."""
    tf = translation(64.0, 0.0)
    rng = np.random.default_rng(1)
    pts = rng.uniform(20, 360, size=(300, 2))
    v = _assess(tf, pts, fit_rmse=0.028, loop_error_px=190.08)
    assert v.status == "REJECTED"
    assert v.confidence == "none"
    assert any("loop closure" in r.lower() for r in v.reasons)


def test_same_evidence_but_closing_loop_is_verified():
    """Only the loop error differs from the case above."""
    tf = translation(64.0, 0.0)
    rng = np.random.default_rng(1)
    pts = rng.uniform(20, 360, size=(300, 2))
    v = _assess(tf, pts, fit_rmse=0.028, loop_error_px=0.31)
    assert v.status == "VERIFIED"
    assert v.confidence == "high"


# ---------------------------------------------------------------------------
# the exclusion rules
# ---------------------------------------------------------------------------

def test_fit_rmse_never_changes_the_verdict(points):
    """ADR-0003 / D-003, as a test rather than a docstring promise."""
    tf = translation(3.0, 2.0)
    verdicts = {
        _assess(tf, points, fit_rmse=rmse, loop_error_px=0.2).status
        for rmse in (0.0, 1e-13, 0.5, 12.0, 1e6, float("nan"))
    }
    assert len(verdicts) == 1, f"fit_rmse changed the verdict: {verdicts}"


def test_excluded_signals_are_documented_with_their_disqualifying_measurement():
    for name, why in EXCLUDED_FROM_VERDICT.items():
        assert any(ch.isdigit() for ch in why), (
            f"{name} is excluded without citing a measurement")


def test_fit_rmse_is_reported_but_marked_excluded(points):
    v = _assess(translation(1.0, 1.0), points, fit_rmse=0.5, loop_error_px=0.1)
    e = next(x for x in v.evidence if x.name == "fit_rmse")
    assert e.weight == "excluded"
    assert v.metrics["fit_rmse"] == 0.5


# ---------------------------------------------------------------------------
# the deployable rule
# ---------------------------------------------------------------------------

def test_too_few_inliers_is_decisive_regardless_of_everything_else(points):
    """D-023: the rule is `<= 8`, not `< 8`."""
    v = _assess(translation(1.0, 1.0), points, n=INLIER_CUTOFF,
                fit_rmse=1e-15, loop_error_px=0.0)
    assert v.status == "REJECTED"
    e = next(x for x in v.evidence if x.name == "n_inliers")
    assert e.verdict == "decisive_against"


def test_nine_inliers_is_not_decisive_against(points):
    v = _assess(translation(1.0, 1.0), points, n=INLIER_CUTOFF + 1,
                fit_rmse=0.2, loop_error_px=0.1)
    e = next(x for x in v.evidence if x.name == "n_inliers")
    assert e.verdict == "supports"


def test_no_transform_is_rejected():
    v = assess(transform=None, src_points=np.zeros((3, 2)),
               dst_points=np.zeros((3, 2)), inlier_mask=np.zeros(3, bool),
               shape=SHAPE)
    assert v.status == "REJECTED" and v.confidence == "none"


def test_missing_loop_closure_yields_inconclusive_not_verified(points):
    """Absence of the decisive check must never read as a pass."""
    v = _assess(translation(2.0, 1.0), points, fit_rmse=0.3, loop_error_px=None)
    assert v.status == "INCONCLUSIVE"
    e = next(x for x in v.evidence if x.name == "loop_error_px")
    assert e.verdict == "inconclusive" and e.weight == "decisive"


def test_verdict_is_json_serialisable(points):
    import json
    v = _assess(translation(1.0, 1.0), points, fit_rmse=0.1, loop_error_px=0.05)
    json.dumps(v.as_dict())


# ---------------------------------------------------------------------------
# real-data scenario: added alongside the synthetic ones, never replacing them
# ---------------------------------------------------------------------------

def _client():
    from fastapi.testclient import TestClient
    from siim.demo.api import app
    return TestClient(app)


def test_synthetic_adversarial_scenarios_survive_real_data_integration():
    """The coherent-wrong construction is the case that demonstrates the
    project's central claim. Adding real data must not displace it."""
    d = _client().get("/api/scenarios").json()
    ids = {s["id"] for s in d["scenarios"]}
    assert {"easy_same_sun", "coherent_wrong"} <= ids
    by_id = {s["id"]: s for s in d["scenarios"]}
    assert by_id["coherent_wrong"]["adversarial"] is True
    assert by_id["easy_same_sun"]["data_source"] == "synthetic"


def test_every_scenario_declares_its_data_source():
    for s in _client().get("/api/scenarios").json()["scenarios"]:
        assert s["data_source"] in ("synthetic", "real_lro_nac")



# The three tests that stood here targeted the ``real_lro_nac`` scenario, which
# REAL-DATA-02 retired: its two tiles are 22.75 km apart and share no ground
# (E-028, E-029), so demonstrating a "failure" on it would have shown a failure
# of the acquisition, not of the matcher. They are not restored, because
# tests/test_demo_real_data.py now asserts the same three properties against the
# edges that replaced it -- no ground-truth claim, no synthetic substitution for
# a missing artefact, and a triplet loop residual never attributed to one edge --
# and additionally asserts that the retired scenario is no longer offered.


# ---------------------------------------------------------------------------
# The geometric form of the E-008 trap, and the layer that actually stops it
# ---------------------------------------------------------------------------
#
# Added by the 2026-08-29 pre-freeze audit. ``siim.geometry.estimate`` documents
# COLLINEARITY_THRESHOLD as firing "only on real degeneracy", and
# tests/test_geometry.py now measures that a configuration just above it is
# admitted while being badly wrong off the fitted line, at a sub-pixel fit
# residual. That is the E-008 trap arising from GEOMETRY rather than from
# repetitive texture, and the estimator does not catch it.
#
# The system does. This is where, and it is measured rather than argued, because
# "coverage bounds worst-case local error" (ADR-0006) had been justified by
# argument and never by a case it demonstrably rejects. NOTHING here changes a
# verdict criterion -- COVERAGE_GAP_WARN is pre-registered and untouched.


def _near_collinear_case(n=60, jitter=1.0, seed=20260829):
    """Correspondences strung along one line, with a CORRECT transform fitted."""
    rng = np.random.default_rng(seed)
    truth = np.array([[1.0, 0.0, 40.0], [0.0, 1.0, 25.0], [0.0, 0.0, 1.0]])
    x = rng.uniform(40.0, 470.0, n)
    src = np.column_stack([x, 256.0 + rng.normal(0.0, jitter, n)])
    dst = (truth @ np.column_stack([src, np.ones(n)]).T).T[:, :2]
    dst = dst + rng.normal(0.0, 0.3, dst.shape)
    return src, dst


def test_coverage_rejects_the_near_collinear_fit_the_guard_admits():
    """A clustered-on-a-line correspondence set must never come back VERIFIED.

    The inlier count is healthy (60, far above the rule of 8) and the fit
    residual is sub-pixel, so ``n_inliers`` and ``fit_rmse`` both say "fine".
    Only ``coverage_max_gap`` sees the problem, which is exactly the role
    ADR-0006 assigns it.
    """
    src, dst = _near_collinear_case()
    res = estimate(src, dst, "affine")
    assert res.ok and res.rmse < 1.0

    v = assess(transform=res.transform, src_points=src, dst_points=dst,
               inlier_mask=np.ones(len(src), bool), shape=(512, 512),
               fit_rmse=res.rmse, loop_error_px=None)

    assert v.metrics["n_inliers"] > INLIER_CUTOFF, "the inlier rule is satisfied"
    assert v.metrics["coverage_max_gap"] > COVERAGE_GAP_WARN, (
        "coverage must see the empty half of the image")
    assert v.status != "VERIFIED", (
        "a transform constrained only along one line was reported as VERIFIED")
    gap_evidence = next(e for e in v.evidence if e.name == "coverage_max_gap")
    assert gap_evidence.verdict == "against"


def test_the_same_case_is_still_rejected_when_the_transform_is_badly_wrong():
    """And when it IS wrong, nothing in the evidence stack calls it good.

    The transform is displaced by 64 px -- E-008's coherent wrong answer --
    while still fitting its own near-collinear points. fit_rmse stays small and
    is excluded; coverage still refuses.
    """
    src, dst = _near_collinear_case()
    res = estimate(src, dst, "affine")
    wrong = translation(64.0, 0.0) @ res.transform

    v = assess(transform=wrong, src_points=src, dst_points=dst,
               inlier_mask=np.ones(len(src), bool), shape=(512, 512),
               fit_rmse=res.rmse, loop_error_px=None)
    assert v.status != "VERIFIED"
    assert any(e.name == "fit_rmse" and e.weight == "excluded" for e in v.evidence)
