"""Data generation and ingestion."""

from .synthetic_terrain import (
    ANGLE_OF_REPOSE_DEG,
    REFERENCE_BASELINE_M,
    SUN_HIGH,
    SUN_LOW,
    TERRAIN_REGIMES,
    SceneType,
    SyntheticPair,
    TerrainRegime,
    height_field,
    make_pair,
    normalise_slope,
    render,
    slope_statistics,
)

__all__ = [
    "SceneType",
    "SyntheticPair",
    "TerrainRegime",
    "TERRAIN_REGIMES",
    "height_field",
    "render",
    "make_pair",
    "slope_statistics",
    "normalise_slope",
    "SUN_LOW",
    "SUN_HIGH",
    "ANGLE_OF_REPOSE_DEG",
    "REFERENCE_BASELINE_M",
]
