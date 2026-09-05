"""Baselines B0, B2, B3, B5 and B7, behind one interface (ANALYSIS §E.1).

Why these five, and why now
---------------------------
The contribution criterion in §E.2 is a delta measured against *seven*
baselines, run twice each -- as their authors intended, and wrapped in our
protocol. With only B1 implemented that criterion is unmeasurable, so every
comparative claim the project might make is currently undefendable. These five
need no data we do not have, no GPU, and no pretrained weight, so nothing but
effort was ever blocking them.

The five
--------
=========  ==========================================  ==========================
 ID         Method                                      Role (§E.1)
=========  ==========================================  ==========================
 B0         Identity -- no registration at all          Absolute error floor
 B2         ASIFT (affine-simulated SIFT)               Second classical detector
 B2K        AKAZE + ratio test + LO-RANSAC              Nonlinear scale space
 B3         ORB + ratio test + LO-RANSAC                Efficiency floor
 B5         Phase correlation seeding ECC               Direct / intensity method
 B7         Phase congruency, then SIFT on that map     Multimodal classical
=========  ==========================================  ==========================

A substitution, recorded rather than made silently
--------------------------------------------------
§E.1 nominates **AKAZE** for the second-classical slot. OpenCV 5 moved AKAZE,
KAZE and BRISK out of the core distribution into ``opencv_contrib``, so on a
core-only build ``B2K`` is unavailable and raises a message saying exactly
that -- it is not quietly replaced, and a contrib build lights it up with no
other change.

**B2 is therefore ASIFT**: ``AffineFeature`` simulating tilts over a SIFT
backend. This is a defensible substitution on its merits rather than a
convenience. ASIFT is one of the five methods benchmarked by the published
Chandrayaan-2 matcher comparison (Makharia et al., arXiv:2509.04775), so
including it puts this project's numbers alongside an incumbent's on a shared
method; and it attacks viewpoint rather than scale space, which is the axis
§B7's relief displacement actually threatens.

B4 (learned sparse) and B6 (learned coarse-to-fine) remain absent. Note for
whoever fills them: **OpenCV 5 ships DISK, ALIKED and LightGlue in core**
(Apache-2.0 code), each loading an ONNX model supplied separately. That path
avoids SuperGlue's and original SuperPoint's non-commercial restriction
entirely -- but the ONNX weight files still need the ADR-0008 licence audit
before any of them enters this repository, and that audit is not this module's
job.

The identical-harness rule
--------------------------
Spec §49 forbids sabotaging a baseline and §E.2 makes the vanilla/wrapped
delta the measure of our own contribution. Every engine here therefore shares
the *same* ratio test, the *same* mutual-consistency check, the *same*
LO-RANSAC and the *same* seed as B1. Where an engine cannot share a stage --
B0 and B5 produce no correspondences at all -- the difference is recorded in
the result rather than papered over with a plausible-looking number.

What B0 and B5 must not be allowed to fake
------------------------------------------
Neither produces putative matches, so ``inlier_ratio`` and ``inlier_rmse`` are
**undefined** for them, not zero and not small. They are returned as NaN with
a stated reason. This matters more than it looks: a direct method that
reported a comfortable-looking inlier RMSE would be inventing precisely the
statistic ADR-0003 exists to distrust, and would then rank well on a metric it
never computed.
"""

from __future__ import annotations

import time
from typing import Callable

import cv2
import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..geometry import Transform
from ..matching.representations import phase_congruency, to_float
from ..matching.rootsift import Features, MatchSet, detect_and_describe, match_descriptors
from ..verification.ransac import RansacResult, ransac
from .rootsift_pipeline import BaselineResult, run_rootsift_baseline

__all__ = [
    "BASELINE_IDS",
    "BASELINE_ROLES",
    "akaze_available",
    "run_baseline",
    "run_identity_baseline",
    "run_asift_baseline",
    "run_akaze_baseline",
    "run_orb_baseline",
    "run_direct_baseline",
    "run_phase_congruency_baseline",
]

#: Registry order. B4 and B6 are learned and gated on the ADR-0008 licence
#: audit; they are named here so their absence is visible rather than implied.
#: B2K is present but unavailable on OpenCV core builds -- see the module
#: docstring. It is listed so the gap is legible, not hidden.
BASELINE_IDS = ("B0", "B1", "B2", "B3", "B5", "B7")
OPTIONAL_BASELINE_IDS = ("B2K", "B4L", "B4X")

BASELINE_ROLES = {
    "B0": "identity -- absolute error floor",
    "B1": "RootSIFT + ratio + LO-RANSAC -- reference classical",
    "B2": "ASIFT + ratio + LO-RANSAC -- second classical, affine-simulated",
    "B3": "ORB + ratio + LO-RANSAC -- efficiency floor",
    "B5": "phase correlation + ECC -- direct/intensity",
    "B7": "phase congruency + SIFT -- multimodal classical",
}


def akaze_available() -> bool:
    """Whether this OpenCV build exposes AKAZE (contrib in OpenCV 5)."""
    return hasattr(cv2, "AKAZE_create")


# --------------------------------------------------------------------------
# helpers shared by every engine
# --------------------------------------------------------------------------


def _empty_features(width: int) -> Features:
    return Features(points=np.zeros((0, 2)), descriptors=np.zeros((0, width), np.float32))


def _empty_matches() -> MatchSet:
    z_i = np.zeros(0, dtype=np.int64)
    z_f = np.zeros(0, dtype=np.float64)
    return MatchSet(z_i, z_i, np.zeros((0, 2)), np.zeros((0, 2)), z_f, z_f)


def _direct_result(transform: Transform | None, model: str, reason: str) -> RansacResult:
    """Wrap a transform that was found without correspondences.

    ``inlier_ratio`` and ``inlier_rmse`` stay at their NaN/zero defaults and
    ``reason`` says why. A direct method has no putative set, so those fields
    have no value -- as opposed to a small one.
    """
    return RansacResult(
        transform=transform,
        model=model,
        inlier_mask=np.zeros(0, dtype=bool),
        n_inliers=0,
        inlier_ratio=float("nan"),
        inlier_rmse=float("nan"),
        iterations=0,
        success=transform is not None,
        reason=reason,
    )


def _keypoint_engine(
    source: ArrayLike,
    reference: ArrayLike,
    *,
    describe: Callable[[ArrayLike], Features],
    norm: int,
    model: str,
    ratio: float,
    mutual: bool,
    ransac_threshold: float,
    seed: int,
) -> BaselineResult:
    """Detect, describe, match and fit -- the shared path for B1/B2/B3/B7."""
    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    f_src = describe(source)
    f_dst = describe(reference)
    timings["detect_describe_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    matches = match_descriptors(f_src, f_dst, ratio=ratio, mutual=mutual, norm=norm)
    timings["match_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    rres = ransac(
        matches.src_points,
        matches.dst_points,
        model=model,
        threshold=ransac_threshold,
        seed=seed,
    )
    timings["ransac_s"] = time.perf_counter() - t0
    timings["total_s"] = sum(timings.values())

    return BaselineResult(
        src_features=f_src,
        dst_features=f_dst,
        matches=matches,
        ransac=rres,
        runtime=timings,
    )


# --------------------------------------------------------------------------
# B0 -- identity
# --------------------------------------------------------------------------


def run_identity_baseline(source: ArrayLike, reference: ArrayLike) -> BaselineResult:
    """Do nothing, and say so. The absolute floor (§E.1 B0).

    B0 exists to calibrate what "an error" means. A method that beats B0 by a
    little on an easy pair has demonstrated very little; a method that *loses*
    to B0 has actively made the alignment worse, which is a result worth being
    able to state. Without B0 in the table there is no scale against which any
    other number can be read.
    """
    t0 = time.perf_counter()
    identity = Transform(matrix=np.eye(3, dtype=np.float64), model="euclidean")
    elapsed = time.perf_counter() - t0
    return BaselineResult(
        src_features=_empty_features(1),
        dst_features=_empty_features(1),
        matches=_empty_matches(),
        ransac=_direct_result(identity, "euclidean", "identity baseline; nothing estimated"),
        runtime={"detect_describe_s": 0.0, "match_s": 0.0, "ransac_s": 0.0, "total_s": elapsed},
    )


# --------------------------------------------------------------------------
# B2 -- ASIFT (affine-simulated SIFT)
# --------------------------------------------------------------------------


def _asift_features(image: ArrayLike, contrast_threshold: float, max_tilt: int) -> Features:
    img = _as_uint8(image)
    sift = cv2.SIFT_create(contrastThreshold=contrast_threshold)
    asift = cv2.AffineFeature_create(sift, max_tilt)
    kps, desc = asift.detectAndCompute(img, None)
    if desc is None or len(kps) == 0:
        return _empty_features(128)
    desc = desc.astype(np.float32)
    # RootSIFT on the descriptors, as B1 does, so the two differ only in the
    # affine simulation and not in the descriptor normalisation (§E.2).
    l1 = np.abs(desc).sum(axis=1, keepdims=True)
    desc = np.sqrt(desc / np.maximum(l1, 1e-12))
    return Features(
        points=np.array([kp.pt for kp in kps], dtype=np.float64),
        descriptors=desc,
        scales=np.array([kp.size for kp in kps], dtype=np.float64),
        angles=np.array([kp.angle for kp in kps], dtype=np.float64),
        responses=np.array([kp.response for kp in kps], dtype=np.float64),
    )


def run_asift_baseline(
    source: ArrayLike,
    reference: ArrayLike,
    *,
    model: str = "affine",
    ratio: float = 0.8,
    mutual: bool = True,
    ransac_threshold: float = 3.0,
    seed: int = 0,
    contrast_threshold: float = 0.04,
    max_tilt: int = 3,
) -> BaselineResult:
    """ASIFT: SIFT over simulated affine tilts (§E.1 B2, substituted).

    Why this occupies the second-classical slot, and what it costs
    -------------------------------------------------------------
    AKAZE was the §E.1 nomination and is unavailable on OpenCV core builds
    (see the module docstring). ASIFT is the substitute on two arguments: it
    is benchmarked by the published Chandrayaan-2 matcher comparison, so this
    project's numbers land beside an incumbent's on a shared method; and it
    attacks *viewpoint*, which is the axis relief displacement threatens
    (§B7), rather than re-testing scale space.

    The cost is runtime. ASIFT simulates a tilt family, so it detects on
    several warped copies of each image -- roughly an order of magnitude
    slower than B1. ``max_tilt`` is left at 3 rather than the paper's 5,
    which keeps it tractable on the CPU this project is committed to
    (ADR-0002) and is recorded here as the reason rather than presented as a
    tuned choice.
    """
    return _keypoint_engine(
        source,
        reference,
        describe=lambda im: _asift_features(im, contrast_threshold, max_tilt),
        norm=cv2.NORM_L2,
        model=model,
        ratio=ratio,
        mutual=mutual,
        ransac_threshold=ransac_threshold,
        seed=seed,
    )


# --------------------------------------------------------------------------
# B2K -- AKAZE, when the build provides it
# --------------------------------------------------------------------------


def _akaze_features(image: ArrayLike, threshold: float) -> Features:
    if not akaze_available():
        raise RuntimeError(
            "AKAZE is not present in this OpenCV build. OpenCV 5 moved AKAZE, KAZE "
            "and BRISK to opencv_contrib; install a contrib build to enable baseline "
            "B2K. B2 (ASIFT) is the available second classical detector and is not a "
            "silent substitute -- the two are separate entries in the registry."
        )
    img = _as_uint8(image)
    akaze = cv2.AKAZE_create(threshold=threshold)
    kps, desc = akaze.detectAndCompute(img, None)
    if desc is None or len(kps) == 0:
        return _empty_features(61)
    return Features(
        points=np.array([kp.pt for kp in kps], dtype=np.float64),
        descriptors=np.ascontiguousarray(desc),  # uint8 MLDB; Hamming distance
        scales=np.array([kp.size for kp in kps], dtype=np.float64),
        angles=np.array([kp.angle for kp in kps], dtype=np.float64),
        responses=np.array([kp.response for kp in kps], dtype=np.float64),
    )


def run_akaze_baseline(
    source: ArrayLike,
    reference: ArrayLike,
    *,
    model: str = "affine",
    ratio: float = 0.8,
    mutual: bool = True,
    ransac_threshold: float = 3.0,
    seed: int = 0,
    threshold: float = 0.001,
) -> BaselineResult:
    """AKAZE + ratio test + LO-RANSAC (§E.1 B2, registered as B2K).

    AKAZE builds a *nonlinear* scale space, which -- unlike SIFT's Gaussian
    pyramid -- does not blur across edges as it coarsens. On crater rims,
    whose whole signal is a strong edge, that is a plausible advantage, and it
    is the reason §20-B asks for a second classical detector rather than a
    second parameterisation of the first.

    Its descriptor (MLDB) is binary, so matching uses Hamming distance. That
    is a change of metric, not of protocol: the ratio test, the mutual check,
    the model, the threshold and the seed are all B1's.
    """
    return _keypoint_engine(
        source,
        reference,
        describe=lambda im: _akaze_features(im, threshold),
        norm=cv2.NORM_HAMMING,
        model=model,
        ratio=ratio,
        mutual=mutual,
        ransac_threshold=ransac_threshold,
        seed=seed,
    )


# --------------------------------------------------------------------------
# B3 -- ORB
# --------------------------------------------------------------------------


def _orb_features(image: ArrayLike, n_features: int, fast_threshold: int) -> Features:
    img = _as_uint8(image)
    orb = cv2.ORB_create(nfeatures=n_features, fastThreshold=fast_threshold)
    kps, desc = orb.detectAndCompute(img, None)
    if desc is None or len(kps) == 0:
        return _empty_features(32)
    return Features(
        points=np.array([kp.pt for kp in kps], dtype=np.float64),
        descriptors=np.ascontiguousarray(desc),  # uint8 rBRIEF; Hamming distance
        scales=np.array([kp.size for kp in kps], dtype=np.float64),
        angles=np.array([kp.angle for kp in kps], dtype=np.float64),
        responses=np.array([kp.response for kp in kps], dtype=np.float64),
    )


def run_orb_baseline(
    source: ArrayLike,
    reference: ArrayLike,
    *,
    model: str = "affine",
    ratio: float = 0.8,
    mutual: bool = True,
    ransac_threshold: float = 3.0,
    seed: int = 0,
    n_features: int = 20_000,
    fast_threshold: int = 20,
) -> BaselineResult:
    """ORB + ratio test + LO-RANSAC (§E.1 B3), the efficiency floor.

    A structural caveat, recorded rather than discovered later
    ---------------------------------------------------------
    ORB *requires* a feature cap and retains the strongest responses within
    it, so it concentrates keypoints in high-contrast terrain -- exactly the
    spatial bias spec §15 objects to, and the bias B1 avoids by running
    uncapped. ``n_features`` is therefore set high (20 000) to make the cap
    non-binding on the tile sizes used here, but on a texture-rich tile it can
    still bind. When it does, the coverage metrics will say so, and that is a
    property of ORB rather than a defect in this wrapper.
    """
    return _keypoint_engine(
        source,
        reference,
        describe=lambda im: _orb_features(im, n_features, fast_threshold),
        norm=cv2.NORM_HAMMING,
        model=model,
        ratio=ratio,
        mutual=mutual,
        ransac_threshold=ransac_threshold,
        seed=seed,
    )


# --------------------------------------------------------------------------
# B5 -- phase correlation seeding ECC
# --------------------------------------------------------------------------


def _as_uint8(image: ArrayLike) -> NDArray[np.uint8]:
    """Reuse the matching module's stretch so every engine sees one encoding."""
    from ..matching.rootsift import _to_uint8  # noqa: PLC0415 - deliberate reuse

    return _to_uint8(image)


def _common_extent(a: NDArray[np.float64], b: NDArray[np.float64]):
    """Crop both arrays to their shared extent.

    Phase correlation is defined for equal-sized arrays. Cropping is stated
    here rather than resizing, because resizing would introduce a scale change
    into a method that is being measured on its ability to find one.
    """
    rows = min(a.shape[0], b.shape[0])
    cols = min(a.shape[1], b.shape[1])
    return a[:rows, :cols], b[:rows, :cols]


def run_direct_baseline(
    source: ArrayLike,
    reference: ArrayLike,
    *,
    model: str = "affine",
    max_iterations: int = 200,
    epsilon: float = 1e-6,
) -> BaselineResult:
    """Phase correlation for a translation seed, then ECC refinement (§E.1 B5).

    The one direct method in the set. It never forms a correspondence, so it
    is immune to the descriptor failure mode that dominates the illumination
    axis -- and equally immune to every check built on inlier statistics. That
    combination is the reason §20-D asks for it: it fails differently, and a
    baseline suite whose members all fail the same way measures one thing
    repeatedly.

    Direction convention
    --------------------
    ECC solves ``template(x) ~= input(W(x))``. Passing the **source** as the
    template and the **reference** as the input therefore yields a ``W`` that
    maps source coordinates to reference coordinates -- which is the
    project-wide direction (contract C1). This sign is not obvious, it is the
    kind of convention error E-001 was, and there is a test that pins it to a
    known synthetic translation.

    What it returns
    ---------------
    A transform, or ``None`` when ECC fails to converge. Never an inlier
    count and never a fit RMSE: it computed neither.
    """
    timings: dict[str, float] = {"detect_describe_s": 0.0, "match_s": 0.0}
    t0 = time.perf_counter()

    src_f = to_float(_as_uint8(source)).astype(np.float32)
    dst_f = to_float(_as_uint8(reference)).astype(np.float32)
    src_c, dst_c = _common_extent(src_f, dst_f)

    # Seed: phaseCorrelate(a, b) returns the shift taking a's content to b's.
    try:
        (dx, dy), _response = cv2.phaseCorrelate(
            src_c.astype(np.float64), dst_c.astype(np.float64)
        )
    except cv2.error:  # pragma: no cover - degenerate input only
        dx = dy = 0.0

    motion = cv2.MOTION_AFFINE if model in ("affine", "projective") else cv2.MOTION_EUCLIDEAN
    warp = np.eye(2, 3, dtype=np.float32)
    warp[0, 2] = float(dx)
    warp[1, 2] = float(dy)

    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, max_iterations, epsilon)
    transform: Transform | None = None
    reason = ""
    try:
        _cc, warp = cv2.findTransformECC(src_c, dst_c, warp, motion, criteria, None, 5)
        matrix = np.eye(3, dtype=np.float64)
        matrix[:2, :] = warp.astype(np.float64)
        transform = Transform(matrix=matrix, model="affine" if motion == cv2.MOTION_AFFINE else "euclidean")
    except cv2.error as exc:
        reason = f"ECC did not converge: {exc.err.strip() if hasattr(exc, 'err') else exc}"

    timings["ransac_s"] = time.perf_counter() - t0
    timings["total_s"] = sum(timings.values())

    return BaselineResult(
        src_features=_empty_features(1),
        dst_features=_empty_features(1),
        matches=_empty_matches(),
        ransac=_direct_result(
            transform,
            "affine" if motion == cv2.MOTION_AFFINE else "euclidean",
            reason or "direct method; no putative set, so no inlier statistics exist",
        ),
        runtime=timings,
    )


# --------------------------------------------------------------------------
# B7 -- phase congruency, then SIFT on that map
# --------------------------------------------------------------------------


def _phase_congruency_features(
    image: ArrayLike, *, n_scale: int, n_orient: int, contrast_threshold: float
) -> Features:
    pc = phase_congruency(image, n_scale=n_scale, n_orient=n_orient)
    return detect_and_describe(pc.pc, root_sift=True, contrast_threshold=contrast_threshold)


def run_phase_congruency_baseline(
    source: ArrayLike,
    reference: ArrayLike,
    *,
    model: str = "affine",
    ratio: float = 0.8,
    mutual: bool = True,
    ransac_threshold: float = 3.0,
    seed: int = 0,
    n_scale: int = 4,
    n_orient: int = 6,
    contrast_threshold: float = 0.01,
) -> BaselineResult:
    """Phase congruency, then RootSIFT on the congruency map (§E.1 B7).

    The multimodal-classical slot -- the one §12 notes most teams omit. Phase
    congruency responds to *where the local Fourier components are in phase*,
    which is a structural property of an edge rather than a property of its
    contrast. Two images of the same crater rim under different Sun angles
    have very different gradient magnitudes there and similar phase
    congruency, which is the whole argument for the family.

    Honest naming
    -------------
    This is **not** RIFT2. RIFT2 builds a rotation-invariant descriptor from
    the per-orientation log-Gabor amplitudes; this runs an ordinary RootSIFT
    over the scalar congruency map. It is the cheap member of the family and
    should be reported as "phase congruency + RootSIFT", never as RIFT. The
    log-Gabor bank underneath is the same one EXP-003 used, so this arm
    inherits that stage's measured behaviour rather than introducing a new
    untested filter.

    ``contrast_threshold`` is lowered from B1's 0.04 because the congruency
    map occupies [0, 1] with far lower dynamic range than an intensity image;
    keeping SIFT's intensity-tuned default would starve the detector and
    produce an artificially weak arm, which §49 forbids.
    """
    return _keypoint_engine(
        source,
        reference,
        describe=lambda im: _phase_congruency_features(
            im, n_scale=n_scale, n_orient=n_orient, contrast_threshold=contrast_threshold
        ),
        norm=cv2.NORM_L2,
        model=model,
        ratio=ratio,
        mutual=mutual,
        ransac_threshold=ransac_threshold,
        seed=seed,
    )


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------

def _run_learned(source, reference, **kwargs) -> BaselineResult:
    """B4L: DISK + LightGlue (Apache-2.0), imported lazily so the package
    never requires torch. B4/B6 (SuperGlue-family) stay refused."""
    from .learned import run_disk_lightglue_baseline
    return run_disk_lightglue_baseline(source, reference, **kwargs)


def _run_xfeat(source, reference, **kwargs) -> BaselineResult:
    """B4X: XFeat (Apache-2.0, pinned commit), imported lazily like B4L."""
    from .xfeat import run_xfeat_baseline
    return run_xfeat_baseline(source, reference, **kwargs)


_ENGINES: dict[str, Callable[..., BaselineResult]] = {
    "B0": run_identity_baseline,
    "B1": run_rootsift_baseline,
    "B2": run_asift_baseline,
    "B2K": run_akaze_baseline,
    "B3": run_orb_baseline,
    "B5": run_direct_baseline,
    "B7": run_phase_congruency_baseline,
    "B4L": _run_learned,
    "B4X": _run_xfeat,
}


def run_baseline(name: str, source: ArrayLike, reference: ArrayLike, **kwargs) -> BaselineResult:
    """Dispatch to a baseline by its §E.1 identifier.

    One entry point so a sweep cannot accidentally give one arm a different
    harness from another -- the failure mode §E.2 is built to prevent. Unknown
    identifiers raise rather than falling back to a default, because a silent
    fallback would report a comparison that never ran.
    """
    key = name.upper()
    if key not in _ENGINES:
        raise KeyError(
            f"unknown baseline {name!r}; expected one of {', '.join(BASELINE_IDS)}. "
            "B4 and B6 are learned engines and remain gated on the ADR-0008 licence audit."
        )
    return _ENGINES[key](source, reference, **kwargs)
