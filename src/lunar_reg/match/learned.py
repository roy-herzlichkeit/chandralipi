"""Learned matchers (LoFTR, DISK+LightGlue) via kornia.

VRAM CONSTRAINT -- the tightest in the project.

Both families here are zero-shot: pretrained weights, no training run, which is
what makes the "POC in days on an RTX 4060" claim hold. What does *not* come
for free is memory:

* :class:`LoFTRMatcher` is dense. Cost grows as the fourth power of tile side
  (see :mod:`lunar_reg.device`). Do not hand it a raw OHRC strip; feed it tiles
  sized by :func:`~lunar_reg.device.plan_dense_tile`.
* :class:`LightGlueMatcher` is sparse. Cost grows with the square of keypoint
  count, which is far cheaper -- prefer it when a scene needs large tiles.

Every forward pass runs under ``inference_mode``. DISK runs under fp16 autocast
on CUDA; LightGlue always runs in fp32 (kornia's positional encoding is fp32).
LoFTR runs under fp16 autocast on CUDA when ``precision="fp16"``. Inference mode
and autocast are load-bearing for fitting in 8 GB, not incidental optimisations.
"""

from __future__ import annotations

import logging
from contextlib import nullcontext

import numpy as np

from lunar_reg.device import get_device, plan_dense_tile, plan_keypoint_budget
from lunar_reg.match.base import MatchResult
from lunar_reg.preprocess.radiometric import to_uint8

logger = logging.getLogger(__name__)

#: LoFTR's pretrained weight sets. ``outdoor`` is the right prior for orbital
#: imagery; ``indoor`` is trained on room-scale scenes and transfers poorly.
LOFTR_WEIGHTS = ("outdoor", "indoor")

#: LoFTR's coarse level runs at 1/8 resolution, so inputs are padded to this.
LOFTR_PAD_MULTIPLE = 8


def _to_tensor(image: np.ndarray, device: str):
    """Single-band image -> ``(1, 1, H, W)`` float32 tensor in ``[0, 1]``.

    uint8 input is divided by 255. Anything else goes through
    :func:`~lunar_reg.preprocess.radiometric.to_uint8` first (NaN-safe
    percentile stretch), so every matcher sees the same normalisation whatever
    the input's bit depth.
    """
    import torch

    arr = np.asarray(image)
    is_uint8 = arr.dtype == np.uint8
    if arr.ndim == 3:
        arr = arr.mean(axis=-1)
    u8 = arr.astype(np.uint8) if is_uint8 else to_uint8(arr)
    out = u8.astype(np.float32) / np.float32(255.0)
    return torch.from_numpy(np.ascontiguousarray(out))[None, None].to(device)


def _pad_to_multiple(tensor, multiple: int):
    """Zero-pad a ``(1, C, H, W)`` tensor on the bottom/right to a multiple of ``multiple``."""
    import torch.nn.functional as F

    h, w = tensor.shape[-2:]
    pad_h, pad_w = (-h) % multiple, (-w) % multiple
    if not (pad_h or pad_w):
        return tensor
    return F.pad(tensor, (0, pad_w, 0, pad_h))


def _drop_outside(features, shape: tuple[int, int]):
    """Keep only DISK keypoints inside the unpadded ``(H, W)`` image."""
    import kornia.feature as KF

    h, w = shape
    kp = features.keypoints
    keep = (kp[:, 0] < w) & (kp[:, 1] < h)
    if bool(keep.all()):
        return features
    return KF.DISKFeatures(kp[keep], features.descriptors[keep], features.detection_scores[keep])


class LoFTRMatcher:
    """Dense detector-free matching.

    Produces dense, well-spread correspondences, which suits the
    uniform-distribution requirement directly -- but only within one tile, so
    whole-image uniformity still depends on the tiling in
    :mod:`lunar_reg.match.tiled`.
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

            self._model = KF.LoFTR(pretrained=self.weights).to(self.device).eval()
        return self._model

    def match(self, source: np.ndarray, reference: np.ndarray) -> MatchResult:
        import torch

        h, w = source.shape[:2]
        limit = self.max_tile_px
        if max(h, w) > limit:
            raise ValueError(
                f"{self.name}: input is {h}x{w} but the VRAM budget allows at most "
                f"{limit}px on this device. Tile the input first "
                f"(lunar_reg.match.tiled.TiledMatcher) rather than raising the cap."
            )

        model = self._get_model()
        autocast = (
            torch.autocast("cuda", dtype=torch.float16)
            if (self.device == "cuda" and self.precision == "fp16")
            else nullcontext()
        )

        # LoFTR's feature pyramid needs both sides divisible by 8. Zero-pad
        # bottom/right so coordinates are unchanged; matches that land in the
        # padding are against fabricated pixels and are dropped below.
        t0 = _pad_to_multiple(_to_tensor(source, self.device), LOFTR_PAD_MULTIPLE)
        t1 = _pad_to_multiple(_to_tensor(reference, self.device), LOFTR_PAD_MULTIPLE)

        with torch.inference_mode(), autocast:
            out = model({"image0": t0, "image1": t1})
            src = out["keypoints0"].float().cpu().numpy()
            dst = out["keypoints1"].float().cpu().numpy()
            conf = out["confidence"].float().cpu().numpy()

        if self.device == "cuda":
            # Dense activations are large and short-lived; releasing them keeps
            # the next tile from tripping over allocator fragmentation.
            torch.cuda.empty_cache()

        h_ref, w_ref = reference.shape[:2]
        inside = (src[:, 0] < w) & (src[:, 1] < h) & (dst[:, 0] < w_ref) & (dst[:, 1] < h_ref)
        keep = inside & (conf >= self.confidence)
        return MatchResult(
            src_pts=src[keep],
            dst_pts=dst[keep],
            scores=conf[keep],
            matcher=self.name,
            meta={
                "device": self.device,
                "precision": self.precision,
                "weights": f"loftr_{self.weights}",
                "confidence_threshold": self.confidence,
                "pad_multiple": LOFTR_PAD_MULTIPLE,
            },
        )


class LightGlueMatcher:
    """Sparse DISK + LightGlue matching.

    Memory scales with keypoint count rather than image area, so this tolerates
    much larger tiles than LoFTR at the same VRAM. Correspondences are sparser
    and concentrate on high-texture structure, which on smooth mare terrain can
    leave gaps the uniformity metric will flag.
    """

    def __init__(
        self,
        device: str | None = None,
        max_keypoints: int | None = None,
        features: str = "disk",
    ) -> None:
        self.device = device or get_device()
        self.max_keypoints = max_keypoints or plan_keypoint_budget(self.device)
        self.features = features
        self.name = f"lightglue/{features}"
        self._extractor = None
        self._matcher = None

    def _get_models(self):
        if self._extractor is None:
            import kornia.feature as KF

            self._extractor = KF.DISK.from_pretrained("depth").to(self.device).eval()
            self._matcher = KF.LightGlue(self.features).to(self.device).eval()
        return self._extractor, self._matcher

    def match(self, source: np.ndarray, reference: np.ndarray) -> MatchResult:
        import torch

        extractor, matcher = self._get_models()
        autocast = (
            torch.autocast("cuda", dtype=torch.float16) if self.device == "cuda" else nullcontext()
        )

        with torch.inference_mode():
            with autocast:
                # DISK expects 3-channel input; repeat the single band. It also
                # rejects any side that is not a multiple of 16, so pad
                # bottom/right with zeros: keypoint coordinates are unchanged by
                # padding there, and anything detected inside it is dropped below.
                t0 = _pad_to_multiple(_to_tensor(source, self.device), 16).repeat(1, 3, 1, 1)
                t1 = _pad_to_multiple(_to_tensor(reference, self.device), 16).repeat(1, 3, 1, 1)
                f0 = extractor(t0, n=self.max_keypoints, window_size=5, score_threshold=0.0)[0]
                f1 = extractor(t1, n=self.max_keypoints, window_size=5, score_threshold=0.0)[0]
                f0 = _drop_outside(f0, source.shape[:2])
                f1 = _drop_outside(f1, reference.shape[:2])

            # Outside autocast, in fp32: kornia's LightGlue positional encoding
            # is fp32, and fp16 input under an outer autocast raises on CUDA.
            out = matcher(
                {
                    "image0": {
                        "keypoints": f0.keypoints.float()[None],
                        "descriptors": f0.descriptors.float()[None],
                        "image_size": torch.tensor(source.shape[:2][::-1], device=self.device)[
                            None
                        ],
                    },
                    "image1": {
                        "keypoints": f1.keypoints.float()[None],
                        "descriptors": f1.descriptors.float()[None],
                        "image_size": torch.tensor(reference.shape[:2][::-1], device=self.device)[
                            None
                        ],
                    },
                }
            )
            idx = out["matches"][0].cpu().numpy()
            src = f0.keypoints.float().cpu().numpy()
            dst = f1.keypoints.float().cpu().numpy()

        if self.device == "cuda":
            torch.cuda.empty_cache()

        meta = {
            "device": self.device,
            "precision": "fp16-disk+fp32-lightglue" if self.device == "cuda" else "fp32",
            "weights": "disk_depth+lightglue_disk",
            "max_keypoints": self.max_keypoints,
        }
        if idx.size == 0:
            empty = MatchResult.empty(self.name)
            empty.meta = {**meta, "empty_reason": "no_lightglue_matches"}
            return empty
        return MatchResult(
            src_pts=src[idx[:, 0]],
            dst_pts=dst[idx[:, 1]],
            matcher=self.name,
            meta=meta,
        )
