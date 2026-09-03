"""Exact significance of the Δincidence separation claim.

The tests that matter here are the two that pin real numbers:
``test_the_six_real_edges_do_not_reach_alpha_0_05`` fixes the project's actual
p-value at 0.0667, and ``test_one_more_failing_edge_is_enough`` fixes the
cheapest route out. If either changes, a documented claim has to change with
it.
"""

from __future__ import annotations

import math

import pytest

from siim.evaluation.significance import (
    exact_separation_test,
    minimum_additional_edges,
    summarise,
)

#: The six measured real edges, as recorded across REAL-DATA-03 and -04.
#: (label, Δincidence in degrees, outcome)
REAL_EDGES = [
    ("B->C", 0.96, "SUCCEED"),
    ("D->A", 11.73, "SUCCEED"),
    ("C->A", 38.85, "FAIL"),
    ("A->B rd03", 39.81, "FAIL"),
    ("A->B rd04", 39.81, "FAIL"),
    ("B->D", 51.54, "FAIL"),
]

_VALUES = [e[1] for e in REAL_EDGES]
_IS_SUCCESS = [e[2] == "SUCCEED" for e in REAL_EDGES]


# --------------------------------------------------------------------------
# the project's own numbers
# --------------------------------------------------------------------------


def test_the_six_real_edges_do_not_reach_alpha_0_05():
    """p = 1/15 = 0.0667. The separation is real and not yet significant.

    Both facts matter. The successes genuinely are the two lowest Δincidence --
    the separation is perfect, U hits its maximum -- and with n = 6 that is
    still what chance produces once in fifteen.
    """
    t = exact_separation_test(_VALUES, _IS_SUCCESS)
    assert t.perfectly_separated
    assert t.statistic == t.statistic_max == 8
    assert t.exact and t.n_assignments == 15
    assert t.p_value == pytest.approx(1 / 15)
    assert t.p_value > 0.05, "if this ever passes, the README may state significance"


def test_one_more_failing_edge_is_enough():
    """The cheapest route to α = 0.05 is a *failing* edge, not a succeeding one.

    This is the finding the project's history obscured. REAL-DATA-05 screened
    906 archive products for a second low-incidence frame and found none
    admissible -- while one more high-incidence edge, which the archive
    supplies readily, reaches p = 0.0476.
    """
    plan = minimum_additional_edges(2, 4, target_alpha=0.05)
    assert (plan.extra_low, plan.extra_high) == (0, 1)
    assert plan.resulting_p == pytest.approx(1 / 21)
    assert plan.resulting_p <= 0.05

    routes = {(a, b): p for a, b, p in plan.routes}
    assert routes[(0, 1)] == pytest.approx(1 / 21)
    assert routes[(1, 0)] == pytest.approx(1 / 35)


def test_reaching_alpha_0_01_needs_substantially_more():
    """Three more successes, or two successes and a failure. Not a small ask."""
    plan = minimum_additional_edges(2, 4, target_alpha=0.01)
    assert plan.resulting_p <= 0.01
    assert plan.extra_low + plan.extra_high >= 3


def test_summary_record_is_serialisable_and_flags_the_lower_bound():
    import json

    rec = summarise(_VALUES, _IS_SUCCESS)
    json.dumps(rec)  # must not raise
    assert rec["test"]["p_value_is_lower_bound"] is True
    assert rec["test"]["significant_at"]["0.05"] is False
    assert any("LOWER BOUND" in a for a in rec["test"]["assumptions"])


# --------------------------------------------------------------------------
# the test itself
# --------------------------------------------------------------------------


def test_perfect_separation_gives_one_over_n_choose_k():
    for n, k in [(6, 2), (7, 2), (7, 3), (10, 4)]:
        values = list(range(n))
        low = [i < k for i in range(n)]
        t = exact_separation_test(values, low)
        assert t.perfectly_separated
        assert t.p_value == pytest.approx(1 / math.comb(n, k))


def test_no_separation_is_not_significant():
    """Interleaved classes must produce a p-value near chance."""
    values = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    low = [True, False, True, False, True, False]
    t = exact_separation_test(values, low)
    assert not t.perfectly_separated
    assert t.p_value > 0.2


def test_reversed_direction_is_maximally_unsurprising():
    """Labelling the *highest* values as the low group must give p ~ 1.

    A one-tailed test pointed the wrong way should report no evidence, not a
    small number. This is the guard against reading the statistic backwards.
    """
    values = [0.0, 1.0, 2.0, 3.0]
    low = [False, False, True, True]
    t = exact_separation_test(values, low)
    assert t.statistic == 0
    assert t.p_value == pytest.approx(1.0)


def test_ties_are_scored_as_half_not_as_evidence():
    values = [1.0, 1.0, 1.0, 1.0]
    low = [True, True, False, False]
    t = exact_separation_test(values, low)
    assert t.statistic == pytest.approx(2.0)  # 4 pairs x 0.5
    assert t.p_value == pytest.approx(1.0)


def test_the_real_edges_contain_a_genuine_tie():
    """Both A->B edges sit at 39.81°. The tie must not be silently dropped."""
    assert _VALUES.count(39.81) == 2
    t = exact_separation_test(_VALUES, _IS_SUCCESS)
    # The tie is between two same-class observations, so U is unaffected.
    assert t.statistic == 8


# --------------------------------------------------------------------------
# refusals
# --------------------------------------------------------------------------


def test_single_class_is_refused():
    with pytest.raises(ValueError, match="both outcome classes"):
        exact_separation_test([1.0, 2.0, 3.0], [True, True, True])


def test_non_finite_is_refused():
    with pytest.raises(ValueError, match="non-finite"):
        exact_separation_test([1.0, float("nan")], [True, False])


def test_mismatched_lengths_are_refused():
    with pytest.raises(ValueError):
        exact_separation_test([1.0, 2.0, 3.0], [True, False])


def test_planning_refuses_an_empty_class():
    with pytest.raises(ValueError, match="at least one"):
        minimum_additional_edges(0, 4)
