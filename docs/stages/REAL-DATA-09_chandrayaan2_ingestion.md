# REAL-DATA-09 — Chandrayaan-2 ingestion, and the first Chandrayaan-2 ↔ LRO NAC registrations (OHRC, TMC-2, IIRS)

**Part 1 — pre-registration. FROZEN 2026-09-05, before any Chandrayaan-2 byte
is on disk.** The PRADAN registration and download are the user's action on
2026-09-06; this document is written so that nothing about the data can shape
the criteria. Part 2 is empty until Part 1 is committed and the products exist.

**Classification: DELIVERABLE-CRITICAL.** The problem statement is titled for
Chandrayaan-2 optical products against lunar reference imagery. Every result
in this repository to date is LRO NAC ↔ LRO NAC, plus two open-archive proxies
for the radar and 100 m rungs (REAL-DATA-08). This is the stage in which the
title becomes a measurement — or in which the honest position remains that it
could not.

## 1. Why this stage exists

`docs/STAGE_HISTORY.md` has carried *"NO Chandrayaan-2 data — no multi-modal
claim is supported"* since the first commit. REAL-DATA-08 measured the two
things a proxy can measure — a real modality change (radar: registered by
nothing) and the 100 m rung (registered by the learned engine on three of four
frames, with one wrong pass). What no proxy can measure is the actual sensor
family the problem statement names: OHRC at 0.25 m, TMC-2 at 5 m with its own
stereo DEM, and IIRS at 80 m with a spectral response no LRO instrument
shares. The ingestion machinery for their formats does not exist either; only
the LRO NAC PDS4 reader does.

## 2. The questions

**Q0 (ingestion).** Does every downloaded product load through a documented,
verified path — label parsed, structural identity checked, window decoded by
byte range, sanity-gated — and does its geometry place it on the ground the
recorded NAC frames cover?

**Q1 (TMC-2 rung).** Does a TMC-2 Level-2 orthoimage register to an LRO NAC
tile degraded to the TMC-2 GSD, and is the transform consistent with both
products' geometry?

**Q2 (OHRC rung).** Does an OHRC Level-1 calibrated product register to an LRO
NAC tile at the 2:1 to 5:1 ratio the two sensors actually have here?

**Q3 (IIRS rung).** Does an IIRS reflectance-band composite register to the
100 m WAC mosaic or to NAC degraded to 80 m, placed by IIRS's separate
geometry file?

**Q4 (physics conditioning at a fine DEM).** Does the TMC-2 DEM, rendered
under each image's Sun, carry matchable structure where the 59 m SLDEM did not
(RL-039b)?

**Q5 (the ladder).** Can an OHRC product be localised in IIRS pixels through
the chain OHRC → NAC or TMC-2 → IIRS, and with what error against the geometry
prediction, in IIRS pixels?

## 3. Data, fixed in advance

**Requested products (user action, 2026-09-06).** Search box latitude
19.0–21.5 N, longitude 21.5–22.8 E (Mare Serenitatis; contains both recorded
windows, the SLDEM window, the Mini-RF strip and the WAC block). Priority:

| instrument | products | rung |
|---|---|---|
| TMC-2 | one Level-2 orthoimage + its DEM (GeoTIFF), plus the Level-1 calibrated product if offered | 5 m; the DEM is a render source (Q4) |
| OHRC | two Level-1 calibrated products over the box if two exist, else one, with XML labels | 0.25 m |
| IIRS | one Level-1 calibrated cube with its geometry file (line-sample ↔ lat-lon); Level-2 reflectance if offered | 80 m |
| DFSAR | optional, one Level-2 product | radar (proxy already measured) |

**Fallback region.** If the box has no OHRC or IIRS coverage, the Chandrayaan-3
landing region (≈ 69.4 S, 32.3 E; OHRC stereo and NAC coverage exist). No NAC
tile from that region is on disk; using it means a fresh NAC acquisition with
the existing geometry-driven scripts, at high incidence, and every criterion
below applies unchanged with that stated.

**Placement.** Unrenamed, with every label and geometry file that came with
each product, under `data/raw/chandrayaan2/<instrument>/`. Nothing is
converted. A manifest under `data/manifests/chandrayaan2_manifest.json`
records for every file: path, size, SHA-256, the label fields the ingestion
contract reads, and the PRADAN product ID.

**What is not known and is not invented (spec §72).** The exact file layout
of each product, the PDS4 label schema ISRO uses for OHRC/TMC/IIRS, the IIRS
geometry file's format and its convention (which pixel corner, which
longitude domain), the GeoTIFF projection and datum of the TMC-2 Level-2
products, and the products' geolocation accuracy. The contract in §4 is
therefore written as **what the reader must verify**, not as an assumed
layout; where a product does not satisfy a check, the stage reports *format
not ingested* for that product and proceeds with the others. No silent
fallback, no partial decode presented as a decode.

**Licence and acknowledgement (recorded from https://pradan.issdc.gov.in/ch2/ack.xhtml, retrieved 2026-09-05; the user re-reads it on the day and any difference is recorded).**
Publications using the data must include: *"We acknowledge the use of data
from the Chandrayaan-II, second lunar mission of the Indian Space Research
Organisation (ISRO), archived at the Indian Space Science Data Centre
(ISSDC)."* — or, for work based on published Chandrayaan-2 results: *"The
research is based partially / to a significant extent (whichever is
applicable) on the results obtained from the Chandrayaan-II, second lunar
mission of the Indian Space Research Organisation (ISRO), archived at the
Indian Space Science Data Centre (ISSDC)."* The page further requires that
"Chandrayaan-II" appear in the abstract, that results be made available to
the community through publication, and that any printed data product carry
**"© reserved ISRO"**. The deliverable's licence section carries this
wording verbatim, and every figure that shows Chandrayaan-2 pixels carries the
© marking.

## 4. Ingestion contract, fixed in advance (behaviour, not code)

For every product, in this order, each step refusing rather than guessing:

1. **Label.** PDS4 XML parsed by the existing reader
   (`siim.ingest.pds4`), extended only by *explicit* additions to its data-type
   table and, for IIRS, by `Array_3D_Spectrum` / `Array_3D_Image` with a
   named band axis. Any element the contract needs that is absent raises
   with its name. GeoTIFF products are read by a pure-Python TIFF reader
   (`tifffile`, BSD-3; declared as the `chandrayaan2` extra), and the four
   GeoTIFF geometry tags — ModelTiepoint (33922), ModelPixelScale (33550),
   ModelTransformation (34264), GeoKeyDirectory (34735) — are recorded as
   found. A GeoTIFF without a tiepoint-or-transformation is *not ingested*.
2. **Structural identity.** File size must equal offset + lines × samples
   (× bands) × itemsize for arrays; for TIFF, strip/tile byte counts must sum
   to the image size. The check is the one that caught E-025's shape on NAC
   and is not optional.
3. **Window decode by byte range** (arrays) or by strip/tile (TIFF), into
   `array[line, sample]` (contract C2). A window is placed on the recorded
   RD-03 or RD-04 target ground point through the product's own geometry
   (step 5), never by a guessed centre.
4. **Sanity gate**, unchanged (`siim.ingest.sanity`): DN statistics, lag-1
   autocorrelation, decode-evidence margin. A tile that fails is reported as
   failing the gate, with the cause named as *decode* or *data* (D-032).
5. **Geometry**, one of three routes, recorded per product:
   - *Level-1 line-scan (OHRC, TMC-2 L1)*: corner coordinates from the label
     → bilinear corner map (the NAC machinery, `FrameCorners`), with the same
     ~150 m class uncertainty as the NAC corners, propagated by the same
     Monte-Carlo. If the label carries no corners, *not placed*; the product
     may still be matched against a placed product and the match reported
     with *no geometry check available*.
   - *Map-projected (TMC-2 L2 ortho and DEM)*: tiepoint + pixel scale (or the
     4 × 4 transformation) in the file's CRS; lon/lat per pixel through the
     projection named in the GeoKeys on the 1737.4 km sphere. Equirectangular
     and polar stereographic are implemented; any other projection is *not
     placed*. This is the `MapBlock` route REAL-DATA-08 used for Mini-RF and
     WAC.
   - *IIRS*: the separate geometry file gives (line, sample) ↔ (lat, lon); a
     bilinear map is fitted per tile and its residual recorded. Without the
     file the cube is *not placed*.
6. **Band policy (IIRS).** The matching channel is the mean of the
   reflectance-dominated bands **0.8–2.0 µm** (ANALYSIS §B1; IIRS L2
   literature). Bands 2.0–3.5 µm are excluded absent a thermal correction;
   bands ≥ 3.5 µm are excluded outright. The band indices used are recorded.
7. **Scale.** The finer product is degraded to the coarser GSD with the
   PSF-aware operator (`siim.preprocessing.degrade_to_gsd`, FWHM 1.0 coarse
   pixel, stated) — the operator REAL-DATA-08 Part 1 named and did not use.
8. **Orientation.** Level-1 tiles are rotated north-up from their corner
   signature (`siim.ingest.orientation`); map-projected products already are.
9. **Provenance.** Every artefact row carries the product ID, file SHA-256,
   window, decimation, band indices, geometry route and its residual.

## 5. Method, fixed in advance

Engines `B1` (unmodified RootSIFT) and `B4L` (DISK + LightGlue), through the
deliverable pipeline `siim.pipeline.register_pair` (estimate → refine →
re-estimate with rule B → verify) with engine agreement recorded; LO-RANSAC
affine, threshold 3.0 px, seed 0; failure rule `n_inliers <= 8` (D-023),
unchanged. Every pass is checked against the geometry prediction where both
products are placed, with a floor of `max(150 m, σ_C2) / GSD_reference` plus
the 1.2 % bilinear term, where `σ_C2` is the Chandrayaan-2 product's stated
geolocation uncertainty if the label gives one and **50 m** otherwise (master
plan §55 risk 4, stated as an assumption). A pass that is INCONSISTENT is a
wrong pass. Where three products cover one ground point (OHRC, TMC-2, NAC),
loop closure is computed and reported.

Pairs and rungs, run in this order and stopped only by a missing product:

| pair | source → reference | reference GSD | rung |
|---|---|---|---|
| P1 | TMC-2 L2 ortho → NAC long window degraded to the TMC GSD | ≈ 5 m | 5 m |
| P2 | NAC (native) → OHRC degraded to the NAC GSD | 0.9–1.3 m | 2:1–5:1 |
| P3 | OHRC → TMC-2 L2 ortho, OHRC degraded to 5 m | 5 m | 20:1 |
| P4 | IIRS 0.8–2.0 µm composite → WAC 100 m block (and → NAC degraded to 80 m) | 80–100 m | IIRS |
| P5 | TMC-2 ortho → TMC-2 DEM render under the ortho's Sun; NAC degraded to 5 m → same DEM render under NAC's Sun; composed through the ground (EXP-007's two-leg arm) | 5 m | Q4 |
| P6 | OHRC → IIRS, through P2/P3 and P4 composed; reported as OHRC's location in IIRS pixels against the geometry prediction | 80 m | 320:1 |

## 6. Hypotheses and criteria — FROZEN

**S0 (ingestion gate).** Every downloaded product either passes steps 1–5 of
§4 with its geometry placing the target inside it, or is reported *not
ingested* with the failing step named. *Nothing in S1–S5 is evaluated on a
product that failed S0.* Prediction: TMC-2 L2 and OHRC L1 ingested; IIRS
placed only if the geometry file is understood. Confidence MEDIUM.

**H1 (TMC-2 rung).** P1 registers.
> **S1 MET** if ≥ 1 P1 pair passes the rule under B1 or B4L with a
> geometry-consistent (or, if only one side is placed, unchecked-and-stated)
> transform, and the engine's agreement with the other engine is within the
> agreement floor where both pass. Prediction: MET for B4L (EXP-007 tier 2
> registered ~40° NAC pairs at 3.6–7 m; the ortho is map-projected and
> north-up). Confidence MEDIUM.

**H2 (OHRC rung).** P2 registers.
> **S2 MET** if ≥ 1 P2 pair passes under either engine with a
> geometry-consistent transform. Prediction: MET if the OHRC swath (3 km)
> actually covers a recorded window; UNKNOWN otherwise. Confidence LOW-MEDIUM.

**H3 (IIRS rung).** P4 registers.
> **S3 MET** if ≥ 1 P4 pair passes under B4L with a geometry-consistent
> transform, in WAC or NAC-degraded pixels. Prediction: LOW-MEDIUM (REAL-DATA-08
> gave B4L 3 of 4 at 100 m NAC ↔ WAC; IIRS adds a spectral response change and
> 80 m sampling).

**H4 (physics conditioning at a fine DEM).** P5's render arm passes at least
one pair that the raw B1 arm of the same pair fails.
> **S4 MET** if so, with a geometry-consistent composed transform. Prediction:
> UNKNOWN (the DEM/GSD ratio at this rung is ≈ 2:1 against 30:1 for SLDEM at
> native NAC). Confidence LOW. This is RL-039b's first test if the TMC-2 DEM
> arrives.

**H5 (the ladder).** P6 localises OHRC in IIRS pixels.
> **S5 MET** if the composed OHRC → IIRS transform places the OHRC tile centre
> within **1 IIRS pixel** (80 m) of the geometry prediction, with a bootstrap
> CI reported in IIRS pixels. Prediction: LOW. Reported either way.

**S6 (control, must hold).** The `none` arm on the six recorded NAC edges
reproduces 5365, 1656, 4, 4, 7, 3 in this run's environment; no Chandrayaan-2
step changes any NAC number. If S6 fails the stage stops.

**Wrong-pass rate** per engine, reported, feeding the verdict's
false-acceptance bound (1 / 23 for B4L after REAL-DATA-07/08).

## 7. What each outcome licenses

| Result | Claim |
|---|---|
| S0 fails for an instrument | "Format not ingested" for that instrument, with the failing check named; no result for it, and no proxy presented in its place |
| S1 MET | The TMC-2 rung of the ladder is demonstrated on the real sensor; the words "Chandrayaan-2" may appear in a result sentence for the first time |
| S2 MET | OHRC ↔ NAC at 2–5:1 demonstrated; the deliverable's two named products can be emitted for a Chandrayaan-2 pair |
| S3 MET | The IIRS rung demonstrated with the band policy stated; the multimodal claim is supported for *spectral* modality change, still not for radar |
| S3 NOT MET | IIRS ↔ visible remains unsupported; reported with the band policy and the RD-08 proxy beside it |
| S4 MET | H0 restored within a stated DEM/GSD ratio (D-046 reversed in scope) |
| S4 NOT MET | H0 not supported at a 2:1 DEM/GSD ratio either; the physics-conditioning claim is withdrawn from the architecture except as a verifier |
| S5 MET | The 320:1 localisation is demonstrated with a CI, in the reference's own pixels |
| Any S NOT MET | Reported as such; nothing is re-scoped after the fact |

## 8. Threats to validity, registered in advance

- **Geolocation of the Chandrayaan-2 products** is not known to this
  project; the 50 m assumption sets the floor and is stated wherever a floor
  is quoted. A product whose label states its accuracy replaces the
  assumption.
- **Orthorectified vs raw.** TMC-2 L2 is map-projected on its own DEM; NAC
  tiles are not. On this mare the relief displacement is small (< 1 px at 5 m
  for < 10 m relief within a tile); it is stated, not corrected.
- **Illumination is uncontrolled.** Each product comes with its own Sun; the
  stage records Δincidence per pair and interprets outcomes in the light of
  REAL-DATA-07's envelope (nothing above 40° passes at ≈ 2 m; four frames fail
  regardless), and does not claim illumination invariance from one pair.
- **OHRC coverage.** A 3 km swath may miss both recorded windows; then P2, P3
  and P6 have no data and say so.
- **IIRS thermal contamination** at 2–3.5 µm and the emission-dominated bands
  beyond are excluded by policy, not corrected; a matched IIRS pair says
  nothing about those bands.
- **The fallback region** is at ≈ 69 S where incidence is high on every
  product; results there are a different regime from Mare Serenitatis and are
  labelled as such.
- **n is what the download gives.** No significance claim.
- **The dependency** `tifffile` enters the repository for this stage; its
  licence (BSD-3) is recorded in the licence audit.

## 9. What this stage does NOT do

No matcher tuning, no Chandrayaan-2-specific engine, no accuracy claim
(no ground truth), no thermal-band matching, no radar claim beyond
REAL-DATA-08, no bundle adjustment, no SPICE (corner geometry only), no
redistribution of Chandrayaan-2 pixels beyond figures carrying the ISRO
marking.

---

## Part 2 — Results

*Empty until Part 1 is committed and the products exist.*
