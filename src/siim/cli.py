"""``siim register``: two images in, four deliverables out (next-session plan R10).

    python -m siim register SOURCE REFERENCE --out DIR [--engine B1|B4L|both]
                            [--decimate K] [--seed 0] [--model affine]

Inputs are 2-D images: ``.npy`` arrays (float or integer DN, NaN = invalid) or
anything Pillow reads (PNG, TIFF, ...), converted to a single grey channel.
Both are preprocessed exactly as every recorded real-data stage preprocessed
its tiles: optional block-mean decimation by ``K``, then a 1-99 percentile
stretch per image. Nothing else is done to the pixels.

Outputs, written into ``--out`` (which must not already contain them):

``points.csv``
    One row per putative correspondence: source pixel, the engine's reference
    pixel, the refined reference pixel and its ECC shift and confidence, the
    residual under the final transform, and a 2x2 covariance of the final
    transform's *prediction* at that point from bootstrap re-estimates over
    the refined correspondences. That covariance is the uncertainty of the
    global model at the point; it does not include the local refiner's own
    error (0.003 px on self-warps, EXP-010) and it is not an accuracy.
``registered.npy`` / ``registered.png`` / ``difference.png``
    The source warped into the reference grid under the final transform, a
    preview, and |registered - reference| over the valid region.
``metrics.json``
    Every measured number: counts, held-out residuals per model, coverage,
    runtimes, and the transform matrices before and after re-estimation.
``verdict.json``
    VERIFIED / REJECTED / INCONCLUSIVE with the named evidence, the
    pre-registered rule stated separately, ``model_selected_by``, and the
    provenance block: input paths and SHA-256, shapes, preprocessing, engine,
    seed, library versions, git commit, time.

Exit status: 0 for VERIFIED or INCONCLUSIVE, 3 for REJECTED (a refused
alignment is a successful run of this tool), 2 for an input the tool cannot
read. A REJECTED pair still gets ``points.csv``, ``metrics.json`` and
``verdict.json``; it gets no registered product, because emitting one would
contradict the verdict beside it (the same rule as the REAL-DATA-04 products).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from . import __version__
from .geometry import Transform, warp
from .pipeline import (
    AGREEMENT_FLOOR_PX,
    PIPELINE_ORDER,
    RegistrationResult,
    engine_agreement,
    register_pair,
    with_agreement,
)
from .pipeline.select import reestimate

__all__ = ["main", "load_image", "preprocess"]

BOOTSTRAP_N = 200
BOOTSTRAP_SEED = 20260905
RULE = "n_inliers <= 8 -> REJECTED (D-023, validated EXP-002; false-alarm 0.369 in the mixed regime, EXP-003)"


# --------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------

def load_image(path: Path) -> np.ndarray:
    """A 2-D float image from ``.npy`` or any Pillow-readable file."""
    if path.suffix.lower() == ".npy":
        a = np.load(path)
        if a.ndim == 3:
            a = a.mean(axis=2)
        if a.ndim != 2:
            raise ValueError(f"{path}: expected a 2-D array, got shape {a.shape}")
        return a.astype(np.float64)
    from PIL import Image
    with Image.open(path) as im:
        if im.mode not in ("F", "I", "I;16", "L"):
            im = im.convert("L")
        a = np.asarray(im, dtype=np.float64)
    if a.ndim == 3:
        a = a.mean(axis=2)
    return a


def preprocess(a: np.ndarray, decimate: int = 1) -> np.ndarray:
    """Block-mean decimation then a 1-99 percentile stretch: the recorded order."""
    a = np.asarray(a, np.float64)
    if decimate > 1:
        k = decimate
        a = a[: a.shape[0] // k * k, : a.shape[1] // k * k]
        a = np.nanmean(a.reshape(a.shape[0] // k, k, a.shape[1] // k, k), axis=(1, 3))
    v = a[np.isfinite(a)]
    if v.size == 0:
        raise ValueError("image has no finite pixels")
    lo, hi = np.percentile(v, [1.0, 99.0])
    out = (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)
    out = np.clip(out, 0.0, 1.0)
    return np.where(np.isfinite(a), out, np.nan)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                             timeout=10, cwd=Path(__file__).resolve().parents[2])
        return out.stdout.strip() or None if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _versions(engine: str) -> dict[str, str]:
    import cv2
    v = {"python": platform.python_version(), "numpy": np.__version__,
         "opencv": cv2.__version__, "siim": __version__, "platform": platform.platform()}
    if engine in ("B4L", "both"):
        try:
            import kornia
            import torch
            v["torch"] = torch.__version__
            v["kornia"] = kornia.__version__
        except ImportError:
            pass
    return v


# --------------------------------------------------------------------------
# uncertainty of the final transform, by bootstrap over refined points
# --------------------------------------------------------------------------

def prediction_covariance(res: RegistrationResult, points: np.ndarray,
                          n_boot: int = BOOTSTRAP_N, seed: int = BOOTSTRAP_SEED) -> np.ndarray | None:
    """(N, 2, 2) covariance of T_b(points) over bootstrap re-estimates T_b of the
    final model from the refined correspondences. ``None`` when the final
    transform was not re-estimated (nothing to resample)."""
    if res.transform is None or res.model_selected_by not in (
            "held_out_on_refined_points", "held_out_on_raw_points"):
        return None
    m = res.refined_mask if res.model_selected_by == "held_out_on_refined_points" else res.inlier_mask
    p, q = res.src_points[m], res.dst_points_refined[m]
    n = p.shape[0]
    rng = np.random.default_rng(seed)
    preds = np.empty((n_boot, points.shape[0], 2))
    got = 0
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        try:
            tb = reestimate(p[idx], q[idx], res.transform.model)
        except ValueError:
            continue
        preds[got] = tb.apply(points)
        got += 1
    if got < 10:
        return None
    preds = preds[:got]
    d = preds - preds.mean(axis=0, keepdims=True)
    cov = np.einsum("bni,bnj->nij", d, d) / (got - 1)
    return cov


# --------------------------------------------------------------------------
# outputs
# --------------------------------------------------------------------------

def _write_points(path: Path, res: RegistrationResult, cov: np.ndarray | None) -> int:
    resid = res.residuals_px()
    p, q, qr = res.src_points, res.dst_points, res.dst_points_refined
    shift = np.full((p.shape[0], 2), np.nan)
    conf = np.full(p.shape[0], np.nan)
    if res.refinement is not None:
        idx = np.flatnonzero(res.inlier_mask)
        shift[idx] = res.refinement.shift
        conf[idx] = res.refinement.confidence
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        nl = "\n"
        fh.write("# siim register: putative correspondences, source -> reference, "
                 "(x, y) at pixel centres (contract C1)" + nl)
        fh.write(f"# engine {res.engine}; pipeline {' -> '.join(PIPELINE_ORDER)}; final model "
                 f"{None if res.transform is None else res.transform.model} selected by "
                 f"{res.model_selected_by}" + nl)
        fh.write("# residual_px: ||T(src) - dst_refined|| under the FINAL transform. "
                 "A fit statistic, NOT an accuracy (D-003)" + nl)
        fh.write(f"# model_pred_cov_*_px2: covariance (px^2) of the GLOBAL MODEL's prediction at this point over "
                 f"{BOOTSTRAP_N} bootstrap re-estimates of the refined correspondences; excludes the "
                 "refiner's own error (0.003 px on self-warps, EXP-010) and every error the geometry check "
                 "cannot see; NOT an accuracy and NOT a per-point uncertainty" + nl)
        w.writerow(["index", "is_inlier", "is_refined", "src_x", "src_y",
                    "dst_x_engine", "dst_y_engine", "dst_x_refined", "dst_y_refined",
                    "refine_shift_x", "refine_shift_y", "refine_confidence",
                    "residual_px", "model_pred_cov_xx_px2", "model_pred_cov_xy_px2", "model_pred_cov_yy_px2"])
        for i in range(p.shape[0]):
            c = cov[i] if cov is not None else None
            w.writerow([i, int(res.inlier_mask[i]), int(res.refined_mask[i]),
                        f"{p[i, 0]:.4f}", f"{p[i, 1]:.4f}", f"{q[i, 0]:.4f}", f"{q[i, 1]:.4f}",
                        f"{qr[i, 0]:.4f}", f"{qr[i, 1]:.4f}",
                        f"{shift[i, 0]:.4f}", f"{shift[i, 1]:.4f}", f"{conf[i]:.4f}",
                        f"{resid[i]:.4f}" if resid.size else "",
                        *(["", "", ""] if c is None else
                          [f"{c[0, 0]:.6e}", f"{c[0, 1]:.6e}", f"{c[1, 1]:.6e}"])])
    return p.shape[0]


def _png(path: Path, a: np.ndarray, valid: np.ndarray | None = None) -> None:
    from PIL import Image
    v = np.isfinite(a) if valid is None else (valid & np.isfinite(a))
    out = np.zeros(a.shape, np.uint8)
    if v.any():
        lo, hi = np.percentile(a[v], [1, 99])
        s = (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)
        out[v] = np.clip(s[v] * 255, 0, 255).astype(np.uint8)
    Image.fromarray(out).save(path)


def _write_product(out: Path, src: np.ndarray, ref: np.ndarray, tf: Transform) -> dict[str, Any]:
    reg, valid = warp(src, tf, out_shape=ref.shape, order=3, cval=np.nan)
    np.save(out / "registered.npy", reg)
    _png(out / "registered.png", reg, valid)
    diff = np.where(valid & np.isfinite(ref), np.abs(reg - ref), np.nan)
    _png(out / "difference.png", diff, valid)
    d = diff[np.isfinite(diff)]
    return {"valid_fraction": float(valid.mean()),
            "abs_difference_median": float(np.median(d)) if d.size else None,
            "abs_difference_p90": float(np.percentile(d, 90)) if d.size else None,
            "note": "|registered - reference| over the valid region, in stretched units; a "
                    "photometric residual, not a geometric accuracy"}


# --------------------------------------------------------------------------
# the command
# --------------------------------------------------------------------------

def register_command(args: argparse.Namespace) -> int:
    t_start = time.perf_counter()
    src_path, ref_path, out = Path(args.source), Path(args.reference), Path(args.out)
    try:
        src_raw, ref_raw = load_image(src_path), load_image(ref_path)
    except (OSError, ValueError) as exc:
        print(f"cannot read input: {exc}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    names = ["points.csv", "metrics.json", "verdict.json", "registered.npy",
             "registered.png", "difference.png"]
    clash = [n for n in names if (out / n).exists()]
    if clash and not args.overwrite:
        print(f"{clash} already exist in {out}; pass --overwrite to replace them", file=sys.stderr)
        return 2
    src = preprocess(src_raw, args.decimate)
    ref = preprocess(ref_raw, args.decimate)

    engine = args.engine.upper() if args.engine.lower() != "both" else "both"
    agreement = None
    secondary: RegistrationResult | None = None
    if engine == "both":
        res = register_pair(src, ref, engine="B1", model=args.model, seed=args.seed,
                            refine=not args.no_refine)
        secondary = register_pair(src, ref, engine="B4L", model=args.model, seed=args.seed,
                                  refine=not args.no_refine)
        agreement = engine_agreement("B1", res.transform, "B4L", secondary.transform, src.shape,
                                     floor_px=AGREEMENT_FLOOR_PX)
        if agreement.agree is not None:
            res = with_agreement(res, src.shape, agreement.median_px, AGREEMENT_FLOOR_PX)
    else:
        res = register_pair(src, ref, engine=engine, model=args.model, seed=args.seed,
                            refine=not args.no_refine)

    cov = prediction_covariance(res, res.src_points) if res.transform is not None else None
    n_rows = _write_points(out / "points.csv", res, cov)

    product: dict[str, Any] | None = None
    if res.verdict.status != "REJECTED" and res.transform is not None:
        product = _write_product(out, src, ref, res.transform)

    prov = {
        "tool": f"siim {__version__} register", "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": _git_commit(), "versions": _versions(engine),
        "inputs": {
            "source": {"path": str(src_path), "sha256": _sha256(src_path), "shape_raw": list(src_raw.shape)},
            "reference": {"path": str(ref_path), "sha256": _sha256(ref_path), "shape_raw": list(ref_raw.shape)},
        },
        "preprocessing": {"decimation": args.decimate, "stretch": "per-image 1-99 percentile, clipped to [0, 1]",
                          "shape_used": list(src.shape)},
        "engine": engine, "seed": args.seed, "ransac_model_default": args.model,
        "refinement": None if args.no_refine else {"method": "ecc", "window": 48},
        "pipeline_order": list(PIPELINE_ORDER),
        "pre_registered_rule": RULE,
    }
    metrics = {"primary": res.summary(), "verdict_metrics": res.verdict.metrics,
               "coverage": {k: res.verdict.metrics.get(k) for k in ("coverage_max_gap", "coverage_occupancy")},
               "product": product, "n_points_rows": n_rows,
               "secondary": None if secondary is None else secondary.summary(),
               "engine_agreement": None if agreement is None else agreement.__dict__,
               "wall_s": time.perf_counter() - t_start}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2, default=_json_default), encoding="utf-8")
    verdict = res.verdict.as_dict()
    verdict["rule_stated_separately"] = RULE
    verdict["what_verified_means"] = ("corroborated by the named evidence; no ground truth exists "
                                      "for a real pair and none is claimed")
    verdict["provenance"] = prov
    verdict["files"] = {n: str(out / n) for n in names if (out / n).exists()}
    (out / "verdict.json").write_text(json.dumps(verdict, indent=2, default=_json_default), encoding="utf-8")

    print(f"{res.verdict.status} / {res.verdict.confidence}  "
          f"inliers={res.n_inliers} refined={int(res.refined_mask.sum())} "
          f"model={None if res.transform is None else res.transform.model} "
          f"({res.model_selected_by})  -> {out}")
    for r in res.verdict.reasons:
        print(f"  - {r}")
    return 3 if res.verdict.status == "REJECTED" else 0


def _json_default(o: Any):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return str(o)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="siim", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    r = sub.add_parser("register", help="register a source image to a reference image")
    r.add_argument("source")
    r.add_argument("reference")
    r.add_argument("--out", required=True, help="output directory")
    r.add_argument("--engine", default="B1", help="B1 (RootSIFT), B4L (DISK+LightGlue), or both")
    r.add_argument("--model", default="affine", help="RANSAC model for the initial estimate")
    r.add_argument("--decimate", type=int, default=1, help="block-mean decimation before matching")
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--no-refine", action="store_true", help="skip sub-pixel refinement (diagnostic)")
    r.add_argument("--overwrite", action="store_true")
    r.set_defaults(func=register_command)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
