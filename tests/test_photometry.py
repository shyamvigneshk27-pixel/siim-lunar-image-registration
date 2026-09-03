"""Photometric normalisation (sources.md S10).

The tests worth reading first are the physical ones: that a scene rendered
under two different Suns becomes *more* similar after correction
(``test_correction_reduces_disagreement_between_two_illuminations``), and that
the module refuses the two things it must never do quietly -- correct a thermal
band, or invent a value for a shadow.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from siim.preprocessing import (
    PhotometricCorrection,
    PhotometricModel,
    ReflectanceDomainError,
    hapke_hg,
    lambert,
    lommel_seeliger,
    normalise,
    reflectance_domain_bands,
)
from siim.preprocessing.photometry import STANDARD_GEOMETRY

ALL_MODELS = list(PhotometricModel)


# --------------------------------------------------------------------------
# the photometric functions themselves
# --------------------------------------------------------------------------


@pytest.mark.parametrize("model", ALL_MODELS)
def test_every_model_is_positive_and_finite_in_the_normal_regime(model):
    from siim.preprocessing.photometry import _MODELS

    inc = np.linspace(0.0, 80.0, 17)
    f = np.asarray(_MODELS[model](inc, 0.0, inc))
    assert np.isfinite(f).all()
    assert (f > 0).all()


@pytest.mark.parametrize("model", ALL_MODELS)
def test_every_model_decreases_as_the_sun_gets_lower(model):
    """More oblique illumination must not brighten the surface."""
    from siim.preprocessing.photometry import _MODELS

    inc = np.linspace(0.0, 85.0, 20)
    f = np.asarray(_MODELS[model](inc, 0.0, inc))
    assert np.all(np.diff(f) <= 1e-12), f"{model.value} is not monotone in incidence"


def test_lambert_is_exactly_cos_i():
    assert lambert(60.0, 0.0, 60.0) == pytest.approx(0.5)
    assert lambert(0.0, 0.0, 0.0) == pytest.approx(1.0)


def test_lommel_seeliger_is_one_half_at_nadir_view_and_nadir_sun():
    """mu0 = mu = 1 gives 1/2 exactly -- a value that pins the formula."""
    assert lommel_seeliger(0.0, 0.0, 0.0) == pytest.approx(0.5)


def test_lommel_seeliger_falls_off_more_slowly_than_lambert():
    """The physical point of using it: dark regolith is not Lambertian.

    Normalised to their nadir values, Lommel-Seeliger must retain more signal
    at high incidence than Lambert -- which is why the Moon's limb does not
    darken the way a Lambertian sphere's would.
    """
    inc = 70.0
    ls = lommel_seeliger(inc, 0.0, inc) / lommel_seeliger(0.0, 0.0, 0.0)
    lam = lambert(inc, 0.0, inc) / lambert(0.0, 0.0, 0.0)
    assert ls > lam


def test_hapke_opposition_surge_brightens_towards_zero_phase():
    """The surge is the reason a full Moon is disproportionately bright."""
    near = hapke_hg(5.0, 0.0, 5.0)
    far = hapke_hg(5.0, 0.0, 60.0)
    assert near > far


def test_hapke_single_scattering_albedo_scales_brightness():
    assert hapke_hg(30.0, 0.0, 30.0, w=0.5) > hapke_hg(30.0, 0.0, 30.0, w=0.2)


# --------------------------------------------------------------------------
# the physical claim: correction makes two illuminations comparable
# --------------------------------------------------------------------------


@pytest.mark.parametrize("model", ALL_MODELS)
def test_correction_reduces_disagreement_between_two_illuminations(model, terrain):
    """A scene under two Suns must agree better after correction than before.

    This is the whole argument for the stage. The same reflectance field is
    rendered at incidence 20° and 55°; correcting both to the standard geometry
    must bring them closer together. If it does not, the correction is not
    doing its job and no downstream illumination result is interpretable.
    """
    from siim.preprocessing.photometry import _MODELS

    reflectance = terrain
    i_a, i_b = 20.0, 55.0
    fn = _MODELS[model]
    obs_a = reflectance * float(np.asarray(fn(i_a, 0.0, i_a)))
    obs_b = reflectance * float(np.asarray(fn(i_b, 0.0, i_b)))

    before = float(np.mean(np.abs(obs_a - obs_b)))

    ca, va, _ = normalise(obs_a, incidence_deg=i_a, emission_deg=0.0, model=model)
    cb, vb, _ = normalise(obs_b, incidence_deg=i_b, emission_deg=0.0, model=model)
    both = va & vb
    after = float(np.mean(np.abs(ca[both] - cb[both])))

    assert after < before
    # For a uniform-albedo scene the correction is exact up to float error.
    assert after < 1e-9, f"{model.value} left residual {after:.3e}"


def test_correction_is_identity_at_the_standard_geometry(terrain):
    """Correcting an image already at standard geometry must change nothing."""
    out, valid, rec = normalise(
        terrain,
        incidence_deg=STANDARD_GEOMETRY["incidence_deg"],
        emission_deg=STANDARD_GEOMETRY["emission_deg"],
        phase_deg=STANDARD_GEOMETRY["phase_deg"],
    )
    assert valid.all()
    np.testing.assert_allclose(out, terrain, rtol=1e-12)
    assert rec.factor_median == pytest.approx(1.0)


# --------------------------------------------------------------------------
# the two refusals
# --------------------------------------------------------------------------


def test_thermal_bands_are_refused_not_corrected():
    """IIRS beyond ~3 um is not reflected sunlight.

    Applying a reflectance model there produces a physically meaningless
    number that looks exactly like a valid one, so it must raise.
    """
    img = np.ones((4, 4))
    with pytest.raises(ReflectanceDomainError, match="thermal-emission dominated"):
        normalise(
            img,
            incidence_deg=30.0,
            emission_deg=0.0,
            wavelengths_um=[1.2, 2.4, 4.6],
        )


def test_reflectance_bands_of_the_iirs_range_are_selected_correctly():
    wl = np.array([0.8, 1.5, 2.9, 3.1, 5.0])
    ok = reflectance_domain_bands(wl)
    assert ok.tolist() == [True, True, True, False, False]


def test_shadowed_pixels_are_masked_not_filled(terrain):
    """Incidence >= 90 deg means no illuminated facet. There is nothing to scale."""
    inc = np.full(terrain.shape, 40.0)
    inc[:64, :] = 95.0
    out, valid, rec = normalise(terrain, incidence_deg=inc, emission_deg=0.0)
    assert not valid[:64, :].any()
    assert np.isnan(out[:64, :]).all()
    assert valid[64:, :].all()
    assert rec.invalid_fraction == pytest.approx(0.25, abs=0.01)
    assert any("self-shadowed" in n for n in rec.notes)


def test_vanishing_photometric_factor_is_masked_not_divided_by(terrain):
    """Dividing by a near-zero f manufactures speckle a detector will match on."""
    # cos(89.999 deg) ~ 1.7e-5, well below the 1e-3 floor. Emission stays at
    # nadir so this exercises the min_factor path and not the phase guard.
    out, valid, rec = normalise(
        terrain, incidence_deg=89.999, emission_deg=0.0, model=PhotometricModel.LAMBERT
    )
    assert rec.invalid_fraction == pytest.approx(1.0)
    assert np.isnan(out).all()
    assert not valid.any()


def test_missing_angles_are_refused(terrain):
    with pytest.raises(ValueError, match="never a default"):
        normalise(terrain, incidence_deg=np.nan, emission_deg=0.0)


def test_nadir_phase_approximation_is_refused_when_viewing_is_oblique(terrain):
    """g = i only holds near nadir. Off-nadir must supply phase explicitly."""
    with pytest.raises(ValueError, match="supply phase_deg explicitly"):
        normalise(terrain, incidence_deg=30.0, emission_deg=25.0)


def test_nadir_phase_approximation_is_allowed_but_recorded(terrain):
    """Every frame this project has used is within 1.75 deg of nadir."""
    _, _, rec = normalise(terrain, incidence_deg=30.0, emission_deg=1.75)
    assert any("g = i" in n for n in rec.notes)


# --------------------------------------------------------------------------
# the artefact -- correction is never silent
# --------------------------------------------------------------------------


def test_correction_record_is_returned_and_serialisable(terrain):
    _, _, rec = normalise(terrain, incidence_deg=45.0, emission_deg=0.0)
    assert isinstance(rec, PhotometricCorrection)
    d = rec.to_dict()
    json.dumps(d)
    assert d["model"] == "lommel_seeliger"
    assert d["standard_geometry"] == STANDARD_GEOMETRY


def test_hapke_records_that_its_parameters_are_defaults_not_fits(terrain):
    """The circularity guard: assumed parameters must travel with the number."""
    _, _, rec = normalise(
        terrain, incidence_deg=45.0, emission_deg=0.0, model=PhotometricModel.HAPKE_HG
    )
    assert any("NOT fitted" in n for n in rec.notes)
    assert any("roughness" in n for n in rec.notes)
    assert set(rec.parameters) >= {"w", "b", "b0", "h"}


def test_hapke_roughness_caveat_names_the_regime_it_matters_in(terrain):
    """Frames B and C sit near 70 deg incidence, where the omission is not small."""
    _, _, rec = normalise(
        terrain, incidence_deg=70.0, emission_deg=0.0, model=PhotometricModel.HAPKE_HG
    )
    assert any("high incidence" in n for n in rec.notes)


def test_non_2d_input_is_refused():
    with pytest.raises(ValueError, match="must be 2-D"):
        normalise(np.ones((3, 3, 3)), incidence_deg=30.0, emission_deg=0.0)
