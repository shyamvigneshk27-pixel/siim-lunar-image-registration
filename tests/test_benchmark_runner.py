"""Config, provenance and the runner.

The runner is exercised with an injected registration function, so these tests
need no imagery and no optional engine dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pytest

from siim.geometry import Transform, translation
from siim.benchmark.config import BENCHMARK_IDS, ExperimentConfig, load_config
from siim.benchmark.manifest import PairManifest, ProductManifest
from siim.benchmark.provenance import capture_provenance, file_digest, git_state
from siim.benchmark.runner import BenchmarkRunner
from siim.benchmark.schema import validate_run


# -- fakes ------------------------------------------------------------------

@dataclass
class FakeVerdict:
    status: str = "VERIFIED"
    confidence: str = "moderate"
    reasons: list = field(default_factory=list)


@dataclass
class FakeResult:
    """Mimics the fields of ``siim.pipeline.RegistrationResult`` that are used."""

    src_points: np.ndarray
    dst_points_refined: np.ndarray
    inlier_mask: np.ndarray
    refined_mask: np.ndarray
    transform: Transform | None
    verdict: FakeVerdict
    model_selected_by: str = "held_out_on_refined_points"

    @property
    def n_inliers(self) -> int:
        return int(self.inlier_mask.sum())

    def residuals_px(self) -> np.ndarray:
        return np.full(int(self.src_points.shape[0]), 0.25)


def make_result(n=40, status="VERIFIED", spread=40.0, size=100):
    rng = np.random.default_rng(0)
    pts = rng.uniform(size / 2 - spread, size / 2 + spread, size=(n, 2))
    mask = np.ones(n, dtype=bool)
    return FakeResult(
        src_points=pts, dst_points_refined=pts + 1.0,
        inlier_mask=mask, refined_mask=mask,
        transform=translation(1.0, 1.0), verdict=FakeVerdict(status=status),
    )


def fake_register(source, reference, **kwargs):
    return make_result()


def product(pid, instrument="LRO_NAC", corpus="PROXY", **kw):
    return ProductManifest(product_id=pid, instrument=instrument,
                           corpus_class=corpus, **kw)


def pair(pid="p1", overlap="CONFIRMED", corpus="PROXY", **kw):
    return PairManifest(
        pair_id=pid, source=product(f"{pid}_src"), reference=product(f"{pid}_ref"),
        corpus_class=corpus, ground_truth="CORROBORATION_ONLY",
        overlap_status=overlap, **kw,
    )


def loader(_pair):
    return np.zeros((100, 100)), np.zeros((100, 100)), None


def cfg(**kw):
    d = dict(benchmark_id="B2", arm="baseline", corpus_class="PROXY",
             ground_truth="CORROBORATION_ONLY", engines=("B1",))
    d.update(kw)
    return ExperimentConfig(**d)


# -- configuration ----------------------------------------------------------

def test_every_benchmark_id_has_a_title():
    assert set(BENCHMARK_IDS) == {f"B{i}" for i in range(1, 14)}
    assert all(t.strip() for t in BENCHMARK_IDS.values())


def test_unknown_benchmark_id_is_rejected():
    with pytest.raises(ValueError, match="benchmark_id"):
        cfg(benchmark_id="B99")


def test_unknown_engine_is_rejected():
    with pytest.raises(ValueError, match="unknown engine"):
        cfg(engines=("B1", "MAGIC"))


def test_at_least_one_engine_is_required():
    with pytest.raises(ValueError, match="at least one engine"):
        cfg(engines=())


def test_uniformity_thresholds_are_unset_by_default():
    """A threshold must be derived or calibrated, never defaulted in code."""
    c = cfg()
    assert c.u1_max is None and c.u2_max_px is None and c.u3_min is None
    assert c.uniformity_gated is False


def test_asking_for_a_u2_threshold_without_replicates_is_rejected():
    with pytest.raises(ValueError, match="bootstrap_samples"):
        cfg(u2_max_px=0.5, bootstrap_samples=0)


def test_preregistration_is_recorded_and_absent_by_default():
    assert cfg().is_preregistered is False
    assert cfg(preregistered_at="2026-09-21T00:00:00Z").is_preregistered is True


def test_config_round_trips(tmp_path):
    import json

    c = cfg(u1_max=0.3, pass_criteria={"min_successes": 2},
            claims_not_supported=("no Chandrayaan-2 data",))
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(c.to_dict()), encoding="utf-8")
    assert load_config(p) == c


# -- provenance -------------------------------------------------------------

def test_file_digest_is_stable(tmp_path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"lunar")
    assert file_digest(p) == file_digest(p)
    assert len(file_digest(p)) == 64


def test_provenance_records_libraries_and_platform():
    prov = capture_provenance(seed=7)
    d = prov.as_dict()
    assert d["seed"] == 7
    assert d["libraries"]["python"]
    assert "numpy" in d["libraries"]
    assert d["platform"]


def test_provenance_flags_a_missing_input_rather_than_ignoring_it(tmp_path):
    prov = capture_provenance(inputs=[tmp_path / "nope.img"])
    assert prov.input_digests == {}
    assert "does not exist" in next(iter(prov.input_problems.values()))


def test_provenance_records_when_digesting_was_skipped(tmp_path):
    p = tmp_path / "big.img"
    p.write_bytes(b"0" * 16)
    prov = capture_provenance(inputs=[p], digest_inputs=False)
    assert "skipped" in prov.input_problems[str(p)]


def test_provenance_without_a_seed_is_caveated():
    assert any("seed" in c for c in capture_provenance().caveats())


def test_git_state_reports_availability_explicitly():
    state = git_state()
    assert "available" in state
    if state["available"]:
        assert len(state["commit"]) >= 7


# -- the runner: refusals ---------------------------------------------------

def test_a_pair_without_confirmed_overlap_is_refused_not_failed():
    runner = BenchmarkRunner(cfg(), loader, register_fn=fake_register)
    out = runner.run([pair(overlap="UNKNOWN")])
    assert out.n_rows == 0
    assert out.n_refused == 1
    assert out.refusals[0]["stage"] == "overlap_gate"


def test_a_not_confirmed_pair_is_refused_too():
    runner = BenchmarkRunner(cfg(), loader, register_fn=fake_register)
    out = runner.run([pair(overlap="NOT_CONFIRMED")])
    assert out.n_refused == 1
    assert "not established to share ground" in out.refusals[0]["reason"]


def test_a_corpus_class_mismatch_is_refused():
    """A proxy pair must not be recorded under a Chandrayaan-2 experiment."""
    c = cfg(corpus_class="CHANDRAYAAN2")
    runner = BenchmarkRunner(c, loader, register_fn=fake_register)
    out = runner.run([pair(corpus="PROXY")])
    assert out.n_rows == 0
    assert out.refusals[0]["stage"] == "corpus_class"


def test_a_loader_failure_is_refused_with_its_reason():
    def bad_loader(_p):
        raise OSError("tile missing")

    runner = BenchmarkRunner(cfg(), bad_loader, register_fn=fake_register)
    out = runner.run([pair()])
    assert out.refusals[0]["stage"] == "load"
    assert "tile missing" in out.refusals[0]["reason"]


# -- the runner: rows -------------------------------------------------------

def test_a_confirmed_pair_produces_one_row_per_engine():
    runner = BenchmarkRunner(cfg(engines=("B1", "B3")), loader,
                             register_fn=fake_register)
    out = runner.run([pair()])
    assert out.n_rows == 2
    assert {r["engine"] for r in out.rows} == {"B1", "B3"}


def test_rows_validate_and_carry_corpus_class_and_ground_truth():
    runner = BenchmarkRunner(cfg(), loader, register_fn=fake_register)
    out = runner.run([pair()])
    validate_run(out.envelope)
    row = out.rows[0]
    assert row["corpus_class"] == "PROXY"
    assert row["ground_truth"] == "CORROBORATION_ONLY"
    assert row["fit_rmse_is_not_accuracy"] is True


def test_cost_metrics_are_recorded():
    runner = BenchmarkRunner(cfg(), loader, register_fn=fake_register)
    row = runner.run([pair()]).rows[0]
    assert row["metrics"]["wall_s"]["kind"] == "cost"
    assert row["metrics"]["peak_mem_mb"]["value"] >= 0


def test_a_missing_optional_engine_yields_cannot_check_not_a_failure():
    def unavailable(*_a, **_k):
        raise RuntimeError("B4L needs kornia and torch")

    runner = BenchmarkRunner(cfg(engines=("B4L",)), loader,
                             register_fn=unavailable)
    out = runner.run([pair()])
    assert out.rows[0]["verdict"] == "CANNOT_CHECK"
    assert "kornia" in out.rows[0]["verdict_reasons"][0]
    assert out.rows[0]["extra"]["cannot_check_reason"] == "missing_optional_dependency"


# -- the runner: uniformity gate -------------------------------------------

def test_without_thresholds_the_verdict_is_untouched():
    runner = BenchmarkRunner(cfg(), loader, register_fn=fake_register)
    assert runner.run([pair()]).rows[0]["verdict"] == "VERIFIED"


def test_failing_uniformity_downgrades_to_inconclusive_never_rejected():
    """Non-uniformity does not establish that the alignment is wrong."""
    def clustered(*_a, **_k):
        return make_result(spread=3.0)

    runner = BenchmarkRunner(cfg(u1_max=0.05), loader, register_fn=clustered)
    row = runner.run([pair()]).rows[0]
    assert row["verdict"] == "INCONCLUSIVE"
    assert any("uniformity" in r.lower() for r in row["verdict_reasons"])


def test_the_gate_does_not_promote_a_rejected_row():
    def rejected(*_a, **_k):
        return make_result(status="REJECTED")

    runner = BenchmarkRunner(cfg(u1_max=0.99), loader, register_fn=rejected)
    assert runner.run([pair()]).rows[0]["verdict"] == "REJECTED"


def test_bootstrap_replicates_populate_u2():
    runner = BenchmarkRunner(cfg(bootstrap_samples=12), loader,
                             register_fn=fake_register)
    row = runner.run([pair()]).rows[0]
    assert row["extra"]["n_bootstrap_replicates"] > 0
    assert row["uniformity"]["u2_max_prediction_sd_px"] is not None


def test_u2_is_undefined_when_bootstrapping_is_off():
    runner = BenchmarkRunner(cfg(), loader, register_fn=fake_register)
    row = runner.run([pair()]).rows[0]
    assert row["uniformity"]["u2_max_prediction_sd_px"] is None
    assert "replicates" in row["uniformity"]["undefined"]["u2"]


# -- the runner: aggregates and output --------------------------------------

def test_aggregates_count_verdicts():
    runner = BenchmarkRunner(cfg(), loader, register_fn=fake_register)
    out = runner.run([pair("a"), pair("b"), pair("c", overlap="UNKNOWN")])
    assert out.verdict_counts() == {"VERIFIED": 2}
    assert out.aggregates.value_of("n_rows") == 2
    assert out.aggregates.get("false_acceptance_rate").value is None


def test_run_writes_a_validated_envelope(tmp_path):
    runner = BenchmarkRunner(cfg(), loader, register_fn=fake_register,
                             out_dir=tmp_path)
    out = runner.run([pair()])
    assert out.output_path is not None and out.output_path.exists()
    assert out.envelope["config"]["benchmark_id"] == "B2"
    assert out.envelope["provenance"]["captured_utc"]


def test_running_no_pairs_is_valid_and_empty():
    runner = BenchmarkRunner(cfg(), loader, register_fn=fake_register)
    out = runner.run([])
    validate_run(out.envelope)
    assert out.n_rows == 0 and out.n_refused == 0


def test_the_run_is_deterministic_for_a_fixed_seed():
    runner = BenchmarkRunner(cfg(bootstrap_samples=8), loader,
                             register_fn=fake_register)
    a = runner.run([pair()]).rows[0]["uniformity"]
    b = runner.run([pair()]).rows[0]["uniformity"]
    assert a["u2_max_prediction_sd_px"] == b["u2_max_prediction_sd_px"]
