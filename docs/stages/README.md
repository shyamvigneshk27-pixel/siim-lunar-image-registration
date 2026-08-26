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
| [`REAL-DATA_LRO_NAC.md`](REAL-DATA_LRO_NAC.md) | **REAL-DATA-01 — Real LRO NAC ingestion and first real registration** | **Ingestion, decoding and sanity validation succeed; the first real registration FAILS (class C / REJECTED).** 3 inliers at **fit RMSE 1.575e-12 px** — E-008 reproduced on real lunar data. **Cause unattributed** between the overlap and illumination hypotheses. **Not** Chandrayaan-2, **not** multi-modal, **not** azimuth-controlled |
| [`REAL-DATA-02_overlap_verification.md`](REAL-DATA-02_overlap_verification.md) | **REAL-DATA-02 — Independent real-image overlap verification** | **The tiles behind the first real registration were 22.75 km apart and shared 0.0000 km².** Overlap established from the PDS archive index table's **named** frame corners, with no pixel read and no matcher component used. The same products cropped the other way **do** overlap (68.6 % / 70.5 %) and still returned 5 inliers — the project's first interpretable real-data result. **The failure is still not attributed to illumination** |
| [`REAL-DATA-03_real_overlap_registration.md`](REAL-DATA-03_real_overlap_registration.md) | **REAL-DATA-03 — The first correctly controlled real-data registration experiment** | **Overlap confirmed first (97.12 %), then the unmodified baseline: 4 inliers at Δincidence 39.8°, 5365 at 0.96°, on the same mare.** Seven candidate causes eliminated by measurement; illumination is the only survivor and is **not** claimed as the cause. First real loop closure, three independently estimated edges |

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
| **Real LRO NAC ingestion** (REAL-DATA-01) | Decoding **provably correct**: `file_size` identity exact; declared vs byte-swapped autocorrelation 0.959/0.593, 0.942/0.668, 0.976/0.612. Positive controls on real imagery: identity to **1.14e-12**, known (+40,+25) px shift recovered as **(40.142, 24.941)** |
| **First real registration** | **FAILED.** 3 inliers / 35 putative at **fit RMSE 1.575e-12 px** → REJECTED, class C. **E-008 on real data.** All four line-direction combinations fail (3, 4, 4, 5) |
| **Real tile overlap** (REAL-DATA-02) | Established **independently of the matcher** from the PDS archive index table's named frame corners. The REAL-DATA-01 headline pair: **0.0000 km²**, centres **22.75 km** apart — **OVERLAP_INSUFFICIENT**. The same products at H2: **68.59 % / 70.51 %**, IoU **0.5330** — **OVERLAP_CONFIRMED**. Terminator pair: 28.29 % — **OVERLAP_UNKNOWN** |
| **First VALID real registration experiment** (REAL-DATA-03) | Overlap CONFIRMED **before** interpretation (97.12 % / 82.72 % / 85.00 %). Unmodified baseline: **4 inliers** at Δincidence 39.81°, **5365 inliers** (ratio 0.9950) at Δincidence 0.96° — same mare, same code. Seven candidate causes eliminated by measurement. The succeeding edge's recovered scale matches a SPICE-derived archive field to **0.04 %** |
| **Loop closure on real data** | Ran for the first time, three **independently estimated** edges, residual **1201.04 px** — it did not manufacture a small number. Two of three legs were garbage, so its *power* on real data is still unmeasured |
| **Tests** | **376 passed, 2 skipped** *(was 168 at EXP-002, 194 after the demo scaffold, 260 after REAL-DATA-01, 357 after REAL-DATA-02)* |

| | **Evidence insufficient** |
|---|---|
| **Why a confirmed-overlap real pair fails** | **Narrowed to one candidate, not attributed.** REAL-DATA-03 eliminated overlap, mare texture poverty, decimation, resolution mismatch, relief displacement, window uncertainty, the affine model and any pipeline defect — each by measurement against a succeeding edge on the same ground. **Illumination difference is the only survivor, and across three frames it is perfectly confounded with frame identity** and separately with Δazimuth, which was not measured (D-036, RL-033b) |
| **Why the first real registration failed** | **Resolved — and not in either direction the question assumed.** REAL-DATA-02 shows the headline pair's tiles were **22.75 km apart**, so that run measured nothing about the matcher. The remaining live question is narrower: why `registration_usableH2.json` returned 5 inliers on tiles with **68.6 %** confirmed shared ground. **That failure must still not be attributed to illumination** — mare texture poverty (D-026), decimation, resolution ratio and relief displacement are equally untested (D-031, RL-031b) |
| **Loop closure on real data** | **Never run.** Needs a third overlapping real product, not acquired. The project's only trustworthy GT-free check remains synthetic-only |
| Real Chandrayaan-2 imagery | **Still none.** OHRC/TMC-2/IIRS remain behind ISSDC authentication. REAL-DATA-01 is **LRO NAC only** and does **not** discharge this |
| Any multi-modal claim | No real modality difference tested |
| Scale beyond 4× | Real ladder reaches 320:1 |
| Frequency of coherent wrong solutions in reality | All such cases were constructed |
| Loop closure under correlated real-matcher errors | Validated on constructed transforms only |
| Availability of overlapping triplets in a real dataset | Unknown since ANALYSIS §F.1.4 |
| Relief displacement breaking global models | Derivation only, since EXP-000 |

---

## Stage progression, as it actually stands (2026-08-25)

| Stage | Status |
|---|---|
| PHASE-0 / EXP-000 · EXP-001 · EXP-002 | COMPLETE |
| **EXP-003** — illumination-robust representations | **COMPLETE — pre-registered criterion NOT met** |
| **REAL-DATA-01** — real LRO NAC ingestion | **COMPLETE — ingestion succeeded, registration FAILED (class C).** Its headline pair is now known not to overlap (REAL-DATA-02, E-028) |
| **EXP-004** — orientation assignment | **PRE-REGISTERED, NOT STARTED.** Part 1 frozen; Part 2 empty; no implementation exists |
| **REAL-DATA-02** — establish real overlap independently of the matcher | **COMPLETE — question answered.** Headline pair **OVERLAP_INSUFFICIENT** (0.0000 km², centres 22.75 km apart); `usable_H2` **OVERLAP_CONFIRMED** (68.6 % / 70.5 %); terminator **OVERLAP_UNKNOWN** (28.3 %) |
| **REAL-DATA-03** — geometry-driven re-acquisition + a third product for loop closure | **COMPLETE — the experiment is valid.** Overlap CONFIRMED 97.12 % / 82.72 % / 85.00 % **before** interpretation; unmodified baseline gives **4 inliers at Δinc 39.8°** and **5365 at Δinc 0.96°**; first real loop closure at **1201.04 px** |
| **REAL-DATA-04** — can frame identity and illumination be separated? | **COMPLETE — ANSWERED.** Overlap CONFIRMED 97.87 % / 71.30 % / 70.35 % **before** interpretation, the two decisive edges matched to 0.95 pp. **D↔A succeeds (1656 inliers, occupancy 1.000 at Δinc 11.73°); D↔B fails (3 at 51.54°).** Six real edges now place every frame on both sides, so **Δincidence predicts all six and frame identity predicts nothing across that set**. Illumination attributed (D-040); frame identity **substantially weakened, NOT conclusively refuted** — A and D each have n = 1 in the successful regime |
| **REAL-DATA-05** — does the illumination result replicate on a second low-incidence frame? | **CLOSED — UNRESOLVED, BY DATA AVAILABILITY.** The pre-registered screen returned **zero** admissible frames at every tier and rung. Of 906 archive products, 8 can centre a full tile on shared ground; only 2 are in the required incidence band and **both are orientation-incompatible** with the incumbents (rejected by H5, REAL-DATA-04's own filter). **No image byte fetched, no registration run, decision table never reached.** The replication debt stands |
| **September 2 demo** | **THE CURRENT PRIORITY.** Scientific expansion stopped after REAL-DATA-05 |

**REAL-DATA-01 is a real-data *validation* stage, not completion of the Chandrayaan-2
objective.** It proves the project can obtain, decode, verify and register-attempt genuine
lunar imagery from a public archive. It does **not** provide Chandrayaan-2 data, and it
supports **no multi-modal claim** — both frames are the same instrument — and **no
Sun-azimuth claim**, because azimuth is not published for these products (E-020).

**The real registration failed and that is preserved as evidence, not smoothed over.** What
succeeded is the *rejection*: a conventional pipeline reporting inlier RMSE would have
presented `1.575e-12 px` as a picometre-accurate registration.

### The next stage — there isn't one. It is the demo.

**REAL-DATA-04 — can frame identity and illumination be separated? COMPLETE — ANSWERED.**

**Yes, and the answer is illumination.** Frame **D** (`nac.m1299958135lc`, incidence 18.22°)
registers against frame **A** — **1656 inliers**, inlier ratio 0.9414, coverage occupancy
**1.000**, Δincidence **11.73°** — and fails against frame **B** — **3 inliers**, Δincidence
**51.54°** — on two edges whose independently confirmed overlap differs by **0.95 percentage
points**. That is the first row of the table REAL-DATA-03 wrote down before the data existed.

**Frame identity is substantially weakened — not conclusively refuted.** Across the **six**
real edges now measured, on five frames and two ground windows, **every frame appears in both
a succeeding and a failing edge**. No frame's presence predicts the outcome across that set.
Δincidence does, separating successes at 0.96° and 11.73° from failures at 38.85°, 39.81°,
39.81° and 51.54°.

Two limits keep this short of a refutation, and both are structural rather than a matter of
emphasis. **The argument is a join across two stages, not a within-experiment result**: inside
REAL-DATA-04's own triplet, frame B sits in both failing edges and no succeeding one — exactly
the partition that blocked REAL-DATA-03, mirrored from A onto B — and it is only
REAL-DATA-03's B→C success that breaks it, at a different ground window. And **frames A and D
each have n = 1 observations in the successful regime**: the single D→A edge carries the whole
claim for both. **REAL-DATA-05 was the pre-registered replication and returned UNRESOLVED**,
so that debt is undischarged. See the superseding note on **D-040**.

The succeeding edge is corroborated by a field the matcher never saw: its recovered scale
matches SPICE-derived `SCALED_PIXEL` to **0.04 % / 0.13 %**, and it is the only edge in either
stage whose corner-polygon disagreement falls **below** the discrimination floor (0.53×).

**Two things cost the stage something, and both are recorded rather than smoothed over.**
The pre-registered acquisition was **impossible** — frame A is the only low-incidence frame
over REAL-DATA-03's ground point, out of 17 that cover it — so hard filter 1 was amended to a
shared *tile-admissible* region with A and B unchanged. And **E-032**: the
`LRO_FLIGHT_DIRECTION` rule for which latitude line 0 sits at is **not a rule** (8/10, two
counterexamples), and the `NORTH_AZIMUTH` cross-check quoted for it had **no discriminating
power** in the sample it was validated on. The resulting orientation filter **rejected the
stage's own top-ranked candidate**. Both amendments were registered before a single image byte
of D was fetched and before any registration ran.

### What comes next: September 2

**Scientific expansion stops here, as planned.** REAL-DATA-04 was the final high-value causal
experiment and its evidence is sufficient. The next action is **demo engineering**, not
another stage.

What REAL-DATA-04 hands the demo is more than a result — it is a story with both halves:

- a **real, corroborated registration** on real LRO NAC imagery (D → A);
- a **real failure** beside it (B → D) whose cause is now identified by measurement;
- a **verdict engine that rejects the failure for the right reasons** and is not fooled by its
  `1.885e-13 px` fit RMSE — had `fit_rmse` been the criterion, the stage would have concluded
  the opposite;
- an **overlap gate that ran before the result** and would have stopped the demo from showing
  an uninterpretable pair.

A system that knows when it is wrong, demonstrated on real data, is a stronger demo than a
system that always succeeds.

**Still true, and still not started:** no matcher change, no tuning and no learned component is
justified by this stage — it established a *cause*, not a *fix*. **EXP-004 remains
pre-registered and NOT started.** For the first time it points at a real question — the
*mechanism* behind the Δincidence failure — and it stays behind the demo.

**Deferred behind September 2:** locating the real illumination cliff (bracketed to
11.73°–38.85°); the project's first real **azimuth**-controlled pair (RL-032b — every real
result so far is incidence only); and loop closure's discriminating power, which has now been
*exercised* twice on real data without a false closure (1201.04 px, 943.75 px) but needs three
**successful** real edges to be *measured* (RL-034b).

*(Historical note, retained under integrity rule 3: the section below was written when
REAL-DATA-03 had not started. It is left as it was rather than rewritten.)*

**REAL-DATA-03 — geometry-driven re-acquisition, and a third product for loop closure.
NOT STARTED.**

REAL-DATA-02 answered the blocking question and, in answering it, invalidated the tiles
rather than the products. The two frames of the `usable` pair do share ground; the crops
taken out of them for the headline result did not. The corrected windows are already
computed from archive geometry and project to **97.1 %** tile overlap — a specification, not
a measurement, since no such tile has been cut (D-033, §8.4 of the stage report).

Two things must happen in that order:

1. **Re-acquire the usable pair at the geometry-derived windows**, verify the overlap through
   the same independent path *before* registering, and only then run the unmodified B1
   baseline. A failure there would be the project's first real-data measurement of the
   matcher that means something.
2. **Acquire a third overlapping product** so loop closure — the project's only trustworthy
   GT-free check — can meet real data for the first time (RL-030b). REAL-DATA-02 supplies the
   means to select one: index-table corners give tile-level overlap *before* anything is
   fetched.

**No matcher change, no tuning and no learned component is justified until a real pair capable
of succeeding has been supplied.** EXP-004 remains pre-registered, not started, and unaffected.

*(Historical note, retained under integrity rule 3: the paragraph below was written when
REAL-DATA-02 had not started. It is left as it was.)*

**REAL-DATA-02 — establish real overlap independently of the matcher. NOT STARTED.**
Until overlap is known, every real registration failure is uninterpretable (D-030, D-031,
RL-029b). Highest-value item within it: acquire a **third overlapping product** so loop
closure — the project's only trustworthy GT-free check — can meet real data for the first
time (RL-030b).

*(Historical note, retained under integrity rule 3: the section below was written when
EXP-003 had not started. It is left as it was rather than rewritten.)*

## The next stage *(as recorded before EXP-003 ran)*

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
