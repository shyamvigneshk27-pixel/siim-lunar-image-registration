"""Acquire a small, representative LRO NAC subset and write the dataset manifest.

Deliberately small: labels for every candidate (~13 KB each), image bytes only
for the selected demo pair, via HTTP range requests. NAC frames are 93-530 MB
and the project does not need whole archives to demonstrate registration.

Chandrayaan-2 (OHRC / TMC-2 / IIRS) is NOT acquired here and cannot be: it
requires an authenticated ISSDC account. The manifest records that explicitly so
no downstream reader can mistake this for multi-modal data.

Run:  python scripts/acquire_lro_nac.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siim.ingest.lro_nac import (  # noqa: E402
    fetch_label,
    find_illumination_pairs,
    product_to_manifest_entry,
    query_nac,
    sha256_of,
    write_manifest,
)

DATA = ROOT / "data"

#: Regions of interest. Chosen for terrain variety and heavy NAC coverage, not
#: for any expected result. Longitudes are 0-360 East.
REGIONS = [
    {"name": "apollo15_hadley", "min_lat": 25.5, "max_lat": 26.5,
     "min_lon": 2.5, "max_lon": 3.5, "terrain": "mare/highland boundary"},
    {"name": "mare_serenitatis", "min_lat": 19.0, "max_lat": 20.0,
     "min_lon": 21.0, "max_lon": 22.0, "terrain": "mare (low texture)"},
    {"name": "tycho_highlands", "min_lat": -43.8, "max_lat": -42.8,
     "min_lon": 348.5, "max_lon": 349.5, "terrain": "highlands / crater"},
]


def main() -> None:
    entries: list[dict] = []
    all_products = {}
    pair_report = []

    print("== LRO NAC acquisition (PDS ODE, no credentials) ==\n")
    for reg in REGIONS:
        name = reg["name"]
        try:
            prods = query_nac(
                min_lat=reg["min_lat"], max_lat=reg["max_lat"],
                min_lon=reg["min_lon"], max_lon=reg["max_lon"], limit=40,
            )
        except Exception as e:  # network / service failure is a fact to record
            print(f"  {name:20s} QUERY FAILED: {type(e).__name__}: {e}")
            pair_report.append({"region": name, "status": f"query failed: {e}"})
            continue

        inc = [p.incidence_deg for p in prods if p.incidence_deg is not None]
        print(f"  {name:20s} {len(prods):3d} products | incidence "
              f"{min(inc):.1f}-{max(inc):.1f} deg" if inc else
              f"  {name:20s} {len(prods):3d} products | no incidence metadata")

        pairs = find_illumination_pairs(prods)
        print(f"  {'':20s} {len(pairs):3d} candidate illumination pairs "
              f"(footprint IoU >= 0.20; azimuth delta NOT available)")
        if pairs:
            a, b, m = pairs[0]
            print(f"  {'':20s} best: {a.pdsid} vs {b.pdsid}  "
                  f"d_incidence={m['incidence_delta_deg']:.1f} deg  "
                  f"IoU={m['footprint_iou']:.3f}")
        all_products[name] = prods
        pair_report.append({
            "region": name, "terrain": reg["terrain"],
            "n_products": len(prods), "n_candidate_pairs": len(pairs),
            "incidence_range_deg": [min(inc), max(inc)] if inc else None,
            "best_pair": ([pairs[0][0].pdsid, pairs[0][1].pdsid, pairs[0][2]]
                          if pairs else None),
        })

    # -- labels for the top candidates only. Cheap (~2-13 KB). NOTE: verified
    #    2026-08-24 that these PDS4 labels do NOT carry illumination geometry;
    #    they are kept for provenance and product identity, not for Sun angles. --
    print("\n== fetching PDS labels for top candidates ==")
    n_lab = 0
    for name, prods in all_products.items():
        pairs = find_illumination_pairs(prods)
        for a, b, _ in pairs[:1]:
            for p in (a, b):
                try:
                    lp = fetch_label(p, DATA / "metadata" / name)
                    entries.append(product_to_manifest_entry(
                        p, region=name, local_label=str(lp.relative_to(ROOT)),
                        label_sha256=sha256_of(lp),
                        local_image=None,
                        image_status="not downloaded (range fetch on demand)",
                    ))
                    n_lab += 1
                    print(f"  {p.pdsid:22s} label {lp.stat().st_size:6d} B -> "
                          f"{lp.relative_to(ROOT)}")
                except Exception as e:
                    print(f"  {p.pdsid:22s} LABEL FAILED: {type(e).__name__}: {e}")

    mpath = write_manifest(
        entries, DATA / "manifests" / "lro_nac_manifest.json",
        note=("Labels only; image bytes fetched on demand via HTTP range "
              "requests. Pairs are selected by incidence difference AND "
              "measured footprint IoU (rasterised, approximate). Sun-AZIMUTH "
              "difference is NOT available from ODE or from these labels and "
              "must be derived from observation time via a solar ephemeris, "
              "so these are illumination-varied but NOT azimuth-controlled "
              "pairs."),
    )
    (DATA / "manifests" / "region_survey.json").write_text(
        json.dumps({"regions": pair_report}, indent=2), encoding="utf-8")

    print(f"\nmanifest: {mpath.relative_to(ROOT)}  ({n_lab} labels)")
    print(f"survey  : {(DATA/'manifests'/'region_survey.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
