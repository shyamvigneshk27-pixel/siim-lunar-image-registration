"""Synthetic lunar terrain: height fields, physical shading, and GT image pairs.

Why a height field rather than warped photographs
-------------------------------------------------
The defining difficulty of this problem is that a change in Sun azimuth
*reverses* the intensity gradient across every crater rim (ANALYSIS §B2).
No photometric perturbation of a single image can reproduce that: gain, bias
and gamma all preserve the sign of a gradient. Only re-illuminating an actual
surface does.

So this module builds a 2.5-D height field and renders it under controllable
Sun geometry. A 180 degree azimuth change then swaps which crater wall is lit
and which is shadowed, exactly as it does on the Moon -- while the geometric
ground truth stays exactly known. That combination (real polarity reversal +
exact GT) is what makes a non-circular evaluation of illumination robustness
possible at all.

What this is not
----------------
* The photometric model is **Lambertian with cast shadows**. Real lunar
  regolith follows a Hapke-type BRDF with strong backscatter and an opposition
  surge. Lambert gets the *geometry* of illumination right -- which wall is
  lit, where shadows fall, how they move with the Sun -- and gets the
  *radiometry* only approximately.
* The terrain is fractal noise plus parametric craters. Real lunar terrain has
  structure this does not reproduce: ejecta rays, secondary crater chains,
  lava flow fronts, regolith mass wasting.
* Therefore results here measure **algorithm behaviour under controlled,
  known conditions**. They are evidence about the method, not about real
  Chandrayaan-2 data, and spec §13 forbids reporting them as the latter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import ndimage

from ..geometry import Transform, translation, warp

__all__ = [
    "SceneType",
    "SyntheticPair",
    "TerrainRegime",
    "TERRAIN_REGIMES",
    "height_field",
    "render",
    "make_pair",
    "slope_statistics",
    "normalise_slope",
    "SUN_LOW",
    "SUN_HIGH",
    "ANGLE_OF_REPOSE_DEG",
    "REFERENCE_BASELINE_M",
]

SceneType = Literal["highlands", "mare", "repetitive", "mixed"]

#: Representative Sun elevations. Low Sun means long shadows and high contrast
#: -- the polar-like regime where classical descriptors are reported to
#: degrade (sources.md S3).
SUN_LOW: float = 15.0
SUN_HIGH: float = 55.0

#: Lunar regolith angle of repose. Slopes materially steeper than this are
#: "almost absent" on the Moon: the megaregolith lacks the cohesion to hold
#: them, and the slope-frequency distribution shows a steep rollover here.
#: What little exceeds it sits on young large impact craters. (sources.md S7)
ANGLE_OF_REPOSE_DEG: float = 33.0

#: Baseline at which the reference slope statistics in ``TERRAIN_REGIMES`` were
#: measured. Slope statistics are strongly baseline-dependent (the Moon is
#: rougher at shorter baselines), so a target median is meaningless without
#: one. Quoting it also makes the OHRC caveat explicit: at 0.25 m/px the real
#: surface is rougher than these 15 m figures.
REFERENCE_BASELINE_M: float = 15.0


@dataclass(frozen=True)
class TerrainRegime:
    """A named, reproducible terrain configuration with explicit slope targets.

    ``target_slope_median_deg = None`` disables slope normalisation entirely,
    which reproduces pre-EXP-002 behaviour exactly.
    """

    name: str
    scene: SceneType
    target_slope_median_deg: float | None
    #: Fractal octaves and persistence set the *spectral* content, which drives
    #: feature density. Slope normalisation sets the *amplitude*. Separating
    #: them is what lets feature density be varied at a fixed slope target.
    octaves: int = 6
    persistence: float = 0.6
    crater_density: float = 1.0
    realistic: bool = True
    note: str = ""


#: Terrain regimes for EXP-002 onward. Targets are anchored to LOLA-derived
#: lunar slope statistics at a 15 m baseline (sources.md S7):
#: highlands median 9.1 deg (mean 11.0, sd 7.0); mare median 3.5 deg
#: (mean 4.9, sd 4.5); angle of repose ~33 deg.
TERRAIN_REGIMES: dict[str, TerrainRegime] = {
    "A_mare_moderate": TerrainRegime(
        name="A_mare_moderate",
        scene="mare",
        target_slope_median_deg=3.5,
        octaves=5,
        persistence=0.55,
        crater_density=1.0,
        note="Realistic mare. Low slope AND low feature density: the "
        "information-poor case (Challenge G).",
    ),
    "A_highlands_moderate": TerrainRegime(
        name="A_highlands_moderate",
        scene="highlands",
        target_slope_median_deg=9.1,
        octaves=6,
        persistence=0.6,
        crater_density=1.0,
        note="Realistic highlands, the LOLA 15 m median. The default "
        "regime for drawing conclusions about real terrain.",
    ),
    "B_highlands_challenging": TerrainRegime(
        name="B_highlands_challenging",
        scene="highlands",
        target_slope_median_deg=18.0,
        octaves=7,
        persistence=0.68,
        crater_density=1.6,
        note="Rugged crater-saturated highlands. Median well above the LOLA "
        "mean; tail approaches the angle of repose. Physically plausible but "
        "at the rough end of the real distribution.",
    ),
    "C_extreme_diagnostic": TerrainRegime(
        name="C_extreme_diagnostic",
        scene="highlands",
        target_slope_median_deg=None,
        octaves=6,
        persistence=0.6,
        crater_density=1.0,
        realistic=False,
        note="The EXP-001 terrain, unchanged. p99 slope ~78 deg, which is "
        "physically impossible on the Moon (far past the angle of repose). "
        "RETAINED DELIBERATELY as a diagnostic stress test and to keep "
        "EXP-001 reproducible -- not as evidence about lunar imagery.",
    ),
}


# ------------------------------------------------------------------ terrain


def _crater(
    shape: tuple[int, int],
    cx: float,
    cy: float,
    radius: float,
    depth: float,
    rim_ratio: float = 0.22,
) -> NDArray[np.float64]:
    """A single crater: parabolic bowl plus a raised rim.

    Depth-to-diameter for fresh lunar craters is roughly 1:5; callers scale
    ``depth`` from ``radius`` accordingly. The raised rim matters more than
    the bowl for this project, because it is the rim that casts the shadow
    whose polarity reverses.
    """
    # Only evaluate inside the crater's footprint: the profile is negligible
    # beyond ~1.6 R, and a full-array evaluation per crater dominates runtime
    # once the field is large.
    out = np.zeros(shape, dtype=np.float64)
    reach = max(radius * 1.6, 3.0)
    x0 = max(0, int(np.floor(cx - reach)))
    x1 = min(shape[1], int(np.ceil(cx + reach)) + 1)
    y0 = max(0, int(np.floor(cy - reach)))
    y1 = min(shape[0], int(np.ceil(cy + reach)) + 1)
    if x0 >= x1 or y0 >= y1:
        return out

    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float64)
    r = np.hypot(xx - cx, yy - cy) / max(radius, 1e-6)
    bowl = np.where(r <= 1.0, depth * (r**2 - 1.0), 0.0)
    rim = depth * rim_ratio * np.exp(-(((r - 1.0) / 0.18) ** 2))
    out[y0:y1, x0:x1] = bowl + rim
    return out


def _fractal(
    shape: tuple[int, int], rng: np.random.Generator, octaves: int = 6, persistence: float = 0.6
) -> NDArray[np.float64]:
    """Sum of smoothed-noise octaves: rolling regional topography."""
    out = np.zeros(shape, dtype=np.float64)
    amplitude = 1.0
    sigma = max(shape) / 8.0
    for _ in range(octaves):
        out += amplitude * ndimage.gaussian_filter(rng.normal(size=shape), sigma=sigma)
        amplitude *= persistence
        sigma = max(sigma / 2.0, 1.0)
    out -= out.mean()
    denom = np.abs(out).max()
    return out / denom if denom > 0 else out


def slope_statistics(
    height: ArrayLike, pixel_scale: float = 1.0
) -> dict[str, float]:
    """Slope distribution of a height field, in degrees.

    Slope is ``arctan(|grad z| / pixel_scale)``. Reported rather than assumed,
    because "realistic terrain" is a claim that has to be checkable against
    published lunar statistics (sources.md S7).
    """
    h = np.asarray(height, dtype=np.float64)
    gy, gx = np.gradient(h, pixel_scale)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    return {
        "median_deg": float(np.median(slope)),
        "mean_deg": float(slope.mean()),
        "std_deg": float(slope.std()),
        "p90_deg": float(np.percentile(slope, 90)),
        "p99_deg": float(np.percentile(slope, 99)),
        "max_deg": float(slope.max()),
        "frac_above_repose": float((slope > ANGLE_OF_REPOSE_DEG).mean()),
    }


def normalise_slope(
    height: ArrayLike, target_median_deg: float, pixel_scale: float = 1.0
) -> NDArray[np.float64]:
    """Rescale heights so the median slope hits ``target_median_deg``.

    Scaling all heights by ``k`` scales every gradient by ``k``, so
    ``k = tan(target) / tan(current_median)`` places the median exactly
    (arctan is monotonic, so the median slope is the arctan of the median
    gradient). The *shape* of the distribution is unchanged -- only its scale --
    which is why the resulting tail must still be reported rather than assumed.

    Crucially this is a pure vertical rescale: it does not touch the horizontal
    coordinate system, so **ground-truth geometry is untouched**.
    """
    h = np.asarray(height, dtype=np.float64)
    gy, gx = np.gradient(h, pixel_scale)
    current = float(np.median(np.hypot(gx, gy)))
    if current < 1e-12:
        return h
    k = np.tan(np.deg2rad(target_median_deg)) / current
    return h * k


def height_field(
    shape: tuple[int, int],
    rng: np.random.Generator,
    scene: SceneType = "highlands",
    relief: float = 30.0,
    ambiguity: float = 0.0,
    target_slope_median_deg: float | None = None,
    octaves: int = 6,
    persistence: float = 0.6,
    crater_density: float = 1.0,
    pixel_scale: float = 1.0,
) -> NDArray[np.float64]:
    """Generate a synthetic lunar height field, in metres.

    Parameters
    ----------
    scene
        ``highlands``
            Crater-saturated, wide size range. Texture-rich; the easy case.
        ``mare``
            Smooth, sparse small craters, low relief. The **low-texture**
            case that Challenge G targets, and where uniform correspondence
            coverage (spec §15) is genuinely hard.
        ``repetitive``
            A regular lattice of near-identical craters. Deliberately
            adversarial: it is built to induce the coherent-wrong-solution
            failure of ANALYSIS §B6, where a match set shifted by one lattice
            period is self-consistent and passes RANSAC.
        ``mixed``
            Highlands abutting mare, with a boundary. Tests behaviour when
            information density varies sharply across one image.
    relief
        Vertical scale in metres. Combined with the renderer's ``pixel_scale``
        this sets how dramatic the shading is.
    ambiguity
        Only used by ``repetitive``. 0.0 keeps a weak fractal base and small
        per-crater jitter; 1.0 removes both, giving a near-perfectly periodic
        scene with no disambiguating context. See the note in that branch.
    target_slope_median_deg
        If given, heights are rescaled so the **median slope** equals this,
        at ``pixel_scale`` metres per pixel (:func:`normalise_slope`). This is
        the explicit realism control: LOLA gives highlands median 9.1 deg and
        mare median 3.5 deg at a 15 m baseline (sources.md S7).

        ``None`` disables normalisation and reproduces pre-EXP-002 behaviour
        exactly, which is how regime ``C_extreme_diagnostic`` stays bit-identical
        to EXP-001.
    octaves, persistence
        Fractal spectrum. These set high-frequency *content*, which is what
        drives keypoint density. Because slope normalisation fixes the
        amplitude afterwards, feature density can be varied at a fixed slope
        target -- the two controls are separable, which the old ``relief``
        parameter did not allow.
    crater_density
        Multiplier on crater count. The other feature-density control, acting
        on structure rather than spectrum.
    pixel_scale
        Metres per pixel, used only to interpret the slope target. Slope
        statistics are meaningless without a stated baseline.
    """
    h, w = shape
    field_ = _fractal(shape, rng, octaves=octaves, persistence=persistence)

    if scene == "highlands":
        base = field_ * relief
        n = max(1, int(round(55 * crater_density)))
        for _ in range(n):
            radius = float(rng.uniform(4, 46))
            base += _crater(
                shape,
                float(rng.uniform(0, w)),
                float(rng.uniform(0, h)),
                radius,
                depth=radius * 0.4,
            )

    elif scene == "mare":
        # Low relief, few craters: deliberately information-poor.
        base = field_ * (relief * 0.18)
        for _ in range(max(1, int(round(7 * crater_density)))):
            radius = float(rng.uniform(3, 11))
            base += _crater(
                shape,
                float(rng.uniform(0, w)),
                float(rng.uniform(0, h)),
                radius,
                depth=radius * 0.35,
            )

    elif scene == "repetitive":
        # A lattice of near-identical craters. The period is the distance by
        # which a wrong-but-self-consistent solution can shift.
        #
        # `ambiguity` controls how nearly perfect the repetition is. This is
        # parameterised rather than fixed because the first version of this
        # scene -- lattice plus a weak fractal base plus small per-crater
        # jitter -- did NOT fool RootSIFT at all (EXP-001, RL-010). The
        # residual context was enough to disambiguate. Inducing the §B6
        # failure requires suppressing that context deliberately, and saying
        # so is part of the result: the failure is real but needs a genuinely
        # feature-poor, near-perfectly periodic scene.
        base = field_ * (relief * 0.10 * (1.0 - ambiguity))
        period = 64
        radius = 17.0
        jitter = 1.0 * (1.0 - ambiguity)
        size_jitter = 0.03 * (1.0 - ambiguity)
        for gy in range(period // 2, h, period):
            for gx in range(period // 2, w, period):
                base += _crater(
                    shape,
                    gx + float(rng.uniform(-jitter, jitter)) if jitter > 0 else float(gx),
                    gy + float(rng.uniform(-jitter, jitter)) if jitter > 0 else float(gy),
                    radius
                    * (
                        float(rng.uniform(1 - size_jitter, 1 + size_jitter))
                        if size_jitter > 0
                        else 1.0
                    ),
                    depth=radius * 0.4,
                )

    elif scene == "mixed":
        base = field_ * relief
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
        highland_mask = (xx + 0.35 * yy) > (0.75 * w)
        base *= np.where(highland_mask, 1.0, 0.2)
        for _ in range(max(1, int(round(40 * crater_density)))):
            cx, cy = float(rng.uniform(0, w)), float(rng.uniform(0, h))
            dense = (cx + 0.35 * cy) > (0.75 * w)
            if not dense and rng.random() > 0.2:
                continue
            radius = float(rng.uniform(4, 40))
            base += _crater(shape, cx, cy, radius, depth=radius * 0.4)
    else:
        raise ValueError(f"unknown scene type {scene!r}")

    if target_slope_median_deg is not None:
        base = normalise_slope(base, target_slope_median_deg, pixel_scale)
    return base


# ------------------------------------------------------------------ shading


def _sun_vector(azimuth_deg: float, elevation_deg: float) -> NDArray[np.float64]:
    """Unit vector pointing **towards** the Sun, in image ``(x, y, z)`` axes.

    Azimuth is compass-style: measured clockwise from "up" in the image
    (``-y``), so 0 deg puts the Sun toward the top of the frame and 90 deg
    toward the right. ``z`` is out of the surface.
    """
    az = np.deg2rad(azimuth_deg)
    el = np.deg2rad(elevation_deg)
    return np.array(
        [np.cos(el) * np.sin(az), -np.cos(el) * np.cos(az), np.sin(el)],
        dtype=np.float64,
    )


def _cast_shadow_mask(
    height: NDArray[np.float64],
    sun: NDArray[np.float64],
    pixel_scale: float,
    max_steps: int = 140,
    step_px: float = 1.25,
) -> NDArray[np.bool_]:
    """March towards the Sun; mark pixels whose line of sight is blocked.

    Cast shadows are what make a low Sun hard, and they are the part a
    Lambertian ``n·l`` term alone does not capture: an unshadowed slope facing
    away from the Sun merely goes dark, whereas a shadowed one is *occluded*
    and carries no surface information at all.
    """
    horiz = np.hypot(sun[0], sun[1])
    if horiz < 1e-9 or sun[2] <= 1e-9:
        return np.zeros(height.shape, dtype=bool)
    ux, uy = sun[0] / horiz, sun[1] / horiz
    tan_el = sun[2] / horiz

    h_, w_ = height.shape
    yy, xx = np.mgrid[0:h_, 0:w_].astype(np.float64)
    shadowed = np.zeros(height.shape, dtype=bool)

    # A ray leaving the lowest point cannot be blocked once it has climbed
    # past the highest terrain, so marching further is provably wasted work.
    # This is an exact bound, not an approximation: it removes only steps that
    # cannot change the result. Flatter (more realistic) terrain casts shorter
    # shadows, so this matters most in exactly the regimes EXP-002 adds.
    relief_range = float(np.ptp(height))
    needed = int(np.ceil(relief_range / max(tan_el * pixel_scale * step_px, 1e-9)))
    max_steps = max(1, min(max_steps, needed))

    for i in range(1, max_steps + 1):
        t = i * step_px
        sx = xx + t * ux
        sy = yy + t * uy
        if (sx.max() < -1 or sx.min() > w_) and (sy.max() < -1 or sy.min() > h_):
            break
        sampled = ndimage.map_coordinates(
            height, np.vstack([sy.ravel(), sx.ravel()]), order=1, mode="nearest"
        ).reshape(height.shape)
        ray_height = height + t * pixel_scale * tan_el
        shadowed |= sampled > ray_height
    return shadowed


def render(
    height: ArrayLike,
    sun_azimuth_deg: float,
    sun_elevation_deg: float,
    pixel_scale: float = 1.0,
    cast_shadows: bool = True,
    albedo: ArrayLike | None = None,
    ambient: float = 0.06,
    noise_std: float = 0.004,
    rng: np.random.Generator | None = None,
) -> NDArray[np.float64]:
    """Shade a height field under a given Sun geometry. Returns a [0, 1] image.

    Parameters
    ----------
    pixel_scale
        Metres per pixel. This is what couples the vertical and horizontal
        scales: halving it doubles the apparent slope of the same terrain, so
        it must be updated whenever an image is resampled, or the synthetic
        scale-change pair becomes physically inconsistent.
    ambient
        Small floor so shadowed regions are dark but not identically zero,
        matching real imagery where scattered light fills shadows slightly.
    """
    h = np.asarray(height, dtype=np.float64)
    if h.ndim != 2:
        raise ValueError(f"height must be 2-D; got {h.shape}")
    if pixel_scale <= 0 or not np.isfinite(pixel_scale):
        raise ValueError(f"pixel_scale must be finite and positive; got {pixel_scale}")

    gy, gx = np.gradient(h, pixel_scale)
    norm = np.sqrt(gx**2 + gy**2 + 1.0)
    sun = _sun_vector(sun_azimuth_deg, sun_elevation_deg)

    # n = (-dz/dx, -dz/dy, 1) / |.|
    cos_i = (-gx * sun[0] - gy * sun[1] + sun[2]) / norm
    shade = np.clip(cos_i, 0.0, None)

    if cast_shadows:
        shade = np.where(_cast_shadow_mask(h, sun, pixel_scale), 0.0, shade)

    img = ambient + (1.0 - ambient) * shade
    if albedo is not None:
        img = img * np.asarray(albedo, dtype=np.float64)
    if noise_std > 0:
        gen = rng if rng is not None else np.random.default_rng(0)
        img = img + gen.normal(0.0, noise_std, size=img.shape)
    return np.clip(img, 0.0, 1.0)


# ------------------------------------------------------------- paired scenes


@dataclass(frozen=True)
class SyntheticPair:
    """A source/reference image pair with an exactly known transform."""

    source: NDArray[np.float64]
    reference: NDArray[np.float64]
    #: TRUE transform, source -> reference. This is the ground truth.
    transform: Transform
    #: Pixels of the reference that came from inside the height field.
    reference_valid: NDArray[np.bool_]
    overlap_fraction: float
    meta: dict = field(default_factory=dict)

    def __repr__(self) -> str:  # pragma: no cover - display only
        return (
            f"SyntheticPair(scene={self.meta.get('scene')!r}, "
            f"model={self.transform.model!r}, "
            f"d_azimuth={self.meta.get('delta_azimuth_deg')}, "
            f"overlap={self.overlap_fraction:.2f})"
        )


def make_pair(
    rng: np.random.Generator,
    transform: Transform,
    *,
    scene: SceneType = "highlands",
    out_shape: tuple[int, int] = (512, 512),
    sun_source: tuple[float, float] = (315.0, 45.0),
    sun_reference: tuple[float, float] | None = None,
    pixel_scale: float = 1.0,
    relief: float = 30.0,
    ambiguity: float = 0.0,
    regime: "TerrainRegime | None" = None,
    cast_shadows: bool = True,
    field_margin: float = 2.0,
    base_field: NDArray[np.float64] | None = None,
) -> SyntheticPair:
    """Build a source/reference pair related by an exactly known ``transform``.

    Both images are rendered from **the same height field**, one in the source
    frame and one in the reference frame, each under its own Sun geometry. The
    geometric ground truth is therefore exact while the appearance difference
    is physically produced rather than simulated by pixel manipulation.

    Parameters
    ----------
    transform
        TRUE source -> reference transform. Ground truth.
    sun_source, sun_reference
        ``(azimuth_deg, elevation_deg)``. If ``sun_reference`` is ``None`` the
        Sun is unchanged, isolating the geometric difficulty from the
        illumination one -- which is the right control when you want to
        attribute a failure to one or the other.
    field_margin
        How much larger than the output the underlying height field is. Needs
        to be big enough that the warped reference is fully covered; the
        returned ``overlap_fraction`` reports whether it was.
    base_field
        Reuse a previously generated height field instead of building a new
        one. Field generation dominates runtime, so sweeping many transforms
        and Sun angles over *the same terrain* is both much faster and a
        better experiment: it holds the scene fixed so a difference in result
        is attributable to the condition under test rather than to terrain
        luck.
    """
    if sun_reference is None:
        sun_reference = sun_source

    h_out, w_out = out_shape
    if base_field is not None:
        big = np.asarray(base_field, dtype=np.float64)
        big_h, big_w = big.shape
        if big_h < h_out or big_w < w_out:
            raise ValueError(
                f"base_field {big.shape} is smaller than out_shape {out_shape}"
            )
    else:
        big_h = int(h_out * field_margin)
        big_w = int(w_out * field_margin)
        if regime is not None:
            scene = regime.scene
            big = height_field(
                (big_h, big_w), rng, scene=regime.scene, relief=relief,
                ambiguity=ambiguity,
                target_slope_median_deg=regime.target_slope_median_deg,
                octaves=regime.octaves, persistence=regime.persistence,
                crater_density=regime.crater_density, pixel_scale=pixel_scale,
            )
        else:
            big = height_field(
                (big_h, big_w), rng, scene=scene, relief=relief, ambiguity=ambiguity
            )

    # Source is a centred crop of the big field.
    ox = (big_w - w_out) // 2
    oy = (big_h - h_out) // 2
    pad = 40  # rendered margin so cast shadows entering the crop are correct
    src_height = big[
        max(0, oy - pad) : oy + h_out + pad, max(0, ox - pad) : ox + w_out + pad
    ]
    px0, py0 = min(pad, ox), min(pad, oy)

    src_img_full = render(
        src_height,
        *sun_source,
        pixel_scale=pixel_scale,
        cast_shadows=cast_shadows,
        rng=rng,
    )
    source = src_img_full[py0 : py0 + h_out, px0 : px0 + w_out]

    # Reference: warp the height field from big coords into reference coords.
    #   source -> big is a translation by (ox, oy), so
    #   big -> reference is  transform @ translation(-ox, -oy).
    #
    # The extra translation(pad, pad) is load-bearing. We render into a canvas
    # padded by `pad` on every side so cast shadows entering the frame are
    # correct, then crop it back off. Without composing that offset into the
    # warp, the crop silently shifts the reference origin by (pad, pad) and the
    # returned "ground truth" transform is wrong by |pad| * sqrt(2) pixels --
    # while RANSAC still reports a ~99% inlier ratio and sub-pixel fit RMSE,
    # because a uniformly shifted match set is perfectly self-consistent.
    # That is ANALYSIS §B6 in miniature, and it is why GT is not optional.
    src_to_big = translation(float(ox), float(oy))
    big_to_ref = translation(float(pad), float(pad)) @ transform @ src_to_big.inverse()

    ref_height, valid = warp(
        big, big_to_ref, out_shape=(h_out + 2 * pad, w_out + 2 * pad), cval=0.0
    )
    # Rendering needs finite heights everywhere; validity is tracked separately.
    ref_height = np.where(valid, ref_height, 0.0)

    # A scale change alters metres-per-pixel, and hence apparent slope. Keeping
    # this consistent is what makes the synthetic scale pair physically honest
    # rather than just a resized picture.
    ref_pixel_scale = pixel_scale
    if transform.model in ("similarity", "euclidean", "translation"):
        ref_pixel_scale = pixel_scale / transform.decompose_similarity()["scale"]
    else:
        det = abs(np.linalg.det(transform.matrix[:2, :2]))
        if det > 1e-12:
            ref_pixel_scale = pixel_scale / np.sqrt(det)

    ref_img_full = render(
        ref_height,
        *sun_reference,
        pixel_scale=ref_pixel_scale,
        cast_shadows=cast_shadows,
        rng=rng,
    )
    reference = ref_img_full[pad : pad + h_out, pad : pad + w_out]
    ref_valid = valid[pad : pad + h_out, pad : pad + w_out]

    d_az = float((sun_reference[0] - sun_source[0] + 180.0) % 360.0 - 180.0)
    return SyntheticPair(
        source=source,
        reference=reference,
        transform=transform,
        reference_valid=ref_valid,
        overlap_fraction=float(ref_valid.mean()),
        meta={
            "scene": scene,
            "sun_source": sun_source,
            "sun_reference": sun_reference,
            "delta_azimuth_deg": d_az,
            "delta_elevation_deg": float(sun_reference[1] - sun_source[1]),
            "pixel_scale_source": pixel_scale,
            "pixel_scale_reference": ref_pixel_scale,
            "relief_m": relief,
            "ambiguity": ambiguity,
            "regime": regime.name if regime is not None else None,
            "cast_shadows": cast_shadows,
            "model": transform.model,
        },
    )
