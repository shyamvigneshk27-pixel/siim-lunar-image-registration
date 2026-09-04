# EXP-011 — Which transform model, chosen by what evidence, and does re-estimation from refined points remove the E-034 bias?

**Part 1 — pre-registration. FROZEN 2026-09-04, before any model-selection code
was written.** Part 2 is empty until Part 1 is committed.

**Classification: ACCURACY-CRITICAL.** E-034 (ERROR_LEDGER) showed that the
default affine model recovers a pure integer self-shift of frame D to 0.99 px
median / 2.31 px maximum with 11 849 inliers and a zero residual, while a
translation model recovers it to 0.002 px. Every recorded real edge used the
affine default. The verdict engine has no model-selection step.

## 1. The mechanism, stated so it can be refuted

The keypoints on frame D (high Sun, low contrast, percentile-stretched noise)
are localised with an error that is **spatially correlated** across the tile.
A translation fit averages that error out; an affine fit absorbs it into the
linear terms as a spurious shear of 3e-3. Because the error is shared by the
keypoints themselves, **any selection rule built from the keypoints' own
residuals, held-out or not, will prefer the model that absorbs the error**.
The bias is invisible from inside the correspondence set. Two things can see
it: ground truth (available on self-warps), and points whose localisation
error has been removed by local area-based refinement (EXP-010: 0.30 → 0.009
px on this tile).

## 2. Questions

**Q1.** Does held-out residual on the raw inliers select the true model on
self-warps of the four recorded tiles? Prediction: **no** on frame D (it selects
affine for a translation truth). This is the refutation test of fit-based
selection.

**Q2.** Does re-estimating the transform from **refined** points, then
selecting by held-out residual on those points, select the true model and reach
< 0.05 px dense error? Prediction: **yes** for translation and similarity
truths; affine truths are selected as affine.

**Q3.** Does a **geometry prior** rule (similarity when both frames are
near-nadir and the archive's scaled pixels are known, affine otherwise) reach
the same accuracy without any selection statistic?

## 3. Data, fixed in advance

Self-warps of the four recorded tiles (A, B, C, D, decimation 2), truth models
translation (7.25, −4.75), similarity (scale 1.05, rotation 2°, anchored at the
centre), affine (shear 0.02, scale 0.98/1.03), projective (perspective 2e-5), 3
seeds of B1 (0, 1, 2) → 48 cases. Plus the six recorded real edges' inlier sets
from the recorded artefacts, where no truth exists and only the geometry
disagreement can be reported.

## 4. Method, fixed in advance

1. B1 inliers under the affine default (as recorded).
2. Candidate models: translation, similarity, affine, projective.
3. Selection rule A — **held-out on raw inliers**: 5-fold, median held-out
   residual, choose the simplest model within 10 % of the best.
4. Selection rule B — **held-out on refined points**: refine every inlier with
   ECC 48 (EXP-010), drop points whose refinement was not `ok`, then rule A on
   the refined set.
5. Selection rule C — **geometry prior**: similarity if both frames have
   emission ≤ 5° and archive scaled pixels; else affine; re-estimated from
   refined points.
6. Score every (case, rule) by dense endpoint error against truth over a 16 px
   grid; report the selected model and the error; bootstrap CIs.

## 5. Hypotheses and criteria — FROZEN

**S1 (fit-based selection is refuted where it matters).** Rule A selects a
model other than the truth on ≥ 1 of frame D's 3 translation cases **and** the
selected model's dense error is ≥ 5× the truth model's. Prediction: MET.

**S2 (refined re-estimation recovers the truth).** Rule B's dense median error
< 0.05 px on all translation and similarity cases across all four tiles, and
its selected model equals the truth model on ≥ 90 % of the 48 cases.
Prediction: MET. Confidence MEDIUM.

**S3 (prior rule).** Rule C's dense median error < 0.05 px on all translation
and similarity cases. Prediction: MET. Confidence MEDIUM-HIGH.

**S4 (real edges, reported).** For the two succeeding real edges, the change in
archive-geometry disagreement under rules B and C versus the recorded affine.
Reported, not a criterion (no truth).

**Gate.** Rule B on the identity self-warp must select translation with
< 0.01 px error on all four tiles.

## 6. What each outcome licenses

S1 MET: the deliverable's model choice may not rest on residual statistics
alone; the verdict engine gains a "model selected by" field. S2 or S3 MET:
the pipeline order becomes estimate → refine → re-estimate → verify, and the
recorded D → A and B → C edges are re-reported with the re-estimated transform
beside the recorded one (the recorded artefacts are not edited).

## 7. What this stage does NOT do

No change to any recorded artefact or frozen rule. No new data. Self-warps
share texture with their originals, so absolute errors are upper bounds.

---

## Part 2 — Results

**Run:** 2026-09-04, `scripts/run_exp011.py` (commit 37244d4), 26.0 min, 52
cases (4 tiles × 4 truths × 3 seeds + 4 identity gates), B1 passed on all.
Artefact: `experiments/EXP-011/exp011_results.json`.

**Implementation clarification, recorded:** the selection rule "simplest model
within 10 % of the best held-out median" (Part 1 §4.3) carries an absolute tie
floor of 0.005 px, because on an exact self-warp every model's held-out
residual is ~1e-9 and a purely relative tolerance chose by rounding noise. The
floor cannot change a selection where models genuinely differ.

### Gate — MET
Identity self-warp, rule B: translation selected on all four tiles, error
< 0.01 px.

### S1 (fit-based selection refuted on D) — NOT MET. H1's mechanism half right.
Rule A selected **translation** on all three D cases, with error 0.002 px. The
prediction that it would select affine was **wrong**. What the artefact shows
is why: the held-out residuals of the translation and affine models on D are
**0.0338 versus 0.0336 px**, i.e. indistinguishable, exactly as the mechanism
in Part 1 §1 says (the correlated localisation error is invisible from inside
the correspondence set). The rule chose correctly only because of its
**simplicity preference**, not because the evidence separated the models.
That is a weaker guarantee than "selected by evidence" and is stated as such:
rule A works on these cases by construction of the tie-break, and would fail
on any case where the wrong model's held-out residual is more than 10 % better,
which none of these 48 cases produced.

### S2 (refined re-estimation) — MET
Rule B (refine with ECC 48, then select on refined points) selected the truth
model in **48 of 48** cases and reached a pooled dense median error of
**0.0018 px** (95 % CI 0.0013–0.0033) against **0.0975 px** (CI 0.022–0.355)
for the recorded affine default. On frame D's translation cases: affine
default 0.19 / 0.37 / 0.31 px → rule B 0.0034 / 0.0003 / 0.0012 px. On frame A:
0.44 / 0.94 / 0.34 → 0.0016 / 0.0024 / 0.0013.

### S3 (geometry prior) — MET
Rule C (similarity, re-estimated from refined points) reached < 0.05 px on
every translation and similarity case (pooled 0.0051 px). Its CI upper bound
of 2.8 px comes from the affine and projective truths, where a similarity prior
is wrong by construction; the rule is only proposed for near-nadir same-sensor
pairs, and this is the measured cost of applying it elsewhere.

### E-034 in numbers
The affine default's error on pure-translation self-warps is 0.19–0.94 px on
frames A and D and 0.002–0.003 px on B and C. Frames A and D are the two
low-incidence (18°, 30°) tiles: high Sun, low contrast, texture dominated by
stretched noise. Correlated localisation error is a property of the *tile*,
not of the model, and the affine model is what exposes it.

### Consequences
- Pipeline order becomes **estimate → refine → re-estimate with selection**;
  rule B is the deployed rule, rule A is the fallback when refinement fails.
- The verdict gains a `model_selected_by` field.
- The recorded D → A and B → C transforms are not edited; REAL-DATA-07 reports
  rule-B re-estimates beside them for every pass.
- H1's mechanism is confirmed (held-out cannot see the bias); H1's predicted
  *consequence* (wrong selection) did not occur under the simplicity tie-break.
  Recorded as a partial refutation, not reframed.

