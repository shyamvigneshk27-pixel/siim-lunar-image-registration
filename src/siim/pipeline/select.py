"""Transform-model selection by held-out evidence (EXP-011, rule B).

The rule, exactly as pre-registered in EXP-011 Part 1 section 4.3 and
clarified in Part 2:

    Fit every candidate model on k-1 folds of the correspondences and score it
    by the median residual on the held-out fold. Choose the SIMPLEST model
    whose held-out median is within 10 % of the best one, with an absolute tie
    floor of 0.005 px so that an exact self-warp (where every model scores
    ~1e-9) is not decided by rounding noise.

Why the input matters more than the rule
----------------------------------------
EXP-011 measured that the held-out residuals of the translation and affine
models on frame D's raw RANSAC inliers are 0.0338 and 0.0336 px -- the
correspondence set cannot see the correlated localisation bias the affine
model absorbs (E-034). The rule picked the right model there only through its
simplicity preference. Selection on REFINED points (``siim.refinement``) is
what makes the evidence, not the tie-break, do the choosing: 48/48 correct
models at 0.0018 px dense error against 0.0975 px for the affine default.

This module re-states the rule for the deliverable pipeline; the experiment
runner ``scripts/run_exp011.py`` keeps its own copy, and a test pins the two
to identical selections so the pipeline cannot drift from the artefact that
justifies it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from ..evaluation.gtfree import held_out_residual
from ..geometry import estimate
from ..geometry.transforms import MODEL_MIN_POINTS, Transform

__all__ = ["MODELS", "ModelSelection", "select_model", "reestimate"]

#: Candidate models, simplest first. Euclidean is omitted, as in EXP-011: a
#: near-nadir pair with any resolution ratio needs the similarity's scale, and
#: the four kept models span the DOF ladder 2 / 4 / 6 / 8.
MODELS: tuple[str, ...] = ("translation", "similarity", "affine", "projective")
COMPLEXITY = {m: i for i, m in enumerate(MODELS)}
#: "simplest model within 10 % of the best" (EXP-011 Part 1 section 4.3).
WITHIN = 0.10
#: Absolute tie floor (EXP-011 Part 2, implementation clarification).
TIE_FLOOR_PX = 0.005
#: Held-out needs each training fold to still determine the most general
#: model; below this many points the rule is not applied at all.
MIN_POINTS = 12


@dataclass(frozen=True)
class ModelSelection:
    """Which model was chosen, from what evidence."""

    model: str
    #: Held-out median residual per candidate, in reference pixels. ``inf``
    #: where the fit failed.
    heldout_px: dict[str, float]
    #: Candidates inside the tolerance band; the chosen one is the simplest.
    candidates: tuple[str, ...]
    #: True when more than one candidate lay inside the band, i.e. the
    #: simplicity tie-break, not the evidence, made the choice.
    decided_by_tie_break: bool
    n_points: int


def select_model(src: ArrayLike, dst: ArrayLike, *, seed: int = 0,
                 models: tuple[str, ...] = MODELS) -> ModelSelection:
    """Rule B core: simplest model within ``WITHIN`` of the best held-out median."""
    p = np.asarray(src, float).reshape(-1, 2)
    q = np.asarray(dst, float).reshape(-1, 2)
    n = p.shape[0]
    if n < MIN_POINTS:
        raise ValueError(f"model selection needs >= {MIN_POINTS} correspondences, got {n}")
    scores: dict[str, float] = {}
    for m in models:
        r = held_out_residual(p, q, model=m, k_folds=5, seed=seed)
        scores[m] = float(r.median) if r.ok and np.isfinite(r.median) else float("inf")
    best = min(scores.values())
    if not np.isfinite(best):
        raise ValueError("no candidate model produced a finite held-out residual")
    band = max(best * (1 + WITHIN), best + TIE_FLOOR_PX)
    cands = tuple(m for m in models if scores[m] <= band)
    chosen = min(cands, key=lambda m: COMPLEXITY[m])
    return ModelSelection(model=chosen, heldout_px=scores, candidates=cands,
                          decided_by_tie_break=len(cands) > 1, n_points=n)


def reestimate(src: ArrayLike, dst: ArrayLike, model: str) -> Transform:
    """Least-squares re-estimate of ``model`` from (refined) correspondences."""
    p = np.asarray(src, float).reshape(-1, 2)
    q = np.asarray(dst, float).reshape(-1, 2)
    if p.shape[0] < MODEL_MIN_POINTS[model]:
        raise ValueError(f"{model} needs >= {MODEL_MIN_POINTS[model]} points, got {p.shape[0]}")
    res = estimate(p, q, model)
    if not res.ok or res.transform is None:
        raise ValueError(f"re-estimation of {model} failed: {res.reason}")
    return res.transform
