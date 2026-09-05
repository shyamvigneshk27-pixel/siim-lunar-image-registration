# REAL-DATA-08 — Cross-sensor and cross-modality correspondence on open archive proxies: NAC ↔ Mini-RF S-band radar (15 m) and NAC ↔ WAC (100 m)

**Part 1 — pre-registration. FROZEN 2026-09-04, before any radar or WAC byte
was matched.** Part 2 is empty until Part 1 is committed.

**Classification: DELIVERABLE-CRITICAL, PROXY.** The problem statement's title
says *multi-modal* and names IIRS. No Chandrayaan-2 product is available to
this repository (PRADAN account not yet created). This stage measures the
pipeline on the two open archive products over the recorded ground that change
the physics most: a **radar** image (genuine modality change) and a **100 m
mono mosaic** (the IIRS/WAC scale rung). Every result is labelled PROXY and is
never reported as a Chandrayaan-2 result.

## 1. Why this stage exists

Multi-modality has never been defined or tested here (MASTER PLAN §21). Two
open products cover the recorded Mare Serenitatis windows and were located on
2026-09-04 through ODE:

| Product | What it measures | Sampling | Coverage | Access |
|---|---|---|---|---|
| Mini-RF `LSZ_02951_2S1_EKU_16N022_V1` (LRO, S-band 12.6 cm, Stokes S1 total power, level 2, map-projected equirectangular, 2048 px/deg ≈ 14.8 m) | Radar backscatter: roughness at the wavelength scale, dielectric properties, incidence-dependent; **not** reflected sunlight | 33192 lines × 1816 samples, PC_REAL 32-bit, RECORD_BYTES 7264; lat 7.81–24.02 N, lon 21.50–22.39 E; radar incidence 51.8° | HTTP 206 verified on `pds-geosciences.wustl.edu` |
| LROC WAC global morphology mosaic tile `WAC_GLOBAL_E300N0450_100M` (643 nm mono, 100 m, equirectangular, lat 0–60 N, lon 0–90 E, 1.8 GB) | Reflected sunlight, photometrically normalised mosaic of ~15,000 frames at a **fixed** illumination convention | 100 m | covers both windows | `pds.lroc.im-ldi.com` byte ranges (slow, verified for NAC) |

Radar ↔ optical is the standard hard case of the multimodal literature (RIFT,
MINIMA, arXiv 2604.10217) and the pairing used by the Chandrayaan-2 comparison
paper (DFSAR). WAC ↔ NAC at 100 m is the IIRS rung of the sensor ladder
(IIRS 80 m) on a photometrically normalised reference, which is also how paper
2 (IIRS seleno-referencing) was done.

## 2. Questions

**Q1 (radar).** Does any engine register a NAC tile, degraded to the radar's
sampling, to the Mini-RF strip, and is the transform consistent with archive
geometry?

**Q2 (100 m rung).** Does the pipeline register a NAC tile degraded to 100 m
against the WAC mosaic, and with what error against the geometry bound?

**Q3 (what modality costs).** Compared with NAC ↔ NAC at the same GSD and a
similar Δincidence (REAL-DATA-07), how much does the modality change cost in
success rate and in inlier count?

## 3. Data, fixed in advance

Source: the four incumbent NAC frames' recorded tiles (A, B, C, D) and, for
the coarse rungs, the EXP-007 long windows. Radar rung: NAC degraded by
PSF-aware block mean to 14.8 m (k = 16 on the long windows; k = 8 on 4096-line
tiles gives ≈ 7 m and is also run). WAC rung: NAC long windows degraded to
100 m (k ≈ 110; a 12288-line window becomes ≈ 110 × 45 px, which is small and is
stated as the limit of what a NAC strip can offer at this rung; the whole
frames are not fetched).

Reference windows are cut from the map-projected products by byte range around
each ground window with a 2 km margin. Ground truth is the archive geometry:
NAC pixel → (lon, lat) by the corner map; map product (lon, lat) → pixel by its
label's projection. This is a **bound** (corner quantisation ≈ 150 m ≈ 10 radar
px, 1.5 WAC px), not a pixel-exact truth.

## 4. Method, fixed in advance

Engines: `B1` RootSIFT; `B7` phase congruency + RootSIFT (the project's
multimodal classical arm); `B4L` DISK + LightGlue. Tiles north-up from corner
geometry (REAL-DATA-07 machinery); map products are already north-up. Radar
intensity is log-compressed (dB) before the percentile stretch, stated here
because it is the one modality-specific preprocessing step. LO-RANSAC affine,
threshold 3.0, seed 0; rule `n_inliers <= 8`; geometry check with the restated
floor; a pass that is INCONSISTENT is a wrong pass.

## 5. Hypotheses and criteria — FROZEN

**H1 (radar is hard).** B1 fails on every NAC ↔ radar pair.
> **S1 MET** if 0 of the radar pairs pass under B1 with a consistent geometry.
> Prediction: MET. Confidence HIGH.

**H2 (structure survives modality).** At least one of B7 or B4L registers at
least one NAC ↔ radar pair with a geometry-consistent transform.
> **S2 MET** if ≥ 1 such pair. Prediction: MET for B4L on the low-incidence
> frames D or A (shading contrast lowest, topography dominates both images).
> Confidence LOW-MEDIUM.

**H3 (100 m rung).** NAC ↔ WAC registers under B1 for ≥ 2 of the 4 frames
with geometry-consistent transforms, in WAC pixels.
> **S3 MET** if ≥ 2 of 4. Prediction: MET; the WAC mosaic is photometrically
> normalised and 100 m mare morphology is crater-dominated. Confidence MEDIUM.

**H4 (cost of modality, reported).** Success rate and median inliers for
NAC ↔ radar versus NAC ↔ NAC at k = 16 from REAL-DATA-07/EXP-007, at the
nearest Δincidence bin. Reported, not a criterion.

## 6. What each outcome licenses

S2 MET: the deliverable may state that the pipeline registers a genuine
modality change on real lunar data with a named engine and a stated
success rate; the IIRS thermal case remains untested. S3 MET: the IIRS rung of
the scale ladder is demonstrated on a real 100 m reference. Nothing here is a
Chandrayaan-2 result; the words OHRC, TMC-2 and IIRS do not appear in Part 2's
claims except as the rungs these proxies stand in for.

## 7. Threats to validity

Radar incidence 51.8° and side-looking geometry produce layover/foreshortening
that no affine model captures over relief; on mare relief is low, which is why
this window is tractable and why the result must not be extrapolated to
highlands. Corner-map geolocation error is the same as everywhere. The WAC
mosaic's own registration to LOLA is ~100 m class. Small pixel counts at the
100 m rung limit inlier statistics.

## 8. What this stage does NOT do

No Chandrayaan-2, no IIRS thermal, no Diviner (the only L3 product over the
window in ODE is rock abundance, not temperature), no matcher tuning, no
sub-pixel claim.

---

## Part 2 — Results

**Run:** 2026-09-05, `scripts/run_real_data_08.py` (Part 1 frozen at commit
d475124), **5.8 min**, 126 rows → `experiments/REAL-DATA-08/real_data_08_results.json`.
The 2026-09-04 run died with the machine after 47 rows (log preserved as
`logs/run_died_v1.log`; an earlier crash on a stale module reference as
`run_crash_v1.log`). Proxies: Mini-RF `LSZ_02951_2S1_EKU_16N022_V1` block
(SHA-256 `d0b34834…`) and WAC `WAC_GLOBAL_E300N0450_100M` block (`ce24939c…`),
cut by byte range around the two windows. Sources: the four recorded NAC tiles
(A, B, C, D from both stage manifests) and the EXP-007 long windows. Engines
B1, B7, B4L; rule and geometry check as frozen.

**Deviation from Part 1, recorded.** §3 says the NAC source is degraded by a
*PSF-aware* block mean. The runner used the plain block mean of EXP-007
(`decimate`: a box average, no Gaussian at the coarse sensor's MTF). A
PSF-aware degradation now exists (`siim.preprocessing.degrade_to_gsd`, R9)
and was **not** used here; every number below is with the box average. The
deviation is stated rather than corrected after the fact; a re-run with the
PSF-aware operator is a separate, labelled row set if it is ever made.

### S1 — B1 fails on every NAC ↔ radar pair: MET

48 radar rows (4 frames × 2 rungs × up to 2 windows × 3 engines). Under B1:
0–4 inliers on every pair, every transform INCONSISTENT with the geometry
prediction (median disagreement 120–18 800 px against floors of 12–20 px).
Predicted, and it happened.

### S2 — a structure engine registers at least one radar pair: NOT MET

B7 (phase congruency) 0 / 16 and B4L 0 / 16. The closest anything came:
B4L on frame D's long window at k = 16 (17 m NAC against 14.8 m radar) found 9
putative and **8** inliers — fails the rule by one — with a transform 193 px
from the prediction (floor 15 px): a wrong answer that nearly passed. Every
other radar row is 0–5 inliers, INCONSISTENT or no transform.

**No modality change is registered by anything in this repository.** The
optical-to-radar case, which the multimodal literature treats as the standard
hard problem and which paper 2's DFSAR arm is the Chandrayaan-2 instance of,
is not solved here by classical, phase-congruency or DISK + LightGlue
matching on this mare window at 7–17 m. H4 (cost of modality): NAC ↔ NAC at
k = 16 on the same windows registers three of four ~40° pairs under B4L and
both low-Δ pairs under every engine (EXP-007 tier 2); NAC ↔ radar registers
**none** under any engine at any Δ. The cost is total.

### S3 — NAC ↔ WAC registers under B1 for ≥ 2 of 4 frames: NOT MET (1 of 4)

B1 passes on **one** frame: D, long window, k = 64 (68 m NAC against 97 m WAC),
**9** inliers of 13 putative, CONSISTENT (2.56 px against a 2.79 px floor). A,
B and C under B1: 0–5 inliers at every rung. The NAC sources at this rung are
small — 128 × 64 px (recorded tiles at k = 32), 192 × 79 (long windows at
k = 64) and **111 × 46** (long windows at k = 110, the 100 m rung proper) — and
B1 finds 13–189 keypoints in them, which is the detector starvation of D-026
in its coarse-rung form.

**What the learned engine did at the 100 m rung (reported; S3 is a B1
criterion and this earns no credit under it).** B4L, north-up NAC long
windows against the WAC block:

| frame | inc | rung (NAC m / WAC m) | src px | B4L inliers / putative | geometry (median / floor) |
|---|---|---|---|---|---|
| A | 29.95° | 60 / 97 | 192 × 79 | **74 / 77** | **CONSISTENT** 1.92 / 2.79 |
| A | 29.95° | 102 / 97 | 111 × 46 | **40 / 43** | **CONSISTENT** 2.11 / 2.27 |
| B | 69.76° | 59 / 97 | 192 × 79 | 9 / 26 | **INCONSISTENT** 27.7 / 2.79 — a **wrong pass** |
| B | 69.76° | 101 / 97 | 111 × 46 | **34 / 43** | **CONSISTENT** 1.84 / 2.27 |
| C | 68.80° | 55 / 97 | 192 × 79 | 11 / 28 | INCONCLUSIVE 6.39 / 2.79 |
| C | 68.80° | 94 / 97 | 111 × 46 | 10 / 16 | INCONCLUSIVE 3.92 / 2.27 |
| D | 18.22° | 69 / 97 | 192 × 79 | **99 / 102** | **CONSISTENT** 2.73 / 2.79 |
| D | 18.22° | 118 / 97 | 111 × 46 | 40 / 50 | INCONCLUSIVE 2.37 / 2.27 |

Each A and B row appears twice in the artefact (once per stage manifest); the
second A row at 102 m gives 8 inliers INCONSISTENT and the second B row at
101 m gives 4 — the same pair, a different 46-px-wide strip. Taken together:
B4L registers a 111 × 46 px NAC strip at 100 m to the WAC mosaic on three of
four frames with a geometry-consistent transform, at ≈ 2 px against a ≈ 2.3 px
floor, on Sun geometries from 18° to 70° incidence against a photometrically
normalised mosaic; and it produced **one wrong pass** (B at 59 m: 9 inliers,
28 px off), the first wrong pass recorded for the engine (0 / 17 in REAL-DATA-07
becomes 1 / 23 across the two stages). B7 registers nothing at this rung
(0–3 inliers everywhere).

### What is claimed and what is not

- **Claimed:** on real archive data over Mare Serenitatis, NAC ↔ Mini-RF
  S-band radar at 7–17 m is registered by **no** engine in this repository
  (B1 0 / 16, B7 0 / 16, B4L 0 / 16); the radar arm is a measured negative.
- **Claimed:** NAC ↔ WAC at the 100 m rung is registered by B1 on one frame
  (9 inliers, consistent) and by B4L on three of four frames with 34–99
  geometry-consistent inliers at ~2 px against a ~2.3 px floor, from NAC
  strips of 111 × 46 px; B4L also produced one wrong pass at 59 m. The
  100 m rung of the scale ladder is therefore **demonstrated on a real
  reference by the learned engine and not by the classical one**, on mare,
  with the floor stated.
- **Not claimed:** anything about Chandrayaan-2, OHRC, TMC-2 or IIRS — these
  are open-archive PROXIES for the rungs, and the words appear here only as
  the rungs they stand in for; any radar registration; any accuracy finer
  than the geometry floor; any highland or high-relief radar behaviour
  (layover untested); anything with the PSF-aware operator (not used).

### Consequences

- **D-050:** the multimodal claim of the problem statement is **not supported
  by a radar proxy**, and the deliverable says so; the 100 m rung is supported
  by B4L with one wrong pass in six passes at that rung, so a pass at the
  coarse rung is never reported without its geometry verdict.
- The scale-ladder design (D-005) gets its first real coarse-rung
  measurement: degradation to the reference GSD before matching works for the
  learned engine at 100 m and starves the classical detector.
- R9 (PSF-aware degradation) is implemented after this stage and is the
  operator any future rung run uses; this artefact stays as the box-average
  result it is.

## Part 2 — Addendum (2026-09-05): the PSF-aware re-run

The deviation recorded above (box average where Part 1 named a PSF-aware
operator) was closed the same day: `scripts/run_real_data_08.py --psf-fwhm 1.0
--out real_data_08_psf_fwhm1.json` degrades the NAC source through a Gaussian
of one coarse-pixel FWHM and then the block mean (`siim.preprocessing.degrade_to_gsd`).
Artefact: `experiments/REAL-DATA-08/real_data_08_psf_fwhm1.json` (84 engine
rows, 24.2 min under CPU contention). The original artefact stands; this is a
labelled second row set, not a replacement.

**Criteria, unchanged in outcome.** S1 MET (radar: B1 0 / 16). S2 NOT MET
(radar: 0 / 48 under all three engines; best 9 inliers). S3 NOT MET (B1 on
WAC: 1 of 4 frames, D at 68 m, 9 inliers, CONSISTENT — identical to the box run).

**B4L at the WAC rung, box vs PSF (same windows, same k):**

| frame, rung | box average | PSF-aware |
|---|---|---|
| A, 60 m | 74 CONSISTENT | 68 CONSISTENT |
| A, 102 m | 40 CONSISTENT | 41 CONSISTENT |
| B, 59 m | 9 INCONSISTENT (wrong pass) | 10 and 15 INCONSISTENT (wrong passes) |
| B, 101 m | 34 CONSISTENT / 4 | 32 CONSISTENT / 27 INCONCLUSIVE |
| C, 55 m / 94 m | 11 / 10 INCONCLUSIVE | 11 / 19 INCONCLUSIVE |
| D, 69 m | 99 CONSISTENT | 101 CONSISTENT |
| D, 118 m | 40 INCONCLUSIVE | 30 INCONCLUSIVE |

The PSF operator changes no verdict on A, C or D and moves B's marginal rows
by a few inliers in both directions; it produces **three** B4L wrong passes on
frame B (10, 11, 15 inliers, 28–77 px off) where the box run produced one.
Frame B at 70° incidence with a 46-px-wide strip is where the engine's false
acceptances live, at both operators. The wrong-pass tally for B4L across
REAL-DATA-07/08 is therefore stated as **1 / 23 (box) or 3 / 25 (PSF)**, and
the coarse-rung rule stands: no pass is reported without its geometry verdict.

**What this closes.** The recorded deviation is closed with a measurement,
and the measurement says the operator was not what limited the classical
engine at 100 m (B1 still starves: 13–189 keypoints) and not what made the
learned engine succeed (its consistent passes are within ±6 inliers of the box
run). R9 is the operator every future rung run uses because it is the honest
model of a coarse sensor, not because it changed a result here.
