"""PDS3 index-label parsing and binary-search row lookup.

The lookup runs over HTTP range requests against a 50 MB table, so the failures
worth pinning are the ones that return *a* row rather than raising: a truncated
record silently yielding a prefix of a value, a column that overruns the record
length, a table that is not sorted by the key it is searched on, and a key that
belongs to a different volume entirely.

Every test drives :func:`find_row_by_product_id` through an in-memory
``read_record`` so nothing here touches the network.
"""

from __future__ import annotations

import pytest

from siim.ingest.index_table import (
    IndexLabelError,
    IndexRowNotFound,
    find_row_by_product_id,
    parse_index_label,
)

# One record, byte by byte (1-based, as PDS3 counts):
#   1-5   '"VOL"'   -- VOLUME_ID is declared at START_BYTE 1, BYTES 4, so the
#                      column covers '"VOL' and the parser must strip the quote
#   6-18  PRODUCT_ID (13)
#   19    separator
#   20-25 UPPER_LEFT_LATITUDE (6)
#   26    newline
RECORD_BYTES = 26


def make_label(record_bytes: int = RECORD_BYTES, file_records: int = 5,
               *, lat_bytes: int = 6, extra: str = "") -> str:
    return f"""PDS_VERSION_ID          = PDS3
^INDEX_TABLE            = "INDEX.TAB"
RECORD_TYPE             = FIXED_LENGTH
RECORD_BYTES            = {record_bytes}
FILE_RECORDS            = {file_records}

OBJECT                  = INDEX_TABLE
  ROWS                  = {file_records}
  ROW_BYTES             = {record_bytes}

  OBJECT           = COLUMN
    NAME           = VOLUME_ID
    COLUMN_NUMBER  = 1
    DATA_TYPE      = CHARACTER
    START_BYTE     = 1
    BYTES          = 4
    DESCRIPTION    = "Volume id."
  END_OBJECT       = COLUMN

  OBJECT           = COLUMN
    NAME           = PRODUCT_ID
    COLUMN_NUMBER  = 2
    DATA_TYPE      = CHARACTER
    START_BYTE     = 6
    BYTES          = 13
    DESCRIPTION    = "Product id."
  END_OBJECT       = COLUMN

  OBJECT           = COLUMN
    NAME           = UPPER_LEFT_LATITUDE
    COLUMN_NUMBER  = 3
    DATA_TYPE      = ASCII_REAL
    START_BYTE     = 20
    BYTES          = {lat_bytes}
    DESCRIPTION    = "Upper left latitude."
  END_OBJECT       = COLUMN
{extra}
END_OBJECT              = INDEX_TABLE
END
"""


PRODUCTS = ["M1000000001LC", "M1000000002LC", "M1000000003LC",
            "M2000000000RC", "M3000000000RC"]


def make_rows(products=PRODUCTS, lats=None) -> list[str]:
    lats = lats or [f"{20.0 + i / 100:6.2f}" for i in range(len(products))]
    return [f'"VOL"{p} {lat}\n' for p, lat in zip(products, lats)]


def reader(rows):
    calls: list[int] = []

    def read(i: int) -> str:
        calls.append(i)
        return rows[i]

    read.calls = calls  # type: ignore[attr-defined]
    return read


# --------------------------------------------------------------------------
# label parsing
# --------------------------------------------------------------------------

def test_parses_record_geometry_and_columns():
    spec = parse_index_label(make_label())
    assert spec.record_bytes == RECORD_BYTES
    assert spec.file_records == 5
    assert set(spec.columns) == {"VOLUME_ID", "PRODUCT_ID",
                                 "UPPER_LEFT_LATITUDE"}


def test_start_byte_is_treated_as_one_based():
    spec = parse_index_label(make_label())
    assert spec.columns["VOLUME_ID"].span == slice(0, 4)
    assert spec.columns["PRODUCT_ID"].span == slice(5, 18)


def test_field_strips_padding_and_odl_quotes():
    spec = parse_index_label(make_label())
    row = make_rows()[0]
    assert spec.field(row, "VOLUME_ID") == "VOL"
    assert spec.field(row, "PRODUCT_ID") == "M1000000001LC"
    assert spec.field(row, "UPPER_LEFT_LATITUDE") == "20.00"


def test_float_field_parses_and_returns_none_for_blank():
    spec = parse_index_label(make_label())
    rows = make_rows(lats=["      ", " 21.00", " 22.00", " 23.00", " 24.00"])
    assert spec.float_field(rows[1], "UPPER_LEFT_LATITUDE") == pytest.approx(21.0)
    assert spec.float_field(rows[0], "UPPER_LEFT_LATITUDE") is None


def test_float_field_returns_none_rather_than_nan_for_unparsable_text():
    """``nan`` would flow into arithmetic and produce a silently empty
    footprint; ``None`` forces the caller to notice."""
    spec = parse_index_label(make_label())
    row = '"VOL"M1000000001LC    N/A\n'
    assert spec.float_field(row, "UPPER_LEFT_LATITUDE") is None


def test_a_short_row_raises_instead_of_yielding_a_prefix_of_a_value():
    # 21.93 truncated to "21.9" still parses as a float, 30 m from the truth.
    spec = parse_index_label(make_label())
    with pytest.raises(IndexLabelError, match="truncated range response"):
        spec.field(make_rows()[0][:-3], "UPPER_LEFT_LATITUDE")


def test_an_unknown_column_names_what_is_available():
    spec = parse_index_label(make_label())
    with pytest.raises(IndexLabelError, match="PRODUCT_ID"):
        spec.field(make_rows()[0], "SUB_SOLAR_AZIMUTH")


def test_missing_record_geometry_raises_rather_than_defaulting():
    label = make_label().replace("RECORD_BYTES            = 26", "")
    with pytest.raises(IndexLabelError, match="RECORD_BYTES"):
        parse_index_label(label)


def test_non_integer_record_geometry_raises():
    label = make_label().replace("RECORD_BYTES            = 26",
                                 "RECORD_BYTES            = many")
    with pytest.raises(IndexLabelError, match="not integers"):
        parse_index_label(label)


def test_non_positive_record_geometry_raises():
    with pytest.raises(IndexLabelError, match="non-positive"):
        parse_index_label(make_label(file_records=0))


def test_a_column_overrunning_the_record_raises_instead_of_being_clipped():
    with pytest.raises(IndexLabelError, match="only 26 bytes"):
        parse_index_label(make_label(lat_bytes=40))


def test_a_label_with_no_columns_raises():
    label = """RECORD_BYTES = 10
FILE_RECORDS = 2
END
"""
    with pytest.raises(IndexLabelError, match="no usable COLUMN"):
        parse_index_label(label)


# --------------------------------------------------------------------------
# row lookup
# --------------------------------------------------------------------------

def test_finds_every_product_in_a_sorted_table():
    spec = parse_index_label(make_label())
    rows = make_rows()
    for i, pid in enumerate(PRODUCTS):
        idx, row = find_row_by_product_id(spec, pid, reader(rows))
        assert idx == i
        assert spec.field(row, "PRODUCT_ID") == pid


def test_the_search_is_logarithmic_not_linear():
    n = 4096
    products = [f"M{i:012d}" for i in range(n)]
    rows = [f'"VOL"{p} {20.0:6.2f}\n' for p in products]
    spec = parse_index_label(make_label(file_records=n))
    read = reader(rows)
    find_row_by_product_id(spec, products[3000], read)
    # 2 bracket probes + at most ceil(log2(4096)) = 12 search probes.
    assert len(read.calls) <= 16


def test_first_and_last_records_are_returned_without_a_search():
    spec = parse_index_label(make_label())
    rows = make_rows()
    read = reader(rows)
    idx, _ = find_row_by_product_id(spec, PRODUCTS[0], read)
    assert idx == 0
    # Both bracket records are read; the hit is served from them rather than
    # costing a third request.
    assert read.calls == [0, len(rows) - 1]


def test_a_key_outside_the_volume_range_says_so_rather_than_not_found():
    spec = parse_index_label(make_label())
    with pytest.raises(IndexRowNotFound, match="different volume"):
        find_row_by_product_id(spec, "M9999999999ZZ", reader(make_rows()))


def test_a_key_before_the_first_record_is_also_a_different_volume():
    spec = parse_index_label(make_label())
    with pytest.raises(IndexRowNotFound, match="different volume"):
        find_row_by_product_id(spec, "M0000000000AA", reader(make_rows()))


def test_a_key_absent_from_a_sorted_table_reports_its_probe_trail():
    spec = parse_index_label(make_label())
    with pytest.raises(IndexRowNotFound, match="Probe keys"):
        find_row_by_product_id(spec, "M1500000000LC", reader(make_rows()))


def test_a_descending_table_is_rejected_instead_of_returning_a_random_row():
    """A binary search on an unsorted table does not fail -- it returns
    whichever row the halving happens to land on, which is a real, valid,
    wrong product."""
    spec = parse_index_label(make_label())
    rows = make_rows(products=list(reversed(PRODUCTS)))
    with pytest.raises(IndexRowNotFound, match="not ascending"):
        find_row_by_product_id(spec, PRODUCTS[2], reader(rows))


def test_an_empty_table_raises():
    spec = parse_index_label(make_label(file_records=0).replace(
        "FILE_RECORDS            = 0", "FILE_RECORDS            = 1"))
    object.__setattr__(spec, "file_records", 0)
    with pytest.raises(IndexRowNotFound, match="zero records"):
        find_row_by_product_id(spec, "X", reader(make_rows()))


def test_lookup_can_search_on_a_different_key_column():
    spec = parse_index_label(make_label())
    rows = make_rows()
    idx, _ = find_row_by_product_id(spec, "20.02", reader(rows),
                                    key_column="UPPER_LEFT_LATITUDE")
    assert idx == 2
