"""EXP-002 objective 2 -- terrain realism, and how it changes EXP-001.

Part A: slope and feature-density statistics for every regime, over several
        seeds, against published lunar values (sources.md S7).
Part B: the separability demonstration -- feature density varied ~27x while
        the median slope is held fixed.
Part C: a representative EXP-001 subset re-run on all four regimes, to
        quantify which EXP-001 conclusions were artefacts of the terrain.

Run:  python scripts/run_exp002_terrain.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from exp002_common import SHAPE, CaseSpec, run_case  # noqa: E402

from siim.data import (  # noqa: E402
    ANGLE_OF_REPOSE_DEG,
    TERRAIN_REGIMES,
    height_field,
    render,
    slope_statistics,
)
from siim.matching import detect_and_describe  # noqa: E402

OUT = ROOT / "experiments" / "EXP-002"
SEEDS = (1001, 1002, 1003, 1004, 1005)

#: LOLA-derived reference values at a 15 m baseline (sources.md S7).
LOLA_REFERENCE = {
    "highlands": {"median_deg": 9.1, "mean_deg": 11.0, "std_deg": 7.0},
    "mare": {"median_deg": 3.5, "mean_deg": 4.9, "std_deg": 4.5},
    "angle_of_repose_deg": ANGLE_OF_REPOSE_DEG,
    "baseline_m": 15.0,
}


def part_a_statistics() -> dict:
    out = {}
    for name, reg in TERRAIN_REGIMES.items():
        stats, densities = [], []
        for seed in SEEDS:
            f = height_field(
                (512, 512),
                np.random.default_rng(seed),
                scene=reg.scene,
                target_slope_median_deg=reg.target_slope_median_deg,
                octaves=reg.octaves,
                persistence=reg.persistence,
                crater_density=reg.crater_density,
                pixel_scale=1.0,
            )
            stats.append(slope_statistics(f, 1.0))
            img = render(f, 315.0, 45.0, pixel_scale=1.0, noise_std=0.002)
            densities.append(len(detect_and_describe(img)) / (512 * 512 / 1e6))

        agg = {
            k: {
                "mean": float(np.mean([s[k] for s in stats])),
                "std": float(np.std([s[k] for s in stats])),
            }
            for k in stats[0]
        }
        out[name] = {
            "scene": reg.scene,
            "target_slope_median_deg": reg.target_slope_median_deg,
            "realistic": reg.realistic,
            "note": reg.note,
            "n_seeds": len(SEEDS),
            "slope": agg,
            "keypoints_per_megapixel": {
                "mean": float(np.mean(densities)),
                "std": float(np.std(densities)),
            },
        }
    return out


def part_b_separability() -> list[dict]:
    """Vary spectral content at a FIXED slope target."""
    rows = []
    for pers, octv in [(0.35, 4), (0.45, 5), (0.60, 6), (0.70, 7)]:
        meds, p99s, dens = [], [], []
        for seed in SEEDS[:3]:
            f = height_field(
                (512, 512),
                np.random.default_rng(seed),
                scene="highlands",
                target_slope_median_deg=9.1,
                octaves=octv,
                persistence=pers,
                pixel_scale=1.0,
            )
            st = slope_statistics(f, 1.0)
            meds.append(st["median_deg"])
            p99s.append(st["p99_deg"])
            dens.append(
                len(detect_and_describe(render(f, 315.0, 45.0, noise_std=0.002)))
                / (512 * 512 / 1e6)
            )
        rows.append({
            "persistence": pers,
            "octaves": octv,
            "slope_median_deg": float(np.mean(meds)),
            "slope_p99_deg": float(np.mean(p99s)),
            "keypoints_per_megapixel": float(np.mean(dens)),
        })
    return rows


def part_c_exp001_subset() -> list[dict]:
    """The EXP-001 headline axes, re-run on every regime with 3 seeds."""
    rows = []
    specs: list[CaseSpec] = []
    for regime in TERRAIN_REGIMES:
        for seed in SEEDS[:3]:
            for d_az in (0, 15, 30, 45, 60, 90):
                specs.append(CaseSpec(
                    regime=regime, seed=seed, transform_kind="similarity",
                    delta_azimuth=float(d_az), label=f"d_az={d_az}",
                ))
            for sc in (1.0, 2.0, 4.0):
                specs.append(CaseSpec(
                    regime=regime, seed=seed, scale=sc, label=f"scale={sc}",
                ))

    for i, spec in enumerate(specs, 1):
        row = run_case(spec)
        rows.append(row)
        if i % 12 == 0 or i == len(specs):
            print(f"  [{i:3d}/{len(specs)}] {spec.regime:24s} {spec.label:12s} "
                  f"inl={row['n_inliers']:5d} err={row['transform_error_median']:9.3f}px")
    return rows


def summarise_c(rows: list[dict]) -> dict:
    """Where is the illumination cliff in each regime?"""
    out = {}
    for regime in TERRAIN_REGIMES:
        per_az, per_scale = {}, {}
        for r in rows:
            if r["regime"] != regime:
                continue
            if r["label"].startswith("d_az"):
                per_az.setdefault(r["delta_azimuth"], []).append(r)
            elif r["label"].startswith("scale"):
                per_scale.setdefault(r["scale"], []).append(r)

        def agg(group):
            return {
                str(k): {
                    "n_seeds": len(v),
                    "success_rate": float(np.mean([not x["is_wrong"] for x in v])),
                    "median_inliers": float(np.median([x["n_inliers"] for x in v])),
                    "median_true_error": float(np.median(
                        [x["transform_error_median"] for x in v])),
                }
                for k, v in sorted(group.items())
            }

        az_agg = agg(per_az)
        # Cliff = largest delta-azimuth at which every seed still succeeded.
        cliff = None
        for k in sorted(per_az, key=float):
            if az_agg[str(k)]["success_rate"] == 1.0:
                cliff = k
        out[regime] = {
            "azimuth": az_agg,
            "scale": agg(per_scale),
            "last_fully_successful_delta_azimuth": cliff,
        }
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("== Part A: slope + feature-density statistics ==")
    stats = part_a_statistics()
    hdr = f"{'regime':26s} {'median':>7s} {'mean':>7s} {'p90':>7s} {'p99':>7s} {'>repose':>8s} {'kp/Mpx':>8s}"
    print(hdr)
    for name, s in stats.items():
        sl = s["slope"]
        print(f"{name:26s} {sl['median_deg']['mean']:7.2f} {sl['mean_deg']['mean']:7.2f} "
              f"{sl['p90_deg']['mean']:7.2f} {sl['p99_deg']['mean']:7.2f} "
              f"{sl['frac_above_repose']['mean']*100:7.2f}% {s['keypoints_per_megapixel']['mean']:8.0f}")
    print(f"  LOLA 15 m reference: highlands median {LOLA_REFERENCE['highlands']['median_deg']}, "
          f"mare median {LOLA_REFERENCE['mare']['median_deg']}, repose {ANGLE_OF_REPOSE_DEG}")

    print("\n== Part B: feature density is separable from slope ==")
    sep = part_b_separability()
    print(f"{'persistence':>11s} {'octaves':>7s} {'median_deg':>10s} {'p99_deg':>8s} {'kp/Mpx':>8s}")
    for r in sep:
        print(f"{r['persistence']:11.2f} {r['octaves']:7d} {r['slope_median_deg']:10.2f} "
              f"{r['slope_p99_deg']:8.2f} {r['keypoints_per_megapixel']:8.0f}")

    print("\n== Part C: EXP-001 subset on each regime ==")
    rows = part_c_exp001_subset()
    summary = summarise_c(rows)

    print("\n  Illumination success rate by regime:")
    azs = sorted({r["delta_azimuth"] for r in rows if r["label"].startswith("d_az")})
    print("  " + f"{'regime':26s}" + "".join(f"{int(a):>7d}" for a in azs) + "   cliff")
    for regime, s in summary.items():
        cells = "".join(
            f"{s['azimuth'].get(str(a), {}).get('success_rate', float('nan')):7.2f}" for a in azs
        )
        print(f"  {regime:26s}{cells}   <= {s['last_fully_successful_delta_azimuth']}")

    print("\n  Scale success rate by regime:")
    scs = sorted({r["scale"] for r in rows if r["label"].startswith("scale")})
    print("  " + f"{'regime':26s}" + "".join(f"{a:>7.1f}" for a in scs))
    for regime, s in summary.items():
        cells = "".join(
            f"{s['scale'].get(str(a), {}).get('success_rate', float('nan')):7.2f}" for a in scs
        )
        print(f"  {regime:26s}{cells}")

    with open(OUT / "objective2_terrain_cases.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (OUT / "objective2_terrain.json").write_text(json.dumps({
        "objective": "2 - terrain realism",
        "lola_reference": LOLA_REFERENCE,
        "seeds": list(SEEDS),
        "image_shape": list(SHAPE),
        "regime_statistics": stats,
        "density_slope_separability": sep,
        "exp001_subset_summary": summary,
    }, indent=2, default=float))
    print(f"\nwritten: {OUT/'objective2_terrain.json'}, {OUT/'objective2_terrain_cases.csv'}")


if __name__ == "__main__":
    main()
