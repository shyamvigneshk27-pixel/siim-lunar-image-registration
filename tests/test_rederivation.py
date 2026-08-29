"""The recorded registration numbers must be re-derivable from the tile bytes.

This is the only check in the repository that compares a recorded number
against an **image** rather than against another recorded number. Everything
else -- asset certification, ``_check_asset_matches_artefact``, the demo
integration tests -- verifies internal consistency, which a sufficiently
careful hand-edit would survive. Re-running the pipeline would not.

**These tests SKIP on a fresh clone**, because the decoded tiles are gitignored
(~166 MB, re-fetchable by the byte ranges and SHA-256 in ``data/manifests/``).
A skip is reported as *"cannot check"*, never as *"checked and fine"* -- that
distinction is E-024's lesson, and ``test_a_skip_is_reported_as_cannot_check``
pins it so the skip can never quietly become a pass.

What a pass establishes: the recorded numbers are genuine pipeline output on
this environment from these bytes. What it does not: that any registration is
correct. The B -> D edge reproduces its ``1.885e-13 px`` fit residual to every
digit while being independently measured hundreds of pixels wrong.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "_rederive", ROOT / "scripts" / "rederive_recorded_registrations.py")
_rederive = importlib.util.module_from_spec(_spec)
sys.modules["_rederive"] = _rederive
_spec.loader.exec_module(_rederive)


def _skip_if_tiles_absent(stage: str) -> None:
    manifest = _rederive.STAGES[stage][0]
    absent = _rederive.missing_tiles(manifest)
    if absent:
        pytest.skip(
            f"CANNOT CHECK (not 'checked and fine'): {len(absent)} tile(s) for "
            f"{stage} are not on disk -- they are gitignored and ~166 MB. "
            f"First missing: {absent[0]}. Re-fetch with the byte ranges in "
            "data/manifests/ and this test becomes live.")


@pytest.mark.parametrize("stage", sorted(_rederive.STAGES))
def test_recorded_registration_numbers_rederive_from_the_tile_bytes(stage):
    """The anti-hardcoding test with actual teeth.

    Loads the archive tiles, applies the stage's preprocessing, runs the
    unmodified baseline, and compares 9 quantities per edge -- including the
    full 3x3 transform matrix -- against the recorded artefact.
    """
    _skip_if_tiles_absent(stage)
    report = _rederive.rederive_stage(stage, verbose=False)
    assert report["fields_checked"] >= 27, (
        f"only {report['fields_checked']} quantities were compared for {stage}; "
        "the artefact is missing fields this check depends on")
    assert not report["mismatches"], (
        "recorded artefact disagrees with the pipeline in this repository:\n"
        + "\n".join(f"  {edge} {field}: recorded {r!r}, re-derived {g!r}"
                    for edge, field, r, g in report["mismatches"]))


def test_the_baseline_configuration_is_read_from_the_artefact_not_hardcoded():
    """The check must not be able to pass by testing a different configuration.

    If the constants were literals in the checking script, editing an
    artefact's ``baseline`` block would leave the check comparing against a
    configuration nobody ran.
    """
    text = (ROOT / "scripts" / "rederive_recorded_registrations.py").read_text(
        encoding="utf-8")
    for key in ("downsample", "ransac_threshold_px", "seed", "model"):
        assert f'base["{key}"]' in text, (
            f"the baseline {key} is not read from the recorded artefact")


def test_the_checker_does_not_reuse_the_producing_scripts_helpers():
    """A check built from the code it checks confirms nothing (E-021's shape)."""
    text = (ROOT / "scripts" / "rederive_recorded_registrations.py").read_text(
        encoding="utf-8")
    assert "register_real_triplet" not in text.split('"""')[2], (
        "the re-derivation imports the producing script; a defect in its "
        "preprocessing would reproduce itself and the check would be circular")


def test_preprocessing_order_is_decimate_then_normalise():
    """MEASURED, load-bearing, and previously undocumented.

    The pipeline computes ``normalise(decimate(tile, k))``. Reversing it is not
    a rounding difference: the percentile stretch is then taken over a
    different population. The audit that first wrote the re-derivation with the
    order reversed measured keypoint counts moving 2-3 %, inliers by up to 60,
    and every fit RMSE changing -- indistinguishable from an irreproducible
    result. This pins the order on real-shaped data.
    """
    rng = np.random.default_rng(20260829)
    tile = rng.normal(1400.0, 60.0, (256, 128))
    tile[:8, :] = 30000.0        # a bright band, as a saturated column would be
    a = _rederive.normalise(_rederive.decimate(tile, 2))
    b = _rederive.decimate(_rederive.normalise(tile), 2)
    assert not np.allclose(a, b), (
        "decimate-then-normalise and normalise-then-decimate agree on this "
        "input, so the test cannot detect the ordering it exists to pin")
    assert _rederive.preprocess(tile, 2).shape == (128, 64)
    assert np.allclose(_rederive.preprocess(tile, 2), a)


def test_a_skip_is_reported_as_cannot_check():
    """E-024's lesson: absent evidence must never read as favourable evidence."""
    import inspect
    src = inspect.getsource(_skip_if_tiles_absent)
    assert "CANNOT CHECK" in src and "checked and fine" in src


def test_missing_tiles_is_reported_distinctly_from_a_mismatch():
    """Exit 2 (cannot check) and exit 1 (checked and wrong) are different answers."""
    text = (ROOT / "scripts" / "rederive_recorded_registrations.py").read_text(
        encoding="utf-8")
    assert "SystemExit(2)" in text and "SystemExit(1)" in text
