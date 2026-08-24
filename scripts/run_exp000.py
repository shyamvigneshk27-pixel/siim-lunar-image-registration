"""EXP-000 -- geometry gate measurements.

Produces the numbers recorded in ``experiments/EXP-000/metrics.json``.
Tests answer "is it correct?"; this answers "how correct, and how fast?",
which is what the benchmark table needs (spec §34, §101).

Run:  python scripts/run_exp000.py
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siim.geometry import (  # noqa: E402
    MODEL_ORDER,
    corner_points,
    endpoint_error,
    estimate,
    identity,
    image_centre,
    pixel_grid,
    random_transform,
    resize,
    scale_transform,
    similarity,
    warp,
)

SEED = 20260824
SHAPE = (512, 512)


def measure_recovery(rng: np.random.Generator) -> dict:
    """True endpoint error when recovering each model from exact points."""
    out = {}
    for model in MODEL_ORDER:
        worst_max, worst_med, conds = 0.0, 0.0, []
        t0 = time.perf_counter()
        trials = 50
        for _ in range(trials):
            truth = random_transform(rng, model, SHAPE)
            src = rng.uniform(0, SHAPE[1], size=(60, 2))
            res = estimate(src, truth.apply(src), model)
            assert res.ok, res.reason
            err = endpoint_error(res.transform, truth, SHAPE, step=32)
            worst_max = max(worst_max, err.max)
            worst_med = max(worst_med, err.median)
            conds.append(res.condition)
        elapsed = time.perf_counter() - t0
        out[model] = {
            "trials": trials,
            "worst_max_endpoint_error_px": worst_max,
            "worst_median_endpoint_error_px": worst_med,
            "max_condition_number": float(np.max(conds)),
            "ms_per_estimate": 1000 * elapsed / trials,
        }
    return out


def measure_large_coordinate_stability(rng: np.random.Generator) -> dict:
    """Does Hartley normalisation hold up at NAC-sized coordinates?

    LRO NAC frames run to ~52,000 lines (S2), so the DLT must stay conditioned
    at coordinates far outside the tidy 0-512 range used elsewhere.
    """
    out = {}
    for extent in (512, 10_000, 60_000):
        worst, conds = 0.0, []
        for _ in range(20):
            truth = random_transform(rng, "projective", (extent, extent))
            src = rng.uniform(0, extent, size=(60, 2))
            res = estimate(src, truth.apply(src), "projective")
            assert res.ok, res.reason
            worst = max(
                worst, endpoint_error(res.transform, truth, (extent, extent), step=extent // 16).max
            )
            conds.append(res.condition)
        out[f"extent_{extent}"] = {
            "worst_max_endpoint_error_px": worst,
            "relative_error": worst / extent,
            "max_condition_number": float(np.max(conds)),
        }
    return out


def measure_scale_convention() -> dict:
    """Contract C4, checked against real resampling of a Gaussian feature."""

    def blob(shape, x0, y0, sigma=4.0):
        yy, xx = np.mgrid[0 : shape[0], 0 : shape[1]].astype(float)
        return np.exp(-(((xx - x0) ** 2 + (yy - y0) ** 2) / (2 * sigma**2)))

    def centroid(img):
        yy, xx = np.mgrid[0 : img.shape[0], 0 : img.shape[1]].astype(float)
        tot = img.sum()
        return np.array([(xx * img).sum() / tot, (yy * img).sum() / tot])

    x0, y0 = 50.3, 61.7
    img = blob((128, 128), x0, y0)
    out = {}
    for s in (0.25, 0.5, 2.0, 3.0):
        resized, tf = resize(img, s)
        measured = centroid(resized)
        predicted = tf.apply([[x0, y0]]).ravel()
        naive = np.array([s * x0, s * y0])
        out[f"scale_{s}"] = {
            "contract_c4_error_px": float(np.abs(measured - predicted).max()),
            "naive_formula_error_px": float(np.abs(measured - naive).max()),
        }
    return out


def measure_warp(rng: np.random.Generator) -> dict:
    """Round-trip resampling loss on a smooth synthetic terrain image."""
    from scipy import ndimage

    gen = np.random.default_rng(7)
    terrain = ndimage.gaussian_filter(gen.normal(size=(256, 256)), sigma=4.0)
    terrain -= terrain.min()
    terrain /= terrain.max()

    tf = similarity(1.0, np.deg2rad(11.0), 4.0, -3.0)
    t0 = time.perf_counter()
    once, _ = warp(terrain, tf, cval=0.0)
    warp_ms = 1000 * (time.perf_counter() - t0)
    back, _ = warp(once, tf.inverse(), cval=0.0)

    interior = (slice(60, 196), slice(60, 196))
    diff = np.abs(back[interior] - terrain[interior])

    ident, valid = warp(terrain, identity())
    return {
        "identity_warp_max_error": float(np.abs(ident - terrain).max()),
        "round_trip_median_error": float(np.median(diff)),
        "round_trip_p99_error": float(np.percentile(diff, 99)),
        "round_trip_max_error": float(diff.max()),
        "warp_ms_256x256_cubic": warp_ms,
    }


def main() -> None:
    rng = np.random.default_rng(SEED)
    t0 = time.perf_counter()

    metrics = {
        "experiment": "EXP-000",
        "objective": (
            "Establish a verified geometry layer and coordinate contract before "
            "any real lunar data is touched (ADR-0007, ANALYSIS §I gate)."
        ),
        "seed": SEED,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
            "processor": platform.processor(),
        },
        "model_recovery": measure_recovery(rng),
        "large_coordinate_stability": measure_large_coordinate_stability(rng),
        "scale_convention_c4": measure_scale_convention(),
        "resampling": measure_warp(rng),
        "total_runtime_s": None,
    }
    metrics["total_runtime_s"] = time.perf_counter() - t0

    out_dir = ROOT / "experiments" / "EXP-000"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

    # Console summary
    print(f"EXP-000  seed={SEED}  ({metrics['total_runtime_s']:.1f}s)\n")
    print("Exact-correspondence recovery (true endpoint error over 50 trials):")
    for model, m in metrics["model_recovery"].items():
        print(
            f"  {model:<12} max={m['worst_max_endpoint_error_px']:.3e} px   "
            f"cond<={m['max_condition_number']:.3g}   "
            f"{m['ms_per_estimate']:.2f} ms/fit"
        )
    print("\nLarge-coordinate stability (homography, Hartley-normalised):")
    for k, m in metrics["large_coordinate_stability"].items():
        print(
            f"  {k:<14} max={m['worst_max_endpoint_error_px']:.3e} px   "
            f"rel={m['relative_error']:.2e}   cond<={m['max_condition_number']:.3g}"
        )
    print("\nContract C4 (scale offset) vs real resampling:")
    for k, m in metrics["scale_convention_c4"].items():
        print(
            f"  {k:<12} contract={m['contract_c4_error_px']:.4f} px   "
            f"naive={m['naive_formula_error_px']:.4f} px"
        )
    print("\nResampling:")
    for k, v in metrics["resampling"].items():
        print(f"  {k:<32} {v:.5f}")
    print(f"\nWritten: {out_dir / 'metrics.json'}")


if __name__ == "__main__":
    main()
