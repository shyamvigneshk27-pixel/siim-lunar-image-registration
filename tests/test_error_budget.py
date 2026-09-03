"""The accuracy budget, and its refusal to look complete when it is not."""

from __future__ import annotations

import json
import math

import pytest

from siim.evaluation.error_budget import (
    BudgetTerm,
    ErrorBudget,
    TermKind,
    TermStatus,
    nac_reference_budget,
)


def _term(name, kind=TermKind.RANDOM, status=TermStatus.MEASURED, metres=1.0):
    return BudgetTerm(name, kind, status, metres, source="test")


# --------------------------------------------------------------------------
# the refusal that is the point of the module
# --------------------------------------------------------------------------


def test_a_budget_with_a_pending_term_is_not_complete():
    b = ErrorBudget("x").with_term(_term("a")).with_term(
        BudgetTerm("b", TermKind.RANDOM, TermStatus.PENDING, None, source="pending")
    )
    t = b.total()
    assert t.complete is False
    assert t.pending_terms == ("b",)
    assert "INCOMPLETE" in t.statement and "LOWER BOUND" in t.statement


def test_a_complete_budget_states_a_total():
    b = ErrorBudget("x").with_term(_term("a")).with_term(_term("b"))
    t = b.total()
    assert t.complete is True
    assert "INCOMPLETE" not in t.statement
    assert t.metres == pytest.approx(math.sqrt(2))


def test_pending_terms_must_not_carry_a_value():
    with pytest.raises(ValueError, match="must not carry a value"):
        BudgetTerm("a", TermKind.RANDOM, TermStatus.PENDING, 3.0, source="s")


def test_determined_terms_must_carry_a_value():
    with pytest.raises(ValueError, match="has no value"):
        BudgetTerm("a", TermKind.RANDOM, TermStatus.MEASURED, None, source="s")


def test_every_term_must_be_traceable():
    with pytest.raises(ValueError, match="no source"):
        BudgetTerm("a", TermKind.RANDOM, TermStatus.MEASURED, 1.0, source="  ")


# --------------------------------------------------------------------------
# metrology: the two kinds do not combine the same way
# --------------------------------------------------------------------------


def test_random_terms_combine_in_quadrature():
    b = ErrorBudget("x").with_term(_term("a", metres=3.0)).with_term(_term("b", metres=4.0))
    assert b.total().metres == pytest.approx(5.0)


def test_systematic_terms_combine_linearly():
    b = (
        ErrorBudget("x")
        .with_term(_term("a", kind=TermKind.SYSTEMATIC, metres=3.0))
        .with_term(_term("b", kind=TermKind.SYSTEMATIC, metres=4.0))
    )
    assert b.total().metres == pytest.approx(7.0)


def test_mixing_kinds_does_not_rss_everything():
    """RSS-ing biases is the standard way to understate a budget.

    3 (random) and 4 (systematic) must give 7, not 5.
    """
    b = (
        ErrorBudget("x")
        .with_term(_term("r", kind=TermKind.RANDOM, metres=3.0))
        .with_term(_term("s", kind=TermKind.SYSTEMATIC, metres=4.0))
    )
    t = b.total()
    assert t.random_component == pytest.approx(3.0)
    assert t.systematic_component == pytest.approx(4.0)
    assert t.metres == pytest.approx(7.0)
    assert t.metres != pytest.approx(5.0)


# --------------------------------------------------------------------------
# units
# --------------------------------------------------------------------------


def test_pixels_require_an_explicit_gsd():
    b = ErrorBudget("x").with_term(_term("a", metres=10.0))
    assert b.in_pixels(2.0) == pytest.approx(5.0)
    with pytest.raises(ValueError):
        b.in_pixels(0.0)


# --------------------------------------------------------------------------
# resolution as evidence arrives
# --------------------------------------------------------------------------


def test_resolving_a_pending_term_can_complete_the_budget():
    b = ErrorBudget("x").with_term(
        BudgetTerm("a", TermKind.RANDOM, TermStatus.PENDING, None, source="pending")
    )
    assert not b.total().complete
    b2 = b.resolve("a", 2.0, status=TermStatus.MEASURED, source="experiments/X/y.json")
    assert b2.total().complete
    assert b2.total().metres == pytest.approx(2.0)
    # the original is untouched -- budgets are immutable records
    assert not b.total().complete


def test_resolving_an_already_determined_term_is_refused():
    b = ErrorBudget("x").with_term(_term("a"))
    with pytest.raises(ValueError, match="already"):
        b.resolve("a", 1.0, status=TermStatus.MEASURED, source="s")


def test_duplicate_terms_are_refused():
    b = ErrorBudget("x").with_term(_term("a"))
    with pytest.raises(ValueError, match="duplicate"):
        b.with_term(_term("a"))


# --------------------------------------------------------------------------
# the project's actual budget
# --------------------------------------------------------------------------


def test_the_nac_budget_is_incomplete_and_says_so():
    """Three of five terms are pending. The total must not pretend otherwise."""
    b = nac_reference_budget()
    t = b.total()
    assert not t.complete
    assert set(t.pending_terms) == {
        "anchoring_residual",
        "correspondence_localisation",
        "resampling_and_interpolation",
    }
    # 13 m + 10 m, both systematic, both published.
    assert t.systematic_component == pytest.approx(23.0)
    assert t.random_component == pytest.approx(0.0)


def test_the_nac_budget_already_beats_the_current_corroboration_floor():
    """Even incomplete, the reference chain is tighter than what is in use.

    The project currently corroborates against archive geometry with a 105.6 px
    discrimination floor. At 2 m/px NAC resolution the two published terms
    alone come to ~11.5 px, and at 0.5 m/px to 46 px -- both inside the floor.
    That is the argument for running the anchoring experiment.
    """
    t = nac_reference_budget().total()
    assert t.as_pixels(2.0) < 105.6
    assert t.as_pixels(0.5) < 105.6


def test_fit_residual_is_not_a_budget_term():
    """It measures self-consistency, not accuracy (ADR-0003).

    A recorded real edge reports 1.885e-13 px on a transform measured 797 px
    wrong. Admitting it here would be the most misleading thing this module
    could do.
    """
    names = {t.name for t in nac_reference_budget().terms}
    assert not any("rmse" in n or "residual_fit" in n or "fit_" in n for n in names)


def test_every_nac_term_names_a_source_or_the_experiment_that_would_fill_it():
    for term in nac_reference_budget().terms:
        assert term.source.strip()
        if term.status is TermStatus.PENDING:
            assert "PENDING" in term.source


def test_budget_serialises():
    json.dumps(nac_reference_budget().to_dict())
