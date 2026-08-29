"""The registered product and match points: two named PS deliverables.

The problem statement asks for four things -- software, a **registered
product**, **corresponding match points**, and evaluation metrics. The first
and last existed in this repository; the middle two did not.
``register_real_triplet.py --emit-product`` produces them for the one real edge
that passes the pre-registered inlier rule (D -> A, 1656 inliers).

**What these tests are guarding.** The product is emitted from *recorded*
evidence -- the transform from ``loop_closure_real_data_04.json``, the
correspondences from the certified overlay asset -- and **nothing is
estimated**. So the failure mode to guard against is not a wrong number; it is
the product silently drifting away from, or quietly re-deciding, what the stage
recorded. Specifically:

* the emitted match points must agree with the recorded inlier count;
* the mandated class-B statement must appear, identically, everywhere;
* ``warp``'s NaN fill must survive to the product -- on this data near-zero is
  a legal value, so a zero-filled border is indistinguishable from lunar
  shadow (E-003);
* no recorded artefact may change;
* no verdict criterion or threshold may change.

Tests requiring the emitted product **skip** when it is absent, and requiring
the tiles **skip** when those are absent, reporting "cannot check" rather than
passing (E-024).
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS = ROOT / "experiments" / "REAL-DATA-04" / "products"
CSV_PATH = PRODUCTS / "correspondences_D_A.csv"
PROV_PATH = PRODUCTS / "PRODUCT_PROVENANCE_D_A.json"
REGISTERED = PRODUCTS / "registered_D_A.png"
DIFFERENCE = PRODUCTS / "difference_D_A.png"

RECORDED = ROOT / "experiments" / "REAL-DATA-04" / "loop_closure_real_data_04.json"
EDGE = "nac.m1299958135lc -> nac.m1271742202lc"

_spec = importlib.util.spec_from_file_location(
    "_triplet", ROOT / "scripts" / "register_real_triplet.py")
_triplet = importlib.util.module_from_spec(_spec)
sys.modules["_triplet"] = _triplet
_spec.loader.exec_module(_triplet)


def _need(path: Path):
    if not path.exists():
        pytest.skip(
            f"CANNOT CHECK (not 'checked and fine'): {path.relative_to(ROOT)} "
            "is absent. Regenerate with `python scripts/register_real_triplet.py "
            "--emit-product --manifest real_quad_d_geo_manifest.json "
            "--outdir REAL-DATA-04 --overlap-artefact "
            "experiments/REAL-DATA-04/overlap_real_data_04.json`")


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    _need(CSV_PATH)
    with CSV_PATH.open(encoding="utf-8", newline="") as fh:
        data = [ln for ln in fh if not ln.lstrip('"').startswith("#")]
    return list(csv.DictReader(data))


@pytest.fixture(scope="module")
def prov() -> dict:
    _need(PROV_PATH)
    return json.loads(PROV_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def recorded_edge() -> dict:
    doc = json.loads(RECORDED.read_text(encoding="utf-8"))
    return next(e for e in doc["edges"] if e["edge"] == EDGE)


# ---------------------------------------------------------------------------
# CSV round-trip
# ---------------------------------------------------------------------------

def test_csv_round_trips(rows):
    """Every row parses, every column is present, every value is finite."""
    assert rows, "no data rows"
    expected = {"index", "is_inlier", "residual_px",
                "src_line", "src_sample", "src_lon_deg", "src_lat_deg",
                "dst_line", "dst_sample", "dst_lon_deg", "dst_lat_deg",
                "src_tile_x", "src_tile_y", "dst_tile_x", "dst_tile_y"}
    assert set(rows[0]) == expected
    for i, r in enumerate(rows):
        assert int(r["index"]) == i, "index column is not a contiguous 0-based key"
        assert r["is_inlier"] in ("0", "1")
        for col in expected - {"index", "is_inlier"}:
            assert np.isfinite(float(r[col])), f"row {i} column {col} is not finite"


def test_csv_row_count_matches_the_recorded_putative_count(rows, recorded_edge):
    assert len(rows) == recorded_edge["n_putative_mutual_ratio_matches"] == 1759


def test_csv_inlier_count_matches_the_recorded_artefact(rows, recorded_edge):
    """The one number that must never drift: the stage's inlier count."""
    assert sum(int(r["is_inlier"]) for r in rows) == recorded_edge["n_inliers"] == 1656


# ---------------------------------------------------------------------------
# Correspondence integrity
# ---------------------------------------------------------------------------

def test_pixel_coordinates_lie_inside_their_own_tile_windows(rows):
    """Full-frame coordinates must fall inside the window each tile was cut at.

    Catches the class of defect that produced E-025 and E-030: a coordinate
    computed against the wrong window still looks like a plausible number.
    """
    man = json.loads((ROOT / "data" / "manifests"
                      / "real_quad_d_geo_manifest.json").read_text(encoding="utf-8"))
    t = {x["pdsid"]: x for x in man["tiles"]}
    src, dst = EDGE.split(" -> ")
    for r in rows:
        for pid, pre in ((src, "src"), (dst, "dst")):
            w = t[pid]
            assert w["line0"] <= float(r[f"{pre}_line"]) <= w["line0"] + w["n_lines"]
            assert w["sample0"] <= float(r[f"{pre}_sample"]) <= w["sample0"] + w["n_samples"]


def test_ground_coordinates_are_near_the_stage_target(rows):
    """A sanity bound, not an accuracy claim.

    Every tile in REAL-DATA-04 is centred on one ground point, and a 4096x2048
    tile spans well under a degree. Coordinates far from that target would mean
    the wrong corners, the wrong window, or the wrong frame.
    """
    man = json.loads((ROOT / "data" / "manifests"
                      / "real_quad_d_geo_manifest.json").read_text(encoding="utf-8"))
    lon_t, lat_t = man["target_ground_point_lon_lat"]
    for r in rows:
        for pre in ("src", "dst"):
            assert abs(float(r[f"{pre}_lon_deg"]) - lon_t) < 0.5
            assert abs(float(r[f"{pre}_lat_deg"]) - lat_t) < 0.5


def test_inliers_have_small_residuals_and_outliers_do_not(rows, recorded_edge):
    """The residual column must actually correspond to the inlier flag.

    Every inlier is inside the recorded RANSAC threshold; the flagged outliers
    are not. This is a consistency check on the CSV, **not** an accuracy
    measurement -- these are FIT residuals (D-003).
    """
    doc = json.loads(RECORDED.read_text(encoding="utf-8"))
    threshold = float(doc["baseline"]["ransac_threshold_px"])
    inl = [float(r["residual_px"]) for r in rows if r["is_inlier"] == "1"]
    out = [float(r["residual_px"]) for r in rows if r["is_inlier"] == "0"]
    assert inl and out
    assert max(inl) <= threshold, (
        f"an inlier has residual {max(inl):.3f} px above the recorded "
        f"threshold {threshold}; the flag and the residual disagree")
    assert min(out) > threshold


def test_the_residual_is_named_a_fit_residual_not_an_accuracy():
    """D-003. The column must carry its own disqualification."""
    header = CSV_PATH.read_text(encoding="utf-8") if CSV_PATH.exists() else ""
    _need(CSV_PATH)
    assert "FIT residual, not an accuracy" in header


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def test_the_mandated_class_statement_appears_identically_everywhere(prov):
    """One constant, three places. A claim restated by hand drifts."""
    statement = _triplet.PRODUCT_CLASS_STATEMENT
    assert statement == ("a registered product; no ground truth exists for it; "
                         "corroborated, not verified; class B.")
    assert prov["product_class"] == statement
    assert statement in CSV_PATH.read_text(encoding="utf-8")


def test_provenance_states_what_the_product_is_not(prov):
    joined = " ".join(prov["what_this_is_NOT"])
    assert "NOT evidence that the registration is correct" in joined
    assert "no ground truth exists" in joined.lower()
    assert "NOT a registration error map" in joined, (
        "the difference image must be disclaimed: the two frames differ by "
        "11.73 deg of incidence, so radiometric difference is expected")
    assert "NOT Chandrayaan-2" in joined


def test_provenance_records_that_nothing_was_estimated(prov):
    assert "No matcher ran" in prov["nothing_was_estimated_here"]


def test_provenance_statistics_equal_the_recorded_artefact(prov, recorded_edge):
    """The product may not carry a statistic that disagrees with the stage."""
    for key, value in prov["recorded_statistics"].items():
        assert value == recorded_edge[key], f"{key} disagrees with the artefact"
    assert prov["transform_matrix"] == recorded_edge["transform_matrix"]


def test_provenance_names_and_hashes_its_sources(prov):
    for path, digest in prov["source_sha256"].items():
        p = ROOT / path
        assert p.exists(), f"provenance names {path}, which is not on disk"
        assert len(digest) == 64
        assert _triplet._sha256(p) == digest, (
            f"{path} has changed since the product was emitted; the product is "
            "stale and must be regenerated rather than trusted")


def test_the_saturated_coverage_check_is_not_counted_as_a_confirmation(prov):
    """E-027's lesson, applied to a check this script itself adds.

    The warp coverage and the archive-geometry coverage both saturate at 1.0 on
    this edge, so no disagreement was possible and the agreement confirms
    nothing. That must be stated, not counted.
    """
    cc = prov["coverage_cross_check"]
    if not cc.get("available"):
        pytest.skip("no overlap artefact was supplied when the product was emitted")
    assert "discriminating_power" in cc
    if min(cc["warp_valid_fraction"],
           cc["archive_geometry_fraction_of_reference_tile"]) > 0.999:
        assert "NONE on this edge" in cc["discriminating_power"]


# ---------------------------------------------------------------------------
# warp NaN border -- near-zero is a legal lunar value (E-003)
# ---------------------------------------------------------------------------

def test_warp_fills_outside_the_source_with_nan_not_zero():
    """The property the product depends on, tested directly on `warp`.

    A zero-filled border is indistinguishable from genuine lunar shadow, which
    is exactly E-003. This uses a transform that provably pushes part of the
    output outside the source, so the no-data region certainly exists.
    """
    from siim.geometry import translation, warp
    img = np.full((64, 64), 0.5)
    warped, valid = warp(img, translation(20.0, 12.0), out_shape=(64, 64))
    assert not valid.all(), "the transform must leave part of the output outside"
    assert np.isnan(warped[~valid]).all(), (
        "outside-source pixels are not NaN; a zero fill here is "
        "indistinguishable from lunar shadow (E-003)")
    assert np.isfinite(warped[valid]).all()


def test_the_emitted_product_preserved_the_nan_convention(prov):
    """And the product records the no-data convention it used."""
    assert prov["nodata_rgb"] if "nodata_rgb" in prov else True
    assert "Zero-fill is not used" in prov["nodata_convention"]
    assert prov["registered_image"]["nodata_rgb"] == [255, 0, 255]


def test_the_registered_product_covers_the_reference_grid_as_geometry_predicts(prov):
    """On THIS edge the reference tile lies wholly inside the source footprint.

    ``fraction_of_a`` is 1.0000 in the recorded overlap artefact -- measured
    from archive corners with no pixel read -- so a warp with zero no-data
    pixels is the geometrically correct outcome here, not a lost NaN mask.
    Asserted against the artefact rather than against the observed value.
    """
    ov = json.loads((ROOT / "experiments" / "REAL-DATA-04"
                     / "overlap_real_data_04.json").read_text(encoding="utf-8"))
    case = next(c for c in ov["cases"]
                if set(c["products"]) == set(EDGE.split(" -> ")))
    src, dst = EDGE.split(" -> ")
    key = "fraction_of_a" if case["products"][0] == dst else "fraction_of_b"
    assert prov["registered_image"]["valid_fraction"] == pytest.approx(
        case["primary"][key], abs=1e-9)


def test_registered_and_difference_images_have_the_reference_grid_shape(prov):
    doc = json.loads(RECORDED.read_text(encoding="utf-8"))
    assert prov["registered_image"]["shape_rows_cols"] == doc["shape_after_decimation"]
    assert prov["difference_image"]["shape_rows_cols"] == doc["shape_after_decimation"]


def test_the_png_files_exist_and_decode_at_the_stated_size(prov):
    _need(REGISTERED)
    _need(DIFFERENCE)
    from PIL import Image
    rows, cols = prov["registered_image"]["shape_rows_cols"]
    for path in (REGISTERED, DIFFERENCE):
        with Image.open(path) as im:
            assert im.size == (cols, rows), f"{path.name} is {im.size}"
            assert im.mode == "RGB", (
                f"{path.name} is {im.mode}; RGB is required so the no-data "
                "colour cannot be confused with a grey level")


# ---------------------------------------------------------------------------
# Nothing else moved
# ---------------------------------------------------------------------------

def test_emitting_a_product_changes_no_verdict_criterion_or_threshold():
    """The frozen constants, asserted from their declaration sites."""
    from siim.demo.verdict import (COVERAGE_GAP_WARN, INLIER_CUTOFF,
                                   LOOP_ERROR_REJECT_PX)
    assert INLIER_CUTOFF == 8
    assert COVERAGE_GAP_WARN == 0.15
    assert LOOP_ERROR_REJECT_PX == 2.0
    assert _triplet.N_INLIERS_FAILURE_RULE == 8
    assert _triplet.RANSAC_THRESHOLD_PX == 3.0
    assert _triplet.SEED == 0


def test_the_emit_path_never_writes_outside_the_products_directory():
    """Read the source: the only writes are into experiments/<outdir>/products/."""
    src = (ROOT / "scripts" / "register_real_triplet.py").read_text(encoding="utf-8")
    body = src.split("def emit_product(")[1].split("\ndef ")[0]
    for token in ("write_text", "savefig", ".save("):
        for line in body.splitlines():
            if token in line:
                assert "paths[" in line, (
                    f"emit_product writes via {token!r} outside paths[]: {line.strip()}")


def test_a_rejected_edge_gets_no_registered_product():
    """A product implies the registration was accepted.

    Emitting one for an edge the pre-registered rule REJECTED would contradict
    the verdict displayed beside it. B -> D has 3 inliers and must be refused.
    """
    src = (ROOT / "scripts" / "register_real_triplet.py").read_text(encoding="utf-8")
    assert "No registered product is emitted for a rejected edge." in src
    doc = json.loads(RECORDED.read_text(encoding="utf-8"))
    bd = next(e for e in doc["edges"]
              if e["edge"] == "nac.m1335207975rc -> nac.m1299958135lc")
    assert bd["n_inliers_failure_flag"] is True


def test_out_of_unit_range_values_are_explained_not_hidden(prov):
    """Cubic resampling overshoots; the product says so rather than clipping.

    The registered image's true valid range runs slightly outside [0, 1]
    because `warp` uses an order-3 spline, which rings at crater rims and
    shadow edges. The reported min/max are the TRUE resampled values -- only
    the PNG render clips -- and an unexplained negative reflectance in a
    delivered product is exactly the kind of number that draws a question we
    should already have answered.
    """
    reg = prov["registered_image"]
    assert "why_values_can_fall_outside_0_1" in reg
    assert "cubic spline" in reg["why_values_can_fall_outside_0_1"]
    assert "NOT a defect" in reg["why_values_can_fall_outside_0_1"]
    assert reg["out_of_unit_range_fraction"] is not None
    assert reg["out_of_unit_range_fraction"] < 0.05, (
        f"{reg['out_of_unit_range_fraction']:.3f} of valid pixels fall outside "
        "[0, 1]; that is far more than interpolator overshoot and needs a "
        "different explanation than the one recorded")
