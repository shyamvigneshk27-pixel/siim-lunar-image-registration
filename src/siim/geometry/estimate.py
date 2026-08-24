"""Transform estimation from point correspondences, with degeneracy reporting.

Every estimator here:

* applies **Hartley normalisation** before solving and de-normalises after
  (contract C9). Without it the design matrix for image-sized coordinates is
  badly conditioned and the fit degrades in ways that are invisible in the
  residuals;
* reports the **condition number** of the solve;
* **detects degenerate configurations** -- too few points, collinear points,
  insufficient spatial spread -- and flags them rather than returning a
  confident-looking fit built on nothing.

That last point is not defensive programming for its own sake. A transform
estimated from four nearly-collinear correspondences will have a small
residual on those four points and be wildly wrong everywhere else. Spec §26
requires the system to know when it is failing; this is where that starts.

Note on residuals: ``residuals`` here are **fit** residuals, in the sense of
ANALYSIS §A.3 -- they are computed on the same points that determined the
transform, and they are therefore not an accuracy measurement. Held-out and
cross-validated residuals live in ``siim.evaluation``. The naming is
deliberate; nothing in this module may be reported as an accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .conventions import PointArray, as_points
from .transforms import (
    MODEL_MIN_POINTS,
    MODEL_ORDER,
    Transform,
    affine,
    projective,
)

__all__ = [
    "EstimationResult",
    "estimate",
    "estimate_translation",
    "estimate_euclidean",
    "estimate_similarity",
    "estimate_affine",
    "estimate_projective",
    "transfer_residuals",
    "collinearity",
]

#: Below this ratio of second to first singular value, a point set is treated
#: as collinear. Chosen conservatively: a genuinely 2-D spread sits well above
#: it, so this fires only on real degeneracy.
COLLINEARITY_THRESHOLD: Final[float] = 1e-3

#: Above this condition number the solve is reported as ill-conditioned.
CONDITION_WARN: Final[float] = 1e8


@dataclass(frozen=True)
class EstimationResult:
    """Outcome of fitting one transform model to one correspondence set."""

    transform: Transform | None
    model: str
    n_points: int
    #: Per-point forward transfer error ||T(p) - q||, in reference pixels.
    #: These are FIT residuals, not an accuracy measurement (see module docstring).
    residuals: NDArray[np.float64] = field(default_factory=lambda: np.empty(0))
    rmse: float = float("nan")
    median_error: float = float("nan")
    condition: float = float("nan")
    degenerate: bool = False
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.transform is not None and not self.degenerate

    def __repr__(self) -> str:  # pragma: no cover - display only
        status = "ok" if self.ok else f"DEGENERATE({self.reason})"
        return (
            f"EstimationResult(model={self.model!r}, n={self.n_points}, "
            f"fit_rmse={self.rmse:.4f}, cond={self.condition:.3g}, {status})"
        )


def _failed(model: str, n: int, reason: str) -> EstimationResult:
    return EstimationResult(
        transform=None, model=model, n_points=n, degenerate=True, reason=reason
    )


def collinearity(pts: ArrayLike) -> float:
    """Ratio of second to first singular value of the centred point set.

    ``0.0`` means perfectly collinear (no spread off the principal axis);
    ``1.0`` means isotropic spread. This is the quantity that matters for
    whether a 2-D transform is determined at all.
    """
    p = as_points(pts)
    if p.shape[0] < 2:
        return 0.0
    centred = p - p.mean(axis=0)
    sv = np.linalg.svd(centred, compute_uv=False)
    if sv[0] < 1e-12:
        return 0.0
    return float(sv[1] / sv[0])


def _hartley_normalise(
    pts: PointArray,
) -> tuple[PointArray, NDArray[np.float64]] | None:
    """Translate centroid to origin and scale mean distance to sqrt(2).

    Returns ``(normalised_points, T)`` where ``T`` is the 3x3 normalising
    transform, or ``None`` if the point set has no spread at all.
    """
    centroid = pts.mean(axis=0)
    centred = pts - centroid
    mean_dist = float(np.sqrt((centred**2).sum(axis=1)).mean())
    if mean_dist < 1e-12:
        return None
    s = np.sqrt(2.0) / mean_dist
    t = np.array(
        [
            [s, 0.0, -s * centroid[0]],
            [0.0, s, -s * centroid[1]],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    return centred * s, t


def transfer_residuals(
    transform: Transform, src: ArrayLike, dst: ArrayLike
) -> NDArray[np.float64]:
    """Forward transfer error ``||T(src) - dst||`` per correspondence.

    Points that the transform sends to infinity yield ``inf`` rather than
    ``NaN``, so that they sort as maximally bad under any threshold test
    instead of silently vanishing from a ``nanmean``.
    """
    p, q = as_points(src), as_points(dst)
    if p.shape != q.shape:
        raise ValueError(f"src and dst must have equal shape; got {p.shape} vs {q.shape}")
    mapped = transform.apply(p)
    err = np.sqrt(((mapped - q) ** 2).sum(axis=1))
    return np.where(np.isfinite(err), err, np.inf)


def _finish(
    transform: Transform,
    model: str,
    src: PointArray,
    dst: PointArray,
    condition: float,
) -> EstimationResult:
    res = transfer_residuals(transform, src, dst)
    finite = res[np.isfinite(res)]
    return EstimationResult(
        transform=transform,
        model=model,
        n_points=src.shape[0],
        residuals=res,
        rmse=float(np.sqrt((finite**2).mean())) if finite.size else float("inf"),
        median_error=float(np.median(finite)) if finite.size else float("inf"),
        condition=condition,
        degenerate=condition > CONDITION_WARN,
        reason=f"ill-conditioned solve (cond={condition:.3g})"
        if condition > CONDITION_WARN
        else "",
    )


def _check_inputs(
    src: ArrayLike, dst: ArrayLike, model: str
) -> tuple[PointArray, PointArray] | EstimationResult:
    p, q = as_points(src), as_points(dst)
    if p.shape != q.shape:
        raise ValueError(f"src and dst must have equal shape; got {p.shape} vs {q.shape}")
    n = p.shape[0]
    need = MODEL_MIN_POINTS[model]
    if n < need:
        return _failed(model, n, f"need >= {need} correspondences for {model}, got {n}")
    if not (np.isfinite(p).all() and np.isfinite(q).all()):
        return _failed(model, n, "non-finite coordinates in correspondences")
    return p, q


# -- individual estimators ----------------------------------------------


def estimate_translation(src: ArrayLike, dst: ArrayLike) -> EstimationResult:
    """Least-squares translation: the mean displacement."""
    checked = _check_inputs(src, dst, "translation")
    if isinstance(checked, EstimationResult):
        return checked
    p, q = checked
    t = (q - p).mean(axis=0)
    m = np.eye(3, dtype=np.float64)
    m[0, 2], m[1, 2] = t[0], t[1]
    return _finish(Transform(m, "translation"), "translation", p, q, 1.0)


def _umeyama(p: PointArray, q: PointArray, with_scale: bool) -> NDArray[np.float64]:
    """Closed-form least-squares similarity/rigid fit (Umeyama 1991)."""
    mu_p, mu_q = p.mean(axis=0), q.mean(axis=0)
    dp, dq = p - mu_p, q - mu_q
    var_p = float((dp**2).sum() / p.shape[0])
    cov = (dq.T @ dp) / p.shape[0]
    u, d, vt = np.linalg.svd(cov)
    s = np.eye(2)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        # Reflection is not a rigid motion; flip the least-significant axis.
        s[1, 1] = -1.0
    r = u @ s @ vt
    scale = float((d * np.diag(s)).sum() / var_p) if (with_scale and var_p > 1e-12) else 1.0
    t = mu_q - scale * (r @ mu_p)
    m = np.eye(3, dtype=np.float64)
    m[:2, :2] = scale * r
    m[:2, 2] = t
    return m


def estimate_euclidean(src: ArrayLike, dst: ArrayLike) -> EstimationResult:
    """Least-squares rigid transform (rotation + translation, no scale)."""
    checked = _check_inputs(src, dst, "euclidean")
    if isinstance(checked, EstimationResult):
        return checked
    p, q = checked
    m = _umeyama(p, q, with_scale=False)
    return _finish(Transform(m, "euclidean"), "euclidean", p, q, 1.0)


def estimate_similarity(src: ArrayLike, dst: ArrayLike) -> EstimationResult:
    """Least-squares similarity transform (rotation + isotropic scale + shift)."""
    checked = _check_inputs(src, dst, "similarity")
    if isinstance(checked, EstimationResult):
        return checked
    p, q = checked
    m = _umeyama(p, q, with_scale=True)
    if abs(np.linalg.det(m[:2, :2])) < 1e-15:
        return _failed("similarity", p.shape[0], "degenerate scale (collapsed to a point)")
    return _finish(Transform(m, "similarity"), "similarity", p, q, 1.0)


def estimate_affine(src: ArrayLike, dst: ArrayLike) -> EstimationResult:
    """Least-squares affine fit, Hartley-normalised."""
    checked = _check_inputs(src, dst, "affine")
    if isinstance(checked, EstimationResult):
        return checked
    p, q = checked
    if collinearity(p) < COLLINEARITY_THRESHOLD:
        return _failed(
            "affine",
            p.shape[0],
            f"source points are collinear (spread ratio "
            f"{collinearity(p):.2e}); an affine transform is not determined",
        )
    np_ = _hartley_normalise(p)
    nq_ = _hartley_normalise(q)
    if np_ is None or nq_ is None:
        return _failed("affine", p.shape[0], "point set has zero spread")
    pn, tp = np_
    qn, tq = nq_

    design = np.hstack([pn, np.ones((pn.shape[0], 1))])  # (N, 3)
    sol, *_ = np.linalg.lstsq(design, qn, rcond=None)  # (3, 2)
    cond = float(np.linalg.cond(design))

    m_n = np.eye(3, dtype=np.float64)
    m_n[:2, :3] = sol.T
    m = np.linalg.inv(tq) @ m_n @ tp
    m[2] = [0.0, 0.0, 1.0]  # re-impose exactness after float round-trip
    return _finish(affine(m[:2]), "affine", p, q, cond)


def estimate_projective(src: ArrayLike, dst: ArrayLike) -> EstimationResult:
    """Homography by the normalised DLT."""
    checked = _check_inputs(src, dst, "projective")
    if isinstance(checked, EstimationResult):
        return checked
    p, q = checked
    if collinearity(p) < COLLINEARITY_THRESHOLD:
        return _failed(
            "projective",
            p.shape[0],
            f"source points are collinear (spread ratio "
            f"{collinearity(p):.2e}); a homography is not determined",
        )
    np_ = _hartley_normalise(p)
    nq_ = _hartley_normalise(q)
    if np_ is None or nq_ is None:
        return _failed("projective", p.shape[0], "point set has zero spread")
    pn, tp = np_
    qn, tq = nq_

    n = pn.shape[0]
    x, y = pn[:, 0], pn[:, 1]
    u, v = qn[:, 0], qn[:, 1]
    zero = np.zeros(n)
    one = np.ones(n)
    # Two rows per correspondence, the standard DLT arrangement.
    a = np.empty((2 * n, 9), dtype=np.float64)
    a[0::2] = np.column_stack([-x, -y, -one, zero, zero, zero, u * x, u * y, u])
    a[1::2] = np.column_stack([zero, zero, zero, -x, -y, -one, v * x, v * y, v])

    # full_matrices=False is load-bearing, not a micro-optimisation. The DLT
    # needs only the last row of Vt; the default full SVD also builds U at
    # (2N x 2N), which for N=2115 is a 4230x4230 array of 17.9M elements that
    # is then discarded. Measured: 394.72 ms -> 1.06 ms, a 372x speedup, with
    # singular values and Vt identical (EXP-002 objective 1).
    _, sv, vt = np.linalg.svd(a, full_matrices=False)
    cond = float(sv[0] / sv[-2]) if sv[-2] > 1e-15 else float("inf")
    h_n = vt[-1].reshape(3, 3)

    h = np.linalg.inv(tq) @ h_n @ tp
    if abs(h[2, 2]) < 1e-12:
        return _failed("projective", n, "degenerate homography (h[2,2] ~ 0)")
    h = h / h[2, 2]
    return _finish(projective(h), "projective", p, q, cond)


_ESTIMATORS = {
    "translation": estimate_translation,
    "euclidean": estimate_euclidean,
    "similarity": estimate_similarity,
    "affine": estimate_affine,
    "projective": estimate_projective,
}


def estimate(src: ArrayLike, dst: ArrayLike, model: str) -> EstimationResult:
    """Fit ``model`` to the correspondences. Dispatch entry point."""
    if model not in _ESTIMATORS:
        raise ValueError(f"unknown model {model!r}; expected one of {MODEL_ORDER}")
    return _ESTIMATORS[model](src, dst)
