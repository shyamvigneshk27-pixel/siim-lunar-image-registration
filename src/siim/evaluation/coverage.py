"""Spatial coverage metrics for correspondence sets (spec §15).

Spec §15 asks which coverage metric is most meaningful and demands a
justification. Ours is :data:`max_uncovered_disc_radius`, and the argument is
in ADR-0006:

    Registration error at a point grows with distance to the nearest
    constraining correspondence, because the transform interpolates between
    constraints where they exist and extrapolates where they do not. The
    largest empty disc therefore upper-bounds the region of worst-case local
    error. Occupancy and entropy are averages, and an average cannot bound a
    worst case -- a point set can score excellent entropy while leaving one
    large hole exactly where accuracy was needed.

The averages are still computed and reported, as secondary descriptors. That
claim -- that the disc radius predicts local error better than the averages do
-- is a hypothesis, and EXP-007 is what tests it. It is not established here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import ndimage
from scipy.spatial import ConvexHull, QhullError

from ..geometry import as_points

__all__ = ["CoverageMetrics", "coverage_metrics"]


@dataclass(frozen=True)
class CoverageMetrics:
    """Spatial distribution of a correspondence set over a region of interest."""

    n_points: int
    #: PRIMARY (ADR-0006). Radius of the largest disc inside the ROI holding no
    #: point, as a fraction of the image diagonal. Lower is better.
    max_uncovered_disc_ratio: float
    #: Same quantity in pixels.
    max_uncovered_disc_px: float
    #: Fraction of grid cells (over the ROI) containing at least one point.
    grid_occupancy: float
    #: Shannon entropy of the per-cell counts, normalised to [0, 1].
    spatial_entropy: float
    #: Convex hull of the points as a fraction of the ROI area.
    hull_ratio: float
    #: Median nearest-neighbour distance between points, in pixels.
    median_nn_distance: float
    grid_size: int

    def __repr__(self) -> str:  # pragma: no cover - display only
        return (
            f"CoverageMetrics(n={self.n_points}, "
            f"max_gap={self.max_uncovered_disc_ratio:.3f}D, "
            f"occupancy={self.grid_occupancy:.3f}, "
            f"entropy={self.spatial_entropy:.3f})"
        )


def coverage_metrics(
    points: ArrayLike,
    shape: tuple[int, int],
    roi: ArrayLike | None = None,
    grid_size: int = 8,
) -> CoverageMetrics:
    """Measure how well ``points`` cover ``roi`` within an image of ``shape``.

    Parameters
    ----------
    points
        ``(N, 2)`` correspondence locations in ``(x, y)``.
    roi
        Boolean region of interest, normally the estimated overlap. Coverage
        of the *whole frame* is the wrong question when the images only
        partly overlap: it would penalise a method for not finding matches
        where no common terrain exists.
    grid_size
        Cells per axis for occupancy and entropy.
    """
    h, w = int(shape[0]), int(shape[1])
    pts = as_points(points)
    mask = np.ones((h, w), dtype=bool) if roi is None else np.asarray(roi, dtype=bool)
    if mask.shape != (h, w):
        raise ValueError(f"roi shape {mask.shape} does not match image shape {(h, w)}")

    diag = float(np.hypot(w, h))
    roi_area = float(mask.sum())
    if pts.shape[0] == 0 or roi_area == 0:
        return CoverageMetrics(
            n_points=int(pts.shape[0]),
            max_uncovered_disc_ratio=1.0,
            max_uncovered_disc_px=diag,
            grid_occupancy=0.0,
            spatial_entropy=0.0,
            hull_ratio=0.0,
            median_nn_distance=float("nan"),
            grid_size=grid_size,
        )

    # -- primary: largest empty disc, by exact distance transform ----------
    seeds = np.ones((h, w), dtype=bool)
    xi = np.clip(np.round(pts[:, 0]).astype(int), 0, w - 1)
    yi = np.clip(np.round(pts[:, 1]).astype(int), 0, h - 1)
    seeds[yi, xi] = False
    dist = ndimage.distance_transform_edt(seeds)
    max_gap_px = float(dist[mask].max())

    # -- secondary: occupancy and entropy over a grid ----------------------
    gx = np.clip((pts[:, 0] / w * grid_size).astype(int), 0, grid_size - 1)
    gy = np.clip((pts[:, 1] / h * grid_size).astype(int), 0, grid_size - 1)
    counts = np.zeros((grid_size, grid_size), dtype=np.float64)
    np.add.at(counts, (gy, gx), 1.0)

    # Only score cells that actually contain ROI, else a small overlap is
    # unfairly punished for the empty cells outside it.
    cell_h = max(1, h // grid_size)
    cell_w = max(1, w // grid_size)
    roi_cells = np.zeros((grid_size, grid_size), dtype=bool)
    for iy in range(grid_size):
        for ix in range(grid_size):
            block = mask[iy * cell_h : (iy + 1) * cell_h, ix * cell_w : (ix + 1) * cell_w]
            roi_cells[iy, ix] = block.size > 0 and block.mean() > 0.25

    n_roi_cells = int(roi_cells.sum())
    occupancy = (
        float(((counts > 0) & roi_cells).sum() / n_roi_cells) if n_roi_cells else 0.0
    )

    active = counts[roi_cells]
    total = active.sum()
    if total > 0 and n_roi_cells > 1:
        p = active[active > 0] / total
        entropy = float(-(p * np.log(p)).sum() / np.log(n_roi_cells))
    else:
        entropy = 0.0

    # -- secondary: convex hull and nearest-neighbour spacing --------------
    hull_ratio = 0.0
    if pts.shape[0] >= 3:
        try:
            hull_ratio = float(ConvexHull(pts).volume / roi_area)  # 2-D: volume is area
        except (QhullError, ValueError):
            hull_ratio = 0.0  # degenerate (collinear) point set

    if pts.shape[0] >= 2:
        d2 = ((pts[:, None, :] - pts[None, :, :]) ** 2).sum(axis=2)
        np.fill_diagonal(d2, np.inf)
        median_nn = float(np.median(np.sqrt(d2.min(axis=1))))
    else:
        median_nn = float("nan")

    return CoverageMetrics(
        n_points=int(pts.shape[0]),
        max_uncovered_disc_ratio=max_gap_px / diag,
        max_uncovered_disc_px=max_gap_px,
        grid_occupancy=occupancy,
        spatial_entropy=entropy,
        hull_ratio=min(hull_ratio, 1.0),
        median_nn_distance=median_nn,
        grid_size=grid_size,
    )
