"""Acquisition requirements, and what the products actually on disk can support.

Several tests below encode facts measured from the real Chandrayaan-2 products
in ``data/realdata``. They are regression tests against over-claiming: if
someone later asserts that the OHRC pair on disk demonstrates illumination
invariance, these fail.
"""

from __future__ import annotations

import pytest

from siim.benchmark.acquisition import (
    MEASURED_ENVELOPE_DEG,
    REQUIREMENTS,
    assess_products,
    co_located,
    requirement_by_id,
    spans_overlap,
)
from siim.benchmark.manifest import ProductManifest

# Measured from the delivered PDS4 labels on 2026-09-21.
OHRC_A = ProductManifest(
    product_id="ch2_ohr_ncp_20240425T1012478407_d_img_d18",
    instrument="OHRC", corpus_class="CHANDRAYAAN2", processing_level="calibrated",
    pixel_resolution_m=0.26, spacecraft_altitude_km=102.33,
    solar_incidence_deg=78.476392, sun_azimuth_deg=303.534993,
    sun_elevation_deg=11.523608, orbit_number=20811,
    corners_lat_lon=((-69.074457, 32.194100), (-68.985942, 32.269512),
                     (-69.903718, 32.352484), (-69.813625, 32.426454)),
)
OHRC_B = ProductManifest(
    product_id="ch2_ohr_ncp_20240425T1603031918_d_img_d18",
    instrument="OHRC", corpus_class="CHANDRAYAAN2", processing_level="calibrated",
    pixel_resolution_m=0.26, solar_incidence_deg=79.097263,
    sun_azimuth_deg=304.447986, sun_elevation_deg=10.902737, orbit_number=20814,
    corners_lat_lon=((-69.080380, 32.114577), (-68.996683, 32.195090),
                     (-69.907373, 32.395812), (-69.823404, 32.479809)),
)
TMC2 = ProductManifest(
    product_id="ch2_tmc_ncn_20241214T1937388207_d_img_d18",
    instrument="TMC-2", corpus_class="CHANDRAYAAN2", processing_level="calibrated",
    pixel_resolution_m=4.93, spacecraft_altitude_km=98.62,
    solar_incidence_deg=20.744092, sun_azimuth_deg=268.242487,
    corners_lat_lon=((-33.625187, 23.830219), (-33.741157, 23.868958),
                     (31.255195, 22.407841), (31.141818, 22.458821)),
)


# -- helpers ----------------------------------------------------------------

def test_spans_overlap_basics():
    assert spans_overlap((0.0, 1.0), (0.5, 2.0)) is True
    assert spans_overlap((0.0, 1.0), (1.5, 2.0)) is False
    assert spans_overlap((0.0, 1.0), None) is None


def test_co_location_is_unknown_without_corner_geometry():
    bare = ProductManifest(product_id="x", instrument="LRO_NAC",
                           corpus_class="PROXY")
    assert co_located(OHRC_A, bare) is None


def test_the_two_ohrc_products_do_cover_the_same_ground():
    assert co_located(OHRC_A, OHRC_B) is True


def test_ohrc_and_the_tmc2_strip_are_not_co_located():
    """The OHRC products are south polar; the TMC-2 strip is equatorial."""
    assert co_located(OHRC_A, TMC2) is False


# -- the facts that constrain the experiments -------------------------------

def test_the_ohrc_pair_on_disk_is_not_an_illumination_pair():
    """0.9 deg of azimuth and 0.6 deg of incidence is a control, not a test."""
    d_inc = abs(OHRC_A.solar_incidence_deg - OHRC_B.solar_incidence_deg)
    d_az = abs(OHRC_A.sun_azimuth_deg - OHRC_B.sun_azimuth_deg)
    assert d_inc < 1.0
    assert d_az < 1.0

    req = requirement_by_id("R-OHRC-ILLUM")
    problems = req.check(OHRC_A, OHRC_B)
    assert any("incidence difference" in p for p in problems)


def test_the_ohrc_pair_cannot_satisfy_the_illumination_requirement():
    report = assess_products([OHRC_A, OHRC_B])
    status = next(s for s in report.statuses
                  if s.requirement.requirement_id == "R-OHRC-ILLUM")
    assert status.satisfied is False


def test_no_chandrayaan2_cross_sensor_pair_exists_in_the_data_on_disk():
    report = assess_products([OHRC_A, OHRC_B, TMC2])
    status = next(s for s in report.statuses
                  if s.requirement.requirement_id == "R-OHRC-TMC")
    assert status.satisfied is False
    assert any("same ground" in p
               for _, problems in status.near_misses for p in problems)


def test_without_an_lro_reference_the_ohrc_products_register_to_nothing():
    report = assess_products([OHRC_A, OHRC_B, TMC2])
    status = next(s for s in report.statuses
                  if s.requirement.requirement_id == "R-OHRC-NAC")
    assert status.satisfied is False
    assert "LRO_NAC" in status.missing


def test_a_co_located_nac_reference_satisfies_the_ohrc_requirement():
    nac = ProductManifest(
        product_id="nac.polar", instrument="LRO_NAC", corpus_class="PROXY",
        pixel_resolution_m=0.6, solar_incidence_deg=70.0,
        corners_lat_lon=((-69.0, 32.2), (-69.0, 32.4),
                         (-69.9, 32.2), (-69.9, 32.4)),
    )
    report = assess_products([OHRC_A, nac])
    status = next(s for s in report.statuses
                  if s.requirement.requirement_id == "R-OHRC-NAC")
    assert status.satisfied is True
    assert (OHRC_A.product_id, nac.product_id) in status.satisfying_pairs


def test_iirs_is_absent_and_the_report_says_so_plainly():
    report = assess_products([OHRC_A, OHRC_B, TMC2])
    status = next(s for s in report.statuses
                  if s.requirement.requirement_id == "R-IIRS-WAC")
    assert status.satisfied is False
    assert "no IIRS product is held at all" in status.missing
    assert "IIRS" not in report.instruments_present


# -- the envelope -----------------------------------------------------------

def test_a_derived_product_is_not_a_second_viewing_geometry():
    """The TMC-2 ortho derives from the nadir image: one look, not two.

    Without this check the readiness report claimed the stereo-triplet
    requirement was satisfied by an image paired with its own orthoimage.
    """
    nadir = ProductManifest(
        product_id="ch2_tmc_ncn_20241214T1937388207_d_img_d18",
        instrument="TMC-2", corpus_class="CHANDRAYAAN2",
        acquisition_time="2024-12-14T19:37:38.8207Z",
        solar_incidence_deg=20.74, pixel_resolution_m=4.93,
        corners_lat_lon=((-33.6, 23.8), (-33.7, 23.9), (31.3, 22.4), (31.1, 22.5)),
    )
    ortho = ProductManifest(
        product_id="ch2_tmc_ndn_20241214T1937388207_d_oth_d18",
        instrument="TMC-2", corpus_class="CHANDRAYAAN2",
        acquisition_time="2024-12-14T19:37:38.8207Z",
        solar_incidence_deg=20.74,
        corners_lat_lon=((-33.6, 23.8), (-33.7, 23.9), (31.3, 22.4), (31.1, 22.5)),
    )
    req = requirement_by_id("R-TMC-VIEWPOINT")
    problems = req.check(nadir, ortho)
    assert any("same acquisition" in p for p in problems)

    report = assess_products([nadir, ortho])
    status = next(s for s in report.statuses
                  if s.requirement.requirement_id == "R-TMC-VIEWPOINT")
    assert status.satisfied is False


def test_two_genuinely_distinct_looks_pass_the_acquisition_check():
    fore = ProductManifest(
        product_id="fore", instrument="TMC-2", corpus_class="CHANDRAYAAN2",
        acquisition_time="2024-12-14T19:37:38.0000Z",
        corners_lat_lon=((0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0)),
    )
    aft = ProductManifest(
        product_id="aft", instrument="TMC-2", corpus_class="CHANDRAYAAN2",
        acquisition_time="2024-12-14T19:38:10.0000Z",
        corners_lat_lon=((0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0)),
    )
    assert requirement_by_id("R-TMC-VIEWPOINT").check(fore, aft) == []


def test_a_missing_acquisition_time_is_reported_not_assumed_distinct():
    a = ProductManifest(product_id="a", instrument="TMC-2",
                        corpus_class="CHANDRAYAAN2",
                        corners_lat_lon=((0.0, 0.0), (0.0, 1.0),
                                         (1.0, 0.0), (1.0, 1.0)))
    b = ProductManifest(product_id="b", instrument="TMC-2",
                        corpus_class="CHANDRAYAAN2",
                        corners_lat_lon=((0.0, 0.0), (0.0, 1.0),
                                         (1.0, 0.0), (1.0, 1.0)))
    problems = requirement_by_id("R-TMC-VIEWPOINT").check(a, b)
    assert any("acquisition_time missing" in p for p in problems)


def test_the_ohrc_pair_on_disk_is_two_distinct_acquisitions():
    """They are distinct looks; what they are not is distinct illumination."""
    a = ProductManifest(**{**OHRC_A.to_dict(),
                           "acquisition_time": "2024-04-25T10:12:47.8407Z",
                           "corners_lat_lon": OHRC_A.corners_lat_lon,
                           "shape": OHRC_A.shape})
    b = ProductManifest(**{**OHRC_B.to_dict(),
                           "acquisition_time": "2024-04-25T16:03:03.1918Z",
                           "corners_lat_lon": OHRC_B.corners_lat_lon,
                           "shape": OHRC_B.shape})
    problems = requirement_by_id("R-OHRC-ILLUM").check(a, b)
    assert not any("same acquisition" in p for p in problems)
    assert any("incidence difference" in p for p in problems)


def test_the_ceiling_requirement_is_marked_as_expecting_failure():
    """Asking for a regime the measured envelope says fails is deliberate."""
    req = requirement_by_id("R-OHRC-POLAR-CEILING")
    assert req.expects_failure is True
    assert req.incidence_delta_band[0] == pytest.approx(MEASURED_ENVELOPE_DEG)


def test_comfortable_band_requirements_sit_inside_the_measured_envelope():
    for rid in ("R-OHRC-NAC", "R-TMC-NAC", "R-IIRS-WAC"):
        req = requirement_by_id(rid)
        assert req.incidence_delta_band[1] <= MEASURED_ENVELOPE_DEG


# -- report mechanics -------------------------------------------------------

def test_every_requirement_has_a_unique_id_and_a_rationale():
    ids = [r.requirement_id for r in REQUIREMENTS]
    assert len(ids) == len(set(ids))
    for r in REQUIREMENTS:
        assert r.rationale.strip()
        assert r.title.strip()


def test_requirement_lookup_raises_for_an_unknown_id():
    with pytest.raises(KeyError, match="no requirement"):
        requirement_by_id("R-NOPE")


def test_an_empty_product_set_satisfies_nothing_and_asks_for_everything():
    report = assess_products([])
    assert report.n_products == 0
    assert len(report.satisfied) == 0
    assert len(report.shopping_list()) == len(REQUIREMENTS)


def test_shopping_list_is_ordered_by_priority():
    report = assess_products([])
    priorities = [
        s.requirement.priority
        for s in sorted(report.unsatisfied,
                        key=lambda s: (s.requirement.priority,
                                       s.requirement.requirement_id))
    ]
    assert priorities == sorted(priorities)
    assert report.shopping_list()[0].startswith("[P1]")


def test_a_product_is_never_paired_with_itself():
    report = assess_products([OHRC_A])
    status = next(s for s in report.statuses
                  if s.requirement.requirement_id == "R-OHRC-ILLUM")
    for a, b in status.satisfying_pairs:
        assert a != b
    assert status.satisfied is False


def test_report_serialises_with_the_shopping_list():
    d = assess_products([OHRC_A, TMC2]).as_dict()
    assert d["n_products"] == 2
    assert "shopping_list" in d
    assert len(d["statuses"]) == len(REQUIREMENTS)
    assert all("rationale" in s for s in d["statuses"])
