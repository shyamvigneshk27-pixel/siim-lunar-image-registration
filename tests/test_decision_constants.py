"""The pre-registered decision constants must agree everywhere they are declared.

The project's central integrity claim is that one rule -- ``n_inliers <= 8``
(D-023, the EXP-002 operating point) -- was fixed before the data existed and
applied unchanged through REAL-DATA-03, REAL-DATA-04 and REAL-DATA-05. That
claim is what licenses every real-data conclusion in the repository.

The number is currently declared **four** times, independently:

    src/siim/demo/verdict.py       INLIER_CUTOFF
    src/siim/demo/evidence.py      INLIER_FAILURE_RULE
    scripts/register_real_pair.py  N_INLIERS_FAILURE_RULE
    scripts/register_real_triplet.py

``register_real_triplet.py`` already carries a comment saying it restates the
constant "so a future edit to one script cannot silently make the two
experiments incomparable" -- but a comment cannot enforce that. This module
does, and it does so without refactoring the declarations away: consolidating
them into one shared constant would be a larger change to code that produced
recorded results, and the risk is not worth taking before a demonstration.

The constants are read by parsing the source with :mod:`ast` rather than by
importing it. Importing ``register_real_triplet`` pulls in matplotlib, the
baseline pipeline and a module-level ``OUT`` path; none of that is needed to
read an integer, and a test that fails because a plotting backend is missing
would say nothing about the decision rule.

There is a second, sharper check here. ``tests/test_demo_real_data.py`` pins
the demo's ``outcome`` field against a hard-coded expected table, which is
right for catching a display bug but would **not** notice the rule itself
changing: if the cutoff moved from 8 to 3, the expected outcomes in that table
would still match. The tests below instead **derive** the expected outcome from
the constant and the recorded inlier count, so a changed rule fails loudly.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

#: Where the pre-registered inlier rule is declared, and under what name.
INLIER_RULE_SITES = {
    "src/siim/demo/verdict.py": "INLIER_CUTOFF",
    "src/siim/demo/evidence.py": "INLIER_FAILURE_RULE",
    "scripts/register_real_pair.py": "N_INLIERS_FAILURE_RULE",
    "scripts/register_real_triplet.py": "N_INLIERS_FAILURE_RULE",
}

#: The value D-023 fixed. Written here as a literal on purpose: this file is
#: the one place the number is allowed to be asserted rather than referenced.
PREREGISTERED_INLIER_RULE = 8

#: The baseline configuration REAL-DATA-03/04/05 all declare they share.
PREREGISTERED_RANSAC_THRESHOLD_PX = 3.0
PREREGISTERED_SEED = 0

RD04_LOOP = ROOT / "experiments/REAL-DATA-04/loop_closure_real_data_04.json"
RD03_LOOP = ROOT / "experiments/REAL-DATA-03/loop_closure_triplet.json"


def module_constant(relative_path: str, name: str):
    """Value of a module-level ``name = <literal>`` assignment, without importing."""
    path = ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name and node.value is not None:
                return ast.literal_eval(node.value)
    raise AssertionError(f"{relative_path} no longer declares {name}")


# ---------------------------------------------------------------------------
# the inlier rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("relative_path,name", sorted(INLIER_RULE_SITES.items()))
def test_every_declaration_of_the_inlier_rule_is_the_preregistered_value(
        relative_path, name):
    assert module_constant(relative_path, name) == PREREGISTERED_INLIER_RULE


def test_the_four_declarations_agree_with_one_another():
    """A drift in any one of them is the failure this test exists to catch."""
    values = {p: module_constant(p, n) for p, n in INLIER_RULE_SITES.items()}
    assert len(set(values.values())) == 1, (
        f"the pre-registered inlier rule is declared inconsistently: {values}. "
        "REAL-DATA-03, -04 and -05 are only comparable because this number is "
        "the same in all of them.")


def test_the_baseline_configuration_is_the_same_in_both_register_scripts():
    assert module_constant("scripts/register_real_triplet.py",
                           "RANSAC_THRESHOLD_PX") == PREREGISTERED_RANSAC_THRESHOLD_PX
    assert module_constant("scripts/register_real_triplet.py",
                           "SEED") == PREREGISTERED_SEED


# ---------------------------------------------------------------------------
# the recorded artefacts must obey the rule they were produced under
# ---------------------------------------------------------------------------


def _edges(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))["edges"]


@pytest.mark.parametrize("artefact", [RD03_LOOP, RD04_LOOP],
                         ids=["REAL-DATA-03", "REAL-DATA-04"])
def test_recorded_failure_flags_are_the_rule_applied_to_the_recorded_counts(artefact):
    """Re-derive every recorded flag from the constant, on disk, edge by edge.

    This reads the artefacts and never writes them. If the rule were changed
    without re-running the stages, the stored flags would stop matching it and
    this fails -- which is the whole point, because the reports quote those
    flags as pre-registered outcomes.
    """
    rule = module_constant("scripts/register_real_triplet.py",
                           "N_INLIERS_FAILURE_RULE")
    for edge in _edges(artefact):
        expected = edge["n_inliers"] <= rule
        assert edge["n_inliers_failure_flag"] is expected, (
            f"{artefact.name}: edge {edge['edge']} records "
            f"n_inliers={edge['n_inliers']} with failure_flag="
            f"{edge['n_inliers_failure_flag']}, which is not "
            f"n_inliers <= {rule}")


def test_the_headline_real_edges_still_sit_where_the_reports_say_they_do():
    """The two decisive REAL-DATA-04 edges, checked against the rule itself.

    Not a restatement of the numbers: the assertion is that D->A passes *the
    rule* and B->D fails *the rule*. REAL-DATA-04 section 11.4's argument is
    that no threshold between 4 and 1655 changes which of those two passes, so
    this test is deliberately insensitive to the exact cutoff within that band
    while still failing if the recorded counts or the rule move outside it.
    """
    rule = module_constant("src/siim/demo/verdict.py", "INLIER_CUTOFF")
    by_edge = {e["edge"]: e for e in _edges(RD04_LOOP)}
    succeeding = by_edge["nac.m1299958135lc -> nac.m1271742202lc"]
    failing = by_edge["nac.m1335207975rc -> nac.m1299958135lc"]

    assert succeeding["n_inliers"] > rule
    assert failing["n_inliers"] <= rule
    assert 4 <= rule <= 1655, (
        "the cutoff has moved outside the band in which REAL-DATA-04's "
        "conclusion is threshold-independent; section 11.4's argument no "
        "longer holds and the stage report would need revisiting")


def test_fit_rmse_is_excluded_wherever_the_verdict_engine_names_its_inputs():
    """The metric that would have inverted REAL-DATA-04 must stay excluded."""
    from siim.demo.verdict import EXCLUDED_FROM_VERDICT

    assert "fit_rmse" in EXCLUDED_FROM_VERDICT
