"""EXP-007 building blocks: DEM-on-tile-grid geometry, Sun direction in image
axes, DEM rendering, and the licensable learned engine.

The tests worth reading first are the two orientation tests. A DEM render
under a Sun that is 180 degrees wrong in image axes is still a perfectly
plausible shaded relief, so an azimuth-convention error here would produce
a clean, confident, wrong experiment.
"""

from __future__ import annotations

import numpy as np
import pytest

from siim.ingest.footprint import FrameCorners
from siim.ingest.lola_dem import (
    MOON_RADIUS_M,
    DemWindow,
    dem_on_tile_grid,
    local_incidence_deg,
    sun_in_tile_frame,
)
from siim.preprocessing.dem_render import render_tile_under_sun


def _dem(rows=200, cols=23040, row0=5000, fill=None):
    h = np.zeros((rows, cols), np.float32) if fill is None else fill
    return DemWindow(heights_km=h, row0=row0, ppd=512, lat_top_deg=30.0,
                     lon_left_deg=0.0, provenance={"test": True})


def _north_up_frame():
    """Line 0 at MAXIMUM latitude, sample increasing EASTWARD: a map-like frame.

    The longitude span is chosen so the pixels are SQUARE on the ground
    (0.4 deg of latitude over 2000 lines; 0.4 / cos(20.2 deg) / 10 of longitude
    over 200 samples). With non-square pixels a direction in pixel axes is a
    different angle from the same direction on the ground, which is physics,
    not a defect, and the real NAC frames carry 3-7 % of that anisotropy."""
    span_lon = 0.4 / np.cos(np.deg2rad(20.2)) / 10.0
    return FrameCorners(upper_left=(22.00, 20.40), upper_right=(22.00 + span_lon, 20.40),
                        lower_left=(22.00, 20.00), lower_right=(22.00 + span_lon, 20.00),
                        lines=2001, samples=201)


def _archive_like_frame():
    """The real NAC frames: line 0 at MINIMUM latitude, sample increasing WESTWARD (E-032)."""
    return FrameCorners(upper_left=(22.08, 19.39), upper_right=(21.93, 19.40),
                        lower_left=(22.19, 21.06), lower_right=(22.02, 21.07),
                        lines=52224, samples=5064)


# ---------------------------------------------------------------------------
# DEM sampling
# ---------------------------------------------------------------------------

def test_dem_height_lookup_uses_the_pixel_registered_label_convention():
    """lat = 30 - (line + 0.5)/512: a lookup exactly on a pixel centre returns it."""
    h = np.zeros((10, 23040), np.float32)
    h[3, 11276] = -2.75
    dem = _dem(rows=10, row0=5100, fill=h)
    line = 5103
    lat = 30.0 - (line + 0.5) / 512
    lon = (11276 + 0.5) / 512
    assert dem.height_m_at(lon, lat) == pytest.approx(-2750.0)


def test_dem_lookup_outside_the_window_raises_instead_of_clamping():
    dem = _dem(rows=10, row0=5100)
    with pytest.raises(ValueError, match="outside the fetched DEM window"):
        dem.height_m_at(22.0, 29.0)


def test_decimated_tile_pixel_is_sampled_at_the_block_centre():
    """A decimated pixel is the mean of a k x k block and sits at its centre."""
    f = _north_up_frame()
    dem = _dem(rows=400, row0=4900)
    _, lon, lat = dem_on_tile_grid(dem, f, line0=100, sample0=20, n_lines=40,
                                   n_samples=8, decimation=4)
    exp_lon, exp_lat = f.lonlat_at(100 + 1.5, 20 + 1.5)
    assert lon[0, 0] == pytest.approx(exp_lon, abs=1e-9)
    assert lat[0, 0] == pytest.approx(exp_lat, abs=1e-9)
    assert lon.shape == (10, 2)


# ---------------------------------------------------------------------------
# the Sun in image axes -- the convention that decides the experiment
# ---------------------------------------------------------------------------

def test_north_up_frame_keeps_the_ground_azimuth():
    """Map-like frame: image up is north, image right is east, so azimuths agree."""
    f = _north_up_frame()
    sub_lon = 22.00 + 0.4 / np.cos(np.deg2rad(20.2)) / 20.0   # frame centre longitude
    s = sun_in_tile_frame(f, 1000, 100, sub_lon, -40.0)          # Sun due SOUTH
    assert s["azimuth_ground_deg_cw_from_north"] == pytest.approx(180.0, abs=0.5)
    assert s["azimuth_image_deg_cw_from_up"] == pytest.approx(180.0, abs=0.5)
    east = sun_in_tile_frame(f, 1000, 100, 60.0, 20.2)
    assert east["azimuth_image_deg_cw_from_up"] == pytest.approx(
        east["azimuth_ground_deg_cw_from_north"], abs=1.0)


def test_archive_frame_rotates_the_azimuth_by_about_180_degrees():
    """Line 0 at minimum latitude and westward samples: north is image DOWN,
    east is image LEFT. A Sun due east on the ground is due left in the image."""
    f = _archive_like_frame()
    s = sun_in_tile_frame(f, 20000, 2500, 60.0, 20.2)
    assert 80 < s["azimuth_ground_deg_cw_from_north"] < 100
    assert 260 < s["azimuth_image_deg_cw_from_up"] < 280
    assert s["north_direction_in_pixels_xy"][1] > 0       # north points to +line


def test_elevation_is_ninety_minus_incidence_and_scale_is_sane():
    f = _archive_like_frame()
    s = sun_in_tile_frame(f, 20000, 2500, 44.82, 0.21)
    assert s["elevation_deg"] == pytest.approx(90.0 - s["incidence_deg"])
    lo, hi = s["corner_map_pixel_scale_m"]
    assert 0.7 < lo < 1.3 and 0.7 < hi < 1.3            # NAC at ~0.9-1.0 m


def test_corner_map_jacobian_matches_the_lunar_radius():
    """One degree of latitude along a north-up frame is pi/180 * R metres."""
    f = _north_up_frame()
    s_top = sun_in_tile_frame(f, 0, 100, 22.02, -40.0)
    s_bot = sun_in_tile_frame(f, 2000, 100, 22.02, -40.0)
    scale = s_top["corner_map_pixel_scale_m"][1]
    span_m = scale * 2000
    assert span_m == pytest.approx(np.deg2rad(0.4) * MOON_RADIUS_M, rel=0.02)
    assert s_bot["lon_lat_at_pixel"][1] < s_top["lon_lat_at_pixel"][1]


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def test_render_of_a_flat_dem_is_uniform_and_lit_by_cos_incidence():
    f = _north_up_frame()
    dem = _dem(rows=400, row0=4900)
    r = render_tile_under_sun(dem, f, line0=100, sample0=20, n_lines=64,
                              n_samples=64, decimation=1, pixel_scale_m=30.0,
                              sub_solar_lon_deg=22.02, sub_solar_lat_deg=-40.0)
    assert r.image.shape == (64, 64)
    assert r.image.std() < 1e-9
    inc = r.record["sun"]["incidence_deg"]
    expected = 0.06 + 0.94 * np.cos(np.deg2rad(inc))
    assert r.image.mean() == pytest.approx(expected, abs=1e-6)
    assert r.record["shadow_fraction"] == 0.0


def test_render_of_a_ridge_is_bright_on_the_sunward_side():
    """A north-south ridge lit from the east must be brighter on its east face."""
    f = _north_up_frame()
    h = np.zeros((400, 23040), np.float32)
    # a ridge along latitude (constant longitude column band) -> east/west faces
    cols = np.arange(23040)
    ridge = np.exp(-((cols - 11275) / 2.0) ** 2) * 0.2       # 200 m tall
    h[:] = ridge[None, :]
    dem = _dem(rows=400, row0=4900, fill=h)
    r = render_tile_under_sun(dem, f, line0=100, sample0=0, n_lines=40,
                              n_samples=200, decimation=1, pixel_scale_m=30.0,
                              sub_solar_lon_deg=60.0, sub_solar_lat_deg=20.2)
    # ridge at lon 22.0215 (sample 11275 -> (11275.5)/512); frame lon 22.00 + 0.0426 * u
    col = int(round((11275.5 / 512 - 22.0) / (0.4 / np.cos(np.deg2rad(20.2)) / 10.0) * 200))
    east_face = r.image[:, col + 2:col + 8].mean()
    west_face = r.image[:, col - 8:col - 2].mean()
    assert east_face > west_face


def test_local_incidence_is_the_spherical_incidence_on_flat_ground():
    flat = np.zeros((32, 32))
    inc = local_incidence_deg(flat, 270.0, 60.0, 30.0)
    assert np.allclose(inc, 30.0)


# ---------------------------------------------------------------------------
# learned engine
# ---------------------------------------------------------------------------

learned = pytest.importorskip("kornia", reason="kornia not installed")


def test_b4l_recovers_a_known_shift_on_terrain(terrain):
    from scipy import ndimage

    from siim.baselines import run_baseline

    reference = ndimage.shift(terrain, shift=(-4.0, 6.0), order=3, mode="reflect")
    res = run_baseline("B4L", terrain, reference, seed=0)
    assert res.runtime["engine"].startswith("B4L")
    assert res.success, res.ransac.reason
    probe = np.array([[100.0, 120.0], [60.0, 200.0]])
    mapped = res.transform.apply(probe)
    np.testing.assert_allclose(mapped, probe + np.array([6.0, -4.0]), atol=0.75)
    assert res.src_features.descriptors.shape[1] == 128


def test_b4l_is_registered_as_optional_and_b4_stays_refused(terrain):
    from siim.baselines import OPTIONAL_BASELINE_IDS, run_baseline

    assert "B4L" in OPTIONAL_BASELINE_IDS
    with pytest.raises(KeyError, match="ADR-0008"):
        run_baseline("B4", terrain, terrain)
