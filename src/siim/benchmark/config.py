"""Experiment configuration.

A configuration states what will be measured and what will count as a pass,
**before** the data is seen. That ordering is the whole point: a criterion
chosen after seeing the result is a description, not a test.

``preregistered_at`` records when the criteria were frozen. It is not
decoration. A configuration whose criteria were written after its inputs
existed should say so by leaving it unset, so that a reader can tell the
difference between a prediction and a summary.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .manifest import CORPUS_CLASSES, GROUND_TRUTH_KINDS, _require

__all__ = ["BENCHMARK_IDS", "ExperimentConfig", "load_config"]

#: The benchmark classes from ``05_BENCHMARK_PROTOCOL``.
BENCHMARK_IDS: Mapping[str, str] = {
    "B1": "Illumination variation, controlled",
    "B2": "Sun-angle difference on real imagery",
    "B3": "Scale variation ladder",
    "B4": "Rotation",
    "B5": "Viewpoint variation",
    "B6": "Cross-modality",
    "B7": "Shadow-heavy scenes",
    "B8": "Low-texture scenes",
    "B9": "Repeated textures",
    "B10": "Wrong overlap",
    "B11": "Orientation and mirror errors",
    "B12": "Uneven match distributions",
    "B13": "Wrong but low-residual alignments",
}

#: Engines from ``siim.baselines.engines``. B4L and B4X need optional deps.
_KNOWN_ENGINES = ("B0", "B1", "B2", "B2K", "B3", "B5", "B7", "B4L", "B4X")


@dataclass(frozen=True)
class ExperimentConfig:
    """One benchmark arm, fully specified before it runs."""

    benchmark_id: str
    arm: str
    corpus_class: str
    ground_truth: str
    engines: tuple[str, ...] = ("B1",)
    model: str = "affine"
    ransac_threshold: float = 3.0
    seed: int = 0
    refine: bool = True
    #: Bootstrap replicates for the uncertainty and U2 estimates. Zero disables.
    bootstrap_samples: int = 0
    #: Uniformity thresholds. **Unset by default, deliberately.** A threshold
    #: must be derived from the accuracy budget or calibrated with inlier count
    #: held constant; defaulting one in code would smuggle in an invented value.
    u1_max: float | None = None
    u2_max_px: float | None = None
    u3_min: int | None = None
    #: Free-form, machine-readable pass criteria, fixed in advance.
    pass_criteria: Mapping[str, Any] = field(default_factory=dict)
    #: ISO timestamp at which the criteria were frozen. ``None`` means they
    #: were not pre-registered, which is a fact about the experiment.
    preregistered_at: str | None = None
    #: Claims this arm explicitly does not support.
    claims_not_supported: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""

    def __post_init__(self) -> None:
        if self.benchmark_id not in BENCHMARK_IDS:
            raise ValueError(
                f"benchmark_id={self.benchmark_id!r} is not one of "
                f"{sorted(BENCHMARK_IDS)}"
            )
        _require(self.corpus_class, CORPUS_CLASSES, "corpus_class")
        _require(self.ground_truth, GROUND_TRUTH_KINDS, "ground_truth")
        if not self.engines:
            raise ValueError("at least one engine must be named")
        unknown = [e for e in self.engines if e not in _KNOWN_ENGINES]
        if unknown:
            raise ValueError(
                f"unknown engine(s) {unknown}; known: {list(_KNOWN_ENGINES)}"
            )
        if self.ransac_threshold <= 0:
            raise ValueError("ransac_threshold must be positive")
        if self.bootstrap_samples < 0:
            raise ValueError("bootstrap_samples must be non-negative")
        if self.u2_max_px is not None and self.bootstrap_samples < 3:
            raise ValueError(
                "u2_max_px was set but bootstrap_samples < 3. U2 is a bootstrap "
                "spread; asking for the threshold without the replicates would "
                "silently never evaluate it."
            )
        for name, v in (("u1_max", self.u1_max), ("u2_max_px", self.u2_max_px)):
            if v is not None and v <= 0:
                raise ValueError(f"{name} must be positive when set")
        if self.u3_min is not None and self.u3_min < 0:
            raise ValueError("u3_min must be non-negative when set")

    @property
    def title(self) -> str:
        return BENCHMARK_IDS[self.benchmark_id]

    @property
    def is_preregistered(self) -> bool:
        return self.preregistered_at is not None

    @property
    def uniformity_gated(self) -> bool:
        """Whether any uniformity threshold will actually be enforced."""
        return any(v is not None for v in (self.u1_max, self.u2_max_px, self.u3_min))

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "title": self.title,
            "arm": self.arm,
            "corpus_class": self.corpus_class,
            "ground_truth": self.ground_truth,
            "engines": list(self.engines),
            "model": self.model,
            "ransac_threshold": self.ransac_threshold,
            "seed": self.seed,
            "refine": self.refine,
            "bootstrap_samples": self.bootstrap_samples,
            "u1_max": self.u1_max,
            "u2_max_px": self.u2_max_px,
            "u3_min": self.u3_min,
            "uniformity_gated": self.uniformity_gated,
            "pass_criteria": dict(self.pass_criteria),
            "preregistered_at": self.preregistered_at,
            "is_preregistered": self.is_preregistered,
            "claims_not_supported": list(self.claims_not_supported),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ExperimentConfig":
        return cls(
            benchmark_id=d["benchmark_id"],
            arm=d["arm"],
            corpus_class=d["corpus_class"],
            ground_truth=d["ground_truth"],
            engines=tuple(d.get("engines", ("B1",))),
            model=d.get("model", "affine"),
            ransac_threshold=float(d.get("ransac_threshold", 3.0)),
            seed=int(d.get("seed", 0)),
            refine=bool(d.get("refine", True)),
            bootstrap_samples=int(d.get("bootstrap_samples", 0)),
            u1_max=d.get("u1_max"),
            u2_max_px=d.get("u2_max_px"),
            u3_min=d.get("u3_min"),
            pass_criteria=dict(d.get("pass_criteria", {})),
            preregistered_at=d.get("preregistered_at"),
            claims_not_supported=tuple(d.get("claims_not_supported", ())),
            notes=d.get("notes", ""),
        )


def load_config(path: str | Path) -> ExperimentConfig:
    """Read one experiment configuration from JSON."""
    with open(path, encoding="utf-8") as fh:
        return ExperimentConfig.from_dict(json.load(fh))
