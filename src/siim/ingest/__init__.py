"""Real-data ingestion."""

from .lro_nac import (
    NacProduct,
    fetch_byte_range,
    fetch_image_tile,
    fetch_image_window,
    fetch_label,
    find_illumination_pairs,
    observational_label_url,
    query_nac,
    write_manifest,
)
from .sanity import (
    TileChecks,
    byte_order_evidence,
    check_tile,
    lag1_autocorrelation,
)
from .footprint import (
    OVERLAP_CONFIRMED,
    OVERLAP_INSUFFICIENT,
    OVERLAP_UNKNOWN,
    FrameCorners,
    LocalPlane,
    OverlapMetrics,
    classify_overlap,
    convex_clip,
    overlap_metrics,
    polygon_area_km2,
)
from .solar_geometry import (
    SolarGeometry,
    angular_difference_deg,
    incidence_agreement,
    solar_geometry_at,
)
from .index_table import (
    IndexRowNotFound,
    IndexTableSpec,
    find_row_by_product_id,
    parse_index_label,
)
from .pds4 import (
    PDS4_DATA_TYPES,
    Pds4ImageStructure,
    Pds4LabelError,
    decode_tile,
    detect_product_type,
    parse_display_direction,
    parse_image_structure,
    plan_tile_byte_range,
    summarise_label,
    validate_structure,
)

__all__ = [
    "NacProduct",
    "query_nac",
    "find_illumination_pairs",
    "observational_label_url",
    "fetch_label",
    "fetch_byte_range",
    "fetch_image_tile",
    "fetch_image_window",
    "write_manifest",
    "PDS4_DATA_TYPES",
    "Pds4ImageStructure",
    "Pds4LabelError",
    "detect_product_type",
    "parse_image_structure",
    "validate_structure",
    "plan_tile_byte_range",
    "decode_tile",
    "summarise_label",
    "TileChecks",
    "check_tile",
    "lag1_autocorrelation",
    "byte_order_evidence",
    "parse_display_direction",
    # REAL-DATA-02: overlap geometry, independent of the matcher
    "FrameCorners",
    "LocalPlane",
    "OverlapMetrics",
    "polygon_area_km2",
    "convex_clip",
    "overlap_metrics",
    "classify_overlap",
    "OVERLAP_CONFIRMED",
    "OVERLAP_INSUFFICIENT",
    "OVERLAP_UNKNOWN",
    "IndexTableSpec",
    "IndexRowNotFound",
    "parse_index_label",
    "find_row_by_product_id",
    # Pre-freeze audit (2026-08-29): illumination geometry at a ground point,
    # for the Dazimuth confound check on D-040. Not pre-registered; applied
    # after the decision, and may not change one.
    "SolarGeometry",
    "solar_geometry_at",
    "angular_difference_deg",
    "incidence_agreement",
]
