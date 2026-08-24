"""Synthetic transform generation and ground-truth error measurement.

This is estimator **F.1.1** of the evidence stack (ANALYSIS §F.1): apply a
*known* transform to a real image, recover it, and measure the true endpoint
error on a dense grid. It is the only estimator in the project that has access
to exact truth.

What it does and does not prove
-------------------------------
Synthetic ground truth measures **algorithm correctness**. It does **not**
measure data difficulty: a warped copy of an image is not a different sensor,
and no amount of photometric perturbation makes it one. Spec §13 forbids
conflating the two, so every number produced here must be reported as
"synthetic GT" and never presented as evidence of real cross-modal or real
Sun-angle invariance.

Its actual job is the EXP-000/EXP-001 gate: a pipeline that cannot recover a
known homography to well under a pixel has a bug, and every subsequent
measurement on real data would be measuring that bug.

On the photometric perturbations
--------------------------------
:func:`photometric_perturb` applies gain, bias, gamma and noise. These model
*radiometric* differences only. They are explicitly **not** a lunar relighting
model: they cannot reverse a shadow, which is the actual difficulty
(ANALYSIS §B2). Real relighting requires a DEM and a scattering model and
belongs to EXP-003. Using this function and calling the result
"Sun-angle invariance" would be precisely the false claim spec §13 warns about.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .conventions import PointArray, as_points, image_centre, pixel_grid
from .transforms import (
    Transform,
    affine,
    euclidean,
    projective,
    similarity,
    translation,
)

__all__ = [
    "GroundTruthError",
    "random_transform",
    "anchor_at",
    "endpoint_error",
    "photometric_perturb",
]


def anchor_at(transform: Transform, centre: ArrayLike) -> Transform:
    """Re-anchor a transform so it acts about ``centre`` instead of the origin.

    A rotation about the origin of a 4096-pixel image translates its content
    off-canvas; a rotation about the image centre is what "rotate the image by
    5 degrees" actually means. Anchoring keeps generated transforms
    interpretable and keeps the overlap non-trivial.
    """
    c = as_points(centre)[0]
    to_origin = translation(-c[0], -c[1])
    back = translation(c[0], c[1])
    return back @ transform @ to_origin


@dataclass(frozen=True)
class GroundTruthError:
    """True endpoint error of an estimated transform against a known one."""

    mean: float
    median: float
    p90: float
    p99: float
    max: float
    rms: float
    n_points: int

    def __repr__(self) -> str:  # pragma: no cover - display only
        return (
            f"GroundTruthError(median={self.median:.4f}px, mean={self.mean:.4f}px, "
            f"p90={self.p90:.4f}px, max={self.max:.4f}px, n={self.n_points})"
        )


def random_transform(
    rng: np.random.Generator,
    model: str,
    shape: tuple[int, int],
    *,
    max_translation: float = 30.0,
    max_rotation_deg: float = 15.0,
    scale_range: tuple[float, float] = (0.8, 1.25),
    max_shear: float = 0.08,
    max_perspective: float = 2.5e-4,
) -> Transform:
    """Generate a random transform of class ``model``, anchored at image centre.

    Magnitudes are bounded so the warped image retains substantial overlap
    with the original; a synthetic pair with 5% overlap tests nothing useful.
    Perspective terms are scaled by image size internally, so
    ``max_perspective`` is dimensionless and behaves consistently across
    image resolutions.
    """
    h, w = shape
    diag = float(np.hypot(w, h))

    tx = float(rng.uniform(-max_translation, max_translation))
    ty = float(rng.uniform(-max_translation, max_translation))
    ang = float(np.deg2rad(rng.uniform(-max_rotation_deg, max_rotation_deg)))
    sc = float(rng.uniform(*scale_range))

    if model == "translation":
        base = translation(tx, ty)
    elif model == "euclidean":
        base = euclidean(ang, tx, ty)
    elif model == "similarity":
        base = similarity(sc, ang, tx, ty)
    elif model == "affine":
        c, s = sc * np.cos(ang), sc * np.sin(ang)
        shear = float(rng.uniform(-max_shear, max_shear))
        base = affine([[c, -s + shear * c, tx], [s, c + shear * s, ty]])
    elif model == "projective":
        c, s = sc * np.cos(ang), sc * np.sin(ang)
        shear = float(rng.uniform(-max_shear, max_shear))
        # Divide by the diagonal so the perspective effect is resolution-independent.
        g = float(rng.uniform(-max_perspective, max_perspective)) / diag * 100.0
        hh = float(rng.uniform(-max_perspective, max_perspective)) / diag * 100.0
        base = projective(
            [[c, -s + shear * c, tx], [s, c + shear * s, ty], [g, hh, 1.0]]
        )
    else:
        raise ValueError(f"unknown model {model!r}")

    return anchor_at(base, image_centre(shape))


def endpoint_error(
    estimated: Transform,
    truth: Transform,
    shape: tuple[int, int],
    step: int = 16,
) -> GroundTruthError:
    """True error between two transforms, sampled on a grid over the image.

    This compares the *maps*, not their residuals on the correspondences that
    produced them -- which is what makes it a genuine accuracy measurement and
    not the circular statistic of ANALYSIS §A.3.

    Sampling on a grid rather than at the matched points matters: it reports
    error *where there were no correspondences*, which is where extrapolation
    error lives and precisely what the coverage metric (ADR-0006) is about.
    """
    grid = pixel_grid(shape, step=step)
    a = estimated.apply(grid)
    b = truth.apply(grid)
    err = np.sqrt(((a - b) ** 2).sum(axis=1))
    finite = err[np.isfinite(err)]
    if finite.size == 0:
        return GroundTruthError(*([float("inf")] * 6), n_points=0)
    return GroundTruthError(
        mean=float(finite.mean()),
        median=float(np.median(finite)),
        p90=float(np.percentile(finite, 90)),
        p99=float(np.percentile(finite, 99)),
        max=float(finite.max()),
        rms=float(np.sqrt((finite**2).mean())),
        n_points=int(finite.size),
    )


def photometric_perturb(
    image: ArrayLike,
    rng: np.random.Generator,
    *,
    gain_range: tuple[float, float] = (0.7, 1.3),
    bias_range: tuple[float, float] = (-0.1, 0.1),
    gamma_range: tuple[float, float] = (0.7, 1.4),
    noise_std: float = 0.01,
) -> NDArray[np.float64]:
    """Apply gain, bias, gamma and Gaussian noise to a [0, 1] image.

    **Radiometric perturbation only.** This cannot reverse a shadow and so
    does not simulate a Sun-azimuth change (see module docstring). It is
    adequate for testing that a representation is invariant to *contrast and
    exposure* differences, which is a necessary but far from sufficient
    condition for the real problem.
    """
    img = np.asarray(image, dtype=np.float64)
    gain = float(rng.uniform(*gain_range))
    bias = float(rng.uniform(*bias_range))
    gamma = float(rng.uniform(*gamma_range))

    out = np.clip(img, 0.0, 1.0) ** gamma
    out = gain * out + bias
    if noise_std > 0:
        out = out + rng.normal(0.0, noise_std, size=out.shape)
    return np.clip(out, 0.0, 1.0)
