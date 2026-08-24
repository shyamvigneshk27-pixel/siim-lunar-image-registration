"""EXP-001 -- RootSIFT classical baseline against synthetic ground truth.

Purpose (ANALYSIS §I): establish a trustworthy classical baseline *and* a
non-circular evaluation harness, before any learned matcher is considered.

The harness is the deliverable as much as the baseline is. Every case reports
both what the pipeline believes about itself (inlier ratio, fit RMSE) and what
is actually true (GT precision, true transform error). The gap between those
two columns is the finding.

Run:  python scripts/run_exp001.py
"""

from __future__ import annotations

import csv
import json
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siim.baselines import run_rootsift_baseline  # noqa: E402
from siim.data import height_field, make_pair  # noqa: E402
from siim.evaluation import (  # noqa: E402
    classify_failure,
    correspondence_metrics,
    coverage_metrics,
)
from siim.geometry import (  # noqa: E402
    anchor_at,
    affine,
    image_centre,
    pixel_grid,
    projective,
    similarity,
    translation,
    euclidean,
)

SEED = 20260824
SHAPE = (512, 512)
FIELD = (1024, 1024)
RANSAC_THRESHOLD = 3.0
CORRECT_THRESHOLD = 3.0
SUN_REF = (315.0, 45.0)  # NW illumination, mid elevation -- a standard choice

OUT = ROOT / "experiments" / "EXP-001"


# --------------------------------------------------------------- ROI helper


def overlap_roi(gt_transform, shape) -> np.ndarray:
    """Source-image mask of pixels that have a counterpart in the reference.

    Coverage must be scored over the *overlap*, not the whole frame: penalising
    a method for finding no matches where no common terrain exists would be
    measuring the scene, not the method.
    """
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


# ------------------------------------------------------------- case running


@dataclass
class Case:
    group: str
    label: str
    transform: object
    scene: str = "highlands"
    sun_source: tuple = SUN_REF
    sun_reference: tuple | None = None
    ambiguity: float = 0.0
    root_sift: bool = True
    model: str = "affine"


def run_case(case: Case, field_cache: dict) -> dict:
    key = (case.scene, round(case.ambiguity, 3))
    if key not in field_cache:
        field_cache[key] = height_field(
            FIELD,
            np.random.default_rng(SEED + hash(key) % 1000),
            scene=case.scene,
            ambiguity=case.ambiguity,
        )

    t0 = time.perf_counter()
    pair = make_pair(
        np.random.default_rng(SEED),
        case.transform,
        scene=case.scene,
        out_shape=SHAPE,
        sun_source=case.sun_source,
        sun_reference=case.sun_reference,
        ambiguity=case.ambiguity,
        base_field=field_cache[key],
    )
    gen_s = time.perf_counter() - t0

    res = run_rootsift_baseline(
        pair.source,
        pair.reference,
        model=case.model,
        ransac_threshold=RANSAC_THRESHOLD,
        root_sift=case.root_sift,
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
        runtime=res.runtime,
    )

    src_in, _ = res.inlier_points
    cov = coverage_metrics(src_in, SHAPE, roi=overlap_roi(pair.transform, SHAPE))
    failure = classify_failure(m, coverage=cov)

    return {
        "group": case.group,
        "label": case.label,
        "scene": case.scene,
        "model": case.model,
        "root_sift": case.root_sift,
        "delta_azimuth_deg": pair.meta["delta_azimuth_deg"],
        "delta_elevation_deg": pair.meta["delta_elevation_deg"],
        "sun_elevation_src": case.sun_source[1],
        "ambiguity": case.ambiguity,
        "overlap_fraction": pair.overlap_fraction,
        "n_kp_src": m.n_keypoints_src,
        "n_kp_dst": m.n_keypoints_dst,
        "n_putative": m.n_putative,
        "n_inliers": m.n_inliers,
        "reported_inlier_ratio": m.reported_inlier_ratio,
        "reported_fit_rmse": m.reported_inlier_rmse,
        "true_putative_precision": m.true_putative_precision,
        "true_inlier_precision": m.true_inlier_precision,
        "true_inlier_recall": m.true_inlier_recall,
        "true_error_median": m.true_error_median,
        "true_error_p90": m.true_error_p90,
        "transform_error_median": m.transform_error_median,
        "transform_error_p90": m.transform_error_p90,
        "transform_error_max": m.transform_error_max,
        "confidence_gap": m.confidence_gap,
        "coverage_max_gap_ratio": cov.max_uncovered_disc_ratio,
        "coverage_occupancy": cov.grid_occupancy,
        "coverage_entropy": cov.spatial_entropy,
        "failure_mode": failure,
        "gen_s": gen_s,
        "detect_s": res.runtime["detect_describe_s"],
        "match_s": res.runtime["match_s"],
        "ransac_s": res.runtime["ransac_s"],
        "pipeline_s": res.runtime["total_s"],
    }


# ------------------------------------------------------------- case catalogue


def build_cases() -> list[Case]:
    c = image_centre(SHAPE)
    cases: list[Case] = []

    # A -- transform model recovery, illumination held fixed.
    models = {
        "translation": translation(14.0, -9.0),
        "euclidean": anchor_at(euclidean(np.deg2rad(7.0), 10.0, -6.0), c),
        "similarity": anchor_at(similarity(1.15, np.deg2rad(7.0), 10.0, -6.0), c),
        "affine": anchor_at(affine([[1.05, 0.06, 10.0], [-0.04, 1.02, -6.0]]), c),
        "projective": anchor_at(
            projective(
                [[1.03, 0.04, 8.0], [-0.03, 1.01, -5.0], [4.0e-5, -2.5e-5, 1.0]]
            ),
            c,
        ),
    }
    for name, tf in models.items():
        fit = "projective" if name == "projective" else "affine"
        cases.append(Case("A_model", f"truth={name}", tf, model=fit))

    # B -- illumination sweep. THE headline axis (spec §13).
    base_tf = anchor_at(similarity(1.0, np.deg2rad(5.0), 10.0, -6.0), c)
    for d_az in (0, 15, 30, 45, 60, 90, 135, 180):
        cases.append(
            Case(
                "B_azimuth",
                f"d_az={d_az}",
                base_tf,
                sun_reference=(SUN_REF[0] + d_az, SUN_REF[1]),
            )
        )
    for d_el in (-30, -15, 15):
        cases.append(
            Case(
                "B_elevation",
                f"d_el={d_el}",
                base_tf,
                sun_reference=(SUN_REF[0], SUN_REF[1] + d_el),
            )
        )

    # C -- scale sweep. Real sensor ratios go to 320:1 (ANALYSIS §C.3); this
    # probes where a naive pipeline gives out, which is expected far sooner.
    for s in (1.0, 1.25, 1.5, 2.0, 3.0, 4.0):
        cases.append(
            Case("C_scale", f"scale={s}", anchor_at(similarity(s, 0.0, 0.0, 0.0), c))
        )

    # D -- scene types, with and without an illumination change.
    for scene in ("highlands", "mare", "repetitive", "mixed"):
        cases.append(Case("D_scene", f"{scene}/same_sun", base_tf, scene=scene))
        cases.append(
            Case(
                "D_scene",
                f"{scene}/d_az=60",
                base_tf,
                scene=scene,
                sun_reference=(SUN_REF[0] + 60, SUN_REF[1]),
            )
        )

    # E -- adversarial repetition. Shift by exactly one lattice period so a
    # wrong-but-self-consistent solution is available to be found.
    for amb in (0.0, 0.4, 0.7, 0.9, 1.0):
        cases.append(
            Case(
                "E_ambiguity",
                f"ambiguity={amb}",
                translation(64.0, 0.0),
                scene="repetitive",
                ambiguity=amb,
                sun_source=(315.0, 35.0),
            )
        )

    # F -- low Sun. Long shadows, high contrast: the polar-like regime.
    for el in (10.0, 20.0, 35.0, 60.0):
        cases.append(
            Case(
                "F_low_sun",
                f"elevation={el}",
                base_tf,
                sun_source=(315.0, el),
                sun_reference=(315.0 + 45.0, el),
            )
        )

    # G -- RootSIFT vs plain SIFT. Justifies the B1 choice by measurement
    # rather than by citation (spec §49: no weak baselines).
    for rs in (True, False):
        for d_az in (0, 45, 90):
            cases.append(
                Case(
                    "G_rootsift",
                    f"root_sift={rs}/d_az={d_az}",
                    base_tf,
                    sun_reference=(SUN_REF[0] + d_az, SUN_REF[1]),
                    root_sift=rs,
                )
            )

    return cases


# ------------------------------------------------------------------ figures


def make_figures(rows: list[dict], field_cache: dict) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib unavailable; skipping figures")
        return

    fig_dir = OUT / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    # 1 -- illumination degradation
    az = [r for r in rows if r["group"] == "B_azimuth"]
    az.sort(key=lambda r: abs(r["delta_azimuth_deg"]))
    x = [abs(r["delta_azimuth_deg"]) for r in az]
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
    ax[0].plot(x, [r["n_inliers"] for r in az], "o-", color="#3b6fb6")
    ax[0].set_ylabel("inliers"); ax[0].set_yscale("symlog")
    ax[1].plot(x, [r["true_inlier_precision"] for r in az], "o-", color="#2e8b57")
    ax[1].set_ylabel("TRUE inlier precision"); ax[1].set_ylim(-0.05, 1.05)
    ax[2].semilogy(
        [xx for xx, r in zip(x, az) if np.isfinite(r["transform_error_median"])],
        [r["transform_error_median"] for r in az if np.isfinite(r["transform_error_median"])],
        "o-", color="#c0392b",
    )
    ax[2].axhline(1.0, ls="--", c="grey", lw=1)
    ax[2].set_ylabel("true transform error (px)")
    for a in ax:
        a.set_xlabel("|Sun azimuth change| (deg)"); a.grid(alpha=0.3)
    fig.suptitle("EXP-001 B: RootSIFT vs Sun-azimuth change (synthetic terrain, exact GT)")
    fig.tight_layout(); fig.savefig(fig_dir / "illumination_curve.png", dpi=130); plt.close(fig)

    # 2 -- scale degradation
    sc = sorted(
        [r for r in rows if r["group"] == "C_scale"],
        key=lambda r: float(r["label"].split("=")[1]),
    )
    xs = [float(r["label"].split("=")[1]) for r in sc]
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
    ax[0].plot(xs, [r["n_inliers"] for r in sc], "o-", color="#3b6fb6")
    ax[0].set_ylabel("inliers")
    ax[1].semilogy(xs, [max(r["transform_error_median"], 1e-3) for r in sc], "o-", color="#c0392b")
    ax[1].axhline(1.0, ls="--", c="grey", lw=1); ax[1].set_ylabel("true transform error (px)")
    for a in ax:
        a.set_xlabel("scale ratio"); a.grid(alpha=0.3)
    fig.suptitle("EXP-001 C: RootSIFT vs scale ratio")
    fig.tight_layout(); fig.savefig(fig_dir / "scale_curve.png", dpi=130); plt.close(fig)

    # 3 -- what shadow reversal actually looks like
    fld = field_cache.get(("highlands", 0.0))
    if fld is not None:
        tf = anchor_at(similarity(1.0, np.deg2rad(5.0), 10.0, -6.0), image_centre(SHAPE))
        fig, ax = plt.subplots(1, 4, figsize=(14, 3.7))
        for i, (ttl, sun) in enumerate(
            [("source, Sun 315deg", None), ("d_az=0", (315.0, 45.0)),
             ("d_az=90", (45.0, 45.0)), ("d_az=180 (reversal)", (135.0, 45.0))]
        ):
            p = make_pair(np.random.default_rng(SEED), tf, scene="highlands",
                          out_shape=SHAPE, sun_source=(315.0, 45.0),
                          sun_reference=sun, base_field=fld)
            ax[i].imshow(p.source if i == 0 else p.reference, cmap="gray", vmin=0, vmax=1)
            ax[i].set_title(ttl, fontsize=10); ax[i].axis("off")
        fig.suptitle("EXP-001: physically re-illuminated terrain -- crater shading inverts")
        fig.tight_layout(); fig.savefig(fig_dir / "illumination_examples.png", dpi=130); plt.close(fig)

    print(f"figures -> {fig_dir}")


# ---------------------------------------------------------------------- main


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cases = build_cases()
    field_cache: dict = {}
    rows: list[dict] = []

    t_start = time.perf_counter()
    for i, case in enumerate(cases, 1):
        row = run_case(case, field_cache)
        rows.append(row)
        print(
            f"[{i:2d}/{len(cases)}] {case.group:13s} {case.label:24s} "
            f"put={row['n_putative']:5d} inl={row['n_inliers']:5d} "
            f"rep={row['reported_inlier_ratio']:.3f} "
            f"TRUEprec={row['true_inlier_precision']:.3f} "
            f"tf_err={row['transform_error_median']:9.3f}px  {row['failure_mode']}"
        )
    total_s = time.perf_counter() - t_start

    with open(OUT / "results.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "experiment": "EXP-001",
        "objective": (
            "Establish a trustworthy RootSIFT classical baseline and a "
            "non-circular (ground-truth-based) evaluation harness."
        ),
        "seed": SEED,
        "config": {
            "shape": SHAPE,
            "field": FIELD,
            "ransac_threshold_px": RANSAC_THRESHOLD,
            "correct_threshold_px": CORRECT_THRESHOLD,
            "sun_reference": SUN_REF,
            "ratio_test": 0.8,
            "mutual_nn": True,
            "ransac_model_default": "affine",
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "opencv": __import__("cv2").__version__,
            "platform": platform.platform(),
        },
        "n_cases": len(rows),
        "total_runtime_s": total_s,
        "failure_counts": {
            k: sum(1 for r in rows if r["failure_mode"] == k)
            for k in sorted({r["failure_mode"] for r in rows})
        },
        "rows": rows,
    }
    (OUT / "metrics.json").write_text(json.dumps(summary, indent=2, default=float))

    make_figures(rows, field_cache)

    print(f"\n{len(rows)} cases in {total_s:.1f}s")
    print("failure modes:", summary["failure_counts"])
    print(f"written: {OUT/'results.csv'}, {OUT/'metrics.json'}")


if __name__ == "__main__":
    main()
