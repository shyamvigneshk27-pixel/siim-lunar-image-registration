# SIH 2026 — SIH26166

# MASTER PROJECT PROMPT FOR CLAUDE CODE

# Chandrayaan-2 Multi-Modal, Sun-Angle and Scale-Invariant Image Correspondence

# Goal: Build an exceptionally strong, technically defensible, evaluation-grade solution

You are now the lead technical architect, research scientist, computer vision engineer, machine-learning engineer, remote-sensing specialist, software architect, experiment designer, and critical reviewer for a serious SIH 2026 project.

The problem is:

**SIH Problem Statement ID: 26166**

**Title:**
Multi-modal, Sun angle and scale invariant image correspondence using Chandrayaan-2 optical images (OHRC, TMC and IIRS)

**Organization:**
Indian Space Research Organisation (ISRO)

**Department:**
Department of Space / Indian Space Research Organisation

**Category:**
Software

**Theme:**
Space Technology

---

# 1. FULL PROBLEM STATEMENT

Image Registration is the process of aligning two or more images of the same scene taken at different times, from different viewpoints, or by different sensors into a common coordinate system.

It has two main components:

1. Source Image (Moving):
   The image that is to be geometrically transformed to align with the reference image.

2. Reference Image (Fixed):
   The target image about which the source image is to be geometrically transformed.

The process of lunar image registration involves finding match points between source and reference image and then aligning the source image with the reference image.

The key challenges are:

### Illumination variation

Illumination variation refers to changes in sun azimuth and elevation that affect the surface lighting conditions and therefore the visual appearance of lunar surface features. The same terrain can appear very different under different lighting conditions.

### Viewpoint variation

Viewpoint variation refers to geometric distortions caused by different camera positions/orientations capturing the same scene. Features may appear shifted, scaled, rotated, or perspective-distorted depending on the observing geometry.

### Scale variation

Lunar imaging missions operate at vastly different altitudes and at different spatial resolutions. This creates significant scale differences between images.

### Expected Solution

Develop a generic software solution for finding correspondence between Chandrayaan-2 acquired optical images and lunar reference images with sub-pixel accuracy of the source image while maintaining a uniform distribution of matching points across the images.

The expected solution includes:

* Software
* Registered product
* Corresponding match points
* Evaluation metrics such as:

  * RMSE
  * Inlier match count
  * Inlier ratio
  * other appropriate metrics

### Dataset sources mentioned in the problem statement

Chandrayaan-2 optical payloads:

* OHRC
* TMC-2
* IIRS

Reference imagery:

* LRO NAC Images
* Lunar Reconnaissance Orbiter Narrow Angle Camera

Dataset/reference resources mentioned:

* Chandrayaan-2 / ISSDC:
  https://chmapbrowse.issdc.gov.in/
* LRO-related reference:
  https://lroc.im-ldi.com/images/downloads/
* LRO QuickMap:
  https://quickmap.lroc.im-ldi.com/

The exact SIH dataset may be provided separately/TBD, so the software must be designed so that the actual evaluation dataset can be integrated cleanly.

---

# 2. PROJECT OBJECTIVE

The goal is NOT to build a basic image registration demo.

The goal is to build a robust, scientifically defensible, computationally efficient, reproducible, and visually demonstrable **lunar cross-modal correspondence and registration system** capable of handling:

* large illumination differences
* different Sun azimuths
* different Sun elevations
* strong shadow changes
* different sensor characteristics
* different spatial resolutions
* large scale differences
* viewpoint changes
* rotation
* translation
* perspective effects where applicable
* local geometric distortions where necessary
* low-texture terrain
* repetitive terrain structures
* image noise
* varying contrast
* cross-modal appearance differences
* potentially difficult overlap conditions
* unseen lunar scenes
* unseen illumination conditions
* unseen sensor pair combinations

The system should produce:

1. Reliable correspondence points.
2. Spatially well-distributed correspondence points.
3. Outlier-rejected inlier correspondences.
4. Sub-pixel refined correspondence wherever realistically achievable.
5. A geometrically registered source image.
6. Quantitative metrics.
7. Confidence/quality measures.
8. Diagnostic visualizations.
9. An experimental framework showing exactly why the chosen method is superior to simpler alternatives.

---

# 3. VERY IMPORTANT PROJECT MINDSET

Treat this as a serious research-and-engineering problem, not a tutorial.

The final system must be strong enough to withstand questioning from:

* ISRO scientists
* computer-vision experts
* remote-sensing experts
* ML researchers
* IIT/NIT engineering teams
* judges trying to find flaws
* reviewers asking "why did you choose this?"
* reviewers asking "why should this work on unseen lunar scenes?"
* reviewers asking "what happens when your assumptions fail?"
* reviewers asking for numerical evidence

Do NOT optimize only for visual appearance.

Do NOT optimize only for benchmark performance on a small curated test set.

Do NOT make the model unnecessarily complicated just because it looks advanced.

Do NOT use AI as decoration.

Do NOT assume a transformer is automatically better than classical vision.

Do NOT assume more matches means better registration.

Do NOT assume a low average error proves robustness.

Do NOT claim "sub-pixel accuracy" without an appropriate evaluation methodology.

Do NOT claim generalization unless it has actually been tested.

Do NOT silently use assumptions that cannot be justified.

Always distinguish:

* experimentally demonstrated
* theoretically plausible
* expected
* unknown
* unverified

If something is uncertain, explicitly say so.

---

# 4. COMPETITIVE STANDARD

Assume that approximately 500 teams may attempt this problem, including highly capable teams from:

* IITs
* NITs
* IIITs
* major engineering universities
* research-focused institutions
* teams with strong ML backgrounds
* teams with computer vision specialists

We therefore do NOT want a generic solution.

The target is not:

"build something that works."

The target is:

"build the strongest technically defensible solution we can realistically execute, demonstrate, benchmark, explain, and deploy."

We should aim to develop an approach that many teams would not consider.

But "novel" does NOT mean unnecessarily complicated.

The winning philosophy should be:

**smarter + simpler + more logical + more robust + more measurable + more efficient**

rather than:

**more layers + more parameters + more buzzwords**

---

# 5. FIRST PRINCIPLES ANALYSIS BEFORE CODING

Before writing substantial implementation code, analyze the problem from first principles.

Explain:

1. What does "image correspondence" mathematically mean?
2. What does image registration mathematically mean?
3. What transformations may occur between lunar images?
4. Under what conditions is a homography valid?
5. When is affine transformation sufficient?
6. When is a projective transformation required?
7. When does a global transformation become insufficient?
8. When should local/non-rigid correction be considered?
9. What physically causes illumination changes?
10. What physically causes viewpoint changes?
11. What physically causes scale differences?
12. What makes lunar imagery different from ordinary Earth imagery?
13. Why is cross-sensor matching fundamentally difficult?
14. Why can raw intensity matching fail?
15. Why can ordinary feature descriptors fail?
16. Why can deep features fail?
17. What assumptions are safe?
18. What assumptions are dangerous?
19. What can be learned from lunar terrain geometry?
20. What information is preserved under lighting changes?
21. What information disappears under severe illumination changes?
22. What information is sensor-dependent?
23. What information is more invariant across sensors?

Do not rush through this section.

Build the reasoning foundation before architecture decisions.

---

# 6. EXPLAIN "IMAGE CORRESPONDENCE" PRECISELY

The system must identify physical points or local structures that correspond to the same lunar surface locations in two different images.

For example:

Image A:

(x1, y1)

corresponds to:

Image B:

(x2, y2)

The system should produce many such pairs:

(x1, y1) -> (x2, y2)
(x3, y3) -> (x4, y4)
...

Explain:

* local correspondence
* sparse correspondence
* dense correspondence
* descriptor matching
* learned correspondence
* geometric correspondence
* physically meaningful correspondence

Explain when each is useful.

Do not confuse visual similarity with true geometric correspondence.

---

# 7. EXPLAIN "IMAGE REGISTRATION" PRECISELY

Registration means estimating the geometric relationship between the source and reference images and transforming the source into the reference coordinate system.

Analyze:

* translation
* rotation
* scale
* similarity transform
* affine transform
* projective/homography transform
* polynomial models
* spline-based models
* local deformation models
* terrain-aware transformations if appropriate

Determine which models are physically and geometrically appropriate for lunar imagery under realistic acquisition conditions.

Do NOT simply default to homography.

Determine the correct transformation model based on:

* imaging geometry
* terrain relief
* viewing angle
* image scale
* sensor characteristics
* available metadata
* observed residuals

---

# 8. WHY THIS IS HARD ON THE MOON

Analyze lunar-specific difficulties deeply.

At minimum investigate:

* absence of atmosphere
* harsh illumination
* long shadows
* changing solar geometry
* extreme contrast
* crater-rich morphology
* repetitive terrain patterns
* low-texture areas
* shadowed areas
* specular/photometric effects where relevant
* sensor-dependent appearance
* resolution changes
* off-nadir viewing
* geometric distortions
* terrain relief/parallax
* different acquisition times
* potentially different processing levels
* image artifacts
* compression
* noise
* radiometric differences

Do not copy generic Earth computer-vision assumptions into lunar remote sensing without testing them.

---

# 9. CHALLENGE #1 — ILLUMINATION VARIATION

This is one of the central difficulties.

The same lunar feature may appear drastically different under:

* different Sun azimuth
* different Sun elevation
* different phase geometry
* different shadow direction
* different shadow length
* different brightness distribution

Analyze:

* why intensity-invariant matching matters
* why ordinary correlation can fail
* why gradient-based methods may help
* why edge-based methods may help
* why local surface morphology may be more invariant
* whether phase congruency could help
* whether gradient orientation can help
* whether local shape can help
* whether learned features can help
* whether pseudo-relighting or illumination normalization can help
* whether DEM/shading information could theoretically help
* whether shadow-aware masking is useful
* how to avoid destroying valid geometric information during normalization

Investigate multiple strategies experimentally.

---

# 10. CHALLENGE #2 — VIEWPOINT VARIATION

Study:

* camera position change
* camera orientation change
* off-nadir imaging
* local perspective changes
* terrain slope
* crater walls
* parallax
* relief displacement

Determine:

* which distortions are globally explainable
* which are locally varying
* when homography becomes insufficient
* when a piecewise model may help
* when local refinement is appropriate
* whether physical orbital/camera metadata can improve registration

Do not invent a complex deformation model unless experiments demonstrate that it is necessary.

---

# 11. CHALLENGE #3 — SCALE VARIATION

Investigate large scale differences resulting from:

* altitude
* sensor resolution
* image product resolution
* acquisition geometry

Evaluate:

* image pyramids
* feature pyramids
* multi-scale descriptors
* coarse-to-fine matching
* learned scale-space features
* keypoint scale normalization
* adaptive tiling

Do not assume the scale difference will always be small.

---

# 12. HIDDEN MAJOR CHALLENGE — MULTI-MODAL MATCHING

The title explicitly says "multi-modal."

Investigate the differences among:

* OHRC
* TMC-2
* IIRS
* LRO NAC

Study, as far as available from authoritative sources:

* spatial resolution
* spectral characteristics
* imaging geometry
* detector characteristics
* radiometric behavior
* acquisition mechanisms
* noise characteristics
* typical image products
* image size
* data formats
* metadata
* expected dynamic range

The architecture should not assume:

"same sensor + same image statistics."

Instead assume that cross-modal matching may require representations that preserve structural/geometric information while suppressing modality-specific appearance.

Investigate:

* modality-invariant representations
* cross-modal descriptors
* gradient/edge representations
* phase-based representations
* self-supervised representations
* contrastive learning
* cross-modal metric learning
* local feature normalization
* learned correspondence
* geometry-aware matching

Compare them experimentally.

---

# 13. "SUN ANGLE INVARIANT" MUST BE TREATED AS A REAL ENGINEERING REQUIREMENT

The system should maintain correspondence quality despite major illumination changes.

Design experiments that intentionally vary:

* Sun elevation
* Sun azimuth
* shadow orientation
* illumination direction

If real data metadata supports this, use it.

If not, derive controlled subsets carefully and clearly label synthetic augmentation versus real variation.

Do not claim Sun-angle invariance merely because two arbitrary images happen to match.

Create a specific evaluation axis:

**Correspondence performance vs illumination change.**

Report:

* inlier ratio
* inlier count
* RMSE
* reprojection error
* registration quality
* failure rate

versus illumination difference.

---

# 14. "SCALE INVARIANT" MUST BE TREATED AS A REAL ENGINEERING REQUIREMENT

Create controlled experiments across multiple scale ratios.

Example conceptual levels:

* 1x
* 1.5x
* 2x
* 4x
* 8x
* larger if realistic

Do NOT hardcode those values if the actual dataset suggests more appropriate ranges.

Measure performance degradation as scale difference increases.

---

# 15. CORRESPONDENCE POINTS MUST BE SPATIALLY WELL DISTRIBUTED

This is an explicit requirement.

Do not allow the system to find hundreds of matches concentrated in a single crater or texture-rich region.

The system should enforce or optimize:

**coverage across the common overlap region**

Potential approaches to investigate:

* grid-based selection
* adaptive spatial binning
* farthest-point sampling
* coverage-aware non-maximum suppression
* entropy-based spatial selection
* uncertainty-aware selection
* quality-weighted spatial sampling
* region quotas
* adaptive correspondence selection

The final solution should have metrics for spatial coverage.

Do not only report the number of matches.

Measure:

* convex hull coverage
* occupancy ratio
* grid occupancy
* spatial entropy
* nearest-neighbor distribution
* max uncovered region
* region-wise match density
* uniformity score

Determine which metric is most meaningful and justify it.

---

# 16. SUB-PIXEL ACCURACY

This is a major requirement.

Do not casually claim sub-pixel performance.

Investigate techniques such as:

* local correlation refinement
* inverse compositional alignment
* Lucas-Kanade-style refinement where appropriate
* differentiable correlation
* local cost-volume refinement
* quadratic/parabolic peak interpolation
* Gaussian peak fitting
* local template optimization
* learned fine matching
* geometric optimization
* bundle-like refinement where applicable

Determine the best method experimentally.

The system should distinguish:

**coarse correspondence**

from:

**fine/sub-pixel correspondence refinement**

A potential architecture:

coarse matching
→ geometric filtering
→ fine matching
→ sub-pixel refinement

Do not assume every coarse match can be refined successfully.

Attach confidence and reject unstable points.

---

# 17. EXPECTED OUTPUTS

The application must produce:

## A. Match points

For each correspondence, store at minimum:

* source_x
* source_y
* reference_x
* reference_y
* confidence
* scale if available
* orientation if available
* matching score
* inlier/outlier status
* refinement status
* uncertainty estimate if available

Use a clear machine-readable format such as JSON/CSV/Parquet as appropriate.

## B. Registered product

Produce the geometrically transformed source image aligned with the reference image.

Support:

* side-by-side visualization
* overlay
* alpha blending
* checkerboard comparison
* difference image
* edge overlay

## C. Quantitative evaluation

Report:

* RMSE
* median error
* max error where meaningful
* inlier count
* inlier ratio
* reprojection error
* registration success rate
* coverage metrics
* computational cost
* runtime
* memory usage
* failure cases

## D. Diagnostic report

Generate visual diagnostics for every experiment.

---

# 18. EVALUATION METRICS

Do not use only one metric.

At minimum evaluate:

### Accuracy

* RMSE
* median correspondence error
* percentile errors
* reprojection error

### Robustness

* inlier ratio
* outlier rate
* success/failure rate
* performance under illumination change
* performance under scale change
* performance under viewpoint change
* cross-sensor performance

### Coverage

* spatial uniformity
* overlap coverage
* grid occupancy
* spatial entropy

### Efficiency

* runtime
* inference time
* GPU memory
* CPU memory
* model size
* preprocessing time
* postprocessing time

### Generalization

Evaluate separately across:

* scene
* sensor
* illumination
* scale
* viewpoint
* acquisition conditions

Do NOT randomly split adjacent patches from the same scene into train and test if that creates leakage.

Scene-level or geographically separated evaluation is strongly preferred when appropriate.

---

# 19. DATA LEAKAGE IS FORBIDDEN

Treat this as a critical rule.

Never create a misleading benchmark by allowing nearly identical neighboring patches from the same lunar scene to appear in both training and testing without explicitly accounting for it.

Investigate:

* scene-level split
* region-level split
* acquisition-level split
* sensor-level split
* illumination-level split

Document exactly how datasets are partitioned.

If the SIH dataset is hidden, create a robust development protocol without contaminating the final evaluation.

---

# 20. BASELINES ARE MANDATORY

Before claiming the proposed solution is strong, implement strong baselines.

At minimum investigate:

### Baseline A

SIFT + descriptor matching + ratio test + RANSAC

### Baseline B

AKAZE or another strong classical local-feature method

### Baseline C

A robust learned local-feature / matcher combination

### Baseline D

A direct/intensity-based method where meaningful

### Baseline E

A strong coarse-to-fine learned matcher if feasible

Do not choose weak baselines just to make our method look better.

The purpose is to determine:

**What actually works on lunar cross-modal data?**

Benchmark honestly.

---

# 21. RESEARCH EXISTING TECHNOLOGIES BEFORE FINAL ARCHITECTURE

Before finalizing the method, investigate relevant state-of-the-art approaches from:

* computer vision
* remote sensing
* lunar image registration
* cross-modal image matching
* satellite image registration
* planetary remote sensing
* feature matching
* dense correspondence
* geometric verification
* image alignment
* illumination-invariant matching
* multi-scale matching

Investigate relevant methods such as, where appropriate:

* SIFT
* RootSIFT
* AKAZE
* ORB
* SuperPoint
* DISK
* R2D2
* D2-Net
* LoFTR
* LightGlue
* SuperGlue
* related modern local feature/matching systems
* phase-based approaches
* gradient-based approaches
* learned dense correspondence
* optical-flow-like methods
* multi-scale correlation methods

Also investigate approaches specifically useful for:

* remote sensing registration
* cross-modal registration
* SAR-optical matching if conceptually relevant
* infrared-optical matching if conceptually relevant
* planetary image registration

Do not blindly copy a paper.

For every candidate method, ask:

1. Does its assumption apply to lunar imagery?
2. Does it handle cross-modal differences?
3. Does it handle large scale differences?
4. Does it handle illumination changes?
5. Does it require extensive training data?
6. Can it operate with our compute constraints?
7. Does it provide useful uncertainty/confidence?
8. Can it produce sub-pixel refinement?
9. Is it robust to unseen scenes?
10. Can we explain it to ISRO judges?

---

# 22. DO NOT FINALIZE THE ALGORITHM TOO EARLY

Generate multiple candidate architectures.

For example:

### Candidate 1

Classical robust pipeline

### Candidate 2

Learned local feature + learned matcher

### Candidate 3

Coarse-to-fine dense matcher

### Candidate 4

Hybrid classical + learned

### Candidate 5

Geometry-aware multi-modal pipeline

### Candidate 6

Hybrid feature + morphology + geometry approach

For each candidate, score:

* expected accuracy
* robustness
* cross-modal performance
* data requirement
* compute requirement
* engineering complexity
* explainability
* reproducibility
* training difficulty
* inference speed
* risk
* SIH demo quality
* real-world feasibility

Then select the best approach based on evidence.

---

# 23. STRONGLY CONSIDER A HYBRID APPROACH

Do not assume the final answer must be 100% deep learning.

Investigate whether the strongest architecture is something like:

Input images
→ metadata-aware preprocessing
→ illumination normalization
→ multi-scale representation
→ robust feature extraction
→ coarse correspondence
→ geometric verification
→ cross-modal matching
→ confidence estimation
→ spatial redistribution
→ fine local matching
→ sub-pixel refinement
→ robust transformation estimation
→ registration
→ uncertainty/quality report

The best architecture may combine:

* physics/domain knowledge
* classical computer vision
* learned features
* geometric methods
* optimization
* statistical validation

A hybrid solution may be more robust and defensible than a pure black-box model.

But this must be proven experimentally.

---

# 24. INVESTIGATE WHETHER METADATA CAN BE USED

Treat image metadata as potentially valuable information.

Investigate available metadata such as:

* spacecraft position
* camera geometry
* viewing angle
* Sun azimuth
* Sun elevation
* acquisition timestamp
* spatial resolution
* sensor identity
* projection information
* orientation

Determine whether metadata can improve:

* candidate search
* scale estimation
* image overlap estimation
* transformation initialization
* illumination normalization
* geometric model selection
* quality assessment

DO NOT fabricate metadata.

If metadata is unavailable, design the system to work without it.

A strong system should degrade gracefully.

---

# 25. INVESTIGATE PHYSICS-AWARE IDEAS

This project is about lunar imagery, so investigate whether lunar surface geometry can be exploited.

Consider, only where justified:

* crater morphology
* ridges
* rims
* valleys
* geological boundaries
* topographic edges
* terrain orientation
* DEM-derived descriptors
* shape descriptors
* gradient fields
* shadow boundaries
* relief-aware registration

Investigate whether a physics/geometry-aware representation can be more illumination-invariant than raw image intensity.

Do not include physics simply to sound sophisticated.

Include it only when measurable evidence supports it.

---

# 26. FAILURE-AWARE ARCHITECTURE

A strong system must know when it is failing.

Design:

**Correspondence confidence**

**Registration confidence**

**Coverage confidence**

**Geometric consistency score**

**Uncertainty estimate**

The system should be able to say:

"Registration confidence is too low; do not trust this result."

This is preferable to generating a visually plausible but incorrect registration.

Potential failure detection signals:

* low inlier ratio
* poor spatial coverage
* high residual error
* inconsistent local transformations
* descriptor ambiguity
* low confidence
* unstable refinement
* degenerate geometry
* excessive extrapolation outside overlap

---

# 27. NEVER ACCEPT "MANY MATCHES = GOOD"

This is a major mistake.

A system with:

10,000 incorrect matches

is worse than:

200 high-quality distributed correspondences.

Optimize for:

**accuracy + robustness + distribution + geometric consistency**

not raw match count.

---

# 28. NEVER ACCEPT "LOW RMSE = PERFECT"

RMSE alone can be misleading.

A small subset of good points can give a deceptively good estimate.

Always analyze:

* RMSE
* median error
* error distribution
* inlier ratio
* spatial coverage
* region-wise accuracy

Visualize residual vectors.

---

# 29. NEVER ACCEPT "HIGH INLIER RATIO = PERFECT"

A system can obtain a high inlier ratio from a small, highly concentrated region.

Therefore:

**inlier ratio + coverage + count + geometric consistency**

must be considered together.

---

# 30. NEVER OVERFIT TO ONE CRATER OR ONE SCENE

The final method must not secretly be:

"excellent on one example."

Test:

* different craters
* different geological environments
* bright/high-albedo terrain
* dark terrain
* smooth terrain
* highly textured terrain
* shadow-heavy scenes
* different illumination conditions
* different sensor combinations
* different scales

---

# 31. ARCHITECTURE REQUIREMENT

Design the software as a modular research and production system.

Recommended conceptual structure:

```text
siim/
├── data/
│   ├── raw/
│   ├── processed/
│   ├── metadata/
│   ├── splits/
│   └── cache/
│
├── src/
│   ├── io/
│   ├── preprocessing/
│   ├── normalization/
│   ├── features/
│   ├── matching/
│   ├── geometry/
│   ├── refinement/
│   ├── registration/
│   ├── confidence/
│   ├── evaluation/
│   ├── visualization/
│   ├── training/
│   └── inference/
│
├── models/
│
├── configs/
│
├── experiments/
│
├── notebooks/
│
├── tests/
│
├── scripts/
│
├── outputs/
│
├── reports/
│
└── docs/
```

Adapt this architecture as evidence demands.

Do not create unnecessary folders just for appearance.

---

# 32. CONFIGURATION MUST BE CLEAN

Do not hardcode critical parameters into Python files.

Use configuration files for:

* model
* detector
* matcher
* thresholds
* image pyramid
* RANSAC
* refinement
* spatial coverage
* dataset paths
* evaluation settings
* hardware mode
* training parameters

Every experiment should be reproducible from configuration.

---

# 33. REPRODUCIBILITY

Every experiment must store:

* configuration
* code version
* dataset version
* random seed where applicable
* model checkpoint
* metrics
* logs
* output visualizations

Do not produce results that cannot be reproduced.

---

# 34. EXPERIMENT TRACKING

Create a consistent experiment system.

Example:

```text
EXP-001 baseline-SIFT
EXP-002 AKAZE
EXP-003 learned-local-feature
EXP-004 cross-modal-normalization
EXP-005 hybrid-matcher
EXP-006 spatial-selection
EXP-007 subpixel-refinement
EXP-008 final-system
```

For each experiment store:

* objective
* configuration
* dataset
* metrics
* observations
* failure cases
* conclusion

---

# 35. ABLATION STUDIES ARE REQUIRED

The final system should include ablations such as:

* without illumination normalization
* with illumination normalization
* classical vs learned features
* without spatial balancing
* without geometric verification
* without fine refinement
* without sub-pixel refinement
* with and without metadata
* different transformation models

The purpose is to prove which components actually contribute.

---

# 36. AVOID "FEATURE SOUP"

Do not combine 15 techniques because they sound impressive.

Every component must have a reason.

For every module ask:

* What problem does this solve?
* Why is it needed?
* What evidence supports it?
* What is its computational cost?
* What happens if it is removed?

If a component does not help, remove it.

---

# 37. COMPUTATIONAL EFFICIENCY MATTERS

Although this is software, optimize seriously.

Track:

* preprocessing latency
* feature extraction latency
* matching latency
* geometric estimation latency
* refinement latency
* total runtime
* memory
* GPU memory
* model size

Consider:

* CPU fallback
* GPU acceleration
* batching
* caching
* image pyramids
* tiling
* approximate nearest-neighbor search
* half precision where numerically safe
* model quantization if appropriate

Do not sacrifice the core accuracy for meaningless micro-optimizations.

---

# 38. SCALABILITY

The architecture should support:

* small images
* large images
* tiled processing
* batch processing
* multiple image pairs
* multiple sensors
* future lunar missions
* future planetary datasets

Avoid hardcoding everything specifically for one example image.

---

# 39. DATA PIPELINE

Build a robust data ingestion system.

It should support:

* reading image formats
* metadata parsing
* normalization
* calibration/processing where required
* resizing
* tiling
* overlap handling
* coordinate mapping
* ground-truth correspondence if available
* train/validation/test split
* caching

Never silently change image geometry during preprocessing.

Whenever resizing or warping occurs, correctly update coordinates.

---

# 40. COORDINATE SYSTEM SAFETY

This is a critical source of bugs.

Maintain clear definitions for:

* raw pixel coordinates
* preprocessed coordinates
* pyramid coordinates
* feature coordinates
* reference coordinates
* registered coordinates
* physical coordinates when available

Every transformation must be explicitly tracked.

Never mix:

* x/y
* row/column
* width/height
* pixel-center conventions
* normalized coordinates

without explicit conversions.

Add tests.

---

# 41. IMAGE RESAMPLING SAFETY

Investigate:

* interpolation method
* aliasing
* pyramid construction
* pixel-center conventions
* border behavior

Do not accidentally introduce fake correspondences through poor interpolation.

---

# 42. GEOMETRIC VERIFICATION

Every candidate correspondence should be checked for consistency.

Investigate:

* RANSAC
* MAGSAC-like approaches if useful
* robust estimation
* local consistency
* mutual consistency
* cycle consistency
* neighborhood consistency

Do not trust descriptor similarity alone.

---

# 43. TRANSFORMATION MODEL SELECTION

The system should potentially compare:

* similarity
* affine
* homography
* local models

and choose based on evidence.

Define a principled model-selection procedure.

Do not create arbitrary if/else logic without validation.

Consider:

* inlier quality
* residual distribution
* model complexity
* spatial coverage
* stability

Potentially use a model-selection criterion balancing fit and complexity.

---

# 44. LOCAL REFINEMENT

After global registration, investigate whether local refinement improves alignment.

Potentially:

global alignment
→ local patches
→ fine correspondence
→ local adjustment

But avoid uncontrolled local warping that can produce visually nice but physically incorrect results.

The registered product must remain geometrically meaningful.

---

# 45. SUB-PIXEL REFINEMENT

The sub-pixel stage should:

1. start from a high-quality coarse correspondence;
2. evaluate a local neighborhood;
3. estimate a continuous-valued optimum;
4. compute uncertainty;
5. reject unstable matches;
6. feed only trustworthy points to final geometric estimation where appropriate.

Do not refine obviously incorrect correspondences.

---

# 46. SPATIAL COVERAGE MODULE

Create a dedicated module that selects correspondence points based on both:

* matching quality
* spatial distribution

Potentially optimize a score such as:

quality
+
coverage
+
geometric diversity
-------------------

redundancy

Test multiple strategies.

---

# 47. VISUALIZATION SYSTEM

The final demo should be excellent.

Include:

1. source image
2. reference image
3. detected features
4. raw matches
5. filtered matches
6. inlier matches
7. spatial distribution
8. transformation
9. registered image
10. overlay
11. checkerboard comparison
12. error map
13. confidence map
14. metrics dashboard

The visualization should help a judge understand the system within seconds.

---

# 48. DEMO DESIGN

Create an end-to-end demo:

Input:

* Chandrayaan image
* reference image

System displays:

### Stage 1

Input images

### Stage 2

Preprocessing / normalization

### Stage 3

Candidate matches

### Stage 4

Verified correspondences

### Stage 5

Uniform spatial selection

### Stage 6

Sub-pixel refinement

### Stage 7

Registration

### Stage 8

Metrics

The demo should clearly show why the approach is robust.

---

# 49. COMPARISON DEMO

A particularly strong presentation would show:

### Conventional pipeline

SIFT + RANSAC

versus

### Proposed pipeline

our final system

under difficult conditions:

* different Sun angle
* different scale
* different sensor

Show:

* failed/misaligned conventional result
* successful proposed result

But ONLY if the comparison is experimentally fair.

Do not artificially sabotage the baseline.

---

# 50. BUILD A "CHALLENGE SUITE"

Create standardized challenging test categories:

```text
Challenge A — Small illumination difference
Challenge B — Large illumination difference
Challenge C — Low Sun elevation
Challenge D — Large scale difference
Challenge E — Viewpoint change
Challenge F — Cross-sensor
Challenge G — Low-texture terrain
Challenge H — Repetitive terrain
Challenge I — Shadow-heavy terrain
Challenge J — Difficult unseen scene
```

Generate a scorecard.

---

# 51. CREATE A FAILURE TAXONOMY

Explicitly classify failures:

* insufficient overlap
* repetitive terrain ambiguity
* severe shadow mismatch
* modality gap
* low texture
* large scale gap
* extreme viewpoint
* geometric model mismatch
* insufficient correspondences
* poor spatial coverage
* local minima
* image artifacts
* metadata error
* preprocessing error

Use this taxonomy to improve the system systematically.

---

# 52. RESEARCH THE POSSIBILITY OF SELF-SUPERVISED LEARNING

If training data is limited, investigate self-supervised or weakly supervised approaches.

Potential sources of supervision:

* geometric transformations
* synthetic illumination changes
* scale changes
* simulated perspective changes
* image pyramids
* physically plausible augmentations
* known correspondence from controlled warps

But do NOT let synthetic training create a false sense of generalization.

Validate heavily on real lunar imagery.

---

# 53. SYNTHETIC DATA MUST BE PHYSICALLY REASONABLE

If synthetic augmentation is used, do not use arbitrary ImageNet-style transformations blindly.

Investigate realistic lunar-specific transformations:

* illumination changes
* contrast changes
* shadow changes
* scale
* rotation
* viewpoint perturbation
* blur
* noise
* resolution changes

Where possible use physical/metadata-informed simulation.

---

# 54. CROSS-SENSOR LEARNING

If training is used, consider explicitly training for:

OHRC ↔ reference

TMC-2 ↔ reference

IIRS ↔ reference

and potentially cross-sensor relationships.

Evaluate whether a unified model or sensor-specific adaptation works better.

Do not assume one model is best.

---

# 55. GENERALIZATION TARGET

The final architecture should aim to generalize to:

* unseen scenes
* unseen craters
* unseen acquisition conditions
* unseen illumination
* unseen scales
* possibly unseen sensor pairings

Do not optimize only for the SIH sample.

The conceptual target should be:

**a general lunar image correspondence engine**

rather than:

**a one-dataset model.**

---

# 56. PHYSICAL FEASIBILITY

This is primarily a software problem, but still consider operational realism.

Think about:

* compute cost
* storage
* throughput
* reliability
* reproducibility
* deployment
* maintainability

The concepts of:

* cost
* mass
* power
* reliability
* efficiency
* scalability
* manufacturability

are more critical for hardware systems, but where they map into this software problem, interpret them as:

### Cost

developer/runtime/cloud/GPU cost

### Mass

software/model/data footprint

### Power

compute energy / hardware efficiency

### Reliability

failure rate / robustness

### Efficiency

accuracy per compute cost

### Scalability

large datasets / multiple sensors / future missions

### Manufacturability

for software, interpret as deployment simplicity and operational maintainability

Do NOT pretend these are hardware parameters when they are not.

---

# 57. SOFTWARE ARCHITECTURE SHOULD BE PRODUCTION-QUALITY

Use:

* clean interfaces
* typed Python where practical
* proper error handling
* logging
* configuration
* reproducibility
* tests
* documentation
* modularity

Avoid:

* giant scripts
* duplicated logic
* hidden global state
* hardcoded paths
* unexplained constants
* untracked preprocessing
* silent failures

---

# 58. TESTING REQUIREMENTS

Create automated tests for:

* image loading
* metadata loading
* preprocessing
* coordinate transformations
* resizing
* tiling
* matcher output
* RANSAC logic
* spatial balancing
* sub-pixel refinement
* metric calculations
* registration
* output formatting

Include synthetic geometry tests where the true transformation is known.

---

# 59. SYNTHETIC VALIDATION

Before relying exclusively on real lunar data, create synthetic test cases with known transformations.

For example:

known translation
known rotation
known scale
known affine transform
known homography
known local perturbation

Then test whether the system recovers them.

This isolates algorithmic bugs from data difficulties.

---

# 60. NUMERICAL STABILITY

Pay special attention to:

* floating-point precision
* matrix conditioning
* degenerate point configurations
* normalization
* coordinate scaling
* large images
* sub-pixel optimization

Do not allow unstable geometry to produce apparently reasonable but numerically incorrect output.

---

# 61. CONFIDENCE MODEL

Explore whether each correspondence can have:

* confidence
* uncertainty
* local ambiguity
* geometric consistency

A strong system should be able to rank matches.

Use this information for:

* filtering
* spatial selection
* refinement
* final transformation estimation
* failure detection

---

# 62. UNCERTAINTY-AWARE REGISTRATION

Investigate whether transformation confidence can be derived from:

* number of inliers
* spatial spread
* residuals
* point uncertainty
* model stability

A registration based on widely distributed points should generally be more trustworthy than one based on clustered points.

Quantify this.

---

# 63. SEARCH SPACE REDUCTION

If metadata or geometry allows candidate overlap estimation, use it.

Do not waste computation matching every pixel of enormous images against every other pixel.

Investigate:

* coarse localization
* image pyramids
* region proposals
* overlap estimation
* tiling
* candidate windows
* metadata-guided search

This can materially improve efficiency.

---

# 64. MULTI-SCALE COARSE-TO-FINE DESIGN

Strongly investigate a hierarchy:

Level 1:
coarse global localization

Level 2:
coarse correspondence

Level 3:
geometric verification

Level 4:
fine correspondence

Level 5:
sub-pixel refinement

Level 6:
final registration

This may be more reliable than attempting dense high-resolution matching immediately.

Prove whether this hierarchy helps.

---

# 65. TILE-BASED PROCESSING

For very large lunar images, investigate tiled matching.

Requirements:

* overlap between tiles
* coordinate continuity
* duplicate correspondence removal
* tile boundary handling
* global consistency
* efficient parallel processing

Do not create seams or inconsistent transformations.

---

# 66. USE A STRONG BASELINE EVEN IF WE EXPECT IT TO FAIL

The baseline serves multiple purposes:

* sanity check
* debugging
* benchmark
* judge explanation

The correct narrative is:

"Here is what conventional methods can do."

"Here is where they fail."

"Here is the precise weakness."

"Here is what we changed."

"Here is the measured improvement."

That is much stronger than:

"we built an AI model and it worked."

---

# 67. FINAL ALGORITHM SELECTION

After experiments, explicitly create a comparison table:

| Approach | Accuracy | Inlier Ratio | Coverage | Robustness | Runtime | Memory | Complexity | Generalization | Overall |
| -------- | -------: | -----------: | -------: | ---------: | ------: | -----: | ---------: | -------------: | ------: |

Select the final architecture based on evidence.

If the most complicated method is not the best, choose the simpler method.

This is critical.

---

# 68. THE FINAL SOLUTION SHOULD HAVE A CLEAR CORE IDEA

By the end of research, reduce the entire system to a memorable technical thesis.

For example, the thesis might eventually become something conceptually like:

"Geometry-aware, illumination-robust, cross-modal coarse-to-fine lunar correspondence with spatially uniform sub-pixel refinement."

But DO NOT force this exact wording.

Derive the actual core idea from experiments.

The final solution needs one central idea that a judge can remember.

---

# 69. DO NOT COPY PAPER CLAIMS BLINDLY

Whenever a paper claims:

"state of the art"

ask:

* on which dataset?
* what sensors?
* what image size?
* what task?
* what overlap?
* what illumination?
* what training data?
* what evaluation protocol?
* does the claim transfer to lunar imagery?

Use evidence.

---

# 70. RESEARCH REQUIREMENT

When external information is required, use current and authoritative sources.

Prefer:

1. ISRO
2. NASA
3. USGS
4. ESA
5. peer-reviewed research
6. official project documentation
7. established technical repositories

Use papers for algorithms.

Use official mission documentation for sensor characteristics.

Use primary sources whenever possible.

Do not cite random blogs when a primary source exists.

---

# 71. SOURCE TRACEABILITY

Whenever an architectural decision relies on an external fact, record:

* source
* URL or paper
* relevant fact
* how it influenced the design

Maintain a research notes document.

---

# 72. DO NOT MAKE UP DATASET CHARACTERISTICS

If the official SIH dataset is not yet available:

say:

"Dataset characteristic unknown."

Do not invent:

* number of images
* resolution
* sensor distributions
* train/test split
* exact Sun-angle distribution
* annotation quality

Instead design the pipeline to adapt once the real data arrives.

---

# 73. WHEN THE ACTUAL SIH DATASET ARRIVES

Immediately create:

1. dataset profile
2. metadata profile
3. image resolution statistics
4. sensor distribution
5. overlap analysis
6. illumination statistics
7. scale statistics
8. data-quality assessment
9. annotation availability
10. train/validation/test strategy

Do not begin major model training before understanding the dataset.

---

# 74. THE PROJECT SHOULD WORK IN STAGES

Phase 0:
Research

Phase 1:
Dataset understanding

Phase 2:
Classical baselines

Phase 3:
Learned baselines

Phase 4:
Cross-modal robustness

Phase 5:
Hybrid architecture

Phase 6:
Spatial coverage

Phase 7:
Sub-pixel refinement

Phase 8:
Robust evaluation

Phase 9:
Optimization

Phase 10:
Demo

Phase 11:
Final documentation

Do not skip directly to Phase 8 because the demo "looks good."

---

# 75. STOP CONDITIONS

You must explicitly identify when NOT to add another component.

For example:

If adding module X gives:

+0.3% accuracy

but:

+5x runtime

and no meaningful robustness improvement,

the module may not be worth keeping.

Use quantitative tradeoffs.

---

# 76. OPTIMIZATION OBJECTIVE

Think in terms of a multi-objective score:

Accuracy
+
Robustness
+
Coverage
+
Generalization
+
Efficiency
+
Reliability
+
Explainability

not simply:

maximum benchmark score.

---

# 77. AVOID DATASET-SPECIFIC HACKS

Never:

* hardcode crater coordinates
* hardcode known correspondences
* memorize image IDs
* manually choose feature locations for the final system
* use ground truth during inference
* tune thresholds to one test image
* use test images to select the model

The final pipeline must work automatically.

---

# 78. NO HUMAN-IN-THE-LOOP IN THE FINAL PIPELINE

The development environment may use manual inspection.

The final pipeline should not require:

"click three corresponding points."

It should be automatic.

A judge should be able to give:

Image A
Image B

and obtain:

correspondences
+
registration
+
metrics.

---

# 79. CREATE AN INFERENCE API

Design a clean API concept such as:

```python
result = register_lunar_images(
    source_image=...,
    reference_image=...,
    source_metadata=...,
    reference_metadata=...,
)
```

The result should contain structured information.

---

# 80. OUTPUT SCHEMA

Design a clear result object, conceptually:

```python
RegistrationResult(
    registered_image=...,
    correspondences=[...],
    transformation=...,
    rmse=...,
    median_error=...,
    inlier_count=...,
    inlier_ratio=...,
    coverage_score=...,
    confidence=...,
    runtime_ms=...,
    diagnostics=...,
    success=...,
    failure_reason=...,
)
```

Adapt implementation details as needed.

---

# 81. ERROR HANDLING

Do not crash on:

* insufficient matches
* corrupted files
* no overlap
* degenerate geometry
* low-confidence matches
* missing metadata
* incompatible image dimensions
* unsupported formats

Return meaningful errors.

---

# 82. REPRODUCIBLE ENVIRONMENT

Create:

* requirements
* environment configuration
* installation instructions
* hardware requirements
* model download instructions where allowed
* deterministic settings where appropriate

The project should be easy for another engineer to reproduce.

---

# 83. DOCUMENT THE WHY, NOT JUST THE WHAT

Every major module should document:

* purpose
* assumptions
* algorithm
* inputs
* outputs
* limitations
* why it exists
* evidence of effectiveness

---

# 84. JUDGE-LEVEL QUESTIONS TO PREPARE FOR

Prepare strong answers to:

1. Why won't SIFT solve this?
2. Why won't ORB solve this?
3. Why do learned matchers help?
4. Why might learned methods still fail?
5. Why is this multi-modal?
6. How do you handle different Sun angles?
7. How do you handle scale?
8. How do you handle viewpoint?
9. How do you guarantee uniform correspondence distribution?
10. How do you obtain sub-pixel accuracy?
11. How do you reject false matches?
12. How do you detect failure?
13. How do you know your test isn't leaking?
14. How does this generalize to unseen craters?
15. How does this generalize across sensors?
16. How does this generalize to unseen illumination?
17. What if the overlap is tiny?
18. What if the scene has very little texture?
19. What if the transformation is not a homography?
20. Why is your approach computationally feasible?
21. What happens if metadata is missing?
22. What is the strongest baseline?
23. How much better are you than the baseline?
24. What is your biggest weakness?
25. What happens on failure?
26. Why should ISRO trust the output?

The implementation and experiments should make these questions answerable.

---

# 85. FINAL REPORT REQUIREMENTS

Produce a technical report containing:

1. Problem definition
2. Motivation
3. Lunar imaging challenges
4. Related work
5. Baselines
6. Proposed approach
7. Architecture
8. Algorithms
9. Data pipeline
10. Training methodology if applicable
11. Evaluation methodology
12. Results
13. Ablation studies
14. Failure analysis
15. Computational analysis
16. Generalization analysis
17. Limitations
18. Future work
19. Conclusion

Never claim more than the evidence supports.

---

# 86. FINAL PRESENTATION REQUIREMENTS

The final presentation should communicate:

### Problem

Different lunar images do not look the same.

### Challenge

Different sensor + Sun angle + scale + viewpoint.

### Conventional problem

Ordinary matching can fail.

### Our insight

Use a robust representation and geometry-aware correspondence system.

### Our system

Show architecture.

### Evidence

Show benchmark.

### Result

Show registered product.

### Differentiator

Explain the specific innovation.

### Reliability

Show failure detection and confidence.

---

# 87. CODE QUALITY RULE

Do not create toy code.

When implementing something, create complete production-usable code.

Avoid:

```python
# TODO: implement later
```

unless there is a genuine external dependency that has not yet been resolved.

Do not leave critical pipeline stages mocked.

---

# 88. DEVELOPMENT RULE

Work iteratively.

After every major stage:

1. run tests
2. inspect metrics
3. inspect visualizations
4. inspect failures
5. document findings
6. decide next step

Do not blindly continue stacking features.

---

# 89. CRITICAL THINKING RULE

You are expected to challenge my ideas.

If I propose something bad, tell me:

"This is probably not the correct approach because..."

Then explain why and propose a stronger alternative.

Do not agree with me simply because I suggested it.

---

# 90. DO NOT OPTIMIZE FOR EGO

The project is highly competitive and I am personally very motivated to win.

However, do not let that motivation cause bad engineering.

A solution that is:

* simpler
* faster
* more robust
* easier to explain
* better validated

is preferable to a flashy but unreliable solution.

The real objective is to produce a system that survives technical scrutiny.

---

# 91. DO NOT CLAIM "100% WIN"

No one can guarantee an SIH victory.

Never make an unsupported claim that this solution will definitely win.

Instead maximize the controllable factors:

* technical quality
* evidence
* reliability
* novelty
* implementation completeness
* demo quality
* explanation
* benchmarking
* robustness

---

# 92. EXPECT THE HIDDEN JUDGE

Assume the judges may use examples that our system has never seen.

Therefore optimize for:

**generalization rather than memorization.**

---

# 93. EXPECT ADVERSARIAL TEST CASES

Assume the evaluation may contain:

* difficult lighting
* large scale changes
* unusual terrain
* weak texture
* sensor mismatch
* limited overlap
* noisy imagery
* deceptive local structures

Build robustness deliberately.

---

# 94. POTENTIAL STRATEGIC DIFFERENTIATOR

Investigate whether our strongest differentiator can be:

**not merely finding matches, but finding high-confidence, geometrically consistent, spatially distributed, sub-pixel correspondence with explicit uncertainty and failure detection.**

This is potentially more defensible than claiming:

"we use a transformer."

Do not assume this is the final differentiator; verify it experimentally.

---

# 95. AN IMPORTANT POSSIBLE DESIGN PRINCIPLE

Separate the problem into:

### Recognition

Where could correspondence exist?

### Verification

Are these points geometrically compatible?

### Precision

Where exactly is the correspondence at sub-pixel level?

### Coverage

Are correspondences spatially distributed?

### Registration

What transformation best aligns the images?

### Confidence

Should the result be trusted?

This decomposition should be seriously evaluated.

It may be more robust than trying to solve everything through one end-to-end black box.

---

# 96. POTENTIAL FINAL PIPELINE

Do NOT blindly implement this. Evaluate it against alternatives.

A promising architecture to investigate is:

```text
                 SOURCE IMAGE
                     │
                     ▼
             Metadata ingestion
                     │
                     ▼
          Radiometric preprocessing
                     │
                     ▼
       Illumination-robust representation
                     │
                     ▼
             Multi-scale pyramid
                     │
                     ▼
          Coarse candidate matching
                     │
                     ▼
            Cross-modal matching
                     │
                     ▼
        Geometric consistency filtering
                     │
                     ▼
          Spatial coverage selection
                     │
                     ▼
             Fine correspondence
                     │
                     ▼
           Sub-pixel refinement
                     │
                     ▼
         Robust transformation model
                     │
                     ▼
         Final geometric registration
                     │
             ┌───────┴────────┐
             ▼                ▼
     Registered product    Quality report
                              │
                 ┌────────────┼─────────────┐
                 ▼            ▼             ▼
               RMSE       Inlier ratio   Coverage
                 │
                 ▼
            Confidence
```

Again: this is a hypothesis, not a requirement.

---

# 97. WHAT WE MUST NEVER DO

Never:

* use only raw pixel correlation
* blindly trust SIFT
* blindly trust a single deep model
* assume homography always works
* use only RMSE
* optimize only inlier count
* ignore spatial distribution
* claim sub-pixel accuracy without measurement
* use data leakage
* train and test on nearly identical regions without careful splitting
* hardcode dataset-specific behavior
* overfit one crater
* manually select matches for the final pipeline
* use ground truth during inference
* hide failure cases
* cherry-pick results
* choose only the best examples
* compare against weak baselines
* make unsupported "state-of-the-art" claims
* add modules merely because they sound advanced
* sacrifice reproducibility for a demo
* sacrifice robustness for a single impressive screenshot
* hide uncertainty
* hide limitations
* fabricate unavailable dataset details
* confuse visual similarity with physical/geometric correspondence

---

# 98. WHEN SOMETHING FAILS

Do not immediately patch it with another arbitrary model.

Instead:

1. reproduce the failure
2. classify it
3. identify root cause
4. test hypotheses
5. compare alternatives
6. measure the effect
7. keep the change only if evidence supports it

---

# 99. RESEARCH NOTEBOOK

Maintain a running research document:

`docs/research_log.md`

For every important discovery include:

* observation
* hypothesis
* experiment
* result
* interpretation
* decision

This prevents circular experimentation.

---

# 100. DECISION LOG

Maintain:

`docs/architecture_decisions.md`

For every major architecture decision record:

* decision
* alternatives
* evidence
* trade-offs
* rationale

---

# 101. RESULTS TABLE

Maintain a machine-readable and human-readable experiment table.

For example:

`results/benchmark.csv`

and:

`docs/benchmark_report.md`

---

# 102. FINAL QUALITY BAR

Before calling the project "complete", verify:

### Functionality

* automatic correspondence
* automatic registration
* registered output
* match point output

### Accuracy

* low RMSE
* high inlier ratio
* high inlier count
* strong sub-pixel refinement

### Robustness

* illumination
* scale
* viewpoint
* sensor differences

### Coverage

* uniform spatial distribution

### Reliability

* confidence
* failure detection

### Generalization

* unseen scenes
* difficult examples

### Efficiency

* acceptable runtime
* acceptable memory

### Engineering

* tests
* configuration
* logging
* reproducibility
* documentation

### Demonstrability

* strong visualization
* clear metrics
* baseline comparison

---

# 103. REQUIRED INITIAL RESPONSE FROM CLAUDE CODE

Before starting major implementation, DO NOT immediately write hundreds of lines of code.

First produce a structured project analysis containing:

## A. Problem interpretation

Explain the problem in your own words.

## B. Technical challenges

Rank the challenges by difficulty and impact.

## C. Research landscape

Identify promising existing methods and why they may or may not transfer to lunar imagery.

## D. Candidate architectures

Propose at least 5 serious approaches.

## E. Baseline strategy

Define exactly which baselines we will implement.

## F. Evaluation strategy

Define metrics and dataset splits.

## G. Risk register

List the top technical risks.

## H. Recommended architecture

Recommend the current best architecture, but clearly mark uncertain assumptions.

## I. Experimental plan

Define the first sequence of experiments.

## J. Repository architecture

Propose the codebase structure.

## K. Data requirements

Specify exactly what data and metadata are required.

## L. Success criteria

Define what numerical and qualitative performance would make the system genuinely strong.

---

# 104. AFTER THE INITIAL ANALYSIS

Once the research plan is established, begin implementation in controlled stages.

At each major stage:

* implement
* test
* benchmark
* visualize
* analyze
* report
* decide

Do not skip validation.

---

# 105. FINAL PRINCIPLE

The strongest solution is NOT necessarily the one using the most advanced neural network.

The strongest solution is the one that most convincingly answers:

> Why does this work on lunar imagery?

> Why does it survive Sun-angle changes?

> Why does it survive scale changes?

> Why does it survive viewpoint changes?

> Why does it survive cross-modal differences?

> Why are the correspondences actually correct?

> Why are they spatially well distributed?

> How is sub-pixel accuracy obtained?

> How do we know when the result is trustworthy?

> How much better is it than conventional approaches?

> Can another engineer reproduce it?

> Can the system handle unseen lunar scenes?

> Can the system fail safely?

That is the standard.

---

# 106. IMMEDIATE TASK

Now begin.

Step 1:
Perform the technical/research analysis described above.

Step 2:
Research the current state of the art relevant to lunar / planetary image correspondence, cross-modal matching, illumination-invariant registration, scale-invariant registration, robust geometry, and sub-pixel refinement.

Step 3:
Identify the strongest practical candidate architectures.

Step 4:
Compare them against serious baselines.

Step 5:
Select an initial experimental architecture based on evidence.

Step 6:
Create the project repository structure.

Step 7:
Implement the baseline pipeline first.

Step 8:
Create the evaluation infrastructure before optimizing the final model.

Step 9:
Run experiments and record actual numerical results.

Step 10:
Iteratively improve the system based on measured weaknesses.

DO NOT skip the baseline.

DO NOT jump straight into a giant neural network.

DO NOT optimize the final architecture before understanding the dataset.

DO NOT claim success before benchmarking.

---

# 107. COMMUNICATION STYLE

Throughout the project:

* be direct
* be skeptical
* be technically precise
* challenge weak assumptions
* state uncertainty
* quantify decisions
* distinguish fact from hypothesis
* explain important trade-offs
* prioritize evidence

When you recommend a technique, explain:

**Problem → Mechanism → Expected Benefit → Cost → Risk → Experiment → Evidence → Decision**

---

# 108. FINAL OBJECTIVE

Build the strongest practical solution we can for:

**SIH26166 — Multi-modal, Sun angle and scale invariant image correspondence using Chandrayaan-2 optical images (OHRC, TMC and IIRS).**

The result should not merely be a software prototype.

It should be a:

**research-backed, benchmarked, robust, explainable, reproducible, efficient, production-quality lunar image correspondence and registration system suitable for serious SIH evaluation.**

The project should aim to stand out among hundreds of teams through:

**better reasoning, better engineering, better validation, stronger robustness, cleaner architecture, and measurable technical differentiation.**

Start with the research analysis.
