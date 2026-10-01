"""SuperPoint + SuperGlue, and its Apache-2.0 alternative.

SuperGlue (Sarlin et al., CVPR 2020) is the strongest performer in the Makharia
et al. benchmark, so it belongs in this project's comparison. But its licence
makes it unusable in a deliverable, and that has to be handled explicitly rather
than discovered later.

The licence problem
-------------------
``magicleap/SuperGluePretrainedNetwork`` is released under a **"SOFTWARE LICENSE
AGREEMENT -- ACADEMIC OR NON-PROFIT ORGANIZATION NONCOMMERCIAL RESEARCH USE
ONLY"**. Three clauses matter here:

* *"You may not distribute, copy or use the Software except as explicitly
  permitted herein"* -- it cannot ship inside a submission.
* *"a personal, non-exclusive, non-transferable license to use the Software for
  noncommercial research purposes"* -- adoption or operational use is outside
  the grant.
* *"You agree that all and any such derivatives and modifications will be owned
  by Licensor"* -- a wrapper written around it would, by the terms, become Magic
  Leap's property.

That last clause is why this module wraps SuperGlue only behind an explicit
acknowledgement, and why the weights are never vendored. For a Smart India
Hackathon entry that ISRO may evaluate or carry forward, shipping it would be a
straightforward licence breach.

The Apache-2.0 route
--------------------
:class:`lunar_reg.match.learned.LightGlueMatcher` is the recommended default. LightGlue is by
substantially the same authors as SuperGlue, is its acknowledged successor, is
faster and more accurate on published benchmarks, and both ``cvg/LightGlue`` and
the kornia packaging are Apache-2.0. It fills the same role in the pipeline with
no licence encumbrance.

Use :class:`SuperGlueMatcher` only for a local research comparison, never in
anything distributed.
"""

from __future__ import annotations

import logging

import numpy as np

from lunar_reg.device import get_device, plan_keypoint_budget
from lunar_reg.match.base import MatchResult

logger = logging.getLogger(__name__)

#: Quoted from the repository's LICENSE file.
SUPERGLUE_LICENCE = (
    "ACADEMIC OR NON-PROFIT ORGANIZATION NONCOMMERCIAL RESEARCH USE ONLY "
    "(magicleap/SuperGluePretrainedNetwork). Forbids distribution; derivatives "
    "become the property of Magic Leap, Inc."
)

_LICENCE_REFUSAL = f"""SuperGlue is licence-encumbered and is disabled by default.

{SUPERGLUE_LICENCE}

For anything distributed -- including a Smart India Hackathon submission -- use
LightGlueMatcher instead. LightGlue is by substantially the same authors, is
SuperGlue's acknowledged successor, is faster and more accurate, and is
Apache-2.0 through both cvg/LightGlue and kornia.

If you are running a local research comparison only, and your use falls inside
the academic/non-profit noncommercial grant, construct with:

    SuperGlueMatcher(acknowledge_noncommercial_licence=True)

You must also install the weights yourself; this project does not vendor them,
because redistribution is exactly what the licence forbids."""


class SuperGlueMatcher:
    """SuperPoint + SuperGlue. **Licence-gated; not for anything distributed.**

    Refuses to construct unless ``acknowledge_noncommercial_licence=True``, and
    never vendors the weights -- the licence forbids redistribution, so the
    weights must be obtained separately and pointed at with ``weights_dir``.

    Prefer :class:`lunar_reg.match.learned.LightGlueMatcher` unless you
    specifically need a SuperGlue row for a local research comparison against
    the Makharia et al. benchmark.
    """

    def __init__(
        self,
        acknowledge_noncommercial_licence: bool = False,
        weights_dir: str | None = None,
        device: str | None = None,
        max_keypoints: int | None = None,
        weights: str = "outdoor",
        keypoint_threshold: float = 0.005,
        match_threshold: float = 0.2,
    ) -> None:
        if not acknowledge_noncommercial_licence:
            raise PermissionError(_LICENCE_REFUSAL)

        self.device = device or get_device()
        self.max_keypoints = max_keypoints or plan_keypoint_budget(self.device)
        self.weights = weights
        self.weights_dir = weights_dir
        self.keypoint_threshold = keypoint_threshold
        self.match_threshold = match_threshold
        self.name = f"superglue/{weights}"
        self._model = None
        logger.warning(
            "SuperGlue enabled under its noncommercial research licence. "
            "Do not include it or its outputs in a distributed deliverable."
        )

    def _get_model(self):
        """Load SuperPoint+SuperGlue from a user-provided checkout.

        Deliberately imports from a path the user supplies rather than a vendored
        copy. If the import fails the message says exactly why, because the most
        likely cause is that the weights were never obtained.
        """
        if self._model is not None:
            return self._model

        import sys

        if self.weights_dir:
            sys.path.insert(0, str(self.weights_dir))
        try:
            from models.matching import Matching  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "Could not import SuperGlue. This project does not vendor it -- its "
                "licence forbids redistribution. Clone "
                "magicleap/SuperGluePretrainedNetwork yourself and pass its path as "
                "weights_dir=..., having satisfied yourself that your use falls inside "
                "the academic/non-profit noncommercial grant. "
                "For a distributable pipeline use LightGlueMatcher instead."
            ) from exc

        import torch

        config = {
            "superpoint": {
                "nms_radius": 4,
                "keypoint_threshold": self.keypoint_threshold,
                "max_keypoints": self.max_keypoints,
            },
            "superglue": {
                "weights": self.weights,
                "sinkhorn_iterations": 20,
                "match_threshold": self.match_threshold,
            },
        }
        self._model = Matching(config).eval().to(self.device)
        _ = torch
        return self._model

    def match(self, source: np.ndarray, reference: np.ndarray) -> MatchResult:
        import torch

        from lunar_reg.match.learned import _to_tensor

        model = self._get_model()
        with torch.inference_mode():
            output = model(
                {
                    "image0": _to_tensor(source, self.device),
                    "image1": _to_tensor(reference, self.device),
                }
            )
            keypoints0 = output["keypoints0"][0].cpu().numpy()
            keypoints1 = output["keypoints1"][0].cpu().numpy()
            matches = output["matches0"][0].cpu().numpy()
            confidence = output["matching_scores0"][0].cpu().numpy()

        if self.device == "cuda":
            torch.cuda.empty_cache()

        valid = matches > -1
        if not valid.any():
            return MatchResult.empty(self.name)

        return MatchResult(
            src_pts=keypoints0[valid],
            dst_pts=keypoints1[matches[valid]],
            scores=confidence[valid],
            matcher=self.name,
            meta={
                "detector": "superglue",
                "device": self.device,
                "licence": "NONCOMMERCIAL RESEARCH ONLY -- do not distribute",
            },
        )


def licence_report() -> str:
    """Licence status of every learned matcher, for the submission checklist."""
    rows = [
        ("LoFTR (kornia)", "Apache-2.0", "yes", "dense; best on low-texture terrain"),
        ("LightGlue + DISK (kornia)", "Apache-2.0", "yes", "sparse; SuperGlue's successor"),
        (
            "SuperGlue (magicleap)",
            "Noncommercial research only",
            "NO",
            "distribution forbidden; derivatives owned by Magic Leap",
        ),
    ]
    width = max(len(r[0]) for r in rows)
    lines = [f"{'matcher'.ljust(width)}  {'licence':<28} {'shippable':<9} notes", "-" * 100]
    lines += [f"{n.ljust(width)}  {lic:<28} {ship:<9} {note}" for n, lic, ship, note in rows]
    lines += [
        "",
        "Only the Apache-2.0 matchers may appear in a distributed deliverable.",
        "SuperGlue is available for local research comparison behind an explicit flag.",
    ]
    return "\n".join(lines)
