"""Photometric normalisation: divide the Sun out instead of tolerating it.

Why this module is the one that was missing
-------------------------------------------
This project measured an illumination failure threshold -- successes at
Δincidence 0.96° and 11.73°, failures from 38.85° -- using a pipeline with **no
photometric correction at all**. That makes the threshold a property of
uncorrected RootSIFT, not of the Moon, and it is the first thing a planetary
reviewer will say. Planetary photogrammetry does not fight illumination with
descriptors; it removes illumination before matching, because the illumination
geometry is *known* from ephemeris (sources.md S10).

The governing identity is that observed radiance factors into surface
reflectance and a photometric function of the illumination and viewing
geometry:

    observed(x) = reflectance(x) * f(i(x), e(x), g(x))

All three angles are computable per pixel from the archive's sub-solar point
and the spacecraft geometry, so ``f`` is not a nuisance to be tolerated. It is
a term to be divided out. Normalising to a fixed standard geometry then makes
two images of the same ground directly comparable:

    corrected = observed * f(standard) / f(observed)

Three models, and why all three are here
----------------------------------------
=================  =========================================================
 ``LAMBERT``        ``f = mu0``. The naive choice, and the one a pipeline
                    applies implicitly by doing nothing thoughtful. Included
                    as the **control**: a claim that a better model helps is
                    only meaningful against the model it replaces.
 ``LOMMEL_SEELIGER`` ``f = mu0 / (mu0 + mu)``. Parameter-free, and much closer
                    to real regolith than Lambert -- the Moon is a
                    single-scattering-dominated, dark, porous surface. This is
                    the transparent default: nothing to tune means nothing to
                    tune *on the test set*.
 ``HAPKE_HG``       Hapke's bidirectional reflectance with a single-term
                    Henyey-Greenstein phase function, Chandrasekhar
                    multiple-scattering H-functions and an opposition surge.
                    The model established practice uses above ~60° incidence
                    (S10).
=================  =========================================================

What this implementation does NOT do, stated up front
-----------------------------------------------------
**Macroscopic roughness is not modelled.** Hapke's shadowing function ``S`` for
sub-resolution topography is omitted. Its effect grows with incidence angle, so
the model is *least* trustworthy exactly where this project's failures live --
frames B and C sit near 70° incidence. Any result obtained here at high
incidence must carry that caveat; it is not a small residual term in that
regime. Implementing ``S`` requires a mean-slope parameter that would have to
be fitted, and fitting it on these frames would make the correction circular.

**Cast shadows are not corrected, and are not correctable here.** A photometric
model describes diffuse shading on an illuminated facet. A shadow is a
geometric occlusion: there is no signal to rescale, and dividing by a small
``f`` there amplifies noise without bound. The module therefore emits a
**shadow mask** and refuses to claim correction inside it, rather than
returning plausible-looking numbers for pixels that carry none.

**Hapke parameters are literature defaults, not fits.** They are recorded in
the returned artefact so a reader can see exactly what was assumed. Tuning them
on the pairs being tested would be the circularity ADR-0003 exists to prevent.

Instrument-conditionality
-------------------------
A reflectance-domain correction assumes the signal *is* reflected sunlight.
For Chandrayaan-2 IIRS that is false beyond roughly 3 µm, where thermal
emission dominates and depends on surface temperature rather than instantaneous
solar geometry (sources.md S1, S10). :func:`reflectance_domain_bands` gates
that, and :func:`normalise` raises rather than silently producing a physically
meaningless result. OHRC, TMC-2 and LRO NAC are panchromatic reflectance
instruments and need no such gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = [
    "PhotometricModel",
    "PhotometricCorrection",
    "ReflectanceDomainError",
    "STANDARD_GEOMETRY",
    "HAPKE_DEFAULTS",
    "lambert",
    "lommel_seeliger",
    "hapke_hg",
    "reflectance_domain_bands",
    "normalise",
]


class PhotometricModel(Enum):
    LAMBERT = "lambert"
    LOMMEL_SEELIGER = "lommel_seeliger"
    HAPKE_HG = "hapke_hg"


#: The community standard geometry: incidence 60°, emission 0°, phase 60°
#: (sources.md S10, Sato et al. 2014). Chosen so outputs compare against
#: published lunar photometric work rather than an internal convention.
#: Note e = 0 and i = g = 60 is self-consistent: with nadir viewing the phase
#: angle equals the incidence angle.
STANDARD_GEOMETRY = {"incidence_deg": 60.0, "emission_deg": 0.0, "phase_deg": 60.0}

#: Literature-typical lunar Hapke parameters. **Defaults, not fits.** Recorded
#: in every correction artefact so the assumption travels with the number.
HAPKE_DEFAULTS = {
    "w": 0.33,      # single-scattering albedo, mare-to-highland typical
    "b": 0.21,      # Henyey-Greenstein asymmetry; positive = backscattering
    "b0": 1.0,      # opposition surge amplitude
    "h": 0.07,      # opposition surge angular width
}

#: Beyond this wavelength the lunar daytime signal is thermal-emission
#: dominated and a reflectance model does not apply (S1, S10).
THERMAL_ONSET_UM = 3.0


class ReflectanceDomainError(ValueError):
    """Raised when a reflectance model is applied outside its physical domain."""


def _cos(deg: ArrayLike) -> NDArray[np.float64]:
    return np.cos(np.deg2rad(np.asarray(deg, dtype=np.float64)))


# --------------------------------------------------------------------------
# the three photometric functions
# --------------------------------------------------------------------------


def lambert(incidence_deg: ArrayLike, emission_deg: ArrayLike, phase_deg: ArrayLike):
    """``f = cos(i)``. The naive model, present as the control.

    Emission and phase are accepted and ignored, so all three models share one
    signature and a caller cannot pass the wrong one by accident.
    """
    del emission_deg, phase_deg
    return np.clip(_cos(incidence_deg), 0.0, None)


def lommel_seeliger(incidence_deg: ArrayLike, emission_deg: ArrayLike, phase_deg: ArrayLike):
    """``f = mu0 / (mu0 + mu)``. Parameter-free, and right for dark regolith.

    Singular only where both cosines vanish, i.e. grazing illumination *and*
    grazing view; that region is masked by the caller rather than fudged with
    an epsilon that would quietly invent a value.
    """
    del phase_deg
    mu0 = np.clip(_cos(incidence_deg), 0.0, None)
    mu = np.clip(_cos(emission_deg), 0.0, None)
    denom = mu0 + mu
    return np.divide(mu0, denom, out=np.zeros_like(mu0 + mu), where=denom > 0)


def _h_function(x: NDArray[np.float64], w: float) -> NDArray[np.float64]:
    """Hapke's 2002 analytic approximation to the Chandrasekhar H-function."""
    gamma = np.sqrt(1.0 - w)
    r0 = (1.0 - gamma) / (1.0 + gamma)
    safe = np.clip(x, 1e-9, None)
    inner = r0 + (1.0 - 2.0 * r0 * safe) / 2.0 * np.log((1.0 + safe) / safe)
    return 1.0 / np.clip(1.0 - w * safe * inner, 1e-9, None)


def hapke_hg(
    incidence_deg: ArrayLike,
    emission_deg: ArrayLike,
    phase_deg: ArrayLike,
    *,
    w: float = HAPKE_DEFAULTS["w"],
    b: float = HAPKE_DEFAULTS["b"],
    b0: float = HAPKE_DEFAULTS["b0"],
    h: float = HAPKE_DEFAULTS["h"],
):
    """Hapke bidirectional reflectance, single-term Henyey-Greenstein.

    ``f = (w/4pi) * mu0/(mu0+mu) * [(1 + B(g)) p(g) + H(mu0)H(mu) - 1]``

    with ``p(g) = (1-b^2) / (1 + 2b cos g + b^2)^{3/2}`` and opposition surge
    ``B(g) = b0 / (1 + tan(g/2)/h)``.

    **Roughness is not modelled** -- see the module docstring. At the near-nadir
    emission of every frame this project has used, and at moderate incidence,
    the omission is second-order; at the ~70° incidence of frames B and C it is
    not, and results there must say so.
    """
    mu0 = np.clip(_cos(incidence_deg), 0.0, None)
    mu = np.clip(_cos(emission_deg), 0.0, None)
    g = np.deg2rad(np.asarray(phase_deg, dtype=np.float64))

    cos_g = np.cos(g)
    p = (1.0 - b**2) / np.clip((1.0 + 2.0 * b * cos_g + b**2) ** 1.5, 1e-12, None)
    surge = b0 / (1.0 + np.tan(np.clip(g, 0.0, np.pi - 1e-9) / 2.0) / h)

    denom = mu0 + mu
    ls = np.divide(mu0, denom, out=np.zeros_like(mu0 + mu), where=denom > 0)
    multi = _h_function(mu0, w) * _h_function(mu, w) - 1.0
    return (w / (4.0 * np.pi)) * ls * ((1.0 + surge) * p + multi)


_MODELS = {
    PhotometricModel.LAMBERT: lambert,
    PhotometricModel.LOMMEL_SEELIGER: lommel_seeliger,
    PhotometricModel.HAPKE_HG: hapke_hg,
}


# --------------------------------------------------------------------------
# instrument-conditional gate
# --------------------------------------------------------------------------


def reflectance_domain_bands(wavelengths_um: ArrayLike) -> NDArray[np.bool_]:
    """Which bands are reflected-sunlight dominated, and so correctable here.

    Chandrayaan-2 IIRS spans 0.8-5.0 µm; beyond ~3 µm the daytime lunar signal
    is thermal-emission dominated and depends on surface temperature, not on
    instantaneous solar geometry. Established practice estimates the thermal
    component in the 4-5 µm region and removes it from the shorter bands --
    that separation is a prerequisite for this module, not a part of it.
    """
    wl = np.asarray(wavelengths_um, dtype=np.float64)
    if not np.isfinite(wl).all() or (wl <= 0).any():
        raise ValueError("wavelengths must be finite and positive, in micrometres")
    return wl < THERMAL_ONSET_UM


# --------------------------------------------------------------------------
# the correction record -- never silent
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PhotometricCorrection:
    """What was applied, to how much of the image, and what was refused.

    Returned alongside every corrected image. Photometric correction is a
    pipeline stage with its own artefact, not preprocessing folded into a
    loader: an unrecorded normalisation makes every downstream number
    uninterpretable, which is D-005's lesson restated.
    """

    model: PhotometricModel
    parameters: dict[str, float]
    standard_geometry: dict[str, float]
    #: Pixels excluded: self-shadowed, grazing, or where ``f`` is too small to
    #: divide by without amplifying noise without bound.
    invalid_fraction: float
    #: Multiplicative factor statistics over the valid region.
    factor_min: float
    factor_median: float
    factor_max: float
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model.value,
            "parameters": dict(self.parameters),
            "standard_geometry": dict(self.standard_geometry),
            "invalid_fraction": self.invalid_fraction,
            "factor_min": self.factor_min,
            "factor_median": self.factor_median,
            "factor_max": self.factor_max,
            "notes": list(self.notes),
        }


def normalise(
    image: ArrayLike,
    *,
    incidence_deg: ArrayLike,
    emission_deg: ArrayLike,
    phase_deg: ArrayLike | None = None,
    model: PhotometricModel = PhotometricModel.LOMMEL_SEELIGER,
    standard: dict[str, float] | None = None,
    wavelengths_um: ArrayLike | None = None,
    min_factor: float = 1e-3,
    **model_kwargs: float,
) -> tuple[NDArray[np.float64], NDArray[np.bool_], PhotometricCorrection]:
    """Normalise ``image`` to a standard illumination geometry.

    Returns ``(corrected, valid_mask, record)``. Invalid pixels are ``NaN`` in
    ``corrected``, following the geometry layer's convention that unusable
    regions must be unmistakable rather than plausible (contract C5).

    Parameters
    ----------
    incidence_deg, emission_deg
        Scalar or per-pixel. **Required.** There is no default: defaulting a
        missing angle is how a pipeline acquires a silent tens-of-pixels error,
        which this project has survived once already (E-005).
    phase_deg
        Scalar or per-pixel. Optional only because it is exactly recoverable at
        nadir viewing, where ``g = i``; that substitution is recorded in the
        returned notes rather than made quietly. Every frame this project has
        used is near-nadir (emission <= 1.75°), so the approximation is
        justified here and would not be elsewhere.
    wavelengths_um
        When given, every band must be reflected-sunlight dominated or the call
        raises. Pass it for IIRS; omit it for panchromatic instruments.
    min_factor
        Pixels whose photometric function falls below this are masked instead
        of divided by. Dividing by a vanishing ``f`` amplifies noise without
        bound and manufactures bright speckle that a detector will happily
        treat as texture.
    """
    img = np.asarray(image, dtype=np.float64)
    if img.ndim != 2:
        raise ValueError(f"image must be 2-D; got shape {img.shape}")

    if wavelengths_um is not None:
        ok = reflectance_domain_bands(wavelengths_um)
        if not ok.all():
            bad = np.asarray(wavelengths_um, dtype=np.float64)[~ok]
            raise ReflectanceDomainError(
                f"{(~ok).sum()} band(s) at or beyond {THERMAL_ONSET_UM} um "
                f"(e.g. {bad[0]:.2f} um) are thermal-emission dominated. A "
                "reflectance photometric model does not apply there. Separate "
                "the thermal component first (sources.md S10)."
            )

    inc = np.asarray(incidence_deg, dtype=np.float64)
    emi = np.asarray(emission_deg, dtype=np.float64)
    if not (np.isfinite(inc).all() and np.isfinite(emi).all()):
        raise ValueError(
            "incidence and emission must be finite everywhere; a missing angle "
            "is a refusal, never a default"
        )

    notes: list[str] = []
    if phase_deg is None:
        max_emission = float(np.max(np.abs(emi)))
        if max_emission > 5.0:
            raise ValueError(
                f"phase_deg omitted but emission reaches {max_emission:.2f} deg. "
                "The nadir approximation g = i is only defensible near nadir; "
                "supply phase_deg explicitly."
            )
        pha = inc
        notes.append(
            f"phase not supplied; used g = i, valid at near-nadir viewing "
            f"(max emission {max_emission:.2f} deg)"
        )
    else:
        pha = np.asarray(phase_deg, dtype=np.float64)
        if not np.isfinite(pha).all():
            raise ValueError("phase must be finite everywhere")

    std = dict(STANDARD_GEOMETRY if standard is None else standard)
    fn = _MODELS[model]

    f_obs = np.asarray(fn(inc, emi, pha, **model_kwargs), dtype=np.float64)
    f_std = float(
        np.asarray(
            fn(std["incidence_deg"], std["emission_deg"], std["phase_deg"], **model_kwargs)
        )
    )
    if not np.isfinite(f_std) or f_std <= 0:
        raise ValueError(f"standard geometry gives a non-positive factor for {model.value}")

    f_obs = np.broadcast_to(f_obs, img.shape)
    valid = np.isfinite(img) & np.isfinite(f_obs) & (f_obs >= min_factor)

    # Self-shadowed facets carry no reflected signal to rescale.
    shadowed = np.broadcast_to(np.asarray(inc, dtype=np.float64), img.shape) >= 90.0
    valid &= ~shadowed
    if shadowed.any():
        notes.append(
            f"{100.0 * shadowed.mean():.2f}% of pixels are self-shadowed "
            "(incidence >= 90 deg) and are masked, not corrected"
        )

    factor = np.full(img.shape, np.nan)
    np.divide(f_std, f_obs, out=factor, where=valid)

    corrected = np.full(img.shape, np.nan)
    np.multiply(img, factor, out=corrected, where=valid)

    if model is PhotometricModel.HAPKE_HG:
        notes.append(
            "Hapke parameters are literature defaults, NOT fitted to this data"
        )
        notes.append(
            "macroscopic roughness (Hapke's S) is not modelled; the model is "
            "least reliable at high incidence, which is where this project's "
            "registration failures occur"
        )

    fv = factor[valid]
    return (
        corrected,
        valid,
        PhotometricCorrection(
            model=model,
            parameters=(
                {**HAPKE_DEFAULTS, **model_kwargs}
                if model is PhotometricModel.HAPKE_HG
                else dict(model_kwargs)
            ),
            standard_geometry=std,
            invalid_fraction=float(1.0 - valid.mean()),
            factor_min=float(fv.min()) if fv.size else float("nan"),
            factor_median=float(np.median(fv)) if fv.size else float("nan"),
            factor_max=float(fv.max()) if fv.size else float("nan"),
            notes=tuple(notes),
        ),
    )
