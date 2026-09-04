"""SLDEM2015 / LOLA gridded DEM access, and the Sun direction in a tile's frame.

Why this module exists
----------------------
The Moon is the one registration target whose appearance change under a
different Sun is *predictable*: the surface is static, airless, and mapped
globally at 512 pixels per degree (SLDEM2015, Barker et al. 2016, ~59 m at the
equator, 3-4 m vertical). Every archive product carries its sub-solar point.
Together those let a reference DEM be shaded under **each image's own Sun** and
matched to that image, so the illumination difference is carried by the DEM and
not by the matcher (EXP-007, `docs/MASTER_RESEARCH_AND_ARCHITECTURE_PLAN.md`).

This module does two geometric jobs and nothing else:

1. **Bring the DEM onto a tile's pixel grid.** A tile is a window of a NAC frame
   whose ground map is the bilinear corner model of :class:`FrameCorners`
   (REAL-DATA-02). For each decimated tile pixel the (lon, lat) is looked up
   through that map and the DEM is sampled there. The result is a height field
   in **tile pixel coordinates**, which is what a renderer needs.

2. **Express the Sun direction in the tile's pixel axes.** The solar azimuth
   from :func:`siim.ingest.solar_geometry.solar_geometry_at` is clockwise from
   north on the ground. The renderer's azimuth is clockwise from image "up".
   The two differ by the frame's orientation, which for the frames used so far
   is roughly 180 degrees (line 0 at *minimum* latitude, sample increasing
   *westward*, E-032). The rotation is computed from the corner map's local
   Jacobian rather than assumed, and it is done per pixel location because the
   frames are long and slightly skewed.

Archive facts (from the PDS3 label, verified 2026-09-04)
----------------------------------------------------------
* Tile ``SLDEM2015_512_00N_30N_000_045_FLOAT.IMG``: 15360 lines x 23040
  samples, ``PC_REAL`` 32-bit little-endian, unit km relative to 1737.4 km,
  simple cylindrical, pixel-registered: ``lat = 30 - (line + 0.5) / 512``,
  ``lon = (sample + 0.5) / 512``. Record bytes 92160.
* The server honours HTTP byte ranges, so a row block is fetched without the
  1.4 GB tile. The fetched block and its SHA-256 are recorded in
  ``data/manifests/sldem2015_window_mare_serenitatis.json``.

What this module does NOT do
----------------------------
No camera model, no SPICE, no orthorectification. The ground map is the same
0.01-degree-quantised corner geometry every previous real-data stage used, so
the DEM is misplaced relative to the image by up to ~150 m. That offset is
absorbed by the image-to-render match, and is reported, not hidden.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from .footprint import FrameCorners

__all__ = [
    "MOON_RADIUS_M",
    "DemWindow",
    "load_sldem_window",
    "dem_on_tile_grid",
    "sun_in_tile_frame",
    "local_incidence_deg",
]

#: Reference radius of the SLDEM2015 product, metres.
MOON_RADIUS_M = 1_737_400.0

_DEFAULT_MANIFEST = "sldem2015_window_mare_serenitatis.json"


@dataclass(frozen=True)
class DemWindow:
    """A contiguous block of rows of one SLDEM2015 tile, held in memory."""

    #: (rows, 23040) heights in **kilometres** relative to the reference radius.
    heights_km: NDArray[np.float32]
    #: First tile line held in ``heights_km``.
    row0: int
    #: Pixels per degree of the tile.
    ppd: int
    #: Latitude of the tile's top edge and longitude of its left edge, degrees.
    lat_top_deg: float
    lon_left_deg: float
    #: Provenance carried into every artefact that uses this window.
    provenance: dict

    # ---- coordinate transforms (pixel-registered, PDS label convention) ----

    def line_of_lat(self, lat_deg):
        return (self.lat_top_deg - np.asarray(lat_deg, float)) * self.ppd - 0.5

    def sample_of_lon(self, lon_deg):
        return (np.asarray(lon_deg, float) - self.lon_left_deg) * self.ppd - 0.5

    @property
    def lat_range(self) -> tuple[float, float]:
        n = self.heights_km.shape[0]
        lo = self.lat_top_deg - (self.row0 + n - 0.5) / self.ppd
        hi = self.lat_top_deg - (self.row0 + 0.5) / self.ppd
        return (float(lo), float(hi))

    def height_m_at(self, lon_deg, lat_deg) -> NDArray[np.float64]:
        """Bilinear height in metres at (lon, lat); raises outside the window.

        Raising rather than clamping follows the footprint module's rule: an
        extrapolated height is a plausible number that hides a real error.
        """
        lon = np.asarray(lon_deg, float)
        lat = np.asarray(lat_deg, float)
        line = self.line_of_lat(lat) - self.row0
        samp = self.sample_of_lon(lon)
        rows, cols = self.heights_km.shape
        if (line.min() < 0 or line.max() > rows - 1
                or samp.min() < 0 or samp.max() > cols - 1):
            raise ValueError(
                "requested ground point lies outside the fetched DEM window "
                f"(lat range {self.lat_range}, lon range "
                f"({self.lon_left_deg + 0.5 / self.ppd:.4f}, "
                f"{self.lon_left_deg + (cols - 0.5) / self.ppd:.4f}))")
        i0 = np.floor(line).astype(int)
        j0 = np.floor(samp).astype(int)
        i1 = np.minimum(i0 + 1, rows - 1)
        j1 = np.minimum(j0 + 1, cols - 1)
        fi = line - i0
        fj = samp - j0
        h = self.heights_km.astype(np.float64)
        top = h[i0, j0] * (1 - fj) + h[i0, j1] * fj
        bot = h[i1, j0] * (1 - fj) + h[i1, j1] * fj
        return (top * (1 - fi) + bot * fi) * 1000.0


def load_sldem_window(manifest_name: str = _DEFAULT_MANIFEST,
                      root: Path | None = None) -> DemWindow:
    """Load the cached row block named by a manifest under ``data/manifests``.

    The block itself is gitignored (``data/raw``); the manifest records the byte
    range and SHA-256 so it can be re-fetched. A missing block is an error that
    names what to fetch, never a silent fallback to a flat surface.
    """
    root = root or Path(__file__).resolve().parents[3]
    man_path = root / "data" / "manifests" / manifest_name
    if not man_path.exists():
        raise FileNotFoundError(f"DEM window manifest not found: {man_path}")
    man = json.loads(man_path.read_text(encoding="utf-8"))
    npy = root / "data" / "raw" / "sldem" / (
        f"SLDEM2015_512_00N_30N_000_045_rows{man['row0']}_{man['row1_exclusive']}.npy")
    if not npy.exists():
        raise FileNotFoundError(
            f"DEM block {npy} is absent. Re-fetch bytes "
            f"{man['byte_start']}-{man['byte_start'] + man['byte_count'] - 1} of "
            f"{man['source_url']} (SHA-256 {man['bytes_sha256'][:16]}...)")
    heights = np.load(npy)
    if heights.shape != (man["row1_exclusive"] - man["row0"], man["line_samples"]):
        raise ValueError(f"DEM block shape {heights.shape} disagrees with its manifest")
    return DemWindow(
        heights_km=heights.astype(np.float32),
        row0=int(man["row0"]),
        ppd=int(man["map"]["ppd"]),
        lat_top_deg=30.0,
        lon_left_deg=0.0,
        provenance={"manifest": str(man_path.relative_to(root)),
                    "source_url": man["source_url"],
                    "bytes_sha256": man["bytes_sha256"],
                    "unit": man["unit"], "credit": man["credit"]},
    )


# --------------------------------------------------------------------------
# the corner map, vectorised
# --------------------------------------------------------------------------


def _lonlat_grid(corners: FrameCorners, lines: NDArray, samples: NDArray):
    """Bilinear (lon, lat) for arrays of 0-based frame line/sample."""
    u = np.asarray(samples, float) / (corners.samples - 1)
    v = np.asarray(lines, float) / (corners.lines - 1)
    ul = np.asarray(corners.upper_left, float)
    ur = np.asarray(corners.upper_right, float)
    ll = np.asarray(corners.lower_left, float)
    lr = np.asarray(corners.lower_right, float)
    w_ul = (1 - u) * (1 - v)
    w_ur = u * (1 - v)
    w_ll = (1 - u) * v
    w_lr = u * v
    lon = w_ul * ul[0] + w_ur * ur[0] + w_ll * ll[0] + w_lr * lr[0]
    lat = w_ul * ul[1] + w_ur * ur[1] + w_ll * ll[1] + w_lr * lr[1]
    return lon, lat


def dem_on_tile_grid(dem: DemWindow, corners: FrameCorners,
                     line0: int, sample0: int, n_lines: int, n_samples: int,
                     decimation: int):
    """Heights (metres) on a decimated tile grid, plus the (lon, lat) grids.

    A decimated pixel is the mean of a ``k x k`` block, so it sits at the
    block's centre: frame line ``line0 + r*k + (k-1)/2`` (the convention of
    :class:`siim.ingest.footprint.TileWindow`). Getting this wrong shifts the
    render by half a block and survives review, which is why it is pinned by a
    test rather than left to the reader.
    """
    k = int(decimation)
    if k < 1:
        raise ValueError("decimation must be >= 1")
    h_out = n_lines // k
    w_out = n_samples // k
    rr = line0 + np.arange(h_out) * k + (k - 1) / 2.0
    cc = sample0 + np.arange(w_out) * k + (k - 1) / 2.0
    lines, samples = np.meshgrid(rr, cc, indexing="ij")
    lon, lat = _lonlat_grid(corners, lines, samples)
    heights = dem.height_m_at(lon, lat)
    return heights, lon, lat


# --------------------------------------------------------------------------
# the Sun, in the tile's own axes
# --------------------------------------------------------------------------


def _ground_jacobian(corners: FrameCorners, line: float, sample: float,
                     step: float = 8.0) -> NDArray[np.float64]:
    """d(east_m, north_m) / d(sample, line) by central differences."""
    def en(li, sa):
        lon, lat = _lonlat_grid(corners, np.array([li]), np.array([sa]))
        return float(lon[0]), float(lat[0])

    lon_c, lat_c = en(line, sample)
    coslat = np.cos(np.deg2rad(lat_c))
    m_per_deg = np.deg2rad(1.0) * MOON_RADIUS_M

    def delta(li, sa):
        lon, lat = en(li, sa)
        return np.array([(lon - lon_c) * coslat * m_per_deg,
                         (lat - lat_c) * m_per_deg])

    d_sample = (delta(line, sample + step) - delta(line, sample - step)) / (2 * step)
    d_line = (delta(line + step, sample) - delta(line - step, sample)) / (2 * step)
    return np.column_stack([d_sample, d_line])  # 2x2: rows (E, N), cols (ds, dl)


def sun_in_tile_frame(corners: FrameCorners, line: float, sample: float,
                      sub_solar_lon_deg: float, sub_solar_lat_deg: float) -> dict:
    """Sun azimuth in image axes (clockwise from image up) and elevation.

    ``elevation = 90 - incidence`` on the spherical normal; local slopes are
    the renderer's business. The returned dict also carries the ground
    azimuth, the north direction in pixel axes and the pixel scale implied by
    the corner map, so the conversion can be audited from the artefact.
    """
    from .solar_geometry import solar_geometry_at

    lon, lat = _lonlat_grid(corners, np.array([line]), np.array([sample]))
    geo = solar_geometry_at(float(lon[0]), float(lat[0]),
                            sub_solar_lon_deg, sub_solar_lat_deg)
    jac = _ground_jacobian(corners, line, sample)
    if abs(np.linalg.det(jac)) < 1e-9:
        raise ValueError("degenerate corner map at the requested pixel")
    inv = np.linalg.inv(jac)

    az = np.deg2rad(geo.azimuth_deg)
    ground_dir = np.array([np.sin(az), np.cos(az)])          # (east, north)
    pix = inv @ ground_dir                                    # (dsample, dline)
    north_pix = inv @ np.array([0.0, 1.0])
    # image azimuth: clockwise from "up" (-y == -line), x == sample
    image_az = float(np.degrees(np.arctan2(pix[0], -pix[1])) % 360.0)
    sv = np.linalg.svd(jac, compute_uv=False)
    return {
        "incidence_deg": geo.incidence_deg,
        "elevation_deg": 90.0 - geo.incidence_deg,
        "azimuth_ground_deg_cw_from_north": geo.azimuth_deg,
        "azimuth_image_deg_cw_from_up": image_az,
        "north_direction_in_pixels_xy": [float(north_pix[0]), float(north_pix[1])],
        "corner_map_pixel_scale_m": [float(sv.min()), float(sv.max())],
        "lon_lat_at_pixel": [float(lon[0]), float(lat[0])],
    }


def local_incidence_deg(heights_m: NDArray, sun_azimuth_image_deg: float,
                        sun_elevation_deg: float, pixel_scale_m: float) -> NDArray:
    """Per-pixel incidence on the DEM-derived facet normal, degrees.

    The same normal and Sun vector the renderer uses, exposed so a per-pixel
    photometric normalisation can be built from the DEM. Exploratory in
    EXP-007; not part of its frozen criteria.
    """
    from ..data.synthetic_terrain import _sun_vector

    gy, gx = np.gradient(np.asarray(heights_m, float), pixel_scale_m)
    norm = np.sqrt(gx ** 2 + gy ** 2 + 1.0)
    sun = _sun_vector(sun_azimuth_image_deg, sun_elevation_deg)
    cos_i = (-gx * sun[0] - gy * sun[1] + sun[2]) / norm
    return np.degrees(np.arccos(np.clip(cos_i, -1.0, 1.0)))
