"""REAL-DATA-02: does each acquired real tile pair actually share ground?

Run:  python scripts/verify_tile_overlap.py

Reads only what is already on disk -- the three REAL-DATA-01 tile manifests,
the PDS4 labels, and the archive corner geometry fetched by
``scripts/fetch_index_geometry.py``. **Fetches nothing. Reads no pixels.**

The primary result is a ground area in square kilometres, computed from named
frame corners and integer tile windows. It does not use the detector, the
descriptor, the matcher, RANSAC, the fit residual, the coverage metrics or the
verdict engine, and it would be identical if the matcher did not exist. That is
the point: REAL-DATA-01's only overlap evidence was the registration it was
trying to explain, so it could not attribute its own failure.

The registration results *are* loaded, at the end, and printed beside the
geometry as **secondary corroboration**. They are never allowed to influence
the classification -- ``classify_overlap`` is called before they are read.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from siim.ingest.footprint import (  # noqa: E402
    OVERLAP_CONFIRMED,
    FrameCorners,
    LocalPlane,
    classify_overlap,
    convex_clip,
    north_azimuth_agreement,
    north_azimuth_discriminating_power,
    overlap_metrics,
)
from siim.ingest.pds4 import parse_display_direction  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "experiments" / "REAL-DATA-02"
GEOMETRY = DATA / "manifests" / "real_pair_index_geometry.json"

# ---------------------------------------------------------------------------
# Pre-registered criteria. Fixed here, in code, before any pair is classified.
# ---------------------------------------------------------------------------

#: Shared fraction of the WORSE-COVERED tile at or above which overlap is
#: CONFIRMED, evaluated at the pessimistic end of the uncertainty interval.
#: Anchored to the only regime this project has ever measured its matcher in:
#: the synthetic transforms of ``scripts/exp002_common.py`` hold source-to-
#: target overlap at 0.757 at worst and 0.945 typically (measured over the five
#: transform classes). 0.50 sits below that floor, so confirming a pair does
#: not claim it is as easy as the synthetic case -- only that a majority of
#: each tile is shared ground, which is the condition under which a matcher
#: failure is a statement about appearance rather than about geography.
CONFIRM_AT = 0.50

#: Shared fraction below which overlap is INSUFFICIENT, evaluated at the
#: OPTIMISTIC end. Below a fifth, the shared strip is a minority of each tile
#: and far outside any regime the pipeline has been characterised in; a failure
#: there carries no information about illumination robustness.
INSUFFICIENT_BELOW = 0.20

#: Corner coordinates are published to two decimal places, so each carries a
#: rounding error in +/-0.005 deg -- about 152 m in latitude and 142 m in
#: longitude at 20 deg N. Propagated by Monte Carlo, independently per
#: coordinate, which is the standard treatment for quantisation and is stated
#: as an assumption rather than hidden.
CORNER_QUANTISATION_DEG = 0.005
N_MONTE_CARLO = 4000
MC_SEED = 20260826

#: Reported interval is the 5th to 95th percentile of the Monte Carlo draw.
MC_LOW_PCT, MC_HIGH_PCT = 5.0, 95.0

# ---------------------------------------------------------------------------
# The tile pairs to test. Each entry names the exact artefact whose numbers it
# corresponds to, so a classification can never drift away from the run it is
# about.
# ---------------------------------------------------------------------------

CASES: list[dict] = [
    {
        "case": "usable_H1",
        "role": "PRIMARY -- the REAL-DATA-01 headline pair",
        "manifest": "real_pair_usable_manifest.json",
        "registration": "registration_usable.json",
        "note": "the 3-inlier result quoted in REAL-DATA_LRO_NAC.md section 4.4",
    },
    {
        "case": "usable_H2",
        "role": "the same two products, tiles cropped under the other "
                "line-direction hypothesis",
        "manifest": "real_pair_usableH2_manifest.json",
        "registration": "registration_usableH2.json",
        "note": "row A@H2 x B@H2 of hypothesis_grid.json",
    },
    {
        "case": "terminator_H1",
        "role": "the Delta-incidence 65.3 deg pair",
        "manifest": "real_pair_terminator_manifest.json",
        "registration": "registration_terminator.json",
        "note": "one frame fails the sanity check on data quality (E-026)",
    },
]

#: The two mixed rows of ``hypothesis_grid.json``, which have no manifest of
#: their own -- they combine tiles from the two usable manifests.
MIXED_CASES: list[dict] = [
    {
        "case": "usable_A@H1_B@H2",
        "role": "hypothesis_grid.json row 2",
        "tiles": [("nac.m1271742202lc", "real_pair_usable_manifest.json"),
                  ("nac.m1335207975rc", "real_pair_usableH2_manifest.json")],
        "registration": None,
        "note": "4 inliers, fit RMSE 3.434e-13",
    },
    {
        "case": "usable_A@H2_B@H1",
        "role": "hypothesis_grid.json row 3",
        "tiles": [("nac.m1271742202lc", "real_pair_usableH2_manifest.json"),
                  ("nac.m1335207975rc", "real_pair_usable_manifest.json")],
        "registration": None,
        "note": "4 inliers, fit RMSE 3.888e-01",
    },
]


# ---------------------------------------------------------------------------


def load_manifests(cases: list[dict], mixed: list[dict]) -> dict[str, dict]:
    out = {}
    for name in sorted({c["manifest"] for c in cases}
                       | {m for c in mixed for _, m in c["tiles"]}):
        out[name] = json.loads(
            (DATA / "manifests" / name).read_text(encoding="utf-8"))
    return out


def tile_entry(manifests: dict[str, dict], manifest: str, pdsid: str) -> dict:
    for t in manifests[manifest]["tiles"]:
        if t["pdsid"] == pdsid:
            return t
    raise SystemExit(f"{pdsid} not in {manifest}")


def build_corners(geometry: dict) -> dict[str, FrameCorners]:
    """``pdsid -> FrameCorners``, with the corner naming taken from each
    product's own PDS4 label rather than from convention."""
    frames: dict[str, FrameCorners] = {}
    for pdsid, rec in geometry["products"].items():
        f = rec["fields"]
        label = (ROOT / _tile_label_path(pdsid)).read_text(encoding="utf-8")
        disp = parse_display_direction(label)
        if (disp["vertical_axis"], disp["vertical_direction"]) != (
                "Line", "Top to Bottom"):
            raise SystemExit(
                f"{pdsid}: PDS4 Display_Direction is {disp}; this script only "
                "interprets UPPER_* as line 0 when the label says Line runs "
                "Top to Bottom, and it does not guess otherwise")
        if (disp["horizontal_axis"], disp["horizontal_direction"]) != (
                "Sample", "Left to Right"):
            raise SystemExit(
                f"{pdsid}: PDS4 Display_Direction is {disp}; *_LEFT is only "
                "read as sample 0 when Sample runs Left to Right")

        def c(corner: str) -> tuple[float, float]:
            return (float(f[corner + "_LONGITUDE"]),
                    float(f[corner + "_LATITUDE"]))

        frames[pdsid] = FrameCorners(
            upper_left=c("UPPER_LEFT"), upper_right=c("UPPER_RIGHT"),
            lower_left=c("LOWER_LEFT"), lower_right=c("LOWER_RIGHT"),
            lines=int(f["IMAGE_LINES"]), samples=int(f["LINE_SAMPLES"]),
        )
    return frames


def _tile_label_path(pdsid: str) -> str:
    """The stored PDS4 label for a product, found on disk rather than tabulated.

    The corner naming is only read from a label that is actually present
    (§6.5); a missing label is refused, never defaulted to a convention.
    """
    for path in sorted((ROOT / "data" / "metadata").rglob(f"{pdsid}.xml")):
        return str(path.relative_to(ROOT)).replace("\\", "/")
    raise SystemExit(
        f"no stored PDS4 label for {pdsid} under data/metadata/; the corner "
        "naming cannot be verified for it and is not assumed")


def perturbed(corners: FrameCorners, rng: np.random.Generator) -> FrameCorners:
    """One Monte Carlo draw of the corner quantisation error."""
    def jitter(p):
        return (p[0] + rng.uniform(-CORNER_QUANTISATION_DEG,
                                   CORNER_QUANTISATION_DEG),
                p[1] + rng.uniform(-CORNER_QUANTISATION_DEG,
                                   CORNER_QUANTISATION_DEG))
    return FrameCorners(
        upper_left=jitter(corners.upper_left),
        upper_right=jitter(corners.upper_right),
        lower_left=jitter(corners.lower_left),
        lower_right=jitter(corners.lower_right),
        lines=corners.lines, samples=corners.samples,
    )


def measure(ca: FrameCorners, ta: dict, cb: FrameCorners, tb: dict):
    """Overlap of two tile windows. Returns ``(metrics, poly_a_km, poly_b_km)``."""
    pa = ca.tile_polygon(line0=ta["line0"], n_lines=ta["n_lines"],
                         sample0=ta["sample0"], n_samples=ta["n_samples"])
    pb = cb.tile_polygon(line0=tb["line0"], n_lines=tb["n_lines"],
                         sample0=tb["sample0"], n_samples=tb["n_samples"])
    plane = LocalPlane.centred_on([pa, pb])
    ka, kb = plane.to_km(pa), plane.to_km(pb)
    return overlap_metrics(ka, kb), ka, kb


def centre_separation_km(ka: np.ndarray, kb: np.ndarray) -> float:
    return float(np.hypot(*(kb.mean(axis=0) - ka.mean(axis=0))))


def analyse_case(name: str, meta: dict, frames: dict[str, FrameCorners],
                 tiles: list[tuple[str, dict]]) -> dict:
    (pid_a, ta), (pid_b, tb) = tiles
    ca, cb = frames[pid_a], frames[pid_b]

    point, ka, kb = measure(ca, ta, cb, tb)
    mirror_point, mka, mkb = measure(ca.mirrored_along_track(), ta,
                                     cb.mirrored_along_track(), tb)

    rng = np.random.default_rng(MC_SEED)
    draws = np.empty(N_MONTE_CARLO)
    for i in range(N_MONTE_CARLO):
        m, _, _ = measure(perturbed(ca, rng), ta, perturbed(cb, rng), tb)
        draws[i] = m.min_fraction
    lo = float(np.percentile(draws, MC_LOW_PCT))
    hi = float(np.percentile(draws, MC_HIGH_PCT))

    classification, reason = classify_overlap(
        lo, hi, confirm_at=CONFIRM_AT, insufficient_below=INSUFFICIENT_BELOW)

    tile_km = float(np.hypot(*(ka[1] - ka[0])))
    tile_km_along = float(np.hypot(*(ka[3] - ka[0])))

    return {
        "case": name,
        "role": meta.get("role"),
        "note": meta.get("note"),
        "products": [pid_a, pid_b],
        "tile_windows": [
            {k: t[k] for k in ("pdsid", "line0", "n_lines", "sample0",
                               "n_samples", "tile_npy", "bytes_sha256")}
            for t in (ta, tb)],
        "coordinate_system": (
            "ground: (lon, lat) degrees east-positive, from the PDS archive "
            "index table; areas in a local equirectangular plane in km, "
            "centred on the mean of the two tile rings, sphere R = 1737.4 km"),
        "primary": point.as_dict(),
        "monte_carlo": {
            "n_draws": N_MONTE_CARLO,
            "seed": MC_SEED,
            "corner_quantisation_deg": CORNER_QUANTISATION_DEG,
            "min_fraction_p5": lo,
            "min_fraction_p50": float(np.percentile(draws, 50.0)),
            "min_fraction_p95": hi,
            "min_fraction_min": float(draws.min()),
            "min_fraction_max": float(draws.max()),
        },
        "alternative_corner_reading": {
            "description": (
                "UPPER_* read as the LAST image line instead of the first, "
                "i.e. the mirror of what each product's PDS4 "
                "disp:Display_Direction states. Reported so the dependence on "
                "that reading is visible, not to endorse it."),
            **mirror_point.as_dict(),
        },
        "geometry_scale": {
            "tile_cross_track_km": tile_km,
            "tile_along_track_km": tile_km_along,
            "tile_centre_separation_km": centre_separation_km(ka, kb),
            "tile_centre_separation_km_alternative_reading":
                centre_separation_km(mka, mkb),
        },
        "classification": classification,
        "classification_reason": reason,
        "evidence_is_independent_of_matcher": True,
        "evidence_used": [
            "PDS archive index table corner coordinates (UPPER_LEFT ... "
            "LOWER_RIGHT latitude/longitude) via "
            "data/manifests/real_pair_index_geometry.json",
            "PDS4 disp:Display_Direction from each product's stored label, "
            "which states that Line runs Top to Bottom and Sample Left to "
            "Right",
            "the integer tile windows recorded in the REAL-DATA-01 manifests",
            "IMAGE_LINES / LINE_SAMPLES from the same index row",
        ],
        "assumptions": [
            "the ground coordinate of an arbitrary pixel is bilinear in "
            "(line, sample) between the four named corners -- an "
            "approximation, bounded below by the SCALED_PIXEL agreement",
            "corner coordinates carry independent uniform rounding error of "
            f"+/-{CORNER_QUANTISATION_DEG} deg",
            "a sphere of radius 1737.4 km, and a local equirectangular plane "
            "for area",
        ],
        "polygons_km": {
            "a": ka.tolist(), "b": kb.tolist(),
            "a_alternative": mka.tolist(), "b_alternative": mkb.tolist(),
        },
        "registration_artefact": meta.get("registration"),
    }


def recommended_windows(name: str, frames: dict[str, FrameCorners],
                        tiles: list[tuple[str, dict]]) -> dict:
    """What the tile windows *should* be to centre both tiles on shared ground.

    A projection, not a measurement. It computes, from the same corner
    geometry, the ``(line0, sample0)`` that would place each tile on the
    centroid of the two frames' overlapping footprint, and the ground overlap
    that would then result. Nothing is fetched and no tile is cut; this exists
    so the next stage has a concrete specification rather than an instruction
    to "select better".

    The projected overlap is what the *geometry* implies. It says nothing about
    whether those tiles would register.
    """
    (pid_a, ta), (pid_b, tb) = tiles
    ca, cb = frames[pid_a], frames[pid_b]

    fa, fb = ca.frame_polygon(), cb.frame_polygon()
    plane = LocalPlane.centred_on([fa, fb])
    shared = convex_clip(plane.to_km(fa), plane.to_km(fb))
    if len(shared) < 3:
        return {"case": name, "feasible": False,
                "reason": "the two frames' footprints do not intersect"}
    centroid_km = shared.mean(axis=0)
    k = np.pi / 180.0 * 1737.4
    target_lon = plane.lon0 + centroid_km[0] / (k * np.cos(
        np.deg2rad(plane.lat0)))
    target_lat = plane.lat0 + centroid_km[1] / k

    out_tiles = []
    for pid, t, corners in ((pid_a, ta, ca), (pid_b, tb, cb)):
        try:
            line, sample = corners.pixel_at(target_lon, target_lat)
        except ValueError as exc:
            return {"case": name, "feasible": False, "reason": str(exc)}
        # (n - 1) / 2, not n / 2: tile_polygon spans the last INCLUDED pixel.
        line0 = int(round(line - (t["n_lines"] - 1) / 2.0))
        sample0 = int(round(sample - (t["n_samples"] - 1) / 2.0))
        line0 = max(0, min(line0, corners.lines - t["n_lines"]))
        sample0 = max(0, min(sample0, corners.samples - t["n_samples"]))
        out_tiles.append({
            "pdsid": pid,
            "line0": line0, "n_lines": t["n_lines"],
            "sample0": sample0, "n_samples": t["n_samples"],
            "line0_used_in_real_data_01": t["line0"],
            "sample0_used_in_real_data_01": t["sample0"],
            "line0_delta": line0 - t["line0"],
            "sample0_delta": sample0 - t["sample0"],
        })

    wa = dict(ta, **{k2: out_tiles[0][k2]
                     for k2 in ("line0", "n_lines", "sample0", "n_samples")})
    wb = dict(tb, **{k2: out_tiles[1][k2]
                     for k2 in ("line0", "n_lines", "sample0", "n_samples")})
    projected, _, _ = measure(ca, wa, cb, wb)
    return {
        "case": name,
        "feasible": True,
        "status": ("PROJECTION from geometry only. No tile was cut and no "
                   "registration was run; this is a specification for a "
                   "future stage, not a result."),
        "target_ground_point_lon_lat": [target_lon, target_lat],
        "target_is": ("centroid of the intersection of the two frames' full "
                      "footprints"),
        "tiles": out_tiles,
        "projected_overlap": projected.as_dict(),
    }


def corner_naming_evidence(geometry: dict,
                           frames: dict[str, FrameCorners]) -> dict:
    """Everything that bears on 'is UPPER_* really line 0?', including what
    fails to bear on it."""
    per_frame = {}
    scale_ratios = []
    for pdsid, corners in frames.items():
        f = geometry["products"][pdsid]["fields"]
        plane = LocalPlane.centred_on(
            [np.array([corners.upper_left, corners.lower_right])])

        def km(p, q):
            xy = plane.to_km(np.array([p, q]))
            return float(np.hypot(*(xy[1] - xy[0])))

        along = 0.5 * (km(corners.upper_left, corners.lower_left)
                       + km(corners.upper_right, corners.lower_right))
        cross = 0.5 * (km(corners.upper_left, corners.upper_right)
                       + km(corners.lower_left, corners.lower_right))
        m_line = along * 1000.0 / corners.lines
        m_samp = cross * 1000.0 / corners.samples
        sph = float(f["SCALED_PIXEL_HEIGHT"])
        spw = float(f["SCALED_PIXEL_WIDTH"])
        res = float(f["RESOLUTION"])
        scale_ratios += [m_line / sph, m_samp / spw]
        upper_is_north = (0.5 * (corners.upper_left[1] + corners.upper_right[1])
                          > 0.5 * (corners.lower_left[1]
                                   + corners.lower_right[1]))
        per_frame[pdsid] = {
            "upper_is_northward": bool(upper_is_north),
            "line0_at_latitude": "MAX" if upper_is_north else "MIN",
            "real_data_01_hypothesis_this_corresponds_to":
                "H1" if upper_is_north else "H2",
            "orbit_node": f["ORBIT_NODE"],
            "lro_flight_direction": f["LRO_FLIGHT_DIRECTION"],
            "corner_implied_m_per_line": m_line,
            "scaled_pixel_height_m": sph,
            "ratio_vs_scaled_pixel_height": m_line / sph,
            "corner_implied_m_per_sample": m_samp,
            "scaled_pixel_width_m": spw,
            "ratio_vs_scaled_pixel_width": m_samp / spw,
            "resolution_m": res,
            "ratio_vs_resolution": m_line / res,
            "north_azimuth_check": north_azimuth_agreement(
                corners, float(f["NORTH_AZIMUTH"])),
        }

    flight = {}
    for pdsid, d in per_frame.items():
        flight.setdefault(d["lro_flight_direction"], set()).add(
            d["line0_at_latitude"])
    flight_partitions_cleanly = all(len(v) == 1 for v in flight.values()) \
        and len(flight) > 1

    power = north_azimuth_discriminating_power(
        {p: (c, float(geometry["products"][p]["fields"]["NORTH_AZIMUTH"]))
         for p, c in frames.items()})

    return {
        "question": "does UPPER_* in the index table mean image line 0?",
        "primary_evidence": (
            "Each product's own PDS4 label states disp:Display_Direction = "
            "(Line, Top to Bottom) and (Sample, Left to Right). The top row of "
            "the displayed image is therefore the first line, so UPPER_* is "
            "line 0 and *_LEFT is sample 0. This is archive documentation "
            "about the specific products, not a convention assumed from "
            "elsewhere."),
        "corroboration_pixel_scale": {
            "statement": (
                "Corner-implied pixel scale is compared against "
                "SCALED_PIXEL_HEIGHT/WIDTH, which the archive derives from "
                "SPICE and which do not depend on these corner values."),
            "n_comparisons": len(scale_ratios),
            "ratio_min": float(min(scale_ratios)),
            "ratio_max": float(max(scale_ratios)),
            "ratio_mean": float(np.mean(scale_ratios)),
        },
        "corroboration_flight_direction": {
            "statement": (
                "If UPPER_* were a compass label it would be the northern edge "
                "of every frame. It is not: the four frames split 2-2, and the "
                "split follows LRO_FLIGHT_DIRECTION exactly. A spacecraft yaw "
                "flip reverses the along-track readout direction, which is "
                "what an image-position label should track and a compass label "
                "cannot."),
            "partition": {k: sorted(v) for k, v in flight.items()},
            "partitions_cleanly": bool(flight_partitions_cleanly),
        },
        "non_corroboration_north_azimuth": {
            "statement": (
                "A NORTH_AZIMUTH cross-check was implemented and turned out to "
                "have no discriminating power for these products. Its own "
                "column description says the angle is 'relative to the RDR "
                "products' -- the map-projected derivative, which is north-up "
                "by construction -- and the measurement bears that out. It is "
                "reported and NOT used; a disagreement from a test with no "
                "power is not evidence (E-024)."),
            **power,
        },
        "per_frame": per_frame,
    }


def figure(results: list[dict], frames: dict[str, FrameCorners],
           path: Path) -> None:
    n = len(results)
    fig, axes = plt.subplots(1, n, figsize=(4.1 * n, 4.6))
    axes = np.atleast_1d(axes)
    for ax, r in zip(axes, results):
        a = np.array(r["polygons_km"]["a"])
        b = np.array(r["polygons_km"]["b"])
        ref = np.vstack([a, b]).mean(axis=0)
        for poly, colour, lab in ((a, "#2a6f4f", r["products"][0]),
                                  (b, "#a33", r["products"][1])):
            ring = np.vstack([poly, poly[:1]]) - ref
            ax.plot(ring[:, 0], ring[:, 1], color=colour, lw=1.8, label=lab)
            ax.fill(ring[:, 0], ring[:, 1], color=colour, alpha=0.18)
        ax.set_aspect("equal")
        ax.set_xlabel("east (km)")
        ax.set_ylabel("north (km)")
        mc = r["monte_carlo"]
        ax.set_title(
            f"{r['case']}\n{r['classification']}\n"
            f"shared {r['primary']['min_fraction'] * 100:.1f}% of the "
            f"worse-covered tile\n"
            f"(p5-p95 {mc['min_fraction_p5'] * 100:.1f}-"
            f"{mc['min_fraction_p95'] * 100:.1f}%)",
            fontsize=9)
        ax.legend(fontsize=7, loc="upper right")
        ax.grid(alpha=0.25, lw=0.5)
    fig.suptitle(
        "REAL-DATA-02 — tile ground footprints from PDS archive index corners. "
        "NO pixels read, NO matcher involved, NO ground-truth registration.",
        fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    print(f"figure: {path.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=None,
                    help="verify this tile manifest instead of the built-in "
                         "REAL-DATA-01/02 case list. Three or more tiles are "
                         "verified as every pairwise EDGE")
    ap.add_argument("--case", default=None, help="name for the supplied case")
    ap.add_argument("--role", default=None, help="role recorded for the case")
    ap.add_argument("--registration", default=None,
                    help="registration artefact under experiments/REAL-DATA/ "
                         "to print as SECONDARY corroboration, read only after "
                         "every classification is fixed")
    ap.add_argument("--extra-geometry", action="append", default=[],
                    help="additional index-geometry manifest name(s)")
    ap.add_argument("--out", default="overlap_verification.json",
                    help="output filename under experiments/REAL-DATA-02/")
    ap.add_argument("--figure", default="tile_overlap.png",
                    help="figure filename under the output directory")
    ap.add_argument("--outdir", default=None,
                    help="output directory under experiments/ (default "
                         "REAL-DATA-02, where this analysis originated)")
    ap.add_argument("--stage", default=None,
                    help="stage id recorded in the report. Defaults to the "
                         "output directory, so an artefact written into "
                         "experiments/REAL-DATA-04/ records REAL-DATA-04. The "
                         "2026-08-29 audit found four artefacts carrying the "
                         "stage of this script's DEFAULT rather than of the "
                         "run that produced them; the recorded files are left "
                         "as written (integrity rule 3, E-033) and this is the "
                         "fix that stops it recurring")
    ap.add_argument("--require-confirmed", action="store_true",
                    help="exit non-zero unless every case is OVERLAP_CONFIRMED. "
                         "This is the gate REAL-DATA-03 runs BEFORE it is "
                         "allowed to interpret a registration")
    args = ap.parse_args()

    global OUT
    if args.outdir:
        OUT = ROOT / "experiments" / args.outdir

    for name in (args.out, args.figure):
        if (OUT / name).exists() and name not in (
                "overlap_verification.json", "tile_overlap.png"):
            raise SystemExit(
                f"{(OUT / name).relative_to(ROOT)} already exists; choose a "
                "new name rather than overwriting an analysis artefact")

    if not GEOMETRY.exists():
        raise SystemExit(
            f"missing {GEOMETRY.relative_to(ROOT)}; run "
            "scripts/fetch_index_geometry.py first")
    geometry = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    geometry_sources = [str(GEOMETRY.relative_to(ROOT))]
    for extra in args.extra_geometry:
        path = DATA / "manifests" / extra
        if not path.exists():
            raise SystemExit(f"missing index geometry {path}")
        geometry["products"].update(
            json.loads(path.read_text(encoding="utf-8"))["products"])
        geometry_sources.append(str(path.relative_to(ROOT)))

    cases = list(CASES)
    mixed = list(MIXED_CASES)
    if args.manifest:
        # An explicit manifest replaces the built-in REAL-DATA-01/02 case list
        # rather than adding to it: those five are a fixed historical record
        # and re-deriving them on every run of a new stage would be noise.
        cases = [{
            "case": args.case or Path(args.manifest).stem,
            "role": args.role or "supplied on the command line",
            "manifest": args.manifest,
            "registration": args.registration,
            "note": "",
        }]
        mixed = []

    manifests = load_manifests(cases, mixed)
    frames = build_corners(geometry)

    print("== REAL-DATA-02: independent tile overlap verification ==\n")
    print(f"criteria fixed before classification: CONFIRMED if the pessimistic "
          f"(p{MC_LOW_PCT:.0f}) shared fraction of the worse-covered tile is "
          f">= {CONFIRM_AT:.2f};")
    print(f"INSUFFICIENT if the optimistic (p{MC_HIGH_PCT:.0f}) fraction is "
          f"< {INSUFFICIENT_BELOW:.2f}; otherwise UNKNOWN.\n")

    naming = corner_naming_evidence(geometry, frames)
    print("-- corner naming --")
    for pdsid, d in sorted(naming["per_frame"].items()):
        print(f"   {pdsid}: line 0 at {d['line0_at_latitude']} latitude "
              f"(= REAL-DATA-01 hypothesis {d['real_data_01_hypothesis_this_corresponds_to']}), "
              f"node {d['orbit_node']}, flight {d['lro_flight_direction']}, "
              f"scale ratio {d['ratio_vs_scaled_pixel_height']:.4f} / "
              f"{d['ratio_vs_scaled_pixel_width']:.4f}")
    cps = naming["corroboration_pixel_scale"]
    print(f"   pixel-scale agreement over {cps['n_comparisons']} comparisons: "
          f"{cps['ratio_min']:.4f} .. {cps['ratio_max']:.4f}")
    print(f"   flight-direction partition: "
          f"{naming['corroboration_flight_direction']['partition']} "
          f"(clean: {naming['corroboration_flight_direction']['partitions_cleanly']})")
    print(f"   NORTH_AZIMUTH check: has_power="
          f"{naming['non_corroboration_north_azimuth']['has_power']} -- "
          f"{naming['non_corroboration_north_azimuth']['reason']}\n")

    results: list[dict] = []
    projections: list[dict] = []
    for meta in cases:
        man = manifests[meta["manifest"]]
        tiles = [(t["pdsid"], t) for t in man["tiles"]]
        if len(tiles) > 2:
            # A triplet is verified as its three EDGES. A loop needs every
            # pair to share ground; three tiles that pairwise overlap only
            # around a common centre still make a valid loop, and three that
            # share a centre but not each other do not.
            for (pa, ta), (pb, tb) in itertools.combinations(tiles, 2):
                edge = f"{meta['case']}::{pa.split('.')[-1]}-{pb.split('.')[-1]}"
                results.append(analyse_case(
                    edge, {**meta, "role": f"edge of {meta['case']}",
                           "registration": None},
                    frames, [(pa, ta), (pb, tb)]))
            projections.append(recommended_windows(
                meta["case"], frames, tiles[:2]))
        else:
            results.append(analyse_case(meta["case"], meta, frames, tiles))
            projections.append(recommended_windows(meta["case"], frames, tiles))
    for meta in mixed:
        tiles = [(pid, tile_entry(manifests, m, pid))
                 for pid, m in meta["tiles"]]
        results.append(analyse_case(meta["case"], meta, frames, tiles))

    print("-- overlap --")
    for r in results:
        p, mc = r["primary"], r["monte_carlo"]
        print(f"{r['case']:20s} {r['classification']}")
        print(f"   A {p['area_a_km2']:.3f} km2   B {p['area_b_km2']:.3f} km2   "
              f"intersection {p['area_intersection_km2']:.4f} km2")
        print(f"   IoU {p['iou']:.4f}   of A {p['fraction_of_a'] * 100:.2f}%   "
              f"of B {p['fraction_of_b'] * 100:.2f}%   "
              f"min {p['min_fraction'] * 100:.2f}%")
        print(f"   p{MC_LOW_PCT:.0f}-p{MC_HIGH_PCT:.0f} of min fraction: "
              f"{mc['min_fraction_p5'] * 100:.2f}% .. "
              f"{mc['min_fraction_p95'] * 100:.2f}%")
        print(f"   tile centres {r['geometry_scale']['tile_centre_separation_km']:.3f} km "
              f"apart; tile is "
              f"{r['geometry_scale']['tile_along_track_km']:.2f} x "
              f"{r['geometry_scale']['tile_cross_track_km']:.2f} km")
        print(f"   alternative corner reading would give min "
              f"{r['alternative_corner_reading']['min_fraction'] * 100:.2f}%")
        print(f"   {r['classification_reason']}\n")

    print("-- projected windows for a geometry-driven re-selection "
          "(specification, not a measurement) --")
    for pr in projections:
        if not pr["feasible"]:
            print(f"{pr['case']:20s} not feasible: {pr['reason']}")
            continue
        po = pr["projected_overlap"]
        print(f"{pr['case']:20s} would share {po['min_fraction'] * 100:.1f}% "
              f"of the worse-covered tile (IoU {po['iou']:.3f})")
        for t in pr["tiles"]:
            print(f"   {t['pdsid']}: line0 {t['line0']} "
                  f"({t['line0_delta']:+d}), sample0 {t['sample0']} "
                  f"({t['sample0_delta']:+d})")
    print()

    # -- SECONDARY ONLY. Read after every classification is already fixed. --
    print("-- secondary corroboration (NOT used in the classification) --")
    exp = ROOT / "experiments" / "REAL-DATA"
    for r in results:
        art = r["registration_artefact"]
        if not art or not (exp / art).exists():
            r["secondary_registration"] = None
            continue
        reg = json.loads((exp / art).read_text(encoding="utf-8"))
        r["secondary_registration"] = {
            "artefact": f"experiments/REAL-DATA/{art}",
            "n_keypoints": [reg["n_keypoints_src"], reg["n_keypoints_dst"]],
            "n_putative": reg["n_putative_mutual_ratio_matches"],
            "n_inliers": reg["n_inliers"],
            "fit_rmse_px": reg["fit_rmse_px"],
            "verdict": reg["verdict"]["status"],
            "classification": reg["classification"],
            "status": ("SECONDARY CORROBORATION ONLY. Derived from the "
                       "matcher and therefore not admissible as overlap "
                       "evidence; recorded to show whether the independent "
                       "geometry and the registration outcome are consistent."),
        }
        s = r["secondary_registration"]
        print(f"   {r['case']:20s} geometry {r['classification']:22s} "
              f"registration {s['n_inliers']} inliers / {s['n_putative']} "
              f"putative, {s['verdict']}")

    OUT.mkdir(parents=True, exist_ok=True)
    shown = [r for r in results
             if r["case"] in ("usable_H1", "usable_H2", "terminator_H1")]
    if args.manifest:
        shown = results
    figure(shown, frames, OUT / args.figure)

    report = {
        "stage": args.stage or (args.outdir or "REAL-DATA-02"),
        "generated_utc": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "question": ("Do the tile pairs given to the matcher in REAL-DATA-01 "
                     "cover the same ground?"),
        "primary_evidence_is_independent_of_the_matcher": True,
        "what_was_not_used": [
            "the feature detector and descriptor",
            "putative matches, RANSAC, inlier counts, inlier ratio",
            "fit RMSE and every residual",
            "loop closure",
            "the verdict engine",
            "the decoded pixel values themselves -- no image was read",
        ],
        "preregistered_criteria": {
            "confirm_at": CONFIRM_AT,
            "insufficient_below": INSUFFICIENT_BELOW,
            "evaluated_on": ("the shared fraction of the WORSE-COVERED tile, "
                             f"at the p{MC_LOW_PCT:.0f} (confirm) and "
                             f"p{MC_HIGH_PCT:.0f} (insufficient) ends of the "
                             "Monte Carlo uncertainty interval"),
            "confirm_at_justification": (
                "The synthetic regime in which this project's matcher was "
                "measured holds source-to-target overlap at 0.757 at worst and "
                "0.945 typically (scripts/exp002_common.py). 0.50 is below "
                "that floor and is not a claim of equivalent difficulty."),
        },
        "geometry_source": {
            "manifest": "data/manifests/real_pair_index_geometry.json",
            "source": geometry["source"],
            "absent_from": geometry["geometry_absent_from"],
        },
        "corner_naming": naming,
        "cases": results,
        "projected_geometry_driven_windows": projections,
        "claims_not_supported": [
            "No ground-truth registration accuracy on real imagery.",
            "No claim that any real registration succeeded.",
            "No attribution of any registration failure to illumination: Sun "
            "AZIMUTH remains unavailable for these products from ODE and from "
            "the PDS4 labels, and the index table's SUB_SOLAR_AZIMUTH is "
            "stated to be relative to the RDR products, so it has not been "
            "used here.",
            "No Chandrayaan-2 data, no multi-modal capability, no "
            "azimuth-controlled pair.",
            "No claim that a tile whose overlap is CONFIRMED is registered: "
            "confirmed overlap means shared ground, not a known transform.",
        ],
        "licence": ("NASA PDS public domain; credit NASA/GSFC/Arizona State "
                    "University."),
    }
    report["geometry_source"]["manifests"] = geometry_sources
    (OUT / args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nreport: {(OUT / args.out).relative_to(ROOT)}")

    worst = [r["classification"] for r in results]
    if args.require_confirmed:
        bad = [r for r in results if r["classification"] != OVERLAP_CONFIRMED]
        if bad:
            print("\nSTOP: overlap is not CONFIRMED for "
                  + ", ".join(f"{r['case']} ({r['classification']})"
                              for r in bad)
                  + ".\nRegistration results from these tiles must NOT be "
                    "interpreted.")
            raise SystemExit(2)
        print(f"\nALL {len(worst)} edge(s) OVERLAP_CONFIRMED.")


if __name__ == "__main__":
    main()
