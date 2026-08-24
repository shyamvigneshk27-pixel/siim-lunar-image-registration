"""LRO NAC real-data acquisition via the PDS Orbital Data Explorer (ODE).

Verified working 2026-08-24 against the live service. What was checked, so the
next person does not have to rediscover it:

* ODE REST endpoint ``https://oderest.rsl.wustl.edu/live2/`` is open, no
  credentials.
* The identifiers are ``ihid=LRO``, ``iid=LROC``, ``pt=CDRNAC4`` (calibrated) or
  ``pt=EDRNAC4`` (raw). **Not** ``EDRNAC`` -- that returns an error.
* Product records carry ``Incidence_angle``, ``Emission_angle``, ``Phase_angle``
  and ``Map_resolution``, which is what makes illumination-pair selection
  possible from metadata alone.
* Product URLs 302-redirect from ``pds.lroc.im-ldi.com`` to
  ``pds.mcp.nasa.gov``; follow redirects.
* **IMG files serve HTTP 206 range requests** (verified: 2048 bytes pulled from
  a 93 MB product). This is load-bearing: NAC frames reach ~52 000 lines and
  ~93-530 MB, and the demo needs tiles, not archives.

Chandrayaan-2 is NOT available here. ODE indexes Chandrayaan-1 (``CH1-ORB``) but
has no Chandrayaan-2 at all; OHRC / TMC-2 / IIRS live behind an authenticated
Keycloak login at ``pradan.issdc.gov.in``. Nothing in this module can obtain
them, and no multi-modal claim may rest on it.

Nothing here fabricates availability: every function either returns what the
service actually returned or raises.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests

__all__ = [
    "ODE_ENDPOINT",
    "NacProduct",
    "query_nac",
    "find_illumination_pairs",
    "fetch_label",
    "fetch_image_window",
    "write_manifest",
]

ODE_ENDPOINT = "https://oderest.rsl.wustl.edu/live2/"

#: Calibrated NAC. EDRNAC4 is the raw counterpart.
PT_CALIBRATED = "CDRNAC4"
PT_RAW = "EDRNAC4"

_TIMEOUT = 90
_UA = {"User-Agent": "SIIM/0.1 (SIH 26166 research; contact via repository)"}


@dataclass(frozen=True)
class NacProduct:
    """One NAC product, as ODE described it. Fields absent upstream stay None."""

    pdsid: str
    utc_start: str | None
    center_lat: float | None
    center_lon: float | None
    map_resolution_m: float | None
    incidence_deg: float | None
    emission_deg: float | None
    phase_deg: float | None
    image_url: str | None
    label_url: str | None
    image_kbytes: int | None
    #: Everything ODE returned, kept verbatim so nothing is silently dropped.
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def sub_solar_azimuth_proxy(self) -> float | None:
        """Illumination *azimuth* is not in the ODE product summary.

        Returns None deliberately, and this is a real gap rather than an
        oversight. ``Incidence_angle`` constrains Sun *elevation*
        (90 - incidence) but says nothing about azimuth, and the project's
        entire illumination finding is that **azimuth dominates elevation**
        (EXP-001 §11.1, Delta-el -30 deg survived at 0.750 px while Delta-az 45
        deg failed at 325 px).

        Verified 2026-08-24: ODE's product record has no sub-solar azimuth
        field (it offers ``Solar_longitude``, which is the seasonal Ls, not a
        local azimuth), **and the PDS4 CDR labels carry no illumination
        geometry at all** -- an earlier version of this docstring claimed they
        did, and that was wrong. Obtaining azimuth requires deriving the
        sub-solar point from ``UTC_start_time`` plus target coordinates via a
        solar ephemeris.

        Consequence: pairs selected here are **illumination-varied**, not
        **azimuth-controlled**, and must never be described as the latter.
        """
        return None


def _get(params: dict[str, Any]) -> dict:
    r = requests.get(ODE_ENDPOINT, params=params, timeout=_TIMEOUT, headers=_UA)
    r.raise_for_status()
    return r.json().get("ODEResults", {})


def _as_list(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _f(d: dict, key: str) -> float | None:
    v = d.get(key)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_product(p: dict) -> NacProduct:
    img_url = lbl_url = None
    img_kb = None
    for f in _as_list((p.get("Product_files") or {}).get("Product_file")):
        url = str(f.get("URL") or "")
        up = url.upper()
        if up.endswith(".IMG"):
            img_url = url
            try:
                img_kb = int(float(f.get("KBytes")))
            except (TypeError, ValueError):
                img_kb = None
        elif up.endswith((".XML", ".LBL")):
            lbl_url = url
    return NacProduct(
        pdsid=str(p.get("pdsid") or ""),
        utc_start=p.get("UTC_start_time"),
        center_lat=_f(p, "Center_latitude"),
        center_lon=_f(p, "Center_longitude"),
        map_resolution_m=_f(p, "Map_resolution"),
        incidence_deg=_f(p, "Incidence_angle"),
        emission_deg=_f(p, "Emission_angle"),
        phase_deg=_f(p, "Phase_angle"),
        image_url=img_url,
        label_url=lbl_url,
        image_kbytes=img_kb,
        raw=p,
    )


def query_nac(
    *,
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    product_type: str = PT_CALIBRATED,
    limit: int = 50,
) -> list[NacProduct]:
    """Products intersecting a lat/lon box. Longitudes are 0-360 East.

    **The longitude parameters are ``westernlon``/``easternlon``, not
    ``minlon``/``maxlon``.** ODE accepts an unknown parameter silently, returns
    ``Status: Success``, and filters on latitude only -- so ``minlon`` produced
    a plausible-looking result set spanning the entire Moon in longitude
    (measured: 97.9 deg to 296.6 deg for a box requesting 21-22 deg). The
    failure is invisible unless the returned centres are checked against the
    box that was asked for, which is what ``_verify_box`` below does.
    """
    res = _get({
        "query": "product", "results": "fmp", "output": "JSON", "target": "moon",
        "ihid": "LRO", "iid": "LROC", "pt": product_type,
        "minlat": min_lat, "maxlat": max_lat,
        "westernlon": min_lon, "easternlon": max_lon,
        "limit": limit,
    })
    if str(res.get("Status", "")).upper() != "SUCCESS":
        raise RuntimeError(f"ODE query failed: {res.get('Error') or res.get('Status')}")
    prods = [_parse_product(p)
             for p in _as_list((res.get("Products") or {}).get("Product"))]
    _verify_box(prods, min_lat, max_lat, min_lon, max_lon)
    return prods


def _verify_box(prods, min_lat, max_lat, min_lon, max_lon, *, margin_deg=5.0):
    """Fail loudly if the service ignored the spatial filter.

    A silently-unfiltered query is worse than an error: it returns real,
    well-formed products from the wrong hemisphere, and every downstream
    statistic is then computed on the wrong region. NAC footprints are long
    strips so centres legitimately sit somewhat outside the requested box --
    hence the margin -- but not by tens of degrees.
    """
    lons = [p.center_lon for p in prods if p.center_lon is not None]
    lats = [p.center_lat for p in prods if p.center_lat is not None]
    if not lons:
        return
    span_lon = max(lons) - min(lons)
    asked_lon = (max_lon - min_lon) + 2 * margin_deg
    if span_lon > max(asked_lon, 3 * margin_deg):
        raise RuntimeError(
            f"ODE returned products spanning {span_lon:.1f} deg of longitude for a "
            f"{max_lon - min_lon:.1f} deg request -- the spatial filter was ignored. "
            f"Check the longitude parameter names (westernlon/easternlon)."
        )
    if lats:
        span_lat = max(lats) - min(lats)
        if span_lat > max((max_lat - min_lat) + 2 * margin_deg, 3 * margin_deg):
            raise RuntimeError(
                f"ODE returned products spanning {span_lat:.1f} deg of latitude for a "
                f"{max_lat - min_lat:.1f} deg request -- spatial filter ignored."
            )


def parse_footprint(wkt: str | None) -> list[tuple[float, float]]:
    """Vertices of a WKT ``POLYGON ((lon lat, ...))``. Empty list if absent."""
    if not wkt or "EMPTY" in wkt.upper():
        return []
    m = re.search(r"\(\(\s*(.*?)\s*\)\)", wkt, re.S)
    if not m:
        return []
    pts = []
    for part in m.group(1).split(","):
        bits = part.strip().split()
        if len(bits) >= 2:
            try:
                pts.append((float(bits[0]), float(bits[1])))
            except ValueError:
                continue
    return pts


def footprint_overlap(a_wkt: str | None, b_wkt: str | None, *, grid: int = 220) -> float:
    """Intersection-over-union of two footprints, by rasterising a lat/lon grid.

    Approximate by construction and deliberately so: it needs no geometry
    dependency, the footprints are simple quadrilateral-ish strips, and this is
    a *candidate selector* -- the authoritative overlap test is whether
    registration succeeds. Resolution is ~1/grid of the bounding box, so IoU is
    accurate to roughly a percent, which is far more than a shortlist needs.

    This replaces centre proximity, which was a poor proxy: NAC footprints are
    long strips, so two frames can share a centre and barely overlap, or sit
    0.2 deg apart and overlap heavily along-track.
    """
    pa, pb = parse_footprint(a_wkt), parse_footprint(b_wkt)
    if len(pa) < 3 or len(pb) < 3:
        return float("nan")
    import numpy as np
    from matplotlib.path import Path as MplPath

    xs = [p[0] for p in pa + pb]
    ys = [p[1] for p in pa + pb]
    if max(xs) - min(xs) > 180:  # meridian-crossing footprint; not handled
        return float("nan")
    gx = np.linspace(min(xs), max(xs), grid)
    gy = np.linspace(min(ys), max(ys), grid)
    X, Y = np.meshgrid(gx, gy)
    pts = np.column_stack([X.ravel(), Y.ravel()])
    ina = MplPath(pa).contains_points(pts)
    inb = MplPath(pb).contains_points(pts)
    union = (ina | inb).sum()
    return float((ina & inb).sum() / union) if union else 0.0


def find_illumination_pairs(
    products: list[NacProduct],
    *,
    min_incidence_delta_deg: float = 15.0,
    min_footprint_overlap: float = 0.20,
    max_resolution_ratio: float = 1.5,
) -> list[tuple[NacProduct, NacProduct, dict]]:
    """Candidate pairs of the same ground area under different illumination.

    **This is a candidate generator, not a verified-overlap detector.** Centre
    overlap is measured from the ODE ``Footprint_geometry`` polygons by
    rasterised intersection-over-union -- approximate, but a real measurement
    rather than the centre-proximity proxy this originally used. The
    authoritative overlap test remains whether registration succeeds.

    The stronger axis -- Sun **azimuth** difference -- is not available in the
    ODE product summary and must be read from the PDS labels (see
    ``NacProduct.sub_solar_azimuth_proxy``). Until that is done, an
    incidence-selected pair is an *illumination-varied* pair, not a
    *azimuth-varied* one, and must not be described as the latter.
    """
    out = []
    for i in range(len(products)):
        for j in range(i + 1, len(products)):
            a, b = products[i], products[j]
            if None in (a.incidence_deg, b.incidence_deg):
                continue
            d_inc = abs(a.incidence_deg - b.incidence_deg)
            if d_inc < min_incidence_delta_deg:
                continue
            if a.map_resolution_m and b.map_resolution_m:
                lo, hi = sorted((a.map_resolution_m, b.map_resolution_m))
                if lo > 0 and hi / lo > max_resolution_ratio:
                    continue
            iou = footprint_overlap(a.raw.get("Footprint_geometry"),
                                    b.raw.get("Footprint_geometry"))
            if not (iou == iou) or iou < min_footprint_overlap:
                continue
            out.append((a, b, {
                "incidence_delta_deg": d_inc,
                "footprint_iou": iou,
                "resolution_ratio": (max(a.map_resolution_m, b.map_resolution_m)
                                     / min(a.map_resolution_m, b.map_resolution_m))
                if (a.map_resolution_m and b.map_resolution_m) else None,
                "overlap_status": f"footprint IoU {iou:.3f} (rasterised, approximate)",
                "azimuth_delta_deg": None,
                "azimuth_status": (
                    "NOT AVAILABLE. ODE exposes incidence/emission/phase and "
                    "Solar_longitude (seasonal Ls), but no sub-solar AZIMUTH, "
                    "and the PDS4 CDR labels carry no illumination geometry "
                    "either (verified). Azimuth must be derived from "
                    "observation time + target coordinates via a solar "
                    "ephemeris. Until then these are illumination-varied "
                    "pairs, NOT azimuth-controlled pairs."),
            }))
    out.sort(key=lambda t: -t[2]["incidence_delta_deg"])
    return out


def fetch_label(product: NacProduct, dest_dir: Path) -> Path:
    """Download the PDS label (~13 KB). Cheap, and carries the real geometry."""
    if not product.label_url:
        raise ValueError(f"{product.pdsid}: no label URL in the ODE record")
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{product.pdsid}{Path(product.label_url).suffix.lower()}"
    r = requests.get(product.label_url, timeout=_TIMEOUT, headers=_UA, allow_redirects=True)
    r.raise_for_status()
    out.write_bytes(r.content)
    return out


def fetch_image_window(
    product: NacProduct, dest_dir: Path, *, byte_start: int = 0,
    byte_count: int = 8 << 20,
) -> Path:
    """Fetch a byte range of the IMG rather than the whole product.

    NAC frames are 93-530 MB. Range requests are verified to work (HTTP 206),
    which keeps a demo dataset to tens of megabytes instead of gigabytes.

    Returns the path to the partial file. **This is raw bytes, not a decoded
    image**: interpreting it requires the label's ``RECORD_BYTES`` / line
    layout. Decoding is a separate step and is deliberately not done here.
    """
    if not product.image_url:
        raise ValueError(f"{product.pdsid}: no image URL in the ODE record")
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{product.pdsid}.partial.img"
    end = byte_start + byte_count - 1
    headers = {**_UA, "Range": f"bytes={byte_start}-{end}"}
    r = requests.get(product.image_url, timeout=_TIMEOUT, headers=headers,
                     allow_redirects=True)
    if r.status_code not in (200, 206):
        r.raise_for_status()
    if r.status_code == 200:
        # Server ignored the Range header and sent the whole product. Truncate
        # rather than silently writing hundreds of megabytes to disk.
        content = r.content[byte_start:byte_start + byte_count]
    else:
        content = r.content
    out.write_bytes(content)
    return out


def sha256_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def write_manifest(
    entries: list[dict], path: Path, *, note: str = ""
) -> Path:
    """Dataset manifest. Every real-data file the project holds is listed here."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": "LRO NAC (LROC) via PDS ODE",
        "source": ODE_ENDPOINT,
        "authentication": "none required",
        "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "licence": (
            "NASA PDS data are in the public domain; LROC data credit "
            "NASA/GSFC/Arizona State University. Verify before publication."
        ),
        "chandrayaan2_status": (
            "NOT OBTAINED. ODE does not index Chandrayaan-2. OHRC/TMC-2/IIRS "
            "require an authenticated account at pradan.issdc.gov.in. No "
            "multi-modal claim is supported by this manifest."
        ),
        "note": note,
        "n_entries": len(entries),
        "entries": entries,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def product_to_manifest_entry(p: NacProduct, **extra) -> dict:
    d = {k: v for k, v in asdict(p).items() if k != "raw"}
    d.update(extra)
    return d
