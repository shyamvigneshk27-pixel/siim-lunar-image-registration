# REAL-DATA-02 — Independent real-image overlap verification

**Stage ID:** REAL-DATA-02
**Name:** Establish, independently of the feature matcher, whether the real LRO NAC tile pairs of REAL-DATA-01 cover the same ground
**Status:** **COMPLETE — the question is answered. The REAL-DATA-01 headline pair does NOT overlap.**
**Date:** 2026-08-26 · **Depends on:** REAL-DATA-01 (`REAL-DATA_LRO_NAC.md`) · **Runs beside:** EXP-004 (still not started), DEMO_TRACK
**Classification:** RESEARCH-RELEVANT. Not an EXP-numbered experiment — it measures the *data*, not a method. Criteria were nonetheless fixed in code before any pair was classified (§3).

> **Standing under integrity rules 8 and 10 is unchanged.** No multi-modal claim. No
> Chandrayaan-2 data was obtained or simulated. No Sun-azimuth claim. Nothing here is
> compared against synthetic ground truth, and **nothing here is a registration result.**

---

## 1. Objective

Answer one question, rigorously, and optimise nothing else until it is answered:

> **Did we actually give the matcher two overlapping pieces of the Moon?**

REAL-DATA-01 measured 3 RANSAC inliers on a real NAC pair and classified it C / REJECTED. It
could not say what that meant, because its only overlap evidence *was* the registration it
was trying to explain (`REAL-DATA_LRO_NAC.md` §18, D-030, D-031, RL-029b). Overlap evidence
derived from the matcher cannot adjudicate the matcher.

## 2. Scientific question

Two hypotheses were left live by REAL-DATA-01 and it separated neither:

| | |
|---|---|
| **H1** | the selected tiles do not actually overlap sufficiently |
| **H2** | they overlap, but illumination / appearance defeats the matcher |

This stage tests **H1 only**, and tests it with evidence that would be identical if the
matcher did not exist. It does not test H2 and makes no claim about it.

## 3. Pre-registered / fixed criteria

Fixed in `scripts/verify_tile_overlap.py` as module constants, before any pair was
classified. The quantity classified is the **shared fraction of the worse-covered tile**,
`min(area∩/areaA, area∩/areaB)` — reported in preference to IoU because it is what a matcher
actually experiences: a tile of which 20 % is shared ground offers 20 % of its keypoints as
candidates, whatever the other tile does.

| Class | Rule |
|---|---|
| **OVERLAP_CONFIRMED** | pessimistic (p5) `min_fraction` **≥ 0.50** |
| **OVERLAP_INSUFFICIENT** | optimistic (p95) `min_fraction` **< 0.20** |
| **OVERLAP_UNKNOWN** | anything else, including any interval straddling a threshold |

**Where 0.50 comes from, and what it does *not* claim.** The only regime in which this
project has ever *measured* its matcher is the synthetic one. Measuring
`scripts/exp002_common.py`'s `make_transform` / `overlap_roi` over 20 draws × 5 transform
classes gives a source-to-target overlap of **0.757 at worst, 0.945 median**. 0.50 sits
**below** that floor, so CONFIRMED does not certify "as easy as the synthetic case". It
certifies that a majority of each tile is shared ground — the condition under which a
matcher failure becomes a statement about appearance rather than about geography.
0.20 is the mirror: below a fifth, the shared strip is a minority of each tile, far outside
any characterised regime, and a failure there carries no information at all.

**Uncertainty is required to decide, not the point estimate.** `classify_overlap` takes an
interval. Passing the point estimate twice is legal and gives a classification with no
uncertainty allowance, which is exactly what must never be reported.

## 4. Existing evidence, and why it was not enough

| What REAL-DATA-01 had | Why it cannot answer the question |
|---|---|
| ODE `footprint_iou` = 0.400 (terminator) / 0.516 (usable) | **Whole-frame** IoU on 48 × 5 km strips. Two 3.7 × 1.9 km tiles inside two overlapping frames can be 22 km apart |
| `overlap_latitude_band_deg` in the manifests | Latitude only. Says nothing about cross-track (longitude) position |
| the 1.05 implied-m/line consistency ratio | Supports a first-order **along-track** model. Silent on where the tile sits |
| 3 / 4 / 4 / 5 inliers across the H1/H2 grid | **Matcher-derived.** Inadmissible as overlap evidence here |
| `tile_pair_*.png` side-by-side figures | Captioned "APPROXIMATE"; a visual impression, not a measurement |

## 5. Data used

**No image bytes were fetched and no pixel was read.** The tiles on disk were not opened.

| Artefact | Role | New? |
|---|---|---|
| `data/manifests/real_pair_usable_manifest.json` | tile windows for the primary pair | existing |
| `data/manifests/real_pair_usableH2_manifest.json` | tile windows, other line hypothesis | existing |
| `data/manifests/real_pair_terminator_manifest.json` | tile windows, Δinc 65.3° pair | existing |
| `data/metadata/mare_serenitatis/*.xml` | PDS4 labels — `disp:Display_Direction` | existing |
| **`data/manifests/real_pair_index_geometry.json`** | **named corner geometry** | **NEW (§6.3)** |
| `experiments/REAL-DATA/registration_*.json` | secondary corroboration only | existing |

**Nothing existing was modified or overwritten.** `fetch_index_geometry.py` refuses to run
if its output exists, and `--force-refetch` writes a timestamped sibling rather than
replacing the original (integrity rule 4).

## 6. Geometry available — the audit, done before any calculation

The brief required determining what geometry actually exists rather than assuming PDS4
supports a field. Four sources were searched. The first two are empty.

### 6.1 The PDS4 `Product_Observational` label — **NO geometry**

`[MEASURED]` All four labels in `data/metadata/mare_serenitatis/` were read in full. They
contain `Identification_Area`, `Time_Coordinates` (start/stop only), `Investigation_Area`,
`Observing_System`, `Target_Identification`, `lro:LRO_Parameters` (orbit number, clock
counts, temperatures, exposure), `img:Imaging`, `disp:Display_Settings`, and
`File_Area_Observational`.

They contain **no** `Cartography`, **no** `Geometry`, **no** corner coordinates, **no**
sub-solar or sub-spacecraft point, **no** latitude or longitude of any kind. A NAC CDR is in
sensor geometry and the label does not geolocate it.

### 6.2 The PDS3 attached header inside the `.IMG` — **NO geometry**

`[MEASURED]` The label declares `Header: offset 0, object_length 5064, PDS3`. Those 5064
bytes were fetched live over HTTP 206 for `M1271742202LC.IMG` and read. They carry file
characteristics, data identification, `DATA_QUALITY_DESC`, environment temperatures,
imaging parameters and the `IMAGE` object — and **no geometry keywords whatsoever**. No
corner coordinates, no `SUB_SOLAR_AZIMUTH`, no `NORTH_AZIMUTH`.

`[INTERPRETATION]` This extends E-020 rather than contradicting it: the CDR *product* — both
its PDS4 label and its embedded PDS3 header — is geometrically silent. E-020 said the PDS4
labels carry no illumination geometry; they carry no positional geometry either.

### 6.3 The ODE product record — a polygon whose **vertex order is undocumented**

`[MEASURED]` ODE returns `Footprint_geometry` as a WKT ring of four vertices, plus
`Footprint_souce = "PDS Archive Index Table"`.

```
nac.m1271742202lc  POLYGON ((21.93 19.4, 22.02 21.07, 22.19 21.06, 22.08 19.39, 21.93 19.4))
```

A ring has an order; nothing in the response says what the order **means**. Which vertex is
image line 0 is not recoverable from it. Guessing wrong mirrors a tile along-track by up to a
whole frame — **48 km** for a NAC CDR — which is precisely the unresolved H1/H2 ambiguity of
REAL-DATA-01 §4.5. **This source alone cannot answer the question**, and the stop condition
"the only available evidence is whole-product footprint overlap" would have fired here.

### 6.4 The PDS archive index table — **named corners.** This is the source that works

ODE names its own source, and it is in the archive one directory above the data:
`LRO-L-LROC-3-CDR-V1.0/<VOLUME>/INDEX/INDEX.TAB` with a detached `INDEX.LBL`.

`[MEASURED]` The label declares 83 columns over `RECORD_BYTES = 901`. Among them:

```
UPPER_LEFT_LATITUDE   UPPER_LEFT_LONGITUDE     LOWER_LEFT_LATITUDE   LOWER_LEFT_LONGITUDE
UPPER_RIGHT_LATITUDE  UPPER_RIGHT_LONGITUDE    LOWER_RIGHT_LATITUDE  LOWER_RIGHT_LONGITUDE
NORTH_AZIMUTH   SUB_SOLAR_AZIMUTH   ORBIT_NODE   LRO_FLIGHT_DIRECTION
SCALED_PIXEL_WIDTH   SCALED_PIXEL_HEIGHT   RESOLUTION   IMAGE_LINES   LINE_SAMPLES
```

Corners with **identities**, not a bare ring. That is exactly the missing ingredient.

**Cost.** The tables are 18–54 MB per volume, but `RECORD_TYPE = FIXED_LENGTH` and sorted by
`PRODUCT_ID`, so one row costs a binary search: **15–18 HTTP range requests of 901 bytes**
each, plus one 31 KB label. Measured total for four products: **~130 KB, no image bytes.**

### 6.5 What "upper" and "left" mean — pinned by the product's own label

The corner names are only useful if something says which image line is at the top. Each
product's PDS4 label says it, per product:

```xml
<disp:Display_Direction>
  <disp:horizontal_display_axis>Sample</disp:horizontal_display_axis>
  <disp:horizontal_display_direction>Left to Right</disp:horizontal_display_direction>
  <disp:vertical_display_axis>Line</disp:vertical_display_axis>
  <disp:vertical_display_direction>Top to Bottom</disp:vertical_display_direction>
</disp:Display_Direction>
```

`[MEASURED]` Present and identical in all four observational labels
(`test_every_stored_mare_serenitatis_label_states_line_top_to_bottom`). Line increases
downward ⇒ the top row is the **first** line ⇒ `UPPER_*` is line 0, and `*_LEFT` is sample 0.
`scripts/verify_tile_overlap.py` **refuses to run** on any product whose label says otherwise
rather than falling back to convention.

### 6.6 Two independent corroborations, and one check that failed

**(a) Pixel scale — 8 comparisons, all within 1.2 %.** `[MEASURED]` The corner-implied
metres per line and per sample were compared against the archive's own
`SCALED_PIXEL_HEIGHT` / `SCALED_PIXEL_WIDTH`, which are derived from SPICE and do not depend
on these corner values:

| product | m/line implied | `SCALED_PIXEL_HEIGHT` | ratio | m/sample implied | `SCALED_PIXEL_WIDTH` | ratio |
|---|---|---|---|---|---|---|
| `nac.m1225876972lc` | 1.0085 | 1.00 | **1.0085** | 0.9273 | 0.92 | **1.0080** |
| `nac.m1271742202lc` | 0.9712 | 0.96 | **1.0117** | 0.9010 | 0.90 | **1.0011** |
| `nac.m1322281266lc` | 0.9219 | 0.92 | **1.0021** | 0.8452 | 0.84 | **1.0062** |
| `nac.m1335207975rc` | 0.9543 | 0.95 | **1.0046** | 0.8751 | 0.88 | **0.9943** |

Range **0.9943 … 1.0117**. A misassigned corner would not produce agreement this tight on
both axes for four frames from four different volumes and four different years.

**This also closes an open item from REAL-DATA-01 §18.** That stage recorded an unexplained
**1.05** ratio between footprint-implied m/line and ODE's `Map_resolution`, and left it as
*"possibly a footprint-polygon convention, possibly real along-track scale."* Neither.
`Map_resolution` **is** the index's `RESOLUTION` column, which is not the down-scan pixel
scale; the down-scan scale is `SCALED_PIXEL_HEIGHT`. Against `RESOLUTION` the ratios here are
1.048 / 1.041 / 1.049 / 1.040 — REAL-DATA-01's 1.05, reproduced. Against
`SCALED_PIXEL_HEIGHT` they are 1.002–1.012. **The 5 % was a comparison against the wrong
field, not a geometry error.**

**(b) Flight direction — a 2-2 partition that matches exactly.** `[MEASURED]`

| product | `ORBIT_NODE` | `LRO_FLIGHT_DIRECTION` | line 0 sits at | = REAL-DATA-01 hypothesis |
|---|---|---|---|---|
| `nac.m1225876972lc` | A | **+X** | MAX latitude | **H1** |
| `nac.m1322281266lc` | A | **+X** | MAX latitude | **H1** |
| `nac.m1271742202lc` | A | **−X** | MIN latitude | **H2** |
| `nac.m1335207975rc` | A | **−X** | MIN latitude | **H2** |

`[INTERPRETATION]` If `UPPER_*` were a *compass* label it would be the northern edge of every
frame. It is not — the four split 2-2, and the split follows `LRO_FLIGHT_DIRECTION` exactly.
A spacecraft yaw flip reverses the along-track readout direction, which is what an
image-position label should track and a compass label cannot. This eliminates the main
alternative reading of the column names. It is corroboration, not proof: a 2-2 split matches
by chance with probability 1/3.

**(c) `NORTH_AZIMUTH` — a designed check that turned out to have no power.** `[MEASURED]`
268.59 / 274.77 / 267.72 / 272.94 — a tight cluster around 270° while the frames split 2-2 on
line direction. Group means differ by **5.70°**. The column's own description says the angle
is *"relative to the RDR products"* — the map-projected derivative, which is north-up by
construction — and the measurement bears that out.

`[INTERPRETATION]` The check is **inapplicable**, not failed. `north_azimuth_agreement` would
report "agrees" for two frames and "disagrees" for two, and both verdicts would be noise.
This is E-024's lesson applied *before* the fact: a discriminator needs a stated domain of
validity, and reporting a disagreement from a powerless test sends the next reader to debug
correct data. It is recorded as **E-027** and is **not used**.

### 6.7 A by-product: ODE's ring order, decoded

`[MEASURED]` Every ODE `Footprint_geometry` vertex matches a named index corner to machine
precision, in the order **(UR, LR, LL, UL)** for all four products. That confirms
`Footprint_souce`, and it confirms the refusal in §6.3 was right: the order is fixed but
undocumented, and it is *not* the natural UL-first order anyone would guess.

### 6.8 A by-product with consequences: `SUB_SOLAR_AZIMUTH` exists

`[MEASURED]` The index table carries `SUB_SOLAR_AZIMUTH`: **144.09 / 175.27 / 177.73 /
120.46** degrees for the four products.

`[NOT VERIFIED]` **It was not used anywhere in this stage.** It carries the same
"relative to the RDR products" caveat as `NORTH_AZIMUTH`, and that caveat is exactly what
would need to be settled before any Δazimuth number could be quoted. It also does **not**
make these pairs azimuth-*controlled*: they were selected on incidence, and a field
discovered afterwards cannot retroactively control an experiment. See §17 and E-020.

## 7. Method

Implemented in `src/siim/ingest/footprint.py` (new) and `src/siim/ingest/index_table.py`
(new), driven by `scripts/verify_tile_overlap.py` (new).

1. **Named corners → a ground map.** `FrameCorners` holds the four corners keyed by image
   position and interpolates `(lon, lat)` **bilinearly** in `(line, sample)`. Bilinear, not a
   camera model: these are 5 × 48 km strips at near-nadir emission (1.17–1.74°), so
   along-track is very nearly linear in line and cross-track in sample — and §6.6(a) bounds
   the residual at ~1 %.
2. **Tile window → ground quadrilateral.** `tile_polygon(line0, n_lines, sample0, n_samples)`
   maps the four tile corners, using the **last included** pixel (`line0 + n_lines − 1`).
3. **Common plane.** Both rings are projected onto **one** local equirectangular plane
   centred on their mean vertex, sphere R = 1737.4 km. One plane for both shapes, never one
   each — two shapes on different planes cannot be intersected, and doing it anyway produces
   a confident wrong number.
4. **Exact intersection.** Sutherland–Hodgman convex clip, with the clip polygon's convexity
   **checked and raising** — a concave clip does not fail, it returns degenerate spurs with a
   plausible area.
5. **Uncertainty.** Corner coordinates are published to two decimals, so each carries
   independent uniform rounding error in ±0.005° (≈152 m in latitude, ≈142 m in longitude at
   20° N). Propagated by **4000 Monte Carlo draws** (seed 20260826) perturbing all eight
   coordinates of both frames; the 5th–95th percentile of `min_fraction` is the interval.
6. **Classify**, then and only then read the registration artefacts (§10).
7. **Report the alternative corner reading for every pair**, via
   `mirrored_along_track()`, so the dependence on §6.5 is visible rather than silent.

**The cross-track naming ambiguity is provably harmless here.** All six tiles use a
**sample-centred** window (`sample0 = (5064 − 2048) / 2 = 1508`), and mirroring the sample
direction maps a centred window onto itself. Asserted and tested
(`test_cross_track_mirroring_leaves_a_sample_centred_tile_exactly_where_it_was`, with the
off-centre counter-case beside it).

**Independence.** `footprint.py` imports only `numpy`. It touches no detector, descriptor,
matcher, RANSAC, residual, coverage metric or verdict, and reads no pixel.

## 8. Results

`[MEASURED]` `experiments/REAL-DATA-02/overlap_verification.json`,
`experiments/REAL-DATA-02/tile_overlap.png`. All tiles are 4096 × 2048 px ≈ 3.8 × 1.8 km.

| case | tile A / B line0 | area A | area B | **∩** | IoU | of A | of B | **min** | p5–p95 | centres apart |
|---|---|---|---|---|---|---|---|---|---|---|
| **`usable_H1`** | 30126 / 18367 | 7.451 | 6.944 | **0.0000** | 0.0000 | 0.0 % | 0.0 % | **0.0 %** | 0.0–0.0 % | **22.754 km** |
| **`usable_H2`** | 18002 / 29761 | 7.239 | 7.042 | **4.9653** | 0.5330 | 68.59 % | 70.51 % | **68.59 %** | 62.9–74.1 % | 0.527 km |
| **`terminator_H1`** | 19466 / 30517 | 6.524 | 7.909 | **2.2375** | 0.1835 | 34.30 % | 28.29 % | **28.29 %** | 23.4–33.0 % | 1.243 km |
| `usable_A@H1_B@H2` | 30126 / 29761 | 7.442 | 7.034 | **0.0000** | 0.0000 | 0.0 % | 0.0 % | **0.0 %** | 0.0–0.0 % | 11.883 km |
| `usable_A@H2_B@H1` | 18002 / 18367 | 7.247 | 6.952 | **0.0000** | 0.0000 | 0.0 % | 0.0 % | **0.0 %** | 0.0–0.0 % | 10.988 km |

Areas and intersection in km². `min` = shared fraction of the worse-covered tile.

### 8.1 The headline

**The tile pair behind REAL-DATA-01's headline 3-inlier result shares no ground at all.**
Its two tiles are **22.75 km apart** — nearly six tile-lengths. The frames overlap
(whole-frame IoU 0.516); the crops taken out of them do not.

### 8.2 Why, exactly

Two independent defects in `scripts/acquire_real_pair.py`, both now visible:

1. **The line-direction hypothesis is per-frame, and the script forced it to be global.** Its
   docstring reasons: *"Because both frames come from the same camera and the same processing
   pipeline, the convention is the same for both — H1-for-both or H2-for-both, never mixed."*
   The archive says otherwise (§6.6b): direction follows `LRO_FLIGHT_DIRECTION`, which
   differs between frames. Both usable frames are **H2**; both terminator frames are **H1**.
   The `usable` pair was acquired at **H1** — the wrong one — which is why its tiles landed on
   opposite sides of the frame centre. Recorded as **E-028**.
2. **Cross-track position was never matched.** Each tile takes its own frame's centre 2048
   samples, on the reasoning that "the two frames' longitude ranges overlap in their middles".
   The two frames' centre longitudes differ by ~0.04–0.06°, i.e. **1.1–1.7 km**, against a
   tile only 1.8 km wide. This is what caps `usable_H2` at 68.6 % instead of ~100 %, and it is
   the main reason `terminator_H1` reaches only 28 %. Recorded as **E-029**.

### 8.3 What REAL-DATA-01 §4.5 actually showed

That section tested four H1/H2 combinations, found 3/4/4/5 inliers, and concluded *"All four
fail. The direction hypothesis is not the explanation."* The geometry says exactly one of the
four rows — `A@H2 × B@H2` — has overlapping tiles. The other three are disjoint by 11–23 km
and **could not have succeeded**. The direction hypothesis was resolvable, it was not
resolved, and it *was* the explanation for three of the four rows.

`[INTERPRETATION]` The inference "all conditions failed, therefore this variable does not
matter" is only valid if every condition was otherwise capable of succeeding. Here three were
not. This is the mirror image of E-025: there, identical results across different conditions
were a bug; here, uniformly negative results across conditions were read as evidence about a
variable when they were evidence about the sampling.

### 8.4 A projection for the next stage, not a measurement

`[MEASURED, but a projection]` Using the same geometry to re-cut both tiles centred on the
centroid of the two frames' shared footprint:

| pair | projected `min_fraction` | projected IoU | A: line0, sample0 | B: line0, sample0 |
|---|---|---|---|---|
| usable | **97.12 %** | 0.9695 | `nac.m1271742202lc` 17955, 1811 | `nac.m1335207975rc` 29822, 1227 |
| terminator | **82.48 %** | 0.8248 | `nac.m1322281266lc` 19331, 2092 | `nac.m1225876972lc` 30626, 733 |

No tile was cut and no registration was run. This is a **specification** for REAL-DATA-03, so
that stage has concrete numbers rather than an instruction to "select better". 97.1 % sits
above the synthetic regime's 0.757 floor.

## 9. Overlap classification

Every classification below is derived **only** from archive geometry and integer tile
windows. The full record, per pair, is in
`experiments/REAL-DATA-02/overlap_verification.json`.

### `usable_H1` — **OVERLAP_INSUFFICIENT**

| | |
|---|---|
| **Evidence used** | index-table named corners for `nac.m1271742202lc` / `nac.m1335207975rc`; `disp:Display_Direction` from both PDS4 labels; `IMAGE_LINES` / `LINE_SAMPLES`; the tile windows in `real_pair_usable_manifest.json` |
| **Coordinate system** | ground `(lon, lat)` east-positive; areas in a local equirectangular plane in km, sphere R = 1737.4 km |
| **Assumptions** | bilinear ground coordinate between named corners; ±0.005° independent uniform corner rounding; `UPPER_*` = line 0 per §6.5 |
| **Uncertainty** | p5–p95 of `min_fraction` = **0.000 – 0.000**. Tile centres 22.75 km apart. Allowing for both tiles' half-diagonals (2.21 and 2.15 km), it would take a **≥ 18.4 km** systematic geolocation error merely to bring them into contact — **121×** the 152 m corner quantisation |
| **Independent of the matcher?** | **Yes.** No pixel read, no matcher component used |
| **Source artefacts** | `data/manifests/real_pair_index_geometry.json`, `data/manifests/real_pair_usable_manifest.json`, `data/metadata/mare_serenitatis/nac.m{1271742202lc,1335207975rc}.xml` |
| **Alternative corner reading** | would give 68.59 % — **this classification depends on §6.5** and the dependence is stated, not hidden |

### `usable_H2` — **OVERLAP_CONFIRMED**

| | |
|---|---|
| **Evidence used** | as above, with the tile windows in `real_pair_usableH2_manifest.json` |
| **Coordinate system** | as above |
| **Assumptions** | as above |
| **Uncertainty** | p5–p95 = **0.629 – 0.741**, point estimate 0.686. The pessimistic end clears the 0.50 criterion by 0.13 |
| **Independent of the matcher?** | **Yes** |
| **Source artefacts** | `real_pair_index_geometry.json`, `real_pair_usableH2_manifest.json`, both labels; tiles `nac.m1271742202lc.H2.l18002.tile.npy`, `nac.m1335207975rc.H2.l29761.tile.npy` |
| **Alternative corner reading** | would give 0.00 % — same dependence, opposite direction |

### `terminator_H1` — **OVERLAP_UNKNOWN**

| | |
|---|---|
| **Evidence used** | as above, for `nac.m1322281266lc` / `nac.m1225876972lc`, windows from `real_pair_terminator_manifest.json` |
| **Coordinate system** | as above |
| **Assumptions** | as above |
| **Uncertainty** | p5–p95 = **0.234 – 0.330**, point estimate 0.283. Lands in the band between the criteria; the geometry does not decide it |
| **Independent of the matcher?** | **Yes** |
| **Source artefacts** | `real_pair_index_geometry.json`, `real_pair_terminator_manifest.json`, both labels |
| **Alternative corner reading** | would give 0.00 % |

### `usable_A@H1_B@H2` and `usable_A@H2_B@H1` — **OVERLAP_INSUFFICIENT** (both)

Zero shared area, centres 11.88 km and 10.99 km apart, p5–p95 = 0.000–0.000 in both cases.
Both are **INSUFFICIENT under the alternative corner reading as well**, so these two are the
only classifications in this stage that do not depend on §6.5 at all. Evidence, coordinate
system, assumptions and independence as above; windows taken from the two usable manifests.

## 10. Secondary corroboration — explicitly not primary evidence

Read **after** every classification above was fixed. `classify_overlap` is called before
these files are opened, in code.

| case | **geometry (primary)** | registration (secondary) | consistent? |
|---|---|---|---|
| `usable_H1` | OVERLAP_INSUFFICIENT (0 %) | 3 inliers / 35 putative, REJECTED, class C | yes — a disjoint pair should not register |
| `usable_H2` | OVERLAP_CONFIRMED (68.6 %) | 5 inliers / 43 putative, REJECTED, class C | **the informative case** — see §15 |
| `terminator_H1` | OVERLAP_UNKNOWN (28.3 %) | 3 inliers / 5 putative, REJECTED, class C | uninformative either way |

`[INTERPRETATION]` The geometry and the registration outcomes are consistent, and the
consistency adds little: three rejections are what a disjoint pair, a hard overlapping pair
and an unusable frame would all produce. The corroboration is recorded because an
*inconsistency* would have been important — a confirmed-disjoint pair that registered
confidently would have indicted the geometry.

## 11. Uncertainty

| Source | Magnitude | How it was handled |
|---|---|---|
| Corner coordinate quantisation | ±0.005° = **±152 m** lat, **±142 m** lon | 4000-draw Monte Carlo, all 8 coordinates of both frames, seed 20260826 |
| Bilinear model vs true sensor geometry | **≤ 1.2 %** of frame extent | bounded by the `SCALED_PIXEL` agreement (§6.6a); not separately propagated, and stated as a residual |
| Spherical Moon vs ellipsoid | ~2 m over 50 km (flattening 1.2e-3) | negligible — 75× below the quantisation |
| Equirectangular plane vs sphere | < 1e-5 relative over 5 km | negligible |
| **Corner naming (§6.5)** | **binary, and it flips three of five results** | **not** folded into the interval. Reported explicitly as `alternative_corner_reading` for every pair |
| `IMAGE_LINES` / `LINE_SAMPLES` | exact integers, agree with the PDS4 label | none needed |

**The assumptions do not dominate the numeric result, but one of them does dominate three of
the five classifications.** The margins are large relative to the propagated uncertainty
(0 % vs 68.6 %, not 45 % vs 55 %) — but which of the two the pair receives depends entirely on
§6.5. That is why §6.5 rests on a *per-product archive statement* rather than on convention,
and why §6.6 exists.

## 12. What this evidence does NOT establish

1. **It does not establish that any real registration succeeded.** None did. This stage ran no
   registration.
2. **It does not attribute the `usable_H2` failure to illumination.** Overlap is now excluded
   as the cause for that pair; several causes remain live and this stage tested none of them —
   illumination difference, mare texture poverty (D-026: realistic mare yields 24 keypoints at
   384², and whether mare is measurable at all is an open question), the 2× decimation, the
   1.6 % resolution ratio, and real relief displacement between two frames at different
   emission angles that no global affine model absorbs.
3. **It does not establish Δazimuth for any pair.** `SUB_SOLAR_AZIMUTH` was found (§6.8) and
   deliberately not used. These pairs remain **illumination-varied by incidence only**, not
   azimuth-controlled.
4. **Confirmed overlap is not registration.** `usable_H2` shares ground; the transform between
   its tiles remains unknown, and no ground truth exists for these products.
5. **It does not validate `n_inliers <= 8` on real data.** Unchanged from REAL-DATA-01.
6. **It says nothing about loop closure on real data.** Still never run; still needs a third
   overlapping real product.
7. **No Chandrayaan-2, no multi-modal claim.** Both frames of every pair are the same
   instrument, and no ISSDC data was obtained.
8. **The 82.5 % / 97.1 % of §8.4 are projections, not measurements.** No such tile exists.
9. **It does not generalise beyond these four products.** Four frames, one region, one
   instrument, one product type.

## 13. Errors encountered

Each uses **Problem → Evidence → Root Cause → Fix → Verification → Lesson** and exactly one of
the five classes. **E-027 is a defect in this stage's own new code/design; E-028 and E-029 are
defects in REAL-DATA-01's acquisition script that this stage's evidence exposed.**

---

### E-027 — A `NORTH_AZIMUTH` cross-check was designed, implemented, and has no discriminating power
**Class: Experimental / design mistake.** Severity **MEDIUM**.

**Problem.** `north_azimuth_agreement()` was written to test the corner naming of §6.5 against
an independent column. Run on the four frames it reports **agrees** for two and **disagrees**
for two. Taken at face value it says the archive contradicts itself, and it would have sent
the next reader to debug a correct corner assignment.

**Evidence.** `NORTH_AZIMUTH` = 268.59, 274.77, 267.72, 272.94 — a **5.70°** spread between the
two line-direction groups, while the frames split 2-2 on line direction. The column's own
description in `INDEX.LBL` reads *"This angle is relative to the RDR products"* — the
map-projected derivative, which is north-up by construction, so the value is ~270° for every
LROC CDR regardless of its line order.

**Root cause.** The check was designed from the column's *name* and its angle convention
without reading its stated **domain of validity**. It measures the RDR, not the CDR.

**Fix.** `north_azimuth_discriminating_power()` evaluates the column across a *set* of frames
and reports `has_power = False` when the frames split on line direction while their azimuths
do not (< 15° between group means). The per-frame verdict is still computed and recorded, and
is **explicitly not used**. Nothing about the corner naming was changed.

**Verification.** `test_a_constant_azimuth_across_a_split_set_has_no_power` reproduces the
real four values; `test_a_set_whose_azimuths_track_the_line_direction_has_power` shows the
function still passes a genuinely informative set; `test_a_set_with_only_one_line_direction_cannot_show_anything`
covers the degenerate case.

**Lesson.** **This is E-024 recurring, and recognising it is why it cost an hour instead of a
day.** E-024's lesson was "a discriminator needs a stated margin *and* a stated domain of
validity"; here the domain of validity was written in the archive label and not read. A
disagreement reported by a test with no power is worse than no test: it manufactures doubt
about correct data.

---

### E-028 — The line-direction hypothesis was forced to be global, and it is per-frame
**Class: Experimental / design mistake.** Severity **HIGH** — it invalidates REAL-DATA-01's
headline pair.

**Problem.** `scripts/acquire_real_pair.py` applies one `--hypothesis H1|H2` to both frames of
a pair. Its docstring states the reasoning explicitly: *"Because both frames come from the
same camera and the same processing pipeline, the convention is the same for both —
H1-for-both or H2-for-both, never mixed."* The `usable` pair was acquired at H1. Both of its
frames are H2. The two tiles landed **22.75 km apart** and the resulting 3-inlier result
became REAL-DATA-01's headline.

**Evidence.** `LRO_FLIGHT_DIRECTION` = `−X` for both usable frames and `+X` for both
terminator frames, with `UPPER_*` at MIN and MAX latitude respectively (§6.6b). Independently:
the corner-implied pixel scale agrees with `SCALED_PIXEL_HEIGHT`/`WIDTH` to within 1.2 % on
all 8 comparisons only under this assignment. The overlap consequence is
`experiments/REAL-DATA-02/overlap_verification.json`, case `usable_H1`.

**Root cause.** The line readout direction relative to the ground track is set by **spacecraft
attitude**, not by the camera or the processing pipeline. LRO yaw-flips, and these four
products span 2016–2020 across both attitudes. "Same instrument, same pipeline" was true and
irrelevant. The archive publishes the answer in `LRO_FLIGHT_DIRECTION` and in the corner
latitudes themselves; neither was consulted, because REAL-DATA-01 did not know the index table
existed.

**Fix.** **Not fixed in `acquire_real_pair.py`, deliberately.** Fixing it means re-acquiring
tiles, which is a new acquisition and a new registration run — REAL-DATA-03, not this stage
(the brief's "do not acquire a large new dataset" and "do not optimise anything else until
that question is answered" both bind here). What this stage delivers instead is the *means*:
`FrameCorners.pixel_at()` inverts the ground map, and §8.4 gives the exact corrected
`(line0, sample0)` for both pairs. Recorded as **D-033**.

**Verification.** The correctness of the inverse is pinned by
`test_pixel_at_inverts_lonlat_at_exactly` (7 pixels including all four corners),
`test_a_window_centred_by_pixel_at_lands_on_the_requested_ground_point`, and
`test_along_track_mirroring_moves_a_tile_by_the_length_of_the_frame`, which asserts that the
mirrored reading relocates a tile by nearly a frame — the size of the error being fixed.

**Lesson.** **An assumption justified by a plausible physical argument is still an assumption,
and this one had a published answer.** The docstring's reasoning was careful, explicit and
wrong, and its very carefulness is what made it survive: it reads like a derivation. The
tell that should have triggered the search was already recorded — REAL-DATA-01 §17.3, *"the
line-direction ambiguity is unresolved; the data does not decide it."* **"The data does not
decide it" is a statement about the data one has looked at.**

---

### E-029 — Cross-track tile position was never matched between frames
**Class: Experimental / design mistake.** Severity **MEDIUM**.

**Problem.** `acquire_real_pair.py` takes `sample0 = (samples − n_samples) // 2` for both
frames independently — each frame's own centre — on the stated reasoning that *"the two
frames' longitude ranges overlap in their middles."* They do not overlap in their middles;
they are offset.

**Evidence.** Centre longitudes differ by ~0.04° (usable) and ~0.06° (terminator), i.e.
**1.1 km and 1.7 km**, against a tile **1.8 km** wide. Measured consequence: `usable_H2`
reaches 68.6 % rather than the 97.1 % the same frames allow (§8.4), and `terminator_H1` is
capped at 28.3 % — which is what leaves it **UNKNOWN**.

**Root cause.** Along-track position was derived from the footprint; cross-track was assumed.
The frame is 5064 samples ≈ 4.6 km wide and the tiles are 2048 samples ≈ 1.8 km, so there was
never enough margin for a centre-of-frame assumption to absorb a 1.7 km offset.

**Fix.** Not fixed in the acquisition script, for the same reason as E-028. `pixel_at()` plus
the projected windows of §8.4 supply the correction; **D-033** carries it.

**Verification.** Projection recomputed through the same tested code path
(`recommended_windows` in `scripts/verify_tile_overlap.py`), giving 97.1 % and 82.5 %.

**Lesson.** **A selection that constrains one axis and assumes the other has not been
verified — it has been half-verified, which reads the same in a manifest.** The manifest
recorded `overlap_latitude_band_deg` and nothing about longitude, and that asymmetry was
visible on the page the whole time.

---

### Two failures during this stage that were transport, not data

Recorded because the brief asks for the exact failure, and because both would otherwise look
like data problems:

```
# 1. The archive drops keep-alive between range requests. A 16-probe binary
#    search failed mid-way with no retry:
requests.exceptions.ConnectionError: ('Connection aborted.',
    RemoteDisconnected('Remote end closed connection without response'))
# Fix: retry with backoff in _get(), plus verification that every 206 returned
# exactly the requested byte count. Not a data defect; the same probe succeeds.

# 2. The first foreground run of fetch_index_geometry.py exceeded a 2-minute
#    tool timeout: ~3.0 s per range request x ~66 requests. Re-run in the
#    background. Not an error, but recorded so the ~4 minute cost is on record.
```

Two test-authoring mistakes were also made and fixed in the same session (a fixture record one
byte short of `RECORD_BYTES`, and a half-pixel tile-centring expectation). Neither reached an
artefact; the second is now pinned as a convention in
`test_a_window_centred_by_pixel_at_lands_on_the_requested_ground_point`.

## 14. Fixes

| What | Where | Status |
|---|---|---|
| `NORTH_AZIMUTH` domain-of-validity detector (E-027) | `footprint.py:north_azimuth_discriminating_power` | **FIXED**, tested |
| Retry + byte-count verification on archive range requests | `scripts/fetch_index_geometry.py:_get` | **FIXED** |
| Bilinear inverse so a tile can be centred on a ground point (E-028, E-029) | `footprint.py:FrameCorners.pixel_at` | **ADDED**, tested |
| Line direction taken per frame from the archive | `scripts/verify_tile_overlap.py:build_corners` | **ADDED** (analysis path only) |
| `acquire_real_pair.py` global-hypothesis and centre-sample defects | — | **NOT FIXED — deliberately.** Fixing means re-acquiring. **D-033**, REAL-DATA-03 |

**No existing artefact was modified or overwritten.** No historical result was rewritten:
REAL-DATA-01's document stands as written, and §16 below records how it must now be read.

## 15. Interpretation

`[INTERPRETATION]` Four readings, kept separate from the measurements above.

**1. REAL-DATA-01's headline number measured nothing about the matcher.** 3 inliers from two
tiles 22.75 km apart is the correct output of a correctly-working pipeline given disjoint
inputs. The E-008 observation that stage drew from it — a catastrophically wrong transform
reported at 1.575e-12 px fit RMSE — **survives intact and arguably strengthens**: the
demonstration is that a fit residual can be picometre-perfect on inputs that share *no ground
at all*. What does not survive is any reading of the 3 inliers as evidence about real-data
matcher performance.

**2. The stage's own verdict engine was right for reasons it could not know.** It rejected the
`usable_H1` registration on `n_inliers <= 8`. The pair was unregistrable in principle. That is
a rejection working, not a rule validated — the rule has still never been tested against a
real pair that *could* have registered.

**3. `usable_H2` is the first real-data result this project has that is interpretable at all.**
Two NAC frames, **68.6 % / 70.5 % shared ground** established independently of the matcher,
Δincidence 39.8°, and the unmodified B1 baseline returns **43 putative matches and 5 inliers**
out of 9740 / 13411 keypoints, REJECTED. Overlap is now excluded as the explanation for *that*
pair. That is a genuine narrowing — and it is as far as this stage may go, because the
remaining candidates (§12.2) are untested and one of them, mare texture poverty, is a standing
open question of its own (D-026).

**4. The evidence-failure pattern held again, in a new place.** All three errors here (E-027,
E-028, E-029) are **design mistakes, not code defects**: a check with no power, an assumption
with a published answer, and an axis constrained on one side only. The 260-test suite that
existed before this stage was passing throughout, and could not have caught any of them. The
ledger's pattern 5 — *"the dominant risk is believing a result more than the evidence
supports"* — now has an instance where the over-believed result was **a negative one**.

## 16. Decision

The six questions the stage was set, answered directly.

**Q1. Do we now know that the two real tiles overlap?**
**Yes, for each pair, and the answer differs by pair.** The `usable` pair as acquired for
REAL-DATA-01's headline result (`usable_H1`) **does not overlap** — 0 km², centres 22.75 km
apart. The same two products cropped at `usable_H2` **do overlap**. The terminator pair is
**UNKNOWN**. Two of the five tested configurations are classified without depending on the
corner-naming reading at all; three depend on it, and the dependence is quantified in §9.

**Q2. If yes, by how much?**
`usable_H2`: intersection **4.9653 km²**, IoU **0.5330**, **68.59 %** of tile A and **70.51 %**
of tile B, p5–p95 of the binding fraction **62.9–74.1 %**.
`terminator_H1`: **2.2375 km²**, IoU **0.1835**, 34.30 % / 28.29 %, p5–p95 **23.4–33.0 %**.
`usable_H1` and both mixed grid rows: **0.0000 km²**.

**Q3. Is the overlap evidence independent of the matcher?**
**Yes, completely.** It uses archive corner coordinates, per-product PDS4 display direction,
and the integer tile windows. `src/siim/ingest/footprint.py` imports only `numpy`, reads no
pixel, and would produce identical numbers if `siim.matching` were deleted. The registration
artefacts are opened only after every classification is fixed, in code.

**Q4. Does REAL-DATA-01 therefore provide evidence about matcher failure?**
**Not from the pair it headlined — no.** `registration_usable.json` (3 inliers) is a
measurement on disjoint inputs and carries no information about matcher performance,
illumination robustness, or real-data behaviour. Neither do the two mixed rows of
`hypothesis_grid.json`.
**From `registration_usableH2.json` — partially, and this is new.** That run used tiles now
independently confirmed to share 68.6 % of their ground, and it produced 5 inliers and a
REJECTED verdict. Overlap is excluded as its cause. **The failure is still not attributed**,
and must not be described as an illumination failure (§12.2).
And REAL-DATA-01's *ingestion, decoding, sanity and positive-control* results are untouched by
any of this — they never depended on overlap.

**Q5. If not, exactly what remains UNKNOWN?**
- **Why `usable_H2` failed.** Illumination, mare texture poverty, decimation, resolution ratio
  and real relief displacement all remain live. Nothing here tests any of them.
- **Δazimuth for any real pair.** `SUB_SOLAR_AZIMUTH` was found but its RDR-relative frame is
  unverified and it was not used.
- **The terminator pair's overlap**, at 23.4–33.0 % — genuinely undecided by the geometry, and
  separately unusable on data quality (E-026).
- **Whether the corner naming of §6.5 is right.** It rests on a per-product archive statement
  plus two corroborations, with a third check found powerless. Three of five classifications
  invert if it is wrong.
- **Loop closure on real data.** Never run. Still needs a third overlapping product.
- **`n_inliers <= 8` on real data.** Still never tested against a real pair capable of success.
- **Whether overlapping real triplets exist at all** (RL-030b) — untouched.

**Q6. Which next experiment is scientifically justified?**
**REAL-DATA-03 — geometry-driven re-acquisition of the `usable` pair, plus a third overlapping
product for loop closure.** Justified because: the overlap question is now answered and the
answer invalidates the tiles, not the products; the corrected windows are already computed
(§8.4) and project to 97.1 %; and it is the only route to a real registration attempt whose
outcome would mean something. **Not** justified: any matcher change, any tuning, any learned
component — none of them has yet been given a real pair capable of succeeding. EXP-004 remains
pre-registered, not started, and unaffected.

## 17. Remaining evidence debt

| Debt | Owner | Note |
|---|---|---|
| Attribute the `usable_H2` failure | REAL-DATA-03+ | needs the corrected tiles first; several causes live |
| Loop closure on real data | REAL-DATA-03 | needs a third overlapping product; the project's only trustworthy GT-free check is still synthetic-only (RL-030b) |
| `n_inliers <= 8` on a real pair capable of success | REAL-DATA-03 | never tested |
| Verify the frame of `SUB_SOLAR_AZIMUTH` before quoting any Δazimuth | REAL-DATA-03 | "relative to the RDR products"; would be the first azimuth information this project has had (E-020) |
| Confirm the corner naming against a non-archive source | later | a SPICE/camera-model reconstruction, or a product whose `Display_Direction` differs |
| Fix `find_illumination_pairs()` — incidence ceiling | later | **D-029**, still recorded-not-implemented |
| Fix `acquire_real_pair.py` — per-frame direction and cross-track matching | REAL-DATA-03 | **D-033**, E-028, E-029 |
| Are overlapping real triplets available in this region at all? | REAL-DATA-03 | unknown since ANALYSIS §F.1.4 |

## 18. Exact next action

```bash
# 1. Re-acquire the usable pair at the geometry-derived windows of section 8.4.
#    NEW manifest name; nothing existing is overwritten (integrity rule 4).
#    Requires acquire_real_pair.py to take per-frame line0/sample0 (D-033).
python scripts/acquire_real_pair.py --pair usable --lines 4096 --samples 2048 \
       --from-geometry data/manifests/real_pair_index_geometry.json \
       --out real_pair_usable_geo_manifest.json

# 2. Sanity-check the new tiles before anything reads them (D-032).
python scripts/check_real_tiles.py --manifest real_pair_usable_geo_manifest.json

# 3. Verify the new windows through the SAME independent path, before registering.
python scripts/verify_tile_overlap.py

# 4. Only then: the unmodified B1 baseline.
python scripts/register_real_pair.py --manifest real_pair_usable_geo_manifest.json \
       --downsample 2
```

Step 3 before step 4 is the point of this stage: **the overlap must be established before the
registration is run, not explained by it afterwards.**

The third product for loop closure is a separate search and should be selected by the same
geometry — a `mare_serenitatis` CDR whose index-table corners give ≥ 50 % tile overlap with
*both* members of the usable pair, with incidence ≤ 75° (D-029).

---

## 19. Commands executed

```bash
# -- geometry audit --
python -c "...read all four PDS4 labels, list every element..."          # no Cartography/Geometry
python -c "...HTTP 206 bytes=0-5063 of M1271742202LC.IMG, decode ASCII..."  # no geometry keywords
python -c "...ODE query=product pdsid=<each>, print every field..."      # Footprint_geometry only
python -c "...HEAD <volume>/INDEX/INDEX.LBL and INDEX.TAB..."            # 31 KB label, 18-54 MB table
python -c "...parse INDEX.LBL, list the 83 column names..."              # UPPER_LEFT_LATITUDE etc.

# -- acquisition (metadata only, ~130 KB, no image bytes) --
python scripts/fetch_index_geometry.py

# -- analysis --
python scripts/verify_tile_overlap.py

# -- the pre-registered threshold's anchor, measured not assumed --
python -c "...exp002_common.make_transform/overlap_roi over 5 classes x 20 draws..."
# -> min 0.757, median 0.945

# -- tests --
python -m pytest tests/ -q     # 357 passed, 2 skipped
```

**Commands that failed, recorded rather than tidied away:** see §13, "transport, not data".

## 20. Files changed

**New source**
`src/siim/ingest/footprint.py` · `src/siim/ingest/index_table.py`

**New scripts**
`scripts/fetch_index_geometry.py` · `scripts/verify_tile_overlap.py`

**New tests** (97 added; 260 → 357)
`tests/test_ingest_footprint.py` (71) · `tests/test_ingest_index_table.py` (21) ·
`tests/test_ingest_pds4.py` (+5, display direction)

**Modified source** (additive only)
`src/siim/ingest/pds4.py` — `parse_display_direction()` added, nothing changed ·
`src/siim/ingest/__init__.py` — re-exports

**New artefacts**
`data/manifests/real_pair_index_geometry.json` ·
`experiments/REAL-DATA-02/overlap_verification.json` ·
`experiments/REAL-DATA-02/tile_overlap.png`

**Documentation**
this file · `ERROR_LEDGER.md` (E-027, E-028, E-029) · `DECISION_LEDGER.md` (D-033, D-034;
D-030 and D-031 updated) · `research_log.md` (RL-031, RL-032; RL-029b closed) ·
`STAGE-INDEX.md` · `stages/README.md` · `README.md`

**No ADR was created.** Nothing here is a durable architectural decision: the corner-geometry
route is a data-access method, and the two acquisition defects are bugs with a fix pending in
the next stage. `docs/architecture_decisions.md` is unchanged.

## 21. Integrity checklist

| | |
|---|---|
| Criteria fixed before classification | **Yes** — module constants in `verify_tile_overlap.py`, anchored to a measured synthetic-regime floor |
| Primary evidence independent of the matcher | **Yes** — no pixel read, no matcher component imported |
| Secondary evidence labelled and read after classification | **Yes** — §10, enforced by call order in code |
| Uncertainty propagated and reported as an interval | **Yes** — 4000 draws, seed 20260826, p5–p95 |
| The load-bearing assumption stated, and its alternative computed | **Yes** — §6.5, §11, `alternative_corner_reading` per pair |
| Negative and inconclusive results reported as such | **Yes** — one UNKNOWN, three INSUFFICIENT, one powerless check (E-027) |
| No historical artefact modified or overwritten | **Yes** — every output is a new path |
| No prior stage report rewritten | **Yes** — REAL-DATA-01 stands as written; §15/§16 record how to read it |
| Every quoted number traced to an artefact | **Yes** — `overlap_verification.json`, `real_pair_index_geometry.json` |
| Claims explicitly not supported, listed | **Yes** — §12 |
| Full suite run after implementation | **Yes** — 357 passed, 2 skipped (from 260 passed, 2 skipped) |
| Data licence and credit recorded | **Yes** — NASA PDS public domain; **NASA/GSFC/Arizona State University** |
