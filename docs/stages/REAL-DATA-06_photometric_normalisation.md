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

*Empty. To be written only after Part 1 is committed and the run has completed.*
