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
| S1 MET | D-040-N1's replication debt is discharged; frame identity ceases to explain A's edges within the tested set. *(Wording corrected 2026-09-04 after commit f8a961c: the original sentence used the phrasing D-040-N1 withdrew; the criterion S1 is unchanged.)* |
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

**Runs.** Acquisition 2026-09-04 (census tiles: 12 over RD-03, 8 over RD-04;
four frames excluded because the target ground point is outside their swath,
including replication candidate **E1** `nac.m124423514lc`). Overlap verified
from geometry before any registration: **23 of 66** RD-03 pairs and **19 of 28**
RD-04 pairs CONFIRMED; the rest excluded and listed in the artefacts.
Registration: RD-03 2026-09-04 (36.9 min, `rows_rd03.json`); RD-04 2026-09-05
(15.5 min, `rows_rd04.json`; the 2026-09-04 run died with the machine at 22:16
after six rows, log preserved as `run_rd04_died_v1.log`); the raw reproduction
arm for RD-03 re-run in the recorded direction 2026-09-05 (`rows_rd03_repro.json`,
0.6 min). Evaluation: `scripts/run_real_data_07.py --evaluate` →
`experiments/REAL-DATA-07/real_data_07_results.json`, **188 rows, 42 registered
pairs × 2 engines**, Part 1 frozen at commit f8a961c. Environment as EXP-007.

**One implementation error, found by the gate and preserved (E-036).** The
first RD-03 run executed the raw reproduction arm in the stage's own
lower-to-higher incidence order, which for two of the six recorded edges is the
opposite of the recorded direction; those rows (C → B **5381** against a
recorded B → C 5365; A → C **8** against a recorded C → A 4) carry
`reproduces_recorded: false` and stay in `rows_rd03.json`. The runner was
corrected to run the recorded direction (commit 840af46) and the arm re-run.
The evaluation reads only rows flagged `recorded_direction`.

### S4 — reproduction: MET

All six recorded edges reproduce exactly in the recorded direction on raw
tiles: 5365, 4, 4 (RD-03) and 1656, 3, 7 (RD-04).

### S1 — replication of the low-incidence success: NOT MET

E1 never entered: the RD-04 target lies outside its swath (normalised sample
−0.04), so no tile could be cut on the shared ground point. E2
(`nac.m1315225542lc`, 21.13°, resolution 0.81 m) entered and **failed both
decisive edges**:

| edge | Δinc | B1 inliers / putative | geometry | B4L |
|---|---|---|---|---|
| E2 → A | 8.82° | **6** / 67 | INCONSISTENT (924 px) | 5 / 17, CONSISTENT (73 px) |
| E2 → B | 48.63° | 3 / 36 | INCONSISTENT | 0 |

E2 fails against **every** partner it was paired with: → `m1341069775rc`
(21.30°) 6, → `m1212932972lc` (24.35°) 5, and against D at **Δinc 2.91°** it
passes by two inliers (10 / 107, CONSISTENT at 36 px) while B4L gives 3. Its
tile decodes cleanly (9553 SIFT keypoints, the brightest DN median of the set at
1669, no clamping, overlap CONFIRMED with every partner). D-040-N1's replication
debt is **not discharged**; see the interpretation below for what E2 does to
the illumination claim.

### S6 — north-up changes no recorded outcome: NOT MET, by two inliers on one edge

| edge (window) | recorded, raw | north-up | outcome changed? |
|---|---|---|---|
| B → C (RD-03) | 5365 | 5392 | no |
| C → A (RD-03) | 4 | 6 | no |
| A → B (RD-03) | 4 | 3 | no |
| D → A (RD-04) | 1656 | 1608 | no |
| B → D (RD-04) | 3 | 4 | no |
| **A → B (RD-04)** | **7** (fail) | **9** (pass, CONSISTENT: 91 px / 103 px floor) | **yes** |

The exact quarter-turn moved one edge from 7 to 9 inliers across the cutoff of
8. By Part 1 §5 every north-up result below carries this caveat and EXP-004's
question is reopened — in the narrow sense the data supports: **the rotation
changes counts by −1 to +27 and moved one edge sitting one inlier below the
rule to one above it.** It did not turn a 1656 into a 4 or a 4 into a 1656.
This is the D-023 rule's known behaviour at its edge (false-alarm 0.369 in the
mixed regime, EXP-003), not evidence that orientation assignment governs
outcomes.

### S2 — B1 envelope: MET as worded, and the envelope is not a clean cliff

Success = pass under the rule **and** transform not INCONSISTENT with archive
geometry. B1, north-up, both windows pooled, 42 pairs, 5° bins of Δincidence:

| bin | 0–5 | 5–10 | 10–15 | 15–20 | 20–25 | 25–30 | 30–35 | 35–40 | 40–45 | 45–50 | 50–55 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| n | 7 | 4 | 3 | 3 | 9 | 7 | 2 | 3 | 1 | 1 | 2 |
| B1 success | 0.71 | 0.50 | 1.00 | 0.67 | 0.44 | 0.29 | 0.50 | 0.33 | 0 | 0 | 0 |
| B4L success | 0.43 | 0.50 | 1.00 | 0.67 | 0.44 | 0.29 | 0.50 | 0 | 0 | 0 | 0 |

The largest bin with success ≥ 0.8 is 10–15° (n = 3), below 39°, and every bin
above 40° is 0 — so S2's letter is MET. Its spirit — a rate near 1 at small Δ
that falls through 0.8 somewhere between 12° and 39° — is **not what the data
shows**: the rate is already 0.71 at 0–5° and 0.50 at 5–10°, because four
frames fail against every partner regardless of Δincidence (below). Per window:
RD-03 largest ≥ 0.8 bin 10°; RD-04 35° (n = 1 in that bin).

### S3 — B4L envelope exceeds B1's by ≥ 15°: NOT MET

Both engines' largest ≥ 0.8 bin is 10–15°. Pooled, B1 succeeds on **20 / 42**
pairs and B4L on **17 / 42**; B4L fails every pair B1 fails and three more
(the marginal B1 passes at 9–19 inliers: D → E2, `m1096350825rc →
m1142297886lc`, and A → B RD-04). Where both succeed at Δinc 12–34°, B4L's
yield is 5–25× B1's (1206 vs 47, 1561 vs 265, 1183 vs 144, 849 vs 68, 676 vs 28)
— a **within-envelope yield gain at this GSD, not an envelope extension**.

This bears directly on D-047. EXP-007's tier-1 evidence for the engine was one
edge, C → A, run raw in that direction with 56 inliers; here the same pair, run
A → C **north-up**, gives B4L **0** inliers (B1: 6). The tier-1 success is not
robust to direction and rotation. EXP-007's tier-2 evidence — three of four
~40° pairs at 7–30 m with 447–2042 consistent inliers — is unaffected by this
stage, which ran at ≈ 2 m only. D-047 is amended (D-047-N1): the learned engine
extends the envelope at the coarser rungs and raises yield inside it at native
scale; it does not extend the native-scale envelope on these tiles.

### S5 — significance: NOT MET as worded (pooled p = 0.0042; RD-04 p = 0.121)

`exact_separation_test` on Δincidence vs success, B1 north-up:

| set | n | successes | p | exact? |
|---|---|---|---|---|
| pooled | 42 | 20 | **0.0042** | no (Monte-Carlo above the exact limit) |
| RD-03 | 23 | 10 | **0.0040** | yes |
| RD-04 | 19 | 10 | 0.121 | yes |

Pooled and RD-03 clear the 0.01 and 0.05 bars; RD-04 does not clear 0.05, so
S5 is NOT MET by its per-window clause. The pooled value is the first
sub-0.01 significance this project has held for the Δincidence separation,
against 0.0667 on six edges; it is stated with its caveats: not perfectly
separated (the statistic is a rank sum), pairs sharing frames are not
independent, and B4L's pooled p is 0.016.

### Wrong-pass rate (reported): 0 of 37

No pass under the rule had a transform INCONSISTENT with archive geometry:
B1 0 / 20, B4L 0 / 17. Two B1 passes and two B4L passes are INCONCLUSIVE
(B → C at 150 px / 100 px, as at every prior stage; D → `m1212932972lc` at
99 px / 96 px). This is the number the verdict's false-acceptance estimate is
built from: on 37 passes at ≈ 2 m over two mare windows, zero were
geometry-inconsistent, with the geometry check resolving only to ~100 px.

### The finding the criteria did not anticipate: four frames fail against everyone

Per-frame B1 success (north-up), sorted by incidence:

| frame | inc | tile DN median | B1 successes | Δinc of its failures |
|---|---|---|---|---|
| D `m1299958135lc` | 18.22° | — | 5 / 7 | 52°, 54° |
| **E2 `m1315225542lc`** | 21.13° | 1669 | **1 / 5** | 9°, 21°, 24°, 49° |
| A `m1271742202lc` | 29.95° | — | 6 / 10 | 9°, 39°, 40°, 45° |
| `m1341069775rc` | 42.43° | 865 | 2 / 5 | 3°, 21°, 27° |
| `m1182331886lc` | 43.74° | — | 3 / 6 | 23°, 29°, 31° |
| `m1236465772rc` | 44.44° | — | 1 / 2 | 22° |
| `m1212932972lc` | 45.48° | — | 9 / 15 | 3°, 21°, 24°, 27°, 27°, 29° |
| `m1175268993rc` | 48.47° | — | 1 / 2 | 18° |
| `m1363396554rc` | 52.40° | — | 3 / 3 | — |
| **`m1199981485rc`** | 66.88° | 529 | **0 / 5** | 8°, 18°, 21°, 22°, 23° |
| C `m1452560468lc` | 68.80° | — | 2 / 3 | 39° |
| B `m1335207975rc` | 69.76° | — | 5 / 10 | 5°, 27°, 40°, 49°, 52° |
| **`m1096350825rc`** | 72.29° | 391 / 385 | **1 / 5** | 27°, 27°, 29°, 54° |
| **`m1142297886lc`** | 74.65° | 342 | **1 / 6** | 5°, 8°, 29°, 31°, 45° |

Every failure at Δincidence below 20° involves one of E2, `m1199981485rc`,
`m1096350825rc` or `m1142297886lc`; remove those four frames and the remaining
24 pairs separate on Δincidence with one exception (A → B RD-03 at 39.81°,
which fails as recorded, and the marginal passes at 24–34°). The three
high-incidence outliers are the three darkest tiles of the set (DN medians
342–529 against 865–1669 for the rest), sit at 66.9–74.7° — at or just below
the D-029 ceiling of 75°, which was recorded as *a provisional cut, unswept*
(RL-028b) — and one of them (`m1199981485rc`) had its window clamped 717
samples to the frame edge. E2 is the opposite case: the brightest tile, at
21°, failing against D at Δinc 2.9° by every measure except a 10-inlier pass.

What this licenses, stated carefully:

- **The six-edge result stands** (S4) and the pooled separation reaches
  p = 0.004, but **Δincidence alone does not predict the outcome across 14
  frames.** Something frame-level governs at least four of them. For the
  three dark frames the obvious candidate is absolute incidence (shadow
  fraction and dynamic range at > 66°), which D-029 named and never swept;
  for E2 no candidate is identified. **This is the frame-identity question of
  D-040-N1 returning with n = 4, not being discharged.**
- **No replication of the low-incidence success is held.** D → A at 11.73°
  remains the only low-Δ, low-incidence success on frame A.
- **Δincidence is necessary but not sufficient**: no pair above 40° passes
  under either engine (0 / 4), and the marginal passes at 24–34° (9–28 B1
  inliers) are where the rule's edge sits.

### What is claimed and what is not

- **Claimed:** 42 geometry-confirmed real pairs over two mare windows, 14
  frames, two engines, 0 wrong passes in 37; the pooled Δincidence separation
  p = 0.004 for B1 (0.016 for B4L); no success above 40° at ≈ 2 m; B4L's yield
  inside the envelope 5–25× B1's; north-up rotation moves counts by ≤ 27 and
  one marginal edge across the rule.
- **Claimed as a negative:** the replication did not occur; four frames fail
  against every partner irrespective of Δincidence; the learned engine's
  native-scale envelope equals the classical one on these tiles.
- **Not claimed:** any cause for the four outlier frames (not measured); any
  accuracy (no ground truth; 0 wrong passes is at a ~100 px floor); anything
  about azimuth, sub-pixel, or Chandrayaan-2.

### Consequences

- **D-049:** the illumination claim is re-scoped to *frames below ~66°
  incidence with unclamped tiles*, the D-029 ceiling becomes a stage of its own
  (sweep 60–75° with the frames this census already located), and E2 is
  investigated before any further replication attempt (tile placement,
  orientation signature, saturation).
- **D-047-N1:** the learned engine is admitted for coarser rungs and as a
  yield engine at native scale; the native-scale envelope claim is withdrawn.
- **S6 caveat** attaches to every north-up number above. EXP-004 stays
  pre-registered; what reopens is the narrow measurement of rotation
  sensitivity at the rule's edge, not the orientation-assignment programme.
- The 0 / 37 wrong-pass rate enters the verdict engine's documentation as its
  first measured false-acceptance bound on real data, with its floor stated.
