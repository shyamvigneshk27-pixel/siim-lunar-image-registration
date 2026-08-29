# SIH26166 — Project Analysis (Spec §103 deliverable)

**Status:** Pre-implementation analysis. No pipeline code written yet, by design (§103, §106).
**Date:** 2026-08-24
**Scope:** Multi-modal, Sun-angle and scale-invariant image correspondence — Chandrayaan-2 (OHRC / TMC-2 / IIRS) ↔ lunar reference imagery (LRO NAC).

Every claim below is tagged:
`[FACT]` sourced and verifiable · `[EVIDENCE]` measured in published work, cited · `[HYPOTHESIS]` plausible, untested here · `[UNKNOWN]` explicitly not known.

---

## A. Problem interpretation

### A.1 Formal statement

Given a source image `S` (Chandrayaan-2 optical: OHRC, TMC-2, or IIRS) and a reference image `R` (LRO NAC or another CH-2 product), both observing an overlapping region of the lunar surface `Ω`, find:

1. A correspondence set `C = {(p_i, q_i)}`, `p_i ∈ S`, `q_i ∈ R`, such that `p_i` and `q_i` are projections of the **same physical surface point** `X_i ∈ Ω`.
2. A transform `T : S → R` in a model class chosen from evidence, not assumed.
3. A resampled product in `R`'s frame.
4. Metrics + a **trust decision**.

The correspondence is the composition of two camera projections:
`p_i = proj_S(X_i)`, `q_i = proj_R(X_i)`, hence `q_i = proj_R(proj_S_inverse(p_i))`.

`proj_S_inverse` is **not defined without depth**. This single fact is the source of most of the difficulty: any 2D-to-2D transform `T` is an approximation that is exact only when the surface is planar or the viewing geometry is degenerate (pure rotation, or relief height negligible against orbit altitude). Everything about model selection, residual structure, and local refinement follows from how badly that approximation holds. `[FACT]`

### A.2 What the problem is actually testing

Three gaps must be crossed simultaneously. Most teams will address the first two and ignore the third.

| Gap | Nature | Why it is hard |
|---|---|---|
| **Appearance gap** | Modality + illumination | The same point has different radiance under different Sun geometry and different spectral bands. Intensity is not a stable identity. |
| **Geometric gap** | Scale + viewpoint + relief | Sensor pairs mandate scale ratios up to **320:1** (see C.3). Relief breaks any single global model. |
| **Evidence gap** | No ground-truth correspondences | There is no supplied set of true `(p_i, q_i)` pairs. Therefore "sub-pixel accuracy" cannot be measured by any naive means. |

The **evidence gap is the decisive one** and is addressed in F.1. A solution that matches well but cannot honestly demonstrate that it matches well will lose to one that can.

### A.3 A correction to the problem framing (spec §89 invites this)

The problem statement and spec §17/§18 name **RMSE** as a headline metric. As normally computed — reprojection residual of RANSAC inliers under the fitted model — **RMSE is circular and gameable**:

- It measures how well the model fits the points that were *selected because they fit the model*.
- Tightening the RANSAC threshold monotonically decreases reported RMSE while decreasing inlier count and coverage.
- A pipeline reporting `RMSE = 0.3 px` on 40 clustered inliers is strictly worse than one reporting `RMSE = 0.9 px` on 800 distributed inliers, yet looks better on the headline number.

**Decision:** we report RMSE because the problem statement requires it, but never alone, and always beside a *non-circular* accuracy estimate (F.1). We state this explicitly in the report and to judges. This directly answers spec §28 and judge question §84.24 ("what is your biggest weakness").

---

## B. Technical challenges, ranked by (difficulty × impact)

Highest first. Ranking is my assessment; it is a hypothesis to be confirmed experimentally.

### B1 — Cross-modal appearance gap, worst case IIRS ↔ visible `[FACT + HYPOTHESIS]`

IIRS covers **800–5000 nm in ~256 contiguous bands at 80 m GSD** `[FACT]`. Beyond roughly 3 µm, lunar radiance becomes **thermal-emission dominated** rather than reflectance dominated. A thermal-emission image is essentially a map of *temperature*, which tracks slope and illumination history — not the albedo/shading structure a visible panchromatic NAC image records. `[HYPOTHESIS: appearance-based matching of IIRS >3 µm bands to visible imagery is close to ill-posed.]`

**Design consequence:** IIRS must not be treated as "one image". We select the sub-1.5 µm reflectance-dominated bands (or synthesise a panchromatic from them) as the matching channel, and say so openly. Feeding a full IIRS cube to a generic learned matcher is the mistake that looks sophisticated and fails.

> ## ⚠ B2's DESIGN CONSEQUENCE IS SUPERSEDED — 2026-08-24, by EXP-003 / ADR-0004
>
> **The physics below is unaffected. The prescription is withdrawn.**
>
> B2 concludes that *"the illumination-robust representation **must be polarity-agnostic** —
> gradient orientation modulo π, or phase congruency."* **EXP-003 tested exactly that and
> refuted it**, and **ADR-0004**, which encoded this prescription, is `SUPERSEDED`:
>
> * **mod-π was the worst of the six arms.** Head-to-head against an otherwise-identical 2π
>   descriptor on **identical keypoints**, it **wins 0, loses 38, ties 61**. Last
>   fully-successful Δazimuth **0°** on mare against the raw-intensity baseline's 21°.
> * **Phase congruency did not rescue it.** Contrast- and polarity-invariant *by
>   construction* — verified to 1e-6 and exactly 0.0 — and still bounded at 27–30° on the
>   A-regimes; **void on mare**, where both PC arms failed the Δaz = 0 positive control.
> * **Raw intensity won.** No arm met the pre-registered bar S1.
> * **The mechanism B2 missed:** shadow *movement* changes **which structures exist**, not
>   merely their contrast or polarity — which is why a polarity-agnostic representation
>   cannot repair it. The post-hoc probe found SIFT's assigned **dominant orientation**
>   drifting ~1:1 with Sun azimuth, so the failure is orientation **assignment**, not
>   orientation **binning**. That is held as **D-024**, a *pre-registration target for
>   EXP-004* — **not an accepted decision**, because it is post-hoc, single-stage, synthetic
>   and confounded with the custom descriptor. **EXP-004 is not started.**
>
> **Why this banner exists here and not only in the ADR register.** `README.md` declares:
> *"The design documents are normative. Code that contradicts them is a bug."* A normative
> document that still prescribes a refuted method would make correct code look like a
> defect. Recorded here, at the section, for the same reason E-032 was recorded against the
> claim rather than against the code.
>
> **The section body below is preserved exactly as written**, under the working rule that a
> record is never rewritten to make a result look better. See `architecture_decisions.md`
> ADR-0004, `stages/EXP-003_illumination_robust_representations.md`, and D-024 in
> `stages/DECISION_LEDGER.md`.

### B2 — Illumination variation with shadow reversal `[FACT]`

This is not merely a contrast change. When Sun azimuth differs by ~180°, the illuminated and shadowed walls of every crater **swap**, and the intensity gradient across a rim **reverses sign**.

This breaks a specific, widely-used assumption: SIFT, ORB, AKAZE and most classical descriptors encode **gradient orientation over [0, 2π)**. Under azimuth reversal, corresponding gradients differ by π — so the descriptors do not merely degrade, they become systematically wrong. `[FACT: this follows from the descriptor definition, not from an experiment.]`

Published lunar-specific evidence agrees in direction: SIFT and AKAZE "perform well near the equator but degrade under polar lighting" on Chandrayaan-2 data `[EVIDENCE: arXiv 2509.04775]`.

**Design consequence:** the illumination-robust representation must be **polarity-agnostic** — gradient orientation modulo π, or phase congruency, which is invariant to contrast and to the light/dark polarity of an edge.

### B3 — Extreme, physically-mandated scale gaps `[FACT]`

See C.3. The spec's §14 example ladder (1×, 1.5×, 2×, 4×, 8×) is **below the real requirement** for three of the six sensor pairs. Correcting this is one of our first concrete contributions.

### B4 — The evidence gap: measuring sub-pixel accuracy without ground truth `[FACT]`

Addressed in F.1. High difficulty, maximum impact, and *low compute cost* — the best effort-to-differentiation ratio in the project.

### B5 — Spatial uniformity and match quality are in direct tension `[FACT]`

Lunar terrain has grossly non-uniform information density: mare are smooth and low-texture, highlands are crater-saturated. Any quality-maximising matcher concentrates matches in the highlands. Spec §15 demands uniform distribution across the overlap. These objectives conflict; the tradeoff must be explicit and measured, not buried in a heuristic.

### B6 — Repetitive terrain producing *coherent wrong solutions* `[HYPOTHESIS]`

The dangerous failure mode is not noise. Crater fields are quasi-repetitive; a systematically shifted match set — every crater matched to its neighbour — is **mutually geometrically consistent**, and will pass RANSAC with a high inlier ratio and a low RMSE. Every headline metric looks excellent while the registration is wrong by one crater spacing.

This is the strongest reason why inlier ratio and RMSE cannot be trusted alone (spec §28, §29), and it is precisely what our failure-detection layer must catch.

### B7 — Terrain relief and parallax invalidating global models `[FACT]`

Relief displacement for a feature of height `h` at radial distance `r` from nadir, orbit altitude `H`, is `Δr ≈ h·r / H`. For OHRC at `H = 100 km` with a 3 km swath, `r ≤ 1.5 km`; a 500 m crater rim then gives `Δr ≈ 7.5 m`, which at 0.25 m GSD is **30 pixels**. `[FACT: geometric identity combined with published altitude and swath.]`

**30 px is two orders of magnitude above our sub-pixel target.** Relief is therefore not a second-order effect that a homography quietly absorbs. It is the dominant residual in high-relief scenes, and because it is spatially correlated with topography it appears as *structured* patterns in the residual field — which means we can detect, visualise and report it.

### B8 — Compute: CPU-only development machine `[FACT, measured this session]`

AMD Ryzen 5 7520U, 4 cores / 8 threads, 15.2 GB RAM, `torch 2.10.0+cpu`, `torch.cuda.is_available() == False`, integrated Radeon (no CUDA), 118 GB free disk.

This eliminates from the *local* path: training any dense matcher from scratch, and probably real-time RoMa-class inference. It does **not** eliminate learned matchers as inference-only components — see D and G-R2. It is a real constraint that must shape the architecture rather than be wished away.

### B9 — Data access and format `[UNKNOWN]`

ISSDC PRADAN product listings sit behind an authenticated endpoint (`/ch2/protected/payload.xhtml`); public pages do not state processing levels, file formats, or metadata schema. Per spec §72 this is recorded as unknown and **not** invented. See K.

---

## C. Sensor facts and their direct design consequences

### C.1 Verified instrument parameters `[FACT — sources in docs/sources.md]`

| Sensor | GSD @ 100 km | Swath | Spectral | Notes |
|---|---|---|---|---|
| **OHRC** | 0.25 m | 3 km | visible panchromatic | Highest-resolution lunar imager flown |
| **TMC-2** | 5 m | ~20 km | 0.4–0.85 µm pan | Stereo triplet: fore / nadir / aft |
| **IIRS** | 80 m | 20 km | 0.8–5.0 µm, ~256 bands | Hyperspectral; thermal component at long end |
| **LRO NAC** | 0.5 m (10 µrad IFOV) | 5 km | visible panchromatic | Pair ≈ 10k × 52k px; f/3.59 Cassegrain, EFL 700 mm |

### C.2 Consequence — TMC-2 stereo is an asset, not merely an image source `[HYPOTHESIS]`

TMC-2 acquires fore/nadir/aft triplets specifically for DEM generation `[FACT]`. So for TMC-2 scenes, *topography is derivable from the source data itself*. A DEM-derived representation (slope, curvature, ridge/valley structure) is **illumination-invariant by construction** — it is geometry, not radiance. This is the most physically principled route to Sun-angle invariance available (spec §25), and it requires inventing nothing.

**Caveat that must be tested, not assumed:** DEM generation from TMC-2 stereo is itself a hard, compute-heavy pipeline, and a DEM at 5 m posting cannot constrain a 0.25 m OHRC match to sub-pixel accuracy. Its likely role is **coarse initialisation and independent validation**, not fine matching. Do not oversell it.

### C.3 Consequence — the real scale ladder `[FACT, derived from C.1]`

| Pair | Scale ratio |
|---|---|
| OHRC ↔ NAC | **2 : 1** |
| TMC-2 ↔ NAC | **10 : 1** |
| TMC-2 ↔ IIRS | **16 : 1** |
| OHRC ↔ TMC-2 | **20 : 1** |
| IIRS ↔ NAC | **160 : 1** |
| OHRC ↔ IIRS | **320 : 1** |

Off-the-shelf matchers are reliable to roughly 2–4× scale difference. **Four of six pairs exceed that; two exceed it by two orders of magnitude.** No matcher, learned or classical, solves this by itself.

**Therefore scale normalisation is not a preprocessing convenience — it is a required, first-class pipeline stage**, driven by metadata where available and by search where not. A team that feeds a raw OHRC/IIRS pair to LoFTR and reports failure has diagnosed their own pipeline, not the method.

---

## D. Candidate architectures

Six candidates, scored on the spec §22 axes, 1–5, higher is better. **These scores are prior estimates to be replaced by measurements** — they are the hypothesis, not the result.

| # | Candidate | Acc | Robust | X-modal | Data need | CPU feas. | Explain | Repro | Risk (low=good) | Demo |
|---|---|---|---|---|---|---|---|---|---|---|
| C1 | Classical illumination-robust (phase congruency / RIFT2 / CFOG + MAGSAC++ + ECC) | 3 | 3 | 4 | 5 | **5** | **5** | 5 | 2 | 3 |
| C2 | Learned sparse (XFeat or SuperPoint + LightGlue) | 4 | 4 | 3 | 4 | **4** | 4 | 4 | 2 | 4 |
| C3 | Detector-free semi-dense (ELoFTR / XoFTR) | 4 | 4 | **5** | 4 | 3 | 3 | 4 | 3 | 4 |
| C4 | Dense (RoMa / MINIMA-RoMa) | **5** | **5** | **5** | 4 | **1** | 2 | 3 | 4 | 5 |
| C5 | **Hybrid cascade, pluggable matcher** | 4–5 | **5** | 4–5 | 4 | 4 | **5** | **5** | 2 | **5** |
| C6 | Self-supervised lunar finetune of C3/C4 | ? | ? | ? | 2 | 1 | 3 | 3 | 5 | 4 |

### D.1 Notes on each

**C1 — Classical, illumination-robust.** RIFT2, HOPC and CFOG were designed for exactly this problem class (multimodal remote-sensing registration) around phase congruency, which is contrast- and polarity-invariant. Zero training, zero GPU, fully explainable. RIFT2 appeared in the Chandrayaan-2 comparison study `[EVIDENCE: arXiv 2509.04775]`. Weakness: does not solve large scale gaps on its own.

**C2 — Learned sparse.** XFeat is explicitly designed for CPU-real-time operation and is Apache-2.0. SuperPoint+LightGlue is the strong standard — note the licensing trap in G-R7.

**C3 — Detector-free semi-dense.** XoFTR is purpose-built for cross-modal (thermal↔visible) matching and is the recommended choice "when per-pair latency matters" — **0.4 s/pair vs RoMa's 5.0 s** `[EVIDENCE: arXiv 2604.10217]`. Best accuracy-per-compute for cross-modal work.

**C4 — Dense.** Strongest measured cross-modal accuracy: on SpaceNet9 SAR-optical, **XoFTR and RoMa tie at 3.0 px mean tie-point error; RoMa Success@10 = 94.2%, XoFTR = 90.5%**. MINIMA-RoMa leads on SRIF (47.0 px mean error, zero failures) and SARptical retrieval (0.57 AUROC) `[EVIDENCE: arXiv 2604.10217]`. RoMa's cross-modal robustness is attributed to its **frozen DINOv2 features**. But that 5 s/pair is *on GPU*; on our CPU it is likely one to two orders slower. `[UNKNOWN: actual CPU latency — must be measured in EXP-005, not assumed.]`

**C5 — Hybrid cascade.** See D.3.

**C6 — Self-supervised finetune.** Highest ceiling, highest risk; spec §52 explicitly warns that synthetic training creates false confidence in generalisation. **Deferred.** Not before Phase 5, and only if EXP-003/EXP-005 expose a specific diagnosed deficiency that finetuning is the right answer to.

### D.2 The finding that determines the architecture `[EVIDENCE]`

From a benchmark of 24 pretrained matcher configurations on SAR-optical satellite registration:

> **Protocol choices can change mean error by up to 33× for a single matcher — exceeding the difference between top-tier and mid-tier matchers.**
> Affine vs. homography geometry alone: mean error **12.3 px → 9.7 px**. Recommended baseline: affine geometry, 512×512 tiles with 256 px overlap, per-matcher normalisation, RANSAC threshold 3 px for dense / ≥5 px for sparse. This reaches **<8 px mean error with no domain-specific training**.
> — arXiv 2604.10217

This is the most actionable result found. It says the *wrapper* around the matcher matters more than the matcher. Three consequences:

1. The matcher must be a **swappable component**, not the architecture.
2. Our engineering effort belongs in normalisation, tiling, geometry, verification, coverage, sub-pixel and confidence — all of which are **CPU-cheap**.
3. Our CPU constraint stops being a handicap and becomes an argument: we are optimising the axis the evidence says dominates.

**This must be replicated on lunar data before we lean on it** (EXP-006). It is evidence from SAR-optical satellite imagery; transfer to lunar cross-modal is plausible but unproven. `[HYPOTHESIS until EXP-006.]`

### D.3 Recommendation: C5

```
  S, R  ──▶ [0] IO + metadata ingestion (graceful degradation if absent)
            [1] Band / channel selection       ← IIRS: reflectance bands only
            [2] Radiometric normalisation      ← per-modality, documented
            [3] SCALE NORMALISATION            ← metadata-driven or log-polar search
            [4] Illumination-robust representation  ← polarity-agnostic structure
            [5] Coarse global localisation     ← Fourier-Mellin / pyramid
            [6] Tiled correspondence  ◀───────── PLUGGABLE ENGINE {C1|C2|C3|C4}
            [7] Geometric verification + MODEL SELECTION (cross-validated)
            [8] Coverage-aware selection
            [9] Sub-pixel refinement in *structural* space, with uncertainty
           [10] Robust transform estimation
           [11] Confidence + failure detection  ──▶ TRUST / NO-TRUST
                 └─▶ registered product · match points · metrics · diagnostics
```

**Uncertain assumptions in this design, stated explicitly (spec §103-H requires this):**

- `[UNCERTAIN]` That the 33× protocol finding transfers from SAR-optical to lunar. → EXP-006
- `[UNCERTAIN]` That affine beats homography on lunar pairs. Relief (B7) may instead favour local models. → EXP-009
- `[UNCERTAIN]` That a polarity-agnostic structural representation beats raw intensity by enough to justify its cost. → EXP-003
- `[UNCERTAIN]` That ECC/LK refinement in structural space outperforms refinement in intensity space. → EXP-008
- `[UNCERTAIN]` That any learned engine is fast enough on this CPU to be the default. → EXP-005

### D.4 The core idea (spec §68), stated provisionally

> **The matcher is a replaceable part; the protocol is the contribution.**
> We build a scale-normalised, illumination-polarity-agnostic, coverage-constrained correspondence *protocol* with calibrated confidence and non-circular accuracy evidence — and we show it lifts every matcher plugged into it, classical and learned alike.

This is falsifiable (EXP-006 plus the "baseline + our protocol" ablation in E.2 can refute it), memorable, and does not depend on owning a GPU. **Provisional — to be confirmed or replaced by evidence, exactly as spec §68 instructs.**

---

## E. Baseline strategy

### E.1 Baselines to implement (spec §20)

| ID | Method | Role | Spec |
|---|---|---|---|
| B0 | Identity (no registration) | Absolute floor; calibrates what "an error" means | — |
| B1 | RootSIFT + ratio test + MAGSAC++ | Reference classical baseline | §20-A |
| B2 | AKAZE + MAGSAC++ | Second classical, nonlinear scale space | §20-B |
| B3 | ORB + MAGSAC++ | Efficiency floor | §20-B |
| B4 | XFeat / SuperPoint + LightGlue | Learned sparse | §20-C |
| B5 | ECC + phase correlation | Direct / intensity method | §20-D |
| B6 | ELoFTR / XoFTR | Learned coarse-to-fine | §20-E |
| B7 | RIFT2 / CFOG-style phase congruency | Multimodal classical — the one most teams omit | §12 |

### E.2 The fair-comparison rule (spec §49: do not sabotage the baseline)

Every baseline runs through the **identical harness**: same tiling, normalisation, RANSAC variant and threshold, metrics and seeds. Each baseline is additionally run **twice**:

- **(a) Vanilla** — the method as its authors intended, naive protocol.
- **(b) + our protocol** — same matcher, wrapped in the full cascade.

`(b) − (a)` measures *our* contribution, isolated from the matcher. `best(b) − ours` measures whether our chosen engine matters at all. **This is what makes the D.4 thesis testable rather than rhetorical**, and it makes it structurally impossible to win by weakening a baseline: a stronger baseline makes our protocol look *better*, not worse.

---

## F. Evaluation strategy

### F.1 Closing the evidence gap — four non-circular accuracy estimators

The problem supplies no ground-truth correspondences. We therefore build accuracy evidence from four independent directions. **This is the methodological core of the project.**

**F.1.1 — Synthetic ground truth (spec §59).** Take one real lunar image; apply a *known* transform plus a physically-motivated photometric perturbation (F.2); recover the transform; measure true endpoint error on a dense grid.
- Gives true error, exactly known, everywhere.
- Does **not** test the real modality gap — a warped image is not a different sensor. It **measures algorithm correctness, not data difficulty**, and must be labelled that way (spec §13 forbids conflating the two).

**F.1.2 — Cross-validated residual (the key cheap idea).** Fit `T` on a random 70% of inliers; evaluate residual on the **held-out 30%**; repeat over K folds.
- Converts a *fit residual* into a *generalisation residual*, breaking the circularity of A.3 at near-zero compute cost.
- Works on real cross-modal pairs with no ground truth at all.
- Still cannot detect a globally coherent wrong solution (B6) — the held-out points are wrong in the same consistent way. That needs F.1.4.

**F.1.3 — Cycle consistency.** Match `S→R` and, independently, `R→S`. For a correct correspondence, `T_RS(T_SR(p)) ≈ p`. Matcher asymmetry makes this a genuinely independent check.

**F.1.4 — Loop closure over image triplets.** With three overlapping images `A, B, C`, compose `T_AB ∘ T_BC ∘ T_CA`. For correct registration this is the identity; the deviation is a **ground-truth-free accuracy bound**.
- This is the estimator that catches B6: a one-crater-spacing shift in `A→B` does not cancel around a loop unless all three transforms are wrong in exactly the same way, which is far less likely.
- Requires overlapping triplets. `[UNKNOWN whether the evaluation dataset supplies them — but LRO NAC coverage is dense enough that we can construct them for development.]`

**Reporting rule:** the headline accuracy claim is always the *worst* of the applicable estimators, never the best. Every reported RMSE is labelled `fit` or `held-out`.

### F.2 Illumination axis (spec §13)

Performance is reported **as a function of illumination difference**, not averaged over it. Where metadata gives sub-solar azimuth/elevation, bin real pairs by Δazimuth and Δelevation. Where it does not, use controlled synthetic relighting — clearly labelled synthetic — and never present a synthetic result as evidence of real Sun-angle invariance.

### F.3 Scale axis (spec §14)

Sweep the **real** ladder from C.3 — 2×, 10×, 16×, 20×, 160×, 320×, plus intermediate points — rather than the spec's illustrative 1–8× list.

### F.4 Coverage metrics, and which one is primary (spec §15 asks us to justify)

We compute grid occupancy, spatial entropy, convex-hull ratio, and nearest-neighbour distribution. **We nominate as primary: `max_uncovered_disc_radius`** — the radius of the largest disc inside the overlap region containing no selected correspondence.

**Justification, which is the part that must survive a judge:** registration error at a point grows with distance from the nearest constraining correspondence, because the transform interpolates between constraints where they exist and extrapolates where they do not. The largest empty disc therefore **upper-bounds the region of worst-case local error** — it is a bound on the quantity we actually care about. Entropy and occupancy are averages, and an average cannot bound a worst case: a distribution can show excellent entropy while still leaving one large hole. Those are reported as secondary descriptors.

### F.5 Splits — leakage prevention (spec §19)

- **Geographic block splitting** on selenographic lat/lon with a **guard band** between train/val/test blocks, wide enough that no test tile is adjacent to a train tile.
- **Never** random patch splitting within a scene.
- Held-out axes evaluated separately: unseen **scene**, unseen **sensor pair**, unseen **illumination regime**.
- **The final test set is frozen before final tuning and is not inspected during development.** Violating this is the easiest way to produce numbers that collapse on the judges' hidden data (spec §92).

### F.6 Efficiency (spec §37)

Per-stage wall time, peak RSS, on-disk model size, logged automatically per run — not measured by hand at the end.

---

## G. Risk register

| ID | Risk | P | Impact | Mitigation |
|---|---|---|---|---|
| **R1** | ISSDC data access / format unknown; portal authenticated | High | High | Build on open LRO NAC first; abstract IO behind a format-agnostic reader; resolve access in parallel with Phase 2. Do **not** block on it. |
| **R2** | No GPU → dense learned matchers may be unusable | High | Med | CPU-first engines (XFeat, ELoFTR, RIFT2); measure real CPU latency (EXP-005) before excluding anything; keep a GPU-optional high-accuracy mode on free Colab/Kaggle for training and heavy ablations only — never as a dependency of the deliverable. |
| **R3** | No ground truth → unverifiable accuracy claims | High | High | The four-estimator evidence stack (F.1). |
| **R4** | IIRS thermal bands may be fundamentally unmatchable to visible | Med | Med | Reflectance band selection; report honestly if a pair is out of scope. A well-argued negative result is defensible; a fabricated positive is not. |
| **R5** | Coherent wrong solution passes RANSAC (B6) | Med | **High** | Loop closure (F.1.4) + mutual-NN + degeneracy checks (inlier spatial spread, matrix condition number) + multi-model consensus. |
| **R6** | Overfitting to a few demo pairs (spec §30, §77) | Med | High | Frozen test set; challenge suite A–J; scene-disjoint splits. |
| **R7** | **Pretrained model licensing** | Med | **High** | SuperGlue's released weights carry a research-/non-commercial-only license — a genuine problem for a submitted deliverable. Prefer Apache-2.0 / MIT alternatives (LightGlue, XFeat, ELoFTR). **Audit and record the license of every weight file before it enters the pipeline.** Most teams will miss this; an ISRO judge may not. |
| **R8** | Coordinate-convention bugs (x/y vs row/col, pixel centre, warp direction) | **High** | High | Silent, and they produce plausible-looking wrong output. Mitigation: a written coordinate contract plus property-based round-trip tests, before any matching code exists (spec §40). |
| **R9** | Scope inflation / feature soup (spec §36) | Med | Med | Stop conditions (spec §75): a component ships only if it improves a primary metric by a pre-declared margin at acceptable cost. |

---

## H. Recommended architecture

**C5 (D.3)**, with the matcher slot filled by whichever engine EXP-005/EXP-006 selects on measured evidence — explicitly **not** chosen now. All five uncertain assumptions are listed in D.3 alongside the experiment that resolves each.

---

## I. Experimental plan

Ordered. Each resolves a stated decision; none is exploratory for its own sake.

| ID | Experiment | Resolves |
|---|---|---|
| EXP-000 | Environment + coordinate contract + synthetic geometry harness + property tests | R8; makes every later number trustworthy |
| EXP-001 | RootSIFT baseline against synthetic GT | Validates the harness before any data difficulty enters |
| EXP-002 | Classical baseline sweep (B1–B3, B5, B7) | Where classical methods actually break |
| EXP-003 | Representation comparison: raw / CLAHE / gradient-mag / grad-orientation-mod-π / phase congruency / CFOG, under controlled relighting | D.3 assumption 3 |
| EXP-004 | Scale-gap sweep on the real ladder (C.3) | Whether scale normalisation suffices at 20× and 320× |
| EXP-005 | Learned engines on **this CPU**: latency, memory, accuracy | R2; which engines are admissible at all |
| EXP-006 | **Protocol ablation** — tile size, overlap, affine vs homography, threshold, normalisation | The 33× question, on lunar data. Confirms or refutes D.4 |
| EXP-007 | Coverage selection strategies | F.4; the quality-vs-uniformity tradeoff curve |
| EXP-008 | Sub-pixel refinement comparison + **uncertainty calibration** | D.3 assumption 4; whether reported uncertainty is honest |
| EXP-009 | Transformation model selection (similarity / affine / homography / local) by cross-validated residual | D.3 assumption 2; the B7 relief question |
| EXP-010 | Confidence + failure-detection calibration | Whether the system knows when it is wrong (spec §26) |
| EXP-011 | Challenge suite A–J scorecard | spec §50 |
| EXP-012 | Final system + full ablation | spec §35 |

**Gate:** EXP-000 and EXP-001 must pass before any real-data experiment. A pipeline that cannot recover a known synthetic homography to <0.1 px has a bug, and every subsequent number would be measuring that bug rather than the science.

---

## J. Repository architecture

Trimmed from spec §31 — folders are created **when a stage exists**, not upfront (spec §31: "do not create unnecessary folders just for appearance").

```
SIH/
├── configs/            # every experiment reproducible from a config file (§32)
├── src/siim/
│   ├── io/             # readers, metadata parsing, graceful degradation
│   ├── geometry/       # coordinate contract, transforms, model selection  ← FIRST
│   ├── preprocessing/  # band selection, radiometric + scale normalisation
│   ├── representation/ # illumination-robust representations
│   ├── matching/       # pluggable engine interface + adapters
│   ├── verification/   # RANSAC/MAGSAC, degeneracy, cycle & loop closure
│   ├── coverage/       # coverage-aware selection
│   ├── refinement/     # sub-pixel + uncertainty
│   ├── confidence/     # trust decision
│   ├── evaluation/     # the four estimators, metrics, challenge suite
│   ├── visualization/
│   └── api.py          # register_lunar_images(...)   (spec §79)
├── tests/              # incl. property-based coordinate round-trip tests
├── experiments/        # EXP-XXX, one dir each: config + metrics + logs + figures
├── results/benchmark.csv
├── docs/               # this file, research_log, architecture_decisions, sources
└── outputs/
```

`src/siim/geometry/` is written **first**, with tests, because everything downstream depends on its correctness (R8).

---

## K. Data requirements

### K.1 Required

- **Reference:** LRO NAC EDR/CDR for target regions (openly available).
- **Source:** Chandrayaan-2 OHRC, TMC-2, IIRS products via ISSDC PRADAN.
- **Metadata per image, ideally:** sub-solar azimuth and elevation, incidence/emission/phase angles, spacecraft altitude and position, pixel scale, map projection and datum, acquisition timestamp, sensor ID, processing level.
- **Development need:** overlapping **triplets** for loop closure (F.1.4).

### K.2 Explicitly unknown — not to be invented (spec §72)

`[UNKNOWN]` SIH-supplied dataset size, composition, sensor mix, processing levels, file formats, projection, whether any ground-truth correspondences or tie points are provided, whether metadata accompanies images, Sun-angle distribution, overlap fractions.

### K.3 Design consequence

The IO layer must (a) work with **no metadata at all**, degrading gracefully to search-based scale/rotation estimation, and (b) exploit metadata fully when present. This is a spec requirement (§24) and simultaneously the correct hedge against K.2.

---

## L. Success criteria

**Targets, not predictions. To be revised once the dataset is characterised (spec §73).**

| Axis | Target | Measured by |
|---|---|---|
| Algorithmic correctness | Median endpoint error **< 0.3 px**, p90 < 0.7 px on synthetic GT at 1× | F.1.1 |
| Real cross-modal accuracy | Median **held-out** residual **< 1.0 px** (OHRC↔NAC) | F.1.2 |
| Coherence | Loop-closure error **< 2 px** on triplets | F.1.4 |
| Coverage | `max_uncovered_disc_radius` **≤ 15%** of overlap diagonal; grid occupancy ≥ 0.7 | F.4 |
| Robustness | Success rate **≥ 90%** on Challenges A, B, D, F; honest reporting on G, H, I, J | spec §50 |
| **Failure detection** | Failure recall **≥ 95%** at false-alarm **≤ 20%** | EXP-010 |
| Efficiency | **≤ 60 s/pair** on 4096² tiled input, this CPU, no GPU | F.6 |
| Contribution | `(baseline + our protocol) − (baseline vanilla)` improvement significant across **≥ 4 of 7** baselines | E.2 |

The failure-detection row matters more than it looks. A system that is right 90% of the time **and knows which 10%** is operationally more valuable to ISRO than one that is right 95% of the time and cannot tell you when it is not (spec §26, §94).

---

## Open questions for the project owner

1. **Data:** is the SIH dataset available yet, or do we develop against public LRO NAC plus ISSDC downloads? Determines whether Phase 1 starts now or is deferred.
2. **Compute:** is any GPU reachable (Colab / Kaggle free tier, institutional cluster)? Decides whether C4-class engines are ever admissible, and whether C6 is on the table at all.
3. **Timeline:** the phase plan is sequential; the deadline determines how many of Phases 5–9 are reachable.
4. **Deliverable licensing:** must the submission be free of non-commercial-only weights? (R7 — this affects engine selection now, not later.)
