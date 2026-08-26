"""REAL-DATA-02 step 1: pull named corner geometry for the acquired NAC frames.

Run:  python scripts/fetch_index_geometry.py

Why a new acquisition was necessary
-----------------------------------
REAL-DATA-01 could not say whether its two tiles shared ground. Auditing what
was on disk showed why, and the gap is in the products themselves:

* the PDS4 ``Product_Observational`` labels in ``data/metadata/`` carry **no**
  ``Cartography``, no ``Geometry``, no corner coordinates -- only time, mission
  parameters and the array structure;
* the 5064-byte PDS3 attached header inside each ``.IMG`` carries **no**
  geometry keywords either (checked byte-for-byte against a live range fetch);
* the ODE product record carries ``Footprint_geometry``, a WKT polygon -- but
  its **vertex order is undocumented**, so it cannot say which corner is line
  0. Getting that backwards mirrors the tile top-to-bottom, which is precisely
  the unresolved H1/H2 ambiguity of REAL-DATA-01 §4.5.

ODE names its own source: ``Footprint_souce = "PDS Archive Index Table"``. That
table is in the archive, one directory up from the data, and its columns are
named ``UPPER_LEFT_LATITUDE`` ... ``LOWER_RIGHT_LONGITUDE`` -- corners with
identities rather than a bare ring. It also carries ``NORTH_AZIMUTH``,
``ORBIT_NODE`` and ``LRO_FLIGHT_DIRECTION``, which cross-check the corner
naming, and ``SUB_SOLAR_AZIMUTH``, which REAL-DATA-01 recorded as unavailable
(E-020).

Cost: the tables are 18-54 MB, but they are ``FIXED_LENGTH`` and sorted by
``PRODUCT_ID``, so each product costs one 31 KB label plus ~16 range requests
of one record. Roughly 130 KB total, no image bytes. This is the minimal
acquisition that answers the question.

Output: ``data/manifests/real_pair_index_geometry.json`` -- a NEW artefact.
Nothing existing is modified or overwritten; the script refuses to run if the
output already exists unless ``--force-refetch`` is given, and even then it
writes a timestamped sibling rather than replacing the original.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import requests  # noqa: E402

from siim.ingest.index_table import (  # noqa: E402
    find_row_by_product_id,
    parse_index_label,
)
from siim.ingest.lro_nac import ODE_ENDPOINT, _parse_product  # noqa: E402

DATA = ROOT / "data"
OUT = DATA / "manifests" / "real_pair_index_geometry.json"

_UA = {"User-Agent": "SIIM/0.1 (SIH 26166 research; contact via repository)"}
_TIMEOUT = 120
_ARCHIVE = "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-3-CDR-V1.0"

#: The four products acquired in REAL-DATA-01, with the volume each was
#: fetched from. The volume is read straight out of the existing manifests'
#: ``image_url`` rather than guessed -- see :func:`volumes_from_manifests`.
MANIFESTS = [
    "real_pair_usable_manifest.json",
    "real_pair_usableH2_manifest.json",
    "real_pair_terminator_manifest.json",
]

#: Everything read out of the index row. Corner columns first, because they are
#: the point; the rest are the cross-checks and the provenance.
FIELDS = [
    "PRODUCT_ID",
    "UPPER_LEFT_LATITUDE", "UPPER_LEFT_LONGITUDE",
    "UPPER_RIGHT_LATITUDE", "UPPER_RIGHT_LONGITUDE",
    "LOWER_LEFT_LATITUDE", "LOWER_LEFT_LONGITUDE",
    "LOWER_RIGHT_LATITUDE", "LOWER_RIGHT_LONGITUDE",
    "CENTER_LATITUDE", "CENTER_LONGITUDE",
    "NORTH_AZIMUTH", "SUB_SOLAR_AZIMUTH",
    "SUB_SOLAR_LATITUDE", "SUB_SOLAR_LONGITUDE",
    "SUB_SPACECRAFT_LATITUDE", "SUB_SPACECRAFT_LONGITUDE",
    "ORBIT_NODE", "LRO_FLIGHT_DIRECTION", "SLEW_ANGLE",
    "IMAGE_LINES", "LINE_SAMPLES",
    "SCALED_PIXEL_WIDTH", "SCALED_PIXEL_HEIGHT", "RESOLUTION",
    "INCIDENCE_ANGLE", "EMISSION_ANGLE", "PHASE_ANGLE",
    "NAC_FRAME_ID", "ORBIT_NUMBER", "START_TIME", "STOP_TIME",
    "FILE_SPECIFICATION_NAME",
]


def _get(url: str, *, byte_range: tuple[int, int] | None = None,
         tries: int = 5) -> requests.Response:
    """GET with retries. The archive drops keep-alive connections between
    range requests often enough that a bare ``requests.get`` fails a
    16-probe binary search roughly every other run; that is a transport
    flake, not a data problem, so it is retried rather than reported."""
    headers = dict(_UA)
    if byte_range is not None:
        headers["Range"] = f"bytes={byte_range[0]}-{byte_range[1]}"
    last: Exception | None = None
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=headers, timeout=_TIMEOUT)
            r.raise_for_status()
            if byte_range is not None:
                want = byte_range[1] - byte_range[0] + 1
                if len(r.content) != want:
                    raise RuntimeError(
                        f"range request returned {len(r.content)} B, asked for "
                        f"{want} B ({r.headers.get('Content-Range')})")
            return r
        except Exception as exc:  # noqa: BLE001 - retried, then re-raised
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed after {tries} attempts: {last}")


def volumes_from_manifests() -> dict[str, dict[str, str]]:
    """``pdsid -> {volume, img_url, product_id}``, read from the existing
    manifests. The volume is a path segment of the URL that was actually
    fetched in REAL-DATA-01, so the index table consulted here is guaranteed
    to be the one describing the bytes on disk."""
    found: dict[str, dict[str, str]] = {}
    for name in MANIFESTS:
        path = DATA / "manifests" / name
        if not path.exists():
            raise SystemExit(f"missing manifest {path}; run REAL-DATA-01 first")
        man = json.loads(path.read_text(encoding="utf-8"))
        for tile in man["tiles"]:
            url = tile["image_url"]
            if not url.startswith(_ARCHIVE + "/"):
                raise SystemExit(
                    f"unexpected archive root in {url!r}; refusing to guess "
                    "the volume layout")
            volume = url[len(_ARCHIVE) + 1:].split("/", 1)[0]
            entry = {
                "volume": volume,
                "img_url": url,
                "product_id": Path(tile["img_file_name"]).stem,
                "source_manifest": name,
            }
            prior = found.get(tile["pdsid"])
            if prior and prior["volume"] != volume:
                raise SystemExit(
                    f"{tile['pdsid']} appears under two volumes "
                    f"({prior['volume']}, {volume}); not reconcilable here")
            found.setdefault(tile["pdsid"], entry)
    return found


def volumes_from_ode(pdsids: list[str]) -> dict[str, dict[str, str]]:
    """``pdsid -> {volume, img_url, product_id}``, resolved live from ODE.

    Used for a product this project has never acquired, which therefore has no
    manifest to read the volume out of. The volume is taken from the ``.IMG``
    URL ODE returns, so the index table consulted is the one belonging to the
    same archive volume as the data -- never guessed from the product id, whose
    numbering does not encode the volume.
    """
    found: dict[str, dict[str, str]] = {}
    for pdsid in pdsids:
        r = requests.get(ODE_ENDPOINT, timeout=_TIMEOUT, headers=_UA, params={
            "query": "product", "results": "fmp", "output": "JSON",
            "target": "moon", "ihid": "LRO", "iid": "LROC",
            "pt": "CDRNAC4", "pdsid": pdsid,
        })
        r.raise_for_status()
        prods = r.json().get("ODEResults", {}).get("Products")
        if isinstance(prods, str) or not prods:
            raise SystemExit(f"ODE returned no product for pdsid={pdsid!r}")
        rec = prods["Product"]
        rec = rec[0] if isinstance(rec, list) else rec
        prod = _parse_product(rec)
        if not prod.image_url or not prod.image_url.startswith(_ARCHIVE + "/"):
            raise SystemExit(
                f"{pdsid}: unexpected archive root in {prod.image_url!r}; "
                "refusing to guess the volume layout")
        found[pdsid] = {
            "volume": prod.image_url[len(_ARCHIVE) + 1:].split("/", 1)[0],
            "img_url": prod.image_url,
            "product_id": Path(prod.image_url).stem,
            "source_manifest": "(none -- resolved live from ODE)",
        }
    return found


def fetch_row(volume: str, product_id: str) -> dict:
    base = f"{_ARCHIVE}/{volume}/INDEX/"
    lbl_url, tab_url = base + "INDEX.LBL", base + "INDEX.TAB"
    lbl = _get(lbl_url).text
    spec = parse_index_label(lbl)
    n_requests = 0

    def read_record(i: int) -> str:
        nonlocal n_requests
        n_requests += 1
        start = i * spec.record_bytes
        r = _get(tab_url, byte_range=(start, start + spec.record_bytes - 1))
        return r.content.decode("ascii", "replace")

    idx, row = find_row_by_product_id(spec, product_id, read_record)
    fields = {k: spec.field(row, k) for k in FIELDS if k in spec.columns}
    missing = [k for k in FIELDS if k not in spec.columns]
    return {
        "index_lbl_url": lbl_url,
        "index_tab_url": tab_url,
        "index_lbl_sha256": hashlib.sha256(lbl.encode("utf-8")).hexdigest(),
        "index_lbl_declared_md5": None,
        "record_bytes": spec.record_bytes,
        "file_records": spec.file_records,
        "row_index_0based": idx,
        "row_byte_range": [idx * spec.record_bytes,
                           idx * spec.record_bytes + spec.record_bytes - 1],
        "row_sha256": hashlib.sha256(row.encode("ascii")).hexdigest(),
        "raw_row": row,
        "range_requests_used": n_requests,
        "fields": fields,
        "columns_requested_but_absent": missing,
        "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-refetch", action="store_true",
                    help="re-fetch even if the manifest exists; the existing "
                         "file is kept and the new one is written alongside "
                         "it with a timestamp (integrity rule 4)")
    ap.add_argument("--pdsids", default=None,
                    help="comma-separated product ids to fetch instead of the "
                         "ones in the existing tile manifests. Volumes are "
                         "resolved live from ODE. Requires --out")
    ap.add_argument("--out", default=None,
                    help="output manifest filename under data/manifests/. "
                         "A NEW name; an existing file is never overwritten")
    args = ap.parse_args()

    if args.pdsids and not args.out:
        raise SystemExit("--pdsids requires --out: an explicit product set "
                         "must not be written over the default manifest")

    OUT_PATH = (DATA / "manifests" / args.out) if args.out else OUT
    out = OUT_PATH
    if OUT_PATH.exists():
        if not args.force_refetch:
            print(f"{OUT_PATH.relative_to(ROOT)} already exists; nothing "
                  "fetched.\nPass --force-refetch to acquire again (the "
                  "existing file is never overwritten).")
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = OUT_PATH.with_name(f"{OUT_PATH.stem}.{stamp}.json")

    if args.pdsids:
        targets = volumes_from_ode(
            [x.strip() for x in args.pdsids.split(",") if x.strip()])
    else:
        targets = volumes_from_manifests()
    print(f"== REAL-DATA-02: archive index geometry for "
          f"{len(targets)} products ==\n")

    records: dict[str, dict] = {}
    for pdsid, info in sorted(targets.items()):
        print(f"{pdsid}  (volume {info['volume']}, product {info['product_id']})")
        rec = fetch_row(info["volume"], info["product_id"])
        rec.update(info)
        records[pdsid] = rec
        f = rec["fields"]
        print(f"   row {rec['row_index_0based']} of {rec['file_records']} "
              f"in {rec['range_requests_used']} range requests")
        print(f"   UL ({f.get('UPPER_LEFT_LATITUDE')}, "
              f"{f.get('UPPER_LEFT_LONGITUDE')})   "
              f"UR ({f.get('UPPER_RIGHT_LATITUDE')}, "
              f"{f.get('UPPER_RIGHT_LONGITUDE')})")
        print(f"   LL ({f.get('LOWER_LEFT_LATITUDE')}, "
              f"{f.get('LOWER_LEFT_LONGITUDE')})   "
              f"LR ({f.get('LOWER_RIGHT_LATITUDE')}, "
              f"{f.get('LOWER_RIGHT_LONGITUDE')})")
        print(f"   north_azimuth {f.get('NORTH_AZIMUTH')}  "
              f"sub_solar_azimuth {f.get('SUB_SOLAR_AZIMUTH')}  "
              f"node {f.get('ORBIT_NODE')}  "
              f"flight_dir {f.get('LRO_FLIGHT_DIRECTION')}")
        print(f"   lines x samples {f.get('IMAGE_LINES')} x "
              f"{f.get('LINE_SAMPLES')}   scaled px "
              f"{f.get('SCALED_PIXEL_WIDTH')} x {f.get('SCALED_PIXEL_HEIGHT')} m"
              f"   resolution {f.get('RESOLUTION')} m\n")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "stage": "REAL-DATA-02",
        "purpose": (
            "Named image-corner coordinates for the REAL-DATA-01 NAC frames, "
            "so tile ground footprints can be computed independently of the "
            "feature matcher."),
        "source": (
            "PDS Archive Index Table (per-volume INDEX.TAB + INDEX.LBL) under "
            f"{_ARCHIVE}. This is the source ODE itself cites in "
            "Footprint_souce."),
        "geometry_absent_from": [
            "PDS4 Product_Observational label (no Cartography/Geometry class)",
            "PDS3 attached header inside the .IMG (no geometry keywords)",
        ],
        "corner_naming_assumption": (
            "UPPER_* is taken to mean the first image LINE and LOWER_* the "
            "last, following the PDS image convention that line 1 is the top "
            "row. This is an ASSUMPTION about the column semantics; it is "
            "cross-checked against NORTH_AZIMUTH, ORBIT_NODE and "
            "LRO_FLIGHT_DIRECTION in scripts/verify_tile_overlap.py and the "
            "check is reported with the result."),
        "licence": ("NASA PDS public domain; credit NASA/GSFC/Arizona State "
                    "University."),
        "chandrayaan2_status": (
            "NOT OBTAINED. Nothing here involves Chandrayaan-2 and no "
            "multi-modal claim rests on it."),
        "products": records,
    }, indent=2), encoding="utf-8")
    print(f"written: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
