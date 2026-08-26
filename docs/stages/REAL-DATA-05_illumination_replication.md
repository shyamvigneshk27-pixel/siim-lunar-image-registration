# REAL-DATA-05 — Does the illumination result replicate on a second low-incidence frame?

**Stage ID:** REAL-DATA-05
**Name:** Replication of the REAL-DATA-04 Δincidence result with an independent low-incidence frame E
**Status:** **CLOSED — UNRESOLVED, BY DATA AVAILABILITY (§12).** The screen was run as written and returned **zero** admissible frames at every tier and rung. **No image byte was fetched. No registration was run. The §6 decision table was never reached.**
*(Only this Status line was edited after the stage ran; §1–§11 are the frozen pre-registration and are unchanged — see §12.6 for the single pre-acquisition documentation correction.)*
**Date registered:** 2026-08-26 · **Date closed:** 2026-08-26 · **Depends on:** REAL-DATA-04, REAL-DATA-03, REAL-DATA-02, REAL-DATA-01
**Classification:** RESEARCH-RELEVANT. **Replication experiment, not algorithm development.**

> Standing under integrity rules 8 and 10 is unchanged. No multi-modal claim. No Chandrayaan-2
> data. **No Sun-azimuth claim.** Nothing is compared against synthetic ground truth, and no
> ground truth exists for these products.
>
> **This stage develops nothing.** The matcher, descriptor, detector, ratio, RANSAC threshold,
> seed, model, decimation, preprocessing and verdict criteria are all frozen at REAL-DATA-04's
> values. EXP-004 is **not** started. No illumination normalisation is added. No threshold is
> tuned. No match is removed by hand. The only new code permitted is two additive selection
> filters in the screening script (§7.1), which read metadata and touch no image and no matcher.

---

## 1. Why this stage exists

REAL-DATA-04 concluded — from a pre-registered decision table, on its first row, unmodified —
that Δ**incidence** is the driver of the real-data registration failures (D-040). The
conclusion is sound as far as it goes, and §2 states exactly how far that is.

It rests on **two** succeeding real edges in the entire project:

| stage | succeeding edge | Δinc | inliers |
|---|---|---|---|
| REAL-DATA-03 | B → C | 0.96° | 5365 |
| REAL-DATA-04 | D → A | 11.73° | 1656 |

and the whole of the frame-identity refutation turns on **D → A alone** — it is the only edge
in the project in which frame A or frame D has ever succeeded. **n = 1 for the decisive
observation.** D-040's scope sentence says "five frames, two windows"; it does not say the
effect has been shown reproducible with a *different* low-incidence frame, because it has not.

**The question this stage asks, and the only one:**

> **Does registration success/failure track illumination difference when the same ground
> region and the unchanged baseline matcher are used, across more than one low-incidence
> frame?**

If a second, independent low-incidence frame E reproduces D's pattern — passing against A,
failing against B — the effect is reproducible rather than a property of frame D. If it does
not, D-040 is over-stated and must be reduced.

## 2. What REAL-DATA-04 established, and what it did not — the audit this stage answers

`[MEASURED]`, all from `experiments/REAL-DATA-04/*.json` and
`experiments/REAL-DATA-03/loop_closure_triplet.json`. Nothing below was recomputed.

**Established.** Across six real edges, no frame's presence predicts the outcome (every frame
appears in both a succeeding and a failing edge), and Δincidence separates all six with a gap
between 11.73° and 38.85°. The two decisive REAL-DATA-04 edges were overlap-matched to
**0.95 pp** before any registration ran and differ by a factor of **552** in inliers.

**Not established — the replication debt.**

1. **REAL-DATA-04 alone does not break the frame-identity confound.** Inside its own triplet
   {A, B, D}, frame **B** is in both failing edges and in no succeeding edge — the identical
   structure that blocked REAL-DATA-03, mirrored from A onto B. The break comes only from
   **joining** REAL-DATA-03's B → C success, which is a **different ground window** and a
   **different stage**. The refutation is a cross-stage join, not a within-experiment result.
2. **One succeeding edge carries two frames.** A's and D's entire non-defectiveness rests on
   the single D → A run.
3. **Δphase is not separated from Δincidence and cannot be** at these emission angles (§6.2).
4. **Δazimuth was never controlled** (§6.2) — although, as this pre-registration's audit
   records, the recorded values do **not** track the outcome.

## 3. Design — frozen

**Frames.** A = `nac.m1271742202lc` (29.95°), B = `nac.m1335207975rc` (69.76°),
D = `nac.m1299958135lc` (18.22°), all unchanged. **E** = one new independent low-incidence
CDR frame over the same ground region, selected by §4.

**Comparisons.**

| edge | role | source |
|---|---|---|
| **E ↔ A** | **decisive** — low ↔ low | measured in this stage |
| **E ↔ B** | **decisive** — low ↔ high | measured in this stage |
| A ↔ B | control, high Δinc, expected FAIL | measured in this stage |
| D ↔ A | **retained**, not re-run | REAL-DATA-04, recorded |
| D ↔ B | **retained**, not re-run | REAL-DATA-04, recorded |

The three measured edges form the triplet {A, B, E} and are run by the **existing**
`register_real_triplet.py` in the order A → B, B → E, E → A — structurally identical to
REAL-DATA-04's {A, B, D}. **No new registration code is written.**

**Why exactly one new frame.** Replication over expansion. E is the minimum addition that
gives a second independent instance of both the passing and the failing regime, and it adds
exactly one new product to the design. Nothing else changes.

## 4. Selection criterion for frame E — FROZEN BEFORE ANY SCREENING

Applied in this order. A candidate failing any hard filter is **discarded, not weighed**.

### 4.1 Hard filters

**H1 — real archive product.** LRO NAC **CDR** (`LRO-L-LROC-3-CDR-V1.0`) with a retrievable
PDS4 `Product_Observational` label and an archive index row.

**H2 — ground point.** A **two-tier ladder, registered now**, so no target point can be moved
silently after the fact:

* **T1 (preferred).** E's frame admits a full 4096 × 2048 tile centred, **unclamped on both
  axes**, on REAL-DATA-04's exact target: lon **22.010350422685136**, lat
  **19.66625467769675**. Under T1 the tiles of A, B and D are **byte-identical** to
  REAL-DATA-04's, so D ↔ A and D ↔ B are literally retained rather than re-derived, and the
  A ↔ B control becomes an exact determinism check (§5.3).
* **T2 (fallback).** Used **only** if the full spatial ladder of §4.4 returns zero T1
  candidates, and only with that candidate count recorded in the stage report. Target = the
  centroid of the intersection of the tile-admissible footprints of **{A, B, D, E}** — all
  four, D included, so D can be re-cut at the RD-05 window without a new search if a
  cross-window objection is ever raised. A and B are re-cut; D ↔ A and D ↔ B remain the
  retained REAL-DATA-04 measurements at REAL-DATA-04's window, and A ↔ B measured at both
  windows is the bridge between them.
* **T3.** If T2 also returns zero, the stage reports **UNRESOLVED — BY DATA AVAILABILITY** and
  stops. It does **not** drop D from the intersection, does **not** relax any other filter,
  and does **not** substitute a frame outside the incidence band.

**H3 — tile fits.** A full 4096 × 2048 tile centred on the chosen target must fit inside E's
frame with `window_detail.fully_inside_frame == true` (D-039). Checked in the manifest, never
assumed.

**H4 — incidence band: `incidence_E` ∈ [18.22°, 30.91°]** (new, **D-041**). Also
`incidence_E ≤ 75°` (D-029), which this subsumes.

The band is arithmetic on the two bracket edges REAL-DATA-04 left behind — the largest Δinc yet
observed to **succeed** (11.73°) and the smallest yet observed to **fail** (38.85°):

| requirement | gives |
|---|---|
| Δinc(E ↔ A) ≤ **11.73°** — inside the demonstrated-success bracket | `incidence_E` ∈ [18.22, 41.68] |
| Δinc(E ↔ B) ≥ **38.85°** — at or beyond the smallest demonstrated failure | `incidence_E` ≤ 30.91 |
| **intersection** | **[18.22°, 30.91°]** |

| at the band edge | Δinc(E↔A) | Δinc(E↔B) | contrast |
|---|---|---|---|
| `incidence_E` = 18.22° | **11.73°** | **51.54°** | 39.81° |
| `incidence_E` = 30.91° | **0.96°** | **38.85°** | 37.89° |

The contrast never falls below **37.89°** anywhere in the band, so the design cannot invert.
More importantly: at **both** edges of the band, and everywhere between them, **both** decisive
edges sit in a Δincidence regime whose outcome has **already been measured** on real data —
11.73° and 0.96° both succeeded; 51.54° and 38.85° both failed. The band is deliberately
narrower than REAL-DATA-04's [9.95°, 39.95°]: it buys a clean replication instead of a
cliff-locating datum, and a Δinc landing in the unbracketed 11.73°–38.85° gap would make the
outcome uninterpretable as replication. **Locating the cliff is a different experiment and is
not attempted here.**

**H5 — orientation match (REAL-DATA-04 filter 1c, D-038, unchanged).** E's
`(along-track, cross-track)` signature, from the archive's **named** corner columns, must
equal the incumbents' **(+1, −1)**. Same function, same code path.

**H6 — near-nadir: `EMISSION_ANGLE` ≤ 5.0°** (new, **D-042**). The incumbents span 1.17°–1.75°.
An off-nadir E would introduce relief displacement / parallax as a fresh variable on the
decisive edge. REAL-DATA-04 eliminated Δemission empirically, but over a range of 0.58°, which
is no licence to admit a frame at 20°. This filter **holds a variable fixed**; it can only
shrink the candidate set and can never rescue a preferred frame.

**H7 — same NAC camera as A and D: `NAC_FRAME_ID == "LEFT"`** (new, **D-043**). A, C and D are
LEFT; B is RIGHT. The recorded evidence says camera pairing does **not** partition outcomes
(L–L both succeeds and fails; R–L both succeeds and fails — §6.3), so this is precaution, not
necessity. It keeps the **decisive E ↔ A edge** free of a camera change, at the cost of a
smaller pool. E ↔ B is then LEFT–RIGHT, exactly as A ↔ B and B → C already are.

**H8 — novelty.** E ∉ {A, B, C, D}, and E's tile must differ from all of theirs by SHA-256,
asserted in code before any result is interpreted (E-025).

### 4.2 Deciding criterion

Among candidates passing **every** hard filter: **minimise the maximum `Map_resolution` ratio
against A, B and D.** Unchanged in kind from REAL-DATA-03 §10 criterion 3 and REAL-DATA-04 §3
criterion 6. Scale mismatch is the one axis on which this project has *measured* a failure
(EXP-001: mare fails at 2×), so it stays the decider.

**Tie-break 1:** smaller `|incidence_E − incidence_D|` — the tightest replication of D's own
illumination regime. **Tie-break 2:** smaller `|emission_E − emission_D|`.

**Why illumination is a filter and not the decider,** as in REAL-DATA-04: illumination is this
stage's independent variable, so the design requires a low-incidence E or there is no
experiment; but among frames that are all admissible by design, the specific frame must still
not be chosen *on* illumination.

### 4.3 The criteria are executed, not described

The screen runs in code (`scripts/screen_frame_e.py`, §7.1) and writes **every** candidate and
its rejection reason to the artefact. The winner is produced by the script under the full
filter set. **No frame is picked from a list after the fact**, and the funnel is reported in
full whatever it contains.

### 4.4 The spatial search ladder — quantify availability, never move a criterion

Widening is **spatial only**. No filter is ever relaxed to find a candidate.

1. **S1** — REAL-DATA-04's box: lat [18.5, 21.5], lon [21.5, 22.6], limit 500.
2. **S2** — if S1 yields zero admissible: lat [17.5, 22.5], lon [20.5, 23.6], limit 1500.
   Candidates outside A's and B's own footprints cannot share tile-admissible ground with
   them, so S2 bounds the search: the admissible strip is a property of A and B, both fixed.
3. **S3** — if S2 yields zero: the archive is exhausted for this design. Report
   **UNRESOLVED — BY DATA AVAILABILITY** and stop.

The stage report must state, for every rung reached: products returned, and the count rejected
by **each** filter separately. That is the "quantify candidate availability" record, and it is
required whether the answer is 1 or 0.

## 5. Acceptance / rejection criteria — FROZEN BEFORE ACQUISITION

### 5.1 Overlap gates — defined before acquisition, evaluated before any registration is interpreted

Method and criteria are REAL-DATA-02's, **unchanged**: named archive corners, corner naming
from each product's own PDS4 `disp:Display_Direction`, bilinear ground map, one common local
plane, exact convex clip, 4000 Monte Carlo draws over the ±0.005° corner quantisation. No pixel
is read; no matcher component is involved.

* **Blocking gate.** `verify_tile_overlap.py --require-confirmed` must classify **all three**
  edges — E ↔ A, E ↔ B and A ↔ B — as **`OVERLAP_CONFIRMED`**, i.e. p5 of the worse-covered
  tile's shared fraction ≥ **0.50**. It exits non-zero otherwise and **no registration is run
  or interpreted**. A stage that cannot clear this gate reports **UNRESOLVED — GATE NOT MET**.
* **Non-blocking, pre-declared caveat rule.** If the primary `min_fraction` of the two decisive
  edges differ by **more than 5.0 percentage points**, the overlap-difference confound is
  declared **live** in the report and the conclusion is downgraded one step
  (SUPPORT → INCONCLUSIVE). REAL-DATA-04's decisive edges were matched to 0.95 pp, and that
  match is a large part of why its comparison was clean. This is a **recorded caveat, not a
  gate** — a blocking criterion invented from a post-acquisition geometry fact would be a
  moving criterion.

### 5.2 Success / failure of an edge — unchanged, D-023

> An edge **FAILS** iff `n_inliers <= 8`, or no transform is estimated. Otherwise it **passes
> the inlier rule.**

Identical to REAL-DATA-03 and REAL-DATA-04. Still **applied, not validated on real data**.

**`fit_rmse` is excluded from the decision.** D-003 measured it at ROC AUC 0.4947 and inverted
in the failure regime; REAL-DATA-04 §10.2 is the cleanest instance — 1.885e-13 px on an edge
independently measured 797 px wrong, against 0.878 px on the succeeding edge. It is reported
and it decides nothing.

**Corroboration classifies; it never moves the line.** `check_transform_against_geometry.py`
runs *after* the decision and assigns class B vs class C. One pre-declared consequence: **if
E ↔ A passes the inlier rule but the corner-polygon check returns `INCONSISTENT`, the edge is
recorded as PASS / class C and the replication is downgraded to INCONCLUSIVE** — a passing edge
that the archive says is hundreds of pixels wrong does not replicate D → A, which was
CONSISTENT (0.53× the discrimination floor) and matched SPICE-derived `SCALED_PIXEL` to
0.04 % / 0.13 %.

### 5.3 Two integrity checks available before any interpretation

* **Determinism (T1 only).** Under T1 the A and B tiles are byte-identical to REAL-DATA-04's
  and the seed is 0, so A → B **must reproduce REAL-DATA-04's numbers exactly**: 50 putative,
  **7** inliers, `fit_rmse` 1.1053335547230574, and the same transform matrix. **If it does
  not, the pipeline is not deterministic, the whole stage is void, and nothing in it may be
  interpreted** — report the discrepancy and stop.
* **Control (T2 only).** Under T2 the A ↔ B control is a third independent replication at a
  third window and is expected to **FAIL**. **If A ↔ B passes under T2, the control has broken
  and the stage is INCONCLUSIVE regardless of what E's edges do.**

### 5.4 Loop closure — recorded, and excluded from the decision, in advance

`register_real_triplet.py` computes loop closure over {A, B, E}. Under the predicted outcome
two of the three legs are broken, and **a loop with two broken legs corroborates nothing** —
REAL-DATA-03 (1201.04 px) and REAL-DATA-04 (943.75 px) both exercised it in exactly that state.
It is reported for the record and **excluded from this stage's decision**, stated here so it
cannot be read into the result afterwards. Its discriminating power still needs **three
succeeding** real edges, which this design does not produce.

## 6. The decision table — FROZEN BEFORE THE DATA EXISTS

| E ↔ A | E ↔ B | conclusion |
|---|---|---|
| **PASS** | **FAIL** | **REPLICATED — the Δincidence effect is reproducible.** A second, independently selected low-incidence frame reproduces D's pattern on the same ground with the same unchanged matcher. D-040 is upheld and its "n = 1 decisive edge" debt is discharged. Scope is still one region, one terrain type, one instrument, incidence only. |
| **FAIL** | **PASS** | **REFUTED — the result does not replicate and inverts.** Δincidence is not the driver; a frame-specific or acquisition-specific factor is. D-040 must be withdrawn and superseded. |
| **FAIL** | **FAIL** | **NOT REPLICATED — INCONCLUSIVE.** Consistent with D → A being specific to frame D, with an E-specific defect, or with something about the window. **Illumination is not supported by this stage**, and REAL-DATA-04's result stands as an unreplicated n = 1. D-040 is reduced to "observed once, not reproduced". |
| **PASS** | **PASS** | **ILLUMINATION WEAKENED.** A ≥ 38.85° Δincidence edge that registers refutes the simple monotone form: Δincidence is not sufficient to predict failure, and D-040's scope must narrow. |

**Additional conditions for the first row to be read as SUPPORT** — all pre-declared:

1. Both decisive edges `OVERLAP_CONFIRMED` (§5.1).
2. Their inlier counts separated widely enough that **no threshold between the two counts
   changes which one passes** — the same argument REAL-DATA-04 §11.4 used to make its
   conclusion independent of the value 8. If the two counts straddle 8 narrowly, the row is
   read as **INCONCLUSIVE**, not SUPPORT.
3. E ↔ A not `INCONSISTENT` against archive geometry (§5.2).
4. The A ↔ B control behaving as §5.3 requires for the tier in force.
5. The §5.1 caveat rule not triggered (else downgrade one step).

**What this stage may still NOT conclude, whatever it finds:**

* **Not** a location of the illumination cliff. The band is chosen precisely so that no
  measurement lands in the unbracketed 11.73°–38.85° gap.
* **Not** an azimuth result (§6.2).
* **Not** a separation of Δincidence from Δphase (§6.2).
* **Not** a validation of `n_inliers <= 8`.
* **Not** an accuracy claim of any kind. No ground truth exists for these products.
* **Not** a generalisation beyond mare terrain in Mare Serenitatis with LRO NAC, near-nadir,
  −X flight direction.

## 6.1 Confounds held fixed by construction

| variable | held at | mechanism |
|---|---|---|
| matcher, descriptor, ratio, RANSAC threshold, seed, model | REAL-DATA-04 §5 exactly | frozen, restated as constants in the scripts |
| decimation | 2× on every edge | one code path |
| preprocessing | 1–99 percentile stretch, per image | identical rule for every tile |
| tile size | 4096 × 2048, unclamped | H3, `fully_inside_frame` |
| ground region | one target point, all frames | H2 ladder |
| instrument, product level | LRO NAC CDR | H1 |
| orientation signature | (+1, −1) | H5 |
| emission angle | ≤ 5°, incumbents 1.17–1.75° | H6 |
| NAC camera on the decisive edge | LEFT ↔ LEFT | H7 |
| flight direction | −X for A, B, C, D | recorded; a **scope limit**, not a control (§6.4) |
| terrain, texture | same mare ground, same window | H2 |

## 6.2 Confounds that vary, are uncontrolled, and are explicitly tracked

**Δphase — perfectly collinear with Δincidence, and not separable by any version of this
experiment.** With emission ≈ 1.7° for every frame, phase ≈ incidence:

| edge | Δinc | Δphase | outcome |
|---|---|---|---|
| B → C | 0.96° | 1.90° | SUCCEED |
| D → A | 11.73° | 12.92° | SUCCEED |
| C → A | 38.85° | 39.15° | FAIL |
| A → B | 39.81° | 37.25° | FAIL (×2) |
| B → D | 51.54° | 50.17° | FAIL |

Δphase partitions the six edges identically to Δincidence. **Separating them would require an
E with a large emission angle, which H6 forbids because it would introduce parallax on the
decisive edge.** This is a permanent limitation of near-nadir single-instrument data and is
recorded as such, not as something REAL-DATA-05 failed to do. Every claim in this stage must
be read as "Δincidence, inseparable from Δphase at near-nadir emission".

**Δazimuth — never controlled, and the recorded values do not track the outcome.** `[MEASURED]`
`SUB_SOLAR_AZIMUTH` from the index rows; `[NOT VERIFIED]` its frame is RDR-relative and
unverified (RL-032b), so the numbers are used **only** to check whether azimuth could be the
partition, never to claim an azimuth result:

| edge | Δaz | Δinc | outcome |
|---|---|---|---|
| B → C | 1.83° | 0.96° | **SUCCEED** |
| A → B | 31.18° | 39.81° | FAIL (×2) |
| C → A | 33.01° | 38.85° | FAIL |
| **D → A** | **49.05°** | 11.73° | **SUCCEED** |
| B → D | 80.23° | 51.54° | FAIL |

**The succeeding D → A has a larger Δazimuth than three of the four failing edges.** Δazimuth
therefore does **not** partition the six outcomes, and a monotone Δazimuth explanation of the
failures is not supported by the recorded data. This is an audit finding of this
pre-registration, recorded **before** E is chosen, and it must be reported unchanged whatever E
does. It is **not** an azimuth robustness claim, and it neither confirms nor refutes EXP-003's
synthetic Δaz 21–27° cliff, which is a different axis measured a different way.

**Pre-declared azimuth analysis for E**, so it cannot be selected after the fact: Δaz(E ↔ A)
and Δaz(E ↔ B) are computed from E's index row and recorded in the screen artefact **before
acquisition**. If E ↔ A passes with Δaz(E ↔ A) larger than a failing edge's, the
anti-correlation is strengthened; if Δaz turns out to partition all eight edges as cleanly as
Δincidence does, that is reported as a **live confound** and this stage's conclusion is
downgraded to INCONCLUSIVE on the azimuth axis. Azimuth is **not** a filter — filtering on it
would tune the experiment toward its preferred answer.

**Acquisition interval.** `[MEASURED]` succeeding 10.7 and 44.6 months; failing 13.4, 24.1,
24.1 and 68.7. Not monotonic across stages; recorded for E, not filtered on.

## 6.3 Confounds checked against recorded evidence

Every row below except the first is **eliminated as a partition** of the six recorded
outcomes. The first row is **not**, and is stated separately for that reason.

| candidate | status against the recorded evidence |
|---|---|
| **frame / product identity** | **SUBSTANTIALLY WEAKENED BUT NOT ELIMINATED.** Across the six edges every frame appears on both sides: A succeeds in D → A and fails in A → B (×2) and C → A; B succeeds in B → C and fails in A → B (×2) and B → D; C succeeds in B → C, fails in C → A; D succeeds in D → A, fails in B → D. But this is a **cross-stage join**, and **A and D each have n = 1 observations in the relevant successful regime**, so **REAL-DATA-05 provides the required independent replication** |
| **resolution ratio** | succeeding 1.1479 and 1.0737; failing 1.1667, 1.0163, 1.0912, 1.0163. Ranges overlap; the smallest ratio in the project (1.0163) fails twice and the second-largest (1.1479) succeeds |
| **image scale** | as above; and D → A's recovered scale matches SPICE `SCALED_PIXEL` to 0.04 % / 0.13 %, so a scale error is excluded on the succeeding edge by a field the matcher never saw |
| **emission angle / relief displacement / parallax** | Δemission: succeeding 0.01° and 0.55°; failing 0.58°, 0.57°, 0.02°, 0.57°. Both classes take both extremes. Further constrained by H6 |
| **texture** | same mare ground; D → A found 1759 putative / 1656 inliers on it |
| **overlap** | REAL-DATA-04's decisive edges matched to 0.95 pp diverge by 552×; across both stages the *most*-overlapping edges (97.9 %, 97.1 %) fail and the *least*-overlapping (71.3 %, 85.0 %) succeed |
| **NAC camera (LEFT/RIGHT)** | L–L succeeds (D → A) and fails (C → A); R–L succeeds (B → C) and fails (B → D). Does not partition. Held fixed on the decisive edge anyway by H7 |
| **sub-solar latitude** | Δ: succeeding 0.58°, 0.81°; failing 1.67°, 1.09°, **0.28°**, 1.09°. The *smallest* difference fails |
| **window clamping / tile-window uncertainty** | no window clamped on either axis in either stage; `fully_inside_frame: true` throughout |
| **decimation, affine model, pipeline defect** | identical on every edge; D → A is a successful cross-frame registration at inlier ratio 0.9414 and occupancy 1.000 |

## 6.4 Confounds that would invalidate the conclusion, and the pre-declared response

| confound | response, fixed in advance |
|---|---|
| E's tile not distinct, or an artefact overwritten | H8 SHA-256 assertion; every output on a new path; the scripts refuse to overwrite (integrity rule 4) |
| Overlap not confirmed, or badly mismatched between the decisive edges | blocking gate + 5.0 pp caveat rule (§5.1) |
| E ↔ A passes but is geometrically wrong | INCONSISTENT ⇒ class C ⇒ downgrade to INCONCLUSIVE (§5.2) |
| Pipeline non-determinism | T1 determinism check voids the stage (§5.3) |
| Control inversion | A ↔ B passing under T2 ⇒ INCONCLUSIVE regardless (§5.3) |
| A Δinc landing in the unbracketed 11.73°–38.85° gap | impossible under H4 by construction |
| Δazimuth turning out to partition the outcomes | pre-declared analysis ⇒ downgrade to INCONCLUSIVE on that axis (§6.2) |
| Δphase | **not removable**; every conclusion stated as "Δincidence, inseparable from Δphase" (§6.2) |
| Orientation assignment / EXP-004 | excluded by H5 before acquisition, as in REAL-DATA-04 |
| Flight direction never varied (−X throughout) | a **scope limit**: nothing here tests +X, and no claim may span it |
| Terrain heterogeneity if T2 moves the window | A ↔ B measured at the new window is the bridge; the move and its reason documented under §4.1 T2 with the T1 candidate count that forced it |
| Generalisation | one region, one terrain, one instrument. Stated in every conclusion |

## 7. Order of operations — the gate before the interpretation

Identical in structure to REAL-DATA-04 §4.

0. Extend the screen additively (§7.1). Tests pass before it is used.
1. Screen candidates from ODE metadata only. **No image bytes.** Ladder §4.4.
2. Fetch **authoritative** named index geometry for **every** admissible candidate, and re-run
   the screen under the full filter set including H5, so the ranking is produced by the script.
3. Acquire exactly one tile for E. Verify HTTP 206 length and `Content-Range`, the `file_size`
   identity, and **SHA-256**.
4. Image sanity (`check_real_tiles.py`, unchanged) — must PASS for every tile.
5. **Independent overlap verification, `--require-confirmed`, BEFORE any registration is run
   or interpreted.** Separate command; exits non-zero unless every edge is CONFIRMED.
6. Only then, the **unmodified** baseline; each edge estimated independently from its own
   image pair.
7. Independent check of the estimated transforms against archive geometry.
8. Interpret against §6, and only §6.

**Preserve every failed run.** Empty screens, refused gates and any non-zero exit are kept as
artefacts and reported, exactly as REAL-DATA-04 §13 kept its two empty screens.

### 7.1 The only code permitted

`scripts/screen_frame_e.py` — a copy of `screen_frame_d.py` with three **additive** options:
`--emission-max` (H6), `--nac-frame-id` (H7) and `--stage` (report/figure label). Defaults
reproduce `screen_frame_d.py`'s behaviour exactly, so REAL-DATA-04's invocations remain
reproducible. Tests in `tests/test_screen_frame_e.py` must cover: a candidate rejected on
emission alone, a candidate rejected on camera alone, and the funnel accounting for every
candidate. **Nothing in `src/siim/` is modified. The matcher, the verdict engine and the
evaluation code are untouched.**

## 8. Exact commands to execute — after this preregistration is verified, not before

```bash
# ---- step 0: additive screen extension + tests (no network, no images) ----
python -m pytest tests/test_screen_frame_e.py tests/test_screen_frame_d.py \
                 tests/test_ingest_footprint.py -q

# ---- step 1: screen, METADATA ONLY. Rung S1, tier T1. ----
python scripts/screen_frame_e.py \
       --stage REAL-DATA-05 \
       --incumbent-manifest real_quad_d_geo_manifest.json \
       --incumbent-geometry real_pair_index_geometry.json,real_frame_d_selected_index_geometry.json \
       --target-lonlat 22.010350422685136,19.66625467769675 \
       --incidence-band 18.22,30.91 --incidence-max 75.0 \
       --emission-max 5.0 --nac-frame-id LEFT \
       --lines 4096 --samples 2048 \
       --minlat 18.5 --maxlat 21.5 --westernlon 21.5 --easternlon 22.6 --limit 500 \
       --out screen_frame_e_T1.json

# ---- step 2: AUTHORITATIVE corners for every admissible candidate, then re-run
#      the screen with H5 in force so the ranking is produced under the full set ----
python scripts/fetch_index_geometry.py \
       --pdsids <all admissible from screen_frame_e_T1.json> \
       --out real_frame_e_candidates_index_geometry.json

python scripts/screen_frame_e.py \
       --stage REAL-DATA-05 \
       --incumbent-manifest real_quad_d_geo_manifest.json \
       --incumbent-geometry real_pair_index_geometry.json,real_frame_d_selected_index_geometry.json \
       --candidate-geometry real_frame_e_candidates_index_geometry.json \
       --target-lonlat 22.010350422685136,19.66625467769675 \
       --incidence-band 18.22,30.91 --incidence-max 75.0 \
       --emission-max 5.0 --nac-frame-id LEFT \
       --lines 4096 --samples 2048 \
       --minlat 18.5 --maxlat 21.5 --westernlon 21.5 --easternlon 22.6 --limit 500 \
       --out screen_frame_e_T1_authoritative.json

#   If ZERO admissible -> rung S2 (SPATIAL widening only, same criteria); keep both artefacts:
#       --minlat 17.5 --maxlat 22.5 --westernlon 20.5 --easternlon 23.6 --limit 1500
#       --out screen_frame_e_T1_S2.json
#   If still ZERO -> tier T2: same boxes, replace --target-lonlat with
#       --shared-target --incumbent-frames nac.m1271742202lc,nac.m1335207975rc,nac.m1299958135lc
#       --out screen_frame_e_T2.json
#   If T2 is also ZERO -> STOP. Report UNRESOLVED - BY DATA AVAILABILITY.

# ---- step 2b: authoritative geometry for the SELECTED frame, fetched alone ----
python scripts/fetch_index_geometry.py --pdsids <E> \
       --out real_frame_e_selected_index_geometry.json
#   Must reproduce the candidate manifest's row_sha256 for E exactly.

# ---- step 3: acquisition -- ONE tile. T1 form shown. ----
python scripts/acquire_real_pair.py \
       --from-geometry real_frame_e_selected_index_geometry.json \
       --products <E> \
       --target-lonlat 22.010350422685136,19.66625467769675 \
       --lines 4096 --samples 2048 \
       --role real_data_05_replication_frame_e \
       --out real_frame_e_geo_manifest.json
#   T2 form instead: drop --target-lonlat, pass --target-shared-tile and acquire
#   E, A and B together against the {A,B,D,E} tile-admissible centroid.

python scripts/compose_triplet_manifest.py \
       --from real_quad_d_geo_manifest.json,real_frame_e_geo_manifest.json \
       --products nac.m1271742202lc,nac.m1335207975rc,<E> \
       --out real_triplet_e_geo_manifest.json
#   Order fixes the edges: A -> B, B -> E, E -> A.

# ---- step 4: image sanity. Must PASS for all three tiles. ----
python scripts/check_real_tiles.py --manifest real_triplet_e_geo_manifest.json \
       --outdir REAL-DATA-05

# ---- step 5: THE GATE. Separate command. Exits non-zero unless all CONFIRMED. ----
python scripts/verify_tile_overlap.py \
       --manifest real_triplet_e_geo_manifest.json \
       --extra-geometry real_frame_e_selected_index_geometry.json \
       --case real_data_05 --role "replication triplet A/B/E" \
       --outdir REAL-DATA-05 --out overlap_real_data_05.json \
       --figure tile_overlap_real_data_05.png \
       --require-confirmed
#   STOP HERE if this exits non-zero. Do not run step 6.

# ---- step 6: the UNMODIFIED baseline, three independent edges ----
python scripts/register_real_triplet.py \
       --manifest real_triplet_e_geo_manifest.json \
       --stage REAL-DATA-05 --outdir REAL-DATA-05 --tag real_data_05 \
       --model affine --downsample 2 \
       --overlap-artefact experiments/REAL-DATA-05/overlap_real_data_05.json \
       --overlap-note "<the three CONFIRMED percentages from step 5>"

# ---- step 7: independent check against archive geometry ----
python scripts/check_transform_against_geometry.py \
       --manifest real_triplet_e_geo_manifest.json \
       --registration experiments/REAL-DATA-05/loop_closure_real_data_05.json \
       --geometry real_pair_index_geometry.json \
       --extra-geometry real_frame_e_selected_index_geometry.json \
       --model affine --downsample 2 \
       --outdir REAL-DATA-05 --out transform_vs_geometry_real_data_05.json

# ---- step 8: full suite, then interpret against section 6 and only section 6 ----
python -m pytest tests/ -q
```

**Not run, and not to be run in this stage:** any matcher variant, any threshold sweep, any
illumination normalisation, any manual removal of matches, EXP-004, and anything in
`src/siim/demo/`. **The demo is not scientific evidence and is not consulted.**

## 9. Expected interpretations

**If E ↔ A PASSES and E ↔ B FAILS** (the predicted outcome if D-040 is right):
**REPLICATED.** Two independently selected low-incidence frames, D and E, each register against
A and each fail against B, on confirmed-overlapping tiles of the same mare ground, through an
unchanged pipeline at a fixed seed. The n = 1 debt on the decisive observation is discharged
and the frame-identity refutation stops depending on a single edge. **Still not proven, and
still scoped:** Δincidence inseparable from Δphase; incidence only, not azimuth; one region,
one terrain type, one instrument; near-nadir only; −X flight direction only; and the cliff
still unlocated between 11.73° and 38.85°.

**If E ↔ A FAILS and E ↔ B PASSES:** **REFUTED and inverted.** D-040 is withdrawn. The
attribution returns to frame- or acquisition-specific factors, and the next stage is a
diagnosis of what distinguishes D from E — not a matcher change.

**If both FAIL:** **NOT REPLICATED — INCONCLUSIVE.** D → A becomes an unreplicated single
observation and D-040 is reduced to "observed once, not reproduced". The next questions are
whether the effect is specific to frame D and whether the E tile is defective; the sanity
artefact and the geometry check are the first evidence to consult, and neither may be used to
rescue the conclusion.

**If both PASS:** **ILLUMINATION WEAKENED.** A ≥ 38.85° edge that registers means Δincidence is
not sufficient to predict failure, and the earlier failures need a second factor this design
did not vary. D-040's scope narrows accordingly.

**In every case** the full funnel, all three measured edges, both retained D edges, the overlap
table, the geometry check, the loop residual and every failed run are reported. No result is
dropped, and the table in §6 is not reinterpreted.

## 10. Ledger entries this stage will claim

`D-041` incidence band [18.22°, 30.91°] · `D-042` emission ceiling 5° · `D-043` NAC LEFT on the
decisive edge · and, on completion, a decision that upholds, reduces or supersedes `D-040`.
`RL-036` is the research-log thread. **None is written until the stage runs**, except this
document, which is the pre-registration and is frozen on the date above.

## 11. Integrity checklist for this pre-registration

| | |
|---|---|
| Decision table fixed before the data exists | **Yes** — §6; no candidate has been screened |
| Selection criterion for E fixed before any outcome imagery | **Yes** — §4, before any screen was run |
| Overlap gates defined before acquisition | **Yes** — §5.1 |
| Success/failure criterion unchanged from the previous stage | **Yes** — `n_inliers <= 8`, D-023 |
| `fit_rmse` excluded from the decision, in advance | **Yes** — §5.2 |
| Target-point ladder registered in advance, no silent move | **Yes** — §4.1 T1/T2/T3, with the availability count required in the report |
| Search widening is spatial only | **Yes** — §4.4 |
| Confounds enumerated before the result | **Yes** — §6.1–6.4, including the Δazimuth audit finding recorded before E is chosen |
| An unremovable confound stated as such | **Yes** — Δphase, §6.2 |
| The matcher and verdict criteria untouched | **Yes** — §7.1; only the metadata screen is extended, additively, with tests |
| Failed runs to be preserved | **Yes** — §7 |
| Demo excluded from evidence | **Yes** — §8 |
| Nothing acquired yet | **Yes — this stage has not started** |

---

# 12. RESULT — UNRESOLVED, BY DATA AVAILABILITY

**Everything above this line is the pre-registration and is unchanged.** Sections 1–11 were
frozen before the screen ran. Nothing in them was edited after a result was seen, except one
correction to the §6.3 audit wording, made *before* acquisition began and recorded in §12.6.

**Status: the stage reached §4.1 tier T3 / §4.4 rung S3 and stopped. No frame E was selected.
No image byte was fetched. No registration was run. Steps 3–7 of §7 did not execute.**

## 12.1 The screening funnel, every rung

`[MEASURED]` `data/manifests/screen_frame_e_*.json` — eight artefacts, all preserved.

| tier | rung | H5 | ODE products | filter 2 / 1b | filter 4 | filter 5 | filter 6 | **H5** | **H6** | **H7** | **admissible** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1 | S1 | off | 261 | 250 (+5 f3) | 1 | 2 | 2 | — | 0 | 0 | **1** |
| T1 | S1 | **on** | 261 | 250 (+5 f3) | 1 | 2 | 2 | **1** | 0 | 0 | **0** |
| T1 | S2 | off | 906 | 895 (+5 f3) | 1 | 2 | 2 | — | 0 | 0 | **1** |
| T1 | S2 | **on** | 906 | 895 (+5 f3) | 1 | 2 | 2 | **1** | 0 | 0 | **0** |
| T2 | S1 | off | 261 | 55 | 48 | 154 | 2 | — | 0 | 0 | **2** |
| T2 | S1 | **on** | 261 | 10 | 48 | 154 | 2 | **47** | 0 | 0 | **0** |
| T2 | S2 | off | 906 | 206 | 135 | 561 | 2 | — | 0 | 0 | **2** |
| **T2** | **S2** | **on** | **906** | **56** | **135** | **561** | **2** | **152** | **0** | **0** | **0** |

filter 2 = target not inside frame (T1) · filter 3 = tile runs off the frame (T1) ·
filter 1b = no shared tile-admissible ground with {A, B, D} (T2) · filter 4 = incidence > 75° ·
filter 5 = incidence outside [18.22°, 30.91°] · filter 6 = incumbent · H5 = orientation
mismatch · H6 = emission · H7 = camera.

**Widening the box from 261 to 906 products changed nothing** — the same candidates survive at
S2 as at S1, in both tiers. This reproduces REAL-DATA-04 §3.1's finding that the admissible set
is bounded by the incumbents' own footprints, not by the query box.

## 12.2 Every rejected candidate that reached the deciding stage

Two candidates survived every filter except H5, in both T2 rungs. Both were judged on
**authoritative named index columns**, fetched before they were ranked.
`[MEASURED]` `data/manifests/real_frame_e_T2_candidates_index_geometry.json`.

| candidate | incidence | emission | camera | `Map_resolution` | max ratio vs A,B,D | flight dir | **orientation** | outcome |
|---|---|---|---|---|---|---|---|---|
| `nac.m1315225542lc` | 21.13° | 1.72° | LEFT | 0.806 m | 1.3288 | **+X** | **(−1, −1)** | **rejected — H5** |
| `nac.m1373951417lc` | 20.13° | 1.71° | LEFT | 0.759 m | 1.4111 | **+X** | **(−1, −1)** | **rejected — H5** |

Required signature, from the incumbents and agreed among them: **(+1, −1)**. Both candidates
image the ground in the opposite along-track sense, so a tile cut from either would be rotated
180° relative to A's and B's. Admitting one would put orientation assignment — EXP-004,
pre-registered and deliberately not started — onto the decisive edge, which is precisely what
D-038 forbids.

`nac.m1315225542lc` and `nac.m1373951417lc` were **already rejected by REAL-DATA-04's filter
1c** for the same reason. The screen re-derived that verdict independently here.

## 12.3 Availability of frame E, quantified

`[MEASURED]` `data/manifests/screen_frame_e_availability_diagnostic_only.json`. **A DIAGNOSTIC,
NOT A SELECTION** — run with the incidence band, emission ceiling and camera filter disabled
solely to measure what the archive holds. No candidate from it was used, and none may be.

Of **906** CDR products across lat [17.5, 22.5] × lon [20.5, 23.6], exactly **8** can centre a
full 4096 × 2048 tile on ground shared with A, B and D:

| pdsid | incidence | camera | max ratio | shared km² | orientation | in band? |
|---|---|---|---|---|---|---|
| `nac.m1341069775rc` | 42.43° | RIGHT | 1.1098 | 11.02 | *(not fetched)* | no |
| `nac.m1363396554rc` | 52.40° | RIGHT | 1.1220 | 3.83 | *(not fetched)* | no |
| `nac.m1212932972lc` | 45.48° | LEFT | 1.1786 | 10.48 | *(not fetched)* | no |
| `nac.m1452560468lc` **(= frame C)** | 68.80° | LEFT | 1.2526 | 4.40 | **(+1, −1)** | no |
| `nac.m1315225542lc` | **21.13°** | LEFT | 1.3288 | 21.20 | **(−1, −1)** | **yes** |
| `nac.m1373951417lc` | **20.13°** | LEFT | 1.4111 | 2.50 | **(−1, −1)** | **yes** |
| `nac.m1096350825rc` | 72.29° | RIGHT | 1.4183 | 13.23 | *(not fetched)* | no |
| `nac.m124423514lc` | 18.00° | LEFT | 2.1813 | 6.31 | **(+1, +1)** | no — 0.22° below the band |

**The archive holds exactly two frames in the required illumination band over the ground A, B
and D share, and both are acquired in the opposite along-track sense.** The only frame over
this ground with an incidence anywhere near the band and a non-(−1,−1) signature is
`nac.m124423514lc` at 18.00° — which is (+1, +1), a *third* signature, and 0.22° outside the
band besides. The search space defined in §4 is exhausted.

## 12.4 The two filters added by this stage cost it nothing

**H6 (emission ≤ 5°) and H7 (NAC LEFT) rejected zero candidates at every rung** — they do not
appear in any funnel. Both surviving candidates were LEFT with emission 1.71°–1.72° and passed
both. **The stop is caused entirely by H5, which is REAL-DATA-04's own filter 1c (D-038),
unchanged.** Had this stage run REAL-DATA-04's filter set verbatim, the outcome would have been
identical.

**Nor did the inferred ODE ring decide anything.** `[MEASURED]` cross-checked between
`screen_frame_e_T2_S2.json` and `screen_frame_e_T2_S2_authoritative.json`: of the 152 rejected
by H5 on the inferred ring, **zero** would have been admissible without it — every one also
fails filter 1b. Both candidates that survived all other filters had authoritative corners.

## 12.5 What was NOT done, and why that matters

Per §4.1 T3 and §4.4 S3, the stage stopped rather than:

* relaxing the incidence band to admit `nac.m124423514lc` at 18.00° (0.22° outside);
* relaxing H5 to admit a 180°-rotated frame;
* dropping D from the T2 intersection to widen the shared region;
* substituting a mid-incidence frame and reinterpreting the decision table.

**The decision table in §6 was never reached and is not evaluated.** No row of it applies. The
replication question is open.

## 12.6 The one documentation change, made before acquisition

§6.3's frame/product-identity row was corrected from an elimination claim to: *substantially
weakened but not eliminated; A and D each have n = 1 observations in the relevant successful
regime, so REAL-DATA-05 provides the required independent replication.* Registered before the
screen ran. No frozen criterion was altered.

## 12.7 Artefacts, all preserved

`data/manifests/` — `screen_frame_e_T1.json`, `screen_frame_e_T1_authoritative.json`,
`screen_frame_e_T1_S2.json`, `screen_frame_e_T1_S2_authoritative.json`,
`screen_frame_e_T2.json`, `screen_frame_e_T2_authoritative.json`,
`screen_frame_e_T2_S2.json`, `screen_frame_e_T2_S2_authoritative.json`,
`screen_frame_e_availability_diagnostic_only.json`,
`real_frame_e_candidates_index_geometry.json`,
`real_frame_e_T2_candidates_index_geometry.json`.

**The four empty screens are kept, not tidied away.** Each exits non-zero by design.

New code: `scripts/screen_frame_e.py` (imports REAL-DATA-04's selection logic unchanged; adds
H5-in-fixed-point-tier, H6, H7) · `tests/test_screen_frame_e.py` (20 tests).
**Nothing under `src/siim/` was modified. The matcher, verdict engine and evaluation code are
untouched.** Suite: **461 passed, 2 skipped.**

## 12.8 Consequence for D-040

**D-040 is not upheld, not reduced and not superseded by this stage** — no evidence was produced
either way. It stands exactly as REAL-DATA-04 recorded it, **with its replication debt
undischarged**: A and D each still have n = 1 observations in the successful regime, and frame
identity remains *substantially weakened but not eliminated*.

## 12.9 Evidence debt this stage adds

| Debt | Note |
|---|---|
| The replication of REAL-DATA-04 is still owed | The §4 search space is exhausted; a successor must change the *design*, pre-registered, not this stage's criteria |
| Why the archive's low-incidence coverage of this ground is single-orientation | 2 of 2 in-band frames are +X / (−1, −1); the incumbents are −X / (+1, −1). Not investigated here |
| Whether a 180°-rotated tile is in fact matchable | This is **EXP-004's** question, and it is now the blocker on the replication, not merely an open item |
