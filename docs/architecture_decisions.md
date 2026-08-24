# Architecture Decision Record (spec §100)

Each entry: **Decision · Alternatives · Evidence · Trade-offs · Rationale · Status.**
Status values: `PROPOSED` (reasoned, not yet validated) · `ACCEPTED` (validated by experiment) · `SUPERSEDED` · `REJECTED`.

As of 2026-08-24 (after EXP-000, EXP-001 and EXP-002): **6 of 12 accepted, 6 still proposed.** A `PROPOSED` decision is reasoned but unvalidated, and each carries the experiment that will confirm or overturn it. Marking these honestly is the point of the register — ADR-0009 records a hypothesis our own measurement failed to support.

---

## ADR-0001 — Pluggable matcher engine behind a fixed protocol

**Decision.** Architect the system as a fixed geometric protocol (scale normalisation → representation → coarse localisation → tiled matching → verification & model selection → coverage selection → sub-pixel refinement → confidence) with the **matcher as a swappable component behind a stable interface**. Do not select the matcher now.

**Alternatives considered.**
- (a) Commit to a single learned matcher and build around it — the common approach.
- (b) Commit to a purely classical pipeline for full explainability.
- (c) Ensemble several matchers and fuse.

**Evidence.** S4 (arXiv 2604.10217): protocol choices change mean error by **up to 33×** for a fixed matcher, exceeding the top-tier-vs-mid-tier matcher gap; affine vs homography alone moved mean error 12.3 → 9.7 px. `[EVIDENCE — but from SAR-optical, not lunar; transfer is HYPOTHESIS pending EXP-006.]`

**Trade-offs.** An abstraction boundary costs engineering effort and slightly constrains engine-specific optimisations. It buys the ability to benchmark every baseline through an identical harness (which spec §49 demands anyway), and it removes the risk of the whole project being hostage to one model's licence, weights, or CPU latency.

**Rationale.** If the evidence transfers, this places our effort on the dominant axis. If it does *not* transfer, we still have a clean harness and lose nothing but the headline framing. The downside is bounded; the upside is the project's thesis. It is also the only architecture that stays viable under the CPU constraint (ADR-0002) without betting the project on one engine's inference speed.

**Status:** `PROPOSED` → confirm/refute at EXP-006.

---

## ADR-0002 — CPU-first engine selection; GPU is optional, never a dependency

**Decision.** All engines are ranked by **measured** latency and accuracy on the actual development CPU. Any GPU access is used only for training experiments and heavy ablations, never as a runtime dependency of the delivered system.

**Alternatives.**
- (a) Target GPU and require judges/deployers to have one.
- (b) Rent cloud GPU for the deliverable.
- (c) Restrict to classical methods only, sidestepping the issue.

**Evidence.** Measured: no CUDA device, 4C/8T, 15.2 GB RAM (RL-001). Published latency, GPU: XoFTR 0.4 s/pair vs RoMa 5.0 s/pair (S4). CPU multipliers are `[UNKNOWN]` and will be measured in EXP-005.

**Trade-offs.** Gives up the top of the accuracy leaderboard (RoMa / MINIMA-RoMa, S4/S6). Gains a system that runs anywhere, reproduces trivially, and cannot fail on demo day for want of a device.

**Rationale.** A deliverable that requires hardware we do not have is not a deliverable. Spec §56 asks us to read "manufacturability" as deployment simplicity — CPU-only *is* the deployment-simple answer, and it is honestly defensible to ISRO rather than being a concession we hide. Option (c) is rejected because it forecloses learned engines before measuring them, which is exactly the kind of unmeasured assumption spec §21 forbids.

**Status:** `PROPOSED` → EXP-005 fixes the ranking.

---

## ADR-0003 — Accuracy is reported from non-circular estimators; RMSE never stands alone

**Decision.** Report the required RMSE, but always alongside at least one non-circular estimator, and label every RMSE as `fit` or `held-out`. The headline accuracy claim is the **worst** applicable estimator, not the best.

> **Superseded in part by ADR-0011.** This ADR originally named the K-fold cross-validated residual as the *primary* GT-free estimator, with loop closure as a secondary coherence check. EXP-002 objective 4 measured the opposite: the held-out residual is **blind to coherent wrong solutions** (0.47 px reported on a match set 64 px wrong), while loop closure detects them at 100%/0%. **Loop closure is primary; the held-out residual is a degeneracy detector.**

**Alternatives.**
- (a) Report inlier RMSE, as is standard in this literature (including S3).
- (b) Report only synthetic-GT error, where truth is exact.
- (c) Manually annotate ground-truth tie points.

**Evidence.** Structural argument, not empirical: inlier RMSE is computed on points selected for fitting the model, and decreases monotonically as the RANSAC threshold tightens. It is therefore a fit statistic, not an accuracy. Independently, it cannot detect the coherent-wrong-solution failure (ANALYSIS §B6) because a uniformly shifted match set is self-consistent. `[FACT by construction.]`

**Trade-offs.** Our headline numbers will look *worse* than competitors reporting fit RMSE on identical performance. That is a real competitive cost and must be handled by explaining the distinction rather than by quietly matching their reporting. Option (c) is rejected: manual annotation cannot reach reliable sub-pixel truth, and spec §77/§78 forbid human-in-the-loop in the final pipeline.

**Rationale.** The problem asks for *sub-pixel accuracy*. A claim of sub-pixel accuracy backed by a circular statistic will not survive a competent reviewer, and §84.13 ("how do you know your test isn't leaking?") is on the anticipated question list. Turning the weakness into an explicit methodological contribution is both more honest and, we judge, more persuasive than hiding it.

**Status:** `ACCEPTED` (2026-08-24), diagnosis confirmed in EXP-001 and the estimator stack discharged in EXP-002 — with the primary/secondary ordering **reversed** by measurement (ADR-0011).

**Validation — stronger than the decision originally claimed.** Of 17 EXP-001 cases that were wrong (true error > 3 px), **11 reported fit RMSE below 1e-12 px** while being 190–2400 px wrong (e.g. 5.68e-14 px at 325.59 px true error). The mechanism is algebraic: an affine model has 6 DOF, so at its **minimal set of 3 correspondences** the least-squares fit interpolates them exactly and the residual vanishes by construction. (Corrected in EXP-002, RL-021: exact interpolation holds at *n = minimal set*, not at "3–4 points" as first written — 4 random pairs give 27.85 px. The empirical observation is unaffected, because RANSAC *selects* mutually consistent points, so a 4th inlier is by construction near-consistent with the 3-point fit.)

So fit RMSE is not merely circular and gameable, as this ADR argued — **in the failure regime it is inverted**, attaining its best possible value at the moment of total failure. An evaluation quoting inlier RMSE alone would have ranked these catastrophic failures as its best results.

**Reporting rule extended:** every RMSE must be quoted with its inlier count, because RMSE is uninterpretable without knowing how close `n` is to the model DOF. Codified in `test_fit_rmse_collapses_when_inliers_approach_model_dof`.

**Discharged in EXP-002.** All four GT-free estimators are built (`siim.evaluation.gtfree`) and scored against ground truth. The result was not the one this ADR assumed — see **ADR-0011**: only loop closure detects a coherent wrong solution; held-out residual and spatial split consistency are blind to it.

Independent support arrived from the negative control in EXP-002 objective 3: `fit_rmse` scored **ROC AUC 0.495** on 192 unseen cases — indistinguishable from a coin flip — while `n_inliers` scored 0.993. Fit RMSE carries no failure information whatsoever.

---

## ADR-0004 — Illumination robustness via polarity-agnostic structure, not intensity normalisation

**Decision.** The default matching representation is polarity-agnostic structure (gradient orientation modulo π, or phase congruency), not raw or contrast-normalised intensity.

**Alternatives.** (a) Raw intensity. (b) CLAHE / histogram matching. (c) Learned invariance only (rely on the matcher). (d) Physical relighting / photometric normalisation to a common Sun geometry.

**Evidence.** Structural: SIFT/ORB/AKAZE descriptors encode gradient orientation over [0, 2π); a ~180° azimuth change reverses gradient sign across crater rims, so corresponding descriptors differ by π `[FACT by construction]`. Contrast normalisation is sign-preserving and therefore cannot repair this. Empirical support in direction: classical methods degrade under polar lighting on CH-2 data (S3). Phase congruency underlies RIFT2/HOPC/CFOG, designed for multimodal remote sensing.

**Trade-offs.** Structural representations discard absolute radiometry, which loses information where illumination happens to be similar — so on *easy* pairs this may slightly underperform intensity matching. Phase congruency also costs compute. Option (d) is attractive physically but needs a DEM plus accurate Sun geometry, and is circular for the OHRC case where no DEM exists at matching resolution.

**Rationale.** The problem statement names Sun-angle invariance as a core requirement, so the hard case is the design point, not the average case. Prefer a representation whose invariance is *provable by construction* over one that is merely trained and hoped for.

**Status:** **`SUPERSEDED` (2026-08-24, EXP-003).** Raw intensity won. The register exists to record that outcome, not to defend the guess.

> **Supersession record — EXP-003, RL-023.** EXP-003 ran the sweep this ADR asked for: 594 evaluations, 6 arms, 3 regimes × 3 seeds × 11 azimuths, one shared image pair per case. The pre-registered criterion — last fully-successful Δazimuth **strictly > 30°** on both realistic A-regimes — was met by **no arm** (`exp003_representations.json:verdict`).
>
> The ADR's own mechanism fared worst. `A_orient_mod_pi` — gradient orientation binned mod π, this ADR's primary proposal — is the **weakest of the six arms**: last fully-successful Δaz **0°** on mare and **21°** on highlands, against the raw-intensity baseline's 21°/27°. Head-to-head against an otherwise-identical 2π descriptor on **identical keypoints**, mod-π **wins 0, loses 38, ties 61**. At Δaz 0 both yield ~770 putative matches, so this is not a distinctiveness deficit: mod-π degrades specifically under illumination change, which is the one thing it was adopted to survive.
>
> Phase congruency did not rescue it either. It is contrast- and polarity-invariant *by construction* — verified to **1e-6** and **exactly 0.0** respectively (`tests/test_representations.py`) — and still bounded at 27–30° on A-regimes, because shadow motion changes **which structures exist**, not merely their contrast. That distinction is what this ADR missed.
>
> **What replaces it.** EXP-003's control arm produced the only positive effect, and a direct probe found the mechanism: **SIFT's assigned dominant orientation drifts almost 1:1 with Sun azimuth** (median |Δangle| 6.7° → 44.8° as Δaz goes 0° → 45°; 67% of keypoints off by >30° at 45°). The failure at these azimuths is orientation **assignment**, not orientation **binning**. That is a *refinement* of this ADR's diagnosis, not a vindication of its prescription — and it is **post-hoc**, so it is recorded as D-024, a pre-registration target for EXP-004, and explicitly **not** as an accepted decision.

---

## ADR-0005 — Scale normalisation is a required pipeline stage, not preprocessing

**Decision.** An explicit scale-normalisation stage runs before matching, driven by metadata GSD where available and by log-polar / Fourier-Mellin or pyramid search where not.

**Alternatives.** (a) Rely on the matcher's own scale invariance. (b) Multi-scale matching without explicit normalisation. (c) Require metadata.

**Evidence.** Derived from verified GSDs (S1, S2): pairwise ratios of 2:1, 10:1, 16:1, 20:1, 160:1, **320:1** (RL-002). Off-the-shelf matchers are reliable to roughly 2–4×. Four of six pairs exceed that; two by two orders of magnitude. `[FACT — mission hardware, independent of any dataset.]`

**Trade-offs.** Resampling introduces interpolation error and aliasing — spec §41 warns precisely about manufacturing false correspondences this way. Mitigation: anti-aliased downsampling of the finer image toward the coarser (never upsampling the coarser, which invents information), with the resampling factor tracked in the coordinate contract so residuals are always reported in the *native* pixel units of the image being registered.

**Rationale.** Option (a) is refuted by the numbers. Option (c) is refused by spec §24 (must degrade gracefully without metadata).

**Status:** `PROPOSED` → EXP-004 sweeps the real ladder and finds where normalisation stops rescuing the match.

---

## ADR-0006 — `max_uncovered_disc_radius` as the primary coverage metric

**Decision.** Primary coverage metric is the radius of the largest disc within the overlap region containing no selected correspondence. Grid occupancy, spatial entropy, convex-hull ratio and NN-distance distribution are reported as secondary.

**Alternatives.** (a) Grid occupancy as primary. (b) Spatial entropy as primary. (c) Convex hull area ratio.

**Evidence.** Argument from what the metric bounds: registration error at a point grows with distance to the nearest constraining correspondence, since the transform interpolates where constraints exist and extrapolates where they do not. The largest empty disc therefore upper-bounds the region of worst-case local error.

**Trade-offs.** More expensive to compute than occupancy (largest-empty-circle over a point set within a polygon), and less familiar to readers. Both costs are small and one-time.

**Rationale.** Spec §15 explicitly asks which coverage metric is most meaningful *and for the justification*. Occupancy and entropy are averages, and an average cannot bound a worst case — a point set can have excellent entropy and still leave one large hole precisely where the user needs accuracy. Choosing the metric that bounds the failure we care about is a principled answer rather than a menu.

**Status:** `PROPOSED` → EXP-007 checks that it actually correlates with local held-out error better than the alternatives do. If it does not, it is the wrong metric and gets replaced.

---

## ADR-0007 — `geometry/` module and its coordinate contract are built first, with tests

**Decision.** Implement `src/siim/geometry/` — coordinate conventions, transform composition, warping, model fitting — before any matching, representation or IO code. Ship it with property-based round-trip tests.

**Alternatives.** (a) Build the pipeline end-to-end first, fix conventions as bugs surface. (b) Adopt OpenCV conventions implicitly throughout.

**Evidence.** Risk R8, rated high-probability/high-impact. Coordinate-convention errors (x/y vs row/col, pixel-centre vs pixel-corner, forward vs inverse warp, resampling factor bookkeeping) are **silent**: they produce plausible-looking output and corrupt every downstream number without raising an error. Spec §40 flags this as "a critical source of bugs"; spec §60 adds numerical stability.

**Trade-offs.** Delays the first visible demo. Everything after it is trustworthy, which is the trade the whole project is built on.

**Rationale.** The EXP-000/EXP-001 gate — recover a known synthetic homography to <0.1 px before touching real data — is only meaningful if the geometry layer is already known-correct. Option (b) is rejected because implicit conventions are exactly how these bugs are born.

**Status:** `ACCEPTED` (2026-08-24, EXP-000).

**Validation.** 68 tests pass. All five transform models recover from exact correspondences at ~1e-13 px true endpoint error, against a 0.1 px gate — eleven orders of margin. Hartley normalisation holds the DLT condition number flat at ~3.4 across coordinate extents from 512 to 60,000 px, which matters because NAC frames run to ~52,000 lines.

The decision paid for itself immediately on one measurement: the naive resampling coordinate update `p' = s·p` is wrong by `(s−1)/2` px — **1.0 px at 3× resampling** — while contract C4 is exact. Since scale normalisation across the real sensor ladder involves factors up to 320× (ADR-0005), the implicit-convention path (option b) would have burned the entire sub-pixel budget before any matching began, invisibly. See `experiments/EXP-000/README.md`.

---

## ADR-0008 — Licence audit gates every pretrained weight

**Decision.** No pretrained weight file enters the pipeline until its licence is read and recorded in `docs/sources.md`. Prefer Apache-2.0 / MIT engines.

**Alternatives.** (a) Use the best-performing weights and address licensing later. (b) Avoid pretrained weights entirely.

**Evidence.** Risk R7. SuperGlue's released weights are believed to carry a research-/non-commercial-only licence. `[UNVERIFIED — must be checked against the actual licence text, not recollection.]` Candidate permissive alternatives: LightGlue, XFeat, ELoFTR — each also to be verified rather than assumed.

**Trade-offs.** May exclude a strong engine. Option (b) gives up too much performance for no licensing benefit that a permissive engine does not already provide.

**Rationale.** This is a submitted deliverable for a government space agency. A licence problem discovered at evaluation is unrecoverable, whereas choosing a permissive engine early costs nothing. Cheap insurance against an expensive, entirely foreseeable failure.

**Status:** `PROPOSED` → `ACCEPTED` once the audit table exists and is populated.


---

## ADR-0009 — Retain RootSIFT as baseline B1; drop the claim that it beats plain SIFT

**Decision.** Keep RootSIFT as the descriptor for baseline B1, but stop asserting an advantage over plain SIFT. Do not promote either to the final pipeline.

**Alternatives.** (a) Promote RootSIFT on the strength of the literature. (b) Revert to plain SIFT. (c) Drop SIFT-family features from the project entirely.

**Evidence (EXP-001).** Under fixed illumination the baseline is strong — all five transform models recovered at 0.009–0.386 px with ≥ 99.7% true precision, in 0.387 s on CPU. It is a legitimate, non-strawman B1 (spec §49).

But group G measured RootSIFT against plain SIFT directly:

| Δaz | RootSIFT | plain SIFT |
|---|---|---|
| 0° | 2023 inl / 0.359 px | 2024 inl / **0.223 px** |
| 45° | 4 inl / 326 px ✗ | 5 inl / 318 px ✗ |
| 90° | 3 inl / 1000 px ✗ | 4 inl / 410 px ✗ |

**No measurable advantage, and marginally worse at Δaz = 0.**

Group B established the structural ceiling: a cliff between Δazimuth 30° (147 inliers, 0.29 px) and 45° (4 inliers, 325 px). SIFT bins gradient orientation over [0, 2π); shadow motion changes those orientations. No threshold repairs that.

**Trade-offs.** Retaining RootSIFT costs nothing (two lines, no runtime) and keeps us aligned with common practice, which makes the baseline easier to defend. Reverting to plain SIFT would buy nothing and invite the question of why we deviated. The real cost of option (a) would be carrying an unsupported claim into the final report.

**Rationale.** Spec §69 forbids repeating a published claim we have not verified, and §36 forbids keeping components for appearance. Three comparison points at one seed each is weak evidence — which is exactly why the honest position is "no measured difference", not "RootSIFT is worse". We record the negative result and move the decision to where the evidence points: the descriptor is not the problem, the *representation it is computed on* is.

**Status:** `ACCEPTED` (2026-08-24, EXP-001). Revisit only if EXP-002 measures a difference with proper replication.

---

## ADR-0010 — Illumination robustness (EXP-003) is promoted ahead of the classical baseline sweep

**Decision.** Reorder the experimental plan: representation comparison (EXP-003) moves ahead of the remaining classical baselines (AKAZE, ORB, ECC), which were originally EXP-002.

**Alternatives.** (a) Keep the original order and finish the baseline sweep first. (b) Skip straight to a learned matcher.

**Evidence (EXP-001).** The failure axes are not comparable in severity:

| Axis | Where the baseline breaks |
|---|---|
| **Illumination (azimuth)** | **cliff between 30° and 45°** — total failure |
| Scale | no failure through 4×; error crosses 1 px near 3× |
| Elevation | survivable — Δel = −30° still gave 0.750 px |
| Repetitive terrain | robust unless context is removed entirely (RL-012) |

Illumination is the dominant axis by a wide margin, and it is the axis the problem statement names in its title.

**Trade-offs.** Delays a complete baseline table, a spec §20 deliverable. Mitigated because AKAZE and ORB share SIFT's gradient-orientation assumption and are therefore *predicted* to fail on the same axis — measuring that is confirmatory, not exploratory. RIFT2/phase-congruency is the exception and stays in EXP-002 precisely because it is the direct competitor to our representation hypothesis.

**Rationale.** Spec §88 requires choosing the next step from measured weaknesses rather than following a preset plan. The measured weakness is illumination. Option (b) is rejected: EXP-001 has not established what a better *representation* can do with classical machinery, so a learned engine's complexity is not yet justified (spec §36, §75).

**Status:** `ACCEPTED` (2026-08-24, EXP-001).


---

## ADR-0011 — Loop closure is the primary GT-free correctness check; held-out residual and split consistency are demoted to degeneracy detection

**Decision.** Of the four GT-free estimators specified in ANALYSIS §F.1, only **loop closure** is treated as evidence that a registration is *correct*. **Held-out residual** and **spatial split consistency** are retained, but only as **degeneracy detectors**, and must never be described as protection against a wrong-but-consistent answer. **Cycle consistency** is retained with an explicit, tested blind spot.

**Alternatives.** (a) Treat all four as a combined confidence score, as ANALYSIS §F.1 originally implied. (b) Keep only held-out residual, the cheapest. (c) Drop the GT-free stack and rely on inlier count.

**Evidence (EXP-002 objective 4).** Adversarial cases were *constructed* with 300 correspondences each, so that counting inliers cannot help:

| case | true error | held-out residual | flagged | split consistency | flagged |
|---|---|---|---|---|---|
| correct_noisy | 0.00 px | 1.42 px | 0.00 | 0.54 | 0.00 |
| lattice_shift | **64.00 px** | **0.47 px** | **0.00** | 0.17 | 0.00 |
| coherent_affine | **52.71 px** | **0.48 px** | **0.00** | 0.16 | 0.00 |
| partial_overlap | **21.14 px** | **0.47 px** | **0.00** | 0.52 | 0.00 |
| low_inlier_degenerate | 275.65 px | ∞ | 1.00 | ∞ | 1.00 |

Detection rate **0.200** for both — the degenerate case only. A match set 64 px wrong yields a held-out residual of **0.47 px**, *lower* than a genuinely correct but noisy set at 1.42 px.

| estimator | detection | false alarm |
|---|---|---|
| `cycle_error` | 1.000 | **1.000** |
| **`loop_error`** | **1.000** | **0.000** |

A one-period error on each loop edge accumulates to **190.08 px ≈ 3 × 64** instead of cancelling.

A prior artefact was also caught: in objective 3 these estimators appeared to score ROC AUC 0.97–0.99, but they returned `inf` in 104/192 cases (103 of them wrong) and were finite in 88 cases (0 wrong). Their apparent skill was **a proxy for low inlier count**, not independent information.

> **Addendum (2026-08-24).** That artefact reached further than objective 3's signal table. `run_exp002_threshold.py` also selects the signal for its per-subset **sensitivity** analysis by highest validation AUC, so the recorded sensitivity table was computed for `split_consistency` — at the `1e12` sentinel — while the documentation presented it as `n_inliers`. Recomputed for `n_inliers` in `experiments/EXP-002/objective3_ninliers_sensitivity.json` (RL-022). The proxy is now quantified: the sentinel fires in exact agreement with `n_inliers < 8` on **192/192** validation cases, which is why the mislabelled table's confusion matrix looked correct and only its AUC column was wrong. **A metric override must be propagated to every derived table, not only to the one that motivated it.**

**Trade-offs.** Loop closure needs three overlapping images, which the evaluation dataset may not supply — an operational cost the other estimators do not carry. Held-out residual and split consistency are near-free and genuinely do catch degeneracy (the `n ≈ DOF` regime where fit RMSE collapses), so removing them (option b/c) would lose real coverage. Option (a) is rejected outright: averaging a working detector with two blind ones dilutes the signal and manufactures exactly the false confidence this project exists to avoid.

**Rationale.** ANALYSIS §F.1.4 predicted, from first principles, that loop closure would be the estimator able to catch a coherent wrong solution because a consistent per-edge error accumulates around a loop rather than cancelling. That prediction is now measured and correct. The same section's optimism about the other three was wrong, and the register records that rather than quietly rebalancing a combined score.

**Limits, explicit.** Parts A and B are **constructed**, not produced by the image pipeline — they demonstrate the estimators' mathematics, not how often such cases arise on real lunar imagery `[HYPOTHESIS, untested]`. Cycle consistency's 1.000 false-alarm rate comes from a construction that deliberately targets its blind spot (forward and backward exact inverses); on a real pipeline the reverse pass is an independent estimate that would not cancel exactly. The defensible claim is **"cycle consistency cannot detect symmetric errors"**, not "cycle consistency is useless".

**Status:** `ACCEPTED` (2026-08-24, EXP-002) for the mathematics. Real-data frequency remains open.

---

## ADR-0012 — Terrain realism is controlled by an explicit slope target anchored to LOLA statistics

**Decision.** Synthetic terrain is generated to a **target median slope** measured at a stated baseline, with four named regimes. The physically implausible EXP-001 terrain is **retained** as `C_extreme_diagnostic` rather than deleted. Conclusions are drawn from the realistic A-regimes and reported **per regime, never pooled**.

**Alternatives.** (a) Keep the EXP-001 terrain and note the caveat. (b) Replace it outright with one realistic regime. (c) Tune `relief` by eye until the images "look lunar".

**Evidence.** LOLA-derived statistics at a 15 m baseline (sources.md S7): highlands median **9.1°**, mare median **3.5°**; slopes past the **~33° angle of repose** are "almost absent". Measured across 5 seeds:

| regime | median | p99 | > repose | kp/Mpx |
|---|---|---|---|---|
| A_mare_moderate | 3.50° | 9.32° | 0.00% | 312 |
| A_highlands_moderate | 9.10° | 22.64° | 0.00% | 22 119 |
| B_highlands_challenging | 18.00° | 40.05° | 6.36% | 32 582 |
| C_extreme (EXP-001) | 58.53° | 76.76° | **89.55%** | 31 246 |

The A-regimes reproduce the published medians exactly. **The EXP-001 terrain has 89.55% of its surface steeper than the angle of repose** — physically impossible on the Moon.

This was not cosmetic. Re-running the EXP-001 axes across regimes changed two conclusions: the illumination cliff moved **earlier** (15–30° on A-regimes vs 30–45° reported), and "scale survives to 4×" turned out **false on realistic mare**, which fails at 2×.

**Trade-offs.** Slope normalisation is a pure vertical rescale, so it fixes the *median* without fitting the distribution *shape* — full percentiles are reported rather than a single number, and shape-fitting is logged as low-priority debt. Keeping regime C costs a little complexity but preserves EXP-001 reproducibility exactly (`target_slope_median_deg=None` is bit-identical to the old path) and gives a genuine stress test. Option (c) is rejected as unfalsifiable.

**Rationale.** "Realistic terrain" is a claim, and spec §70 requires claims to be checkable against authoritative sources. A target median slope with a stated baseline is checkable; "looks lunar" is not. Separating amplitude (slope) from spectrum (feature density) also makes the two controllable independently — measured at **24× density variation with the median held at 9.10°** — which the old single `relief` parameter could not do.

**Status:** `ACCEPTED` (2026-08-24, EXP-002).
