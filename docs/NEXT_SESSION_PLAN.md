# NEXT SESSION PLAN — refinements to win SIH 2026 (written 2026-09-04, end of day)

State of the repository when this was written: commit 9f4af7d plus running jobs
(see §5). Read `docs/MASTER_RESEARCH_AND_ARCHITECTURE_PLAN.md` addendum A1–A3
first; this file is the ordered to-do list that follows from it.

## 1. What the day established (measured, committed)

1. A licensable learned engine (DISK + LightGlue, Apache-2.0, CPU) registers
   real NAC pairs at 39–40° incidence difference where RootSIFT fails, with
   geometry-consistent transforms (EXP-007 tier 1 and tier 2 at 15 m).
2. The 59 m SLDEM rendered under each image's Sun carries no matchable
   structure on this mare window at 1.8, 3.6, 7 or 15 m. H0 is demoted to
   "conditional on a fine DEM". Honest, and it removes a weak leg from the story.
3. Sub-pixel is real and measured: 0.003 px on real self-warps; < 0.25 px
   under synthetic Sun change to 30° (EXP-010).
4. The affine default was quietly costing up to 1 px (E-034); refine-then-
   reselect fixes it to 0.002 px (EXP-011).
5. 42 geometry-confirmed real pairs across two windows are being registered
   (REAL-DATA-07); radar and 100 m proxies are on disk (REAL-DATA-08 queued).

## 2. Refinements that raise the ceiling (ordered by value / cost)

| # | Refinement | Why it wins | Cost | Depends on |
|---|---|---|---|---|
| R1 | **Add XFeat + LighterGlue as engine B4X** (Apache-2.0, real-time sparse inference on CPU, torch.hub) | Same licence class as B4L, 3–10× faster on CPU; makes the live demo instant and gives a second learned engine for cross-checking (two independent engines agreeing is verification evidence) | 0.5 day | none |
| R2 | **Engine agreement as a verifier**: B4L and B4X (or B1) transforms must agree within the geometry floor; disagreement → INCONCLUSIVE | Closes the per-image gauge blind spot of loop closure without a third image; cheap independent evidence | 0.5 day | R1 |
| R3 | **MatchAnything-ELoFTR as a cross-modality arm for REAL-DATA-08** (check the weight licence on HuggingFace first; ELoFTR is Apache-2.0, MatchAnything weights unverified) | Radar↔optical is exactly what it was pre-trained for; if it registers Mini-RF↔NAC, the multimodal claim becomes real | 1 day | licence check |
| R4 | **Pipeline order estimate → refine → re-estimate (rule B) → verify** wired into `assess()` with `model_selected_by` | Turns EXP-010/011 into deliverable behaviour; every real pass gets a re-estimated transform and a sub-pixel refinement | 1 day | none |
| R5 | **SERENRIDGE1 site** (23.75 N, 24.65 E; NAC DTM 5 m, LOLA RMS 1.05 m): re-run EXP-007's render arm with the fine DTM | The only way to keep the physics-conditioning claim alive; H2's second half ("a fine DTM restores it") is still untested | 1.5 days (DTM fetch + NAC census + run) | archive access |
| R6 | **Second region for REAL-DATA-07** (highlands, e.g. near Tycho or Apollo 16) | A judge will ask whether the illumination envelope is a mare result; one highland window answers it | 1.5 days | none |
| R7 | **Manual check points** on 3 real cross-illumination pairs (crater rims, boulders; 20–30 points each, two independent annotators) | The only route to a sub-pixel claim on real cross-illumination data | 1 day of human work + 0.5 day tooling | user/team time |
| R8 | **Render-consistency verifier** (registered image vs DEM render agreement) — only at fine-DEM sites | Closes loop closure's null space where a DEM exists | 0.5 day | R5 |
| R9 | **PSF-aware degradation** for the 100 m rung (Gaussian at the coarse MTF) | Correctness at the IIRS/WAC rung | 0.5 day | none |
| R10 | **`siim register` CLI**: two products in, four deliverables out (points CSV with covariance, registered product, metrics, verdict JSON with provenance) | The judges get a tool, not an experiment runner | 1.5 days | R4 |
| R11 | **Chandrayaan-2 ingestion** (PDS4 raw/calibrated OHRC/TMC, TMC-2 GeoTIFF L2, IIRS cube + geometry file) and the first C2↔NAC registration | The title of the problem | 2 days | **PRADAN download by the user** |
| R12 | Demo: three beats (learned engine at 40°; REJECTED with named evidence; 320:1 localisation) reading only recorded artefacts, plus a live `siim register` on a judge-supplied pair | Presentation score | 1 day | R10 |

## 3. What to stop doing

- No more time on the SLDEM render arm at mare sites; it has been measured.
- No more per-frame photometric arms; RD-06's frozen criteria are answered by
  EXP-007 tier 1 (S5 MET) and Part 2 should be written from that artefact.
- EXP-004 stays demoted; EXP-006 stays reframed as the ablation of R10.

## 4. Order of work when we resume

1. Read the completed artefacts: `experiments/EXP-007/exp007_results.json`,
   `experiments/REAL-DATA-07/real_data_07_results.json`,
   `experiments/REAL-DATA-08/real_data_08_results.json`,
   `experiments/REAL-DATA-06/photometric_normalisation_real_data_06.json`.
2. Write Part 2 for EXP-007, REAL-DATA-06, REAL-DATA-07, REAL-DATA-08 exactly
   as their frozen criteria dictate (S6 of EXP-007 will read NOT MET as worded;
   say so). Add stage-index rows and ledger decisions (D-044…).
3. R1, R2, R4, R10 (engine, agreement verifier, pipeline order, CLI).
4. R5 and R6 in parallel with whichever the user's PRADAN download enables (R11).
5. R7 check points once the team can annotate.
6. Re-score honestly; update the master plan's decision matrix with measured
   numbers.

## 5. Jobs left running at the end of the session (detached shell jobs)

- `scripts/run_exp007.py` full run → `experiments/EXP-007/logs/run_full.log`,
  then `scripts/run_real_data_08.py` → `experiments/REAL-DATA-08/logs/run.log`.
- `scripts/run_real_data_07.py --window RD03` → `logs/run_rd03.log`, then
  `--window RD04`, then `--reproduction-only` for RD03, then `--evaluate`
  → `experiments/REAL-DATA-07/real_data_07_results.json`.
- Each log ends with `EXIT <code>` when done. If a job died, its log says so;
  re-run the same command (each refuses to overwrite an existing artefact).

## 6. What the user must do before the next session

- PRADAN registration and the four downloads listed in the session notes
  (TMC-2 L2 ortho + DEM, one or two OHRC calibrated products, one IIRS cube with
  its geometry file, optional DFSAR) for lat 19.0–21.5 N, lon 21.5–22.8 E,
  placed unrenamed under `data/raw/chandrayaan2/<instrument>/`.
- Decide who annotates check points (R7).
