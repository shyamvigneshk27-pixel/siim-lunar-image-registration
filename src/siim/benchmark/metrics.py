"""Metric modules, typed so that a fit statistic cannot pass as an accuracy.

The single most consequential measurement in this project is negative: the fit
residual scores **ROC AUC 0.495** as a failure detector, which is chance. One
real edge reports a residual of 1.885e-13 px for a transform independently
measured 797 px wrong. Reporting that residual is fine and the problem
statement invites it. Letting it decide anything is not.

Type discipline is how that is enforced here rather than remembered. Every
value carries a :class:`MetricKind`. ``FIT`` values are measured on the points
that determined the transform and are therefore goodness-of-fit statistics;
``ACCURACY`` values require truth the matcher never saw. The serialiser in
:mod:`siim.benchmark.schema` refuses to place a ``FIT`` value in a field named
for accuracy, so the confusion cannot survive a round-trip to JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = [
    "MetricKind",
    "METRIC_KINDS",
    "MetricValue",
    "MetricSet",
    "fit_statistics",
    "correspondence_summary",
    "absolute_error",
    "aggregate_rates",
]


class MetricKind(str, Enum):
    """What a number is, which decides what may be concluded from it."""

    #: Compared against truth the matcher never saw. The only kind that may be
    #: called an accuracy.
    ACCURACY = "accuracy"
    #: Measured on the points that determined the transform. Falls monotonically
    #: as the inlier threshold tightens; blind to a uniformly shifted solution.
    FIT = "fit"
    #: Spatial arrangement of the correspondences.
    DISTRIBUTION = "distribution"
    #: Evidence independent of the fit: loop closure, engine agreement, archive
    #: geometry.
    INDEPENDENT_CHECK = "independent_check"
    #: Precision under the assumed model. Not accuracy: a systematically wrong
    #: correspondence set yields a small, confident uncertainty.
    UNCERTAINTY = "uncertainty"
    #: Counts of things.
    COUNT = "count"
    #: Runtime, memory.
    COST = "cost"


METRIC_KINDS: tuple[str, ...] = tuple(k.value for k in MetricKind)

#: Metric names that must never carry a FIT value. Checked by the schema.
_ACCURACY_FIELD_NAMES = frozenset(
    {"abs_err_px", "absolute_error_px", "accuracy_px", "true_error_px"}
)


@dataclass(frozen=True)
class MetricValue:
    """One number, its units, its kind, and the caveat that travels with it."""

    name: str
    value: float | int | None
    kind: MetricKind
    units: str = ""
    #: Set when the metric could not be computed, e.g. no ground truth exists.
    undefined_reason: str | None = None
    caveat: str = ""

    def __post_init__(self) -> None:
        if self.value is None and not self.undefined_reason:
            raise ValueError(
                f"metric {self.name!r} has no value and no undefined_reason. "
                "An absent measurement must say why it is absent; it is not zero."
            )
        if self.name in _ACCURACY_FIELD_NAMES and self.kind is not MetricKind.ACCURACY:
            raise ValueError(
                f"metric {self.name!r} is an accuracy field but was given kind "
                f"{self.kind.value!r}. A fit residual is not an accuracy."
            )
        if self.value is not None and isinstance(self.value, float):
            if not np.isfinite(self.value):
                raise ValueError(
                    f"metric {self.name!r} is {self.value}; use value=None with "
                    "an undefined_reason instead of a non-finite number."
                )

    @property
    def defined(self) -> bool:
        return self.value is not None

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "value": self.value,
            "kind": self.kind.value,
            "units": self.units,
        }
        if self.undefined_reason:
            d["undefined_reason"] = self.undefined_reason
        if self.caveat:
            d["caveat"] = self.caveat
        return d


@dataclass(frozen=True)
class MetricSet:
    """A named collection of metrics, immutable and mergeable."""

    values: tuple[MetricValue, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for v in self.values:
            if v.name in seen:
                raise ValueError(f"duplicate metric {v.name!r} in MetricSet")
            seen.add(v.name)

    def __len__(self) -> int:
        return len(self.values)

    def __contains__(self, name: object) -> bool:
        return any(v.name == name for v in self.values)

    def get(self, name: str) -> MetricValue | None:
        for v in self.values:
            if v.name == name:
                return v
        return None

    def value_of(self, name: str) -> float | int | None:
        v = self.get(name)
        return None if v is None else v.value

    def of_kind(self, kind: MetricKind) -> tuple[MetricValue, ...]:
        return tuple(v for v in self.values if v.kind is kind)

    def merge(self, other: "MetricSet") -> "MetricSet":
        """Combine two sets. Raises on any name collision rather than guessing."""
        names = {v.name for v in self.values}
        clash = names.intersection({v.name for v in other.values})
        if clash:
            raise ValueError(f"cannot merge: duplicate metric names {sorted(clash)}")
        return MetricSet(self.values + other.values)

    def as_dict(self) -> dict[str, Any]:
        return {v.name: v.as_dict() for v in self.values}

    def flat(self) -> dict[str, float | int | None]:
        """Name to bare value, for tabular output. Kinds are lost: use with care."""
        return {v.name: v.value for v in self.values}


def fit_statistics(residuals: ArrayLike) -> MetricSet:
    """Residual statistics under the final transform.

    **Every value returned is a fit statistic**, measured on the points that
    determined the transform. None of them is an accuracy, and the caveat is
    attached to each so it survives serialisation.
    """
    r = np.asarray(residuals, dtype=float).ravel()
    caveat = (
        "Fit statistic: measured on the correspondences that determined the "
        "transform. Not an accuracy. Scores ROC AUC 0.495 as a failure "
        "detector, which is chance."
    )
    if r.size == 0:
        reason = "no correspondences under the final transform"
        return MetricSet(
            tuple(
                MetricValue(n, None, MetricKind.FIT, "px",
                            undefined_reason=reason, caveat=caveat)
                for n in ("fit_rmse_px", "med_res_px", "max_res_px")
            )
        )
    finite = r[np.isfinite(r)]
    if finite.size == 0:
        reason = "all residuals non-finite"
        return MetricSet(
            tuple(
                MetricValue(n, None, MetricKind.FIT, "px",
                            undefined_reason=reason, caveat=caveat)
                for n in ("fit_rmse_px", "med_res_px", "max_res_px")
            )
        )
    return MetricSet(
        (
            MetricValue("fit_rmse_px", float(np.sqrt(np.mean(finite ** 2))),
                        MetricKind.FIT, "px", caveat=caveat),
            MetricValue("med_res_px", float(np.median(finite)),
                        MetricKind.FIT, "px", caveat=caveat),
            MetricValue("max_res_px", float(np.max(finite)),
                        MetricKind.FIT, "px", caveat=caveat),
        )
    )


def correspondence_summary(n_putative: int, n_inliers: int) -> MetricSet:
    """Counts and the inlier ratio.

    The inlier count is the project's primary acceptance signal, validated at
    recall 1.000 and false-positive rate 0.0112 on 192 unseen cases. The ratio
    is supporting evidence only.
    """
    if n_putative < 0 or n_inliers < 0:
        raise ValueError("counts must be non-negative")
    if n_inliers > n_putative:
        raise ValueError(
            f"n_inliers={n_inliers} exceeds n_putative={n_putative}: "
            "an inlier is a putative correspondence that survived"
        )
    ratio: MetricValue
    if n_putative == 0:
        ratio = MetricValue(
            "inlier_ratio", None, MetricKind.COUNT, "fraction",
            undefined_reason="no putative correspondences",
        )
    else:
        ratio = MetricValue(
            "inlier_ratio", float(n_inliers) / float(n_putative),
            MetricKind.COUNT, "fraction",
            caveat="Supporting evidence only; never decisive.",
        )
    return MetricSet(
        (
            MetricValue("n_putative", int(n_putative), MetricKind.COUNT, "count"),
            MetricValue("n_inliers", int(n_inliers), MetricKind.COUNT, "count",
                        caveat="Primary acceptance signal (rule: reject at <= 8)."),
            ratio,
        )
    )


def absolute_error(
    predicted: ArrayLike,
    truth: ArrayLike,
    *,
    reference: str,
) -> MetricSet:
    """Error against positions the matcher never saw.

    ``reference`` names where truth came from and must be one of
    ``GROUND_TRUTH`` or ``CHECK_POINTS``. There is deliberately no option for
    deriving truth from the fit: that would be the circularity this whole
    module exists to prevent.
    """
    if reference not in ("GROUND_TRUTH", "CHECK_POINTS"):
        raise ValueError(
            f"reference={reference!r} must be GROUND_TRUTH or CHECK_POINTS. "
            "Truth derived from the fit is not truth."
        )
    p = np.asarray(predicted, dtype=float)
    t = np.asarray(truth, dtype=float)
    if p.shape != t.shape:
        raise ValueError(f"shape mismatch: predicted {p.shape} vs truth {t.shape}")
    if p.size == 0:
        reason = "no points to compare"
        return MetricSet(
            (
                MetricValue("abs_err_px", None, MetricKind.ACCURACY, "px",
                            undefined_reason=reason),
                MetricValue("abs_err_max_px", None, MetricKind.ACCURACY, "px",
                            undefined_reason=reason),
            )
        )
    d = np.linalg.norm(p.reshape(-1, p.shape[-1]) - t.reshape(-1, t.shape[-1]), axis=1)
    note = f"Measured against {reference}."
    return MetricSet(
        (
            MetricValue("abs_err_px", float(np.median(d)), MetricKind.ACCURACY,
                        "px", caveat=note),
            MetricValue("abs_err_max_px", float(np.max(d)), MetricKind.ACCURACY,
                        "px", caveat=note),
        )
    )


def aggregate_rates(rows: Iterable[Mapping[str, Any]]) -> MetricSet:
    """False acceptance, false rejection and inconclusive rates over a run.

    A **wrong pass** is a row that satisfied the acceptance rule while the
    transform is independently established to be wrong. False acceptance is
    the operationally important number: a system that is right 90 per cent of
    the time and knows which 10 per cent is worth more than one that is right
    95 per cent and cannot tell you when it is not.

    Rows are mappings carrying ``verdict`` and optionally ``wrong_pass`` and
    ``known_correct``. Rows missing a field are excluded from the rate that
    needs it, and the denominator reports how many contributed.
    """
    rows = list(rows)
    n = len(rows)
    passes = [r for r in rows if r.get("verdict") == "VERIFIED"]
    rejects = [r for r in rows if r.get("verdict") == "REJECTED"]
    inconclusive = [r for r in rows if r.get("verdict") == "INCONCLUSIVE"]

    # A row counts as scored only when it carries an actual determination.
    # A present-but-None ``wrong_pass`` means "not checked", and treating it as
    # "checked and clean" would report a false acceptance rate of zero for a
    # run in which nothing was verified at all. "0 wrong passes in 76" has to
    # mean 76 were checked.
    scored = [r for r in passes if r.get("wrong_pass") is not None]
    n_wrong = sum(1 for r in scored if r.get("wrong_pass"))
    far: MetricValue
    if not scored:
        far = MetricValue(
            "false_acceptance_rate", None, MetricKind.INDEPENDENT_CHECK, "fraction",
            undefined_reason=(
                "no accepted row carries a wrong_pass determination; without an "
                "independent check a pass cannot be scored"
            ),
        )
    else:
        far = MetricValue(
            "false_acceptance_rate", n_wrong / len(scored),
            MetricKind.INDEPENDENT_CHECK, "fraction",
            caveat=f"Over {len(scored)} scored acceptances.",
        )

    known = [r for r in rows if r.get("known_correct") is True]
    frr: MetricValue
    if not known:
        frr = MetricValue(
            "false_rejection_rate", None, MetricKind.INDEPENDENT_CHECK, "fraction",
            undefined_reason="no row is independently established as correct",
        )
    else:
        n_rej = sum(1 for r in known if r.get("verdict") == "REJECTED")
        frr = MetricValue(
            "false_rejection_rate", n_rej / len(known),
            MetricKind.INDEPENDENT_CHECK, "fraction",
            caveat=f"Over {len(known)} independently correct cases.",
        )

    inc: MetricValue
    if n == 0:
        inc = MetricValue(
            "inconclusive_rate", None, MetricKind.COUNT, "fraction",
            undefined_reason="no rows",
        )
    else:
        inc = MetricValue("inconclusive_rate", len(inconclusive) / n,
                          MetricKind.COUNT, "fraction")

    return MetricSet(
        (
            MetricValue("n_rows", n, MetricKind.COUNT, "count"),
            MetricValue("n_verified", len(passes), MetricKind.COUNT, "count"),
            MetricValue("n_rejected", len(rejects), MetricKind.COUNT, "count"),
            MetricValue("n_inconclusive", len(inconclusive), MetricKind.COUNT,
                        "count"),
            MetricValue("n_wrong_passes", n_wrong, MetricKind.COUNT, "count"),
            far,
            frr,
            inc,
        )
    )
