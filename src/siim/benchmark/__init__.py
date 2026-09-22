"""Benchmark infrastructure: manifests, metrics, uniformity, schema, runner.

This package does NOT register images. It describes what is to be measured,
measures it, and records the result so that a number can never be read as
something it is not.

Three invariants hold throughout, and the tests pin all three.

1. **A fit statistic is never an accuracy.** Every metric carries a
   :class:`~siim.benchmark.metrics.MetricKind`, and the serialiser refuses to
   emit a fit statistic in a field named for accuracy.
2. **A proxy result is never a Chandrayaan-2 result.** Every manifest and every
   result row carries ``corpus_class``; it has no default.
3. **Nothing is interpreted before overlap is proven.** A pair whose overlap is
   not ``CONFIRMED`` is not runnable, and the runner refuses it.
"""

from .manifest import (
    CORPUS_CLASSES,
    GROUND_TRUTH_KINDS,
    OVERLAP_STATUSES,
    PairManifest,
    ProductManifest,
    load_pair_manifest,
    load_product_manifest,
)
from .acquisition import (
    REQUIREMENTS,
    AcquisitionReport,
    PairRequirement,
    assess_products,
    requirement_by_id,
)
from .config import BENCHMARK_IDS, ExperimentConfig, load_config
from .metrics import (
    METRIC_KINDS,
    MetricKind,
    MetricSet,
    MetricValue,
    aggregate_rates,
    correspondence_summary,
    fit_statistics,
)
from .uniformity import UniformityMetrics, coverage_curve, uniformity_metrics
from .schema import (
    RESULT_SCHEMA_VERSION,
    SchemaError,
    result_row,
    validate_result,
    validate_run,
)
from .provenance import Provenance, capture_provenance, file_digest
from .runner import BenchmarkRunner, RunOutcome

__all__ = [
    "CORPUS_CLASSES",
    "GROUND_TRUTH_KINDS",
    "OVERLAP_STATUSES",
    "ProductManifest",
    "PairManifest",
    "load_product_manifest",
    "load_pair_manifest",
    "REQUIREMENTS",
    "PairRequirement",
    "AcquisitionReport",
    "assess_products",
    "requirement_by_id",
    "BENCHMARK_IDS",
    "ExperimentConfig",
    "load_config",
    "MetricKind",
    "METRIC_KINDS",
    "MetricValue",
    "MetricSet",
    "fit_statistics",
    "correspondence_summary",
    "aggregate_rates",
    "UniformityMetrics",
    "uniformity_metrics",
    "coverage_curve",
    "RESULT_SCHEMA_VERSION",
    "SchemaError",
    "result_row",
    "validate_result",
    "validate_run",
    "Provenance",
    "capture_provenance",
    "file_digest",
    "BenchmarkRunner",
    "RunOutcome",
]
