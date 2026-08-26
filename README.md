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
| EXP-003 — Illumination-robust representations | **complete — pre-registered criterion NOT met.** ADR-0004 superseded — `experiments/EXP-003/` |
| REAL-DATA-01 — Real LRO NAC ingestion | **complete — ingestion succeeded, first registration FAILED (class C / REJECTED)** — `experiments/REAL-DATA/` |
| EXP-004 — Orientation assignment | **pre-registered, NOT started.** Part 1 frozen; no implementation exists |
| REAL-DATA-02 — Establish real overlap independently of the matcher | **complete — question answered.** The REAL-DATA-01 headline pair does **not** overlap — `experiments/REAL-DATA-02/` |
| REAL-DATA-03 — The first correctly controlled real-data registration experiment | **complete — the experiment is valid; 2 of 3 edges fail, 1 succeeds** — `experiments/REAL-DATA-03/` |
| REAL-DATA-04 — Can frame identity and illumination be separated? | **complete — ANSWERED.** D↔A succeeds (1656 inliers at Δinc 11.73°), D↔B fails (3 at 51.54°). **Illumination attributed, frame identity refuted** — `experiments/REAL-DATA-04/` |
| **September 2 demo** | **the current priority.** Scientific expansion stopped after REAL-DATA-04 |
| Chandrayaan-2 (OHRC / TMC-2 / IIRS) | **NOT OBTAINED** — ISSDC authentication required. No multi-modal claim is supported |

**Where the real data stands.** The project now ingests, decodes and verifies genuine LRO NAC
imagery from the public PDS archive end to end. **The first real registration attempt failed**
— 3 inliers at a fit RMSE of `1.575e-12 px`, correctly rejected — and REAL-DATA-02 has since
established, **independently of the matcher**, why: those two tiles were **22.75 km apart and
shared no ground at all**. That run measured nothing about the matcher, and the fit residual
was reported at a picometre for a transform between disjoint pieces of the Moon.

REAL-DATA-03 then built the experiment properly. Three real NAC tiles of the same patch of
mare, every window derived from archive geometry, **overlap confirmed before anything was
interpreted** — 97.12 %, 82.72 %, 85.00 % — and the **unmodified** baseline run on all three
edges:

| edge | Δincidence | inliers | result |
|---|---|---|---|
| A → B | **39.81°** | **4** of 9538/12420 keypoints | REJECTED, and independently measured **1614 px wrong** at a fit residual of 4.1e-13 px |
| **B → C** | **0.96°** | **5365** (inlier ratio 0.9950) | recovers a scale a SPICE-derived archive field predicts to **0.04 %** |
| C → A | **38.85°** | **4** | REJECTED |

**A failure on a valid pair is the result, and this is one.** Seven candidate causes —
overlap, mare texture, decimation, resolution mismatch, relief displacement, window
uncertainty, the affine model — are eliminated by measurement against the succeeding edge on
the same ground. **Illumination difference is the only survivor, and it is deliberately not
claimed as the cause**: across three frames it is perfectly confounded with frame identity.
One more frame settles it, and the prediction is already written down.

Loop closure also met real data for the first time — three **independently estimated** edges,
residual 1201.04 px, no false closure.
See [`docs/stages/REAL-DATA_LRO_NAC.md`](docs/stages/REAL-DATA_LRO_NAC.md),
[`docs/stages/REAL-DATA-02_overlap_verification.md`](docs/stages/REAL-DATA-02_overlap_verification.md)
and [`docs/stages/REAL-DATA-03_real_overlap_registration.md`](docs/stages/REAL-DATA-03_real_overlap_registration.md).

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
| [`docs/stages/REAL-DATA_LRO_NAC.md`](docs/stages/REAL-DATA_LRO_NAC.md) | The real-data stage: what was ingested, what was measured, and what the registration failure does and does not license |
| [`docs/stages/REAL-DATA-02_overlap_verification.md`](docs/stages/REAL-DATA-02_overlap_verification.md) | Whether the real tiles ever shared ground, answered from archive geometry with **no pixel read and no matcher involved** |
| [`docs/stages/REAL-DATA-03_real_overlap_registration.md`](docs/stages/REAL-DATA-03_real_overlap_registration.md) | The first **valid** real-data registration experiment: overlap confirmed first, baseline unmodified, and what the failure does and does not license |

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
python -m pytest tests/ -q            # 376 passed, 2 skipped
python scripts/run_exp000.py          # geometry gate measurements
python scripts/run_exp001.py          # classical baseline vs synthetic ground truth
python scripts/run_exp002_ransac.py   # LO-RANSAC defect: before/after
python scripts/run_exp002_terrain.py  # terrain realism + regime comparison
python scripts/run_exp002_threshold.py  # failure threshold, disjoint validation
python scripts/run_exp002_gtfree.py     # GT-free estimators vs coherent wrong answers

# real LRO NAC (network; tiles are gitignored and must be fetched once)
python scripts/acquire_real_pair.py     # observational labels + byte-range image tiles
python scripts/check_real_tiles.py      # Phase-6 sanity checks + diagnostic figures
python scripts/register_real_pair.py    # UNMODIFIED baseline on the real pair

# does the pair actually share ground? (metadata only, ~130 KB, no image bytes)
python scripts/fetch_index_geometry.py  # named frame corners from the PDS archive index
python scripts/verify_tile_overlap.py   # tile overlap in km2 -- NO pixels, NO matcher

# a valid real experiment: geometry-driven windows, gated on confirmed overlap
python scripts/acquire_real_pair.py --from-geometry real_pair_index_geometry.json \
       --products nac.m1271742202lc,nac.m1335207975rc --out real_pair_usable_geo_manifest.json
python scripts/verify_tile_overlap.py --manifest real_pair_usable_geo_manifest.json \
       --outdir REAL-DATA-03 --require-confirmed        # THE GATE: non-zero unless CONFIRMED
python scripts/register_real_pair.py --manifest real_pair_usable_geo_manifest.json \
       --outdir REAL-DATA-03
python scripts/register_real_triplet.py                 # 3 INDEPENDENT edges + loop closure
python scripts/check_transform_against_geometry.py \
       --manifest real_triplet_geo_manifest.json \
       --registration experiments/REAL-DATA-03/loop_closure_triplet.json
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
src/siim/ingest/       PDS4 decoding, byte-range fetch, tile sanity checks        [done]
src/siim/demo/         verdict engine + FastAPI demonstrator                      [done]
docs/                  normative design documents
tests/                 property tests pinning the coordinate contract
scripts/               experiment runners
experiments/           EXP-XXX: config, metrics, findings
```

Further modules are added when a stage exists, not upfront.
