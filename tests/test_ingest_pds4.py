"""PDS4 label parsing and byte-range tile decoding.

The failures these pin down are the ones that do **not** announce themselves:
a browse label that parses cleanly, an offset that shifts every row by most of
a line, a byte-order flip that turns terrain into noise, a truncated range
response whose tail reads as lunar shadow. Every test here asserts on a
specific wrong outcome, not merely that the code runs.

A synthetic PDS4 label is built from a template so that offset, dimensions,
data type and axis order can each be corrupted independently.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from siim.ingest.lro_nac import _parse_product
from siim.ingest.pds4 import (
    PDS4_DATA_TYPES,
    Pds4LabelError,
    decode_tile,
    detect_product_type,
    parse_display_direction,
    parse_image_structure,
    plan_tile_byte_range,
    summarise_label,
    validate_structure,
)

NS = 'xmlns="http://pds.nasa.gov/pds4/pds/v1"'


def make_label(
    *,
    lines: int = 8,
    samples: int = 5,
    offset: int = 64,
    data_type: str = "SignedLSB2",
    itemsize: int = 2,
    file_size: int | None = None,
    axis_order: tuple[str, str] = ("Line", "Sample"),
    index_order: str = "Last Index Fastest",
    root: str = "Product_Observational",
    n_axes: int = 2,
    with_special: bool = True,
    with_array: bool = True,
    with_offset: bool = True,
) -> str:
    """A minimal but structurally faithful PDS4 label, corruptible per-field.

    Mirrors the real NAC CDR shape: a ``Header`` with its own ``offset`` of 0
    (so a parser that greps for the first ``<offset>`` reads the wrong one),
    then the ``Array_2D_Image``.
    """
    if file_size is None:
        file_size = offset + lines * samples * itemsize
    special = """
      <Special_Constants>
        <missing_constant>-32768</missing_constant>
        <low_instrument_saturation>-32766</low_instrument_saturation>
        <valid_minimum>-32752</valid_minimum>
      </Special_Constants>""" if with_special else ""
    off = f"<offset unit=\"byte\">{offset}</offset>" if with_offset else ""
    array = f"""
    <Array_2D_Image>
      <local_identifier>Array_2D_Image</local_identifier>
      {off}
      <axes>{n_axes}</axes>
      <axis_index_order>{index_order}</axis_index_order>
      <Element_Array>
        <data_type>{data_type}</data_type>
        <unit>Scaled I/F</unit>
        <scaling_factor>2.0</scaling_factor>
      </Element_Array>
      <Axis_Array>
        <axis_name>{axis_order[0]}</axis_name>
        <elements>{lines}</elements>
        <sequence_number>1</sequence_number>
      </Axis_Array>
      <Axis_Array>
        <axis_name>{axis_order[1]}</axis_name>
        <elements>{samples}</elements>
        <sequence_number>2</sequence_number>
      </Axis_Array>{special}
    </Array_2D_Image>""" if with_array else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<{root} {NS}>
  <Identification_Area><logical_identifier>urn:test</logical_identifier></Identification_Area>
  <File_Area_Observational>
    <File>
      <file_name>TEST.IMG</file_name>
      <file_size unit="byte">{file_size}</file_size>
      <md5_checksum>deadbeef</md5_checksum>
    </File>
    <Header>
      <offset unit="byte">0</offset>
      <object_length unit="byte">{offset}</object_length>
      <parsing_standard_id>PDS3</parsing_standard_id>
    </Header>{array}
  </File_Area_Observational>
</{root}>
"""


def make_bytes(lines: int, samples: int, offset: int, dtype: str = "<i2") -> bytes:
    """A file whose every pixel encodes its own (line, sample).

    ``value = line * 1000 + sample`` makes offset, stride, transposition and
    byte-order errors each produce a *distinct, identifiable* wrong answer
    rather than merely different noise.
    """
    img = (np.arange(lines)[:, None] * 1000 + np.arange(samples)[None, :])
    return b"\xAB" * offset + img.astype(np.dtype(dtype)).tobytes()


# --------------------------------------------------------------------------
# product type detection and browse rejection
# --------------------------------------------------------------------------

def test_detects_observational_and_browse_root_elements():
    assert detect_product_type(make_label()) == "Product_Observational"
    assert detect_product_type(make_label(root="Product_Browse")) == "Product_Browse"


def test_browse_label_is_rejected_not_parsed():
    """E-022. A browse label is well-formed XML served from the same host with
    the same extension. Only the root element distinguishes it."""
    browse = make_label(root="Product_Browse")
    with pytest.raises(Pds4LabelError, match="Product_Browse"):
        parse_image_structure(browse)


def test_browse_label_can_be_summarised_without_raising():
    s = summarise_label(make_label(root="Product_Browse"))
    assert s["product_type"] == "Product_Browse"
    assert s["image_structure"] is None


def test_malformed_xml_raises_label_error_not_parse_error():
    with pytest.raises(Pds4LabelError, match="well-formed"):
        detect_product_type("<Product_Observational><unclosed>")


# --------------------------------------------------------------------------
# structure parsing
# --------------------------------------------------------------------------

def test_parses_the_real_nac_structure():
    s = parse_image_structure(make_label(lines=52224, samples=5064, offset=5064))
    assert (s.lines, s.samples) == (52224, 5064)
    assert s.offset_bytes == 5064
    assert s.numpy_dtype == "<i2"
    assert s.itemsize == 2
    assert s.line_stride_bytes == 5064 * 2
    assert s.expected_file_bytes == 5064 + 52224 * 5064 * 2 == 528929736
    assert s.shape == (52224, 5064)


def test_signed_lsb2_maps_to_signed_16_bit_little_endian_explicitly():
    """Byte order is never inferred. SignedLSB2 and SignedMSB2 differ only in
    the last letter and would be one typo apart under any name-munging rule."""
    assert PDS4_DATA_TYPES["SignedLSB2"] == "<i2"
    assert PDS4_DATA_TYPES["SignedMSB2"] == ">i2"
    assert np.dtype(PDS4_DATA_TYPES["SignedLSB2"]).byteorder in ("<", "=")
    assert np.dtype(PDS4_DATA_TYPES["SignedLSB2"]).itemsize == 2


def test_offset_is_read_from_the_array_not_the_header():
    """The Header element carries its own <offset>0</offset>. Reading that one
    would start the array at byte 0 of a file whose data begins at 5064,
    displacing every row by most of a line -- and still looking like terrain."""
    s = parse_image_structure(make_label(offset=5064))
    assert s.offset_bytes == 5064


def test_unknown_data_type_raises_rather_than_guessing():
    with pytest.raises(Pds4LabelError, match="unsupported PDS4 data_type"):
        parse_image_structure(make_label(data_type="ComplexLSB16"))


def test_missing_offset_is_not_defaulted_to_zero():
    with pytest.raises(Pds4LabelError, match="offset"):
        parse_image_structure(make_label(with_offset=False))


def test_missing_array_2d_image_raises():
    with pytest.raises(Pds4LabelError, match="no Array_2D_Image"):
        parse_image_structure(make_label(with_array=False))


def test_transposed_axis_order_is_rejected():
    """A transposed read is geometrically wrong while being statistically
    indistinguishable from the correct one."""
    with pytest.raises(Pds4LabelError, match="Line, Sample"):
        parse_image_structure(make_label(axis_order=("Sample", "Line")))


def test_column_major_index_order_is_rejected_not_assumed():
    with pytest.raises(Pds4LabelError, match="axis_index_order"):
        parse_image_structure(make_label(index_order="First Index Fastest"))


def test_non_2d_array_is_rejected():
    with pytest.raises(Pds4LabelError, match="axes"):
        parse_image_structure(make_label(n_axes=3))


# --------------------------------------------------------------------------
# the file_size identity -- validates offset, dims and itemsize together
# --------------------------------------------------------------------------

def test_file_size_identity_passes_on_a_consistent_label():
    checks = validate_structure(parse_image_structure(make_label()))
    assert any("file_size identity" in c for c in checks)


@pytest.mark.parametrize("bad_offset", [0, 63, 65, 5064])
def test_file_size_identity_catches_a_wrong_offset(bad_offset):
    """file_size is declared independently of the array description, so the
    identity offset + lines*samples*itemsize == file_size fails if any one of
    them is wrong. This is the single strongest structural check available."""
    good = 64
    if bad_offset == good:
        pytest.skip("not a corruption")
    lbl = make_label(offset=bad_offset, file_size=good + 8 * 5 * 2)
    with pytest.raises(Pds4LabelError, match="internally inconsistent"):
        validate_structure(parse_image_structure(lbl))


def test_file_size_identity_catches_a_wrong_element_size():
    """A label claiming 1-byte elements for a file sized as 2-byte elements."""
    lbl = make_label(data_type="UnsignedByte", itemsize=2)  # file_size from itemsize=2
    with pytest.raises(Pds4LabelError, match="internally inconsistent"):
        validate_structure(parse_image_structure(lbl))


# --------------------------------------------------------------------------
# byte-range planning: offset + stride arithmetic
# --------------------------------------------------------------------------

def test_byte_range_starts_at_offset_for_the_first_line():
    s = parse_image_structure(make_label(lines=8, samples=5, offset=64))
    start, count = plan_tile_byte_range(s, line0=0, n_lines=1)
    assert start == 64
    assert count == 5 * 2


def test_byte_range_advances_by_one_full_line_stride():
    s = parse_image_structure(make_label(lines=8, samples=5, offset=64))
    a, _ = plan_tile_byte_range(s, line0=0, n_lines=1)
    b, _ = plan_tile_byte_range(s, line0=1, n_lines=1)
    assert b - a == s.line_stride_bytes == 10


def test_byte_range_on_the_real_nac_geometry():
    """offset 5064, Sample 5064, SignedLSB2 -> stride 10128 B/line."""
    s = parse_image_structure(make_label(lines=52224, samples=5064, offset=5064))
    start, count = plan_tile_byte_range(s, line0=24000, n_lines=2048)
    assert s.line_stride_bytes == 10128
    assert start == 5064 + 24000 * 10128 == 243077064
    assert count == 2048 * 10128 == 20742144


def test_byte_range_refuses_to_run_past_the_last_line():
    s = parse_image_structure(make_label(lines=8, samples=5))
    with pytest.raises(ValueError, match="exceed"):
        plan_tile_byte_range(s, line0=7, n_lines=2)


@pytest.mark.parametrize("line0,n_lines", [(-1, 2), (0, 0), (0, -3)])
def test_byte_range_rejects_invalid_windows(line0, n_lines):
    s = parse_image_structure(make_label(lines=8, samples=5))
    with pytest.raises(ValueError):
        plan_tile_byte_range(s, line0=line0, n_lines=n_lines)


# --------------------------------------------------------------------------
# decoding a synthetic PDS4 byte stream
# --------------------------------------------------------------------------

def test_decodes_a_synthetic_stream_at_the_right_offset_and_stride():
    lines, samples, offset = 8, 5, 64
    s = parse_image_structure(make_label(lines=lines, samples=samples, offset=offset))
    blob = make_bytes(lines, samples, offset)
    start, count = plan_tile_byte_range(s, line0=2, n_lines=3)
    img = decode_tile(blob[start:start + count], s, n_lines=3,
                      mask_special_constants=False)
    assert img.shape == (3, samples)
    # value == line*1000 + sample, so row 0 of the tile must be source line 2
    assert img[0, 0] == 2000
    assert img[2, 4] == 4004


def test_decode_is_row_line_column_sample_not_transposed():
    s = parse_image_structure(make_label(lines=8, samples=5, offset=64))
    blob = make_bytes(8, 5, 64)
    start, count = plan_tile_byte_range(s, line0=0, n_lines=8)
    img = decode_tile(blob[start:start + count], s, n_lines=8,
                      mask_special_constants=False)
    assert img.shape == (8, 5)             # (rows=lines, cols=samples)
    assert img[3, 1] == 3001               # row is the line, column is the sample
    assert img[1, 3] == 1003               # and not the other way round


def test_sample_window_selects_columns_after_decoding():
    s = parse_image_structure(make_label(lines=8, samples=5, offset=64))
    blob = make_bytes(8, 5, 64)
    start, count = plan_tile_byte_range(s, line0=0, n_lines=2)
    img = decode_tile(blob[start:start + count], s, n_lines=2,
                      sample0=2, n_samples=2, mask_special_constants=False)
    assert img.shape == (2, 2)
    assert img[0, 0] == 2 and img[1, 1] == 1003


def test_sample_window_out_of_bounds_raises():
    s = parse_image_structure(make_label(lines=8, samples=5, offset=64))
    blob = make_bytes(8, 5, 64)
    start, count = plan_tile_byte_range(s, line0=0, n_lines=1)
    with pytest.raises(ValueError, match="outside"):
        decode_tile(blob[start:start + count], s, n_lines=1, sample0=4, n_samples=3)


def test_wrong_offset_produces_visibly_wrong_values():
    """Not a code path -- a demonstration that an offset error is silent at the
    array level. Decoding one byte early shifts every sample by half an element
    and yields values that are still finite, still int16, still 'an image'."""
    s = parse_image_structure(make_label(lines=8, samples=5, offset=64))
    blob = make_bytes(8, 5, 64)
    good = decode_tile(blob[64:64 + 10], s, n_lines=1, mask_special_constants=False)
    bad = decode_tile(blob[63:63 + 10], s, n_lines=1, mask_special_constants=False)
    assert good[0, 0] == 0
    assert bad[0, 0] != good[0, 0]
    assert np.isfinite(bad).all()          # nothing about `bad` looks wrong


def test_endianness_flip_changes_every_value():
    """SignedMSB2 over little-endian bytes: the decode succeeds and the numbers
    are garbage. This is why the dtype table is explicit."""
    s_le = parse_image_structure(make_label(lines=4, samples=4, offset=0))
    s_be = parse_image_structure(
        make_label(lines=4, samples=4, offset=0, data_type="SignedMSB2"))
    blob = make_bytes(4, 4, 0, dtype="<i2")
    le = decode_tile(blob, s_le, n_lines=4, mask_special_constants=False)
    be = decode_tile(blob, s_be, n_lines=4, mask_special_constants=False)
    assert le[1, 1] == 1001
    assert be[1, 1] != 1001
    assert not np.array_equal(le, be)


# --------------------------------------------------------------------------
# truncation: the failure that reads as lunar shadow
# --------------------------------------------------------------------------

def test_short_buffer_raises_and_is_never_padded():
    s = parse_image_structure(make_label(lines=8, samples=5, offset=64))
    blob = make_bytes(8, 5, 64)
    start, count = plan_tile_byte_range(s, line0=0, n_lines=4)
    truncated = blob[start:start + count - 6]
    with pytest.raises(ValueError, match="truncated range fetch"):
        decode_tile(truncated, s, n_lines=4)


def test_over_long_buffer_also_raises():
    """Too many bytes means the window was not the one that was planned."""
    s = parse_image_structure(make_label(lines=8, samples=5, offset=64))
    blob = make_bytes(8, 5, 64)
    start, count = plan_tile_byte_range(s, line0=0, n_lines=2)
    with pytest.raises(ValueError, match="expected exactly"):
        decode_tile(blob[start:start + count + 10], s, n_lines=2)


# --------------------------------------------------------------------------
# special constants
# --------------------------------------------------------------------------

def test_sentinels_are_masked_to_nan():
    s = parse_image_structure(make_label(lines=2, samples=3, offset=0))
    raw = np.array([[-32768, 5, 6], [7, -32766, 9]], dtype="<i2").tobytes()
    out = decode_tile(raw, s, n_lines=2, mask_special_constants=True)
    assert np.isnan(out[0, 0]) and np.isnan(out[1, 1])
    assert out[0, 1] == 5


def test_valid_minimum_is_a_bound_and_is_never_masked():
    """valid_minimum (-32752) is the bottom of the legal range, not a sentinel.
    Masking it by equality would delete the darkest legitimate pixels -- the
    shadowed terrain this project cares about most (E-003)."""
    s = parse_image_structure(make_label(lines=1, samples=2, offset=0))
    assert -32752 not in s.sentinel_values
    raw = np.array([[-32752, 4]], dtype="<i2").tobytes()
    out = decode_tile(raw, s, n_lines=1, mask_special_constants=True)
    assert out[0, 0] == -32752
    assert not np.isnan(out[0, 0])


def test_scaling_factor_is_off_by_default_and_exact_when_applied():
    s = parse_image_structure(make_label(lines=1, samples=2, offset=0))
    raw = np.array([[10, 20]], dtype="<i2").tobytes()
    plain = decode_tile(raw, s, n_lines=1, mask_special_constants=False)
    scaled = decode_tile(raw, s, n_lines=1, mask_special_constants=False,
                         apply_scaling=True)
    assert plain[0, 0] == 10
    assert scaled[0, 0] == 20.0  # scaling_factor 2.0 in the template


# --------------------------------------------------------------------------
# ODE label selection -- E-022 regression
# --------------------------------------------------------------------------

def _ode_record(files):
    return {"pdsid": "nac.test", "Product_files": {"Product_file": files}}


def test_ode_product_label_wins_over_browse_label_listed_after_it():
    """E-022. ODE lists Browse AFTER Product; extension matching with
    unconditional assignment therefore picked the browse label for every
    product that had a browse pyramid -- 4 of 6 acquired products."""
    p = _parse_product(_ode_record([
        {"Type": "Product", "URL": "https://h/DATA/ESM3/2019248/NAC/M1.IMG",
         "KBytes": "504001"},
        {"Type": "Product", "URL": "https://h/DATA/ESM3/2019248/NAC/M1.xml",
         "KBytes": "13"},
        {"Type": "Browse", "URL": "https://h/EXTRAS/BROWSE/2019248/M1_pyr.xml",
         "KBytes": "2"},
    ]))
    assert p.label_url.endswith("/DATA/ESM3/2019248/NAC/M1.xml")
    assert p.browse_label_url.endswith("_pyr.xml")
    assert p.image_url.endswith("M1.IMG")


def test_ode_label_selection_is_independent_of_file_order():
    files = [
        {"Type": "Browse", "URL": "https://h/EXTRAS/BROWSE/2019248/M1_pyr.xml"},
        {"Type": "Product", "URL": "https://h/DATA/ESM3/2019248/NAC/M1.xml"},
        {"Type": "Product", "URL": "https://h/DATA/ESM3/2019248/NAC/M1.IMG"},
    ]
    for order in (files, list(reversed(files))):
        p = _parse_product(_ode_record(order))
        assert p.label_url.endswith("/NAC/M1.xml"), order


def test_untyped_records_never_select_a_browse_path_label():
    """Defensive: if ODE ever stops sending Type, the extension fallback must
    still refuse anything under EXTRAS/BROWSE/."""
    p = _parse_product(_ode_record([
        {"URL": "https://h/EXTRAS/BROWSE/2019248/M1_pyr.xml"},
        {"URL": "https://h/DATA/ESM3/2019248/NAC/M1.xml"},
        {"URL": "https://h/DATA/ESM3/2019248/NAC/M1.IMG"},
    ]))
    assert p.label_url.endswith("/NAC/M1.xml")


def test_observational_label_url_refuses_to_synthesise_from_a_browse_url():
    """The DATA/<phase>/ segment (ESM2, ESM3, ESM4, SCI, MAP) is not
    recoverable from the browse path, so no URL is ever constructed."""
    from siim.ingest.lro_nac import observational_label_url
    p = _parse_product(_ode_record([
        {"Type": "Browse", "URL": "https://h/EXTRAS/BROWSE/2019248/M1_pyr.xml"},
        {"Type": "Product", "URL": "https://h/DATA/ESM3/2019248/NAC/M1.IMG"},
    ]))
    assert p.label_url is None
    with pytest.raises(ValueError, match="not derivable"):
        observational_label_url(p)


# --------------------------------------------------------------------------
# display direction -- what "upper" and "left" mean for this product
# --------------------------------------------------------------------------

DISPLAY_BLOCK = """
    <Discipline_Area>
      <disp:Display_Settings xmlns:disp="http://pds.nasa.gov/pds4/disp/v1">
        <disp:Display_Direction>
          <disp:horizontal_display_axis>{h_axis}</disp:horizontal_display_axis>
          <disp:horizontal_display_direction>{h_dir}</disp:horizontal_display_direction>
          <disp:vertical_display_axis>{v_axis}</disp:vertical_display_axis>
          <disp:vertical_display_direction>{v_dir}</disp:vertical_display_direction>
        </disp:Display_Direction>
      </disp:Display_Settings>
    </Discipline_Area>"""


def label_with_display(h_axis="Sample", h_dir="Left to Right",
                       v_axis="Line", v_dir="Top to Bottom",
                       *, omit: str | None = None) -> str:
    block = DISPLAY_BLOCK.format(h_axis=h_axis, h_dir=h_dir,
                                 v_axis=v_axis, v_dir=v_dir)
    if omit:
        block = "\n".join(l for l in block.splitlines() if omit not in l)
    return make_label().replace("<File_Area_Observational>",
                                block + "\n  <File_Area_Observational>")


def test_display_direction_states_which_line_is_at_the_top():
    """This is what makes the archive index table's UPPER_*/LOWER_* corner
    columns mean something: without it, 'upper' is a guess, and guessing wrong
    mirrors a tile along-track by up to a whole frame."""
    d = parse_display_direction(label_with_display())
    assert d == {
        "horizontal_axis": "Sample",
        "horizontal_direction": "Left to Right",
        "vertical_axis": "Line",
        "vertical_direction": "Top to Bottom",
    }


def test_a_bottom_to_top_label_is_reported_as_such_and_not_normalised():
    d = parse_display_direction(label_with_display(v_dir="Bottom to Top"))
    assert d["vertical_direction"] == "Bottom to Top"


def test_a_label_without_display_direction_raises_rather_than_defaulting():
    with pytest.raises(Pds4LabelError, match="no disp:Display_Direction"):
        parse_display_direction(make_label())


def test_an_incomplete_display_direction_names_what_is_missing():
    with pytest.raises(Pds4LabelError, match="vertical_direction"):
        parse_display_direction(
            label_with_display(omit="vertical_display_direction"))


def test_every_stored_mare_serenitatis_label_states_line_top_to_bottom():
    """The four REAL-DATA-01 products, read from disk. If any archive label
    ever says otherwise, REAL-DATA-02's corner mapping is void for it and this
    test is where that is found."""
    root = Path(__file__).resolve().parents[1]
    labels = sorted((root / "data" / "metadata" / "mare_serenitatis").glob("*.xml"))
    checked = 0
    for path in labels:
        text = path.read_text(encoding="utf-8")
        if detect_product_type(text) != "Product_Observational":
            continue
        d = parse_display_direction(text)
        assert (d["vertical_axis"], d["vertical_direction"]) == (
            "Line", "Top to Bottom"), path.name
        assert (d["horizontal_axis"], d["horizontal_direction"]) == (
            "Sample", "Left to Right"), path.name
        checked += 1
    assert checked >= 4, f"expected at least 4 observational labels, saw {checked}"
