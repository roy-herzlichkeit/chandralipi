"""Log-Gabor filter bank, phase congruency, and PC moments.

Clean-room implementation from the published equations. Written from:

* Li, Hu & Ai, "RIFT: Multi-modal Image Matching Based on Radiation-variation
  Insensitive Feature Transform", IEEE TIP 2020 (arXiv:1804.09493), equations
  (1)-(16).
* Kovesi's published phase-congruency formulation, which RIFT equations (6)-(10)
  restate.

**No unlicensed source code was consulted.** Neither the MATLAB reference
implementation nor the third-party Python port was read; both are unlicensed,
which is precisely why this exists. Everything here derives from the papers'
equations and from the standard published log-Gabor construction.

Why phase congruency at all
---------------------------
Intensity and gradient have only *linear* radiation invariance, so they break
under the nonlinear radiation differences between sensors -- optical vs
hyperspectral, or either vs SAR. Phase congruency is computed from the *phase*
of the local frequency response, which is invariant to brightness and contrast
change and degrades gracefully under nonlinear distortion. That is the whole
basis of RIFT's robustness, and the reason it is the right classical matcher for
the OHRC-to-IIRS case.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

# --- Parameters stated in the RIFT paper (section IV-B parameter study) -----
#: Number of log-Gabor orientations. Paper: "fixed to No = 6". The six
#: directions are 0, 30, 60, 90, 120, 150 degrees.
N_ORIENTATIONS = 6
#: Number of log-Gabor scales. Paper: "Ns = 4 ... achieves the best".
N_SCALES = 4

# --- Standard log-Gabor construction constants ------------------------------
# The RIFT paper gives the filter *form* (its equation 1) but not these values.
# They are the conventional published defaults for a log-Gabor bank and are
# marked here so nobody mistakes them for RIFT-specified values.
MIN_WAVELENGTH = 3.0     # shortest wavelength, in pixels
MULT = 2.1               # scaling factor between successive scales
SIGMA_ON_F = 0.55        # ratio of filter bandwidth to centre frequency
D_THETA_SIGMA = 1.2      # angular spread, as a multiple of the orientation step
K_NOISE = 2.0            # noise threshold, in standard deviations
CUTOFF = 0.5             # frequency-spread weighting cutoff
GAIN = 10.0              # sharpness of the weighting sigmoid
EPSILON = 1e-4


@dataclass
class PhaseResult:
    """Everything the later RIFT stages need from the filter bank."""

    #: ``(n_orientations, rows, cols)`` summed amplitude per orientation,
    #: equation (17). This is the log-Gabor convolution sequence the MIM is
    #: built from.
    amplitude_by_orientation: np.ndarray
    #: Minimum moment: equivalent to cornerness (equation 16).
    min_moment: np.ndarray
    #: Maximum moment: the edge map (equation 15).
    max_moment: np.ndarray
    #: Per-orientation phase congruency maps.
    pc_by_orientation: np.ndarray

    @property
    def n_orientations(self) -> int:
        return self.amplitude_by_orientation.shape[0]


def _lowpass_filter(shape: tuple[int, int], cutoff: float = 0.45, order: int = 15):
    """Butterworth lowpass, used to stop the log-Gabor bank ringing at Nyquist."""
    rows, cols = shape
    y, x = np.mgrid[0:rows, 0:cols]
    x = (x - cols // 2) / cols
    y = (y - rows // 2) / rows
    radius = np.sqrt(x**2 + y**2)
    return np.fft.ifftshift(1.0 / (1.0 + (radius / cutoff) ** (2 * order)))


def build_log_gabor_bank(
    shape: tuple[int, int],
    n_scales: int = N_SCALES,
    n_orientations: int = N_ORIENTATIONS,
) -> np.ndarray:
    """Frequency-domain log-Gabor filters, shaped ``(n_scales, n_orientations, r, c)``.

    Implements the paper's equation (1): a radial log-Gaussian times an angular
    Gaussian, in log-polar frequency coordinates.
    """
    rows, cols = shape
    y, x = np.mgrid[0:rows, 0:cols]
    x = (x - cols // 2) / cols
    y = (y - rows // 2) / rows

    radius = np.fft.ifftshift(np.sqrt(x**2 + y**2))
    theta = np.fft.ifftshift(np.arctan2(-y, x))
    radius[0, 0] = 1.0  # avoid log(0) at the DC term; the lowpass kills it anyway

    sin_theta, cos_theta = np.sin(theta), np.cos(theta)
    lowpass = _lowpass_filter(shape)

    bank = np.zeros((n_scales, n_orientations, rows, cols))
    angular_sigma = (np.pi / n_orientations) / D_THETA_SIGMA

    for s in range(n_scales):
        wavelength = MIN_WAVELENGTH * (MULT**s)
        f0 = 1.0 / wavelength
        # Radial log-Gaussian: equation (1)'s first exponential, in log-frequency.
        radial = np.exp(-((np.log(radius / f0)) ** 2) / (2 * np.log(SIGMA_ON_F) ** 2))
        radial *= lowpass
        radial[0, 0] = 0.0

        for o in range(n_orientations):
            angle = o * np.pi / n_orientations
            # Angular distance, computed via sin/cos so it wraps correctly.
            ds = sin_theta * np.cos(angle) - cos_theta * np.sin(angle)
            dc = cos_theta * np.cos(angle) + sin_theta * np.sin(angle)
            d_theta = np.abs(np.arctan2(ds, dc))
            angular = np.exp(-(d_theta**2) / (2 * angular_sigma**2))
            bank[s, o] = radial * angular

    return bank


def compute_phase_congruency(
    image: np.ndarray,
    n_scales: int = N_SCALES,
    n_orientations: int = N_ORIENTATIONS,
) -> PhaseResult:
    """Per-orientation phase congruency, its moments, and the amplitude sequence.

    Implements RIFT equations (3)-(17). Returns everything the detection and
    description stages need in one pass, because the log-Gabor convolutions are
    by far the expensive part and both stages consume them.
    """
    image = np.asarray(image, dtype=np.float64)
    if image.ndim != 2:
        raise ValueError(f"expected a 2D single-band image, got shape {image.shape}")

    rows, cols = image.shape
    fft_image = np.fft.fft2(image)
    bank = build_log_gabor_bank((rows, cols), n_scales, n_orientations)

    amplitude_by_orientation = np.zeros((n_orientations, rows, cols))
    pc_by_orientation = np.zeros((n_orientations, rows, cols))

    for o in range(n_orientations):
        sum_e = np.zeros((rows, cols))
        sum_o = np.zeros((rows, cols))
        sum_amplitude = np.zeros((rows, cols))
        max_amplitude = np.zeros((rows, cols))
        energy = np.zeros((rows, cols))
        tau = None

        responses = []
        for s in range(n_scales):
            # Equation (3): convolve with the even/odd wavelet pair.
            response = np.fft.ifft2(fft_image * bank[s, o])
            even, odd = np.real(response), np.imag(response)
            # Equation (4): amplitude.
            amplitude = np.sqrt(even**2 + odd**2)
            responses.append((even, odd, amplitude))

            sum_e += even
            sum_o += odd
            sum_amplitude += amplitude
            max_amplitude = np.maximum(max_amplitude, amplitude)
            if s == 0:
                # Noise is estimated from the smallest scale, where it dominates.
                # Rayleigh-distributed magnitude -> median / sqrt(log 4).
                tau = np.median(amplitude) / np.sqrt(np.log(4))

        # Equations (8)-(10): the mean phase direction over scales.
        norm = np.sqrt(sum_e**2 + sum_o**2) + EPSILON
        mean_e, mean_o = sum_e / norm, sum_o / norm

        for even, odd, _ in responses:
            # Equation (7): phase deviation, weighted by amplitude.
            energy += even * mean_e + odd * mean_o - np.abs(even * mean_o - odd * mean_e)

        # Equation (6)'s noise compensation term T, accumulated across scales.
        total_tau = (tau or 0.0) * (1 - (1 / MULT) ** n_scales) / (1 - 1 / MULT)
        noise_mean = total_tau * np.sqrt(np.pi / 2)
        noise_sigma = total_tau * np.sqrt((4 - np.pi) / 2)
        threshold = noise_mean + K_NOISE * noise_sigma
        energy = np.maximum(energy - threshold, 0.0)

        # Frequency-spread weighting w_o: suppresses responses from a single
        # scale, which are usually noise rather than a real feature.
        width = (sum_amplitude / (max_amplitude + EPSILON) - 1.0) / max(n_scales - 1, 1)
        weight = 1.0 / (1.0 + np.exp((CUTOFF - width) * GAIN))

        pc_by_orientation[o] = weight * energy / (sum_amplitude + EPSILON)
        # Equation (17): sum amplitudes over scales to get the convolution layer.
        amplitude_by_orientation[o] = sum_amplitude

    min_moment, max_moment = compute_moments(pc_by_orientation)
    return PhaseResult(
        amplitude_by_orientation=amplitude_by_orientation,
        min_moment=min_moment,
        max_moment=max_moment,
        pc_by_orientation=pc_by_orientation,
    )


def compute_moments(pc_by_orientation: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Minimum and maximum moments of the per-orientation PC maps.

    Implements equations (11)-(16). The minimum moment is a cornerness measure;
    the maximum moment is an edge map. RIFT detects on both because corners are
    repeatable but few, while edges are plentiful but less repeatable.
    """
    n_orientations = pc_by_orientation.shape[0]
    angles = np.arange(n_orientations) * np.pi / n_orientations

    a = np.zeros(pc_by_orientation.shape[1:])
    b = np.zeros(pc_by_orientation.shape[1:])
    c = np.zeros(pc_by_orientation.shape[1:])
    for o in range(n_orientations):
        pc = pc_by_orientation[o]
        # Equations (11)-(13). Note b's factor of 2 and the cos*sin cross term.
        a += (pc * np.cos(angles[o])) ** 2
        b += 2.0 * (pc * np.cos(angles[o])) * (pc * np.sin(angles[o]))
        c += (pc * np.sin(angles[o])) ** 2

    discriminant = np.sqrt(b**2 + (a - c) ** 2)
    max_moment = 0.5 * (c + a + discriminant)  # equation (15)
    min_moment = 0.5 * (c + a - discriminant)  # equation (16)
    return min_moment, max_moment
