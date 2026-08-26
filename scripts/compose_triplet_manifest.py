"""Compose a loop-closure triplet manifest from acquisitions that already exist.

Run:  python scripts/compose_triplet_manifest.py --from A.json,B.json --out T.json

A triplet manifest is **not** an acquisition. It lists tiles that were acquired
by ``acquire_real_pair.py``, unchanged, so that a three-image loop can be
verified and registered without re-fetching 41 MB per tile or cutting a second
copy of a tile that already exists.

Why compose rather than acquire all three at once
-------------------------------------------------
The pair A/B was cut on the centroid of *their* shared footprint. Acquiring a
triplet in one pass would centre all three on the centroid of the *three*-frame
intersection, which is a different ground point -- so A and B would be
different tiles from the ones the primary registration used, and the loop's
A->B edge would no longer be the experiment it is meant to corroborate. Cutting
C on the pair's existing target point keeps A->B identical to the primary run
and adds exactly one new tile. That is also the minimal acquisition.

What this script guarantees, because a composed manifest is easy to get wrong:

* every tile entry is copied **verbatim** from its source manifest -- no field
  is recomputed, so provenance, byte ranges and SHA-256 cannot drift;
* the tile files it names must exist on disk;
* the tiles must be **distinct** -- E-025 was three "different" conditions that
  were one file, and a loop built from a repeated tile closes perfectly and
  means nothing;
* every tile must have been cut on the **same ground point**, or the loop is
  not a loop;
* the output must be a new path.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

#: Tolerance on the target ground point, in degrees. Tiles cut on points
#: further apart than this were not aimed at the same place, and composing
#: them into a "loop" would be a fiction. 1e-6 deg is ~3 cm.
TARGET_TOLERANCE_DEG = 1e-6


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="sources", required=True,
                    help="comma-separated source manifest names under "
                         "data/manifests/")
    ap.add_argument("--products", default=None,
                    help="comma-separated product ids to include, in loop "
                         "order. Default: every tile in the sources, in order")
    ap.add_argument("--out", required=True,
                    help="output manifest name under data/manifests/")
    ap.add_argument("--role", default="loop_closure_triplet")
    args = ap.parse_args()

    out_path = DATA / "manifests" / args.out
    if out_path.exists():
        raise SystemExit(
            f"{out_path.relative_to(ROOT)} already exists; choose a new name "
            "(integrity rule 4)")

    by_pdsid: dict[str, dict] = {}
    order: list[str] = []
    sources: list[str] = []
    for name in args.sources.split(","):
        path = DATA / "manifests" / name.strip()
        if not path.exists():
            raise SystemExit(f"missing source manifest {path}")
        man = json.loads(path.read_text(encoding="utf-8"))
        sources.append(name.strip())
        for tile in man["tiles"]:
            pid = tile["pdsid"]
            if pid in by_pdsid and by_pdsid[pid] != tile:
                raise SystemExit(
                    f"{pid} appears in two sources with different tile "
                    "entries; not reconciled here")
            if pid not in by_pdsid:
                order.append(pid)
            by_pdsid[pid] = tile

    if args.products:
        order = [p.strip() for p in args.products.split(",") if p.strip()]
        missing = [p for p in order if p not in by_pdsid]
        if missing:
            raise SystemExit(f"not in the sources: {', '.join(missing)}")
    if len(order) != 3:
        raise SystemExit(
            f"a loop-closure triplet needs exactly three products, got "
            f"{len(order)}: {', '.join(order)}")

    tiles = [by_pdsid[p] for p in order]

    # -- the checks, in the order in which getting one wrong is worst --
    hashes = [t["bytes_sha256"] for t in tiles]
    if len(set(hashes)) != 3:
        raise SystemExit(
            "the three tiles are not distinct by SHA-256. A loop built from a "
            "repeated tile closes exactly and means nothing (E-025).")

    for t in tiles:
        npy = ROOT / t["tile_npy"]
        if not npy.exists():
            raise SystemExit(f"missing tile file {npy.relative_to(ROOT)}")

    targets = [t.get("target_ground_point_lon_lat") for t in tiles]
    if any(x is None for x in targets):
        raise SystemExit(
            "every tile must record target_ground_point_lon_lat; a tile from "
            "the pre-REAL-DATA-03 footprint-latitude path cannot be composed "
            "into a loop, because it was not aimed at a stated ground point")
    lon0, lat0 = targets[0]
    for t, (lon, lat) in zip(tiles, targets):
        if (abs(lon - lon0) > TARGET_TOLERANCE_DEG
                or abs(lat - lat0) > TARGET_TOLERANCE_DEG):
            raise SystemExit(
                f"{t['pdsid']} was cut on ({lon:.6f}, {lat:.6f}) but the first "
                f"tile on ({lon0:.6f}, {lat0:.6f}); these tiles were not aimed "
                "at the same ground point and do not form a loop")

    shapes = {(t["n_lines"], t["n_samples"]) for t in tiles}
    if len(shapes) != 1:
        raise SystemExit(
            f"tiles have different shapes {shapes}; the loop-closure residual "
            "is evaluated on one image grid and would be ill-defined")

    incs = [t["incidence_deg"] for t in tiles]
    ress = [t["ode_map_resolution_m"] for t in tiles]
    out_path.write_text(json.dumps({
        "dataset": "LRO NAC (LROC) real image tiles via PDS ODE",
        "stage": "REAL-DATA-03",
        "region": tiles[0].get("region"),
        "pair": order,
        "pair_role": args.role,
        "composed_from": sources,
        "composition_note": (
            "This manifest was COMPOSED from existing acquisitions, not "
            "acquired. Every tile entry is copied verbatim from its source; no "
            "byte was re-fetched and no field was recomputed. The three tiles "
            "were verified distinct by SHA-256, present on disk, identical in "
            "shape, and all cut on the same target ground point."),
        "target_ground_point_lon_lat": [lon0, lat0],
        "incidence_deg": incs,
        "incidence_delta_deg": float(max(incs) - min(incs)),
        "resolution_ratio": float(max(ress) / min(ress)),
        "loop_edges": [f"{order[0]} -> {order[1]}",
                       f"{order[1]} -> {order[2]}",
                       f"{order[2]} -> {order[0]}"],
        "loop_closure_rule": (
            "Every edge MUST be estimated independently from its own image "
            "pair. Deriving the closing edge algebraically from the other two "
            "manufactures a zero residual for an arbitrarily wrong solution "
            "(E-021)."),
        "chandrayaan2_status": (
            "NOT OBTAINED. No Chandrayaan-2 data is present. No multi-modal "
            "claim is supported by this manifest."),
        "licence": ("NASA PDS public domain; credit NASA/GSFC/Arizona State "
                    "University."),
        "tiles": tiles,
    }, indent=2), encoding="utf-8")

    print(f"composed {len(tiles)} tiles from {', '.join(sources)}")
    for t in tiles:
        print(f"   {t['pdsid']}  incidence {t['incidence_deg']:.2f} deg  "
              f"lines [{t['line0']}, {t['line0'] + t['n_lines']})  "
              f"samples [{t['sample0']}, {t['sample0'] + t['n_samples']})  "
              f"sha {t['bytes_sha256'][:16]}")
    print(f"target ground point: {lon0:.6f}, {lat0:.6f}")
    print(f"manifest: {out_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
