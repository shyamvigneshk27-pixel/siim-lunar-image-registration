"""Metrics, and the type discipline that stops a fit residual becoming an accuracy."""

from __future__ import annotations

import numpy as np
import pytest

from siim.benchmark.metrics import (
    MetricKind,
    MetricSet,
    MetricValue,
    absolute_error,
    aggregate_rates,
    correspondence_summary,
    fit_statistics,
)


# -- the central invariant --------------------------------------------------

def test_an_accuracy_field_refuses_a_fit_value():
    """This is the confusion the whole module exists to prevent."""
    with pytest.raises(ValueError, match="not an accuracy"):
        MetricValue("abs_err_px", 0.5, MetricKind.FIT, "px")


def test_an_accuracy_field_accepts_an_accuracy_value():
    v = MetricValue("abs_err_px", 0.5, MetricKind.ACCURACY, "px")
    assert v.kind is MetricKind.ACCURACY


def test_every_fit_statistic_is_labelled_fit_and_carries_the_caveat():
    ms = fit_statistics([0.1, 0.2, 0.3])
    assert len(ms) == 3
    for v in ms.values:
        assert v.kind is MetricKind.FIT
        assert "Not an accuracy" in v.caveat
        assert "chance" in v.caveat


def test_a_picometre_residual_is_still_only_a_fit_statistic():
    """The real B->D edge reports 1.885e-13 px while being 797 px wrong."""
    ms = fit_statistics([1.885e-13, 1.9e-13, 1.88e-13])
    v = ms.get("fit_rmse_px")
    assert v.value < 1e-12
    assert v.kind is MetricKind.FIT


# -- absent is not zero -----------------------------------------------------

def test_a_metric_without_a_value_must_say_why():
    with pytest.raises(ValueError, match="undefined_reason"):
        MetricValue("x", None, MetricKind.COUNT)


def test_no_correspondences_yields_undefined_not_zero():
    ms = fit_statistics([])
    for name in ("fit_rmse_px", "med_res_px", "max_res_px"):
        v = ms.get(name)
        assert v.value is None
        assert "no correspondences" in v.undefined_reason


def test_all_non_finite_residuals_yield_undefined():
    ms = fit_statistics([np.nan, np.inf])
    assert ms.get("fit_rmse_px").value is None


def test_non_finite_values_are_refused_outright():
    with pytest.raises(ValueError, match="non-finite"):
        MetricValue("x", float("inf"), MetricKind.FIT)


def test_fit_statistics_ignore_non_finite_entries_when_some_are_finite():
    ms = fit_statistics([1.0, np.nan, 3.0])
    assert ms.get("max_res_px").value == pytest.approx(3.0)


# -- correspondence counts --------------------------------------------------

def test_inlier_ratio_and_counts():
    ms = correspondence_summary(100, 25)
    assert ms.value_of("n_putative") == 100
    assert ms.value_of("n_inliers") == 25
    assert ms.value_of("inlier_ratio") == pytest.approx(0.25)


def test_inliers_cannot_exceed_putatives():
    with pytest.raises(ValueError, match="exceeds"):
        correspondence_summary(10, 11)


def test_negative_counts_are_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        correspondence_summary(-1, 0)


def test_ratio_is_undefined_rather_than_zero_when_nothing_was_putative():
    ms = correspondence_summary(0, 0)
    v = ms.get("inlier_ratio")
    assert v.value is None
    assert "no putative" in v.undefined_reason


# -- absolute error requires real truth -------------------------------------

def test_absolute_error_refuses_truth_derived_from_the_fit():
    with pytest.raises(ValueError, match="not truth"):
        absolute_error([[0, 0]], [[1, 1]], reference="FIT_RESIDUAL")


def test_absolute_error_against_ground_truth():
    ms = absolute_error([[0.0, 0.0], [0.0, 0.0]],
                        [[3.0, 4.0], [6.0, 8.0]], reference="GROUND_TRUTH")
    assert ms.get("abs_err_px").kind is MetricKind.ACCURACY
    assert ms.value_of("abs_err_px") == pytest.approx(7.5)
    assert ms.value_of("abs_err_max_px") == pytest.approx(10.0)


def test_absolute_error_shape_mismatch_is_rejected():
    with pytest.raises(ValueError, match="shape mismatch"):
        absolute_error([[0, 0]], [[0, 0], [1, 1]], reference="CHECK_POINTS")


# -- metric sets ------------------------------------------------------------

def test_duplicate_names_are_rejected_in_a_set():
    with pytest.raises(ValueError, match="duplicate"):
        MetricSet((MetricValue("a", 1, MetricKind.COUNT),
                   MetricValue("a", 2, MetricKind.COUNT)))


def test_merge_refuses_to_silently_overwrite():
    a = MetricSet((MetricValue("a", 1, MetricKind.COUNT),))
    b = MetricSet((MetricValue("a", 2, MetricKind.COUNT),))
    with pytest.raises(ValueError, match="duplicate metric names"):
        a.merge(b)


def test_merge_combines_disjoint_sets():
    merged = fit_statistics([1.0]).merge(correspondence_summary(5, 2))
    assert "fit_rmse_px" in merged
    assert "n_inliers" in merged
    assert len(merged) == 6


def test_of_kind_filters():
    merged = fit_statistics([1.0]).merge(correspondence_summary(5, 2))
    assert len(merged.of_kind(MetricKind.FIT)) == 3
    assert len(merged.of_kind(MetricKind.ACCURACY)) == 0


# -- aggregate rates --------------------------------------------------------

def _row(verdict, **kw):
    d = {"verdict": verdict}
    d.update(kw)
    return d


def test_false_acceptance_rate_over_scored_acceptances():
    rows = [
        _row("VERIFIED", wrong_pass=False),
        _row("VERIFIED", wrong_pass=False),
        _row("VERIFIED", wrong_pass=True),
        _row("REJECTED"),
    ]
    ms = aggregate_rates(rows)
    assert ms.value_of("n_wrong_passes") == 1
    assert ms.value_of("false_acceptance_rate") == pytest.approx(1 / 3)


def test_false_acceptance_is_undefined_without_an_independent_determination():
    """76 passes with nothing to score them against is not a rate of zero."""
    ms = aggregate_rates([_row("VERIFIED"), _row("VERIFIED")])
    v = ms.get("false_acceptance_rate")
    assert v.value is None
    assert "wrong_pass determination" in v.undefined_reason


def test_a_present_but_null_wrong_pass_still_counts_as_unchecked():
    """The runner emits ``wrong_pass: None``; key presence is not a verdict."""
    ms = aggregate_rates([_row("VERIFIED", wrong_pass=None),
                          _row("VERIFIED", wrong_pass=None)])
    assert ms.get("false_acceptance_rate").value is None


def test_a_partially_scored_run_uses_only_the_scored_rows():
    ms = aggregate_rates([
        _row("VERIFIED", wrong_pass=None),   # not checked
        _row("VERIFIED", wrong_pass=False),  # checked, clean
        _row("VERIFIED", wrong_pass=True),   # checked, wrong
    ])
    assert ms.value_of("false_acceptance_rate") == pytest.approx(0.5)
    assert ms.value_of("n_wrong_passes") == 1


def test_false_rejection_needs_cases_known_to_be_correct():
    ms = aggregate_rates([_row("REJECTED"), _row("VERIFIED", wrong_pass=False)])
    assert ms.get("false_rejection_rate").value is None

    ms = aggregate_rates([
        _row("REJECTED", known_correct=True),
        _row("VERIFIED", known_correct=True, wrong_pass=False),
    ])
    assert ms.value_of("false_rejection_rate") == pytest.approx(0.5)


def test_inconclusive_rate_and_counts():
    rows = [_row("VERIFIED", wrong_pass=False), _row("INCONCLUSIVE"),
            _row("REJECTED"), _row("INCONCLUSIVE")]
    ms = aggregate_rates(rows)
    assert ms.value_of("n_rows") == 4
    assert ms.value_of("n_inconclusive") == 2
    assert ms.value_of("inconclusive_rate") == pytest.approx(0.5)


def test_empty_run_has_undefined_rates_not_zero():
    ms = aggregate_rates([])
    assert ms.value_of("n_rows") == 0
    assert ms.get("inconclusive_rate").value is None
