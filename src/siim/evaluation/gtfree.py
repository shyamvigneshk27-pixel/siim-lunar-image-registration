"""Ground-truth-free quality estimators (ANALYSIS §F.1, ADR-0003).

On real lunar pairs there are no ground-truth correspondences, so the only
accuracy evidence available must be derived from the correspondences and the
images themselves. These four estimators are that evidence.

**None of them may consult ground truth.** GT is used *only* to score how well
they work (EXP-002 objective 4). An estimator that peeked at GT would be
useless in deployment, which is the whole point.

What each one can and cannot see
--------------------------------
This matters more than the implementations, and EXP-002 measures it:

``held_out_residual``
    Fit on some inliers, measure on others. Detects **degenerate
    over-fitting** -- the ``n ~ DOF`` regime where fit RMSE collapses to zero
    (RL-010). Cannot detect a coherent wrong solution: if every match follows
    the same wrong transform, the held-out matches follow it too.

``cycle_consistency``
    Match A->B and independently B->A; the composition should be the identity.
    Detects matcher asymmetry and unstable fits. Also **structurally blind to
    a symmetric wrong solution**: if forward finds +64 px and backward finds
    -64 px, they cancel perfectly.

``loop_closure``
    Compose a cycle over three images. This is the one estimator that *can*
    catch a coherent wrong solution, because a consistent per-edge shift
    accumulates around a loop instead of cancelling. It is the reason
    ANALYSIS §F.1.4 exists.

``spatial_split_consistency``
    Fit the model on two disjoint spatial halves of the inliers and compare
    the resulting maps. Detects transforms that are unconstrained away from
    where the correspondences happen to sit -- the extrapolation risk that
    ADR-0006 is about.

Their blind spots are different, which is the argument for using them
together rather than picking one.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..geometry import (
    Transform,
    as_points,
    endpoint_error,
    estimate,
    identity,
    pixel_grid,
    transfer_residuals,
)
from ..geometry.transforms import MODEL_MIN_POINTS

__all__ = [
    "HeldOutResidual",
    "held_out_residual",
    "cycle_consistency",
    "loop_closure",
    "spatial_split_consistency",
    "compose_cycle",
]


@dataclass(frozen=True)
class HeldOutResidual:
    """K-fold cross-validated residual over the inlier set."""

    median: float
    p90: float
    mean: float
    n_folds: int
    n_points: int
    ok: bool
    reason: str = ""

    def __repr__(self) -> str:  # pragma: no cover - display only
        return (
            f"HeldOutResidual(median={self.median:.3f}px, p90={self.p90:.3f}px, "
            f"n={self.n_points}, folds={self.n_folds}, ok={self.ok})"
        )


def held_out_residual(
    src: ArrayLike,
    dst: ArrayLike,
    model: str = "affine",
    k_folds: int = 5,
    seed: int = 0,
) -> HeldOutResidual:
    """Cross-validated residual: fit on k-1 folds, measure on the held-out one.

    This converts a *fit* residual into a *generalisation* residual, breaking
    the circularity of ANALYSIS §A.3 at negligible compute cost.

    Its main power is against degeneracy. With ``n`` close to the model DOF a
    plain fit interpolates its points and reports ~0 residual (RL-010);
    holding points out removes exactly that freedom, so the residual jumps.
    """
    p, q = as_points(src), as_points(dst)
    n = p.shape[0]
    m = MODEL_MIN_POINTS[model]

    # Each training split must still determine the model, else we measure the
    # splitting rather than the correspondences.
    if n < m + 2:
        return HeldOutResidual(
            float("inf"), float("inf"), float("inf"), 0, n, False,
            f"need >= {m + 2} points for held-out evaluation of {model}, got {n}",
        )
    folds = max(2, min(k_folds, n // max(m, 1)))
    if folds < 2:
        return HeldOutResidual(
            float("inf"), float("inf"), float("inf"), 0, n, False,
            "too few points to form two folds",
        )

    rng = np.random.default_rng(seed)
    order = rng.permutation(n)
    residuals: list[NDArray[np.float64]] = []

    for f in range(folds):
        test_idx = order[f::folds]
        train_idx = np.setdiff1d(order, test_idx, assume_unique=False)
        if train_idx.size < m or test_idx.size == 0:
            continue
        res = estimate(p[train_idx], q[train_idx], model)
        if not res.ok:
            continue
        residuals.append(transfer_residuals(res.transform, p[test_idx], q[test_idx]))

    if not residuals:
        return HeldOutResidual(
            float("inf"), float("inf"), float("inf"), folds, n, False,
            "no fold produced a valid fit",
        )

    all_res = np.concatenate(residuals)
    finite = all_res[np.isfinite(all_res)]
    if finite.size == 0:
        return HeldOutResidual(
            float("inf"), float("inf"), float("inf"), folds, n, False,
            "all held-out residuals non-finite",
        )
    return HeldOutResidual(
        median=float(np.median(finite)),
        p90=float(np.percentile(finite, 90)),
        mean=float(finite.mean()),
        n_folds=folds,
        n_points=n,
        ok=True,
    )


def compose_cycle(transforms: list[Transform]) -> Transform:
    """Compose a list of transforms in order: ``T[-1] o ... o T[0]``."""
    if not transforms:
        raise ValueError("compose_cycle needs at least one transform")
    out = transforms[0]
    for t in transforms[1:]:
        out = t @ out
    return out


def cycle_consistency(
    forward: Transform | None,
    backward: Transform | None,
    shape: tuple[int, int],
    step: int = 16,
) -> float:
    """Deviation of ``backward o forward`` from the identity, in pixels.

    ``forward`` maps A->B and ``backward`` maps B->A, each estimated by an
    independent run of the pipeline. Returns the median displacement of a grid
    of points under the round trip.

    **Known blind spot:** a wrong solution that is symmetric under reversal
    (forward +64 px, backward -64 px) cancels exactly and scores zero. EXP-002
    measures how often that happens rather than assuming it away.
    """
    if forward is None or backward is None:
        return float("inf")
    err = endpoint_error(compose_cycle([forward, backward]), identity(), shape, step=step)
    return err.median


def loop_closure(
    transforms: list[Transform | None],
    shape: tuple[int, int],
    step: int = 16,
) -> float:
    """Deviation of a composed transform cycle from the identity, in pixels.

    For three overlapping images, ``T_CA o T_BC o T_AB`` should be the
    identity. The deviation is a **ground-truth-free accuracy bound**.

    This is the estimator that can catch the coherent wrong solution of
    ANALYSIS §B6: a shift of one crater period on each edge accumulates to
    three periods around the loop, instead of cancelling as it does under a
    simple forward/backward cycle.
    """
    if any(t is None for t in transforms):
        return float("inf")
    composed = compose_cycle([t for t in transforms if t is not None])
    return endpoint_error(composed, identity(), shape, step=step).median


def spatial_split_consistency(
    src: ArrayLike,
    dst: ArrayLike,
    model: str = "affine",
    shape: tuple[int, int] = (512, 512),
    step: int = 16,
    seed: int = 0,
) -> float:
    """Disagreement between models fitted to two disjoint spatial halves.

    The inliers are split by their median x (falling back to y if that split
    is degenerate), a model is fitted to each half, and the two maps are
    compared over the whole image grid.

    High disagreement means the transform is only pinned down where the
    correspondences are, and is extrapolating elsewhere -- precisely the
    failure that ``max_uncovered_disc_radius`` bounds (ADR-0006). Unlike a
    random split, a *spatial* split probes extrapolation rather than noise.
    """
    p, q = as_points(src), as_points(dst)
    n = p.shape[0]
    m = MODEL_MIN_POINTS[model]
    if n < 2 * (m + 1):
        return float("inf")

    for axis in (0, 1):  # try x, then y
        pivot = np.median(p[:, axis])
        left = p[:, axis] <= pivot
        right = ~left
        if left.sum() < m + 1 or right.sum() < m + 1:
            continue
        res_l = estimate(p[left], q[left], model)
        res_r = estimate(p[right], q[right], model)
        if not (res_l.ok and res_r.ok):
            continue
        return endpoint_error(res_l.transform, res_r.transform, shape, step=step).median

    return float("inf")
