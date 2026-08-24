"""Test configuration: make ``src/`` importable without an install step."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def rng() -> np.random.Generator:
    """Seeded generator. Reproducibility is a spec requirement (§33)."""
    return np.random.default_rng(20260824)


@pytest.fixture
def terrain() -> np.ndarray:
    """A smooth, texture-rich synthetic image standing in for lunar terrain.

    Low-pass filtered noise plus a few crater-like depressions. Smooth enough
    that cubic interpolation is accurate (so warp round-trip tests measure the
    transform, not interpolation error), textured enough to have a
    well-defined centroid and gradient structure.
    """
    from scipy import ndimage

    gen = np.random.default_rng(7)
    base = ndimage.gaussian_filter(gen.normal(size=(256, 256)), sigma=4.0)

    yy, xx = np.mgrid[0:256, 0:256].astype(float)
    for cx, cy, r in [(70.0, 90.0, 22.0), (170.0, 60.0, 15.0), (120.0, 180.0, 30.0)]:
        d = np.hypot(xx - cx, yy - cy)
        base -= 0.8 * np.exp(-((d / r) ** 2))

    base -= base.min()
    return base / base.max()
