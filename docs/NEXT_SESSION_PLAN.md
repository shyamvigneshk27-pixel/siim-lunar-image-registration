# NEXT SESSION PLAN — written 2026-09-05, end of day

State of the repository when this was written: everything below is committed;
no job is running. Read `docs/MASTER_RESEARCH_AND_ARCHITECTURE_PLAN.md`
addenda A1–A4 first, then the four Part 2s written today (EXP-007,
REAL-DATA-06, -07, -08) and the pre-registration of REAL-DATA-09.

## 1. What today established (measured, committed)

1. **EXP-007 Part 2.** The 59 m SLDEM render carries no matchable structure on
   this mare at any rung from 1.8 m to 30 m (0–19 render keypoints on the
   high-Sun frames; 0 of 4 failing pairs at every rung). H0 demoted to
   conditional on a fine DEM (D-046). DISK + LightGlue converts C → A at 38.85°
   (56 consistent inliers) and three of four ~40° pairs at 7–30 m (D-047).
2. **REAL-DATA-06 closed as a null by construction (E-035, D-048):** a
   per-frame scalar correction is removed by the per-image stretch; both frozen
   arms were identical to `none`.
3. **REAL-DATA-07 Part 2 (42 pairs, 14 frames, two engines):** pooled
   Δincidence separation p = 0.0042 (RD-04 window alone 0.121), 0 wrong passes
   in 37, nothing above 40°; **replication NOT MET** (E2 fails vs A and vs B);
   **four frames fail against every partner irrespective of Δincidence**
   (D-049 — the frame-identity question is back with n = 4); the learned
   engine's native-scale envelope equals RootSIFT's, its yield inside it is
   5–25× (D-047-N1); north-up moved one recorded edge 7 → 9 across the rule.
   **Amended 2026-09-06 (E-037):** two of the four frames were mirror images;
   with the corrected orientation the replication is **MET** (E2 → A 2138,
   E2 → B 4), pooled p = **0.0012** with both windows < 0.05, 0 wrong passes
   in 76 across three engines; D-049 withdrawn (D-049-N2), D-040-N1
   discharged (D-040-N2). The two dark frames at 72–75° remain (item B).
4. **REAL-DATA-08 Part 2:** radar registers under no engine (0 / 48); at
   100 m B1 passes one frame and B4L three of four with 34–99 consistent
   inliers from 111 × 46 px strips, plus one wrong pass (D-050). Box average
   used where Part 1 named a PSF-aware operator; deviation recorded, R9 built.
5. **Engineering:** `siim.pipeline` (estimate → refine → re-estimate with rule
   B → verify; engine agreement caps the verdict at INCONCLUSIVE, never
   rejects), `python -m siim register` (points CSV with bootstrap prediction
   covariance, registered product, metrics, verdict with provenance),
   `siim.preprocessing.degrade_to_gsd` (R9), XFeat as engine B4X pinned to a
   commit (R1), the demo's two-engines panel and live registration card (R12
   beats 1 and 4). `learned` and `chandrayaan2` extras declared; torch/kornia
   frozen; DISK/LightGlue/XFeat licences recorded (S14).
6. **REAL-DATA-09 Part 1 frozen** before any Chandrayaan-2 byte exists;
   PRADAN acknowledgement wording recorded verbatim (S15).

## 2. What to do first tomorrow (the PRADAN day)

1. Download per the list in REAL-DATA-09 Part 1 §3; place unrenamed under
   `data/raw/chandrayaan2/<instrument>/`; write
   `data/manifests/chandrayaan2_manifest.json` (path, size, SHA-256, product
   ID) **before** opening any product.
2. Re-read `https://pradan.issdc.gov.in/ch2/ack.xhtml` and record any
   difference from S15.
3. Implement the ingestion contract exactly as §4 says, one step at a time,
   each refusing rather than guessing. `tifffile` for GeoTIFF. Every product
   that fails a step is reported *not ingested* with the step named.
4. Run P1 (TMC-2 ortho ↔ NAC at 5 m) first; it is the pair most likely to
   exist and to register. Then P2, P4, P5, P3, P6 in that order.
5. Write Part 2 as the criteria read. Then the demo's beat 3 (320:1) if and
   only if P6 produced an artefact.

## 3. Refinements still open, ranked (value / cost)

| # | Item | Why | Cost | Depends on |
|---|---|---|---|---|
| ~~A~~ | ~~E2 diagnostic~~ — **DONE 2026-09-05/06 (E-037):** E2 and four other frames are mirror images by their corner metadata; corrected orientation; amended run: replication MET, p = 0.0012, 0 wrong passes / 76 | — | — | — |
| B | **Incidence-ceiling sweep 70–75°** (RL-042c): after the correction 65–70° is 0.75 and 70–75° is 0.33 on n = 3; more frames in that bin | Sets the top of the incidence scope; D-029's 75° looks 5–10° too high here | 0.5 day | ODE census |
| ~~C~~ | ~~Calibrate the engine-agreement floor~~ — **DONE:** 3 px, measured on three engines (agree ≤ 2.16 px, inconsistent ≥ 247 px; D-051) | — | — | — |
| D | **Second region (highlands)** for REAL-DATA-07 | Is the envelope a mare result? | 1.5 days | none |
| E | **SERENRIDGE1** NAC DTM: EXP-007's render arm at a fine DEM (RL-039b) | The only remaining test of H0 | 1.5 days | PDS access |
| F | **Manual check points** on 3 cross-illumination pairs (R7) | The only route to a real sub-pixel claim | 1 day human + 0.5 tooling | annotators |
| G | **MatchAnything-ELoFTR** on the REAL-DATA-08 radar rows (RL-043b) | The only route to a multimodal claim before C2 | 1 day | weight licence |
| ~~H~~ | ~~Re-run the WAC rows with the PSF-aware operator~~ — **DONE** (`real_data_08_psf_fwhm1.json`): criteria unchanged; B4L 68 / 41 / 101 consistent; three wrong passes on frame B | — | — | — |
| ~~I~~ | ~~B4X on the REAL-DATA-07 pairs~~ — **DONE** in the amended run: 27 / 42 successes, 0 wrong passes; three-way agreement measured | — | — | — |
| ~~J~~ | ~~Verdict false-acceptance bound in the docs~~ — **DONE:** `MEASURED_WRONG_PASS` in `siim.demo.verdict` (update to 0 / 46 B1, 1 / 30 B4L incl. RD-08 box run, 0 / 27 B4X after the amended run) | — | — | — |

## 4. What to stop doing

- No more SLDEM render arms on mare (measured twice: EXP-007, EXP-010 D3).
- No per-frame photometric arms (E-035).
- No further replication attempt is needed: the amended run met S1.
- Do not report a coarse-rung pass without its geometry verdict (D-050).

## 5. Known loose ends

- `experiments/REAL-DATA-07/rows_rd03.json` contains the first run's two
  wrong-direction raw rows, flagged `reproduces_recorded: false` (E-036);
  they are excluded from S4 by the `recorded_direction` flag and stay on disk.
- REAL-DATA-08's A and B frames appear twice per rung (one row per stage
  manifest); Part 2 says which row is which.
- The B → C pair is INCONCLUSIVE against archive geometry for every engine at
  every rung since REAL-DATA-03; a property of its corner geometry.
- `pytest -q` prints no summary line because `addopts = "-q"` doubles the
  flag; use `-o addopts=""` to see the count.
