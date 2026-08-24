"""EXP-003 shared machinery: representation arms and the per-case runner.

The fair-comparison guarantee (EXP-003 §1.6) is enforced structurally, not by
discipline: ``run_all_arms`` takes ONE already-built image pair and hands the
identical ``source``/``reference`` arrays to every arm. No arm can see a
different pair, seed, transform or scoring path, because none of them is given
the opportunity to build one.

Everything downstream of the descriptor -- matching, LO-RANSAC, metrics,
coverage, the success criterion -- is the project's existing code, called
identically for every arm.

Ground truth is used only to SCORE. No arm receives ``pair.transform``.
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
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from exp002_common import (  # noqa: E402
    CORRECT_THRESHOLD,
    FIELD_MARGIN,
    RANSAC_THRESHOLD,
    SHAPE,
    SUN_REF,
    WRONG_PX,
    make_transform,
    overlap_roi,
)

from siim.data import TERRAIN_REGIMES, height_field, make_pair  # noqa: E402
from siim.evaluation import correspondence_metrics, coverage_metrics  # noqa: E402
from siim.matching.descriptors import (  # noqa: E402
    describe_gradient_histogram,
    describe_maximum_index,
)
from siim.matching.representations import (  # noqa: E402
    identity_representation,
    maximum_index_map,
    phase_congruency,
)
from siim.matching.rootsift import (  # noqa: E402
    Features,
    detect_and_describe,
    match_descriptors,
)
from siim.verification.ransac import ransac  # noqa: E402

#: Seeds for EXP-003. Disjoint from every EXP-002 seed (1001-1005, 7001-7004)
#: so the D-023 operating point is applied to terrain it never saw.
EXP003_SEEDS = (3001, 3002, 3003)

#: Pre-registered azimuth grid (EXP-003 §1.10). 0 and 15 are controls.
AZIMUTH_GRID = (0.0, 15.0, 18.0, 21.0, 24.0, 27.0, 30.0, 33.0, 36.0, 40.0, 45.0)

#: Priority order fixed by D-019. Mare first, and reported independently.
PRIMARY_REGIMES = ("A_mare_moderate", "A_highlands_moderate", "B_highlands_challenging")

#: Number of log-Gabor orientations. Shared by the PC and RIFT arms so the
#: maximum-index map and the phase-congruency map come from one filter bank.
PC_N_ORIENT = 6

_FIELD_CACHE: dict[tuple, np.ndarray] = {}
_PC_CACHE: dict[int, object] = {}


def get_field(regime_name: str, seed: int) -> np.ndarray:
    """Height field for a regime/seed, cached. Same construction as EXP-002."""
    key = (regime_name, seed)
    if key not in _FIELD_CACHE:
        reg = TERRAIN_REGIMES[regime_name]
        _FIELD_CACHE[key] = height_field(
            (int(SHAPE[0] * FIELD_MARGIN), int(SHAPE[1] * FIELD_MARGIN)),
            np.random.default_rng(seed),
            scene=reg.scene,
            ambiguity=0.0,
            target_slope_median_deg=reg.target_slope_median_deg,
            octaves=reg.octaves,
            persistence=reg.persistence,
            crater_density=reg.crater_density,
            pixel_scale=1.0,
        )
    return _FIELD_CACHE[key]


def _pc_cached(image: np.ndarray):
    """Phase congruency for an image, memoised on identity within a case.

    Both PC arms need the same filter-bank output for the same image; computing
    it twice would only waste time and could not change the result.
    """
    key = id(image)
    if key not in _PC_CACHE:
        _PC_CACHE[key] = phase_congruency(image, n_orient=PC_N_ORIENT)
    return _PC_CACHE[key]


def clear_pc_cache() -> None:
    _PC_CACHE.clear()


# ---------------------------------------------------------------------------
# representation arms
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Arm:
    """One representation arm: how an image becomes features."""

    name: str
    kind: str
    note: str

    def features(self, image: np.ndarray) -> Features:
        img = np.asarray(image, dtype=np.float64)

        if self.kind == "opencv_rootsift":
            return detect_and_describe(img, root_sift=True)

        if self.kind == "opencv_sift":
            return detect_and_describe(img, root_sift=False)

        if self.kind in ("grad_hist_pi", "grad_hist_2pi"):
            # Same detector as B1: only the DESCRIPTOR differs, which is what
            # isolates the orientation-binning hypothesis (H-3.4).
            base = detect_and_describe(img, root_sift=True)
            if len(base) == 0:
                return base
            period = np.pi if self.kind == "grad_hist_pi" else 2.0 * np.pi
            desc = describe_gradient_histogram(
                identity_representation(img),
                base.points,
                base.scales,
                orientation_period=period,
            )
            return Features(
                points=base.points, descriptors=desc,
                scales=base.scales, angles=base.angles, responses=base.responses,
            )

        if self.kind == "pc_rootsift":
            pc = _pc_cached(img).pc
            return detect_and_describe(pc, root_sift=True)

        if self.kind == "pc_mim":
            res = _pc_cached(img)
            base = detect_and_describe(res.pc, root_sift=True)
            if len(base) == 0:
                return base
            mim = maximum_index_map(res.orientation_amplitude)
            desc = describe_maximum_index(
                mim, base.points, base.scales, n_index=PC_N_ORIENT
            )
            return Features(
                points=base.points, descriptors=desc,
                scales=base.scales, angles=base.angles, responses=base.responses,
            )

        raise ValueError(f"unknown arm kind {self.kind!r}")


ARMS: tuple[Arm, ...] = (
    Arm("B1_rootsift", "opencv_rootsift",
        "Established baseline B1: OpenCV SIFT detect + RootSIFT descriptor."),
    Arm("B1_sift", "opencv_sift",
        "Established control: same detector, plain SIFT descriptor (ADR-0009)."),
    Arm("A_orient_mod_pi", "grad_hist_pi",
        "H-3.1: B1 keypoints, gradient-orientation histogram binned over [0, pi)."),
    Arm("A_orient_2pi_control", "grad_hist_2pi",
        "H-3.4 control: identical code at [0, 2pi). Isolates the binning period."),
    Arm("B_phase_congruency", "pc_rootsift",
        "H-3.2: detect and describe on the phase-congruency map."),
    Arm("C_rift2_mim", "pc_mim",
        "H-3.3: RIFT-style, PC detection + maximum-index-map descriptor."),
)


# ---------------------------------------------------------------------------
# case construction and evaluation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CaseSpec:
    regime: str
    seed: int
    delta_azimuth: float
    transform_kind: str = "affine"
    fit_model: str = "affine"
    delta_elevation: float = 0.0
    sun_elevation: float = 45.0


def build_pair(spec: CaseSpec):
    """The ONE image pair every arm in this case will see."""
    rng = np.random.default_rng(spec.seed * 31 + int(spec.delta_azimuth))
    tf = make_transform(spec.transform_kind, rng)
    return make_pair(
        np.random.default_rng(spec.seed),
        tf,
        scene=TERRAIN_REGIMES[spec.regime].scene,
        out_shape=SHAPE,
        sun_source=(SUN_REF[0], spec.sun_elevation),
        sun_reference=(SUN_REF[0] + spec.delta_azimuth,
                       spec.sun_elevation + spec.delta_elevation),
        ambiguity=0.0,
        base_field=get_field(spec.regime, spec.seed),
        field_margin=FIELD_MARGIN,
    )


def evaluate_arm(arm: Arm, pair, spec: CaseSpec) -> dict:
    """Run one arm on an already-built pair and score it against ground truth."""
    t0 = time.perf_counter()
    f_src = arm.features(pair.source)
    f_dst = arm.features(pair.reference)
    detect_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    matches = match_descriptors(f_src, f_dst, ratio=0.8, mutual=True)
    match_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    rres = ransac(
        matches.src_points, matches.dst_points,
        model=spec.fit_model, threshold=RANSAC_THRESHOLD, seed=0,
    )
    ransac_s = time.perf_counter() - t0

    m = correspondence_metrics(
        matches.src_points, matches.dst_points, rres.inlier_mask,
        gt_transform=pair.transform,          # SCORING ONLY
        estimated_transform=rres.transform,
        shape=SHAPE,
        n_keypoints_src=len(f_src), n_keypoints_dst=len(f_dst),
        reported_inlier_rmse=rres.inlier_rmse,
        correct_threshold=CORRECT_THRESHOLD,
    )
    mask = rres.inlier_mask
    src_in = matches.src_points[mask] if mask.size else np.zeros((0, 2))
    cov = coverage_metrics(src_in, SHAPE, roi=overlap_roi(pair.transform))

    wrong = (not np.isfinite(m.transform_error_median)
             or m.transform_error_median > WRONG_PX)

    return {
        "representation": arm.name,
        "regime": spec.regime,
        "seed": spec.seed,
        "delta_azimuth": spec.delta_azimuth,
        "delta_elevation": spec.delta_elevation,
        "sun_elevation": spec.sun_elevation,
        "transform_kind": spec.transform_kind,
        "fit_model": spec.fit_model,
        "overlap_fraction": pair.overlap_fraction,
        "n_kp_src": m.n_keypoints_src,
        "n_kp_dst": m.n_keypoints_dst,
        "n_putative": m.n_putative,
        "n_inliers": m.n_inliers,
        "inlier_ratio": m.reported_inlier_ratio,
        # recorded for the record; forbidden as a criterion (EXP-003 §1.8)
        "fit_rmse": m.reported_inlier_rmse,
        "coverage_max_gap": cov.max_uncovered_disc_ratio,
        "coverage_occupancy": cov.grid_occupancy,
        "coverage_entropy": cov.spatial_entropy,
        # ground truth: scoring only
        "true_inlier_precision": m.true_inlier_precision,
        "transform_error_median": m.transform_error_median,
        "transform_error_p90": m.transform_error_p90,
        "is_wrong": bool(wrong),
        # the deployable flag fixed by D-023
        "flag_n_inliers_le_8": bool(m.n_inliers <= 8),
        "detect_describe_s": detect_s,
        "match_s": match_s,
        "ransac_s": ransac_s,
        "pipeline_s": detect_s + match_s + ransac_s,
    }


def run_all_arms(spec: CaseSpec, arms=ARMS) -> list[dict]:
    """Build the pair once; evaluate every arm on it."""
    pair = build_pair(spec)
    clear_pc_cache()
    rows = []
    for arm in arms:
        rows.append(evaluate_arm(arm, pair, spec))
    clear_pc_cache()
    return rows


# ---------------------------------------------------------------------------
# the pre-registered success criterion
# ---------------------------------------------------------------------------

def last_fully_successful_azimuth(rows: list[dict], grid=AZIMUTH_GRID) -> float | None:
    """Largest Δaz whose success rate is 1.00, with every smaller Δaz also 1.00.

    Same semantics as EXP-002's ``last_fully_successful_delta_azimuth``. Fixed
    in EXP-003 §1.4 before any result existed.
    """
    last = None
    for az in sorted(grid):
        at_az = [r for r in rows if r["delta_azimuth"] == az]
        if not at_az:
            continue
        if all(not r["is_wrong"] for r in at_az):
            last = az
        else:
            break
    return last
