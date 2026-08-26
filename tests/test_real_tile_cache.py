"""Regression coverage for the raw-tile byte cache in ``scripts/check_real_tiles``.

The cache exists so a 41 MB range fetch is not repeated. Its failure mode is
the one this project keeps meeting: an artefact name that omits a varying
parameter, so a second acquisition of the *same product at a different window*
silently reads the first window's bytes.

That is E-030, and it is E-025 recurring in a second script. When it happened,
the byte-order and alignment evidence for a REAL-DATA-03 tile was computed from
REAL-DATA-01 bytes, and the resulting failure message blamed the range fetch —
sending the reader to debug a fetch that was correct (E-024's lesson).

These tests use tiny synthetic byte blobs and never touch the network.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location(
    "check_real_tiles", ROOT / "scripts" / "check_real_tiles.py")
crt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crt)


def _tile(pdsid="nac.mtest", line0=100, sample0=10, n_lines=8, payload=b""):
    return {
        "pdsid": pdsid,
        "line0": line0,
        "sample0": sample0,
        "n_lines": n_lines,
        "n_samples": 4,
        "byte_start": 1000,
        "byte_count": len(payload),
        "bytes_sha256": hashlib.sha256(payload).hexdigest(),
        "image_url": "https://example.invalid/never-fetched.IMG",
    }


class _Struct:
    """Just enough of Pds4ImageStructure for plan_tile_byte_range.

    Chosen so the planned range is exactly ``(1000, 32)`` for the default
    tile: offset 600 + line0 100 x stride 4 = 1000, and 8 lines x 4 B = 32.
    """
    lines, samples = 52224, 4
    offset_bytes = 1000 - 100 * 4

    @property
    def line_stride_bytes(self):
        return 4


def test_the_sidecar_name_encodes_the_window_not_only_the_product():
    """The whole of E-030 in one assertion: two windows of one product must
    not share a cache path."""
    a = crt.raw_sidecar(Path("/out"), _tile(line0=30126, sample0=1508))
    b = crt.raw_sidecar(Path("/out"), _tile(line0=17955, sample0=1811))
    assert a != b
    assert "30126" in a.name and "17955" in b.name
    assert "1508" in a.name and "1811" in b.name


def test_a_matching_cache_entry_is_used_without_fetching(tmp_path):
    payload = b"\x01\x02" * 16
    tile = _tile(payload=payload)
    crt.raw_sidecar(tmp_path, tile).write_bytes(payload)
    raw, how = crt.load_or_fetch_raw(tmp_path, tile, _Struct())
    assert raw == payload
    assert how.startswith("cache")


def test_a_cache_entry_for_a_different_window_is_discarded_not_used(tmp_path, capsys):
    """The exact E-030 scenario. The stale file sits at the LEGACY path, which
    is what REAL-DATA-01 wrote, and it must not be returned."""
    stale = b"\xAA" * 32
    payload = b"\x01\x02" * 16
    tile = _tile(payload=payload)
    crt.legacy_raw_sidecar(tmp_path, tile).write_bytes(stale)

    calls = []

    def fake_fetch(url, start, count):
        calls.append((url, start, count))
        return payload

    crt.fetch_byte_range = fake_fetch
    raw, how = crt.load_or_fetch_raw(tmp_path, tile, _Struct())
    assert raw == payload, "stale bytes were returned for the wrong window"
    assert len(calls) == 1, "the stale cache entry suppressed the re-fetch"
    assert "different window" in capsys.readouterr().out
    assert crt.raw_sidecar(tmp_path, tile).read_bytes() == payload


def test_a_legacy_cache_entry_is_honoured_when_its_hash_proves_it_is_right(tmp_path):
    """REAL-DATA-01 wrote 166 MB of sidecars under the old name. They stay
    usable — but because their bytes match, never because of their name."""
    payload = b"\x07" * 32
    tile = _tile(payload=payload)
    crt.legacy_raw_sidecar(tmp_path, tile).write_bytes(payload)

    def refuse(*_a, **_k):
        raise AssertionError("re-fetched despite a hash-verified legacy cache")

    crt.fetch_byte_range = refuse
    raw, how = crt.load_or_fetch_raw(tmp_path, tile, _Struct())
    assert raw == payload
    assert "legacy cache" in how


def test_a_fetch_never_overwrites_an_existing_sidecar(tmp_path):
    """Integrity rule 4 at the file level: the only way to reach the write is
    a cache miss, so an existing file there means two different byte strings
    claim one window."""
    payload = b"\x03" * 32
    tile = _tile(payload=payload)
    # A file at the correct path whose hash does NOT match: the cache misses,
    # the fetch runs, and the write must refuse rather than clobber it.
    crt.raw_sidecar(tmp_path, tile).write_bytes(b"\x09" * 32)
    crt.fetch_byte_range = lambda *_a, **_k: payload
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        crt.load_or_fetch_raw(tmp_path, tile, _Struct())


def test_a_manifest_range_disagreeing_with_the_label_stops_rather_than_fetching(tmp_path):
    payload = b"\x05" * 32
    tile = _tile(payload=payload)
    tile["byte_start"] = 999999  # manifest disagrees with the label's plan
    crt.fetch_byte_range = lambda *_a, **_k: payload
    with pytest.raises(SystemExit, match="disagrees with the manifest"):
        crt.load_or_fetch_raw(tmp_path, tile, _Struct())
