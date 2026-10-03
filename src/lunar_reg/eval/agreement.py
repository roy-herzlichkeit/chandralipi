"""Cross-matcher agreement on the pre-ECC transforms (docs/plan/CONTRACTS.md C14).

Real lunar pairs have no ground truth. One of the few independent consistency
signals is whether different matchers land on the same transform *before* ECC
refinement: ECC pulls every matcher to the same solution, so post-ECC
agreement says nothing (Phase_1/LLD/agreement.md). This module therefore only
ever takes the pre-ECC matrices (C04 ``PairResult.pre_ecc_transform``).

Each transform maps five probes -- the four source-image corners and the
centre -- into reference pixels. Two matchers disagree by the largest distance
between their mapped probes; the agreement figure is the largest such value
over every pair of matchers.

A transform with a non-finite entry, a singular 3x3 matrix, or one that maps a
probe to a non-finite point is skipped with a warning naming the matcher; it is
not listed in ``matchers`` and does not count toward ``n_matchers``.
"""

from __future__ import annotations

import itertools
import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from lunar_reg.align.estimate import Transform

if TYPE_CHECKING:
    from lunar_reg.results import PairResult

logger = logging.getLogger(__name__)

#: |det| below this marks a 3x3 transform as singular.
_SINGULAR_DET = 1e-12


@dataclass
class AgreementResult:
    matchers: tuple[str, ...]
    pairwise_px: dict[str, float]  # "a|b" (sorted names) -> max probe distance, reference px
    max_disagreement_px: float  # nan when fewer than 2 transforms
    threshold_px: float
    passes: bool  # n_matchers >= 2 and max_disagreement_px <= threshold_px
    n_matchers: int
    gsd_m: float | None
    max_disagreement_m: float | None


def _probes(shape: tuple[int, int]) -> np.ndarray:
    h, w = int(shape[0]), int(shape[1])
    return np.array(
        [
            [0.0, 0.0],
            [w - 1.0, 0.0],
            [0.0, h - 1.0],
            [w - 1.0, h - 1.0],
            [(w - 1.0) / 2.0, (h - 1.0) / 2.0],
        ],
        dtype=np.float64,
    )


def _wrap(matrix: np.ndarray) -> Transform:
    """Wrap a raw matrix so :meth:`Transform.apply` maps points with it."""
    model = "homography" if matrix.shape == (3, 3) else "affine"
    return Transform(matrix=matrix, model=model, n_inliers=0, n_total=0)


def _skip_reason(matrix: np.ndarray) -> str | None:
    if not np.all(np.isfinite(matrix)):
        return "non-finite entry"
    if matrix.shape == (3, 3) and abs(float(np.linalg.det(matrix))) < _SINGULAR_DET:
        return "singular 3x3"
    return None


def cross_matcher_agreement(
    transforms: dict[str, np.ndarray],
    shape: tuple[int, int],
    *,
    threshold_px: float = 1.0,
    gsd_m: float | None = None,
) -> AgreementResult:
    """Pre-ECC disagreement between matchers, in reference pixels (C14).

    ``transforms`` maps matcher name to a 3x3 (projective) or 2x3 (affine)
    source-to-reference matrix; ``shape`` is the source image ``(h, w)``.
    Raises :class:`ValueError` for a matrix that is neither 3x3 nor 2x3.
    """
    probes = _probes(shape)
    mapped: dict[str, np.ndarray] = {}
    for name in sorted(transforms):
        matrix = np.asarray(transforms[name], dtype=np.float64)
        if matrix.shape not in ((3, 3), (2, 3)):
            raise ValueError(f"{name}: transform must be 3x3 or 2x3, got {matrix.shape}")
        reason = _skip_reason(matrix)
        pts = None
        if reason is None:
            with np.errstate(divide="ignore", invalid="ignore"):
                pts = _wrap(matrix).apply(probes)
            if not np.all(np.isfinite(pts)):
                reason = "probe maps to a non-finite point"
        if reason is not None:
            logger.warning("cross_matcher_agreement: skipped matcher %r (%s)", name, reason)
            continue
        mapped[name] = pts

    names = tuple(sorted(mapped))
    pairwise: dict[str, float] = {}
    for a, b in itertools.combinations(names, 2):
        dist = np.linalg.norm(mapped[a] - mapped[b], axis=1)
        pairwise[f"{a}|{b}"] = float(dist.max())

    n = len(names)
    max_px = max(pairwise.values()) if pairwise else math.nan
    passes = bool(n >= 2 and max_px <= threshold_px)
    max_m = None if gsd_m is None else float(max_px * gsd_m)
    return AgreementResult(
        matchers=names,
        pairwise_px=pairwise,
        max_disagreement_px=float(max_px),
        threshold_px=float(threshold_px),
        passes=passes,
        n_matchers=n,
        gsd_m=None if gsd_m is None else float(gsd_m),
        max_disagreement_m=max_m,
    )


def agreement_for_stored(results: list[PairResult], threshold_px: float = 1.0) -> AgreementResult:
    """Cross-matcher agreement over stored results of one source/reference pair.

    Uses each result's ``pre_ecc_transform``; v1 records (where it is None) are
    skipped. The source shape is ``source_image.shape[:2]`` divided by
    ``extra["source_scale"]`` (the C04 loader's thumbnail scale, default 1.0) and
    rounded; ``gsd_m`` comes from ``extra["gsd_m"]``.

    Raises :class:`ValueError` when the results do not share ``source_id`` and
    ``reference_id``, when two usable results name the same matcher, or when no
    usable result carries a ``source_image`` to take the shape from.
    """
    pairs = {(r.source_id, r.reference_id) for r in results}
    if len(pairs) > 1:
        raise ValueError(
            f"agreement_for_stored: results span several source/reference pairs: {sorted(pairs)}"
        )

    usable = [r for r in results if r.pre_ecc_transform is not None]
    n_v1 = len(results) - len(usable)
    if n_v1:
        logger.info("agreement_for_stored: %d result(s) without pre_ecc_transform skipped", n_v1)

    # Names are matcher names (LLD §2), so two usable results with one matcher
    # (e.g. site-runner variants `_<model>` / `_pp-<preset>` of one strip) are
    # ambiguous; the caller must pass one result per matcher (Q-P1.12-1).
    transforms: dict[str, np.ndarray] = {}
    pair_ids: dict[str, str] = {}
    for r in usable:
        if r.matcher in transforms:
            raise ValueError(
                f"agreement_for_stored: matcher {r.matcher!r} appears twice "
                f"(pair_ids {pair_ids[r.matcher]!r}, {r.pair_id!r}); pass one result per matcher"
            )
        transforms[r.matcher] = np.asarray(r.pre_ecc_transform, dtype=np.float64)
        pair_ids[r.matcher] = r.pair_id

    shape: tuple[int, int] = (0, 0)
    gsd_m: float | None = None
    if usable:
        with_image = [r for r in usable if r.source_image is not None]
        if not with_image:
            raise ValueError("agreement_for_stored: no result carries a source_image for shape")
        first = with_image[0]
        scale = float(first.extra.get("source_scale", 1.0))
        h, w = first.source_image.shape[:2]
        shape = (round(h / scale), round(w / scale))
        gsd_values = [r.extra.get("gsd_m") for r in usable if r.extra.get("gsd_m") is not None]
        gsd_m = float(gsd_values[0]) if gsd_values else None

    return cross_matcher_agreement(transforms, shape, threshold_px=threshold_px, gsd_m=gsd_m)
