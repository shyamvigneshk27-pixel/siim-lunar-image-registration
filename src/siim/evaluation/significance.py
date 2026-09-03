"""Exact significance for a small-n separation claim, and what it would take to fix it.

Why this module exists
----------------------
The project's central real-data claim is that registration outcome tracks
Δincidence: across the measured edges every success sits below every failure.
That separation was **reported as a fact and never given a p-value**, and with
six edges the omission is not cosmetic.

Two successes and four failures. Under the null hypothesis that outcome is
independent of Δincidence, the two successes are a uniformly random 2-subset
of the six edges. There are ``C(6, 2) = 15`` such subsets and exactly one puts
both successes below every failure, so

    p = 1 / 15 = 0.0667

which does **not** reach the conventional 0.05. The claim as currently written
in the README -- "Δincidence separates all six edges", "frame identity predicts
nothing" -- reads as an established effect, and any reviewer will compute this
number in under a minute.

What rescues it, and what does not
----------------------------------
**One-tailed is legitimate here.** The direction was fixed in a decision table
frozen before frame D was acquired, which is exactly the condition under which
a directional test is admissible. Pre-registration is what keeps this an honest
0.0667 rather than a meaningless one -- but it does not change *n*.

**One more edge is enough, and it does not have to be the hard one.** The
planning function below reports what this project's own history obscured:
adding a single *failing* edge takes ``C(7, 2) = 21``, so ``p = 0.0476``.
REAL-DATA-05 spent an entire stage hunting a second low-incidence frame and
returned zero admissible candidates -- while a high-incidence frame, which the
archive supplies in abundance, would have discharged the significance problem
just as well. That is a live, actionable consequence, not a retrospective
complaint.

The caveat that makes the number optimistic
-------------------------------------------
The six edges are **not independent**: five frames generate them, several
frames appear in multiple edges, and one frame pair (A→B) appears twice at
different ground windows. Permuting at the edge level therefore assumes more
independence than the data has, so the true p is **at least** what this module
reports. It is a lower bound, and it is reported as one. A frame-level
permutation would be the honest refinement and needs a design with more frames
than five to be worth doing.

This module computes; it does not decide. It takes recorded outcomes and
returns a number with its assumptions attached.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb, isnan
from typing import Iterable, Sequence

import numpy as np

__all__ = [
    "SeparationTest",
    "AdditionalEvidence",
    "exact_separation_test",
    "minimum_additional_edges",
]

#: Above this many label assignments, enumerate by sampling rather than
#: exhaustively. Six edges give 15, so the real case is always exact; the cap
#: exists so the function stays usable if the edge set grows.
_MAX_EXACT_ASSIGNMENTS = 2_000_000


@dataclass(frozen=True)
class SeparationTest:
    """The result of testing whether a predictor separates two outcome classes."""

    #: Mann-Whitney U for the directional hypothesis, counting ties as 0.5.
    statistic: float
    #: Largest value U could take -- ``n_low * n_high``. Reached iff separation
    #: is perfect and untied.
    statistic_max: int
    #: One-tailed exact p-value. A LOWER BOUND when observations share frames.
    p_value: float
    n_total: int
    n_low_group: int
    n_high_group: int
    perfectly_separated: bool
    #: True when every assignment was enumerated; False when sampled.
    exact: bool
    n_assignments: int
    #: Stated rather than implied, because this is the field a reader needs.
    assumptions: tuple[str, ...] = ()

    def __repr__(self) -> str:  # pragma: no cover - display only
        kind = "exact" if self.exact else "sampled"
        return (
            f"SeparationTest(U={self.statistic:g}/{self.statistic_max}, "
            f"p={self.p_value:.4g} ({kind}, one-tailed), "
            f"n={self.n_low_group}+{self.n_high_group}, "
            f"separated={self.perfectly_separated})"
        )


@dataclass(frozen=True)
class AdditionalEvidence:
    """How many more observations reach a target significance level."""

    target_alpha: float
    current_p: float
    #: Extra observations in the low-value class (here: successes).
    extra_low: int
    #: Extra observations in the high-value class (here: failures).
    extra_high: int
    resulting_p: float
    #: Every single-class route that works, cheapest first.
    routes: tuple[tuple[int, int, float], ...] = ()

    def __repr__(self) -> str:  # pragma: no cover - display only
        return (
            f"AdditionalEvidence(alpha={self.target_alpha}, "
            f"+{self.extra_low} low / +{self.extra_high} high -> "
            f"p={self.resulting_p:.4g})"
        )


def _mann_whitney_u(low_values: np.ndarray, high_values: np.ndarray) -> float:
    """Count (low, high) pairs ordered as the hypothesis predicts; ties score 0.5."""
    diff = high_values[None, :] - low_values[:, None]
    return float((diff > 0).sum() + 0.5 * (diff == 0).sum())


def exact_separation_test(
    values: Sequence[float],
    is_low_group: Sequence[bool],
    *,
    seed: int = 0,
    n_samples: int = 200_000,
) -> SeparationTest:
    """Exact one-tailed permutation test that ``is_low_group`` marks low ``values``.

    Parameters
    ----------
    values
        The predictor, one per observation -- for this project, Δincidence per
        edge.
    is_low_group
        ``True`` for observations the directional hypothesis predicts will sit
        at the low end. For the illumination claim that is the *succeeding*
        edges: the pre-registered prediction is that successes have small
        Δincidence.

    Notes
    -----
    The null is that the labels are exchangeable across observations, so every
    assignment of ``k`` low-group labels to ``n`` observations is equally
    likely. The p-value is the fraction of assignments whose U is at least the
    observed U.

    **One-tailed only.** This function does not offer a two-tailed variant,
    because using it on a hypothesis whose direction was not fixed in advance
    would be exactly the misuse it exists to prevent. If the direction was not
    pre-registered, this number does not apply.

    The returned p-value is a **lower bound** whenever observations share
    structure -- as these edges do, being generated by five frames. That
    caveat is attached to the result rather than left to the caller's memory.
    """
    v = np.asarray(values, dtype=np.float64)
    labels = np.asarray(is_low_group, dtype=bool)
    if v.shape != labels.shape or v.ndim != 1:
        raise ValueError("values and is_low_group must be 1-D and the same length")
    if v.size == 0:
        raise ValueError("no observations")
    if not np.isfinite(v).all():
        raise ValueError("values contain non-finite entries")

    n = int(v.size)
    k = int(labels.sum())
    if k == 0 or k == n:
        raise ValueError(
            "both outcome classes must be non-empty; a separation test on a "
            "single class is not defined"
        )

    observed = _mann_whitney_u(v[labels], v[~labels])
    u_max = k * (n - k)
    total = comb(n, k)

    idx = np.arange(n)
    if total <= _MAX_EXACT_ASSIGNMENTS:
        at_least = 0
        for pick in combinations(range(n), k):
            mask = np.zeros(n, dtype=bool)
            mask[list(pick)] = True
            if _mann_whitney_u(v[mask], v[~mask]) >= observed:
                at_least += 1
        p = at_least / total
        exact, n_assign = True, total
    else:  # pragma: no cover - only for edge sets far larger than this project's
        rng = np.random.default_rng(seed)
        at_least = 0
        for _ in range(n_samples):
            mask = np.zeros(n, dtype=bool)
            mask[rng.choice(idx, size=k, replace=False)] = True
            if _mann_whitney_u(v[mask], v[~mask]) >= observed:
                at_least += 1
        p = (at_least + 1) / (n_samples + 1)  # never report exactly zero
        exact, n_assign = False, n_samples

    return SeparationTest(
        statistic=observed,
        statistic_max=u_max,
        p_value=p,
        n_total=n,
        n_low_group=k,
        n_high_group=n - k,
        perfectly_separated=bool(observed == u_max and u_max > 0),
        exact=exact,
        n_assignments=n_assign,
        assumptions=(
            "One-tailed: valid only because the direction was pre-registered.",
            "Observations assumed exchangeable. Edges sharing frames are not, "
            "so this p-value is a LOWER BOUND on the true one.",
            "No correction for the outcome threshold having been chosen on "
            "earlier data; the frozen decision table is what makes that "
            "defensible rather than the arithmetic.",
        ),
    )


def minimum_additional_edges(
    n_low_group: int,
    n_high_group: int,
    *,
    target_alpha: float = 0.05,
    max_extra: int = 40,
) -> AdditionalEvidence:
    """Smallest number of further observations that reach ``target_alpha``.

    Assumes perfect separation continues to hold -- which is the pre-registered
    prediction, and which the new observations genuinely risk falsifying. An
    edge added in the expectation that it will fail, that instead succeeds,
    damages the hypothesis. That is what makes this planning rather than
    fishing.

    Under continued perfect separation the p-value is ``1 / C(n, k)``, so this
    is a search over how to grow ``n`` and ``k`` most cheaply. It reports the
    overall minimum **and** every single-class route, because the two classes
    are not equally expensive to obtain: this project's own history shows that
    low-incidence frames over shared ground are scarce (REAL-DATA-05 screened
    906 archive products and found none admissible) while high-incidence ones
    are not.
    """
    if n_low_group < 1 or n_high_group < 1:
        raise ValueError("both classes must already have at least one observation")
    if not 0.0 < target_alpha < 1.0:
        raise ValueError("target_alpha must lie in (0, 1)")

    def p_for(k: int, m: int) -> float:
        return 1.0 / comb(k + m, k)

    current = p_for(n_low_group, n_high_group)

    best: tuple[int, int, float] | None = None
    routes: list[tuple[int, int, float]] = []
    for extra in range(0, max_extra + 1):
        for a in range(extra + 1):
            b = extra - a
            p = p_for(n_low_group + a, n_high_group + b)
            if p <= target_alpha:
                if best is None:
                    best = (a, b, p)
                if a == 0 or b == 0:
                    routes.append((a, b, p))
        if best is not None and routes:
            break

    if best is None:  # pragma: no cover - unreachable for sane alphas
        raise ValueError(f"target_alpha={target_alpha} unreachable within {max_extra} extra")

    routes.sort(key=lambda r: (r[0] + r[1], r[2]))
    return AdditionalEvidence(
        target_alpha=target_alpha,
        current_p=current,
        extra_low=best[0],
        extra_high=best[1],
        resulting_p=best[2],
        routes=tuple(routes),
    )


def summarise(
    values: Iterable[float],
    is_low_group: Iterable[bool],
    *,
    target_alpha: float = 0.05,
) -> dict:
    """A JSON-serialisable record: the test, the plan, and the caveats.

    Written for an artefact file rather than for a print statement, so the
    number a document quotes can be traced to a run.
    """
    v = list(values)
    labels = list(is_low_group)
    test = exact_separation_test(v, labels)
    plan = minimum_additional_edges(
        test.n_low_group, test.n_high_group, target_alpha=target_alpha
    )
    return {
        "test": {
            "statistic_u": test.statistic,
            "statistic_max": test.statistic_max,
            "p_value_one_tailed": test.p_value,
            "p_value_is_lower_bound": True,
            "exact": test.exact,
            "n_assignments_enumerated": test.n_assignments,
            "n_total": test.n_total,
            "n_low_group": test.n_low_group,
            "n_high_group": test.n_high_group,
            "perfectly_separated": test.perfectly_separated,
            "significant_at": {
                "0.05": bool(test.p_value <= 0.05),
                "0.01": bool(test.p_value <= 0.01),
            },
            "assumptions": list(test.assumptions),
        },
        "to_reach_alpha": {
            "target_alpha": plan.target_alpha,
            "current_p": plan.current_p,
            "cheapest_extra_low_group": plan.extra_low,
            "cheapest_extra_high_group": plan.extra_high,
            "resulting_p": plan.resulting_p,
            "single_class_routes": [
                {"extra_low_group": a, "extra_high_group": b, "resulting_p": p}
                for a, b, p in plan.routes
            ],
        },
    }
