"""Shared case-running helpers for EXP-002 objectives 2-4.

One case = one synthetic pair + the B1 baseline + every metric we can compute,
both ground-truth-based (for scoring) and ground-truth-free (for deployment).

Seed discipline
---------------
``CALIBRATION_SEEDS`` and ``VALIDATION_SEEDS`` are disjoint and are used to
build *different terrain*. Any threshold selected on calibration cases is
evaluated only on validation cases. This is the whole point of EXP-002
objectives 3 and 4: EXP-001's "inlier count >= 8" separation was chosen and
evaluated on the same 45 cases, so it was not evidence of anything.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from siim.baselines import run_rootsift_baseline  # noqa: E402
from siim.data import TERRAIN_REGIMES, height_field, make_pair  # noqa: E402
from siim.evaluation import (  # noqa: E402
    correspondence_metrics,
    coverage_metrics,
    held_out_residual,
    spatial_split_consistency,
)
from siim.geometry import (  # noqa: E402
    affine,
    anchor_at,
    euclidean,
    image_centre,
    pixel_grid,
    projective,
    similarity,
    translation,
)

SHAPE = (384, 384)
FIELD_MARGIN = 2.0
RANSAC_THRESHOLD = 3.0
CORRECT_THRESHOLD = 3.0
SUN_REF = (315.0, 45.0)

#: A case counts as *wrong* when the estimated map differs from truth by more
#: than this, in median true endpoint error over the image.
WRONG_PX = 3.0

CALIBRATION_SEEDS = (1001, 1002, 1003, 1004)
VALIDATION_SEEDS = (7001, 7002, 7003, 7004)

_FIELD_CACHE: dict[tuple, np.ndarray] = {}


def get_field(regime_name: str, seed: int, ambiguity: float = 0.0) -> np.ndarray:
    key = (regime_name, seed, round(ambiguity, 3))
    if key not in _FIELD_CACHE:
        reg = TERRAIN_REGIMES[regime_name]
        h = int(SHAPE[0] * FIELD_MARGIN)
        w = int(SHAPE[1] * FIELD_MARGIN)
        _FIELD_CACHE[key] = height_field(
            (h, w),
            np.random.default_rng(seed),
            scene=reg.scene if ambiguity == 0.0 else "repetitive",
            ambiguity=ambiguity,
            target_slope_median_deg=reg.target_slope_median_deg,
            octaves=reg.octaves,
            persistence=reg.persistence,
            crater_density=reg.crater_density,
            pixel_scale=1.0,
        )
    return _FIELD_CACHE[key]


def make_transform(kind: str, rng: np.random.Generator, shape=SHAPE):
    """A transform of the requested class, with moderate, overlap-preserving size."""
    c = image_centre(shape)
    tx = float(rng.uniform(-14, 14))
    ty = float(rng.uniform(-14, 14))
    ang = float(np.deg2rad(rng.uniform(-8, 8)))
    sc = float(rng.uniform(0.9, 1.15))
    if kind == "translation":
        return translation(tx, ty)
    if kind == "euclidean":
        return anchor_at(euclidean(ang, tx, ty), c)
    if kind == "similarity":
        return anchor_at(similarity(sc, ang, tx, ty), c)
    if kind == "affine":
        cc, ss = sc * np.cos(ang), sc * np.sin(ang)
        sh = float(rng.uniform(-0.05, 0.05))
        return anchor_at(affine([[cc, -ss + sh * cc, tx], [ss, cc + sh * ss, ty]]), c)
    if kind == "projective":
        cc, ss = sc * np.cos(ang), sc * np.sin(ang)
        g = float(rng.uniform(-4e-5, 4e-5))
        hh = float(rng.uniform(-4e-5, 4e-5))
        return anchor_at(
            projective([[cc, -ss, tx], [ss, cc, ty], [g, hh, 1.0]]), c
        )
    raise ValueError(f"unknown transform kind {kind!r}")


def overlap_roi(gt_transform, shape=SHAPE) -> np.ndarray:
    h, w = shape
    grid = pixel_grid(shape)
    mapped = gt_transform.apply(grid)
    ok = (
        np.isfinite(mapped).all(axis=1)
        & (mapped[:, 0] >= -0.5)
        & (mapped[:, 0] <= w - 0.5)
        & (mapped[:, 1] >= -0.5)
        & (mapped[:, 1] <= h - 0.5)
    )
    return ok.reshape(h, w)


@dataclass
class CaseSpec:
    regime: str
    seed: int
    transform_kind: str = "affine"
    delta_azimuth: float = 0.0
    delta_elevation: float = 0.0
    sun_elevation: float = 45.0
    scale: float | None = None
    ambiguity: float = 0.0
    fit_model: str = "affine"
    label: str = ""


def run_case(spec: CaseSpec) -> dict:
    """Build a pair, run B1, and compute every metric. Returns a flat row."""
    rng = np.random.default_rng(spec.seed * 31 + int(spec.delta_azimuth))
    if spec.scale is not None:
        tf = anchor_at(similarity(spec.scale, 0.0, 6.0, -4.0), image_centre(SHAPE))
    else:
        tf = make_transform(spec.transform_kind, rng)

    sun_src = (SUN_REF[0], spec.sun_elevation)
    sun_ref = (
        SUN_REF[0] + spec.delta_azimuth,
        spec.sun_elevation + spec.delta_elevation,
    )

    t0 = time.perf_counter()
    pair = make_pair(
        np.random.default_rng(spec.seed),
        tf,
        scene=TERRAIN_REGIMES[spec.regime].scene,
        out_shape=SHAPE,
        sun_source=sun_src,
        sun_reference=sun_ref,
        ambiguity=spec.ambiguity,
        base_field=get_field(spec.regime, spec.seed, spec.ambiguity),
        field_margin=FIELD_MARGIN,
    )
    gen_s = time.perf_counter() - t0

    res = run_rootsift_baseline(
        pair.source,
        pair.reference,
        model=spec.fit_model,
        ransac_threshold=RANSAC_THRESHOLD,
        seed=0,
    )
    m = correspondence_metrics(
        res.matches.src_points,
        res.matches.dst_points,
        res.inlier_mask,
        gt_transform=pair.transform,
        estimated_transform=res.transform,
        shape=SHAPE,
        n_keypoints_src=len(res.src_features),
        n_keypoints_dst=len(res.dst_features),
        reported_inlier_rmse=res.ransac.inlier_rmse,
        correct_threshold=CORRECT_THRESHOLD,
    )
    src_in, dst_in = res.inlier_points
    cov = coverage_metrics(src_in, SHAPE, roi=overlap_roi(pair.transform))

    # --- ground-truth-free estimators (must not see pair.transform) ---
    ho = held_out_residual(src_in, dst_in, model=spec.fit_model, k_folds=5, seed=0)
    split = spatial_split_consistency(
        src_in, dst_in, model=spec.fit_model, shape=SHAPE, seed=0
    )

    wrong = (
        not np.isfinite(m.transform_error_median)
        or m.transform_error_median > WRONG_PX
    )
    return {
        "label": spec.label,
        "regime": spec.regime,
        "seed": spec.seed,
        "transform_kind": spec.transform_kind if spec.scale is None else "similarity",
        "fit_model": spec.fit_model,
        "scale": spec.scale if spec.scale is not None else 1.0,
        "delta_azimuth": spec.delta_azimuth,
        "delta_elevation": spec.delta_elevation,
        "sun_elevation": spec.sun_elevation,
        "ambiguity": spec.ambiguity,
        "overlap_fraction": pair.overlap_fraction,
        # --- what the pipeline knows about itself (deployable signals) ---
        "n_kp_src": m.n_keypoints_src,
        "n_kp_dst": m.n_keypoints_dst,
        "n_putative": m.n_putative,
        "n_inliers": m.n_inliers,
        "inlier_ratio": m.reported_inlier_ratio,
        "fit_rmse": m.reported_inlier_rmse,
        "held_out_median": ho.median,
        "held_out_p90": ho.p90,
        "held_out_ok": ho.ok,
        "split_consistency": split,
        "coverage_max_gap": cov.max_uncovered_disc_ratio,
        "coverage_occupancy": cov.grid_occupancy,
        "coverage_entropy": cov.spatial_entropy,
        # --- ground truth: for SCORING only, never an input to the above ---
        "true_inlier_precision": m.true_inlier_precision,
        "true_putative_precision": m.true_putative_precision,
        "transform_error_median": m.transform_error_median,
        "transform_error_p90": m.transform_error_p90,
        "is_wrong": bool(wrong),
        "gen_s": gen_s,
        "pipeline_s": res.runtime["total_s"],
        "ransac_s": res.runtime["ransac_s"],
    }
