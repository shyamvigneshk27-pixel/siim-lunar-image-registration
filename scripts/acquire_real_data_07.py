"""REAL-DATA-07 acquisition: every census frame over the two recorded windows.

    python scripts/acquire_real_data_07.py --window RD03
    python scripts/acquire_real_data_07.py --window RD04

Frozen in ``docs/stages/REAL-DATA-07_replication_and_envelope.md`` Part 1 §3:
the frame list, 4096 x 2048 windows centred on each window's recorded target
by the same corner-map inversion as REAL-DATA-03/04, decimation 2 -- except the
0.49 m frame E1, cut at 8192 x 4096 for decimation 4 so its decimated tile has
the same pixel shape and ground extent as the incumbents.

The incumbents' recorded tile entries are copied into the new manifest
unchanged, so the recorded edges are present in the same manifest as the new
ones and the overlap verifier sees every pair at once. Bytes are fetched in
strict chunks with retries (the archive dropped single large requests on
2026-09-04). Labels come from ODE as in acquire_real_pair.py; corner geometry
from ``real_data_07_index_geometry.json`` (fetch_index_geometry.py).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siim.ingest import (  # noqa: E402
    FrameCorners,
    decode_tile,
    fetch_byte_range_chunked,
    fetch_label,
    parse_display_direction,
    parse_image_structure,
    plan_tile_byte_range,
    validate_structure,
)
from siim.ingest.lro_nac import _parse_product  # noqa: E402

_spec = importlib.util.spec_from_file_location("_acq", ROOT / "scripts" / "acquire_real_pair.py")
_acq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_acq)

DATA = ROOT / "data"
REGION = "mare_serenitatis"
NEW_GEOMETRY = "real_data_07_index_geometry.json"

#: Part 1 §3. Frames listed under the window(s) they cover.
WINDOWS = {
    "RD03": {
        "incumbent_manifest": "real_triplet_geo_manifest.json",
        "out": "real_data_07_rd03_manifest.json",
        "new": ["nac.m1356349796lc", "nac.m1182331886lc", "nac.m1236465772rc",
                "nac.m1212932972lc", "nac.m1205872034rc", "nac.m1175268993rc",
                "nac.m1363396554rc", "nac.m1199981485lc", "nac.m1199981485rc",
                "nac.m1096350825rc", "nac.m1142297886lc"],
    },
    "RD04": {
        "incumbent_manifest": "real_quad_d_geo_manifest.json",
        "out": "real_data_07_rd04_manifest.json",
        "new": ["nac.m124423514lc", "nac.m1315225542lc", "nac.m1341069775rc",
                "nac.m1356349796lc", "nac.m1212932972lc", "nac.m1363396554rc",
                "nac.m1096350825rc"],
    },
}
#: E1: finer than the incumbents by 2x; larger window, decimation 4 (Part 1 §3).
FINE_FRAMES = {"nac.m124423514lc": {"n_lines": 8192, "n_samples": 4096, "decimation": 4}}
DEFAULT = {"n_lines": 4096, "n_samples": 2048, "decimation": 2}


def corners_for(pdsid: str, fields: dict, label_text: str) -> FrameCorners:
    disp = parse_display_direction(label_text)
    if (disp["vertical_axis"], disp["vertical_direction"]) != ("Line", "Top to Bottom"):
        raise SystemExit(f"{pdsid}: unexpected Display_Direction {disp}")

    def c(name):
        return (float(fields[name + "_LONGITUDE"]), float(fields[name + "_LATITUDE"]))

    return FrameCorners(c("UPPER_LEFT"), c("UPPER_RIGHT"), c("LOWER_LEFT"),
                        c("LOWER_RIGHT"), int(fields["IMAGE_LINES"]), int(fields["LINE_SAMPLES"]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--window", choices=sorted(WINDOWS), required=True)
    ap.add_argument("--only", default=None, help="comma list of pdsids to fetch (subset)")
    args = ap.parse_args()
    spec = WINDOWS[args.window]

    out_path = DATA / "manifests" / spec["out"]
    if out_path.exists():
        raise SystemExit(f"{out_path.relative_to(ROOT)} exists (integrity rule 4)")
    inc_man = json.loads((DATA / "manifests" / spec["incumbent_manifest"]).read_text(encoding="utf-8"))
    lon, lat = inc_man["target_ground_point_lon_lat"]
    geom_path = DATA / "manifests" / NEW_GEOMETRY
    if not geom_path.exists():
        raise SystemExit(f"{geom_path.relative_to(ROOT)} missing; run fetch_index_geometry.py first")
    geometry = json.loads(geom_path.read_text(encoding="utf-8"))["products"]

    wanted = spec["new"] if not args.only else [x for x in args.only.split(",") if x]
    out_dir = DATA / "processed" / REGION
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"== REAL-DATA-07 acquisition: {args.window} target ({lon:.6f}, {lat:.6f}); "
          f"{len(wanted)} new frames + {len(inc_man['tiles'])} incumbents ==\n")

    entries = [dict(t, role="incumbent (recorded tile, copied unchanged)",
                    decimation=2) for t in inc_man["tiles"]]
    excluded: list[dict] = []
    for pdsid in wanted:
        if pdsid not in geometry:
            raise SystemExit(f"{pdsid}: no corner geometry in {NEW_GEOMETRY}")
        rec = _acq.ode_record(pdsid)
        prod = _parse_product(rec)
        lbl = fetch_label(prod, DATA / "metadata" / REGION)
        text = lbl.read_text(encoding="utf-8")
        struct = parse_image_structure(text)
        for c in validate_structure(struct):
            print(f"   + {pdsid}: {c}")
        fields = geometry[pdsid]["fields"]
        corners = corners_for(pdsid, fields, text)
        if (corners.lines, corners.samples) != (struct.lines, struct.samples):
            raise SystemExit(f"{pdsid}: index shape {corners.lines}x{corners.samples} != "
                             f"label {struct.lines}x{struct.samples}")
        win = FINE_FRAMES.get(pdsid, DEFAULT)
        try:
            line0, sample0, detail = _acq.window_centred_on(corners, lon, lat,
                                                            win["n_lines"], win["n_samples"])
        except ValueError as exc:
            # The target ground point is outside this frame's swath (the census
            # box was +/-0.02 deg, wider than some frames' margin over the target).
            # A tile cannot be centred on the target, so the frame is EXCLUDED and
            # listed -- the same treatment Part 1 section 3 gives an edge whose
            # overlap is not CONFIRMED. No clamping, no re-centring.
            print(f"   !! {pdsid}: EXCLUDED -- {exc}", flush=True)
            excluded.append({"pdsid": pdsid, "reason": str(exc)})
            continue
        if not detail["fully_inside_frame"]:
            print(f"   !! {pdsid}: window CLAMPED {detail['clamped_lines']:+d} lines, "
                  f"{detail['clamped_samples']:+d} samples")
        byte_start, byte_count = plan_tile_byte_range(struct, line0=line0, n_lines=win["n_lines"])
        npy = out_dir / f"{pdsid}.geo.l{line0}s{sample0}.n{win['n_lines']}.tile.npy"
        if npy.exists():
            print(f"   {pdsid}: tile already on disk, verifying hash from manifest is not "
                  "possible here; refusing to overwrite")
            raise SystemExit(f"{npy.relative_to(ROOT)} exists")
        print(f"{pdsid}: inc {rec.get('Incidence_angle')} res {rec.get('Map_resolution')} "
              f"lines [{line0}, {line0 + win['n_lines']}) samples [{sample0}, "
              f"{sample0 + win['n_samples']})  {byte_count / 1e6:.1f} MB", flush=True)
        t0 = time.perf_counter()
        raw = fetch_byte_range_chunked(
            prod.image_url, byte_start, byte_count,
            progress=lambda g, t, _t0=t0: print(f"      {g / 1e6:6.1f}/{t / 1e6:.1f} MB "
                                                f"({time.perf_counter() - _t0:.0f}s)", flush=True)
            if g % (16 << 20) < (8 << 20) or g == t else None)
        digest = hashlib.sha256(raw).hexdigest()
        arr = decode_tile(raw, struct, n_lines=win["n_lines"], sample0=sample0,
                          n_samples=win["n_samples"])
        np.save(npy, np.asarray(arr))
        print(f"   {arr.shape} sha256={digest[:16]}... DN median {np.nanmedian(arr):.1f} "
              f"({time.perf_counter() - t0:.0f}s)\n", flush=True)
        entries.append({
            "pdsid": pdsid, "role": "REAL-DATA-07 census frame",
            "image_url": prod.image_url, "img_file_name": struct.file_name,
            "byte_start": byte_start, "byte_count": byte_count, "bytes_sha256": digest,
            "line0": line0, "n_lines": win["n_lines"], "sample0": sample0,
            "n_samples": win["n_samples"], "decimation": win["decimation"],
            "parent_shape_lines_samples": [struct.lines, struct.samples],
            "data_type": struct.data_type, "numpy_dtype": struct.numpy_dtype,
            "scaling_factor": struct.scaling_factor, "unit": struct.unit,
            "index_convention": "array[row=line, column=sample], 0-based",
            "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "fetch": "strict 8 MB chunks with retries (fetch_byte_range_chunked)",
            "region": REGION, "label_path": str(lbl.relative_to(ROOT)),
            "tile_npy": str(npy.relative_to(ROOT)),
            "incidence_deg": float(rec.get("Incidence_angle") or "nan"),
            "emission_deg": float(rec.get("Emission_angle") or "nan"),
            "utc_start": rec.get("UTC_start_time"),
            "ode_map_resolution_m": float(rec.get("Map_resolution") or "nan"),
            "selection_method": "GEOMETRY-DRIVEN (REAL-DATA-03, D-033); frame from the 2026-09-04 ODE census (REAL-DATA-07 Part 1 §3)",
            "target_ground_point_lon_lat": [lon, lat],
            "window_detail": detail,
            "index_geometry_sources": [NEW_GEOMETRY],
            "index_corners_lon_lat": {
                "upper_left": list(corners.upper_left), "upper_right": list(corners.upper_right),
                "lower_left": list(corners.lower_left), "lower_right": list(corners.lower_right)},
            "lro_flight_direction": fields.get("LRO_FLIGHT_DIRECTION"),
            "orbit_node": fields.get("ORBIT_NODE"),
            "geolocation_status": inc_man["tiles"][0]["geolocation_status"],
            "azimuth_status": inc_man["tiles"][0]["azimuth_status"],
        })

    out_path.write_text(json.dumps({
        "dataset": "LRO NAC (LROC) real image tiles via PDS",
        "stage": "REAL-DATA-07",
        "region": REGION,
        "pair": [e["pdsid"] for e in entries],
        "pair_role": "real_data_07_window",
        "window": args.window,
        "derived_from": spec["incumbent_manifest"],
        "target_ground_point_lon_lat": [lon, lat],
        "incidence_deg": [e["incidence_deg"] for e in entries],
        "chandrayaan2_status": "NOT OBTAINED. No Chandrayaan-2 data is present.",
        "licence": "NASA PDS public domain; credit NASA/GSFC/Arizona State University.",
        "excluded_frames": excluded,
        "tiles": entries,
    }, indent=2), encoding="utf-8")
    print(f"manifest: {out_path.relative_to(ROOT)}  ({len(entries)} tiles, {len(excluded)} excluded)")


if __name__ == "__main__":
    main()
