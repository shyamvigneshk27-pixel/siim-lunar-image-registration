# REAL-DATA-06 — Does photometric normalisation move the illumination threshold?

**Part 1 — pre-registration. FROZEN 2026-09-03, before any correction was applied
to a real tile.** Part 2 is empty and stays empty until Part 1 is committed.

**Classification: RESEARCH-CRITICAL.** This is the stage that determines whether
the project's headline illumination result is a statement about the Moon or a
statement about uncorrected RootSIFT.

---

## 1. Why this stage exists

Every illumination number this project has reported — the cliff bracketed to
11.73°–38.85°, the six-edge separation, the whole causal argument of
REAL-DATA-03 and -04 — was measured with **no photometric correction of any
kind**. Established planetary practice removes illumination before matching,
because the geometry is known from ephemeris (`../sources.md` S10: ISIS
`lronacpho` below ~60° incidence, Hapke with a Henyey–Greenstein phase function
above it).

Until this stage runs, the honest statement of the project's central result is
*"an uncorrected RootSIFT pipeline fails above some Δincidence between 11.73°
and 38.85°"* — a claim about our software. The claim we want to make is about
lunar imagery, and only this experiment can license it.

## 2. The question, in one sentence

**Does normalising both tiles to a standard illumination geometry before
matching change the registration outcome on the four real edges that currently
fail?**

## 3. What exists before this stage runs

Four frames over Mare Serenitatis, two ground windows, six edges — all recorded
and unchanged by this stage.

| Frame | PDS ID | Incidence | Appears in |
|---|---|---|---|
| D | `nac.m1299958135lc` | **18.22°** | 1 success, 1 failure |
| A | `nac.m1271742202lc` | **29.95°** | 1 success, 3 failures |
| C | `nac.m1452560468lc` | **68.80°** | 1 success, 1 failure |
| B | `nac.m1335207975rc` | **69.76°** | 1 success, 3 failures |

| Edge | Stage | Δincidence | Inliers | Outcome |
|---|---|---|---|---|
| B → C | RD-03 | 0.96° | 5365 | SUCCEED |
| D → A | RD-04 | 11.73° | 1656 | SUCCEED |
| C → A | RD-03 | 38.85° | **4** | FAIL |
| A → B | RD-03 | 39.81° | **4** | FAIL |
| A → B | RD-04 | 39.81° | **7** | FAIL |
| B → D | RD-04 | 51.54° | **3** | FAIL |

Exact one-tailed permutation p for the separation: **0.0667** — perfect, and not
yet significant (`siim.evaluation.exact_separation_test`).

## 4. Method, fixed in advance

1. Load the **same** decimated tiles the recorded edges used. No re-acquisition,
   no new windows, no re-decimation. The only variable that changes is the
   correction.
2. Compute per-frame incidence from the archive sub-solar point already recorded
   in the manifests. Emission is ≤ 1.75° for every frame, so the nadir phase
   approximation `g = i` applies and is recorded in each artefact.
3. Normalise both tiles of each edge to the standard geometry
   **i = g = 60°, e = 0°** (`siim.preprocessing.normalise`).
4. Run the **unmodified** B1 baseline — same seed, same ratio, same mutual
   check, same LO-RANSAC threshold, same affine model as every recorded edge.
5. Apply the **unchanged** pre-registered failure rule: `n_inliers <= 8` is a
   rejection (D-023).

**Three arms**, run on all six edges:

| Arm | Correction |
|---|---|
| `none` | the recorded baseline — must reproduce the recorded inlier counts |
| `lommel_seeliger` | parameter-free; the primary arm |
| `hapke_hg` | literature-default parameters, never fitted here |

Lambert is **not** an arm. It is the control that defines what "doing nothing
thoughtful" means and is reported alongside as a sanity reference only.

## 5. Hypotheses and success criteria — FROZEN

**H1 (primary).** Photometric normalisation converts at least one currently
failing edge to a pass under the unchanged D-023 rule.

> **S1 — MET** if ≥ 1 of the four failing edges reaches `n_inliers > 8` in the
> `lommel_seeliger` arm.
> **S1 — NOT MET** otherwise.

**H2 (secondary, quantitative).** Even without changing an outcome, correction
increases correspondence yield on the failing edges.

> **S2 — MET** if the median `n_inliers` across the four failing edges increases
> by ≥ 50 % in the `lommel_seeliger` arm relative to `none`.

**H3 (control, must hold).** Correction does not *damage* the succeeding edges.

> **S3 — MET** if neither succeeding edge drops below `n_inliers > 8`.
> **If S3 fails the stage is inconclusive regardless of S1 and S2**, because a
> correction that breaks what worked is not a correction.

**H4 (reproduction, must hold).** The `none` arm reproduces the recorded counts
exactly: 5365, 1656, 4, 4, 7, 3.

> **If S4 fails, the stage stops.** A harness that cannot reproduce the recorded
> baseline is measuring itself, and every other number in it is void.

## 6. What each outcome licenses

| Result | What may then be claimed |
|---|---|
| S1 MET | The threshold is **not** a fixed property of lunar imagery at these Δincidence values; it moves under correction. Every existing illumination statement must be re-scoped to "uncorrected pipeline", and the corrected threshold becomes the reportable one. |
| S1 NOT MET, S2 MET | Correction helps but does not cross the decision boundary. The threshold survives photometric correction — a **stronger** result for the original claim than currently held, because the obvious confound is eliminated. |
| S1 and S2 NOT MET | The failure is not photometric. This narrows the cause to geometry, texture or descriptor structure and is **publishable as a null result**. It also materially strengthens REAL-DATA-04's attribution. |
| S3 NOT MET | Inconclusive. Investigate before reporting anything. |

**All four outcomes are reportable.** This is written down now precisely so that
none of them can be reframed later as the one that was expected.

## 7. Threats to validity, registered in advance

- **Roughness is not modelled.** Hapke's shadowing function `S` is omitted, and
  its effect grows with incidence. Frames B and C sit at ~69–70°, so the
  `hapke_hg` arm is least reliable exactly on the edges under test. Recorded in
  every correction artefact, and the reason `lommel_seeliger` — which has no
  free parameters at all — is the primary arm rather than Hapke.
- **Uniform-albedo assumption.** Dividing out `f` recovers reflectance only if
  albedo variation is not itself correlated with the illumination geometry. On
  mare with fresh ejecta this is imperfect and is not corrected for.
- **Decimation.** Every tile is decimated. Correction is applied *after*
  decimation, so it operates on averaged radiance rather than native pixels.
  This is a known approximation and is not remedied here.
- **n is unchanged.** This stage cannot improve the separation p-value; it can
  only change which side of the line an edge falls on. If S1 is met the edge
  counts change and the p-value must be **recomputed**, not carried over.
- **No new significance claim** may be made from this stage without rerunning
  `exact_separation_test` on the post-correction outcomes.

## 8. What this stage does NOT do

No new frames. No re-acquisition. No matcher change. No parameter tuning. No
threshold adjustment. No azimuth claim. No Chandrayaan-2 data. It changes
exactly one thing about a recorded experiment and measures the consequence.

---

## Part 2 — Results

**Run:** the arms of this stage were executed, exactly as frozen in §4, as the
`photometric_ls` and `photometric_hapke` arms of EXP-007 (2026-09-04,
`scripts/run_exp007.py`, 84.2 min, commit 75fb001 for the pre-registration).
Artefact: `experiments/EXP-007/exp007_results.json`, rows with
`arm ∈ {none, photometric_ls, photometric_hapke}` and `tier = tier1`. This
stage has no separate artefact; the numbers below are read from that one.
Every correction record carries the incidence used, the emission used, the
`g = i` note, the factor median, and — for the Hapke arm — the two
reliability caveats §7 required.

### S4 — reproduction: MET

`none` reproduces 5365, 1656, 4, 4, 7, 3 exactly (EXP-007 S4).

### S1 (a failing edge converts under Lommel-Seeliger) — NOT MET

0 of 4. The four failing edges return **4, 4, 7, 3** in the `lommel_seeliger`
arm: the recorded counts, unchanged.

### S2 (median inliers on the failing edges rise ≥ 50 %) — NOT MET

Median 4 → 4, a change of 0 %. Every keypoint count, putative count, inlier
count and transform matrix in the corrected arms is **identical** to `none`.

### S3 (succeeding edges undamaged) — MET

B → C 5365 → 5365, D → A 1656 → 1656. Nothing was damaged because nothing was
changed.

### Why every number is identical — the finding (E-035)

Each per-frame record in the artefact carries
`identical_to_none_after_stretch: true`, and that flag is the result of this
stage. The method frozen in §4 computes one incidence **per frame** (the
archive's published value; emission ≤ 1.75°, so `g = i`) and divides the tile
by the model's reflectance factor at that geometry. With one geometry per
frame the factor is one **scalar** per tile — 0.717 (A) and 1.297 (B) for
Lommel-Seeliger, 0.741 and 1.260 for Hapke-HG — and the very next step of the
recorded pipeline, the per-image percentile stretch, maps any scalar multiple
of a tile to the same stretched image. The correction and the stretch cancel
to floating-point identity, so the matcher saw the same pixels it saw in
REAL-DATA-03 and -04.

This is not a bug in the implementation; the implementation does what §4 says.
It is a **design error in the pre-registration**: the frozen method could not
have changed any outcome for any model, any parameters, and any Δincidence.
Recorded as **E-035** in the error ledger. Under integrity rule 2 this Part 2
is written as the null result it is; under rule 3 §4 is left exactly as it was
frozen.

### What was tried beyond the pre-registration (exploratory, no criterion credit)

EXP-007 added a per-**pixel** Lommel-Seeliger arm (`photometric_ls_pixel`)
whose incidence comes from the local SLDEM2015 facet normal, so the factor is
a field rather than a scalar and survives the stretch. It changes counts and
converts nothing: failing edges 4 → 6, 5365-edge → 2469, 1656-edge → 1197 at
tier 1, and no failing pair passes at any of the four coarser rungs either.
With a 59 m DEM the field is the slope of the DEM, not the slope of the
craters the pixels record, and the correction subtracts a smooth
illumination trend the matcher was never failing on. This arm was not
pre-registered; it is reported as what it is and licenses nothing.

### What each outcome licenses (from §6, applied)

The row that applies is **"S1 and S2 NOT MET: the failure is not photometric"**
— with the amendment that this stage, as designed, could not have detected a
photometric cause even if one existed, because the arm was a no-op. The
stronger, honest statement is: **a per-frame scalar photometric normalisation
cannot move the illumination threshold, by construction; a per-pixel
normalisation from the best available global DEM does not move it either, on
this window.** Every illumination statement in the repository therefore keeps
its "uncorrected pipeline" scope with respect to per-frame correction, and
gains "not rescued by DEM-based per-pixel correction at 59 m" as a measured
addendum. No new significance claim is made (§7: n is unchanged).

### Consequences

- REAL-DATA-06 is **closed** (D-048). The photometric-normalisation question
  is not reopened as a new per-frame stage; a per-pixel arm belongs, if
  anywhere, at a fine-DEM site where the facet slope is the pixel slope
  (SERENRIDGE1; EXP-007's next test).
- The `siim.preprocessing.photometry` module stays: its models are correct and
  tested, and are what a per-pixel correction at a fine-DEM site would use.
  Its docstring now records that a per-frame application is a no-op after
  stretch.
- Lesson for the ledger (E-035 pattern): **a pre-registered treatment must be
  shown to change the input the matcher sees before its effect on the output
  is measured.** A one-line assertion — corrected tile ≠ stretched tile — would
  have caught this before the run.
