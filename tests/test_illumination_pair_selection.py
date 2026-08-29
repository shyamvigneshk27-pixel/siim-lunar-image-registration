"""D-029's incidence ceiling, implemented and pinned.

The defect this guards against is E-024, and it is a design defect rather than
a coding one. ``find_illumination_pairs`` selects on *maximum incidence
difference*, which is unbounded above, so it maximises its objective by walking
to the terminator. REAL-DATA-01's "best" pair therefore contained an 89.96 deg
frame whose tile measured DN median **29 +/- 20** with a lag-1 autocorrelation
of **0.355** (against 0.976 for the usable frame on the same ground) and failed
the sanity gate on data quality.

**A frame with no signal is not an illumination condition; it is an absence of
data.** D-029 was recorded at the time and remained *recorded-and-not-
implemented* through four subsequent stages -- so the selector that produced
the failure was still capable of producing it. These tests exist so that
cannot silently regress again.

**No recorded artefact is affected.** REAL-DATA-03, -04 and -05 acquired frames
through geometry-driven screening (``screen_frame_d.py``, ``screen_frame_e.py``),
which never calls this function. REAL-DATA-01, which did, ran under the
pre-ceiling behaviour and is preserved by passing ``max_incidence_deg=inf``.
"""

from __future__ import annotations

import math

import pytest

from siim.ingest.lro_nac import (
    MAX_USABLE_INCIDENCE_DEG,
    NacProduct,
    find_illumination_pairs,
)

#: A footprint polygon shared by every synthetic product below, so that
#: footprint overlap is constant and cannot be what a test is measuring.
_RING = "POLYGON((21.9 19.5, 22.2 19.5, 22.2 20.4, 21.9 20.4, 21.9 19.5))"


def _product(pdsid: str, incidence: float, resolution: float = 1.0) -> NacProduct:
    return NacProduct(
        pdsid=pdsid, utc_start=None, center_lat=20.0, center_lon=22.0,
        map_resolution_m=resolution, incidence_deg=incidence,
        emission_deg=1.5, phase_deg=incidence, image_url=None, label_url=None,
        image_kbytes=None, raw={"Footprint_geometry": _RING},
    )


#: The four real incidence values this project has handled, plus the
#: terminator frame that motivated D-029.
USABLE = 69.76      # frame B -- the highest incidence ever used successfully
TERMINATOR = 89.96  # the E-024 frame


def test_the_ceiling_sits_above_every_frame_actually_used():
    """The cut must not have been fitted to the data it separates."""
    assert USABLE < MAX_USABLE_INCIDENCE_DEG < TERMINATOR


def test_a_terminator_frame_is_excluded():
    """The E-024 pair: maximum incidence difference, minimum usable signal."""
    pairs = find_illumination_pairs([_product("a", 24.64),
                                     _product("b", TERMINATOR)])
    assert pairs == [], (
        "a pair containing an 89.96 deg terminator frame was offered as an "
        "illumination pair; D-029 exists precisely to refuse it")


def test_a_usable_high_incidence_frame_is_retained():
    """The ceiling must not throw away the real frames the project depends on.

    B (69.76 deg) is in REAL-DATA-03's *succeeding* edge B -> C. A ceiling that
    excluded it would have removed the project's first real registration
    success, so this is the test that stops the cut being set too low.
    """
    pairs = find_illumination_pairs([_product("a", 29.95), _product("b", USABLE)])
    assert len(pairs) == 1
    assert pytest.approx(pairs[0][2]["incidence_delta_deg"], abs=1e-9) == 39.81


def test_the_ceiling_is_applied_to_both_frames_not_only_the_brighter():
    """Either frame being unusable makes the pair unusable."""
    assert find_illumination_pairs([_product("a", TERMINATOR),
                                    _product("b", 24.64)]) == []


def test_the_pre_d029_behaviour_is_still_reachable():
    """REAL-DATA-01 ran without the ceiling and its artefacts must stay explicable.

    Integrity rule 3 protects what was recorded; this keeps the code path that
    produced it reachable and named, rather than making a historical artefact
    impossible to account for.
    """
    pairs = find_illumination_pairs([_product("a", 24.64),
                                     _product("b", TERMINATOR)],
                                    max_incidence_deg=math.inf)
    assert len(pairs) == 1, (
        "the pre-D-029 selection is no longer reproducible, so REAL-DATA-01's "
        "pair choice can no longer be explained from the code")


def test_the_ceiling_does_not_disturb_the_other_criteria():
    """Difference, resolution and overlap filters must behave exactly as before."""
    # below the difference floor
    assert find_illumination_pairs([_product("a", 30.0), _product("b", 40.0)],
                                   min_incidence_delta_deg=15.0) == []
    # above it
    assert len(find_illumination_pairs([_product("a", 30.0), _product("b", 50.0)],
                                       min_incidence_delta_deg=15.0)) == 1
    # resolution ratio filter still bites, with both frames under the ceiling
    assert find_illumination_pairs([_product("a", 30.0, resolution=1.0),
                                    _product("b", 50.0, resolution=3.0)],
                                   max_resolution_ratio=1.5) == []
