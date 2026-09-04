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

*Empty until Part 1 is committed and the run has completed.*
