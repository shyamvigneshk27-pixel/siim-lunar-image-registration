"""Illumination-robust image representations (EXP-003).

The hypothesis under test (ADR-0004, `PROPOSED`) is that classical matching
fails on Sun-azimuth change because SIFT bins gradient orientation over
``[0, 2*pi)``, and that a representation which does not carry gradient
*polarity* -- or which encodes local structure by phase rather than by
intensity contrast -- survives further.

A *representation* here is a map from an intensity image to another image on
which the ordinary detection/description pipeline is then run. Keeping it that
shape is deliberate: everything downstream (matching, RANSAC, scoring) stays
byte-identical across arms, so a difference in outcome is attributable to the
representation and not to the protocol.

Nothing in this module consults ground truth.

Phase congruency
----------------
Implements the classical 2-D formulation (Kovesi): a bank of log-Gabor filters
over ``n_scale`` scales and ``n_orient`` orientations, from which a
contrast-invariant measure of local phase alignment is computed.

Phase congruency is invariant to local contrast **magnitude** by construction:
it is a ratio of aligned energy to total amplitude, so multiplying the image by
a constant leaves it unchanged. That is a stronger invariance than gain/bias
normalisation and is the reason it is the standard first move in multi-modal
remote-sensing registration.

**What it does not give you, stated up front.** Phase congruency is *not*
invariant to a change in illumination *direction*. Shadow movement changes
which structures exist in the image, not merely their contrast. EXP-003
measures how much of the gap that leaves.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = [
    "to_float",
    "identity_representation",
    "gradient_magnitude_representation",
    "PhaseCongruency",
    "phase_congruency",
    "maximum_index_map",
]

_EPS = 1e-9


def to_float(image: ArrayLike) -> NDArray[np.float64]:
    """Finite float image, NaN-filled with the finite mean.

    ``warp`` fills outside-footprint regions with NaN by contract C4/E-003.
    Representations built on FFTs cannot carry NaN, so it is replaced by the
    finite mean -- a neutral value that adds no gradient structure. The
    alternative, zero-fill, is exactly the domain hazard E-003 rejected: on the
    Moon a zero region is indistinguishable from real shadow.
    """
    img = np.asarray(image, dtype=np.float64)
    finite = np.isfinite(img)
    if not finite.any():
        return np.zeros(img.shape, dtype=np.float64)
    if not finite.all():
        img = np.where(finite, img, float(img[finite].mean()))
    return img


def identity_representation(image: ArrayLike) -> NDArray[np.float64]:
    """The raw intensity image. The control arm."""
    return to_float(image)


def gradient_magnitude_representation(image: ArrayLike) -> NDArray[np.float64]:
    """``|grad I|`` -- invariant to a global sign flip of the image.

    Recorded as the cheapest possible polarity-agnostic representation. Note
    what it is *not*: invariant to illumination *direction*. Under azimuth
    rotation the gradient field rotates, and its magnitude changes with it.
    """
    img = to_float(image)
    gy, gx = np.gradient(img)
    return np.hypot(gx, gy)


class PhaseCongruency:
    """Phase congruency map plus the per-orientation amplitudes behind it.

    Attributes
    ----------
    pc
        (H, W) phase congruency in [0, 1]. Contrast-invariant.
    orientation_amplitude
        (n_orient, H, W) log-Gabor amplitude summed over scales, per
        orientation. This is what the RIFT-style maximum-index map is built
        from, so it is returned rather than recomputed.
    """

    __slots__ = ("pc", "orientation_amplitude")

    def __init__(self, pc: NDArray[np.float64], amp: NDArray[np.float64]) -> None:
        self.pc = pc
        self.orientation_amplitude = amp


def _log_gabor_bank(
    shape: tuple[int, int],
    n_scale: int,
    n_orient: int,
    min_wavelength: float,
    mult: float,
    sigma_on_f: float,
    d_theta_on_sigma: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Radial log-Gabor terms and angular spreads, in the frequency domain."""
    rows, cols = shape

    # Frequency grid, normalised so the Nyquist radius is 0.5.
    fy = np.fft.ifftshift((np.arange(rows) - rows // 2) / rows)
    fx = np.fft.ifftshift((np.arange(cols) - cols // 2) / cols)
    fxg, fyg = np.meshgrid(fx, fy)
    radius = np.sqrt(fxg**2 + fyg**2)
    radius[0, 0] = 1.0  # avoid log(0); the DC term is zeroed below

    theta = np.arctan2(-fyg, fxg)
    sin_t, cos_t = np.sin(theta), np.cos(theta)

    # Low-pass Butterworth to suppress the corners of the frequency square.
    lp = 1.0 / (1.0 + (radius / 0.45) ** (2 * 15))

    log_gabor = np.empty((n_scale, rows, cols))
    for s in range(n_scale):
        wavelength = min_wavelength * (mult**s)
        f0 = 1.0 / wavelength
        lg = np.exp(-((np.log(radius / f0)) ** 2) / (2 * np.log(sigma_on_f) ** 2))
        lg *= lp
        lg[0, 0] = 0.0
        log_gabor[s] = lg

    theta_sigma = np.pi / n_orient / d_theta_on_sigma
    spread = np.empty((n_orient, rows, cols))
    for o in range(n_orient):
        angl = o * np.pi / n_orient
        # Angular distance, computed via sin/cos so it wraps correctly.
        ds = sin_t * np.cos(angl) - cos_t * np.sin(angl)
        dc = cos_t * np.cos(angl) + sin_t * np.sin(angl)
        d_theta = np.abs(np.arctan2(ds, dc))
        spread[o] = np.exp(-(d_theta**2) / (2 * theta_sigma**2))

    return log_gabor, spread


def phase_congruency(
    image: ArrayLike,
    *,
    n_scale: int = 4,
    n_orient: int = 6,
    min_wavelength: float = 3.0,
    mult: float = 2.1,
    sigma_on_f: float = 0.55,
    k_noise: float = 2.0,
    cut_off: float = 0.5,
    g: float = 10.0,
    d_theta_on_sigma: float = 1.2,
) -> PhaseCongruency:
    """Phase congruency and the per-orientation amplitudes it is built from.

    Parameters follow the conventional defaults for this filter bank. They are
    **not tuned on EXP-003 data**: tuning one arm on information the other arms
    do not get would break the fair-comparison requirement.
    """
    img = to_float(image)
    rows, cols = img.shape
    fft_img = np.fft.fft2(img)

    log_gabor, spread = _log_gabor_bank(
        (rows, cols), n_scale, n_orient, min_wavelength, mult, sigma_on_f, d_theta_on_sigma
    )

    pc_sum = np.zeros((rows, cols))
    amp_per_orient = np.zeros((n_orient, rows, cols))

    for o in range(n_orient):
        sum_e = np.zeros((rows, cols))
        sum_o = np.zeros((rows, cols))
        sum_an = np.zeros((rows, cols))
        responses = []

        for s in range(n_scale):
            filt = log_gabor[s] * spread[o]
            resp = np.fft.ifft2(fft_img * filt)
            responses.append(resp)
            sum_e += resp.real
            sum_o += resp.imag
            sum_an += np.abs(resp)

            if s == 0:
                # Noise floor from the smallest scale, via the Rayleigh median.
                median_an = np.median(np.abs(resp))
                mean_an = median_an / np.sqrt(np.log(4.0)) if median_an > 0 else 0.0
                sigma_noise = mean_an * np.sqrt((4 - np.pi) / np.pi) if mean_an else 0.0
                noise_t = mean_an * np.sqrt(np.pi / 2.0) + k_noise * sigma_noise

        amp_per_orient[o] = sum_an

        x_energy = np.sqrt(sum_e**2 + sum_o**2) + _EPS
        mean_e = sum_e / x_energy
        mean_o = sum_o / x_energy

        energy = np.zeros((rows, cols))
        for resp in responses:
            energy += resp.real * mean_e + resp.imag * mean_o
            energy -= np.abs(resp.real * mean_o - resp.imag * mean_e)

        energy = np.maximum(energy - noise_t, 0.0)

        # Frequency-spread weighting: penalise responses from a single scale,
        # which are not evidence of a real feature.
        width = (sum_an / (np.max(np.abs(np.stack([r for r in responses])), axis=0) + _EPS)
                 - 1.0) / (n_scale - 1)
        weight = 1.0 / (1.0 + np.exp(g * (cut_off - width)))

        pc_sum += weight * energy / (sum_an + _EPS)

    pc = pc_sum / n_orient
    pc = np.clip(np.nan_to_num(pc), 0.0, 1.0)
    return PhaseCongruency(pc, amp_per_orient)


def maximum_index_map(amplitudes: NDArray[np.float64]) -> NDArray[np.int32]:
    """RIFT's maximum index map: which orientation responds most, per pixel.

    The index of the strongest log-Gabor orientation channel carries local
    structure while discarding its amplitude, so it is invariant to contrast
    and -- unlike a gradient-orientation histogram over ``[0, 2*pi)`` -- it is
    built from an orientation basis that is already defined mod pi.
    """
    return np.argmax(amplitudes, axis=0).astype(np.int32)
