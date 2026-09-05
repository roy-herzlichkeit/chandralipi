"""Scale alignment between sensors.

Scale ratios here are extreme -- OHRC to IIRS is roughly 320x. No detector is
invariant across that range, so the pipeline closes most of the gap by
resampling before matching and leaves only a residual factor for the matcher to
absorb.
"""

from __future__ import annotations

import logging

import numpy as np

from lunar_reg.constants import MAX_SAFE_SCALE_RATIO, SENSORS

logger = logging.getLogger(__name__)


def to_common_gsd(
    image: np.ndarray,
    src_gsd_m: float,
    target_gsd_m: float,
) -> np.ndarray:
    """Resample an image from ``src_gsd_m`` to ``target_gsd_m`` ground sampling.

    Downsampling uses ``INTER_AREA``, which integrates over the source footprint
    and is the correct choice when shrinking; ``INTER_LINEAR`` at a 20x
    reduction aliases badly and manufactures false corners. Upsampling uses
    ``INTER_CUBIC``.
    """
    import cv2

    if src_gsd_m <= 0 or target_gsd_m <= 0:
        raise ValueError("GSD values must be positive")

    factor = src_gsd_m / target_gsd_m
    if abs(factor - 1.0) < 1e-6:
        return image

    h, w = image.shape[:2]
    new_size = (max(1, int(round(w * factor))), max(1, int(round(h * factor))))
    interp = cv2.INTER_AREA if factor < 1.0 else cv2.INTER_CUBIC
    return cv2.resize(image, new_size, interpolation=interp)


def match_scale(
    source: np.ndarray,
    reference: np.ndarray,
    source_sensor: str,
    reference_sensor: str,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Bring a sensor pair onto the coarser of their two grids.

    Returns ``(source, reference, applied_ratio)``. Resampling *down* to the
    coarser grid rather than up to the finer one is deliberate: upsampling OHRC
    to IIRS scale would inflate a tile 320x in each axis and blow the memory
    budget without adding any real information.
    """
    src_gsd = SENSORS[source_sensor].gsd_m
    ref_gsd = SENSORS[reference_sensor].gsd_m
    common = max(src_gsd, ref_gsd)
    ratio = max(src_gsd, ref_gsd) / min(src_gsd, ref_gsd)

    if ratio > MAX_SAFE_SCALE_RATIO:
        logger.warning(
            "scale ratio %s->%s is %.1fx, above the %.1fx single-hop limit; "
            "consider bridging via TMC-2 rather than matching directly",
            source_sensor,
            reference_sensor,
            ratio,
            MAX_SAFE_SCALE_RATIO,
        )

    return (
        to_common_gsd(source, src_gsd, common),
        to_common_gsd(reference, ref_gsd, common),
        ratio,
    )


def paper_target_gsd(source_sensor: str | None, reference_sensor: str | None) -> float | None:
    """The resampling target Makharia et al. state for a sensor pair, in m/pixel.

    The paper gives a target for each pair it registers (its section 4.1.2).
    Returns ``None`` for a pair the paper does not cover -- callers must then
    supply an explicit target rather than have one invented for them.
    """
    from lunar_reg.preprocess.params import RESAMPLE_TARGETS

    if source_sensor is None or reference_sensor is None:
        return None
    param = RESAMPLE_TARGETS.get((source_sensor, reference_sensor))
    if param is None:
        logger.debug(
            "no paper-stated resampling target for %s -> %s; supply target_gsd_m",
            source_sensor, reference_sensor,
        )
        return None
    return float(param.value)
