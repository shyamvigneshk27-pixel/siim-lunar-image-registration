"""Coverage for the REAL-DATA-05 frame-E screen, ``scripts/screen_frame_e.py``.

The E screen is the D screen plus three hard filters, and the thing worth
defending in a test is that it only ever *tightens*. Its selection logic is
imported from ``screen_frame_d.py`` rather than copied, so the tests here are
about the additions:

* **H6** rejects an off-nadir frame, on emission alone;
* **H7** rejects the wrong NAC camera, on camera alone;
* **H5** is applied in the fixed-point tier too, which the D screen never did;
* a candidate the imported screen already rejected keeps its imported reason,
  so no REAL-DATA-04 criterion can be loosened here;
* every candidate is accounted for in the funnel, admissible or not.

No network access. Rows and index fields are constructed by hand.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location(
    "screen_frame_e", ROOT / "scripts" / "screen_frame_e.py")
sfe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sfe)

from siim.ingest.footprint import FrameCorners  # noqa: E402

INCUMBENT = (1, -1)


def _corners(*, along: int = 1, cross: int = -1) -> FrameCorners:
    lat_top, lat_bot = (19.0, 21.0) if along == 1 else (21.0, 19.0)
    lon_left, lon_right = (22.0, 22.2) if cross == 1 else (22.2, 22.0)
    return FrameCorners(
        upper_left=(lon_left, lat_top), upper_right=(lon_right, lat_top),
        lower_left=(lon_left, lat_bot), lower_right=(lon_right, lat_bot),
        lines=52224, samples=5064)


def _admissible_row(pdsid: str = "nac.m1111111111lc") -> dict:
    """What the imported screen returns for a candidate that passed."""
    return {"pdsid": pdsid, "incidence_deg": 25.0, "map_resolution_m": 1.0,
            "admissible": True, "rejected_by": None,
            "max_resolution_ratio": 1.05, "abs_d_incidence_vs_A": 4.95}


def _apply(row, rec, **kw):
    kw.setdefault("emission_max", 5.0)
    kw.setdefault("want_camera", "LEFT")
    kw.setdefault("fields", None)
    kw.setdefault("authoritative", None)
    kw.setdefault("anchor_orientation", INCUMBENT)
    kw.setdefault("apply_orientation", False)
    return sfe.apply_e_filters(row, rec, **kw)


# --------------------------------------------------------------------------
# camera derivation
# --------------------------------------------------------------------------


@pytest.mark.parametrize("pdsid,expected", [
    ("nac.m1271742202lc", "LEFT"),      # frame A
    ("nac.m1335207975rc", "RIGHT"),     # frame B
    ("nac.m1452560468lc", "LEFT"),      # frame C
    ("nac.m1299958135lc", "LEFT"),      # frame D
    ("NAC.M1299958135LC", "LEFT"),
    ("something_else", None),
])
def test_camera_is_read_from_the_archive_product_id_suffix(pdsid, expected):
    assert sfe.nac_frame_id_from_pdsid(pdsid) == expected


# --------------------------------------------------------------------------
# H6 -- emission, on its own
# --------------------------------------------------------------------------


def test_h6_rejects_an_off_nadir_frame_on_emission_alone():
    row = _apply(_admissible_row(), {"Emission_angle": 21.4})
    assert row["admissible"] is False
    assert row["rejected_by"].startswith("filter H6")
    assert "21.4" in row["rejected_by"]


def test_h6_admits_a_near_nadir_frame_that_differs_in_nothing_else():
    row = _apply(_admissible_row(), {"Emission_angle": 1.75})
    assert row["admissible"] is True
    assert row["emission_deg_used"] == pytest.approx(1.75)


def test_h6_rejects_a_frame_with_no_published_emission():
    row = _apply(_admissible_row(), {})
    assert row["admissible"] is False
    assert row["rejected_by"].startswith("filter H6")


def test_h6_prefers_the_named_index_column_over_the_ode_summary():
    row = _apply(_admissible_row(), {"Emission_angle": 1.0},
                 fields={"nac.m1111111111lc": {"EMISSION_ANGLE": "31.0",
                                               "NAC_FRAME_ID": "LEFT"}})
    assert row["admissible"] is False
    assert row["rejected_by"].startswith("filter H6")
    assert row["emission_source"] == "index table, NAMED column"


# --------------------------------------------------------------------------
# H7 -- camera, on its own
# --------------------------------------------------------------------------


def test_h7_rejects_the_wrong_camera_on_camera_alone():
    row = _apply(_admissible_row("nac.m1111111111rc"),
                 {"Emission_angle": 1.5})
    assert row["admissible"] is False
    assert row["rejected_by"].startswith("filter H7")
    assert "RIGHT" in row["rejected_by"]


def test_h7_admits_the_required_camera():
    row = _apply(_admissible_row("nac.m1111111111lc"),
                 {"Emission_angle": 1.5})
    assert row["admissible"] is True
    assert row["nac_frame_id_used"] == "LEFT"


def test_h7_rejects_a_candidate_whose_id_and_index_row_disagree():
    row = _apply(_admissible_row("nac.m1111111111lc"),
                 {"Emission_angle": 1.5},
                 fields={"nac.m1111111111lc": {"EMISSION_ANGLE": "1.5",
                                               "NAC_FRAME_ID": "RIGHT"}})
    assert row["admissible"] is False
    assert row["rejected_by"].startswith("filter H7")
    assert "cannot be established" in row["rejected_by"]


def test_h7_can_be_disabled_without_touching_h6():
    row = _apply(_admissible_row("nac.m1111111111rc"),
                 {"Emission_angle": 1.5}, want_camera=None)
    assert row["admissible"] is True


# --------------------------------------------------------------------------
# H5 in the fixed-point tier -- the gap the D screen left
# --------------------------------------------------------------------------


def test_h5_rejects_a_rotated_frame_in_the_fixed_point_tier():
    pid = "nac.m1111111111lc"
    row = _apply(_admissible_row(pid), {"Emission_angle": 1.5},
                 authoritative={pid: _corners(along=-1, cross=-1)},
                 apply_orientation=True)
    assert row["admissible"] is False
    assert row["rejected_by"].startswith("filter H5")
    assert row["orientation_signature"] == [-1, -1]


def test_h5_admits_a_matching_frame_in_the_fixed_point_tier():
    pid = "nac.m1111111111lc"
    row = _apply(_admissible_row(pid), {"Emission_angle": 1.5},
                 authoritative={pid: _corners(along=1, cross=-1)},
                 apply_orientation=True)
    assert row["admissible"] is True
    assert row["orientation_signature"] == [1, -1]


def test_h5_refuses_to_assume_an_orientation_it_cannot_verify():
    row = _apply(_admissible_row(), {"Emission_angle": 1.5},
                 authoritative={}, apply_orientation=True)
    assert row["admissible"] is False
    assert row["rejected_by"].startswith("filter H5")
    assert "not assumed" in row["rejected_by"]


# --------------------------------------------------------------------------
# the additions can only tighten
# --------------------------------------------------------------------------


def test_a_row_the_imported_screen_rejected_is_returned_untouched():
    rejected = {"pdsid": "nac.m1111111111lc", "admissible": False,
                "rejected_by": "filter 5: incidence 44.00 outside the band"}
    row = _apply(dict(rejected), {"Emission_angle": 1.0})
    assert row["rejected_by"] == rejected["rejected_by"]
    assert row["admissible"] is False
    assert "emission_deg_used" not in row


def test_no_added_filter_can_make_an_inadmissible_row_admissible():
    rejected = {"pdsid": "nac.m1111111111lc", "admissible": False,
                "rejected_by": "filter 3: tile would run off the frame"}
    assert _apply(dict(rejected), {"Emission_angle": 1.0})["admissible"] is False


# --------------------------------------------------------------------------
# funnel accounting
# --------------------------------------------------------------------------


def test_every_candidate_is_accounted_for_in_the_funnel():
    rows = [
        _apply(_admissible_row("nac.m1000000001lc"), {"Emission_angle": 1.5}),
        _apply(_admissible_row("nac.m1000000002rc"), {"Emission_angle": 1.5}),
        _apply(_admissible_row("nac.m1000000003lc"), {"Emission_angle": 30.0}),
        {"pdsid": "nac.m1000000004lc", "admissible": False,
         "rejected_by": "filter 5: incidence outside the band"},
    ]
    funnel: dict[str, int] = {}
    for r in rows:
        key = ("ADMISSIBLE" if r["admissible"]
               else r["rejected_by"].split(":")[0])
        funnel[key] = funnel.get(key, 0) + 1
    assert sum(funnel.values()) == len(rows)
    assert funnel == {"ADMISSIBLE": 1, "filter H7": 1, "filter H6": 1,
                      "filter 5": 1}
