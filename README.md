# SIIM — Satellite / Lunar Image Integrity & Matching

**SIH 2026 · Problem Statement 26166 (ISRO)** · CPU-only · runs offline

> **A lunar image-registration system that refuses to report an alignment it cannot defend.**

Registration failure is not the danger in orbital imagery. **Silent** registration failure is —
an aligner that returns a confident, self-consistent, wrong answer, and a quality metric that
agrees with it. SIIM is built around that problem: it establishes overlap *before* it
interprets anything, excludes the metric the field normally trusts, corroborates against data
the matcher never saw, and states the scope of every claim it makes.

## Run it — one command

```bash
python -m pip install -e ".[dev]"
python scripts/run_demo.py --open
```

That is the whole setup. **No network access, no API keys, no build step, no GPU.** Every
real-data number in the demonstrator is read from a recorded artefact under `experiments/`
and every image is a local PNG, so it behaves identically on a disconnected laptop. If port
8000 is busy the launcher moves to the next free port and says so.

**What you will see**, in four steps on one page, for a real pair of LRO NAC frames:

| | |
|---|---|
| **1 · Do these images even overlap?** | Answered from archive corner geometry with **no pixel read and no matcher involved**, with the archive's own coordinate quantisation propagated by Monte Carlo |
| **2 · What did the matcher find?** | The unmodified RootSIFT + LO-RANSAC baseline, with its correspondences drawn on the real tiles |
| **3 · What does the evidence say?** | Inlier count, coverage, loop closure — and `fit_rmse` shown but **flagged as excluded from the verdict** |
| **4 · Should this be trusted?** | `VERIFIED` / `REJECTED` / `INCONCLUSIVE` **with the reasons**, the pre-registered pass/fail rule stated separately, and every number naming the file it came from |

Three real cases are loaded (one that succeeds, one that fails, one control) plus a
**controlled synthetic adversarial case**: an alignment that is 64 px wrong, self-consistent,
and reports a near-zero fit residual. Comparing that case against the real failing edge is the
fastest way to see what this project is actually about.

## How to verify the demo evidence

The demonstrator's real-data figures are **read from recorded experiment
artefacts**, not recomputed while you watch. That is deliberate — it keeps the
page identical to the stage reports that justify it — but it means "read from a
file" and "typed into a file" look the same from the outside. Three mechanisms
exist so you don't have to take it on trust:

| | |
|---|---|
| **The overlay is certified when it is built** | `scripts/build_demo_assets.py` re-runs the identical seeded pipeline and **refuses to write** unless every recomputed statistic matches the recorded artefact exactly |
| **It is re-checked at load time** | `_check_asset_matches_artefact` in `src/siim/demo/evidence.py` re-verifies that certification on every request, so a hand-edited asset is rejected rather than displayed |
| **Tests pin the page to the artefacts** | the displayed numbers are asserted equal to the recorded ones, edge by edge |

Run the third one yourself — it takes a few seconds and needs no network:

```bash
python -m pytest tests/test_demo_real_data.py tests/test_demo_evidence_integrity.py -q
```

Those cover, among other things: displayed numbers equal recorded numbers; every
step names the artefact it came from; a missing **or corrupt** artefact produces
a clean error naming the file rather than a silent substitution; an overlay that
disagrees with its artefact is refused; and a diagnostic that *fails* is never
displayed as a diagnostic that was *not applicable*.

In the demo itself, each real case's provenance panel lists the exact repo-relative
path of every file its numbers were read from, alongside the byte ranges and
SHA-256 of the archive imagery. Open any of them and check.

### The strongest version of that check: re-derive the numbers from the pixels

Every mechanism above compares **a recorded number against another recorded
number**. A sufficiently careful hand-edit would survive all three. Re-running
the pipeline would not.

```bash
python scripts/rederive_recorded_registrations.py
```

This loads the archive tile bytes, applies each stage's preprocessing, runs the
**unmodified** baseline, and compares **54 quantities** against the recorded
artefacts — keypoint counts, putative counts, inliers, inlier ratio, fit RMSE,
both coverage metrics and the full 3×3 transform matrix, for all six real edges
of REAL-DATA-03 and REAL-DATA-04. It exits non-zero on any disagreement, and the
baseline configuration is read **out of each artefact** rather than hard-coded,
so it cannot pass by checking a configuration nobody ran.

Current result: **all 54 re-derive exactly** — including `4.138e-13 px`,
`1.885e-13 px`, and every transform matrix to `max|Δ| = 0`.

It needs the decoded tiles, which are gitignored (~166 MB, re-fetchable by the
byte ranges and SHA-256 in `data/manifests/`). Without them it exits **2** —
*cannot check* — which is deliberately a different answer from **1**, *checked
and wrong*. `tests/test_rederivation.py` runs it when the tiles are present and
**skips** otherwise, reporting the skip as "cannot check", never as a pass.

**What a pass establishes:** the recorded numbers are genuine pipeline output.
**What it does not:** that any registration is *correct*. The B→D edge
reproduces its `1.885e-13 px` fit residual to every digit while being
independently measured hundreds of pixels wrong. Reproducing a wrong answer
exactly is still a wrong answer — which is the entire point of this project.

## What is honestly claimed, and what is not

| | |
|---|---|
| **Real LRO NAC, end to end** | Byte-range fetched from the public PDS archive, SHA-256 recorded, PDS4-decoded, sanity-gated, registered by an unmodified baseline |
| **Δincidence predicts registration outcome — separation is perfect, and NOT YET SIGNIFICANT** | On **six** real edges across five frames and two ground windows — successes at 0.96° and 11.73°, failures at 38.85°–51.54°. **Exact one-tailed permutation test: p = 0.0667** (`siim.evaluation.exact_separation_test`, computed from the rows, not asserted). Two successes among six edges: chance produces this separation once in fifteen, so the result **does not reach the conventional 0.05**. One-tailed is admissible only because the direction was frozen in a decision table before frame D was acquired. The edges share frames and are therefore not independent, so **0.0667 is a lower bound**. **One further failing edge would give p = 0.0476** — and high-incidence frames are abundant where the low-incidence frames REAL-DATA-05 hunted are not |
| **The RMSE trap, on real data** | A real edge reports a fit RMSE of `1.885e-13 px` for a transform independently measured **797 px wrong** |
| **NOT proven: illumination as *the* cause** | Frame identity is **substantially weakened, not conclusively refuted** — see D-040-N1. The replication (REAL-DATA-05) returned **UNRESOLVED** |
| **NO Chandrayaan-2 data** | OHRC / TMC-2 / IIRS are behind ISSDC authentication. **No multi-modal claim is supported anywhere in this repository** |
| **NO ground truth on real imagery — and the corroboration resolves only to ~100 px** | None exists for these products. A succeeding real edge is *corroborated*, never verified — and the resolution of that corroboration is stated here rather than left to be found. The archive-geometry bound **discriminates at the scale of ~100 px and certifies nothing finer**: D→A's median disagreement is **56.3 px against a 105.6 px discrimination floor** (0.53×), i.e. *inside* the floor, so the check cannot separate a correct alignment from one translated by up to ~100 px. The **0.04 % / 0.13 %** `SCALED_PIXEL` agreement constrains **SCALE ONLY, not translation**. **Neither check provides any sub-pixel accuracy evidence.** `[MEASURED]` REAL-DATA-04 §11.2. **Amended 2026-09-03 (S9):** the first sentence is too broad and is left as written rather than restated. No *correspondence* ground truth exists — but **geodetic control does**, and this project has not used it. LROC NAC regional controlled mosaics have a published average positional offset **below 13 m** (median <12 m latitude, <5 m longitude), which at NAC resolution is roughly **7–26 px** against the 105.6 px floor quoted above. The accuracy claim is therefore weaker than the evidence available, not weaker than the evidence obtainable, and closing that gap is an unblocked task rather than a limitation of the data |
| **Δazimuth measured, and it does NOT explain the outcomes** | `[MEASURED]` `scripts/check_solar_geometry.py` — ground solar azimuth computed from the archive's sub-solar point. **Δincidence separates all six edges (11.73° → 38.85°); Δazimuth does not** (the strongest success sits at Δaz 50.29°, above three of four failures). **Not pre-registered** — run after the fact as a confound check |
| **Δphase and Δincidence are NOT separable here** | Every frame is near-nadir (emission ≤ 1.75°), so phase = incidence + emission and the two deltas agree to **2.56°**. Lunar photometry is **phase**-driven, so *incidence* is our **label** for the variable, not a demonstrated mechanism. Separating them needs an off-nadir frame we do not have |
| **NO sub-pixel accuracy on real imagery** | The PS's headline accuracy requirement. Sub-pixel is shown **only against synthetic ground truth under fixed illumination** (0.009–0.386 px, EXP-001). `check_transform_against_geometry.py` states in its own output that it *"certifies NO accuracy, and in particular NO sub-pixel accuracy."* **No sub-pixel refinement stage is implemented** |
| **Registered product + match points: produced, for ONE edge** | The two named PS deliverables now exist for the D→A edge — `experiments/REAL-DATA-04/products/`: 1759 correspondences with full-frame pixel and archive-derived ground coordinates, the warped source tile, and a difference image. **Emitted from recorded evidence; no matcher runs and nothing is estimated.** Labelled *"a registered product; no ground truth exists for it; corroborated, not verified; class B."* An edge the pre-registered rule **rejected** is refused a product |
| **Scale: 4× on mare, 8× on highlands — the PS implies 320:1** | `[MEASURED]` `experiments/EXP-001/scale_limit_probe.json`. **Every** failure beyond those ratios is **detector starvation**, not descriptor failure — mare yields *literally zero* SIFT keypoints at 128², which is D-026's texture poverty in its sharpest form. The fix is normalising to a common GSD before matching (D-005): **designed, not implemented**, and untestable here because no cross-modal data exists |
| **The pipeline runs on tiles, not full frames** | `[MEASURED]` matching is O(keypoints²): 0.18 s at 0.26 Mpx, 5.68 s at 1.05 Mpx. A full 264 Mpx NAC frame extrapolates to ~100 h/edge and ~2 GB of descriptors. Every real result used 2048×1024 decimated tiles (4.5–10.1 s). Tiling is what the geometry layer is built for; **the tiling driver is not written** |
| **NOT established: that the synthetic illumination model predicts real behaviour** | The two disagree, in both directions, and we state it rather than wait to be told. EXP-001 measured Δelevation −30° (≈ Δincidence 30°) as **survivable** — 49 inliers, 0.81 px — where real Δincidence 38.85° gives **4**. EXP-003 put the Δazimuth cliff at **21–27°** on A-regimes, where real edge D→A succeeds with **1656** inliers at Δaz **50.29°**. *(That real edge also has small Δincidence, so it is not a controlled azimuth test — but the synthetic model offers no mechanism by which small Δincidence rescues large Δazimuth.)* Likely causes, none measured: Lambertian shading with cast shadows omits the Hapke backscatter and opposition surge that dominate real regolith; the synthetic scene is highlands where the real data is mare; the synthetic sweep never reaches the 70° incidence regime of frames B and C. **EXP-001/002/003 remain internally valid; their external validity to lunar imagery is unsupported** |
| **NO Sun-azimuth *invariance* claim** | Every real result is illumination-varied by **incidence** (see the two rows above for what that does and does not mean) |

The project is named for Sun-angle invariance, and the honest position is that **we measured
the classical baseline and it is not Sun-angle invariant**. That measurement — on real archive
imagery, against criteria fixed before the data existed — is the contribution.

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
| REAL-DATA-04 — Can frame identity and illumination be separated? | **complete — ANSWERED.** D↔A succeeds (1656 inliers at Δinc 11.73°), D↔B fails (3 at 51.54°). **Illumination attributed (D-040); frame identity substantially weakened, NOT conclusively refuted** — `experiments/REAL-DATA-04/` |
| REAL-DATA-05 — Does the illumination result replicate on a second low-incidence frame? | **complete — UNRESOLVED, BY DATA AVAILABILITY.** The pre-registered screen returned **zero** admissible frames at every tier and rung; no image byte was fetched and no registration was run. The replication is still owed — `data/manifests/screen_frame_e_*.json` |
| **September 2 demo** | **the current priority.** Scientific expansion stopped after REAL-DATA-05 |
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
the same ground. At that point illumination was the only survivor and was deliberately **not**
claimed as the cause: across three frames it was perfectly confounded with frame identity.

**REAL-DATA-04 broke that confound with a fourth frame D**, against a decision table frozen
before the data existed. D↔A succeeds (**1656** inliers at Δinc 11.73°) and D↔B fails (**3**
at 51.54°) on edges whose independently confirmed overlap differs by 0.95 percentage points.
Across the six real edges now measured, every frame appears in both a succeeding and a failing
edge, and Δincidence separates all six.

**What that does and does not license.** Illumination — specifically Δ*incidence* — is the
attributed cause, in the scope D-040 states. Frame identity is **substantially weakened, not
conclusively refuted**: the argument is a join across two stages, and frames A and D each have
**n = 1** observations in the successful regime. **REAL-DATA-05 was the pre-registered
replication and it returned UNRESOLVED** — of 906 archive products, only two sit in the
required incidence band over shared ground, and both are orientation-incompatible with the
incumbents, so the screen returned zero admissible frames and the stage stopped rather than
relax a criterion. The replication is owed, and **EXP-004** (orientation assignment,
pre-registered and not started) is now the measured blocker on it.

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

This is a hypothesis carried over from SAR-optical imagery, not an established lunar result — and its source is a **single preprint** (`docs/sources.md` S4), carried with an explicit transfer caveat. **EXP-006 is the experiment that would test this hypothesis; it is not pre-registered and has not been started.** Until it runs, the thesis above is a design rationale and nothing more, and the project reports the refutation if that is the outcome.

## What this system is built to do that the obvious version does not

- **Measure accuracy non-circularly.** Reprojection RMSE over RANSAC inliers is a *fit* statistic: it falls monotonically as you tighten the threshold, and it cannot detect a match set uniformly shifted by one crater spacing. Accuracy is instead evidenced by **synthetic ground truth** and **loop closure over image triplets**. K-fold held-out residuals and cycle consistency are retained as **degeneracy detectors only** — ADR-0011 measured their detection of a coherent wrong solution at **0.200**, and forbids describing them as protection against one. Headline claims quote the *worst* applicable estimator.
- **Handle the real scale ladder.** Sensor GSDs mandate ratios of 2:1 up to **320:1** (OHRC↔IIRS). The unmodified baseline is measured to hold to **4× on mare and 8× on highlands** (`experiments/EXP-001/scale_limit_probe.json`), and every failure beyond that is **detector starvation**, not descriptor failure. Scale normalisation to a common GSD is therefore **designed as a first-class stage (D-005) and is NOT implemented** — the gap is stated, not closed, and it is untestable here because no cross-modal data exists.
- **Survive shadow motion.** Measured against exact ground truth on terrain matched to published LOLA slope statistics: a RootSIFT baseline fails between **Δazimuth 15° and 30°** — a cliff, not a slope. We expected the break at 180° from shadow *reversal*; it arrives far earlier, because shadow *movement* alone changes gradient orientations. Contrast normalisation cannot repair it, since it preserves sign. Sun elevation is survivable by comparison.
- **Know that a confident answer can still be wrong.** A correspondence set displaced by exactly one crater spacing is 64 px wrong and perfectly self-consistent: fit RMSE reads ~0, held-out residual reads 0.47 px. Measured: `fit_rmse` scores **ROC AUC 0.495** as a failure detector — chance. Only **loop closure** over three images catches it (100% detection, 0% false alarm).
- **Know when it has failed.** A system that is right 90% of the time and knows which 10% is worth more operationally than one that is right 95% and cannot tell you when it is not.

## Reproducing the experiments

**None of this is needed to evaluate the project** — see *Run it* at the top of this file.
Everything below re-derives results that are already recorded under `experiments/`.

```bash
python -m pip install -e ".[dev,viz,experiments]"
python -m pytest tests/ -q            # 605 passed, 2 skipped
                                      # (4 skipped on a fresh clone: the two
                                      #  re-derivation tests report CANNOT CHECK
                                      #  until the gitignored tiles are fetched)
```

Every real-data number is a function of the OpenCV SIFT build, so the exact
environment that produced the recorded artefacts is written down in
[`requirements-frozen.txt`](requirements-frozen.txt) — a record, not a
lockfile. `pip install -e` above remains the documented install; use the frozen
file only to reproduce the artefacts bit-for-bit.

**Offline** — synthetic experiments, no network:

```bash
python scripts/run_exp000.py          # geometry gate measurements
python scripts/run_exp001.py          # classical baseline vs synthetic ground truth
python scripts/run_exp002_ransac.py   # LO-RANSAC defect: before/after
python scripts/run_exp002_terrain.py  # terrain realism + regime comparison
python scripts/run_exp002_threshold.py  # failure threshold, disjoint validation
python scripts/run_exp002_gtfree.py     # GT-free estimators vs coherent wrong answers
```

**Requires network, and re-fetches ~166 MB of archive imagery.** The decoded tiles are
gitignored; the manifests under `data/manifests/` carry the byte ranges and SHA-256 that make
them reproducible. The demonstrator does **not** need any of this.

```bash
# the two named PS deliverables, from RECORDED evidence -- runs NO matcher
# and estimates nothing; needs the tiles only for the warp
python scripts/register_real_triplet.py --emit-product        --manifest real_quad_d_geo_manifest.json --outdir REAL-DATA-04        --overlap-artefact experiments/REAL-DATA-04/overlap_real_data_04.json

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
