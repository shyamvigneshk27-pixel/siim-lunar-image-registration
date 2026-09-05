"""The engine-agreement floor is a measurement, recomputed from the artefact.

REAL-DATA-07 recorded the B1 and B4L transforms (north-up tiles, 2048 x 1024)
for every pair. Pairs where both engines succeed must agree inside the floor;
pairs where one engine failed or was geometry-inconsistent must disagree by
far more. If a re-run changes the rows, this test changes with it.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from siim.geometry import Transform, endpoint_error
from siim.pipeline import AGREEMENT_FLOOR_PX

ROOT = Path(__file__).resolve().parents[1]
ROWS = [ROOT / "experiments" / "REAL-DATA-07" / f"rows_{w}.json" for w in ("rd03", "rd04")]

pytestmark = pytest.mark.skipif(not all(p.exists() for p in ROWS),
                                reason="REAL-DATA-07 row artefacts are not on disk")


def _pairs():
    rows = []
    for p in ROWS:
        rows += [x for x in json.loads(p.read_text(encoding="utf-8"))["rows"]
                 if "engine" in x and x["north_up"]]
    by: dict = {}
    for x in rows:
        by.setdefault((x["window"], x["edge"]), {})[x["engine"]] = x
    agree, other = [], []
    for d in by.values():
        b1, lg = d.get("b1"), d.get("lg")
        if not b1 or not lg or b1["transform_matrix"] is None or lg["transform_matrix"] is None:
            continue
        e = endpoint_error(Transform(np.array(b1["transform_matrix"]), "affine"),
                           Transform(np.array(lg["transform_matrix"]), "affine"),
                           (2048, 1024), step=16)
        (agree if b1["success"] and lg["success"] else other).append(e.median)
    return np.array(agree), np.array(other)


def test_the_floor_separates_agreeing_from_failing_pairs_completely():
    """Original (quarter-turn) rows, B1 vs B4L."""
    agree, other = _pairs()
    assert len(agree) >= 10 and len(other) >= 3
    assert agree.max() <= AGREEMENT_FLOOR_PX, agree.max()
    assert other.min() > AGREEMENT_FLOOR_PX, other.min()
    # the numbers the module docstring quotes
    assert agree.max() == pytest.approx(1.17, abs=0.05)
    assert other.min() == pytest.approx(49.0, abs=1.0)


NUE = [ROOT / "experiments" / "REAL-DATA-07" / f"rows_{w}_nue.json" for w in ("rd03", "rd04")]


@pytest.mark.skipif(not all(p.exists() for p in NUE), reason="amended rows not on disk")
def test_three_engines_agree_inside_the_floor_on_the_corrected_rows():
    """Mirror-corrected rows, B1 / B4L / B4X: every all-success triple agrees
    pairwise inside the floor; every triple with a geometry-inconsistent
    transform disagrees by far more."""
    rows = []
    for p in NUE:
        rows += [x for x in json.loads(p.read_text(encoding="utf-8"))["rows"]
                 if "engine" in x and x["north_up"]]
    by: dict = {}
    for x in rows:
        by.setdefault((x["window"], x["edge"]), {})[x["engine"]] = x
    agree, other = [], []
    for d in by.values():
        if not all(e in d and d[e]["transform_matrix"] for e in ("b1", "lg", "xf")):
            continue
        T = {e: Transform(np.array(d[e]["transform_matrix"]), "affine") for e in ("b1", "lg", "xf")}
        pair = [endpoint_error(T[a], T[b], (2048, 1024), step=16).median
                for a, b in (("b1", "lg"), ("b1", "xf"), ("lg", "xf"))]
        inconsistent = any(str(d[e]["geometry"].get("verdict", "")).startswith("INCONSISTENT")
                           for e in ("b1", "lg", "xf"))
        all_success = all(d[e]["success"] for e in ("b1", "lg", "xf"))
        # Two clean sets: every engine succeeded (rule AND geometry), or at
        # least one transform is geometry-INCONSISTENT. Triples in between (a
        # rule failure whose geometry is merely INCONCLUSIVE) are neither.
        if all_success:
            agree.append(max(pair))
        elif inconsistent:
            other.append(min(pair))
    assert len(agree) >= 20 and len(other) >= 1
    assert max(agree) <= AGREEMENT_FLOOR_PX, max(agree)
    assert min(other) > 10 * AGREEMENT_FLOOR_PX, min(other)
