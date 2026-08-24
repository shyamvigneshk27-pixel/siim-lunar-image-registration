"""Planar transform models, represented uniformly as 3x3 homogeneous matrices.

Direction convention (contract C5): a :class:`Transform` maps **source ->
reference**, i.e. ``q = T.apply(p)``. Image warping needs the inverse map and
inverts internally -- callers always pass the forward transform.

Model hierarchy, in increasing generality and degrees of freedom:

===============  ====  ====================================================
model            DOF   what it can express
===============  ====  ====================================================
``translation``     2  shift only
``euclidean``       3  shift + rotation (rigid)
``similarity``      4  shift + rotation + isotropic scale
``affine``          6  + shear and anisotropic scale; parallel lines stay so
``projective``      8  + perspective; straight lines stay straight
===============  ====  ====================================================

The DOF column is not decoration: model selection (EXP-009) trades fit against
complexity, and a model that costs 8 parameters must earn them against one
costing 4. Relief displacement (ANALYSIS §B7) means the most general model is
not automatically the right one -- a projective fit can absorb topographic
error into perspective parameters and look better while being physically
wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .conventions import PointArray, as_points, from_homogeneous, to_homogeneous

__all__ = [
    "Transform",
    "MODEL_DOF",
    "MODEL_ORDER",
    "identity",
    "translation",
    "euclidean",
    "similarity",
    "affine",
    "projective",
    "scale_transform",
    "more_general",
]

MODEL_DOF: Final[dict[str, int]] = {
    "translation": 2,
    "euclidean": 3,
    "similarity": 4,
    "affine": 6,
    "projective": 8,
}

#: Models in increasing order of generality.
MODEL_ORDER: Final[tuple[str, ...]] = (
    "translation",
    "euclidean",
    "similarity",
    "affine",
    "projective",
)

#: Minimum correspondences needed to determine each model.
MODEL_MIN_POINTS: Final[dict[str, int]] = {
    "translation": 1,
    "euclidean": 2,
    "similarity": 2,
    "affine": 3,
    "projective": 4,
}


def more_general(a: str, b: str) -> str:
    """Return whichever of two model names is the more general."""
    return a if MODEL_ORDER.index(a) >= MODEL_ORDER.index(b) else b


@dataclass(frozen=True)
class Transform:
    """A planar transform: a 3x3 homogeneous matrix plus its model class.

    Immutable. Every operation returns a new instance, so a transform cannot
    be mutated out from under a result that recorded it -- which matters for
    reproducibility (spec §33).
    """

    matrix: NDArray[np.float64]
    model: str

    def __post_init__(self) -> None:
        m = np.asarray(self.matrix, dtype=np.float64)
        if m.shape != (3, 3):
            raise ValueError(f"transform matrix must be 3x3; got {m.shape}")
        if not np.isfinite(m).all():
            raise ValueError("transform matrix contains non-finite values")
        if self.model not in MODEL_DOF:
            raise ValueError(
                f"unknown model {self.model!r}; expected one of {MODEL_ORDER}"
            )
        if self.model != "projective":
            # Affine and below must have an exact [0, 0, 1] bottom row.
            if not np.allclose(m[2], [0.0, 0.0, 1.0], atol=1e-12):
                raise ValueError(
                    f"model {self.model!r} requires bottom row [0, 0, 1]; got {m[2]}. "
                    "Use model='projective' if a perspective component is intended."
                )
        object.__setattr__(self, "matrix", np.ascontiguousarray(m))

    # -- core operations -------------------------------------------------

    def apply(self, pts: ArrayLike) -> PointArray:
        """Map source points to reference points. ``(N, 2)`` -> ``(N, 2)``.

        Points sent to infinity by a projective transform come back as
        ``NaN`` (contract C6); filter with ``conventions.finite_mask``.
        """
        p_h = to_homogeneous(as_points(pts))
        return from_homogeneous(p_h @ self.matrix.T)

    def inverse(self) -> "Transform":
        """The reference -> source transform. Model class is preserved."""
        try:
            inv = np.linalg.inv(self.matrix)
        except np.linalg.LinAlgError as exc:
            raise ValueError(
                "transform is singular and cannot be inverted; this usually "
                "means it was estimated from a degenerate configuration"
            ) from exc
        if self.model != "projective":
            # Re-impose the exact bottom row that float inversion perturbs.
            inv[2] = [0.0, 0.0, 1.0]
        return Transform(inv, self.model)

    def compose(self, other: "Transform") -> "Transform":
        """``self ∘ other``: apply ``other`` first, then ``self``.

        The result takes the more general of the two model classes, since a
        composition can only be as constrained as its loosest factor.
        """
        return Transform(
            self.matrix @ other.matrix, more_general(self.model, other.model)
        )

    def __matmul__(self, other: "Transform") -> "Transform":
        return self.compose(other)

    # -- properties ------------------------------------------------------

    @property
    def dof(self) -> int:
        """Degrees of freedom of this model class."""
        return MODEL_DOF[self.model]

    @property
    def min_points(self) -> int:
        """Minimum correspondences needed to determine this model."""
        return MODEL_MIN_POINTS[self.model]

    @property
    def normalised_matrix(self) -> NDArray[np.float64]:
        """Matrix scaled to a canonical form, for comparison.

        Homogeneous matrices are defined only up to scale, so two numerically
        different matrices can be the same transform. Comparisons must use
        this, never the raw matrix.
        """
        m = self.matrix
        denom = m[2, 2]
        if abs(denom) < 1e-12:
            denom = np.linalg.norm(m)
        return m / denom

    def is_close(self, other: "Transform", atol: float = 1e-8) -> bool:
        """Whether two transforms are numerically the same map (up to scale)."""
        return bool(
            np.allclose(self.normalised_matrix, other.normalised_matrix, atol=atol)
        )

    def decompose_similarity(self) -> dict[str, float]:
        """Scale, rotation and translation, for similarity-or-simpler models.

        Reporting a recovered scale and rotation in physical terms is what
        makes a result explainable to a reviewer (spec §83), rather than a
        matrix nobody can sanity-check by eye.
        """
        if MODEL_ORDER.index(self.model) > MODEL_ORDER.index("similarity"):
            raise ValueError(
                f"decompose_similarity is only meaningful for similarity or "
                f"simpler models; this transform is {self.model!r}"
            )
        a, b = self.matrix[0, 0], self.matrix[1, 0]
        scale = float(np.hypot(a, b))
        return {
            "scale": scale,
            "rotation_rad": float(np.arctan2(b, a)),
            "tx": float(self.matrix[0, 2]),
            "ty": float(self.matrix[1, 2]),
        }

    def __repr__(self) -> str:  # pragma: no cover - display only
        with np.printoptions(precision=6, suppress=True):
            return f"Transform(model={self.model!r}, dof={self.dof},\n{self.matrix})"


# -- constructors --------------------------------------------------------


def identity(model: str = "translation") -> Transform:
    """The identity transform, declared as ``model``."""
    return Transform(np.eye(3, dtype=np.float64), model)


def translation(tx: float, ty: float) -> Transform:
    m = np.eye(3, dtype=np.float64)
    m[0, 2], m[1, 2] = float(tx), float(ty)
    return Transform(m, "translation")


def euclidean(angle_rad: float, tx: float = 0.0, ty: float = 0.0) -> Transform:
    """Rigid transform: rotation about the origin, then translation.

    Angle is CCW-positive in the ``(x, y)`` frame; because ``y`` points down
    in image space, it reads clockwise on screen (contract C8).
    """
    c, s = np.cos(angle_rad), np.sin(angle_rad)
    m = np.array(
        [[c, -s, float(tx)], [s, c, float(ty)], [0.0, 0.0, 1.0]], dtype=np.float64
    )
    return Transform(m, "euclidean")


def similarity(
    scale: float, angle_rad: float = 0.0, tx: float = 0.0, ty: float = 0.0
) -> Transform:
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError(f"similarity scale must be finite and positive; got {scale}")
    c, s = scale * np.cos(angle_rad), scale * np.sin(angle_rad)
    m = np.array(
        [[c, -s, float(tx)], [s, c, float(ty)], [0.0, 0.0, 1.0]], dtype=np.float64
    )
    return Transform(m, "similarity")


def affine(matrix_2x3: ArrayLike) -> Transform:
    """Build an affine transform from a ``(2, 3)`` matrix."""
    a = np.asarray(matrix_2x3, dtype=np.float64)
    if a.shape != (2, 3):
        raise ValueError(f"affine matrix must be (2, 3); got {a.shape}")
    m = np.vstack([a, [0.0, 0.0, 1.0]])
    return Transform(m, "affine")


def projective(matrix_3x3: ArrayLike) -> Transform:
    """Build a projective transform (homography) from a ``(3, 3)`` matrix."""
    return Transform(np.asarray(matrix_3x3, dtype=np.float64), "projective")


def scale_transform(scale: float) -> Transform:
    """The coordinate update for resampling an image by ``scale`` (>1 enlarges).

    Implements contract C4, ``p' = scale * (p + 0.5) - 0.5``, as a transform so
    the resampling factor lives in the transform chain and cannot be dropped.

    The offset term ``(scale - 1) / 2`` is the part that the naive ``p' =
    scale * p`` omits. At ``scale = 2`` that omission is a half-pixel error --
    the whole sub-pixel budget.
    """
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError(f"scale must be finite and positive; got {scale}")
    s = float(scale)
    offset = (s - 1.0) / 2.0
    m = np.array(
        [[s, 0.0, offset], [0.0, s, offset], [0.0, 0.0, 1.0]], dtype=np.float64
    )
    return Transform(m, "similarity")
