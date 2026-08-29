"""The scale limit of the unmodified baseline, and WHY it is where it is.

The problem statement names scale variation as a core challenge and its sensor
ladder implies ratios to ~320:1 (OHRC 0.25 m against IIRS 80 m). EXP-001 swept
to 4x and stopped, so *"what happens at 320:1?"* had no answer.

``scripts/measure_scale_limit.py`` measures it. These tests pin the two facts
that make the answer defensible rather than merely numeric:

1. **Where** the limit is, per realistic regime -- and it must not silently
   improve, because an improvement would mean the matcher changed.
2. **Why** it is there. Every failure observed is **detector starvation** (the
   downscaled image is too small to contain features), not descriptor failure.
   That distinction decides the fix: starvation is a sampling problem whose
   remedy is normalising both images to a common ground sampling distance
   before matching (D-005, designed and NOT implemented), whereas descriptor
   failure would be a matcher problem.

Synthetic only. Illumination is identical in both images, so scale is the sole
variable. Nothing here licenses any claim about OHRC, TMC-2 or IIRS.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARTEFACT = ROOT / "experiments" / "EXP-001" / "scale_limit_probe.json"


@pytest.fixture(scope="module")
def probe() -> dict:
    if not ARTEFACT.exists():
        pytest.skip(
            "CANNOT CHECK (not 'checked and fine'): "
            f"{ARTEFACT.relative_to(ROOT)} is absent. Regenerate with "
            "`python scripts/measure_scale_limit.py --out scale_limit_probe.json`")
    return json.loads(ARTEFACT.read_text(encoding="utf-8"))


def test_illumination_is_held_fixed_so_scale_is_the_only_variable(probe):
    """Otherwise this would reproduce EXP-003's confound rather than measure scale."""
    cfg = probe["configuration"]
    assert "IDENTICAL" in cfg["illumination"]
    assert cfg["sun_azimuth_deg"] is not None
    assert cfg["sun_elevation_deg"] is not None


def test_the_failure_rule_is_the_preregistered_one(probe):
    """D-023, applied. Not re-derived, not softened for this measurement."""
    assert "n_inliers <= 8" in probe["configuration"]["failure_rule"]


def test_mare_stops_at_4x_and_highlands_at_8x(probe):
    """The measured limits, per realistic regime.

    Mare is the harder case and independently reproduces EXP-001's 4x, which
    is a check on both. If either number rises, the matcher or the terrain
    generator changed and the stage reports quoting them need revisiting --
    so this asserts equality, not a lower bound.
    """
    s = probe["summary"]
    assert s["A_mare_moderate"]["last_ratio_passing_all_seeds"] == 4
    assert s["A_highlands_moderate"]["last_ratio_passing_all_seeds"] == 8


def test_every_observed_failure_is_detector_starvation_not_descriptor_failure(probe):
    """The finding that decides what the fix is.

    If a descriptor failure ever appears, SIFT's scale invariance is the
    binding constraint and a normalisation stage will NOT rescue it. Until
    then, the limit is a sampling problem.
    """
    causes = {c["failure_cause"] for c in probe["cases"] if c["failure_cause"]}
    assert causes == {"detector_starvation"}, (
        f"a non-starvation failure appeared: {causes - {'detector_starvation'}}. "
        "The scale limit is no longer purely a sampling problem and D-005's "
        "normalisation stage would not be sufficient to fix it")


def test_mare_yields_literally_zero_keypoints_at_8x(probe):
    """D-026's texture poverty, in its sharpest form.

    At 128x128 a mare tile produces **no** SIFT keypoints at all -- not few,
    none. This is why mare fails an octave earlier than highlands, and it is
    an independent confirmation of the mare-poverty result that EXP-002 and
    REAL-DATA-03 both rely on.
    """
    cells = [c for c in probe["cases"]
             if c["regime"] == "A_mare_moderate" and c["ratio"] == 8]
    assert cells and all(c["n_keypoints_src"] == 0 for c in cells)


def test_the_artefact_refuses_the_claims_it_cannot_support(probe):
    """A measurement that does not state its scope invites being over-quoted."""
    text = " ".join(probe["claims_not_supported"]).upper()
    for term in ("OHRC", "IIRS", "SYNTHETIC", "320:1"):
        assert term in text
    assert "NOT a pre-registered experiment" in probe["status"]


def test_exp001_recorded_results_are_untouched():
    """This measurement adds a file; it does not edit EXP-001's output."""
    results = ROOT / "experiments" / "EXP-001" / "results.csv"
    assert results.exists()
    header = results.read_text(encoding="utf-8").splitlines()[0]
    assert header.startswith("group,label,scene,model,root_sift")
