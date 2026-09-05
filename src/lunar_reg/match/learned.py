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

Every forward pass runs under ``inference_mode`` and, on CUDA, ``autocast``
fp16. Both are load-bearing for fitting in 8 GB, not incidental optimisations.
"""

from __future__ import annotations

import logging
from contextlib import nullcontext

import numpy as np

from lunar_reg.device import get_device, plan_dense_tile, plan_keypoint_budget
from lunar_reg.match.base import MatchResult

logger = logging.getLogger(__name__)

#: LoFTR's pretrained weight sets. ``outdoor`` is the right prior for orbital
#: imagery; ``indoor`` is trained on room-scale scenes and transfers poorly.
LOFTR_WEIGHTS = ("outdoor", "indoor")


def _to_tensor(image: np.ndarray, device: str):
    """Single-band uint8/float image -> normalised ``(1, 1, H, W)`` tensor."""
    import torch

    arr = np.asarray(image, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr.mean(axis=-1)
    if arr.max() > 1.0:
        arr = arr / 255.0
    return torch.from_numpy(arr)[None, None].to(device)


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

        with torch.inference_mode(), autocast:
            out = model({
                "image0": _to_tensor(source, self.device),
                "image1": _to_tensor(reference, self.device),
            })
            src = out["keypoints0"].float().cpu().numpy()
            dst = out["keypoints1"].float().cpu().numpy()
            conf = out["confidence"].float().cpu().numpy()

        if self.device == "cuda":
            # Dense activations are large and short-lived; releasing them keeps
            # the next tile from tripping over allocator fragmentation.
            torch.cuda.empty_cache()

        keep = conf >= self.confidence
        return MatchResult(
            src_pts=src[keep],
            dst_pts=dst[keep],
            scores=conf[keep],
            matcher=self.name,
            meta={"confidence_threshold": self.confidence, "precision": self.precision},
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
            torch.autocast("cuda", dtype=torch.float16)
            if self.device == "cuda"
            else nullcontext()
        )

        with torch.inference_mode(), autocast:
            # DISK expects 3-channel input; repeat the single band.
            t0 = _to_tensor(source, self.device).repeat(1, 3, 1, 1)
            t1 = _to_tensor(reference, self.device).repeat(1, 3, 1, 1)
            f0 = extractor(t0, n=self.max_keypoints, window_size=5, score_threshold=0.0)[0]
            f1 = extractor(t1, n=self.max_keypoints, window_size=5, score_threshold=0.0)[0]

            out = matcher({
                "image0": {
                    "keypoints": f0.keypoints[None],
                    "descriptors": f0.descriptors[None],
                    "image_size": torch.tensor(source.shape[:2][::-1], device=self.device)[None],
                },
                "image1": {
                    "keypoints": f1.keypoints[None],
                    "descriptors": f1.descriptors[None],
                    "image_size": torch.tensor(reference.shape[:2][::-1], device=self.device)[None],
                },
            })
            idx = out["matches"][0].cpu().numpy()
            src = f0.keypoints.float().cpu().numpy()
            dst = f1.keypoints.float().cpu().numpy()

        if self.device == "cuda":
            torch.cuda.empty_cache()

        if idx.size == 0:
            return MatchResult.empty(self.name)
        return MatchResult(
            src_pts=src[idx[:, 0]],
            dst_pts=dst[idx[:, 1]],
            matcher=self.name,
            meta={"max_keypoints": self.max_keypoints},
        )


def build_matcher(name: str, **kwargs):
    """Construct a matcher by name, for config-driven runs and the CLI."""
    from lunar_reg.match.classical import ClassicalMatcher

    name = name.lower()
    if name.startswith("loftr"):
        return LoFTRMatcher(**kwargs)
    if name.startswith(("lightglue", "disk")):
        return LightGlueMatcher(**kwargs)
    if name in {"sift", "akaze", "orb"}:
        return ClassicalMatcher(detector=name, **kwargs)
    raise ValueError(f"unknown matcher {name!r}")
