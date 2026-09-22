"""Report which benchmark requirements the data on disk can actually satisfy.

Reads the Chandrayaan-2 PDS4 labels under a data directory, builds product
manifests from what the labels themselves report, and prints which pairings
are possible and what is missing.

This is a **readiness check, not an ingestion stage**. It reads labels only,
never image bytes, so it is fast and safe to run against tens of gigabytes.
Full Chandrayaan-2 ingestion is pre-registered separately as REAL-DATA-09.

    python scripts/assess_data_readiness.py
    python scripts/assess_data_readiness.py --data-dir data/realdata --json out.json

Exit status is 0 when the report was produced. It is **not** an assertion that
the data is adequate: read the shopping list.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from siim.benchmark import assess_products  # noqa: E402
from siim.benchmark.manifest import ProductManifest  # noqa: E402

#: Which ISSDC instrument token maps to which instrument name.
_INSTRUMENT_BY_TOKEN = {"ohr": "OHRC", "tmc": "TMC-2", "iir": "IIRS"}


def _text(xml: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}[^>]*>([^<]+)</{tag}>", xml)
    return m.group(1).strip() if m else None


def _float(xml: str, tag: str) -> float | None:
    v = _text(xml, tag)
    try:
        return float(v) if v is not None else None
    except ValueError:
        return None


def _corners(xml: str) -> tuple[tuple[float, float], ...] | None:
    out: list[tuple[float, float]] = []
    for corner in ("upper_left", "upper_right", "lower_left", "lower_right"):
        lat = _float(xml, f"isda:{corner}_latitude")
        lon = _float(xml, f"isda:{corner}_longitude")
        if lat is None or lon is None:
            return None
        out.append((lat, lon))
    return tuple(out)


def product_from_label(path: Path) -> ProductManifest | None:
    """Build a manifest from one PDS4 label, or ``None`` if it is not one."""
    try:
        xml = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    if "isda" not in xml and "Product_Observational" not in xml:
        return None

    token = path.name.split("_")[1] if "_" in path.name else ""
    instrument = _INSTRUMENT_BY_TOKEN.get(token)
    if instrument is None:
        return None

    # Geometry grids (``_g_grd_``) accompany an image product; they are a
    # lat/lon lattice, not an image, and counting them as products would
    # inflate what the archive appears to supply.
    if "_g_grd_" in path.name:
        return None

    elements = [int(x) for x in re.findall(r"<elements>(\d+)</elements>", xml)]
    shape = (elements[0], elements[1]) if len(elements) >= 2 else None

    return ProductManifest(
        product_id=path.stem,
        instrument=instrument,
        corpus_class="CHANDRAYAAN2",
        processing_level=(_text(xml, "processing_level") or "unknown").lower(),
        path=str(path),
        shape=shape,
        data_type=_text(xml, "data_type"),
        pixel_resolution_m=_float(xml, "isda:pixel_resolution"),
        spacecraft_altitude_km=_float(xml, "isda:spacecraft_altitude"),
        sun_azimuth_deg=_float(xml, "isda:sun_azimuth"),
        sun_elevation_deg=_float(xml, "isda:sun_elevation"),
        solar_incidence_deg=_float(xml, "isda:solar_incidence"),
        corners_lat_lon=_corners(xml),
        orbit_number=(
            int(_float(xml, "isda:imaging_orbit_number"))
            if _float(xml, "isda:imaging_orbit_number") is not None else None
        ),
        acquisition_time=_text(xml, "start_date_time"),
        notes=_text(xml, "isda:area") or "",
    )


def scan(data_dir: Path) -> list[ProductManifest]:
    """Find every data-product label under ``data_dir``.

    Browse labels are skipped: accepting one in place of a data label has
    already cost this project four products (ERROR_LEDGER E-022).
    """
    found: dict[str, ProductManifest] = {}
    for xml_path in sorted(data_dir.rglob("*.xml")):
        parts = {p.lower() for p in xml_path.parts}
        if "browse" in parts or "miscellaneous" in parts:
            continue
        product = product_from_label(xml_path)
        if product is not None:
            found.setdefault(product.product_id, product)
    return list(found.values())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default="data/realdata",
                    help="directory to scan for PDS4 labels")
    ap.add_argument("--json", default=None, help="write the report here")
    args = ap.parse_args(argv)

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"data directory {data_dir} does not exist", file=sys.stderr)
        print("Nothing to assess. See 02_DATASET_ACQUISITION_PLAN.md.")
        return 0

    products = scan(data_dir)
    report = assess_products(products)

    print(f"Scanned {data_dir}: {len(products)} product label(s)")
    for p in sorted(products, key=lambda x: (x.instrument, x.product_id)):
        res = f"{p.pixel_resolution_m:g} m" if p.pixel_resolution_m else "unknown"
        inc = (f"{p.solar_incidence_deg:.1f} deg"
               if p.solar_incidence_deg is not None else "unknown")
        lat = p.latitude_span()
        where = f"lat {lat[0]:.2f}..{lat[1]:.2f}" if lat else "no corners"
        print(f"  {p.instrument:<6} {p.product_id[:52]:<52} "
              f"{res:>8}  incidence {inc:>10}  {where}")

    print(f"\nInstruments present: {', '.join(report.instruments_present) or 'none'}")
    print(f"Requirements satisfied: {len(report.satisfied)} of "
          f"{len(report.statuses)}\n")

    for status in report.satisfied:
        print(f"  SATISFIED  {status.requirement.requirement_id}: "
              f"{status.requirement.title}")
    if report.satisfied:
        print()

    print("What to acquire, highest value first:")
    for line in report.shopping_list():
        print(f"  {line}")

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "data_dir": str(data_dir),
            "products": [p.to_dict() for p in products],
            "report": report.as_dict(),
        }
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
            fh.write("\n")
        print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
