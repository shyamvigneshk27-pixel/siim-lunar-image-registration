# REAL-DATA-04 — Can frame identity and illumination be separated?

> ## ⚠ SUPERSEDED IN PART — 2026-08-26, by D-040-N1
>
> **The Status line below, §11.3's heading and §15 Q5 state that frame identity is
> _refuted_. That claim is withdrawn as too strong.** The defensible statement is:
> **frame identity is substantially weakened as an explanation, but NOT conclusively
> refuted.**
>
> Two structural limits, neither a matter of emphasis:
>
> 1. **The refutation is a cross-stage join, not a within-experiment result.** Inside
>    this stage's own triplet {A, B, D}, frame **B** sits in both failing edges and no
>    succeeding one — precisely the partition that blocked REAL-DATA-03, mirrored from
>    A onto B. Only REAL-DATA-03's B→C success breaks it, and that is at a **different
>    ground window**.
> 2. **n = 1.** Frames A and D each have exactly **one** observation in the successful
>    regime, and it is the **same** observation — the single D→A edge carries the whole
>    claim for both.
>
> **REAL-DATA-05 was the pre-registered replication and returned UNRESOLVED, BY DATA
> AVAILABILITY.** Of 906 archive products only 2 sit in the required incidence band over
> shared ground, and both are orientation-incompatible with the incumbents. No image byte
> was fetched and no registration was run, so **nothing in this note is a new
> measurement**.
>
> **Every number in this report stands unchanged**, and Δincidence remains the attributed
> cause in the scope D-040 states. What discharges this note is a **replication** — a
> second, independently selected low-incidence frame that passes against A and fails
> against B. **EXP-004 is the measured blocker on obtaining one.**
>
> Two later measurements bear on this report and neither is folded into it:
> `scripts/check_solar_geometry.py` (2026-08-29, **not pre-registered**) finds that
> **Δazimuth does not separate these six edges while Δincidence does**, and that Δphase is
> collinear with Δincidence to ±2.6° and cannot be separated from it in this near-nadir
> dataset. `scripts/rederive_recorded_registrations.py` re-derives every number in §10
> from the tile bytes exactly.
>
> **The body below is preserved exactly as written, under integrity rule 3** — the same
> discipline E-032 applied: the claim is corrected in the ledger and in this banner, and
> the report is not rewritten to look better than it was.

**Stage ID:** REAL-DATA-04
**Name:** Break the Δincidence / frame-identity confound with one more real frame
**Status:** **COMPLETE — the experiment is valid. D↔A SUCCEEDS, D↔B FAILS. Illumination strongly supported; frame identity refuted.**
**Date opened:** 2026-08-26 · **Depends on:** REAL-DATA-03, REAL-DATA-02, REAL-DATA-01
**Classification:** RESEARCH-RELEVANT. Decision rule fixed in advance; the gate runs before any registration is interpreted.

> Standing under integrity rules 8 and 10 is unchanged. No multi-modal claim. No
> Chandrayaan-2 data. **No Sun-azimuth claim** — azimuth is still not used. Nothing is
> compared against synthetic ground truth, and no ground truth exists for these products.

---

## 1. The question

REAL-DATA-03 measured three real edges on one patch of Mare Serenitatis:

| edge | Δincidence | overlap (matcher-independent) | inliers | outcome |
|---|---|---|---|---|
| A → B | 39.81° | 97.12 % | **4** | FAIL |
| B → C | **0.96°** | 85.00 % | **5365** | SUCCEED |
| C → A | 38.85° | 82.72 % | **4** | FAIL |

A = `nac.m1271742202lc` (29.95°), B = `nac.m1335207975rc` (69.76°), C = `nac.m1452560468lc` (68.80°).

Seven candidate causes were eliminated by measurement. Illumination is the only enumerated
candidate left standing, and **D-036 refuses to call it the cause**, for a structural reason:

> Across three frames, *large Δincidence* and *the pairing involves frame A* are **the same
> partition**. A is the only low-incidence frame and it is in both failing edges.

**REAL-DATA-04's question:** *can frame identity and illumination be separated?*

One more low-incidence frame **D** breaks the partition, because D↔A is then a
**low-Δincidence pair that does contain frame A**, and D↔B is a **high-Δincidence pair that
does not**.

## 2. The decision table — FROZEN BEFORE THE DATA EXISTS

| D↔A | D↔B | conclusion |
|---|---|---|
| **succeeds** | **fails** | **illumination strongly supported** — Δincidence tracks the outcome with frame A held fixed on the succeeding side |
| **fails** | **succeeds** | **illumination refuted; frame identity survives** — the surviving candidate of D-036 / REAL-DATA-03 §15.3 is eliminated |
| **fails** | **fails** | **causal attribution UNRESOLVED** — consistent with frame identity, with an unmeasured third factor, or with an acquisition defect |
| **succeeds** | **succeeds** | **illumination hypothesis WEAKENED** — a ~40° Δincidence edge that works refutes the simple form of it |

This table is copied unchanged from REAL-DATA-03 §20 and `research_log.md` RL-033b. It is
**not** to be reinterpreted after the result is seen.

### 2.1 What "succeeds" means — the pre-registered criterion, unchanged

An edge **FAILS** iff `n_inliers <= 8` (D-023, the EXP-002 operating point), or no transform
is estimated. Otherwise it **passes the inlier rule**. This is the identical rule
REAL-DATA-03 applied, and it is still **applied, not validated on real data**.

**A small `fit_rmse` is NOT success.** D-003 measured `fit_rmse` at ROC AUC 0.4947 — chance —
and *inverted* in the failure regime. REAL-DATA-03's cleanest instance: A → B reported a fit
RMSE of **4.138e-13 px** for a transform independently measured to be **1614 px** wrong.
`fit_rmse` is reported and is **excluded from the decision**.

**Corroboration, applied after the decision, never to change it.** Each edge that passes the
inlier rule is additionally checked by `scripts/check_transform_against_geometry.py` against
(a) the archive corner polygon and (b) `SCALED_PIXEL_WIDTH`/`HEIGHT`, a SPICE-derived field
the matcher never saw. These *classify* a passing edge (class B vs class C) and are recorded
either way; they do not move an edge across the FAIL/pass line, because that line was fixed
before the data existed.

### 2.2 What this stage may NOT conclude

* **Not** "illumination is the cause because D↔B failed." D↔B failing on its own is exactly
  what REAL-DATA-03 already showed; only the **conjunction with D↔A succeeding** is
  informative, because only the conjunction breaks the partition.
* **Not** a registration called successful on a tiny residual (§2.1).
* **Not** an azimuth claim. `SUB_SOLAR_AZIMUTH` remains unverified in frame (RL-032b). These
  frames are illumination-varied by **incidence only**.
* **Not** a location of the real illumination cliff. Two Δincidence points do not locate a
  threshold across 38 degrees.

## 3. Acquisition requirements for frame D — FROZEN BEFORE SCREENING

Frame D must be a real LRO NAC **CDR** product satisfying, in this order:

**Hard filters** (a candidate failing any one is discarded, not weighed):

1. **Same ground point.** The tile must be cut on lon **22.033852048576282**, lat
   **20.03525252164036** — REAL-DATA-03's target, unchanged, so D's tile covers the same
   ground as A, B and C rather than a new intersection centroid.
2. **A full 4096 × 2048 tile centred on that point must fit inside the frame**, unclamped
   (REAL-DATA-03 §10 criterion 2).
3. **Incidence ≤ 75°** (D-029), subsumed by 4 but stated because it is the standing rule.
4. **Low incidence — the design requirement of this stage.**
   `incidence_D` ∈ **[9.95°, 39.95°]**, i.e. within **+10° / −20°** of A's 29.95°.
   This one filter delivers both required contrasts and is the reason the band is
   asymmetric — the upper edge is set so the design can never invert:

   | at the band edge | Δinc(D↔A) | Δinc(D↔B) | contrast |
   |---|---|---|---|
   | `incidence_D` = 39.95° | 10.00° | 29.81° | 19.81° |
   | `incidence_D` = 9.95° | 20.00° | 59.81° | 39.81° |

   So **Δinc(D↔A) ≤ 20°** and **Δinc(D↔B) ≥ 29.81°** hold for every admissible candidate,
   and Δinc(D↔B) − Δinc(D↔A) ≥ 19.81° everywhere in the band. Recorded as **D-037**.
5. **D ∉ {A, B, C}**, and D's tile must be distinct from all three by SHA-256.

**Deciding criterion** (among candidates that pass every hard filter):

6. **Minimise the maximum `Map_resolution` ratio against A, B and C.** Identical to
   REAL-DATA-03 §10 criterion 3, extended from two incumbents to three exactly as
   REAL-DATA-03 §20 pre-stated. Scale mismatch is the one axis on which this project has
   *measured* a failure (EXP-001: mare fails at 2×), so it stays the decider.

**Tie-break:** smaller `|incidence_D − incidence_A|`.

**Note on what decides what.** Illumination is a **hard filter** here rather than the
decider, because illumination is this stage's *independent variable* — the design requires a
low-incidence D or there is no experiment. Resolution remains the decider so that, among
frames that are all admissible by design, the specific frame is still not chosen on
illumination.

**If no candidate passes filter 4**, the search is widened **spatially** (a larger ODE box —
more of the archive, same criteria) and never by relaxing a criterion. If the archive holds
no admissible D at this ground point, the stage reports
**UNRESOLVED — BY DATA AVAILABILITY** and stops. It does not substitute a mid-incidence
frame and reinterpret the table.

## 3.1 AMENDMENT 1 — hard filter 1 only, forced by data availability

**Registered 2026-08-26, before one image byte of any candidate D was fetched and before
any registration was run in this stage.** Nothing about any registration outcome was known
when this was written, which is what makes it an amendment rather than a rationalisation.

**What was measured.** §3's screen was run as written, then widened spatially as §3
directs — 60 → 261 → 1021 CDR products, and a tight box at the target itself.
`[MEASURED]` `data/manifests/screen_frame_d.json`, `screen_frame_d_tightbox.json`:

| | |
|---|---|
| CDR frames intersecting the target | **17** |
| …containing it with a full 4096 × 2048 tile inside | **8** |
| …with incidence in the frozen band [9.95°, 39.95°] | **1 — frame A itself** |
| next-lowest incidence over that ground point | **43.74°** (`nac.m1182331886lc`) |

Widening the box does not change the set of 8: a tight box at the target returns the same
frames as a box 30× its area. **Frame A is the only low-incidence CDR frame over the
REAL-DATA-03 ground point.** The archive holds no frame D there, and the search space of
§3 is exhausted.

**Why the stage does not stop there.** The region is not short of low-incidence frames —
352 in Mare Serenitatis — and A and B are 45 km strips whose *tile-admissible* footprints
(the set of ground points where a full 4096 × 2048 tile fits inside the frame) intersect in
**75.09 km²**, spanning lat 19.459–20.613. The REAL-DATA-03 target is one point in that
strip, and it is the only thing that has to move.

**The amendment.** Hard filter 1 changes, and **only** hard filter 1:

| | |
|---|---|
| **was** | the tile is cut on lon 22.033852048576282, lat 20.03525252164036 |
| **now** | the tile is cut on the **centroid of the intersection of the tile-admissible footprints of A, B and D** — the same "centroid of the shared region" rule as D-033, applied to the tile-admissible region rather than the full frame so that no window is clamped |

**Unchanged by this amendment:** frames **A** and **B** themselves; the decision table (§2);
the success criterion `n_inliers <= 8` (§2.1); every §2.2 prohibition; hard filters 2–6; the
deciding criterion; the baseline (§5); the order of operations (§4); and the requirement that
overlap be confirmed independently before any registration is interpreted.

**Why the frame-identity test survives intact.** D-036's confound is *"large Δincidence" and
"the pairing involves frame A" are the same partition*. Because **A and B are the same two
products**, the amended design still splits that partition:

| edge | Δincidence | contains A? | predicted if illumination drives |
|---|---|---|---|
| **D ↔ A** | **5.97°** | **yes** | **SUCCEED** |
| **D ↔ B** | **45.78°** | no | **FAIL** |
| A ↔ B | 39.81° | yes | FAIL — control, and REAL-DATA-03 measured 4 inliers |

Frame A now appears in one predicted-**pass** edge and one known-**fail** edge. That is
exactly what the partition could not do with three frames, and it is the whole point.

**The cost of the amendment, stated rather than hidden.** Tiles A and B must be **re-cut** at
the new window. Consequences, all recorded:

1. The A ↔ B edge here is **not numerically identical** to REAL-DATA-03's A → B; it is the
   same two frames over different ground. It is therefore an **independent replication** of
   that failure, not a re-run of it — which is worth more, and is used as such.
2. REAL-DATA-03's tiles, manifests and artefacts are **not modified, moved or deleted**. New
   tiles get new `l{line0}s{sample0}` names and `acquire_real_pair.py` refuses to overwrite.
3. The new target point must be verified to clamp **no** window, in all three frames.

**What the amendment does not buy.** It does not settle whether REAL-DATA-03's *particular*
tile A was defective — only whether *frame* A is. A tile-specific defect at the old window
would survive this design and is recorded as remaining evidence debt.

## 3.2 AMENDMENT 2 — a new hard filter 1c: orientation must match

**Registered 2026-08-26, again before any image byte was fetched and before any registration
was run.** It rejects the frame that amendment 1's screen had already ranked first, which is
the direction that matters: this filter *costs* the stage its top-ranked candidate rather
than rescuing a preferred one.

**What was measured.** Authoritative named corners were pulled for the top-ranked candidate,
`nac.m1343417565rc`, and compared with every frame this project has handled.
`[MEASURED]` `data/manifests/real_frame_d_index_geometry.json`:

| pdsid | flight dir | node | `NORTH_AZIMUTH` | lines | line 0 at | lon vs sample |
|---|---|---|---|---|---|---|
| `nac.m1225876972lc` | +X | A | 268.59 | 52224 | MAX lat | decreases |
| `nac.m1271742202lc` **(A)** | −X | A | 274.77 | 52224 | MIN lat | decreases |
| `nac.m1322281266lc` | +X | A | 267.72 | 52224 | MAX lat | decreases |
| `nac.m1335207975rc` **(B)** | −X | A | 272.94 | 52224 | MIN lat | decreases |
| `nac.m1452560468lc` **(C)** | −X | A | 276.76 | 52224 | MIN lat | decreases |
| **`nac.m1343417565rc`** | **−X** | A | **86.68** | **30720** | **MAX lat** | **increases** |

Two things follow, and they are separate.

**(i) A finding about the archive, recorded as E-032.** REAL-DATA-02's rule — flight
direction **−X** ⇒ line 0 at minimum latitude, **+X** ⇒ maximum — held on five frames and
was called a "fifth independent confirmation" in REAL-DATA-03 §10. **A sixth frame breaks
it**: `nac.m1343417565rc` is −X with line 0 at *maximum* latitude. `NORTH_AZIMUTH` does not
rescue the rule either — it is ~270° for all five earlier frames regardless of which
latitude line 0 sits at, so it never had discriminating power there, and this frame's 86.68°
is the first time it varies at all. **No global rule predicts the line direction.** The
pipeline was never relying on one — `corners_from_index_geometry()` reads each product's own
PDS4 `disp:Display_Direction` and refuses the frame if it disagrees — and this is the
evidence that the per-frame reading was the right design, not an over-cautious one. The
REAL-DATA-02/03 rule is **demoted from a rule to an observed regularity with a known
counterexample**.

**(ii) The filter this stage needs.** Whatever the reason — a genuinely 180°-rotated
acquisition or differently-labelled columns — a tile cut from that frame is **rotated 180°
relative to tiles cut from A and B**. Putting that on the decisive edge would mean a D↔A
failure could be illumination, frame identity, **or orientation assignment** — and
orientation assignment is this project's own open question, **EXP-004, pre-registered and
deliberately not started**. The stage exists to separate causes, so it may not introduce a
third one into the edge that decides it.

**New hard filter 1c**, inserted after filter 1b and applied uniformly to every candidate,
in code (`orientation_signature()` in `scripts/screen_frame_d.py`):

> A candidate's `(along-track, cross-track)` orientation signature, computed from the
> **named** archive corner columns, must equal the incumbents'. The incumbents must agree
> among themselves or the screen refuses to run.

Because this needs *authoritative* corners rather than the inferred ODE ring, index geometry
is fetched for **every** admissible candidate, not only the front-runner, and the screen is
**re-run** so the ranking is produced by the script under the full filter set. The choice is
not made by picking from a list after the fact.

**Still unchanged by this amendment:** the decision table (§2), the success criterion (§2.1),
every §2.2 prohibition, the incidence band, the deciding criterion, the baseline (§5), and
the gate-before-interpretation order (§4).

## 4. Order of operations — the gate before the interpretation

1. Screen candidates from ODE metadata only (`scripts/screen_frame_d.py`). No image bytes.
2. Confirm the winner's geometry from the **authoritative** named index columns
   (`scripts/fetch_index_geometry.py`), not from the ODE ring.
3. Acquire exactly one tile (`scripts/acquire_real_pair.py --from-geometry`).
4. Image sanity (`scripts/check_real_tiles.py`).
5. **Independent overlap verification of D↔A and D↔B, `--require-confirmed`, BEFORE any
   registration is run or interpreted** (`scripts/verify_tile_overlap.py`). This exits
   non-zero unless every edge is `OVERLAP_CONFIRMED`, on archive corner geometry alone —
   no pixel is read and no matcher component is involved.
6. Only then, the **unmodified** baseline, each edge estimated **independently** from its own
   image pair.
7. Independent check of the estimated transforms against archive geometry.
8. Interpret against §2, and only §2.

## 5. Baseline configuration — nothing may be changed

Identical to REAL-DATA-03 §8, restated so a drift is visible:

| | |
|---|---|
| detector / descriptor | SIFT + RootSIFT, unmodified |
| matching | mutual nearest neighbour, ratio **0.8** |
| robust estimation | LO-RANSAC, threshold **3.0 px**, seed **0** |
| model | **affine** |
| decimation | **2×** (`nanmean` over 2×2 blocks) |
| preprocessing | 1–99 percentile stretch per image, identical rule for every tile |
| failure rule | `n_inliers <= 8` (D-023), **applied, not validated on real data** |

**No threshold, descriptor, detector, ratio, model, seed or preprocessing step may be tuned
in this stage, before or after seeing the result.** EXP-004 is **not** started here. No
learned matcher is justified here.

---

## 6. Acquisition — what was actually acquired

**Screening, metadata only.** No image bytes.
`[MEASURED]` `data/manifests/screen_frame_d.json`, `screen_frame_d_tightbox.json`,
`screen_frame_d_amended.json`, `screen_frame_d_amended2.json`.

| screen | criteria in force | products | admissible |
|---|---|---|---|
| §3 as written | original hard filter 1 (one fixed point) | 261 | **0** |
| §3, tight box at the target | same | 17 | **0** |
| amendment 1 | shared tile-admissible region | 105 | 5 |
| **amendment 1 + 2** | **+ orientation match, authoritative corners** | 105 | **1** |

The final screen's funnel, every candidate accounted for: **50** outside the incidence band,
**26** above the 75° ceiling, **1** an incumbent, **21** failing the orientation match, **6**
sharing no tile-admissible ground, **1 admissible**.

**Every candidate that could have been selected was judged on authoritative corners.** All
five amendment-1 survivors had their named index columns fetched; four were rejected by
filter 1c on those columns and one survived. The 17 rejected on the *inferred* ODE ring were
already inadmissible under amendment 1 on independent grounds, so the inference decided
nothing. `[MEASURED]` cross-checked between the two screen artefacts.

| candidate | incidence | `Map_resolution` | max ratio vs A,B,C | orientation | outcome |
|---|---|---|---|---|---|
| `nac.m1343417565rc` | 23.98° | 0.964 | **1.1275** | **(−1, +1)** | **rejected — filter 1c** |
| `nac.m1315225542lc` | 21.13° | 0.806 | 1.1576 | (−1, −1) | rejected — filter 1c |
| `nac.m1373951417lc` | 20.13° | 0.759 | 1.2292 | (−1, −1) | rejected — filter 1c |
| **`nac.m1299958135lc`** | **18.22°** | **1.071** | 1.2526 | **(+1, −1)** | **SELECTED — frame D** |
| `nac.m124423514lc` | 18.00° | 0.491 | 1.9002 | (+1, +1) | rejected — filter 1c |

The deciding criterion never had to be exercised: after the hard filters, **one** candidate
remained. That is worth stating plainly — the frame was not chosen, it was the only one left.

**Frame D:** `nac.m1299958135lc`, incidence **18.22°**, emission 1.75°, `Map_resolution`
1.071 m, 52224 × 5064, `LRO_FLIGHT_DIRECTION` −X, `ORBIT_NODE` A, `NORTH_AZIMUTH` 275.05°,
UTC start 2018-12-20. Volume `LROLRC_1038A`, `DATA/ESM3/2018354/NAC/M1299958135LC.IMG`.

**Its geometry was fetched twice, independently, and reproduces exactly.** Once inside the
five-candidate manifest and once alone (`real_frame_d_selected_index_geometry.json`): every
field identical, and the same `row_sha256`. `[MEASURED]`

**The target ground point.** Computed by `shared_tile_target()` from the three frames'
**authoritative** corners: lon **22.010350422685136**, lat **19.66625467769675** — the
centroid of the ground on which A, B and D can each centre a full 4096 × 2048 tile. It
matches the value the screen implied from the same frame's corners.

| | `line0` | lines | `sample0` | samples | target pixel (line, sample) | clamped? |
|---|---|---|---|---|---|---|
| **A** `nac.m1271742202lc` | **6413** | 4096 | **1866** | 2048 | (8460, 2890) | **no** |
| **B** `nac.m1335207975rc` | **18077** | 4096 | **1145** | 2048 | (20124, 2168) | **no** |
| **D** `nac.m1299958135lc` | **42463** | 4096 | **1693** | 2048 | (44511, 2716) | **no** |

`[MEASURED]` **No window is clamped on either axis**, which is the property amendment 1's
tile-admissible centroid exists to guarantee, and it is checked in the manifest rather than
assumed — `window_detail.fully_inside_frame` is `true` for all three.

**Provenance.** Byte ranges over HTTP 206 with the returned length and `Content-Range`
verified, SHA-256 of the bytes received, `file_size` identity exact on every label, and the
index table's `IMAGE_LINES`/`LINE_SAMPLES` checked against the PDS4 label for all three.

| | byte start + count | SHA-256 (first 16) |
|---|---|---|
| A | 64955928 + 41484288 | `ea54552687d226a8` |
| B | 183088920 + 41484288 | `4df468905a75008e` |
| D | 430070328 + 41484288 | `40ec585fec7558f8` |

**Licence:** NASA PDS public domain. Credit **NASA/GSFC/Arizona State University**.

**Nothing was overwritten.** New manifest (`real_quad_d_geo_manifest.json`), new tiles named
`{pdsid}.geo.l{line0}s{sample0}.tile.npy`. REAL-DATA-03's tiles, manifests and artefacts are
untouched and still on disk.

## 7. Image sanity

`scripts/check_real_tiles.py`, unchanged.
`[MEASURED]` `experiments/REAL-DATA-04/tile_sanity_real_quad_d_geo.json`.

| | shape | finite | DN p1 / med / p99 | min / max | unique | lag-1 autocorr | byte-swapped | zero frac | SHA vs manifest | **verdict** |
|---|---|---|---|---|---|---|---|---|---|---|
| **A** | 4096×2048 | 1.0000 | 1300 / **1390** / 1657 | — | 1795 | **0.9640** | 0.6157 | 0.0 | ✓ | **PASS** |
| **B** | 4096×2048 | 1.0000 | 284 / **468** / 741 | −34 / 2298 | 1706 | **0.9358** | 0.6727 | 0.0 | ✓ | **PASS** |
| **D** | 4096×2048 | 1.0000 | 1616 / **1718** / 2145 | 1044 / 4088 | 1900 | **0.9601** | 0.5095 | 0.0 | ✓ | **PASS** |

All three pass. `finite_fraction` is exactly 1.0000 for all three, so no `NaN` entered any
statistic. Every decode-correctness margin is large (0.26–0.45 against the 0.10
`DECODE_EVIDENCE_MARGIN` of E-024); none is `inconclusive`.

**D is the brightest tile in the project** — median DN 1718 against A's 1390 and B's 468 —
which is what an 18.22° incidence should look like, and is a weak independent check that the
archive's incidence value describes the pixels actually delivered.

## 8. Independent overlap verification — the gate

Run **before** any registration, in a separate command, by
`scripts/verify_tile_overlap.py --require-confirmed`, which exits non-zero unless every edge
is `OVERLAP_CONFIRMED`. Method, criteria and uncertainty are REAL-DATA-02's, **unchanged**:
named archive corners, corner naming from each product's own PDS4 `disp:Display_Direction`,
bilinear ground map, one common local plane, exact convex clip, 4000 Monte Carlo draws over
the ±0.005° corner quantisation. CONFIRMED requires p5 of the worse-covered tile's shared
fraction ≥ 0.50.

`[MEASURED]` `experiments/REAL-DATA-04/overlap_real_data_04.json`.

| edge | Δinc | area 1 | area 2 | **∩** | IoU | **min fraction** | p5–p95 | centres apart | class |
|---|---|---|---|---|---|---|---|---|---|
| **A ↔ B** *(control)* | 39.81° | 7.052 | 6.958 | **6.9019** | 0.9710 | **97.87 %** | 89.87–97.16 % | 1 m | **CONFIRMED** |
| **D ↔ A** *(decisive)* | **11.73°** | 7.052 | 9.891 | **7.0520** | 0.7130 | **71.30 %** | 68.01–74.88 % | 1 m | **CONFIRMED** |
| **D ↔ B** *(decisive)* | **51.54°** | 6.958 | 9.891 | **6.9581** | 0.7035 | **70.35 %** | 67.38–73.56 % | 1 m | **CONFIRMED** |

Areas in km². **All three CONFIRMED; the gate passed and the stage was allowed to proceed.**

Three things in this table matter for §11 and are recorded here, before any registration
number was seen:

1. **The two decisive edges are overlap-matched to within 0.95 percentage points** — 71.30 %
   vs 70.35 %, p5 68.01 % vs 67.38 %. Whatever separates their outcomes, it is not how much
   ground they share.
2. **The most-overlapping edge is a control that is expected to fail.** A ↔ B shares 97.87 %.
3. **D's tile covers more ground** — 9.891 km² against 7.052 — because D's sampling is
   coarser, so A's and B's tiles sit entirely inside D's footprint (`of A 100.00 %`,
   `of B 100.00 %`). The 71 % figure is the fraction of *D's* tile that is shared.

`[INTERPRETATION]` The D-edge p5 bounds (0.680, 0.674) sit **below** the 0.757 worst case of
the synthetic regime this project's matcher was measured in. That is recorded as a limitation
of the regime, not a defect: it makes a *success* on those edges harder to obtain, not easier.

## 9. Baseline configuration — nothing was changed

Exactly §5, and identical to REAL-DATA-03 §8: SIFT + RootSIFT unmodified, mutual nearest
neighbour with ratio 0.8, LO-RANSAC at threshold **3.0 px** and seed **0**, **affine** model,
**2×** decimation, 1–99 percentile stretch per image. The constants are restated in
`register_real_triplet.py` so a future edit to one script cannot silently make the two
experiments incomparable. **No parameter was touched, before or after the result was seen.**

## 10. Registration results

`[MEASURED]` `experiments/REAL-DATA-04/loop_closure_real_data_04.json`. Tiles decimated to
2048 × 1024. Each edge estimated **independently**, from its own image pair, asserted in code
by `_assert_independent()`.

| edge | Δinc | role | keypoints | putative | **inliers** | ratio | fit RMSE (px) | coverage gap | occupancy | `n_inliers<=8` | **outcome** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A → B | 39.81° | control | 10794 / 11633 | 50 | **7** | 0.1400 | 1.1053 | 0.4604 | 0.062 | **True** | **FAIL** |
| B → D | **51.54°** | **decisive** | 11633 / 12593 | 29 | **3** | 0.1034 | **1.885e-13** | 0.4268 | 0.047 | **True** | **FAIL** |
| **D → A** | **11.73°** | **decisive** | 12593 / 10794 | **1759** | **1656** | **0.9414** | 0.8779 | **0.1033** | **1.000** | False | **SUCCEED** |

**Estimated linear parts:**

| edge | σ₁ | σ₂ | rotation |
|---|---|---|---|
| A → B | 1.0242 | 0.9463 | +2.70° |
| B → D | **1.8057** | **0.1846** | **−105.23°** |
| **D → A** | **1.1672** | **1.1340** | **+0.28°** |

### 10.1 The result the stage was built to produce

**D ↔ A succeeds. D ↔ B fails.** 1656 inliers against 3, on tiles whose confirmed shared
ground differs by less than one percentage point, through identical code, at the same seed.

**D → A's occupancy is 1.000** — every cell of the coverage grid contains a correspondence,
the first time that has happened on real data in this project. Coverage gap 0.1033.

### 10.2 `fit_rmse` behaves exactly as D-003 says it does, again

**B → D reports a fit RMSE of 1.885e-13 px** — for a transform §11.2 measures to be **797 px**
wrong, with a recovered anisotropy of 1.81 / 0.18 where the archive predicts 0.84 / 0.87.
Meanwhile the **succeeding** edge D → A reports **0.878 px**, four thousand billion times
*worse*. The metric is inverted in the failure regime, on real data, for the second stage
running. **Had `fit_rmse` been the criterion, this stage would have concluded the exact
opposite.**

### 10.3 The control replicates REAL-DATA-03's failure at a different window

A → B fails again — 7 inliers, `n_inliers <= 8` — at a ground window **11 542 lines**
(≈ 10.8 km) away from REAL-DATA-03's. Same two frames, different ground, same outcome. This
is an **independent replication**, not a re-run: the tiles are different pixels.

The two are not numerically identical and should not be. REAL-DATA-03's A → B gave 32
putative / 4 inliers and a transform **1614 px** wrong; this one gives 50 / 7 and a transform
whose corner-polygon disagreement (92.2 px) the bound cannot resolve, though the sharper
`SCALED_PIXEL` test puts its scale 6.36 % wrong. **7 is close to the threshold of 8**, and
§11.4 addresses what that does and does not put at risk.

## 11. What the evidence eliminates

Every candidate below is eliminated by a **measurement** against the succeeding edge, and —
where REAL-DATA-03's edges are used — the argument is stated **across both stages**, because a
factor that predicts the outcome in one stage and anti-predicts it in the other predicts
nothing.

**The six real edges now measured**, across 5 frames, 2 ground windows and 2 stages:

| stage | edge | Δinc | overlap | inliers | outcome |
|---|---|---|---|---|---|
| RD-03 | B → C | **0.96°** | 85.00 % | **5365** | **SUCCEED** |
| **RD-04** | **D → A** | **11.73°** | 71.30 % | **1656** | **SUCCEED** |
| RD-03 | C → A | 38.85° | 82.72 % | 4 | FAIL |
| RD-03 | A → B | 39.81° | 97.12 % | 4 | FAIL |
| **RD-04** | **A → B** | 39.81° | 97.87 % | 7 | FAIL |
| **RD-04** | **B → D** | **51.54°** | 70.35 % | 3 | FAIL |

**Δincidence separates all six edges, with a gap between 11.73° and 38.85°.**

### 11.1 The eliminations

| candidate | eliminated because |
|---|---|
| **frame identity** | **§11.3, in full — this is the stage's point** |
| tiles do not overlap | 71.30 % and 70.35 % on the decisive edges, CONFIRMED without the matcher, p5 ≥ 0.674 |
| **amount of overlap** | the two decisive edges are matched to **0.95 pp** and diverge by 1656 inliers against 3. Across both stages the **most**-overlapping edge fails (97.9 %, 97.1 %) and the succeeding edges are the least-overlapping (71.3 %, 85.0 %) |
| mare texture poverty (D-026) | D → A found 1759 putative and 1656 inliers on the same mare, at a *new* window |
| 2× decimation | identical on all three edges |
| resolution mismatch | the succeeding D → A has ratio **1.1479**, the failing B → D **1.1667** — 1.6 % apart, against a 550-fold difference in inliers. And A ↔ B has the **smallest** ratio in the project (1.0163) and fails **twice**, at two different windows |
| relief displacement / parallax (Δemission) | **anti-correlated across the two stages**: RD-04's succeeding edge has the *smallest* Δemission of its three (0.01°) while RD-03's succeeding edge had the *largest* of its three (0.55°), and RD-03's failing C → A had the smallest (0.02°). Δemission takes both extremes on both sides |
| time between acquisitions | RD-04 alone is monotonic (11 months succeeds; 14 and 24 fail) — but RD-03's **45-month** B → C succeeds while its 24-month A → B fails. Not monotonic across stages |
| tile-window uncertainty | no window is clamped on either axis in either stage, and the succeeding edge has *less* confirmed overlap than the failing control |
| frame orientation / EXP-004 | excluded **by design before acquisition**: hard filter 1c requires D to share A's and B's orientation signature (+1, −1). Estimated rotation on the succeeding edge is **+0.28°** |
| affine model limitation | same model on all three edges |
| a pipeline defect | D → A is a successful **cross-frame** registration at inlier ratio 0.9414 and occupancy 1.000 |
| a defective tile A | A is in the **succeeding** edge D → A — §11.3 |
| a defective tile D | D is in the succeeding edge D → A and the failing B → D |
| a defective tile B | B is in RD-03's **succeeding** edge B → C |

### 11.2 The estimated transforms against archive geometry

`[MEASURED]` `experiments/REAL-DATA-04/transform_vs_geometry_real_data_04.json`. Predicts
where each pixel of one tile lands in another **from archive corner geometry alone** — no
image data, no matcher output — then measures the endpoint disagreement, with the corner
quantisation propagated by Monte Carlo. **A bound, not a ground truth**: it discriminates at
the scale of ~100 px and certifies nothing finer.

| edge | median disagreement | p5–p95 | discrimination floor | excess | verdict |
|---|---|---|---|---|---|
| A → B | 92.2 px | 41–165 | 102.9 px | **0.90×** | CONSISTENT *(the bound cannot resolve it)* |
| **B → D** | **797.5 px** | 777–823 | 82.7 px | **9.64×** | **INCONSISTENT** |
| **D → A** | **56.3 px** | 25–124 | 105.6 px | **0.53×** | **CONSISTENT** |

The sharper test uses `SCALED_PIXEL_WIDTH` / `SCALED_PIXEL_HEIGHT` — derived by the archive
from SPICE, **never seen by the matcher, and not an input to the corner polygon either**:

| edge | predicted scales | estimated singular values | relative error | tolerance | agrees |
|---|---|---|---|---|---|
| A → B | 1.01053 / 1.02273 | 0.94627 / 1.02422 | **6.36 % / 0.15 %** | 1.70 % | **no** |
| B → D | 0.83810 / 0.87156 | 0.18458 / 1.80568 | **77.98 % / 107.18 %** | 1.70 % | **no** |
| **D → A** | **1.13542 / 1.16667** | **1.13397 / 1.16717** | **0.13 % / 0.04 %** | 1.67 % | **yes** |

`[INTERPRETATION]` **D → A recovers a scale that an independent SPICE-derived archive field
predicts to 0.04 % and 0.13 %**, inside that field's own 1.67 % quantisation — and it is the
only edge in either stage whose corner-polygon disagreement falls **below** the discrimination
floor (0.53×; REAL-DATA-03's best was 1.55×). B → D misses by 78–107 % and is independently
confirmed catastrophically wrong. This is the sharpest independent evidence the project has
produced, and it points the same way as the inlier counts.

### 11.3 Frame identity is refuted — the partition is broken

D-036's objection to REAL-DATA-03 was structural: *large Δincidence* and *the pairing involves
frame A* were the same partition. Across the six edges now measured, **every frame appears on
both sides**:

| frame | incidence | succeeding edges | failing edges |
|---|---|---|---|
| **A** `m1271742202lc` | 29.95° | **D → A** | A → B *(×2, two windows)*, C → A |
| **B** `m1335207975rc` | 69.76° | **B → C** | A → B *(×2)*, B → D |
| **C** `m1452560468lc` | 68.80° | **B → C** | C → A |
| **D** `m1299958135lc` | 18.22° | **D → A** | B → D |

**No frame's presence predicts the outcome. Δincidence does, on all six edges.**

The specific claim REAL-DATA-03 could not make is now available: **frame A is not defective.**
It produced 1656 inliers at ratio 0.9414 and occupancy 1.000 against a frame 11.73° away in
incidence, having produced 4 and 7 against frames ~40° away. Its keypoint count is comparable
in both regimes — 9538, 10794 and 12593 across the project's tiles — so the **detector** is
not failing; what fails is **descriptor matching across illumination**.

**The mirror-image confound is checked too.** Within REAL-DATA-04's triplet *alone*, B is the
only high-incidence frame and is in both failing edges — the same structure that blocked
REAL-DATA-03. It does not survive the join, because REAL-DATA-03's **succeeding** edge B → C
contains B. Neither triplet alone would settle this; the two together do.

### 11.4 The one number close to a threshold, and what it does not put at risk

A → B returned **7** inliers against a failure rule of `<= 8`. That is close, and it is
recorded as close rather than rounded away.

**It does not affect this stage's conclusion**, for a reason that does not depend on the
threshold at all: the decisive comparison is **D → A (1656) against B → D (3)**, separated by
a factor of 552. **No threshold anywhere between 4 and 1655 changes which of those two
passes.** A → B is a *control*, not a decisive edge — its role is to replicate REAL-DATA-03's
failure at a new window, and 7 inliers with inlier ratio 0.1400, coverage gap 0.4604,
occupancy 0.062 and a scale 6.36 % wrong against `SCALED_PIXEL` is that replication whichever
side of 8 it sits on.

**The rule remains applied, not validated on real data.** It has now flagged 4 of 4 failing
real edges and passed 2 of 2 succeeding ones — 6 for 6 across two stages — and six edges
validate nothing.

## 12. Loop closure on real data, a second time

`[MEASURED]` `experiments/REAL-DATA-04/loop_closure_real_data_04.json`.

```
edges with a transform: 3 / 3
LOOP CLOSURE RESIDUAL: 943.752 px   (median over a 2048 x 1024 grid)
```

Every edge was estimated independently from its own image pair; the closing edge was never
derived as `(T_BD ∘ T_AB)⁻¹` (E-021), and the independence is **asserted in code**.

Verdict, evaluated on the **weakest** edge (B → D, 3 inliers): **REJECTED / none** — too few
correspondences, loop closure failing at 943.75 px, clustered correspondences.
**Classification C.**

`[INTERPRETATION]` **What this establishes:** loop closure ran on real data a second time,
with two broken legs, and again did **not** manufacture a small residual. ADR-0011's reversal
condition — *"real-data evidence that per-edge errors are correlated in a way that cancels
around a loop"* — is **not** triggered.

**What it does not establish:** its discriminating power. That still needs **three
successful** real edges, and this triplet has one. The debt carried from REAL-DATA-03 (D-011)
is **not** discharged.

## 13. Errors and failures during this stage

Preserved, not deleted. Every artefact from a failed step is on disk.

**F-1 — the pre-registered acquisition was impossible.** §3's screen returned **0** admissible
frames, twice, and exited non-zero as designed. Both artefacts are kept
(`screen_frame_d.json`, `screen_frame_d_tightbox.json`). Resolution: **amendment 1** (§3.1),
registered before any image byte was fetched.

**F-2 — E-032: the flight-direction rule for line 0 is not a rule.** The top-ranked candidate
`nac.m1343417565rc` is `−X` with line 0 at *maximum* latitude; `nac.m124423514lc` is `+X` with
line 0 at *minimum*. Two counterexamples in 10 frames to a regularity REAL-DATA-03 §10 called
a *"fifth independent confirmation"*. `NORTH_AZIMUTH` was quoted as its cross-check and had
**no discriminating power** in that sample; what it actually separates, 10 / 10, is the
**cross-track** sense. **No pipeline change was needed** — `corners_from_index_geometry()`
always read each product's own `disp:Display_Direction` — so the prose is corrected, not the
code. Full entry in `ERROR_LEDGER.md`. Resolution: **amendment 2** (§3.2), a new hard filter
that **rejected the stage's own top-ranked candidate**.

**F-3 — the overlap gate refused to run, correctly.** The first invocation passed the
five-candidate geometry manifest and exited on:

```
no stored PDS4 label for nac.m124423514lc under data/metadata/; the corner naming
cannot be verified for it and is not assumed
```

The gate builds frames for **every** product in the geometry it is handed, and refuses to
assume a corner convention for one whose label is not on disk. **Working as designed**
(REAL-DATA-02 §6.5). Fix: a D-only authoritative manifest, fetched from the archive rather
than subsetted by hand — which also produced the independent-refetch reproducibility check in
§6. No result was affected: this happened **before** any registration ran.

## 14. Files changed

**New scripts** `scripts/screen_frame_d.py` — the frame-D screen, with the criteria executed
rather than described, and every rejected candidate and its reason written to the artefact.

**Extended, additively** (every prior invocation behaves identically)
`scripts/acquire_real_pair.py` (`--target-shared-tile`) ·
`scripts/register_real_triplet.py` (`--stage`, `--overlap-note`, `--overlap-artefact`,
replacing three REAL-DATA-03 strings that were hard-coded into the report and the figure)

**Modified source** `src/siim/ingest/footprint.py` — `tile_admissible_polygon()` and
`shared_tile_target()` added; nothing existing changed

**New tests** `tests/test_screen_frame_d.py` (12) · `tests/test_ingest_footprint.py` (+10)

**New data** `data/manifests/` — `screen_frame_d.json`, `screen_frame_d_tightbox.json`,
`screen_frame_d_amended.json`, `screen_frame_d_amended2.json`,
`real_frame_d_index_geometry.json`, `real_frame_d_candidates_index_geometry.json`,
`real_frame_d_selected_index_geometry.json`, `real_quad_d_geo_manifest.json` · three tiles
under `data/processed/mare_serenitatis/` · one PDS4 label under `data/metadata/`

**New artefacts** `experiments/REAL-DATA-04/` — `tile_sanity_real_quad_d_geo.json`,
`overlap_real_data_04.json`, `loop_closure_real_data_04.json`,
`transform_vs_geometry_real_data_04.json`, and their figures

**Documentation** this file · `ERROR_LEDGER.md` (E-032) · `DECISION_LEDGER.md` (D-037, D-038,
D-039; D-036 closed) · `research_log.md` (RL-035; RL-033b closed) · `STAGE-INDEX.md` ·
`STAGE_HISTORY.md` · `stages/README.md` · `README.md`

**No ADR was created.** ADR-0011 is **not** amended: its reversal condition was not met, and a
second exercise on real data is not the validation that would change it.

## 15. Decision

**Q1. Did the images independently overlap?** **Yes.** All three edges `OVERLAP_CONFIRMED`
before any registration was interpreted — 97.87 %, 71.30 %, 70.35 %, with pessimistic bounds
89.87 %, 68.01 %, 67.38 %. Evidence: archive corner geometry, no pixel read, no matcher
component. The two decisive edges are matched to **0.95 pp**.

**Q2. Did the unchanged baseline find a registration?** **On the edge the design predicted.**
D → A: **1656 inliers**, ratio 0.9414, occupancy 1.000. B → D: **3**, REJECTED. A → B: **7**,
REJECTED.

**Q3. Is the succeeding registration independently verified?** **No — corroborated, not
verified.** D → A's recovered scale matches SPICE-derived `SCALED_PIXEL` to **0.04 % / 0.13 %**
inside a 1.67 % tolerance, and its corner-polygon disagreement (56.3 px) is **below** the
105.6 px discrimination floor — the only edge in either stage to clear that bound. There is no
ground truth. **Class B.**

**Q4. Does the pre-registered decision table apply?** **Yes — its first row, unmodified.**
*D↔A succeeds and D↔B fails* → **illumination strongly supported**.

**Q5. Is frame identity refuted?** **Yes.** Across six real edges every frame appears in both
a succeeding and a failing edge, and Δincidence separates all six. Frame A specifically is
**not** defective. **D-036's blocking objection is discharged.**

**Q6. Can illumination now be called the cause?** **It is now the supported cause of these
failures, stated with its scope.** The evidence: two successes at Δinc 0.96° and 11.73°, four
failures at 38.85°, 39.81°, 39.81° and 51.54°; every alternative in §11.1 eliminated by
measurement across two stages; the succeeding edge corroborated by an archive field the
matcher never saw. **The scope is Δ*incidence*, on mare terrain, in one region, with one
instrument, over five frames and two ground windows — and it is not an azimuth result.**

**Q7. Does loop closure support anything here?** **No, and it cannot.** 943.75 px, correctly
reflecting two broken legs. It ran on real data a second time and again did not manufacture a
small residual, but a loop with two broken legs corroborates nothing.

## 16. What remains unknown

1. **Where the cliff is.** Bracketed between **11.73°** (works) and **38.85°** (fails) — a
   27° window, narrowed from REAL-DATA-03's 38°, and still not a threshold.
2. **Δazimuth for any real pair.** `SUB_SOLAR_AZIMUTH` is in the index table and was **not
   used**; its frame is unverified (RL-032b). Every real result so far is **incidence only**,
   and EXP-003's synthetic Δaz 21–27° cliff is still **not** confirmed by any real
   measurement — it is a different axis.
3. **Whether D → A is correct**, as opposed to strongly corroborated. No ground truth exists.
4. **Loop closure's discriminating power on real data.** Still needs three successful edges.
5. **`n_inliers <= 8` on real data.** 6 for 6 across two stages; still applied, not validated.
6. **Generalisation.** One region, one terrain type, one instrument, five frames, two windows.
7. **Whether REAL-DATA-03's particular tile A was defective.** This stage clears *frame* A at
   a different window; a defect confined to the old window would survive it.
8. **Why** matching fails across incidence — the mechanism. Δincidence is now an established
   predictor; nothing here measures shadow geometry, gradient reversal, or which stage of the
   pipeline breaks first.

## 17. Evidence debt

| Debt | Owner | Note |
|---|---|---|
| Locate the real illumination cliff | a later stage | bracketed to 11.73°–38.85° |
| A real **azimuth**-controlled pair | a later stage | would be the project's first; needs the sub-solar point derived from `UTC_start_time`, or `SUB_SOLAR_AZIMUTH`'s frame verified |
| Loop closure's power on real data | a later stage | needs three mutually low-Δinc frames |
| `n_inliers <= 8` validated on real data | a later stage | needs many real pairs with known outcomes |
| The mechanism behind the Δincidence failure | **EXP-004 / a later stage** | now, for the first time, a justified question |
| Incidence ceiling in `find_illumination_pairs()` | later | **D-029**, still recorded-not-implemented |
| A ground truth of any kind for real NAC | unresolved | none exists for these products |
| Chandrayaan-2 / multi-modal | blocked | ISSDC authentication |

## 18. Integrity checklist

| | |
|---|---|
| Decision rule fixed before the data existed | **Yes** — §2, REAL-DATA-03 §20's table verbatim |
| Success criterion unchanged from the previous stage | **Yes** — `n_inliers <= 8`, D-023 |
| `fit_rmse` excluded from the decision | **Yes** — and §10.2 shows it would have inverted the conclusion |
| Both amendments registered before any image byte of D was fetched | **Yes** — §3.1, §3.2; no registration had been run |
| Amendment 2 cost the stage its top-ranked candidate | **Yes** — it rejected `nac.m1343417565rc` |
| Overlap established before registration was interpreted | **Yes** — `--require-confirmed`, separate command, exits non-zero |
| Overlap evidence independent of the matcher | **Yes** — archive geometry, no pixel read |
| Baseline unmodified | **Yes** — detector, descriptor, matching, RANSAC, threshold, seed, model, decimation, preprocessing |
| No result cherry-picked | **Yes** — all three edges reported; the failing control is reported at 7, next to a threshold of 8 |
| Frame D selected on pre-stated criteria, in code | **Yes** — §6; after the hard filters exactly one candidate remained |
| Loop edges independently estimated | **Yes** — asserted in code (`_assert_independent`) |
| Failed attempts preserved | **Yes** — §13, with the two empty screens and the gate's exact refusal message |
| Nothing overwritten | **Yes** — every output is a new path; REAL-DATA-03's tiles are untouched |
| No prior stage report rewritten | **Yes** — REAL-DATA-01/02/03 stand as written; E-032 corrects a *claim*, in the ledger, not the report |
| Every quoted number traced to an artefact | **Yes** — `experiments/REAL-DATA-04/*.json`, `data/manifests/*.json` |
| Hypotheses eliminated only by evidence | **Yes** — §11.1, each with its measurement, argued across both stages |
| The conclusion stated with its scope | **Yes** — §15 Q6: Δ*incidence*, mare, one region, one instrument |
| No azimuth claim | **Yes** — §16.2 |
| REAL DATA distinguished from SYNTHETIC | **Yes** — in the artefacts, the figure titles and the runner's output |
| Licence and credit recorded | **Yes** — NASA PDS public domain; **NASA/GSFC/Arizona State University** |

## 19. Commands executed

```bash
# -- screening, METADATA ONLY, no image bytes --
python scripts/screen_frame_d.py --out screen_frame_d.json                 # 0 admissible
python scripts/screen_frame_d.py --minlat 20.02 --maxlat 20.05 \
       --westernlon 22.02 --easternlon 22.05 --limit 2000 \
       --out screen_frame_d_tightbox.json                                  # 0 admissible
# -> AMENDMENT 1 registered here, before any image byte was fetched
python scripts/screen_frame_d.py --shared-target --minlat 19.0 --maxlat 21.1 \
       --westernlon 21.8 --easternlon 22.3 --limit 5000 \
       --incumbent-frames nac.m1271742202lc,nac.m1335207975rc \
       --out screen_frame_d_amended.json                                   # 5 admissible

# -- authoritative corners for EVERY admissible candidate, not just the leader --
python scripts/fetch_index_geometry.py --pdsids nac.m1343417565rc \
       --out real_frame_d_index_geometry.json
python scripts/fetch_index_geometry.py \
       --pdsids nac.m1343417565rc,nac.m1315225542lc,nac.m1373951417lc,\
nac.m1299958135lc,nac.m124423514lc \
       --out real_frame_d_candidates_index_geometry.json
# -> E-032 found; AMENDMENT 2 registered here, still before any image byte
python scripts/screen_frame_d.py --shared-target --minlat 19.0 --maxlat 21.1 \
       --westernlon 21.8 --easternlon 22.3 --limit 5000 \
       --incumbent-frames nac.m1271742202lc,nac.m1335207975rc \
       --candidate-geometry real_frame_d_candidates_index_geometry.json \
       --out screen_frame_d_amended2.json                    # 1 admissible: frame D

# -- acquisition: one command, three tiles, one authoritative ground point --
python scripts/acquire_real_pair.py \
       --from-geometry real_pair_index_geometry.json,\
real_frame_d_candidates_index_geometry.json \
       --products nac.m1271742202lc,nac.m1335207975rc,nac.m1299958135lc \
       --lines 4096 --samples 2048 --target-shared-tile \
       --role real_data_04_illumination_vs_frame_identity \
       --out real_quad_d_geo_manifest.json

# -- sanity --
python scripts/check_real_tiles.py --manifest real_quad_d_geo_manifest.json \
       --outdir REAL-DATA-04

# -- THE GATE, before any registration was run or interpreted --
python scripts/fetch_index_geometry.py --pdsids nac.m1299958135lc \
       --out real_frame_d_selected_index_geometry.json   # after F-3; also a re-fetch check
python scripts/verify_tile_overlap.py --manifest real_quad_d_geo_manifest.json \
       --case real_data_04 \
       --extra-geometry real_frame_d_selected_index_geometry.json \
       --outdir REAL-DATA-04 --out overlap_real_data_04.json \
       --figure tile_overlap_real_data_04.png --require-confirmed

# -- the UNMODIFIED baseline, three independently estimated edges --
python scripts/register_real_triplet.py --manifest real_quad_d_geo_manifest.json \
       --downsample 2 --outdir REAL-DATA-04 --tag real_data_04 \
       --stage REAL-DATA-04 \
       --overlap-note "overlap CONFIRMED independently of the matcher: 97.9% / 70.4% / 71.3%" \
       --overlap-artefact experiments/REAL-DATA-04/overlap_real_data_04.json

# -- independent check of the estimated transforms --
python scripts/check_transform_against_geometry.py \
       --manifest real_quad_d_geo_manifest.json \
       --registration experiments/REAL-DATA-04/loop_closure_real_data_04.json \
       --extra-geometry real_frame_d_selected_index_geometry.json \
       --downsample 2 --outdir REAL-DATA-04 \
       --out transform_vs_geometry_real_data_04.json

# -- full suite --
python -m pytest tests/
```

Commands that failed are in §13, with their exact messages.

## 20. Exact next action — and it is not another experiment

**The causal question this stage was opened to answer is answered.** Δincidence, not frame
identity, drives the failure. Under the standing constraint that REAL-DATA-04 is the final
high-value causal experiment, **scientific expansion stops here** and the work switches to
demo engineering for **September 2**.

```bash
# The next action is DEMO_TRACK, not a new stage.
#
# What REAL-DATA-04 hands the demo, and it is a lot:
#   * a REAL, CORROBORATED registration on real LRO NAC -- D -> A, 1656 inliers,
#     inlier ratio 0.9414, coverage occupancy 1.000, recovered scale matching a
#     SPICE-derived archive field the matcher never saw to 0.04 % / 0.13 %;
#   * a REAL failure next to it -- B -> D, 3 inliers -- with the cause identified
#     by measurement rather than asserted;
#   * a verdict engine that rejects the failure for the right reasons and does
#     not reward its 1.885e-13 px fit RMSE;
#   * an overlap gate that ran before the result and would have stopped the demo
#     from showing an uninterpretable pair.
#
# That is a demo about a system that KNOWS WHEN IT IS WRONG, on real data,
# which is a stronger story than a system that always succeeds.
```

**EXP-004 remains pre-registered and NOT started.** It is, for the first time, *pointed at a
real question* — §16.8, the mechanism behind the Δincidence failure — but nothing in this
stage justifies starting it before the demo, and the standing constraint says it does not.

**No matcher change, no tuning, no learned component is justified by this stage.** What it
established is a *cause*, not a *fix*, and the correct order is: demo first.
