"""Performance regression tests for LO-RANSAC (EXP-002 objective 1).

EXP-001 shipped a projective case that took **59 s**, against a 0.387 s median
for every other case. Two independent causes:

1. **A numerical defect.** ``estimate_projective`` called ``np.linalg.svd``
   with the default ``full_matrices=True``, which builds U at (2N x 2N) --
   4230 x 4230 = 17.9M elements for N=2115 -- and then discards it. The DLT
   needs only the last row of Vt. Measured 394.72 ms -> 1.06 ms, **372x**,
   with singular values and Vt identical.
2. **An algorithmic defect.** Local optimisation ran on *every* sample whose
   consensus exceeded the minimal set, rather than only on a new best as in
   Chum et al. (2003). 298 large refits for 100 iterations.

Combined: 54.29 s -> 0.047 s, **1155x**, with the same inlier set.

These tests are wall-clock assertions, which are normally a bad idea because
they are machine-dependent and flaky. They are justified here because the
regression they guard is 3 orders of magnitude, so the thresholds can sit far
above any plausible machine variation and still catch it. Where a
machine-independent invariant exists (refit counts, SVD shape) it is asserted
instead of, not as well as, a timing.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from siim.geometry import affine, endpoint_error, estimate, projective
from siim.verification import ransac


@pytest.fixture(scope="module")
def big_projective_case():
    """The EXP-001 case that took 59 s: ~2115 near-perfect correspondences."""
    rng = np.random.default_rng(0)
    n = 2115
    truth = projective(
        [[1.03, 0.04, 8.0], [-0.03, 1.01, -5.0], [4.0e-5, -2.5e-5, 1.0]]
    )
    src = rng.uniform(0, 512, size=(n, 2))
    dst = truth.apply(src) + rng.normal(0, 0.3, size=(n, 2))
    return src, dst, truth


class TestSvdDefect:
    def test_dlt_uses_the_economy_svd(self):
        """Machine-independent: the full SVD is ~470,000x larger in U.

        Asserted on shapes rather than time, so it holds on any hardware.
        """
        n = 500
        a = np.random.default_rng(0).normal(size=(2 * n, 9))
        u_full, s_full, vt_full = np.linalg.svd(a)
        u_econ, s_econ, vt_econ = np.linalg.svd(a, full_matrices=False)

        assert u_full.shape == (2 * n, 2 * n)
        assert u_econ.shape == (2 * n, 9)
        # The parts the DLT actually uses are identical.
        assert np.allclose(s_full, s_econ)
        assert np.allclose(np.abs(vt_full), np.abs(vt_econ))

    def test_large_projective_fit_is_fast(self, big_projective_case):
        src, dst, _ = big_projective_case
        t0 = time.perf_counter()
        res = estimate(src, dst, "projective")
        elapsed = time.perf_counter() - t0
        assert res.ok
        # Measured 1.06 ms after the fix, 373.93 ms before. 50 ms sits two
        # orders below the defect and two above the fixed cost.
        assert elapsed < 0.05, (
            f"projective fit on {len(src)} points took {elapsed*1000:.1f} ms; "
            f"the full_matrices=True SVD defect has likely regressed"
        )


class TestLocalOptimisationBudget:
    def test_lo_runs_only_on_a_new_best(self, big_projective_case):
        """Machine-independent: refit count, not wall time.

        Chum et al. (2003) run LO only when a new best model is found, which
        happens O(log n) times. The EXP-001 version ran it on nearly every
        iteration: 298 refits for 100 iterations.
        """
        src, dst, _ = big_projective_case
        res = ransac(src, dst, "projective", threshold=3.0, seed=0, min_iterations=100)
        assert res.success
        assert res.timing.n_minimal_fits == 100
        assert res.timing.n_lo_refits <= 20, (
            f"{res.timing.n_lo_refits} LO refits for 100 iterations; LO is "
            f"running on non-improving samples again"
        )

    def test_end_to_end_runtime_regression(self, big_projective_case):
        src, dst, truth = big_projective_case
        t0 = time.perf_counter()
        res = ransac(src, dst, "projective", threshold=3.0, seed=0)
        elapsed = time.perf_counter() - t0

        assert res.success
        assert res.n_inliers == len(src)
        # 54.29 s before, 0.047 s after. 5 s is 3 orders below the defect.
        assert elapsed < 5.0, (
            f"LO-RANSAC took {elapsed:.2f} s on the EXP-001 projective case "
            f"(was 54.29 s before the fix, 0.047 s after)"
        )

    def test_timing_breakdown_is_populated(self, big_projective_case):
        """Stage timing is what made the defect diagnosable at all (spec §37)."""
        src, dst, _ = big_projective_case
        t = ransac(src, dst, "projective", seed=0).timing
        assert t.total > 0
        assert t.sampling > 0 and t.minimal_fit > 0 and t.scoring > 0
        parts = t.sampling + t.minimal_fit + t.scoring + t.local_optimisation + t.final_fit
        assert parts <= t.total + 1e-6


class TestCorrectnessPreserved:
    """The fixes must not have bought speed with accuracy or robustness."""

    def test_accuracy_unchanged_on_the_big_case(self, big_projective_case):
        src, dst, truth = big_projective_case
        res = ransac(src, dst, "projective", threshold=3.0, seed=0)
        err = endpoint_error(res.transform, truth, (512, 512), step=32)
        assert err.median < 0.2, f"median true endpoint error {err.median:.4f} px"

    @pytest.mark.parametrize("outlier_frac", [0.3, 0.5, 0.6, 0.7])
    def test_robustness_across_outlier_rates(self, outlier_frac):
        rng = np.random.default_rng(7)
        truth = affine([[1.04, 0.05, 12.0], [-0.03, 1.01, -7.0]])
        n = 300
        src = rng.uniform(0, 400, size=(n, 2))
        dst = truth.apply(src) + rng.normal(0, 0.2, size=(n, 2))
        n_out = int(n * outlier_frac)
        dst[:n_out] = rng.uniform(0, 400, size=(n_out, 2))

        res = ransac(src, dst, "affine", threshold=2.0, seed=1)
        assert res.success
        assert res.n_inliers > 0.75 * (n - n_out)
        assert endpoint_error(res.transform, truth, (400, 400), step=25).median < 1.0

    def test_lo_subsampling_does_not_degrade_accuracy(self):
        """`lo_max_points` caps the refit sample, never the consensus scoring.

        A 1000-point least-squares fit is already vastly over-determined for a
        model with at most 8 DOF, so capping it must not move the estimate.
        """
        rng = np.random.default_rng(11)
        truth = affine([[1.02, 0.03, 6.0], [-0.02, 1.0, -3.0]])
        n = 4000
        src = rng.uniform(0, 600, size=(n, 2))
        dst = truth.apply(src) + rng.normal(0, 0.3, size=(n, 2))

        capped = ransac(src, dst, "affine", threshold=2.0, seed=3, lo_max_points=200)
        uncapped = ransac(src, dst, "affine", threshold=2.0, seed=3, lo_max_points=n)

        e_cap = endpoint_error(capped.transform, truth, (600, 600), step=40).median
        e_unc = endpoint_error(uncapped.transform, truth, (600, 600), step=40).median
        assert abs(e_cap - e_unc) < 0.05, f"capped {e_cap:.4f} vs uncapped {e_unc:.4f}"
        # And the consensus set itself is unaffected -- scoring is never subsampled.
        assert abs(capped.n_inliers - uncapped.n_inliers) < 0.02 * n

    def test_scoring_is_never_subsampled(self):
        """The robustness criterion must be evaluated against every match."""
        rng = np.random.default_rng(13)
        truth = affine([[1.0, 0.0, 5.0], [0.0, 1.0, -5.0]])
        n = 3000
        src = rng.uniform(0, 500, size=(n, 2))
        dst = truth.apply(src)
        res = ransac(src, dst, "affine", threshold=1.0, seed=2, lo_max_points=50)
        # Every correspondence is a true inlier; all must be found despite the
        # tiny LO cap.
        assert res.n_inliers == n
