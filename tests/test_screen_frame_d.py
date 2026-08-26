"""Coverage for the REAL-DATA-04 frame-D screen, ``scripts/screen_frame_d.py``.

The screen picks the frame that the whole stage's causal conclusion rests on.
Two of its decisions are the ones worth defending in a test:

* **the orientation signature** (hard filter 1c). Its job is to reject a frame
  whose tile would be rotated 180 degrees relative to A and B, because such an
  edge could fail for illumination, for frame identity, *or* for orientation
  assignment -- and orientation assignment is this project's own open question
  (EXP-004, pre-registered, not started). Getting the signature backwards would
  admit exactly the frames it exists to exclude, and the stage would still look
  like it had run correctly. E-032 is the archive evidence behind it: no
  ``LRO_FLIGHT_DIRECTION`` rule predicts the along-track sense.
* **the ODE ring reader**, which must refuse a degenerate ring rather than
  build a frame from three distinct points and a repeat.

No network access. Rings and corner sets are constructed by hand.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location(
    "screen_frame_d", ROOT / "scripts" / "screen_frame_d.py")
sfd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sfd)

from siim.ingest.footprint import FrameCorners  # noqa: E402

#: The signature every REAL-DATA-03 frame has: line 0 at MINIMUM latitude
#: (latitude increases down the image) and longitude DECREASING with sample.
INCUMBENT = (1, -1)


def _corners(*, along: int, cross: int, lines: int = 52224,
             samples: int = 5064) -> FrameCorners:
    """A frame with a chosen orientation signature.

    ``along = +1`` puts line 0 at minimum latitude; ``cross = +1`` makes
    longitude increase with sample.
    """
    lat_top, lat_bot = (19.0, 21.0) if along == 1 else (21.0, 19.0)
    lon_left, lon_right = (22.0, 22.2) if cross == 1 else (22.2, 22.0)
    return FrameCorners(
        upper_left=(lon_left, lat_top), upper_right=(lon_right, lat_top),
        lower_left=(lon_left, lat_bot), lower_right=(lon_right, lat_bot),
        lines=lines, samples=samples)


# --------------------------------------------------------------------------
# orientation_signature
# --------------------------------------------------------------------------


@pytest.mark.parametrize("along", [1, -1])
@pytest.mark.parametrize("cross", [1, -1])
def test_the_signature_reports_the_orientation_it_was_built_with(along, cross):
    assert sfd.orientation_signature(_corners(along=along, cross=cross)) == (
        along, cross)


def test_the_incumbent_orientation_is_line_zero_at_minimum_latitude():
    """Guards the sign convention itself. If this flips, filter 1c admits
    precisely the 180-degree-rotated frames it exists to reject, and every
    downstream number still looks reasonable."""
    a = FrameCorners(upper_left=(22.08, 19.39), upper_right=(21.93, 19.40),
                     lower_left=(22.19, 21.06), lower_right=(22.02, 21.07),
                     lines=52224, samples=5064)
    assert sfd.orientation_signature(a) == INCUMBENT


def test_a_frame_rotated_180_degrees_does_not_match_the_incumbents():
    """The real rejected candidate, ``nac.m1343417565rc``: line 0 at MAXIMUM
    latitude and longitude INCREASING with sample (E-032)."""
    d = FrameCorners(upper_left=(21.95, 21.53), upper_right=(22.11, 21.54),
                     lower_left=(22.02, 20.52), lower_right=(22.18, 20.53),
                     lines=30720, samples=5064)
    sig = sfd.orientation_signature(d)
    assert sig == (-1, 1)
    assert sig != INCUMBENT


def test_a_frame_flipped_on_one_axis_only_is_also_rejected():
    """A half-flip is not a rotation and is not repaired by one either; both
    axes must agree or the tiles are mirrored rather than rotated."""
    for sig in ((-1, -1), (1, 1)):
        assert sfd.orientation_signature(
            _corners(along=sig[0], cross=sig[1])) != INCUMBENT


def test_the_signature_reads_both_rows_and_both_columns():
    """A frame is a quadrilateral, not a rectangle. Reading only ``upper_left``
    and ``upper_right`` would misclassify a skewed frame whose corner pair
    happens to tie, so the signature averages each row and each column."""
    skewed = FrameCorners(
        upper_left=(22.10, 19.40), upper_right=(22.10, 19.30),
        lower_left=(22.19, 21.06), lower_right=(21.99, 21.07),
        lines=52224, samples=5064)
    assert skewed.upper_left[0] == skewed.upper_right[0]   # the tie
    assert sfd.orientation_signature(skewed) == INCUMBENT


# --------------------------------------------------------------------------
# corners_from_ode_ring
# --------------------------------------------------------------------------


def _ring(pts) -> dict:
    body = ", ".join(f"{lon} {lat}" for lon, lat in pts)
    return {"Footprint_geometry": f"POLYGON (({body}))"}


def test_the_ode_ring_is_read_in_the_order_real_data_02_decoded():
    """(UR, LR, LL, UL) -- REAL-DATA-02 section 6.3. An inference, used only to
    rank candidates, but it must at least be applied as documented."""
    ur, lr, ll, ul = (22.2, 19.0), (22.3, 21.0), (22.0, 21.0), (21.9, 19.0)
    c = sfd.corners_from_ode_ring(_ring([ur, lr, ll, ul, ur]), 52224, 5064)
    assert c is not None
    assert (c.upper_right, c.lower_right) == (ur, lr)
    assert (c.lower_left, c.upper_left) == (ll, ul)


def test_a_closing_vertex_is_dropped_rather_than_treated_as_a_fifth_corner():
    pts = [(22.2, 19.0), (22.3, 21.0), (22.0, 21.0), (21.9, 19.0)]
    assert sfd.corners_from_ode_ring(_ring(pts + [pts[0]]), 52224, 5064) \
        == sfd.corners_from_ode_ring(_ring(pts), 52224, 5064)


def test_a_ring_with_a_repeated_vertex_is_refused_not_silently_accepted():
    pts = [(22.2, 19.0), (22.2, 19.0), (22.0, 21.0), (21.9, 19.0)]
    assert sfd.corners_from_ode_ring(_ring(pts), 52224, 5064) is None


def test_a_missing_or_empty_footprint_is_refused():
    assert sfd.corners_from_ode_ring({}, 52224, 5064) is None
    assert sfd.corners_from_ode_ring(
        {"Footprint_geometry": "MULTIPOLYGON EMPTY"}, 52224, 5064) is None
