# EXP-007 — Does conditioning correspondence on known illumination geometry (DEM rendering) move the real-data illumination threshold, and where does DEM resolution stop it?

**Part 1 — pre-registration. FROZEN 2026-09-04, before any DEM was rendered, any
learned matcher was run on a real tile, and any long-window tile was matched.**
Part 2 is empty and stays empty until Part 1 is committed.

**Classification: RESEARCH-CRITICAL.** This is the first stage in the repository
whose treatment could *succeed* where the recorded baseline fails. Every previous
real-data stage measured a failure it could not fix.

**Origin.** `docs/MASTER_RESEARCH_AND_ARCHITECTURE_PLAN.md` §16 (H0–H5) and §37.
It supersedes nothing: REAL-DATA-06 stays frozen as written and is executed
here as the photometric arms, on the same tiles, with the same rule.

---

## 1. Why this stage exists

Every illumination number this project has reported was measured with an
uncorrected RootSIFT pipeline on two ground windows of 3.7 km × 1.8 km. Six real
LRO NAC edges separate perfectly by Δincidence (successes at 0.96° and 11.73°,
failures at 38.85°–51.54°; exact one-tailed p = 0.0667). Nothing has yet been
tried that could register the failing edges.

The Moon offers a prior no terrestrial registration problem has: the topography
is mapped globally (SLDEM2015, 512 px/deg ≈ 59 m, vertical accuracy 3–4 m) and
the Sun direction at every pixel of every product follows from the archive's
sub-solar point. The literature uses this for terrain-relative navigation (JPL
LIMA, LuNaMaps) and for NAC-to-DEM registration (hillshade + ASIFT + LSM). It has
never been quantified across a GSD ladder for this sensor family with a frozen
success rule.

## 2. The question, in one sentence

**If each image is matched against a DEM rendered under its own Sun, so that the
illumination difference is carried by the DEM rather than by the matcher, do the
currently failing real edges register, and at which ground sampling distance
does the 59 m DEM stop being enough?**

## 3. What exists before this stage runs

| Frame | PDS ID | Incidence | Sub-solar (lon, lat) | Scaled pixel (w × h, m) |
|---|---|---|---|---|
| D | `nac.m1299958135lc` | 18.22° | (22.45, 0.79) | 1.05 × 1.09 |
| A | `nac.m1271742202lc` | 29.95° | (44.82, 0.21) | 0.90 × 0.96 |
| C | `nac.m1452560468lc` | 68.80° | (89.33, −0.07) | 0.82 × 0.89 |
| B | `nac.m1335207975rc` | 69.76° | (90.08, −0.88) | 0.88 × 0.95 |

Recorded edges (tier 1, decimation 2, tiles 2048 × 1024 after decimation):

| Edge | Stage | Δincidence | Inliers | Outcome |
|---|---|---|---|---|
| B → C | RD-03 | 0.96° | 5365 | SUCCEED |
| D → A | RD-04 | 11.73° | 1656 | SUCCEED |
| C → A | RD-03 | 38.85° | 4 | FAIL |
| A → B | RD-03 | 39.81° | 4 | FAIL |
| A → B | RD-04 | 39.81° | 7 | FAIL |
| B → D | RD-04 | 51.54° | 3 | FAIL |

DEM: SLDEM2015 tile `SLDEM2015_512_00N_30N_000_045_FLOAT.IMG` (PDS3, 15360 lines
× 23040 samples, PC_REAL 32-bit, km relative to 1737.4 km, simple cylindrical,
line = (30 − lat) × 512 − 0.5, sample = lon × 512 − 0.5). Byte-range access
verified 2026-09-04 (HTTP 206). Height at the RD-03 target (22.034 E, 20.035 N)
reads −2.75 km, physically consistent with Mare Serenitatis.

Learned engine: DISK (`depth` weights, Apache-2.0) + LightGlue (`disk` weights,
Apache-2.0) via kornia 0.8.3 on CPU (torch 2.10 CPU). Verified to load and run
2026-09-04. SuperPoint/SuperGlue are **not** used (non-commercial licence).

## 4. Data, fixed in advance

**Tier 1 — the recorded tiles.** The six edges above, loaded from the recorded
`.npy` tiles, decimated by 2 then percentile-stretched exactly as
`scripts/rederive_recorded_registrations.py` does. No re-acquisition.

**Tier 2 — long windows on the same two ground points.** For the recorded ground
targets (RD-03: 22.033852 E, 20.035253 N with frames A, B, C; RD-04:
22.010350 E, 19.666255 N with frames A, B, D) a window of **12288 lines ×
5064 samples** (full cross-track width, ≈ 11 km × 4.5 km) is cut on each frame
by the existing geometry-driven acquisition (`scripts/acquire_real_pair.py
--from-geometry`), centred on the same target. This is the same selection
method as REAL-DATA-03/04 with a longer window; it introduces no new ground and
no new frame. Rungs: decimation **k ∈ {4, 8, 16, 32}**, i.e. ≈ 3.6, 7.3, 14.6,
29 m per pixel on frames A/B/C and ≈ 4.3, 8.6, 17, 34 m on frame D. These bracket
the TMC-2 (5 m) rung and approach the IIRS rung by a factor of 3.

Tier 2 exists because tier 1 tiles at coarse rungs shrink to 64 × 32 pixels,
which cannot test anything. The pairs at tier 2 are the same five unordered
pairs as tier 1 (A–B twice, at both targets).

## 5. Method, fixed in advance

Every arm ends in the **unmodified** LO-RANSAC (affine, threshold 3.0 px,
seed 0) and the **unchanged** failure rule `n_inliers <= 8` (D-023).

| Arm | What changes |
|---|---|
| `none` | B1 RootSIFT on the raw pair. Tier 1 must reproduce the recorded counts exactly. |
| `photometric_ls` | REAL-DATA-06 arm: per-frame Lommel-Seeliger normalisation to i = g = 60°, e = 0°, nadir approximation g = i (all emissions ≤ 1.75°), applied after decimation and before the percentile stretch; then B1. |
| `photometric_hapke` | REAL-DATA-06 arm: same with Hapke-HG at literature-default parameters, roughness not modelled. |
| `dem_render_b1` | Two legs. For each frame, the SLDEM2015 heights are sampled onto that frame's tile grid through the archive corner geometry (bilinear frame map, same map RD-02/03/04 used), rendered with the existing Lambertian shading with cast shadows, pixel scale = k × mean scaled pixel, under the Sun direction from `solar_geometry_at` rotated into the tile's pixel frame, elevation = 90° − incidence, no noise. Leg = B1 between the image and its own render. The pair transform is composed through the ground: T_SR = T_R⁻¹ ∘ G_SR ∘ T_S, where G_SR is the corner-geometry map between the two tile grids and T_S, T_R are the leg transforms. |
| `dem_render_lg` | Same two legs with DISK + LightGlue instead of B1. |
| `learned_lg` | DISK + LightGlue on the raw pair (H3). Run at tier 1 and at tier-2 rungs k ∈ {8, 16, 32}; k = 4 is excluded for CPU memory, stated here rather than discovered. |

Learned-engine settings, fixed: DISK `depth` weights, up to 4096 keypoints per
image, LightGlue `disk` weights, default confidence thresholds, images given as
the same percentile-stretched float image replicated to three channels. No
fine-tuning. Mutual-consistency and ratio tests do not apply to LightGlue's
output; its matches go straight to LO-RANSAC.

**Outcome of a two-leg arm on a pair** = PASS only if *both* legs have
`n_inliers > 8`. The composed transform is additionally compared with (a) the
archive-geometry prediction and its discrimination floor
(`scripts/check_transform_against_geometry.py` logic: median disagreement over
a 9 × 9 grid against a floor of 3 × the corner-quantisation Monte-Carlo spread
plus the 1.2 % bilinear model term) and (b) the `none` arm's direct transform
where that arm passed. Both comparisons are **reported, not used as criteria**,
because neither is ground truth.

## 6. Hypotheses and success criteria — FROZEN

**S4 (reproduction, must hold).** The `none` arm at tier 1 reproduces
5365, 1656, 4, 4, 7, 3. *If S4 fails the stage stops.*

**H1 (coarse rungs).** At tier 2, `dem_render_b1` PASSES every one of the four
failing pairs at some rung k ≥ 16.
> **S1 — MET** if ≥ 3 of the 4 failing pairs PASS at k = 16 or k = 32.
> Prediction: MET. Confidence MEDIUM.

**H2 (the bound).** At tier 1 (native, ≈ 1.8 m) `dem_render_b1` does NOT
convert any failing edge.
> **S2 — MET** if 0 of 4 failing tier-1 edges PASS in `dem_render_b1`.
> Prediction: MET (the 59 m DEM cannot resolve what a 1.8 m matcher uses).
> Confidence MEDIUM-HIGH. If S2 is NOT MET the result is *better* than
> predicted and is reported as such; nothing is re-scoped.

**H3 (learned zero-shot).** `learned_lg` converts at least one failing tier-1
edge.
> **S3 — MET** if ≥ 1 of 4 failing tier-1 edges has `n_inliers > 8` in
> `learned_lg` **and** its transform agrees with the archive-geometry prediction
> within the discrimination floor. Prediction: UNKNOWN (this is the experiment
> competitors will win if it is MET and we ignore it). Confidence LOW.

**H4 (photometric control).** Neither photometric arm changes any tier-1
outcome.
> **S5 — MET** if all six tier-1 outcomes are unchanged in both photometric
> arms. Prediction: MET. Confidence HIGH. This fills REAL-DATA-06 Part 2.

**H5 (control, must hold).** No arm breaks a succeeding pair.
> **S6 — MET** if B → C and D → A remain PASS in every arm at every rung where
> the `none` arm passes them. If S6 fails for an arm, that arm's other results
> are reported but its S1/S3 credit is void.

**Rung transition (reported, not a criterion).** For each failing pair the
smallest k at which `dem_render_b1` PASSES is recorded as the measured DEM
bound for this DEM and this terrain.

## 7. What each outcome licenses

| Result | What may be claimed |
|---|---|
| S4 fails | Nothing. Harness broken. |
| S1 MET, S2 MET | H0 supported within scope: DEM conditioning moves the illumination threshold at TMC-scale GSD and is resolution-bounded. The threshold becomes a property of DEM/GSD ratio, not of the Moon. |
| S1 MET, S2 NOT MET | Stronger than predicted; the 59 m DEM already suffices at native NAC scale on this terrain. Report; do not extrapolate to other terrain. |
| S1 NOT MET, S2 MET | H0 REFUTED for SLDEM2015 on this terrain at every tested rung. Possible causes to distinguish in Part 2: DEM too coarse even at 29 m (mare relief too low), render model, corner-geometry offset larger than the matcher's search. A NAC-DTM site is the next test; nothing here is re-scoped. |
| S3 MET | A licensable zero-shot learned engine already crosses the threshold at native scale. It becomes an engine arm of the architecture; the physics layer is then justified by scale, viewpoint and verification, not by illumination at this rung. |
| S3 NOT MET | Learned zero-shot does not rescue the fine rung on this data. |
| S5 NOT MET | Photometric normalisation alone moves a real outcome; REAL-DATA-06's own table applies. |
| S6 NOT MET for an arm | That arm damages what works; its results are inconclusive. |

All outcomes are reportable. None may be reframed later as the expected one.

## 8. Threats to validity, registered in advance

- **Corner-geometry offset.** Frame corners are quoted to 0.01°, so the render
  is misplaced relative to the image by up to ~150 m (≈ 80 px at k = 2, ≈ 5 px
  at k = 32). The legs must absorb this as a translation. A leg that fails
  because the offset exceeds the matcher's tolerance is a real failure of this
  method as built and is reported as such.
- **DEM resolution vs mare relief.** Mare Serenitatis is low-relief; the DEM may
  carry little shading structure at any rung. This is what S1 tests.
- **Render model.** Lambertian with cast shadows, unit albedo, no noise. The
  image carries albedo variation the render does not. Any mismatch counts
  against the method.
- **Anisotropic pixels.** NAC pixels are 0.90 × 0.96 m etc.; the render uses
  the mean. The 3 % anisotropy is absorbed by the affine model.
- **Learned-engine determinism.** DISK/LightGlue are deterministic on CPU at
  fixed inputs; verified by running twice and recording both counts.
- **No ground truth.** No arm's transform is verified; PASS means the rule,
  composed transforms are corroborated against geometry only.
- **n is small.** Four failing pairs, two succeeding. No significance claim
  is made from this stage.

## 9. What this stage does NOT do

No new frames, no new ground, no matcher tuning, no threshold change, no
Chandrayaan-2 data, no azimuth claim, no sub-pixel claim, no NAC DTM (none is
known to cover this window; that is the next stage if S1 is NOT MET).

---

## Part 2 — Results

**Run:** 2026-09-04 20:51–22:15, `scripts/run_exp007.py` (full run; Part 1 frozen
at commit 75fb001), **84.2 min CPU**, 199 rows. Artefact:
`experiments/EXP-007/exp007_results.json` (+ `exp007_results_rows.csv`); log
`experiments/EXP-007/logs/run_full.log`. Environment: CPython 3.13.7, numpy
2.3.3, OpenCV 5.0.0, torch 2.10.0+cpu, kornia 0.8.3, Windows 11. A smoke run and
a preliminary tier-1 run of all arms are preserved under `logs/`; their tier-1
numbers are identical to the full run's.

Arms run exactly as Part 1 §5 lists them, plus two **exploratory** arms that
were not pre-registered and carry no criterion credit: `photometric_ls_pixel`
(Lommel-Seeliger with a *per-pixel* incidence from the SLDEM facet normal,
added when the pre-registered per-frame arms turned out to be a no-op, §S5
below) and `learned_lg_repeat` (a second run of one edge, for determinism).
`learned_lg` and `dem_render_lg` were not run at k = 4 (stated in advance in
Part 1 §5); `dem_render_lg` was also not run at tier-2 k = 4.

### S4 — reproduction gate: MET

The `none` arm at tier 1 reproduces every recorded count exactly: A → B **4**,
B → C **5365**, C → A **4** (RD-03); A → B **7**, B → D **3**, D → A **1656**
(RD-04). Keypoint, putative and inlier counts and the transform matrices agree
with the recorded artefacts to the digit. The harness is the recorded harness.

### S1 (DEM render converts the failing pairs at k ≥ 16) — NOT MET

`dem_render_b1` passed **0 of 4** failing pairs at k = 16, **0 of 4** at
k = 32, and 0 of 4 at every other rung. No rung transition exists to report;
`rung_transition_smallest_passing_k` is empty. Every leg (image against the
render of its own ground under its own Sun) returned **0–7 inliers**, and most
legs returned 0–3.

The cause is visible in the leg statistics rather than needing to be inferred.
The render side carried almost no detectable structure at any rung:

| rung | image keypoints (B1, typical) | render keypoints (B1) | render putative → inliers |
|---|---|---|---|
| tier 1, 1.8 m | 9 500–12 600 | **0** on A and D, 7–17 on B and C | 0–6 → 0–3 |
| k = 4, 3.6 m | 12 000–20 700 | 7–171 | 1–22 → 0–3 |
| k = 8, 7 m | 3 400–7 700 | 6–176 | 0–20 → 0–4 |
| k = 16, 15 m | 1 500–3 100 | 4–160 | 0–11 → 0–4 |
| k = 32, 30 m | 560–1 000 | 5–86 | 0–5 → 0–3 |

The high-Sun frames A and D render to a near-uniform surface (0–19 SIFT
keypoints at every rung); the low-Sun frames B and C render to a soft
undulation with 57–176. `logs/render_check_tier1_rd04.png` shows it: the NAC
tiles are dominated by 10–100 m craters and boulders, and a 59 m DEM contains
none of them. DISK (`dem_render_lg`) detects its usual 4096 points on the
render because it always returns a fixed budget, and LightGlue then finds
0–24 putative matches with 0–7 inliers — the same result by a different route.

Of the three causes Part 1 §7 asked Part 2 to distinguish, this is the first:
**the DEM is too coarse for the relief this mare window has**, at every rung
down to 30 m. It is *not* the corner-geometry offset (an offset failure would
show hundreds of render keypoints and no consistent matches; here there are no
keypoints to mismatch), and the render model cannot be blamed for structure
the height field does not contain. Whether a better model would matter on a
fine DEM is untested here and is exactly what the SERENRIDGE1 site (NAC DTM,
5 m posts) would answer.

### S2 (no tier-1 conversion by the DEM render) — MET

0 of 4 failing tier-1 edges pass in `dem_render_b1`. Predicted, and for the
reason predicted.

### S3 (learned zero-shot converts a failing tier-1 edge) — MET

`learned_lg` (DISK + LightGlue, Apache-2.0, CPU) at tier 1 on the four failing
edges:

| edge | Δinc | recorded B1 | `learned_lg` inliers / putative | vs archive geometry (median disagreement / floor) | counts for S3? |
|---|---|---|---|---|---|
| C → A (RD-03) | 38.85° | 4 | **56 / 72** | **CONSISTENT** — 47.4 px / 104.1 px | **yes** |
| A → B (RD-03) | 39.81° | 4 | 38 / 46 | INCONCLUSIVE — 108.1 px / 91.2 px | no (rule passed, geometry did not) |
| A → B (RD-04) | 39.81° | 7 | 3 / 3 | — | no |
| B → D (RD-04) | 51.54° | 3 | 3 / 3 | — | no |

One edge satisfies both halves of S3, which is the criterion's threshold. It is
recorded as MET on **one** edge with a **56-inlier** transform whose agreement
with the archive is inside the ~100 px discrimination floor: corroborated at
that scale, not verified, and not a sub-pixel statement.

**Determinism (Part 1 §8).** The repeated edge (`learned_lg_repeat`, A → B
RD-04) returned 3 inliers both times. That is the weakest possible
demonstration — a failing edge — and is stated as such; REAL-DATA-07 runs the
engine on 42 pairs and is where a repeat on a succeeding edge belongs.

### S5 (photometric arms change no tier-1 outcome) — MET, for a reason that voids the arms

Both `photometric_ls` and `photometric_hapke` returned counts **identical** to
`none` on all six edges (4, 5365, 4, 7, 3, 1656; same keypoints, same
matrices). Every per-frame record carries
`identical_to_none_after_stretch: true`. The reason is arithmetic, not
physics: the pre-registered correction applies one factor per **frame**
(incidence taken as the frame's published value, `g = i` under the near-nadir
approximation), so it multiplies the whole tile by a scalar (0.72 for A, 1.30
for B under Lommel-Seeliger), and the percentile stretch that follows divides
that scalar straight back out. REAL-DATA-06's arms, exactly as frozen, could
never have changed any outcome. This is logged as **E-035** and fills
REAL-DATA-06 Part 2; S5 is MET, and the finding is that the criterion was
answered by construction rather than by the Moon.

The exploratory per-pixel arm was added to see whether a correction that
*can* change the image does anything useful. It does change counts — B → C
5365 → 2469, D → A 1656 → 1197, C → A 4 → 4, A → B (RD-03) 4 → 6 — and converts
**no** failing edge at any rung while costing 25–55 % of the inliers on the
succeeding ones. With a 59 m DEM the per-pixel incidence (A: 17.5–44.1°, B:
59.2–83.8°) is the DEM's slope field at 59 m, not the crater-scale slope the
pixels actually see; the correction adds a smooth multiplicative field the
matcher did not need and removes nothing it was failing on.

### S6 (no arm breaks a succeeding pair) — NOT MET, for the two DEM-render arms only

`dem_render_b1` and `dem_render_lg` fail on B → C and D → A at **every** rung
where `none` passes them (0–3 composed inliers), so by Part 1 §6 their S1/S3
credit is void. They had none to void. The arms that carry credit break
nothing:

| arm | B → C (k = 2 / 8 / 16 / 32) | D → A (k = 2 / 8 / 16 / 32) |
|---|---|---|
| `none` | 5365 / 3054 / 1373 / 566 | 1656 / 1665 / 693 / 243 |
| `learned_lg` | 2305 / 3026 / 2646 / 724 | 2016 / 2644 / 2697 / 625 |
| `photometric_ls`, `photometric_hapke` | = `none` | = `none` |
| `photometric_ls_pixel` (exploratory) | 2469 / 242 / 17 / 12 | 1197 / 894 / 360 / 160 |

The `none` arm also passes both succeeding pairs at k = 4 (9460 and 3693).

### Tier 2 — the illumination envelope by rung (reported, not a criterion)

Composed two-leg arms aside, the tier-2 long windows (12288 × 5064 samples,
≈ 11 × 4.5 km) give the first view of how the *direct* arms behave as GSD
coarsens. Inliers, with the archive-geometry verdict in brackets (C =
CONSISTENT, I = INCONCLUSIVE, X = INCONSISTENT; the floor shrinks with k
because it is quoted in pixels):

| pair | Δinc | arm | k = 4 (3.6 m) | k = 8 (7 m) | k = 16 (15 m) | k = 32 (30 m) |
|---|---|---|---|---|---|---|
| A → B (RD-03) | 39.81° | `none` | 4 (X) | 4 (X) | 4 (X) | 3 (X) |
| | | `learned_lg` | — | **1434 (C)** | **2042 (C)** | **511 (C)** |
| C → A (RD-03) | 38.85° | `none` | **10 (C)** | 4 (X) | 6 (C) | 3 (X) |
| | | `learned_lg` | — | **1348 (C)** | **1863 (C)** | **475 (C)** |
| A → B (RD-04) | 39.81° | `none` | **10 (C)** | **9 (C)** | **10 (C)** | 8 (C) |
| | | `learned_lg` | — | **1409 (C)** | **1536 (C)** | **447 (C)** |
| B → D (RD-04) | 51.54° | `none` | 3 (X) | 3 (X) | 3 (X) | 3 (X) |
| | | `learned_lg` | — | 0 | 5 (C) | 37 (I) |

Bold = passes the D-023 rule. Three findings, in decreasing strength:

1. **The learned engine registers the ≈ 39–40° pairs at 7, 15 and 30 m with
   hundreds to thousands of geometry-consistent inliers** (median disagreement
   2.7–28 px against floors of 7.7–33 px). Its tier-1 result on C → A is not a
   fluke of one tile; it holds on three of the four failing pairs at every
   coarser rung tested. It does **not** cross 51.54°: B → D gives 0, 5 and 37
   inliers, the last passing the rule with a transform the geometry check can
   neither confirm nor refute (7.1 px against a 6.8 px floor).
2. **RootSIFT itself crosses the rule at coarser GSD on two of the four pairs,
   by one or two inliers.** C → A at 3.6 m (10 inliers) and A → B (RD-04) at
   3.6–15 m (10, 9, 10), each with a geometry-consistent transform, and 8
   inliers — a fail by exactly one — at 30 m. These are passes at the edge of
   D-023, whose false-alarm rate in the mixed regime is 0.369 (EXP-003), so they
   are reported as *marginal, geometry-consistent passes*, not as conversions.
   The mechanism is plausible (decimation averages out the sub-10 m shading
   texture that changes most with the Sun) and is not tested here.
3. **The B → C edge is INCONCLUSIVE against archive geometry at every rung**
   (161.9 px / 104.6 px at tier 1; 10.1 / 8.3 at k = 32), for every arm that
   passes it, learned or classical. This was already the case in REAL-DATA-03
   and is a property of that pair's corner geometry, not of any arm; D → A is
   CONSISTENT for every passing arm at every rung.

### What is claimed and what is not

- **Claimed:** on this mare window, DEM-render conditioning with SLDEM2015
  produces no usable correspondence at any rung from 1.8 m to 30 m, because
  the 59 m height field contains none of the relief the images are made of.
  H0 is not supported at any tested rung with this DEM (Part 1 §7, row
  "S1 NOT MET, S2 MET"). It is **not** refuted for a fine DEM; that is untested.
- **Claimed:** a licensable, CPU-only learned engine (DISK + LightGlue)
  registers one failing real edge at native scale (56 inliers, C → A, 38.85°,
  CONSISTENT) and three of four at 7–30 m, where the unmodified RootSIFT
  baseline returns 3–10. The transforms are corroborated against archive
  geometry inside its ~100 px (tier 1) to ~8 px (k = 32) floor. No ground truth
  exists; nothing here is an accuracy figure.
- **Claimed:** per-frame photometric normalisation of the REAL-DATA-06 kind is
  a no-op after per-image stretch (E-035). Per-pixel normalisation from a 59 m
  DEM changes counts and converts nothing.
- **Not claimed:** any azimuth result; any sub-pixel number; anything about
  Chandrayaan-2 or any modality other than NAC ↔ NAC; that the learned
  engine's 51.54° behaviour generalises; that the marginal RootSIFT passes at
  coarse rungs are robust.

### Consequences

- **H0 is demoted from central to conditional** (D-046): the DEM-render tier of
  the architecture is kept only for sites with a DEM finer than the matcher's
  working GSD, and is retired on this window. The next test is the SERENRIDGE1
  NAC-DTM site.
- **B4L becomes an engine arm of the architecture** (D-047, superseding D-028's
  deferral): the illumination engine at the fine and mid rungs on mare is the
  learned engine, and the physics layer's jobs are overlap, prior transform,
  scale and verification.
- REAL-DATA-06 is closed from this artefact (Part 2 written there; D-048,
  E-035). REAL-DATA-07 measures the learned engine's envelope on 42 real pairs;
  REAL-DATA-08 takes it to radar and 100 m.
- S6 as worded is NOT MET; the wording is kept, the two arms it voids are the
  two that already failed everything, and the arms that carry this stage's
  results break nothing.
