"""Reflection-aware orientation (E-037): a mirrored tile is flipped before the
quarter-turn, the composed transform is exact, and nothing changes for a tile
of the incumbents' handedness."""

from __future__ import annotations

import numpy as np
import pytest

from siim.ingest.footprint import FrameCorners
from siim.ingest.orientation import handedness, north_up, north_up_east_right


def _corners(mirrored: bool, along_north_down: bool = True) -> FrameCorners:
    """A synthetic frame: lines run north-south, samples east-west. The
    incumbents' handedness has east increasing with sample when north is up
    after the rotation; ``mirrored`` reverses the sample axis on the ground."""
    lon0, lat0, dlon, dlat = 22.0, 20.0, 0.05, 0.10
    # line 0 at the top row of the corner table; latitude decreases downward
    # when along_north_down, so north is UP in the image (k = 0 expected).
    top, bot = (lat0 + dlat, lat0) if along_north_down else (lat0, lat0 + dlat)
    left, right = (lon0, lon0 + dlon) if not mirrored else (lon0 + dlon, lon0)
    return FrameCorners(upper_left=(left, top), upper_right=(right, top),
                        lower_left=(left, bot), lower_right=(right, bot),
                        lines=4000, samples=2000)


@pytest.fixture
def tile(rng):
    return rng.uniform(size=(64, 32))


def test_handedness_sign_is_negative_for_a_proper_view_and_positive_when_mirrored():
    assert handedness(_corners(False), 2000, 1000) < 0
    assert handedness(_corners(True), 2000, 1000) > 0


def test_a_proper_tile_is_unchanged_relative_to_north_up(tile):
    c = _corners(False)
    a = north_up(tile, c, line=2000, sample=1000)
    b = north_up_east_right(tile, c, line=2000, sample=1000)
    np.testing.assert_array_equal(a.image, b.image)
    np.testing.assert_allclose(a.forward.matrix, b.forward.matrix)
    assert b.record["mirrored"] is False and b.k == a.k


def test_a_mirrored_tile_is_flipped_and_the_map_back_is_exact(tile):
    c = _corners(True)
    out = north_up_east_right(tile, c, line=2000, sample=1000)
    assert out.record["mirrored"] is True
    # the flipped-then-rotated image is a permutation of the original
    assert sorted(out.image.ravel()) == sorted(tile.ravel())
    # forward maps original (x, y) to the position of the same pixel value
    h, w = tile.shape
    for x, y in [(0, 0), (w - 1, 0), (5, 17), (w - 1, h - 1)]:
        xo, yo = out.forward.apply(np.array([[x, y]], float))[0]
        assert out.image[int(round(yo)), int(round(xo))] == tile[y, x]
    # inverse is exact
    pts = np.array([[3.0, 4.0], [20.0, 50.0]])
    np.testing.assert_allclose(out.inverse.apply(out.forward.apply(pts)), pts, atol=1e-12)


def test_mirrored_and_proper_views_of_the_same_ground_coincide_after_correction(rng):
    """The property that matters: two tiles of one ground, one of them mirrored,
    land on the same image once both are corrected."""
    ground = rng.uniform(size=(64, 32))
    proper = ground                       # north up, east right already
    mirrored = np.fliplr(ground)          # what a positive-determinant frame delivers
    a = north_up_east_right(proper, _corners(False), line=2000, sample=1000)
    b = north_up_east_right(mirrored, _corners(True), line=2000, sample=1000)
    np.testing.assert_array_equal(a.image, b.image)
    # the quarter-turn alone cannot do this
    c = north_up(mirrored, _corners(True), line=2000, sample=1000)
    assert not np.array_equal(a.image, c.image)
