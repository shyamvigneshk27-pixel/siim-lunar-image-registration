"""Equirectangular map blocks: pixel-registered round trips and block offsets."""

from __future__ import annotations

import numpy as np
import pytest

from siim.ingest.mapgrid import MapBlock


def _block():
    return MapBlock(data=np.zeros((100, 80), np.float32), row0=7600, col0=100,
                    ppd_lat=2048.0, ppd_lon=2048.0, lat_top_deg=24.017439,
                    lon_left_deg=21.503989, name="t", provenance={})


def test_pixel_centre_convention_round_trips():
    b = _block()
    lat = b.lat_of_line(7650)
    assert b.line_of_lat(lat) == pytest.approx(7650.0, abs=1e-9)
    lon = b.lon_of_sample(140)
    assert b.sample_of_lon(lon) == pytest.approx(140.0, abs=1e-9)


def test_block_coordinates_subtract_the_block_origin():
    b = _block()
    xy = b.block_xy_of_lonlat(b.lon_of_sample(140), b.lat_of_line(7650))
    assert xy[0, 0] == pytest.approx(40.0, abs=1e-9)
    assert xy[0, 1] == pytest.approx(50.0, abs=1e-9)
    lon, lat = b.lonlat_of_block_xy(40.0, 50.0)
    assert lon == pytest.approx(b.lon_of_sample(140))
    assert lat == pytest.approx(b.lat_of_line(7650))


def test_metres_per_pixel_is_about_fifteen_for_the_minirf_grid():
    mx, my = _block().metres_per_pixel
    assert 13.5 < mx < 15.0 and 14.5 < my < 15.0


def test_ranges_are_ordered():
    b = _block()
    lo, hi = b.lat_range
    assert lo < hi
    lo, hi = b.lon_range
    assert lo < hi
