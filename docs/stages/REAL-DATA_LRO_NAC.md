# REAL-DATA — LRO NAC image ingestion and first real registration

**Stage ID:** REAL-DATA-01
**Name:** Turn acquired LRO NAC metadata into decoded real lunar image tiles that can enter the registration pipeline, and measure what the pipeline does with them
**Status:** **COMPLETE — ingestion SUCCEEDED, first registration FAILED (class C)**
**Date:** 2026-08-25 · **Depends on:** the 2026-08-24 real-data acquisition (E-019, E-020) · **Runs beside:** EXP-004 (not started), DEMO_TRACK
**Classification:** DEMO-RELEVANT and RESEARCH-RELEVANT. Not an EXP-numbered experiment: no hypothesis was pre-registered, because this is an ingestion and instrumentation stage. Everything measured here is reported as measurement, not as a validated claim.

> **Standing under integrity rule 10 is unchanged.** No multi-modal claim. No
> Chandrayaan-2 data was obtained or simulated. Nothing here is compared against
> synthetic ground truth.

---

## 1. Objective

Convert the LRO NAC products already identified in metadata into **decoded, provenance-tracked, sanity-checked real image tiles**, and run the existing RootSIFT baseline on them **unmodified**, so that the first real-data result is a measurement of the pipeline as built rather than of a pipeline tuned to the answer.

Two sub-objectives, both of which had to hold before any registration number could mean anything:

1. **Resolve the label defect** — 4 of 6 acquired labels were `Product_Browse`, which describe a JPEG pyramid and carry no image structure at all.
2. **Decode correctly, and be able to prove it** — offset, stride, byte order, axis order and truncation each produce a finite, correctly-shaped, wrong array.

## 2. Starting state (verified, not assumed)

| | |
|---|---|
| Git | clean at `54e8087`; EXP-000..003 complete; EXP-003 did not meet its criterion |
| Real image bytes on disk | **zero** — 108 KB of XML and nothing else |
| Labels | 12 on disk, 6 in the manifest; **4 of those 6 were `Product_Browse`** |
| Best candidate pair | `mare_serenitatis`, `nac.m1322281266lc` ↔ `nac.m1225876972lc`, Δincidence 65.3°, footprint IoU 0.400 |
| PDS4 decoder | did not exist anywhere in the repository |
| `src/siim/ingest` test coverage | **zero** |
| Tests | 194 passed, 2 skipped |

## 3. What was implemented

| File | What it is |
|---|---|
| `src/siim/ingest/pds4.py` | **new.** PDS4 `Array_2D_Image` label parsing, explicit dtype table, byte-range planning, tile decoding |
| `src/siim/ingest/sanity.py` | **new.** Quantitative pre-pipeline checks: byte order, alignment, saturation, truncation, spatial structure |
| `src/siim/ingest/lro_nac.py` | `_parse_product` selects files by ODE `Type`; `observational_label_url()`; validating `fetch_label()`; strict `fetch_byte_range()`; `fetch_image_tile()` |
| `scripts/acquire_real_pair.py` | **new.** Reproducible acquisition: labels → structures → footprint-based tile selection → byte-range fetch → manifest |
| `scripts/check_real_tiles.py` | **new.** Phase-6 sanity checks + diagnostic figures |
| `scripts/register_real_pair.py` | **new.** Unmodified B1 baseline on real tiles, with A/B/C/D classification |
| `src/siim/demo/api.py`, `static/index.html` | real scenario added **beside** the synthetic ones; provenance and caveats rendered |
| `tests/test_ingest_pds4.py` (41), `tests/test_ingest_sanity.py` (20), `tests/test_demo_verdict.py` (+5) | **new.** 66 tests where there were 0 |

### 3.1 The decoder, and the conventions it fixes

`Array_2D_Image` is parsed for `file_name`, `offset`, `axes`, `axis_index_order`, both `Axis_Array` entries (by **`sequence_number`**, which is 1-based), and `Element_Array/data_type`. Nothing is defaulted; every absent element raises with its own name.

- **`SignedLSB2` → `<i2`**, from an explicit table. Byte order is never inferred from a type name — `SignedLSB2` and `SignedMSB2` are one character apart.
- **Axis order comes from `sequence_number`, not document order.** `Line` = 1, `Sample` = 2.
- **Coordinate convention:** decoded arrays are `array[row, column] == array[line, sample]`, the project's C2 convention.
- **PDS4 line/sample numbering is 1-based**; numpy is 0-based; the mapping is `numpy_row = pds_line - 1`. **No function in this module accepts a 1-based index**, so there is no conversion to get wrong at a call site.
- **Offset is read from `Array_2D_Image`, not from `Header`.** `Header` carries its own `<offset>0</offset>`; reading it would start a NAC array at byte 0 instead of 5064 and displace every row by half a line, invisibly.

### 3.2 The structural check that validates everything at once

The label declares `File/file_size` independently of the array description, so

```
offset + lines × samples × itemsize  ==  file_size
5064   + 52224 × 5064  × 2           ==  528 929 736     ✓ exact
```

This single identity validates offset, both dimensions and element size **together**; any one being wrong breaks it. It is enforced in `validate_structure()` and raises rather than returning a flag.

## 4. What was measured

### 4.1 Decoded tiles

Two pairs were acquired, both from `mare_serenitatis`, tiles of 4096 lines × 2048 samples (41 484 288 bytes each, whole lines fetched, sample window applied after decoding).

| Product | Incidence | DN median | DN std | lag-1 autocorr | byte-swapped | decode verdict | **check** |
|---|---|---|---|---|---|---|---|
| `nac.m1271742202lc` | 29.95° | 1359 | 86.5 | **0.9590** | 0.5933 | consistent | **PASS** |
| `nac.m1335207975rc` | 69.76° | 473 | 79.1 | **0.9415** | 0.6680 | consistent | **PASS** |
| `nac.m1225876972lc` | 24.64° | 1582 | 133.6 | **0.9759** | 0.6123 | consistent | **PASS** |
| `nac.m1322281266lc` | **89.96°** | **29** | **19.6** | **0.3553** | 0.3531 | **inconclusive** | **FAIL — data quality** |

`[MEASURED]` — `experiments/REAL-DATA/tile_sanity_usable.json`, `tile_sanity_terminator.json`.

### 4.2 Independent support for the geolocation approximation

The footprint's latitude span divided by the frame's line count gives an implied metres-per-line that can be compared with ODE's independently-reported `Map_resolution`:

| Product | implied m/line | ODE `Map_resolution` | ratio |
|---|---|---|---|
| `nac.m1322281266lc` | 0.923 | 0.879 | **1.050** |
| `nac.m1225876972lc` | 1.010 | 0.962 | **1.050** |
| `nac.m1335207975rc` | 0.958 | 0.918 | **1.044** |

`[INTERPRETATION]` Three frames from different orbits and different years agreeing on the same 1.05 ratio supports the linear-latitude model as a *first-order* description of along-track geometry. It does **not** make the crop geographically registered — a constant 5% scale bias is exactly what a first-order model with no camera model would show.

### 4.3 Positive controls — the pipeline works on real NAC imagery

| Control | Result |
|---|---|
| `nac.m1271742202lc` vs **itself** | 12 707/12 707 inliers, identity recovered, max\|T−I\| **1.14e-12** |
| `nac.m1335207975rc` vs **itself** | 11 412/11 412 inliers, identity recovered, max\|T−I\| **1.25e-12** |
| Real tile vs itself shifted by a known **(+40, +25) px** | 11 521 inliers, recovered **(40.142, 24.941)** — error **0.14 px**, linear part max\|A−I\| 2.05e-04 |

`[MEASURED]` `[INTERPRETATION]` **The decode, preprocessing, detector, matcher, RANSAC and geometry chain is sound on real lunar imagery.** This bounds the interpretation of §4.4: the cross-pair failure is not an ingestion or pipeline defect.

### 4.4 First real registration — the headline measurement

Unmodified B1 (RootSIFT, mutual NN, ratio 0.8, LO-RANSAC, affine, threshold 3.0 px), tiles decimated 2× to 2048×1024.

| | `usable` pair (Δinc 39.8°) | `terminator` pair (Δinc 65.3°) |
|---|---|---|
| keypoints | 12 707 / 11 412 | 2 515 / 9 706 |
| putative (mutual + ratio) | 35 | 5 |
| **RANSAC inliers** | **3** | **3** |
| inlier ratio | 0.0857 | 0.6000 |
| **fit RMSE** | **1.575e-12 px** | **1.313e-13 px** |
| coverage gap | 0.4629 | 0.5616 |
| `n_inliers <= 8` | **FAIL** | **FAIL** |
| verdict | **REJECTED / none** | **REJECTED / none** |
| classification | **C** | **C** |
| runtime | 7.56 s | 1.04 s |

`[MEASURED]` `experiments/REAL-DATA/registration_usable.json`, `registration_terminator.json`.

**The estimated transform for the `usable` pair:**

```
 11.35236   -2.45232   -5801.51978
 17.88721   -3.07281   -9344.45726
  0.00000    0.00000       1.00000
```

An 11–18× scale change and a ~10 000 px translation between two frames of the same region at nearly the same resolution. It is nonsense.

> `[INTERPRETATION]` **This is E-008 reproduced on real lunar data for the first time.**
> The fit RMSE is **1.6e-12 px**. A pipeline that reported inlier RMSE — as most
> of the registration literature does — would present this as a registration
> accurate to a picometre. It is a catastrophically wrong answer, and the fit
> residual is at its *best* precisely because the solution collapsed to the
> affine minimal set of 3 correspondences. The project's founding claim was
> measured on synthetic terrain; it now has a real-data instance.

### 4.5 The line-direction ambiguity does not explain the failure

Whether line 0 sits at maximum (`H1`) or minimum (`H2`) latitude is not recoverable from the footprint. All four tile combinations were tested on genuinely distinct tiles (SHA-256 verified distinct before the comparison was trusted — see E-025):

| combination | line0 A | line0 B | keypoints | putative | inliers | fit RMSE | |
|---|---|---|---|---|---|---|---|
| A@H1 × B@H1 | 30 126 | 18 367 | 12 707 / 11 412 | 35 | **3** | 1.575e-12 | FAIL |
| A@H1 × B@H2 | 30 126 | 29 761 | 12 707 / 13 411 | 44 | **4** | 3.434e-13 | FAIL |
| A@H2 × B@H1 | 18 002 | 18 367 | 9 740 / 11 412 | 38 | **4** | 3.888e-01 | FAIL |
| A@H2 × B@H2 | 18 002 | 29 761 | 9 740 / 13 411 | 43 | **5** | 8.135e-13 | FAIL |

`[MEASURED]` `experiments/REAL-DATA/hypothesis_grid.json`. **All four fail.** The direction hypothesis is not the explanation, and three of the four again show the near-zero fit RMSE signature.

## 5. Exact commands executed

```bash
# label diagnosis (live ODE, per product)
python -c "... query=product, pdsid=nac.m1322281266lc, pt=CDRNAC4 ..."

# acquisition
python scripts/acquire_real_pair.py --pair terminator --lines 4096 --samples 2048 --hypothesis H1 \
       --out real_pair_terminator_manifest.json
python scripts/acquire_real_pair.py --pair usable --lines 4096 --samples 2048 --hypothesis H1 \
       --out real_pair_usable_manifest.json
python scripts/acquire_real_pair.py --pair usable --lines 4096 --samples 2048 --hypothesis H2 \
       --out real_pair_usableH2_manifest.json

# sanity checks + figures
python scripts/check_real_tiles.py --manifest real_pair_usable_manifest.json
python scripts/check_real_tiles.py --manifest real_pair_terminator_manifest.json

# registration
python scripts/register_real_pair.py --manifest real_pair_usable_manifest.json --downsample 2
python scripts/register_real_pair.py --manifest real_pair_usableH2_manifest.json --downsample 2
python scripts/register_real_pair.py --manifest real_pair_terminator_manifest.json --downsample 2

# tests
python -m pytest tests/ -q          # 260 passed, 2 skipped
```

**Commands that failed, recorded rather than tidied away:**

```bash
# ODE rejects the bare product id and reports Success with no products.
# The E-019 pattern again: a "successful" query is not a correct query.
pdsid=m1322281266lc   -> {"Products": "No Products Found", "Status": "Success"}
pdsid=nac.m1322281266lc -> 7 files returned

# two AttributeErrors from guessing the metrics API instead of reading it
cov.max_uncovered_disc_radius  -> AttributeError (it is max_uncovered_disc_ratio)
cov.occupancy                  -> AttributeError (it is grid_occupancy)
```

## 6. Dataset and product identifiers

| Role | pdsid | IMG | acquired (UTC) | incidence | `Map_resolution` |
|---|---|---|---|---|---|
| usable A | `nac.m1271742202lc` | `M1271742202LC.IMG` | 2018-01-28 | 29.95° | 0.904 m |
| usable B | `nac.m1335207975rc` | `M1335207975RC.IMG` | 2020-02-01 | 69.76° | 0.918 m |
| terminator A | `nac.m1322281266lc` | `M1322281266LC.IMG` | 2019-09-05 | 89.96° | 0.879 m |
| terminator B | `nac.m1225876972lc` | `M1225876972LC.IMG` | 2016-08-15 | 24.64° | 0.962 m |

All four: `LRO-L-LROC-3-CDR-V1.0`, 52 224 lines × 5 064 samples, `SignedLSB2`, array offset 5064 B, file 528 929 736 B.

## 7. Data provenance

Every tile is a byte range of an archive product, fetched over HTTP 206 with the returned length and `Content-Range` verified against the request. Manifests: `data/manifests/real_pair_{usable,usableH2,terminator}_manifest.json`.

Source: NASA PDS Orbital Data Explorer, `https://oderest.rsl.wustl.edu/live2/`, no credentials. Products served from `pds.lroc.im-ldi.com` (302 → `pds.mcp.nasa.gov`).
**Licence:** NASA PDS data are public domain. Credit **NASA/GSFC/Arizona State University**.

## 8. SHA-256 (of the fetched bytes, not of the decoded array)

| Product | tile lines | byte range | SHA-256 |
|---|---|---|---|
| `nac.m1271742202lc` H1 | [30126, 34222) | 305121192 + 41484288 | `56236a0fe23f34843d8bbf937c1239899139d785bdf6886ce33911250af2aa2d` |
| `nac.m1335207975rc` H1 | [18367, 22463) | 186026040 + 41484288 | `634394e50d7ace9dd7c4945de93a3a390d11bbf04464f5942f9c50eda2d6fff1` |
| `nac.m1322281266lc` | [19466, 23562) | — | `26b993bbc95a1858e560e8da8128d41417d75c6563a50552afee9838ed981342` |
| `nac.m1225876972lc` | [30517, 34613) | — | `d470f3ea4dfc265d3d56e69329e8e03f7263efdd68fa0b8420d6ba46798d39fa` |

The H1 tiles were re-fetched after the E-025 fix and reproduced these hashes **byte for byte**, which is the reproducibility evidence for the range fetch.

Observational label MD5 (from the labels themselves): `M1322281266LC` `d53866b856df1420a397c4ab98cdf32e` · `M1225876972LC` `bae3cbaa74af28197bee7e1a132d0681` · `M116385823RC` `426aec22b003640bd93651a7019372e0`.

## 9–13. Errors, detection, root cause, fix, regression test

Every entry uses **Problem → Evidence → Root Cause → Fix → Verification → Lesson** and is classified into exactly one of the five classes.

---

### E-022 — A `Product_Browse` label was accepted for 4 of 6 products, including both halves of the best pair
**Class: Implementation bug.** Severity **HIGH**.

**Problem.** The labels stored for four products described a JPEG browse pyramid, not the `.IMG`. They carry no `File_Area_Observational`, no dimensions, no offset, no data type. Decoding was impossible and the reason was invisible.

**Evidence.** Root elements of the six manifest labels: 4 × `Product_Browse` (~2 KB), 2 × `Product_Observational` (~13 KB). Grepping for image-structure elements: 0 hits in the browse labels, 7 in the observational ones.

**Root cause — and it is *not* a URL-pattern problem.** ODE returns both labels, each with an explicit `Type`:

```
Type=Product   PDS4 PRODUCT LABEL FILE   13 KB  .../DATA/ESM3/2019248/NAC/M1322281266LC.xml
Type=Browse    BROWSE LABEL               2 KB  .../EXTRAS/BROWSE/2019248/M1322281266LC_pyr.xml
```

`_parse_product` matched on file **extension** and assigned unconditionally (`elif up.endswith((".XML",".LBL")): lbl_url = url`), so the **last** `.xml` in list order won — and ODE lists `Browse` after `Product`. Products with a browse pyramid (7 files) got the wrong label; products without one (5 files) were correct **by accident**. Exactly 4 of 6, as observed.

**Fix.** Select by ODE's `Type` field — an explicit, documented, ODE-specific mapping. The browse URL is *kept* in `NacProduct.browse_label_url` rather than discarded, so the distinction stays visible. `observational_label_url()` **refuses to synthesise** a URL: the `DATA/<phase>/` segment (`ESM2`, `ESM3`, `ESM4`, `SCI`, `MAP`) is not recoverable from the browse path. Independently, `fetch_label()` validates the root element and the image structure of whatever actually arrives, and writes to disk only after it validates.

**Verification.** Both mare_serenitatis observational labels re-fetched live and validated (`Product_Observational`, structure parsed, `file_size` identity exact). Tests: `test_ode_product_label_wins_over_browse_label_listed_after_it`, `test_ode_label_selection_is_independent_of_file_order`, `test_untyped_records_never_select_a_browse_path_label`, `test_observational_label_url_refuses_to_synthesise_from_a_browse_url`, `test_browse_label_is_rejected_not_parsed`.

**Lesson.** **When a service classifies its own data, read the classification.** Inferring type from a filename discards information the API already gave you, and the failure is silent because both files are valid XML at the same URL shape. This is E-019's lesson in a new place: the response was successful and wrong.

---

### E-023 — The decode-correctness statistic collapsed onto the `-32768` sentinel border
**Class: Experimental / design mistake.** Severity **HIGH**.

**Problem.** The byte-order and alignment evidence reported **0.9919 for two different frames**, identical to four decimal places, with a vertical correlation of exactly **1.0000**.

**Evidence.** A whole-line NAC read includes wide constant `-32768` (`missing_constant`) border columns. Unmasked, their variance is ~3664 DN against a scene standard deviation of ~19.6 DN. Column medians: `-32768` for the first and last 8 columns, ~29 in the centre.

**Root cause.** `byte_order_evidence` and `byte_alignment_evidence` decoded with `mask_special_constants=False` and over the full 5064-sample width. Two large constant blocks separated by real data give a lag-1 correlation near 1 regardless of image content. **The statistic was measuring the border, not the image.**

**Fix.** Both functions now mask sentinels and apply the same sample window as the tile under test.

**Verification.** `test_sentinel_border_does_not_dominate_the_autocorrelation` constructs two framed scenes of very different contrast: unmasked they differ by < 1e-3 (indistinguishable), masked they differ by > 1e-3. On the real tiles the statistic now equals the plain autocorrelation exactly (0.9590, 0.9415, 0.9759, 0.3553).

**Lesson.** **This is E-010 recurring.** A statistic that collapses onto a sentinel measures the sentinel. The tell was the same both times — an implausibly round, implausibly identical number — and it was nearly reported as a result both times. *Always check what fraction of the data is sentinel before trusting a summary statistic computed over it.*

---

### E-024 — A 0.002 margin was reported as proof that working code had the byte order wrong
**Class: Experimental / design mistake.** Severity **MEDIUM**.

**Problem.** For the terminator tile the check reported *"byte-order reversal or misaligned offset"* on a decode that was demonstrably correct, sending the reader to debug working code.

**Evidence.** Declared decode 0.3553 vs byte-swapped 0.3531 — a margin of **0.0022**. On a synthetic pure-noise tile the swapped decode "won" by 0.0002 and was reported as a defect.

**Root cause.** The verdict used a bare `>` comparison. On a noise-dominated tile every decode is equally incoherent, so the test has **no discriminating power** there and the sign of a 1e-4 difference is arbitrary.

**Fix.** `DECODE_EVIDENCE_MARGIN = 0.10`. Below it the verdict is **`inconclusive`**, stated as such, with the margins reported. The low-autocorrelation failure is now split: with a `consistent` or `inconclusive` decode it is classified **`data quality (low SNR)`**, not a decoding defect, and the message says so.

**Verification.** `test_check_tile_blames_data_quality_not_the_decode_for_a_noisy_scene`, `test_thin_decode_margins_are_never_reported_as_a_decode_defect`, `test_check_tile_fails_a_byte_swapped_tile_and_blames_the_decode` (a genuine 0.256 margin is still caught).

**Lesson.** A discriminator needs a stated margin **and** a stated domain of validity. "Inconclusive" is a result; reporting it as a defect wastes the next reader's time on correct code. What actually justifies trusting the terminator tile's decode is that the *same code path* scores 0.9759 on its partner frame — argued from elsewhere, exactly as the check now says.

---

### E-025 — Acquiring the same product at a second offset silently overwrote the first tile
**Class: Implementation bug.** Severity **HIGH** (integrity rule 4 violation).

**Problem.** A four-way comparison of H1/H2 tile combinations returned **byte-identical results in all four rows** (9740/13411 keypoints, 43 putative, 5 inliers, fit RMSE 8.135e-13) — impossible for four different tile pairs.

**Evidence.** The identical numbers themselves. Then: tiles were written to `{pdsid}.tile.npy`, which encodes the product but **not the tile position**, so the H2 acquisition overwrote the H1 tiles and both manifests pointed at one file.

**Root cause.** Output filename omitted the tile position. This also violates integrity rule 4 — *never overwrite a superseded artefact*.

**Fix.** Filenames are now `{pdsid}.{hypothesis}.l{line0}.tile.npy`. Both hypotheses were re-acquired; the H1 re-fetch **reproduced its original SHA-256 exactly**, which is independent evidence that the byte-range fetch is deterministic. The comparison script now asserts the four tiles have four distinct hashes *before* interpreting the results.

**Verification.** The re-run produced four genuinely different rows (3, 4, 4, 5 inliers). The distinctness assertion is in `experiments/REAL-DATA/hypothesis_grid.json`'s generator.

**Lesson.** **Identical results across supposedly different conditions are a bug report, not a finding.** The instinct to explain the coincidence scientifically ("the direction hypothesis doesn't matter") would have produced a plausible, published, wrong conclusion. Encode every varying parameter in the artefact's name.

---

### E-026 — Maximising Δincidence selects the terminator, where one frame is unusable
**Class: Genuine research negative result** (about the *selector*, not the matcher). Severity **MEDIUM**.

**Problem.** The pair selector ranks candidates by incidence difference alone. Its top pick for `mare_serenitatis` was 89.96° vs 24.64°. An incidence of 89.96° puts the Sun 0.04° above the horizon.

**Evidence.** `nac.m1322281266lc`: DN median **29** ± 19.6 (I/F ≈ 0.00088), lag-1 autocorrelation **0.3553**, versus 1582 ± 133.6 and 0.9759 for its partner — a **55× brightness difference**. The tile decodes perfectly and fails the sanity check on data quality. Only 2 515 keypoints were detected against 9 706 in the partner, and the pair produced **5 putative matches**.

**Root cause.** A difference-maximising criterion with **no upper bound** on either operand necessarily selects the extreme of the range, and the extreme of incidence is the terminator.

**Fix.** Recorded as **D-029**: pair selection needs an incidence **ceiling** as well as a difference floor. A survey with both incidences ≤ 75° gave **32 usable pairs**, the best being `nac.m1271742202lc` × `nac.m1335207975rc` — Δinc 39.8°, footprint IoU **0.516** (the highest in the usable set), resolution ratio **1.016**. That pair became the primary case. The selector itself is **not yet changed in code** — see §18.

**Lesson.** An optimisation criterion is a specification of what you will get. "Most illumination difference" and "most informative illumination difference" are different objectives, and the archive contains enough range to make the difference fatal.

---

## 14. Numerical results

Collected in §4. Headline: **first real registration — 3 inliers, fit RMSE 1.575e-12 px, REJECTED, class C.** Positive control on the same real imagery: known (+40, +25) px shift recovered as (40.142, 24.941), **0.14 px**, 11 521 inliers.

## 15. Images and diagnostics produced

| Artefact | Content |
|---|---|
| `experiments/REAL-DATA/tile_sanity_{usable,terminator}.png` | Per tile: stretched image, DN histogram, and the four-bar decode-correctness evidence against the 0.60 plausibility floor |
| `experiments/REAL-DATA/tile_pair_{usable,terminator}.png` | The two tiles side by side under matched stretch, captioned as approximate overlap selection |
| `experiments/REAL-DATA/registration_{usable,usableH2,terminator}.png` | Inlier correspondences on both frames, captioned with class and "NO ground truth, NO azimuth control" |
| `experiments/REAL-DATA/tile_sanity_*.json`, `registration_*.json`, `hypothesis_grid.json` | Every statistic quoted above |

## 16. What succeeded

1. **The label defect is fixed at its root** and cannot silently recur: selection by ODE `Type`, plus independent validation of the content that arrives.
2. **A correct, explicit PDS4 decoder exists**, with the `file_size` identity as a structural proof and 41 tests.
3. **Real lunar image bytes are on disk** — 4 tiles, 166 MB fetched, SHA-256 recorded, byte-range fetch shown reproducible.
4. **The pipeline is proven sound on real NAC imagery** by two positive controls, one of which recovers a known shift to 0.14 px.
5. **The sanity layer caught a genuinely unusable frame** and, after E-024, attributed it correctly to data quality rather than to decoding.
6. **The verdict engine rejected a real registration whose fit RMSE was 1.6e-12 px** — the project's thesis, on real data.
7. **`src/siim/ingest` went from 0 to 61 tests**; suite 194 → **260 passed, 2 skipped**.

## 17. What failed

1. **Registration of both real pairs failed** — 3 and 3 inliers, class C.
2. **The terminator frame is unusable** for pixel-scale matching (E-026).
3. **The line-direction ambiguity is unresolved.** All four combinations fail, so the data does not decide it.
4. **Loop closure was not run on real data** — it needs a third overlapping real product, which was not acquired. The project's only trustworthy GT-free check is therefore **absent from every real-data result in this stage**.

## 18. What remains uncertain

- **Why the registration failed.** Two candidate causes remain live and this stage **does not separate them**: (a) the tiles do not actually overlap — the crop is an approximation with no camera model; (b) the illumination difference defeats the matcher, which is exactly what EXP-003 predicts (cliff at Δaz 21–27° on synthetic A-regimes) — though Δ*azimuth* is unknown here, so even that expectation is not directly applicable. **Evidence insufficient** to attribute.
- **Whether these frames overlap at all.** The footprint IoU of 0.516 is a whole-frame figure; it says nothing about whether two 3.7 km tiles inside those frames share ground.
- **The 1.05 metres-per-line ratio.** Consistent across three frames, unexplained. Possibly a footprint-polygon convention, possibly real along-track scale.
- **Whether `n_inliers <= 8` is a good rule on real data.** Applied here; **not validated here**. D-025 already withdrew its false-alarm rate once on synthetic data.
- **The pair selector is not yet fixed in code.** D-029 is recorded; `find_illumination_pairs()` still has no incidence ceiling.

## 19. Claims explicitly NOT supported

1. **No ground-truth accuracy claim of any kind on real imagery.** None exists for these products.
2. **No sub-pixel accuracy claim on real data.** The 0.14 px figure is a *self-consistency control* on a synthetically shifted copy of one real tile — not a registration of two independent frames.
3. **No comparison against synthetic ground truth**, and none was made.
4. **No Sun-azimuth invariance claim.** Azimuth is not published for these products (E-020). These pairs are **illumination-varied by incidence only**, never azimuth-controlled.
5. **No claim that the crop is geographically registered.** It is a **pre-registration overlap selection** from footprint latitude.
6. **No Chandrayaan-2 claim.** OHRC/TMC-2/IIRS remain behind ISSDC authentication; no such data was obtained, simulated or implied.
7. **No multi-modal claim.** Both frames are the same instrument.
8. **No validation of `n_inliers <= 8` on real data.**
9. **No loop-closure evidence on real data.**
10. **No claim that the registration failure is attributable to illumination.** See §18.

## 20. Next recommended experiment

**REAL-DATA-02 — establish real overlap independently of the matcher**, because until overlap is known, every real registration failure is uninterpretable.

In priority order:

1. **Acquire a third overlapping product** and run loop closure with three independently estimated edges. This is the project's strongest check and it is currently absent from all real-data results.
2. **Reduce the geolocation approximation.** Either use the browse pyramid (already identified, low resolution, whole-frame) as an overview to locate overlap by image content, or introduce a camera model / SPICE. The browse route needs no new dependency and directly answers "do these tiles share ground?".
3. **Add the incidence ceiling to `find_illumination_pairs()`** (D-029) and re-rank all 117 candidates.
4. **Then, and only then**, attribute the registration failure. With overlap established, a failure becomes a measurement of illumination robustness on real data; without it, it is not.

EXP-004 is unaffected by this stage and remains pre-registered and not started.
