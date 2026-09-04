# REAL-DATA-07 — Replication of the low-incidence result, and the illumination envelope of three engines on every archived frame over two ground windows

**Part 1 — pre-registration. FROZEN 2026-09-04, before any new frame's tile was
fetched and before EXP-007's tier-2 rungs had run.** Part 2 is empty until Part 1
is committed.

**Classification: RESEARCH-CRITICAL.** This stage pays the two debts a reviewer
would raise first: the replication REAL-DATA-05 could not perform (D-040-N1),
and a sample of six edges that cannot reach significance.

## 1. Why this stage exists

Every real-data conclusion rests on six edges over two windows. REAL-DATA-05
found two additional low-incidence frames over the RD-04 window and rejected
both under filter H5 because their tiles are rotated 180° relative to the
incumbents, and whether the matcher's orientation assignment survives that was
an open question. That question is now moot: the rotation between two frames is
**known from the archive corner columns** and can be removed before matching by
an exact quarter-turn permutation (`siim.ingest.orientation.north_up`). Nothing
is estimated, so no cause is entangled.

A census on 2026-09-04 (ODE, 0.04° box around each target, calibrated NAC)
found 18 frames over the RD-03 window and 14 over the RD-04 window. After
excluding the four incumbents, frames with incidence > 75° (D-029), one night
frame (149.9°) and one off-nadir frame (emission 6.5°), **14 new frames**
remain, spanning 18.0° to 74.7° incidence, all with emission ≤ 1.8°.

EXP-007 tier 1 (preliminary rows, same tiles as the recorded edges) showed the
licensable learned engine B4L (DISK + LightGlue) registering C → A at 38.85°
with 56 inliers and a transform CONSISTENT with archive geometry, where RootSIFT
gave 4. The engine's real envelope is unknown beyond that single edge.

## 2. The questions

**Q1 (replication).** Does a second, independently acquired low-incidence frame
succeed against A and fail against B, as D → A did?

**Q2 (envelope).** For each engine, what is the largest Δincidence at which the
success rate over all real edges is still ≥ 0.8, and where does it fall to 0?

**Q3 (significance).** With all edges, does the exact separation test reach
p ≤ 0.01 for the RootSIFT baseline, and what is p for each engine?

## 3. Frames, fixed in advance

Incumbents A, B, C, D as in EXP-007 Part 1 §3. New frames (ODE census):

| Window | PDS ID | Incidence | Emission | Resolution | Role |
|---|---|---|---|---|---|
| RD-04 | `nac.m124423514lc` | 18.00° | 1.69° | 0.49 m | **replication candidate E1** (decimation 4 so its tile matches the incumbents' ground sampling) |
| RD-04 | `nac.m1315225542lc` | 21.13° | 1.72° | 0.81 m | **replication candidate E2** |
| RD-04 | `nac.m1341069775rc` | 42.43° | 1.17° | 0.96 m | envelope |
| RD-03 | `nac.m1356349796lc` | 41.09° | 1.73° | 0.98 m | envelope (also covers RD-04) |
| RD-03 | `nac.m1182331886lc` | 43.74° | 1.76° | 1.20 m | envelope |
| RD-03 | `nac.m1236465772rc` | 44.44° | 1.18° | 1.13 m | envelope |
| RD-03 | `nac.m1212932972lc` | 45.48° | 1.77° | 1.08 m | envelope (also covers RD-04) |
| RD-03 | `nac.m1205872034rc` | 47.11° | 1.17° | 1.07 m | envelope |
| RD-03 | `nac.m1175268993rc` | 48.47° | 1.18° | 1.21 m | envelope |
| RD-03 | `nac.m1363396554rc` | 52.40° | 1.17° | 1.03 m | envelope (also covers RD-04) |
| RD-03 | `nac.m1199981485lc` | 66.72° | 1.74° | 1.07 m | envelope |
| RD-03 | `nac.m1199981485rc` | 66.88° | 1.17° | 1.07 m | envelope (same orbit as the previous; counted as one frame for independence) |
| RD-03 | `nac.m1096350825rc` | 72.29° | 1.19° | 1.30 m | envelope (also covers RD-04) |
| RD-03 | `nac.m1142297886lc` | 74.65° | 1.76° | 1.23 m | envelope, at the D-029 limit |

Tiles: 4096 lines × 2048 samples centred on each window's recorded target by the
same corner-map inversion as REAL-DATA-03/04, decimation 2 (4 for E1), fetched
by strict chunks. Overlap is verified by `verify_tile_overlap.py`
(`--require-confirmed`) before any registration; an edge whose overlap is not
CONFIRMED is excluded and listed.

Edges: every ordered pair of frames over the same window whose tile overlap is
CONFIRMED, one direction per unordered pair (the lower-incidence frame as
source), plus the six recorded edges as controls. Expected ≈ 60–90 edges per
window before overlap exclusion.

## 4. Method, fixed in advance

1. Each tile is rotated to north-up by `north_up` (a known quarter-turn from
   corner columns), then decimated, then percentile-stretched. The rotation is
   recorded and every reported transform is mapped back to original tile
   pixels.
2. Engines: `B1` RootSIFT (unmodified), `B4L` DISK + LightGlue (unmodified,
   4096 keypoints), and `B1` on north-up tiles versus `B1` on raw tiles for the
   recorded six edges only, to measure what the rotation alone changes.
3. LO-RANSAC affine, threshold 3.0 px, seed 0; failure rule `n_inliers <= 8`
   (D-023), unchanged.
4. Every pass is checked against archive geometry with the discrimination floor
   of `check_transform_against_geometry.py` (restated constants). A pass whose
   transform is INCONSISTENT is counted as a **wrong pass** and reported as
   such; it is never counted as success in Q2 or Q3.
5. Significance: `exact_separation_test` on Δincidence with outcome = pass and
   geometry ∈ {CONSISTENT, INCONCLUSIVE}, per engine, per window and pooled,
   with the pooled value labelled as pooled.

## 5. Hypotheses and criteria — FROZEN

**S4 (gate).** The six recorded edges reproduce their recorded inlier counts on
raw tiles under B1. If not, stop.

**H1 (replication).** E1 or E2 → A passes under B1 and the same frame → B
fails under B1, with the passing transform CONSISTENT with archive geometry.
> **S1 MET** if at least one of E1, E2 satisfies both. Prediction: MET for E2
> (21.13° vs A's 29.95°, Δ = 8.8°); E1 depends on the resolution-ratio handling.
> Confidence MEDIUM.

**H2 (envelope, B1).** B1's success rate falls below 0.8 between 12° and 39°
Δincidence and is 0 above 39°.
> **S2 MET** if the largest Δincidence bin (5° bins) with success rate ≥ 0.8 is
> below 39° and no bin above 39° exceeds 0.2. Prediction: MET. Confidence HIGH.

**H3 (envelope, B4L).** B4L's envelope extends beyond B1's by ≥ 15°.
> **S3 MET** if B4L's largest ≥ 0.8 bin exceeds B1's by ≥ 15°, counting only
> geometry-consistent passes. Prediction: MET. Confidence LOW-MEDIUM (one edge
> of evidence).

**H4 (significance).** With ≥ 30 edges, B1's separation reaches p ≤ 0.01.
> **S5 MET** if p ≤ 0.01 pooled and ≤ 0.05 in each window separately.
> Prediction: MET if the envelope is as sharp as H2 says. Confidence MEDIUM.

**H5 (rotation control, must hold).** North-up rotation does not change the
six recorded outcomes under B1.
> **S6 MET** if all six outcomes are unchanged. If S6 fails, every north-up
> result is reported with the caveat and EXP-004's question is reopened.

**Wrong-pass rate (reported, not a criterion).** For each engine, the fraction
of passes whose transform is INCONSISTENT with archive geometry. This is the
number the verdict engine's false-acceptance estimate will be built from.

## 6. What each outcome licenses

| Result | Claim |
|---|---|
| S1 MET | D-040-N1's replication debt is discharged; frame identity is refuted for A within the tested set. |
| S1 NOT MET | The low-incidence success does not replicate; D-040 is downgraded to "one succeeding pair". |
| S2, S5 MET | The illumination cliff of the uncorrected baseline is located to a 5° bin at p ≤ 0.01. |
| S3 MET | A licensable zero-shot learned engine is the fine-rung engine of the architecture; the physics layer is justified by scale, viewpoint and verification. |
| S3 NOT MET | B4L's single success was not representative. |
| S6 NOT MET | Orientation is a cause after all; EXP-004 is reinstated. |

## 7. Threats to validity

Frames from the same orbit (L/R pairs) are not independent; they are counted
once. Resolution ratios up to 1.5 enter (0.81–1.30 m); E1 at 0.49 m is handled
by decimation 4. Corner-map geolocation error (~150 m) is the same as in every
prior stage. The archive served 100 KB/s on the day of writing; acquisition
may take hours and is sequenced after EXP-007's downloads. No ground truth.

## 8. What this stage does NOT do

No new ground, no matcher tuning, no DEM rendering (EXP-007 owns that), no
Chandrayaan-2, no azimuth control, no sub-pixel claim.

---

## Part 2 — Results

*Empty until Part 1 is committed and the run has completed.*
