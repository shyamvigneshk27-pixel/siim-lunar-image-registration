"""Spatial uniformity of a correspondence set.

The problem statement asks for correspondence "maintaining uniform
distribution across the images", alongside sub-pixel accuracy, in one
sentence. The two requirements are the same requirement seen twice:
sub-pixel accuracy measured at three clustered points is not sub-pixel
accuracy of the image.

Three quantities are computed, and the choice of each is argued.

``U1`` — normalised largest empty disc. The radius of the largest disc inside
the valid overlap containing no correspondence, divided by the radius of a
disc of the same area as that overlap. **Registration error at a point grows
with distance to the nearest constraint**, so the largest empty disc
upper-bounds the region of worst local error. An average cannot bound a worst
case, which is why occupancy and entropy are reported but do not decide.

The normalisation differs deliberately from
:func:`siim.evaluation.coverage.coverage_metrics`, which divides by the image
diagonal. Dividing by ``sqrt(area / pi)`` makes the value comparable between
overlaps of different size and shape; the diagonal form is not, and this
project has previously compared a 111x46 strip against a 2048x1024 tile as if
the two numbers meant the same thing.

``U2`` — maximum predicted mapping standard deviation over the overlap, in
source pixels. This is the criterion of record. It is the only candidate whose
threshold can be **derived** from the accuracy budget rather than chosen, and
it is expressed in the units the problem statement uses. It is computed
non-parametrically from bootstrap transform replicates, so it needs no
analytic Jacobian and works for every motion model.

**U2 is a precision, not an accuracy.** It bounds the uncertainty *given* the
correspondences are right. A systematically displaced correspondence set
yields a small, confident U2. Establishing correctness is the job of loop
closure, engine agreement and the geometry gate.

``U3`` — minimum per-cell correspondence count, over cells with enough valid
area to count. Catches the thin spread that satisfies U1 and U2 globally while
leaving local regions with too few points to constrain anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import ndimage

from ..geometry import as_points

__all__ = ["UniformityMetrics", "uniformity_metrics", "coverage_curve"]


def _roi_mask(shape: tuple[int, int], roi: ArrayLike | None) -> NDArray[np.bool_]:
    h, w = int(shape[0]), int(shape[1])
    if roi is None:
        return np.ones((h, w), dtype=bool)
    mask = np.asarray(roi, dtype=bool)
    if mask.shape != (h, w):
        raise ValueError(f"roi shape {mask.shape} does not match shape {(h, w)}")
    return mask


def _distance_field(points: NDArray[np.float64],
                    mask: NDArray[np.bool_]) -> NDArray[np.float64] | None:
    """Euclidean distance from every mask pixel to the nearest point.

    Returns ``None`` when no point falls inside the image, which is a real
    outcome and not a zero distance.
    """
    h, w = mask.shape
    seeds = np.ones((h, w), dtype=bool)
    placed = 0
    for x, y in points:
        xi, yi = int(round(float(x))), int(round(float(y)))
        if 0 <= xi < w and 0 <= yi < h:
            seeds[yi, xi] = False
            placed += 1
    if placed == 0:
        return None
    return ndimage.distance_transform_edt(seeds)


@dataclass(frozen=True)
class UniformityMetrics:
    """Uniformity of one correspondence set over one overlap region."""

    n_points: int
    #: Area of the valid overlap, in pixels.
    roi_area_px: float
    #: Radius of a disc of the same area as the overlap, in pixels.
    roi_radius_px: float
    #: U1. Largest empty disc radius / roi_radius_px. Lower is better.
    u1_largest_gap: float | None
    #: The same quantity in pixels, before normalisation.
    u1_largest_gap_px: float | None
    #: U2. Max predicted mapping standard deviation over the overlap, source px.
    u2_max_prediction_sd_px: float | None
    #: U3. Minimum correspondences in any sufficiently-valid grid cell.
    u3_min_cell_count: int | None
    #: Secondary descriptors. Averages: reported, never decisive.
    grid_occupancy: float | None
    grid_size: int
    #: Set when a quantity could not be computed, keyed by metric name.
    undefined: dict[str, str]

    @property
    def u1_defined(self) -> bool:
        return self.u1_largest_gap is not None

    def meets(self, *, u1_max: float | None = None,
              u2_max_px: float | None = None,
              u3_min: int | None = None) -> tuple[bool, list[str]]:
        """Test against thresholds supplied by the caller.

        **No threshold is defaulted here.** A uniformity threshold must be
        derived from the accuracy budget or calibrated on constructed cases
        with inlier count held constant; inventing one in a library would be
        exactly the error the specification warns against. An undefined metric
        cannot pass a threshold that was asked for, and says so.
        """
        reasons: list[str] = []
        if u1_max is not None:
            if self.u1_largest_gap is None:
                reasons.append(
                    f"U1 threshold {u1_max} requested but U1 is undefined: "
                    f"{self.undefined.get('u1', 'no reason recorded')}"
                )
            elif self.u1_largest_gap > u1_max:
                reasons.append(
                    f"U1 {self.u1_largest_gap:.3f} exceeds {u1_max:.3f}: the "
                    "largest unconstrained region is too big relative to the "
                    "overlap, so the transform extrapolates there."
                )
        if u2_max_px is not None:
            if self.u2_max_prediction_sd_px is None:
                reasons.append(
                    f"U2 threshold {u2_max_px} requested but U2 is undefined: "
                    f"{self.undefined.get('u2', 'no reason recorded')}"
                )
            elif self.u2_max_prediction_sd_px > u2_max_px:
                reasons.append(
                    f"U2 {self.u2_max_prediction_sd_px:.4f} px exceeds "
                    f"{u2_max_px:.4f} px: somewhere in the overlap the mapping "
                    "is less certain than the accuracy budget allows."
                )
        if u3_min is not None:
            if self.u3_min_cell_count is None:
                reasons.append(
                    f"U3 threshold {u3_min} requested but U3 is undefined: "
                    f"{self.undefined.get('u3', 'no reason recorded')}"
                )
            elif self.u3_min_cell_count < u3_min:
                reasons.append(
                    f"U3 {self.u3_min_cell_count} below {u3_min}: at least one "
                    "region of the overlap has too few correspondences to "
                    "constrain the model locally."
                )
        return (not reasons), reasons

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_points": self.n_points,
            "roi_area_px": self.roi_area_px,
            "roi_radius_px": self.roi_radius_px,
            "u1_largest_gap": self.u1_largest_gap,
            "u1_largest_gap_px": self.u1_largest_gap_px,
            "u2_max_prediction_sd_px": self.u2_max_prediction_sd_px,
            "u3_min_cell_count": self.u3_min_cell_count,
            "grid_occupancy": self.grid_occupancy,
            "grid_size": self.grid_size,
            "undefined": dict(self.undefined),
            "u2_is_precision_not_accuracy": True,
        }


def _u2_from_samples(
    transform_samples: Sequence[Any],
    mask: NDArray[np.bool_],
    max_eval_points: int,
    rng: np.random.Generator,
) -> tuple[float | None, str | None]:
    """Max over the overlap of the bootstrap spread of the predicted position."""
    k = len(transform_samples)
    if k < 3:
        return None, (
            f"only {k} transform replicate(s); a spread needs at least 3. "
            "Supply bootstrap replicates of the estimated transform."
        )
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return None, "overlap region is empty"
    if xs.size > max_eval_points:
        idx = rng.choice(xs.size, size=max_eval_points, replace=False)
        xs, ys = xs[idx], ys[idx]
    pts = np.column_stack([xs.astype(float), ys.astype(float)])

    mapped = np.empty((k, pts.shape[0], 2), dtype=float)
    for i, t in enumerate(transform_samples):
        out = t.apply(pts) if hasattr(t, "apply") else _apply_matrix(t, pts)
        arr = np.asarray(out, dtype=float)
        if arr.shape != pts.shape:
            raise ValueError(
                f"transform replicate {i} mapped {pts.shape} points to "
                f"{arr.shape}; expected the same shape"
            )
        mapped[i] = arr
    if not np.isfinite(mapped).all():
        return None, "a transform replicate produced non-finite positions"

    centred = mapped - mapped.mean(axis=0, keepdims=True)
    denom = float(k - 1)
    cxx = np.einsum("kn,kn->n", centred[:, :, 0], centred[:, :, 0]) / denom
    cyy = np.einsum("kn,kn->n", centred[:, :, 1], centred[:, :, 1]) / denom
    cxy = np.einsum("kn,kn->n", centred[:, :, 0], centred[:, :, 1]) / denom
    half = 0.5 * (cxx + cyy)
    rad = np.sqrt(np.maximum(0.0, (0.5 * (cxx - cyy)) ** 2 + cxy ** 2))
    lam_max = np.maximum(0.0, half + rad)
    return float(np.sqrt(lam_max).max()), None


def _apply_matrix(matrix: ArrayLike, pts: NDArray[np.float64]) -> NDArray[np.float64]:
    m = np.asarray(matrix, dtype=float)
    if m.shape != (3, 3):
        raise TypeError(
            "transform replicates must expose .apply(points) or be 3x3 matrices"
        )
    h = np.column_stack([pts, np.ones(pts.shape[0])])
    out = h @ m.T
    w = out[:, 2:3]
    with np.errstate(divide="ignore", invalid="ignore"):
        return out[:, :2] / w


def uniformity_metrics(
    points: ArrayLike,
    shape: tuple[int, int],
    roi: ArrayLike | None = None,
    *,
    grid_size: int = 8,
    transform_samples: Sequence[Any] | None = None,
    max_eval_points: int = 4096,
    seed: int = 0,
    min_cell_valid_fraction: float = 0.5,
) -> UniformityMetrics:
    """Measure U1, U2 and U3 for one correspondence set.

    Parameters
    ----------
    points
        ``(N, 2)`` correspondence locations in source-image ``(x, y)``.
    shape
        ``(height, width)`` of the source image.
    roi
        Boolean valid-overlap mask. Uniformity is measured **over the overlap**,
        not over the whole frame: measuring over the frame would penalise a
        correct registration merely for the images overlapping partially,
        which is the normal case.
    transform_samples
        Bootstrap replicates of the estimated transform, each exposing
        ``apply(points)`` or being a 3x3 matrix. Required for U2; without them
        U2 is reported undefined rather than guessed.
    """
    mask = _roi_mask(shape, roi)
    pts = as_points(points)
    rng = np.random.default_rng(seed)
    undefined: dict[str, str] = {}

    area = float(mask.sum())
    radius = float(np.sqrt(area / np.pi)) if area > 0 else 0.0

    u1 = u1_px = None
    if area <= 0:
        undefined["u1"] = "overlap region is empty"
    elif pts.shape[0] == 0:
        undefined["u1"] = "no correspondences"
    else:
        field = _distance_field(pts, mask)
        if field is None:
            undefined["u1"] = "no correspondence falls inside the image"
        else:
            u1_px = float(field[mask].max())
            u1 = u1_px / radius if radius > 0 else None
            if u1 is None:
                undefined["u1"] = "overlap radius is zero"

    if transform_samples is None:
        u2 = None
        undefined["u2"] = (
            "no transform replicates supplied; U2 is a bootstrap spread and "
            "cannot be inferred from a single transform"
        )
    else:
        u2, why = _u2_from_samples(transform_samples, mask, max_eval_points, rng)
        if why:
            undefined["u2"] = why

    u3: int | None = None
    occupancy: float | None = None
    if area <= 0:
        undefined["u3"] = "overlap region is empty"
    else:
        h, w = mask.shape
        g = max(1, int(grid_size))
        ye = np.linspace(0, h, g + 1).astype(int)
        xe = np.linspace(0, w, g + 1).astype(int)
        counts: list[int] = []
        occupied = 0
        considered = 0
        for i in range(g):
            for j in range(g):
                cell = mask[ye[i]:ye[i + 1], xe[j]:xe[j + 1]]
                if cell.size == 0:
                    continue
                valid_frac = float(cell.sum()) / float(cell.size)
                if valid_frac < min_cell_valid_fraction:
                    continue
                considered += 1
                inside = (
                    (pts[:, 0] >= xe[j]) & (pts[:, 0] < xe[j + 1])
                    & (pts[:, 1] >= ye[i]) & (pts[:, 1] < ye[i + 1])
                ).sum() if pts.shape[0] else 0
                counts.append(int(inside))
                if inside > 0:
                    occupied += 1
        if not counts:
            undefined["u3"] = (
                f"no grid cell reaches {min_cell_valid_fraction:.0%} valid area "
                "at this grid size"
            )
        else:
            u3 = int(min(counts))
            occupancy = occupied / considered

    return UniformityMetrics(
        n_points=int(pts.shape[0]),
        roi_area_px=area,
        roi_radius_px=radius,
        u1_largest_gap=u1,
        u1_largest_gap_px=u1_px,
        u2_max_prediction_sd_px=u2,
        u3_min_cell_count=u3,
        grid_occupancy=occupancy,
        grid_size=int(grid_size),
        undefined=undefined,
    )


def coverage_curve(
    points: ArrayLike,
    shape: tuple[int, int],
    roi: ArrayLike | None = None,
    radii_px: Sequence[float] | None = None,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Fraction of the overlap within distance ``r`` of a correspondence.

    Returns ``(radii, fractions)``. A scalar can be gamed; the curve cannot,
    and it is what belongs in a figure.
    """
    mask = _roi_mask(shape, roi)
    pts = as_points(points)
    if radii_px is None:
        diag = float(np.hypot(shape[1], shape[0]))
        radii_px = tuple(float(x) for x in np.linspace(0.0, diag / 4.0, 16))
    radii = tuple(float(r) for r in radii_px)
    if mask.sum() == 0 or pts.shape[0] == 0:
        return radii, tuple(0.0 for _ in radii)
    field = _distance_field(pts, mask)
    if field is None:
        return radii, tuple(0.0 for _ in radii)
    inside = field[mask]
    total = float(inside.size)
    return radii, tuple(float((inside <= r).sum()) / total for r in radii)
