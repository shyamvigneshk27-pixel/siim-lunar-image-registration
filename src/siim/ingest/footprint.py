"""Ground footprint of an image tile, from named frame corners.

This module answers one question and refuses to answer any other:

    *Do two extracted image tiles cover the same piece of the Moon?*

It is deliberately independent of everything in :mod:`siim.matching`,
:mod:`siim.geometry` and :mod:`siim.evaluation`. Nothing here reads a pixel.
The inputs are four named corner coordinates and a pair of integer tile
windows; the output is an area in square kilometres. That independence is the
whole value: REAL-DATA-01 measured 3 RANSAC inliers on a real NAC pair and
could not say whether that meant "the matcher failed" or "the tiles do not
overlap", because the only overlap evidence available was the registration
itself. Overlap evidence derived from the registration cannot adjudicate the
registration.

What "named corners" buys, and why a polygon is not enough
---------------------------------------------------------
ODE publishes ``Footprint_geometry`` as a WKT ring. A ring has an order, but
the order's *meaning* is undocumented: nothing in the response says which
vertex is image line 0. Assume wrong and the tile is mirrored along-track,
which moves a 3.7 km crop by up to a frame length -- 48 km. That is exactly the
H1/H2 ambiguity REAL-DATA-01 could not resolve (§4.5: all four combinations
failed, so the data did not decide it).

The archive index table instead names its corners --
``UPPER_LEFT_LATITUDE``, ``LOWER_RIGHT_LONGITUDE`` and so on -- which is an
identity, not an ordering. :class:`FrameCorners` takes those names, and what
"upper" and "left" mean for a given product is then read out of that product's
own PDS4 label rather than assumed: ``disp:Display_Direction`` states
``vertical_display_axis = Line`` with ``vertical_display_direction = Top to
Bottom``, so the top row is the first line
(:func:`siim.ingest.pds4.parse_display_direction`).

Coordinate conventions
----------------------
* Ground coordinates are ``(lon, lat)`` in degrees, east-positive, as the
  archive states them. **Ordered lon-then-lat**, matching WKT and *not*
  matching the ``(lat, lon)`` order of prose; the dataclass field names carry
  the meaning so no call site depends on remembering it.
* Image coordinates are 0-based ``(line, sample)`` == ``(row, column)``, the
  project's C2 convention (``docs/coordinate_contract.md``), consistent with
  :mod:`siim.ingest.pds4`.
* Planar coordinates are kilometres east/north of a stated reference point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

__all__ = [
    "MOON_RADIUS_KM",
    "OVERLAP_CONFIRMED",
    "OVERLAP_INSUFFICIENT",
    "OVERLAP_UNKNOWN",
    "FrameCorners",
    "LocalPlane",
    "OverlapMetrics",
    "polygon_area_km2",
    "is_convex",
    "convex_clip",
    "overlap_metrics",
    "classify_overlap",
    "north_azimuth_agreement",
    "north_azimuth_discriminating_power",
    "TileWindow",
    "predicted_correspondences",
    "tile_admissible_polygon",
    "shared_tile_target",
]

#: Mean lunar radius, km (IAU). Used only to convert degrees to kilometres.
#: The Moon's flattening is ~1.2e-3, so a sphere is good to about 2 m over the
#: 50 km frames handled here -- three orders of magnitude below the 150 m
#: quantisation of the corner coordinates themselves.
MOON_RADIUS_KM = 1737.4

OVERLAP_CONFIRMED = "OVERLAP_CONFIRMED"
OVERLAP_INSUFFICIENT = "OVERLAP_INSUFFICIENT"
OVERLAP_UNKNOWN = "OVERLAP_UNKNOWN"


@dataclass(frozen=True)
class FrameCorners:
    """Ground coordinates of the four corners of a full image frame.

    Corners are named by their **image** position, not by compass direction:

    ========================  ==========================
    field                     image pixel
    ========================  ==========================
    ``upper_left``            ``(line 0,       sample 0)``
    ``upper_right``           ``(line 0,       sample S-1)``
    ``lower_left``            ``(line L-1,     sample 0)``
    ``lower_right``           ``(line L-1,     sample S-1)``
    ========================  ==========================

    **The mapping this class depends on lives here**: the archive's
    ``UPPER_*`` columns are taken to mean the first image line and ``*_LEFT``
    the first sample. That is not assumed from convention -- each product's
    PDS4 label states it directly, via ``disp:Display_Direction``
    (``Line`` / ``Top to Bottom``, ``Sample`` / ``Left to Right``), parsed by
    :func:`siim.ingest.pds4.parse_display_direction`. A caller working from a
    product whose label says otherwise must relabel the corners before
    constructing this class; nothing here infers it.

    The opposite reading is still computable, by
    :meth:`mirrored_along_track`, so a result can be reported with the
    alternative next to it rather than resting silently on the reading above.

    Each value is ``(lon, lat)`` in degrees east-positive.
    """

    upper_left: tuple[float, float]
    upper_right: tuple[float, float]
    lower_left: tuple[float, float]
    lower_right: tuple[float, float]
    lines: int
    samples: int

    def __post_init__(self) -> None:
        if self.lines < 2 or self.samples < 2:
            raise ValueError(
                f"frame must be at least 2x2, got {self.lines}x{self.samples}")
        for name in ("upper_left", "upper_right", "lower_left", "lower_right"):
            v = getattr(self, name)
            if len(v) != 2 or not all(np.isfinite(v)):
                raise ValueError(f"{name} is not a finite (lon, lat) pair: {v!r}")

    def _lonlat_uv(self, u: float, v: float) -> np.ndarray:
        """Bilinear map on normalised coordinates, **without** bounds checks.

        Private and unchecked because :meth:`pixel_at`'s Newton iteration
        legitimately steps a few thousandths outside ``[0, 1]`` on its way to a
        corner. The public :meth:`lonlat_at` keeps the check, so no caller can
        reach an extrapolated coordinate through the API.
        """
        ul = np.asarray(self.upper_left, float)
        ur = np.asarray(self.upper_right, float)
        ll = np.asarray(self.lower_left, float)
        lr = np.asarray(self.lower_right, float)
        return ((1 - u) * (1 - v) * ul + u * (1 - v) * ur
                + (1 - u) * v * ll + u * v * lr)

    def lonlat_at(self, line: float, sample: float) -> tuple[float, float]:
        """Bilinear interpolation of ``(lon, lat)`` at a 0-based pixel.

        Bilinear, not a camera model. A NAC frame is a 5 km x 48 km strip
        imaged at near-nadir emission (1.2-1.7 deg for these products), so the
        along-track coordinate is very nearly linear in line number and the
        cross-track in sample number. The residual is bounded in the stage
        report by comparing the corner-implied pixel scale against the
        archive's own ``SCALED_PIXEL_WIDTH``/``SCALED_PIXEL_HEIGHT``, which are
        computed from SPICE and are not derived from these corners.

        Extrapolation outside the frame is refused: a tile window that runs off
        the frame is a caller error, and quietly extrapolating a bilinear
        surface would return a plausible coordinate for a pixel that does not
        exist.
        """
        if not (0.0 <= line <= self.lines - 1):
            raise ValueError(
                f"line {line} outside frame [0, {self.lines - 1}]")
        if not (0.0 <= sample <= self.samples - 1):
            raise ValueError(
                f"sample {sample} outside frame [0, {self.samples - 1}]")
        p = self._lonlat_uv(sample / (self.samples - 1),
                            line / (self.lines - 1))
        return float(p[0]), float(p[1])

    def pixel_at(
        self, lon: float, lat: float, *, tol_deg: float = 1e-12,
        max_iter: int = 60,
    ) -> tuple[float, float]:
        """Inverse of :meth:`lonlat_at`: the 0-based ``(line, sample)`` of a
        ground point.

        Newton iteration on the bilinear map. Bilinear inversion has a closed
        form via a quadratic, but the quadratic degenerates as the quad
        approaches a parallelogram -- which a near-nadir NAC frame does -- and
        the degenerate branch is the numerically bad one. Newton from the
        centre converges in a handful of steps on a quad this close to affine,
        and it fails loudly rather than returning the wrong root.

        Raises if the point is outside the frame, or if the iteration does not
        converge. **No clamping**: a caller asking for a ground point the frame
        does not contain has a real problem, and returning the nearest edge
        pixel would hide it inside a plausible number.
        """
        v = u = 0.5
        for _ in range(max_iter):
            r = np.array([lon, lat]) - self._lonlat_uv(u, v)
            if abs(r[0]) < tol_deg and abs(r[1]) < tol_deg:
                break
            ul = np.asarray(self.upper_left, float)
            ur = np.asarray(self.upper_right, float)
            ll = np.asarray(self.lower_left, float)
            lr = np.asarray(self.lower_right, float)
            d_du = (1 - v) * (ur - ul) + v * (lr - ll)
            d_dv = (1 - u) * (ll - ul) + u * (lr - ur)
            jac = np.column_stack([d_du, d_dv])
            det = float(np.linalg.det(jac))
            if abs(det) < 1e-18:
                raise ValueError(
                    "the corner quad is degenerate; (line, sample) cannot be "
                    "recovered from a ground point")
            step = np.linalg.solve(jac, r)
            u, v = u + float(step[0]), v + float(step[1])
        else:
            raise ValueError(
                f"bilinear inverse did not converge for (lon {lon}, lat {lat})")
        if not (-1e-9 <= u <= 1 + 1e-9 and -1e-9 <= v <= 1 + 1e-9):
            raise ValueError(
                f"(lon {lon}, lat {lat}) is outside the frame: it solves to "
                f"normalised (line {v:.4f}, sample {u:.4f}), and no clamping "
                "is applied")
        return (float(np.clip(v, 0.0, 1.0) * (self.lines - 1)),
                float(np.clip(u, 0.0, 1.0) * (self.samples - 1)))

    def frame_polygon(self) -> np.ndarray:
        """``(4, 2)`` ring of the whole frame, in image corner order."""
        return np.array([self.upper_left, self.upper_right,
                         self.lower_right, self.lower_left], float)

    def tile_polygon(
        self, *, line0: int, n_lines: int, sample0: int, n_samples: int
    ) -> np.ndarray:
        """``(4, 2)`` ring of ``(lon, lat)`` for a tile window, in image order.

        The ring runs ``(line0, sample0) -> (line0, sampleN) -> (lineN,
        sampleN) -> (lineN, sample0)``, where the ``N`` indices are the **last
        included** pixel -- ``line0 + n_lines - 1``. Using the last included
        pixel rather than the exclusive end matters at this scale only as one
        pixel (~0.9 m), but getting it wrong is the kind of off-by-one that
        survives review because it changes nothing visible.
        """
        if n_lines < 1 or n_samples < 1:
            raise ValueError(
                f"tile must be at least 1x1, got {n_lines}x{n_samples}")
        l1, s1 = line0 + n_lines - 1, sample0 + n_samples - 1
        return np.array([
            self.lonlat_at(line0, sample0),
            self.lonlat_at(line0, s1),
            self.lonlat_at(l1, s1),
            self.lonlat_at(l1, sample0),
        ], dtype=float)

    def mirrored_along_track(self) -> "FrameCorners":
        """The same frame under the opposite line-direction convention.

        Swapping ``upper`` and ``lower`` is exactly what happens if ``UPPER_*``
        turns out to mean the last line rather than the first. Provided so the
        alternative can be *computed* and reported rather than argued about:
        REAL-DATA-01 left this ambiguity open, and a result that is only valid
        under one reading of a column name must say so with the other reading's
        number next to it.
        """
        return FrameCorners(
            upper_left=self.lower_left,
            upper_right=self.lower_right,
            lower_left=self.upper_left,
            lower_right=self.upper_right,
            lines=self.lines,
            samples=self.samples,
        )

    def mirrored_cross_track(self) -> "FrameCorners":
        """The same frame under the opposite sample-direction convention.

        For a **sample-centred** tile window this changes the tile's ground
        polygon not at all, which is why the cross-track naming ambiguity is
        not a threat to this stage's result. That invariance is a claim, so it
        is tested rather than asserted.
        """
        return FrameCorners(
            upper_left=self.upper_right,
            upper_right=self.upper_left,
            lower_left=self.lower_right,
            lower_right=self.lower_left,
            lines=self.lines,
            samples=self.samples,
        )


@dataclass(frozen=True)
class LocalPlane:
    """Equirectangular projection about a reference point, in kilometres.

    ``x`` is east, ``y`` is north, both in km from ``(lon0, lat0)``. Areas are
    computed in this plane rather than in degrees because a square degree is
    not a constant area and comparing two overlap fractions across latitudes in
    degrees would be comparing different units.

    Accuracy: over the ~5 km extent of the tiles compared here the scale error
    of an equirectangular plane relative to the sphere is below 1e-5 relative,
    i.e. centimetres. The projection is not the limiting uncertainty; the
    two-decimal corner coordinates are, by four orders of magnitude.
    """

    lon0: float
    lat0: float
    radius_km: float = MOON_RADIUS_KM

    @classmethod
    def centred_on(cls, polygons: Iterable[np.ndarray]) -> "LocalPlane":
        """A plane centred on the mean vertex of the given ``(lon, lat)`` rings.

        One plane is built for *all* polygons in a comparison, never one per
        polygon: two shapes projected onto different planes cannot be
        intersected, and doing it anyway produces a confident wrong number.
        """
        pts = np.vstack([np.asarray(p, float) for p in polygons])
        if pts.size == 0:
            raise ValueError("no vertices to centre a plane on")
        return cls(lon0=float(pts[:, 0].mean()), lat0=float(pts[:, 1].mean()))

    def to_km(self, lonlat: np.ndarray) -> np.ndarray:
        """``(N, 2)`` of ``(lon, lat)`` degrees -> ``(N, 2)`` of ``(x, y)`` km."""
        p = np.atleast_2d(np.asarray(lonlat, float))
        if p.shape[-1] != 2:
            raise ValueError(f"expected (N, 2) lon/lat, got shape {p.shape}")
        k = np.pi / 180.0 * self.radius_km
        x = (p[:, 0] - self.lon0) * k * np.cos(np.deg2rad(self.lat0))
        y = (p[:, 1] - self.lat0) * k
        return np.column_stack([x, y])


def _signed_area(poly: np.ndarray) -> float:
    p = np.asarray(poly, float)
    if len(p) < 3:
        return 0.0
    x, y = p[:, 0], p[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def polygon_area_km2(poly: np.ndarray) -> float:
    """Shoelace area of a planar ring. Orientation-independent, never negative."""
    return abs(_signed_area(poly))


def _as_ccw(poly: np.ndarray) -> np.ndarray:
    p = np.asarray(poly, float)
    return p if _signed_area(p) >= 0 else p[::-1]


def is_convex(poly: np.ndarray, *, tol: float = 1e-12) -> bool:
    """True if a planar ring is convex (allowing collinear vertices)."""
    p = _as_ccw(np.asarray(poly, float))
    n = len(p)
    if n < 3:
        return False
    for i in range(n):
        a, b, c = p[i], p[(i + 1) % n], p[(i + 2) % n]
        cross = ((b[0] - a[0]) * (c[1] - b[1])
                 - (b[1] - a[1]) * (c[0] - b[0]))
        if cross < -tol:
            return False
    return True


def convex_clip(subject: np.ndarray, clip: np.ndarray) -> np.ndarray:
    """Sutherland-Hodgman clip of ``subject`` by a **convex** ``clip`` polygon.

    Returns the intersection ring, or an empty ``(0, 2)`` array when the two do
    not meet. Exact for convex-by-convex, which is all this module needs: a
    bilinear image of an axis-aligned rectangle under four corners is a
    (possibly skewed) quadrilateral, and a quadrilateral from an almost-planar
    near-nadir strip is convex in practice.

    ``clip`` being convex is a **precondition and is checked**. Sutherland-
    Hodgman against a concave clip silently returns a wrong polygon -- it does
    not fail, it produces degenerate spurs -- and a wrong area here would be
    reported as a scientific result.
    """
    subject = np.asarray(subject, float)
    clip = np.asarray(clip, float)
    if len(subject) < 3 or len(clip) < 3:
        return np.zeros((0, 2))
    if not is_convex(clip):
        raise ValueError(
            "clip polygon is not convex; Sutherland-Hodgman would return a "
            "silently wrong intersection rather than failing")

    cl = _as_ccw(clip)
    out = [np.asarray(v, float) for v in _as_ccw(subject)]
    for i in range(len(cl)):
        a, b = cl[i], cl[(i + 1) % len(cl)]
        if not out:
            break
        inp, out = out, []
        ex, ey = b[0] - a[0], b[1] - a[1]

        def side(p, _ax=a[0], _ay=a[1], _ex=ex, _ey=ey):
            return _ex * (p[1] - _ay) - _ey * (p[0] - _ax)

        for j, cur in enumerate(inp):
            prv = inp[j - 1]
            sc, sp = side(cur), side(prv)
            if sc >= 0.0:
                if sp < 0.0:
                    out.append(prv + (sp / (sp - sc)) * (cur - prv))
                out.append(cur)
            elif sp >= 0.0:
                out.append(prv + (sp / (sp - sc)) * (cur - prv))
    return np.array(out, float) if out else np.zeros((0, 2))


@dataclass(frozen=True)
class OverlapMetrics:
    """Areas and fractions for one pair of tile footprints, in km^2."""

    area_a_km2: float
    area_b_km2: float
    area_intersection_km2: float

    @property
    def iou(self) -> float:
        union = self.area_a_km2 + self.area_b_km2 - self.area_intersection_km2
        return float(self.area_intersection_km2 / union) if union > 0 else 0.0

    @property
    def fraction_of_a(self) -> float:
        return (float(self.area_intersection_km2 / self.area_a_km2)
                if self.area_a_km2 > 0 else 0.0)

    @property
    def fraction_of_b(self) -> float:
        return (float(self.area_intersection_km2 / self.area_b_km2)
                if self.area_b_km2 > 0 else 0.0)

    @property
    def min_fraction(self) -> float:
        """The binding constraint: the worse-covered of the two tiles.

        Reported in preference to IoU because it is the quantity a matcher
        actually experiences. A tile of which 20% is shared ground offers 20%
        of its keypoints as candidates, whatever the other tile does.
        """
        return min(self.fraction_of_a, self.fraction_of_b)

    def as_dict(self) -> dict:
        return {
            "area_a_km2": self.area_a_km2,
            "area_b_km2": self.area_b_km2,
            "area_intersection_km2": self.area_intersection_km2,
            "iou": self.iou,
            "fraction_of_a": self.fraction_of_a,
            "fraction_of_b": self.fraction_of_b,
            "min_fraction": self.min_fraction,
        }


def overlap_metrics(poly_a_km: np.ndarray, poly_b_km: np.ndarray) -> OverlapMetrics:
    """Intersection of two planar rings, already projected to kilometres."""
    inter = convex_clip(poly_a_km, poly_b_km)
    return OverlapMetrics(
        area_a_km2=polygon_area_km2(poly_a_km),
        area_b_km2=polygon_area_km2(poly_b_km),
        area_intersection_km2=polygon_area_km2(inter),
    )


def classify_overlap(
    min_fraction_low: float,
    min_fraction_high: float,
    *,
    confirm_at: float = 0.50,
    insufficient_below: float = 0.20,
) -> tuple[str, str]:
    """Classify a pair from an uncertainty **interval** on ``min_fraction``.

    ``min_fraction_low`` and ``min_fraction_high`` are the pessimistic and
    optimistic ends of the shared-area fraction of the worse-covered tile,
    after propagating the geometric uncertainty. Passing the point estimate
    twice is legal and gives a classification with no uncertainty allowance,
    which is exactly what should never be reported -- so callers pass an
    interval and this function makes the interval decide.

    Thresholds, and where they come from:

    ``confirm_at = 0.50``
        The only regime in which this project's matcher has been *measured* is
        the synthetic one, whose transforms hold source-to-target overlap at
        0.76 at worst and 0.95 typically (``scripts/exp002_common.py``
        ``make_transform``/``overlap_roi``). 0.50 is below that floor, so it
        does not certify "as easy as the synthetic case"; it certifies that a
        majority of each tile is shared ground, which is the condition under
        which a 3-inlier failure is a statement about appearance rather than
        about geography.

    ``insufficient_below = 0.20``
        Below a fifth, the shared strip is a minority of each tile and far
        outside any regime the pipeline has been characterised in. A failure
        there carries no information about illumination robustness, which makes
        it useless as evidence -- and that, not the number itself, is the
        finding.

    Between the two, or straddling either, the answer is
    :data:`OVERLAP_UNKNOWN`. Returns ``(classification, reason)``.
    """
    if not (np.isfinite(min_fraction_low) and np.isfinite(min_fraction_high)):
        return OVERLAP_UNKNOWN, (
            "the overlap fraction is not finite; the geometry did not produce "
            "a usable estimate")
    if min_fraction_low > min_fraction_high:
        raise ValueError(
            f"interval is inverted: low {min_fraction_low} > high "
            f"{min_fraction_high}")
    if min_fraction_low >= confirm_at:
        return OVERLAP_CONFIRMED, (
            f"even at the pessimistic end of the geometric uncertainty "
            f"{min_fraction_low:.3f} of the worse-covered tile is shared "
            f"ground, at or above the {confirm_at:.2f} criterion")
    if min_fraction_high < insufficient_below:
        return OVERLAP_INSUFFICIENT, (
            f"even at the optimistic end of the geometric uncertainty only "
            f"{min_fraction_high:.3f} of the worse-covered tile is shared "
            f"ground, below the {insufficient_below:.2f} criterion")
    return OVERLAP_UNKNOWN, (
        f"the uncertainty interval [{min_fraction_low:.3f}, "
        f"{min_fraction_high:.3f}] straddles the criteria "
        f"(confirm >= {confirm_at:.2f}, insufficient < {insufficient_below:.2f}); "
        "the geometry does not decide this pair")


def north_azimuth_agreement(
    corners: FrameCorners, north_azimuth_deg: float | None
) -> dict:
    """Does ``NORTH_AZIMUTH`` agree that ``UPPER_*`` is the first image line?

    The archive defines ``NORTH_AZIMUTH`` as the angle, clockwise as the image
    is displayed, from the reference axis (frame centre towards the right edge,
    i.e. ``+sample``) to the direction of the north pole. Clockwise on a
    displayed image carries ``+sample`` towards ``+line``, so the north
    direction in image coordinates is

    ``(d_sample, d_line) = (cos NA, sin NA)``

    and north lies towards **decreasing** line -- the top of the image -- when
    ``sin NA < 0``, i.e. ``NA`` in ``(180, 360)``. If the ``UPPER_*`` corners
    are genuinely line 0, their mean latitude must then exceed the ``LOWER_*``
    mean. That is a falsifiable prediction from a column the corner values do
    not feed into, which is what makes it a check rather than a restatement.

    Returns a dict with the prediction, the observation and whether they agree;
    ``agrees`` is ``None`` when ``NORTH_AZIMUTH`` is absent or sits within
    ``5 deg`` of 0 or 180, where ``sin NA`` is too small to carry a sign and
    the test has no discriminating power. Reporting "no power" as "disagrees"
    was E-024's mistake and is not repeated here.
    """
    lat_upper = 0.5 * (corners.upper_left[1] + corners.upper_right[1])
    lat_lower = 0.5 * (corners.lower_left[1] + corners.lower_right[1])
    observed_upper_is_north = bool(lat_upper > lat_lower)
    out = {
        "north_azimuth_deg": north_azimuth_deg,
        "lat_upper_mean": float(lat_upper),
        "lat_lower_mean": float(lat_lower),
        "observed_upper_is_northward": observed_upper_is_north,
        "predicted_upper_is_northward": None,
        "agrees": None,
        "note": "",
    }
    if north_azimuth_deg is None or not np.isfinite(north_azimuth_deg):
        out["note"] = "NORTH_AZIMUTH absent; the corner naming is unchecked here"
        return out
    na = float(north_azimuth_deg) % 360.0
    s = float(np.sin(np.deg2rad(na)))
    if abs(s) < np.sin(np.deg2rad(5.0)):
        out["note"] = (
            f"NORTH_AZIMUTH {na:.2f} deg is within 5 deg of the cross-track "
            "axis, where sin(NA) carries no usable sign; this check has no "
            "discriminating power for this frame and reports neither agreement "
            "nor disagreement")
        return out
    predicted = bool(s < 0.0)
    out["predicted_upper_is_northward"] = predicted
    out["agrees"] = bool(predicted == observed_upper_is_north)
    out["note"] = (
        f"NORTH_AZIMUTH {na:.2f} deg puts north towards "
        f"{'decreasing' if predicted else 'increasing'} line; the corner "
        f"latitudes put the UPPER pair "
        f"{'north' if observed_upper_is_north else 'south'} of the LOWER pair")
    return out


def north_azimuth_discriminating_power(
    frames: dict[str, tuple[FrameCorners, float | None]],
    *,
    spread_deg: float = 15.0,
) -> dict:
    """Can ``NORTH_AZIMUTH`` distinguish line-direction across a set of frames?

    A per-frame agreement test (:func:`north_azimuth_agreement`) is only
    meaningful if the column actually varies with what it is supposed to
    describe. Run it across a set instead: if the frames split on
    ``observed_upper_is_northward`` while their ``NORTH_AZIMUTH`` values sit in
    one tight cluster, the column is describing something other than these
    images -- and each individual "agrees"/"disagrees" verdict is noise.

    This is E-024's lesson applied before the fact rather than after: a
    discriminator needs a stated **domain of validity**, and reporting a
    disagreement from a test with no power sends the next reader to debug
    correct data.

    Returns a dict with the observed split, the angular spread of
    ``NORTH_AZIMUTH`` across the set, and ``has_power`` -- ``True`` only when
    the frames genuinely split *and* the azimuths separate by at least
    ``spread_deg`` between the two groups.
    """
    groups: dict[bool, list[float]] = {True: [], False: []}
    for _, (corners, na) in frames.items():
        if na is None or not np.isfinite(na):
            continue
        upper_north = (0.5 * (corners.upper_left[1] + corners.upper_right[1])
                       > 0.5 * (corners.lower_left[1] + corners.lower_right[1]))
        groups[upper_north].append(float(na) % 360.0)

    out = {
        "n_frames_with_azimuth": len(groups[True]) + len(groups[False]),
        "azimuths_where_upper_is_north": sorted(groups[True]),
        "azimuths_where_upper_is_south": sorted(groups[False]),
        "has_power": False,
        "reason": "",
    }
    if not groups[True] or not groups[False]:
        out["reason"] = (
            "every frame in the set has the same line direction, so this set "
            "cannot show whether NORTH_AZIMUTH tracks it")
        return out

    mean_n = float(np.mean(groups[True]))
    mean_s = float(np.mean(groups[False]))
    separation = abs((mean_n - mean_s + 180.0) % 360.0 - 180.0)
    out["mean_azimuth_upper_north"] = mean_n
    out["mean_azimuth_upper_south"] = mean_s
    out["group_separation_deg"] = separation
    out["has_power"] = bool(separation >= spread_deg)
    out["reason"] = (
        f"frames split {len(groups[True])}/{len(groups[False])} on line "
        f"direction, but their NORTH_AZIMUTH group means differ by only "
        f"{separation:.2f} deg (< {spread_deg:.0f} deg): the column does not "
        f"track the line direction of these products and cannot test the "
        f"corner naming"
        if not out["has_power"] else
        f"frames split {len(groups[True])}/{len(groups[False])} on line "
        f"direction and their NORTH_AZIMUTH group means differ by "
        f"{separation:.2f} deg (>= {spread_deg:.0f} deg): the column tracks "
        f"the line direction and can test the corner naming")
    return out


@dataclass(frozen=True)
class TileWindow:
    """A tile cut out of a frame, plus the decimation applied before matching.

    ``decimation`` matters and is easy to drop. A pipeline that matches on a
    2x-decimated tile works in a pixel grid whose origin is offset by
    ``(k - 1) / 2`` original pixels, because a decimated pixel is the mean of a
    ``k x k`` block and therefore sits at that block's centre. Ignoring the
    offset shifts a predicted correspondence by half a decimated pixel -- small,
    but this class exists precisely so that the conversion is written once.
    """

    line0: int
    sample0: int
    n_lines: int
    n_samples: int
    decimation: int = 1

    def __post_init__(self) -> None:
        if self.decimation < 1:
            raise ValueError(f"decimation must be >= 1, got {self.decimation}")
        if self.n_lines < 1 or self.n_samples < 1:
            raise ValueError("tile must be at least 1x1")

    @property
    def shape(self) -> tuple[int, int]:
        """``(rows, columns)`` of the tile **after** decimation."""
        return (self.n_lines // self.decimation,
                self.n_samples // self.decimation)

    def to_frame(self, row: float, col: float) -> tuple[float, float]:
        """Decimated tile ``(row, col)`` -> full-frame ``(line, sample)``."""
        k = self.decimation
        off = (k - 1) / 2.0
        return (self.line0 + row * k + off, self.sample0 + col * k + off)

    def from_frame(self, line: float, sample: float) -> tuple[float, float]:
        """Full-frame ``(line, sample)`` -> decimated tile ``(row, col)``."""
        k = self.decimation
        off = (k - 1) / 2.0
        return ((line - self.line0 - off) / k,
                (sample - self.sample0 - off) / k)


def predicted_correspondences(
    corners_a: FrameCorners, window_a: TileWindow,
    corners_b: FrameCorners, window_b: TileWindow,
    *, grid: int = 9,
) -> tuple[np.ndarray, np.ndarray]:
    """Where archive geometry says each pixel of tile A lands in tile B.

    Returns ``(points_a, points_b)`` as ``(N, 2)`` arrays of ``(x, y)`` ==
    ``(column, row)`` in **decimated tile** coordinates -- the same convention
    the matcher and :mod:`siim.geometry` use, so the two are directly
    comparable.

    This is the independent check that a registration is not *catastrophically*
    wrong. It goes tile A pixel -> ground (bilinear, from named corners) ->
    tile B pixel, and touches no image data: it would give the same answer if
    both tiles were blank. What it cannot do is validate accuracy. The corner
    coordinates are quoted to 0.01 deg, about 150 m, which at NAC scale is
    ~165 full-frame pixels; the prediction is therefore a **bound at the scale
    of hundreds of pixels**, not a ground truth, and must never be reported as
    one.

    Points that fall outside frame B are dropped rather than extrapolated, and
    an empty result is returned when none survive -- a caller must then say
    "the geometry does not constrain this pair" rather than fit to nothing.
    """
    if grid < 2:
        raise ValueError(f"grid must be at least 2x2, got {grid}")
    rows, cols = window_a.shape
    if rows < 1 or cols < 1:
        raise ValueError("tile A has no pixels after decimation")

    rr = np.linspace(0, rows - 1, grid)
    cc = np.linspace(0, cols - 1, grid)
    src, dst = [], []
    for r in rr:
        for c in cc:
            line, sample = window_a.to_frame(r, c)
            try:
                lon, lat = corners_a.lonlat_at(line, sample)
                lb, sb = corners_b.pixel_at(lon, lat)
            except ValueError:
                continue  # outside a frame: dropped, never extrapolated
            rb, cb = window_b.from_frame(lb, sb)
            src.append((c, r))
            dst.append((cb, rb))
    if not src:
        return np.zeros((0, 2)), np.zeros((0, 2))
    return np.asarray(src, float), np.asarray(dst, float)


def tile_admissible_polygon(
    corners: FrameCorners, *, n_lines: int, n_samples: int
) -> np.ndarray:
    """``(4, 2)`` ring of the ground points a full tile can be **centred** on.

    A tile of ``n_lines x n_samples`` centred on pixel ``(line, sample)`` starts
    at ``line - (n_lines - 1) / 2`` -- the same ``(n - 1) / 2`` convention
    ``acquire_real_pair.window_centred_on`` uses, because a tile spans its last
    *included* pixel. The tile fits inside the frame without clamping exactly
    when that centre lies in the axis-aligned pixel rectangle

    ``[(n_lines - 1) / 2, lines - 1 - (n_lines - 1) / 2]`` by the same in
    samples, and this returns that rectangle's four corners mapped to ground.

    Why it is not simply the frame footprint: the frame footprint answers
    "does the frame cover this point", which is the wrong question when the
    experiment needs a *whole tile* on shared ground. A point 100 pixels from a
    frame edge is inside the footprint and cannot carry a 4096-line tile, and
    centring one there silently clamps the window off the requested ground
    point -- visible in REAL-DATA-03's ``window_detail.clamped_*`` fields, and
    the reason they exist.

    Raises if the frame is too small to hold the tile at all, rather than
    returning an inverted rectangle that would clip to an empty intersection
    several steps later with no explanation.
    """
    if n_lines < 1 or n_samples < 1:
        raise ValueError(f"tile must be at least 1x1, got {n_lines}x{n_samples}")
    if n_lines > corners.lines or n_samples > corners.samples:
        raise ValueError(
            f"a {n_lines}x{n_samples} tile does not fit in a "
            f"{corners.lines}x{corners.samples} frame")
    half_l, half_s = (n_lines - 1) / 2.0, (n_samples - 1) / 2.0
    l0, l1 = half_l, corners.lines - 1 - half_l
    s0, s1 = half_s, corners.samples - 1 - half_s
    return np.array([corners.lonlat_at(l0, s0), corners.lonlat_at(l0, s1),
                     corners.lonlat_at(l1, s1), corners.lonlat_at(l1, s0)],
                    float)


def shared_tile_target(
    frames: Iterable[FrameCorners], *, n_lines: int, n_samples: int
) -> tuple[float, float]:
    """``(lon, lat)`` every frame can centre a full tile on: the centroid of
    the intersection of their :func:`tile_admissible_polygon` regions.

    This is D-033's "centroid of the shared region" rule with the region
    tightened from *the frames overlap here* to *every frame can put a whole
    tile here*. On the frames this project handles the two differ by about a
    tile's half-width, which is 1.9 km along track -- enough to clamp a window
    and move a tile off the ground point it was supposed to sit on.

    Raises if the frames have no common tile-admissible ground. That is a real
    answer -- those frames cannot carry a comparable tile set -- and inventing
    a point would put tiles somewhere no evidence supports.
    """
    frames = list(frames)
    if not frames:
        raise ValueError("no frames given")
    polys = [tile_admissible_polygon(f, n_lines=n_lines, n_samples=n_samples)
             for f in frames]
    plane = LocalPlane.centred_on(polys)
    shared = plane.to_km(polys[0])
    for poly in polys[1:]:
        shared = convex_clip(shared, plane.to_km(poly))
        if len(shared) < 3:
            raise ValueError(
                "the frames share no ground on which every one of them can "
                f"centre a full {n_lines}x{n_samples} tile")
    centroid = np.asarray(shared, float).mean(axis=0)
    k = np.pi / 180.0 * MOON_RADIUS_KM
    lon = plane.lon0 + centroid[0] / (k * np.cos(np.deg2rad(plane.lat0)))
    lat = plane.lat0 + centroid[1] / k
    return float(lon), float(lat)
