"""REAL-DATA-05 step 1: screen the archive for frame E. Metadata only.

Run:  python scripts/screen_frame_e.py --out screen_frame_e_T1.json ...

This is REAL-DATA-04's frame-D screen **plus two hard filters**, from the frozen
pre-registration in ``docs/stages/REAL-DATA-05_illumination_replication.md``
section 4.1:

* **H6** ``EMISSION_ANGLE <= --emission-max`` (default 5.0 deg). Holds relief
  displacement / parallax fixed on the decisive edge. The incumbents span
  1.17-1.75 deg.
* **H7** ``NAC_FRAME_ID == --nac-frame-id`` (default ``LEFT``). Keeps the
  decisive E<->A edge free of a camera change. A, C and D are LEFT.

and one gap in the D screen closed:

* **H5** (orientation match, D-038) is applied in the **fixed-point** tier too.
  ``screen_frame_d.screen_one`` only ever ran in amendment-1 shared-target mode,
  where ``screen_one_shared`` carries the orientation test; the fixed-point path
  ignored ``--candidate-geometry`` entirely. REAL-DATA-05's preferred tier T1 is
  a fixed point, so without this the pre-registered H5 would silently not run.

**Nothing from REAL-DATA-04 is copied.** ``screen_one`` and ``screen_one_shared``
are *imported* from ``screen_frame_d.py`` and called unchanged, so the D-stage
criteria cannot drift; this module only adds filters on top of their verdict. A
candidate rejected by an imported filter keeps the imported reason, so the
recorded ``rejected_by`` is always the first failure in evaluation order.

**This script reads no image bytes.** It costs ODE metadata queries only.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from siim.ingest.footprint import (  # noqa: E402
    FrameCorners,
    LocalPlane,
    convex_clip,
    polygon_area_km2,
    tile_admissible_polygon,
)
from siim.ingest.lro_nac import query_nac  # noqa: E402

from screen_frame_d import (  # noqa: E402
    NOMINAL_LINES,
    NOMINAL_SAMPLES,
    ODE_RING_ORDER,
    corners_from_ode_ring,
    incumbent_corners,
    orientation_signature,
    screen_one,
    screen_one_shared,
)

DATA = ROOT / "data"

#: H6 and H7 defaults, from REAL-DATA-05 section 4.1. Stated as constants so a
#: run that changed them is visible in the artefact rather than in a shell line.
DEFAULT_EMISSION_MAX_DEG = 5.0
DEFAULT_NAC_FRAME_ID = "LEFT"


def nac_frame_id_from_pdsid(pdsid: str) -> str | None:
    """``LEFT`` / ``RIGHT`` from the archive's own product-id suffix.

    LROC NAC product ids end ``lc`` or ``rc`` for the left and right cameras.
    Verified against ``NAC_FRAME_ID`` in the archive index rows of all six
    frames this project has fetched authoritative geometry for (6/6). It is
    still only a naming convention, so when authoritative index fields are
    available the derived value is **cross-checked** against them and a
    disagreement rejects the candidate rather than picking a winner.
    """
    p = pdsid.strip().lower()
    if p.endswith("lc"):
        return "LEFT"
    if p.endswith("rc"):
        return "RIGHT"
    return None


def candidate_fields(paths: list[str]) -> dict[str, dict]:
    """Raw NAMED index-table fields for candidates, keyed by pdsid."""
    out: dict[str, dict] = {}
    for name in paths:
        g = json.loads((DATA / "manifests" / name.strip())
                       .read_text(encoding="utf-8"))
        for pid, rec in g["products"].items():
            out[pid] = rec["fields"]
    return out


def apply_e_filters(row: dict, rec: dict, *, emission_max: float | None,
                    want_camera: str | None,
                    fields: dict[str, dict] | None,
                    authoritative: dict[str, FrameCorners] | None,
                    anchor_orientation: tuple[int, int] | None,
                    apply_orientation: bool) -> dict:
    """H6, H7 and (fixed-point tier only) H5, applied to an imported verdict.

    Only ever *tightens*: a row the imported screen already rejected is
    returned untouched, so no REAL-DATA-04 criterion can be loosened here.
    """
    if not row.get("admissible"):
        return row
    pdsid = row["pdsid"]
    auth = (fields or {}).get(pdsid)

    # -- H6 emission ------------------------------------------------------
    emis = None
    for source, key in ((auth, "EMISSION_ANGLE"), (rec, "Emission_angle")):
        if source is not None and source.get(key) not in (None, ""):
            try:
                emis = float(source[key])
                row["emission_source"] = ("index table, NAMED column"
                                          if source is auth else "ODE summary")
                break
            except (TypeError, ValueError):
                continue
    row["emission_deg_used"] = emis
    if emission_max is not None:
        if emis is None:
            row["admissible"] = False
            row["rejected_by"] = "filter H6: no emission angle published"
            return row
        if emis > emission_max:
            row["admissible"] = False
            row["rejected_by"] = (
                f"filter H6: emission {emis:.2f} > {emission_max} deg; an "
                "off-nadir frame introduces relief displacement / parallax on "
                "the decisive edge (REAL-DATA-05 D-042)")
            return row

    # -- H7 camera --------------------------------------------------------
    derived = nac_frame_id_from_pdsid(pdsid)
    declared = (auth or {}).get("NAC_FRAME_ID")
    declared = declared.strip().upper() if isinstance(declared, str) else None
    row["nac_frame_id_from_pdsid"] = derived
    row["nac_frame_id_declared"] = declared
    if declared is not None and derived is not None and declared != derived:
        row["admissible"] = False
        row["rejected_by"] = (
            f"filter H7: product id implies {derived} but the index table "
            f"declares {declared}; the camera cannot be established")
        return row
    camera = declared or derived
    row["nac_frame_id_used"] = camera
    if want_camera is not None:
        if camera is None:
            row["admissible"] = False
            row["rejected_by"] = "filter H7: NAC camera could not be determined"
            return row
        if camera != want_camera:
            row["admissible"] = False
            row["rejected_by"] = (
                f"filter H7: NAC camera {camera} != required {want_camera}; "
                "the decisive E<->A edge must not also change camera "
                "(REAL-DATA-05 D-043)")
            return row

    # -- H5 orientation, fixed-point tier only ----------------------------
    if apply_orientation and anchor_orientation is not None:
        if authoritative is None or pdsid not in authoritative:
            row["admissible"] = False
            row["rejected_by"] = (
                "filter H5: no authoritative named corners supplied for this "
                "candidate, so its orientation cannot be verified and is not "
                "assumed")
            return row
        sig = orientation_signature(authoritative[pdsid])
        row["orientation_signature"] = list(sig)
        row["corner_source"] = "PDS archive index table, NAMED columns"
        if sig != anchor_orientation:
            row["admissible"] = False
            row["rejected_by"] = (
                f"filter H5: frame orientation {sig} does not match the "
                f"incumbents' {anchor_orientation}; its tile would be rotated "
                "180 deg relative to A and B, entangling this stage with "
                "EXP-004's open orientation-assignment question (D-038)")
            return row
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="REAL-DATA-05",
                    help="stage id recorded in the artefact")
    ap.add_argument("--incumbent-manifest", default="real_quad_d_geo_manifest.json",
                    help="manifest whose tiles are the incumbent frames")
    ap.add_argument("--target-lonlat", default=None,
                    help="lon,lat; default: the incumbent manifest's target")
    ap.add_argument("--minlat", type=float, default=18.5)
    ap.add_argument("--maxlat", type=float, default=21.5)
    ap.add_argument("--westernlon", type=float, default=21.5)
    ap.add_argument("--easternlon", type=float, default=22.6)
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--lines", type=int, default=4096)
    ap.add_argument("--samples", type=int, default=2048)
    ap.add_argument("--frame-lines", type=int, default=NOMINAL_LINES)
    ap.add_argument("--frame-samples", type=int, default=NOMINAL_SAMPLES)
    ap.add_argument("--incidence-max", type=float, default=75.0,
                    help="D-029 hard ceiling")
    ap.add_argument("--incidence-band", default="18.22,30.91",
                    help="pre-registered band for frame E (D-041). Changing "
                         "this changes the experiment")
    ap.add_argument("--emission-max", type=float,
                    default=DEFAULT_EMISSION_MAX_DEG,
                    help="H6 (D-042). Pass a large value to disable")
    ap.add_argument("--nac-frame-id", default=DEFAULT_NAC_FRAME_ID,
                    help="H7 (D-043): required NAC camera, LEFT or RIGHT. "
                         "Pass ANY to disable")
    ap.add_argument("--shared-target", action="store_true",
                    help="tier T2: derive the target as the centroid of the "
                         "anchors' shared tile-admissible region")
    ap.add_argument("--incumbent-geometry",
                    default="real_pair_index_geometry.json",
                    help="index-geometry manifest(s), comma separated, giving "
                         "the incumbents' AUTHORITATIVE named corners")
    ap.add_argument("--incumbent-frames", default=None,
                    help="comma-separated incumbent pdsids to anchor on")
    ap.add_argument("--candidate-geometry", default=None,
                    help="index-geometry manifest(s) giving CANDIDATES' "
                         "authoritative named corners; enables H5")
    ap.add_argument("--out", required=True,
                    help="output manifest name under data/manifests/")
    args = ap.parse_args()

    out_path = DATA / "manifests" / args.out
    if out_path.exists():
        raise SystemExit(f"{out_path.relative_to(ROOT)} already exists; choose "
                         "a new name (integrity rule 4)")

    want_camera = (None if args.nac_frame_id.strip().upper() == "ANY"
                   else args.nac_frame_id.strip().upper())
    emission_max = args.emission_max

    man = json.loads((DATA / "manifests" / args.incumbent_manifest)
                     .read_text(encoding="utf-8"))
    incumbents = {t["pdsid"]: float(t["ode_map_resolution_m"]) for t in man["tiles"]}
    inc_by_pdsid = {t["pdsid"]: float(t["incidence_deg"]) for t in man["tiles"]}
    inc_a = min(inc_by_pdsid.values())
    pdsid_a = min(inc_by_pdsid, key=inc_by_pdsid.get)
    if args.target_lonlat:
        lon, lat = (float(x) for x in args.target_lonlat.split(","))
    else:
        lon, lat = man["target_ground_point_lon_lat"]
    band = tuple(float(x) for x in args.incidence_band.split(","))

    print(f"== {args.stage} step 1: screening for frame E (METADATA ONLY) ==\n")
    print("incumbents      : " + ", ".join(
        f"{p} ({inc_by_pdsid[p]:.2f} deg, {incumbents[p]:.3f} m)"
        for p in incumbents))
    print(f"A (lowest inc)  : {pdsid_a} at {inc_a:.2f} deg")
    print(f"tier            : {'T2 shared-target' if args.shared_target else 'T1 fixed point'}")
    print(f"target point    : {lon:.12f}, {lat:.12f}")
    print(f"tile            : {args.lines} x {args.samples}")
    print(f"incidence band  : [{band[0]}, {band[1]}] deg   ceiling "
          f"{args.incidence_max} deg")
    print(f"H6 emission max : {emission_max} deg")
    print(f"H7 NAC camera   : {want_camera or 'ANY'}")
    print(f"ODE box         : lat [{args.minlat}, {args.maxlat}]  lon "
          f"[{args.westernlon}, {args.easternlon}]  limit {args.limit}\n")

    prods = query_nac(min_lat=args.minlat, max_lat=args.maxlat,
                      min_lon=args.westernlon, max_lon=args.easternlon,
                      limit=args.limit)
    print(f"ODE returned {len(prods)} CDR products\n")

    incumbent_polys: list = []
    anchors: list[str] = []
    anchor_orientation: tuple[int, int] | None = None
    authoritative: dict[str, FrameCorners] | None = None
    fields: dict[str, dict] | None = None

    anchor_names = ([x.strip() for x in args.incumbent_frames.split(",")]
                    if args.incumbent_frames else list(incumbents))
    anchor_corners = incumbent_corners(args.incumbent_geometry.split(","),
                                       anchor_names)
    anchor_sigs = {p: orientation_signature(anchor_corners[p])
                   for p in anchor_names}
    if len(set(anchor_sigs.values())) != 1:
        raise SystemExit(
            f"the anchor frames disagree on orientation ({anchor_sigs}); "
            "there is no single orientation for a candidate to match")
    anchor_orientation = next(iter(anchor_sigs.values()))
    print(f"anchors         : {', '.join(anchor_names)}")
    print(f"anchor orientation signature: {anchor_orientation} "
          "(along-track, cross-track)\n")

    if args.shared_target:
        anchors = anchor_names
        incumbent_polys = [
            tile_admissible_polygon(anchor_corners[p], n_lines=args.lines,
                                    n_samples=args.samples) for p in anchors]
        plane = LocalPlane.centred_on(incumbent_polys)
        shared = plane.to_km(incumbent_polys[0])
        for poly in incumbent_polys[1:]:
            shared = convex_clip(shared, plane.to_km(poly))
            if len(shared) < 3:
                raise SystemExit(
                    "the incumbent frames share no tile-admissible ground")
        print(f"T2: incumbent shared tile-admissible region "
              f"{polygon_area_km2(shared):.3f} km2\n")

    if args.candidate_geometry:
        paths = args.candidate_geometry.split(",")
        fields = candidate_fields(paths)
        authoritative = incumbent_corners(paths, sorted(fields))
        print(f"authoritative corners supplied for {len(authoritative)} "
              "candidate(s); hard filter H5 (orientation match) is ACTIVE\n")

    rows = []
    for p in prods:
        if args.shared_target:
            row = screen_one_shared(
                p.raw, incumbent_polys=incumbent_polys, n_lines=args.lines,
                n_samples=args.samples, inc_max=args.incidence_max,
                inc_band=band, incumbents=incumbents, inc_a=inc_a,
                lines=args.frame_lines, samples=args.frame_samples,
                authoritative=authoritative,
                anchor_orientation=(anchor_orientation
                                    if authoritative else None))
            apply_orientation = False
        else:
            row = screen_one(
                p.raw, target=(lon, lat), n_lines=args.lines,
                n_samples=args.samples, inc_max=args.incidence_max,
                inc_band=band, incumbents=incumbents, inc_a=inc_a,
                lines=args.frame_lines, samples=args.frame_samples)
            apply_orientation = authoritative is not None
        row = apply_e_filters(
            row, p.raw, emission_max=emission_max, want_camera=want_camera,
            fields=fields, authoritative=authoritative,
            anchor_orientation=anchor_orientation,
            apply_orientation=apply_orientation)
        if row["admissible"]:
            row["d_incidence_vs_incumbents"] = {
                k: abs(row["incidence_deg"] - v)
                for k, v in inc_by_pdsid.items()}
        rows.append(row)

    admissible = [r for r in rows if r["admissible"]]
    admissible.sort(key=lambda r: (r["max_resolution_ratio"],
                                   r["abs_d_incidence_vs_A"]))

    funnel: dict[str, int] = {}
    for r in rows:
        key = "ADMISSIBLE" if r["admissible"] else r["rejected_by"].split(":")[0]
        funnel[key] = funnel.get(key, 0) + 1
    print("screening funnel")
    for k in sorted(funnel):
        print(f"   {k:<14} {funnel[k]}")

    print(f"\n{len(admissible)} admissible candidate(s), ranked by the "
          "deciding criterion (max resolution ratio):\n")
    if not admissible:
        print("   NONE. Per the pre-registration, widen the search SPATIALLY "
              "or move to the next target tier; do NOT relax a criterion.")
    for i, r in enumerate(admissible):
        d = r["d_incidence_vs_incumbents"]
        print(f"   {i + 1}. {r['pdsid']}  incidence {r['incidence_deg']:.2f} "
              f"deg  emission {r.get('emission_deg_used')}  "
              f"camera {r.get('nac_frame_id_used')}  "
              f"res {r['map_resolution_m']:.3f} m  "
              f"max ratio {r['max_resolution_ratio']:.4f}")
        print("      d_incidence: " + "  ".join(
            f"{k[-8:]} {v:.2f}" for k, v in d.items()))
        if "implied_target_lon_lat" in r:
            t = r["implied_target_lon_lat"]
            print(f"      shared tile-admissible "
                  f"{r['shared_tile_admissible_km2']:.3f} km2  implied target "
                  f"({t[0]:.6f}, {t[1]:.6f})")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "stage": args.stage,
        "step": "1 - candidate screening for frame E",
        "data_read": "ODE product METADATA ONLY. No image bytes were fetched.",
        "criteria_source": (
            "docs/stages/REAL-DATA-05_illumination_replication.md section 4.1, "
            "frozen before this ran"),
        "screen_provenance": (
            "screen_one / screen_one_shared are IMPORTED unchanged from "
            "scripts/screen_frame_d.py; this script only ADDS H5 (fixed-point "
            "tier), H6 and H7 on top of their verdict and can never loosen a "
            "REAL-DATA-04 criterion."),
        "criteria": {
            "tier": "T2 shared-target" if args.shared_target else "T1 fixed point",
            "H2_target_lon_lat": None if args.shared_target else [lon, lat],
            "H2_shared_tile_admissible_anchors": anchors if args.shared_target else None,
            "H3_full_tile_fits_unclamped": [args.lines, args.samples],
            "H4_incidence_band_deg": list(band),
            "H4_incidence_max_deg": args.incidence_max,
            "H5_orientation_signature_required": (
                list(anchor_orientation) if authoritative else None),
            "H6_emission_max_deg": emission_max,
            "H7_nac_frame_id_required": want_camera,
            "H8_not_an_incumbent": sorted(incumbents),
            "deciding": "minimise the maximum Map_resolution ratio vs A, B, D",
            "tie_break": "smaller |incidence - incidence_A|",
        },
        "ode_query": {
            "product_type": "CDRNAC4", "minlat": args.minlat,
            "maxlat": args.maxlat, "westernlon": args.westernlon,
            "easternlon": args.easternlon, "limit": args.limit,
            "n_returned": len(prods),
        },
        "frame_size_assumption": {
            "lines": args.frame_lines, "samples": args.frame_samples,
            "note": ("Nominal NAC CDR dimensions are used to RANK candidates "
                     "only; the winner's true dimensions come from the archive "
                     "index table before acquisition, and acquire_real_pair.py "
                     "refuses to clamp a window."),
        },
        "footprint_vertex_order_assumption": {
            "order": list(ODE_RING_ORDER),
            "note": ("ODE's ring order is undocumented (REAL-DATA-02 section "
                     "6.3). Used ONLY to rank candidates."),
        },
        "incumbents": {p: {"incidence_deg": inc_by_pdsid[p],
                           "map_resolution_m": incumbents[p]}
                       for p in incumbents},
        "funnel": funnel,
        "n_admissible": len(admissible),
        "ranked_admissible": admissible,
        "selected": admissible[0]["pdsid"] if admissible else None,
        "all_candidates": rows,
        "licence": ("NASA PDS public domain; credit NASA/GSFC/Arizona State "
                    "University."),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2), encoding="utf-8")
    print(f"\nwritten: {out_path.relative_to(ROOT)}")
    if admissible:
        print(f"SELECTED frame E: {admissible[0]['pdsid']}")
    else:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
