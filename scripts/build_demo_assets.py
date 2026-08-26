"""Build the demo's real-data visual assets from the REAL-DATA-04 tiles.

Run:  python scripts/build_demo_assets.py

Why this exists, and why it is not "recomputing the science"
------------------------------------------------------------
The demo must show, for a real LRO NAC edge, *where the correspondences are* --
a picture of 1656 green lines against 3 red ones is the whole argument. But
``experiments/REAL-DATA-04/loop_closure_real_data_04.json`` records the match
**statistics**, not the match **coordinates**: it stores 1656, not the 1656
points. The picture cannot be drawn from the recorded artefact alone.

So this script re-runs the identical registration to recover the coordinates,
and then **refuses to write anything unless every recomputed statistic is
bit-identical to the recorded artefact**. Keypoint counts, putative counts,
inlier counts, inlier ratio, fit RMSE and all six transform-matrix entries must
match exactly, on all three edges. If any differs, the environment has drifted
and the demo would be showing a picture of a different run than the numbers
beside it -- so it stops instead.

The distinction the demo then keeps, in the API response and in the UI:

* every **number** shown comes from the recorded experiment artefact;
* only the **line positions in the overlay picture** come from here, and they
  are certified to belong to the same run.

The equality check itself is recorded in the asset file
(``verified_against_artefact``) so the guarantee is auditable rather than a
claim in a docstring.

To guarantee the code path is the same rather than merely similar, the
preprocessing and the edge runner are **imported from
``scripts/register_real_triplet.py``** instead of being copied here. A copy
would be free to drift; an import cannot.

Outputs, all under ``src/siim/demo/assets/`` (new files, nothing overwritten
elsewhere):

* ``real_data_04.json`` -- per-edge correspondence coordinates and inlier mask
* ``tile_<pdsid>.png``  -- one grayscale preview per tile
"""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ARTEFACT = ROOT / "experiments" / "REAL-DATA-04" / "loop_closure_real_data_04.json"
MANIFEST = ROOT / "data" / "manifests" / "real_quad_d_geo_manifest.json"
ASSETS = ROOT / "src" / "siim" / "demo" / "assets"

#: Extra decimation applied to the PNG previews only. Correspondence
#: coordinates stay in the matcher's own 2048x1024 grid and are mapped by this
#: factor at draw time, so the stored numbers remain the matcher's.
PREVIEW_DECIMATION = 2

#: Statistics that must reproduce exactly. Floats are compared with ``==``
#: deliberately: the pipeline is seeded and deterministic, so anything other
#: than an exact match means something changed.
MUST_MATCH = (
    "n_keypoints_src", "n_keypoints_dst", "n_putative_mutual_ratio_matches",
    "n_inliers", "inlier_ratio", "fit_rmse_px",
    "coverage_max_uncovered_disc_ratio", "coverage_occupancy",
)


def _load_triplet_runner():
    """Import the experiment's own runner, so the code path is identical."""
    spec = importlib.util.spec_from_file_location(
        "register_real_triplet", ROOT / "scripts" / "register_real_triplet.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _png_bytes(a: np.ndarray) -> bytes:
    from PIL import Image
    k = PREVIEW_DECIMATION
    if k > 1:
        a = a[: a.shape[0] // k * k, : a.shape[1] // k * k]
        a = a.reshape(a.shape[0] // k, k, a.shape[1] // k, k).mean(axis=(1, 3))
    a = np.clip(np.nan_to_num(a), 0.0, 1.0)
    buf = io.BytesIO()
    Image.fromarray((a * 255).astype(np.uint8)).save(buf, format="PNG",
                                                     optimize=True)
    return buf.getvalue()


def main() -> None:
    if not ARTEFACT.exists():
        raise SystemExit(
            f"missing {ARTEFACT.relative_to(ROOT)}. The demo assets are built "
            "from the recorded REAL-DATA-04 result; run that stage first.")
    rec = json.loads(ARTEFACT.read_text(encoding="utf-8"))
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rrt = _load_triplet_runner()

    print("== building demo assets from the RECORDED REAL-DATA-04 result ==")
    print(f"artefact : {ARTEFACT.relative_to(ROOT)}")
    print(f"manifest : {MANIFEST.relative_to(ROOT)}")
    print(f"baseline : {rec['baseline']['pipeline']}, model "
          f"{rec['baseline']['model']}, threshold "
          f"{rec['baseline']['ransac_threshold_px']}, seed {rec['baseline']['seed']}, "
          f"downsample {rec['baseline']['downsample']}\n")

    k = int(rec["baseline"]["downsample"])
    tiles = man["tiles"]
    imgs, names = [], []
    for t in tiles:
        p = ROOT / t["tile_npy"]
        if not p.exists():
            raise SystemExit(
                f"missing tile {t['tile_npy']}. Tiles are gitignored; they must "
                "be on disk to build the overlay assets. The demo will not "
                "invent correspondences.")
        a = rrt.decimate(np.load(p), k)
        imgs.append(rrt.normalise(a))
        names.append(t["pdsid"])
        print(f"{t['pdsid']}: incidence {t['incidence_deg']:.2f} deg, "
              f"tile {a.shape}")

    shape = imgs[0].shape
    if list(shape) != list(rec["shape_after_decimation"]):
        raise SystemExit(
            f"tiles decimate to {shape}, the artefact records "
            f"{rec['shape_after_decimation']}; refusing to build assets from a "
            "different grid")

    order = [(0, 1), (1, 2), (2, 0)]
    by_edge = {e["edge"]: e for e in rec["edges"]}
    out_edges, mismatches = [], []

    print(f"\nre-running the unmodified baseline on {len(order)} edges to "
          "recover correspondence COORDINATES\n")
    for i, j in order:
        name = f"{names[i]} -> {names[j]}"
        summary, _tf = rrt.run_edge(name, imgs[i], imgs[j],
                                    rec["baseline"]["model"])
        res = summary.pop("_res")
        want = by_edge[name]

        bad = [f for f in MUST_MATCH if summary.get(f) != want.get(f)]
        m_now = np.asarray(summary.get("transform_matrix"), float)
        m_rec = np.asarray(want.get("transform_matrix"), float)
        if m_now.shape != m_rec.shape or not np.array_equal(m_now, m_rec):
            bad.append("transform_matrix")
        status = "MATCHES the artefact" if not bad else f"DIFFERS: {bad}"
        print(f"{name}\n   putative {summary['n_putative_mutual_ratio_matches']}"
              f"   inliers {summary['n_inliers']}   -> {status}")
        if bad:
            mismatches.append((name, bad))
            continue

        mask = (np.asarray(res.inlier_mask, dtype=bool)
                if np.size(res.inlier_mask) else np.zeros(0, bool))
        src = np.asarray(res.matches.src_points, float)
        dst = np.asarray(res.matches.dst_points, float)
        out_edges.append({
            "edge": name,
            "src_pdsid": names[i],
            "dst_pdsid": names[j],
            "correspondences": {
                "src": [[round(float(x), 2), round(float(y), 2)] for x, y in src],
                "dst": [[round(float(x), 2), round(float(y), 2)] for x, y in dst],
                "inlier": [bool(b) for b in mask],
            },
            "grid_shape_lines_samples": [int(shape[0]), int(shape[1])],
            "coordinates_are": (
                "(x, y) = (sample, line) in the matcher's own 2x-decimated tile "
                "grid, NOT in the preview PNG's grid"),
        })

    if mismatches:
        raise SystemExit(
            "\nREFUSING TO WRITE ASSETS. Re-running the baseline did not "
            "reproduce the recorded REAL-DATA-04 statistics:\n"
            + "\n".join(f"   {n}: {b}" for n, b in mismatches)
            + "\nThe environment has drifted from the one that produced "
              "experiments/REAL-DATA-04/. Writing the overlay anyway would put "
              "a picture of one run next to the numbers of another.")

    ASSETS.mkdir(parents=True, exist_ok=True)
    previews = {}
    for img, t in zip(imgs, tiles):
        png = _png_bytes(img)
        path = ASSETS / f"tile_{t['pdsid']}.png"
        path.write_bytes(png)
        previews[t["pdsid"]] = {
            "file": path.name,
            "bytes": len(png),
            "preview_decimation_from_matcher_grid": PREVIEW_DECIMATION,
            "sha256_of_source_tile_bytes": t["bytes_sha256"],
        }
        print(f"preview: {path.relative_to(ROOT)}  ({len(png) / 1e3:.0f} kB)")

    out = {
        "purpose": (
            "Visual assets for the SIIM demo. Correspondence COORDINATES and "
            "grayscale previews only. Every SCIENTIFIC NUMBER the demo displays "
            "is read from the recorded experiment artefacts, not from here."),
        "stage": rec["stage"],
        "data": rec["data"],
        "source_artefact": str(ARTEFACT.relative_to(ROOT)).replace("\\", "/"),
        "source_manifest": str(MANIFEST.relative_to(ROOT)).replace("\\", "/"),
        "baseline": rec["baseline"],
        "verified_against_artefact": {
            "checked": list(MUST_MATCH) + ["transform_matrix"],
            "comparison": "exact equality (the pipeline is seeded and deterministic)",
            "edges_checked": len(order),
            "edges_matching": len(out_edges),
            "all_match": len(out_edges) == len(order),
            "note": ("This script refuses to write unless every recomputed "
                     "statistic equals the recorded one on every edge, so the "
                     "overlay below belongs to the same run as the numbers the "
                     "demo displays."),
        },
        "tile_previews": previews,
        "edges": out_edges,
        "licence": ("NASA PDS public domain; credit NASA/GSFC/Arizona State "
                    "University."),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    path = ASSETS / "real_data_04.json"
    path.write_text(json.dumps(out, indent=1), encoding="utf-8")
    size = path.stat().st_size
    print(f"\nassets: {path.relative_to(ROOT)}  ({size / 1e3:.0f} kB)")
    print(f"ALL {len(order)} EDGES REPRODUCED THE RECORDED ARTEFACT EXACTLY.")


if __name__ == "__main__":
    main()
