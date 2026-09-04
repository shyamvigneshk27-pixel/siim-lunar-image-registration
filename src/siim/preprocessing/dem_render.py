"""Render a DEM under a given image's Sun, on that image's tile grid.

This is the illumination-conditioning treatment of EXP-007. The renderer is
the project's existing Lambertian shader with cast shadows
(:func:`siim.data.synthetic_terrain.render`); nothing new is invented here, and
that is deliberate: the hypothesis under test is about *where the invariance
comes from*, not about a better shading model. Unit albedo, no noise.

The returned record states every number that went into the render, so a
reader can recompute it from the archive: which DEM bytes, which corners, the
Sun in ground and image axes, the pixel scale, the decimation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from ..data.synthetic_terrain import render
from ..ingest.footprint import FrameCorners
from ..ingest.lola_dem import DemWindow, dem_on_tile_grid, sun_in_tile_frame

__all__ = ["DemRender", "render_tile_under_sun"]


@dataclass(frozen=True)
class DemRender:
    """A rendered illumination-matched intermediary and its provenance."""

    image: NDArray[np.float64]
    heights_m: NDArray[np.float64]
    record: dict = field(default_factory=dict)


def render_tile_under_sun(dem: DemWindow, corners: FrameCorners, *,
                          line0: int, sample0: int, n_lines: int, n_samples: int,
                          decimation: int, pixel_scale_m: float,
                          sub_solar_lon_deg: float, sub_solar_lat_deg: float,
                          cast_shadows: bool = True) -> DemRender:
    """Shade the DEM as this tile would see it under this product's Sun.

    ``pixel_scale_m`` is the decimated pixel size (``k x`` the archive's scaled
    pixel). It couples horizontal and vertical scales in the shading, so it is
    an explicit argument rather than something inferred from the corner map,
    whose own scale is quoted to 0.01 degrees.
    """
    heights, lon, lat = dem_on_tile_grid(dem, corners, line0, sample0,
                                         n_lines, n_samples, decimation)
    centre_line = line0 + (n_lines - 1) / 2.0
    centre_sample = sample0 + (n_samples - 1) / 2.0
    sun = sun_in_tile_frame(corners, centre_line, centre_sample,
                            sub_solar_lon_deg, sub_solar_lat_deg)
    img = render(heights, sun["azimuth_image_deg_cw_from_up"],
                 sun["elevation_deg"], pixel_scale=pixel_scale_m,
                 cast_shadows=cast_shadows, noise_std=0.0)
    record = {
        "dem": dict(dem.provenance),
        "window": {"line0": int(line0), "sample0": int(sample0),
                   "n_lines": int(n_lines), "n_samples": int(n_samples),
                   "decimation": int(decimation)},
        "pixel_scale_m": float(pixel_scale_m),
        "sun": sun,
        "shading": "Lambertian n.l with cast shadows, unit albedo, ambient 0.06, no noise",
        "height_stats_m": {"min": float(np.min(heights)), "max": float(np.max(heights)),
                           "ptp": float(np.ptp(heights))},
        "lon_lat_extent": [[float(lon.min()), float(lon.max())],
                           [float(lat.min()), float(lat.max())]],
        "shadow_fraction": float((img <= 0.06 + 1e-9).mean()),
    }
    return DemRender(image=img, heights_m=heights, record=record)
