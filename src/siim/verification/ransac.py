"""Robust transform estimation by LO-RANSAC.

Implemented here rather than taken from OpenCV for two reasons. It works
against our own estimators, so every model in ``MODEL_ORDER`` is supported
uniformly and model selection (EXP-009) has a level playing field. And it
keeps the geometry stack free of OpenCV conventions (ADR-0007), so the
coordinate contract has exactly one definition.

A warning that this module cannot fix
-------------------------------------
RANSAC reports an **inlier ratio**: the fraction of putative matches
consistent with the model it found. That number is routinely quoted as a
quality measure, and it is not one. RANSAC maximises consensus; if the
correspondences contain a large, mutually consistent *wrong* subset -- which
is exactly what repetitive crater terrain produces (ANALYSIS §B6) -- then
RANSAC will find it and report a high inlier ratio with total confidence.

The inlier ratio measures self-consistency, never correctness. Nothing inside
this module can distinguish the two. Detecting that failure requires evidence
from outside the fit: ground truth, held-out residuals, cycle consistency or
loop closure (``siim.evaluation.gtfree``, ANALYSIS §F.1).

Local optimisation
------------------
LO is run **only when a new best model is found**, which is the published
LO-RANSAC of Chum, Matas & Kittler (2003). EXP-001 shipped a version that ran
LO on *every* sample whose consensus exceeded the minimal set; combined with a
separate SVD defect that cost 59 s on a single projective case. Both are fixed
and pinned by ``tests/test_ransac_performance.py``. See EXP-002 objective 1.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..geometry import Transform, as_points, estimate, transfer_residuals
from ..geometry.transforms import MODEL_MIN_POINTS, MODEL_ORDER

__all__ = ["RansacResult", "RansacTiming", "ransac"]


@dataclass(frozen=True)
class RansacTiming:
    """Per-stage wall time, in seconds (spec §37).

    Broken out because "RANSAC is slow" is not a diagnosis. EXP-001's 59 s
    outlier was invisible until the refit stage was measured separately from
    sampling and scoring.
    """

    sampling: float = 0.0
    minimal_fit: float = 0.0
    scoring: float = 0.0
    local_optimisation: float = 0.0
    final_fit: float = 0.0
    total: float = 0.0

    #: How many large-consensus refits were performed. The quantity that blew
    #: up in EXP-001; cheap to record and immediately diagnostic.
    n_lo_refits: int = 0
    n_minimal_fits: int = 0

    def as_dict(self) -> dict[str, float]:
        return {
            "sampling_s": self.sampling,
            "minimal_fit_s": self.minimal_fit,
            "scoring_s": self.scoring,
            "local_optimisation_s": self.local_optimisation,
            "final_fit_s": self.final_fit,
            "total_s": self.total,
            "n_lo_refits": float(self.n_lo_refits),
            "n_minimal_fits": float(self.n_minimal_fits),
        }


@dataclass(frozen=True)
class RansacResult:
    """Outcome of a robust fit."""

    transform: Transform | None
    model: str
    inlier_mask: NDArray[np.bool_] = field(default_factory=lambda: np.zeros(0, bool))
    n_inliers: int = 0
    #: Fraction of putative matches consistent with the model.
    #: SELF-CONSISTENCY, NOT CORRECTNESS -- see the module docstring.
    inlier_ratio: float = 0.0
    #: Fit residuals of the inliers (circular; not an accuracy -- ANALYSIS §A.3).
    #: Uninterpretable without ``n_inliers``: as n approaches the model DOF the
    #: fit interpolates exactly and this goes to zero (ADR-0003, RL-010).
    inlier_rmse: float = float("nan")
    iterations: int = 0
    success: bool = False
    reason: str = ""
    timing: RansacTiming = field(default_factory=RansacTiming)

    def __repr__(self) -> str:  # pragma: no cover - display only
        return (
            f"RansacResult(model={self.model!r}, inliers={self.n_inliers}, "
            f"ratio={self.inlier_ratio:.3f}, fit_rmse={self.inlier_rmse:.3f}, "
            f"iters={self.iterations}, success={self.success}"
            + (f", reason={self.reason!r}" if self.reason else "")
            + ")"
        )


def _required_iterations(
    inlier_ratio: float, sample_size: int, confidence: float, cap: int
) -> int:
    """Adaptive stopping rule: iterations needed to see one clean sample."""
    if inlier_ratio <= 0.0:
        return cap
    p_clean = inlier_ratio**sample_size
    if p_clean >= 1.0:
        return 1
    denom = math.log(max(1.0 - p_clean, 1e-12))
    return min(cap, int(math.ceil(math.log(max(1.0 - confidence, 1e-12)) / denom)))


def ransac(
    src: ArrayLike,
    dst: ArrayLike,
    model: str = "affine",
    threshold: float = 3.0,
    confidence: float = 0.999,
    max_iterations: int = 10_000,
    min_iterations: int = 100,
    seed: int | None = 0,
    local_optimization: bool = True,
    lo_rounds: int = 4,
    lo_max_points: int = 1000,
) -> RansacResult:
    """Fit ``model`` robustly to putative correspondences.

    Parameters
    ----------
    threshold
        Inlier distance in reference pixels. This is a **protocol parameter**,
        and the SAR-optical benchmark (sources.md S4) found protocol
        parameters can move mean error by up to 33x -- so it is a variable to
        be swept in EXP-006, never a constant to be hardcoded.
    local_optimization
        Refit on the consensus set and re-score whenever a **new best** model
        is found (Chum et al. 2003). LO-RANSAC converges in far fewer samples
        than plain RANSAC and yields a markedly more stable model.
    lo_max_points
        Cap on the consensus subsample used for an LO refit. Above this many
        inliers a uniform random subsample is used instead of the full set.
        This bounds refit cost without weakening the robustness criterion:
        **scoring is always done against every correspondence**, so the
        consensus set that decides the winner is never subsampled -- only the
        least-squares refit that proposes a candidate is. A 1000-point
        least-squares fit is already vastly over-determined for a model with
        at most 8 DOF, so the estimate is not measurably degraded (verified in
        ``test_lo_subsampling_does_not_degrade_accuracy``).
    """
    if model not in MODEL_ORDER:
        raise ValueError(f"unknown model {model!r}; expected one of {MODEL_ORDER}")
    p, q = as_points(src), as_points(dst)
    if p.shape != q.shape:
        raise ValueError(f"src and dst must have equal shape; got {p.shape} vs {q.shape}")

    t_start = time.perf_counter()
    t_sample = t_minimal = t_score = t_lo = t_final = 0.0
    n_lo_refits = n_minimal_fits = 0

    n = p.shape[0]
    m = MODEL_MIN_POINTS[model]
    if n < m:
        return RansacResult(
            None, model, np.zeros(n, bool), reason=f"need >= {m} matches, got {n}"
        )

    rng = np.random.default_rng(seed)
    best_mask = np.zeros(n, bool)
    best_count = 0
    best_tf: Transform | None = None

    iters = 0
    budget = max(min_iterations, 1)
    while iters < budget and iters < max_iterations:
        iters += 1

        t0 = time.perf_counter()
        idx = rng.choice(n, size=m, replace=False)
        t_sample += time.perf_counter() - t0

        t0 = time.perf_counter()
        res = estimate(p[idx], q[idx], model)
        t_minimal += time.perf_counter() - t0
        n_minimal_fits += 1
        if not res.ok:
            continue  # degenerate minimal sample; a normal event, not an error

        t0 = time.perf_counter()
        mask = transfer_residuals(res.transform, p, q) <= threshold
        count = int(mask.sum())
        t_score += time.perf_counter() - t0

        if count <= best_count:
            continue  # not a new best: no LO, per Chum et al. (2003)

        cand_tf, cand_mask, cand_count = res.transform, mask, count

        if local_optimization and count > m:
            t0 = time.perf_counter()
            lo_tf, lo_mask, lo_count = res.transform, mask, count
            for _ in range(lo_rounds):
                fit_idx = np.flatnonzero(lo_mask)
                if fit_idx.size > lo_max_points:
                    fit_idx = rng.choice(fit_idx, size=lo_max_points, replace=False)
                lo_res = estimate(p[fit_idx], q[fit_idx], model)
                n_lo_refits += 1
                if not lo_res.ok:
                    break
                # Scoring is always against ALL correspondences.
                new_mask = transfer_residuals(lo_res.transform, p, q) <= threshold
                new_count = int(new_mask.sum())
                if new_count <= lo_count:
                    break
                lo_tf, lo_mask, lo_count = lo_res.transform, new_mask, new_count
            if lo_count > cand_count:
                cand_tf, cand_mask, cand_count = lo_tf, lo_mask, lo_count
            t_lo += time.perf_counter() - t0

        best_count, best_mask, best_tf = cand_count, cand_mask, cand_tf
        budget = max(
            min_iterations,
            _required_iterations(best_count / n, m, confidence, max_iterations),
        )

    if best_tf is None or best_count < m:
        return RansacResult(
            None,
            model,
            np.zeros(n, bool),
            iterations=iters,
            reason="no model reached the minimum consensus",
            timing=RansacTiming(
                sampling=t_sample, minimal_fit=t_minimal, scoring=t_score,
                local_optimisation=t_lo, total=time.perf_counter() - t_start,
                n_lo_refits=n_lo_refits, n_minimal_fits=n_minimal_fits,
            ),
        )

    # Final refit on the full consensus set -- not subsampled: this is the
    # estimate that ships, and it is computed once.
    t0 = time.perf_counter()
    final = estimate(p[best_mask], q[best_mask], model)
    if final.ok:
        final_mask = transfer_residuals(final.transform, p, q) <= threshold
        if int(final_mask.sum()) >= best_count:
            best_tf, best_mask = final.transform, final_mask
            best_count = int(final_mask.sum())
    t_final = time.perf_counter() - t0

    resid = transfer_residuals(best_tf, p[best_mask], q[best_mask])
    finite = resid[np.isfinite(resid)]
    return RansacResult(
        transform=best_tf,
        model=model,
        inlier_mask=best_mask,
        n_inliers=best_count,
        inlier_ratio=best_count / n,
        inlier_rmse=float(np.sqrt((finite**2).mean())) if finite.size else float("inf"),
        iterations=iters,
        success=True,
        timing=RansacTiming(
            sampling=t_sample, minimal_fit=t_minimal, scoring=t_score,
            local_optimisation=t_lo, final_fit=t_final,
            total=time.perf_counter() - t_start,
            n_lo_refits=n_lo_refits, n_minimal_fits=n_minimal_fits,
        ),
    )
