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

*Empty. To be written only after Part 1 is committed and the run has completed.*
