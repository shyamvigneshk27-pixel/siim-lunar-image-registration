"""Recorded artefacts must describe themselves correctly -- or knowably wrongly.

E-033, found by the 2026-08-29 pre-freeze audit. Five judge-facing artefacts
record a ``stage`` field naming the stage of the *script's default*, not of the
run that produced them. The scientific content of all five was independently
recomputed and reproduces; the defect is a label.

The artefacts are **not edited** -- integrity rule 3 -- so this test does the
only honest thing available: it enumerates the mismatches that are recorded
history, and **fails if a new one appears**. That converts a field nothing
checked into a field something checks, which is E-033's whole lesson.

The producing scripts now derive ``stage`` from their output directory, so a
future run cannot add to this list. If one does, this test is what says so.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: The five artefacts whose ``stage`` field disagrees with where they live.
#: Recorded as history, with the value each actually carries. Nothing may be
#: added here without a ledger entry explaining why a NEW artefact was written
#: with a wrong label after the scripts were fixed.
KNOWN_STALE_STAGE_LABELS = {
    "experiments/REAL-DATA-03/overlap_triplet.json": "REAL-DATA-02",
    "experiments/REAL-DATA-03/overlap_usable_geo.json": "REAL-DATA-02",
    "experiments/REAL-DATA-04/overlap_real_data_04.json": "REAL-DATA-02",
    "experiments/REAL-DATA-04/transform_vs_geometry_real_data_04.json": "REAL-DATA-03",
    "data/manifests/real_quad_d_geo_manifest.json": "REAL-DATA-03",
}


def _artefacts_with_a_stage_field():
    out = {}
    for pattern in ("experiments/**/*.json", "data/manifests/*.json"):
        for path in sorted(ROOT.glob(pattern)):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(doc, dict) and isinstance(doc.get("stage"), str):
                rel = path.relative_to(ROOT).as_posix()
                out[rel] = doc["stage"]
    return out


def _expected_stage(rel: str) -> str | None:
    """The stage an artefact's location implies, or None if it implies nothing."""
    parts = rel.split("/")
    if parts[0] == "experiments" and parts[1].startswith("REAL-DATA"):
        return parts[1]
    return None


def test_no_new_artefact_records_the_wrong_stage():
    """The regression guard. A NEW mismatch is a defect; the five are history."""
    found = {}
    for rel, stage in _artefacts_with_a_stage_field().items():
        expected = _expected_stage(rel)
        if expected is not None and stage != expected:
            found[rel] = stage
    manifest_stale = {
        rel: stage for rel, stage in _artefacts_with_a_stage_field().items()
        if rel in KNOWN_STALE_STAGE_LABELS and rel.startswith("data/manifests/")
    }
    found.update(manifest_stale)

    new = {k: v for k, v in found.items() if k not in KNOWN_STALE_STAGE_LABELS}
    assert not new, (
        "artefact(s) record a stage that disagrees with where they live, and "
        f"are not in the E-033 known list: {new}. The producing scripts derive "
        "`stage` from --outdir, so this means a script regressed or a new one "
        "hard-codes a literal.")


def test_the_known_stale_labels_are_still_exactly_as_recorded():
    """History must not drift either.

    If one of the five is silently corrected, that is a recorded artefact being
    rewritten -- which integrity rule 3 forbids and which this test catches
    just as loudly as a new mismatch.
    """
    actual = _artefacts_with_a_stage_field()
    for rel, stage in KNOWN_STALE_STAGE_LABELS.items():
        assert rel in actual, f"{rel} no longer carries a `stage` field"
        assert actual[rel] == stage, (
            f"{rel} recorded stage {stage!r} and now reads {actual[rel]!r}. "
            "A recorded artefact was edited. If that was deliberate, it needs "
            "a ledger entry, not a quiet test update.")


def test_scripts_no_longer_hard_code_a_stage_literal_in_their_report():
    """The fix itself, pinned. E-033's lesson is that nothing checked this."""
    for name in ("verify_tile_overlap.py", "check_transform_against_geometry.py"):
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert '"stage": args.stage or' in text, (
            f"{name} no longer derives its recorded stage from its arguments; "
            "E-033 will recur")
