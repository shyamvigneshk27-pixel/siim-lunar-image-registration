# REAL-DATA-03 — The first correctly controlled real-data registration experiment

**Stage ID:** REAL-DATA-03
**Name:** Acquire a real LRO NAC pair at geometry-derived tile windows, verify overlap independently, run the unmodified baseline, and close a real three-image loop
**Status:** **COMPLETE — the experiment is valid. Two of three edges FAIL; one SUCCEEDS.**
**Date:** 2026-08-26 · **Depends on:** REAL-DATA-02 (`REAL-DATA-02_overlap_verification.md`), REAL-DATA-01 · **Runs beside:** EXP-004 (still not started), DEMO_TRACK
**Classification:** RESEARCH-RELEVANT. The overlap gate was passed **before** any registration was interpreted, in code.

> **Standing under integrity rules 8 and 10 is unchanged.** No multi-modal claim.
> No Chandrayaan-2 data was obtained or simulated. **No Sun-azimuth claim** — azimuth
> was not used. Nothing here is compared against synthetic ground truth, and no
> ground truth exists for these products.

---

## 1. Objective

Obtain the project's **first scientifically interpretable real-data registration
experiment**: a real LRO NAC pair whose overlap is established independently of the
matcher, given to the **unmodified** baseline, with the outcome — success or failure —
accepted as a valid result.

This stage is **not** a search for a successful registration. It is a search for a
correctly controlled one.

## 2. Scientific question

REAL-DATA-02 closed the overlap question and left one narrower one open (RL-031b):

> With shared ground independently confirmed, does the unmodified baseline register two
> real LRO NAC frames taken under different illumination — and if not, what does the
> evidence actually eliminate?

## 3. Relationship to REAL-DATA-01 and REAL-DATA-02

| Stage | What it established | What it could not say |
|---|---|---|
| **REAL-DATA-01** | Ingestion, decoding and sanity all work; the pipeline is sound on real NAC (self-registration to 1.14e-12, a known +40/+25 px shift recovered to 0.14 px) | Whether its tiles overlapped. Its 3-inlier headline was uninterpretable |
| **REAL-DATA-02** | Those headline tiles were **22.75 km apart**, sharing 0.0000 km². Two acquisition defects found: a per-frame line direction forced global (E-028) and an unmatched cross-track window (E-029). Corrected windows computed and **projected** to 97.12 % | Whether tiles cut at those windows would actually overlap, or register |
| **REAL-DATA-03** *(this)* | Cut them, **measured** 97.12 %, and ran the unmodified baseline on a valid pair. Added a third product and closed a real loop | Why the illumination-different edges fail beyond eliminating the alternatives (§17) |

**Nothing from either earlier stage was rewritten.** REAL-DATA-01's artefacts, manifests
and tiles are untouched; REAL-DATA-02's `overlap_verification.json` re-runs and reproduces every classification and every number unchanged (the file itself differs only in its `generated_utc` stamp).

## 4. Acquisition

Geometry-driven, via a new `--from-geometry` mode on `scripts/acquire_real_pair.py`
(D-033). Every tile is centred on **one ground point**, derived by inverting a bilinear
ground map built from the archive index table's **named** frame corners. The line
direction is read per frame from the archive, never assumed — the defect that produced
REAL-DATA-01's disjoint pair.

**Target ground point:** lon **22.033852**, lat **20.035253** — the centroid of the
intersection of A's and B's full footprints, carried over unchanged from REAL-DATA-02 so
that the loop's A→B edge *is* the primary pair rather than a second cut of it.

| Role | pdsid | UTC start | incidence | emission | `Map_resolution` | flight dir | node |
|---|---|---|---|---|---|---|---|
| **A** | `nac.m1271742202lc` | 2018-01-28T01:28:54.845Z | **29.95°** | 1.74° | 0.933 m | −X | A |
| **B** | `nac.m1335207975rc` | 2020-02-01T14:51:48.224Z | **69.76°** | 1.17° | 0.918 m | −X | A |
| **C** | `nac.m1452560468lc` | 2023-10-21T20:46:41.301Z | **68.80°** | 1.72° | 0.855 m | −X | A |

Δincidence across the triplet **39.81°**; resolution ratio **1.0912**.

**Provenance.** Byte ranges over HTTP 206 with the returned length and `Content-Range`
verified; SHA-256 of the bytes actually received; label validated (`file_size` identity
exact) before use; the index table's `IMAGE_LINES`/`LINE_SAMPLES` checked against the
PDS4 label for every product.

| Product | byte range | SHA-256 |
|---|---|---|
| A | 181853304 + 41484288 | `de96b5e885dc9871b4df8ad4168b38ee25c4ec1a5bc80dde690eda932d73f3c3` |
| B | 302042280 + 41484288 | `9df3e88129c1a438695ef65a63bdcd1869b71d2205eb86a7bd4ea029864c6657` |
| C | 92048328 + 41484288 | `2eaa0639322be4de7ec104becb179ecfa50686efd68e36ab71c956d0300538c1` |

Source: `https://pds.lroc.im-ldi.com/data/LRO-L-LROC-3-CDR-V1.0/{LROLRC_1034, LROLRC_1042B,
LROLRC_1057B}/DATA/{ESM3/2018028, ESM4/2020032, ESM5/2023294}/NAC/`.
**Licence:** NASA PDS public domain. Credit **NASA/GSFC/Arizona State University**.

**Nothing was overwritten.** New manifests (`real_pair_usable_geo_manifest.json`,
`real_third_c_geo_manifest.json`, `real_triplet_geo_manifest.json`), new tile files named
`{pdsid}.geo.l{line0}s{sample0}.tile.npy`, and an explicit refusal to write over an
existing tile — which fired once during this stage and is recorded in §12.

## 5. Exact tile windows

All tiles 4096 lines × 2048 samples ≈ 3.8 × 1.8 km, decimated 2× before matching.

| | `line0` | lines | `sample0` | samples | target pixel (line, sample) | clamped? |
|---|---|---|---|---|---|---|
| **A** | **17955** | 4096 | **1811** | 2048 | (20003, 2835) | no |
| **B** | **29822** | 4096 | **1227** | 2048 | (31869, 2250) | no |
| **C** | **9088** | 4096 | **717** | 2048 | (11136, 1741) | no |

`[MEASURED]` A and B reproduce REAL-DATA-02's projected windows **exactly** (17955/1811
and 29822/1227), by an independent code path that inverts the ground map rather than
re-reading the projection.

## 6. Independent overlap verification

Run **before** any registration was interpreted, by
`scripts/verify_tile_overlap.py --require-confirmed`, which exits non-zero unless every
edge is `OVERLAP_CONFIRMED`. Method, criteria and uncertainty are REAL-DATA-02's,
**unchanged**: named archive corners, corner naming taken from each product's own PDS4
`disp:Display_Direction`, bilinear ground map, one common local plane, exact convex clip,
and 4000 Monte Carlo draws (seed 20260826) over the ±0.005° corner quantisation.
CONFIRMED requires p5 of the worse-covered tile's shared fraction ≥ 0.50.

`[MEASURED]` `experiments/REAL-DATA-03/overlap_usable_geo.json`, `overlap_triplet.json`.

| edge | area A | area B | **∩** | IoU | of A | of B | **min** | p5–p95 | centres apart | class |
|---|---|---|---|---|---|---|---|---|---|---|
| **A ↔ B** | 7.238 | 7.043 | **7.0297** | **0.9695** | 97.12 % | 99.81 % | **97.12 %** | 90.03–97.31 % | **1 m** | **CONFIRMED** |
| **A ↔ C** | 7.238 | 5.987 | **5.9868** | 0.8272 | 82.72 % | 100.00 % | **82.72 %** | 78.57–86.38 % | 0 m | **CONFIRMED** |
| **B ↔ C** | 7.043 | 5.987 | **5.9868** | 0.8500 | 85.00 % | 100.00 % | **85.00 %** | 80.62–88.60 % | 1 m | **CONFIRMED** |

Areas in km². **All three edges CONFIRMED**, and the A↔B pessimistic bound (0.900) sits
**above** the 0.757 worst case of the synthetic regime in which this project's matcher was
measured. The gate passed; the stage was allowed to proceed.

`[INTERPRETATION]` The measurement (97.12 %) and REAL-DATA-02's projection (97.12 %) agree
because both use the same ground map — that is *self-consistency*, not independent
corroboration, and it is reported as such. What it does establish independently is that
the tiles now on disk cover the ground the windows were designed to cover.

## 7. Image sanity

`scripts/check_real_tiles.py`, unchanged in substance (two defects fixed, §12–13).
`[MEASURED]` `experiments/REAL-DATA-03/tile_sanity_real_triplet_geo.json`.

| | shape | dtype | finite | DN p1 / med / p99 | min / max | unique | lag-1 autocorr | byte-swapped | zero frac | SHA vs manifest | **verdict** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **A** | 4096×2048 | float64 (from `<i2`) | 1.0000 | 1280 / **1376** / 1814 | 537 / 3588 | 2052 | **0.9655** | 0.6114 | 0.0 | ✓ | **PASS** |
| **B** | 4096×2048 | float64 (from `<i2`) | 1.0000 | 311 / **469** / 734 | −15 / 2328 | 1733 | **0.9314** | 0.6648 | 7.2e-07 | ✓ | **PASS** |
| **C** | 4096×2048 | float64 (from `<i2`) | 1.0000 | 316 / **495** / 772 | −482 / 2397 | 1951 | **0.9004** | 0.5711 | 4.3e-06 | ✓ | **PASS** |

**All three pass.** No tile was discarded. Sentinels (`-32768` and neighbours) are masked
by the decoder and none survives — `finite_fraction` is exactly 1.0000 for all three, so
no `NaN` entered any statistic. Every decode-correctness margin is large (0.28–0.35
against the 0.10 `DECODE_EVIDENCE_MARGIN` of E-024), so none is `inconclusive`.

The negative `min` values for B and C are legitimate: `valid_minimum` is −32752 and only
the sentinel constants are masked, so a genuinely dark shadowed pixel stays negative
(E-003 — on the Moon, near-zero is a real value).

## 8. Baseline configuration

**Nothing was changed.** `run_rootsift_baseline` (B1) as built, with the parameters
`register_real_pair.py` has used since REAL-DATA-01:

| | |
|---|---|
| detector / descriptor | SIFT + RootSIFT, unmodified |
| matching | mutual nearest neighbour, ratio **0.8** |
| robust estimation | LO-RANSAC, threshold **3.0 px**, seed **0** |
| model | **affine** |
| decimation | **2×** (`nanmean` over 2×2 blocks) |
| preprocessing | 1–99 percentile stretch per image, identical rule for every tile |
| failure rule | `n_inliers <= 8` (D-023), **applied, not validated on real data** |

The threshold, ratio, model, decimation and preprocessing are restated as constants in
`register_real_triplet.py` so that a future edit to one script cannot silently make the
two experiments incomparable.

## 9. Registration results

`[MEASURED]` `experiments/REAL-DATA-03/registration_usable_geo.json`,
`loop_closure_triplet.json`. Tiles decimated to 2048×1024.

| edge | Δinc | keypoints | putative | **inliers** | ratio | fit RMSE (px) | coverage gap | occupancy | `n_inliers<=8` |
|---|---|---|---|---|---|---|---|---|---|
| **A → B** | 39.81° | 9538 / 12420 | 32 | **4** | 0.1250 | **4.138e-13** | 0.4767 | 0.047 | **FAIL** |
| **B → C** | **0.96°** | 12420 / 11477 | **5392** | **5365** | **0.9950** | **0.5829** | **0.1076** | **0.875** | **pass** |
| **C → A** | 38.85° | 11477 / 9538 | 49 | **4** | 0.0816 | 0.8851 | 0.4406 | 0.047 | **FAIL** |

The standalone primary-pair run (`registration_usable_geo.json`) reproduces the A→B edge
**exactly** — 32 putative, 4 inliers, fit RMSE 4.1382633578908315e-13 — as it must at
seed 0.

**Estimated linear parts**, as singular values and rotation:

| edge | σ₁ | σ₂ | rotation |
|---|---|---|---|
| A → B | **2.0627** | **0.4676** | 166.6° |
| B → C | 1.0785 | 1.0670 | −1.73° |
| C → A | **0.5910** | **0.3472** | −30.5° |

### 9.1 The headline: a valid pair, and the baseline fails on it

**A → B is the experiment this stage was built to run.** 97.12 % of tile A is ground it
shares with tile B, established without the matcher, and the unmodified baseline returns
**4 inliers out of 9538 and 12420 keypoints**, verdict **REJECTED**, class **C**.

`[INTERPRETATION]` **A failure is a valid result, and this is one.** It is the first real
registration failure this project can interpret at all, because it is the first whose
inputs are known to be registrable in principle.

### 9.2 E-008 demonstrated on a valid real pair, with an independent measure of the error

A → B reports a fit RMSE of **4.138e-13 px** — a quarter of a picometre — for a transform
that stretches by 2.06× along one axis and squashes by 0.47× along the other, and rotates
166.6°, between two frames of the same ground at a true resolution ratio of 1.016.

§9.4 puts a number on how wrong: **1614 px median**, against an independent bound whose
own resolution is 91 px.

### 9.3 The within-loop positive control

**B → C succeeds by a wide margin**: 5392 putative matches, **5365 inliers**, inlier ratio
**0.9950**, fit RMSE 0.583 px, coverage gap 0.108 with occupancy 0.875 — correspondences
spread across the whole overlap rather than clustered.

This edge is the stage's most valuable control, and it was **not selected for that
purpose**. C was chosen on a criterion fixed in advance — *minimise the maximum resolution
ratio against A and B* — because scale mismatch is an axis on which this project has
measured a failure (EXP-001: mare fails at 2×). C won that criterion outright (1.091
against 1.179 for the next candidate). Its near-match in incidence with B is a
consequence, not the reason.

### 9.4 The estimated transforms against archive geometry

`[MEASURED]` `experiments/REAL-DATA-03/transform_vs_geometry.json`. A new check
(`scripts/check_transform_against_geometry.py`) predicts where each pixel of one tile
lands in another **from archive corner geometry alone** — it reads no image data and uses
no matcher output — then measures the endpoint disagreement against the estimated
transform over the tile grid, with the corner quantisation propagated by Monte Carlo.

**It is a bound, not a ground truth.** Corner coordinates are quoted to 0.01° ≈ 150 m
≈ 165 full-frame px, so it discriminates at the scale of hundreds of pixels and certifies
nothing finer.

| edge | median disagreement | p5–p95 | discrimination floor | excess | verdict |
|---|---|---|---|---|---|
| **A → B** | **1614.1 px** | 1610–1625 | 91.2 px | **17.7×** | **INCONSISTENT** |
| **B → C** | **161.9 px** | 98–230 | 104.6 px | **1.55×** | **INCONCLUSIVE** |
| **C → A** | **583.5 px** | 541–645 | 104.1 px | **5.6×** | **INCONSISTENT** |

A second, sharper test uses a different archive field. A transform mapping A's pixels onto
B's must scale by the ratio of their ground samplings, and `SCALED_PIXEL_WIDTH` /
`SCALED_PIXEL_HEIGHT` are derived by the archive from SPICE — **the matcher never saw
them, and they do not feed the corner polygon either**:

| edge | predicted scales | estimated singular values | relative error | tolerance | agrees |
|---|---|---|---|---|---|
| A → B | 1.01053 / 1.02273 | 0.46759 / 2.06267 | **53.7 % / 101.7 %** | 1.70 % | **no** |
| **B → C** | **1.06742 / 1.07317** | **1.06699 / 1.07851** | **0.04 % / 0.50 %** | 1.83 % | **yes** |
| C → A | 0.91111 / 0.92708 | 0.34718 / 0.59103 | **61.9 % / 36.3 %** | 1.83 % | **no** |

`[INTERPRETATION]` The B → C registration recovers a scale that an independent SPICE-derived
archive field predicts to **0.04 %** and **0.50 %**, inside that field's own 1.83 %
quantisation. The two failing edges miss by 36–102 %. This is the sharpest independent
evidence in the stage, and it is the reason B → C's `INCONCLUSIVE` verdict on the coarser
corner-polygon bound should be read as *the bound is too blunt*, not as doubt about the
edge: the polygon route's own predicted anisotropy (1.065) disagrees with `SCALED_PIXEL`
(1.005) more than the estimate does.

## 10. Third-image acquisition

**One** additional product. Screening cost one ODE metadata query; the chosen product cost
one 31 KB index label, 17 range requests of 901 bytes, and one 41.5 MB tile.

**Screening.** 60 CDR products intersecting a box around the target; 13 carried a usable
four-vertex footprint; **8 frames contain the target ground point with a full
4096×2048 tile inside**, two of which are A and B. Screening used the ODE ring with the
vertex order REAL-DATA-02 decoded (UR, LR, LL, UL) — an inference from four products, used
**only** to rank candidates, never to make a claim.

**Selection criteria, fixed before choosing:**

1. incidence ≤ 75° (D-029) — hard;
2. a full tile centred on the target must fit inside the frame — hard;
3. **minimise the maximum resolution ratio against A and B** — the deciding criterion;
4. tie-break: prefer a triplet containing at least one low-Δincidence edge, so the loop
   carries its own positive control.

| candidate | incidence | `Map_resolution` | ratio vs A | ratio vs B | **max** |
|---|---|---|---|---|---|
| **`nac.m1452560468lc`** | 68.80° | 0.855 | 1.091 | 1.074 | **1.091** |
| `nac.m1212932972lc` | 45.48° | 1.082 | 1.160 | 1.179 | 1.179 |
| `nac.m1182331886lc` | 43.74° | 1.197 | 1.283 | 1.304 | 1.304 |
| `nac.m1142297886lc` | 74.65° | 1.226 | 1.314 | 1.336 | 1.336 |
| `nac.m1096350825rc` | 72.29° | 1.302 | 1.395 | 1.418 | 1.418 |

Criterion 3 decided it outright. **The choice was made on resolution, not on
illumination**, and criterion 4 was never reached.

**Confirmation, not inference.** The chosen product's geometry was then fetched from the
authoritative named index columns: UL (19.70, 22.05), UR (19.72, 21.91), LL (21.24,
22.20), LR (21.26, 22.06), `LRO_FLIGHT_DIRECTION` **−X**, `ORBIT_NODE` **A**, 52224×5064,
`SCALED_PIXEL` 0.82 × 0.89 m.

`[MEASURED]` C's line 0 sits at **minimum** latitude with flight direction **−X** — a
**fifth independent instance** of REAL-DATA-02's rule (−X → line 0 at min latitude,
+X → max), on a product from a different volume and a different mission phase, five years
after the frames that established it (E-028).

## 11. Real loop closure

`[MEASURED]` `experiments/REAL-DATA-03/loop_closure_triplet.json`,
`loop_closure_triplet.png`.

**This is the first time loop closure — the project's only GT-free estimator that detects a
coherent wrong answer (EXP-002: detection 1.000, false alarm 0.000 at loop level) — has met
real data.** D-011 was accepted on mathematics and validated on constructed transforms and
synthetic pipeline edges; it had never seen a real overlapping triplet, because one had
never been acquired.

**Every edge was estimated independently, from its own image pair.** The closing edge was
never derived as `(T_BC ∘ T_AB)⁻¹`. That derivation is **E-021** — it manufactures an
exactly-zero residual for an arbitrarily wrong solution, and it was once reported as
VERIFIED / high confidence on a registration 64 px wrong. Here the independence is
**asserted in code**: `_assert_independent()` refuses to report a loop unless the three
edges carry three distinct sets of match statistics, which three separate estimations on
three different image pairs necessarily do and an algebraic closure necessarily does not.

```
edges with a transform: 3 / 3
LOOP CLOSURE RESIDUAL: 1201.04 px   (median over a 2048 x 1024 grid)
```

Verdict, evaluated on the **weakest** edge (A → B, 4 inliers): **REJECTED / none**, with
three reasons — too few correspondences, loop closure failing at 1201.04 px, and clustered
correspondences. **Classification C.**

`[INTERPRETATION]` What this does and does not establish:

- **It does establish that loop closure runs on real data and did not manufacture a small
  residual.** ADR-0011's reversal condition — *"real-data evidence that per-edge errors are
  correlated in a way that cancels around a loop"* — is **not** triggered. Two edges are
  independently confirmed catastrophically wrong (§9.4) and the loop reported 1201 px
  rather than closing.
- **It does not test loop closure's discriminating power on real data.** A loop containing
  two garbage edges is not a test of the estimator; it is a test that the estimator does not
  lie when handed garbage. Measuring its power needs **three successful edges**, which needs
  a fourth product (§20).
- **The 1201 px figure is not an accuracy for anything.** It is the residual of a cycle two
  of whose legs are meaningless.

## 12. Errors encountered

Each uses **Problem → Evidence → Root Cause → Fix → Verification → Lesson**, with exactly
one of the five classes. Both are defects in **existing** code that this stage's data
exposed; neither reached a reported result.

---

### E-030 — The raw-tile byte cache was keyed by product, not by window
**Class: Implementation bug.** Severity **HIGH** (it silently corrupts decode evidence).

**Problem.** `check_real_tiles.py` cached a tile's raw bytes as `{pdsid}.tile.raw`. Running
it on the REAL-DATA-03 tiles found the REAL-DATA-01 bytes for the same products and computed
the byte-order and alignment evidence from a window **22.75 km away** from the tile under
test.

**Evidence.** The failed run is preserved at
`experiments/REAL-DATA/tile_sanity_usable_geo_preE030.json` (and its two figures). It
reports SHA-256 `56236a0fe23f3484` — REAL-DATA-01's H1 tile at line 30126 — for a tile whose
manifest records `de96b5e885dc9871` at line 17955, and it computed the decode evidence as
**0.9612** where the correct bytes give **0.9655**.

**Root cause.** An artefact name that omits a varying parameter. **This is E-025 recurring
in a second script**: E-025 was `{pdsid}.tile.npy` losing the line offset, and its stated
lesson was *"encode every varying parameter in the artefact's name"*. The `.raw` sidecar in
a different file was never audited against that lesson.

**A second defect on top of it.** The mismatch *was* caught by the SHA check — and reported
as **"the range fetch is not reproducible"**, which is false and sends the reader to debug a
correct fetch. That is E-024's lesson (a verdict must name the right cause) in a new place.

**Fix.** The sidecar is now `{pdsid}.l{line0}s{sample0}n{n_lines}.tile.raw`. Every cache hit
is hash-verified against the manifest **before** use; a mismatch is not an error but the
wrong cache entry, so it is discarded with a printed note and the bytes are re-fetched. The
pre-E-030 name is still *readable* — REAL-DATA-01 wrote 166 MB of sidecars — but only when
its hash proves it holds the right bytes, never because of its name. A fetch refuses to
overwrite an existing sidecar. The failure message now states that reaching it means the
**archive** returned different bytes, not that the cache is stale.

**Verification.** Six tests in `tests/test_real_tile_cache.py`, driving the cache through an
in-memory reader with no network: the two-window name separation, a hash-verified hit, the
exact E-030 scenario (stale legacy file must be discarded *and* the re-fetch must happen),
a legacy hit honoured on its hash, the overwrite refusal, and a manifest/label range
disagreement. The re-run passes all three tiles with the correct bytes.

**Lesson.** **A lesson recorded in the ledger only protects the file it was learned in.**
E-025's fix was applied to the acquisition script and its rule was written down; the same
rule was violated in the sanity script one directory away, and nothing checked. When a
failure mode is named in the ledger, **grep for its shape across the repository**, not just
the line that caused it.

---

### E-031 — A diagnostic figure crashed and took a set of passing checks with it
**Class: Implementation bug.** Severity **MEDIUM**.

**Problem.** `check_real_tiles.py` laid its figures out as `plt.subplots(2, 3)` — two rows,
because it had only ever been run on pairs. On the three-tile loop manifest it raised
`IndexError: index 2 is out of bounds for axis 0 with size 2`. The crash came **after** all
three sanity checks had run and passed, and **before** the JSON report was written, so a
completed measurement was lost to a plotting bug.

**Evidence.** The traceback, with `PASSED: True` printed for all three tiles immediately
above it.

**Root cause.** Two independent things: a hard-coded row count, and an ordering in which the
measurement was persisted after the presentation.

**Fix.** The grid is sized from the number of tiles (`squeeze=False`), and **the report is
written before any figure is drawn**. The side-by-side figure's caption now reflects whether
the windows were geometry-driven rather than always claiming the footprint-latitude
approximation.

**Verification.** The triplet run writes `tile_sanity_real_triplet_geo.json` with all three
tiles passing, then both figures.

**Lesson.** **Persist the measurement before rendering it.** A figure is a convenience; a
measurement is the result. Any ordering in which a presentation failure can destroy a
completed measurement is wrong regardless of how unlikely the failure looks.

---

### Failures that were the guards working, recorded rather than tidied away

```
# 1. Acquiring the triplet in one pass, with A re-listed for provenance:
data\processed\mare_serenitatis\nac.m1271742202lc.geo.l17955s1811.tile.npy already
exists; refusing to overwrite an acquired tile (integrity rule 4, E-025)
#    -> correct. The tile was already on disk from the pair acquisition. Resolved by
#       acquiring C alone at the pair's target point, which is also the minimal
#       acquisition, and composing the triplet manifest from the two (Section 4).

# 2. scripts/acquire_real_pair.py --products <one id>
"--products needs at least two product ids"
#    -> a real limitation of the new code, not of the data. Relaxed: one product is
#       legitimate when --target-lonlat is supplied, which is exactly how a third
#       image is cut on a point an existing pair already shares.

# 3. Transform(np.asarray(mat, float))
TypeError: Transform.__init__() missing 1 required positional argument: 'model'
#    -> an API mistake in new code, fixed by passing the model. Recorded because
#       REAL-DATA-01 logged its two AttributeErrors from guessing an API, and the
#       habit is worth keeping.
```

**A design defect caught in its own new code, before it produced a claim.** The first
version of `check_transform_against_geometry.py` compared a point estimate against a p95
floor with a bare `>`, and labelled B → C **INCONSISTENT** at 1.55× the floor — while the
disagreement's own p5–p95 (98–230 px) straddled that floor. That is E-024 exactly. The
verdict is now three-valued with a stated margin (`INCONSISTENT_MARGIN = 3.0`, a
**provisional cut, not a measured threshold**), and `INCONCLUSIVE` is reported as a result.

## 13. Fixes

| What | Where | Status |
|---|---|---|
| Cache keyed by window, hash-verified, correct failure attribution (E-030) | `scripts/check_real_tiles.py` | **FIXED**, 6 tests |
| Figure grid sized from tile count; report written before figures (E-031) | `scripts/check_real_tiles.py` | **FIXED** |
| Geometry-driven per-frame tile windows on both axes (D-033, E-028, E-029) | `scripts/acquire_real_pair.py` `--from-geometry` | **IMPLEMENTED**; the old path retained unchanged so REAL-DATA-01 stays reproducible |
| Three-valued verdict with a stated margin | `scripts/check_transform_against_geometry.py` | **FIXED** before any result was reported |
| Overlap gate that exits non-zero | `scripts/verify_tile_overlap.py --require-confirmed` | **ADDED** |
| Edge-independence assertion for loop closure (E-021) | `scripts/register_real_triplet.py` | **ADDED** |

**Nothing in the matcher, RANSAC, descriptors, thresholds or preprocessing was touched.**

## 14. Tests

**357 passed, 2 skipped → 376 passed, 2 skipped.** +19:

| File | Added | Covers |
|---|---|---|
| `tests/test_real_tile_cache.py` | **6** (new file) | E-030: window-keyed cache, hash-verified hits, stale-entry discard, legacy honour, overwrite refusal, range disagreement |
| `tests/test_ingest_footprint.py` | **+13** | `TileWindow` frame↔tile round trip, the `(k−1)/2` decimation centre, shape after decimation; `predicted_correspondences` identity, known shift, `(x, y)` order, decimation scaling, a known 2× sampling ratio, out-of-frame drop, grid validation, and that the signature admits no image data |

No unrelated test was modified.

## 15. Interpretation

`[INTERPRETATION]` Kept separate from the measurements above.

**1. The experiment is valid, and that is the deliverable.** For the first time this project
gave its matcher two real lunar images that are *known*, independently of the matcher, to
show the same ground — 97.12 % of one tile — and the result, whatever it was, would have
meant something. It happens to be a failure.

**2. Three edges, one variable, and a within-loop control.** All three tiles are the same
patch of mare, same instrument, same decoder, same preprocessing, same 2× decimation, same
affine model, same RANSAC threshold and seed, all near-nadir (emission 1.17–1.74°), all with
CONFIRMED overlap ≥ 82.7 %, all passing sanity. One edge finds 5365 inliers; two find 4.

**3. What the evidence actually eliminates.** Each of these is eliminated by a measurement,
not by argument:

| Candidate cause of the A→B and C→A failures | Status | Because |
|---|---|---|
| **Tiles do not overlap** | **ELIMINATED** | 97.12 % and 82.72 %, confirmed without the matcher (§6) |
| **Mare texture poverty** (D-026) | **ELIMINATED as sufficient** | B → C found 5392 putative and 5365 inliers on **the same ground** |
| **2× decimation** | **ELIMINATED** | Identical decimation on the succeeding edge |
| **Resolution mismatch** | **ELIMINATED** | A↔B has the *smallest* ratio in the triplet (1.016) and fails; B↔C has 1.074 and succeeds |
| **Relief displacement / parallax** | **ELIMINATED as sufficient** | The succeeding edge spans the *largest* emission difference (1.17°→1.72°); the failing C→A spans the smallest (1.72°→1.74°) |
| **Residual geometric uncertainty in the windows** | **ELIMINATED** | The succeeding edge has *less* confirmed overlap (85.0 %) than the failing A↔B (97.1 %) |
| **Registration model limitation (affine)** | **ELIMINATED as sufficient** | Same model on all three edges |
| **A defect in the pipeline** | **ELIMINATED** | B → C is a successful *cross-frame* registration — a stronger control than REAL-DATA-01's self-registration |
| **Something intrinsically wrong with tile A** | **NOT eliminated** | See §17 |
| **Illumination difference** | **THE ONLY SURVIVING ENUMERATED CANDIDATE** | It is the one variable that tracks the outcome: Δincidence 0.96° → success, 38.85° and 39.81° → failure |

**4. And yet illumination cannot be named as the cause.** In a three-frame design,
"large Δincidence" and "the pairing involves frame A" are **perfectly confounded**: A is the
only low-incidence frame and it is in both failing edges. Nothing here separates them.
Further, Δ*incidence* is itself confounded with Δ*azimuth*, which was **not measured**
(RL-032b) — two frames at nearly the same incidence are plausibly at nearly the same azimuth
too. So the honest statement is:

> **Illumination difference is the only enumerated candidate the evidence has not
> eliminated. It is not established as the cause, and this stage's design cannot establish
> it.** Resolving the confound needs a fourth frame (§20).

**5. E-008 has its cleanest instance yet.** A → B: fit RMSE **4.138e-13 px**, independently
measured error **1614 px**. Not on synthetic terrain, not on tiles that turned out to be
disjoint — on a pair with 97 % confirmed shared ground. The residual is smallest precisely
where the solution collapsed to the affine minimal set.

**6. A successful real registration exists, and it is class B, not class A.** B → C recovers
a scale matching a SPICE-derived archive field to 0.04 % / 0.50 %, with 5365 inliers spread
across 87.5 % of the grid. That is strong. It is still **not verified**: there is no ground
truth, and loop closure cannot corroborate it because the other two legs of the only
available loop are broken. Calling it a verified registration would be exactly the
over-claim this project exists to avoid.

## 16. What is established

1. **A geometry-driven acquisition produces tiles that overlap as designed** — 97.12 %
   measured against 97.12 % projected, cut by an independent code path.
2. **D-033 is implemented and works.** The line direction read per frame from the archive
   put A and B on the same ground to within **1 metre** of tile-centre separation.
3. **The unmodified baseline fails on a valid real illumination-different NAC pair**:
   4 inliers of 9538/12420 keypoints, REJECTED, class C.
4. **The unmodified baseline succeeds on a valid real illumination-*similar* NAC pair**:
   5365 inliers, ratio 0.9950, coverage occupancy 0.875 — and its recovered scale matches an
   independent archive field to 0.04 %.
5. **Loop closure has met real data**, with three independently estimated edges, and did not
   manufacture a small residual.
6. **Seven candidate causes of the failure are eliminated by measurement** (§15.3).
7. **A fifth independent confirmation of the E-028 flight-direction rule**, on a product from
   a different volume and mission phase.

## 17. What remains unknown

1. **Whether illumination is the cause.** It is the only surviving candidate, and it is
   confounded with frame identity in a three-frame design. **Evidence insufficient.**
2. **Δazimuth for any real pair.** `SUB_SOLAR_AZIMUTH` exists in the index table and was
   **not used**; its "relative to the RDR products" frame is unverified (RL-032b). These pairs
   are illumination-varied by **incidence only** and are **not azimuth-controlled**.
3. **Where the real cliff is.** Two points — 0.96° works, ~39° does not — bracket it across
   38 degrees of incidence. EXP-003's synthetic Δaz 21–27° cliff is **not** confirmed by
   this: it is a different axis.
4. **Whether the B → C registration is correct.** Strongly corroborated, never verified. No
   ground truth exists, and the only available loop has two broken legs.
5. **Loop closure's discriminating power on real data.** Needs three successful edges.
6. **`n_inliers <= 8` on real data.** It flagged the two failing edges and passed the
   succeeding one — 3 for 3 — but three edges validate nothing and the rule is still
   **applied, not validated**.
7. **Whether anything is intrinsically wrong with tile A.** Its keypoints (9538) and its
   REAL-DATA-01 self-registration argue against it, but the confound stands.
8. **Generalisation.** One region, one terrain type, one instrument, three frames.

## 18. Evidence debt

| Debt | Owner | Note |
|---|---|---|
| Break the Δincidence / frame-identity confound | **REAL-DATA-04** | needs a **fourth** frame at low incidence: if D↔A succeeds and D↔B fails, Δincidence is the driver |
| Loop closure's power on real data | REAL-DATA-04 | needs three mutually low-Δinc frames, i.e. a second triplet |
| Verify the frame of `SUB_SOLAR_AZIMUTH` | REAL-DATA-04 | would be this project's first real azimuth information (E-020, RL-032b) |
| Locate the real illumination cliff | a later stage | bracketed only between 0.96° and 38.85° of Δincidence |
| `n_inliers <= 8` validated on real data | a later stage | needs many real pairs with known outcomes |
| Incidence ceiling in `find_illumination_pairs()` | later | **D-029**, still recorded-not-implemented |
| A ground truth of any kind for real NAC | unresolved | none exists for these products at this project's disposal |
| Chandrayaan-2 / multi-modal | blocked | ISSDC authentication |

## 19. Decision

**Q1. Did the images independently overlap?** **Yes.** All three edges
`OVERLAP_CONFIRMED` before any registration was interpreted: 97.12 %, 82.72 %, 85.00 %, with
pessimistic bounds 90.03 %, 78.57 %, 80.62 % — the A↔B bound above the 0.757 floor of the only
regime the matcher has been measured in. Evidence: archive corner geometry, no pixel read, no
matcher component.

**Q2. Did the unchanged baseline find a registration?** **On one of three edges.**
B → C: 5365 inliers, ratio 0.9950. A → B and C → A: 4 inliers each, REJECTED, class C.

**Q3. If it failed, what evidence supports the cause?** Seven candidates are eliminated by
measurement (§15.3), each by a comparison against the succeeding edge on the same ground with
the same code. Illumination difference is the only enumerated candidate left standing. The
failures are independently confirmed catastrophic — 1614 px and 583 px against a 91–104 px
bound, with recovered scales wrong by 36–102 % against an archive field.

**Q4. If it succeeded, is the registration independently verified?** **No — corroborated, not
verified.** B → C's recovered scale matches SPICE-derived `SCALED_PIXEL` to 0.04 % / 0.50 %
within a 1.83 % tolerance, and its endpoint disagreement with the corner-polygon prediction
(162 px) is 1.55× a bound whose own resolution is 105 px. There is no ground truth. **Class B.**

**Q5. Does loop closure support the registration?** **No, and it cannot here.** The loop
residual is **1201.04 px**, which correctly reflects two broken legs. Loop closure ran on real
data for the first time, with three independently estimated edges, and did not manufacture a
small residual — but a loop containing two garbage edges cannot corroborate the third.

**Q6. Can illumination now legitimately be implicated?** **Implicated, not established.** It
is the only surviving enumerated candidate, and saying more would ignore that Δincidence is
perfectly confounded with frame identity across three frames, and separately confounded with
Δazimuth, which was not measured. **This stage does not attribute the failure to
illumination.**

**Q7. What remains unresolved?** §17, in full.

## 20. Exact next action

```bash
# REAL-DATA-04 — break the confound with ONE more frame.
# A fourth product D at LOW incidence (near A's 29.95 deg), on the same ground point,
# selected by the same pre-stated criteria: incidence <= 75 deg, a full tile inside the
# frame, minimum max-resolution-ratio against the existing three.
python scripts/fetch_index_geometry.py --pdsids <D> --out real_index_geometry_D.json
python scripts/acquire_real_pair.py --from-geometry real_index_geometry_D.json \
       --products <D> --target-lonlat 22.033852048576282,20.03525252164036 \
       --lines 4096 --samples 2048 --out real_fourth_d_geo_manifest.json

# The gate FIRST, as always.
python scripts/verify_tile_overlap.py --manifest <triplet with D> \
       --outdir REAL-DATA-04 --require-confirmed

# Then the unmodified baseline on the two edges that decide it.
#   D <-> A   (Delta-incidence ~0 deg)   -- predicted to SUCCEED if illumination is the driver
#   D <-> B   (Delta-incidence ~40 deg)  -- predicted to FAIL if illumination is the driver
# If instead D <-> A fails and D <-> B succeeds, the driver is frame identity, not
# illumination, and section 15.3's surviving candidate is refuted.
```

**This prediction is written down before the data exists**, which is what makes it a test.

The second item, once the confound is settled: a triplet of three mutually
illumination-similar frames, so loop closure's discriminating power can be measured on real
data rather than merely exercised.

**No matcher change, no tuning, no learned component is justified yet.** A single failing
regime has been isolated but not attributed, and EXP-004 remains pre-registered, not started,
and unaffected.

---

## 21. Commands executed

```bash
# -- third-image screening (metadata only) --
python -c "...ODE query minlat=19.5 maxlat=20.5 westernlon=21.9 easternlon=22.2..."
python -c "...rank candidates by max resolution ratio against A and B..."

# -- acquisition --
python scripts/fetch_index_geometry.py --pdsids nac.m1452560468lc \
       --out real_pair_index_geometry_C.json
python scripts/acquire_real_pair.py --from-geometry real_pair_index_geometry.json \
       --products nac.m1271742202lc,nac.m1335207975rc --lines 4096 --samples 2048 \
       --role usable_geo --out real_pair_usable_geo_manifest.json
python scripts/acquire_real_pair.py --from-geometry real_pair_index_geometry_C.json \
       --products nac.m1452560468lc \
       --target-lonlat 22.033852048576282,20.03525252164036 \
       --lines 4096 --samples 2048 --role third_product_for_loop_closure \
       --out real_third_c_geo_manifest.json
python scripts/compose_triplet_manifest.py \
       --from real_pair_usable_geo_manifest.json,real_third_c_geo_manifest.json \
       --products nac.m1271742202lc,nac.m1335207975rc,nac.m1452560468lc \
       --out real_triplet_geo_manifest.json

# -- the gate, BEFORE any registration was interpreted --
python scripts/verify_tile_overlap.py --manifest real_pair_usable_geo_manifest.json \
       --case usable_geo --outdir REAL-DATA-03 --out overlap_usable_geo.json \
       --figure tile_overlap_usable_geo.png --require-confirmed
python scripts/verify_tile_overlap.py --manifest real_triplet_geo_manifest.json \
       --case triplet --extra-geometry real_pair_index_geometry_C.json \
       --outdir REAL-DATA-03 --out overlap_triplet.json \
       --figure tile_overlap_triplet.png --require-confirmed

# -- sanity --
python scripts/check_real_tiles.py --manifest real_pair_usable_geo_manifest.json \
       --outdir REAL-DATA-03
python scripts/check_real_tiles.py --manifest real_triplet_geo_manifest.json \
       --outdir REAL-DATA-03

# -- the unmodified baseline --
python scripts/register_real_pair.py --manifest real_pair_usable_geo_manifest.json \
       --downsample 2 --outdir REAL-DATA-03
python scripts/register_real_triplet.py --manifest real_triplet_geo_manifest.json \
       --downsample 2

# -- independent check of the estimated transforms --
python scripts/check_transform_against_geometry.py \
       --manifest real_triplet_geo_manifest.json \
       --registration experiments/REAL-DATA-03/loop_closure_triplet.json \
       --extra-geometry real_pair_index_geometry_C.json --downsample 2

# -- REAL-DATA-02 reproduced unchanged, and the full suite --
python scripts/verify_tile_overlap.py
python -m pytest tests/      # 376 passed, 2 skipped
```

Commands that failed are in §12, with their exact messages.

## 22. Files changed

**New scripts** `scripts/register_real_triplet.py` · `scripts/compose_triplet_manifest.py` ·
`scripts/check_transform_against_geometry.py`

**Extended scripts** (additive; every prior invocation still behaves identically)
`scripts/acquire_real_pair.py` (`--from-geometry`, `--products`, `--target-lonlat`, `--role`) ·
`scripts/fetch_index_geometry.py` (`--pdsids`, `--out`) ·
`scripts/verify_tile_overlap.py` (`--manifest`, `--outdir`, `--require-confirmed`, triplet
edges) · `scripts/check_real_tiles.py` (`--outdir`, E-030, E-031) ·
`scripts/register_real_pair.py` (`--outdir`)

**Modified source** `src/siim/ingest/footprint.py` — `TileWindow` and
`predicted_correspondences` added; nothing existing changed

**New tests** `tests/test_real_tile_cache.py` (6) · `tests/test_ingest_footprint.py` (+13)

**New data** `data/manifests/real_pair_index_geometry_C.json` ·
`real_pair_usable_geo_manifest.json` · `real_third_c_geo_manifest.json` ·
`real_triplet_geo_manifest.json` · three tiles under `data/processed/mare_serenitatis/`

**New artefacts** `experiments/REAL-DATA-03/` — `overlap_usable_geo.json`,
`overlap_triplet.json`, `tile_sanity_*.json`, `registration_usable_geo.json`,
`loop_closure_triplet.json`, `transform_vs_geometry.json`, and their figures ·
`experiments/REAL-DATA/tile_sanity_usable_geo_preE030.*` (the E-030 failure, preserved)

**Documentation** this file · `ERROR_LEDGER.md` (E-030, E-031) · `DECISION_LEDGER.md`
(D-035, D-036; D-031 and D-033 updated) · `research_log.md` (RL-033, RL-034; RL-031b and
RL-030b closed) · `STAGE-INDEX.md` · `STAGE_HISTORY.md` · `stages/README.md` · `README.md`

**No ADR was created.** ADR-0011 (loop closure) is **not** amended: its reversal condition was
not met, and a first exercise on real data is not the validation that would change it.

## 23. Integrity checklist

| | |
|---|---|
| Overlap established before registration was interpreted | **Yes** — `--require-confirmed` exits non-zero; run first, in a separate command |
| Overlap evidence independent of the matcher | **Yes** — archive geometry, no pixel read |
| Baseline unmodified | **Yes** — detector, descriptor, matching, RANSAC, threshold, seed, model, decimation and preprocessing all unchanged and restated as constants |
| No result cherry-picked | **Yes** — all three edges reported; the failing pair is the headline |
| Third product selected on pre-stated criteria | **Yes** — §10, decided by resolution ratio, not illumination |
| Loop edges independently estimated | **Yes** — asserted in code (`_assert_independent`), not merely intended |
| Failed attempts preserved | **Yes** — `*_preE030.*`, and §12's exact messages |
| Nothing overwritten | **Yes** — every output is a new path; the overwrite guard fired once and is recorded |
| No prior stage report rewritten | **Yes** — REAL-DATA-01 and -02 stand as written |
| Every quoted number traced to an artefact | **Yes** — `experiments/REAL-DATA-03/*.json` |
| Hypotheses eliminated only by evidence | **Yes** — §15.3, each with the measurement that eliminates it |
| The surviving hypothesis **not** asserted as the cause | **Yes** — §15.4, §19 Q6 |
| Full suite run | **Yes** — 376 passed, 2 skipped (from 357 passed, 2 skipped) |
| REAL DATA distinguished from SYNTHETIC | **Yes** — in the loop-closure artefact, its figure title and the runner's output |
| Licence and credit recorded | **Yes** — NASA PDS public domain; **NASA/GSFC/Arizona State University** |
