"""Property tests for the EXP-003 representations and descriptors.

These pin the two claims the EXP-003 hypotheses actually rest on:

* phase congruency is invariant to contrast **and to polarity**, by construction;
* a gradient-orientation histogram binned over ``[0, pi)`` is invariant to a
  polarity flip while the otherwise-identical ``[0, 2*pi)`` descriptor is not.

The second pair is the mechanism behind H-3.4. If the mod-pi descriptor did not
actually collapse polarity, the whole arm would be measuring nothing, and a
null result would be uninterpretable. These tests exist so that a null result
can be read as evidence about the *hypothesis* rather than about the code.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import ndimage

from siim.matching.descriptors import (
    describe_gradient_histogram,
    describe_maximum_index,
)
from siim.matching.representations import (
    gradient_magnitude_representation,
    identity_representation,
    maximum_index_map,
    phase_congruency,
    to_float,
)


@pytest.fixture
def step_image() -> np.ndarray:
    img = np.zeros((96, 96))
    img[:, 48:] = 1.0
    img[20:28, :] = 0.5
    return img


# ---------------------------------------------------------------------------
# representations
# ---------------------------------------------------------------------------

def test_to_float_replaces_nan_with_the_finite_mean_not_zero(step_image):
    """E-003: on the Moon a zero region is indistinguishable from real shadow.

    Filling invalid regions with 0.0 would inject a fake dark patch with real
    gradient structure at its border. The finite mean adds no such structure.
    """
    img = step_image.copy()
    img[0:5, 0:5] = np.nan
    out = to_float(img)
    assert np.isfinite(out).all()
    assert out[0, 0] == pytest.approx(np.nanmean(img))
    assert out[0, 0] != 0.0


def test_phase_congruency_is_invariant_to_contrast(step_image):
    """The defining property: PC is a ratio, so affine intensity change cancels."""
    base = phase_congruency(step_image).pc
    scaled = phase_congruency(3.0 * step_image + 0.7).pc
    assert np.abs(scaled - base).max() < 1e-4


def test_phase_congruency_is_invariant_to_polarity(step_image):
    """Negating the image leaves PC exactly unchanged.

    This is the property that makes PC a candidate for Sun-azimuth robustness:
    unlike a gradient-orientation histogram, it does not encode which side of
    an edge is bright.
    """
    base = phase_congruency(step_image).pc
    flipped = phase_congruency(-step_image).pc
    assert np.abs(flipped - base).max() < 1e-9


def test_phase_congruency_responds_to_edges_not_to_flat_regions(step_image):
    pc = phase_congruency(step_image).pc
    edge = pc[:, 46:50].mean()
    flat = pc[:, 8:24].mean()
    assert edge > 5.0 * flat


def test_phase_congruency_is_sparse_on_smooth_terrain():
    """A smooth field has little phase congruency -- which is why realistic
    mare starves PC-based detection. Documented as a property, not a defect."""
    rng = np.random.default_rng(3)
    smooth = ndimage.gaussian_filter(rng.normal(size=(96, 96)), 12.0)
    textured = ndimage.gaussian_filter(rng.normal(size=(96, 96)), 2.0)
    assert (phase_congruency(smooth).pc > 0.1).mean() < 0.15
    assert (phase_congruency(textured).pc > 0.1).mean() > 0.5


def test_maximum_index_map_selects_the_strongest_orientation():
    amps = np.zeros((4, 8, 8))
    amps[2] = 1.0
    amps[0] = 0.5
    assert (maximum_index_map(amps) == 2).all()


def test_gradient_magnitude_is_polarity_invariant(step_image):
    a = gradient_magnitude_representation(step_image)
    b = gradient_magnitude_representation(-step_image)
    assert np.abs(a - b).max() < 1e-12


def test_identity_representation_is_the_image(step_image):
    assert np.array_equal(identity_representation(step_image), step_image)


# ---------------------------------------------------------------------------
# descriptors -- the H-3.4 mechanism
# ---------------------------------------------------------------------------

def _kp(n: int = 12):
    rng = np.random.default_rng(11)
    pts = rng.uniform(24, 72, size=(n, 2))
    scales = np.full(n, 6.0)
    return pts, scales


def test_mod_pi_descriptor_is_invariant_to_a_polarity_flip(step_image):
    """The whole point of arm A: negating the image must not change it.

    Negating an image negates every gradient, i.e. rotates each orientation by
    pi. Binned mod pi, that is the identity.
    """
    pts, scales = _kp()
    a = describe_gradient_histogram(step_image, pts, scales, orientation_period=np.pi)
    b = describe_gradient_histogram(-step_image, pts, scales, orientation_period=np.pi)
    assert np.abs(a - b).max() < 1e-6


def test_two_pi_control_descriptor_is_NOT_invariant_to_a_polarity_flip(step_image):
    """The control must genuinely differ, or the comparison proves nothing.

    If this test ever passes, arm ``A_orient_2pi_control`` has stopped being a
    control and H-3.4 becomes untestable.
    """
    pts, scales = _kp()
    a = describe_gradient_histogram(step_image, pts, scales, orientation_period=2 * np.pi)
    b = describe_gradient_histogram(-step_image, pts, scales, orientation_period=2 * np.pi)
    assert np.abs(a - b).max() > 0.05


def test_descriptors_are_l2_normalised_before_the_root_transform(step_image):
    pts, scales = _kp()
    d = describe_gradient_histogram(step_image, pts, scales, root=False)
    norms = np.linalg.norm(d, axis=1)
    nonzero = norms > 1e-8
    assert np.allclose(norms[nonzero], 1.0, atol=1e-5)


def test_descriptor_shape_and_determinism(step_image):
    pts, scales = _kp(7)
    d1 = describe_gradient_histogram(step_image, pts, scales)
    d2 = describe_gradient_histogram(step_image, pts, scales)
    assert d1.shape == (7, 4 * 4 * 8)
    assert np.array_equal(d1, d2)


def test_descriptor_handles_empty_keypoint_set(step_image):
    d = describe_gradient_histogram(step_image, np.zeros((0, 2)), np.zeros(0))
    assert d.shape == (0, 128)


def test_mim_descriptor_is_contrast_invariant_by_construction(step_image):
    """MIM records which orientation channel wins, never by how much."""
    res = phase_congruency(step_image)
    mim = maximum_index_map(res.orientation_amplitude)
    pts, scales = _kp()
    a = describe_maximum_index(mim, pts, scales, n_index=6)

    res2 = phase_congruency(5.0 * step_image)
    mim2 = maximum_index_map(res2.orientation_amplitude)
    b = describe_maximum_index(mim2, pts, scales, n_index=6)
    assert np.abs(a - b).max() < 1e-6


def test_mim_descriptor_shape():
    mim = np.zeros((64, 64), dtype=np.int32)
    pts, scales = _kp(5)
    d = describe_maximum_index(mim, pts, scales, n_index=6, n_spatial=6)
    assert d.shape == (5, 6 * 6 * 6)
