"""Metrics. See ANALYSIS §F for why fit residuals are not accuracies."""

from .coverage import CoverageMetrics, coverage_metrics
from .gtfree import (
    HeldOutResidual,
    compose_cycle,
    cycle_consistency,
    held_out_residual,
    loop_closure,
    spatial_split_consistency,
)
from .error_budget import (
    BudgetTerm,
    BudgetTotal,
    ErrorBudget,
    TermKind,
    TermStatus,
    nac_reference_budget,
)
from .significance import (
    AdditionalEvidence,
    SeparationTest,
    exact_separation_test,
    minimum_additional_edges,
)
from .metrics import (
    CorrespondenceMetrics,
    FailureMode,
    classify_failure,
    correspondence_metrics,
)

__all__ = [
    "CorrespondenceMetrics",
    "FailureMode",
    "correspondence_metrics",
    "classify_failure",
    "CoverageMetrics",
    "coverage_metrics",
    "HeldOutResidual",
    "held_out_residual",
    "cycle_consistency",
    "loop_closure",
    "spatial_split_consistency",
    "compose_cycle",
    "SeparationTest",
    "AdditionalEvidence",
    "exact_separation_test",
    "minimum_additional_edges",
    "BudgetTerm",
    "BudgetTotal",
    "ErrorBudget",
    "TermKind",
    "TermStatus",
    "nac_reference_budget",
]
