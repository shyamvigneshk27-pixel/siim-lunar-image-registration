"""EXP-007 -- DEM-conditioned correspondence on real LRO NAC edges, across a GSD ladder.

Pre-registered in ``docs/stages/EXP-007_dem_conditioned_correspondence.md``
Part 1 (commit 75fb001) BEFORE this script existed. Arms, rungs, criteria and
the reproduction gate are fixed there and are not editable in the light of
results.

    python scripts/run_exp007.py                     # everything
    python scripts/run_exp007.py --tier 1            # recorded tiles only
    python scripts/run_exp007.py --tier 2 --rungs 16,32 --arms none,dem_render_b1

WHAT IS RESTATED, NOT IMPORTED
------------------------------
``decimate`` and ``stretch`` are restated from
``scripts/rederive_recorded_registrations.py`` (decimate FIRST, stretch SECOND;
the order is load-bearing). The reproduction gate S4 then proves, from the
tile bytes, that this script's ``none`` arm is the recorded pipeline.

The discrimination-floor logic and its constants are restated from
``scripts/check_transform_against_geometry.py`` with the same values, so a
composed transform is judged against the same bound the recorded edges were.

The failure rule ``n_inliers <= 8`` (D-023) is restated as a constant and
never re-derived.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siim.baselines import learned_available, run_rootsift_baseline  # noqa: E402
from siim.evaluation.coverage import coverage_metrics  # noqa: E402
from siim.geometry import Transform, endpoint_error, estimate  # noqa: E402
from siim.ingest.footprint import FrameCorners, TileWindow, predicted_correspondences  # noqa: E402
from siim.ingest.lola_dem import load_sldem_window, local_incidence_deg  # noqa: E402
from siim.ingest.pds4 import parse_display_direction  # noqa: E402
from siim.ingest.solar_geometry import solar_geometry_at  # noqa: E402
from siim.preprocessing import PhotometricModel, normalise, render_tile_under_sun  # noqa: E402

STAGE = "EXP-007"
DATA = ROOT / "data"
EXPERIMENTS = ROOT / "experiments"
OUT = EXPERIMENTS / STAGE

#: D-023, restated. Never re-derived.
N_INLIERS_FAILURE_RULE = 8

#: Tier 1: the recorded edges, with the artefacts the ``none`` arm must reproduce.
TIER1: dict[str, tuple[str, str]] = {
    "REAL-DATA-03": ("real_triplet_geo_manifest.json",
                     "REAL-DATA-03/loop_closure_triplet.json"),
    "REAL-DATA-04": ("real_quad_d_geo_manifest.json",
                     "REAL-DATA-04/loop_closure_real_data_04.json"),
}
#: Tier 2: long windows on the same two ground points (Part 1 section 4).
TIER2: dict[str, tuple[str, list[tuple[str, str]]]] = {
    "RD03-target": ("exp007_long_triplet_abc_manifest.json",
                    [("nac.m1271742202lc", "nac.m1335207975rc"),
                     ("nac.m1335207975rc", "nac.m1452560468lc"),
                     ("nac.m1452560468lc", "nac.m1271742202lc")]),
    "RD04-target": ("exp007_long_triplet_abd_manifest.json",
                    [("nac.m1271742202lc", "nac.m1335207975rc"),
                     ("nac.m1335207975rc", "nac.m1299958135lc"),
                     ("nac.m1299958135lc", "nac.m1271742202lc")]),
}
TIER2_RUNGS = (4, 8, 16, 32)
LEARNED_RUNGS = (8, 16, 32)          # k = 4 excluded for CPU memory (Part 1 section 5)
ALL_ARMS = ("none", "photometric_ls", "photometric_hapke", "dem_render_b1",
            "dem_render_lg", "learned_lg", "photometric_ls_pixel")
#: The last arm is EXPLORATORY: per-pixel incidence from the DEM. Not in Part 1's
#: criteria; reported separately and never counted toward S1-S6.
EXPLORATORY_ARMS = ("photometric_ls_pixel",)

GEOMETRY_FILES = ["real_pair_index_geometry.json", "real_pair_index_geometry_C.json",
                  "real_frame_d_candidates_index_geometry.json",
                  "real_frame_d_selected_index_geometry.json"]

# Restated from scripts/check_transform_against_geometry.py, same values.
CORNER_QUANTISATION_DEG = 0.005
N_MONTE_CARLO = 200
MC_SEED = 20260826
GRID = 9
INCONSISTENT_MARGIN = 3.0
BILINEAR_MODEL_RESIDUAL = 0.012

FRAME_LETTER = {"nac.m1271742202lc": "A", "nac.m1335207975rc": "B",
                "nac.m1452560468lc": "C", "nac.m1299958135lc": "D"}


# --------------------------------------------------------------------------
# preprocessing (restated; decimate FIRST, stretch SECOND)
# --------------------------------------------------------------------------

def stretch(a: np.ndarray) -> np.ndarray:
    v = a[np.isfinite(a)]
    lo, hi = np.percentile(v, [1.0, 99.0])
    out = (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)
    return np.clip(np.nan_to_num(out, nan=float(np.median(out[np.isfinite(out)]))),
                   0.0, 1.0)


def decimate(a: np.ndarray, k: int) -> np.ndarray:
    if k <= 1:
        return a
    a = a[: a.shape[0] // k * k, : a.shape[1] // k * k]
    return np.nanmean(a.reshape(a.shape[0] // k, k, a.shape[1] // k, k), axis=(1, 3))


# --------------------------------------------------------------------------
# archive context per frame
# --------------------------------------------------------------------------

def load_products() -> dict:
    out: dict = {}
    for name in GEOMETRY_FILES:
        p = DATA / "manifests" / name
        if p.exists():
            out.update(json.loads(p.read_text(encoding="utf-8"))["products"])
    return out


def corners_for(pdsid: str, products: dict) -> FrameCorners:
    f = products[pdsid]["fields"]
    label = next((DATA / "metadata").rglob(f"{pdsid}.xml"), None)
    if label is None:
        raise SystemExit(f"no stored PDS4 label for {pdsid}")
    disp = parse_display_direction(label.read_text(encoding="utf-8"))
    if (disp["vertical_axis"], disp["vertical_direction"]) != ("Line", "Top to Bottom"):
        raise SystemExit(f"{pdsid}: unexpected Display_Direction {disp}")

    def c(name):
        return (float(f[name + "_LONGITUDE"]), float(f[name + "_LATITUDE"]))

    return FrameCorners(c("UPPER_LEFT"), c("UPPER_RIGHT"), c("LOWER_LEFT"),
                        c("LOWER_RIGHT"), int(f["IMAGE_LINES"]), int(f["LINE_SAMPLES"]))


class FrameContext:
    """Everything the arms need to know about one frame, from the archive."""

    def __init__(self, pdsid: str, tile: dict, products: dict, target: tuple[float, float]):
        f = products[pdsid]["fields"]
        self.pdsid = pdsid
        self.letter = FRAME_LETTER.get(pdsid, "?")
        self.tile = tile
        self.corners = corners_for(pdsid, products)
        self.sub_solar = (float(f["SUB_SOLAR_LONGITUDE"]), float(f["SUB_SOLAR_LATITUDE"]))
        self.scaled_pixel_m = 0.5 * (float(f["SCALED_PIXEL_WIDTH"])
                                     + float(f["SCALED_PIXEL_HEIGHT"]))
        self.emission_deg = float(tile.get("emission_deg", f.get("EMISSION_ANGLE")))
        self.incidence_published = float(f["INCIDENCE_ANGLE"])
        self.incidence_at_target = solar_geometry_at(target[0], target[1],
                                                     *self.sub_solar).incidence_deg
        self._raw: np.ndarray | None = None
        self._cache: dict = {}

    def window(self, k: int) -> TileWindow:
        t = self.tile
        return TileWindow(t["line0"], t["sample0"], t["n_lines"], t["n_samples"], k)

    def raw(self) -> np.ndarray:
        if self._raw is None:
            path = ROOT / self.tile["tile_npy"].replace("\\", "/")
            if not path.exists():
                raise FileNotFoundError(path)
            self._raw = np.load(path)
        return self._raw

    def dn(self, k: int) -> np.ndarray:
        key = ("dn", k)
        if key not in self._cache:
            self._cache[key] = decimate(self.raw(), k)
        return self._cache[key]

    def img(self, k: int) -> np.ndarray:
        key = ("img", k)
        if key not in self._cache:
            self._cache[key] = stretch(self.dn(k))
        return self._cache[key]

    def render(self, k: int, dem):
        key = ("render", k)
        if key not in self._cache:
            t = self.tile
            self._cache[key] = render_tile_under_sun(
                dem, self.corners, line0=t["line0"], sample0=t["sample0"],
                n_lines=t["n_lines"], n_samples=t["n_samples"], decimation=k,
                pixel_scale_m=k * self.scaled_pixel_m,
                sub_solar_lon_deg=self.sub_solar[0], sub_solar_lat_deg=self.sub_solar[1])
        return self._cache[key]

    def release(self) -> None:
        self._raw = None
        self._cache.clear()


# --------------------------------------------------------------------------
# geometry bound (restated from check_transform_against_geometry.py)
# --------------------------------------------------------------------------

def _jitter(corners: FrameCorners, rng) -> FrameCorners:
    q = CORNER_QUANTISATION_DEG

    def j(p):
        return (p[0] + rng.uniform(-q, q), p[1] + rng.uniform(-q, q))

    return FrameCorners(j(corners.upper_left), j(corners.upper_right),
                        j(corners.lower_left), j(corners.lower_right),
                        corners.lines, corners.samples)


def _predict(ca, wa, cb, wb, model="affine"):
    src, dst = predicted_correspondences(ca, wa, cb, wb, grid=GRID)
    if len(src) < 6:
        return None, len(src)
    res = estimate(src, dst, model)
    return (res.transform if res.ok else None), len(src)


def geometry_check(est: Transform | None, ca, wa, cb, wb, model="affine") -> dict:
    predicted, n_pts = _predict(ca, wa, cb, wb, model)
    out: dict = {"n_predicted_correspondences": n_pts}
    if predicted is None:
        out["status"] = "archive geometry does not constrain this edge"
        return out
    out["predicted_transform_matrix"] = np.asarray(predicted.matrix).tolist()
    if est is None:
        out["status"] = "no transform"
        return out
    err = endpoint_error(est, predicted, wa.shape, step=16)
    rng2 = np.random.default_rng(MC_SEED + 1)
    spread = []
    for _ in range(N_MONTE_CARLO):
        p_j, _ = _predict(_jitter(ca, rng2), wa, _jitter(cb, rng2), wb, model)
        if p_j is not None:
            spread.append(endpoint_error(p_j, predicted, wa.shape, step=32).median)
    quant = float(np.percentile(spread, 95)) if spread else float("nan")
    diag = float(np.hypot(*wa.shape)) / 2.0
    floor = quant + BILINEAR_MODEL_RESIDUAL * diag
    rng = np.random.default_rng(MC_SEED)
    draws = []
    for _ in range(N_MONTE_CARLO):
        p_j, _ = _predict(_jitter(ca, rng), wa, _jitter(cb, rng), wb, model)
        if p_j is not None:
            draws.append(endpoint_error(est, p_j, wa.shape, step=32).median)
    lo = float(np.percentile(draws, 5)) if draws else err.median
    if err.median <= floor:
        verdict = "CONSISTENT WITH ARCHIVE GEOMETRY"
    elif lo > INCONSISTENT_MARGIN * floor:
        verdict = "INCONSISTENT WITH ARCHIVE GEOMETRY"
    else:
        verdict = "INCONCLUSIVE"
    out.update({
        "disagreement_px": {"median": err.median, "p90": err.p90, "max": err.max},
        "disagreement_px_p5_p95": [lo, float(np.percentile(draws, 95))] if draws else None,
        "discrimination_floor_px": floor,
        "excess_over_floor": float(err.median / floor) if floor > 0 else float("inf"),
        "verdict": verdict,
        "status": "ok",
    })
    return out


# --------------------------------------------------------------------------
# one baseline result -> a flat record
# --------------------------------------------------------------------------

def summarise_result(res, shape) -> dict:
    mask = (np.asarray(res.inlier_mask, dtype=bool) if np.size(res.inlier_mask)
            else np.zeros(0, bool))
    n_in = int(mask.sum())
    n_put = int(res.matches.src_points.shape[0])
    rec = {
        "n_keypoints_src": int(len(res.src_features)),
        "n_keypoints_dst": int(len(res.dst_features)),
        "n_putative": n_put,
        "n_inliers": n_in,
        "inlier_ratio": (n_in / n_put) if n_put else 0.0,
        "fit_rmse_px": float(res.ransac.inlier_rmse),
        "fit_rmse_is_not_accuracy": True,
        "n_inliers_failure_flag": bool(n_in <= N_INLIERS_FAILURE_RULE),
        "pass": bool(n_in > N_INLIERS_FAILURE_RULE),
        "transform_matrix": (np.asarray(res.transform.matrix).tolist()
                             if res.transform is not None else None),
        "wall_s": float(res.runtime.get("total_s", float("nan"))),
    }
    if n_in >= 3:
        cov = coverage_metrics(res.matches.src_points[mask], shape)
        rec["coverage_max_uncovered_disc_ratio"] = float(cov.max_uncovered_disc_ratio)
        rec["coverage_occupancy"] = float(cov.grid_occupancy)
    return rec


def run_engine(engine: str, a: np.ndarray, b: np.ndarray, base: dict):
    if engine == "b1":
        return run_rootsift_baseline(a, b, model=base["model"],
                                     ransac_threshold=base["ransac_threshold_px"],
                                     seed=base["seed"])
    if engine == "lg":
        from siim.baselines import run_disk_lightglue_baseline
        return run_disk_lightglue_baseline(a, b, model=base["model"],
                                           ransac_threshold=base["ransac_threshold_px"],
                                           seed=base["seed"])
    if engine == "xf":
        # Added 2026-09-05 (B4X, XFeat at a pinned commit) for the REAL-DATA-07
        # third-engine column. A new branch only: the "b1" and "lg" arms that
        # produced every recorded artefact are byte-for-byte unchanged.
        from siim.baselines import run_xfeat_baseline
        return run_xfeat_baseline(a, b, model=base["model"],
                                  ransac_threshold=base["ransac_threshold_px"],
                                  seed=base["seed"])
    raise ValueError(engine)


# --------------------------------------------------------------------------
# arms
# --------------------------------------------------------------------------

def arm_direct(fs: FrameContext, fr: FrameContext, k: int, base: dict,
               engine: str, imgs: tuple[np.ndarray, np.ndarray] | None = None) -> dict:
    a, b = imgs if imgs is not None else (fs.img(k), fr.img(k))
    res = run_engine(engine, a, b, base)
    rec = summarise_result(res, a.shape)
    rec["transform"] = res.transform
    return rec


def arm_photometric(fs: FrameContext, fr: FrameContext, k: int, base: dict,
                    model: PhotometricModel) -> dict:
    imgs, notes = [], []
    for f in (fs, fr):
        corrected, valid, record = normalise(
            f.dn(k), incidence_deg=f.incidence_at_target,
            emission_deg=f.emission_deg, model=model)
        img = stretch(np.where(valid, corrected, np.nan))
        imgs.append(img)
        notes.append({"frame": f.letter, "incidence_used": f.incidence_at_target,
                      "emission_used": f.emission_deg,
                      "factor_median": record.factor_median,
                      "identical_to_none_after_stretch": bool(np.allclose(img, f.img(k))),
                      "notes": list(record.notes)})
    rec = arm_direct(fs, fr, k, base, "b1", imgs=(imgs[0], imgs[1]))
    rec["photometric"] = {"model": model.value, "frames": notes}
    return rec


def arm_photometric_pixel(fs: FrameContext, fr: FrameContext, k: int, base: dict,
                          dem) -> dict:
    imgs, notes = [], []
    for f in (fs, fr):
        r = f.render(k, dem)
        inc = local_incidence_deg(r.heights_m, r.record["sun"]["azimuth_image_deg_cw_from_up"],
                                  r.record["sun"]["elevation_deg"], k * f.scaled_pixel_m)
        dn = f.dn(k)
        h, w = min(dn.shape[0], inc.shape[0]), min(dn.shape[1], inc.shape[1])
        corrected, valid, record = normalise(
            dn[:h, :w], incidence_deg=inc[:h, :w], emission_deg=f.emission_deg,
            model=PhotometricModel.LOMMEL_SEELIGER)
        img = stretch(np.where(valid, corrected, np.nan))
        imgs.append(img)
        notes.append({"frame": f.letter, "incidence_range": [float(inc.min()), float(inc.max())],
                      "invalid_fraction": record.invalid_fraction})
    rec = arm_direct(fs, fr, k, base, "b1", imgs=(imgs[0], imgs[1]))
    rec["photometric_pixel"] = {"model": "lommel_seeliger, per-pixel incidence from SLDEM facet",
                                "frames": notes, "exploratory": True}
    return rec


def arm_dem_render(fs: FrameContext, fr: FrameContext, k: int, base: dict,
                   engine: str, dem, direct_transform: Transform | None) -> dict:
    legs = {}
    transforms = {}
    for f in (fs, fr):
        r = f.render(k, dem)
        img = f.img(k)
        h, w = min(img.shape[0], r.image.shape[0]), min(img.shape[1], r.image.shape[1])
        res = run_engine(engine, img[:h, :w], r.image[:h, :w], base)
        leg = summarise_result(res, (h, w))
        leg["render"] = r.record
        legs[f.letter] = leg
        transforms[f.letter] = res.transform
    both = all(legs[x]["pass"] for x in legs)
    rec = {
        "legs": legs,
        "pass": bool(both),
        "n_inliers": int(min(legs[x]["n_inliers"] for x in legs)),
        "n_inliers_failure_flag": not both,
        "transform": None,
        "transform_matrix": None,
    }
    if both:
        ca, cb = fs.corners, fr.corners
        wa, wb = fs.window(k), fr.window(k)
        g_sr, _ = _predict(ca, wa, cb, wb, base["model"])
        if g_sr is not None:
            t_s, t_r = transforms[fs.letter], transforms[fr.letter]
            composed = t_r.inverse() @ g_sr @ t_s
            rec["transform"] = composed
            rec["transform_matrix"] = np.asarray(composed.matrix).tolist()
            rec["composition"] = "T_SR = T_R^-1 o G_SR o T_S (legs absorb the archive offset)"
            rec["leg_translation_px"] = {
                fs.letter: [float(t_s.matrix[0, 2]), float(t_s.matrix[1, 2])],
                fr.letter: [float(t_r.matrix[0, 2]), float(t_r.matrix[1, 2])],
            }
            if direct_transform is not None:
                e = endpoint_error(composed, direct_transform, wa.shape, step=16)
                rec["agreement_with_direct_none_px"] = {
                    "median": e.median, "p90": e.p90}
    return rec


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def run_pair(tier: str, target_name: str, fs: FrameContext, fr: FrameContext, k: int,
             base: dict, arms: list[str], dem, recorded: dict | None,
             learned_ok: bool) -> list[dict]:
    edge = f"{fs.pdsid} -> {fr.pdsid}"
    label = f"{fs.letter} -> {fr.letter}"
    d_inc = abs(fs.incidence_published - fr.incidence_published)
    rows: list[dict] = []
    direct_tf = None
    common = {"tier": tier, "target": target_name, "edge": edge, "label": label,
              "decimation": k, "gsd_m": k * 0.5 * (fs.scaled_pixel_m + fr.scaled_pixel_m),
              "delta_incidence_deg": d_inc, "shape": list(fs.img(k).shape)}
    for arm in arms:
        if arm in ("learned_lg", "dem_render_lg") and not learned_ok:
            continue
        if arm == "learned_lg" and tier == "tier2" and k not in LEARNED_RUNGS:
            continue
        if arm == "dem_render_lg" and tier == "tier2" and k not in LEARNED_RUNGS:
            continue
        t0 = time.perf_counter()
        if arm == "none":
            rec = arm_direct(fs, fr, k, base, "b1")
            direct_tf = rec["transform"]
            if recorded is not None:
                rec["recorded_n_inliers"] = recorded["n_inliers"]
                rec["reproduces_recorded"] = bool(recorded["n_inliers"] == rec["n_inliers"])
                if recorded.get("transform_matrix") is not None and rec["transform_matrix"] is not None:
                    d = float(np.abs(np.asarray(recorded["transform_matrix"], float)
                                     - np.asarray(rec["transform_matrix"], float)).max())
                    rec["reproduces_recorded"] = rec["reproduces_recorded"] and d < 1e-9
        elif arm == "photometric_ls":
            rec = arm_photometric(fs, fr, k, base, PhotometricModel.LOMMEL_SEELIGER)
        elif arm == "photometric_hapke":
            rec = arm_photometric(fs, fr, k, base, PhotometricModel.HAPKE_HG)
        elif arm == "photometric_ls_pixel":
            rec = arm_photometric_pixel(fs, fr, k, base, dem)
        elif arm == "dem_render_b1":
            rec = arm_dem_render(fs, fr, k, base, "b1", dem, direct_tf)
        elif arm == "dem_render_lg":
            rec = arm_dem_render(fs, fr, k, base, "lg", dem, direct_tf)
        elif arm == "learned_lg":
            rec = arm_direct(fs, fr, k, base, "lg")
        else:
            raise ValueError(arm)
        tf = rec.pop("transform", None)
        rec["geometry"] = geometry_check(tf, fs.corners, fs.window(k), fr.corners,
                                         fr.window(k), base["model"])
        rec["arm"] = arm
        rec["exploratory"] = arm in EXPLORATORY_ARMS
        rec["arm_wall_s"] = time.perf_counter() - t0
        rec.update(common)
        rows.append(rec)
        n = rec.get("n_inliers")
        print(f"  [{tier} {target_name} k={k:2d}] {label:8s} dInc={d_inc:5.2f}  "
              f"{arm:20s} inliers={n!s:>6}  {'PASS' if rec.get('pass') else 'fail':4s}  "
              f"geom={rec['geometry'].get('verdict', rec['geometry'].get('status'))[:12]}  "
              f"({rec['arm_wall_s']:.0f}s)", flush=True)
    return rows


def evaluate(rows: list[dict]) -> dict:
    """Apply Part 1's frozen criteria S1-S6 to the rows."""
    t1 = [r for r in rows if r["tier"] == "tier1"]
    t2 = [r for r in rows if r["tier"] == "tier2"]
    failing_t1 = {(r["target"], r["edge"]) for r in t1 if r["arm"] == "none" and not r["pass"]}
    succeeding_t1 = {(r["target"], r["edge"]) for r in t1 if r["arm"] == "none" and r["pass"]}

    def count(arm, subset, tier_rows, k=None):
        return sum(1 for r in tier_rows if r["arm"] == arm and (r["target"], r["edge"]) in subset
                   and (k is None or r["decimation"] == k) and r["pass"])

    s4 = all(r.get("reproduces_recorded") for r in t1 if r["arm"] == "none") and \
        len([r for r in t1 if r["arm"] == "none"]) == 6
    failing_pairs_t2 = {frozenset(e.split(" -> ")) for (_, e) in failing_t1}
    s1_pass = set()
    for r in t2:
        if r["arm"] == "dem_render_b1" and r["pass"] and r["decimation"] in (16, 32) \
                and frozenset(r["edge"].split(" -> ")) in failing_pairs_t2:
            s1_pass.add((r["target"], r["edge"]))
    s2_conversions = count("dem_render_b1", failing_t1, t1)
    s3_hits = [r for r in t1 if r["arm"] == "learned_lg" and r["pass"]
               and (r["target"], r["edge"]) in failing_t1
               and r["geometry"].get("verdict", "").startswith("CONSISTENT")]
    s5 = all(
        r["pass"] == next(x["pass"] for x in t1 if x["arm"] == "none"
                          and x["target"] == r["target"] and x["edge"] == r["edge"])
        for r in t1 if r["arm"] in ("photometric_ls", "photometric_hapke"))
    s6_broken = [
        (r["arm"], r["target"], r["edge"], r["decimation"]) for r in rows
        if not r["exploratory"] and r["arm"] != "none" and not r["pass"]
        and any(x["arm"] == "none" and x["pass"] and x["target"] == r["target"]
                and x["edge"] == r["edge"] and x["decimation"] == r["decimation"] for x in rows)]
    transition = {}
    for r in t2:
        if r["arm"] == "dem_render_b1" and r["pass"]:
            key = f"{r['target']} {r['label']}"
            transition[key] = min(transition.get(key, 999), r["decimation"])
    return {
        "S4_reproduction_gate": {"met": bool(s4)},
        "S1_dem_render_b1_at_k16_or_k32_on_failing_pairs": {
            "n_pass": len(s1_pass), "of": len(failing_t1), "met": len(s1_pass) >= 3,
            "pairs": sorted(s1_pass)},
        "S2_no_tier1_conversion_by_dem_render_b1": {
            "conversions": s2_conversions, "met": s2_conversions == 0},
        "S3_learned_converts_a_tier1_failing_edge": {
            "n_hits": len(s3_hits), "met": len(s3_hits) >= 1,
            "edges": [(r["target"], r["edge"]) for r in s3_hits]},
        "S5_photometric_arms_change_no_tier1_outcome": {"met": bool(s5)},
        "S6_no_arm_breaks_a_succeeding_pair": {"met": not s6_broken, "broken": s6_broken},
        "rung_transition_smallest_passing_k": transition,
        "tier1_failing_edges": sorted(failing_t1),
        "tier1_succeeding_edges": sorted(succeeding_t1),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tier", choices=["1", "2", "all"], default="all")
    ap.add_argument("--rungs", default=",".join(map(str, TIER2_RUNGS)))
    ap.add_argument("--arms", default=",".join(ALL_ARMS))
    ap.add_argument("--targets", default=None, help="comma list of tier-2 targets")
    ap.add_argument("--out", default="exp007_results.json")
    ap.add_argument("--rd06-artefact", default=None,
                    help="also write REAL-DATA-06's artefact (tier-1 none/photometric rows) "
                         "under experiments/REAL-DATA-06/<name>; its stage label is "
                         "REAL-DATA-06 because that directory is where it lives (E-033)")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    out_json = OUT / args.out
    if out_json.exists():
        raise SystemExit(f"{out_json.relative_to(ROOT)} exists; choose --out (integrity rule 4)")

    arms = [a for a in args.arms.split(",") if a]
    rungs = [int(x) for x in args.rungs.split(",") if x]
    learned_ok = learned_available()
    if not learned_ok:
        print("kornia/torch unavailable: learned arms skipped")
    products = load_products()
    dem = load_sldem_window()
    print(f"DEM window {dem.heights_km.shape} lat {dem.lat_range}  ({dem.provenance['bytes_sha256'][:12]})")

    rows: list[dict] = []
    t_start = time.perf_counter()

    if args.tier in ("1", "all"):
        for stage, (man_name, art_rel) in TIER1.items():
            man = json.loads((DATA / "manifests" / man_name).read_text(encoding="utf-8"))
            rec = json.loads((EXPERIMENTS / art_rel).read_text(encoding="utf-8"))
            base = {"model": rec["baseline"]["model"],
                    "ransac_threshold_px": float(rec["baseline"]["ransac_threshold_px"]),
                    "seed": int(rec["baseline"]["seed"])}
            k = int(rec["baseline"]["downsample"])
            target = tuple(man["target_ground_point_lon_lat"])
            ctx = {t["pdsid"]: FrameContext(t["pdsid"], t, products, target) for t in man["tiles"]}
            print(f"\n=== tier 1 / {stage}: {len(rec['edges'])} recorded edges, k={k} ===")
            for e in rec["edges"]:
                s, d = e["edge"].split(" -> ")
                rows += run_pair("tier1", stage, ctx[s], ctx[d], k, base, arms, dem, e, learned_ok)
            # determinism of the learned engine, demonstrated on one edge
            if learned_ok and "learned_lg" in arms and stage == "REAL-DATA-04":
                e = rec["edges"][0]
                s, d = e["edge"].split(" -> ")
                r1 = arm_direct(ctx[s], ctx[d], k, base, "lg")
                r2 = arm_direct(ctx[s], ctx[d], k, base, "lg")
                rows.append({"tier": "tier1", "target": stage, "edge": e["edge"],
                             "label": "determinism", "arm": "learned_lg_repeat",
                             "exploratory": True, "decimation": k,
                             "n_inliers": [r1["n_inliers"], r2["n_inliers"]],
                             "pass": r1["n_inliers"] == r2["n_inliers"],
                             "geometry": {"status": "n/a"}, "delta_incidence_deg": None,
                             "gsd_m": None, "shape": None, "arm_wall_s": 0.0})
            for c in ctx.values():
                c.release()

    if args.tier in ("2", "all"):
        base = {"model": "affine", "ransac_threshold_px": 3.0, "seed": 0}
        targets = args.targets.split(",") if args.targets else list(TIER2)
        for tname in targets:
            man_name, edges = TIER2[tname]
            man_path = DATA / "manifests" / man_name
            if not man_path.exists():
                print(f"\n!! tier 2 {tname}: manifest {man_name} absent; skipped")
                continue
            man = json.loads(man_path.read_text(encoding="utf-8"))
            target = tuple(man["target_ground_point_lon_lat"])
            ctx = {t["pdsid"]: FrameContext(t["pdsid"], t, products, target) for t in man["tiles"]}
            for k in rungs:
                print(f"\n=== tier 2 / {tname}: k={k} ===")
                for s, d in edges:
                    rows += run_pair("tier2", tname, ctx[s], ctx[d], k, base, arms, dem,
                                     None, learned_ok)
                for c in ctx.values():
                    c._cache.clear()
            for c in ctx.values():
                c.release()

    verdict = evaluate(rows)
    payload = {
        "stage": STAGE,
        "preregistration": "docs/stages/EXP-007_dem_conditioned_correspondence.md Part 1 (commit 75fb001)",
        "failure_rule": f"n_inliers <= {N_INLIERS_FAILURE_RULE} (D-023), applied unchanged",
        "fit_rmse_policy": "recorded; never a criterion",
        "arms_run": arms, "tier2_rungs": rungs,
        "exploratory_arms": list(EXPLORATORY_ARMS) + ["learned_lg_repeat"],
        "dem": dem.provenance,
        "learned_engine": ("B4L DISK(depth)+LightGlue(disk) via kornia, CPU, Apache-2.0"
                           if learned_ok else "unavailable"),
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "opencv": __import__("cv2").__version__,
                        "torch": (__import__("torch").__version__ if learned_ok else None),
                        "kornia": (__import__("kornia").__version__ if learned_ok else None),
                        "platform": platform.platform()},
        "total_runtime_s": time.perf_counter() - t_start,
        "criteria": verdict,
        "rows": rows,
        "claims_not_supported": [
            "No ground truth: PASS is the pre-registered rule, not correctness.",
            "No Chandrayaan-2 data. No multimodal claim.",
            "No azimuth claim: the real edges vary in incidence, not in controlled azimuth.",
            "No sub-pixel claim.",
        ],
    }
    out_json.write_text(json.dumps(payload, indent=2, default=float), encoding="utf-8")
    flat = [{k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
             for k, v in r.items() if k not in ("legs", "geometry", "photometric",
                                                "photometric_pixel", "transform_matrix")}
            for r in rows]
    with open(OUT / args.out.replace(".json", "_rows.csv"), "w", newline="", encoding="utf-8") as fh:
        keys = sorted({k for r in flat for k in r})
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(flat)

    print("\n=== criteria (Part 1, frozen) ===")
    for k, v in verdict.items():
        print(f"  {k}: {json.dumps(v, default=str)[:160]}")
    print(f"\nwritten: {out_json.relative_to(ROOT)}   ({payload['total_runtime_s'] / 60:.1f} min)")


if __name__ == "__main__":
    main()
