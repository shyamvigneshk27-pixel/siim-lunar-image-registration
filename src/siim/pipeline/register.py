"""The deliverable pipeline: estimate -> refine -> re-estimate -> verify.

This is the order EXP-010 and EXP-011 measured into existence (D-044, D-045):

1. **estimate** -- any engine behind the identical harness
   (``siim.baselines.run_baseline``): detector, matcher, then the unmodified
   LO-RANSAC with the pre-registered failure rule ``n_inliers <= 8`` (D-023).
2. **refine** -- each surviving correspondence is refined to sub-pixel by
   translation-only ECC on a local patch (``siim.refinement``; 0.003 px on
   real self-warps, EXP-010 S1).
3. **re-estimate** -- the transform model is chosen by held-out evidence on
   the REFINED points (rule B) and re-estimated from them, which removes the
   correlated localisation bias the engine's default affine model absorbs
   (E-034; 0.0975 px -> 0.0018 px, EXP-011 S2).
4. **verify** -- the verdict engine (``siim.demo.verdict.assess``) decides
   VERIFIED / REJECTED / INCONCLUSIVE from named evidence, with ``fit_rmse``
   structurally excluded and ``model_selected_by`` recorded.

Refinement runs only after a pass. A pair the rule rejects gets no refined
points and no re-estimate: refining three inliers would produce a number that
looks like accuracy for a registration the evidence already refuses.

What a result is and is not
---------------------------
``RegistrationResult.transform`` maps source pixels to reference pixels
(contract C5). ``verdict`` says whether to trust it and why. No ground truth
is involved anywhere; a VERIFIED verdict is *corroborated*, and the
sub-pixel figures from EXP-010/011 are upper bounds measured on self-warps,
not accuracies on a real cross-illumination pair.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..baselines import BaselineResult, run_baseline
from ..demo.verdict import INLIER_CUTOFF, Verdict, assess
from ..geometry import Transform, transfer_residuals
from ..refinement import Refinement, refine_correspondences
from .agreement import AGREEMENT_FLOOR_PX, EngineAgreement, engine_agreement
from .select import MIN_POINTS, ModelSelection, reestimate, select_model

__all__ = ["RegistrationResult", "register_pair", "register_pair_two_engines",
           "with_agreement", "PIPELINE_ORDER"]

PIPELINE_ORDER = ("estimate", "refine", "reestimate", "verify")


@dataclass(frozen=True)
class RegistrationResult:
    """Everything the four stages produced, with the provenance of each."""

    engine: str
    baseline: BaselineResult
    #: The engine's own transform (stage 1). ``None`` when nothing was estimated.
    initial_transform: Transform | None
    #: Stage 2. ``None`` when the rule rejected the pair (nothing to refine).
    refinement: Refinement | None
    #: Stage 3. ``None`` when selection was not applied.
    selection: ModelSelection | None
    #: Where the final model came from: ``held_out_on_refined_points`` (rule B),
    #: ``held_out_on_raw_points`` (rule A fallback when refinement kept too few
    #: points), ``engine_default`` (too few points for either), or ``none``
    #: (rejected; no final transform beyond the engine's).
    model_selected_by: str
    #: The final transform, source -> reference.
    transform: Transform | None
    #: Putative correspondences and the RANSAC inlier mask (stage 1), and the
    #: refined reference points where refinement succeeded (else the initial).
    src_points: NDArray[np.float64]
    dst_points: NDArray[np.float64]
    dst_points_refined: NDArray[np.float64]
    inlier_mask: NDArray[np.bool_]
    #: Mask of correspondences that are inliers AND were refined successfully;
    #: these are the points the final transform was estimated from.
    refined_mask: NDArray[np.bool_]
    verdict: Verdict
    runtime_s: dict[str, float] = field(default_factory=dict)

    @property
    def n_inliers(self) -> int:
        return int(self.inlier_mask.sum()) if self.inlier_mask.size else 0

    def residuals_px(self) -> NDArray[np.float64]:
        """||T(src) - dst_refined|| per correspondence under the FINAL transform.
        A fit statistic (D-003): reported, never an accuracy."""
        if self.transform is None or self.src_points.shape[0] == 0:
            return np.zeros(0)
        return transfer_residuals(self.transform, self.src_points, self.dst_points_refined)

    def summary(self) -> dict[str, Any]:
        v = self.verdict
        return {
            "engine": self.engine,
            "pipeline_order": list(PIPELINE_ORDER),
            "status": v.status, "confidence": v.confidence,
            "n_putative": int(self.src_points.shape[0]), "n_inliers": self.n_inliers,
            "n_refined": int(self.refined_mask.sum()) if self.refined_mask.size else 0,
            "model_selected_by": self.model_selected_by,
            "model": None if self.transform is None else self.transform.model,
            "initial_model": None if self.initial_transform is None else self.initial_transform.model,
            "heldout_px": None if self.selection is None else self.selection.heldout_px,
            "decided_by_tie_break": None if self.selection is None else self.selection.decided_by_tie_break,
            "transform_matrix": None if self.transform is None else np.asarray(self.transform.matrix).tolist(),
            "initial_transform_matrix": (None if self.initial_transform is None
                                         else np.asarray(self.initial_transform.matrix).tolist()),
            "runtime_s": dict(self.runtime_s),
        }


def register_pair(source: ArrayLike, reference: ArrayLike, *, engine: str = "B1",
                  model: str = "affine", ransac_threshold: float = 3.0, seed: int = 0,
                  refine: bool = True, refine_window: int = 48,
                  loop_error_px: float | None = None,
                  engine_agreement_px: float | None = None,
                  engine_agreement_floor_px: float = AGREEMENT_FLOOR_PX,
                  **engine_kwargs: Any) -> RegistrationResult:
    """Run the four stages on one pair. Images are 2-D arrays; NaN is invalid."""
    src = np.asarray(source, dtype=np.float64)
    ref = np.asarray(reference, dtype=np.float64)
    if src.ndim != 2 or ref.ndim != 2:
        raise ValueError("source and reference must be 2-D images")
    rt: dict[str, float] = {}

    # 1. estimate
    t0 = time.perf_counter()
    base = run_baseline(engine, src, ref, model=model, ransac_threshold=ransac_threshold,
                        seed=seed, **engine_kwargs)
    rt["estimate"] = time.perf_counter() - t0
    p = np.asarray(base.matches.src_points, float).reshape(-1, 2)
    q = np.asarray(base.matches.dst_points, float).reshape(-1, 2)
    mask = np.asarray(base.inlier_mask, bool).reshape(-1) if np.size(base.inlier_mask) \
        else np.zeros(p.shape[0], bool)
    if mask.shape[0] != p.shape[0]:
        mask = np.zeros(p.shape[0], bool)
    t_init = base.transform
    n_in = int(mask.sum())

    refinement: Refinement | None = None
    selection: ModelSelection | None = None
    refined_mask = np.zeros(p.shape[0], bool)
    q_ref = q.copy()
    final = t_init
    selected_by = "none"

    if t_init is not None and n_in > INLIER_CUTOFF:
        selected_by = "engine_default"
        pin, qin = p[mask], q[mask]
        # 2. refine
        if refine:
            t0 = time.perf_counter()
            refinement = refine_correspondences(src, ref, t_init, pin, window=refine_window,
                                                method="ecc")
            rt["refine"] = time.perf_counter() - t0
            idx = np.flatnonzero(mask)[refinement.ok]
            refined_mask[idx] = True
            q_ref[idx] = refinement.dst_refined[refinement.ok]
        # 3. re-estimate
        t0 = time.perf_counter()
        n_ref = int(refined_mask.sum())
        if n_ref >= MIN_POINTS:
            selection = select_model(p[refined_mask], q_ref[refined_mask], seed=seed)
            final = reestimate(p[refined_mask], q_ref[refined_mask], selection.model)
            selected_by = "held_out_on_refined_points"
        elif n_in >= MIN_POINTS:
            selection = select_model(pin, qin, seed=seed)
            final = reestimate(pin, qin, selection.model)
            selected_by = "held_out_on_raw_points"
        rt["reestimate"] = time.perf_counter() - t0

    # 4. verify
    t0 = time.perf_counter()
    verdict = assess(
        transform=final, src_points=p, dst_points=q_ref, inlier_mask=mask, shape=src.shape,
        fit_rmse=float(base.ransac.inlier_rmse) if base.ransac is not None else None,
        loop_error_px=loop_error_px,
        engine_agreement_px=engine_agreement_px,
        engine_agreement_floor_px=engine_agreement_floor_px,
        annotations={
            "engine": engine,
            "pipeline_order": list(PIPELINE_ORDER),
            "model_selected_by": selected_by,
            "initial_model": None if t_init is None else t_init.model,
            "n_refined": int(refined_mask.sum()),
            "heldout_px": None if selection is None else selection.heldout_px,
            "decided_by_tie_break": None if selection is None else selection.decided_by_tie_break,
        })
    rt["verify"] = time.perf_counter() - t0

    return RegistrationResult(
        engine=engine, baseline=base, initial_transform=t_init, refinement=refinement,
        selection=selection, model_selected_by=selected_by, transform=final,
        src_points=p, dst_points=q, dst_points_refined=q_ref, inlier_mask=mask,
        refined_mask=refined_mask, verdict=verdict, runtime_s=rt)


def register_pair_two_engines(source: ArrayLike, reference: ArrayLike, *,
                              engines: tuple[str, str] = ("B1", "B4L"),
                              primary: str | None = None,
                              floor_px: float = AGREEMENT_FLOOR_PX,
                              **kwargs: Any) -> tuple[RegistrationResult, RegistrationResult, EngineAgreement]:
    """Run two independent engines, measure their agreement, and fold it into
    the primary engine's verdict (R2). Returns (primary, secondary, agreement).

    The primary defaults to the first engine. The secondary's verdict is
    computed without the agreement term, so the two results are independent
    evidence and only the primary's verdict is capped.
    """
    a, b = engines
    primary = primary or a
    ra = register_pair(source, reference, engine=a, **kwargs)
    rb = register_pair(source, reference, engine=b, **kwargs)
    src_shape = np.asarray(source).shape
    agr = engine_agreement(a, ra.transform, b, rb.transform, src_shape, floor_px=floor_px)
    prim, sec = (ra, rb) if primary == a else (rb, ra)
    if agr.agree is not None:
        prim = with_agreement(prim, src_shape, agr.median_px, floor_px,
                              loop_error_px=kwargs.get("loop_error_px"))
    return prim, sec, agr


def with_agreement(res: RegistrationResult, shape: tuple[int, int], agreement_px: float,
                   floor_px: float = AGREEMENT_FLOOR_PX, *,
                   loop_error_px: float | None = None) -> RegistrationResult:
    """Re-run ONLY the verdict (stage 4) with the agreement term. The estimate,
    refinement and re-estimation are the recorded ones; nothing is recomputed,
    so the live two-engine path costs one extra assess(), not a third engine run."""
    from dataclasses import replace
    t0 = time.perf_counter()
    verdict = assess(
        transform=res.transform, src_points=res.src_points, dst_points=res.dst_points_refined,
        inlier_mask=res.inlier_mask, shape=shape,
        fit_rmse=float(res.baseline.ransac.inlier_rmse) if res.baseline.ransac is not None else None,
        loop_error_px=loop_error_px, engine_agreement_px=agreement_px,
        engine_agreement_floor_px=floor_px,
        annotations={k: v for k, v in res.verdict.metrics.items()
                     if k in ("engine", "pipeline_order", "model_selected_by", "initial_model",
                              "n_refined", "heldout_px", "decided_by_tie_break")})
    rt = dict(res.runtime_s); rt["verify_with_agreement"] = time.perf_counter() - t0
    return replace(res, verdict=verdict, runtime_s=rt)
