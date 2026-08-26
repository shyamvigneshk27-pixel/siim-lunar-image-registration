"""Acquire the first REAL LRO NAC image pair: observational labels + decoded tiles.

Run:  python scripts/acquire_real_pair.py [--lines 4096] [--hypothesis H1|H2]

What this does, and what it deliberately does not do
----------------------------------------------------
It fetches two byte-range tiles from two real NAC frames, decodes them through
the PDS4 label, and records full provenance. It does **not** produce a
geographically registered pair.

**The tile-selection approximation, stated plainly.** LRO NAC CDR products are
in sensor geometry, not map-projected. This project has no SPICE kernels and no
camera model, so there is no exact pixel -> (lat, lon) mapping available. What
is available is the ODE ``Footprint_geometry`` polygon, which gives the frame's
latitude and longitude bounds. The approximation used here is:

    line index is linear in latitude across the frame

which is defensible for a push-broom sensor in a near-polar orbit -- latitude
is the along-track coordinate and varies monotonically along the frame -- and
is supported by an independent consistency check this script prints: the
implied metres-per-line derived from the footprint's latitude span agrees with
ODE's reported ``Map_resolution`` to ~5% for both frames.

It is still an approximation. Cross-track (sample) position is taken as the
centre of the frame, on the reasoning that the two frames' longitude ranges
overlap in their middles. **The resulting crop is a plausible overlapping
region, not a registered one.** Whether the tiles actually overlap is decided
by the registration attempt, and that is reported as such.

**The line-direction ambiguity.** Whether line 0 sits at the frame's maximum or
minimum latitude is not recoverable from the footprint polygon. LRO images the
dayside on the descending pass (north to south), which makes line 0 at maximum
latitude the physically expected case; that is ``H1``. Because both frames come
from the same camera and the same processing pipeline, **the convention is the
same for both** -- the choice is H1-for-both or H2-for-both, never mixed. If H1
yields no correspondences, H2 is the remaining hypothesis, and which one was
used is recorded in the output.

.. warning::

   **The paragraph above is wrong, and it is left exactly as written under
   integrity rule 3 because it is the defect's own evidence.** REAL-DATA-02
   (E-028) showed that the line readout direction relative to the ground track
   is set by **spacecraft attitude**, not by the camera or the pipeline: LRO
   yaw-flips, and the archive publishes the answer per frame in
   ``LRO_FLIGHT_DIRECTION`` (``-X`` -> line 0 at minimum latitude, ``+X`` ->
   maximum). Both frames of the ``usable`` pair are ``H2``; the pair was
   acquired at ``H1``, and its two tiles landed **22.75 km apart**. The
   ``--from-geometry`` mode below supersedes the whole ``--hypothesis`` /
   footprint-latitude path: it reads named corner coordinates from the PDS
   archive index table and inverts the ground map per frame, on **both** axes
   (E-029: cross-track position was assumed too). The old path is retained,
   unchanged, so the REAL-DATA-01 artefacts stay reproducible.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import requests  # noqa: E402

from siim.ingest.lro_nac import (  # noqa: E402
    ODE_ENDPOINT,
    _parse_product,
    fetch_image_tile,
    fetch_label,
    observational_label_url,
    parse_footprint,
)
from siim.ingest.footprint import (  # noqa: E402
    FrameCorners,
    LocalPlane,
    convex_clip,
    shared_tile_target,
)
from siim.ingest.pds4 import (  # noqa: E402
    parse_display_direction,
    parse_image_structure,
    validate_structure,
)

DATA = ROOT / "data"
REGION = "mare_serenitatis"

#: Default pair. NOTE the incidence values: 89.96 deg and 24.64 deg. Selecting
#: on MAXIMUM incidence difference drives the choice to the terminator, where
#: one frame carries almost no signal (measured: DN median 29 +/- 20, lag-1
#: autocorrelation 0.355 against 0.976 for the other frame). See ERROR_LEDGER
#: E-024 and DECISION_LEDGER D-029: the pair selector needs an incidence
#: CEILING as well as a difference floor.
PAIR_TERMINATOR = ["nac.m1322281266lc", "nac.m1225876972lc"]

#: Best-conditioned pair with both incidences below 75 deg: d_incidence 39.8,
#: footprint IoU 0.516 (the highest in the usable set), resolution ratio 1.016.
PAIR_USABLE = ["nac.m1271742202lc", "nac.m1335207975rc"]

PAIR = PAIR_USABLE
_UA = {"User-Agent": "SIIM/0.1 (SIH 26166 research; contact via repository)"}

#: Mean lunar radius, km. Used only for the metres-per-line consistency check.
MOON_RADIUS_KM = 1737.4


def ode_record(pdsid: str) -> dict:
    r = requests.get(ODE_ENDPOINT, timeout=90, headers=_UA, params={
        "query": "product", "results": "fmp", "output": "JSON", "target": "moon",
        "ihid": "LRO", "iid": "LROC", "pt": "CDRNAC4", "pdsid": pdsid,
    })
    r.raise_for_status()
    prods = r.json().get("ODEResults", {}).get("Products")
    if isinstance(prods, str):
        raise RuntimeError(f"ODE returned {prods!r} for pdsid={pdsid!r}")
    p = prods["Product"]
    return p[0] if isinstance(p, list) else p


def lat_bounds(rec: dict) -> tuple[float, float]:
    """Latitude span of the frame, from the footprint polygon.

    Preferred over ``Minimum_latitude`` / ``Maximum_latitude`` so that the
    bounds and the geometry come from the same object.
    """
    pts = parse_footprint(rec.get("Footprint_geometry"))
    if len(pts) < 3:
        raise RuntimeError("no usable footprint polygon")
    lats = [p[1] for p in pts]
    return min(lats), max(lats)


# ---------------------------------------------------------------------------
# Geometry-driven tile selection (REAL-DATA-03). Supersedes the footprint-
# latitude path above; see the warning in the module docstring, E-028, E-029
# and D-033.
# ---------------------------------------------------------------------------


def corners_from_index_geometry(pdsid: str, geometry: dict,
                                label_text: str) -> FrameCorners:
    """Named frame corners for one product, with the naming checked per product.

    ``UPPER_*`` is read as image line 0 and ``*_LEFT`` as sample 0 **only**
    when the product's own PDS4 label says so via ``disp:Display_Direction``.
    A product whose label reads otherwise raises rather than falling back to
    convention -- the convention is exactly what was wrong in E-028.
    """
    rec = geometry["products"].get(pdsid)
    if rec is None:
        raise SystemExit(
            f"{pdsid} is not in the index-geometry manifest; run "
            f"scripts/fetch_index_geometry.py --pdsids {pdsid} --out <new>")
    disp = parse_display_direction(label_text)
    if (disp["vertical_axis"], disp["vertical_direction"]) != (
            "Line", "Top to Bottom"):
        raise SystemExit(
            f"{pdsid}: disp:Display_Direction is {disp}; UPPER_* is only read "
            "as line 0 when the label says Line runs Top to Bottom")
    if (disp["horizontal_axis"], disp["horizontal_direction"]) != (
            "Sample", "Left to Right"):
        raise SystemExit(
            f"{pdsid}: disp:Display_Direction is {disp}; *_LEFT is only read "
            "as sample 0 when Sample runs Left to Right")
    f = rec["fields"]

    def c(corner: str) -> tuple[float, float]:
        return (float(f[corner + "_LONGITUDE"]), float(f[corner + "_LATITUDE"]))

    return FrameCorners(
        upper_left=c("UPPER_LEFT"), upper_right=c("UPPER_RIGHT"),
        lower_left=c("LOWER_LEFT"), lower_right=c("LOWER_RIGHT"),
        lines=int(f["IMAGE_LINES"]), samples=int(f["LINE_SAMPLES"]),
    )


def shared_footprint_centroid(frames: list[FrameCorners]) -> tuple[float, float]:
    """Centroid of the intersection of every frame's full footprint.

    Raises if the frames do not all share ground -- there is then no point on
    which every tile could be centred, and inventing one would put the tiles
    somewhere no evidence supports.
    """
    plane = LocalPlane.centred_on([f.frame_polygon() for f in frames])
    shared = plane.to_km(frames[0].frame_polygon())
    for f in frames[1:]:
        shared = convex_clip(shared, plane.to_km(f.frame_polygon()))
        if len(shared) < 3:
            raise SystemExit(
                "the frames' footprints do not all intersect; there is no "
                "ground point every tile could be centred on")
    centroid = np.asarray(shared, float).mean(axis=0)
    k = np.pi / 180.0 * MOON_RADIUS_KM
    lon = plane.lon0 + centroid[0] / (k * np.cos(np.deg2rad(plane.lat0)))
    lat = plane.lat0 + centroid[1] / k
    return float(lon), float(lat)


def window_centred_on(corners: FrameCorners, lon: float, lat: float,
                      n_lines: int, n_samples: int) -> tuple[int, int, dict]:
    """``(line0, sample0, detail)`` for a tile centred on a ground point.

    ``(n - 1) / 2``, not ``n / 2``: a tile spans its **last included** pixel,
    so the centre of a window starting at ``line0`` is ``line0 + (n-1)/2``.
    Half a pixel is 0.45 m here and changes nothing, but the convention is
    fixed in one place rather than re-derived at each call site.

    The window is clamped into the frame, and the clamp is **reported** --
    a clamped window no longer sits on the requested ground point, and that
    has to be visible rather than absorbed.
    """
    line, sample = corners.pixel_at(lon, lat)
    want_l = int(round(line - (n_lines - 1) / 2.0))
    want_s = int(round(sample - (n_samples - 1) / 2.0))
    line0 = max(0, min(want_l, corners.lines - n_lines))
    sample0 = max(0, min(want_s, corners.samples - n_samples))
    return line0, sample0, {
        "target_pixel_line": float(line),
        "target_pixel_sample": float(sample),
        "unclamped_line0": want_l,
        "unclamped_sample0": want_s,
        "clamped_lines": int(line0 - want_l),
        "clamped_samples": int(sample0 - want_s),
        "fully_inside_frame": bool(line0 == want_l and sample0 == want_s),
    }


def acquire_from_geometry(args) -> None:
    """REAL-DATA-03 acquisition: windows derived from archive corner geometry.

    Every product is cut on the **same ground point**, so a pair is centred on
    shared ground and a triplet is centred on ground all three share. Nothing
    about the illumination, the matcher or any previous result enters the
    choice.
    """
    geom_paths = [DATA / "manifests" / n for n in args.from_geometry.split(",")]
    geometry: dict = {"products": {}, "sources": []}
    for gp in geom_paths:
        if not gp.exists():
            raise SystemExit(f"missing index geometry {gp}; run "
                             "scripts/fetch_index_geometry.py first")
        g = json.loads(gp.read_text(encoding="utf-8"))
        geometry["products"].update(g["products"])
        geometry["sources"].append(str(gp.relative_to(ROOT)))

    pdsids = [x.strip() for x in args.products.split(",") if x.strip()]
    if len(pdsids) < 1:
        raise SystemExit("--products needs at least one product id")
    if len(pdsids) < 2 and not (args.target_lonlat or args.target_shared_tile):
        raise SystemExit(
            "a single product has no shared footprint to centre on; supply "
            "--target-lonlat, which is how a third image is cut on the ground "
            "point an existing pair already shares")

    man_name = args.out or f"real_geo_{'_'.join(str(len(pdsids)))}_manifest.json"
    man_path = DATA / "manifests" / man_name
    if man_path.exists():
        raise SystemExit(
            f"{man_path.relative_to(ROOT)} already exists. Choose a new name; "
            "an acquisition manifest is never overwritten (integrity rule 4, "
            "E-025).")

    print("== REAL-DATA-03: geometry-driven acquisition ==\n")
    print(f"index geometry: {', '.join(geometry['sources'])}\n")

    meta: dict[str, dict] = {}
    for pdsid in pdsids:
        rec = ode_record(pdsid)
        prod = _parse_product(rec)
        print(f"{pdsid}")
        print(f"   observational label : {observational_label_url(prod)}")
        lbl = fetch_label(prod, DATA / "metadata" / REGION)
        text = lbl.read_text(encoding="utf-8")
        struct = parse_image_structure(text)
        for c in validate_structure(struct):
            print(f"      + {c}")
        corners = corners_from_index_geometry(pdsid, geometry, text)
        if (corners.lines, corners.samples) != (struct.lines, struct.samples):
            raise SystemExit(
                f"{pdsid}: the index table says {corners.lines}x"
                f"{corners.samples} but the PDS4 label says {struct.lines}x"
                f"{struct.samples}. Two archive sources disagreeing about the "
                "array shape is not reconciled here.")
        g = geometry["products"][pdsid]["fields"]
        upper_north = (0.5 * (corners.upper_left[1] + corners.upper_right[1])
                       > 0.5 * (corners.lower_left[1] + corners.lower_right[1]))
        print(f"      + index shape agrees with the label: "
              f"{corners.lines} x {corners.samples}")
        print(f"      + line 0 at {'MAX' if upper_north else 'MIN'} latitude "
              f"(LRO_FLIGHT_DIRECTION {g.get('LRO_FLIGHT_DIRECTION')}, "
              f"ORBIT_NODE {g.get('ORBIT_NODE')})")
        meta[pdsid] = {
            "record": rec, "product": prod, "structure": struct,
            "corners": corners, "label_path": lbl,
            "incidence_deg": float(rec.get("Incidence_angle") or "nan"),
            "emission_deg": float(rec.get("Emission_angle") or "nan"),
            "utc_start": rec.get("UTC_start_time"),
            "ode_map_resolution_m": float(rec.get("Map_resolution") or "nan"),
            "index_fields": g,
        }
        print()

    if args.target_lonlat and args.target_shared_tile:
        raise SystemExit(
            "--target-lonlat and --target-shared-tile both specify the ground "
            "point; pass one")
    if args.target_lonlat:
        lon, lat = (float(x) for x in args.target_lonlat.split(","))
        target_note = "supplied on the command line"
    elif args.target_shared_tile:
        # REAL-DATA-04 amendment 1. The default below centres on the shared
        # FRAME footprint, which can put the point within half a tile of an
        # edge and clamp the window. This centres on the ground every frame can
        # hold a WHOLE tile on, so no window is clamped by construction.
        lon, lat = shared_tile_target(
            [meta[p]["corners"] for p in pdsids],
            n_lines=args.lines, n_samples=args.samples)
        target_note = (
            f"centroid of the intersection of all {len(pdsids)} frames' "
            f"TILE-ADMISSIBLE footprints for a {args.lines}x{args.samples} "
            "tile (REAL-DATA-04 amendment 1; supersedes the shared-frame "
            "centroid, which does not guarantee an unclamped window)")
    else:
        lon, lat = shared_footprint_centroid(
            [meta[p]["corners"] for p in pdsids])
        target_note = ("centroid of the intersection of all "
                       f"{len(pdsids)} frame footprints")
    print(f"target ground point: lon {lon:.6f}, lat {lat:.6f}  ({target_note})\n")

    out_dir = DATA / "processed" / REGION
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for pdsid in pdsids:
        m = meta[pdsid]
        line0, sample0, detail = window_centred_on(
            m["corners"], lon, lat, args.lines, args.samples)
        if not detail["fully_inside_frame"]:
            print(f"   !! {pdsid}: window CLAMPED by "
                  f"{detail['clamped_lines']:+d} lines, "
                  f"{detail['clamped_samples']:+d} samples -- the tile is no "
                  "longer centred on the target ground point")
        print(f"{pdsid}: target pixel (line {detail['target_pixel_line']:.0f}, "
              f"sample {detail['target_pixel_sample']:.0f}) -> tile lines "
              f"[{line0}, {line0 + args.lines}) samples "
              f"[{sample0}, {sample0 + args.samples})")
        arr, prov = fetch_image_tile(m["product"], m["structure"], line0=line0,
                                     n_lines=args.lines, sample0=sample0,
                                     n_samples=args.samples)
        # Filename encodes BOTH tile axes, not just the line offset: a
        # geometry-driven window differs from an H1/H2 window in sample0 as
        # well, and E-025 was exactly an artefact name that omitted a varying
        # parameter.
        npy = out_dir / f"{pdsid}.geo.l{line0}s{sample0}.tile.npy"
        if npy.exists():
            raise SystemExit(
                f"{npy.relative_to(ROOT)} already exists; refusing to "
                "overwrite an acquired tile (integrity rule 4, E-025)")
        np.save(npy, np.asarray(arr))
        prov.update({
            "region": REGION,
            "label_path": str(m["label_path"].relative_to(ROOT)),
            "tile_npy": str(npy.relative_to(ROOT)),
            "incidence_deg": m["incidence_deg"],
            "emission_deg": m["emission_deg"],
            "utc_start": m["utc_start"],
            "ode_map_resolution_m": m["ode_map_resolution_m"],
            "selection_method": "GEOMETRY-DRIVEN (REAL-DATA-03, D-033)",
            "target_ground_point_lon_lat": [lon, lat],
            "target_selection": target_note,
            "window_detail": detail,
            "index_geometry_sources": geometry["sources"],
            "index_corners_lon_lat": {
                "upper_left": list(m["corners"].upper_left),
                "upper_right": list(m["corners"].upper_right),
                "lower_left": list(m["corners"].lower_left),
                "lower_right": list(m["corners"].lower_right),
            },
            "lro_flight_direction": m["index_fields"].get("LRO_FLIGHT_DIRECTION"),
            "orbit_node": m["index_fields"].get("ORBIT_NODE"),
            "geolocation_status": (
                "Tile window derived by inverting a bilinear ground map built "
                "from the PDS archive index table's NAMED frame corners, with "
                "the corner naming taken from this product's own PDS4 "
                "disp:Display_Direction. This is a GEOMETRY-DRIVEN OVERLAP "
                "SELECTION on both axes -- it supersedes the footprint-latitude "
                "approximation of REAL-DATA-01 (E-028, E-029). It is still NOT "
                "a geographic registration: no camera model or SPICE kernel was "
                "used, corner coordinates are quoted to 0.01 deg (~150 m), and "
                "the ground map is bilinear. Overlap must be verified by "
                "scripts/verify_tile_overlap.py before any registration result "
                "is interpreted."),
            "azimuth_status": (
                "Sub-solar AZIMUTH was NOT used. The archive index table does "
                "carry SUB_SOLAR_AZIMUTH, but it is stated to be relative to "
                "the RDR products and that frame is unverified (RL-032b). This "
                "pair is illumination-varied by INCIDENCE only and is NOT "
                "azimuth-controlled."),
        })
        entries.append(prov)
        finite = np.isfinite(arr)
        print(f"   {arr.shape} {arr.dtype}  sha256={prov['bytes_sha256'][:16]}..."
              f"  {prov['byte_count'] / 1e6:.1f} MB")
        print(f"   DN median {np.nanmedian(arr):.1f}  std {np.nanstd(arr):.1f}  "
              f"finite {finite.mean():.4f}\n")

    incs = [m["incidence_deg"] for m in (meta[p] for p in pdsids)]
    ress = [m["ode_map_resolution_m"] for m in (meta[p] for p in pdsids)]
    man_path.write_text(json.dumps({
        "dataset": "LRO NAC (LROC) real image tiles via PDS ODE",
        "stage": "REAL-DATA-03",
        "region": REGION,
        "pair": pdsids,
        "pair_role": args.role or ("triplet" if len(pdsids) > 2 else "pair"),
        "selection_method": (
            "GEOMETRY-DRIVEN: every tile is centred on one ground point, "
            "derived from the archive index table's named frame corners. "
            "Supersedes the footprint-latitude / global-hypothesis path "
            "(E-028, E-029, D-033)."),
        "target_ground_point_lon_lat": [lon, lat],
        "target_selection": target_note,
        "index_geometry_sources": geometry["sources"],
        "incidence_deg": incs,
        "incidence_delta_deg": float(max(incs) - min(incs)),
        "resolution_ratio": float(max(ress) / min(ress)),
        "line_direction_hypothesis": (
            "NOT APPLICABLE -- read per frame from the archive, not assumed"),
        "chandrayaan2_status": (
            "NOT OBTAINED. No Chandrayaan-2 data is present. No multi-modal "
            "claim is supported by this manifest."),
        "licence": ("NASA PDS public domain; credit NASA/GSFC/Arizona State "
                    "University."),
        "tiles": entries,
    }, indent=2), encoding="utf-8")
    print(f"manifest: {man_path.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", type=int, default=4096,
                    help="tile height in lines (default 4096 ~ 3.7 km)")
    ap.add_argument("--samples", type=int, default=2048,
                    help="tile width in samples, centred cross-track")
    ap.add_argument("--hypothesis", choices=["H1", "H2"], default="H1",
                    help="H1: line 0 at max latitude (descending pass, expected)")
    ap.add_argument("--pair", choices=["usable", "terminator"], default="usable",
                    help="which candidate pair to acquire")
    ap.add_argument("--out", default=None, help="manifest basename override")
    ap.add_argument("--from-geometry", default=None,
                    help="comma-separated index-geometry manifest name(s) under "
                         "data/manifests/. Switches to GEOMETRY-DRIVEN tile "
                         "selection (REAL-DATA-03, D-033): windows are derived "
                         "per frame on BOTH axes from named archive corners, "
                         "and --pair/--hypothesis are not used")
    ap.add_argument("--products", default=None,
                    help="comma-separated product ids for --from-geometry; "
                         "two for a pair, three for a loop-closure triplet")
    ap.add_argument("--target-shared-tile", action="store_true",
                    help="centre every tile on the centroid of the ground all "
                         "the listed frames can hold a FULL tile on "
                         "(REAL-DATA-04 amendment 1). Unlike the default "
                         "shared-frame centroid this cannot clamp a window")
    ap.add_argument("--target-lonlat", default=None,
                    help="explicit 'lon,lat' ground point to centre every tile "
                         "on. Default: the centroid of the intersection of all "
                         "the frames' footprints")
    ap.add_argument("--role", default=None,
                    help="label recorded as pair_role in the manifest")
    args = ap.parse_args()

    if args.from_geometry:
        if not args.products:
            raise SystemExit("--from-geometry requires --products")
        acquire_from_geometry(args)
        return

    global PAIR
    PAIR = PAIR_USABLE if args.pair == "usable" else PAIR_TERMINATOR
    man_name = args.out or f"real_pair_{args.pair}_manifest.json"

    print("== first real LRO NAC pair: labels + tiles ==\n")
    meta: dict[str, dict] = {}
    for pdsid in PAIR:
        rec = ode_record(pdsid)
        prod = _parse_product(rec)
        print(f"{pdsid}")
        print(f"   observational label : {observational_label_url(prod)}")
        print(f"   browse label (unused): {prod.browse_label_url}")
        lbl = fetch_label(prod, DATA / "metadata" / REGION)  # validates or raises
        struct = parse_image_structure(lbl.read_text(encoding="utf-8"))
        for c in validate_structure(struct):
            print(f"      + {c}")
        lo, hi = lat_bounds(rec)
        km_per_deg = MOON_RADIUS_KM * np.pi / 180.0
        implied_m_per_line = (hi - lo) * km_per_deg * 1000.0 / struct.lines
        ode_res = float(rec.get("Map_resolution") or "nan")
        print(f"   lat span {lo:.3f}..{hi:.3f} deg over {struct.lines} lines")
        print(f"   implied {implied_m_per_line:.3f} m/line vs ODE Map_resolution "
              f"{ode_res:.3f} m  (ratio {implied_m_per_line / ode_res:.3f})")
        meta[pdsid] = {
            "record": rec, "product": prod, "structure": struct,
            "lat_min": lo, "lat_max": hi, "label_path": lbl,
            "implied_m_per_line": implied_m_per_line, "ode_map_resolution_m": ode_res,
            "incidence_deg": float(rec.get("Incidence_angle") or "nan"),
            "utc_start": rec.get("UTC_start_time"),
        }
        print()

    a, b = (meta[p] for p in PAIR)
    band_lo = max(a["lat_min"], b["lat_min"])
    band_hi = min(a["lat_max"], b["lat_max"])
    if band_hi <= band_lo:
        raise SystemExit("frames do not overlap in latitude; nothing to acquire")
    target = 0.5 * (band_lo + band_hi)
    print(f"overlap latitude band {band_lo:.3f}..{band_hi:.3f} deg "
          f"({(band_hi - band_lo) * MOON_RADIUS_KM * np.pi / 180:.1f} km); "
          f"target latitude {target:.4f} deg")
    print(f"hypothesis {args.hypothesis}: line 0 at "
          f"{'MAXIMUM' if args.hypothesis == 'H1' else 'MINIMUM'} latitude\n")

    out_dir = DATA / "processed" / REGION
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for pdsid in PAIR:
        m = meta[pdsid]
        s = m["structure"]
        frac = (target - m["lat_min"]) / (m["lat_max"] - m["lat_min"])
        centre = (1.0 - frac) * s.lines if args.hypothesis == "H1" else frac * s.lines
        line0 = int(round(centre - args.lines / 2.0))
        line0 = max(0, min(line0, s.lines - args.lines))
        sample0 = (s.samples - args.samples) // 2

        print(f"{pdsid}: frac={frac:.4f} -> centre line {centre:.0f}, "
              f"tile lines [{line0}, {line0 + args.lines})")
        arr, prov = fetch_image_tile(m["product"], s, line0=line0,
                                     n_lines=args.lines, sample0=sample0,
                                     n_samples=args.samples)
        # Filename encodes the tile POSITION, not just the product. An earlier
        # version used "{pdsid}.tile.npy", so acquiring the same product at a
        # different line offset silently overwrote the previous tile and left
        # two manifests pointing at one file -- which produced four "different"
        # registration runs with byte-identical results. ERROR_LEDGER E-025;
        # integrity rule 4 (never overwrite a superseded artefact).
        npy = out_dir / f"{pdsid}.{args.hypothesis}.l{line0}.tile.npy"
        np.save(npy, np.asarray(arr))
        prov.update({
            "region": REGION,
            "label_path": str(m["label_path"].relative_to(ROOT)),
            "tile_npy": str(npy.relative_to(ROOT)),
            "incidence_deg": m["incidence_deg"],
            "utc_start": m["utc_start"],
            "ode_map_resolution_m": m["ode_map_resolution_m"],
            "implied_m_per_line": m["implied_m_per_line"],
            "footprint_lat_min": m["lat_min"], "footprint_lat_max": m["lat_max"],
            "target_latitude_deg": target,
            "latitude_fraction_along_frame": frac,
            "line_direction_hypothesis": args.hypothesis,
            "geolocation_status": (
                "APPROXIMATE, PRE-REGISTRATION OVERLAP SELECTION. Line index "
                "assumed linear in latitude from the ODE footprint polygon; no "
                "camera model or SPICE kernel was used. Cross-track position is "
                "the frame centre. This crop is a plausible overlapping region, "
                "NOT a geographically registered one, and must never be "
                "described as the latter."),
            "azimuth_status": (
                "Sub-solar AZIMUTH is NOT available from ODE or from the PDS4 "
                "labels (E-020). This pair is illumination-varied by INCIDENCE "
                "only, and is NOT azimuth-controlled."),
        })
        entries.append(prov)
        finite = np.isfinite(arr)
        print(f"   {arr.shape} {arr.dtype}  sha256={prov['bytes_sha256'][:16]}...  "
              f"{prov['byte_count'] / 1e6:.1f} MB")
        print(f"   DN median {np.nanmedian(arr):.1f}  std {np.nanstd(arr):.1f}  "
              f"finite {finite.mean():.4f}\n")

    man = DATA / "manifests" / man_name
    man.write_text(json.dumps({
        "dataset": "LRO NAC (LROC) real image tiles via PDS ODE",
        "region": REGION,
        "pair": PAIR,
        "pair_role": args.pair,
        "incidence_delta_deg": abs(a["incidence_deg"] - b["incidence_deg"]),
        "resolution_ratio": max(a["ode_map_resolution_m"], b["ode_map_resolution_m"])
        / min(a["ode_map_resolution_m"], b["ode_map_resolution_m"]),
        "overlap_latitude_band_deg": [band_lo, band_hi],
        "line_direction_hypothesis": args.hypothesis,
        "chandrayaan2_status": (
            "NOT OBTAINED. No Chandrayaan-2 data is present. No multi-modal "
            "claim is supported by this manifest."),
        "licence": ("NASA PDS public domain; credit NASA/GSFC/Arizona State "
                    "University."),
        "tiles": entries,
    }, indent=2), encoding="utf-8")
    print(f"manifest: {man.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
