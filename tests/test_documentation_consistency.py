"""The judge-facing documents must not contradict the decisions they cite.

`README.md` declares: *"The design documents are normative. Code that
contradicts them is a bug."* That cuts both ways -- a normative document that
still prescribes a method the project's own experiment refuted makes correct
code look like a defect, and it is the cheapest thing for a reviewer to find.

Three audits found three separate instances of the same shape: a claim withdrawn
in the ledger while the document that made it carried no pointer to the
withdrawal (REAL-DATA-04's report, `research_log.md` RL-035, and
`00_PROJECT_ANALYSIS.md` section B2). Each was fixed by a dated banner with the
body preserved. **Nothing checked for the next one.** This module is that check.

It asserts pointers and wording, never numbers -- it cannot be satisfied by
changing a measurement, only by keeping the prose consistent with the ADRs and
the decision ledger.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# ADR-0004 / EXP-003 -- the refuted prescription in the normative document
# ---------------------------------------------------------------------------

def test_analysis_b2_carries_its_supersession_banner():
    """B2 prescribes a polarity-agnostic representation; EXP-003 refuted it.

    ADR-0004, which encoded that prescription, is SUPERSEDED. The analysis
    document is declared normative by the README, so the supersession has to be
    visible where the prescription is, not only in the ADR register.
    """
    doc = _read("docs/00_PROJECT_ANALYSIS.md")
    prescription = "the illumination-robust representation must be **polarity-agnostic**"
    assert prescription in doc, (
        "B2's prescription has changed or been deleted. It must be PRESERVED "
        "(the body is historical) and carry a banner -- not be rewritten")

    banner = doc.split("### B2 —")[0]
    assert "SUPERSEDED" in banner, "section B2 has no supersession banner above it"
    for token in ("EXP-003", "ADR-0004", "D-024"):
        assert token in banner, f"B2's banner does not cite {token}"
    assert "physics below is unaffected" in banner.lower() or \
           "physics is unaffected" in banner.lower(), (
        "the banner must separate B2's physics (a definitional fact, still "
        "true) from its prescription (refuted) -- withdrawing both would be "
        "an overcorrection")
    assert "not started" in banner.lower(), (
        "the banner cites D-024, whose status depends on EXP-004; it must say "
        "EXP-004 is not started rather than implying the mechanism is settled")


def test_adr_0004_is_still_recorded_as_superseded():
    """The banner's premise. If this flips, the banner is wrong, not stale."""
    adr = _read("docs/architecture_decisions.md")
    block = adr.split("## ADR-0004")[1].split("## ADR-0005")[0] \
        if "## ADR-0005" in adr else adr.split("## ADR-0004")[1]
    assert "SUPERSEDED" in block


# ---------------------------------------------------------------------------
# ADR-0011 -- the loop-closure null space, and its consequence in the engine
# ---------------------------------------------------------------------------

def test_verdict_docstring_records_that_a_gauge_error_reaches_verified_high():
    """ADR-0011 N1 says loop closure cannot see per-image error.

    The question a reviewer asks next is *"so what does your verdict return in
    that case?"*. The answer is VERIFIED / high on a transform 64 px wrong, and
    it must be written where the engine's limitations are listed -- not left to
    be discovered.
    """
    from siim.demo import verdict
    doc = verdict.__doc__ or ""
    assert "gauge" in doc.lower(), "the verdict docstring does not name the gauge case"
    assert "VERIFIED / high" in doc or "VERIFIED/high" in doc, (
        "the docstring must state the ACTUAL outcome, not merely that a "
        "limitation exists")
    assert "64 px" in doc, "the measured case is not quoted"
    assert "check_transform_against_geometry" in doc, (
        "the docstring must name the evidence that CAN detect a gauge error, "
        "or it records a hole with no route out of it")
    assert "per-image by construction" in doc, (
        "it must say WHY that check works here -- being per-image is the "
        "property, not being independent in general")


def test_the_gauge_paragraph_did_not_become_a_verdict_criterion():
    """Documentation only. The frozen constants must be untouched."""
    from siim.demo.verdict import (COVERAGE_GAP_WARN, EXCLUDED_FROM_VERDICT,
                                   INLIER_CUTOFF, LOOP_ERROR_REJECT_PX)
    assert INLIER_CUTOFF == 8
    assert COVERAGE_GAP_WARN == 0.15
    assert LOOP_ERROR_REJECT_PX == 2.0
    assert set(EXCLUDED_FROM_VERDICT) == {
        "fit_rmse", "held_out_residual", "cycle_consistency"}


# ---------------------------------------------------------------------------
# D-040-N1 -- the withdrawn frame-identity claim, wherever it is asserted
# ---------------------------------------------------------------------------

#: Files that assert "frame identity is refuted" in preserved historical text.
#: Each must carry a banner withdrawing it. A NEW file appearing here is a
#: regression: the claim was reintroduced somewhere without a pointer.
HISTORICAL_REFUTATION_CLAIMS = {
    "docs/research_log.md",
    "docs/stages/REAL-DATA-04_illumination_vs_frame_identity.md",
}


def test_every_file_asserting_the_withdrawn_claim_carries_a_banner():
    pattern = re.compile(r"frame identity is refuted", re.IGNORECASE)
    offenders = set()
    for path in ROOT.glob("**/*.md"):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        if not pattern.search(text):
            continue
        if rel == "docs/stages/DECISION_LEDGER.md":
            continue  # D-040-N1 itself -- it performs the withdrawal
        offenders.add(rel)
        assert "SUPERSEDED" in text and "D-040-N1" in text, (
            f"{rel} asserts 'frame identity is refuted' with no superseding "
            "banner and no pointer to D-040-N1")
    new = offenders - HISTORICAL_REFUTATION_CLAIMS
    assert not new, (
        f"the withdrawn claim appears in new file(s): {sorted(new)}. Add the "
        "banner and register the file here, or remove the claim")


def test_the_current_position_is_stated_in_the_reader_facing_documents():
    for rel in ("README.md", "docs/stages/STAGE-INDEX.md", "docs/STAGE_HISTORY.md"):
        assert "not conclusively refuted" in _read(rel).lower(), (
            f"{rel} does not state the current position on frame identity")


# ---------------------------------------------------------------------------
# README vs the decisions it depends on
# ---------------------------------------------------------------------------

def test_readme_does_not_contradict_adr_0011_on_what_evidences_accuracy():
    """ADR-0011: held-out residual and cycle consistency are degeneracy
    detectors and "must never be described as protection against a
    wrong-but-consistent answer"."""
    rd = _read("README.md")
    assert not re.search(r"[Aa]ccuracy is instead evidenced by[^.]*held-out", rd), (
        "the README lists held-out residuals as accuracy evidence, which "
        "ADR-0011 forbids")
    assert "degeneracy detectors only" in rd


def test_readme_does_not_claim_scale_normalisation_is_implemented():
    """D-005 is designed, not built. `src/siim` contains no such stage."""
    rd = _read("README.md")
    assert not re.search(r"scale normalisation is a first-class pipeline stage", rd)
    assert "NOT implemented" in rd


def test_readme_does_not_claim_an_unregistered_experiment_exists():
    rd = _read("README.md")
    assert "EXP-006 exists" not in rd
    assert "not pre-registered and has not been started" in rd


@pytest.mark.parametrize("stage", ["EXP-004", "EXP-006"])
def test_unstarted_experiments_are_never_described_as_started(stage):
    for rel in ("README.md", "docs/stages/STAGE-INDEX.md"):
        text = _read(rel)
        if stage not in text:
            continue
        assert not re.search(rf"{stage}\s+(?:is\s+)?(?:complete|completed|passed)",
                             text, re.IGNORECASE), (
            f"{rel} describes {stage} as complete; it has not been started")
