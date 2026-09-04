"""Deterministic north-up from archive geometry (REAL-DATA-07 machinery)."""

from __future__ import annotations

import numpy as np
import pytest

from siim.ingest.footprint import FrameCorners
from siim.ingest.orientation import (
    _rot90_transform,
    north_up,
    north_up_rotation_k,
    orientation_signature,
)


def _frame(along: int, cross: int) -> FrameCorners:
    lat_top, lat_bot = (19.0, 21.0) if along == 1 else (21.0, 19.0)
    lon_left, lon_right = (22.0, 22.2) if cross == 1 else (22.2, 22.0)
    return FrameCorners(upper_left=(lon_left, lat_top), upper_right=(lon_right, lat_top),
                        lower_left=(lon_left, lat_bot), lower_right=(lon_right, lat_bot),
                        lines=52224, samples=5064)


@pytest.mark.parametrize("along,cross,expected_k", [
    (-1, 1, 0),    # line 0 at max latitude, east to the right: already north-up
    (1, -1, 2),    # the recorded frames (E-032): rotate 180
])
def test_quarter_turns_follow_the_corner_columns(along, cross, expected_k):
    assert orientation_signature(_frame(along, cross)) == (along, cross)
    assert north_up_rotation_k(_frame(along, cross), 26000, 2500) == expected_k


def test_the_real_frame_a_needs_a_half_turn():
    a = FrameCorners(upper_left=(22.08, 19.39), upper_right=(21.93, 19.40),
                     lower_left=(22.19, 21.06), lower_right=(22.02, 21.07),
                     lines=52224, samples=5064)
    assert orientation_signature(a) == (1, -1)
    assert north_up_rotation_k(a, 20000, 2500) == 2


@pytest.mark.parametrize("k", [0, 1, 2, 3])
def test_rot90_transform_matches_numpy_on_a_labelled_array(k):
    """The map must agree with np.rot90 for every pixel, not just the corners."""
    h, w = 5, 8
    a = np.arange(h * w).reshape(h, w)
    out = np.rot90(a, k)
    tf = _rot90_transform((h, w), k)
    yy, xx = np.mgrid[0:h, 0:w]
    src = np.column_stack([xx.ravel(), yy.ravel()]).astype(float)
    dst = tf.apply(src)
    for (x, y), (x2, y2) in zip(src, dst):
        assert out[int(round(y2)), int(round(x2))] == a[int(y), int(x)]


def test_north_up_is_an_exact_permutation_with_an_exact_inverse():
    rng = np.random.default_rng(0)
    img = rng.random((64, 32))
    res = north_up(img, _frame(1, -1), line=26000, sample=2500)
    assert res.k == 2
    assert np.array_equal(res.image, img[::-1, ::-1])
    p = np.array([[3.0, 7.0], [31.0, 63.0]])
    back = res.inverse.apply(res.forward.apply(p))
    np.testing.assert_allclose(back, p, atol=1e-12)
    assert res.record["quarter_turns_ccw"] == 2


def test_an_already_north_up_frame_is_untouched():
    img = np.zeros((10, 6))
    res = north_up(img, _frame(-1, 1), line=26000, sample=2500)
    assert res.k == 0 and res.image is img
    np.testing.assert_allclose(res.forward.matrix, np.eye(3))
