"""Tests for :mod:`siim.ingest.footprint`.

The module's whole purpose is to produce a number that will be quoted as
scientific evidence about whether two real tiles share ground. So the tests
here are weighted towards the ways such a number can be *confidently wrong*
rather than towards raising errors:

* an intersection routine that returns a plausible area for polygons that do
  not touch,
* an area that changes when the same shape is described in the other winding
  order,
* a projection that silently compares two shapes on different planes,
* a corner convention that mirrors the tile along-track without failing,
* a classifier that upgrades an uncertain interval to a confident answer.
"""

from __future__ import annotations

import numpy as np
import pytest

from siim.ingest.footprint import (
    MOON_RADIUS_KM,
    OVERLAP_CONFIRMED,
    OVERLAP_INSUFFICIENT,
    OVERLAP_UNKNOWN,
    FrameCorners,
    LocalPlane,
    classify_overlap,
    convex_clip,
    is_convex,
    north_azimuth_agreement,
    north_azimuth_discriminating_power,
    overlap_metrics,
    polygon_area_km2,
    predicted_correspondences,
    shared_tile_target,
    tile_admissible_polygon,
    TileWindow,
)

UNIT = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])


def _frame(**kw) -> FrameCorners:
    """A north-up frame: UPPER at higher latitude, LEFT at lower longitude."""
    base = dict(
        upper_left=(10.0, 21.0),
        upper_right=(10.2, 21.0),
        lower_left=(10.0, 20.0),
        lower_right=(10.2, 20.0),
        lines=1001,
        samples=101,
    )
    base.update(kw)
    return FrameCorners(**base)


# --------------------------------------------------------------------------
# polygon area
# --------------------------------------------------------------------------

def test_unit_square_has_unit_area():
    assert polygon_area_km2(UNIT) == pytest.approx(1.0)


def test_area_is_independent_of_winding_order():
    assert polygon_area_km2(UNIT[::-1]) == pytest.approx(polygon_area_km2(UNIT))


def test_area_of_a_degenerate_ring_is_zero_not_an_error():
    assert polygon_area_km2(np.zeros((0, 2))) == 0.0
    assert polygon_area_km2(np.array([[0.0, 0.0], [1.0, 1.0]])) == 0.0


def test_area_of_a_known_triangle():
    tri = np.array([[0.0, 0.0], [4.0, 0.0], [0.0, 3.0]])
    assert polygon_area_km2(tri) == pytest.approx(6.0)


# --------------------------------------------------------------------------
# convexity and clipping
# --------------------------------------------------------------------------

def test_square_is_convex_in_both_windings():
    assert is_convex(UNIT)
    assert is_convex(UNIT[::-1])


def test_l_shape_is_not_convex():
    ell = np.array([[0, 0], [2, 0], [2, 1], [1, 1], [1, 2], [0, 2]], float)
    assert not is_convex(ell)


def test_clipping_by_a_concave_polygon_raises_rather_than_returning_a_wrong_area():
    # Sutherland-Hodgman does not fail on a concave clip, it returns a
    # degenerate polygon with a plausible area. That number would be quoted.
    ell = np.array([[0, 0], [2, 0], [2, 1], [1, 1], [1, 2], [0, 2]], float)
    with pytest.raises(ValueError, match="convex"):
        convex_clip(UNIT, ell)


def test_identical_squares_intersect_in_their_whole_area():
    assert polygon_area_km2(convex_clip(UNIT, UNIT)) == pytest.approx(1.0)


def test_half_offset_squares_intersect_in_exactly_half():
    other = UNIT + np.array([0.5, 0.0])
    assert polygon_area_km2(convex_clip(UNIT, other)) == pytest.approx(0.5)


def test_quarter_overlap_in_both_axes():
    other = UNIT + np.array([0.5, 0.5])
    assert polygon_area_km2(convex_clip(UNIT, other)) == pytest.approx(0.25)


def test_disjoint_squares_intersect_in_nothing():
    other = UNIT + np.array([5.0, 0.0])
    inter = convex_clip(UNIT, other)
    assert len(inter) == 0
    assert polygon_area_km2(inter) == 0.0


def test_edge_touching_squares_have_zero_area_not_a_sliver():
    other = UNIT + np.array([1.0, 0.0])
    assert polygon_area_km2(convex_clip(UNIT, other)) == pytest.approx(0.0, abs=1e-12)


def test_clip_is_symmetric_in_area():
    a = UNIT * 2.0
    b = UNIT + np.array([0.7, 0.3])
    assert polygon_area_km2(convex_clip(a, b)) == pytest.approx(
        polygon_area_km2(convex_clip(b, a)))


def test_contained_square_intersects_in_its_own_area():
    inner = UNIT * 0.25 + np.array([0.3, 0.3])
    assert polygon_area_km2(convex_clip(inner, UNIT)) == pytest.approx(0.0625)


def test_clip_result_is_independent_of_input_winding():
    b = UNIT + np.array([0.4, 0.4])
    forward = polygon_area_km2(convex_clip(UNIT, b))
    reversed_ = polygon_area_km2(convex_clip(UNIT[::-1], b[::-1]))
    assert forward == pytest.approx(reversed_)


# --------------------------------------------------------------------------
# projection
# --------------------------------------------------------------------------

def test_one_degree_of_latitude_is_the_expected_arc():
    plane = LocalPlane(lon0=10.0, lat0=20.0)
    xy = plane.to_km(np.array([[10.0, 21.0]]))
    assert xy[0, 1] == pytest.approx(np.pi / 180.0 * MOON_RADIUS_KM, rel=1e-12)
    assert xy[0, 0] == pytest.approx(0.0, abs=1e-12)


def test_longitude_is_compressed_by_the_cosine_of_latitude():
    plane = LocalPlane(lon0=10.0, lat0=60.0)
    xy = plane.to_km(np.array([[11.0, 60.0]]))
    expected = np.pi / 180.0 * MOON_RADIUS_KM * np.cos(np.deg2rad(60.0))
    assert xy[0, 0] == pytest.approx(expected, rel=1e-12)


def test_the_reference_point_maps_to_the_origin():
    plane = LocalPlane(lon0=-3.25, lat0=44.5)
    xy = plane.to_km(np.array([[-3.25, 44.5]]))
    assert xy[0, 0] == pytest.approx(0.0, abs=1e-12)
    assert xy[0, 1] == pytest.approx(0.0, abs=1e-12)


def test_centred_on_uses_every_polygon_so_both_shapes_share_one_plane():
    a = np.array([[10.0, 20.0], [10.1, 20.0]])
    b = np.array([[12.0, 22.0], [12.1, 22.0]])
    plane = LocalPlane.centred_on([a, b])
    assert 10.0 < plane.lon0 < 12.1
    assert 20.0 < plane.lat0 < 22.0


def test_to_km_rejects_something_that_is_not_lon_lat_pairs():
    with pytest.raises(ValueError, match=r"\(N, 2\)"):
        LocalPlane(0.0, 0.0).to_km(np.zeros((3, 3)))


# --------------------------------------------------------------------------
# FrameCorners: the bilinear map
# --------------------------------------------------------------------------

def test_corners_map_back_to_themselves():
    f = _frame()
    assert f.lonlat_at(0, 0) == pytest.approx(f.upper_left)
    assert f.lonlat_at(0, f.samples - 1) == pytest.approx(f.upper_right)
    assert f.lonlat_at(f.lines - 1, 0) == pytest.approx(f.lower_left)
    assert f.lonlat_at(f.lines - 1, f.samples - 1) == pytest.approx(f.lower_right)


def test_the_frame_centre_is_the_mean_of_the_four_corners():
    f = _frame()
    mid = f.lonlat_at((f.lines - 1) / 2, (f.samples - 1) / 2)
    expected = np.mean([f.upper_left, f.upper_right,
                        f.lower_left, f.lower_right], axis=0)
    assert mid == pytest.approx(tuple(expected))


def test_line_zero_is_the_upper_edge_so_latitude_decreases_with_line():
    f = _frame()
    assert f.lonlat_at(0, 50)[1] > f.lonlat_at(f.lines - 1, 50)[1]


def test_extrapolating_outside_the_frame_raises_instead_of_inventing_a_coordinate():
    f = _frame()
    with pytest.raises(ValueError, match="line"):
        f.lonlat_at(f.lines, 0)
    with pytest.raises(ValueError, match="sample"):
        f.lonlat_at(0, f.samples)
    with pytest.raises(ValueError, match="line"):
        f.lonlat_at(-1, 0)


def test_a_frame_smaller_than_two_pixels_is_rejected():
    with pytest.raises(ValueError, match="2x2"):
        _frame(lines=1)


def test_non_finite_corners_are_rejected():
    with pytest.raises(ValueError, match="finite"):
        _frame(upper_left=(np.nan, 21.0))


def test_tile_polygon_uses_the_last_included_pixel_not_the_exclusive_end():
    f = _frame()
    ring = f.tile_polygon(line0=0, n_lines=1, sample0=0, n_samples=1)
    assert ring == pytest.approx(np.array([f.upper_left] * 4))


def test_a_whole_frame_tile_polygon_is_the_frame():
    f = _frame()
    ring = f.tile_polygon(line0=0, n_lines=f.lines,
                          sample0=0, n_samples=f.samples)
    assert ring == pytest.approx(np.array([f.upper_left, f.upper_right,
                                           f.lower_right, f.lower_left]))


def test_tile_polygon_rejects_an_empty_window():
    with pytest.raises(ValueError, match="1x1"):
        _frame().tile_polygon(line0=0, n_lines=0, sample0=0, n_samples=10)


def test_tile_polygon_refuses_a_window_running_off_the_frame():
    f = _frame()
    with pytest.raises(ValueError):
        f.tile_polygon(line0=f.lines - 10, n_lines=100,
                       sample0=0, n_samples=10)


# --------------------------------------------------------------------------
# the two naming ambiguities
# --------------------------------------------------------------------------

def test_along_track_mirroring_moves_a_tile_by_the_length_of_the_frame():
    """The H1/H2 ambiguity is not a rounding-scale concern: reading the corner
    names the other way round relocates a small tile by nearly a whole frame,
    which is why REAL-DATA-01 could not resolve it and why it is reported."""
    f = _frame()
    a = f.tile_polygon(line0=0, n_lines=10, sample0=0, n_samples=10)
    b = f.mirrored_along_track().tile_polygon(
        line0=0, n_lines=10, sample0=0, n_samples=10)
    assert abs(a[:, 1].mean() - b[:, 1].mean()) > 0.9


def test_mirroring_along_track_twice_is_the_identity():
    f = _frame()
    g = f.mirrored_along_track().mirrored_along_track()
    assert (g.upper_left, g.upper_right, g.lower_left, g.lower_right) == (
        f.upper_left, f.upper_right, f.lower_left, f.lower_right)


def test_cross_track_mirroring_leaves_a_sample_centred_tile_exactly_where_it_was():
    """The claim that the sample-direction ambiguity is harmless, tested.

    It holds only because the acquisition centred its sample window; the next
    test shows it fails the moment the window is off-centre.
    """
    f = _frame(samples=101)
    n = 21
    sample0 = (f.samples - n) // 2
    a = f.tile_polygon(line0=100, n_lines=50, sample0=sample0, n_samples=n)
    b = f.mirrored_cross_track().tile_polygon(
        line0=100, n_lines=50, sample0=sample0, n_samples=n)
    plane = LocalPlane.centred_on([a, b])
    m = overlap_metrics(plane.to_km(a), plane.to_km(b))
    assert m.min_fraction == pytest.approx(1.0, abs=1e-9)


def test_cross_track_mirroring_does_move_an_off_centre_tile():
    f = _frame(samples=101)
    a = f.tile_polygon(line0=100, n_lines=50, sample0=0, n_samples=21)
    b = f.mirrored_cross_track().tile_polygon(
        line0=100, n_lines=50, sample0=0, n_samples=21)
    plane = LocalPlane.centred_on([a, b])
    m = overlap_metrics(plane.to_km(a), plane.to_km(b))
    assert m.area_intersection_km2 == pytest.approx(0.0, abs=1e-9)


# --------------------------------------------------------------------------
# overlap metrics
# --------------------------------------------------------------------------

def test_a_tile_overlaps_itself_completely():
    f = _frame()
    ring = f.tile_polygon(line0=200, n_lines=100, sample0=10, n_samples=50)
    plane = LocalPlane.centred_on([ring])
    m = overlap_metrics(plane.to_km(ring), plane.to_km(ring))
    assert m.iou == pytest.approx(1.0)
    assert m.fraction_of_a == pytest.approx(1.0)
    assert m.fraction_of_b == pytest.approx(1.0)
    assert m.min_fraction == pytest.approx(1.0)


def test_tiles_from_opposite_ends_of_a_frame_share_nothing():
    f = _frame()
    a = f.tile_polygon(line0=0, n_lines=100, sample0=0, n_samples=50)
    b = f.tile_polygon(line0=f.lines - 100, n_lines=100,
                       sample0=0, n_samples=50)
    plane = LocalPlane.centred_on([a, b])
    m = overlap_metrics(plane.to_km(a), plane.to_km(b))
    assert m.area_intersection_km2 == pytest.approx(0.0, abs=1e-9)
    assert m.iou == 0.0
    assert m.min_fraction == 0.0


def test_half_overlapping_tiles_report_a_half_and_an_iou_of_one_third():
    f = _frame()
    a = f.tile_polygon(line0=0, n_lines=100, sample0=0, n_samples=50)
    b = f.tile_polygon(line0=50, n_lines=100, sample0=0, n_samples=50)
    plane = LocalPlane.centred_on([a, b])
    m = overlap_metrics(plane.to_km(a), plane.to_km(b))
    assert m.fraction_of_a == pytest.approx(0.5, rel=0.02)
    assert m.fraction_of_b == pytest.approx(0.5, rel=0.02)
    assert m.iou == pytest.approx(1.0 / 3.0, rel=0.02)


def test_min_fraction_reports_the_worse_covered_tile_not_the_average():
    """A big tile containing a small one is 100% covered from the small tile's
    point of view and barely covered from the big one's. The binding number is
    the small one -- but the *matcher* is limited by the big one, so
    ``min_fraction`` must be the small value, not the large."""
    f = _frame()
    big = f.tile_polygon(line0=0, n_lines=400, sample0=0, n_samples=100)
    small = f.tile_polygon(line0=100, n_lines=100, sample0=20, n_samples=50)
    plane = LocalPlane.centred_on([big, small])
    m = overlap_metrics(plane.to_km(big), plane.to_km(small))
    assert m.fraction_of_b == pytest.approx(1.0, rel=1e-6)
    assert m.fraction_of_a < 0.2
    assert m.min_fraction == m.fraction_of_a


def test_metrics_of_empty_polygons_are_zero_not_nan():
    m = overlap_metrics(np.zeros((0, 2)), np.zeros((0, 2)))
    assert m.iou == 0.0
    assert m.fraction_of_a == 0.0
    assert m.min_fraction == 0.0


def test_as_dict_carries_every_reported_number():
    f = _frame()
    ring = f.tile_polygon(line0=0, n_lines=100, sample0=0, n_samples=50)
    plane = LocalPlane.centred_on([ring])
    d = overlap_metrics(plane.to_km(ring), plane.to_km(ring)).as_dict()
    assert set(d) == {"area_a_km2", "area_b_km2", "area_intersection_km2",
                      "iou", "fraction_of_a", "fraction_of_b", "min_fraction"}


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------

def test_a_confidently_high_interval_is_confirmed():
    cls, why = classify_overlap(0.60, 0.75)
    assert cls == OVERLAP_CONFIRMED
    assert "pessimistic" in why


def test_a_confidently_low_interval_is_insufficient():
    cls, why = classify_overlap(0.00, 0.05)
    assert cls == OVERLAP_INSUFFICIENT
    assert "optimistic" in why


def test_an_interval_straddling_the_confirm_threshold_is_unknown():
    cls, _ = classify_overlap(0.45, 0.70)
    assert cls == OVERLAP_UNKNOWN


def test_an_interval_straddling_the_insufficient_threshold_is_unknown():
    cls, _ = classify_overlap(0.05, 0.30)
    assert cls == OVERLAP_UNKNOWN


def test_the_middle_band_is_unknown_rather_than_rounded_to_the_nearer_verdict():
    cls, _ = classify_overlap(0.30, 0.35)
    assert cls == OVERLAP_UNKNOWN


def test_a_point_estimate_at_the_threshold_confirms_but_one_below_does_not():
    assert classify_overlap(0.50, 0.50)[0] == OVERLAP_CONFIRMED
    assert classify_overlap(0.4999, 0.4999)[0] == OVERLAP_UNKNOWN


def test_non_finite_bounds_are_unknown_not_an_exception():
    cls, why = classify_overlap(float("nan"), float("nan"))
    assert cls == OVERLAP_UNKNOWN
    assert "not finite" in why


def test_an_inverted_interval_is_a_caller_error():
    with pytest.raises(ValueError, match="inverted"):
        classify_overlap(0.7, 0.2)


def test_thresholds_are_adjustable_but_default_to_the_preregistered_values():
    assert classify_overlap(0.25, 0.25, confirm_at=0.2)[0] == OVERLAP_CONFIRMED
    assert classify_overlap(0.25, 0.25)[0] == OVERLAP_UNKNOWN


# --------------------------------------------------------------------------
# the NORTH_AZIMUTH cross-check
# --------------------------------------------------------------------------

def test_north_azimuth_270_agrees_with_a_north_up_frame():
    r = north_azimuth_agreement(_frame(), 270.0)
    assert r["predicted_upper_is_northward"] is True
    assert r["observed_upper_is_northward"] is True
    assert r["agrees"] is True


def test_north_azimuth_90_disagrees_with_a_north_up_frame():
    r = north_azimuth_agreement(_frame(), 90.0)
    assert r["predicted_upper_is_northward"] is False
    assert r["agrees"] is False


def test_north_azimuth_90_agrees_with_a_south_up_frame():
    r = north_azimuth_agreement(_frame().mirrored_along_track(), 90.0)
    assert r["agrees"] is True


def test_a_cross_track_north_azimuth_has_no_power_and_says_so():
    for na in (0.0, 180.0, 3.0, 357.0):
        r = north_azimuth_agreement(_frame(), na)
        assert r["agrees"] is None, na
        assert "no usable sign" in r["note"] or "discriminating power" in r["note"]


def test_a_missing_north_azimuth_is_unchecked_rather_than_failed():
    r = north_azimuth_agreement(_frame(), None)
    assert r["agrees"] is None
    assert "unchecked" in r["note"]


def test_north_azimuth_is_read_modulo_360():
    assert north_azimuth_agreement(_frame(), 270.0)["agrees"] is (
        north_azimuth_agreement(_frame(), 630.0)["agrees"])


# --------------------------------------------------------------------------
# the bilinear inverse
# --------------------------------------------------------------------------

def _skewed_frame() -> FrameCorners:
    """A frame with a genuinely skewed quad, so the inverse is not trivially
    separable and a Newton step actually has to couple the two axes."""
    return FrameCorners(
        upper_left=(10.00, 21.00),
        upper_right=(10.20, 21.02),
        lower_left=(10.01, 20.00),
        lower_right=(10.22, 20.03),
        lines=1001,
        samples=101,
    )


@pytest.mark.parametrize("line,sample", [
    (0, 0), (0, 100), (1000, 0), (1000, 100), (500, 50), (123, 77), (1, 99),
])
def test_pixel_at_inverts_lonlat_at_exactly(line, sample):
    f = _skewed_frame()
    lon, lat = f.lonlat_at(line, sample)
    back = f.pixel_at(lon, lat)
    assert back[0] == pytest.approx(line, abs=1e-6)
    assert back[1] == pytest.approx(sample, abs=1e-6)


def test_pixel_at_refuses_a_point_outside_the_frame_rather_than_clamping():
    """Clamping would return the nearest edge pixel, which is a plausible
    integer that hides a real error in whatever asked for it."""
    f = _skewed_frame()
    with pytest.raises(ValueError, match="outside the frame"):
        f.pixel_at(9.0, 21.0)
    with pytest.raises(ValueError, match="outside the frame"):
        f.pixel_at(10.1, 25.0)


def test_pixel_at_survives_a_frame_that_is_an_exact_parallelogram():
    """The closed-form bilinear inverse degenerates here; Newton does not."""
    f = FrameCorners((10.0, 21.0), (10.2, 21.0), (10.0, 20.0), (10.2, 20.0),
                     1001, 101)
    lon, lat = f.lonlat_at(321, 43)
    assert f.pixel_at(lon, lat) == pytest.approx((321.0, 43.0), abs=1e-6)


def test_pixel_at_rejects_a_quad_collapsed_in_the_cross_track_direction():
    """A frame with zero width has no invertible map: every sample lands on the
    same ground point. The Jacobian is singular and the solve must say so
    rather than returning whatever ``lstsq`` would have volunteered."""
    f = FrameCorners((10.0, 21.0), (10.0, 21.0), (10.0, 20.0), (10.0, 20.0),
                     1001, 101)
    with pytest.raises(ValueError, match="degenerate"):
        f.pixel_at(10.5, 20.5)


def test_frame_polygon_is_the_whole_frame_tile_polygon():
    f = _skewed_frame()
    assert f.frame_polygon() == pytest.approx(
        f.tile_polygon(line0=0, n_lines=f.lines,
                       sample0=0, n_samples=f.samples))


def test_a_window_centred_by_pixel_at_lands_on_the_requested_ground_point():
    """The property the geometry-driven re-selection of REAL-DATA-03 rests on:
    ask for a ground point, get a tile whose centre is that point."""
    f = _skewed_frame()
    target = f.lonlat_at(400, 60)
    line, sample = f.pixel_at(*target)
    # Odd sizes, so the tile centre is an actual pixel and the assertion can
    # be exact. With an even size the centre falls between pixels and half a
    # pixel of offset (0.45 m at NAC scale) is unavoidable.
    n_lines, n_samples = 101, 21
    # The ring spans the LAST INCLUDED pixel, so a window centred on `line`
    # starts at `line - (n_lines - 1) / 2`, not `line - n_lines / 2`. The
    # difference is half a pixel; at 0.9 m/pixel that is 45 cm, and it is
    # pinned here so the geometry-driven re-selection cannot drift by it.
    ring = f.tile_polygon(
        line0=int(round(line - (n_lines - 1) / 2)), n_lines=n_lines,
        sample0=int(round(sample - (n_samples - 1) / 2)), n_samples=n_samples)
    centre = ring.mean(axis=0)
    assert centre[0] == pytest.approx(target[0], abs=2e-5)
    assert centre[1] == pytest.approx(target[1], abs=2e-5)


# --------------------------------------------------------------------------
# NORTH_AZIMUTH: does the column have any power over this frame set?
# --------------------------------------------------------------------------

def test_a_set_whose_azimuths_track_the_line_direction_has_power():
    frames = {
        "north_up_a": (_frame(), 270.0),
        "north_up_b": (_frame(), 272.0),
        "south_up_a": (_frame().mirrored_along_track(), 90.0),
        "south_up_b": (_frame().mirrored_along_track(), 88.0),
    }
    r = north_azimuth_discriminating_power(frames)
    assert r["has_power"] is True
    assert r["group_separation_deg"] == pytest.approx(178.0, abs=1.0)


def test_a_constant_azimuth_across_a_split_set_has_no_power():
    """The real case: NORTH_AZIMUTH sits near 270 for every LROC CDR because
    the column describes the map-projected RDR, so it says nothing about which
    image line is at the top of the CDR."""
    frames = {
        "north_up_a": (_frame(), 268.59),
        "north_up_b": (_frame(), 267.72),
        "south_up_a": (_frame().mirrored_along_track(), 274.77),
        "south_up_b": (_frame().mirrored_along_track(), 272.94),
    }
    r = north_azimuth_discriminating_power(frames)
    assert r["has_power"] is False
    assert "does not track" in r["reason"]


def test_a_set_with_only_one_line_direction_cannot_show_anything():
    frames = {"a": (_frame(), 270.0), "b": (_frame(), 90.0)}
    r = north_azimuth_discriminating_power(frames)
    assert r["has_power"] is False
    assert "same line direction" in r["reason"]


def test_frames_without_an_azimuth_are_skipped_not_counted():
    frames = {
        "a": (_frame(), None),
        "b": (_frame(), 270.0),
        "c": (_frame().mirrored_along_track(), 90.0),
    }
    r = north_azimuth_discriminating_power(frames)
    assert r["n_frames_with_azimuth"] == 2


# --------------------------------------------------------------------------
# TileWindow: tile <-> frame coordinates, including decimation
# --------------------------------------------------------------------------

def test_tile_window_round_trips_frame_coordinates():
    w = TileWindow(line0=17955, sample0=1811, n_lines=4096, n_samples=2048,
                   decimation=2)
    for row, col in ((0, 0), (10.5, 3.25), (2047, 1023)):
        line, sample = w.to_frame(row, col)
        assert w.from_frame(line, sample) == pytest.approx((row, col))


def test_decimated_pixel_sits_at_the_centre_of_its_block_not_its_corner():
    """A decimated pixel is the MEAN of a k x k block, so it sits at the
    block's centre. Treating it as the corner shifts every predicted
    correspondence by (k-1)/2 original pixels — half a pixel at k=2, and the
    kind of offset that survives review because nothing looks wrong."""
    w = TileWindow(line0=100, sample0=200, n_lines=8, n_samples=8, decimation=2)
    assert w.to_frame(0, 0) == pytest.approx((100.5, 200.5))
    assert w.to_frame(1, 1) == pytest.approx((102.5, 202.5))


def test_undecimated_tile_maps_pixel_for_pixel():
    w = TileWindow(line0=100, sample0=200, n_lines=8, n_samples=8)
    assert w.to_frame(0, 0) == pytest.approx((100.0, 200.0))
    assert w.to_frame(3, 5) == pytest.approx((103.0, 205.0))


def test_tile_window_shape_is_after_decimation():
    assert TileWindow(0, 0, 4096, 2048, 2).shape == (2048, 1024)
    assert TileWindow(0, 0, 4096, 2048).shape == (4096, 2048)


def test_a_non_positive_decimation_is_rejected():
    with pytest.raises(ValueError, match="decimation"):
        TileWindow(0, 0, 10, 10, 0)


# --------------------------------------------------------------------------
# predicted_correspondences: the matcher-independent transform prediction
# --------------------------------------------------------------------------

def test_a_tile_predicted_against_itself_is_the_identity():
    f = _skewed_frame()
    w = TileWindow(100, 20, 400, 40, 1)
    src, dst = predicted_correspondences(f, w, f, w, grid=5)
    assert len(src) == 25
    assert dst == pytest.approx(src, abs=1e-6)


def test_a_shifted_window_predicts_exactly_that_shift():
    """The same frame, two windows offset by a known number of pixels: the
    predicted correspondence must reproduce the offset, because both windows
    are read through one ground map."""
    f = _skewed_frame()
    a = TileWindow(100, 20, 400, 40, 1)
    b = TileWindow(130, 25, 400, 40, 1)
    src, dst = predicted_correspondences(f, a, f, b, grid=5)
    assert (dst[:, 0] - src[:, 0]) == pytest.approx(-5.0, abs=1e-6)   # x = sample
    assert (dst[:, 1] - src[:, 1]) == pytest.approx(-30.0, abs=1e-6)  # y = line


def test_points_are_x_y_not_line_sample():
    """The pipeline's points are (x, y) == (column, row). Predicting in the
    other order transposes every correspondence while staying plausible."""
    f = _skewed_frame()
    w = TileWindow(0, 0, 100, 40, 1)
    src, _ = predicted_correspondences(f, w, f, w, grid=3)
    # x spans the SAMPLE extent (40 -> 0..39), y the LINE extent (100 -> 0..99)
    assert src[:, 0].max() == pytest.approx(39.0)
    assert src[:, 1].max() == pytest.approx(99.0)


def test_decimation_halves_the_predicted_coordinates():
    f = _skewed_frame()
    full = TileWindow(100, 20, 400, 40, 1)
    dec = TileWindow(100, 20, 400, 40, 2)
    src_f, _ = predicted_correspondences(f, full, f, full, grid=3)
    src_d, _ = predicted_correspondences(f, dec, f, dec, grid=3)
    assert src_f[:, 0].max() == pytest.approx(39.0)
    assert src_d[:, 0].max() == pytest.approx(19.0)


def test_a_predicted_scale_matches_two_frames_of_different_pixel_size():
    """Two frames covering the same ground with different sampling must predict
    a scale equal to the ratio of their samplings — the property the
    SCALED_PIXEL cross-check rests on."""
    span_lon, span_lat = 0.2, 1.0
    coarse = FrameCorners((10.0, 21.0), (10.0 + span_lon, 21.0),
                          (10.0, 21.0 - span_lat),
                          (10.0 + span_lon, 21.0 - span_lat), 1001, 101)
    fine = FrameCorners((10.0, 21.0), (10.0 + span_lon, 21.0),
                        (10.0, 21.0 - span_lat),
                        (10.0 + span_lon, 21.0 - span_lat), 2001, 201)
    wa = TileWindow(400, 40, 200, 20, 1)
    wb = TileWindow(800, 80, 400, 40, 1)
    src, dst = predicted_correspondences(coarse, wa, fine, wb, grid=4)
    # A coarse pixel is twice a fine pixel, so the map must stretch by ~2.
    dx = (dst[:, 0].max() - dst[:, 0].min()) / (src[:, 0].max() - src[:, 0].min())
    dy = (dst[:, 1].max() - dst[:, 1].min()) / (src[:, 1].max() - src[:, 1].min())
    assert dx == pytest.approx(2.0, rel=0.01)
    assert dy == pytest.approx(2.0, rel=0.01)


def test_points_outside_the_other_frame_are_dropped_not_extrapolated():
    """Extrapolating a bilinear surface returns a plausible coordinate for a
    pixel that does not exist, which would then be fitted to."""
    f = _frame()
    g = FrameCorners((30.0, 21.0), (30.2, 21.0), (30.0, 20.0), (30.2, 20.0),
                     1001, 101)   # a frame on entirely different ground
    w = TileWindow(100, 20, 200, 20, 1)
    src, dst = predicted_correspondences(f, w, g, w, grid=4)
    assert len(src) == 0 and len(dst) == 0


def test_a_grid_smaller_than_two_is_rejected():
    f = _frame()
    w = TileWindow(0, 0, 10, 10, 1)
    with pytest.raises(ValueError, match="grid"):
        predicted_correspondences(f, w, f, w, grid=1)


def test_prediction_reads_no_image_data():
    """Stated as a property of the signature: the function takes frame corners
    and integer windows, and there is nowhere for a pixel to enter."""
    import inspect
    params = set(inspect.signature(predicted_correspondences).parameters)
    assert params == {"corners_a", "window_a", "corners_b", "window_b", "grid"}


# --------------------------------------------------------------------------
# tile_admissible_polygon / shared_tile_target (REAL-DATA-04)
#
# These decide where a real tile gets cut. The failure they exist to prevent is
# silent: a target point that sits inside every frame's footprint but within
# half a tile of an edge, so the window clamps, the tile slides off the ground
# point it was supposed to sit on, and every overlap number downstream is
# computed for a tile that is not where the manifest says it is.
# --------------------------------------------------------------------------


def test_the_admissible_region_is_inset_by_half_a_tile_on_each_axis():
    f = _frame(lines=1001, samples=101)
    poly = tile_admissible_polygon(f, n_lines=101, n_samples=21)
    # corners of the pixel rectangle [50, 950] x [10, 90]
    assert np.allclose(poly[0], f.lonlat_at(50.0, 10.0))
    assert np.allclose(poly[1], f.lonlat_at(50.0, 90.0))
    assert np.allclose(poly[2], f.lonlat_at(950.0, 90.0))
    assert np.allclose(poly[3], f.lonlat_at(950.0, 10.0))


def test_a_1x1_tile_makes_the_admissible_region_the_whole_frame():
    f = _frame()
    assert np.allclose(tile_admissible_polygon(f, n_lines=1, n_samples=1),
                       f.frame_polygon())


def test_the_admissible_region_is_strictly_inside_the_frame_footprint():
    f = _frame()
    plane = LocalPlane.centred_on([f.frame_polygon()])
    whole = polygon_area_km2(plane.to_km(f.frame_polygon()))
    inset = polygon_area_km2(plane.to_km(
        tile_admissible_polygon(f, n_lines=401, n_samples=41)))
    assert 0.0 < inset < whole


def test_a_tile_larger_than_the_frame_is_refused_not_inverted():
    f = _frame(lines=1001, samples=101)
    with pytest.raises(ValueError, match="does not fit"):
        tile_admissible_polygon(f, n_lines=1002, n_samples=21)
    with pytest.raises(ValueError, match="does not fit"):
        tile_admissible_polygon(f, n_lines=101, n_samples=102)


def test_every_point_in_the_admissible_region_gives_an_unclamped_window():
    """The property the region is *for*, checked against the arithmetic that
    ``acquire_real_pair.window_centred_on`` actually performs."""
    f = _frame(lines=1001, samples=101)
    n_lines, n_samples = 201, 41
    poly = tile_admissible_polygon(f, n_lines=n_lines, n_samples=n_samples)
    for u in (0.0, 0.5, 1.0):
        for v in (0.0, 0.5, 1.0):
            top = poly[0] + u * (poly[1] - poly[0])
            bot = poly[3] + u * (poly[2] - poly[3])
            lon, lat = top + v * (bot - top)
            line, sample = f.pixel_at(lon, lat)
            want_l = int(round(line - (n_lines - 1) / 2.0))
            want_s = int(round(sample - (n_samples - 1) / 2.0))
            assert 0 <= want_l <= f.lines - n_lines
            assert 0 <= want_s <= f.samples - n_samples


def test_a_point_just_outside_the_region_does_clamp():
    """The complement of the property above -- otherwise the test passes for a
    region that is simply the whole frame."""
    f = _frame(lines=1001, samples=101)
    n_lines = 201
    lon, lat = f.lonlat_at(10.0, 50.0)          # 10 lines from the top edge
    line, _ = f.pixel_at(lon, lat)
    assert int(round(line - (n_lines - 1) / 2.0)) < 0


def test_shared_tile_target_of_one_frame_is_its_own_region_centre():
    f = _frame()
    lon, lat = shared_tile_target([f], n_lines=101, n_samples=21)
    assert np.allclose((lon, lat), f.lonlat_at(500.0, 50.0), atol=1e-9)


def test_shared_tile_target_lands_where_both_frames_can_hold_a_tile():
    a = _frame()
    b = _frame(upper_left=(10.0, 20.5), upper_right=(10.2, 20.5),
               lower_left=(10.0, 19.5), lower_right=(10.2, 19.5))
    n_lines, n_samples = 201, 41
    lon, lat = shared_tile_target([a, b], n_lines=n_lines, n_samples=n_samples)
    for f in (a, b):
        line, sample = f.pixel_at(lon, lat)
        want_l = int(round(line - (n_lines - 1) / 2.0))
        want_s = int(round(sample - (n_samples - 1) / 2.0))
        assert 0 <= want_l <= f.lines - n_lines
        assert 0 <= want_s <= f.samples - n_samples


def test_frames_that_overlap_but_cannot_both_hold_a_tile_are_refused():
    """The case the function exists for: the footprints intersect, so the old
    shared-frame centroid returns a point happily, but the overlap is thinner
    than a tile and every window cut there would be clamped."""
    a = _frame()
    b = _frame(upper_left=(10.0, 20.02), upper_right=(10.2, 20.02),
               lower_left=(10.0, 19.02), lower_right=(10.2, 19.02))
    plane = LocalPlane.centred_on([a.frame_polygon(), b.frame_polygon()])
    assert len(convex_clip(plane.to_km(a.frame_polygon()),
                           plane.to_km(b.frame_polygon()))) >= 3
    with pytest.raises(ValueError, match="share no ground"):
        shared_tile_target([a, b], n_lines=901, n_samples=41)


def test_shared_tile_target_needs_at_least_one_frame():
    with pytest.raises(ValueError, match="no frames"):
        shared_tile_target([], n_lines=11, n_samples=11)


# ---------------------------------------------------------------------------
# The bilinear ground map's error budget, measured rather than asserted
# ---------------------------------------------------------------------------
#
# Added by the 2026-08-29 pre-freeze audit. REAL-DATA-02 section 11 lists
# "bilinear model vs true sensor geometry" as a residual bounded at "<= 1.2% of
# frame extent" and explicitly NOT separately propagated. A reviewer is
# entitled to ask what that residual actually is, because
# scripts/check_transform_against_geometry.py turns it into a term of the
# discrimination floor that decides whether an edge is called INCONSISTENT.
#
# These tests measure it from the committed archive corners, on the real
# frames, so the answer is evidence in the repository rather than a number in
# a comment. They read no image data and no registration artefact.

import json as _json
from pathlib import Path as _Path

_MANIFESTS = _Path(__file__).resolve().parents[1] / "data" / "manifests"
_GEOMETRY_FILES = [
    "real_pair_index_geometry.json",
    "real_pair_index_geometry_C.json",
    "real_frame_d_candidates_index_geometry.json",
    "real_frame_d_selected_index_geometry.json",
]
#: The four frames every real-data conclusion rests on.
_REAL_FRAMES = ["nac.m1271742202lc", "nac.m1335207975rc",
                "nac.m1452560468lc", "nac.m1299958135lc"]
_MOON_R_KM = MOON_RADIUS_KM


def _real_fields():
    out = {}
    for name in _GEOMETRY_FILES:
        p = _MANIFESTS / name
        if p.exists():
            out.update(_json.loads(p.read_text(encoding="utf-8"))["products"])
    return {k: v["fields"] for k, v in out.items() if k in _REAL_FRAMES}


def _great_circle_km(a, b):
    (lo1, la1), (lo2, la2) = np.deg2rad(a), np.deg2rad(b)
    return float(_MOON_R_KM * 2 * np.arcsin(np.sqrt(
        np.sin((la2 - la1) / 2) ** 2
        + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2)))


def test_bilinear_departure_is_within_the_recorded_model_term():
    """The geometric error of a bilinear map, measured on the real frames.

    A bilinear map is a straight line in (lon, lat) between two named corners;
    the true ground track is a great circle. The gap between them peaks at
    mid-frame and is the ONLY genuine shape error the model has, because the
    map is pinned exactly at both ends. Measured here as the sagitta.

    ``check_transform_against_geometry.BILINEAR_MODEL_RESIDUAL`` produces
    0.012 x half a 2048x1024 tile diagonal = 13.7 px. This asserts the measured
    departure is BELOW that, i.e. the recorded floor is conservative. If a
    future frame breaks this, the floor is no longer conservative and the
    INCONSISTENT verdicts computed with it must be re-examined -- which is why
    the assertion is stated in that direction.
    """
    fields = _real_fields()
    assert len(fields) == 4, "the four real frames' corner geometry must be on disk"
    for pdsid, f in fields.items():
        ul = (float(f["UPPER_LEFT_LONGITUDE"]), float(f["UPPER_LEFT_LATITUDE"]))
        ll = (float(f["LOWER_LEFT_LONGITUDE"]), float(f["LOWER_LEFT_LATITUDE"]))
        # midpoint of the great circle vs the midpoint of the straight line
        la1, lo1 = np.deg2rad(ul[1]), np.deg2rad(ul[0])
        la2, lo2 = np.deg2rad(ll[1]), np.deg2rad(ll[0])
        bx = np.cos(la2) * np.cos(lo2 - lo1)
        by = np.cos(la2) * np.sin(lo2 - lo1)
        gc_mid = (np.rad2deg(lo1 + np.arctan2(by, np.cos(la1) + bx)),
                  np.rad2deg(np.arctan2(np.sin(la1) + np.sin(la2),
                                        np.hypot(np.cos(la1) + bx, by))))
        lin_mid = ((ul[0] + ll[0]) / 2, (ul[1] + ll[1]) / 2)
        sagitta_m = _great_circle_km(gc_mid, lin_mid) * 1000.0

        scale_m_per_line = (_great_circle_km(ul, ll) * 1000.0
                            / (int(f["IMAGE_LINES"]) - 1))
        sagitta_px_decimated = sagitta_m / scale_m_per_line / 2.0
        assert sagitta_px_decimated < 13.7, (
            f"{pdsid}: bilinear departure is {sagitta_px_decimated:.1f} "
            "decimated px, at or above the 13.7 px model term the "
            "discrimination floor uses; the floor is no longer conservative")
        assert sagitta_m < 15.0, f"{pdsid}: sagitta {sagitta_m:.1f} m"


def test_corner_implied_scale_agrees_with_spice_inside_corner_quantisation():
    """The 1.2% of REAL-DATA-02 section 6.6a is quantisation, not model error.

    Corner-implied metres-per-line is compared against the archive's
    SPICE-derived SCALED_PIXEL_HEIGHT. The disagreement must sit inside the
    budget that the +-0.005 deg corner quantisation alone allows on the same
    span -- which is what makes it evidence of agreement rather than evidence
    of a residual.
    """
    for pdsid, f in _real_fields().items():
        ul = (float(f["UPPER_LEFT_LONGITUDE"]), float(f["UPPER_LEFT_LATITUDE"]))
        ll = (float(f["LOWER_LEFT_LONGITUDE"]), float(f["LOWER_LEFT_LATITUDE"]))
        ur = (float(f["UPPER_RIGHT_LONGITUDE"]), float(f["UPPER_RIGHT_LATITUDE"]))
        lr = (float(f["LOWER_RIGHT_LONGITUDE"]), float(f["LOWER_RIGHT_LATITUDE"]))
        span_km = 0.5 * (_great_circle_km(ul, ll) + _great_circle_km(ur, lr))
        implied = span_km * 1000.0 / (int(f["IMAGE_LINES"]) - 1)
        spice = float(f["SCALED_PIXEL_HEIGHT"])
        disagreement = abs(implied / spice - 1.0)
        # two corners, each quantised at +-0.005 deg, on this span
        quant_budget = (0.005 * 111.7 * np.sqrt(2)) / span_km
        assert disagreement <= quant_budget, (
            f"{pdsid}: corner-implied {implied:.4f} m/line vs SPICE {spice:.2f} "
            f"is {disagreement*100:.2f}% apart, OUTSIDE the {quant_budget*100:.2f}% "
            "the corner quantisation allows -- that would be a real model "
            "residual and REAL-DATA-02 section 11 would need revisiting")


def test_ground_speed_from_the_spacecraft_clock_corroborates_the_corner_span():
    """An independent check on the corners, from timing rather than geometry.

    START_TIME/STOP_TIME come from the spacecraft clock, not from the SPICE
    pointing solution that produced the corners. Dividing the corner-implied
    along-track ground distance by the frame duration must give a physically
    correct LRO ground-track speed. It does, consistently, for frames acquired
    years apart -- which no plausible corner-reading error would survive.
    """
    from datetime import datetime
    speeds = {}
    for pdsid, f in _real_fields().items():
        ul = (float(f["UPPER_LEFT_LONGITUDE"]), float(f["UPPER_LEFT_LATITUDE"]))
        ll = (float(f["LOWER_LEFT_LONGITUDE"]), float(f["LOWER_LEFT_LATITUDE"]))
        t0 = datetime.strptime(f["START_TIME"], "%Y-%m-%d %H:%M:%S.%f")
        t1 = datetime.strptime(f["STOP_TIME"], "%Y-%m-%d %H:%M:%S.%f")
        speeds[pdsid] = _great_circle_km(ul, ll) / (t1 - t0).total_seconds()
    for pdsid, v in speeds.items():
        assert 1.4 < v < 1.8, (
            f"{pdsid}: corner span over frame duration gives {v:.3f} km/s, "
            "which is not an LRO ground-track speed -- the corners or the "
            "line count are being misread")
    spread = max(speeds.values()) / min(speeds.values()) - 1.0
    assert spread < 0.05, (
        f"ground speed varies by {spread*100:.1f}% across frames; the corner "
        "reading is not consistent between acquisitions")
