"""Solar illumination geometry, and the Δazimuth confound check on D-040.

Two layers, deliberately separated.

**Closed-form correctness** (``TestSolarGeometry``): the spherical trigonometry
is pinned against cases whose answer is known without computing it -- the
sub-solar point, its antipode, a quarter-circle away, and the four cardinal
bearings. If these hold, the function is right; no archive data is involved.

**The finding on committed archive data** (``TestConfoundCheckOnRealFrames``):
the premise check that licenses the azimuth, the demonstration that the
archive's own ``SUB_SOLAR_AZIMUTH`` is a different quantity, and the six-edge
separation table. These pin a *result*, so that it cannot silently drift and so
that a reviewer can re-run it in a second.

**What these tests are not.** Nothing here is pre-registered; the check was
written on 2026-08-29 during a pre-freeze audit with all six outcomes visible.
Nothing here changes D-040, D-023, any threshold, any verdict, or any recorded
artefact -- and ``test_no_recorded_artefact_is_consulted_for_an_outcome``
states the one direction of dependence that is allowed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from siim.ingest.solar_geometry import (
    angular_difference_deg,
    incidence_agreement,
    solar_geometry_at,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"
EXPERIMENTS = ROOT / "experiments"

GEOMETRY_MANIFESTS = [
    "real_pair_index_geometry.json",
    "real_pair_index_geometry_C.json",
    "real_frame_d_candidates_index_geometry.json",
    "real_frame_d_selected_index_geometry.json",
]

STAGES = {
    "REAL-DATA-03": ("real_triplet_geo_manifest.json",
                     "REAL-DATA-03/loop_closure_triplet.json"),
    "REAL-DATA-04": ("real_quad_d_geo_manifest.json",
                     "REAL-DATA-04/loop_closure_real_data_04.json"),
}


class TestSolarGeometry:
    """Closed-form cases. No archive data, no files."""

    def test_sub_solar_point_has_zero_incidence(self):
        g = solar_geometry_at(30.0, 10.0, 30.0, 10.0)
        assert g.incidence_deg == pytest.approx(0.0, abs=1e-9)

    def test_antipode_has_incidence_180(self):
        g = solar_geometry_at(0.0, 0.0, 180.0, 0.0)
        assert g.incidence_deg == pytest.approx(180.0, abs=1e-9)

    def test_a_quarter_circle_away_is_the_terminator(self):
        assert solar_geometry_at(0.0, 0.0, 90.0, 0.0).incidence_deg == pytest.approx(90.0)
        assert solar_geometry_at(0.0, 0.0, 0.0, 90.0).incidence_deg == pytest.approx(90.0)

    def test_incidence_is_symmetric_in_the_two_points(self):
        """Great-circle distance does not care which end you stand on."""
        a = solar_geometry_at(22.0, 19.7, 90.1, -0.9).incidence_deg
        b = solar_geometry_at(90.1, -0.9, 22.0, 19.7).incidence_deg
        assert a == pytest.approx(b, abs=1e-9)

    @pytest.mark.parametrize("s_lon,s_lat,expected,label", [
        (0.0, 40.0, 0.0, "sun due north"),
        (0.0, -40.0, 180.0, "sun due south"),
        (40.0, 0.0, 90.0, "sun due east"),
        (-40.0, 0.0, 270.0, "sun due west"),
    ])
    def test_cardinal_azimuths(self, s_lon, s_lat, expected, label):
        """Azimuth is clockwise from north, TOWARDS the sub-solar point."""
        got = solar_geometry_at(0.0, 0.0, s_lon, s_lat).azimuth_deg
        assert got == pytest.approx(expected, abs=1e-6), label

    def test_azimuth_is_in_range(self):
        rng = np.random.default_rng(20260829)
        for _ in range(200):
            g = solar_geometry_at(*rng.uniform([-180, -89], [180, 89]),
                                  *rng.uniform([-180, -89], [180, 89]))
            assert 0.0 <= g.azimuth_deg < 360.0
            assert 0.0 <= g.incidence_deg <= 180.0

    def test_angular_difference_wraps(self):
        assert angular_difference_deg(350.0, 10.0) == pytest.approx(20.0)
        assert angular_difference_deg(10.0, 350.0) == pytest.approx(20.0)
        assert angular_difference_deg(0.0, 180.0) == pytest.approx(180.0)
        assert angular_difference_deg(95.04, 178.64) == pytest.approx(83.60, abs=1e-2)

    def test_angular_difference_never_exceeds_180(self):
        rng = np.random.default_rng(7)
        for a, b in rng.uniform(0, 360, (300, 2)):
            assert 0.0 <= angular_difference_deg(a, b) <= 180.0

    def test_incidence_agreement_reports_the_signed_difference(self):
        got, diff = incidence_agreement(0.0, 0.0, 90.0, 0.0, 88.0)
        assert got == pytest.approx(90.0)
        assert diff == pytest.approx(2.0)


def _products() -> dict:
    out: dict = {}
    for name in GEOMETRY_MANIFESTS:
        p = MANIFESTS / name
        if p.exists():
            out.update(json.loads(p.read_text(encoding="utf-8"))["products"])
    return out


def _frames_and_edges():
    products = _products()
    frames, edges = {}, []
    for stage, (manifest, reg_rel) in STAGES.items():
        man = json.loads((MANIFESTS / manifest).read_text(encoding="utf-8"))
        lon_t, lat_t = man["target_ground_point_lon_lat"]
        for pdsid in man["pair"]:
            f = products[pdsid]["fields"]
            g = solar_geometry_at(lon_t, lat_t,
                                  float(f["SUB_SOLAR_LONGITUDE"]),
                                  float(f["SUB_SOLAR_LATITUDE"]))
            frames[(stage, pdsid)] = {
                "published": float(f["INCIDENCE_ANGLE"]),
                "recomputed": g.incidence_deg,
                "ground_az": g.azimuth_deg,
                "archive_az": float(f["SUB_SOLAR_AZIMUTH"]),
            }
        reg = json.loads((EXPERIMENTS / reg_rel).read_text(encoding="utf-8"))
        for e in reg["edges"]:
            src, dst = e["edge"].split(" -> ")
            a, b = frames[(stage, src)], frames[(stage, dst)]
            edges.append({
                "stage": stage, "edge": e["edge"],
                "d_inc": abs(a["published"] - b["published"]),
                "d_az": angular_difference_deg(a["ground_az"], b["ground_az"]),
                "n_inliers": e["n_inliers"],
                "outcome": "FAIL" if e["n_inliers_failure_flag"] else "SUCCEED",
            })
    return frames, edges


class TestConfoundCheckOnRealFrames:
    """The finding, on committed archive data. Re-runs in milliseconds."""

    def test_recomputed_incidence_matches_the_archive_column(self):
        """The premise. Two published columns must reproduce a third.

        This is a cross-check with genuine discriminating power, which is what
        E-027's `NORTH_AZIMUTH` comparison lacked: a frame-convention error in
        the sub-solar coordinates moves the answer by tens of degrees, and the
        four frames span 18-70 deg of incidence, so agreement is not automatic.
        """
        frames, _ = _frames_and_edges()
        assert frames, "no real frames available to check"
        worst = max(abs(v["recomputed"] - v["published"]) for v in frames.values())
        assert worst <= 2.0, (
            f"recomputed incidence is {worst:.2f} deg from the published "
            "INCIDENCE_ANGLE; the sub-solar columns are not being read in the "
            "frame this module assumes, and the azimuth derived from them "
            "must not be used")

    def test_archive_sub_solar_azimuth_is_not_the_ground_azimuth(self):
        """RL-032b's caution, upheld by measurement rather than argued.

        The archive column is a real quantity in some frame; it is NOT the
        solar azimuth at the target, and this pins that so nobody reaches for
        it as a shortcut later.
        """
        frames, _ = _frames_and_edges()
        seps = [angular_difference_deg(v["archive_az"], v["ground_az"])
                for v in frames.values()]
        assert max(seps) > 30.0, (
            "the archive SUB_SOLAR_AZIMUTH now agrees with the computed ground "
            "azimuth; if that is real, RL-032b can be closed the other way and "
            "this test should be replaced rather than relaxed")

    def test_six_edges_are_present_with_two_successes(self):
        _, edges = _frames_and_edges()
        assert len(edges) == 6
        assert sum(e["outcome"] == "SUCCEED" for e in edges) == 2
        assert sum(e["outcome"] == "FAIL" for e in edges) == 4

    def test_delta_incidence_separates_the_outcomes(self):
        """Restates REAL-DATA-04's own observation, from the artefacts."""
        _, edges = _frames_and_edges()
        hi_s = max(e["d_inc"] for e in edges if e["outcome"] == "SUCCEED")
        lo_f = min(e["d_inc"] for e in edges if e["outcome"] == "FAIL")
        assert hi_s < lo_f, "Dincidence no longer separates the six edges"
        assert hi_s == pytest.approx(11.73, abs=0.01)
        assert lo_f == pytest.approx(38.85, abs=0.01)

    def test_delta_azimuth_does_NOT_separate_the_outcomes(self):
        """The confound check's actual result, pinned.

        The strongest success (D->A, 1656 inliers) sits at Dazimuth ~50 deg,
        ABOVE three of the four failures. So on these six edges Dazimuth does
        not order the outcomes and D-040's attribution is not simply Dazimuth
        wearing an incidence label.

        This does NOT establish that azimuth is irrelevant: n = 6, the two
        variables are themselves correlated, and no azimuth-controlled real
        pair has ever been acquired. That debt is unchanged.
        """
        _, edges = _frames_and_edges()
        hi_s = max(e["d_az"] for e in edges if e["outcome"] == "SUCCEED")
        lo_f = min(e["d_az"] for e in edges if e["outcome"] == "FAIL")
        assert hi_s >= lo_f, (
            "Dazimuth now separates the six edges as cleanly as Dincidence "
            "does; the confound is live again and D-040's scope must be "
            "revisited rather than this test relaxed")
        assert hi_s == pytest.approx(50.29, abs=0.05)

    def test_a_real_pair_is_still_not_azimuth_controlled(self):
        """The debt this check does NOT discharge.

        An azimuth-CONTROLLED pair means two frames matched in incidence and
        differing in azimuth. No such pair exists here: every edge that differs
        much in azimuth also differs in incidence.
        """
        _, edges = _frames_and_edges()
        controlled = [e for e in edges if e["d_inc"] < 5.0 and e["d_az"] > 20.0]
        assert not controlled, (
            "an azimuth-controlled edge now exists; REAL-DATA-04's evidence "
            "debt can be revisited")

    def test_no_recorded_artefact_is_consulted_for_an_outcome(self):
        """The outcome label comes from the pre-registered rule, not from here.

        The check reads ``n_inliers_failure_flag`` -- what the stage recorded
        under D-023 -- rather than re-deriving success from any quantity this
        module computes. That is the one direction of dependence allowed: the
        confound check may read the decision, never influence it.
        """
        _, edges = _frames_and_edges()
        for e in edges:
            expected = "FAIL" if e["n_inliers"] <= 8 else "SUCCEED"
            assert e["outcome"] == expected, (
                f"{e['edge']}: recorded flag disagrees with D-023's rule")
