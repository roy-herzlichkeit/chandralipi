"""LoFTR: detector-free dense matching, via kornia.

LoFTR (Sun et al., CVPR 2021) skips keypoint detection entirely and matches
dense coarse features with a transformer, then refines to sub-pixel. That makes
it strong exactly where detector-based methods are weak -- low-texture terrain
such as smooth mare, where SIFT finds nothing to key on.

Licensing
---------
Clean. LoFTR is Apache-2.0 (zju3dv/LoFTR) and kornia, which packages the weights,
is Apache-2.0. Both are redistributable, unlike SuperGlue -- see
:mod:`lunar_reg.match.superglue`.

VRAM
----
This is the most memory-hungry matcher in the project, because the coarse-level
correspondence matrix is quadratic in the number of coarse tokens and therefore
**quartic in tile side**. :attr:`LoFTRMatcher.max_tile_px` derives a safe tile
size from measured free memory rather than a constant, and :meth:`match` refuses
oversized input instead of letting CUDA OOM mid-run.

See :mod:`lunar_reg.match.memory` for how the figures in
``docs/VRAM_CONSTRAINTS.md`` were obtained, and what is measured versus modelled
on a machine with no working GPU.
"""

from __future__ import annotations

import logging
from contextlib import nullcontext

import numpy as np

from lunar_reg.device import get_device, plan_dense_tile
from lunar_reg.match.base import MatchResult

logger = logging.getLogger(__name__)

#: Pretrained weight sets kornia ships. ``outdoor`` is the right prior for
#: orbital imagery; ``indoor`` is trained on room-scale scenes and transfers
#: poorly to terrain.
LOFTR_WEIGHTS = ("outdoor", "indoor")

#: LoFTR's coarse level runs at 1/8 input resolution. This constant appears in
#: the cost model, so it lives next to the code that depends on it.
COARSE_STRIDE = 8


def to_tensor(image: np.ndarray, device: str):
    """Single-band image -> normalised ``(1, 1, H, W)`` float tensor."""
    import torch

    arr = np.asarray(image, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr.mean(axis=-1)
    if arr.max() > 1.0:
        arr = arr / 255.0
    return torch.from_numpy(np.ascontiguousarray(arr))[None, None].to(device)


def pad_to_multiple(image: np.ndarray, multiple: int = COARSE_STRIDE):
    """Pad an image so both sides divide by ``multiple``.

    LoFTR's feature pyramid requires it. Returns ``(padded, (pad_y, pad_x))`` so
    the caller can discard matches that landed in the padding -- those are
    matches against fabricated content and must not reach the transform fit.
    """
    h, w = image.shape[:2]
    pad_y = (-h) % multiple
    pad_x = (-w) % multiple
    if pad_y == 0 and pad_x == 0:
        return image, (0, 0)
    return np.pad(image, ((0, pad_y), (0, pad_x)), mode="edge"), (pad_y, pad_x)


class LoFTRMatcher:
    """Dense detector-free matching.

    Satisfies :class:`lunar_reg.match.base.Matcher`, so it is interchangeable
    with the classical matchers and composes with
    :class:`~lunar_reg.match.tiled.TiledMatcher`.

    Correspondences come out dense and well spread *within a tile*, which suits
    the uniform-distribution requirement -- but whole-image uniformity still
    depends on the tiling, since a tile over featureless mare contributes
    nothing regardless of the matcher.
    """

    def __init__(
        self,
        weights: str = "outdoor",
        device: str | None = None,
        confidence: float = 0.5,
        precision: str = "fp16",
    ) -> None:
        if weights not in LOFTR_WEIGHTS:
            raise ValueError(f"weights must be one of {LOFTR_WEIGHTS}, got {weights!r}")
        self.weights = weights
        self.device = device or get_device()
        self.confidence = confidence
        # fp16 autocast is a CUDA feature; on CPU it is either unsupported or
        # slower, so the request is silently downgraded rather than failing.
        self.precision = precision if self.device == "cuda" else "fp32"
        self.name = f"loftr/{weights}"
        self._model = None

    @property
    def max_tile_px(self) -> int:
        """Largest square tile this matcher should be given on the current device."""
        return plan_dense_tile(self.device, self.precision, self.name).tile_px

    def _get_model(self):
        if self._model is None:
            import kornia.feature as KF

            logger.info("loading LoFTR(%s) onto %s", self.weights, self.device)
            self._model = KF.LoFTR(pretrained=self.weights).to(self.device).eval()
        return self._model

    def match(self, source: np.ndarray, reference: np.ndarray) -> MatchResult:
        import torch

        limit = self.max_tile_px
        for name, image in (("source", source), ("reference", reference)):
            h, w = image.shape[:2]
            if max(h, w) > limit:
                raise ValueError(
                    f"{self.name}: {name} is {h}x{w} but the memory budget allows at "
                    f"most {limit}px on this device. Tile the input "
                    f"(lunar_reg.match.tiled.TiledMatcher) rather than raising the cap "
                    f"-- cost grows as the fourth power of tile side."
                )

        src_padded, (src_pad_y, src_pad_x) = pad_to_multiple(source)
        ref_padded, _ = pad_to_multiple(reference)

        model = self._get_model()
        autocast = (
            torch.autocast("cuda", dtype=torch.float16)
            if (self.device == "cuda" and self.precision == "fp16")
            else nullcontext()
        )

        with torch.inference_mode(), autocast:
            output = model({
                "image0": to_tensor(src_padded, self.device),
                "image1": to_tensor(ref_padded, self.device),
            })
            src_pts = output["keypoints0"].float().cpu().numpy()
            dst_pts = output["keypoints1"].float().cpu().numpy()
            confidence = output["confidence"].float().cpu().numpy()

        if self.device == "cuda":
            # Dense activations are large and short-lived; releasing them stops
            # the next tile tripping over allocator fragmentation.
            torch.cuda.empty_cache()

        keep = confidence >= self.confidence
        if src_pad_y or src_pad_x:
            # Discard anything that landed in the edge padding -- those are
            # matches against fabricated pixels.
            h, w = source.shape[:2]
            keep &= (src_pts[:, 0] < w) & (src_pts[:, 1] < h)

        return MatchResult(
            src_pts=src_pts[keep],
            dst_pts=dst_pts[keep],
            scores=confidence[keep],
            matcher=self.name,
            meta={
                "detector": "loftr",
                "confidence_threshold": self.confidence,
                "precision": self.precision,
                "device": self.device,
            },
        )


def estimated_peak_bytes(tile_px: int, precision: str = "fp16") -> int:
    """Model of LoFTR's peak allocation for one square tile.

    A *model*, not a measurement -- see :mod:`lunar_reg.match.memory` for the
    measured figures. Kept because the quartic scaling is the thing to reason
    about when choosing a tile size, and it is easy to get wrong by intuition.
    """
    from lunar_reg.device import dense_matcher_peak_bytes

    return dense_matcher_peak_bytes(tile_px, precision)
