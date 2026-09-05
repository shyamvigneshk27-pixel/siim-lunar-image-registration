"""REAL-DATA-07 amendment analysis: original vs E-037-corrected rows.

Reads the recorded rows (quarter-turn orientation, rows_rd03.json /
rows_rd04.json) and the amended rows (north-up-east-right, rows_*_nue.json)
and writes ONE artefact with:

* per-pair, per-engine inlier counts before and after the correction, with the
  handedness of each frame;
* the replication edges (E2 -> A, E2 -> B) after the correction;
* per-frame success rates after the correction;
* the incidence-ceiling table: B1 success rate against the HIGHER incidence
  of the pair, 5-degree bins, after the correction (RL-042c);
* three-way engine agreement (B1, B4L, B4X) on pairs where all three passed.

Post hoc, labelled as such: this script was written after Part 2 and after the
mirror was found. It computes, it does not decide; the criteria are Part 1's
and are applied by run_real_data_07.py --evaluate.

    python scripts/analyse_real_data_07_amendment.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siim.geometry import Transform, endpoint_error  # noqa: E402

OUT = ROOT / "experiments" / "REAL-DATA-07"
SHAPE = (2048, 1024)
FRAME_A, FRAME_B, FRAME_D = "nac.m1271742202lc", "nac.m1335207975rc", "nac.m1299958135lc"
E2 = "nac.m1315225542lc"


def load(name: str) -> list[dict]:
    p = OUT / name
    if not p.exists():
        return []
    return [x for x in json.loads(p.read_text(encoding="utf-8"))["rows"] if "engine" in x]


def northup_rows(rows: list[dict]) -> dict:
    return {(x["window"], x["edge"], x["engine"]): x for x in rows if x["north_up"]}


def main() -> None:
    orig = northup_rows(load("rows_rd03.json") + load("rows_rd04.json"))
    nue_rows = load("rows_rd03_nue.json") + load("rows_rd04_nue.json")
    nue = northup_rows(nue_rows)
    if not nue:
        raise SystemExit("amended rows not on disk yet")
    # The runner records north_up as a bool (the record dict is overwritten by
    # rec.update), so the handedness is restated here from the same corner-map
    # determinant the orientation step uses (session 2026-09-05, E-037):
    # positive determinant = mirrored relative to the incumbents.
    MIRRORED = {"nac.m1315225542lc", "nac.m1199981485rc", "nac.m1142297886lc",
                "nac.m1236465772rc", "nac.m1175268993rc", "nac.m1205872034rc"}
    frames_seen = set()
    for x in nue_rows:
        frames_seen.update(x["edge"].split(" -> "))
    mirrored = {f: (f in MIRRORED) for f in frames_seen}

    # ---- per pair before / after -------------------------------------------
    pairs = []
    for (w, edge, eng), x in sorted(nue.items()):
        o = orig.get((w, edge, eng))
        s, d = edge.split(" -> ")
        pairs.append({
            "window": w, "edge": edge, "engine": eng,
            "delta_incidence_deg": x["delta_incidence_deg"],
            "max_incidence_deg": max(x["src_incidence_deg"], x["dst_incidence_deg"]),
            "src_mirrored": mirrored.get(s), "dst_mirrored": mirrored.get(d),
            "handedness_differs": (mirrored.get(s) != mirrored.get(d)),
            "before_inliers": None if o is None else o["n_inliers"],
            "before_success": None if o is None else o["success"],
            "after_inliers": x["n_inliers"], "after_success": x["success"],
            "after_wrong_pass": x["wrong_pass"],
            "after_geometry": (x["geometry"].get("verdict") or x["geometry"].get("status", ""))[:12],
        })

    # ---- replication -------------------------------------------------------
    rep = {}
    for tag, other in (("E2_vs_A", FRAME_A), ("E2_vs_B", FRAME_B), ("E2_vs_D", FRAME_D)):
        for eng in ("b1", "lg", "xf"):
            k = next((k for k in nue if k[0] == "RD04" and set(k[1].split(" -> ")) == {E2, other}
                      and k[2] == eng), None)
            if k:
                x = nue[k]
                rep[f"{tag}_{eng}"] = {"n_inliers": x["n_inliers"], "success": x["success"],
                                       "geometry": x["geometry"].get("verdict"),
                                       "delta_incidence_deg": x["delta_incidence_deg"]}

    # ---- per frame ---------------------------------------------------------
    frames: dict = {}
    for p in pairs:
        if p["engine"] != "b1":
            continue
        for f in p["edge"].split(" -> "):
            fr = frames.setdefault(f, {"pdsid": f, "mirrored": mirrored.get(f), "n": 0,
                                       "before_success": 0, "after_success": 0})
            fr["n"] += 1
            fr["before_success"] += int(bool(p["before_success"]))
            fr["after_success"] += int(bool(p["after_success"]))

    # ---- incidence ceiling (B1, after) ------------------------------------
    ceil: dict = {}
    for p in pairs:
        if p["engine"] != "b1":
            continue
        b = int(p["max_incidence_deg"] // 5 * 5)
        c = ceil.setdefault(b, {"n": 0, "success": 0, "n_small_delta": 0, "success_small_delta": 0})
        c["n"] += 1
        c["success"] += int(p["after_success"])
        if p["delta_incidence_deg"] <= 25:
            c["n_small_delta"] += 1
            c["success_small_delta"] += int(p["after_success"])
    ceiling = {str(b): {**v, "rate": v["success"] / v["n"],
                        "rate_small_delta": (v["success_small_delta"] / v["n_small_delta"]
                                             if v["n_small_delta"] else None)}
               for b, v in sorted(ceil.items())}

    # ---- three-way agreement ----------------------------------------------
    tri = []
    by_pair: dict = {}
    for (w, edge, eng), x in nue.items():
        by_pair.setdefault((w, edge), {})[eng] = x
    for (w, edge), d in by_pair.items():
        if not all(e in d and d[e].get("transform_matrix") for e in ("b1", "lg", "xf")):
            continue
        T = {e: Transform(np.array(d[e]["transform_matrix"]), "affine") for e in ("b1", "lg", "xf")}
        rec = {"window": w, "edge": edge,
               "all_success": all(d[e]["success"] for e in ("b1", "lg", "xf")),
               "success": {e: d[e]["success"] for e in ("b1", "lg", "xf")},
               "inliers": {e: d[e]["n_inliers"] for e in ("b1", "lg", "xf")}}
        for a, b in (("b1", "lg"), ("b1", "xf"), ("lg", "xf")):
            e = endpoint_error(T[a], T[b], SHAPE, step=16)
            rec[f"{a}_vs_{b}_median_px"] = e.median
        tri.append(rec)
    agree_all = [max(r["b1_vs_lg_median_px"], r["b1_vs_xf_median_px"], r["lg_vs_xf_median_px"])
                 for r in tri if r["all_success"]]
    dis = [min(r["b1_vs_lg_median_px"], r["b1_vs_xf_median_px"], r["lg_vs_xf_median_px"])
           for r in tri if not r["all_success"]]

    out = {
        "stage": "REAL-DATA-07",
        "artefact": "amendment analysis (post hoc, 2026-09-05/06): not a criterion, a tabulation",
        "orientation_before": "quarter_turn (north_up)",
        "orientation_after": "north_up_east_right (E-037)",
        "frames_mirrored": sorted(f for f, m in mirrored.items() if m),
        "frames_proper": sorted(f for f, m in mirrored.items() if not m),
        "pairs": pairs,
        "replication_after": rep,
        "frames": sorted(frames.values(), key=lambda f: f["pdsid"]),
        "incidence_ceiling_b1_after": ceiling,
        "three_way_agreement": tri,
        "three_way_summary": {
            "n_all_three_success": len(agree_all),
            "max_pairwise_disagreement_when_all_succeed_px": max(agree_all) if agree_all else None,
            "n_not_all_success_with_three_fits": len(dis),
            "min_pairwise_disagreement_when_not_all_succeed_px": min(dis) if dis else None,
        },
        "note": "Computed from artefacts; the criteria are applied by run_real_data_07.py --evaluate. "
                "Ceiling table is against the HIGHER incidence of the pair, B1, after the correction; "
                "the small-delta column restricts to delta-incidence <= 25 deg so that the ceiling is not "
                "confounded with the envelope.",
    }
    p = OUT / "real_data_07_amendment_analysis.json"
    if p.exists():
        raise SystemExit(f"{p} exists (integrity rule 4)")
    p.write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("frames_mirrored", "replication_after",
                                          "incidence_ceiling_b1_after", "three_way_summary")}, indent=1))
    for f in out["frames"]:
        print(f"  {f['pdsid']:20} mirrored={f['mirrored']!s:5} B1 success before {f['before_success']}/{f['n']}  after {f['after_success']}/{f['n']}")
    print(f"written: {p.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
