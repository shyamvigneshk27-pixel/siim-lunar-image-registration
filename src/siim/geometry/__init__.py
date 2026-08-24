"""Geometry layer: coordinate conventions, transforms, estimation, resampling.

This package is built first and tested hardest (ADR-0007), because everything
downstream depends on its correctness and its failure mode is silent.

Read ``docs/coordinate_contract.md`` before changing anything here.
"""

from .conventions import (
    EPS_HOMOGENEOUS,
    PointArray,
    as_points,
    corner_points,
    finite_mask,
    from_homogeneous,
    image_centre,
    image_extent,
    pixel_grid,
    rc_to_xy,
    scale_coords,
    to_homogeneous,
    xy_to_rc,
)
from .estimate import (
    EstimationResult,
    collinearity,
    estimate,
    estimate_affine,
    estimate_euclidean,
    estimate_projective,
    estimate_similarity,
    estimate_translation,
    transfer_residuals,
)
from .resample import antialias_sigma, resize, warp, warp_bounds
from .synthetic import (
    GroundTruthError,
    anchor_at,
    endpoint_error,
    photometric_perturb,
    random_transform,
)
from .transforms import (
    MODEL_DOF,
    MODEL_MIN_POINTS,
    MODEL_ORDER,
    Transform,
    affine,
    euclidean,
    identity,
    more_general,
    projective,
    scale_transform,
    similarity,
    translation,
)

__all__ = [
    # conventions
    "PointArray",
    "EPS_HOMOGENEOUS",
    "as_points",
    "to_homogeneous",
    "from_homogeneous",
    "finite_mask",
    "xy_to_rc",
    "rc_to_xy",
    "image_extent",
    "image_centre",
    "pixel_grid",
    "corner_points",
    "scale_coords",
    # transforms
    "Transform",
    "MODEL_DOF",
    "MODEL_ORDER",
    "MODEL_MIN_POINTS",
    "identity",
    "translation",
    "euclidean",
    "similarity",
    "affine",
    "projective",
    "scale_transform",
    "more_general",
    # estimation
    "EstimationResult",
    "estimate",
    "estimate_translation",
    "estimate_euclidean",
    "estimate_similarity",
    "estimate_affine",
    "estimate_projective",
    "transfer_residuals",
    "collinearity",
    # resampling
    "warp",
    "resize",
    "warp_bounds",
    "antialias_sigma",
    # synthetic ground truth
    "GroundTruthError",
    "random_transform",
    "anchor_at",
    "endpoint_error",
    "photometric_perturb",
]
