"""PDS3 ``INDEX.LBL`` / ``INDEX.TAB`` parsing and record lookup by product id.

Why this module exists
----------------------
REAL-DATA-01 selected two image tiles and could not say whether they shared
ground. The reason was an absence of geometry, and the absence is real: an LRO
NAC **CDR product carries no geolocation at all**. Verified on the products in
``data/metadata/mare_serenitatis/`` --

* the PDS4 ``Product_Observational`` label has ``Time_Coordinates``,
  ``lro:LRO_Parameters`` and ``Array_2D_Image``, and **no** ``Cartography``,
  no ``Geometry``, no corner coordinates, no sub-solar direction;
* the 5064-byte PDS3 attached header inside the ``.IMG`` has file
  characteristics, instrument temperatures and the image object, and **no**
  geometry keywords either.

The geometry exists one level up, in the **volume index table**, which ODE
itself cites as ``Footprint_souce = "PDS Archive Index Table"``. That table
carries ``UPPER_LEFT_LATITUDE`` ... ``LOWER_RIGHT_LONGITUDE`` under those exact
names, plus ``NORTH_AZIMUTH``, ``ORBIT_NODE`` and ``LRO_FLIGHT_DIRECTION``.
Named corners are what a footprint *polygon* cannot give: a polygon's vertex
order is a convention nobody documented, and guessing it flips the image
top-to-bottom.

An index table is 18-54 MB per volume. It is also ``RECORD_TYPE =
FIXED_LENGTH`` and sorted by ``PRODUCT_ID``, so one row costs a binary search
of ~16 HTTP range requests of ``RECORD_BYTES`` each -- about 15 KB, not 50 MB.
That is the whole point of this module.

Scope: PDS3 ODL as it appears in LROC index labels -- ``OBJECT = COLUMN`` /
``END_OBJECT = COLUMN`` blocks with ``START_BYTE`` (1-based) and ``BYTES``.
Nothing here interprets a value; :meth:`IndexTableSpec.field` returns the
stripped text and the caller decides what it is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

__all__ = [
    "IndexLabelError",
    "IndexRowNotFound",
    "IndexColumn",
    "IndexTableSpec",
    "parse_index_label",
    "find_row_by_product_id",
]


class IndexLabelError(ValueError):
    """An index label is malformed or lacks what a lookup needs."""


class IndexRowNotFound(LookupError):
    """No row carries the requested key, or the table is not sorted by it."""


@dataclass(frozen=True)
class IndexColumn:
    """One fixed-width column. ``start_byte`` is **1-based**, as PDS3 states it."""

    name: str
    start_byte: int
    n_bytes: int
    data_type: str

    @property
    def span(self) -> slice:
        """0-based Python slice. The ``- 1`` is the only place the 1-based
        PDS3 convention is converted, so there is one line to get wrong."""
        return slice(self.start_byte - 1, self.start_byte - 1 + self.n_bytes)


@dataclass(frozen=True)
class IndexTableSpec:
    """Layout of a fixed-length index table, from its detached PDS3 label."""

    record_bytes: int
    file_records: int
    columns: dict[str, IndexColumn]

    def field(self, row: str, name: str) -> str:
        """Column ``name`` of ``row``, stripped of padding and ODL quotes.

        Raises if the row is not exactly ``record_bytes`` long: a short row is
        a truncated range response, and slicing it silently yields a value that
        is a *prefix* of the truth -- ``21.9`` where the table said ``21.93``.
        """
        if len(row) != self.record_bytes:
            raise IndexLabelError(
                f"row is {len(row)} bytes, expected exactly {self.record_bytes}. "
                "A short row is a truncated range response and is never padded."
            )
        col = self.columns.get(name)
        if col is None:
            raise IndexLabelError(
                f"index has no column {name!r}. Available: "
                f"{', '.join(sorted(self.columns))}"
            )
        return row[col.span].strip().strip('"').strip()

    def float_field(self, row: str, name: str) -> float | None:
        """:meth:`field` as a float, or ``None`` when the archive left it blank.

        ``None`` rather than ``nan`` so a missing value cannot be carried
        silently into arithmetic; every caller here checks for it.
        """
        txt = self.field(row, name)
        if not txt:
            return None
        try:
            return float(txt)
        except ValueError:
            return None


_COLUMN_BLOCK = re.compile(
    r"OBJECT\s*=\s*COLUMN(.*?)END_OBJECT\s*=\s*COLUMN", re.S)


def _kw(block: str, key: str) -> str | None:
    m = re.search(r"\b" + key + r"\s*=\s*([^\r\n]+)", block)
    return m.group(1).strip().strip('"').strip() if m else None


def parse_index_label(text: str) -> IndexTableSpec:
    """Parse a PDS3 ``INDEX.LBL`` into an :class:`IndexTableSpec`.

    ``RECORD_BYTES`` and ``FILE_RECORDS`` are taken from the file-level
    keywords, not from ``ROW_BYTES``/``ROWS`` inside ``INDEX_TABLE``: the two
    agree in every LROC label seen, and the file-level pair is what a byte
    offset must be computed from.

    A column that claims to extend past the end of a record raises rather than
    being clipped -- that would return a truncated value that still parses as
    a number.
    """
    rb = _kw(text, "RECORD_BYTES")
    fr = _kw(text, "FILE_RECORDS")
    if rb is None or fr is None:
        raise IndexLabelError(
            "index label has no RECORD_BYTES/FILE_RECORDS; record offsets "
            "cannot be computed and nothing is assumed")
    try:
        record_bytes, file_records = int(rb), int(fr)
    except ValueError as exc:
        raise IndexLabelError(
            f"RECORD_BYTES/FILE_RECORDS are not integers: {rb!r}/{fr!r}") from exc
    if record_bytes <= 0 or file_records <= 0:
        raise IndexLabelError(
            f"non-positive RECORD_BYTES={record_bytes} FILE_RECORDS={file_records}")

    columns: dict[str, IndexColumn] = {}
    for m in _COLUMN_BLOCK.finditer(text):
        block = m.group(1)
        name = _kw(block, "NAME")
        sb, nb = _kw(block, "START_BYTE"), _kw(block, "BYTES")
        if not name or sb is None or nb is None:
            continue
        try:
            start_byte, n_bytes = int(sb), int(nb)
        except ValueError:
            continue
        if start_byte < 1 or n_bytes < 1:
            continue
        if start_byte - 1 + n_bytes > record_bytes:
            raise IndexLabelError(
                f"column {name} spans bytes {start_byte}.."
                f"{start_byte + n_bytes - 1} but a record is only "
                f"{record_bytes} bytes")
        columns[name] = IndexColumn(name, start_byte, n_bytes,
                                    _kw(block, "DATA_TYPE") or "")
    if not columns:
        raise IndexLabelError("index label declares no usable COLUMN objects")
    return IndexTableSpec(record_bytes, file_records, columns)


def find_row_by_product_id(
    spec: IndexTableSpec,
    product_id: str,
    read_record: Callable[[int], str],
    *,
    key_column: str = "PRODUCT_ID",
) -> tuple[int, str]:
    """Binary-search a table sorted by ``key_column``. Returns ``(index, row)``.

    ``read_record(i)`` must return record ``i`` (0-based) as text of exactly
    ``spec.record_bytes`` characters -- normally one HTTP range request.

    **The sort order is a precondition, and it is checked rather than trusted.**
    The first and last records are read up front: a descending table is
    rejected outright, and a key outside ``[first, last]`` means the product
    lives in a different volume, which is a different error from "the table is
    unsorted" and is reported as such. If the search terminates without a hit,
    the probe keys that bracketed the miss are included in the message, because
    from inside the loop an unsorted table and an absent key look identical.
    """
    n = spec.file_records
    if n < 1:
        raise IndexRowNotFound("index table declares zero records")

    first_row = read_record(0)
    first = spec.field(first_row, key_column)
    last_row = read_record(n - 1)
    last = spec.field(last_row, key_column)
    if first > last:
        raise IndexRowNotFound(
            f"index is not ascending in {key_column} (first {first!r} > last "
            f"{last!r}); a binary search would return an arbitrary row")
    if product_id == first:
        return 0, first_row
    if product_id == last:
        return n - 1, last_row
    if not (first < product_id < last):
        raise IndexRowNotFound(
            f"{product_id!r} is outside this volume's {key_column} range "
            f"[{first!r}, {last!r}] -- it belongs to a different volume")

    lo, hi = 0, n - 1
    probes: list[str] = []
    while lo <= hi:
        mid = (lo + hi) // 2
        row = read_record(mid)
        key = spec.field(row, key_column)
        probes.append(key)
        if key == product_id:
            return mid, row
        if key < product_id:
            lo = mid + 1
        else:
            hi = mid - 1
    raise IndexRowNotFound(
        f"{product_id!r} not found in {n} records although it lies within "
        f"[{first!r}, {last!r}]. Either the product is absent from this "
        f"volume's index or the table is not sorted by {key_column}. "
        f"Probe keys: {probes}")
