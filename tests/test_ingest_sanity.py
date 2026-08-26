"""Pre-pipeline sanity checks on decoded tiles.

Includes regressions for two defects found while building this module against
real data (E-023, E-024/E-025 family):

* a statistic that collapsed onto the ``-32768`` sentinel border and reported
  an identical 0.9919 for two different frames;
* a diagnosis that blamed "byte-order reversal or misaligned offset" for a
  tile whose decode was demonstrably correct and whose scene was simply
  noise-dominated.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import ndimage

from siim.ingest.pds4 import parse_image_structure
from siim.ingest.sanity import (
    MIN_PLAUSIBLE_AUTOCORR,
    byte_alignment_evidence,
    byte_order_evidence,
    check_tile,
    lag1_autocorrelation,
)
from test_ingest_pds4 import make_label


def smooth_scene(rows=64, cols=48, seed=3, amp=400.0, base=1500.0) -> np.ndarray:
    """Smooth, positive, terrain-like field as int16-compatible DN."""
    g = np.random.default_rng(seed).normal(size=(rows, cols))
    s = ndimage.gaussian_filter(g, sigma=3.0)
    s = (s - s.min()) / (s.max() - s.min())
    return (base + amp * s).astype("<i2")


def as_bytes(img: np.ndarray, dtype="<i2") -> bytes:
    return img.astype(np.dtype(dtype)).tobytes()


# --------------------------------------------------------------------------
# lag-1 autocorrelation: the central discriminator
# --------------------------------------------------------------------------

def test_autocorrelation_is_high_for_smooth_terrain():
    assert lag1_autocorrelation(smooth_scene()) > 0.95


def test_autocorrelation_collapses_for_white_noise():
    noise = np.random.default_rng(0).integers(-2000, 2000, size=(64, 48))
    assert abs(lag1_autocorrelation(noise)) < 0.2


def test_autocorrelation_is_nan_for_a_constant_tile():
    assert not np.isfinite(lag1_autocorrelation(np.full((32, 32), 7.0)))


def test_autocorrelation_ignores_nan_pixels():
    img = smooth_scene().astype(float)
    img[::7, ::5] = np.nan
    assert lag1_autocorrelation(img) > 0.9


# --------------------------------------------------------------------------
# byte-order and alignment evidence
# --------------------------------------------------------------------------

def test_declared_byte_order_beats_the_swapped_one_on_real_shaped_data():
    img = smooth_scene(32, 24)
    s = parse_image_structure(make_label(lines=32, samples=24, offset=0))
    ev = byte_order_evidence(as_bytes(img), s, n_lines=32)
    assert ev["declared_dtype"] == "<i2"
    assert ev["autocorr_as_declared"] > ev["autocorr_byte_swapped"] + 0.3


def test_byte_order_evidence_flags_a_file_written_big_endian():
    """The label says SignedLSB2 but the bytes are big-endian: the swapped
    decode is the coherent one, and that must be visible."""
    img = smooth_scene(32, 24)
    s = parse_image_structure(make_label(lines=32, samples=24, offset=0))
    ev = byte_order_evidence(as_bytes(img, ">i2"), s, n_lines=32)
    assert ev["autocorr_byte_swapped"] > ev["autocorr_as_declared"]


def test_alignment_evidence_prefers_the_planned_offset():
    img = smooth_scene(32, 24)
    s = parse_image_structure(make_label(lines=32, samples=24, offset=0))
    ev = byte_alignment_evidence(as_bytes(img), s, n_lines=32)
    assert ev["autocorr_aligned"] > ev["autocorr_shifted_one_byte"] + 0.3


# --------------------------------------------------------------------------
# E-023: the sentinel border must not dominate the statistic
# --------------------------------------------------------------------------

def test_sentinel_border_does_not_dominate_the_autocorrelation():
    """E-023 regression.

    A whole-line NAC read carries wide constant ``-32768`` border columns whose
    variance (~3700 DN) dwarfs the scene's (~20 DN). Unmasked, the lag-1
    correlation measures the border: two DIFFERENT frames both scored exactly
    0.9919, with a vertical correlation of exactly 1.0000. Masking sentinels
    must make the statistic reflect the scene, so two different scenes must no
    longer produce the same number.
    """
    rows, cols, border = 40, 60, 20
    s = parse_image_structure(make_label(lines=rows, samples=cols, offset=0))

    def framed(seed, amp):
        scene = smooth_scene(rows, cols - 2 * border, seed=seed, amp=amp)
        out = np.full((rows, cols), -32768, dtype="<i2")
        out[:, border:cols - border] = scene
        return out

    quiet = framed(seed=1, amp=30.0)     # low-contrast scene
    loud = framed(seed=2, amp=900.0)     # high-contrast scene

    unmasked = [lag1_autocorrelation(x.astype(float)) for x in (quiet, loud)]
    ev_q = byte_order_evidence(as_bytes(quiet), s, n_lines=rows)
    ev_l = byte_order_evidence(as_bytes(loud), s, n_lines=rows)
    masked = [ev_q["autocorr_as_declared"], ev_l["autocorr_as_declared"]]

    # unmasked: the border swamps both, so they look nearly identical
    assert abs(unmasked[0] - unmasked[1]) < 1e-3
    assert min(unmasked) > 0.95
    # masked: the two scenes are distinguishable again
    assert abs(masked[0] - masked[1]) > 1e-3


def test_valid_minimum_is_not_treated_as_a_border_sentinel():
    s = parse_image_structure(make_label(lines=8, samples=8, offset=0))
    assert -32768 in s.sentinel_values
    assert -32752 not in s.sentinel_values


# --------------------------------------------------------------------------
# check_tile end to end
# --------------------------------------------------------------------------

def _struct(rows, cols):
    return parse_image_structure(make_label(lines=rows, samples=cols, offset=0))


def test_check_tile_passes_a_well_formed_terrain_tile():
    img = smooth_scene(48, 40)
    s = _struct(48, 40)
    chk = check_tile(img.astype(float), s, raw=as_bytes(img), n_lines=48,
                     expected_shape=(48, 40))
    assert chk.passed, chk.failures
    assert chk.stats["decode_verdict"] == "consistent"
    assert chk.stats["lag1_autocorrelation"] > MIN_PLAUSIBLE_AUTOCORR


def test_check_tile_reports_the_uncheckable_as_a_warning_not_a_pass():
    """An offset wrong by whole lines yields a valid image of the wrong place.
    That must be stated, not omitted."""
    img = smooth_scene(48, 40)
    chk = check_tile(img.astype(float), _struct(48, 40),
                     raw=as_bytes(img), n_lines=48)
    assert any("wrong place" in w or "intended region" in w for w in chk.warnings)


def test_check_tile_fails_a_byte_swapped_tile_and_blames_the_decode():
    img = smooth_scene(48, 40)
    raw = as_bytes(img, ">i2")            # file is big-endian, label says LSB
    s = _struct(48, 40)
    decoded = np.frombuffer(raw, dtype="<i2").reshape(48, 40).astype(float)
    chk = check_tile(decoded, s, raw=raw, n_lines=48)
    assert not chk.passed
    assert chk.stats["decode_verdict"] == "byte order wrong"
    assert "decode defect" in chk.stats["failure_class"]


def test_check_tile_blames_data_quality_not_the_decode_for_a_noisy_scene():
    """E-024 regression.

    A terminator NAC frame decodes correctly and still has almost no
    pixel-scale structure (measured: lag-1 0.355 with DN 29 +/- 20, against
    0.976 for its correctly-decoded partner). The check must fail it -- it is
    unusable for matching -- while attributing the failure to DATA QUALITY,
    because calling it a decoding defect would send the next reader to debug
    working code.
    """
    rng = np.random.default_rng(11)
    noisy = (29 + rng.normal(0, 20, size=(48, 40))).astype("<i2")
    s = _struct(48, 40)
    chk = check_tile(noisy.astype(float), s, raw=as_bytes(noisy), n_lines=48)
    assert not chk.passed
    # On a tile this noisy the byte-order test has no discriminating power, and
    # saying so is the honest outcome -- a 0.0002 difference between two ~0
    # values must never be reported as "byte order wrong".
    assert chk.stats["decode_verdict"] == "inconclusive"
    assert abs(chk.stats["decode_margin_byte_order"]) < 0.10
    assert "data quality" in chk.stats["failure_class"]
    assert any("DATA-QUALITY" in f for f in chk.failures)
    assert any("INCONCLUSIVE" in w for w in chk.warnings)


def test_thin_decode_margins_are_never_reported_as_a_decode_defect():
    """E-023b regression: evidence below the margin is inconclusive, not proof.

    Measured on the real terminator frame nac.m1322281266lc: declared 0.3553
    vs byte-swapped 0.3531. A bare ``>`` comparison called that a byte-order
    defect in working code.
    """
    rng = np.random.default_rng(5)
    noisy = (29 + rng.normal(0, 20, size=(64, 48))).astype("<i2")
    s = _struct(64, 48)
    chk = check_tile(noisy.astype(float), s, raw=as_bytes(noisy), n_lines=64)
    assert chk.stats["decode_verdict"] != "byte order wrong"
    assert chk.stats["decode_verdict"] != "offset misaligned"
    assert "decode defect" not in chk.stats.get("failure_class", "")


def test_check_tile_fails_a_constant_tile():
    flat = np.full((32, 32), 500.0)
    chk = check_tile(flat, _struct(32, 32))
    assert not chk.passed
    assert any("constant" in f for f in chk.failures)


def test_check_tile_fails_a_mostly_zero_tile():
    """Zero-fill is what a padded or truncated read looks like, and on the Moon
    near-zero is a legal value (E-003), so it must be caught explicitly."""
    img = smooth_scene(48, 40).astype(float)
    img[20:, :] = 0.0          # 58% zeros, past the 50% threshold
    chk = check_tile(img, _struct(48, 40))
    assert not chk.passed
    assert any("exactly zero" in f for f in chk.failures)


def test_check_tile_fails_on_a_shape_mismatch():
    img = smooth_scene(48, 40).astype(float)
    chk = check_tile(img, _struct(48, 40), expected_shape=(48, 41))
    assert not chk.passed
    assert any("shape" in f for f in chk.failures)


def test_check_tile_says_when_byte_evidence_was_skipped():
    img = smooth_scene(48, 40).astype(float)
    chk = check_tile(img, _struct(48, 40))       # no raw bytes supplied
    assert chk.stats["byte_order"] is None
    assert chk.stats["decode_verdict"] == "unknown"
    assert any("SKIPPED" in w for w in chk.warnings)


def test_check_tile_counts_saturation_against_the_labels_own_sentinels():
    img = smooth_scene(40, 40)
    img[:8, :] = -32766                      # low_instrument_saturation
    s = _struct(40, 40)
    chk = check_tile(img, s, raw=as_bytes(img), n_lines=40)
    sat = chk.stats["saturation_fractions"]
    assert sat["low_instrument_saturation"] == pytest.approx(0.2, abs=1e-6)
    assert any("saturation" in w for w in chk.warnings)


def test_nan_and_inf_are_counted_separately_and_inf_fails():
    img = smooth_scene(32, 32).astype(float)
    img[0, 0] = np.inf
    chk = check_tile(img, _struct(32, 32))
    assert chk.stats["n_inf"] == 1
    assert not chk.passed
