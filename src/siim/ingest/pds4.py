"""PDS4 ``Array_2D_Image`` label parsing and byte-range tile decoding.

Small and deliberately explicit. This module exists because a NAC frame is
52 224 x 5 064 samples of 16-bit data -- 528 929 736 bytes -- and the project
does not need whole archives to demonstrate registration. It needs *correct*
tiles, and the ways a tile can be silently wrong are the reason every step
below is checked rather than assumed:

* wrong ``offset`` shifts every row by a fraction of a line and produces an
  image that still *looks* like terrain;
* wrong byte order turns a smooth surface into high-frequency noise that a
  detector will happily find keypoints in;
* a transposed or flipped read is geometrically wrong while being
  statistically indistinguishable from the correct read;
* a short HTTP response yields a partially-filled array whose tail is whatever
  the buffer held.

None of these raise on their own. Each one is checked for here.

Scope: what this project has actually encountered. ``SignedLSB2`` is the NAC
CDR element type; the other entries in :data:`PDS4_DATA_TYPES` are written out
explicitly rather than derived from the type name, and **anything absent from
that table raises** instead of being guessed at.

Coordinate convention
---------------------
Decoded arrays are ``array[row, column] == array[line, sample]``, which is the
project's C2 convention (``docs/coordinate_contract.md``): images are indexed
``img[row, col] == img[y, x]``.

**PDS4 axis order** is given by ``<sequence_number>``, which is **1-based**:
``Line`` carries ``sequence_number 1`` and ``Sample`` carries ``2``. Combined
with ``<axis_index_order>Last Index Fastest</axis_index_order>`` -- C /
row-major -- the on-disk layout is line-major with samples contiguous, so line
``L`` begins at ``offset + L * samples * itemsize``.

**PDS4 line and sample numbering is 1-based** in the archive's own
documentation (line 1 is the first line). numpy is 0-based. This module's API
takes and returns **0-based** indices throughout, and the mapping is exactly
``numpy_row = pds_line - 1``. The conversion is never applied implicitly: no
function here accepts a 1-based index, so there is no arithmetic to get wrong
at a call site.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

__all__ = [
    "PDS4_DATA_TYPES",
    "Pds4LabelError",
    "Pds4ImageStructure",
    "detect_product_type",
    "parse_image_structure",
    "plan_tile_byte_range",
    "decode_tile",
    "parse_display_direction",
]

#: PDS4 ``Element_Array/data_type`` -> numpy dtype string, written out one by
#: one. The mapping is explicit on purpose: ``SignedLSB2`` and ``SignedMSB2``
#: differ only in byte order, and a table built by string-munging the type name
#: would turn a typo into a silent endian swap. An unknown type raises.
PDS4_DATA_TYPES: dict[str, str] = {
    "SignedLSB2": "<i2",      # signed 16-bit, little-endian  <- LRO NAC CDR
    "SignedMSB2": ">i2",      # signed 16-bit, big-endian
    "UnsignedLSB2": "<u2",
    "UnsignedMSB2": ">u2",
    "SignedByte": "|i1",
    "UnsignedByte": "|u1",
    "IEEE754LSBSingle": "<f4",
    "IEEE754MSBSingle": ">f4",
}

#: PDS4 namespace of the core information model. Labels declare it as the
#: default namespace, so every element arrives tag-mangled as
#: ``{http://pds.nasa.gov/pds4/pds/v1}file_name``.
_PDS4_NS = "http://pds.nasa.gov/pds4/pds/v1"

#: Only this ordering is supported. ``First Index Fastest`` would be
#: column-major and needs a different stride calculation; rather than guess, it
#: raises. Every LRO NAC CDR label observed carries "Last Index Fastest".
_SUPPORTED_INDEX_ORDER = "Last Index Fastest"


class Pds4LabelError(ValueError):
    """A label is missing, malformed, or not the product type required.

    Distinct from ``ValueError`` so a caller can tell "this label cannot be
    used" from an ordinary argument mistake.
    """


def _local(tag: str) -> str:
    """Element tag without its namespace."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _root(xml_text: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise Pds4LabelError(f"label is not well-formed XML: {exc}") from exc


def detect_product_type(xml_text: str) -> str:
    """PDS4 product class, from the label's root element.

    Returns the bare root tag -- ``"Product_Observational"``,
    ``"Product_Browse"``, ``"Product_Ancillary"``, ... -- with any namespace
    stripped.

    This exists because ODE lists a *browse* label alongside the observational
    one for many products (see :func:`siim.ingest.lro_nac.observational_label_url`).
    A browse label is well-formed XML, parses cleanly, is served over the same
    host with the same ``.xml`` extension, and describes a JPEG pyramid that has
    nothing to do with the ``.IMG``. Distinguishing them requires looking at the
    root element; nothing about the URL or the response reliably says which one
    arrived.
    """
    return _local(_root(xml_text).tag)


@dataclass(frozen=True)
class Pds4ImageStructure:
    """Everything needed to read a rectangle out of a PDS4 2-D image file.

    All indices exposed by this class are **0-based** (see the module
    docstring for the 1-based PDS4 line/sample convention and its mapping).
    """

    file_name: str
    #: Byte offset of the *array*, not of the file. NAC CDRs carry a PDS3
    #: attached header, so this is 5064 rather than 0.
    offset_bytes: int
    lines: int                      # rows      (PDS4 axis "Line",   sequence 1)
    samples: int                    # columns   (PDS4 axis "Sample", sequence 2)
    data_type: str                  # PDS4 spelling, e.g. "SignedLSB2"
    numpy_dtype: str                # explicit mapping, e.g. "<i2"
    axis_index_order: str
    #: ``<file_size>`` from the label, when present. Its agreement with
    #: ``expected_file_bytes`` is the single strongest structural check
    #: available: it validates offset, dimensions and element size together.
    declared_file_bytes: int | None = None
    md5_checksum: str | None = None
    #: DN -> physical units. NAC CDRs are "Scaled I/F"; the factor matters for
    #: radiometry and not at all for feature matching, but dropping it silently
    #: would make the stored numbers uninterpretable.
    scaling_factor: float | None = None
    unit: str | None = None
    #: ``Special_Constants``, verbatim. These are *values*, not flags --
    #: ``-32768`` is a legal 16-bit integer, so an unmasked read puts sentinel
    #: values straight into the image statistics. Note the block also carries
    #: ``valid_minimum``/``valid_maximum``, which are **range bounds and not
    #: sentinels**: see :attr:`sentinel_values`.
    special_constants: dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.special_constants is None:
            object.__setattr__(self, "special_constants", {})

    @property
    def sentinel_values(self) -> set[int]:
        """Values that mean "no datum here", for equality masking.

        ``valid_minimum`` and ``valid_maximum`` are deliberately EXCLUDED. They
        are the bounds of the legal range, not sentinels: masking every pixel
        that happens to equal ``valid_minimum`` (-32752 for these products)
        would delete the darkest legitimate pixels in the frame -- exactly the
        shadowed terrain this project cares about most (E-003: on the Moon,
        near-zero is a real value, not an absence).
        """
        return {v for k, v in self.special_constants.items()
                if not k.startswith(("valid_min", "valid_max"))}

    @property
    def itemsize(self) -> int:
        return int(np.dtype(self.numpy_dtype).itemsize)

    @property
    def line_stride_bytes(self) -> int:
        """Bytes from the start of one line to the start of the next."""
        return self.samples * self.itemsize

    @property
    def image_bytes(self) -> int:
        return self.lines * self.line_stride_bytes

    @property
    def expected_file_bytes(self) -> int:
        return self.offset_bytes + self.image_bytes

    @property
    def shape(self) -> tuple[int, int]:
        """``(rows, columns) == (lines, samples)``, the C2 convention."""
        return (self.lines, self.samples)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.update(
            itemsize=self.itemsize,
            line_stride_bytes=self.line_stride_bytes,
            image_bytes=self.image_bytes,
            expected_file_bytes=self.expected_file_bytes,
            shape_rows_cols=list(self.shape),
            index_convention="array[row=line, column=sample], 0-based",
        )
        return d


def _require(node: ET.Element | None, what: str, ctx: str) -> ET.Element:
    if node is None:
        raise Pds4LabelError(f"label has no {what} inside {ctx}")
    return node


def _find(parent: ET.Element, name: str) -> ET.Element | None:
    """First direct-or-nested child with the given local name."""
    for el in parent.iter():
        if _local(el.tag) == name:
            return el
    return None


def _text_int(el: ET.Element | None, what: str) -> int:
    if el is None or el.text is None or not el.text.strip():
        raise Pds4LabelError(f"label has no usable {what}")
    try:
        return int(el.text.strip())
    except ValueError as exc:
        raise Pds4LabelError(f"{what} is not an integer: {el.text.strip()!r}") from exc


def parse_image_structure(
    xml_text: str, *, require_observational: bool = True
) -> Pds4ImageStructure:
    """Parse ``File_Area_Observational`` -> ``Array_2D_Image`` into a structure.

    Raises :class:`Pds4LabelError`, with the specific missing element named,
    if any of ``File_Area_Observational``, ``File/file_name``,
    ``Array_2D_Image``, ``offset``, the two ``Axis_Array`` entries, or
    ``Element_Array/data_type`` is absent. **Nothing is defaulted.** A missing
    ``offset`` in particular must never be assumed to be 0: NAC CDRs carry a
    5064-byte PDS3 attached header, and reading from 0 yields a plausible image
    displaced by most of a line.
    """
    root = _root(xml_text)
    product_type = _local(root.tag)
    if require_observational and product_type != "Product_Observational":
        raise Pds4LabelError(
            f"label is a {product_type}, not a Product_Observational. "
            "It does not describe the .IMG file and cannot be used to decode "
            "it. For LRO products fetched through ODE this is usually the "
            "browse-pyramid label; see lro_nac.observational_label_url()."
        )

    fao = None
    for el in root:
        if _local(el.tag) == "File_Area_Observational":
            fao = el
            break
    if fao is None:
        raise Pds4LabelError(
            f"{product_type} label contains no File_Area_Observational element"
        )

    file_el = _require(_find(fao, "File"), "File element", "File_Area_Observational")
    fname_el = _require(_find(file_el, "file_name"), "file_name", "File")
    file_name = (fname_el.text or "").strip()
    if not file_name:
        raise Pds4LabelError("File/file_name is empty")

    arr = None
    for el in fao:
        if _local(el.tag) == "Array_2D_Image":
            arr = el
            break
    if arr is None:
        kinds = sorted({_local(e.tag) for e in fao})
        raise Pds4LabelError(
            "File_Area_Observational contains no Array_2D_Image "
            f"(found: {', '.join(kinds)}). Only 2-D images are supported."
        )

    # -- offset: direct child only. ``Header`` also carries an <offset>, and
    #    picking that one up would read from byte 0 of a file whose array
    #    starts at 5064. --
    offset_el = next((e for e in arr if _local(e.tag) == "offset"), None)
    offset = _text_int(offset_el, "Array_2D_Image/offset")
    if offset < 0:
        raise Pds4LabelError(f"Array_2D_Image/offset is negative: {offset}")

    order_el = next((e for e in arr if _local(e.tag) == "axis_index_order"), None)
    index_order = (order_el.text or "").strip() if order_el is not None else ""
    if index_order != _SUPPORTED_INDEX_ORDER:
        raise Pds4LabelError(
            f"axis_index_order is {index_order!r}; only "
            f"{_SUPPORTED_INDEX_ORDER!r} (row-major) is supported. A "
            "column-major array needs a different stride calculation and is "
            "not guessed at here."
        )

    axes_el = next((e for e in arr if _local(e.tag) == "axes"), None)
    n_axes = _text_int(axes_el, "Array_2D_Image/axes")
    if n_axes != 2:
        raise Pds4LabelError(f"Array_2D_Image declares {n_axes} axes; expected 2")

    # -- axis order comes from sequence_number, which is 1-based. Reading the
    #    axes in document order would work for every label seen so far and
    #    would transpose the image the first time one was written differently. --
    axes: dict[int, tuple[str, int]] = {}
    for ax in (e for e in arr if _local(e.tag) == "Axis_Array"):
        name_el, elem_el, seq_el = (_find(ax, "axis_name"), _find(ax, "elements"),
                                    _find(ax, "sequence_number"))
        if name_el is None or name_el.text is None:
            raise Pds4LabelError("Axis_Array has no axis_name")
        seq = _text_int(seq_el, "Axis_Array/sequence_number")
        axes[seq] = (name_el.text.strip(),
                     _text_int(elem_el, f"Axis_Array[{name_el.text.strip()}]/elements"))
    if sorted(axes) != [1, 2]:
        raise Pds4LabelError(
            f"expected Axis_Array sequence_numbers [1, 2], got {sorted(axes)}"
        )
    (name1, n1), (name2, n2) = axes[1], axes[2]
    if (name1, name2) != ("Line", "Sample"):
        raise Pds4LabelError(
            f"expected axis order (Line, Sample) by sequence_number, got "
            f"({name1}, {name2}). A transposed read is geometrically wrong "
            "while looking entirely plausible, so this is not accepted."
        )
    if n1 <= 0 or n2 <= 0:
        raise Pds4LabelError(f"non-positive image dimensions: {n1} x {n2}")

    dt_el = _require(_find(arr, "data_type"), "Element_Array/data_type",
                     "Array_2D_Image")
    data_type = (dt_el.text or "").strip()
    if data_type not in PDS4_DATA_TYPES:
        raise Pds4LabelError(
            f"unsupported PDS4 data_type {data_type!r}. Supported: "
            f"{', '.join(sorted(PDS4_DATA_TYPES))}. Byte order is never "
            "inferred from an unknown type name."
        )

    def _opt_int(el: ET.Element | None) -> int | None:
        try:
            return int((el.text or "").strip()) if el is not None else None
        except ValueError:
            return None

    def _opt_float(el: ET.Element | None) -> float | None:
        try:
            return float((el.text or "").strip()) if el is not None else None
        except (ValueError, AttributeError):
            return None

    sc_el = _find(arr, "Special_Constants")
    special: dict[str, int] = {}
    if sc_el is not None:
        for e in sc_el:
            v = _opt_int(e)
            if v is not None:
                special[_local(e.tag)] = v

    ea = _find(arr, "Element_Array")
    unit_el = _find(ea, "unit") if ea is not None else None

    return Pds4ImageStructure(
        file_name=file_name,
        offset_bytes=offset,
        lines=n1,
        samples=n2,
        data_type=data_type,
        numpy_dtype=PDS4_DATA_TYPES[data_type],
        axis_index_order=index_order,
        declared_file_bytes=_opt_int(_find(file_el, "file_size")),
        md5_checksum=(_find(file_el, "md5_checksum").text or "").strip()
        if _find(file_el, "md5_checksum") is not None else None,
        scaling_factor=_opt_float(_find(ea, "scaling_factor")) if ea is not None else None,
        unit=(unit_el.text or "").strip() if unit_el is not None else None,
        special_constants=special,
    )


def validate_structure(struct: Pds4ImageStructure) -> list[str]:
    """Cross-checks on a parsed structure. Returns the list of checks that passed.

    The important one is ``file_size``: the label states the byte length of the
    ``.IMG`` independently of the array description, so

        ``offset + lines * samples * itemsize == file_size``

    validates the offset, both dimensions and the element size **together**.
    Any one of them being wrong breaks the identity. Raises
    :class:`Pds4LabelError` on disagreement rather than returning a flag,
    because a caller that ignores the flag decodes a corrupt tile.
    """
    passed = []
    if struct.declared_file_bytes is not None:
        if struct.expected_file_bytes != struct.declared_file_bytes:
            raise Pds4LabelError(
                "label is internally inconsistent: offset "
                f"{struct.offset_bytes} + {struct.lines} lines x "
                f"{struct.samples} samples x {struct.itemsize} B = "
                f"{struct.expected_file_bytes} B, but File/file_size declares "
                f"{struct.declared_file_bytes} B "
                f"(difference {struct.expected_file_bytes - struct.declared_file_bytes:+d} B). "
                "Offset, dimensions or element size is wrong."
            )
        passed.append(
            f"file_size identity: {struct.offset_bytes} + {struct.lines}x"
            f"{struct.samples}x{struct.itemsize} = {struct.declared_file_bytes} B"
        )
    passed.append(f"axis order Line(1) x Sample(2) = {struct.shape} rows x cols")
    passed.append(f"data_type {struct.data_type} -> numpy {struct.numpy_dtype}")
    passed.append(f"axis_index_order {struct.axis_index_order!r} (row-major)")
    return passed


def plan_tile_byte_range(
    struct: Pds4ImageStructure, *, line0: int, n_lines: int
) -> tuple[int, int]:
    """Byte range covering whole lines ``[line0, line0 + n_lines)``. 0-based.

    Whole lines, deliberately. A sample-range request would need one HTTP
    range per line (thousands of requests) or a strided read the server cannot
    express; fetching complete lines makes the range **contiguous**, so there
    is exactly one offset to get wrong and the reshape is unambiguous. Sample
    selection happens after decoding, in :func:`decode_tile`.

    Returns ``(byte_start, byte_count)`` for an HTTP ``Range`` header.
    """
    if n_lines <= 0:
        raise ValueError(f"n_lines must be positive, got {n_lines}")
    if line0 < 0:
        raise ValueError(f"line0 must be >= 0 (0-based), got {line0}")
    if line0 + n_lines > struct.lines:
        raise ValueError(
            f"requested lines [{line0}, {line0 + n_lines}) exceed the image's "
            f"{struct.lines} lines"
        )
    start = struct.offset_bytes + line0 * struct.line_stride_bytes
    return start, n_lines * struct.line_stride_bytes


def decode_tile(
    raw: bytes,
    struct: Pds4ImageStructure,
    *,
    n_lines: int,
    sample0: int = 0,
    n_samples: int | None = None,
    mask_special_constants: bool = True,
    apply_scaling: bool = False,
) -> np.ndarray:
    """Decode contiguous whole-line bytes into ``array[row=line, col=sample]``.

    ``raw`` must be exactly the bytes returned for the range planned by
    :func:`plan_tile_byte_range` -- no more, no fewer. A short buffer is the
    signature of a truncated HTTP response and **raises**; padding it would
    produce an array whose last rows are zeros that look like lunar shadow
    (this is E-003 in a new place: on the Moon, near-zero is a legal value).

    Parameters
    ----------
    mask_special_constants
        Replace the label's missing/saturation sentinels with ``NaN``. They are
        ordinary integers (``-32768`` and neighbours), so leaving them in place
        drags the minimum and the mean to the bottom of the range and corrupts
        every statistic computed on the tile.
    apply_scaling
        Multiply by ``scaling_factor`` to get physical units (NAC: I/F). Off by
        default: it is a positive affine map, so it changes no gradient
        *direction* and therefore nothing a feature detector sees, and leaving
        the DN values raw keeps the sentinel comparison exact.
    """
    expected = n_lines * struct.line_stride_bytes
    if len(raw) != expected:
        raise ValueError(
            f"expected exactly {expected} bytes for {n_lines} lines of "
            f"{struct.samples} samples x {struct.itemsize} B, got {len(raw)} "
            f"({len(raw) - expected:+d}). A short response is a truncated "
            "range fetch and is never padded."
        )
    n_samples = struct.samples if n_samples is None else n_samples
    if sample0 < 0 or n_samples <= 0 or sample0 + n_samples > struct.samples:
        raise ValueError(
            f"sample window [{sample0}, {sample0 + n_samples}) is outside the "
            f"image's {struct.samples} samples"
        )

    flat = np.frombuffer(raw, dtype=np.dtype(struct.numpy_dtype))
    if flat.size != n_lines * struct.samples:
        raise ValueError(
            f"decoded {flat.size} elements, expected {n_lines * struct.samples}"
        )
    # Row-major because axis_index_order is "Last Index Fastest" and Sample is
    # sequence 2 -- samples are the contiguous axis.
    img = flat.reshape(n_lines, struct.samples)
    img = img[:, sample0:sample0 + n_samples]

    sentinels = struct.sentinel_values if mask_special_constants else set()
    if not sentinels and not apply_scaling:
        return np.array(img)  # copy: frombuffer views read-only memory

    out = img.astype(np.float64)
    for value in sentinels:
        out[img == value] = np.nan
    if apply_scaling and struct.scaling_factor:
        out *= struct.scaling_factor
    return out


def parse_display_direction(xml_text: str) -> dict[str, str]:
    """``disp:Display_Direction`` from the label, as four plain strings.

    Returns ``{"horizontal_axis", "horizontal_direction", "vertical_axis",
    "vertical_direction"}``. Raises :class:`Pds4LabelError` if the block is
    absent -- there is no default, because the point of reading it is that the
    answer must come from the archive.

    Why this matters far more than a display hint sounds like it should:
    the archive's index table gives corner coordinates under the names
    ``UPPER_LEFT_LATITUDE`` ... ``LOWER_RIGHT_LONGITUDE``, and "upper" is
    meaningless until something says which image line is at the top. This block
    says it, per product::

        vertical_display_axis      = Line
        vertical_display_direction = Top to Bottom

    -- so Line *increases* downwards, the top row is the first line, and
    ``UPPER_*`` is line 0. Likewise ``Sample`` / ``Left to Right`` makes
    ``*_LEFT`` sample 0. Getting the vertical one backwards mirrors a tile
    along-track by up to a whole frame (48 km for a NAC CDR), which is exactly
    the ambiguity REAL-DATA-01 could not resolve and REAL-DATA-02 resolves
    here.
    """
    root = _root(xml_text)
    dd = _find(root, "Display_Direction")
    if dd is None:
        raise Pds4LabelError(
            "label carries no disp:Display_Direction; the meaning of "
            "'upper'/'left' for this product is not stated and is not assumed")
    out: dict[str, str] = {}
    wanted = {
        "horizontal_display_axis": "horizontal_axis",
        "horizontal_display_direction": "horizontal_direction",
        "vertical_display_axis": "vertical_axis",
        "vertical_display_direction": "vertical_direction",
    }
    for el in dd:
        key = wanted.get(_local(el.tag))
        if key is not None:
            out[key] = (el.text or "").strip()
    missing = sorted(set(wanted.values()) - set(out))
    if missing:
        raise Pds4LabelError(
            f"Display_Direction is incomplete, missing {', '.join(missing)}")
    return out


def summarise_label(xml_text: str) -> dict[str, Any]:
    """Product type plus, when observational, the parsed structure. Never raises
    for a browse label -- it reports it, which is what a survey wants."""
    kind = detect_product_type(xml_text)
    out: dict[str, Any] = {"product_type": kind}
    if kind != "Product_Observational":
        out["image_structure"] = None
        out["reason"] = "not an observational label; no image structure present"
        return out
    try:
        s = parse_image_structure(xml_text)
        out["image_structure"] = s.as_dict()
        out["checks_passed"] = validate_structure(s)
    except Pds4LabelError as exc:
        out["image_structure"] = None
        out["reason"] = str(exc)
    return out


def _strip_ns(xml_text: str) -> str:  # pragma: no cover - kept for debugging
    return re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", xml_text)
