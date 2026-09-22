"""Manifests: the overlap gate, corpus-class discipline, and round-trips."""

from __future__ import annotations

import json

import pytest

from siim.benchmark.manifest import (
    PairManifest,
    ProductManifest,
    load_pair_manifest,
    load_product_manifest,
)


def ohrc(**kw) -> ProductManifest:
    base = dict(
        product_id="ch2_ohr_ncp_20240425T1012478407_d_img_d18",
        instrument="OHRC",
        corpus_class="CHANDRAYAAN2",
        processing_level="calibrated",
        pixel_resolution_m=0.26,
        spacecraft_altitude_km=102.33,
        solar_incidence_deg=78.476392,
        sun_azimuth_deg=303.534993,
        sun_elevation_deg=11.523608,
        shape=(91945, 12000),
        data_type="UnsignedByte",
        corners_lat_lon=(
            (-69.074457, 32.194100), (-68.985942, 32.269512),
            (-69.903718, 32.352484), (-69.813625, 32.426454),
        ),
    )
    base.update(kw)
    return ProductManifest(**base)


def nac(**kw) -> ProductManifest:
    base = dict(
        product_id="nac.m1299958135lc",
        instrument="LRO_NAC",
        corpus_class="PROXY",
        pixel_resolution_m=0.5,
        solar_incidence_deg=70.0,
        corners_lat_lon=((-69.0, 32.2), (-69.0, 32.4),
                         (-69.9, 32.2), (-69.9, 32.4)),
    )
    base.update(kw)
    return ProductManifest(**base)


# -- corpus class has no default, and CHANDRAYAAN2 is reserved --------------

def test_corpus_class_must_be_one_of_the_known_values():
    with pytest.raises(ValueError, match="corpus_class"):
        ProductManifest(product_id="x", instrument="OHRC", corpus_class="real")


def test_chandrayaan2_corpus_class_rejects_a_non_chandrayaan2_instrument():
    """An LRO product must never be labelled as Chandrayaan-2 data."""
    with pytest.raises(ValueError, match="only OHRC, TMC-2 and IIRS"):
        ProductManifest(
            product_id="nac.x", instrument="LRO_NAC", corpus_class="CHANDRAYAAN2"
        )


def test_unknown_instrument_is_rejected():
    with pytest.raises(ValueError, match="instrument"):
        ProductManifest(product_id="x", instrument="HiRISE", corpus_class="PROXY")


def test_non_positive_pixel_resolution_is_rejected():
    with pytest.raises(ValueError, match="pixel_resolution_m"):
        ohrc(pixel_resolution_m=0.0)


# -- the overlap gate -------------------------------------------------------

def test_pair_is_not_runnable_until_overlap_is_confirmed():
    pair = PairManifest(
        pair_id="p", source=ohrc(), reference=nac(),
        corpus_class="CHANDRAYAAN2", ground_truth="NONE",
        overlap_status="UNKNOWN",
    )
    assert pair.runnable is False
    assert "has not been run" in pair.refusal_reason()


def test_not_confirmed_overlap_gives_a_distinct_reason_from_unknown():
    unknown = PairManifest(
        pair_id="p", source=ohrc(), reference=nac(),
        corpus_class="CHANDRAYAAN2", ground_truth="NONE",
        overlap_status="UNKNOWN",
    )
    denied = PairManifest(
        pair_id="p", source=ohrc(), reference=nac(),
        corpus_class="CHANDRAYAAN2", ground_truth="NONE",
        overlap_status="NOT_CONFIRMED",
    )
    assert unknown.refusal_reason() != denied.refusal_reason()
    assert "not established to share ground" in denied.refusal_reason()
    assert denied.runnable is False


def test_confirmed_overlap_is_runnable_and_has_no_refusal_reason():
    pair = PairManifest(
        pair_id="p", source=ohrc(), reference=nac(),
        corpus_class="CHANDRAYAAN2", ground_truth="NONE",
        overlap_status="CONFIRMED", overlap_fraction=0.82,
    )
    assert pair.runnable is True
    assert pair.refusal_reason() is None


# -- scale ratio must name its source --------------------------------------

def test_a_scale_ratio_must_name_where_it_came_from():
    """A nominal specification ratio and a measured one are different claims."""
    with pytest.raises(ValueError, match="must name its source"):
        PairManifest(
            pair_id="p", source=ohrc(), reference=nac(),
            corpus_class="CHANDRAYAAN2", ground_truth="NONE",
            scale_ratio=320.0,
        )


def test_measured_scale_ratio_comes_from_the_labels_not_the_declared_value():
    """0.26 m and 0.5 m are what the products report; 320 is a specification."""
    pair = PairManifest(
        pair_id="p", source=ohrc(), reference=nac(),
        corpus_class="CHANDRAYAAN2", ground_truth="NONE",
        scale_ratio=320.0, scale_ratio_source="NOMINAL",
    )
    assert pair.scale_ratio == 320.0
    assert pair.measured_scale_ratio() == pytest.approx(0.5 / 0.26)


def test_measured_scale_ratio_is_none_when_a_resolution_is_missing():
    pair = PairManifest(
        pair_id="p", source=ohrc(pixel_resolution_m=None), reference=nac(),
        corpus_class="CHANDRAYAAN2", ground_truth="NONE",
    )
    assert pair.measured_scale_ratio() is None


def test_measured_ratio_is_orientation_independent():
    a = PairManifest(pair_id="a", source=ohrc(), reference=nac(),
                     corpus_class="CHANDRAYAAN2", ground_truth="NONE")
    b = PairManifest(pair_id="b", source=nac(), reference=ohrc(),
                     corpus_class="CHANDRAYAAN2", ground_truth="NONE")
    assert a.measured_scale_ratio() == pytest.approx(b.measured_scale_ratio())


def test_pair_labelled_chandrayaan2_must_contain_a_chandrayaan2_product():
    with pytest.raises(ValueError, match="neither product is a Chandrayaan-2"):
        PairManifest(
            pair_id="p", source=nac(), reference=nac(product_id="nac.y"),
            corpus_class="CHANDRAYAAN2", ground_truth="NONE",
        )


# -- spans ------------------------------------------------------------------

def test_latitude_and_longitude_spans_are_read_from_the_corners():
    p = ohrc()
    lo, hi = p.latitude_span()
    assert lo == pytest.approx(-69.903718)
    assert hi == pytest.approx(-68.985942)
    lo, hi = p.longitude_span()
    assert lo == pytest.approx(32.194100)
    assert hi == pytest.approx(32.426454)


def test_spans_are_none_without_corner_geometry():
    p = ohrc(corners_lat_lon=None)
    assert p.latitude_span() is None
    assert p.longitude_span() is None


def test_megapixels_from_shape():
    assert ohrc().megapixels == pytest.approx(91945 * 12000 / 1e6)
    assert ohrc(shape=None).megapixels is None


# -- round-trips ------------------------------------------------------------

def test_product_round_trips_through_json(tmp_path):
    p = ohrc()
    path = tmp_path / "product.json"
    path.write_text(json.dumps(p.to_dict()), encoding="utf-8")
    back = load_product_manifest(path)
    assert back == p


def test_pair_round_trips_through_json(tmp_path):
    pair = PairManifest(
        pair_id="p", source=ohrc(), reference=nac(),
        corpus_class="CHANDRAYAAN2", ground_truth="CORROBORATION_ONLY",
        overlap_status="CONFIRMED", overlap_fraction=0.7,
        overlap_bounds=(0.66, 0.74), delta_incidence_deg=8.5,
        scale_ratio=1.92, scale_ratio_source="LABEL", tags=("polar",),
    )
    path = tmp_path / "pair.json"
    path.write_text(json.dumps(pair.to_dict()), encoding="utf-8")
    back = load_pair_manifest(path)
    assert back == pair


def test_serialised_pair_carries_the_gate_decision_for_readers():
    pair = PairManifest(
        pair_id="p", source=ohrc(), reference=nac(),
        corpus_class="CHANDRAYAAN2", ground_truth="NONE",
        overlap_status="NOT_CONFIRMED",
    )
    d = pair.to_dict()
    assert d["runnable"] is False
    assert d["refusal_reason"]
