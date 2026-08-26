"""Sanity checks that must pass before a decoded tile enters the pipeline.

Every failure mode below produces an array that is finite, correctly shaped,
correctly typed, and *wrong*. None of them raises on its own. The checks here
are quantitative and each targets one specific way a byte-range decode can be
silently incorrect:

======================  ====================================================
Failure                 What detects it here
======================  ====================================================
byte order reversed     :func:`lag1_autocorrelation` collapses toward 0
offset off by one byte  same -- 16-bit alignment is destroyed
offset off by lines     cannot be detected intrinsically; reported, not claimed
transposed read         precluded structurally (file_size identity + reshape)
truncated range fetch   length check in ``decode_tile``; SHA-256 in provenance
browse label used       precluded structurally (label root element)
saturation / clipping   fraction at the label's saturation sentinels
dead / constant frame   standard deviation and unique-value count
======================  ====================================================

The central statistic is **lag-1 autocorrelation**. Real terrain imaged by a
push-broom sensor is strongly spatially correlated at the pixel scale; adjacent
samples differ by a small fraction of the local dynamic range. Reading the same
bytes with the wrong endianness, or one byte out of alignment, scrambles the
high and low bytes of every 16-bit word and drives that correlation to
approximately zero. The test is cheap, needs no reference image, and separates
the two cases by an order of magnitude rather than a few percent.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from .pds4 import Pds4ImageStructure, decode_tile

__all__ = [
    "TileChecks",
    "lag1_autocorrelation",
    "check_tile",
    "byte_order_evidence",
]

#: Below this, an image is not plausibly natural terrain at pixel scale.
#: Correct NAC tiles measure ~0.94-0.98; a byte-swapped decode of the same
#: bytes measures ~0.35-0.67. The threshold sits between them.
MIN_PLAUSIBLE_AUTOCORR = 0.60

#: How much one decode must beat its alternative by before the difference is
#: called evidence. Without a margin the comparison is a bare ``>``, and on a
#: noise-dominated tile -- where the correct and the byte-swapped decode both
#: score about zero -- a difference of 0.0002 was enough to declare the byte
#: order wrong. Measured on the real terminator frame: declared 0.3553 vs
#: swapped 0.3531, a margin of 0.0022, which is noise and not a discrimination.
#: Below this margin the evidence is reported as INCONCLUSIVE, which is the
#: honest description and is not the same as passing.
DECODE_EVIDENCE_MARGIN = 0.10


def lag1_autocorrelation(img: np.ndarray) -> float:
    """Mean of the row-wise and column-wise lag-1 Pearson correlation.

    Returns ``nan`` if the tile is constant or has too few finite pixels.
    Computed on finite pixels only, so masked sentinels do not contribute.
    """
    a = np.asarray(img, dtype=np.float64)
    if a.ndim != 2 or a.shape[0] < 2 or a.shape[1] < 2:
        return float("nan")

    def _corr(x: np.ndarray, y: np.ndarray) -> float:
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() < 16:
            return float("nan")
        x, y = x[ok], y[ok]
        sx, sy = x.std(), y.std()
        if sx == 0 or sy == 0:
            return float("nan")
        return float(((x - x.mean()) * (y - y.mean())).mean() / (sx * sy))

    horiz = _corr(a[:, :-1].ravel(), a[:, 1:].ravel())
    vert = _corr(a[:-1, :].ravel(), a[1:, :].ravel())
    vals = [v for v in (horiz, vert) if np.isfinite(v)]
    return float(np.mean(vals)) if vals else float("nan")


def byte_order_evidence(
    raw: bytes, struct: Pds4ImageStructure, *, n_lines: int,
    sample0: int = 0, n_samples: int | None = None,
) -> dict[str, float]:
    """Decode the same bytes both ways and compare spatial correlation.

    Empirical, not a reinterpretation: the label's declared ``data_type`` is
    what the decoder uses. This measures whether that declaration is
    *consistent with the bytes*, which a label alone cannot tell you. The
    declared order should win by a wide margin; if the swapped order wins, the
    label and the file disagree and nothing downstream should be trusted.

    **Sentinels are masked and the sample window is applied**, and both are
    load-bearing. A whole-line NAC read includes wide ``-32768`` border columns
    that are constant by construction. Left in, they carry variance of ~3700 DN
    against a scene standard deviation of ~20, and the lag-1 correlation then
    measures the border rather than the terrain: two different frames scored an
    identical 0.9919 with a vertical correlation of exactly 1.0000. That is
    E-010's sentinel artefact -- a statistic collapsing onto a sentinel --
    recurring in a new place, and it is recorded as **E-023**.
    """
    swapped = "<i2" if struct.numpy_dtype.startswith(">") else ">i2"
    alt = Pds4ImageStructure(**{**asdict(struct), "numpy_dtype": swapped})
    kw = dict(n_lines=n_lines, sample0=sample0, n_samples=n_samples,
              mask_special_constants=True)
    return {
        "autocorr_as_declared": lag1_autocorrelation(decode_tile(raw, struct, **kw)),
        "autocorr_byte_swapped": lag1_autocorrelation(decode_tile(raw, alt, **kw)),
        "declared_dtype": struct.numpy_dtype,
        "swapped_dtype": swapped,
    }


def byte_alignment_evidence(
    raw: bytes, struct: Pds4ImageStructure, *, n_lines: int,
    sample0: int = 0, n_samples: int | None = None,
) -> dict[str, float]:
    """Compare the planned offset against a one-byte-shifted read.

    A one-byte shift keeps every value finite and in range while splitting each
    16-bit word across two pixels. If the shifted read is not markedly worse,
    the array is not aligned to the element grid and the offset is wrong.

    Sentinels are masked and the sample window applied, for the reason given in
    :func:`byte_order_evidence` (E-023).
    """
    stride = struct.line_stride_bytes
    usable = n_lines - 1
    kw = dict(n_lines=usable, sample0=sample0, n_samples=n_samples,
              mask_special_constants=True)
    aligned = decode_tile(raw[:usable * stride], struct, **kw)
    shifted = decode_tile(raw[1:1 + usable * stride], struct, **kw)
    return {
        "autocorr_aligned": lag1_autocorrelation(aligned),
        "autocorr_shifted_one_byte": lag1_autocorrelation(shifted),
    }


@dataclass(frozen=True)
class TileChecks:
    """Outcome of :func:`check_tile`. ``passed`` gates the pipeline."""

    passed: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_tile(
    img: np.ndarray,
    struct: Pds4ImageStructure | None = None,
    *,
    raw: bytes | None = None,
    n_lines: int | None = None,
    sample0: int = 0,
    n_samples: int | None = None,
    expected_shape: tuple[int, int] | None = None,
    label: str = "tile",
) -> TileChecks:
    """Run every intrinsic check available on a decoded tile.

    ``raw`` and ``n_lines`` enable the byte-order and alignment evidence, which
    need the original bytes. Without them those checks are skipped and said to
    be skipped -- never silently passed.

    What this **cannot** check is stated as a warning rather than omitted: an
    offset wrong by a whole number of lines produces a perfectly valid image of
    the wrong part of the Moon, and no intrinsic statistic distinguishes it.
    Only agreement with an independent reference could, and this project has
    none for these products.
    """
    a = np.asarray(img, dtype=np.float64)
    failures: list[str] = []
    warnings: list[str] = []
    stats: dict[str, Any] = {"label": label}

    stats["shape"] = list(a.shape)
    stats["dtype_decoded"] = str(np.asarray(img).dtype)
    if expected_shape is not None and tuple(a.shape) != tuple(expected_shape):
        failures.append(
            f"shape {a.shape} != expected {tuple(expected_shape)}")

    finite = np.isfinite(a)
    n_total = a.size
    stats["n_pixels"] = int(n_total)
    stats["finite_fraction"] = float(finite.mean())
    stats["n_nan"] = int(np.isnan(a).sum())
    stats["n_inf"] = int(np.isinf(a).sum())
    if stats["n_inf"] > 0:
        failures.append(f"{stats['n_inf']} non-finite (inf) pixels")
    if stats["finite_fraction"] < 0.5:
        failures.append(
            f"only {stats['finite_fraction']:.1%} of pixels are finite")

    if finite.any():
        v = a[finite]
        qs = np.percentile(v, [0, 0.1, 1, 25, 50, 75, 99, 99.9, 100])
        stats.update(
            min=float(qs[0]), p0_1=float(qs[1]), p1=float(qs[2]),
            p25=float(qs[3]), median=float(qs[4]), p75=float(qs[5]),
            p99=float(qs[6]), p99_9=float(qs[7]), max=float(qs[8]),
            mean=float(v.mean()), std=float(v.std()),
            zero_fraction=float((v == 0).mean()),
            n_unique=int(np.unique(v).size),
        )
        if stats["std"] == 0:
            failures.append("tile is constant (std = 0): no image content")
        elif stats["n_unique"] < 16:
            failures.append(
                f"only {stats['n_unique']} distinct values: not an image")
        if stats["zero_fraction"] > 0.5:
            failures.append(
                f"{stats['zero_fraction']:.1%} of pixels are exactly zero -- "
                "consistent with a padded or truncated read")
    else:
        failures.append("no finite pixels at all")

    # -- saturation, against the label's own sentinels ----------------------
    if struct is not None and struct.special_constants:
        raw_int = np.asarray(img)
        sat = {}
        for name, value in struct.special_constants.items():
            if name.startswith(("valid_min", "valid_max")):
                continue
            sat[name] = float(np.mean(raw_int == value)) if np.issubdtype(
                raw_int.dtype, np.integer) else float(np.mean(a == value))
        stats["saturation_fractions"] = sat
        hot = {k: v for k, v in sat.items() if v > 0.01}
        if hot:
            warnings.append(
                "saturation sentinels present above 1%: "
                + ", ".join(f"{k}={v:.2%}" for k, v in hot.items()))
        vmin = struct.special_constants.get("valid_minimum")
        if vmin is not None and finite.any():
            below = float(np.mean(a[finite] < vmin))
            stats["fraction_below_valid_minimum"] = below
            if below > 0.01:
                warnings.append(
                    f"{below:.2%} of pixels are below the label's "
                    f"valid_minimum ({vmin})")

    # -- decode-correctness evidence, evaluated BEFORE the plain
    #    autocorrelation so that a low value can be attributed correctly ----
    decode_verdict = "unknown"
    if raw is not None and struct is not None and n_lines is not None:
        win = dict(sample0=sample0, n_samples=n_samples)
        bo = byte_order_evidence(raw, struct, n_lines=n_lines, **win)
        stats["byte_order"] = bo
        d, s = bo["autocorr_as_declared"], bo["autocorr_byte_swapped"]
        ba = byte_alignment_evidence(raw, struct, n_lines=n_lines, **win)
        stats["byte_alignment"] = ba
        al, sh = ba["autocorr_aligned"], ba["autocorr_shifted_one_byte"]
        stats["decode_margin_byte_order"] = (
            float(d - s) if np.isfinite(d) and np.isfinite(s) else None)
        stats["decode_margin_alignment"] = (
            float(al - sh) if np.isfinite(al) and np.isfinite(sh) else None)

        m = DECODE_EVIDENCE_MARGIN
        if np.isfinite(d) and np.isfinite(s) and s - d > m:
            failures.append(
                f"byte-swapped decode is MORE spatially coherent "
                f"({s:.3f}) than the label's declared {bo['declared_dtype']} "
                f"({d:.3f}): the label and the file disagree on byte order")
            decode_verdict = "byte order wrong"
        elif np.isfinite(al) and np.isfinite(sh) and sh - al > m:
            failures.append(
                f"a one-byte-shifted read is MORE coherent ({sh:.3f}) than the "
                f"planned offset ({al:.3f}): the array is not aligned to the "
                "element grid and the offset is wrong")
            decode_verdict = "offset misaligned"
        elif (np.isfinite(d) and np.isfinite(s) and np.isfinite(al)
              and np.isfinite(sh) and d - s > m and al - sh > m):
            decode_verdict = "consistent"
        elif np.isfinite(d) and np.isfinite(s):
            # Both alternatives score about the same. On a noise-dominated tile
            # every decode is equally incoherent, so this test has no power
            # here -- which is a statement about the evidence, not a pass.
            decode_verdict = "inconclusive"
            warnings.append(
                f"decode evidence is INCONCLUSIVE: the declared decode beats "
                f"its byte-swapped alternative by only "
                f"{d - s:+.4f} and its misaligned alternative by "
                f"{al - sh:+.4f}, both under the {m} margin. This test cannot "
                "discriminate on a tile with little pixel-scale structure. "
                "Correctness of the decode must be argued from elsewhere -- "
                "e.g. the same code path scoring decisively on another frame.")
        if decode_verdict in ("byte order wrong", "offset misaligned"):
            stats["failure_class"] = f"decode defect ({decode_verdict})"
    else:
        stats["byte_order"] = None
        stats["byte_alignment"] = None
        warnings.append(
            "byte-order and alignment evidence SKIPPED: raw bytes were not "
            "supplied to check_tile (not the same as having passed)")
    stats["decode_verdict"] = decode_verdict

    # -- spatial structure --------------------------------------------------
    # A low value has two quite different causes and they must not be
    # conflated: the decode is wrong, or the decode is right and the SCENE
    # carries little pixel-scale signal. The byte-order and alignment evidence
    # above discriminates between them -- if the declared decode beats both its
    # byte-swapped and its misaligned alternatives, the bytes are being read
    # correctly and a low correlation is a property of the data.
    ac = lag1_autocorrelation(a)
    stats["lag1_autocorrelation"] = float(ac)
    if not np.isfinite(ac):
        failures.append("lag-1 autocorrelation is undefined (constant tile?)")
    elif ac < MIN_PLAUSIBLE_AUTOCORR:
        if decode_verdict in ("consistent", "inconclusive"):
            qualifier = (
                "the decode is CORRECT (the declared byte order and the "
                "planned offset both beat their alternatives decisively)"
                if decode_verdict == "consistent" else
                "the decode evidence is INCONCLUSIVE here -- on a tile this "
                "noisy no decode looks coherent, so correctness must be "
                "argued from the same code path succeeding on another frame")
            failures.append(
                f"lag-1 autocorrelation {ac:.3f} < {MIN_PLAUSIBLE_AUTOCORR}, "
                f"and {qualifier}. This is a DATA-QUALITY limit, not a "
                "decoding defect: the scene carries little pixel-scale signal "
                "relative to sensor noise. The tile is unsuitable for "
                "pixel-scale feature matching and is failed on those grounds, "
                "not on ingestion grounds.")
            stats["failure_class"] = (
                f"data quality (low SNR), decode {decode_verdict}")
        else:
            failures.append(
                f"lag-1 autocorrelation {ac:.3f} < {MIN_PLAUSIBLE_AUTOCORR} "
                f"and the decode evidence says {decode_verdict!r}: the tile "
                "is finite and correctly shaped, and is not an image.")
            stats["failure_class"] = f"decode defect ({decode_verdict})"

    warnings.append(
        "NOT CHECKED, and not checkable intrinsically: whether the tile is "
        "the intended region of the Moon. An offset wrong by a whole number "
        "of lines yields a valid image of the wrong place. Only an "
        "independent geolocated reference could detect that, and none is "
        "available for these products.")

    return TileChecks(passed=not failures, failures=failures,
                      warnings=warnings, stats=stats)
