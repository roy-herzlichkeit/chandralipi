"""Maximum Index Map, and RIFT2's rotation-invariant recoding.

Clean-room implementation from:

* RIFT (arXiv:1804.09493) section III-B-1, for MIM construction.
* RIFT2 (arXiv:2303.00319) section III, for the dominant-index recoding.

The MIM idea
------------
At each pixel, take the amplitude summed over scales for each of the ``N_o``
orientations, and record *which orientation won*. The resulting index map
discards magnitude entirely and keeps only the ordering of orientation
responses, which is why it survives nonlinear radiation distortion that
destroys both intensity and gradient.

RIFT's rotation problem, and RIFT2's fix
----------------------------------------
Rotating an image does not merely rotate the MIM -- it also *renumbers* it,
because the orientation that wins at a pixel shifts by the rotation angle. So a
SIFT-style dominant-orientation correction is not enough; RIFT v1 handled it by
building ``N_o`` MIMs per reference keypoint from cyclically-shifted convolution
sequences (its "convolution sequence ring"), multiplying both description and
matching cost by ``N_o``.

RIFT2 observes that the renumbering is a *cyclic shift of the MIM histogram*.
So it finds the histogram peak within the patch -- the **dominant index** ``s``
-- and recodes the MIM so that ``s`` becomes 1 (RIFT2 equation 2)::

    MIM_n(x) = MIM(x) - s + 1        if MIM(x) >= s
               MIM(x) + N_o - s + 1  otherwise

The recoded map is rotation-invariant, so one MIM per keypoint suffices. That is
the whole speed-up: roughly 3x less time and memory for equivalent matching
performance.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

#: If the runner-up histogram bin is at least this fraction of the peak, the
#: dominant index is ambiguous and a second descriptor is emitted for that bin
#: too. Paper-stated: RIFT2 Table I gives "dominate ratio: 0.8".
DOMINANT_RATIO = 0.8


def build_mim(amplitude_by_orientation: np.ndarray) -> np.ndarray:
    """Maximum Index Map from the log-Gabor convolution sequence.

    Takes ``(n_orientations, rows, cols)`` summed amplitudes and returns a
    ``(rows, cols)`` map of **1-based** winning orientation indices, matching the
    papers' convention that MIM values run from 1 to ``N_o``.
    """
    amplitude = np.asarray(amplitude_by_orientation)
    if amplitude.ndim != 3:
        raise ValueError(f"expected (n_orientations, rows, cols), got {amplitude.shape}")
    return (np.argmax(amplitude, axis=0) + 1).astype(np.int16)


def mim_histogram(patch: np.ndarray, n_orientations: int) -> np.ndarray:
    """Counts of each MIM index in a patch. Index ``i`` of the result is value ``i+1``."""
    return np.bincount(
        np.asarray(patch, dtype=np.int64).ravel() - 1, minlength=n_orientations
    )[:n_orientations]


def dominant_indices(
    patch: np.ndarray,
    n_orientations: int,
    dominant_ratio: float = DOMINANT_RATIO,
) -> list[int]:
    """Dominant index or indices for a patch, 1-based.

    Returns the histogram peak, plus the runner-up when it reaches
    ``dominant_ratio`` of the peak. RIFT2 emits a second descriptor in that case
    because an ambiguous peak would otherwise pick an arbitrary one of two
    near-equal rotations and silently mis-describe the patch.
    """
    histogram = mim_histogram(patch, n_orientations)
    if histogram.sum() == 0:
        return [1]

    order = np.argsort(histogram)[::-1]
    peak = int(order[0])
    result = [peak + 1]

    if len(order) > 1 and histogram[peak] > 0:
        runner_up = int(order[1])
        if histogram[runner_up] >= dominant_ratio * histogram[peak]:
            result.append(runner_up + 1)
    return result


def recode_mim(patch: np.ndarray, dominant_index: int, n_orientations: int) -> np.ndarray:
    """Cyclically shift MIM values so ``dominant_index`` becomes 1.

    RIFT2 equation (2). This is what makes the descriptor rotation-invariant
    without building one MIM per orientation.
    """
    patch = np.asarray(patch, dtype=np.int16)
    shifted = np.where(
        patch >= dominant_index,
        patch - dominant_index + 1,
        patch + n_orientations - dominant_index + 1,
    )
    return shifted.astype(np.int16)


def rotation_shift_equivalence(
    mim_a: np.ndarray, mim_b: np.ndarray, n_orientations: int
) -> int:
    """Cyclic shift that best aligns two MIM histograms, for diagnostics.

    Not part of the algorithm -- useful for checking that a measured rotation
    produces the expected index shift when validating an implementation.
    """
    hist_a = mim_histogram(mim_a, n_orientations).astype(float)
    hist_b = mim_histogram(mim_b, n_orientations).astype(float)
    scores = [
        float(np.dot(hist_a, np.roll(hist_b, shift))) for shift in range(n_orientations)
    ]
    return int(np.argmax(scores))
