"""What data the benchmarks need, and whether the data in hand supplies it.

The problem statement names three Chandrayaan-2 payloads. Holding a product
from each is not the same as holding a usable experiment: two products only
form a pair if they cover the same ground, and they only test illumination
invariance if their illumination actually differs.

This module states each requirement as checkable criteria and reports, for a
given set of products, which requirements are satisfiable and what is missing
from the ones that are not. It exists so that a 12.7 GB download is decided
before it is started rather than after.

The criteria are not arbitrary. The incidence bands come from this project's
own measured envelope: across 42 real pairs, 14 frames and three engines,
**no engine registered any pair above 39.8 degrees of incidence difference**,
and the last 5-degree bin with a success rate at or above 0.8 was 20-25
degrees. A requirement asking for a pair outside that envelope is asking for a
measured failure, which is sometimes exactly what is wanted, and is then
labelled as such.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from .manifest import ProductManifest

__all__ = [
    "REQUIREMENTS",
    "PairRequirement",
    "RequirementStatus",
    "AcquisitionReport",
    "assess_products",
    "requirement_by_id",
    "co_located",
    "spans_overlap",
]

#: Above this incidence difference nothing in this project has ever registered.
#: Measured, REAL-DATA-07, 42 pairs, three engines.
MEASURED_ENVELOPE_DEG = 39.8

#: Last 5-degree bin with success rate at or above 0.8. Measured, same stage.
COMFORTABLE_ENVELOPE_DEG = 25.0


def spans_overlap(a: tuple[float, float] | None,
                  b: tuple[float, float] | None) -> bool | None:
    """Whether two (min, max) spans intersect. ``None`` if either is unknown."""
    if a is None or b is None:
        return None
    return not (a[1] < b[0] or b[1] < a[0])


def co_located(a: ProductManifest, b: ProductManifest) -> bool | None:
    """Whether two products' corner footprints intersect in both axes.

    This is a **necessary** condition, not a sufficient one: bounding-box
    intersection is coarser than true polygon overlap, and the real gate is the
    geometry module. A ``False`` here is decisive; a ``True`` only means the
    pair is worth putting through the proper overlap check.
    """
    lat = spans_overlap(a.latitude_span(), b.latitude_span())
    lon = spans_overlap(a.longitude_span(), b.longitude_span())
    if lat is None or lon is None:
        return None
    return bool(lat and lon)


@dataclass(frozen=True)
class PairRequirement:
    """One pairing a benchmark needs, with criteria that can be checked."""

    requirement_id: str
    title: str
    source_instrument: str
    reference_instrument: str
    #: Why this pairing exists at all.
    rationale: str
    #: Benchmark ids from ``05_BENCHMARK_PROTOCOL`` this unblocks.
    unblocks: tuple[str, ...] = field(default_factory=tuple)
    #: Inclusive band on |delta incidence|, degrees. ``None`` means unconstrained.
    incidence_delta_band: tuple[float, float] | None = None
    #: Inclusive band on the coarser-over-finer resolution ratio.
    scale_ratio_band: tuple[float, float] | None = None
    #: Whether the two products must cover the same ground.
    require_co_location: bool = True
    #: Minimum distinct products of the source instrument needed.
    min_source_products: int = 1
    #: Require the two products to come from different acquisitions. An image
    #: and its own derived orthoimage are two products of one look, not two
    #: viewing geometries, and pairing them proves nothing about viewpoint or
    #: illumination.
    require_distinct_acquisition: bool = False
    #: True when this requirement deliberately asks for a regime expected to
    #: fail, so that the boundary is measured rather than assumed.
    expects_failure: bool = False
    priority: int = 3

    def check(self, source: ProductManifest,
              reference: ProductManifest) -> list[str]:
        """Return the reasons this pairing does not satisfy the requirement.

        An empty list means every checkable criterion is met. Criteria that
        cannot be evaluated, because a label field is missing, are reported as
        unknown rather than silently passed.
        """
        problems: list[str] = []
        if source.instrument != self.source_instrument:
            problems.append(
                f"source is {source.instrument}, requirement needs "
                f"{self.source_instrument}"
            )
        if reference.instrument != self.reference_instrument:
            problems.append(
                f"reference is {reference.instrument}, requirement needs "
                f"{self.reference_instrument}"
            )
        if self.require_distinct_acquisition:
            sa, ra = source.acquisition_time, reference.acquisition_time
            if sa is None or ra is None:
                problems.append(
                    "distinct acquisition unknown: acquisition_time missing"
                )
            elif sa == ra:
                problems.append(
                    f"both products come from the same acquisition ({sa}); "
                    "an image and its derived products are one look, not two"
                )
        if self.require_co_location:
            same = co_located(source, reference)
            if same is None:
                problems.append("co-location unknown: corner geometry missing")
            elif not same:
                problems.append(
                    "products do not cover the same ground "
                    f"(source lat {source.latitude_span()}, "
                    f"reference lat {reference.latitude_span()})"
                )
        if self.incidence_delta_band is not None:
            lo, hi = self.incidence_delta_band
            si, ri = source.solar_incidence_deg, reference.solar_incidence_deg
            if si is None or ri is None:
                problems.append("incidence difference unknown: label field missing")
            else:
                delta = abs(si - ri)
                if not (lo <= delta <= hi):
                    problems.append(
                        f"incidence difference {delta:.1f} deg outside the "
                        f"required band [{lo}, {hi}]"
                    )
        if self.scale_ratio_band is not None:
            lo, hi = self.scale_ratio_band
            sr, rr = source.pixel_resolution_m, reference.pixel_resolution_m
            if sr is None or rr is None:
                problems.append("scale ratio unknown: pixel_resolution missing")
            else:
                coarse, fine = (sr, rr) if sr >= rr else (rr, sr)
                ratio = coarse / fine
                if not (lo <= ratio <= hi):
                    problems.append(
                        f"scale ratio {ratio:.1f}:1 outside the required band "
                        f"[{lo}, {hi}]"
                    )
        return problems


#: The requirements, ordered by priority. Priority 1 is the work that unlocks
#: the most requirement coverage for the least acquisition.
REQUIREMENTS: tuple[PairRequirement, ...] = (
    PairRequirement(
        requirement_id="R-OHRC-NAC",
        title="OHRC against an LRO NAC reference over the same ground",
        source_instrument="OHRC",
        reference_instrument="LRO_NAC",
        rationale=(
            "The problem statement's reference imagery is LRO NAC. Two OHRC "
            "products are already on disk and cannot be registered to anything "
            "because no NAC frame covers their footprint. This is the cheapest "
            "route from zero Chandrayaan-2 results to one."
        ),
        unblocks=("B7", "B10", "B11"),
        incidence_delta_band=(0.0, COMFORTABLE_ENVELOPE_DEG),
        scale_ratio_band=(1.0, 8.0),
        priority=1,
    ),
    PairRequirement(
        requirement_id="R-TMC-NAC",
        title="TMC-2 orthoimage against LRO NAC degraded to the TMC-2 scale",
        source_instrument="TMC-2",
        reference_instrument="LRO_NAC",
        rationale=(
            "TMC-2 is the only payload delivering a map-projected orthoimage "
            "and a co-registered terrain model, which makes this the easiest "
            "Chandrayaan-2 pairing to pose correctly."
        ),
        unblocks=("B3", "B10"),
        incidence_delta_band=(0.0, COMFORTABLE_ENVELOPE_DEG),
        scale_ratio_band=(1.0, 12.0),
        priority=1,
    ),
    PairRequirement(
        requirement_id="R-IIRS-WAC",
        title="IIRS reflectance composite against the LROC WAC 100 m mosaic",
        source_instrument="IIRS",
        reference_instrument="LRO_WAC",
        rationale=(
            "The only genuine modality gap among the three named payloads. "
            "IIRS below roughly 2 micrometres and WAC are both passive "
            "reflected sunlight at a ratio near 1.25:1, which makes this the "
            "easiest available cross-modal test. Without it the multi-modal "
            "element of the problem statement is unaddressed."
        ),
        unblocks=("B6",),
        incidence_delta_band=(0.0, COMFORTABLE_ENVELOPE_DEG),
        scale_ratio_band=(1.0, 2.0),
        priority=1,
    ),
    PairRequirement(
        requirement_id="R-OHRC-ILLUM",
        title="Two OHRC products over one site with a real illumination difference",
        source_instrument="OHRC",
        reference_instrument="OHRC",
        rationale=(
            "The two OHRC products on disk were acquired 5 h 50 m apart on the "
            "same day and differ by 0.9 degrees in Sun azimuth. They are a "
            "same-illumination control, not an illumination experiment. Any "
            "invariance claim made on that pair would be NOT VALIDATED."
        ),
        unblocks=("B2", "B7"),
        incidence_delta_band=(10.0, COMFORTABLE_ENVELOPE_DEG),
        require_distinct_acquisition=True,
        min_source_products=2,
        priority=2,
    ),
    PairRequirement(
        requirement_id="R-OHRC-TMC",
        title="OHRC against TMC-2 over the same ground",
        source_instrument="OHRC",
        reference_instrument="TMC-2",
        rationale=(
            "The in-mission scale step, nominally 20:1. No co-located "
            "cross-instrument pair exists on disk: the TMC-2 strip is "
            "equatorial and both OHRC products are south polar."
        ),
        unblocks=("B3", "B6"),
        incidence_delta_band=(0.0, COMFORTABLE_ENVELOPE_DEG),
        scale_ratio_band=(10.0, 30.0),
        priority=2,
    ),
    PairRequirement(
        requirement_id="R-OHRC-IIRS",
        title="OHRC located inside an IIRS pixel, the full scale ladder",
        source_instrument="OHRC",
        reference_instrument="IIRS",
        rationale=(
            "The nominal 320:1 rung implied by the instrument specifications. "
            "It has never been attempted at any ratio near it, so it is a "
            "design target, not a demonstrated capability."
        ),
        unblocks=("B3", "B6"),
        scale_ratio_band=(200.0, 400.0),
        priority=3,
    ),
    PairRequirement(
        requirement_id="R-TMC-VIEWPOINT",
        title="TMC-2 fore and aft products to complete a stereo triplet",
        source_instrument="TMC-2",
        reference_instrument="TMC-2",
        rationale=(
            "Viewpoint variation is not named by the problem statement but "
            "arises unavoidably from the stereo triplet and from off-nadir "
            "OHRC. The bundle on disk is nadir only."
        ),
        unblocks=("B5",),
        require_distinct_acquisition=True,
        min_source_products=2,
        priority=3,
    ),
    PairRequirement(
        requirement_id="R-OHRC-POLAR-CEILING",
        title="OHRC pair beyond the measured illumination envelope",
        source_instrument="OHRC",
        reference_instrument="OHRC",
        rationale=(
            "A characterised failure boundary at the illumination regime of "
            "the lunar south pole is more useful to a landing programme than "
            "an unbounded success claim. This requirement deliberately asks "
            "for a regime the measured envelope says will fail."
        ),
        unblocks=("B7",),
        incidence_delta_band=(MEASURED_ENVELOPE_DEG, 90.0),
        require_distinct_acquisition=True,
        min_source_products=2,
        expects_failure=True,
        priority=4,
    ),
)


def requirement_by_id(requirement_id: str) -> PairRequirement:
    """Look up a requirement, raising ``KeyError`` when it does not exist."""
    for req in REQUIREMENTS:
        if req.requirement_id == requirement_id:
            return req
    raise KeyError(
        f"no requirement {requirement_id!r}; known: "
        f"{[r.requirement_id for r in REQUIREMENTS]}"
    )


@dataclass(frozen=True)
class RequirementStatus:
    """Whether one requirement can be satisfied by the products in hand."""

    requirement: PairRequirement
    satisfied: bool
    #: Product id pairs that satisfy it, best first.
    satisfying_pairs: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    #: Why the nearest candidates failed, keyed by the pair that was tried.
    near_misses: tuple[tuple[tuple[str, str], tuple[str, ...]], ...] = field(
        default_factory=tuple
    )
    #: What to acquire, in plain language, when unsatisfied.
    missing: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "requirement_id": self.requirement.requirement_id,
            "title": self.requirement.title,
            "priority": self.requirement.priority,
            "satisfied": self.satisfied,
            "expects_failure": self.requirement.expects_failure,
            "unblocks": list(self.requirement.unblocks),
            "satisfying_pairs": [list(p) for p in self.satisfying_pairs],
            "near_misses": [
                {"pair": list(pair), "problems": list(problems)}
                for pair, problems in self.near_misses
            ],
            "missing": self.missing,
            "rationale": self.requirement.rationale,
        }


@dataclass(frozen=True)
class AcquisitionReport:
    """The full picture: what is satisfiable now, and what to go and get."""

    statuses: tuple[RequirementStatus, ...]
    n_products: int
    instruments_present: tuple[str, ...]

    @property
    def satisfied(self) -> tuple[RequirementStatus, ...]:
        return tuple(s for s in self.statuses if s.satisfied)

    @property
    def unsatisfied(self) -> tuple[RequirementStatus, ...]:
        return tuple(s for s in self.statuses if not s.satisfied)

    def shopping_list(self) -> tuple[str, ...]:
        """What to acquire, ordered by priority then requirement id."""
        rows = sorted(
            self.unsatisfied,
            key=lambda s: (s.requirement.priority, s.requirement.requirement_id),
        )
        return tuple(
            f"[P{s.requirement.priority}] {s.requirement.requirement_id}: {s.missing}"
            for s in rows
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "n_products": self.n_products,
            "instruments_present": list(self.instruments_present),
            "n_satisfied": len(self.satisfied),
            "n_unsatisfied": len(self.unsatisfied),
            "statuses": [s.as_dict() for s in self.statuses],
            "shopping_list": list(self.shopping_list()),
        }


def _missing_text(req: PairRequirement,
                  present: set[str],
                  n_source: int) -> str:
    """Plain-language statement of what to acquire for one requirement."""
    if req.source_instrument not in present:
        return (
            f"no {req.source_instrument} product is held at all. Acquire one "
            f"covering the same ground as a {req.reference_instrument} product."
        )
    if req.reference_instrument not in present:
        return (
            f"no {req.reference_instrument} product is held. Acquire one "
            f"covering the footprint of an existing {req.source_instrument} "
            "product."
        )
    if n_source < req.min_source_products:
        return (
            f"only {n_source} {req.source_instrument} product(s) held; this "
            f"requirement needs {req.min_source_products} over one site."
        )
    band = ""
    if req.incidence_delta_band is not None:
        lo, hi = req.incidence_delta_band
        band = f", with an incidence difference between {lo:g} and {hi:g} degrees"
    return (
        f"products of both instruments are held but no pairing meets the "
        f"criteria. Acquire a {req.source_instrument} and "
        f"{req.reference_instrument} pair over common ground{band}."
    )


def assess_products(
    products: Iterable[ProductManifest],
    requirements: Sequence[PairRequirement] = REQUIREMENTS,
) -> AcquisitionReport:
    """Report which requirements the given products can satisfy.

    Pairings are tried in both directions where the two instruments differ,
    because which product is the source is a choice, not a property of the
    data. Self-pairings of one product with itself are never offered.
    """
    items = list(products)
    present = {p.instrument for p in items}
    statuses: list[RequirementStatus] = []

    for req in requirements:
        hits: list[tuple[str, str]] = []
        misses: list[tuple[tuple[str, str], tuple[str, ...]]] = []
        n_source = sum(1 for p in items if p.instrument == req.source_instrument)

        for a in items:
            for b in items:
                if a.product_id == b.product_id:
                    continue
                if a.instrument != req.source_instrument:
                    continue
                if b.instrument != req.reference_instrument:
                    continue
                problems = req.check(a, b)
                key = (a.product_id, b.product_id)
                if problems:
                    misses.append((key, tuple(problems)))
                else:
                    hits.append(key)

        satisfied = bool(hits)
        statuses.append(
            RequirementStatus(
                requirement=req,
                satisfied=satisfied,
                satisfying_pairs=tuple(hits),
                near_misses=tuple(misses[:6]),
                missing="" if satisfied else _missing_text(req, present, n_source),
            )
        )

    return AcquisitionReport(
        statuses=tuple(statuses),
        n_products=len(items),
        instruments_present=tuple(sorted(present)),
    )
