# STAGE-XXX — <Stage name>

> **Template.** Copy this file to `docs/stages/<STAGE-ID>_<NAME>.md` at the moment a stage is *planned*, fill Part 1, then append Part 2 once it has run.
>
> **This file is append-only in spirit.** A stage report is never rewritten to make a result look better. A hypothesis that was refuted stays in the document, stated as it was originally believed. Negative results are first-class results.

**Stage ID:** · **Status:** PLANNED / IN PROGRESS / COMPLETE / ABANDONED
**Date started:** · **Date completed:**
**Depends on:** · **Supersedes:**

---

# PART 1 — Written BEFORE implementation

## 1.1 Objective

What question does this stage answer? One paragraph. If it cannot be phrased as a question with a measurable answer, the stage is not ready to start.

## 1.2 Hypotheses

Number every hypothesis. State each so that it can be **refuted**.

| ID | Hypothesis | How it could be refuted |
|---|---|---|
| H-x.1 | | |

## 1.3 Success criteria (set in advance)

Numeric where possible. A criterion invented after seeing the result is not a criterion.

| # | Criterion | Threshold | Measured on |
|---|---|---|---|

## 1.4 Failure criteria

What outcome would mean the approach should be abandoned rather than tuned?

## 1.5 Variables and controls

| Role | Item |
|---|---|
| Independent (varied) | |
| Dependent (measured) | |
| Controlled (held fixed) | |
| Confounds (known, unmitigated) | |

## 1.6 Data provenance

State explicitly which of these each dataset is. Never let two roles collapse into one.

| Role | Source | Seeds | Notes |
|---|---|---|---|
| Training | | | |
| Calibration (threshold selection) | | | |
| Validation (performance reporting) | | | |
| Test (held out, untouched) | | | |
| Synthetic ground truth | | | |
| GT-free evaluation only | | | |

## 1.7 Metrics

For each: exact definition, units, and whether it is **fit** (circular) or **held-out / GT** (non-circular).

---

# PART 2 — Written AFTER implementation

## 2.1 What was actually implemented

Files added/changed. Deviations from the plan, and why.

## 2.2 Commands executed

```bash
```

## 2.3 Results

Tables. Every performance claim carries: regime/dataset · number of cases · seeds · metric definition · acceptance criterion · runtime environment · known limitations (integrity rule 12).

## 2.4 Failures and errors encountered

One block per error:

**Problem:**
**Observed symptom:**
**Root cause:**
**Why it was dangerous:**
**How it was discovered:**
**Fix:**
**Validation:**
**Regression protection:**
**Impact:**

## 2.5 Hypotheses: outcome

| ID | Hypothesis | Outcome | Evidence |
|---|---|---|---|
| H-x.1 | | CONFIRMED / REFUTED / INCONCLUSIVE / NOT TESTED | |

Refuted hypotheses are kept in full. For each, record: *original hypothesis · evidence · observed result · why the hypothesis failed · updated conclusion.*

## 2.6 Acceptance criteria: verdict

| # | Criterion | PASS / PARTIAL / FAIL / NOT TESTED | Evidence |
|---|---|---|---|

## 2.7 What this stage proved vs. what remains hypothesis

- **Proven (measured):**
- **Hypothesis (untested):**
- **Evidence insufficient:**

## 2.8 Limitations

What the results do *not* license anyone to claim.

## 2.9 Decisions taken

Reference ADR IDs and `DECISION_LEDGER.md` rows; do not duplicate the argument here.

## 2.10 Effect on the next stage

What changed in the plan because of this stage.

## 2.11 Artefacts

| File | Contents |
|---|---|

---

## Integrity checklist (complete before marking COMPLETE)

- [ ] No hypothesis promoted to fact without experimental evidence
- [ ] No failed experiment omitted
- [ ] No prior result deleted or overwritten; superseded results preserved
- [ ] Data roles (train / calibration / validation / test / GT / GT-free) stated and disjoint
- [ ] No threshold tuned on the data used to report its performance
- [ ] No correctness claim resting on a fit residual alone
- [ ] Illumination invariance claimed only under controlled illumination variation
- [ ] Scale invariance claimed only across a stated, tested scale range
- [ ] Multi-modal robustness claimed only if real modality differences were tested
- [ ] Sub-pixel accuracy claimed only from a non-circular estimator
- [ ] Every performance claim carries regime, n, seeds, metric, criterion, environment, limitations
- [ ] "Evidence insufficient." written wherever it is true
