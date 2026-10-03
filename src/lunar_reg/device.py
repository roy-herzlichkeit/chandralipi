"""Device selection and VRAM budgeting.

Target hardware for this project is a single **RTX 4060 Mobile / Max-Q, 8 GB**.
That number drives almost every tunable in the pipeline, so the budget maths
lives here rather than being scattered as magic numbers.

Two hardware facts worth keeping in mind:

* 8 GB is *total*, not free. A desktop session on the same GPU typically holds
  0.5-1.5 GB, and PyTorch's allocator adds fragmentation on top, so plan
  against :func:`free_vram_bytes`, not against the nameplate capacity.
* Max-Q parts are power-limited. Throughput on long OHRC strips is bounded by
  sustained clocks as much as by memory, so prefer fewer large tiles over many
  small ones once a tile fits.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

from lunar_reg.provenance import ValueSource

logger = logging.getLogger(__name__)

#: Nameplate capacity of the target GPU. Documentation only: nothing uses it as
#: a fallback. A free-memory reading that fails is ``UNKNOWN`` with 0 bytes
#: (see :func:`free_memory_bytes`), never this value.
ASSUMED_TOTAL_VRAM_BYTES: int = 8 * 1024**3
ASSUMED_TOTAL_VRAM_BYTES_SOURCE = ValueSource.DOCUMENTED

#: Fraction of free VRAM a single matcher call is allowed to plan against.
#: The remainder absorbs allocator fragmentation and the odd transient copy.
VRAM_SAFETY_FRACTION: float = 0.75


def get_device(prefer_cuda: bool = True) -> str:
    """Return ``"cuda"`` when a usable CUDA device is present, else ``"cpu"``.

    Import of :mod:`torch` is deferred so that the ingest/eval halves of the
    pipeline stay usable on a machine with no working driver.
    """
    if not prefer_cuda:
        return "cpu"
    try:
        import torch
    except ImportError:
        logger.warning("torch is not installed; falling back to CPU")
        return "cpu"
    if not torch.cuda.is_available():
        logger.warning(
            "CUDA unavailable (driver not loaded, or a CPU-only torch build). "
            "Learned matchers will run on CPU and will be roughly 30-50x slower."
        )
        return "cpu"
    return "cuda"


@dataclass(frozen=True)
class MemoryReading:
    """One free-memory reading for a device (CONTRACTS C17).

    ``source`` is ``MEASURED`` when the bytes were read from the device (CUDA
    ``mem_get_info``) or the host (``/proc/meminfo``), and ``UNKNOWN`` with
    ``free_bytes == total_bytes == 0`` when the reading failed.
    """

    device: str
    free_bytes: int
    total_bytes: int
    source: ValueSource


_PROC_MEMINFO = Path("/proc/meminfo")


def _read_proc_meminfo() -> str:
    """Raw text of ``/proc/meminfo`` (a separate function so tests can fake it)."""
    return _PROC_MEMINFO.read_text()


def _cpu_reading() -> MemoryReading:
    fields: dict[str, int] = {}
    for line in _read_proc_meminfo().splitlines():
        key, _, rest = line.partition(":")
        parts = rest.split()
        if not parts:
            continue
        scale = 1024 if len(parts) > 1 and parts[1].lower() == "kb" else 1
        fields[key.strip()] = int(parts[0]) * scale
    free, total = fields["MemAvailable"], fields["MemTotal"]
    if total <= 0 or free < 0:
        raise ValueError(f"implausible /proc/meminfo: MemAvailable={free} MemTotal={total}")
    return MemoryReading("cpu", int(free), int(total), ValueSource.MEASURED)


def _cuda_reading(device: str) -> MemoryReading:
    import torch

    if device == "cuda":
        index = torch.cuda.current_device()
    else:
        prefix, _, idx = device.partition(":")
        if prefix != "cuda" or not idx.isdigit():
            raise ValueError(f"not a CUDA device string: {device!r}")
        index = int(idx)
    free, total = torch.cuda.mem_get_info(index)
    return MemoryReading(device, int(free), int(total), ValueSource.MEASURED)


def free_memory_bytes(device: str) -> MemoryReading:
    """Measured free/total memory of ``device`` (CONTRACTS C17).

    ``device`` is ``"cpu"`` (host ``MemAvailable`` / ``MemTotal`` from
    ``/proc/meminfo``), ``"cuda"`` (the current CUDA device) or ``"cuda:<n>"``
    (``torch.cuda.mem_get_info(<n>)``). Any failure -- no torch, no driver, no
    such device, unreadable ``/proc/meminfo``, an unrecognised device string --
    returns ``free_bytes=0, total_bytes=0, source=UNKNOWN`` and logs one
    warning; it never substitutes a nameplate value.
    """
    try:
        if device == "cpu":
            return _cpu_reading()
        return _cuda_reading(device)
    except Exception as exc:  # noqa: BLE001 - every failure is the UNKNOWN reading
        logger.warning(
            "free memory of %r could not be read (%s: %s); reporting UNKNOWN, 0 bytes",
            device,
            type(exc).__name__,
            exc,
        )
        return MemoryReading(device, 0, 0, ValueSource.UNKNOWN)


def free_vram_bytes(device: str = "cuda") -> int:
    """Free bytes on ``device``: ``free_memory_bytes(device).free_bytes``.

    For ``"cpu"`` this is host ``MemAvailable``; a failed reading is 0.
    """
    return free_memory_bytes(device).free_bytes


@dataclass(frozen=True)
class TileBudget:
    """A tile size chosen to keep a matcher inside the VRAM envelope."""

    tile_px: int
    est_peak_bytes: int
    free_bytes: int
    matcher: str
    precision: str

    @property
    def est_peak_gb(self) -> float:
        return self.est_peak_bytes / 1024**3

    def __str__(self) -> str:
        return (
            f"{self.matcher}/{self.precision}: {self.tile_px}x{self.tile_px} px tiles, "
            f"~{self.est_peak_gb:.2f} GB peak of {self.free_bytes / 1024**3:.2f} GB free"
        )


# ---------------------------------------------------------------------------
# VRAM CONSTRAINT: dense-transformer matchers
#
# MEASURED, 2026-09-05, by lunar_reg.match.benchmark. An earlier version of this
# module modelled the cost as the coarse score matrix alone, i.e. pure S^4. That
# was wrong below about 900 px, and wrong by roughly 4x at 1024 px, because it
# omitted the backbone entirely. Two terms are needed:
#
#   peak(S) ~ BACKBONE_BYTES_PER_PX * S^2  +  elem * (S/8)^4
#             \_ CNN + linear attention _/    \_ coarse score matrix _/
#
# The second term is exact arithmetic, not a fit: LoFTR matches at 1/8
# resolution, so N = (S/8)^2 coarse tokens produce an N x N matrix. This was
# confirmed the hard way -- the allocation that fails at 1152 px is 1,719,926,784
# bytes, and ((1152/8)^2)^2 * 4 is 1,719,926,784 exactly.
#
# The first term is fitted to measured activations (host RSS, fp32, CPU):
#
#     S      measured   backbone   score matrix
#     256     0.219 GB   0.215 GB   0.004 GB
#     512     0.778 GB   0.716 GB   0.062 GB
#     768     1.756 GB   1.440 GB   0.316 GB
#     896     2.750 GB   2.164 GB   0.586 GB
#    1024     4.500 GB   3.500 GB   1.000 GB
#
# so the local exponent climbs from side^1.83 to side^3.69 across that range as
# the S^4 term takes over. Neither a quadratic nor a quartic model alone fits.
# Residuals of the two-term fit reach 18%, so treat the output as a planning
# figure with margin, which is what VRAM_SAFETY_FRACTION is for.
#
# PROVENANCE, because these are not equally trustworthy:
#  * the S^4 coefficient is exact.
#  * the S^2 coefficient is measured, but on CPU host RSS, because this machine
#    has no working CUDA device. It captures activation tensor shapes correctly;
#    the CUDA caching allocator will not reproduce it exactly.
#  * the fp16 factor is NOT measured. CPU bf16 autocast was attempted as a proxy
#    and abandoned -- it is emulated on this host and did not complete a single
#    512 px pass in 15 minutes. Re-measure on a GPU before relying on it.
# ---------------------------------------------------------------------------
_DENSE_BYTES_PER_ELEM = {"fp32": 4, "fp16": 2}

#: Backbone + attention activations per input pixel, fp32. Fitted to the table
#: above (least squares through the origin on peak-minus-score-matrix).
BACKBONE_BYTES_PER_PX: float = 3203.0

#: How much of the backbone term autocast actually saves. ESTIMATED, NOT
#: MEASURED -- autocast keeps normalisations, softmax and the loss in fp32, so
#: the saving is short of the naive 0.5. Deliberately conservative; correct it
#: with a measured run (`lunar-reg benchmark --matcher loftr --precision fp16`)
#: on a GPU.
FP16_BACKBONE_FACTOR: float = 0.6

#: Hard caps, independent of free memory -- above these the models degrade in
#: quality (receptive field vs. tile) even when they happen to fit.
MAX_DENSE_TILE_PX = 1408
MIN_DENSE_TILE_PX = 256


def dense_matcher_peak_bytes(tile_px: int, precision: str = "fp16") -> int:
    """Estimate peak activation bytes for one LoFTR-style pass on a square tile.

    Excludes model weights and framework overhead, which are a fixed ~0.43 GB on
    top and do not scale with tile size.
    """
    elem = _DENSE_BYTES_PER_ELEM[precision]
    backbone_per_px = BACKBONE_BYTES_PER_PX
    if precision == "fp16":
        backbone_per_px *= FP16_BACKBONE_FACTOR

    n_tokens = (tile_px // 8) ** 2
    score_matrix = n_tokens**2 * elem
    backbone = backbone_per_px * tile_px**2
    return int(backbone + score_matrix)


def plan_dense_tile(
    device: str = "cuda",
    precision: str = "fp16",
    matcher: str = "loftr",
) -> TileBudget:
    """Pick the largest square tile a dense matcher can process on this device.

    Returns a :class:`TileBudget`; the tile side is rounded down to a multiple
    of 64 so it stays compatible with the 1/8-then-1/2 feature pyramid.
    """
    free = free_vram_bytes(device)
    budget = free * VRAM_SAFETY_FRACTION
    elem = _DENSE_BYTES_PER_ELEM[precision]

    backbone_per_px = BACKBONE_BYTES_PER_PX
    if precision == "fp16":
        backbone_per_px *= FP16_BACKBONE_FACTOR

    # Invert dense_matcher_peak_bytes for S. With x = S^2 the model
    #     budget = backbone_per_px * x + (elem / 4096) * x^2
    # is a quadratic in x; take the positive root.
    quartic = elem / 4096.0
    x = (-backbone_per_px + math.sqrt(backbone_per_px**2 + 4 * quartic * budget)) / (2 * quartic)
    side = math.sqrt(max(x, 0.0))
    tile = int(min(side, MAX_DENSE_TILE_PX)) // 64 * 64
    tile = max(tile, MIN_DENSE_TILE_PX)

    return TileBudget(
        tile_px=tile,
        est_peak_bytes=dense_matcher_peak_bytes(tile, precision),
        free_bytes=free,
        matcher=matcher,
        precision=precision,
    )


# ---------------------------------------------------------------------------
# VRAM CONSTRAINT: sparse attention matchers
#
# SuperGlue/LightGlue attend over keypoints, so cost is O(K^2) in keypoint
# count rather than in pixels. 2048 keypoints per tile is comfortable; 4096
# roughly quadruples the attention working set and starts competing with the
# backbone for headroom on 8 GB.
# ---------------------------------------------------------------------------
DEFAULT_MAX_KEYPOINTS = 2048
SAFE_MAX_KEYPOINTS = 4096


def plan_keypoint_budget(device: str = "cuda") -> int:
    """Recommend a per-tile keypoint cap for sparse attention matchers."""
    free_gb = free_vram_bytes(device) / 1024**3
    if free_gb >= 10:
        return SAFE_MAX_KEYPOINTS
    if free_gb >= 5:
        return DEFAULT_MAX_KEYPOINTS
    return 1024


def describe_environment() -> str:
    """Human-readable summary of the compute environment, for logs and reports."""
    device = get_device()
    lines = [f"device: {device}"]
    if device == "cuda":
        import torch

        props = torch.cuda.get_device_properties(0)
        lines += [
            f"gpu: {props.name} (sm_{props.major}{props.minor})",
            f"vram: {props.total_memory / 1024**3:.1f} GB total, "
            f"{free_vram_bytes() / 1024**3:.1f} GB free",
            f"torch: {torch.__version__} / cuda {torch.version.cuda}",
        ]
        lines.append(f"plan: {plan_dense_tile()}")
        lines.append(f"keypoint cap: {plan_keypoint_budget()}")
    else:
        lines.append("learned matchers will be slow; classical track is the practical fallback")
    return "\n".join(lines)


__all__ = [
    "BACKBONE_BYTES_PER_PX",
    "FP16_BACKBONE_FACTOR",
    "MemoryReading",
    "TileBudget",
    "describe_environment",
    "dense_matcher_peak_bytes",
    "free_memory_bytes",
    "free_vram_bytes",
    "get_device",
    "plan_dense_tile",
    "plan_keypoint_budget",
]
