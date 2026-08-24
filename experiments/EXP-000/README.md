# EXP-000 — Geometry gate

**Objective.** Establish a verified geometry layer and coordinate contract before any real lunar data is touched. This is the gate from ANALYSIS §I: a pipeline that cannot recover a known transform to well under a pixel has a bug, and every subsequent measurement would be measuring that bug rather than the science.

**Configuration.** Seed `20260824`. Python 3.13.7, numpy 2.3.3, scipy 1.16.2. AMD Ryzen 5 7520U, 4C/8T, CPU-only. Pure numpy/scipy — no OpenCV, deliberately (ADR-0007 rejects inheriting conventions implicitly).

**Reproduce.** `python scripts/run_exp000.py` · `python -m pytest tests/ -q`

---

## Results

### Exact-correspondence recovery — true endpoint error, 50 trials per model

Error is measured between the *maps*, on a dense grid, not as a residual on the fitted points. That distinction is the whole of ANALYSIS §A.3.

| Model | Worst max endpoint error | Max condition | ms/fit |
|---|---|---|---|
| translation | 8.0e-14 px | 1.00 | 1.25 |
| euclidean | 3.6e-13 px | 1.00 | 1.43 |
| similarity | 4.7e-13 px | 1.00 | 1.34 |
| affine | 4.6e-13 px | 1.52 | 1.45 |
| projective | 7.0e-13 px | 3.54 | 2.45 |

All five recover at machine precision. **Gate target was < 0.1 px; achieved ~1e-13 px — eleven orders of margin.**

### Large-coordinate stability — homography at NAC scale

LRO NAC frames run to ~52,000 lines (sources.md S2), so the DLT has to stay conditioned far outside a tidy 0–512 range.

| Coordinate extent | Worst error | Relative error | Max condition |
|---|---|---|---|
| 512 | 4.9e-13 px | 9.6e-16 | 3.26 |
| 10,000 | 1.3e-11 px | 1.3e-15 | 3.58 |
| 60,000 | 6.2e-11 px | 1.0e-15 | 3.44 |

**Condition number is flat (~3.4) across a 117× span of coordinate magnitude.** That is Hartley normalisation doing exactly its job (contract C9). Without it the design matrix conditioning would degrade roughly as the square of coordinate magnitude, and the failure would appear as a quietly worse fit rather than an error.

### Contract C4 — the half-pixel bug, measured

Verified against *actual image resampling* of a Gaussian feature at a known sub-pixel location, not against the formula restated.

| Resample scale | Contract C4 `p' = s(p+0.5) − 0.5` | Naive `p' = s·p` |
|---|---|---|
| 0.25 | **0.0000 px** | 0.3750 px |
| 0.5 | **0.0000 px** | 0.2500 px |
| 2.0 | **0.0000 px** | 0.5000 px |
| 3.0 | **0.0000 px** | **1.0000 px** |

This is the single most valuable number in EXP-000. The naive coordinate update — which is what most implementations write — is wrong by `(s−1)/2` pixels, reaching **a full pixel at 3× resampling**. Our target is sub-pixel accuracy, and scale normalisation across the real sensor ladder (ANALYSIS §C.3) involves factors up to 320×. Getting this wrong would have consumed the entire error budget before any matching began, while every image still looked perfectly correct.

### Resampling fidelity and cost

| Quantity | Value |
|---|---|
| Identity warp max error | 0.0 (exact) |
| Round-trip median error | < 1e-5 |
| Round-trip p99 / max error | 2e-5 / 4e-5 |
| Cubic warp, 256×256 | **19.5 ms** |

Round-trip loss on smooth terrain is negligible against a sub-pixel budget. The 19.5 ms figure extrapolates to roughly 5 s for a 4096² warp on this CPU — the first real datapoint against the ≤60 s/pair runtime target (ANALYSIS §L), and a reminder that warping is not free at NAC scale.

---

## Test suite

**68 passed, 2 skipped** in 5.5 s. The two skips are intentional: translation and euclidean models cannot express a scale change, so the "recover a similarity truth" case does not apply to them.

Every obligation in the `docs/coordinate_contract.md` table is covered, including two tests that exist to *document* a hazard rather than to check a feature:

- `test_naive_scaling_is_wrong_by_exactly_half_of_scale_minus_one` — fails loudly with the size of the error if anyone "simplifies" `scale_transform`.
- `test_downsampling_without_antialias_aliases` — demonstrates the artefact the antialias default prevents (aliased variance is >3× the clean result), justifying the default rather than asserting it.

---

## Observations

1. **Hartley normalisation is not optional at lunar image scale.** The flat condition number across 512 → 60,000 px is the evidence. Given NAC frame sizes this would have been a real, silent accuracy leak.

2. **The pixel-centre convention has to be settled before scale normalisation is built, not after.** The C4 table shows why: at the scale factors this project actually needs, the naive formula's error exceeds the entire accuracy target.

3. **NaN-fill for invalid warp regions was the right default.** Lunar shadow is genuinely near-zero, so a `0.0` fill would be indistinguishable from real terrain. This is a lunar-specific hazard that a generic vision codebase would not think about, and it is now enforced by a test.

4. **Estimation cost is negligible** (1–2.5 ms/fit). Any runtime budget will be spent on matching and warping, not geometry. This supports putting engineering effort into the protocol layers (ANALYSIS §D.2) without a compute penalty.

---

## Conclusion

**Gate PASSED.** The geometry layer recovers all five transform models at machine precision, stays conditioned at NAC-scale coordinates, and implements the resampling coordinate convention correctly where the obvious implementation is wrong by up to a full pixel.

Real-data experiments are unblocked. ADR-0007 moves to `ACCEPTED`.

**Next:** EXP-001 — RootSIFT baseline against synthetic ground truth, which validates the *matching* harness the same way this validated the geometry harness. This requires a feature-detection dependency (OpenCV or an equivalent); that is the next decision.
