"""Synthetic lunar scenes with controllable illumination.

WHAT THIS IS AND IS NOT
-----------------------
This is **not** lunar data. It is a height field rendered under a Lambertian
shading model with ray-marched cast shadows, which reproduces the one property
the problem statement cares about: the same terrain looks radically different,
and in places *contrast-inverted*, when the sun moves.

Its purpose is error attribution. On real Chandrayaan-2 pairs there is no
ground-truth transform, so a measured RMSE cannot be split between "the matcher
mislocated the point" and "the true transform is not what we assumed". Here the
transform is exact by construction, so every stage's contribution is separable.

Conclusions drawn from these scenes transfer only as far as the shading model
does. Specifically it omits: real lunar photometry (the Moon is strongly
backscattering, closer to Lommel-Seeliger/Hapke than Lambert), regolith opposition
surge, albedo variation independent of topography, detector noise and MTF, and
the pushbroom geometry that makes a real OHRC strip non-projective. Where a
result depends on the shading model it is flagged at the point of use.
"""

from __future__ import annotations

import logging
import math

import numpy as np

logger = logging.getLogger(__name__)

#: Peak-to-trough relief **in pixel units**, which is the unit that matters:
#: shading depends on slope, so a height field must be scaled against the same
#: axis as x and y or the surface comes out flat and every sun angle renders the
#: same. 40 px of relief across a 512 px scene gives crater walls around 20-30
#: degrees, which is steep for the Moon but is what makes a 6-degree sun throw
#: the deep shadows a near-terminator scene actually has.
DEFAULT_RELIEF = 40.0


def fractal_terrain(
    shape: tuple[int, int], octaves: int = 6, seed: int = 0, persistence: float = 0.55
) -> np.ndarray:
    """Value-noise height field, roughly 1/f. Returns floats in ``[0, 1]``."""
    import cv2

    rng = np.random.default_rng(seed)
    height, width = shape
    field = np.zeros(shape, dtype=np.float32)
    amplitude, total = 1.0, 0.0

    for octave in range(octaves):
        cells = 2 ** (octave + 1)
        coarse = rng.random((cells, cells)).astype(np.float32)
        field += amplitude * cv2.resize(coarse, (width, height), interpolation=cv2.INTER_CUBIC)
        total += amplitude
        amplitude *= persistence

    field /= total
    lo, hi = float(field.min()), float(field.max())
    return (field - lo) / (hi - lo + 1e-12)


def add_craters(
    height: np.ndarray, n: int = 45, seed: int = 0, min_radius: int = 10, max_radius: int = 60
) -> np.ndarray:
    """Stamp bowl-shaped depressions with raised rims into a height field.

    The rim matters more than the bowl. A rim is a closed convex ridge, so under
    any sun angle exactly half of it is lit and half shadowed -- and which half
    swaps when the azimuth swings. That swap is the specific failure mode that
    breaks intensity-gradient descriptors, and it is why this generator exists
    rather than a plain noise field.
    """
    out = height.astype(np.float32).copy()
    rows, cols = out.shape
    rng = np.random.default_rng(seed)

    yy, xx = np.mgrid[0:rows, 0:cols].astype(np.float32)
    for _ in range(n):
        cy = float(rng.uniform(0, rows))
        cx = float(rng.uniform(0, cols))
        radius = float(rng.uniform(min_radius, max_radius))
        depth = 0.10 * (radius / max_radius)

        r = np.hypot(yy - cy, xx - cx) / radius
        bowl = np.where(r < 1.0, -depth * (1.0 - r**2), 0.0)
        # Rim: a narrow raised annulus just outside the bowl.
        rim = 0.45 * depth * np.exp(-(((r - 1.05) / 0.16) ** 2))
        out += (bowl + rim).astype(np.float32)

    lo, hi = float(out.min()), float(out.max())
    return (out - lo) / (hi - lo + 1e-12)


def _cast_shadow_mask(
    height: np.ndarray, azimuth_deg: float, elevation_deg: float, relief: float, steps: int = 64
) -> np.ndarray:
    """Ray-march towards the sun; mark pixels whose line of sight is blocked.

    Without this a low sun merely darkens the scene uniformly. Real
    near-terminator imagery has hard-edged black shadows whose *boundaries* are
    strong image gradients that do not correspond to any terrain edge -- they
    move as the sun moves. Those false edges are what a matcher latches onto and
    then mislocates, so omitting them would make the whole experiment optimistic.
    """
    rows, cols = height.shape
    azimuth = math.radians(azimuth_deg)
    # Image convention: azimuth 0 = from the north (up), increasing clockwise.
    dx, dy = math.sin(azimuth), -math.cos(azimuth)
    tan_elev = math.tan(math.radians(max(elevation_deg, 0.5)))

    scaled = height * relief
    blocked = np.zeros((rows, cols), dtype=bool)
    yy, xx = np.mgrid[0:rows, 0:cols].astype(np.float32)

    for step in range(1, steps + 1):
        sample_x = np.clip(xx + dx * step, 0, cols - 1).astype(np.int32)
        sample_y = np.clip(yy + dy * step, 0, rows - 1).astype(np.int32)
        # A blocker must rise above the sun ray's height at that distance.
        ray_height = scaled + step * tan_elev
        blocked |= scaled[sample_y, sample_x] > ray_height
    return blocked


def hillshade(
    height: np.ndarray,
    azimuth_deg: float = 315.0,
    elevation_deg: float = 45.0,
    relief: float = DEFAULT_RELIEF,
    cast_shadows: bool = True,
    ambient: float = 0.04,
    albedo: np.ndarray | None = None,
) -> np.ndarray:
    """Render a height field as an 8-bit image under one sun position.

    Lambertian: brightness is the cosine of the angle between the surface normal
    and the sun direction, clipped at zero. ``ambient`` keeps shadows just above
    pure black, as detector noise and scattered light do in practice.

    ``albedo`` multiplies the shading and is the scene's only illumination-
    *invariant* content. Passing ``None`` makes every image feature a product of
    the sun position, which is a worst case rather than a realistic one -- real
    regolith has intrinsic brightness variation (mare/highland contrast, fresh
    ejecta rays, immature crater interiors) that survives an illumination change
    and gives a matcher something stable to hold onto. See
    :func:`illumination_pair`'s ``albedo_strength``.
    """
    scaled = (height * relief).astype(np.float32)
    dzdy, dzdx = np.gradient(scaled)

    azimuth = math.radians(azimuth_deg)
    elevation = math.radians(elevation_deg)
    sun = np.array([
        math.cos(elevation) * math.sin(azimuth),
        -math.cos(elevation) * math.cos(azimuth),
        math.sin(elevation),
    ], dtype=np.float32)

    normal = np.dstack([-dzdx, -dzdy, np.ones_like(scaled)])
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    shade = np.clip(normal @ sun, 0.0, 1.0)

    if cast_shadows:
        shade[_cast_shadow_mask(height, azimuth_deg, elevation_deg, relief)] = 0.0

    shade = ambient + (1.0 - ambient) * shade
    if albedo is not None:
        shade = shade * albedo
    return np.clip(shade * 255.0, 0, 255).astype(np.uint8)


def illumination_pair(
    shape: tuple[int, int] = (512, 512),
    seed: int = 0,
    source_sun: tuple[float, float] = (285.0, 6.0),
    reference_sun: tuple[float, float] = (105.0, 62.0),
    homography: np.ndarray | None = None,
    relief: float = DEFAULT_RELIEF,
    albedo_strength: float = 0.35,
):
    """A near-terminator / high-sun pair of the same terrain, with exact truth.

    Defaults put the two suns 180 degrees apart in azimuth and 56 degrees apart
    in elevation: the source is a 6-degree grazing illumination with deep cast
    shadows, the reference a 62-degree near-overhead view where relief nearly
    vanishes. Crater rims lit on one side in the first are lit on the opposite
    side in the second. This is the hard end of the problem statement's
    "illumination variation", chosen deliberately over a mild case.

    ``albedo_strength`` sets how much intrinsic surface brightness variation the
    scene has, as a fraction: 0.0 means every feature is pure shading and
    disappears when the sun moves, 0.35 means brightness varies by about +/-35%
    independently of illumination. **This parameter dominates the difficulty of
    the pair** -- at 0.0 classical detectors find no correct match at all, which
    is a property of the scene rather than a finding about the detectors. Real
    lunar imagery is not at 0.0, so results should be read as a function of it.

    Returns ``(source, reference, homography, height)``. The homography maps
    source pixels to reference pixels and is exact.
    """
    import cv2

    height = add_craters(fractal_terrain(shape, seed=seed), seed=seed + 1)

    albedo = None
    if albedo_strength > 0:
        # Independent noise field, at a finer scale than the terrain so it is
        # not merely a proxy for the topography the shading already encodes.
        texture = fractal_terrain(shape, octaves=7, seed=seed + 91)
        albedo = (1.0 - albedo_strength + 2.0 * albedo_strength * texture).astype(np.float32)

    source = hillshade(height, *source_sun, relief=relief, albedo=albedo)

    if homography is None:
        homography = np.array(
            [[1.03, 0.012, 9.0], [-0.018, 0.995, -6.0], [1.2e-5, -8.0e-6, 1.0]]
        )

    # Warp the *terrain*, then light it. Warping the rendered image instead
    # would carry the source's shadows into the reference, which would make the
    # pair far easier than it should be and quietly invalidate the experiment.
    warped_height = cv2.warpPerspective(
        height, homography, (shape[1], shape[0]), flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REFLECT,
    )
    warped_albedo = None
    if albedo is not None:
        warped_albedo = cv2.warpPerspective(
            albedo, homography, (shape[1], shape[0]), flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REFLECT,
        )
    reference = hillshade(
        warped_height, *reference_sun, relief=relief, albedo=warped_albedo
    )
    return source, reference, homography, height


__all__ = [
    "DEFAULT_RELIEF",
    "add_craters",
    "fractal_terrain",
    "hillshade",
    "illumination_pair",
]
