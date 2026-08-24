# `docs/stages/` — the engineering and research history

**SIIM · SIH 2026 · Problem Statement 26166 (ISRO)** — Multi-modal, Sun-angle and scale
invariant image correspondence, Chandrayaan-2 (OHRC, TMC-2, IIRS) ↔ LRO NAC.

---

## What this directory is for

This directory is the project's **long-form memory of how its understanding changed** — not
a summary of what the code does. The code says what it does. These documents say **why it
does that, what we tried that did not work, and which of our own conclusions we had to
withdraw.**

It exists because of a pattern this project measured in itself:

> Of the failures recorded so far, **the majority are failures of *evidence*, not of code** —
> metrics that lied, thresholds validated circularly, conclusions over-generalised from one
> terrain. Only a minority are ordinary software defects.
> **The dominant risk in this project is not broken code; it is believing a result more than
> the evidence supports.**

A test suite catches the first kind. Only a written history catches the second.

### What this directory is not

- **Not a changelog.** Changelogs record what changed. These records exist to preserve
  *what was believed before the change, and why it was wrong.*
- **Not marketing.** No stage report is rewritten to make a result look better.
- **Not a substitute for the artefacts.** Every number here traces back to a JSON or CSV in
  `experiments/`. If the two disagree, **the artefact wins** and the document is corrected
  with the correction recorded.

---

## The binding rule

> **A stage report is never rewritten to make a result look better.**
>
> A hypothesis that was refuted stays in the document, **stated as it was originally
> believed**, next to the evidence that refuted it. Negative results are first-class
> results.

Every retrospective correction in these documents — the relocated illumination cliff, the
withdrawn threshold claim, the reversed GT-free ordering, the recounted fit-RMSE figure — is
recorded *as a correction*, with both the old and the new value. Nothing is silently updated.

---

## How to read this directory

**Start here → [`../STAGE_HISTORY.md`](../STAGE_HISTORY.md)** for the chronological narrative.

### The stage reports

| Document | Stage | One-line result |
|---|---|---|
| [`EXP-000_geometry_gate.md`](EXP-000_geometry_gate.md) | **EXP-000 — Geometry Gate** | All 5 transform models recover at ~1e-13 px against a 0.1 px gate. The naive resampling formula is wrong by up to **1.0 px**, invisibly |
| [`EXP-001_rootsift_baseline.md`](EXP-001_rootsift_baseline.md) | **EXP-001 — RootSIFT / Matching Baseline** | Illumination is the dominant failure axis, and it is a **cliff, not a slope**. Fit RMSE is **inverted** in the failure regime |
| [`EXP-002_ransac_terrain_gtfree.md`](EXP-002_ransac_terrain_gtfree.md) | **EXP-002 — RANSAC, Terrain Realism, Threshold Validation, GT-Free Verification** | LO-RANSAC **968×** faster with the same inlier set; the old terrain was **physically impossible**; **loop closure is the only GT-free estimator that detects a coherent wrong answer** |
| [`EXP-003_illumination_robust_representations.md`](EXP-003_illumination_robust_representations.md) | **EXP-003 — Illumination-Robust Representations** | **Pre-registered criterion met by no arm.** Polarity-agnostic mod-π was the *worst* of six; ADR-0004 **superseded**. The failure is SIFT's orientation **assignment**, which drifts ~1:1 with Sun azimuth — not its binning |

### The template every future stage must use

| Document | Purpose |
|---|---|
| [`STAGE_REPORT_TEMPLATE.md`](STAGE_REPORT_TEMPLATE.md) | **Mandatory.** Copy it when a stage is *planned*; fill Part 1 before writing code |

### Cross-stage indexes (pre-existing, still current)

| Document | Purpose |
|---|---|
| [`STAGE-INDEX.md`](STAGE-INDEX.md) | Navigable per-stage summary table |
| [`ERROR_LEDGER.md`](ERROR_LEDGER.md) | **Every** significant failure across all stages, with root cause, fix and lesson. Nothing is ever removed once entered |
| [`DECISION_LEDGER.md`](DECISION_LEDGER.md) | Every decision, its evidential status, and **what would reverse it** |

### A note on the two generations of files in this directory

This directory contains **two overlapping sets** of stage documents, and both are kept
deliberately:

| Older (retained) | Newer (canonical from here on) |
|---|---|
| `PHASE-0_GEOMETRY.md` | `EXP-000_geometry_gate.md` |
| `EXP-001_ROOTSIFT.md` | `EXP-001_rootsift_baseline.md` |
| `EXP-002_EVALUATION_REALISM_RANSAC.md` | `EXP-002_ransac_terrain_gtfree.md` |
| `STAGE_TEMPLATE.md` | `STAGE_REPORT_TEMPLATE.md` |

**Nothing was deleted**, because integrity rule 3 forbids deleting a superseded record.
The newer set is the canonical one from EXP-003 onward: it adds explicit
`[MEASURED]` / `[INTERPRETATION]` / `[NOT VERIFIED]` marking, the mandatory five-way
failure classification, per-number artefact provenance, and a re-verification of every
headline figure against the raw artefacts. Where the two sets disagree, **the newer set
records the disagreement explicitly** rather than resolving it silently.

### Discrepancies found during re-verification

Writing the newer set involved re-deriving **153 numeric claims** directly from the raw
artefacts. All 153 reconciled. **Three bookkeeping discrepancies were found in the older
narrative documents and are recorded here rather than silently corrected**, because the
integrity rules forbid quietly rewriting a prior record.

| # | Claim, and where it appears | What the artefact says | Effect on any conclusion |
|---|---|---|---|
| **D1** | *"11 of 17 failed cases reported a fit RMSE below 1e-12 px"* — `EXP-001_ROOTSIFT.md` §I.9, `ERROR_LEDGER.md` E-008, `STAGE-INDEX.md`, `experiments/EXP-001/README.md`, `research_log.md` RL-021 | A direct recount of `results_preEXP002.csv` with the predicate `reported_fit_rmse < 1e-12` gives **10**. The 11th is most plausibly `D_scene mare/d_az=60`, whose `reported_fit_rmse` is **`nan`** (0 inliers) — undefined, not "below 1e-12". On the post-fix `results.csv` the count is **9** | **None.** The finding — fit RMSE is inverted in the failure regime — is unaffected, and is independently confirmed at ROC AUC 0.4947 on 192 unseen cases. Corrected in `EXP-001_rootsift_baseline.md` §6.11 |
| **D2** ✅ **RESOLVED** | Heading *"Sensitivity of `n_inliers` (validation)"* — `EXP-002_EVALUATION_REALISM_RANSAC.md` §3.6, `experiments/EXP-002/README.md` | `scripts/run_exp002_threshold.py:202–222` computes `sensitivity` for the **automatically selected best signal**, and every sensitivity block in `objective3_threshold.json` records `threshold_score_space: 1e12` — the `split_consistency` `inf` sentinel. **The table is `split_consistency`'s** and inherits the E-010 artefact | **Resolved 2026-08-24.** Corrected analysis at **`experiments/EXP-002/objective3_ninliers_sensitivity.json`** (+ `_cases.csv`), from `scripts/run_exp002_ninliers_sensitivity.py`. Written up in `EXP-002_ransac_terrain_gtfree.md` **§3.7** (E-002.11, E-002.12), RL-022, **D-023**. Two by-products: the rule form changed to **`n_inliers <= 8`**, and the sentinel is now quantified as a proxy for `n_inliers < 8` at **192/192** agreement |
| **D3** | *"Of 16 entries, 9 are failures of evidence … Only 5 are ordinary software defects"* — `ERROR_LEDGER.md` preamble | The table contains **18** entries (E-001 … E-018), and 9 + 5 = 14 ≠ 18 | **None on the substance** — the qualitative point (evidence failures outnumber code defects) holds. The newer documents state it as a ratio in words rather than propagating the arithmetic |

`[INTERPRETATION]` None of the three changes a conclusion. They are recorded because an
uncorrected arithmetic slip in a headline claim is exactly the kind of thing an external
reviewer finds first, and because a history that quietly fixes its own numbers is not a
history.

---

## Reconstruction basis and its limits

The three stage reports for EXP-000, EXP-001 and EXP-002 are **retrospective**. They were
written after the fact, and reconstructed **from repository artefacts only**: experiment
READMEs, `metrics.json` / `objective*.json`, results CSVs, source, tests,
`research_log.md`, `architecture_decisions.md`, `sources.md`.

**Three limits apply to all three, and are restated in each document:**

1. **The repository is not a git repository.** `git rev-parse --is-inside-work-tree` returns
   `fatal: not a git repository`. **Per-edit chronology, intermediate code states, the order
   in which bugs were found, and wall-clock timestamps are not established from repository
   evidence.** Only the recorded metrics and the final source state are evidence.
2. **All artefacts carry the single date 2026-08-24.** Stage durations are not verifiable.
3. **Pre-fix source text is not preserved** for any defect. Defects are evidenced by
   recorded measurements taken before the fix, and by regression tests that still name them.

Anything that could not be verified against an artefact is marked **`Not verified`** or
**`Evidence insufficient.`** — in those words, not softened.

---

## How EXP-003 and every later stage must be documented

**This is the operative section. It is a requirement, not a suggestion.**

### 1. Before writing any code — create the report and fill Part 1

```bash
cp docs/stages/STAGE_REPORT_TEMPLATE.md docs/stages/EXP-003_<short_name>.md
```

Fill **Part 1** in full: objective (as a question with a measurable answer) · starting
assumptions · **hypotheses stated so they can be refuted** · success criteria with numeric
thresholds · failure criteria · variables and controls · **data provenance with disjoint
roles** · metric definitions labelled `fit` or `held-out` · **negative controls declared in
advance**.

A criterion invented after seeing the result is not a criterion. A hypothesis that cannot
fail is not a hypothesis. **A negative control declared after the run is a rationalisation.**

Then add the stage to `STAGE-INDEX.md` with status `NOT STARTED` and **no results**.

### 2. While the stage runs

- Record **every command exactly as executed**, including the ones that failed.
- Preserve superseded artefacts under a `_pre<STAGE>` name. **Never overwrite.**
- Preserve original figures. *(This was violated once — EXP-001's figures were regenerated
  and the originals lost. Do not repeat it.)*
- Log failures as they happen, not from memory afterwards.

### 3. After the stage — append Part 2

Every section of Part 2 is mandatory. In particular:

**Every important failure uses this six-part structure, in this order:**

> **Problem → Evidence → Root Cause → Fix → Verification → Lesson**

...and is classified into **exactly one** of these five classes, which must not be conflated:

| Class | Meaning | Why the distinction matters |
|---|---|---|
| **Implementation bug** | The code did not do what it was written to do | Fixable, testable, local. Cheapest class |
| **Experimental / design mistake** | The code was correct; the *experiment* could not answer the question asked of it | Invalidates conclusions, not code. A passing test suite will never catch it |
| **Incorrect hypothesis** | A stated prediction was measured and found wrong | **This is a result, not a failure.** Only countable if the prediction was written down first |
| **Limitation of synthetic data** | The result is an artefact of the simulator, not of the algorithm | Bounds what may be claimed about the real world. Silently ignoring it is how a whole stage's conclusions become wrong |
| **Genuine research negative result** | A real, correctly-measured finding that something does not work | **First-class. Publish it.** These are the entries the project is most proud of |

**Preserve the distinction between measured fact and interpretation.** Use the markers:

- `[MEASURED]` — a number from an artefact, with the artefact named.
- `[INTERPRETATION]` — our reading of that number. **It can be wrong while the number stays
  right**, and it must be separable from the number so that a later stage can revise it
  without touching the measurement.
- `[HYPOTHESIS]` — proposed, untested.
- `[NOT VERIFIED]` / **"Evidence insufficient."** — write it wherever it is true.

**Every performance claim carries all seven of:** regime/dataset · number of cases · random
seeds · metric definition · acceptance criterion · runtime environment · known limitations.

### 4. Update the cross-stage records

| File | What to add |
|---|---|
| `ERROR_LEDGER.md` | One row per failure. **Never remove an entry** — a fixed error stays with status `FIXED`, because the lesson outlives the bug |
| `DECISION_LEDGER.md` | One row per decision, with **what would reverse it** |
| `STAGE-INDEX.md` | Update status, key result, major failure |
| `../STAGE_HISTORY.md` | The chronological narrative entry |
| `docs/architecture_decisions.md` | Any new or changed ADR |
| `docs/research_log.md` | Hypothesis outcomes |

### 5. Complete the integrity checklist

At the foot of `STAGE_REPORT_TEMPLATE.md`. A stage is not `COMPLETE` until every box is
ticked or explicitly waived with a reason.

---

## Scientific integrity rules

Binding on all stage documentation.

1. Never convert a hypothesis into a fact without experimental evidence.
2. Never hide a failed experiment.
3. Never delete an old result because a newer benchmark is better.
4. Preserve old experiment outputs (e.g. `experiments/EXP-001/results_preEXP002.csv`).
5. Clearly distinguish **calibration · validation · test · synthetic ground truth ·
   GT-free evaluation**.
6. Never tune a threshold on the data used to claim its performance.
7. Never use a fit residual alone to claim correctness.
8. Never claim illumination invariance except under controlled illumination variation.
9. Never claim scale invariance except across a defined, tested scale range.
10. Never claim multi-modal robustness until actual modality differences are tested.
11. Never claim sub-pixel accuracy merely because the fitted residual is sub-pixel.
12. Every major performance claim carries: dataset/regime · number of cases · random seeds ·
    metric definition · acceptance criterion · runtime environment · known limitations.
13. Where evidence is insufficient, write **"Evidence insufficient."**

### Current standing under rule 10

**No multi-modal claim has been made or is currently supportable.** Every result to date is
on synthetic single-modality data. The real cross-modal gap — OHRC/TMC-2/IIRS ↔ NAC,
including IIRS's thermal-emission bands beyond ~3 µm — is untested.
**Evidence insufficient.**

### Current standing under rules 8 and 9

Illumination results are measured under **controlled, physically-rendered** Sun-geometry
variation with exact ground truth, so rule 8 is satisfied **for synthetic terrain, and only
for that**. Scale results cover **1.0×–4.0× only**; the real sensor ladder extends to
**320:1**. **Evidence insufficient** beyond 4×.

---

## What the history has established so far

A one-screen orientation. Every figure is traced in the stage report that produced it.

| | `[MEASURED]` |
|---|---|
| **Geometry** | 5/5 transform models recover at ~1e-13 px vs a 0.1 px gate; Hartley holds condition ~3.4 from 512 → 60,000 px |
| **Dominant failure axis** | **Illumination** — a cliff, not a slope. Last fully-successful Δazimuth: **15°** on realistic regimes, 30° on extreme terrain |
| **Second axis** | Scale — survives to 4× on textured terrain, **fails at 2× on realistic mare** |
| **Survivable** | Sun **elevation**: Δel −30° → 0.750 px |
| **Fit RMSE as a failure detector** | **ROC AUC 0.4947 — chance.** In the failure regime it is *inverted* |
| **Best deployable failure signal** | `n_inliers <= 8` (D-023) — recall 1.000, FPR 0.0112, ROC AUC 0.9935 on 192 unseen cases; recall 1.000 in every non-degenerate subset |
| **GT-free correctness** | **Loop closure alone**: detection 1.000, false alarm 0.000. Held-out residual and split consistency: 0.200, blind to every coherent wrong answer |
| **Terrain realism** | A-regimes hit LOLA medians exactly (3.50° / 9.10°); the EXP-001 terrain had **89.55% above the angle of repose** |
| **Runtime** | LO-RANSAC 54.29 s → 0.056 s (968×); median pipeline 0.262 s vs a ≤ 60 s/pair budget |
| **Run-to-run variation** | **±0.5853 px** — which retired the RootSIFT-vs-SIFT comparison as noise |
| **Tests** | **168 passed, 2 skipped** |

| | **Evidence insufficient** |
|---|---|
| Real Chandrayaan-2 / LRO NAC imagery | No data in the repository |
| Any multi-modal claim | No real modality difference tested |
| Scale beyond 4× | Real ladder reaches 320:1 |
| Frequency of coherent wrong solutions in reality | All such cases were constructed |
| Loop closure under correlated real-matcher errors | Validated on constructed transforms only |
| Availability of overlapping triplets in a real dataset | Unknown since ANALYSIS §F.1.4 |
| Relief displacement breaking global models | Derivation only, since EXP-000 |

---

## The next stage

**EXP-003 — Illumination-invariant representations. NOT STARTED.** No implementation, no
results.

Planned objective: test whether a **polarity-agnostic representation** moves the
illumination cliff **beyond Δazimuth 30° on realistic (A) terrain regimes** — the criterion
EXP-002 set in advance.

Constraints EXP-002 already fixed for it, and which EXP-003 must honour:

1. Report **per regime, never pooled** (D-021).
2. **Realistic mare is the priority case** (D-019) — 312 vs 22,119 kp/Mpx.
3. Use **`n_inliers <= 8`** (equivalently `< 9`) as the success criterion; **never
   `fit_rmse`**. The form changed at **D-023** — `< 8` demonstrably misses a 367.95 px
   failure sitting exactly at the boundary, at no false-alarm saving.
4. **Loop closure** is the only trustworthy GT-free correctness check.
5. Resolve the cliff edge at **18 / 21 / 24 / 27°**, **≥ 3 seeds**.
6. Runtime is no longer a constraint (D-020).

**ADR-0004** (polarity-agnostic structure as the default representation) remains `PROPOSED`
and states plainly that **if raw intensity wins, the ADR is superseded.** This stage is that
test — the register exists to record that outcome, not to defend the guess.

**Explicitly out of scope until this stage runs:** RIFT2, phase congruency, orientation-mod-π
as a shipped component, and every learned matcher.
