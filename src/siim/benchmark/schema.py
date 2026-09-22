"""Result JSON schema, and the validator that makes it mean something.

The schema is enforced in code rather than declared in a separate file,
because the constraints that matter here are not shapes. They are relations:

* a row may not carry an absolute error unless it had truth to compare against;
* a fit residual must be labelled as not an accuracy, every time;
* a row whose overlap was never confirmed may not report a registration
  verdict, because nothing about the matcher was measured;
* ``corpus_class`` and ``ground_truth`` have no defaults, so a proxy result
  cannot become a Chandrayaan-2 result by omission.

Validation is deliberately strict and raises :class:`SchemaError` with the
reason. A benchmark that silently emits a malformed row is worse than one that
fails, because the malformed row will be read later by someone who trusts it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .manifest import CORPUS_CLASSES, GROUND_TRUTH_KINDS, OVERLAP_STATUSES
from .metrics import METRIC_KINDS, MetricSet

__all__ = [
    "RESULT_SCHEMA_VERSION",
    "SchemaError",
    "result_row",
    "validate_result",
    "validate_run",
    "run_envelope",
    "write_run",
]

RESULT_SCHEMA_VERSION = "1.0.0"

VERDICTS = ("VERIFIED", "REJECTED", "INCONCLUSIVE", "NOT_RUN", "CANNOT_CHECK")

#: Verdicts that assert something about a registration. A row that never
#: matched anything may not carry one.
_REGISTRATION_VERDICTS = frozenset({"VERIFIED", "REJECTED", "INCONCLUSIVE"})

_REQUIRED = (
    "schema_version",
    "benchmark_id",
    "arm",
    "pair_id",
    "corpus_class",
    "ground_truth",
    "engine",
    "seed",
    "verdict",
    "overlap_status",
)

#: Field names that assert an accuracy. Guarded, see ``metrics``.
_ACCURACY_FIELDS = ("abs_err_px", "abs_err_max_px")


class SchemaError(ValueError):
    """A result row or run envelope violated the schema."""


def result_row(
    *,
    benchmark_id: str,
    arm: str,
    pair_id: str,
    corpus_class: str,
    ground_truth: str,
    engine: str,
    seed: int,
    verdict: str,
    overlap_status: str,
    metrics: MetricSet | None = None,
    uniformity: Mapping[str, Any] | None = None,
    transform_matrix: Sequence[Sequence[float]] | None = None,
    model: str | None = None,
    wrong_pass: bool | None = None,
    known_correct: bool | None = None,
    verdict_reasons: Sequence[str] = (),
    scale_ratio: float | None = None,
    scale_ratio_source: str | None = None,
    delta_incidence_deg: float | None = None,
    delta_azimuth_deg: float | None = None,
    artefact_path: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one result row and validate it before returning.

    The row is validated here rather than at write time so that a malformed
    row fails at the point it was constructed, where the context to fix it
    still exists.
    """
    row: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "benchmark_id": benchmark_id,
        "arm": arm,
        "pair_id": pair_id,
        "corpus_class": corpus_class,
        "ground_truth": ground_truth,
        "engine": engine,
        "seed": int(seed),
        "verdict": verdict,
        "verdict_reasons": list(verdict_reasons),
        "overlap_status": overlap_status,
        "model": model,
        "transform_matrix": (
            [list(map(float, r)) for r in transform_matrix]
            if transform_matrix is not None else None
        ),
        "scale_ratio": scale_ratio,
        "scale_ratio_source": scale_ratio_source,
        "delta_incidence_deg": delta_incidence_deg,
        "delta_azimuth_deg": delta_azimuth_deg,
        "wrong_pass": wrong_pass,
        "known_correct": known_correct,
        "artefact_path": artefact_path,
    }
    if metrics is not None:
        row["metrics"] = metrics.as_dict()
        flat = metrics.flat()
        for name in _ACCURACY_FIELDS:
            if name in flat:
                row[name] = flat[name]
        if "fit_rmse_px" in flat:
            row["fit_rmse_px"] = flat["fit_rmse_px"]
            row["fit_rmse_is_not_accuracy"] = True
    if uniformity is not None:
        row["uniformity"] = dict(uniformity)
    if extra:
        row["extra"] = dict(extra)
    validate_result(row)
    return row


def validate_result(row: Mapping[str, Any]) -> None:
    """Raise :class:`SchemaError` if ``row`` violates the schema."""
    missing = [k for k in _REQUIRED if k not in row]
    if missing:
        raise SchemaError(f"missing required field(s): {missing}")

    if row["schema_version"] != RESULT_SCHEMA_VERSION:
        raise SchemaError(
            f"schema_version {row['schema_version']!r} != {RESULT_SCHEMA_VERSION!r}"
        )
    if row["corpus_class"] not in CORPUS_CLASSES:
        raise SchemaError(
            f"corpus_class {row['corpus_class']!r} not in {CORPUS_CLASSES}"
        )
    if row["ground_truth"] not in GROUND_TRUTH_KINDS:
        raise SchemaError(
            f"ground_truth {row['ground_truth']!r} not in {GROUND_TRUTH_KINDS}"
        )
    if row["verdict"] not in VERDICTS:
        raise SchemaError(f"verdict {row['verdict']!r} not in {VERDICTS}")
    if row["overlap_status"] not in OVERLAP_STATUSES:
        raise SchemaError(
            f"overlap_status {row['overlap_status']!r} not in {OVERLAP_STATUSES}"
        )

    # A pair whose overlap was never confirmed cannot have measured anything
    # about the matcher, so it may not carry a registration verdict.
    if (row["verdict"] in _REGISTRATION_VERDICTS
            and row["overlap_status"] != "CONFIRMED"):
        raise SchemaError(
            f"verdict {row['verdict']!r} with overlap_status "
            f"{row['overlap_status']!r}: a registration verdict requires "
            "CONFIRMED overlap. Use NOT_RUN or CANNOT_CHECK instead."
        )

    # An absolute error requires truth the matcher never saw.
    has_accuracy = any(
        row.get(name) is not None for name in _ACCURACY_FIELDS
    )
    if has_accuracy and row["ground_truth"] not in ("EXACT", "CHECK_POINTS"):
        raise SchemaError(
            f"row reports an absolute error but ground_truth is "
            f"{row['ground_truth']!r}. Corroboration is not accuracy, and a "
            "fit residual is not an accuracy."
        )

    if row.get("fit_rmse_px") is not None and not row.get("fit_rmse_is_not_accuracy"):
        raise SchemaError(
            "fit_rmse_px is present without fit_rmse_is_not_accuracy=True. "
            "The flag is mandatory: this statistic scores at chance as a "
            "failure detector."
        )

    if row.get("wrong_pass") is not None and row["verdict"] != "VERIFIED":
        raise SchemaError(
            f"wrong_pass is set but verdict is {row['verdict']!r}. A wrong pass "
            "is an accepted row later shown wrong; a rejected row is not one."
        )

    if row.get("scale_ratio") is not None and not row.get("scale_ratio_source"):
        raise SchemaError(
            "scale_ratio present without scale_ratio_source. A nominal "
            "specification ratio and a ratio measured from delivered labels "
            "are different claims."
        )

    metrics = row.get("metrics")
    if metrics is not None:
        if not isinstance(metrics, Mapping):
            raise SchemaError("metrics must be a mapping of name to record")
        for name, rec in metrics.items():
            if not isinstance(rec, Mapping):
                raise SchemaError(f"metric {name!r} is not a record")
            if "kind" not in rec:
                raise SchemaError(f"metric {name!r} has no kind")
            if rec["kind"] not in METRIC_KINDS:
                raise SchemaError(
                    f"metric {name!r} has kind {rec['kind']!r}, not in "
                    f"{METRIC_KINDS}"
                )
            if rec.get("value") is None and not rec.get("undefined_reason"):
                raise SchemaError(
                    f"metric {name!r} has no value and no undefined_reason"
                )
            if name in _ACCURACY_FIELDS and rec["kind"] != "accuracy":
                raise SchemaError(
                    f"metric {name!r} is an accuracy field with kind "
                    f"{rec['kind']!r}"
                )


def run_envelope(
    *,
    config: Mapping[str, Any],
    provenance: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    aggregates: Mapping[str, Any] | None = None,
    refusals: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Wrap rows with the configuration and provenance that produced them."""
    env = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "config": dict(config),
        "provenance": dict(provenance),
        "n_rows": len(rows),
        "rows": [dict(r) for r in rows],
        "refusals": [dict(r) for r in refusals],
        "aggregates": dict(aggregates or {}),
    }
    validate_run(env)
    return env


def validate_run(envelope: Mapping[str, Any]) -> None:
    """Validate a whole run: envelope shape, then every row."""
    for key in ("schema_version", "config", "provenance", "rows"):
        if key not in envelope:
            raise SchemaError(f"run envelope missing {key!r}")
    if envelope["schema_version"] != RESULT_SCHEMA_VERSION:
        raise SchemaError(
            f"run schema_version {envelope['schema_version']!r} != "
            f"{RESULT_SCHEMA_VERSION!r}"
        )
    rows = envelope["rows"]
    if not isinstance(rows, Sequence):
        raise SchemaError("rows must be a sequence")
    if "n_rows" in envelope and envelope["n_rows"] != len(rows):
        raise SchemaError(
            f"n_rows={envelope['n_rows']} but {len(rows)} rows are present"
        )
    for i, row in enumerate(rows):
        try:
            validate_result(row)
        except SchemaError as exc:
            raise SchemaError(f"row {i}: {exc}") from exc


def write_run(envelope: Mapping[str, Any], path: str | Path) -> Path:
    """Validate, then write a run envelope to JSON. Returns the path."""
    validate_run(envelope)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(envelope, fh, indent=2, sort_keys=False)
        fh.write("\n")
    return out


def read_run(path: str | Path) -> dict[str, Any]:
    """Read and validate a run envelope."""
    with open(path, encoding="utf-8") as fh:
        env = json.load(fh)
    validate_run(env)
    return env


def iter_rows(envelopes: Iterable[Mapping[str, Any]]) -> Iterable[Mapping[str, Any]]:
    """Flatten rows across runs, for aggregate reporting."""
    for env in envelopes:
        for row in env.get("rows", ()):
            yield row
