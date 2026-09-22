"""Dataset and pair manifests.

A **product manifest** describes one archive product as delivered: what it is,
where it came from, and the geometry and illumination its own label reports.
Every field that the label carries is read from the label. Nothing here is
assumed from an instrument specification sheet, because delivered resolution
varies with as-flown altitude and the specification is a nominal nadir figure.

A **pair manifest** describes one source-to-reference pairing and the
conditions under which it may be matched. Its central rule:

    A pair whose overlap is not CONFIRMED is not runnable.

That is not a convention. Establishing overlap before interpreting anything is
what separates "the matcher found nothing" from "there was nothing to find":
the project's first real failure was two tiles 22.75 km apart that shared no
ground at all, and the matcher's silence measured nothing about the matcher.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "CORPUS_CLASSES",
    "GROUND_TRUTH_KINDS",
    "OVERLAP_STATUSES",
    "RATIO_SOURCES",
    "ProductManifest",
    "PairManifest",
    "load_product_manifest",
    "load_pair_manifest",
]

#: What the data actually is. There is no default: a caller must say.
#: ``PROXY`` covers every LRO stand-in. ``CHANDRAYAAN2`` is reserved for real
#: OHRC, TMC-2 or IIRS pixels and must never be used for a stand-in.
CORPUS_CLASSES = ("SYNTHETIC", "SELF_WARP", "PROXY", "CHANDRAYAAN2")

#: What truth, if any, a result can be compared against.
#: ``CORROBORATION_ONLY`` means archive geometry agrees at its own resolution,
#: which for this project's LRO corpus is roughly 100 px. It is not accuracy.
GROUND_TRUTH_KINDS = ("EXACT", "CHECK_POINTS", "CORROBORATION_ONLY", "NONE")

#: Overlap gate outcome. Only CONFIRMED permits matching.
OVERLAP_STATUSES = ("CONFIRMED", "NOT_CONFIRMED", "UNKNOWN")

#: Where a scale ratio came from. ``NOMINAL`` is an instrument specification
#: and is NOT a property of the delivered products; ``LABEL`` is measured.
RATIO_SOURCES = ("LABEL", "PAPER", "NOMINAL", "UNKNOWN")

_INSTRUMENTS = ("OHRC", "TMC-2", "IIRS", "LRO_NAC", "LRO_WAC", "MINI_RF",
                "SELENE_TC", "SYNTHETIC")


def _require(value: Any, allowed: tuple[str, ...], field_name: str) -> str:
    if value not in allowed:
        raise ValueError(
            f"{field_name}={value!r} is not one of {allowed}. "
            "This field has no default: state it explicitly."
        )
    return str(value)


@dataclass(frozen=True)
class ProductManifest:
    """One archive product, as delivered.

    ``pixel_resolution_m`` is the value the product's own label reports, not
    the instrument's nominal figure. The two differ: OHRC is specified at
    0.25 m nadir from 100 km but a delivered product acquired at 102.33 km
    reports 0.26 m. Reading it from the label is the only correct behaviour.
    """

    product_id: str
    instrument: str
    corpus_class: str
    processing_level: str = "unknown"
    path: str | None = None
    sha256: str | None = None
    file_size: int | None = None
    #: (lines, samples), from the label's Axis_Array element counts.
    shape: tuple[int, int] | None = None
    data_type: str | None = None
    #: Metres per pixel, READ FROM THE LABEL. Never a specification value.
    pixel_resolution_m: float | None = None
    spacecraft_altitude_km: float | None = None
    #: Degrees. ``None`` where the archive does not publish the field, which is
    #: the case for LRO NAC sub-solar azimuth.
    sun_azimuth_deg: float | None = None
    sun_elevation_deg: float | None = None
    solar_incidence_deg: float | None = None
    emission_angle_deg: float | None = None
    #: ((lat, lon), ...) for upper-left, upper-right, lower-left, lower-right.
    corners_lat_lon: tuple[tuple[float, float], ...] | None = None
    orbit_number: int | None = None
    #: Acquisition start, from the label. Two products of one acquisition (an
    #: image and its derived ortho, say) are not two viewing geometries, and
    #: requirements that need genuinely distinct looks compare this.
    acquisition_time: str | None = None
    #: True when the corner-map determinant is positive, i.e. the frame is a
    #: reflection. A rotation cannot undo a reflection.
    mirrored: bool | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        _require(self.corpus_class, CORPUS_CLASSES, "corpus_class")
        if self.instrument not in _INSTRUMENTS:
            raise ValueError(
                f"instrument={self.instrument!r} is not one of {_INSTRUMENTS}"
            )
        if self.pixel_resolution_m is not None and self.pixel_resolution_m <= 0:
            raise ValueError("pixel_resolution_m must be positive when given")
        if self.corpus_class == "CHANDRAYAAN2" and self.instrument not in (
            "OHRC", "TMC-2", "IIRS"
        ):
            raise ValueError(
                f"corpus_class=CHANDRAYAAN2 with instrument={self.instrument!r}: "
                "only OHRC, TMC-2 and IIRS are Chandrayaan-2 payloads"
            )

    @property
    def is_chandrayaan2(self) -> bool:
        return self.corpus_class == "CHANDRAYAAN2"

    @property
    def megapixels(self) -> float | None:
        if self.shape is None:
            return None
        return self.shape[0] * self.shape[1] / 1e6

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "product_id": self.product_id,
            "instrument": self.instrument,
            "corpus_class": self.corpus_class,
            "processing_level": self.processing_level,
            "path": self.path,
            "sha256": self.sha256,
            "file_size": self.file_size,
            "shape": list(self.shape) if self.shape else None,
            "data_type": self.data_type,
            "pixel_resolution_m": self.pixel_resolution_m,
            "spacecraft_altitude_km": self.spacecraft_altitude_km,
            "sun_azimuth_deg": self.sun_azimuth_deg,
            "sun_elevation_deg": self.sun_elevation_deg,
            "solar_incidence_deg": self.solar_incidence_deg,
            "emission_angle_deg": self.emission_angle_deg,
            "corners_lat_lon": (
                [list(c) for c in self.corners_lat_lon] if self.corners_lat_lon else None
            ),
            "orbit_number": self.orbit_number,
            "acquisition_time": self.acquisition_time,
            "mirrored": self.mirrored,
            "notes": self.notes,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ProductManifest":
        shape = d.get("shape")
        corners = d.get("corners_lat_lon")
        return cls(
            product_id=d["product_id"],
            instrument=d["instrument"],
            corpus_class=d["corpus_class"],
            processing_level=d.get("processing_level", "unknown"),
            path=d.get("path"),
            sha256=d.get("sha256"),
            file_size=d.get("file_size"),
            shape=(int(shape[0]), int(shape[1])) if shape else None,
            data_type=d.get("data_type"),
            pixel_resolution_m=d.get("pixel_resolution_m"),
            spacecraft_altitude_km=d.get("spacecraft_altitude_km"),
            sun_azimuth_deg=d.get("sun_azimuth_deg"),
            sun_elevation_deg=d.get("sun_elevation_deg"),
            solar_incidence_deg=d.get("solar_incidence_deg"),
            emission_angle_deg=d.get("emission_angle_deg"),
            corners_lat_lon=(
                tuple((float(a), float(b)) for a, b in corners) if corners else None
            ),
            orbit_number=d.get("orbit_number"),
            acquisition_time=d.get("acquisition_time"),
            mirrored=d.get("mirrored"),
            notes=d.get("notes", ""),
        )

    def latitude_span(self) -> tuple[float, float] | None:
        """(min, max) latitude over the corners, or ``None`` if unknown."""
        if not self.corners_lat_lon:
            return None
        lats = [c[0] for c in self.corners_lat_lon]
        return (min(lats), max(lats))

    def longitude_span(self) -> tuple[float, float] | None:
        """(min, max) longitude over the corners, or ``None`` if unknown.

        No meridian-wrap handling: these products do not cross 0/360 in the
        cases this project handles, and silently guessing would be worse than
        refusing. Callers spanning the meridian must handle it themselves.
        """
        if not self.corners_lat_lon:
            return None
        lons = [c[1] for c in self.corners_lat_lon]
        return (min(lons), max(lons))


@dataclass(frozen=True)
class PairManifest:
    """One source-to-reference pairing, and whether it may be matched.

    ``runnable`` is the gate. A pair is runnable only when its overlap has been
    CONFIRMED independently of the matcher. Everything else about the pair may
    be attractive and it still does not earn a pixel read.
    """

    pair_id: str
    source: ProductManifest
    reference: ProductManifest
    corpus_class: str
    ground_truth: str
    overlap_status: str = "UNKNOWN"
    overlap_fraction: float | None = None
    #: Monte-Carlo bounds on the overlap fraction from archive quantisation.
    overlap_bounds: tuple[float, float] | None = None
    scale_ratio: float | None = None
    scale_ratio_source: str = "UNKNOWN"
    delta_incidence_deg: float | None = None
    #: ``None`` means the archive does not publish sub-solar azimuth for these
    #: products, which is true of LRO NAC. It does not mean zero.
    delta_azimuth_deg: float | None = None
    #: Third product for loop closure, if one exists.
    third_product_id: str | None = None
    notes: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require(self.corpus_class, CORPUS_CLASSES, "corpus_class")
        _require(self.ground_truth, GROUND_TRUTH_KINDS, "ground_truth")
        _require(self.overlap_status, OVERLAP_STATUSES, "overlap_status")
        _require(self.scale_ratio_source, RATIO_SOURCES, "scale_ratio_source")
        if self.corpus_class == "CHANDRAYAAN2" and not (
            self.source.is_chandrayaan2 or self.reference.is_chandrayaan2
        ):
            raise ValueError(
                "pair corpus_class=CHANDRAYAAN2 but neither product is a "
                "Chandrayaan-2 product"
            )
        if self.scale_ratio is not None and self.scale_ratio <= 0:
            raise ValueError("scale_ratio must be positive when given")
        if self.scale_ratio is not None and self.scale_ratio_source == "UNKNOWN":
            raise ValueError(
                "a scale_ratio must name its source. NOMINAL is an instrument "
                "specification, LABEL is measured from the delivered products; "
                "they are not interchangeable."
            )

    @property
    def runnable(self) -> bool:
        """Whether matching this pair is permitted. See the module docstring."""
        return self.overlap_status == "CONFIRMED"

    def refusal_reason(self) -> str | None:
        """Why this pair may not be matched, or ``None`` if it may."""
        if self.overlap_status == "CONFIRMED":
            return None
        if self.overlap_status == "NOT_CONFIRMED":
            return (
                f"Overlap NOT CONFIRMED for {self.pair_id}: the two products are "
                "not established to share ground. Matching them would measure "
                "nothing about the matcher."
            )
        return (
            f"Overlap UNKNOWN for {self.pair_id}: the overlap gate has not been "
            "run. Run it before reading a pixel."
        )

    def measured_scale_ratio(self) -> float | None:
        """Scale ratio from the two products' own labels, or ``None``.

        This is the defensible figure. A ratio computed from instrument
        specification pages is nominal and describes the instruments, not the
        products in hand.
        """
        a = self.source.pixel_resolution_m
        b = self.reference.pixel_resolution_m
        if a is None or b is None:
            return None
        lo, hi = (a, b) if a <= b else (b, a)
        return hi / lo

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "source": self.source.to_dict(),
            "reference": self.reference.to_dict(),
            "corpus_class": self.corpus_class,
            "ground_truth": self.ground_truth,
            "overlap_status": self.overlap_status,
            "overlap_fraction": self.overlap_fraction,
            "overlap_bounds": (
                list(self.overlap_bounds) if self.overlap_bounds else None
            ),
            "scale_ratio": self.scale_ratio,
            "scale_ratio_source": self.scale_ratio_source,
            "measured_scale_ratio": self.measured_scale_ratio(),
            "delta_incidence_deg": self.delta_incidence_deg,
            "delta_azimuth_deg": self.delta_azimuth_deg,
            "third_product_id": self.third_product_id,
            "runnable": self.runnable,
            "refusal_reason": self.refusal_reason(),
            "notes": self.notes,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PairManifest":
        bounds = d.get("overlap_bounds")
        return cls(
            pair_id=d["pair_id"],
            source=ProductManifest.from_dict(d["source"]),
            reference=ProductManifest.from_dict(d["reference"]),
            corpus_class=d["corpus_class"],
            ground_truth=d["ground_truth"],
            overlap_status=d.get("overlap_status", "UNKNOWN"),
            overlap_fraction=d.get("overlap_fraction"),
            overlap_bounds=(
                (float(bounds[0]), float(bounds[1])) if bounds else None
            ),
            scale_ratio=d.get("scale_ratio"),
            scale_ratio_source=d.get("scale_ratio_source", "UNKNOWN"),
            delta_incidence_deg=d.get("delta_incidence_deg"),
            delta_azimuth_deg=d.get("delta_azimuth_deg"),
            third_product_id=d.get("third_product_id"),
            notes=d.get("notes", ""),
            tags=tuple(d.get("tags", ())),
        )


def load_product_manifest(path: str | Path) -> ProductManifest:
    """Read one product manifest from JSON."""
    with open(path, encoding="utf-8") as fh:
        return ProductManifest.from_dict(json.load(fh))


def load_pair_manifest(path: str | Path) -> PairManifest:
    """Read one pair manifest from JSON."""
    with open(path, encoding="utf-8") as fh:
        return PairManifest.from_dict(json.load(fh))
