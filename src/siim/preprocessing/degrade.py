"""PSF-aware degradation to a coarser ground sampling distance (R9).

Why a box average is not enough
-------------------------------
Every coarse-rung result so far (EXP-007 tier 2, REAL-DATA-08) degraded the
NAC source with a plain block mean: each coarse pixel is the average of a
k x k block of fine pixels. That is the correct *sampling* operator for an
ideal sensor whose pixel response is a box exactly one coarse pixel wide, and
it is what REAL-DATA-08 Part 2 records as a deviation from its own Part 1.

A real coarse sensor is not a box. Its point-spread function is wider than
its pixel -- optics, detector diffusion and along-track smear give an
effective MTF that a Gaussian of roughly one coarse pixel FWHM approximates
(the LROC WAC and Chandrayaan-2 IIRS instrument papers both quote MTF at
Nyquist well below the box value). Matching a box-averaged NAC strip against
a real 100 m mosaic therefore pits a *sharper* image against the reference
than the reference sensor could ever have produced, and the mismatch is
systematic in exactly the high-frequency band a detector keys on.

The operator
------------
1. Gaussian low-pass with sigma chosen so that the PSF's FWHM equals
   ``psf_fwhm_coarse_px`` coarse pixels (default 1.0), i.e.
   ``sigma_fine = psf_fwhm_coarse_px * k / (2 sqrt(2 ln 2))`` fine pixels,
   applied with NaN-aware normalisation so invalid pixels neither leak nor
   bias their neighbours.
2. Block mean over ``k x k`` (the sampling), so that the result is the same
   size and on the same grid as the box-average degradation and every
   coordinate convention (contract C1-C5, ``TileWindow``) is unchanged.

With ``psf_fwhm_coarse_px = 0`` the operator IS the box average, so the
recorded runs are the zero-PSF member of this family.

What it is not
--------------
Not a calibrated model of any particular instrument: the FWHM is a parameter
to be stated with every result that uses it, and nothing here claims the WAC
or IIRS MTF is Gaussian. It is the honest default when the reference's PSF is
unknown, and a knob when it is known.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import ndimage

__all__ = ["degrade_to_gsd", "block_mean", "psf_sigma_fine_px"]

_FWHM_TO_SIGMA = 1.0 / (2.0 * np.sqrt(2.0 * np.log(2.0)))


def psf_sigma_fine_px(k: int, psf_fwhm_coarse_px: float) -> float:
    """Gaussian sigma in FINE pixels for a PSF of the given FWHM in COARSE pixels."""
    if k < 1:
        raise ValueError("k must be >= 1")
    if psf_fwhm_coarse_px < 0:
        raise ValueError("psf_fwhm_coarse_px must be >= 0")
    return float(psf_fwhm_coarse_px * k * _FWHM_TO_SIGMA)


def block_mean(image: ArrayLike, k: int) -> NDArray[np.float64]:
    """NaN-aware k x k block mean; trailing rows/columns that do not fill a
    block are dropped, as in every recorded run."""
    a = np.asarray(image, dtype=np.float64)
    if a.ndim != 2:
        raise ValueError("expected a 2-D image")
    if k < 1:
        raise ValueError("k must be >= 1")
    if k == 1:
        return a.copy()
    a = a[: a.shape[0] // k * k, : a.shape[1] // k * k]
    if a.size == 0:
        raise ValueError(f"image {np.asarray(image).shape} is smaller than one {k}x{k} block")
    with np.errstate(invalid="ignore"):
        return np.nanmean(a.reshape(a.shape[0] // k, k, a.shape[1] // k, k), axis=(1, 3))


def degrade_to_gsd(image: ArrayLike, k: int, *, psf_fwhm_coarse_px: float = 1.0,
                   truncate: float = 4.0) -> NDArray[np.float64]:
    """Degrade ``image`` by an integer factor ``k`` through a Gaussian PSF then a
    block mean. ``psf_fwhm_coarse_px = 0`` reproduces the recorded box average."""
    a = np.asarray(image, dtype=np.float64)
    if a.ndim != 2:
        raise ValueError("expected a 2-D image")
    sigma = psf_sigma_fine_px(k, psf_fwhm_coarse_px)
    if sigma > 0:
        valid = np.isfinite(a)
        filled = np.where(valid, a, 0.0)
        num = ndimage.gaussian_filter(filled, sigma=sigma, mode="nearest", truncate=truncate)
        den = ndimage.gaussian_filter(valid.astype(np.float64), sigma=sigma, mode="nearest",
                                      truncate=truncate)
        with np.errstate(invalid="ignore", divide="ignore"):
            a = np.where(den > 1e-6, num / den, np.nan)
        a = np.where(valid, a, np.nan)
    return block_mean(a, k)
