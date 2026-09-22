"""The benchmark runner.

It executes one :class:`~siim.benchmark.config.ExperimentConfig` over a set of
pair manifests and emits schema-valid rows. It does not register images
itself: registration is called through an injectable function that defaults to
:func:`siim.pipeline.register_pair`, so the runner can be tested without
imagery and the engine can be replaced without touching the benchmark layer.

Three behaviours are worth stating because they are easy to get wrong.

**A pair that was never confirmed to overlap is refused, not failed.** It
appears in ``refusals`` with a reason, never as a registration result. Nothing
about the matcher was measured, so recording a verdict would be a fabrication.

**A missing optional dependency yields CANNOT_CHECK, not a failure.** Absence
of evidence is a different answer from evidence of absence, and the two must
not share an exit code.

**Failing uniformity downgrades to INCONCLUSIVE, never to REJECTED.**
Rejection asserts the alignment is wrong. Non-uniformity establishes only that
the evidence does not support a claim across the whole image.
"""

from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np
from numpy.typing import NDArray

from .config import ExperimentConfig
from .manifest import PairManifest
from .metrics import (
    MetricKind,
    MetricSet,
    MetricValue,
    aggregate_rates,
    correspondence_summary,
    fit_statistics,
)
from .provenance import Provenance, capture_provenance
from .schema import result_row, run_envelope, write_run
from .uniformity import uniformity_metrics

__all__ = ["BenchmarkRunner", "RunOutcome", "PairImages"]

#: What a loader must return: source, reference, and the valid-overlap mask.
PairImages = tuple[NDArray[np.float64], NDArray[np.float64], "NDArray[np.bool_] | None"]


@dataclass(frozen=True)
class RunOutcome:
    """Everything one run produced."""

    envelope: dict[str, Any]
    rows: tuple[dict[str, Any], ...]
    refusals: tuple[dict[str, Any], ...]
    aggregates: MetricSet
    provenance: Provenance
    output_path: Path | None = None

    @property
    def n_rows(self) -> int:
        return len(self.rows)

    @property
    def n_refused(self) -> int:
        return len(self.refusals)

    def verdict_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.rows:
            counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
        return counts


def _default_register(source, reference, **kwargs):
    """Late import so the benchmark package imports without optional engines."""
    from ..pipeline import register_pair

    return register_pair(source, reference, **kwargs)


class BenchmarkRunner:
    """Run one experiment arm over a set of pairs."""

    def __init__(
        self,
        config: ExperimentConfig,
        loader: Callable[[PairManifest], PairImages],
        *,
        register_fn: Callable[..., Any] | None = None,
        out_dir: str | Path | None = None,
    ) -> None:
        self.config = config
        self.loader = loader
        self.register_fn = register_fn or _default_register
        self.out_dir = Path(out_dir) if out_dir is not None else None

    # -- bootstrap ---------------------------------------------------------

    def _bootstrap_transforms(
        self,
        src: NDArray[np.float64],
        dst: NDArray[np.float64],
        model: str,
        rng: np.random.Generator,
    ) -> list[Any]:
        """Resample the correspondences and re-fit, for the U2 spread.

        Returns fewer replicates than requested when fits fail; the caller
        reports U2 as undefined rather than pretending the spread is tight.
        """
        from ..geometry import MODEL_MIN_POINTS
        from ..geometry.estimate import estimate

        n = int(src.shape[0])
        need = int(MODEL_MIN_POINTS.get(model, 3))
        if n < need:
            return []
        out: list[Any] = []
        for _ in range(self.config.bootstrap_samples):
            idx = rng.integers(0, n, size=n)
            if np.unique(idx).size < need:
                continue
            res = estimate(src[idx], dst[idx], model)
            if res.transform is not None:
                out.append(res.transform)
        return out

    # -- one pair, one engine ---------------------------------------------

    def _run_one(
        self,
        pair: PairManifest,
        engine: str,
        images: PairImages,
        rng: np.random.Generator,
    ) -> dict[str, Any]:
        cfg = self.config
        source, reference, roi = images

        tracemalloc.start()
        t0 = time.perf_counter()
        try:
            result = self.register_fn(
                source,
                reference,
                engine=engine,
                model=cfg.model,
                ransac_threshold=cfg.ransac_threshold,
                seed=cfg.seed,
                refine=cfg.refine,
            )
        except (RuntimeError, ImportError) as exc:
            tracemalloc.stop()
            return result_row(
                benchmark_id=cfg.benchmark_id,
                arm=cfg.arm,
                pair_id=pair.pair_id,
                corpus_class=cfg.corpus_class,
                ground_truth=cfg.ground_truth,
                engine=engine,
                seed=cfg.seed,
                verdict="CANNOT_CHECK",
                overlap_status=pair.overlap_status,
                verdict_reasons=[
                    f"engine {engine} unavailable in this environment: {exc}"
                ],
                extra={"cannot_check_reason": "missing_optional_dependency"},
            )
        wall_s = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        metrics = fit_statistics(result.residuals_px())
        metrics = metrics.merge(
            correspondence_summary(
                int(result.src_points.shape[0]), int(result.n_inliers)
            )
        )
        metrics = metrics.merge(
            MetricSet(
                (
                    MetricValue("wall_s", float(wall_s), MetricKind.COST, "s"),
                    MetricValue("peak_mem_mb", float(peak) / 1e6, MetricKind.COST,
                                "MB"),
                )
            )
        )

        # Uniformity over the inlier set, which is what the transform used and
        # what the deliverable reports. Selecting uniformly at detection time
        # does not guarantee the surviving set is uniform.
        mask = result.inlier_mask
        pts = (
            result.src_points[mask]
            if mask.size and result.src_points.shape[0] else np.zeros((0, 2))
        )
        replicates: list[Any] = []
        if cfg.bootstrap_samples >= 3 and result.transform is not None:
            rmask = result.refined_mask if result.refined_mask.size else mask
            if rmask.size and rmask.sum() > 0:
                replicates = self._bootstrap_transforms(
                    result.src_points[rmask],
                    result.dst_points_refined[rmask],
                    result.transform.model,
                    rng,
                )
        unif = uniformity_metrics(
            pts,
            (int(source.shape[0]), int(source.shape[1])),
            roi,
            transform_samples=replicates or None,
            seed=cfg.seed,
        )

        verdict = result.verdict.status
        reasons = list(result.verdict.reasons)
        if cfg.uniformity_gated and verdict == "VERIFIED":
            ok, why = unif.meets(
                u1_max=cfg.u1_max, u2_max_px=cfg.u2_max_px, u3_min=cfg.u3_min
            )
            if not ok:
                verdict = "INCONCLUSIVE"
                reasons.extend(why)
                reasons.append(
                    "Downgraded to INCONCLUSIVE on spatial uniformity. The "
                    "alignment may be correct; the evidence does not support a "
                    "claim across the whole image."
                )

        return result_row(
            benchmark_id=cfg.benchmark_id,
            arm=cfg.arm,
            pair_id=pair.pair_id,
            corpus_class=cfg.corpus_class,
            ground_truth=cfg.ground_truth,
            engine=engine,
            seed=cfg.seed,
            verdict=verdict,
            overlap_status=pair.overlap_status,
            metrics=metrics,
            uniformity=unif.as_dict(),
            transform_matrix=(
                None if result.transform is None
                else np.asarray(result.transform.matrix).tolist()
            ),
            model=None if result.transform is None else result.transform.model,
            verdict_reasons=reasons,
            scale_ratio=pair.scale_ratio,
            scale_ratio_source=(
                pair.scale_ratio_source if pair.scale_ratio is not None else None
            ),
            delta_incidence_deg=pair.delta_incidence_deg,
            delta_azimuth_deg=pair.delta_azimuth_deg,
            extra={
                "model_selected_by": result.model_selected_by,
                "n_refined": int(result.refined_mask.sum())
                if result.refined_mask.size else 0,
                "n_bootstrap_replicates": len(replicates),
                "measured_scale_ratio": pair.measured_scale_ratio(),
            },
        )

    # -- the run -----------------------------------------------------------

    def run(
        self,
        pairs: Iterable[PairManifest],
        *,
        output_name: str | None = None,
    ) -> RunOutcome:
        """Execute the arm over ``pairs``."""
        cfg = self.config
        rng = np.random.default_rng(cfg.seed)
        rows: list[dict[str, Any]] = []
        refusals: list[dict[str, Any]] = []
        inputs: list[str] = []

        for pair in pairs:
            if not pair.runnable:
                refusals.append(
                    {
                        "pair_id": pair.pair_id,
                        "overlap_status": pair.overlap_status,
                        "reason": pair.refusal_reason(),
                        "stage": "overlap_gate",
                    }
                )
                continue

            if pair.corpus_class != cfg.corpus_class:
                refusals.append(
                    {
                        "pair_id": pair.pair_id,
                        "overlap_status": pair.overlap_status,
                        "reason": (
                            f"pair corpus_class {pair.corpus_class!r} does not "
                            f"match experiment corpus_class {cfg.corpus_class!r}. "
                            "A proxy result must not be recorded as a "
                            "Chandrayaan-2 result, or the reverse."
                        ),
                        "stage": "corpus_class",
                    }
                )
                continue

            for p in (pair.source.path, pair.reference.path):
                if p:
                    inputs.append(p)

            try:
                images = self.loader(pair)
            except (OSError, ValueError) as exc:
                refusals.append(
                    {
                        "pair_id": pair.pair_id,
                        "overlap_status": pair.overlap_status,
                        "reason": f"inputs could not be loaded: {exc}",
                        "stage": "load",
                    }
                )
                continue

            for engine in cfg.engines:
                rows.append(self._run_one(pair, engine, images, rng))

        aggregates = aggregate_rates(rows)
        provenance = capture_provenance(
            seed=cfg.seed,
            inputs=inputs,
            digest_inputs=False,
            extra={
                "benchmark_id": cfg.benchmark_id,
                "arm": cfg.arm,
                "n_refused": len(refusals),
            },
        )
        envelope = run_envelope(
            config=cfg.to_dict(),
            provenance=provenance.as_dict(),
            rows=rows,
            aggregates=aggregates.as_dict(),
            refusals=refusals,
        )

        out_path: Path | None = None
        if self.out_dir is not None:
            name = output_name or f"{cfg.benchmark_id}_{cfg.arm}.json"
            out_path = write_run(envelope, self.out_dir / name)

        return RunOutcome(
            envelope=envelope,
            rows=tuple(rows),
            refusals=tuple(refusals),
            aggregates=aggregates,
            provenance=provenance,
            output_path=out_path,
        )
