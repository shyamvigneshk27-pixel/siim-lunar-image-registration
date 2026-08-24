# `data/` — real lunar imagery

Every file here is externally sourced. Bulk products are **not** tracked in git
(see `.gitignore`); manifests and metadata are.

```
data/
  raw/          product bytes (IMG tiles fetched by byte range)   [gitignored]
  metadata/     PDS labels, one directory per region              [tracked]
  manifests/    dataset manifest + region survey                  [tracked]
  processed/    decoded / tiled / normalised products             [gitignored]
  demo/         the frozen subset the Sept 2 demo loads           [tracked]
```

## What is actually here

| Source | Status | Auth | Verified |
|---|---|---|---|
| **LRO NAC (LROC)** via PDS ODE | **labels acquired** (6), image tiles not yet ingested | none | 2026-08-24 |
| Chandrayaan-2 **OHRC** | **NOT OBTAINED** | ISSDC account required | 2026-08-24 |
| Chandrayaan-2 **TMC-2** | **NOT OBTAINED** | ISSDC account required | 2026-08-24 |
| Chandrayaan-2 **IIRS** | **NOT OBTAINED** | ISSDC account required | 2026-08-24 |

> **No multi-modal claim is supported by anything in this directory.**
> Every result to date is single-modality. See §9 of the project brief.

## LRO NAC — how it is obtained

`python scripts/acquire_lro_nac.py`

Queries the PDS Orbital Data Explorer (`https://oderest.rsl.wustl.edu/live2/`),
which is open and needs no credentials. Facts verified against the live service
on 2026-08-24, recorded so nobody rediscovers them:

- Identifiers are `ihid=LRO`, `iid=LROC`, `pt=CDRNAC4` (calibrated) or
  `EDRNAC4` (raw). **`EDRNAC` is not valid** and returns an error.
- Longitude parameters are **`westernlon`/`easternlon`**. `minlon`/`maxlon` are
  accepted and **silently ignored**, returning `Status: Success` with products
  spanning the whole Moon — see ERROR_LEDGER **E-019**. `query_nac()` now
  verifies the returned footprints against the box requested and raises if they
  disagree.
- Product URLs 302-redirect from `pds.lroc.im-ldi.com` to `pds.mcp.nasa.gov`.
- **IMG files serve HTTP 206 range requests** (verified: 2,048 bytes pulled
  from a 93 MB product). NAC frames run 93–530 MB, so the demo fetches tiles,
  not archives.

## What the metadata does and does not give us

ODE returns per product: `Incidence_angle`, `Emission_angle`, `Phase_angle`,
`Map_resolution`, `UTC_start_time`, `Solar_longitude`, and a real
`Footprint_geometry` polygon.

**It does not return sub-solar azimuth, and neither do the PDS4 labels**
(verified: zero hits for `incidence`/`sub_solar`/`emission` in all 6 downloaded
labels — ERROR_LEDGER **E-020**). Azimuth is the axis this project measured as
*dominant* (EXP-001: Δelevation −30° survived at 0.750 px while Δazimuth 45°
failed at 325 px), and it is the one angle the archive does not publish.

**Consequence, stated wherever these pairs appear:** candidate pairs are
selected by **incidence** difference and are therefore *illumination-varied*,
**not** *azimuth-controlled*. Obtaining azimuth requires deriving the sub-solar
point from observation time and target coordinates via a solar ephemeris. Until
that exists, no real-data azimuth claim may be made.

## Pair selection

`find_illumination_pairs()` shortlists pairs by:

1. incidence difference ≥ 15° (the illumination axis ODE does expose),
2. **measured footprint overlap** — rasterised intersection-over-union of the
   ODE `Footprint_geometry` polygons, ≥ 0.20,
3. map-resolution ratio ≤ 1.5.

Criterion 2 replaced a centre-proximity proxy, which was poor: NAC footprints
are long strips, so two frames can share a centre and barely overlap. The IoU
is approximate (grid-rasterised) and is a **shortlist**, not proof — the
authoritative overlap test is whether registration succeeds.

Survey as of 2026-08-24 (`manifests/region_survey.json`):

| Region | Terrain | Products | Candidate pairs | Best Δincidence | Best IoU |
|---|---|---|---|---|---|
| `apollo15_hadley` | mare/highland boundary | 40 | 37 | 63.7° | 0.247 |
| `mare_serenitatis` | mare (low texture) | 40 | 51 | 65.3° | 0.400 |
| `tycho_highlands` | highlands / crater | 40 | 29 | 41.4° | 0.333 |

## Provenance

Every entry in `manifests/lro_nac_manifest.json` carries: `pdsid`, instrument
identifiers, `utc_start`, centre lat/lon, `map_resolution_m`, incidence /
emission / phase angles, source URL, local path, and a **SHA-256** of each
downloaded file.

## Licensing

NASA PDS data are in the public domain. LROC products should be credited
**NASA/GSFC/Arizona State University**. Chandrayaan-2 data, once obtained, are
governed by ISRO/ISSDC terms accepted at registration — **check them before
redistributing anything**, including in the demo.

## To unblock Chandrayaan-2

Register at `https://pradan.issdc.gov.in` (Login/Signup). Browse and download
sit behind Keycloak OAuth at `idp.issdc.gov.in`; there is no anonymous API, and
ODE does **not** index Chandrayaan-2 (it carries Chandrayaan-1 only). This is a
human step that cannot be automated.
