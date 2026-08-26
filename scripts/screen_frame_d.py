"""REAL-DATA-04 step 1: screen the archive for frame D. Metadata only.

Run:  python scripts/screen_frame_d.py --out screen_frame_d.json

Why a script rather than an inline query
---------------------------------------
REAL-DATA-03's third-image screening was two ``python -c`` one-liners. They
worked, but they are not re-runnable, the candidate table in the report cannot
be regenerated, and the selection criteria live only in prose. REAL-DATA-04's
choice of frame is the entire experiment -- if D is picked badly the decision
table means nothing -- so the criteria are executed here, from the frozen
pre-registration in ``docs/stages/REAL-DATA-04_illumination_vs_frame_identity.md``
section 3, and every candidate considered is written to the artefact including
the ones that were rejected and why.

**This script reads no image bytes.** It costs one ODE metadata query. It also
makes no claim: the ODE footprint ring's vertex order is *undocumented*
(REAL-DATA-02 section 6.3), so the ring is used **only to rank candidates**, and
the winner's geometry is then re-fetched from the authoritative named index
columns by ``scripts/fetch_index_geometry.py`` before anything is acquired.

The hard filters, in the order a candidate is tested against them:

1. footprint parses to four distinct vertices;
2. the target ground point is inside the frame;
3. a full ``--lines x --samples`` tile centred on it fits inside, unclamped;
4. ``incidence <= 75`` (D-029);
5. ``incidence`` inside the pre-registered low band (D-037), default
   ``[9.95, 39.95]`` -- this stage's design requirement;
6. not one of the incumbent frames A, B, C.

Deciding criterion among survivors: **minimise the maximum ``Map_resolution``
ratio against the incumbents**. Tie-break: smaller ``|incidence - incidence_A|``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siim.ingest.footprint import (  # noqa: E402
    MOON_RADIUS_KM,
    FrameCorners,
    LocalPlane,
    convex_clip,
    polygon_area_km2,
    tile_admissible_polygon,
)
from siim.ingest.lro_nac import parse_footprint, query_nac  # noqa: E402

DATA = ROOT / "data"

#: The ODE ring order REAL-DATA-02 decoded from four products, section 6.3:
#: (UR, LR, LL, UL). An INFERENCE, used here only to rank candidates and never
#: to make a claim -- the winner is re-fetched from the named index columns.
ODE_RING_ORDER = ("upper_right", "lower_right", "lower_left", "upper_left")

#: Nominal NAC CDR frame size. ODE does not publish IMAGE_LINES / LINE_SAMPLES
#: in the product summary, and all four REAL-DATA-03 frames are 52224 x 5064.
#: A screening approximation, replaced by the authoritative index values before
#: acquisition. Frames shorter than nominal are screened optimistically, so the
#: fit test is re-run for real in acquire_real_pair.py, which refuses to clamp.
NOMINAL_LINES = 52224
NOMINAL_SAMPLES = 5064


def corners_from_ode_ring(rec: dict, lines: int, samples: int
                          ) -> FrameCorners | None:
    """FrameCorners from the ODE WKT ring, or None if it is not four vertices."""
    pts = parse_footprint(rec.get("Footprint_geometry"))
    if pts and len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) != 4 or len(set(pts)) != 4:
        return None
    kw = {name: pts[i] for i, name in enumerate(ODE_RING_ORDER)}
    try:
        return FrameCorners(lines=lines, samples=samples, **kw)
    except ValueError:
        return None


def screen_one(rec: dict, *, target: tuple[float, float], n_lines: int,
               n_samples: int, inc_max: float, inc_band: tuple[float, float],
               incumbents: dict[str, float], inc_a: float,
               lines: int, samples: int) -> dict:
    """Every filter, applied in order, with the first failure recorded."""
    pdsid = str(rec.get("pdsid") or "")
    try:
        inc = float(rec.get("Incidence_angle"))
    except (TypeError, ValueError):
        inc = None
    try:
        res_m = float(rec.get("Map_resolution"))
    except (TypeError, ValueError):
        res_m = None
    out: dict = {
        "pdsid": pdsid,
        "incidence_deg": inc,
        "emission_deg": rec.get("Emission_angle"),
        "map_resolution_m": res_m,
        "utc_start": rec.get("UTC_start_time"),
        "admissible": False,
        "rejected_by": None,
    }

    corners = corners_from_ode_ring(rec, lines, samples)
    if corners is None:
        out["rejected_by"] = "filter 1: footprint is not four distinct vertices"
        return out

    try:
        line, sample = corners.pixel_at(*target)
    except ValueError as exc:
        out["rejected_by"] = f"filter 2: target not inside the frame ({exc})"
        return out
    out["target_pixel_line"] = line
    out["target_pixel_sample"] = sample

    want_l = int(round(line - (n_lines - 1) / 2.0))
    want_s = int(round(sample - (n_samples - 1) / 2.0))
    fits = (0 <= want_l <= lines - n_lines) and (0 <= want_s <= samples - n_samples)
    out["unclamped_line0"], out["unclamped_sample0"] = want_l, want_s
    out["full_tile_fits_unclamped"] = bool(fits)
    if not fits:
        out["rejected_by"] = (
            f"filter 3: a {n_lines}x{n_samples} tile centred on the target "
            f"would start at line {want_l}, sample {want_s} and run off a "
            f"{lines}x{samples} frame")
        return out

    if inc is None:
        out["rejected_by"] = "filter 4: no incidence angle published"
        return out
    if inc > inc_max:
        out["rejected_by"] = f"filter 4: incidence {inc:.2f} > {inc_max} (D-029)"
        return out

    lo, hi = inc_band
    if not (lo <= inc <= hi):
        out["rejected_by"] = (
            f"filter 5: incidence {inc:.2f} outside the pre-registered low "
            f"band [{lo}, {hi}] (D-037)")
        return out

    if pdsid in incumbents:
        out["rejected_by"] = f"filter 6: {pdsid} is an incumbent frame"
        return out

    if res_m is None or res_m <= 0:
        out["rejected_by"] = "deciding criterion: no Map_resolution published"
        return out

    ratios = {k: max(res_m, v) / min(res_m, v) for k, v in incumbents.items()}
    out["resolution_ratio_vs"] = {k: round(v, 6) for k, v in ratios.items()}
    out["max_resolution_ratio"] = float(max(ratios.values()))
    out["d_incidence_vs_incumbents"] = {
        k: None for k in incumbents}   # filled by caller, which knows incidences
    out["abs_d_incidence_vs_A"] = abs(inc - inc_a)
    out["admissible"] = True
    return out


def incumbent_corners(geometry_paths: list[str], pdsids: list[str]
                      ) -> dict[str, FrameCorners]:
    """Authoritative FrameCorners for the incumbent frames.

    From the NAMED index columns, not from the ODE ring: the incumbents anchor
    the amended target point, so their geometry must be the archive's own
    rather than the inference used to rank candidates.
    """
    fields: dict[str, dict] = {}
    for name in geometry_paths:
        g = json.loads((DATA / "manifests" / name.strip())
                       .read_text(encoding="utf-8"))
        for pid, rec in g["products"].items():
            fields[pid] = rec["fields"]
    out = {}
    for pid in pdsids:
        if pid not in fields:
            raise SystemExit(f"{pid} is not in the supplied index geometry")
        f = fields[pid]

        def c(corner: str, f=f) -> tuple[float, float]:
            return (float(f[corner + "_LONGITUDE"]),
                    float(f[corner + "_LATITUDE"]))

        out[pid] = FrameCorners(
            upper_left=c("UPPER_LEFT"), upper_right=c("UPPER_RIGHT"),
            lower_left=c("LOWER_LEFT"), lower_right=c("LOWER_RIGHT"),
            lines=int(f["IMAGE_LINES"]), samples=int(f["LINE_SAMPLES"]))
    return out


def screen_one_shared(rec: dict, *, incumbent_polys: list, n_lines: int,
                      n_samples: int, inc_max: float,
                      inc_band: tuple[float, float],
                      incumbents: dict[str, float], inc_a: float,
                      lines: int, samples: int,
                      authoritative: dict | None = None,
                      anchor_orientation: tuple[int, int] | None = None) -> dict:
    """Amended hard filter 1 (REAL-DATA-04 amendment 1).

    Instead of "does this frame contain THE target point", the test is "does
    this frame share any ground with the incumbents on which all of them can
    centre a full tile". The target point is then the centroid of that shared
    region, so it is derived from the chosen frame rather than fixed in
    advance -- which is D-033's rule, applied to the tile-admissible region.
    """
    pdsid = str(rec.get("pdsid") or "")
    try:
        inc = float(rec.get("Incidence_angle"))
    except (TypeError, ValueError):
        inc = None
    try:
        res_m = float(rec.get("Map_resolution"))
    except (TypeError, ValueError):
        res_m = None
    out: dict = {
        "pdsid": pdsid, "incidence_deg": inc,
        "emission_deg": rec.get("Emission_angle"),
        "map_resolution_m": res_m, "utc_start": rec.get("UTC_start_time"),
        "admissible": False, "rejected_by": None,
    }

    if inc is None:
        out["rejected_by"] = "filter 4: no incidence angle published"
        return out
    if inc > inc_max:
        out["rejected_by"] = f"filter 4: incidence {inc:.2f} > {inc_max} (D-029)"
        return out
    lo, hi = inc_band
    if not (lo <= inc <= hi):
        out["rejected_by"] = (
            f"filter 5: incidence {inc:.2f} outside the pre-registered low "
            f"band [{lo}, {hi}] (D-037)")
        return out
    if pdsid in incumbents:
        out["rejected_by"] = f"filter 6: {pdsid} is an incumbent frame"
        return out

    if authoritative is not None and pdsid in authoritative:
        corners = authoritative[pdsid]
        out["corner_source"] = "PDS archive index table, NAMED columns"
    else:
        corners = corners_from_ode_ring(rec, lines, samples)
        out["corner_source"] = ("ODE footprint ring, inferred vertex order "
                                "(ranking only)")
    if corners is None:
        out["rejected_by"] = "filter 1a: footprint is not four distinct vertices"
        return out
    out["frame_lines_samples"] = [corners.lines, corners.samples]
    if anchor_orientation is not None:
        sig = orientation_signature(corners)
        out["orientation_signature"] = list(sig)
        if sig != anchor_orientation:
            out["rejected_by"] = (
                f"filter 1c: frame orientation {sig} does not match the "
                f"incumbents' {anchor_orientation}; its tile would be rotated "
                "180 deg relative to A and B, entangling this stage with "
                "EXP-004's open orientation-assignment question")
            return out
    try:
        poly_d = tile_admissible_polygon(corners, n_lines=n_lines,
                                         n_samples=n_samples)
    except ValueError as exc:
        out["rejected_by"] = f"filter 1a: {exc}"
        return out

    polys = incumbent_polys + [poly_d]
    plane = LocalPlane.centred_on(polys)
    shared = plane.to_km(polys[0])
    for poly in polys[1:]:
        shared = convex_clip(shared, plane.to_km(poly))
        if len(shared) < 3:
            out["rejected_by"] = (
                "filter 1b: no ground on which the incumbents AND this frame "
                f"can all centre a full {n_lines}x{n_samples} tile")
            return out
    area = polygon_area_km2(shared)
    if area <= 0.0:
        out["rejected_by"] = "filter 1b: shared tile-admissible region has zero area"
        return out
    centroid = shared.mean(axis=0)
    k = math.pi / 180.0 * MOON_RADIUS_KM
    lon = plane.lon0 + centroid[0] / (k * math.cos(math.radians(plane.lat0)))
    lat = plane.lat0 + centroid[1] / k
    out["shared_tile_admissible_km2"] = float(area)
    out["implied_target_lon_lat"] = [float(lon), float(lat)]

    if res_m is None or res_m <= 0:
        out["rejected_by"] = "deciding criterion: no Map_resolution published"
        return out
    ratios = {k2: max(res_m, v) / min(res_m, v) for k2, v in incumbents.items()}
    out["resolution_ratio_vs"] = {k2: round(v, 6) for k2, v in ratios.items()}
    out["max_resolution_ratio"] = float(max(ratios.values()))
    out["abs_d_incidence_vs_A"] = abs(inc - inc_a)
    out["admissible"] = True
    return out


def orientation_signature(c: FrameCorners) -> tuple[int, int]:
    """``(along_track, cross_track)`` sense of a frame, as two signs.

    ``along_track`` is +1 when latitude INCREASES from the ``UPPER_*`` row to
    the ``LOWER_*`` row (line 0 at minimum latitude), −1 when it decreases.
    ``cross_track`` is +1 when longitude increases from ``*_LEFT`` to
    ``*_RIGHT``.

    Why this is a hard filter and not a footnote. Two frames with opposite
    signatures image the same ground 180 degrees apart, so their tiles are
    rotated 180 degrees with respect to one another. RootSIFT is rotation
    invariant *by design*, but whether its orientation assignment actually
    holds up is this project's own open question -- EXP-004, pre-registered and
    deliberately not started. Putting a 180-degree rotation on REAL-DATA-04's
    decisive edge would entangle the causal question with that open one: a
    failure could then be illumination, frame identity, or orientation
    assignment, and the stage exists precisely to separate causes.

    Computed from the archive's NAMED corner columns, so it is a statement
    about the columns. Whether a frame is genuinely rotated on the ground or
    its columns are labelled differently, the consequence for a tile cut from
    it is the same, and either way it is not comparable with the incumbents.
    """
    along = 1 if (0.5 * (c.lower_left[1] + c.lower_right[1])
                  > 0.5 * (c.upper_left[1] + c.upper_right[1])) else -1
    cross = 1 if (0.5 * (c.upper_right[0] + c.lower_right[0])
                  > 0.5 * (c.upper_left[0] + c.lower_left[0])) else -1
    return along, cross


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--incumbent-manifest", default="real_triplet_geo_manifest.json",
                    help="manifest whose tiles are the incumbent frames A, B, C")
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
    ap.add_argument("--incidence-band", default="9.95,39.95",
                    help="pre-registered low-incidence band for frame D "
                         "(D-037). Changing this changes the experiment")
    ap.add_argument("--shared-target", action="store_true",
                    help="REAL-DATA-04 amendment 1: instead of testing every "
                         "candidate against ONE fixed ground point, accept a "
                         "candidate whose TILE-ADMISSIBLE footprint shares "
                         "ground with the incumbents', and derive the target "
                         "point as the centroid of that shared region")
    ap.add_argument("--incumbent-geometry",
                    default="real_pair_index_geometry.json",
                    help="index-geometry manifest(s), comma separated, giving "
                         "the incumbents' AUTHORITATIVE named corners "
                         "(--shared-target only)")
    ap.add_argument("--incumbent-frames", default=None,
                    help="comma-separated incumbent pdsids to anchor the "
                         "shared region on (--shared-target only). Default: "
                         "every tile in --incumbent-manifest")
    ap.add_argument("--candidate-geometry", default=None,
                    help="index-geometry manifest(s), comma separated, giving "
                         "CANDIDATES' authoritative named corners. Supplying "
                         "it replaces the inferred ODE ring for those "
                         "candidates and enables hard filter 1c, the "
                         "orientation match against the incumbents")
    ap.add_argument("--out", required=True,
                    help="output manifest name under data/manifests/")
    args = ap.parse_args()

    out_path = DATA / "manifests" / args.out
    if out_path.exists():
        raise SystemExit(f"{out_path.relative_to(ROOT)} already exists; choose "
                         "a new name (integrity rule 4)")

    man = json.loads((DATA / "manifests" / args.incumbent_manifest)
                     .read_text(encoding="utf-8"))
    incumbents = {t["pdsid"]: float(t["ode_map_resolution_m"]) for t in man["tiles"]}
    inc_by_pdsid = {t["pdsid"]: float(t["incidence_deg"]) for t in man["tiles"]}
    inc_a = min(inc_by_pdsid.values())   # A is the low-incidence incumbent
    pdsid_a = min(inc_by_pdsid, key=inc_by_pdsid.get)
    if args.target_lonlat:
        lon, lat = (float(x) for x in args.target_lonlat.split(","))
    else:
        lon, lat = man["target_ground_point_lon_lat"]
    band = tuple(float(x) for x in args.incidence_band.split(","))

    print("== REAL-DATA-04 step 1: screening for frame D (METADATA ONLY) ==\n")
    print(f"incumbents      : " + ", ".join(
        f"{p} ({inc_by_pdsid[p]:.2f} deg, {incumbents[p]:.3f} m)"
        for p in incumbents))
    print(f"A (lowest inc)  : {pdsid_a} at {inc_a:.2f} deg")
    print(f"target point    : {lon:.12f}, {lat:.12f}")
    print(f"tile            : {args.lines} x {args.samples}")
    print(f"incidence band  : [{band[0]}, {band[1]}] deg   ceiling "
          f"{args.incidence_max} deg")
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
    if args.shared_target:
        anchors = ([x.strip() for x in args.incumbent_frames.split(",")]
                   if args.incumbent_frames else list(incumbents))
        corners = incumbent_corners(args.incumbent_geometry.split(","), anchors)
        incumbent_polys = [
            tile_admissible_polygon(corners[p], n_lines=args.lines,
                                    n_samples=args.samples) for p in anchors]
        plane = LocalPlane.centred_on(incumbent_polys)
        shared = plane.to_km(incumbent_polys[0])
        for poly in incumbent_polys[1:]:
            shared = convex_clip(shared, plane.to_km(poly))
            if len(shared) < 3:
                raise SystemExit(
                    "the incumbent frames share no tile-admissible ground; "
                    "there is no point at which they could both be re-cut")
        anchor_sigs = {p: orientation_signature(corners[p]) for p in anchors}
        if len(set(anchor_sigs.values())) != 1:
            raise SystemExit(
                f"the anchor frames disagree on orientation ({anchor_sigs}); "
                "there is no single orientation for a candidate to match")
        anchor_orientation = next(iter(anchor_sigs.values()))
        print(f"AMENDMENT 1 shared-target mode: anchors {', '.join(anchors)}")
        print(f"   anchor orientation signature: {anchor_orientation} "
              "(along-track, cross-track)")
        print(f"   incumbent shared tile-admissible region: "
              f"{polygon_area_km2(shared):.3f} km2")
        print("   the target point is DERIVED from the chosen frame, not "
              "fixed in advance\n")

    if args.candidate_geometry:
        fields: dict[str, dict] = {}
        for name in args.candidate_geometry.split(","):
            g = json.loads((DATA / "manifests" / name.strip())
                           .read_text(encoding="utf-8"))
            fields.update(g["products"])
        authoritative = incumbent_corners(
            args.candidate_geometry.split(","), sorted(fields))
        print(f"authoritative corners supplied for {len(authoritative)} "
              "candidate(s); hard filter 1c (orientation match) is ACTIVE\n")

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
        else:
            row = screen_one(
                p.raw, target=(lon, lat), n_lines=args.lines,
                n_samples=args.samples, inc_max=args.incidence_max,
                inc_band=band, incumbents=incumbents, inc_a=inc_a,
                lines=args.frame_lines, samples=args.frame_samples)
        if row["admissible"]:
            row["d_incidence_vs_incumbents"] = {
                k: abs(row["incidence_deg"] - v)
                for k, v in inc_by_pdsid.items()}
        rows.append(row)

    admissible = [r for r in rows if r["admissible"]]
    admissible.sort(key=lambda r: (r["max_resolution_ratio"],
                                   r["abs_d_incidence_vs_A"]))

    # -- how far each candidate got, so the funnel is visible ---------------
    funnel: dict[str, int] = {}
    for r in rows:
        key = "ADMISSIBLE" if r["admissible"] else r["rejected_by"].split(":")[0]
        funnel[key] = funnel.get(key, 0) + 1
    print("screening funnel")
    for k in sorted(funnel):
        print(f"   {k:<12} {funnel[k]}")

    print(f"\n{len(admissible)} admissible candidate(s), ranked by the "
          "deciding criterion (max resolution ratio):\n")
    if not admissible:
        print("   NONE. Per the pre-registration, widen the search SPATIALLY "
              "and re-run; do NOT relax a criterion.")
    for i, r in enumerate(admissible):
        d = r["d_incidence_vs_incumbents"]
        print(f"   {i + 1}. {r['pdsid']}  incidence {r['incidence_deg']:.2f} "
              f"deg  res {r['map_resolution_m']:.3f} m  "
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
        "stage": "REAL-DATA-04",
        "step": "1 - candidate screening for frame D",
        "data_read": "ODE product METADATA ONLY. No image bytes were fetched.",
        "criteria_source": (
            "docs/stages/REAL-DATA-04_illumination_vs_frame_identity.md "
            "section 3, frozen before this ran"),
        "criteria": {
            "hard_1_same_ground_point": (
                None if args.shared_target else [lon, lat]),
            "hard_1_amendment_1_shared_tile_admissible_anchors": (
                anchors if args.shared_target else None),
            "hard_1c_orientation_signature_required": (
                list(anchor_orientation) if anchor_orientation
                and authoritative else None),
            "hard_1_mode": ("AMENDMENT 1: shared tile-admissible region of the "
                            "anchors; target derived as its centroid"
                            if args.shared_target else
                            "original: one fixed ground point"),
            "hard_2_full_tile_fits_unclamped": [args.lines, args.samples],
            "hard_3_incidence_max_deg": args.incidence_max,
            "hard_4_incidence_band_deg": list(band),
            "hard_5_not_an_incumbent": sorted(incumbents),
            "deciding": "minimise the maximum Map_resolution ratio vs A, B, C",
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
            "note": ("ODE does not publish IMAGE_LINES / LINE_SAMPLES in the "
                     "product summary. Nominal NAC CDR dimensions are used to "
                     "RANK candidates only; the winner's true dimensions come "
                     "from the archive index table before acquisition, and "
                     "acquire_real_pair.py refuses to clamp a window."),
        },
        "footprint_vertex_order_assumption": {
            "order": list(ODE_RING_ORDER),
            "note": ("ODE's ring order is undocumented (REAL-DATA-02 section "
                     "6.3). This inference is used ONLY to rank candidates. "
                     "No claim rests on it; the chosen frame's corners are "
                     "re-fetched from the NAMED index columns."),
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
        print(f"SELECTED frame D: {admissible[0]['pdsid']}")
    else:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
