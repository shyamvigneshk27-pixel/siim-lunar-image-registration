"""Registration verdict: MATCH -> REGISTER -> VERIFY -> EXPLAIN.

This module is the project's differentiator (design principle §26). It does not
answer "where do these images align" -- ``ransac`` already does that. It answers
the two questions that make a registration usable:

    "Why should I trust this alignment?"
    "When should I refuse to trust it?"

Every number below is measured. Nothing here invents a confidence score.

What the evidence is, and what each piece is worth
--------------------------------------------------
The project has measured, over four stages, which signals actually carry
information about correctness:

* ``n_inliers`` -- the best single deployable signal. EXP-002 validated
  ``n_inliers <= 8`` at recall 1.000 / FPR 0.0112 on 192 unseen cases, and
  D-023 fixed the rule form. **But EXP-003 measured its false-alarm rate at
  0.369 in a mixed correct/wrong regime** -- 33x worse. So it is treated here
  as a strong FAILURE detector and a weak success gate: few inliers is decisive
  evidence against, many inliers is only weak evidence for.
* ``loop_error`` -- the only GT-free estimator shown to detect a *coherent
  wrong* solution (ADR-0011; EXP-003 measured 1.000 detection / 0.000 false
  alarm at loop level). Decisive when a third image is available, absent
  otherwise.
* ``coverage_max_gap`` -- bounds worst-case local error, because error grows
  with distance to the nearest constraint (ADR-0006). It caught a
  correct-but-fragile 8-inlier case in EXP-001 that error metrics called a
  success, and independently flagged the 2-inlier fluke in EXP-002.
* ``inlier_ratio`` -- self-consistency only. EXP-002: recall 0.913, misses 8.7%
  of failures. Supporting evidence, never decisive.
* ``fit_rmse`` -- **carries no failure information at all.** EXP-002 measured
  ROC AUC 0.4947 as a failure detector against a pre-declared negative control:
  indistinguishable from a coin flip, and *inverted* in the failure regime
  (EXP-001: 10 of 17 catastrophic failures reported < 1e-12 px). It is reported
  here for transparency and is **structurally excluded from the verdict** --
  see ``EXCLUDED_FROM_VERDICT``.

What this engine deliberately does NOT evaluate
------------------------------------------------
It assesses **correspondence evidence** -- how many points survived geometric
verification, how they are distributed, whether an independent loop closes. It
does **not** assess whether the estimated transform is geometrically plausible
for the scene. REAL-DATA-04's ``B -> D`` edge recovered singular values of
1.806 and 0.185 with a rotation of -105.2 deg between two near-nadir frames of
the same ground -- a physically absurd result -- and this engine rejected it on
``n_inliers = 3`` without ever remarking on the transform itself.

That gap is recorded here as a **limitation, not a defect to be patched**.
Transform plausibility is checked by a separate instrument,
``scripts/check_transform_against_geometry.py``, which compares the estimate
against archive corner geometry and SPICE-derived ``SCALED_PIXEL``. It runs
**after** the decision, deliberately: it classifies a passing edge (class B vs
class C) and is reported either way, but it cannot move an edge across the
pass/fail line, because that line was fixed before the data existed.

**Do not add geometric plausibility as a verdict criterion.** Doing so would
introduce a new rejection path into a rule that REAL-DATA-03, -04 and -05 all
declare they applied unchanged, and would retroactively alter what those stages
were evaluated under. The correct place for a new check is a new diagnostic
reported beside the verdict, not inside it.

A per-image gauge error reaches VERIFIED / high
-----------------------------------------------
This is the consequence, at the level of this engine, of the null space recorded
in ADR-0011 note N1: loop closure is *exactly* invariant to any error belonging
to an **image** rather than to an **edge**, because the per-image terms cancel
around the composition. Measured, end to end through :func:`assess`: 400
well-spread inliers and a transform **64 px wrong**, with loop closure returning
**0.0** because the error cancels, come back **VERIFIED / high** at a coverage
gap of 0.082, and **VERIFIED / moderate** at 0.541. Every signal this engine
consults is satisfied, and the answer is still wrong.

The realistic instances are ordinary photogrammetry and ordinary software:
per-frame interior orientation, line-scan jitter, and an uncorrected per-image
resampling convention -- E-001's shape, and the class of defect behind E-025 and
E-030, both of which this project actually committed. Detecting it **requires
evidence from outside the loop**, and ``scripts/check_transform_against_geometry.py``
is such evidence precisely because it is **per-image by construction**: it
predicts pixel-to-pixel correspondence from each frame's own archive corners, so
a gauge attached to one image moves its prediction rather than cancelling.

This is recorded as a **limitation, not a defect to be patched** -- the paragraph
above applies unchanged.

Confidence is therefore an ordinal band backed by named evidence, not a
probability. A number like 0.97 would imply a calibration this project has not
earned, and §12 forbids inventing one.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from ..evaluation.coverage import coverage_metrics
from ..geometry import Transform

__all__ = ["Verdict", "Evidence", "assess", "EXCLUDED_FROM_VERDICT"]

#: Signals deliberately never allowed to influence the verdict, with the
#: measurement that disqualified each. Kept as data so the exclusion is
#: auditable rather than a comment someone can quietly delete.
EXCLUDED_FROM_VERDICT: dict[str, str] = {
    "fit_rmse": (
        "ROC AUC 0.4947 as a failure detector on 192 unseen cases "
        "(EXP-002 objective 3, pre-declared negative control). Inverted in the "
        "failure regime: EXP-001 measured 10 of 17 catastrophic failures "
        "reporting fit RMSE below 1e-12 px while 190-2400 px wrong."
    ),
    "held_out_residual": (
        "Detection 0.200 against coherent wrong solutions (EXP-002 objective 4, "
        "ADR-0011). A match set 64 px wrong yielded 0.468 px -- lower than a "
        "correct-but-noisy set at 1.424 px. Degeneracy detector only."
    ),
    "cycle_consistency": (
        "Blind to symmetric errors by construction (E-012): forward +64 px and "
        "backward -64 px cancel exactly, scoring 0.000 on wrong cases against "
        "0.325 on the correct one -- an inverted signal."
    ),
}

#: The deployable failure rule (D-023). Form matters: '<= 8', not '< 8'.
INLIER_CUTOFF = 8
#: Coverage above this means the transform is extrapolating (ADR-0006).
COVERAGE_GAP_WARN = 0.15
#: Loop closure above this is a hard reject (EXP-003: correct loops 0.258 px
#: median, wrong loops 1368 px -- the gap is four orders of magnitude, so the
#: exact value is not delicate).
LOOP_ERROR_REJECT_PX = 2.0


@dataclass(frozen=True)
class Evidence:
    """One measured piece of evidence and what it says."""

    name: str
    value: float | None
    verdict: str          # "supports" | "against" | "inconclusive" | "decisive_against"
    weight: str           # "decisive" | "strong" | "supporting" | "excluded"
    statement: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Verdict:
    """The full answer: what was estimated, and whether to trust it."""

    status: str                      # "VERIFIED" | "REJECTED" | "INCONCLUSIVE"
    confidence: str                  # "high" | "moderate" | "low" | "none"
    reasons: list[str]               # why, in plain language
    evidence: list[Evidence] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    excluded: dict[str, str] = field(default_factory=lambda: dict(EXCLUDED_FROM_VERDICT))

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence"] = [e.as_dict() for e in self.evidence]
        return d


def _finite(x) -> float | None:
    try:
        v = float(x)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def assess(
    *,
    transform: Transform | None,
    src_points: np.ndarray,
    dst_points: np.ndarray,
    inlier_mask: np.ndarray,
    shape: tuple[int, int],
    fit_rmse: float | None = None,
    loop_error_px: float | None = None,
    roi: np.ndarray | None = None,
    engine_agreement_px: float | None = None,
    engine_agreement_floor_px: float = 2.0,
    annotations: dict[str, Any] | None = None,
) -> Verdict:
    """Decide whether an estimated registration should be trusted, and say why.

    ``loop_error_px`` is optional because it needs a third overlapping image.
    When absent, that is stated as a limit on the verdict rather than silently
    treated as a pass -- the strongest available check simply was not run.

    ``engine_agreement_px`` (added 2026-09-05, next-session plan R2) is the
    dense disagreement between two independent engines' final transforms
    (``siim.pipeline.engine_agreement``). It is optional and was never
    supplied by any recorded stage, so those stages' verdicts are unchanged.
    When supplied and at or above ``engine_agreement_floor_px`` the verdict is
    capped at INCONCLUSIVE: two independent engines disagreeing is a reason to
    refuse, not to choose. It never REJECTS -- rejection stays with the
    pre-registered rule and loop closure -- and it never raises a verdict.

    ``annotations`` are merged into ``metrics`` verbatim and never consulted
    by the decision. The pipeline uses it for ``model_selected_by`` (D-045).
    """
    ev: list[Evidence] = []
    reasons: list[str] = []

    n_in = int(np.asarray(inlier_mask).sum()) if np.size(inlier_mask) else 0
    n_put = int(np.asarray(src_points).shape[0]) if np.size(src_points) else 0
    ratio = (n_in / n_put) if n_put else 0.0

    # ---- no model at all -------------------------------------------------
    if transform is None:
        return Verdict(
            status="REJECTED", confidence="none",
            reasons=["No geometric model could be estimated from the "
                     f"{n_put} putative correspondences."],
            evidence=[Evidence("n_putative", float(n_put), "decisive_against",
                               "decisive", "No transform was produced.")],
            metrics={"n_putative": n_put, "n_inliers": 0,
                     **(dict(annotations) if annotations else {})},
        )

    inl = np.asarray(inlier_mask, dtype=bool)
    src_in = np.asarray(src_points)[inl] if n_in else np.zeros((0, 2))
    cov = coverage_metrics(src_in, shape, roi=roi)
    gap = _finite(cov.max_uncovered_disc_ratio)

    # ---- 1. inlier count: decisive against, weak for (D-023 + EXP-003) ----
    if n_in <= INLIER_CUTOFF:
        ev.append(Evidence(
            "n_inliers", float(n_in), "decisive_against", "decisive",
            f"Only {n_in} inliers (rule: reject at <= {INLIER_CUTOFF}). "
            "Validated at recall 1.000 on 192 unseen cases (EXP-002)."))
        reasons.append(
            f"Too few verified correspondences: {n_in} (threshold {INLIER_CUTOFF}). "
            "Near the model's degrees of freedom, a fit can match its own points "
            "exactly while being catastrophically wrong.")
    else:
        ev.append(Evidence(
            "n_inliers", float(n_in), "supports", "supporting",
            f"{n_in} inliers, above the reject threshold. Weak positive "
            "evidence only: this rule's false-alarm rate was 0.369 in a mixed "
            "regime (EXP-003), so a high count is not proof of correctness."))

    # ---- 2. loop closure: decisive when available (ADR-0011) --------------
    loop = _finite(loop_error_px)
    if loop is None:
        ev.append(Evidence(
            "loop_error_px", None, "inconclusive", "decisive",
            "Not evaluated -- needs a third overlapping image. This is the only "
            "estimator shown to catch a coherent wrong solution, so the verdict "
            "is weaker than it could be."))
    elif loop >= LOOP_ERROR_REJECT_PX:
        ev.append(Evidence(
            "loop_error_px", loop, "decisive_against", "decisive",
            f"Loop closure {loop:.2f} px (reject at >= {LOOP_ERROR_REJECT_PX}). "
            "Detection 1.000 at false alarm 0.000 (EXP-003)."))
        reasons.append(
            f"Loop closure fails: composing the three estimated transforms around "
            f"the image triplet leaves {loop:.2f} px of error instead of returning "
            "to the start. A uniformly shifted -- and therefore perfectly "
            "self-consistent -- wrong answer cannot hide from this.")
    else:
        ev.append(Evidence(
            "loop_error_px", loop, "supports", "decisive",
            f"Loop closure {loop:.3f} px. Independent of the fit, and the only "
            "check that detects a coherent wrong solution."))

    # ---- 3. coverage: bounds worst-case local error (ADR-0006) -----------
    if gap is None:
        ev.append(Evidence("coverage_max_gap", None, "inconclusive", "supporting",
                           "Coverage could not be computed."))
    elif gap > COVERAGE_GAP_WARN:
        ev.append(Evidence(
            "coverage_max_gap", gap, "against", "strong",
            f"Largest unconstrained region is {gap:.3f} of the image "
            f"(target <= {COVERAGE_GAP_WARN}). The transform is extrapolating "
            "where there are no correspondences."))
        reasons.append(
            f"Correspondences are clustered: {gap:.3f} of the overlap has no "
            "nearby constraint, so the alignment is extrapolated there even if "
            "it is accurate where the points are.")
    else:
        ev.append(Evidence(
            "coverage_max_gap", gap, "supports", "strong",
            f"Correspondences span the overlap (largest gap {gap:.3f})."))

    # ---- 4. inlier ratio: supporting only --------------------------------
    ev.append(Evidence(
        "inlier_ratio", ratio,
        "supports" if ratio >= 0.5 else "against", "supporting",
        f"{n_in}/{n_put} putative matches survived geometric verification. "
        "Self-consistency only: misses 8.7% of failures (EXP-002)."))

    # ---- 5. fit_rmse: reported, structurally excluded ---------------------
    ev.append(Evidence(
        "fit_rmse", _finite(fit_rmse), "inconclusive", "excluded",
        "Reported for transparency and EXCLUDED from the verdict. "
        + EXCLUDED_FROM_VERDICT["fit_rmse"]))

    # ---- 6. engine agreement: caps at INCONCLUSIVE, never rejects ---------
    agreement = _finite(engine_agreement_px)
    engines_disagree = False
    if agreement is not None:
        if agreement >= engine_agreement_floor_px:
            engines_disagree = True
            ev.append(Evidence(
                "engine_agreement_px", agreement, "against", "strong",
                f"Two independent engines disagree by {agreement:.2f} px median "
                f"(floor {engine_agreement_floor_px:.1f} px). At least one is wrong; "
                "the verdict is capped at INCONCLUSIVE. Floor provisional."))
            reasons.append(
                f"A second, independent engine reached a different alignment "
                f"({agreement:.2f} px apart). Nothing here says which is right, so "
                "neither is trusted.")
        else:
            ev.append(Evidence(
                "engine_agreement_px", agreement, "supports", "strong",
                f"Two independent engines agree to {agreement:.3f} px median "
                f"(floor {engine_agreement_floor_px:.1f} px). Independent of loop "
                "closure's per-image null space; not an accuracy. Floor provisional."))

    # ---- combine ---------------------------------------------------------
    decisive_against = [e for e in ev if e.verdict == "decisive_against"]
    against = [e for e in ev if e.verdict == "against"]
    loop_ok = loop is not None and loop < LOOP_ERROR_REJECT_PX

    if decisive_against:
        status, confidence = "REJECTED", "none"
    elif engines_disagree:
        status, confidence = "INCONCLUSIVE", "low"
        reasons.append(
            "Independent engines disagree, so the alignment is not reported as "
            "verified even where the other checks pass.")
    elif loop_ok and not against:
        status, confidence = "VERIFIED", "high"
        reasons.append(
            "Independent loop closure agrees, correspondences are numerous and "
            "well spread. This is the strongest evidence the system can produce "
            "without ground truth.")
    elif loop_ok and against:
        status, confidence = "VERIFIED", "moderate"
        reasons.append("Loop closure agrees, but coverage is weak: trust the "
                       "alignment near the correspondences more than far from them.")
    elif not against:
        status, confidence = "INCONCLUSIVE", "moderate"
        reasons.append(
            "No evidence against, but the decisive check (loop closure) was not "
            "run. A self-consistent wrong answer cannot be excluded from a single "
            "image pair -- supply a third overlapping image to settle it.")
    else:
        status, confidence = "INCONCLUSIVE", "low"
        reasons.append(
            "Evidence is mixed and the decisive check was not run.")

    return Verdict(
        status=status, confidence=confidence, reasons=reasons, evidence=ev,
        metrics={
            "n_putative": n_put, "n_inliers": n_in, "inlier_ratio": ratio,
            "coverage_max_gap": gap,
            "coverage_occupancy": _finite(cov.grid_occupancy),
            "fit_rmse": _finite(fit_rmse),
            "loop_error_px": loop,
            "engine_agreement_px": agreement,
            "transform_model": transform.model,
            "transform_matrix": np.asarray(transform.matrix).tolist(),
            **(dict(annotations) if annotations else {}),
        },
    )
