"""The deliverable pipeline (estimate -> refine -> re-estimate -> verify), the
engine-agreement verifier, and the `siim register` command."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from siim.demo.verdict import assess
from siim.geometry import endpoint_error, translation, warp
from siim.pipeline import (
    PIPELINE_ORDER,
    engine_agreement,
    register_pair,
    select_model,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def big_terrain() -> np.ndarray:
    """Larger than conftest's 256^2 so RootSIFT finds hundreds of keypoints
    and the 48 px refinement windows fit inside the image."""
    from scipy import ndimage
    gen = np.random.default_rng(11)
    base = ndimage.gaussian_filter(gen.normal(size=(512, 512)), sigma=2.5)
    yy, xx = np.mgrid[0:512, 0:512].astype(float)
    for cx, cy, r in gen.uniform(40, 470, size=(30, 3)) * np.array([1, 1, 0.06]):
        d = np.hypot(xx - cx, yy - cy)
        base -= 0.9 * np.exp(-((d / max(r, 6.0)) ** 2))
    base -= base.min()
    return base / base.max()


# ---------------------------------------------------------------------------
# rule B agrees with the EXP-011 runner
# ---------------------------------------------------------------------------

def _exp011():
    spec = importlib.util.spec_from_file_location("_exp011", ROOT / "scripts" / "run_exp011.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_select_model_matches_the_exp011_runner_selection(rng):
    """The pipeline's rule is a restatement; it must pick what the recorded
    experiment's code picks, on the same points, for every truth model."""
    e = _exp011()
    p = rng.uniform(0, 400, size=(60, 2))
    truths = e.truths((400, 400))
    for name, tf in truths.items():
        q = tf.apply(p) + rng.normal(scale=0.02, size=p.shape)
        ours = select_model(p, q, seed=0)
        theirs, scores = e.select_by_heldout(p, q, seed=0)
        assert ours.model == theirs, name
        for m in ours.heldout_px:
            assert ours.heldout_px[m] == pytest.approx(scores[m], rel=1e-9, abs=1e-12)


def test_select_model_refuses_too_few_points(rng):
    p = rng.uniform(0, 100, size=(8, 2))
    with pytest.raises(ValueError):
        select_model(p, p + 1.0)


# ---------------------------------------------------------------------------
# the four stages on a known self-warp
# ---------------------------------------------------------------------------

def test_register_pair_recovers_a_subpixel_translation_by_refined_reselection(big_terrain):
    truth = translation(7.25, -4.75)
    ref, valid = warp(big_terrain, truth, cval=np.nan)
    ref = np.where(valid, ref, np.nanmedian(ref))
    res = register_pair(big_terrain, ref, engine="B1", seed=0)

    assert res.verdict.status != "REJECTED"
    assert res.n_inliers > 8
    assert res.model_selected_by == "held_out_on_refined_points"
    assert res.transform is not None and res.transform.model == "translation"
    assert res.refined_mask.sum() >= 12
    err = endpoint_error(res.transform, truth, big_terrain.shape)
    assert err.median < 0.05, err
    # the engine's own affine estimate is what E-034 is about: never better
    # than the re-estimate here, and the re-estimate is what is reported
    err0 = endpoint_error(res.initial_transform, truth, big_terrain.shape)
    assert err.median <= err0.median + 1e-9
    # provenance reaches the verdict without touching the decision
    m = res.verdict.metrics
    assert m["model_selected_by"] == "held_out_on_refined_points"
    assert m["pipeline_order"] == list(PIPELINE_ORDER)
    assert m["transform_model"] == "translation"
    assert "fit_rmse" in res.verdict.excluded
    # no third image: the decisive check was not run, so not VERIFIED
    assert res.verdict.status == "INCONCLUSIVE"


def test_register_pair_rejects_unrelated_images_without_refining(rng, big_terrain):
    noise = rng.uniform(size=big_terrain.shape)
    res = register_pair(big_terrain, noise, engine="B1", seed=0)
    assert res.verdict.status == "REJECTED"
    assert res.refinement is None
    assert res.selection is None
    assert res.model_selected_by == "none"
    assert not res.refined_mask.any()
    assert res.verdict.metrics["model_selected_by"] == "none"


def test_register_pair_without_refinement_falls_back_to_raw_selection(big_terrain):
    truth = translation(3.0, 2.0)
    ref, valid = warp(big_terrain, truth, cval=np.nan)
    ref = np.where(valid, ref, np.nanmedian(ref))
    res = register_pair(big_terrain, ref, engine="B1", seed=0, refine=False)
    assert res.refinement is None
    assert res.model_selected_by == "held_out_on_raw_points"
    assert res.transform is not None


# ---------------------------------------------------------------------------
# engine agreement
# ---------------------------------------------------------------------------

def test_engine_agreement_measures_dense_disagreement():
    a = translation(1.0, 1.0)
    same = engine_agreement("B1", a, "B4L", translation(1.0, 1.0), (256, 256))
    assert same.agree is True and same.median_px == pytest.approx(0.0)
    off = engine_agreement("B1", a, "B4L", translation(11.0, 1.0), (256, 256))
    assert off.agree is False and off.median_px == pytest.approx(10.0)
    none = engine_agreement("B1", a, "B4L", None, (256, 256))
    assert none.agree is None


def test_disagreeing_engines_cap_the_verdict_at_inconclusive(rng):
    """400 well-spread inliers, loop closure 0.0 -- the configuration the
    verdict docstring records as reaching VERIFIED / high -- is capped at
    INCONCLUSIVE when a second engine disagrees, and unchanged when it agrees."""
    pts = rng.uniform(0, 512, size=(400, 2))
    tf = translation(4.0, -3.0)
    kw = dict(transform=tf, src_points=pts, dst_points=tf.apply(pts),
              inlier_mask=np.ones(400, bool), shape=(512, 512), loop_error_px=0.0)
    base = assess(**kw)
    assert base.status == "VERIFIED"
    agree = assess(**kw, engine_agreement_px=0.3)
    assert agree.status == "VERIFIED" and agree.confidence == base.confidence
    disagree = assess(**kw, engine_agreement_px=9.0)
    assert disagree.status == "INCONCLUSIVE" and disagree.confidence == "low"
    assert any(e.name == "engine_agreement_px" and e.verdict == "against" for e in disagree.evidence)
    # never a rejection path
    assert not any(e.name == "engine_agreement_px" and e.verdict == "decisive_against"
                   for e in disagree.evidence)


def test_annotations_reach_metrics_but_not_the_decision(rng):
    pts = rng.uniform(0, 256, size=(50, 2))
    tf = translation(1.0, 1.0)
    v = assess(transform=tf, src_points=pts, dst_points=tf.apply(pts),
               inlier_mask=np.ones(50, bool), shape=(256, 256),
               annotations={"model_selected_by": "held_out_on_refined_points", "x": 1})
    assert v.metrics["model_selected_by"] == "held_out_on_refined_points"
    assert v.metrics["x"] == 1
    assert v.metrics["engine_agreement_px"] is None


# ---------------------------------------------------------------------------
# the command
# ---------------------------------------------------------------------------

def test_siim_register_writes_four_deliverables_with_provenance(tmp_path, big_terrain):
    truth = translation(5.5, -2.25)
    ref, valid = warp(big_terrain, truth, cval=np.nan)
    ref = np.where(valid, ref, np.nanmedian(ref))
    s, r = tmp_path / "src.npy", tmp_path / "ref.npy"
    np.save(s, big_terrain)
    np.save(r, ref)
    out = tmp_path / "out"
    proc = subprocess.run([sys.executable, "-m", "siim", "register", str(s), str(r), "--out", str(out)],
                          capture_output=True, text=True, cwd=ROOT,
                          env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")})
    assert proc.returncode == 0, proc.stderr
    for name in ("points.csv", "registered.npy", "registered.png", "difference.png",
                 "metrics.json", "verdict.json"):
        assert (out / name).exists(), name
    v = json.loads((out / "verdict.json").read_text(encoding="utf-8"))
    assert v["status"] in ("INCONCLUSIVE", "VERIFIED")
    assert v["metrics"]["model_selected_by"] == "held_out_on_refined_points"
    assert v["provenance"]["inputs"]["source"]["sha256"] == __import__("hashlib").sha256(s.read_bytes()).hexdigest()
    assert v["provenance"]["pipeline_order"] == list(PIPELINE_ORDER)
    assert "fit_rmse" in v["excluded"]
    rows = (out / "points.csv").read_text(encoding="utf-8").splitlines()
    header = next(l for l in rows if l.startswith("index,"))
    assert "model_pred_cov_xx_px2" in header and "refine_confidence" in header
    data = [l for l in rows if l and not l.startswith("#") and not l.startswith("index,")]
    assert len(data) == json.loads((out / "metrics.json").read_text())["n_points_rows"]
    # a refined inlier row carries a finite covariance
    inl = next(l for l in data if l.split(",")[1] == "1" and l.split(",")[2] == "1")
    assert float(inl.split(",")[13]) >= 0.0


def test_siim_register_refuses_a_product_for_a_rejected_pair(tmp_path, rng, big_terrain):
    s, r = tmp_path / "src.npy", tmp_path / "ref.npy"
    np.save(s, big_terrain)
    np.save(r, rng.uniform(size=big_terrain.shape))
    out = tmp_path / "out"
    proc = subprocess.run([sys.executable, "-m", "siim", "register", str(s), str(r), "--out", str(out)],
                          capture_output=True, text=True, cwd=ROOT,
                          env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")})
    assert proc.returncode == 3, proc.stderr
    assert (out / "verdict.json").exists() and (out / "points.csv").exists()
    assert not (out / "registered.npy").exists()
    v = json.loads((out / "verdict.json").read_text(encoding="utf-8"))
    assert v["status"] == "REJECTED"
