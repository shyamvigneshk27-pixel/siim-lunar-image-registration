# SIIM — Sun-angle Invariant Image Matching

**SIH 2026 · Problem Statement 26166 (ISRO)**
Multi-modal, Sun-angle and scale invariant image correspondence using Chandrayaan-2 optical images (OHRC, TMC-2, IIRS) against lunar reference imagery (LRO NAC).

---

## Status

| Phase | State |
|---|---|
| Phase 0 — Research & analysis | **complete** — `docs/00_PROJECT_ANALYSIS.md` |
| EXP-000 — Geometry gate | **passed** — `experiments/EXP-000/` |
| EXP-001 — RootSIFT baseline + GT harness | **complete** — `experiments/EXP-001/` |
| EXP-002 — RANSAC fix, terrain realism, threshold + GT-free validation | **complete** — `experiments/EXP-002/` |
| Phase 1 — Dataset understanding | blocked on data access; developing against public LRO NAC |
| EXP-003 — Illumination-robust representations | next (ADR-0010) |

---

## Read these first

The design documents are normative. Code that contradicts them is a bug.

| Document | What it is |
|---|---|
| [`docs/STAGE_HISTORY.md`](docs/STAGE_HISTORY.md) | **Start here.** Chronological record of how the project's understanding evolved, stage by stage |
| [`docs/00_PROJECT_ANALYSIS.md`](docs/00_PROJECT_ANALYSIS.md) | Problem analysis, candidate architectures, evaluation strategy, risk register, success criteria |
| [`docs/coordinate_contract.md`](docs/coordinate_contract.md) | Coordinate conventions, obeyed everywhere. **Read before touching `geometry/`** |
| [`docs/architecture_decisions.md`](docs/architecture_decisions.md) | Every major decision, its alternatives, and what would overturn it |
| [`docs/research_log.md`](docs/research_log.md) | Open hypotheses and the experiments that resolve them |
| [`docs/sources.md`](docs/sources.md) | External facts, their provenance, and how each influenced the design |

### Stage records

| Document | What it is |
|---|---|
| [`docs/stages/STAGE-INDEX.md`](docs/stages/STAGE-INDEX.md) | Navigable per-stage summary: objective, status, key result, major failure |
| [`docs/stages/ERROR_LEDGER.md`](docs/stages/ERROR_LEDGER.md) | Every significant failure found, with root cause, fix and lesson |
| [`docs/stages/DECISION_LEDGER.md`](docs/stages/DECISION_LEDGER.md) | Every decision, its evidential status, and what would reverse it |
| [`docs/stages/STAGE_TEMPLATE.md`](docs/stages/STAGE_TEMPLATE.md) | Mandatory template — every future experiment produces a stage report |
| `docs/stages/PHASE-0_GEOMETRY.md` · `EXP-001_ROOTSIFT.md` · `EXP-002_EVALUATION_REALISM_RANSAC.md` | Full per-stage reports |

**Working rule:** a stage report is never rewritten to make a result look better. Failed hypotheses stay in, stated as they were originally believed. Negative results are first-class results.

## The core idea (provisional)

> **The matcher is a replaceable part; the protocol is the contribution.**

A benchmark of 24 pretrained matchers on cross-modal satellite registration found that *protocol* choices — tiling, normalisation, transform model, RANSAC threshold — change mean error by up to **33×** for a fixed matcher, exceeding the gap between top-tier and mid-tier models. So the architecture is a fixed geometric protocol with a **swappable matcher engine**, and the engine is selected by measurement rather than assumption.

This is a hypothesis carried over from SAR-optical imagery, not an established lunar result. EXP-006 exists to confirm or refute it, and the project reports the refutation if that is the outcome.

## What this system is built to do that the obvious version does not

- **Measure accuracy non-circularly.** Reprojection RMSE over RANSAC inliers is a *fit* statistic: it falls monotonically as you tighten the threshold, and it cannot detect a match set uniformly shifted by one crater spacing. Accuracy is instead evidenced by synthetic ground truth, K-fold **held-out** residuals, cycle consistency, and **loop closure over image triplets**. Headline claims quote the *worst* applicable estimator.
- **Handle the real scale ladder.** Sensor GSDs mandate ratios of 2:1 up to **320:1** (OHRC↔IIRS). Off-the-shelf matchers are reliable to ~2–4×, so scale normalisation is a first-class pipeline stage.
- **Survive shadow motion.** Measured against exact ground truth on terrain matched to published LOLA slope statistics: a RootSIFT baseline fails between **Δazimuth 15° and 30°** — a cliff, not a slope. We expected the break at 180° from shadow *reversal*; it arrives far earlier, because shadow *movement* alone changes gradient orientations. Contrast normalisation cannot repair it, since it preserves sign. Sun elevation is survivable by comparison.
- **Know that a confident answer can still be wrong.** A correspondence set displaced by exactly one crater spacing is 64 px wrong and perfectly self-consistent: fit RMSE reads ~0, held-out residual reads 0.47 px. Measured: `fit_rmse` scores **ROC AUC 0.495** as a failure detector — chance. Only **loop closure** over three images catches it (100% detection, 0% false alarm).
- **Know when it has failed.** A system that is right 90% of the time and knows which 10% is worth more operationally than one that is right 95% and cannot tell you when it is not.

## Quick start

```bash
python -m pip install -e ".[dev,viz]"
python -m pytest tests/ -q            # 168 passed, 2 skipped
python scripts/run_exp000.py          # geometry gate measurements
python scripts/run_exp001.py          # classical baseline vs synthetic ground truth
python scripts/run_exp002_ransac.py   # LO-RANSAC defect: before/after
python scripts/run_exp002_terrain.py  # terrain realism + regime comparison
python scripts/run_exp002_threshold.py  # failure threshold, disjoint validation
python scripts/run_exp002_gtfree.py     # GT-free estimators vs coherent wrong answers
```

CPU-only by design — no CUDA required at any point in the delivered pipeline.

## Layout

```
src/siim/geometry/     coordinate contract, transforms, estimation, resampling  [done]
src/siim/data/         synthetic lunar terrain + physically shaded GT pairs      [done]
src/siim/matching/     RootSIFT detection and descriptor matching                [done]
src/siim/verification/ LO-RANSAC robust estimation                               [done]
src/siim/evaluation/   GT metrics, coverage, failure taxonomy, GT-free estimators [done]
src/siim/baselines/    B1 end-to-end classical pipeline                          [done]
docs/                  normative design documents
tests/                 property tests pinning the coordinate contract
scripts/               experiment runners
experiments/           EXP-XXX: config, metrics, findings
```

Further modules are added when a stage exists, not upfront.
