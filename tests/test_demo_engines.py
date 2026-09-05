"""The two-engines panel and the live registration endpoint of the demo.

The panel's numbers are read from the EXP-007 and REAL-DATA-07 artefacts and
are pinned here to the values those stages recorded, exactly as the
illumination panel's are. The live endpoint is checked for what it labels
itself, never for a number: nothing it computes is a recorded result.
"""

from __future__ import annotations

import base64
import io
import re

import numpy as np
import pytest

from siim.demo import api
from siim.demo import evidence as ev

pytestmark = pytest.mark.skipif(
    not ev.engines_status()["available"],
    reason="EXP-007 or REAL-DATA-07 artefacts are not on disk")


def _client():
    from fastapi.testclient import TestClient
    return TestClient(api.app)


@pytest.fixture(scope="module")
def eng():
    return ev.engines_evidence()


@pytest.fixture(scope="module")
def page() -> str:
    return (api.STATIC / "index.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# read, not typed
# ---------------------------------------------------------------------------

def test_tier1_rows_are_the_recorded_exp007_numbers(eng):
    got = {(r["edge"], r["stage"]): (r["b1_inliers"], r["b4l_inliers"], r["b4l_geometry"], r["counts_for_s3"])
           for r in eng["exp007"]["tier1"]}
    assert got[("C -> A", "REAL-DATA-03")] == (4, 56, "CONSISTENT", True)
    assert got[("A -> B", "REAL-DATA-03")] == (4, 38, "INCONCLUSIVE", False)
    assert got[("A -> B", "REAL-DATA-04")] == (7, 3, "INCONCLUSIVE", False)
    assert got[("B -> D", "REAL-DATA-04")] == (3, 3, "INCONSISTENT", False)
    assert eng["exp007"]["s3_met"] is True
    assert eng["exp007"]["s1_met"] is False


def test_tier2_rows_show_three_of_four_pairs_converted_and_the_fourth_not(eng):
    t2 = {(r["edge"], r["window"], r["k"]): r for r in eng["exp007"]["tier2"]}
    assert t2[("A -> B", "RD03-target", 16)]["b4l_inliers"] == 2042
    assert t2[("A -> B", "RD03-target", 16)]["b4l_success"] is True
    assert t2[("C -> A", "RD03-target", 32)]["b4l_inliers"] == 475
    assert t2[("A -> B", "RD04-target", 8)]["b4l_inliers"] == 1409
    bd = [t2[("B -> D", "RD04-target", k)] for k in (8, 16, 32)]
    assert [r["b4l_inliers"] for r in bd] == [0, 5, 37]
    assert not any(r["b4l_success"] for r in bd)
    # RootSIFT's marginal passes are shown as what they are
    assert t2[("A -> B", "RD04-target", 8)]["b1_inliers"] == 9
    assert t2[("A -> B", "RD04-target", 8)]["b1_pass"] is True


def test_rd07_summary_numbers_are_the_recorded_ones(eng):
    r7 = eng["rd07"]
    assert r7["n_pairs"] == 42
    assert r7["b1_successes"] == 20 and r7["b4l_successes"] == 17
    assert r7["wrong_pass"]["b1"] == {"n_pass": 20, "n_wrong_pass": 0}
    assert r7["wrong_pass"]["b4l"] == {"n_pass": 17, "n_wrong_pass": 0}
    assert r7["significance"]["b1_pooled_p"] == pytest.approx(0.00419, abs=1e-4)
    assert r7["significance"]["b1_rd04_p"] > 0.05
    assert r7["significance"]["s5_met"] is False
    assert r7["envelope"]["b1_largest_bin_ge_0_8"] == 10
    assert r7["envelope"]["b4l_largest_bin_ge_0_8"] == 10
    assert r7["envelope"]["s3_met"] is False
    assert r7["replication"]["s1_met"] is False
    assert r7["north_up_changed"] == ["nac.m1271742202lc -> nac.m1335207975rc"]
    bins = {b["bin_deg"]: b for b in r7["bins"]}
    assert bins[40]["b1_success_rate"] == 0.0 and bins[50]["b4l_success_rate"] == 0.0


def test_the_panel_states_scope_and_negates_every_forbidden_claim(eng):
    scope = eng["scope"].lower()
    for token in ("lro nac", "mare serenitatis", "incidence only", "no ground truth"):
        assert token in scope
    negations = ("no ", "not ", "never", "nothing")
    text = " ".join([eng["summary"], eng["scope"], *eng["not_claimed"]]).lower()
    for term in ("chandrayaan", "multi-modal", "learned matcher", "accuracy", "azimuth"):
        for m in re.finditer(re.escape(term), text):
            window = text[max(0, m.start() - 80): m.end() + 80]
            assert any(n in window for n in negations), f"{term!r} without a negation"


def test_the_engines_sources_are_openable_artefacts(eng):
    c = _client()
    for rel in eng["sources"]:
        r = c.get(f"/artefact/{rel}")
        assert r.status_code == 200, rel
        assert r.json()  # served verbatim as JSON


def test_the_scenarios_endpoint_advertises_the_panel_and_the_live_run():
    d = _client().get("/api/scenarios").json()
    assert d["data_status"]["engines_panel"].startswith("AVAILABLE")
    assert "live" in d["data_status"]["live_register"].lower()


def test_the_page_renders_the_panel_and_offers_the_live_card(page):
    assert "function enginesPanel" in page and "${enginesPanel(vm)}" in page
    assert "/api/evidence/engines" in page
    assert 'id="live-open"' in page and '"/api/register"' in page
    assert "never a recorded number" in page


def test_the_live_card_is_not_wired_as_a_scenario_and_survives_the_boot_race(page):
    """Two defects found in the 2026-09-05 browser check, pinned to the template.

    1. The generic scenario handler is attached to every `button.case` after
       the fetches resolve, so it overrode the live card's handler and posted
       the scenario "__live__" to /api/run. It must skip the live button.
    2. Boot auto-selects the first real case when its fetches complete; on a
       loaded CPU that is seconds after the page is usable, and it clobbered a
       live card the reader had already opened. It must yield to a choice.
    """
    assert 'button.case:not(#live-open)' in page
    assert 'current = "__live__"' in page
    assert 'if (current === "__live__")' in page
    assert 'current === null && !document.getElementById("live-src")' in page
    # the preview images take the API's data URLs verbatim
    assert 'src="${esc(d.source_png)}"' in page and 'src="${esc(d.registered_png)}"' in page
    assert 'src="data:image/png;base64,${d.' not in page


# ---------------------------------------------------------------------------
# the live endpoint: labelled live, never a recorded number
# ---------------------------------------------------------------------------

def _png_b64(a: np.ndarray) -> str:
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def pair(rng):
    from scipy import ndimage
    from siim.geometry import translation, warp
    base = ndimage.gaussian_filter(rng.normal(size=(384, 384)), sigma=2.5)
    yy, xx = np.mgrid[0:384, 0:384].astype(float)
    for cx, cy, r in rng.uniform(40, 340, size=(20, 3)) * np.array([1, 1, 0.07]):
        base -= 0.9 * np.exp(-((np.hypot(xx - cx, yy - cy) / max(r, 6.0)) ** 2))
    base = (base - base.min()) / (base.max() - base.min())
    ref, valid = warp(base, translation(5.5, -3.25), cval=np.nan)
    return base, np.where(valid, ref, np.nanmedian(ref))


def test_live_register_labels_itself_and_runs_the_full_pipeline(pair):
    src, ref = pair
    r = _client().post("/api/register", json={"source_png": _png_b64(src),
                                                "reference_png": _png_b64(ref), "engine": "B1"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["computation"] == "live" and d["data_source"] == "user_supplied"
    assert d["pipeline_order"] == ["estimate", "refine", "reestimate", "verify"]
    assert d["verdict"]["status"] in ("INCONCLUSIVE", "VERIFIED")
    assert d["summary"]["model_selected_by"] == "held_out_on_refined_points"
    assert d["verdict"]["metrics"]["model_selected_by"] == "held_out_on_refined_points"
    assert "fit_rmse" in d["verdict"]["excluded"]
    # the page uses these fields verbatim as <img src>, so they must be full data URLs
    for k in ("source_png", "reference_png", "registered_png"):
        assert str(d[k]).startswith("data:image/png;base64,"), k
    assert any("no recorded artefact" in c.lower() for c in d["caveats"])


def test_live_register_refuses_garbage_and_unknown_engines(pair):
    src, ref = pair
    c = _client()
    r = c.post("/api/register", json={"source_png": "bm90IGFuIGltYWdl", "reference_png": _png_b64(ref)})
    assert r.status_code == 400
    r = c.post("/api/register", json={"source_png": _png_b64(src), "reference_png": _png_b64(ref),
                                      "engine": "B9"})
    assert r.status_code == 400


def test_live_register_rejects_unrelated_images_without_a_product(pair, rng):
    src, _ = pair
    noise = rng.uniform(size=src.shape)
    r = _client().post("/api/register", json={"source_png": _png_b64(src),
                                                "reference_png": _png_b64(noise), "engine": "B1"})
    assert r.status_code == 200
    d = r.json()
    assert d["verdict"]["status"] == "REJECTED"
    assert d["registered_png"] is None
    assert d["summary"]["model_selected_by"] == "none"


@pytest.mark.skipif(not ev.RD07_AMENDED_ARTEFACT.exists(), reason="amended RD-07 artefact not on disk")
def test_the_amended_run_is_shown_beside_the_original_not_in_place_of_it(eng):
    am = eng["rd07_amended"]
    assert am is not None
    assert eng["rd07"]["replication"]["s1_met"] is False          # original, preserved
    assert am["replication"]["s1_met"] is True                    # amended (E-037)
    assert am["significance"]["b1_pooled_p"] == pytest.approx(0.00119, abs=1e-4)
    assert am["significance"]["s5_met"] is True
    assert am["wrong_pass"]["b1"] == {"n_pass": 25, "n_wrong_pass": 0}
    assert am["wrong_pass"]["b4l"] == {"n_pass": 24, "n_wrong_pass": 0}
    assert am["envelope"]["b1_largest_bin_ge_0_8"] == 20
    assert "north_up_east_right" in am["orientation"]
    assert am["source"] in eng["sources"]
