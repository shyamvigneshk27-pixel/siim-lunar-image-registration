"""REAL-DATA-07 -- replication, illumination envelope and significance on every
archived frame over the two recorded windows, with tiles rotated north-up from
archive geometry.

    python scripts/run_real_data_07.py --window RD03 --overlap overlap_rd03.json
    python scripts/run_real_data_07.py --window RD04 --overlap overlap_rd04.json
    python scripts/run_real_data_07.py --evaluate   # pool the per-window artefacts

Pre-registered in ``docs/stages/REAL-DATA-07_replication_and_envelope.md``
Part 1 (commit f8a961c). Engines: B1 (unmodified) and B4L (DISK + LightGlue,
unmodified). Rule ``n_inliers <= 8`` (D-023). Every pass is checked against the
archive-geometry floor; a pass whose transform is INCONSISTENT is a WRONG PASS
and never counts as success.

Shared machinery (stretch, decimate, FrameContext, geometry_check,
summarise_result) is imported from ``scripts/run_exp007.py`` so the two stages
judge transforms by one code path.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import itertools
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siim.baselines import learned_available  # noqa: E402
from siim.evaluation.significance import exact_separation_test  # noqa: E402
from siim.geometry import Transform  # noqa: E402
from siim.ingest.orientation import north_up  # noqa: E402

_spec = importlib.util.spec_from_file_location("_exp007", ROOT / "scripts" / "run_exp007.py")
_e7 = importlib.util.module_from_spec(_spec)
sys.modules["_exp007"] = _e7
_spec.loader.exec_module(_e7)

STAGE = "REAL-DATA-07"
DATA = ROOT / "data"
OUT = ROOT / "experiments" / STAGE
N_INLIERS_FAILURE_RULE = _e7.N_INLIERS_FAILURE_RULE
GEOMETRY_FILES = _e7.GEOMETRY_FILES + ["real_data_07_index_geometry.json"]

WINDOWS = {"RD03": "real_data_07_rd03_manifest.json",
           "RD04": "real_data_07_rd04_manifest.json"}
RECORDED = {"RD03": "REAL-DATA-03/loop_closure_triplet.json",
            "RD04": "REAL-DATA-04/loop_closure_real_data_04.json"}
BASE = {"model": "affine", "ransac_threshold_px": 3.0, "seed": 0}
FRAME_A, FRAME_B = "nac.m1271742202lc", "nac.m1335207975rc"
REPLICATION = ("nac.m124423514lc", "nac.m1315225542lc")


def load_products() -> dict:
    out: dict = {}
    for name in GEOMETRY_FILES:
        p = DATA / "manifests" / name
        if p.exists():
            out.update(json.loads(p.read_text(encoding="utf-8"))["products"])
    return out


def confirmed_pairs(overlap_path: Path) -> set[frozenset]:
    doc = json.loads(overlap_path.read_text(encoding="utf-8"))
    return {frozenset(c["products"]) for c in doc["cases"]
            if c["classification"] == "OVERLAP_CONFIRMED"}


def run_edge(fs, fr, engine: str, rotate: bool) -> dict:
    ks, kr = fs.tile.get("decimation", 2), fr.tile.get("decimation", 2)
    a, b = fs.img(ks), fr.img(kr)
    ra = rb = None
    if rotate:
        ta, tb = fs.tile, fr.tile
        ra = north_up(a, fs.corners, line=ta["line0"] + (ta["n_lines"] - 1) / 2,
                      sample=ta["sample0"] + (ta["n_samples"] - 1) / 2)
        rb = north_up(b, fr.corners, line=tb["line0"] + (tb["n_lines"] - 1) / 2,
                      sample=tb["sample0"] + (tb["n_samples"] - 1) / 2)
        a, b = ra.image, rb.image
    res = _e7.run_engine(engine, a, b, BASE)
    rec = _e7.summarise_result(res, a.shape)
    tf = res.transform
    if tf is not None and rotate:
        # back to ORIGINAL tile pixels: T_orig = R_dst^-1 o T_rot o R_src
        tf = rb.inverse @ tf @ ra.forward
        rec["transform_matrix_original_pixels"] = np.asarray(tf.matrix).tolist()
        rec["north_up"] = {"src": ra.record, "dst": rb.record}
    rec["geometry"] = _e7.geometry_check(tf, fs.corners, fs.window(ks), fr.corners,
                                         fr.window(kr), BASE["model"])
    g = rec["geometry"].get("verdict", "")
    rec["wrong_pass"] = bool(rec["pass"] and g.startswith("INCONSISTENT"))
    rec["success"] = bool(rec["pass"] and not rec["wrong_pass"])
    return rec


def run_window(window: str, overlap_name: str, engines: list[str]) -> list[dict]:
    man = json.loads((DATA / "manifests" / WINDOWS[window]).read_text(encoding="utf-8"))
    target = tuple(man["target_ground_point_lon_lat"])
    products = load_products()
    ctx = {t["pdsid"]: _e7.FrameContext(t["pdsid"], t, products, target) for t in man["tiles"]}
    confirmed = confirmed_pairs(OUT / overlap_name)
    recorded = {e["edge"]: e for e in json.loads(
        (ROOT / "experiments" / RECORDED[window]).read_text(encoding="utf-8"))["edges"]}

    frames = sorted(ctx, key=lambda p: ctx[p].incidence_published)
    rows: list[dict] = []
    seen_orbits: set[str] = set()
    for s, d in itertools.combinations(frames, 2):
        if frozenset((s, d)) not in confirmed:
            rows.append({"window": window, "edge": f"{s} -> {d}", "excluded": "overlap not CONFIRMED"})
            continue
        fs, fr = ctx[s], ctx[d]
        d_inc = abs(fs.incidence_published - fr.incidence_published)
        same_orbit = s[:-2] == d[:-2]
        for engine in engines:
            for rotate in ((False, True) if engine == "b1" else (True,)):
                edge = f"{s} -> {d}"
                rec_key = edge if edge in recorded else f"{d} -> {s}"
                if not rotate and rec_key not in recorded:
                    continue          # raw B1 only on the six recorded edges (S4, S6)
                t0 = time.perf_counter()
                rec = run_edge(fs, fr, engine, rotate)
                rec.update({"window": window, "edge": edge, "engine": engine,
                            "north_up": bool(rotate), "delta_incidence_deg": d_inc,
                            "same_orbit_pair": same_orbit,
                            "src_incidence_deg": fs.incidence_published,
                            "dst_incidence_deg": fr.incidence_published,
                            "wall_s": time.perf_counter() - t0})
                if rec_key in recorded and not rotate:
                    rec["recorded_n_inliers"] = recorded[rec_key]["n_inliers"]
                    rec["reproduces_recorded"] = (rec_key == edge and
                                                  recorded[rec_key]["n_inliers"] == rec["n_inliers"])
                rows.append(rec)
                print(f"  [{window}] {edge[4:16]}->{edge[-13:]} dInc={d_inc:5.2f} {engine:3s} "
                      f"{'NU' if rotate else 'raw'}  inl={rec['n_inliers']:5d} "
                      f"{'SUCCESS' if rec['success'] else ('WRONG-PASS' if rec['wrong_pass'] else 'fail')}"
                      f"  ({rec['wall_s']:.0f}s)", flush=True)
        for c in (fs, fr):
            pass
    for c in ctx.values():
        c.release()
    return rows


def envelope(rows: list[dict]) -> dict:
    bins: dict[int, list[bool]] = {}
    for r in rows:
        if r.get("same_orbit_pair"):
            continue
        b = int(r["delta_incidence_deg"] // 5 * 5)
        bins.setdefault(b, []).append(r["success"])
    table = {str(b): {"n": len(v), "success_rate": float(np.mean(v))} for b, v in sorted(bins.items())}
    ok = [b for b, v in sorted(bins.items()) if np.mean(v) >= 0.8]
    largest_ok = max(ok) if ok else None
    return {"bins_5deg": table, "largest_bin_with_success_rate_ge_0_8": largest_ok}


def significance(rows: list[dict]) -> dict:
    rows = [r for r in rows if not r.get("same_orbit_pair")]
    if len({r["success"] for r in rows}) < 2:
        return {"p_value": None, "note": "one outcome class only"}
    t = exact_separation_test([r["delta_incidence_deg"] for r in rows],
                              [r["success"] for r in rows])
    return {"n_edges": len(rows), "n_success": sum(r["success"] for r in rows),
            "statistic": t.statistic, "p_value": t.p_value, "exact": t.exact,
            "perfectly_separated": t.perfectly_separated}


def evaluate(all_rows: list[dict]) -> dict:
    rows = [r for r in all_rows if "engine" in r]
    b1_raw = [r for r in rows if r["engine"] == "b1" and not r["north_up"]]
    s4 = all(r.get("reproduces_recorded", True) for r in b1_raw) and len(b1_raw) >= 6
    # S6: north-up must not change the six recorded outcomes
    changed = []
    for r in b1_raw:
        nu = next((x for x in rows if x["engine"] == "b1" and x["north_up"]
                   and x["window"] == r["window"] and x["edge"] == r["edge"]), None)
        if nu is not None and nu["pass"] != r["pass"]:
            changed.append(r["edge"])
    # S1: replication
    rep = []
    for e in REPLICATION:
        vs_a = next((x for x in rows if x["engine"] == "b1" and x["north_up"] and x["window"] == "RD04"
                     and set(x["edge"].split(" -> ")) == {e, FRAME_A}), None)
        vs_b = next((x for x in rows if x["engine"] == "b1" and x["north_up"] and x["window"] == "RD04"
                     and set(x["edge"].split(" -> ")) == {e, FRAME_B}), None)
        if vs_a and vs_b:
            rep.append({"frame": e, "vs_A_success": vs_a["success"],
                        "vs_A_geometry": vs_a["geometry"].get("verdict"),
                        "vs_B_pass": vs_b["pass"],
                        "replicates": bool(vs_a["success"] and not vs_b["pass"])})
    out: dict = {"S4_reproduction_gate": {"met": bool(s4)},
                 "S1_replication": {"met": any(x["replicates"] for x in rep), "detail": rep},
                 "S6_north_up_changes_no_recorded_outcome": {"met": not changed, "changed": changed}}
    for eng in ("b1", "lg"):
        sub = [r for r in rows if r["engine"] == eng and r["north_up"]]
        out[f"envelope_{eng}"] = {"pooled": envelope(sub),
                                  **{w: envelope([r for r in sub if r["window"] == w]) for w in WINDOWS}}
        out[f"significance_{eng}"] = {"pooled": significance(sub),
                                      **{w: significance([r for r in sub if r["window"] == w]) for w in WINDOWS}}
        out[f"wrong_pass_rate_{eng}"] = {
            "n_pass": sum(r["pass"] for r in sub), "n_wrong_pass": sum(r["wrong_pass"] for r in sub)}
    e_b1 = out["envelope_b1"]["pooled"]["largest_bin_with_success_rate_ge_0_8"]
    e_lg = out["envelope_lg"]["pooled"]["largest_bin_with_success_rate_ge_0_8"]
    above39 = [v["success_rate"] for b, v in out["envelope_b1"]["pooled"]["bins_5deg"].items() if int(b) >= 40]
    out["S2_b1_envelope"] = {"met": bool(e_b1 is not None and e_b1 < 39 and all(x <= 0.2 for x in above39)),
                             "largest_ok_bin": e_b1}
    out["S3_lg_envelope_exceeds_b1_by_15deg"] = {
        "met": bool(e_b1 is not None and e_lg is not None and e_lg - e_b1 >= 15), "b1": e_b1, "lg": e_lg}
    p_pool = out["significance_b1"]["pooled"].get("p_value")
    p_win = [out["significance_b1"][w].get("p_value") for w in WINDOWS]
    out["S5_significance_b1"] = {"met": bool(p_pool is not None and p_pool <= 0.01
                                             and all(p is not None and p <= 0.05 for p in p_win)),
                                 "pooled_p": p_pool, "per_window_p": p_win}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--window", choices=sorted(WINDOWS))
    ap.add_argument("--overlap", default=None, help="overlap artefact name under experiments/REAL-DATA-07/")
    ap.add_argument("--engines", default="b1,lg")
    ap.add_argument("--evaluate", action="store_true", help="pool rd03/rd04 row artefacts and apply criteria")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    if args.evaluate:
        rows = []
        for w in WINDOWS:
            p = OUT / f"rows_{w.lower()}.json"
            if p.exists():
                rows += json.loads(p.read_text(encoding="utf-8"))["rows"]
        verdict = evaluate(rows)
        out = OUT / (args.out or "real_data_07_results.json")
        if out.exists():
            raise SystemExit(f"{out.relative_to(ROOT)} exists (integrity rule 4)")
        out.write_text(json.dumps({"stage": STAGE, "preregistration":
                                   "docs/stages/REAL-DATA-07_replication_and_envelope.md Part 1 (commit f8a961c)",
                                   "failure_rule": f"n_inliers <= {N_INLIERS_FAILURE_RULE} (D-023)",
                                   "criteria": verdict, "n_rows": len(rows)}, indent=2, default=float),
                       encoding="utf-8")
        print(json.dumps(verdict, indent=1, default=str)[:4000])
        print(f"written: {out.relative_to(ROOT)}")
        return

    if not (args.window and args.overlap):
        raise SystemExit("--window and --overlap are required unless --evaluate")
    engines = [e for e in args.engines.split(",") if e]
    if "lg" in engines and not learned_available():
        raise SystemExit("B4L unavailable: install kornia/torch")
    out = OUT / (args.out or f"rows_{args.window.lower()}.json")
    if out.exists():
        raise SystemExit(f"{out.relative_to(ROOT)} exists (integrity rule 4)")
    t0 = time.perf_counter()
    rows = run_window(args.window, args.overlap, engines)
    out.write_text(json.dumps({
        "stage": STAGE, "window": args.window, "engines": engines,
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "opencv": __import__("cv2").__version__, "platform": platform.platform()},
        "total_runtime_s": time.perf_counter() - t0, "rows": rows}, indent=2, default=float),
        encoding="utf-8")
    flat = [{k: v for k, v in r.items() if k not in ("geometry", "north_up", "transform_matrix",
                                                      "transform_matrix_original_pixels")}
            for r in rows if "engine" in r]
    if flat:
        with open(out.with_suffix(".csv"), "w", newline="", encoding="utf-8") as fh:
            keys = sorted({k for r in flat for k in r})
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(flat)
    print(f"written: {out.relative_to(ROOT)}  ({(time.perf_counter() - t0) / 60:.1f} min)")


if __name__ == "__main__":
    main()
