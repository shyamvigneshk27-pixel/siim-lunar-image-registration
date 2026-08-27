"""What the demonstration page *says*, as distinct from what it computes.

The numbers behind the demo are covered by ``test_demo_real_data.py`` and
``test_demo_evidence_integrity.py``. This file covers the other half of the
same risk: a page whose arithmetic is right and whose presentation misleads the
reader anyway. Three such defects were found in the September 2 rehearsal and
are pinned here.

1. **An advertised provenance path that nothing serves.** The panel prints the
   files its numbers were read from, under the heading "open it and check".
   The paths were plain text and no route served them, so taking the invitation
   up meant leaving the demo for an editor and a repository checkout -- the one
   check that answers *"did you hard-code these numbers?"* was the one check the
   page could not perform. The files are now served, from an allow-list built
   out of the same advertised paths, so nothing outside what the page already
   displays is reachable.

2. **A success mark on the case that exists to be wrong.** The adversarial
   construction satisfies the pre-registered inlier rule -- 1273 inliers -- on
   an estimate deliberately displaced by one crater spacing. The top-of-page
   mark read "REGISTRATION SUCCEEDS", above a REJECTED verdict and a 64 px
   ground-truth error, which is the claim the rest of the page exists to
   refute. It now names the rule that passed instead of asserting an outcome.

3. **A question asked of the wrong verdict.** The note explaining why the
   decisive check did not run was headed *Why not "VERIFIED"?* on every real
   case, including the two that are REJECTED -- where the answer is not that
   the check is missing but that the edge failed on named evidence.

Nothing here touches a verdict criterion, a matcher, or a recorded artefact.
The page is a static template, so the checks on its wording are checks on that
template: they are written to fail if a defect is reintroduced by editing the
line back, which is how it would be reintroduced.
"""

from __future__ import annotations

import re

import pytest

from siim.demo import api
from siim.demo import evidence as ev

REAL = ["real_da_success", "real_bd_failure", "real_ab_control"]

pytestmark = pytest.mark.skipif(
    not ev.real_data_status()["available"],
    reason="REAL-DATA-04 artefacts or demo assets are not on disk")


def _client():
    from fastapi.testclient import TestClient
    return TestClient(api.app)


@pytest.fixture(scope="module")
def page() -> str:
    return (api.STATIC / "index.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. every path the page offers to open, opens
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", REAL)
def test_every_advertised_artefact_is_served_verbatim(scenario):
    """The bytes served are the bytes on disk -- that is the whole claim.

    Reformatting, pretty-printing or re-serialising on the way out would make
    the response evidence about this endpoint rather than about the file, and
    the point of the link is to show the file.
    """
    client = _client()
    for a in ev.build_real_scenario(scenario)["provenance"]["artefacts"]:
        r = client.get("/artefact/" + a["path"])
        assert r.status_code == 200, f"{a['path']} is advertised but not served"
        assert r.content == (ev.ROOT / a["path"]).read_bytes(), (
            f"{a['path']} is served, but not byte for byte")


@pytest.mark.parametrize("scenario", REAL)
def test_the_artefact_link_shows_the_file_instead_of_downloading_it(scenario):
    """A download lands in a folder; the demo needs it on screen."""
    client = _client()
    for a in ev.build_real_scenario(scenario)["provenance"]["artefacts"]:
        r = client.get("/artefact/" + a["path"])
        assert r.headers["content-type"].startswith("application/json")
        assert r.headers.get("content-disposition", "").startswith("inline")


def test_the_illumination_panels_sources_are_openable_too():
    """The cross-edge panel cites REAL-DATA-03 as well, and cites it on screen."""
    client = _client()
    for src in ev.illumination_evidence()["sources"]:
        assert client.get("/artefact/" + src).status_code == 200


@pytest.mark.parametrize("path", [
    "pyproject.toml", "README.md", "src/siim/demo/api.py",
    "data/manifests", "experiments/REAL-DATA-04",
])
def test_a_file_the_page_does_not_advertise_is_not_served(path):
    """An allow-list, not a directory mount.

    The endpoint exists to back up what the page prints. Anything else on disk
    is outside its purpose, and a demo server that hands out arbitrary
    repository files is a different thing from one that shows its sources.
    """
    r = _client().get("/artefact/" + path)
    assert r.status_code == 404
    assert "advertises" in r.json()["detail"]


@pytest.mark.parametrize("path", [
    "../pyproject.toml",
    "experiments/../../pyproject.toml",
    "..%2F..%2Fpyproject.toml",
    "experiments/REAL-DATA-04/../../pyproject.toml",
])
def test_no_path_outside_the_advertised_set_can_be_reached(path):
    """Traversal has nothing to reach: membership is decided before any I/O."""
    assert _client().get("/artefact/" + path).status_code == 404


def test_an_advertised_artefact_that_is_missing_is_named_not_substituted(
        monkeypatch):
    """The same rule as everywhere else here: say which file, show none."""
    monkeypatch.setattr(api, "advertised_artefacts",
                        lambda: frozenset({"experiments/GHOST/absent.json"}))
    r = _client().get("/artefact/experiments/GHOST/absent.json")
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert "experiments/GHOST/absent.json" in detail
    assert "will not substitute or recompute" in detail


def test_the_allow_list_is_exactly_what_the_page_advertises():
    """No file is reachable whose path the reader was not shown."""
    advertised = set()
    for sid in REAL:
        advertised.update(a["path"] for a in
                          ev.build_real_scenario(sid)["provenance"]["artefacts"])
    advertised.update(ev.illumination_evidence()["sources"])
    assert set(api.advertised_artefacts()) == advertised


def test_the_provenance_table_links_every_path_it_prints(page):
    """The path in the table is an anchor to the endpoint that serves it.

    Printing a path the reader cannot click is what made the invitation empty
    in the first place; a table cell that renders the path as bare text again
    would restore the defect without failing any other test here.
    """
    assert re.search(r'href="/artefact/\$\{esc\(a\.path\)\}"', page), (
        "the provenance table must link each advertised path to /artefact/")
    assert "Each path opens the raw file" in page


# ---------------------------------------------------------------------------
# 2. the adversarial case is never marked a success
# ---------------------------------------------------------------------------


def test_the_adversarial_case_passes_the_inlier_rule_and_is_still_wrong():
    """The fact the page's top mark has to survive.

    D-023 (reject at <= 8 inliers) passes here, comfortably, on an answer that
    is 64 px wrong. A mark derived from the inlier count alone must therefore
    not read as an outcome -- which is why the page names the rule instead.
    """
    j = _client().post("/api/run", json={"scenario": "coherent_wrong"}).json()
    assert j["adversarial_construction"] is True
    assert j["verdict"]["metrics"]["n_inliers"] > ev.INLIER_FAILURE_RULE
    assert j["verdict"]["status"] == "REJECTED"
    gt = j["ground_truth"]
    assert gt["available"] is True and gt["true_error_median_px"] > 8.0


def test_the_page_marks_the_adversarial_case_by_the_rule_that_passed(page):
    """"REGISTRATION SUCCEEDS" must be unreachable for an adversarial case."""
    body = page[page.index("function outcomePill"):]
    body = body[:body.index("\n}\n")]
    assert "d.adversarial_construction" in body
    assert (body.index("d.adversarial_construction")
            < body.index("REGISTRATION SUCCEEDS")), (
        "the adversarial branch must be taken before the success wording")
    assert "INLIER RULE PASSES" in body and "WRONG" in body
    assert page.count("✓ REGISTRATION SUCCEEDS") == 1, (
        "the success mark must be emitted from exactly one place -- the "
        "outcome mark's non-adversarial branch")


def test_the_outcome_mark_goes_through_the_one_function_that_knows(page):
    """No second, unguarded copy of the mark may render the pill."""
    assert re.search(r'class="pill outcome-\$\{esc\(outcomePill\(', page)
    assert not re.search(r'class="pill outcome-\$\{vm\.outcome\}"', page)


# ---------------------------------------------------------------------------
# 3. the verdict note asks its question only where the question applies
# ---------------------------------------------------------------------------


def test_the_not_verified_question_is_asked_only_of_an_inconclusive_verdict(
        page):
    """On a REJECTED edge the answer is the rejection, not the missing check."""
    assert re.search(
        r'v\.status === "INCONCLUSIVE" \? "Why not [^"]*VERIFIED[^"]*"', page)
    assert "Why loop closure did not run here" in page


def test_the_two_failing_real_edges_are_rejected_and_still_explain_the_gap():
    """Both halves have to be true for the conditional heading to matter."""
    for sid in ("real_bd_failure", "real_ab_control"):
        d = ev.build_real_scenario(sid)
        assert d["verdict"]["status"] == "REJECTED"
        assert "loop_error_px is passed as None" in d["verdict_note"]
    assert ev.build_real_scenario("real_da_success")["verdict"]["status"] == (
        "INCONCLUSIVE")


# ---------------------------------------------------------------------------
# 4. a case switch lands on the case
# ---------------------------------------------------------------------------


def test_choosing_a_case_scrolls_to_the_top_of_it(page):
    """The stage is re-rendered in place, so the scroll offset survives it.

    Without an explicit reset, clicking "B -> D" from the bottom of the
    previous case leaves the reader halfway down step 1, with no title, no
    outcome mark and no case name on screen.
    """
    render = page[page.index("function render(d)"):]
    render = render[:render.index("/* ------")]
    assert "window.scrollTo(0, 0)" in render


def test_the_evidence_is_one_scroller(page):
    """No nested overflow pane may wrap the stage itself."""
    stage = re.search(r"section#stage\{([^}]*)\}", page).group(1)
    assert "overflow" not in stage


def test_the_page_is_never_served_from_the_browsers_cache():
    """A stale page is the worst shape a demo defect can take.

    Without ``Cache-Control`` the response is heuristically cacheable, and a
    browser re-opening the URL served the previous version of the page with no
    error and nothing on screen to say so -- so a fix applied minutes earlier
    appeared not to have worked. Observed in the September 2 rehearsal.
    """
    r = _client().get("/")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-store"


def test_the_tile_previews_stay_cacheable():
    """The counterpart: /assets is immutable and must not be re-fetched.

    Re-downloading the NAC previews on every case switch is a visible stutter
    on stage, so the no-store rule stops at the page itself.
    """
    r = _client().get("/assets/tile_nac.m1271742202lc.png")
    assert r.status_code == 200
    assert "no-store" not in r.headers.get("cache-control", "")
