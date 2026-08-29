"""Solar illumination geometry at a ground point, from the archive sub-solar point.

Why this module exists
----------------------
REAL-DATA-04 attributes six real-edge outcomes to Δ**incidence** (D-040), and
states its own scope honestly: *"incidence only, NOT azimuth-controlled"*. That
wording is precise, and a reviewer reads it precisely: **azimuth is an
uncontrolled confound, not a constant.** At a fixed lunar site the Sun's
incidence and its azimuth both sweep through the lunation, so two frames tens
of degrees apart in incidence are months apart and will generally differ in
azimuth too -- and this project's own synthetic work (EXP-001, EXP-003) names
Δ*azimuth* as the axis on which the classical baseline breaks.

So "is Δincidence a proxy for Δazimuth?" is the sharpest available objection to
D-040, and until now the repository could not answer it. RL-032b blocked the
answer on the archive's ``SUB_SOLAR_AZIMUTH`` column, whose reference frame is
unverified (E-027's shape: a column quoted without establishing what it means).

**The block was avoidable.** The archive also publishes ``SUB_SOLAR_LATITUDE``
and ``SUB_SOLAR_LONGITUDE`` -- the selenographic coordinates of the sub-solar
point -- and from those the illumination geometry at *any* ground point is
closed-form spherical trigonometry. No frame convention has to be assumed,
because the answer is computed rather than read.

The check that makes it trustworthy
-----------------------------------
The same two numbers also determine the **incidence** angle, which the archive
publishes independently as ``INCIDENCE_ANGLE``. Recomputing incidence and
comparing is a self-check with real discriminating power (unlike E-027's
``NORTH_AZIMUTH`` cross-check, which had none in the sample it was validated
on): if the sub-solar coordinates are misread, mis-scaled, or in an unexpected
frame, the recomputed incidence will not land on the published value across a
50 deg span of four frames. :func:`incidence_agreement` performs exactly that
comparison, and a caller should refuse to use the azimuth if it fails.

What this module does NOT do
----------------------------
* It does **not** change, and may not change, any verdict, threshold or
  recorded artefact. Like ``scripts/check_transform_against_geometry.py`` it is
  a check applied **after** a decision that was fixed before the data existed.
* It is **not** a pre-registered test. It was written on 2026-08-29, during a
  pre-freeze audit, with the six edge outcomes already known and visible. It
  is therefore a *confound check on an existing conclusion*, and it must be
  reported as one -- never as a prediction that was made and then confirmed.
* It computes the geometry on a **sphere**, ignoring topography. Local slope
  changes the true incidence on a facet by the slope angle; over Mare
  Serenitatis (LOLA median ~3.5 deg at a 15 m baseline, sources.md S7) that is
  small against the 0.96--51.54 deg spread of Δincidence this is used to
  interpret, but it is a real limit and is not modelled here.
* Libration and the finite angular radius of the Sun (~0.26 deg) are ignored;
  both are far below the quantisation of the published two-decimal fields.

Conventions
-----------
* ``(lon, lat)`` in degrees, east-positive, matching :mod:`siim.ingest.footprint`.
* **Azimuth is measured clockwise from north**, in the local horizontal frame
  at the target, and is the direction *towards* the sub-solar point -- i.e. the
  direction the Sun lies in, which is the sense that matters for where a
  shadow falls. It is stated here because an azimuth without a stated sense is
  exactly the ambiguity RL-032b is about.
* **Incidence** is the angle between the local surface normal (spherical) and
  the direction to the Sun: 0 deg is overhead, 90 deg is at the terminator.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "SolarGeometry",
    "solar_geometry_at",
    "angular_difference_deg",
    "incidence_agreement",
]


@dataclass(frozen=True)
class SolarGeometry:
    """Illumination geometry at one ground point for one acquisition."""

    #: Angle between the local (spherical) normal and the direction to the Sun.
    incidence_deg: float
    #: Direction towards the sub-solar point, clockwise from north, in [0, 360).
    azimuth_deg: float

    def as_dict(self) -> dict[str, float]:
        return {"incidence_deg": self.incidence_deg,
                "azimuth_deg": self.azimuth_deg}


def solar_geometry_at(
    lon_deg: float, lat_deg: float,
    sub_solar_lon_deg: float, sub_solar_lat_deg: float,
) -> SolarGeometry:
    """Incidence and solar azimuth at ``(lon, lat)`` for a given sub-solar point.

    Both are exact on a sphere. ``incidence`` is the great-circle distance from
    the target to the sub-solar point; ``azimuth`` is the initial bearing along
    that great circle, which is the direction the Sun lies in as seen from the
    ground.

    At the sub-solar point itself the azimuth is undefined (the Sun is
    overhead and there is no horizontal direction to it); ``atan2(0, 0)``
    returns 0.0 there, and a caller comparing azimuths at near-zero incidence
    should treat the value as meaningless rather than as north.
    """
    phi_t, phi_s = np.deg2rad(lat_deg), np.deg2rad(sub_solar_lat_deg)
    dlon = np.deg2rad(sub_solar_lon_deg - lon_deg)

    # The two tangent-plane components of the direction to the Sun. These are
    # the numerator terms of the initial-bearing formula, and they are also
    # exactly the sine part of the angular separation -- azimuth and incidence
    # are the polar coordinates of one vector, so they are computed from one
    # pair of terms rather than two independent expressions that could drift.
    y = np.sin(dlon) * np.cos(phi_s)
    x = (np.cos(phi_t) * np.sin(phi_s)
         - np.sin(phi_t) * np.cos(phi_s) * np.cos(dlon))
    cos_i = (np.sin(phi_t) * np.sin(phi_s)
             + np.cos(phi_t) * np.cos(phi_s) * np.cos(dlon))

    # atan2(sin, cos), NOT arccos(cos). Near the sub-solar point cos_i is
    # 1 - O(eps) and arccos amplifies that rounding by 1/sqrt(1 - cos^2),
    # i.e. it returns O(sqrt(eps)) instead of O(eps): the incidence at the
    # sub-solar point itself came out as 8.5e-7 deg rather than 0. Physically
    # that is a millimetre and it changed no result here, but a geometry
    # function that is ill-conditioned exactly where its answer is smallest is
    # a defect, and the two-argument form is exact across the whole range at
    # no cost. Found by a closed-form test during the 2026-08-29 audit.
    incidence = float(np.rad2deg(np.arctan2(np.hypot(y, x), cos_i)))
    azimuth = float(np.rad2deg(np.arctan2(y, x)) % 360.0)
    return SolarGeometry(incidence_deg=incidence, azimuth_deg=azimuth)


def angular_difference_deg(a_deg: float, b_deg: float) -> float:
    """Smallest unsigned separation between two azimuths, in ``[0, 180]``.

    Azimuth is circular, so ``|a - b|`` is wrong across the wrap: 350 deg and
    10 deg differ by 20, not 340. Returned unsigned because the quantity being
    compared against Δincidence is a *magnitude of illumination change*, and a
    signed difference would depend on an arbitrary edge direction.
    """
    return float(abs((float(a_deg) - float(b_deg) + 180.0) % 360.0 - 180.0))


def incidence_agreement(
    lon_deg: float, lat_deg: float,
    sub_solar_lon_deg: float, sub_solar_lat_deg: float,
    published_incidence_deg: float,
) -> tuple[float, float]:
    """``(recomputed_incidence, signed_difference)`` against the archive value.

    The self-check that licenses the azimuth. The archive derives
    ``INCIDENCE_ANGLE`` from SPICE; this recomputes it from two *different*
    published columns and one ground point. Agreement across several frames
    spanning a wide incidence range is strong evidence that the sub-solar
    coordinates are being read correctly and in the frame assumed here --
    which is the premise the azimuth rests on.

    Disagreement is the informative outcome and must stop the caller: an
    azimuth computed from coordinates that fail this test means nothing.
    """
    g = solar_geometry_at(lon_deg, lat_deg, sub_solar_lon_deg, sub_solar_lat_deg)
    return g.incidence_deg, g.incidence_deg - float(published_incidence_deg)
