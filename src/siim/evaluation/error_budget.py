"""An accuracy budget: named terms, their sources, and what is still missing.

Why this exists
---------------
The project has repeatedly described its accuracy claim as "traceable" without
ever writing the budget down. A budget is the object that makes traceability
checkable: every term named, every term sourced, every term either measured,
quoted from a publication, or **explicitly pending** -- and a total that
refuses to present itself as complete while any term is pending.

That refusal is the whole point. A budget with three of six terms filled and a
confident-looking total is worse than no budget, because it converts an
unknown into a number. :meth:`ErrorBudget.total` therefore returns a
:class:`BudgetTotal` carrying ``complete``; a caller that prints the value and
ignores the flag is doing the thing this module exists to prevent.

Metrology, not statistics
-------------------------
Terms combine according to their kind, not uniformly:

* ``RANDOM`` terms are independent and combine **in quadrature** (root sum of
  squares). Interpolation noise, correspondence localisation scatter.
* ``SYSTEMATIC`` terms are biases that can align, so they combine **linearly**
  -- the conservative choice, and the correct one when the correlation between
  them is unknown rather than known to be zero. A control product's positional
  offset and a resampling convention error are of this kind.

Mixing the two by RSS-ing everything is the standard way to understate a
budget, and it is a mistake a reviewer at a space agency will look for first.

Units
-----
Terms are stored in **metres**, because the geodetic references are published
in metres and a pixel is not a unit of length until a ground sample distance is
named. :meth:`ErrorBudget.in_pixels` converts at an explicit GSD, so the
conversion is always visible rather than assumed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

__all__ = ["TermKind", "TermStatus", "BudgetTerm", "BudgetTotal", "ErrorBudget"]


class TermKind(Enum):
    """How a term combines with the others."""

    RANDOM = "random"          # independent -> quadrature
    SYSTEMATIC = "systematic"  # may align -> linear sum


class TermStatus(Enum):
    """Where the number came from, or that it does not exist yet."""

    MEASURED = "measured"    # this project measured it, artefact recorded
    PUBLISHED = "published"  # quoted from a cited source
    PENDING = "pending"      # not yet determined -- blocks a complete total


@dataclass(frozen=True)
class BudgetTerm:
    """One contribution to the total error, with its provenance attached."""

    name: str
    kind: TermKind
    status: TermStatus
    #: One-sigma equivalent magnitude in metres. ``None`` iff status is PENDING.
    metres: float | None
    #: Where this number comes from: an artefact path, a citation, or the
    #: experiment that would determine it if pending. Never optional.
    source: str
    note: str = ""

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError(f"term {self.name!r} has no source; every term must be traceable")
        if self.status is TermStatus.PENDING:
            if self.metres is not None:
                raise ValueError(f"pending term {self.name!r} must not carry a value")
        else:
            if self.metres is None:
                raise ValueError(f"term {self.name!r} is {self.status.value} but has no value")
            if not math.isfinite(self.metres) or self.metres < 0:
                raise ValueError(f"term {self.name!r} must be finite and non-negative")


@dataclass(frozen=True)
class BudgetTotal:
    """A combined figure, and whether it is allowed to be called a total."""

    metres: float
    random_component: float
    systematic_component: float
    #: False when any term is pending. The value is then a LOWER BOUND on the
    #: true error, and must be reported as one.
    complete: bool
    pending_terms: tuple[str, ...]

    def as_pixels(self, gsd_m: float) -> float:
        if not (math.isfinite(gsd_m) and gsd_m > 0):
            raise ValueError("gsd_m must be positive and finite")
        return self.metres / gsd_m

    @property
    def statement(self) -> str:
        """The sentence this budget is entitled to put in a document."""
        if self.complete:
            return f"Total accuracy budget: {self.metres:.2f} m (1 sigma equivalent)."
        missing = ", ".join(self.pending_terms)
        return (
            f"Accuracy budget is INCOMPLETE: {self.metres:.2f} m from the terms "
            f"determined so far, which is a LOWER BOUND. Pending: {missing}."
        )

    def __repr__(self) -> str:  # pragma: no cover - display only
        tag = "complete" if self.complete else f"incomplete ({len(self.pending_terms)} pending)"
        return f"BudgetTotal({self.metres:.3f} m, {tag})"


@dataclass(frozen=True)
class ErrorBudget:
    """A named collection of terms that knows what it does not yet know."""

    label: str
    terms: tuple[BudgetTerm, ...] = field(default_factory=tuple)

    def with_term(self, term: BudgetTerm) -> "ErrorBudget":
        if any(t.name == term.name for t in self.terms):
            raise ValueError(f"duplicate term {term.name!r}")
        return ErrorBudget(self.label, self.terms + (term,))

    def resolve(self, name: str, metres: float, *, status: TermStatus, source: str) -> "ErrorBudget":
        """Fill in a pending term once its experiment has run."""
        out = []
        found = False
        for t in self.terms:
            if t.name == name:
                if t.status is not TermStatus.PENDING:
                    raise ValueError(f"term {name!r} is already {t.status.value}")
                out.append(BudgetTerm(t.name, t.kind, status, metres, source, t.note))
                found = True
            else:
                out.append(t)
        if not found:
            raise KeyError(f"no term named {name!r}")
        return ErrorBudget(self.label, tuple(out))

    @property
    def pending(self) -> tuple[str, ...]:
        return tuple(t.name for t in self.terms if t.status is TermStatus.PENDING)

    def total(self) -> BudgetTotal:
        """Combine the determined terms; never hide that others are missing."""
        known = [t for t in self.terms if t.status is not TermStatus.PENDING]
        rand = math.sqrt(sum(t.metres**2 for t in known if t.kind is TermKind.RANDOM))
        syst = sum(t.metres for t in known if t.kind is TermKind.SYSTEMATIC)
        return BudgetTotal(
            metres=rand + syst,
            random_component=rand,
            systematic_component=syst,
            complete=not self.pending,
            pending_terms=self.pending,
        )

    def in_pixels(self, gsd_m: float) -> float:
        return self.total().as_pixels(gsd_m)

    def to_dict(self) -> dict:
        t = self.total()
        return {
            "label": self.label,
            "terms": [
                {
                    "name": x.name,
                    "kind": x.kind.value,
                    "status": x.status.value,
                    "metres": x.metres,
                    "source": x.source,
                    "note": x.note,
                }
                for x in self.terms
            ],
            "total_metres": t.metres,
            "random_component_metres": t.random_component,
            "systematic_component_metres": t.systematic_component,
            "complete": t.complete,
            "pending_terms": list(t.pending_terms),
            "statement": t.statement,
        }


def nac_reference_budget() -> ErrorBudget:
    """The budget for registering an image against an LROC NAC controlled mosaic.

    This is the project's *nearest reachable* accuracy chain, and writing it
    down shows immediately what it is short of. Two terms are published and
    citable today; three are pending and each names the experiment that would
    determine it. The total is therefore a lower bound and says so.

    Note what is deliberately **absent**: the fit residual. A fit RMSE measures
    self-consistency, not accuracy (ADR-0003), and this project has a recorded
    real edge reporting 1.885e-13 px on a transform independently measured 797
    px wrong. It is not a budget term and admitting it as one would be the
    single most misleading thing this module could do.
    """
    return ErrorBudget("registration against an LROC NAC controlled mosaic").with_term(
        BudgetTerm(
            "control_product_absolute_position",
            TermKind.SYSTEMATIC,
            TermStatus.PUBLISHED,
            13.0,
            "sources.md S9 -- NAC regional controlled mosaics, average measured "
            "offset <13 m (median <12 m latitude, <5 m longitude)",
            "A bias of the reference itself. Nothing measured against this "
            "product can be more accurate than this term, whatever the matcher does.",
        )
    ).with_term(
        BudgetTerm(
            "geodetic_frame_realisation",
            TermKind.SYSTEMATIC,
            TermStatus.PUBLISHED,
            10.0,
            "sources.md S9 -- LOLA absolute accuracy typically <10 m horizontal",
            "The frame the control product is tied to. Conservative: taken at "
            "its stated upper bound rather than a typical value.",
        )
    ).with_term(
        BudgetTerm(
            "anchoring_residual",
            TermKind.RANDOM,
            TermStatus.PENDING,
            None,
            "PENDING -- determined by matching an archive tile against the "
            "controlled mosaic and measuring the disagreement",
            "The first experiment worth running. Until it exists the budget "
            "cannot be closed and no accuracy figure is defensible.",
        )
    ).with_term(
        BudgetTerm(
            "correspondence_localisation",
            TermKind.RANDOM,
            TermStatus.PENDING,
            None,
            "PENDING -- requires a sub-pixel refinement stage that emits a "
            "per-correspondence uncertainty; none exists",
            "Currently unmeasurable rather than merely unmeasured.",
        )
    ).with_term(
        BudgetTerm(
            "resampling_and_interpolation",
            TermKind.SYSTEMATIC,
            TermStatus.PENDING,
            None,
            "PENDING -- bounded by the EXP-000 geometry gate (~1e-13 px on "
            "synthetic recovery) but not yet measured on decimated real tiles",
            "The geometry layer makes this small; small is not zero, and the "
            "decimation applied to every real tile so far has not been "
            "characterised.",
        )
    )
