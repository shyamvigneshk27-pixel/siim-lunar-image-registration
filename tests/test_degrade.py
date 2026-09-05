"""PSF-aware degradation (R9): the box average is its zero-PSF member, the
Gaussian member is smoother, NaN never leaks, and the grid contract holds."""

from __future__ import annotations

import numpy as np
import pytest

from siim.preprocessing.degrade import block_mean, degrade_to_gsd, psf_sigma_fine_px


def test_zero_psf_is_exactly_the_recorded_box_average(rng):
    a = rng.uniform(size=(64, 48))
    k = 8
    box = a.reshape(8, k, 6, k).mean(axis=(1, 3))
    np.testing.assert_allclose(degrade_to_gsd(a, k, psf_fwhm_coarse_px=0.0), box)
    np.testing.assert_allclose(block_mean(a, k), box)


def test_block_mean_drops_incomplete_trailing_blocks(rng):
    a = rng.uniform(size=(37, 29))
    out = block_mean(a, 8)
    assert out.shape == (4, 3)


def test_psf_sigma_scales_with_k_and_fwhm():
    assert psf_sigma_fine_px(1, 1.0) == pytest.approx(1 / (2 * np.sqrt(2 * np.log(2))))
    assert psf_sigma_fine_px(16, 1.0) == pytest.approx(16 * psf_sigma_fine_px(1, 1.0))
    assert psf_sigma_fine_px(16, 0.0) == 0.0


def test_gaussian_member_removes_more_high_frequency_than_the_box(rng):
    """A checkerboard at the fine Nyquist survives a box average as aliasing
    residue when k is odd; the Gaussian member must attenuate it further."""
    yy, xx = np.mgrid[0:99, 0:99]
    a = ((yy + xx) % 2).astype(float) + 0.05 * rng.normal(size=(99, 99))
    k = 3
    box = degrade_to_gsd(a, k, psf_fwhm_coarse_px=0.0)
    psf = degrade_to_gsd(a, k, psf_fwhm_coarse_px=1.0)
    assert psf.shape == box.shape == (33, 33)
    assert np.nanstd(psf) < np.nanstd(box)


def test_nan_does_not_leak_or_bias(rng):
    a = np.full((64, 64), 0.5) + 0.01 * rng.normal(size=(64, 64))
    a[20:28, 20:28] = np.nan
    out = degrade_to_gsd(a, 4, psf_fwhm_coarse_px=1.0)
    # the fully-invalid coarse block stays NaN ...
    assert np.isnan(out[5:7, 5:7]).all()
    # ... and every valid coarse pixel stays near the constant
    v = out[np.isfinite(out)]
    assert np.abs(v - 0.5).max() < 0.02


def test_mean_is_preserved_on_a_constant_image():
    a = np.full((40, 40), 3.25)
    out = degrade_to_gsd(a, 5, psf_fwhm_coarse_px=1.5)
    np.testing.assert_allclose(out, 3.25)


def test_rejects_bad_arguments(rng):
    with pytest.raises(ValueError):
        degrade_to_gsd(rng.uniform(size=(8, 8)), 0)
    with pytest.raises(ValueError):
        degrade_to_gsd(rng.uniform(size=(8, 8)), 2, psf_fwhm_coarse_px=-1)
    with pytest.raises(ValueError):
        block_mean(rng.uniform(size=(3, 3)), 4)
    with pytest.raises(ValueError):
        degrade_to_gsd(rng.uniform(size=(4, 4, 3)), 2)
