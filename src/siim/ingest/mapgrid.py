"""Row blocks of map-projected archive products, and their (lon, lat) <-> pixel map.

Used by REAL-DATA-08 for the Mini-RF S-band strip (PDS3, equirectangular,
2048 px/deg) and the LROC WAC 100 m global mosaic tile (PDS4, equirectangular,
100 m). Both are *simple cylindrical / equirectangular with the equator as the
standard parallel*, so the pixel map is affine in (lon, lat):

    line   = (lat_top - lat) * ppd_lat - 0.5
    sample = (lon - lon_left) * ppd_lon - 0.5

pixel-registered, matching the PDS convention used for SLDEM (lola_dem). The
block keeps only ``[row0, row1)`` of the product and a column window, fetched
by byte range, and refuses to answer outside what it holds.

Provenance for every block (URL, byte range, SHA-256) is written by
``scripts/acquire_real_data_08.py`` into ``data/manifests``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

__all__ = ["MapBlock", "load_map_block"]


@dataclass(frozen=True)
class MapBlock:
    data: NDArray[np.float32]        # (rows, cols) of the fetched window
    row0: int                        # product line of data[0]
    col0: int                        # product sample of data[:, 0]
    ppd_lat: float
    ppd_lon: float
    lat_top_deg: float               # latitude of the product's line -0.5 edge
    lon_left_deg: float              # longitude of the product's sample -0.5 edge
    name: str
    provenance: dict

    # --- ground <-> pixel, in PRODUCT coordinates ---------------------------
    def line_of_lat(self, lat):
        return (self.lat_top_deg - np.asarray(lat, float)) * self.ppd_lat - 0.5

    def sample_of_lon(self, lon):
        return (np.asarray(lon, float) - self.lon_left_deg) * self.ppd_lon - 0.5

    def lat_of_line(self, line):
        return self.lat_top_deg - (np.asarray(line, float) + 0.5) / self.ppd_lat

    def lon_of_sample(self, sample):
        return self.lon_left_deg + (np.asarray(sample, float) + 0.5) / self.ppd_lon

    # --- ground <-> pixel, in BLOCK coordinates (what the matcher sees) --------
    def block_xy_of_lonlat(self, lon, lat) -> NDArray[np.float64]:
        x = self.sample_of_lon(lon) - self.col0
        y = self.line_of_lat(lat) - self.row0
        return np.column_stack([np.asarray(x, float).ravel(), np.asarray(y, float).ravel()])

    def lonlat_of_block_xy(self, x, y):
        return (self.lon_of_sample(np.asarray(x, float) + self.col0),
                self.lat_of_line(np.asarray(y, float) + self.row0))

    @property
    def lat_range(self) -> tuple[float, float]:
        r = self.data.shape[0]
        return (float(self.lat_of_line(self.row0 + r - 1)), float(self.lat_of_line(self.row0)))

    @property
    def lon_range(self) -> tuple[float, float]:
        c = self.data.shape[1]
        return (float(self.lon_of_sample(self.col0)), float(self.lon_of_sample(self.col0 + c - 1)))

    @property
    def metres_per_pixel(self) -> tuple[float, float]:
        r = 1_737_400.0 * np.pi / 180.0
        return (float(r / self.ppd_lon * np.cos(np.deg2rad(np.mean(self.lat_range)))),
                float(r / self.ppd_lat))


def load_map_block(manifest_name: str, root: Path | None = None) -> MapBlock:
    root = root or Path(__file__).resolve().parents[3]
    man_path = root / "data" / "manifests" / manifest_name
    man = json.loads(man_path.read_text(encoding="utf-8"))
    npy = root / man["block_npy"].replace("\\", "/")
    if not npy.exists():
        raise FileNotFoundError(
            f"{npy} absent; re-fetch bytes {man['byte_start']}-"
            f"{man['byte_start'] + man['byte_count'] - 1} of {man['source_url']} "
            f"(SHA-256 {man['bytes_sha256'][:16]}...)")
    data = np.load(npy)
    g = man["grid"]
    return MapBlock(data=data.astype(np.float32), row0=int(man["row0"]), col0=int(man["col0"]),
                    ppd_lat=float(g["ppd_lat"]), ppd_lon=float(g["ppd_lon"]),
                    lat_top_deg=float(g["lat_top_deg"]), lon_left_deg=float(g["lon_left_deg"]),
                    name=man["product"], provenance={k: man[k] for k in
                                                     ("source_url", "bytes_sha256", "credit", "manifest")
                                                     if k in man} | {"manifest": manifest_name})
