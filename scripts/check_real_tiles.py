"""Phase 6 sanity checks on the acquired real NAC tiles, plus diagnostic figures.

Run:  python scripts/check_real_tiles.py

Re-fetches nothing. Reads the tiles written by ``acquire_real_pair.py``, the
labels they were decoded through, and the raw bytes for the byte-order and
alignment evidence (re-fetched only if the ``.raw`` sidecar is absent).

Writes ``experiments/REAL-DATA/`` : a JSON of every statistic, and figures.
**Registration does not proceed if these checks fail.**
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from siim.ingest.lro_nac import ODE_ENDPOINT, _parse_product, fetch_byte_range  # noqa: E402
from siim.ingest.pds4 import parse_image_structure, plan_tile_byte_range  # noqa: E402
from siim.ingest.sanity import check_tile  # noqa: E402

OUT = ROOT / "experiments" / "REAL-DATA"
DEFAULT_MAN = "real_pair_usable_manifest.json"


def raw_sidecar(out_dir: Path, tile: dict) -> Path:
    """Cache path for a tile's raw bytes, keyed by the WINDOW as well as the
    product.

    An earlier version used ``{pdsid}.tile.raw``, which encodes the product but
    not where in it the tile came from. Acquiring the same product at a second
    window then found the first window's bytes in the cache and computed the
    byte-order and alignment evidence from them -- silently, for a tile they do
    not describe. That is ERROR_LEDGER **E-030**, and it is **E-025 recurring
    in a second script**: an artefact name that omits a varying parameter.
    """
    return out_dir / (f"{tile['pdsid']}.l{tile['line0']}s{tile['sample0']}"
                      f"n{tile['n_lines']}.tile.raw")


def legacy_raw_sidecar(out_dir: Path, tile: dict) -> Path:
    """The pre-E-030 cache path, kept readable so REAL-DATA-01's 166 MB of
    sidecars are not re-fetched. It is used **only** when its SHA-256 matches
    the manifest, i.e. when the bytes prove they are the right ones -- the name
    is never trusted on its own."""
    return out_dir / f"{tile['pdsid']}.tile.raw"


def load_or_fetch_raw(out_dir: Path, tile: dict, struct) -> tuple[bytes, str]:
    """Raw tile bytes, verified against the manifest hash. Returns ``(raw, how)``.

    A cached file whose hash does not match the manifest is **not** an error and
    is **not** reported as one: it is the wrong cache entry, so it is discarded
    and the bytes are re-fetched. Reporting it as "the range fetch is not
    reproducible" sent the reader to debug a correct fetch, which is E-024's
    lesson in a new place.
    """
    import hashlib

    want = tile["bytes_sha256"]
    for path, kind in ((raw_sidecar(out_dir, tile), "cache"),
                       (legacy_raw_sidecar(out_dir, tile), "legacy cache")):
        if not path.exists():
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() == want:
            return raw, f"{kind} {path.name}"
        print(f"   note: {path.name} holds bytes for a different window "
              f"(sha {hashlib.sha256(raw).hexdigest()[:16]} != manifest "
              f"{want[:16]}); ignoring it and re-fetching")

    start, count = plan_tile_byte_range(
        struct, line0=tile["line0"], n_lines=tile["n_lines"])
    if (start, count) != (tile["byte_start"], tile["byte_count"]):
        raise SystemExit(
            f"{tile['pdsid']}: the byte range planned from the label "
            f"({start}, {count}) disagrees with the manifest "
            f"({tile['byte_start']}, {tile['byte_count']})")
    raw = fetch_byte_range(tile["image_url"], start, count)
    dest = raw_sidecar(out_dir, tile)
    if dest.exists():
        raise SystemExit(
            f"{dest} already exists but does not hold these bytes; refusing "
            "to overwrite a cached artefact (integrity rule 4)")
    dest.write_bytes(raw)
    return raw, f"fetched {count} bytes from {start}"


def _stretch(a: np.ndarray, lo_pct=1.0, hi_pct=99.0) -> np.ndarray:
    v = a[np.isfinite(a)]
    lo, hi = np.percentile(v, [lo_pct, hi_pct])
    return np.clip((a - lo) / (hi - lo), 0, 1) if hi > lo else np.zeros_like(a)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=DEFAULT_MAN)
    ap.add_argument("--outdir", default=None,
                    help="output directory under experiments/ (default "
                         "REAL-DATA)")
    args = ap.parse_args()
    man_path = ROOT / "data" / "manifests" / args.manifest
    tag = args.manifest.replace("real_pair_", "").replace("_manifest.json", "")

    global OUT
    if args.outdir:
        OUT = ROOT / "experiments" / args.outdir
    OUT.mkdir(parents=True, exist_ok=True)
    man = json.loads(man_path.read_text(encoding="utf-8"))
    report = {"pair": man["pair"], "manifest": args.manifest,
              "tiles": [], "all_passed": True}

    import requests
    tiles = []
    for t in man["tiles"]:
        pdsid = t["pdsid"]
        img = np.load(ROOT / t["tile_npy"])
        struct = parse_image_structure(
            (ROOT / t["label_path"]).read_text(encoding="utf-8"))

        # Raw bytes for the byte-order / alignment evidence. The cache is
        # keyed by the tile WINDOW and every hit is hash-verified against the
        # manifest before it is used (E-030).
        raw, how = load_or_fetch_raw(OUT, t, struct)
        import hashlib
        got = hashlib.sha256(raw).hexdigest()
        sha_ok = got == t["bytes_sha256"]

        chk = check_tile(img, struct, raw=raw, n_lines=t["n_lines"],
                         sample0=t["sample0"], n_samples=t["n_samples"],
                         expected_shape=(t["n_lines"], t["n_samples"]),
                         label=pdsid)
        d = chk.as_dict()
        d["sha256_matches_manifest"] = sha_ok
        d["raw_bytes_source"] = how
        d["incidence_deg"] = t["incidence_deg"]
        d["geolocation_status"] = t["geolocation_status"]
        if not sha_ok:
            d["passed"] = False
            d["failures"].append(
                f"SHA-256 of the bytes obtained by {how} is {got[:16]}, but "
                f"the manifest records {t['bytes_sha256'][:16]}. A cached file "
                "for the wrong window is discarded and re-fetched before this "
                "point, so reaching it means the ARCHIVE returned different "
                "bytes for the same range -- not a caching problem")
        report["tiles"].append(d)
        report["all_passed"] &= bool(d["passed"])
        tiles.append((pdsid, img, t, d))

        print(f"== {pdsid}  incidence {t['incidence_deg']:.2f} deg")
        print(f"   shape {d['stats']['shape']}  finite {d['stats']['finite_fraction']:.4f}"
              f"  zero_frac {d['stats'].get('zero_fraction', float('nan')):.5f}")
        print(f"   DN  min {d['stats']['min']:.0f}  p1 {d['stats']['p1']:.0f}"
              f"  med {d['stats']['median']:.0f}  p99 {d['stats']['p99']:.0f}"
              f"  max {d['stats']['max']:.0f}  std {d['stats']['std']:.1f}"
              f"  unique {d['stats']['n_unique']}")
        bo, ba = d["stats"]["byte_order"], d["stats"]["byte_alignment"]
        print(f"   autocorr(lag1)          {d['stats']['lag1_autocorrelation']:.4f}")
        print(f"   byte order   declared {bo['autocorr_as_declared']:.4f}"
              f"  vs swapped {bo['autocorr_byte_swapped']:.4f}")
        print(f"   alignment    planned  {ba['autocorr_aligned']:.4f}"
              f"  vs +1 byte  {ba['autocorr_shifted_one_byte']:.4f}")
        print(f"   raw bytes    {how}")
        print(f"   sha256 matches manifest: {sha_ok}")
        print(f"   PASSED: {d['passed']}")
        for f in d["failures"]:
            print(f"     FAIL: {f}")
        print()

    # ---------------- the measurement is written FIRST ----------------
    # The report is saved before any figure is drawn. It used to be saved
    # after, and a plotting failure on a three-tile manifest destroyed a set
    # of checks that had already passed (E-031). A diagnostic picture must
    # never be able to lose a measurement.
    (OUT / f"tile_sanity_{tag}.json").write_text(json.dumps(report, indent=2),
                                                 encoding="utf-8")
    print(f"report: {(OUT / f'tile_sanity_{tag}.json').relative_to(ROOT)}")
    print(f"ALL CHECKS PASSED: {report['all_passed']}\n")

    # ---------------- figures ----------------
    # Rows come from the number of tiles, not from the two this script was
    # first written for: REAL-DATA-03 verifies loop-closure triplets.
    n_rows = len(tiles)
    fig, axes = plt.subplots(n_rows, 3, figsize=(16, 5.5 * n_rows),
                             squeeze=False)
    for r, (pdsid, img, t, d) in enumerate(tiles):
        ax = axes[r, 0]
        ax.imshow(_stretch(img), cmap="gray", aspect="auto",
                  interpolation="nearest")
        ax.set_title(f"{pdsid}\nincidence {t['incidence_deg']:.1f}"
                     r"$^\circ$ · 1–99% stretch", fontsize=10)
        ax.set_xlabel("sample (column)")
        ax.set_ylabel("line (row)")

        ax = axes[r, 1]
        v = img[np.isfinite(img)]
        ax.hist(v.ravel(), bins=200, color="0.3")
        ax.set_yscale("log")
        ax.set_title(f"DN histogram · median {np.median(v):.0f}, "
                     f"std {v.std():.1f}", fontsize=10)
        ax.set_xlabel("DN (raw, before scaling_factor)")

        ax = axes[r, 2]
        bo = d["stats"]["byte_order"]
        ba = d["stats"]["byte_alignment"]
        names = ["declared\n" + bo["declared_dtype"], "byte\nswapped",
                 "planned\noffset", "offset\n+1 byte"]
        vals = [bo["autocorr_as_declared"], bo["autocorr_byte_swapped"],
                ba["autocorr_aligned"], ba["autocorr_shifted_one_byte"]]
        ax.bar(names, vals, color=["#2a6f4f", "#a33", "#2a6f4f", "#a33"])
        ax.axhline(0.60, ls="--", c="k", lw=1)
        ax.set_ylim(-0.15, 1.05)
        ax.set_ylabel("lag-1 autocorrelation")
        ax.set_title("decode-correctness evidence\n(dashed: plausibility floor)",
                     fontsize=10)
        for i, val in enumerate(vals):
            ax.text(i, val + 0.03, f"{val:.3f}", ha="center", fontsize=9)

    fig.suptitle("REAL LRO NAC tiles — Phase 6 sanity checks "
                 "(no ground truth; overlap is pre-registration and approximate)",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT / f"tile_sanity_{tag}.png", dpi=110)
    print(f"figure: {(OUT / f'tile_sanity_{tag}.png').relative_to(ROOT)}")

    # side by side, matched stretch, for visual assessment
    fig2, axes2 = plt.subplots(1, n_rows, figsize=(6.5 * n_rows, 9),
                               squeeze=False)
    for ax, (pdsid, img, t, d) in zip(axes2[0], tiles):
        ax.imshow(_stretch(img, 2, 98), cmap="gray", interpolation="nearest")
        ax.set_title(f"{pdsid}\nincidence {t['incidence_deg']:.1f}"
                     r"$^\circ$, lines "
                     f"[{t['line0']}, {t['line0'] + t['n_lines']})", fontsize=10)
        ax.set_xlabel("sample")
        ax.set_ylabel("line")
    fig2.suptitle(
        man.get("selection_method", "").startswith("GEOMETRY-DRIVEN")
        and ("Overlapping region — tile windows GEOMETRY-DRIVEN from archive "
             "corner geometry; overlap verified separately by "
             "verify_tile_overlap.py")
        or ("Candidate overlapping region — selection is APPROXIMATE "
            "(footprint latitude, no camera model)"), fontsize=11)
    fig2.tight_layout()
    fig2.savefig(OUT / f"tile_pair_{tag}.png", dpi=110)
    print(f"figure: {(OUT / f'tile_pair_{tag}.png').relative_to(ROOT)}")
    if not report["all_passed"]:
        pass  # reported, not fatal: the caller decides


if __name__ == "__main__":
    main()
