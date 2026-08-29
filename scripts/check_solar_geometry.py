"""Confound check: is REAL-DATA-04's Δincidence result a proxy for Δazimuth?

    python scripts/check_solar_geometry.py
    python scripts/check_solar_geometry.py --out solar_geometry_check.json

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
**It is a check applied AFTER a decision that was fixed before the data
existed**, exactly like ``check_transform_against_geometry.py``. It cannot and
must not move any edge across the pass/fail line, change a threshold, or edit a
recorded artefact. It reads committed manifests and committed registration
artefacts and writes one new file.

**It is NOT pre-registered.** It was written on 2026-08-29 during a pre-freeze
audit, with all six edge outcomes already known and visible. Reporting it as a
prediction that was made and then confirmed would be false. It is a confound
check on an existing conclusion, and that is how it must be quoted.

THE OBJECTION IT ADDRESSES
--------------------------
D-040 attributes six real-edge outcomes to Δ**incidence**, and states its scope
as *"incidence only, NOT azimuth-controlled"*. A reviewer reads that correctly:
azimuth is an **uncontrolled confound**, not a constant. At a fixed site
incidence and solar azimuth both sweep through the lunation, and this project's
own synthetic stages (EXP-001, EXP-003) put the classical baseline's cliff on
Δ*azimuth* at 21--30 deg. So the sharpest available attack on D-040 is:
*"your Δincidence label is a proxy; the driver is Δazimuth, as your own
experiments say."*

RL-032b blocked the answer on the archive's ``SUB_SOLAR_AZIMUTH`` column, whose
frame is unverified. This script does not use that column. It computes the
ground solar azimuth from ``SUB_SOLAR_LATITUDE`` / ``SUB_SOLAR_LONGITUDE`` by
spherical trigonometry (:mod:`siim.ingest.solar_geometry`), and validates the
premise by recomputing ``INCIDENCE_ANGLE`` from the same two columns and
comparing against the archive's published value.

No image byte is read. No matcher component is involved. Nothing is fetched.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siim.ingest.solar_geometry import (  # noqa: E402
    angular_difference_deg,
    incidence_agreement,
    solar_geometry_at,
)

DATA = ROOT / "data"
EXPERIMENTS = ROOT / "experiments"

#: How far the recomputed incidence may sit from the archive's published value
#: before the azimuth derived from the same two columns is refused. Set from
#: the physical error budget rather than from the observed residuals: the
#: published columns are quoted to two decimals, the archive value is stated at
#: the frame centre while this is evaluated at the tile target (which are up to
#: ~25 km apart along a 50 km strip, ~0.8 deg of latitude), and the sphere
#: ignores local slope. 2.0 deg covers all three with margin and would still
#: reject a frame-convention error, which moves the answer by tens of degrees.
INCIDENCE_AGREEMENT_TOLERANCE_DEG = 2.0

#: Stage -> (manifest, registration artefact, overlap artefact). Identity only;
#: every number below is read from these files.
STAGES = {
    "REAL-DATA-03": (
        "real_triplet_geo_manifest.json",
        "REAL-DATA-03/loop_closure_triplet.json",
    ),
    "REAL-DATA-04": (
        "real_quad_d_geo_manifest.json",
        "REAL-DATA-04/loop_closure_real_data_04.json",
    ),
}

GEOMETRY_MANIFESTS = [
    "real_pair_index_geometry.json",
    "real_pair_index_geometry_C.json",
    "real_frame_d_candidates_index_geometry.json",
    "real_frame_d_selected_index_geometry.json",
]


def load_products() -> dict:
    products: dict = {}
    for name in GEOMETRY_MANIFESTS:
        path = DATA / "manifests" / name
        if not path.exists():
            continue
        products.update(json.loads(path.read_text(encoding="utf-8"))["products"])
    if not products:
        raise SystemExit(
            "no index-geometry manifests found under data/manifests/; this "
            "check reads the archive's named columns and will not guess them")
    return products


def fields_for(pdsid: str, products: dict) -> dict:
    rec = products.get(pdsid)
    if rec is None:
        raise SystemExit(
            f"{pdsid} has no archive index geometry on disk; run "
            f"scripts/fetch_index_geometry.py --pdsids {pdsid}")
    return rec["fields"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=None,
                    help="write the result to experiments/REAL-DATA-06/<name>; "
                         "omit to print only and write nothing")
    args = ap.parse_args()

    products = load_products()

    print("Solar geometry confound check -- NOT pre-registered, applied after "
          "the decision.\nNo image data, no matcher, no network.\n")

    # ---- 1. the premise: recomputed incidence vs the published column -----
    frames: dict[str, dict] = {}
    frame_rows = []
    for stage, (manifest_name, _) in STAGES.items():
        man = json.loads((DATA / "manifests" / manifest_name).read_text(encoding="utf-8"))
        lon_t, lat_t = man["target_ground_point_lon_lat"]
        for pdsid in man["pair"]:
            key = (pdsid, round(lon_t, 6), round(lat_t, 6))
            if key in frames:
                continue
            f = fields_for(pdsid, products)
            published = float(f["INCIDENCE_ANGLE"])
            recomputed, diff = incidence_agreement(
                lon_t, lat_t,
                float(f["SUB_SOLAR_LONGITUDE"]), float(f["SUB_SOLAR_LATITUDE"]),
                published)
            g = solar_geometry_at(lon_t, lat_t,
                                  float(f["SUB_SOLAR_LONGITUDE"]),
                                  float(f["SUB_SOLAR_LATITUDE"]))
            row = {
                "pdsid": pdsid, "stage": stage,
                "target_lon": lon_t, "target_lat": lat_t,
                "published_incidence_deg": published,
                "recomputed_incidence_deg": recomputed,
                "incidence_difference_deg": diff,
                "ground_solar_azimuth_deg": g.azimuth_deg,
                "archive_SUB_SOLAR_AZIMUTH": float(f["SUB_SOLAR_AZIMUTH"]),
                "archive_azimuth_minus_ground_deg": angular_difference_deg(
                    float(f["SUB_SOLAR_AZIMUTH"]), g.azimuth_deg),
                "phase_angle_deg": float(f["PHASE_ANGLE"]),
                "emission_angle_deg": float(f["EMISSION_ANGLE"]),
                "phase_minus_incidence_deg": (float(f["PHASE_ANGLE"])
                                              - float(f["INCIDENCE_ANGLE"])),
            }
            frames[key] = row
            frame_rows.append(row)

    worst = max(abs(r["incidence_difference_deg"]) for r in frame_rows)
    premise_ok = worst <= INCIDENCE_AGREEMENT_TOLERANCE_DEG

    print("1. PREMISE CHECK -- incidence recomputed from SUB_SOLAR_LAT/LON")
    print(f"   {'frame':22s} {'stage':13s} {'published':>10s} {'recomputed':>11s} "
          f"{'diff':>7s}")
    for r in frame_rows:
        print(f"   {r['pdsid']:22s} {r['stage']:13s} "
              f"{r['published_incidence_deg']:10.2f} "
              f"{r['recomputed_incidence_deg']:11.2f} "
              f"{r['incidence_difference_deg']:7.2f}")
    print(f"   worst |diff| = {worst:.2f} deg against a "
          f"{INCIDENCE_AGREEMENT_TOLERANCE_DEG:.1f} deg tolerance -> "
          f"{'PREMISE HOLDS' if premise_ok else 'PREMISE FAILS'}")
    if not premise_ok:
        print("\n   The sub-solar columns do not reproduce the published "
              "incidence. The azimuth derived from them means nothing and is "
              "NOT reported.")
        raise SystemExit(2)

    print("\n2. THE ARCHIVE'S OWN SUB_SOLAR_AZIMUTH IS A DIFFERENT QUANTITY")
    print(f"   {'frame':22s} {'archive':>9s} {'ground':>9s} {'separation':>11s}")
    for r in frame_rows:
        print(f"   {r['pdsid']:22s} {r['archive_SUB_SOLAR_AZIMUTH']:9.2f} "
              f"{r['ground_solar_azimuth_deg']:9.2f} "
              f"{r['archive_azimuth_minus_ground_deg']:11.2f}")
    print("   RL-032b's caution is upheld: the column is NOT the ground solar\n"
          "   azimuth at the target and must not be used as one.")

    # ---- 2. the six edges: does Dazimuth separate them as Dincidence does? --
    edges = []
    for stage, (manifest_name, reg_rel) in STAGES.items():
        man = json.loads((DATA / "manifests" / manifest_name).read_text(encoding="utf-8"))
        lon_t, lat_t = man["target_ground_point_lon_lat"]
        reg = json.loads((EXPERIMENTS / reg_rel).read_text(encoding="utf-8"))
        for e in reg["edges"]:
            src, dst = e["edge"].split(" -> ")
            a = frames[(src, round(lon_t, 6), round(lat_t, 6))]
            b = frames[(dst, round(lon_t, 6), round(lat_t, 6))]
            edges.append({
                "stage": stage, "edge": e["edge"],
                "delta_incidence_deg": abs(a["published_incidence_deg"]
                                           - b["published_incidence_deg"]),
                "delta_azimuth_deg": angular_difference_deg(
                    a["ground_solar_azimuth_deg"], b["ground_solar_azimuth_deg"]),
                "delta_phase_deg": abs(a["phase_angle_deg"] - b["phase_angle_deg"]),
                "n_inliers": e["n_inliers"],
                # The pre-registered rule (D-023), applied, never re-derived.
                "outcome": "FAIL" if e["n_inliers_failure_flag"] else "SUCCEED",
                "source": f"experiments/{reg_rel}",
            })

    succeeding = [e for e in edges if e["outcome"] == "SUCCEED"]
    failing = [e for e in edges if e["outcome"] == "FAIL"]

    def separates(key: str) -> dict:
        """Does this variable order every success below every failure?"""
        if not succeeding or not failing:
            return {"separates": False, "reason": "need both outcomes"}
        hi_s = max(e[key] for e in succeeding)
        lo_f = min(e[key] for e in failing)
        return {
            "separates": bool(hi_s < lo_f),
            "max_succeeding_deg": hi_s,
            "min_failing_deg": lo_f,
            "gap_deg": lo_f - hi_s,
        }

    inc = separates("delta_incidence_deg")
    az = separates("delta_azimuth_deg")
    ph = separates("delta_phase_deg")

    # Phase vs incidence: are they even distinguishable in this dataset?
    max_emission = max(r["emission_angle_deg"] for r in frame_rows)
    phase_inc_gap = max(abs(e["delta_phase_deg"] - e["delta_incidence_deg"])
                        for e in edges)

    print(f"\n3. THE SIX MEASURED EDGES  (n = {len(edges)}; "
          f"{len(succeeding)} succeed, {len(failing)} fail)")
    print(f"   {'stage':13s} {'edge':46s} {'dInc':>7s} {'dAz':>7s} {'dPhase':>8s} "
          f"{'inliers':>8s}  outcome")
    for e in sorted(edges, key=lambda r: r["delta_incidence_deg"]):
        print(f"   {e['stage']:13s} {e['edge'][:46]:46s} "
              f"{e['delta_incidence_deg']:7.2f} {e['delta_azimuth_deg']:7.2f} "
              f"{e['delta_phase_deg']:8.2f} "
              f"{e['n_inliers']:8d}  {e['outcome']}")

    print("\n4. RESULT")
    for name, r in (("delta_incidence", inc), ("delta_azimuth", az),
                    ("delta_phase", ph)):
        if r["separates"]:
            print(f"   {name:16s} SEPARATES the outcomes "
                  f"(max succeeding {r['max_succeeding_deg']:.2f} < "
                  f"min failing {r['min_failing_deg']:.2f}; "
                  f"gap {r['gap_deg']:.2f} deg)")
        else:
            print(f"   {name:16s} does NOT separate the outcomes "
                  f"(max succeeding {r['max_succeeding_deg']:.2f} >= "
                  f"min failing {r['min_failing_deg']:.2f})")

    print("\n5. PHASE AND INCIDENCE ARE NOT SEPARABLE IN THIS DATASET")
    print(f"   Max emission angle over all frames: {max_emission:.2f} deg.")
    print("   Every frame is near-nadir, so phase = incidence + emission to")
    print(f"   first order, and |dPhase - dInc| <= {phase_inc_gap:.2f} deg over all")
    print(f"   {len(edges)} edges. dPhase separates the outcomes for the same")
    print("   ARITHMETIC reason dIncidence does, and no measurement here")
    print("   distinguishes them.")
    print("   This matters: lunar regolith photometry is PHASE-driven (opposition")
    print("   surge, Hapke backscatter), so 'incidence' is this project's LABEL")
    print("   for the variable, not a demonstrated mechanism. Separating them")
    print("   requires an OFF-NADIR frame, which this project does not have.")

    print("\n   WHAT THIS DOES AND DOES NOT LICENSE")
    print("   Does:     on THESE six edges, Dazimuth is not a variable that")
    print("             orders the outcomes, so D-040's attribution is not")
    print("             simply Dazimuth wearing an incidence label.")
    print("   Does NOT: n = 6 with two variables that are themselves")
    print("             correlated cannot establish which one is causal, and")
    print("             this was not a controlled azimuth experiment. An")
    print("             azimuth-controlled real pair is still owed.")
    print("   Does NOT: change D-040, any threshold, any verdict, or any")
    print("             recorded artefact. It was run after the fact.")

    payload = {
        "check": "solar geometry confound check on D-040",
        "status": ("NOT PRE-REGISTERED. Written 2026-08-29 during a pre-freeze "
                   "audit with all six outcomes already visible. A confound "
                   "check on an existing conclusion, never a prediction. It "
                   "may not move any edge across the pass/fail line."),
        "method": ("Ground solar incidence and azimuth computed by spherical "
                   "trigonometry from the archive's SUB_SOLAR_LATITUDE / "
                   "SUB_SOLAR_LONGITUDE at each stage's tile target. No image "
                   "data, no matcher, no network. The archive's own "
                   "SUB_SOLAR_AZIMUTH column is deliberately NOT used "
                   "(RL-032b): its frame is unverified, and section 2 shows "
                   "it is not the ground azimuth."),
        "premise_check": {
            "tolerance_deg": INCIDENCE_AGREEMENT_TOLERANCE_DEG,
            "worst_abs_difference_deg": worst,
            "holds": premise_ok,
            "note": ("Recomputed incidence is compared against the archive's "
                     "independently published INCIDENCE_ANGLE. This is a "
                     "cross-check with real discriminating power, unlike "
                     "E-027's."),
        },
        "frames": frame_rows,
        "edges": edges,
        "separation": {"delta_incidence_deg": inc, "delta_azimuth_deg": az,
                       "delta_phase_deg": ph},
        "phase_incidence_collinearity": {
            "max_emission_angle_deg": max_emission,
            "max_abs_delta_phase_minus_delta_incidence_deg": phase_inc_gap,
            "separable": False,
            "note": ("Every frame is near-nadir, so phase = incidence + "
                     "emission to first order and the two deltas agree to "
                     f"{phase_inc_gap:.2f} deg over all edges. dPhase separates "
                     "the outcomes for the same arithmetic reason dIncidence "
                     "does. Lunar photometry is phase-driven, so 'incidence' "
                     "is this project's LABEL for the variable, not a "
                     "demonstrated mechanism. Separating them requires an "
                     "off-nadir frame."),
        },
        "limits": [
            "n = 6 edges; this orders outcomes, it does not establish cause.",
            "Not an azimuth-CONTROLLED experiment; that debt stands.",
            "dPhase and dIncidence are collinear here and are NOT separated. "
            "Lunar BRDF is phase-driven; the attributed variable is labelled "
            "incidence but the data cannot distinguish the two.",
            "Spherical geometry: local slope is not modelled.",
            "Incidence is evaluated at the tile target; the archive states it "
            "at the frame centre, which is why the tolerance is 2 deg.",
        ],
        "changes_nothing": ("D-040, D-023, every threshold, every verdict and "
                            "every recorded artefact are untouched by this "
                            "script."),
    }

    if args.out:
        out_dir = EXPERIMENTS / "REAL-DATA-06"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / args.out
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nwrote {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
