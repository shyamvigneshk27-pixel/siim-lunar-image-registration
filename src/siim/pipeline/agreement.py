"""Engine agreement as a verifier (next-session plan R2).

The gap this closes
-------------------
Loop closure is exactly invariant to any error that belongs to an image
rather than to an edge (ADR-0011 N1, ``siim.demo.verdict``): a per-image gauge
error reaches VERIFIED / high. Archive geometry catches it, but only where
archive geometry exists, and only at its ~100 px floor. A cheap, always
available piece of *independent* evidence is a second engine: RootSIFT and
DISK + LightGlue share no detector, no descriptor and no assignment, so a
gauge error introduced by one of them (a resampling convention, an off-by-half
keypoint origin) will not be reproduced by the other. Two independent engines
agreeing is evidence; disagreeing is a reason to say INCONCLUSIVE rather than
to pick one.

What agreement is, exactly
--------------------------
The dense endpoint disagreement between the two engines' FINAL transforms
(after refinement and re-estimation), sampled on a grid over the source image
-- the same map-vs-map comparison ``siim.geometry.endpoint_error`` uses for
ground truth, which is what makes it independent of either engine's own
correspondences.

What it is not
--------------
Not an accuracy. Two engines can agree on a wrong answer that both find
attractive (the coherent-wrong of ANALYSIS B6 on periodic texture), and they
will agree on any error that lives in the shared preprocessing.

The floor, measured (2026-09-05, REAL-DATA-07 rows, north-up tiles 2048 x 1024)
----------------------------------------------------------------------------
Dense median disagreement between the B1 and B4L transforms on the 42 pairs
where both engines produced a transform (21 pairs; on the other 21 one engine
had no fit):

* the 17 pairs where BOTH engines succeed (rule passed, geometry consistent
  or inconclusive): median **0.75 px**, p90 1.12 px, **max 1.17 px**;
* the 4 pairs where at least one engine failed the rule or was
  geometry-inconsistent: **min 49 px**, median 584 px.

A floor anywhere between 1.2 and 49 px separates the two sets completely on
this data. This is a measurement on one mare region at one GSD with
n = 17 + 4, not a universal constant; ``tests/test_agreement_floor.py``
recomputes it from the artefact so a change in the rows changes the test.

Three engines, mirror-corrected run (2026-09-06, ``rows_*_nue.json``)
--------------------------------------------------------------------
On the 24 pairs where B1, B4L and B4X all succeed, the largest pairwise
disagreement is **2.16 px** (B1 vs XFeat; B1 vs B4L max 1.17, B4L vs XFeat
max 1.99): XFeat localises about a pixel worse than the other two before
refinement. Where at least one engine's transform is geometry-INCONSISTENT
the smallest pairwise disagreement is **247 px**. The floor is therefore set
at **3 px**: above every agreeing triple, two orders of magnitude below every
disagreeing one, and still the scale of loop closure's 2 px threshold.
(A B1/XFeat pair where one engine merely failed the inlier RULE while both
transforms were right disagrees by as little as 1.4 px; that is agreement
doing its job, not a counter-example -- the rule and the geometry are
separate signals.)
"""

from __future__ import annotations

from dataclasses import dataclass

from ..geometry import Transform, endpoint_error

__all__ = ["AGREEMENT_FLOOR_PX", "EngineAgreement", "engine_agreement"]

#: Measured on the REAL-DATA-07 rows (module docstring): agreeing pairs max 1.17 px
#: (B1/B4L) and 2.16 px (three engines); disagreeing pairs min 49 px / 247 px.
AGREEMENT_FLOOR_PX = 3.0


@dataclass(frozen=True)
class EngineAgreement:
    engine_a: str
    engine_b: str
    median_px: float
    p90_px: float
    max_px: float
    floor_px: float
    #: True = agree within the floor; False = disagree; None = one engine
    #: produced no transform, so nothing could be compared.
    agree: bool | None
    statement: str


def engine_agreement(engine_a: str, transform_a: Transform | None,
                     engine_b: str, transform_b: Transform | None,
                     shape: tuple[int, int], *, floor_px: float = AGREEMENT_FLOOR_PX,
                     step: int = 16) -> EngineAgreement:
    """Dense disagreement between two engines' transforms over ``shape``."""
    if transform_a is None or transform_b is None:
        missing = engine_a if transform_a is None else engine_b
        return EngineAgreement(engine_a, engine_b, float("nan"), float("nan"), float("nan"),
                               floor_px, None,
                               f"{missing} produced no transform; agreement not evaluated.")
    e = endpoint_error(transform_a, transform_b, shape, step=step)
    agree = bool(e.median <= floor_px)
    if agree:
        st = (f"{engine_a} and {engine_b} agree: median disagreement {e.median:.3f} px "
              f"(p90 {e.p90:.3f}) within the {floor_px:.1f} px floor. Independent "
              "detectors, descriptors and assignment; a per-engine gauge error would "
              "not survive this. Floor measured on REAL-DATA-07 (agree <= 2.2 px, disagree >= 49 px).")
    else:
        st = (f"{engine_a} and {engine_b} DISAGREE: median {e.median:.2f} px "
              f"(max {e.max:.2f}) against a {floor_px:.1f} px floor. At least one "
              "engine is wrong and nothing here says which; the verdict cannot be "
              "VERIFIED.")
    return EngineAgreement(engine_a, engine_b, float(e.median), float(e.p90), float(e.max),
                           floor_px, agree, st)
