"""REAL-DATA-08 acquisition: Mini-RF radar and WAC 100 m row blocks over the windows.

    python scripts/acquire_real_data_08.py

Frozen in ``docs/stages/REAL-DATA-08_multimodal_proxies.md`` Part 1 §1/§3.
Both products are map-projected (equirectangular, equator standard parallel);
a row block covering both recorded windows with a 2 km margin is fetched by
strict chunked byte range, the column window is cut after decoding, and the
block plus its provenance are written. Layouts are read from the archive
labels fetched on 2026-09-04 (values restated here and re-verified against the
label at run time where the label is fetched).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from siim.ingest import fetch_byte_range_chunked  # noqa: E402

DATA = ROOT / "data"
RAW = DATA / "raw" / "proxies"
LAT_MIN, LAT_MAX = 19.40, 20.30          # both windows (19.67 and 20.04 N) + 2 km margin
LON_MIN, LON_MAX = 21.55, 22.45

MINIRF = {
    "product": "LSZ_02951_2S1_EKU_16N022_V1",
    "img": "https://pds-geosciences.wustl.edu/lro/lro-l-mrflro-4-cdr-v1/lromrf_0002/data/sar/02900_02999/level2/lsz_02951_2s1_eku_16n022_v1.img",
    "lbl": "https://pds-geosciences.wustl.edu/lro/lro-l-mrflro-4-cdr-v1/lromrf_0002/data/sar/02900_02999/level2/lsz_02951_2s1_eku_16n022_v1.lbl",
    "manifest": "minirf_lsz_02951_2s1_block_mare_serenitatis.json",
    "credit": "NASA LRO Mini-RF (JHU/APL); PDS Geosciences Node",
    "modality": "S-band (12.6 cm) radar, Stokes S1 total backscattered power, level 2 map-projected",
}
WAC = {
    "product": "WAC_GLOBAL_E300N0450_100M",
    "img": "https://pds.mcp.nasa.gov/data/store/img/lunar_reconnaissance_orbiter/pds4/lroc/lro-l-lroc-5-rdr/LROLRC_2001/DATA/BDR/WAC_GLOBAL/WAC_GLOBAL_E300N0450_100M.IMG",
    "lbl": "https://pds.mcp.nasa.gov/data/store/img/lunar_reconnaissance_orbiter/pds4/lroc/lro-l-lroc-5-rdr/LROLRC_2001/DATA/BDR/WAC_GLOBAL/WAC_GLOBAL_E300N0450_100M.xml",
    "manifest": "wac_global_e300n0450_100m_block_mare_serenitatis.json",
    "credit": "NASA/GSFC/Arizona State University (LROC WAC global morphology mosaic)",
    "modality": "643 nm mono reflectance mosaic, photometrically normalised, 100 m",
    # from the PDS4 label (data/metadata/wac/WAC_GLOBAL_E300N0450_100M.xml)
    "lines": 18194, "samples": 27291, "offset": 109164, "dtype": "<f4",
    # cart:upperleft_corner (x=-50 m, y=1819350 m) is the pixel EDGE: top edge at 60.0 deg,
    # left edge half a pixel west of 0 deg, so sample 0 is centred on lon 0.
    "ppd": 1.0 / 0.0032977886216808585, "lat_top": 60.0, "lon_left": -0.5 * 0.0032977886216808585,
    "missing": np.frombuffer(bytes.fromhex("FF7FFFFB")[::-1], dtype="<f4")[0],
}


def _lbl_value(text: str, key: str) -> str:
    m = re.search(rf"^\s*{key}\s*=\s*([^\s<]+)", text, re.M)
    if not m:
        raise RuntimeError(f"{key} not in label")
    return m.group(1).strip('"')


def fetch_block(name: str, url: str, *, offset: int, lines: int, samples: int, dtype: str,
                ppd_lat: float, ppd_lon: float, lat_top: float, lon_left: float,
                itemsize: int, record_bytes: int) -> tuple[np.ndarray, dict]:
    row0 = max(0, int(np.floor((lat_top - LAT_MAX) * ppd_lat - 0.5)))
    row1 = min(lines, int(np.ceil((lat_top - LAT_MIN) * ppd_lat - 0.5)) + 1)
    col0 = max(0, int(np.floor((LON_MIN - lon_left) * ppd_lon - 0.5)))
    col1 = min(samples, int(np.ceil((LON_MAX - lon_left) * ppd_lon - 0.5)) + 1)
    start = offset + row0 * record_bytes
    count = (row1 - row0) * record_bytes
    print(f"{name}: rows [{row0}, {row1}) cols [{col0}, {col1})  {count / 1e6:.1f} MB", flush=True)
    t0 = time.perf_counter()
    raw = fetch_byte_range_chunked(url, start, count,
                                   progress=lambda g, t: print(f"   {g / 1e6:.1f}/{t / 1e6:.1f} MB", flush=True)
                                   if g == t or g % (32 << 20) < (8 << 20) else None)
    digest = hashlib.sha256(raw).hexdigest()
    arr = np.frombuffer(raw, dtype=dtype).reshape(row1 - row0, record_bytes // itemsize)[:, col0:col1]
    print(f"   {arr.shape} sha256={digest[:16]}... ({time.perf_counter() - t0:.0f}s)")
    return np.array(arr, dtype=np.float32), {
        "row0": row0, "row1_exclusive": row1, "col0": col0, "col1_exclusive": col1,
        "byte_start": start, "byte_count": count, "bytes_sha256": digest,
        "grid": {"ppd_lat": ppd_lat, "ppd_lon": ppd_lon, "lat_top_deg": lat_top, "lon_left_deg": lon_left,
                 "projection": "equirectangular, equator standard parallel, pixel-registered"},
    }


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for spec in (MINIRF, WAC):
        man_path = DATA / "manifests" / spec["manifest"]
        if man_path.exists():
            print(f"{man_path.name} exists; skipping (integrity rule 4)")
            continue
        if spec is MINIRF:
            lbl = requests.get(spec["lbl"], timeout=120).text
            (DATA / "metadata" / "minirf").mkdir(parents=True, exist_ok=True)
            (DATA / "metadata" / "minirf" / f"{spec['product']}.lbl").write_text(lbl, encoding="utf-8")
            lines = int(_lbl_value(lbl, "LINES")); samples = int(_lbl_value(lbl, "LINE_SAMPLES"))
            rb = int(_lbl_value(lbl, "RECORD_BYTES")); bits = int(_lbl_value(lbl, "SAMPLE_BITS"))
            assert _lbl_value(lbl, "SAMPLE_TYPE") == "PC_REAL" and bits == 32
            ppd = float(_lbl_value(lbl, "MAP_RESOLUTION"))
            # The PROJECTION OFFSETS define the grid (ISIS/PDS: 0-based line =
            # LPO - lat*ppd; 0-based sample = SPO + (lon - CENTER_LON)*ppd). The
            # label's MAXIMUM_LATITUDE / WESTERNMOST_LONGITUDE summaries disagree
            # with them by ~1.3 px (measured 2026-09-04: 24.017439 vs 24.018066
            # for the top edge). The offsets are used; the summaries are recorded.
            lpo = float(_lbl_value(lbl, "LINE_PROJECTION_OFFSET"))
            spo = float(_lbl_value(lbl, "SAMPLE_PROJECTION_OFFSET"))
            clon = float(_lbl_value(lbl, "CENTER_LONGITUDE"))
            lat_top = (lpo + 0.5) / ppd                      # top EDGE
            lon_left = clon - (spo + 0.5) / ppd              # left EDGE
            summary = {"MAXIMUM_LATITUDE": float(_lbl_value(lbl, "MAXIMUM_LATITUDE")),
                       "WESTERNMOST_LONGITUDE": float(_lbl_value(lbl, "WESTERNMOST_LONGITUDE")),
                       "top_edge_from_LPO": lat_top, "left_edge_from_SPO": lon_left,
                       "disagreement_px": [(lat_top - float(_lbl_value(lbl, "MAXIMUM_LATITUDE"))) * ppd,
                                           (float(_lbl_value(lbl, "WESTERNMOST_LONGITUDE")) - lon_left) * ppd]}
            arr, prov = fetch_block(spec["product"], spec["img"], offset=0, lines=lines, samples=samples,
                                    dtype="<f4", ppd_lat=ppd, ppd_lon=ppd, lat_top=lat_top,
                                    lon_left=lon_left, itemsize=4, record_bytes=rb)
            extra = {"label_path": f"data/metadata/minirf/{spec['product']}.lbl",
                     "grid_source": "LINE/SAMPLE_PROJECTION_OFFSET (authoritative); summaries recorded",
                     "label_summary_vs_offsets": summary,
                     "radar_incidence_deg": float(_lbl_value(lbl, "INCIDENCE_ANGLE")),
                     "unit": "backscatter power (linear); log-compress before matching"}
        else:
            arr, prov = fetch_block(spec["product"], spec["img"], offset=spec["offset"], lines=spec["lines"],
                                    samples=spec["samples"], dtype=spec["dtype"], ppd_lat=spec["ppd"],
                                    ppd_lon=spec["ppd"], lat_top=spec["lat_top"], lon_left=spec["lon_left"],
                                    itemsize=4, record_bytes=spec["samples"] * 4)
            missing = arr == np.float32(spec["missing"])
            arr = np.where(missing, np.nan, arr)
            extra = {"label_path": "data/metadata/wac/WAC_GLOBAL_E300N0450_100M.xml",
                     "missing_constant_hex": "FF7FFFFB", "missing_fraction": float(missing.mean()),
                     "unit": "normalised reflectance (mosaic)"}
        npy = RAW / f"{spec['product']}.rows{prov['row0']}_{prov['row1_exclusive']}.npy"
        np.save(npy, arr)
        man_path.write_text(json.dumps({
            "stage": "REAL-DATA-08", "product": spec["product"], "modality": spec["modality"],
            "source_url": spec["img"], "label_url": spec["lbl"], "credit": spec["credit"],
            "block_npy": str(npy.relative_to(ROOT)), "window_lat": [LAT_MIN, LAT_MAX],
            "window_lon": [LON_MIN, LON_MAX],
            "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **prov, **extra,
        }, indent=2), encoding="utf-8")
        print(f"manifest: {man_path.relative_to(ROOT)}\n")


if __name__ == "__main__":
    main()
