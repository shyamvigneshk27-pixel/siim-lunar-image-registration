# STAGE REPORT TEMPLATE

> **Copy this file to `docs/stages/EXP-XXX_<short_name>.md` when a stage is planned.**
> Fill Part 1 **before** writing code. Append Part 2 **after** the stage has run.
>
> **A stage report is never rewritten to make a result look better.** A hypothesis that
> was refuted stays in the document, stated as it was originally believed, next to the
> evidence that refuted it. Negative results are first-class results.

**Stage ID:**
**Name:**
**Status:** PLANNED / IN PROGRESS / COMPLETE / ABANDONED
**Date started:** · **Date completed:**
**Depends on:** · **Followed by:** · **Supersedes:**

---

## How to use this template

Six rules bind every section below.

1. **Every number carries its provenance.** A quantitative claim is written as
   `value (source-file:key)` — e.g. `0.056 s (objective1_ransac.json:ransac_before_after.after.total_s)`.
   A number with no artefact behind it is not a result.
2. **Measured fact and interpretation are never mixed in the same sentence.**
   Use the `[MEASURED]` / `[INTERPRETATION]` / `[HYPOTHESIS]` / `[NOT VERIFIED]` markers.
3. **Anything not verifiable from the repository is marked `Not verified`.**
   Not "approximately", not "roughly" — `Not verified`, with a note on what would verify it.
4. **Every important failure uses the six-part block** in §2.6, and is classified into
   exactly one of the five failure classes in §2.7.
5. **Data roles are declared and disjoint** — calibration, validation, test, synthetic
   ground truth, GT-free evaluation. Two roles never collapse into one.
6. **Superseded results are preserved, never overwritten.** If a re-run changes numbers,
   the old artefact is kept under a `_pre<STAGE>` name and both are cited.

---

# PART 1 — written BEFORE implementation

## 1.1 Stage objective

One paragraph. It must be phrased as a **question with a measurable answer**. If it
cannot be, the stage is not ready to start.

## 1.2 Starting assumptions

Everything believed true at the start, with its source and how it could be wrong.

| # | Assumption | Source | Confidence | How it could be falsified |
|---|---|---|---|---|
| A1 | | | measured / reasoned / inherited / assumed | |

## 1.3 Hypotheses

Each stated so that it can be **refuted**. A hypothesis that cannot fail is not a hypothesis.

| ID | Hypothesis | Predicted observation | What would refute it |
|---|---|---|---|
| H-x.1 | | | |

## 1.4 Success criteria (set in advance)

A criterion invented after seeing the result is not a criterion.

| # | Criterion | Threshold | Measured on | Metric definition |
|---|---|---|---|---|

## 1.5 Failure criteria

What outcome would mean the approach should be **abandoned** rather than tuned?

## 1.6 Variables and controls

| Role | Item |
|---|---|
| Independent (varied) | |
| Dependent (measured) | |
| Controlled (held fixed) | |
| Confounds (known, unmitigated) | |

## 1.7 Data provenance and roles

| Role | Source | Seeds | Disjoint from | Notes |
|---|---|---|---|---|
| Calibration (threshold selection) | | | | |
| Validation (performance reporting) | | | | |
| Synthetic ground truth | | | | |
| GT-free evaluation only | | | | |

## 1.8 Metric definitions

For each metric: exact definition, units, and whether it is **fit** (circular) or
**held-out / GT** (non-circular). A fit metric may never carry a correctness claim alone.

## 1.9 Negative controls declared in advance

Signals expected to carry **no** information. Declaring them before the run is what makes
a null result evidence rather than an excuse.

---

# PART 2 — written AFTER implementation

## 2.1 What we implemented

Modules and functions added or changed, with the design decision each embodies.
Deviations from the Part 1 plan, and why.

## 2.2 Experiments performed

| Experiment | Cases | Seeds | Regimes | Artefact |
|---|---|---|---|---|

## 2.3 Exact commands used

```bash
# Every command that produced a number in this report, in order.
# Mark any command that is reconstructed rather than recorded: "Not verified".
```

Environment: python · numpy · opencv · platform · CPU — copied from the artefact's
`environment` block, not from memory.

## 2.4 Quantitative results

Tables. Every performance claim carries: **regime · n cases · seeds · metric definition ·
acceptance criterion · runtime environment · known limitations.**

Mark each row `[MEASURED]`. Interpretation goes in a separate paragraph marked
`[INTERPRETATION]`.

## 2.5 What worked / what failed

**Worked** — with the measurement that shows it.
**Failed** — with the measurement that shows it, and whether the failure was expected.

## 2.6 Errors and bugs discovered

One block per important failure. **All six parts are mandatory.**

### E-XXX — short name

**Class:** implementation bug / experimental-design mistake / incorrect hypothesis /
synthetic-data limitation / genuine research negative result
**Severity:** CRITICAL / HIGH / MEDIUM / LOW

- **Problem:** what was wrong, stated in one sentence.
- **Evidence:** the observation that exposed it, with the artefact reference.
- **Root cause:** why it happened — the mechanism, not the symptom.
- **Fix:** what was changed. If nothing was changed, say so and say why.
- **Verification:** the measurement proving the fix worked, plus the regression test name.
- **Lesson:** what generalises beyond this bug.

**Before / after:**

| | before | after |
|---|---|---|

## 2.7 Failure classification

Every entry in §2.6 is placed in exactly one class. The classes are not interchangeable
and conflating them is itself a documented project failure.

| Class | Meaning | Entries |
|---|---|---|
| **Implementation bug** | The code did not do what it was written to do | |
| **Experimental / design mistake** | The code was correct; the experiment could not answer the question asked of it (circular threshold, missing control, single seed, no held-out split) | |
| **Incorrect hypothesis** | A stated prediction was measured and found wrong | |
| **Synthetic-data limitation** | The result is an artefact of the simulator, not of the algorithm | |
| **Genuine research negative result** | A real, correctly-measured finding that a thing does not work | |

## 2.8 Hypotheses: outcome

| ID | Hypothesis (as originally stated) | Outcome | Evidence |
|---|---|---|---|
| H-x.1 | | CONFIRMED / REFUTED / INCONCLUSIVE / NOT TESTED | |

For each **refuted** hypothesis record, in full:
*original hypothesis · evidence · observed result · why the hypothesis failed · updated conclusion.*

## 2.9 Conclusions that survived

Separate explicitly:

- **[MEASURED] Proven by measurement**, with the regime and n it is proven *within*.
- **[INTERPRETATION] Our reading of the measurement** — could be wrong while the number stays right.
- **[HYPOTHESIS] Untested.**
- **[NOT VERIFIED] Evidence insufficient** — write this sentence wherever it is true.

## 2.10 Conclusions from earlier stages that this stage corrected

| Earlier claim | Stage | Status now | Evidence |
|---|---|---|---|

## 2.11 Decisions / ADRs affected

Reference ADR and `DECISION_LEDGER.md` IDs. Do not restate the argument.

| ID | Decision | Effect of this stage |
|---|---|---|

## 2.12 Tests and reproducibility status

| Item | Status |
|---|---|
| Test count | `python -m pytest tests/ -q` → |
| New tests added | |
| Regression tests that pin a hazard from this stage | |
| Deterministic seeds recorded | |
| Bit-identical re-run? | yes / no — if no, the **stated tolerance** is |
| Superseded artefacts preserved at | |

## 2.13 Files / modules created or changed

| Path | Created / Changed | Purpose |
|---|---|---|

## 2.14 Limitations and threats to validity

What these results do **not** license anyone to claim. Include at minimum:
synthetic-data limits · seed count · regime coverage · untested axes · modality gap.

## 2.15 Lessons learned

Generalisable, not restatements of the results.

## 2.16 What must NOT be repeated

Concrete prohibitions for future stages, each traced to the failure that earned it.

## 2.17 What the next stage should do

Ordered by what this stage's evidence makes most valuable.

## 2.18 Open questions / unresolved risks

| # | Question | Why unresolved | What would resolve it |
|---|---|---|---|

## 2.19 Artefacts

| File | Contents |
|---|---|

---

## Integrity checklist — complete before marking COMPLETE

- [ ] No hypothesis promoted to fact without experimental evidence
- [ ] No failed experiment omitted
- [ ] No prior result deleted or overwritten; superseded results preserved
- [ ] Data roles stated and disjoint
- [ ] No threshold tuned on the data used to report its performance
- [ ] No correctness claim resting on a fit residual alone
- [ ] Illumination invariance claimed only under controlled illumination variation
- [ ] Scale invariance claimed only across a stated, tested scale range
- [ ] Multi-modal robustness claimed only if real modality differences were tested
- [ ] Sub-pixel accuracy claimed only from a non-circular estimator
- [ ] Every performance claim carries regime, n, seeds, metric, criterion, environment, limitations
- [ ] Every failure classified into exactly one of the five classes in §2.7
- [ ] Every number traceable to an artefact, or marked **Not verified**
- [ ] "Evidence insufficient." written wherever it is true
