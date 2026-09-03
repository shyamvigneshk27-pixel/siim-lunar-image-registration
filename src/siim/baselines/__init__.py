"""Baseline pipelines (ANALYSIS §E.1)."""

from .engines import (
    BASELINE_IDS,
    BASELINE_ROLES,
    OPTIONAL_BASELINE_IDS,
    akaze_available,
    run_akaze_baseline,
    run_asift_baseline,
    run_baseline,
    run_direct_baseline,
    run_identity_baseline,
    run_orb_baseline,
    run_phase_congruency_baseline,
)
from .rootsift_pipeline import BaselineResult, run_rootsift_baseline

__all__ = [
    "BASELINE_IDS",
    "BASELINE_ROLES",
    "OPTIONAL_BASELINE_IDS",
    "BaselineResult",
    "akaze_available",
    "run_akaze_baseline",
    "run_asift_baseline",
    "run_baseline",
    "run_direct_baseline",
    "run_identity_baseline",
    "run_orb_baseline",
    "run_phase_congruency_baseline",
    "run_rootsift_baseline",
]
