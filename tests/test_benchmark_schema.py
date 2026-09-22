"""The result schema: the relations it enforces, not merely the shapes."""

from __future__ import annotations

import json

import pytest

from siim.benchmark.config import ExperimentConfig
from siim.benchmark.metrics import (
    MetricKind,
    MetricSet,
    MetricValue,
    correspondence_summary,
    fit_statistics,
)
from siim.benchmark.schema import (
    RESULT_SCHEMA_VERSION,
    SchemaError,
    read_run,
    result_row,
    run_envelope,
    validate_result,
    validate_run,
    write_run,
)


def base(**kw):
    d = dict(
        benchmark_id="B2", arm="baseline", pair_id="p1",
        corpus_class="PROXY", ground_truth="CORROBORATION_ONLY",
        engine="B1", seed=0, verdict="VERIFIED", overlap_status="CONFIRMED",
    )
    d.update(kw)
    return d


# -- required fields and vocabularies ---------------------------------------

def test_a_row_missing_corpus_class_is_refused():
    row = base()
    del row["corpus_class"]
    with pytest.raises(SchemaError, match="missing required field"):
        validate_result({"schema_version": RESULT_SCHEMA_VERSION, **row})


def test_unknown_corpus_class_is_refused():
    with pytest.raises(SchemaError, match="corpus_class"):
        result_row(**base(corpus_class="real"))


def test_unknown_verdict_is_refused():
    with pytest.raises(SchemaError, match="verdict"):
        result_row(**base(verdict="PROBABLY_FINE"))


def test_unknown_ground_truth_is_refused():
    with pytest.raises(SchemaError, match="ground_truth"):
        result_row(**base(ground_truth="pretty_good"))


# -- the overlap relation ---------------------------------------------------

@pytest.mark.parametrize("verdict", ["VERIFIED", "REJECTED", "INCONCLUSIVE"])
def test_a_registration_verdict_requires_confirmed_overlap(verdict):
    """Without confirmed overlap nothing about the matcher was measured."""
    with pytest.raises(SchemaError, match="requires CONFIRMED overlap"):
        result_row(**base(verdict=verdict, overlap_status="UNKNOWN"))


@pytest.mark.parametrize("verdict", ["NOT_RUN", "CANNOT_CHECK"])
def test_non_registration_verdicts_are_allowed_without_overlap(verdict):
    row = result_row(**base(verdict=verdict, overlap_status="NOT_CONFIRMED"))
    assert row["verdict"] == verdict


# -- the accuracy relation --------------------------------------------------

def test_an_absolute_error_requires_truth():
    ms = MetricSet((MetricValue("abs_err_px", 0.4, MetricKind.ACCURACY, "px"),))
    with pytest.raises(SchemaError, match="Corroboration is not accuracy"):
        result_row(**base(ground_truth="CORROBORATION_ONLY"), metrics=ms)


def test_an_absolute_error_is_allowed_with_exact_ground_truth():
    ms = MetricSet((MetricValue("abs_err_px", 0.4, MetricKind.ACCURACY, "px"),))
    row = result_row(**base(ground_truth="EXACT"), metrics=ms)
    assert row["abs_err_px"] == pytest.approx(0.4)


def test_ground_truth_none_forbids_an_accuracy_field():
    ms = MetricSet((MetricValue("abs_err_px", 0.1, MetricKind.ACCURACY, "px"),))
    with pytest.raises(SchemaError):
        result_row(**base(ground_truth="NONE"), metrics=ms)


# -- the fit-residual flag --------------------------------------------------

def test_a_fit_residual_is_always_flagged_as_not_an_accuracy():
    row = result_row(**base(), metrics=fit_statistics([0.5, 0.6]))
    assert row["fit_rmse_px"] == pytest.approx(0.5522680508)
    assert row["fit_rmse_is_not_accuracy"] is True


def test_stripping_the_flag_invalidates_the_row():
    row = result_row(**base(), metrics=fit_statistics([0.5]))
    del row["fit_rmse_is_not_accuracy"]
    with pytest.raises(SchemaError, match="flag is mandatory"):
        validate_result(row)


def test_a_metric_named_for_accuracy_must_carry_the_accuracy_kind():
    row = result_row(**base(ground_truth="EXACT"))
    row["metrics"] = {"abs_err_px": {"value": 1.0, "kind": "fit", "units": "px"}}
    with pytest.raises(SchemaError, match="accuracy field with kind"):
        validate_result(row)


# -- other relations --------------------------------------------------------

def test_wrong_pass_is_meaningless_on_a_rejected_row():
    with pytest.raises(SchemaError, match="a rejected row is not one"):
        result_row(**base(verdict="REJECTED"), wrong_pass=True)


def test_wrong_pass_is_allowed_on_an_accepted_row():
    row = result_row(**base(verdict="VERIFIED"), wrong_pass=True)
    assert row["wrong_pass"] is True


def test_a_scale_ratio_must_name_its_source():
    with pytest.raises(SchemaError, match="scale_ratio_source"):
        result_row(**base(), scale_ratio=320.0)


def test_a_scale_ratio_with_a_source_is_accepted():
    row = result_row(**base(), scale_ratio=320.0, scale_ratio_source="NOMINAL")
    assert row["scale_ratio_source"] == "NOMINAL"


def test_a_metric_without_value_or_reason_is_refused():
    row = result_row(**base())
    row["metrics"] = {"x": {"value": None, "kind": "count"}}
    with pytest.raises(SchemaError, match="no value and no undefined_reason"):
        validate_result(row)


def test_an_unknown_metric_kind_is_refused():
    row = result_row(**base())
    row["metrics"] = {"x": {"value": 1, "kind": "vibes"}}
    with pytest.raises(SchemaError, match="not in"):
        validate_result(row)


# -- run envelopes ----------------------------------------------------------

def _cfg():
    return ExperimentConfig(
        benchmark_id="B2", arm="baseline",
        corpus_class="PROXY", ground_truth="CORROBORATION_ONLY",
    ).to_dict()


def test_a_run_envelope_validates_every_row():
    good = result_row(**base())
    bad = dict(good)
    bad["verdict"] = "nonsense"
    with pytest.raises(SchemaError, match="row 1"):
        run_envelope(config=_cfg(), provenance={}, rows=[good, bad])


def test_n_rows_must_match_the_rows_present():
    env = run_envelope(config=_cfg(), provenance={}, rows=[result_row(**base())])
    env["n_rows"] = 99
    with pytest.raises(SchemaError, match="n_rows"):
        validate_run(env)


def test_a_run_missing_provenance_is_refused():
    with pytest.raises(SchemaError, match="provenance"):
        validate_run({"schema_version": RESULT_SCHEMA_VERSION,
                      "config": {}, "rows": []})


def test_schema_version_mismatch_is_refused():
    row = result_row(**base())
    row["schema_version"] = "0.1.0"
    with pytest.raises(SchemaError, match="schema_version"):
        validate_result(row)


def test_run_round_trips_through_disk(tmp_path):
    env = run_envelope(
        config=_cfg(), provenance={"captured_utc": "now"},
        rows=[result_row(**base(), metrics=correspondence_summary(10, 5))],
        refusals=[{"pair_id": "p2", "reason": "overlap UNKNOWN"}],
    )
    path = write_run(env, tmp_path / "run.json")
    assert path.exists()
    back = read_run(path)
    assert back["n_rows"] == 1
    assert back["refusals"][0]["pair_id"] == "p2"
    assert json.loads(path.read_text(encoding="utf-8"))["config"]["arm"] == "baseline"


def test_write_refuses_an_invalid_run(tmp_path):
    env = run_envelope(config=_cfg(), provenance={}, rows=[])
    env["rows"] = [{"schema_version": RESULT_SCHEMA_VERSION}]
    env["n_rows"] = 1
    with pytest.raises(SchemaError):
        write_run(env, tmp_path / "bad.json")
    assert not (tmp_path / "bad.json").exists()
