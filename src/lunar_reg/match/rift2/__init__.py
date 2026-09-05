"""RIFT2: Radiation-variation Insensitive Feature Transform, version 2.

Clean-room implementation from the published papers:

* Li, Hu & Ai, "RIFT: Multi-modal Image Matching Based on Radiation-variation
  Insensitive Feature Transform", IEEE TIP 2020 (arXiv:1804.09493)
* Li et al., "RIFT2: Speeding-up RIFT with A New Rotation-Invariance Technique",
  2023 (arXiv:2303.00319)

**No unlicensed source code was consulted.** The authors' MATLAB reference and
the third-party Python port both carry no licence, so this project implements
from the papers' equations instead. That is what makes this code ours to
licence with the rest of the project.
"""

from lunar_reg.match.rift2.descriptor import describe_keypoints, describe_patch
from lunar_reg.match.rift2.matcher import RIFT2Matcher, detect_corners, detect_edges
from lunar_reg.match.rift2.mim import build_mim, dominant_indices, recode_mim
from lunar_reg.match.rift2.phase import (
    N_ORIENTATIONS,
    N_SCALES,
    PhaseResult,
    build_log_gabor_bank,
    compute_moments,
    compute_phase_congruency,
)

__all__ = [
    "N_ORIENTATIONS",
    "N_SCALES",
    "PhaseResult",
    "RIFT2Matcher",
    "build_log_gabor_bank",
    "build_mim",
    "compute_moments",
    "compute_phase_congruency",
    "describe_keypoints",
    "describe_patch",
    "detect_corners",
    "detect_edges",
    "dominant_indices",
    "recode_mim",
]
