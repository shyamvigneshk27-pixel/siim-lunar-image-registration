"""EXP-007 tier-2 acquisition: long windows on the two recorded ground points.

    python scripts/acquire_long_windows_exp007.py --target RD03
    python scripts/acquire_long_windows_exp007.py --target RD04

Why a separate script
---------------------
``scripts/acquire_real_pair.py --from-geometry`` is the recorded stages'
acquisition path and it fetches each window as ONE range request. At 12288
lines x 5064 samples (124 MB) the LROC PDS server dropped that request twice
(read timeout; connection reset). This script makes the same geometric choice
-- the same target ground point, the same corner-map inversion, the same
``(n - 1) / 2`` centring -- and fetches the bytes in strict 8 MB chunks with
retries (:func:`siim.ingest.fetch_byte_range_chunked`). It writes the same
manifest schema the runner reads.

No ODE query is made: every product's image URL, label and index geometry are
already recorded in the tier-1 manifests and metadata directory, and reusing
them keeps the tier-2 windows on exactly the frames the recorded edges used.

Frozen in EXP-007 Part 1 section 4: 12288 lines, full 5064-sample width,
centred on the RD-03 target for frames A, B, C and on the RD-04 target for
frames A, B, D. Nothing about illumination, the matcher or any result enters
the choice.
"""

from __future__ import annotations

import argparse
import hashlib
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
    parse_display_direction,
    parse_image_structure,
    plan_tile_byte_range,
    validate_structure,
)

DATA = ROOT / "data"
REGION = "mare_serenitatis"
N_LINES = 12288
N_SAMPLES = 5064

TARGETS = {
    "RD03": {"manifest": "real_triplet_geo_manifest.json",
             "out": "exp007_long_triplet_abc_manifest.json"},
    "RD04": {"manifest": "real_quad_d_geo_manifest.json",
             "out": "exp007_long_triplet_abd_manifest.json"},
}
GEOMETRY_FILES = ["real_pair_index_geometry.json", "real_pair_index_geometry_C.json",
                  "real_frame_d_candidates_index_geometry.json",
                  "real_frame_d_selected_index_geometry.json"]


def load_products() -> dict:
    out: dict = {}
    for name in GEOMETRY_FILES:
        p = DATA / "manifests" / name
        if p.exists():
            out.update(json.loads(p.read_text(encoding="utf-8"))["products"])
    return out


def corners_for(pdsid: str, products: dict, label_text: str) -> FrameCorners:
    disp = parse_display_direction(label_text)
    if (disp["vertical_axis"], disp["vertical_direction"]) != ("Line", "Top to Bottom"):
        raise SystemExit(f"{pdsid}: unexpected Display_Direction {disp}")
    f = products[pdsid]["fields"]

    def c(name):
        return (float(f[name + "_LONGITUDE"]), float(f[name + "_LATITUDE"]))

    return FrameCorners(c("UPPER_LEFT"), c("UPPER_RIGHT"), c("LOWER_LEFT"),
                        c("LOWER_RIGHT"), int(f["IMAGE_LINES"]), int(f["LINE_SAMPLES"]))


def window_centred_on(corners: FrameCorners, lon: float, lat: float,
                      n_lines: int, n_samples: int) -> tuple[int, int, dict]:
    """Restated from acquire_real_pair.py: ``(n - 1) / 2`` centring, clamp reported."""
    line, sample = corners.pixel_at(lon, lat)
    want_l = int(round(line - (n_lines - 1) / 2.0))
    want_s = int(round(sample - (n_samples - 1) / 2.0))
    line0 = max(0, min(want_l, corners.lines - n_lines))
    sample0 = max(0, min(want_s, corners.samples - n_samples))
    return line0, sample0, {
        "target_pixel_line": float(line), "target_pixel_sample": float(sample),
        "unclamped_line0": want_l, "unclamped_sample0": want_s,
        "clamped_lines": int(line0 - want_l), "clamped_samples": int(sample0 - want_s),
        "fully_inside_frame": bool(line0 == want_l and sample0 == want_s),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=sorted(TARGETS), required=True)
    args = ap.parse_args()
    spec = TARGETS[args.target]

    src_man = json.loads((DATA / "manifests" / spec["manifest"]).read_text(encoding="utf-8"))
    out_path = DATA / "manifests" / spec["out"]
    if out_path.exists():
        raise SystemExit(f"{out_path.relative_to(ROOT)} exists; an acquisition manifest is "
                         "never overwritten (integrity rule 4)")
    lon, lat = src_man["target_ground_point_lon_lat"]
    products = load_products()
    out_dir = DATA / "processed" / REGION
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"== EXP-007 tier-2 acquisition: {args.target} target "
          f"({lon:.6f}, {lat:.6f}), {N_LINES} x {N_SAMPLES} ==\n")
    entries = []
    for t in src_man["tiles"]:
        pdsid = t["pdsid"]
        label = (ROOT / t["label_path"].replace("\\", "/")).read_text(encoding="utf-8")
        struct = parse_image_structure(label)
        for c in validate_structure(struct):
            print(f"   + {pdsid}: {c}")
        corners = corners_for(pdsid, products, label)
        line0, sample0, detail = window_centred_on(corners, lon, lat, N_LINES, N_SAMPLES)
        if not detail["fully_inside_frame"]:
            print(f"   !! {pdsid}: window CLAMPED by {detail['clamped_lines']:+d} lines")
        byte_start, byte_count = plan_tile_byte_range(struct, line0=line0, n_lines=N_LINES)
        npy = out_dir / f"{pdsid}.geo.l{line0}s{sample0}.n{N_LINES}.tile.npy"
        if npy.exists():
            raise SystemExit(f"{npy.relative_to(ROOT)} exists; refusing to overwrite")
        print(f"{pdsid}: lines [{line0}, {line0 + N_LINES}) samples [{sample0}, "
              f"{sample0 + N_SAMPLES})  {byte_count / 1e6:.1f} MB")

        t0 = time.perf_counter()

        def progress(got, total, _t0=t0):
            if got % (32 << 20) < (8 << 20) or got == total:
                print(f"      {got / 1e6:7.1f} / {total / 1e6:.1f} MB  "
                      f"({time.perf_counter() - _t0:.0f}s)", flush=True)

        raw = fetch_byte_range_chunked(t["image_url"], byte_start, byte_count,
                                       progress=progress)
        digest = hashlib.sha256(raw).hexdigest()
        arr = decode_tile(raw, struct, n_lines=N_LINES, sample0=sample0,
                          n_samples=N_SAMPLES)
        arr = np.asarray(arr, dtype=np.float32)   # 249 MB per tile instead of 498
        np.save(npy, arr)
        finite = np.isfinite(arr)
        print(f"   {arr.shape} float32  sha256={digest[:16]}...  DN median "
              f"{np.nanmedian(arr):.1f}  finite {finite.mean():.4f}  "
              f"({time.perf_counter() - t0:.0f}s)\n")
        entries.append({
            "pdsid": pdsid, "image_url": t["image_url"],
            "img_file_name": struct.file_name,
            "byte_start": byte_start, "byte_count": byte_count, "bytes_sha256": digest,
            "line0": line0, "n_lines": N_LINES, "sample0": sample0, "n_samples": N_SAMPLES,
            "parent_shape_lines_samples": [struct.lines, struct.samples],
            "data_type": struct.data_type, "numpy_dtype": struct.numpy_dtype,
            "stored_dtype": "float32 (decoded int16 DN cast; sentinels are NaN)",
            "scaling_factor": struct.scaling_factor, "unit": struct.unit,
            "index_convention": "array[row=line, column=sample], 0-based",
            "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "fetch": "strict 8 MB chunks with retries (fetch_byte_range_chunked)",
            "region": REGION, "label_path": t["label_path"], "tile_npy": str(npy.relative_to(ROOT)),
            "incidence_deg": t["incidence_deg"], "emission_deg": t["emission_deg"],
            "utc_start": t.get("utc_start"), "ode_map_resolution_m": t.get("ode_map_resolution_m"),
            "selection_method": "GEOMETRY-DRIVEN (REAL-DATA-03, D-033), long window for EXP-007",
            "target_ground_point_lon_lat": [lon, lat],
            "window_detail": detail,
            "index_geometry_sources": GEOMETRY_FILES,
            "index_corners_lon_lat": t["index_corners_lon_lat"],
            "geolocation_status": t["geolocation_status"],
            "azimuth_status": t["azimuth_status"],
        })

    incs = [e["incidence_deg"] for e in entries]
    out_path.write_text(json.dumps({
        "dataset": "LRO NAC (LROC) real image tiles via PDS, long windows",
        "stage": "EXP-007",
        "region": REGION,
        "pair": [e["pdsid"] for e in entries],
        "pair_role": "exp007_long_window",
        "derived_from": spec["manifest"],
        "selection_method": ("Same ground point and corner-map inversion as the recorded "
                             "stage; window lengthened to 12288 lines x full width so "
                             "coarse GSD rungs keep enough pixels (Part 1 section 4)."),
        "target_ground_point_lon_lat": [lon, lat],
        "incidence_deg": incs,
        "incidence_delta_deg": float(max(incs) - min(incs)),
        "chandrayaan2_status": "NOT OBTAINED. No Chandrayaan-2 data is present.",
        "licence": "NASA PDS public domain; credit NASA/GSFC/Arizona State University.",
        "tiles": entries,
    }, indent=2), encoding="utf-8")
    print(f"manifest: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
