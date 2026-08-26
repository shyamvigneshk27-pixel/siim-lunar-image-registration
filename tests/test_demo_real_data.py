"""The demo's real-data path: what it displays, and what it must refuse to.

This is the September 2 demonstration surface. Its failure modes are not
crashes — they are a page that shows a number the experiments did not produce,
or shows a picture of one run beside the numbers of another, or quietly
substitutes synthetic pixels under a REAL DATA badge. Each of those would be
invisible to a judge and fatal to the claim, so each gets a test.

The values pinned here are REAL-DATA-04's, from
``experiments/REAL-DATA-04/loop_closure_real_data_04.json`` and
``overlap_real_data_04.json``. They are written out literally rather than read
from the artefact, on purpose: if the artefact ever changes, these tests must
fail loudly rather than agree with whatever the new file says.
"""

from __future__ import annotations

import json

import pytest

from siim.demo import evidence as ev

pytestmark = pytest.mark.skipif(
    not ev.real_data_status()["available"],
    reason="REAL-DATA-04 artefacts or demo assets are not on disk")


# -- the recorded values, written out so a drifting artefact fails a test ----
DA = {
    "scenario": "real_da_success", "delta_inc": 11.73, "overlap": 0.7130,
    "putative": 1759, "inliers": 1656, "ratio": 0.9414440022740194,
    "rmse": 0.8779232510137617, "gap": 0.10334689225690416, "occ": 1.0,
    "outcome": "SUCCEED",
}
BD = {
    "scenario": "real_bd_failure", "delta_inc": 51.54, "overlap": 0.7035,
    "putative": 29, "inliers": 3, "ratio": 0.10344827586206896,
    "rmse": 1.8852829216231156e-13, "gap": 0.42682484813887006,
    "occ": 0.046875, "outcome": "FAIL",
}
AB = {
    "scenario": "real_ab_control", "delta_inc": 39.81, "overlap": 0.9787,
    "putative": 50, "inliers": 7, "ratio": 0.14,
    "rmse": 1.1053335547230574, "gap": 0.46042617626927473,
    "occ": 0.0625, "outcome": "FAIL",
}
CASES = [DA, BD, AB]


def _client():
    from fastapi.testclient import TestClient
    from siim.demo.api import app
    return TestClient(app)


@pytest.fixture(scope="module")
def built():
    return {c["scenario"]: ev.build_real_scenario(c["scenario"]) for c in CASES}


# ---------------------------------------------------------------------------
# every displayed number traces to a recorded artefact
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES, ids=lambda c: c["scenario"])
def test_the_displayed_numbers_are_the_recorded_ones(built, case):
    d = built[case["scenario"]]
    reg, ov = d["step2_registration"], d["step1_overlap"]
    assert reg["n_putative"] == case["putative"]
    assert reg["n_inliers"] == case["inliers"]
    assert reg["inlier_ratio"] == case["ratio"]
    assert reg["fit_rmse_px"] == case["rmse"]
    assert reg["coverage_gap"] == case["gap"]
    assert reg["coverage_occupancy"] == case["occ"]
    assert round(ov["min_fraction"], 4) == case["overlap"]
    assert round(d["delta_incidence_deg"], 2) == case["delta_inc"]
    assert d["outcome"] == case["outcome"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["scenario"])
def test_every_step_names_the_artefact_it_came_from(built, case):
    d = built[case["scenario"]]
    for key in ("step1_overlap", "step2_registration"):
        src = d[key]["source"]
        assert src.startswith("experiments/"), src
        assert (ev.ROOT / src).exists(), f"{key} cites a file that is not there"


def test_real_scenarios_are_read_not_computed(built):
    """A recorded result may never be labelled as computed in the request."""
    for d in built.values():
        assert d["computation"] == "recorded_artefact"
        assert d["data_source"] == "real_lro_nac"


# ---------------------------------------------------------------------------
# the overlap gate comes first, and says so
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES, ids=lambda c: c["scenario"])
def test_overlap_is_confirmed_independently_of_the_matcher(built, case):
    o = built[case["scenario"]]["step1_overlap"]
    assert o["classification"] == "OVERLAP_CONFIRMED"
    assert o["independent_of_matcher"] is True
    assert "no pixel is read" in o["method"].lower()
    assert "--require-confirmed" in o["gate"]


def test_the_two_decisive_edges_are_overlap_matched(built):
    """The load-bearing control of the whole demonstration.

    B → D fails and D → A succeeds. If their shared ground differed much, a
    viewer could reasonably say the failure is just less overlap. It is not:
    the two are within one percentage point, and the FAILING edge in the
    control case has the MOST overlap of all three.
    """
    da = built["real_da_success"]["step1_overlap"]
    bd = built["real_bd_failure"]["step1_overlap"]
    ab = built["real_ab_control"]["step1_overlap"]
    assert abs(da["min_fraction"] - bd["min_fraction"]) < 0.01
    assert ab["min_fraction"] > da["min_fraction"]
    assert ab["min_fraction"] > bd["min_fraction"]
    for o in (da, bd, ab):
        assert o["p5"] >= 0.50, "a CONFIRMED edge must clear the p5 criterion"


# ---------------------------------------------------------------------------
# the RMSE trap — the demo's central moment
# ---------------------------------------------------------------------------

def test_the_failing_edge_reports_its_tiny_rmse_unaltered(built):
    """The point of the B → D beat is that the number is real and terrible
    evidence. Rounding, hiding or re-deriving it would destroy the argument."""
    d = built["real_bd_failure"]
    assert d["step2_registration"]["fit_rmse_px"] == 1.8852829216231156e-13
    rmse = [e for e in d["verdict"]["evidence"] if e["name"] == "fit_rmse"]
    assert rmse and rmse[0]["value"] == 1.8852829216231156e-13


def test_fit_rmse_is_excluded_from_every_real_verdict(built):
    for d in built.values():
        rmse = [e for e in d["verdict"]["evidence"] if e["name"] == "fit_rmse"]
        assert rmse, "fit_rmse must be shown, not omitted"
        assert rmse[0]["weight"] == "excluded"
        assert rmse[0]["verdict"] == "inconclusive"
        assert "fit_rmse" in d["verdict"]["excluded"]


def test_the_edge_with_the_smallest_rmse_is_the_one_that_is_rejected(built):
    """States the trap as a property rather than a number: across the three
    real edges, ranking by fit_rmse would pick the worst one first."""
    by_rmse = sorted(built.values(),
                     key=lambda d: d["step2_registration"]["fit_rmse_px"])
    assert by_rmse[0]["scenario"] == "real_bd_failure"
    assert by_rmse[0]["outcome"] == "FAIL"
    assert by_rmse[0]["verdict"]["status"] == "REJECTED"


def test_the_failing_edge_is_rejected_on_named_evidence(built):
    v = built["real_bd_failure"]["verdict"]
    assert v["status"] == "REJECTED"
    decisive = [e for e in v["evidence"] if e["verdict"] == "decisive_against"]
    assert any(e["name"] == "n_inliers" for e in decisive)
    assert any("Too few verified correspondences" in r for r in v["reasons"])


# ---------------------------------------------------------------------------
# the succeeding edge is not over-claimed
# ---------------------------------------------------------------------------

def test_the_succeeding_edge_is_not_called_verified(built):
    """REAL-DATA-04 §15 Q3: corroborated, never verified — class B.

    Loop closure is the only check that catches a coherent wrong answer, and it
    did not run for this edge. Reporting VERIFIED here would claim evidence the
    project does not have, which is the failure this whole system exists to
    prevent — so the demo shows INCONCLUSIVE and explains why.
    """
    d = built["real_da_success"]
    assert d["outcome"] == "SUCCEED"
    assert d["verdict"]["status"] == "INCONCLUSIVE"
    loop = [e for e in d["verdict"]["evidence"] if e["name"] == "loop_error_px"]
    assert loop and loop[0]["value"] is None
    assert "loop" in d["verdict_note"].lower()


def test_no_real_scenario_claims_ground_truth(built):
    for d in built.values():
        assert d["ground_truth"]["available"] is False
        assert d["ground_truth"]["true_error_median_px"] is None


def test_loop_residual_of_the_triplet_is_never_attributed_to_one_edge(built):
    """The recorded loop residual is 943.75 px and belongs to the TRIPLET, two
    of whose legs failed. Feeding it into a single-edge verdict would reject
    the succeeding edge for someone else's failure (and would be E-021's
    cousin: a loop number standing in for evidence it does not carry)."""
    triplet = json.loads(
        (ev.EXPERIMENTS / "REAL-DATA-04" / "loop_closure_real_data_04.json")
        .read_text(encoding="utf-8"))
    assert triplet["loop_closure_residual_px"] > 900
    for d in built.values():
        assert d["verdict"]["metrics"]["loop_error_px"] is None


# ---------------------------------------------------------------------------
# corroboration is shown, and is kept out of the verdict
# ---------------------------------------------------------------------------

def test_archive_geometry_corroborates_but_never_decides(built):
    da, bd = built["real_da_success"], built["real_bd_failure"]
    assert da["corroboration"]["scaled_pixel"]["agrees"] is True
    assert bd["corroboration"]["scaled_pixel"]["agrees"] is False
    for d in (da, bd):
        assert d["corroboration"]["excluded_from_verdict"] is True
        names = {e["name"] for e in d["verdict"]["evidence"]}
        assert "archive_geometry" not in names
        assert "scaled_pixel" not in names


def test_the_succeeding_edge_clears_the_archive_geometry_floor(built):
    c = built["real_da_success"]["corroboration"]
    assert c["excess_over_floor"] < 1.0
    assert c["median_disagreement_px"] < c["discrimination_floor_px"]


# ---------------------------------------------------------------------------
# the overlay picture belongs to the same run as the numbers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES, ids=lambda c: c["scenario"])
def test_the_overlay_matches_the_recorded_counts(built, case):
    d = built[case["scenario"]]
    c = d["correspondences"]
    assert len(c["src"]) == case["putative"]
    assert len(c["dst"]) == case["putative"]
    assert sum(1 for b in c["inlier"] if b) == case["inliers"]
    assert d["overlay_integrity"]["agrees_with_artefact"] is True


def test_an_overlay_that_disagrees_with_the_artefact_is_refused():
    """The check that makes the guarantee real. If the asset file and the
    artefact ever drift apart, the demo must refuse rather than draw one run's
    lines beside another run's numbers."""
    rec = {"n_putative_mutual_ratio_matches": 1759, "n_inliers": 1656}
    asset = {"correspondences": {"src": [[0, 0]] * 10, "dst": [[0, 0]] * 10,
                                 "inlier": [True] * 10}}
    with pytest.raises(ev.DemoDataMissing, match="different runs"):
        ev._check_asset_matches_artefact("edge", rec, asset)


def test_an_internally_inconsistent_overlay_is_refused():
    rec = {"n_putative_mutual_ratio_matches": 3, "n_inliers": 2}
    asset = {"correspondences": {"src": [[0, 0]] * 3, "dst": [[0, 0]] * 2,
                                 "inlier": [True, True, False]}}
    with pytest.raises(ev.DemoDataMissing, match="internally inconsistent"):
        ev._check_asset_matches_artefact("edge", rec, asset)


def test_uncertified_assets_are_refused():
    """``build_demo_assets.py`` writes ``all_match`` only when every recomputed
    statistic equalled the recorded one. Loading trusts that flag, so the flag
    being false must stop the demo."""
    ev._assets.cache_clear()
    try:
        import unittest.mock as mock
        bad = {"verified_against_artefact": {"all_match": False}}
        with mock.patch.object(ev, "_read", return_value=bad):
            with pytest.raises(ev.DemoDataMissing, match="not certified"):
                ev._assets()
    finally:
        ev._assets.cache_clear()


# ---------------------------------------------------------------------------
# the cross-edge causal panel
# ---------------------------------------------------------------------------

def test_the_illumination_panel_carries_every_measured_edge():
    ill = ev.illumination_evidence()
    assert ill["n_edges"] == 6
    got = {(r["label"], r["stage"]): (round(r["delta_incidence_deg"], 2),
                                      r["n_inliers"], r["outcome"])
           for r in ill["rows"]}
    assert got[("B → C", "REAL-DATA-03")] == (0.96, 5365, "SUCCEED")
    assert got[("D → A", "REAL-DATA-04")] == (11.73, 1656, "SUCCEED")
    assert got[("C → A", "REAL-DATA-03")] == (38.85, 4, "FAIL")
    assert got[("A → B", "REAL-DATA-03")] == (39.81, 4, "FAIL")
    assert got[("A → B", "REAL-DATA-04")] == (39.81, 7, "FAIL")
    assert got[("B → D", "REAL-DATA-04")] == (51.54, 3, "FAIL")


def test_delta_incidence_separates_the_edges_and_frame_identity_does_not():
    """The claim the panel is allowed to make, stated as a property of the
    data rather than as a sentence someone typed."""
    ill = ev.illumination_evidence()
    assert ill["separation"]["separated_by_delta_incidence"] is True
    assert ill["separation"]["max_succeeding_delta_deg"] == pytest.approx(11.73)
    assert ill["separation"]["min_failing_delta_deg"] == pytest.approx(38.85)
    assert ill["frame_identity"]["every_frame_on_both_sides"] is True
    for f in ill["frames"]:
        assert f["succeeding_edges"] and f["failing_edges"], f["pdsid"]


def test_the_panel_states_its_scope_and_refuses_the_broader_claim():
    ill = ev.illumination_evidence()
    scope = ill["scope"].lower()
    for token in ("lro nac", "mare serenitatis", "five frames",
                  "two ground windows", "incidence only"):
        assert token in scope
    blob = " ".join(ill["not_claimed"]).lower()
    assert "azimuth" in blob
    assert "chandrayaan-2" in blob
    assert "learned matcher" in blob
    assert "in general" in blob


# ---------------------------------------------------------------------------
# claims the demo must never make
# ---------------------------------------------------------------------------

FORBIDDEN = ("chandrayaan", "multi-modal", "multimodal", "azimuth-invariant",
             "universally", "learned matcher", "deep learning", "neural")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["scenario"])
def test_no_forbidden_claim_appears_as_an_assertion(built, case):
    """Every occurrence of a forbidden term must be a denial.

    Scanning for the words alone would fail on the caveats, which correctly
    say these things are NOT present — so each hit is checked to sit in the
    same sentence as a negation.
    """
    blob = json.dumps(built[case["scenario"]]).lower()
    negations = ("no ", "not ", "never", "nothing")
    for term in FORBIDDEN:
        start = 0
        while (i := blob.find(term, start)) != -1:
            window = blob[max(0, i - 220):i + len(term)]
            assert any(n in window for n in negations), (
                f"{term!r} appears in {case['scenario']} without a negation "
                f"nearby: ...{window[-140:]}")
            start = i + len(term)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["scenario"])
def test_every_real_case_carries_its_caveats_and_scope(built, case):
    d = built[case["scenario"]]
    assert len(d["caveats"]) >= 5
    blob = " ".join(d["caveats"]).lower()
    assert "no ground truth" in blob
    assert "azimuth" in blob
    assert "not validated on real data" in blob
    assert "mare serenitatis" in d["scope"].lower()


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["scenario"])
def test_provenance_is_traceable_to_the_archive_bytes(built, case):
    p = built[case["scenario"]]["provenance"]
    assert p["credit"] == "NASA/GSFC/Arizona State University"
    assert len(p["products"]) == 2
    for x in p["products"]:
        assert len(x["bytes_sha256"]) == 64
        assert x["byte_count"] > 0
        assert x["n_lines"] == 4096 and x["n_samples"] == 2048


# ---------------------------------------------------------------------------
# refusals
# ---------------------------------------------------------------------------

def test_a_missing_artefact_is_reported_never_worked_around():
    with pytest.raises(ev.DemoDataMissing, match="will not substitute"):
        ev._read(ev.EXPERIMENTS / "no-such-stage" / "nope.json", "artefact")


def test_an_unknown_edge_in_a_present_artefact_is_refused():
    with pytest.raises(ev.DemoDataMissing, match="is not in"):
        ev._edge("REAL-DATA-04/loop_closure_real_data_04.json", "x -> y")


def test_the_status_endpoint_names_every_file_the_demo_needs():
    st = ev.real_data_status()
    assert st["available"] is True and st["missing"] == []
    joined = " ".join(st["required_files"])
    assert "REAL-DATA-04/loop_closure_real_data_04.json" in joined
    assert "REAL-DATA-04/overlap_real_data_04.json" in joined
    assert "REAL-DATA-03/loop_closure_triplet.json" in joined
    assert "assets/real_data_04.json" in joined
    assert "no network access" in st["note"].lower()


# ---------------------------------------------------------------------------
# the HTTP surface
# ---------------------------------------------------------------------------

def test_the_api_serves_all_three_real_edges_and_the_synthetic_ones():
    d = _client().get("/api/scenarios").json()
    by_id = {s["id"]: s for s in d["scenarios"]}
    assert {"real_da_success", "real_bd_failure", "real_ab_control"} <= set(by_id)
    assert {"easy_same_sun", "coherent_wrong"} <= set(by_id)
    for sid in ("real_da_success", "real_bd_failure", "real_ab_control"):
        assert by_id[sid]["data_source"] == "real_lro_nac"
    assert by_id["coherent_wrong"]["data_source"] == "synthetic"
    assert by_id["coherent_wrong"]["adversarial"] is True


def test_the_superseded_non_overlapping_pair_is_no_longer_offered():
    """REAL-DATA-01's `real_lro_nac` pair was later measured 22.75 km apart,
    sharing 0.0000 km² (E-028, E-029). Showing its failure would demonstrate a
    broken acquisition, not a matcher limit — the confusion REAL-DATA-02 and
    -03 existed to remove."""
    ids = {s["id"] for s in _client().get("/api/scenarios").json()["scenarios"]}
    assert "real_lro_nac" not in ids


def test_the_illumination_endpoint_is_served():
    j = _client().get("/api/evidence/illumination").json()
    assert j["n_edges"] == 6
    assert j["summary"].startswith("Across the measured real-data edges")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["scenario"])
def test_running_a_real_scenario_over_http_returns_the_recorded_result(case):
    r = _client().post("/api/run", json={"scenario": case["scenario"]})
    assert r.status_code == 200
    j = r.json()
    assert j["computation"] == "recorded_artefact"
    assert j["step2_registration"]["n_inliers"] == case["inliers"]
    assert j["outcome"] == case["outcome"]
    assert j["images"]["src"].startswith("/assets/")


def test_a_missing_artefact_surfaces_as_503_not_a_silent_fallback():
    import unittest.mock as mock
    from siim.demo import api
    with mock.patch.object(api, "build_real_scenario",
                           side_effect=ev.DemoDataMissing("tiles are gone")):
        r = _client().post("/api/run", json={"scenario": "real_da_success"})
    assert r.status_code == 503
    assert "tiles are gone" in r.json()["detail"]
