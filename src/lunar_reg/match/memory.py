"""Empirical memory measurement for matcher inference.

The point of this module is that **no memory figure in this project should be a
guess**. Where a number can be measured it is measured; where it cannot, the
result says so explicitly rather than substituting an estimate.

Two measurement backends
------------------------
``cuda_allocator``
    The real thing. Uses ``torch.cuda.reset_peak_memory_stats`` and
    ``max_memory_allocated``, which report actual device allocation. Only
    available when a CUDA device is present.

``host_rss``
    Fallback when there is no GPU. Measures the process's peak resident set
    size around the call. This is **not** VRAM: it includes the interpreter,
    the framework, and the model weights, and the host allocator behaves
    differently from CUDA's caching allocator. What it does capture faithfully
    is the *activation tensors*, which are the same shapes and dtypes wherever
    they live and which dominate the footprint at large tile sizes. Treat it as
    a lower bound on VRAM and a sound guide to how cost *scales* with tile size,
    not as a device measurement.

Every result carries :attr:`MemoryMeasurement.is_device_measurement` so a caller
can never mistake one for the other.
"""

from __future__ import annotations

import gc
import logging
import os
import resource
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger(__name__)

CUDA_ALLOCATOR = "cuda_allocator"
HOST_RSS = "host_rss"


@dataclass
class MemoryMeasurement:
    """Peak memory observed around one call, and how it was obtained."""

    peak_bytes: int
    method: str
    device: str
    seconds: float
    label: str = ""
    ok: bool = True
    error: str = ""
    #: Memory already held before the measured call: interpreter, framework and
    #: model weights. Subtracting it isolates the *activation* cost, which is the
    #: only part that grows with tile size. Zero when it was not captured.
    baseline_bytes: int = 0
    #: Correspondences the call produced, when the snippet reported them.
    n_matches: int | None = None

    @property
    def peak_gb(self) -> float:
        return self.peak_bytes / 1024**3

    @property
    def activation_bytes(self) -> int:
        """Peak minus the fixed baseline: the part that scales with tile size.

        Falls back to the full peak when no baseline was captured, which would
        make a scaling exponent read far too low -- the fixed term dominates at
        small tiles and flattens the curve.
        """
        if not self.baseline_bytes:
            return self.peak_bytes
        return max(self.peak_bytes - self.baseline_bytes, 0)

    @property
    def activation_gb(self) -> float:
        return self.activation_bytes / 1024**3

    @property
    def has_baseline(self) -> bool:
        return self.baseline_bytes > 0

    @property
    def is_device_measurement(self) -> bool:
        """Whether this is a real VRAM figure rather than a host-side proxy."""
        return self.method == CUDA_ALLOCATOR

    def as_dict(self) -> dict:
        return {**asdict(self), "peak_gb": self.peak_gb,
                "is_device_measurement": self.is_device_measurement}

    def __str__(self) -> str:
        if not self.ok:
            return f"{self.label}: FAILED ({self.error})"
        qualifier = "" if self.is_device_measurement else " (host proxy, NOT VRAM)"
        act = f", {self.activation_gb:.3f} GB activations" if self.has_baseline else ""
        return (f"{self.label}: {self.peak_gb:.3f} GB peak{qualifier}{act}, "
                f"{self.seconds:.2f}s")


def _peak_rss_bytes() -> int:
    """Process peak RSS. Linux reports kilobytes; macOS reports bytes."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak * 1024 if sys.platform.startswith("linux") else peak


def measure_peak_memory(
    fn: Callable[[], Any],
    device: str | None = None,
    label: str = "",
) -> tuple[Any, MemoryMeasurement]:
    """Run ``fn`` and measure its peak memory. Returns ``(result, measurement)``.

    On CUDA this resets the allocator's peak counter first, so the figure is the
    peak *for this call* rather than for the process. On CPU the peak RSS
    counter is a process-lifetime high-water mark that cannot be reset, so the
    number is only meaningful for the first substantial call in a process --
    use :func:`measure_in_subprocess` when comparing several sizes.
    """
    from lunar_reg.device import get_device

    device = device or get_device()

    if device == "cuda":
        import torch

        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        start = time.perf_counter()
        try:
            value = fn()
        except Exception as exc:  # noqa: BLE001 - OOM is a result, not a crash
            return None, MemoryMeasurement(
                0, CUDA_ALLOCATOR, device, time.perf_counter() - start, label,
                ok=False, error=f"{type(exc).__name__}: {exc}",
            )
        elapsed = time.perf_counter() - start
        return value, MemoryMeasurement(
            int(torch.cuda.max_memory_allocated()), CUDA_ALLOCATOR, device, elapsed, label
        )

    gc.collect()
    before = _peak_rss_bytes()
    start = time.perf_counter()
    try:
        value = fn()
    except Exception as exc:  # noqa: BLE001
        return None, MemoryMeasurement(
            0, HOST_RSS, device, time.perf_counter() - start, label,
            ok=False, error=f"{type(exc).__name__}: {exc}",
        )
    elapsed = time.perf_counter() - start
    return value, MemoryMeasurement(
        max(_peak_rss_bytes() - before, 0), HOST_RSS, device, elapsed, label
    )


def measure_in_subprocess(code: str, label: str = "", timeout: int = 900) -> MemoryMeasurement:
    """Run a snippet in a fresh interpreter and report its peak memory.

    Necessary on CPU: ``ru_maxrss`` is a process high-water mark that never
    falls, so measuring several tile sizes in one process would report the
    largest for all of them. A fresh process per size gives independent numbers.

    ``code`` must print ``PEAK_BYTES <int>`` and ``SECONDS <float>``. It may also
    print ``BASELINE_BYTES <int>`` (memory held before the measured call) and
    ``N_MATCHES <int>``; both are optional and default to unknown.
    """
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONWARNINGS": "ignore"},
        )
    except subprocess.TimeoutExpired:
        return MemoryMeasurement(
            0, HOST_RSS, "cpu", time.perf_counter() - start, label,
            ok=False, error=f"timed out after {timeout}s",
        )

    peak, seconds, method, device = 0, 0.0, HOST_RSS, "cpu"
    baseline, n_matches = 0, None
    for line in completed.stdout.splitlines():
        if line.startswith("PEAK_BYTES "):
            peak = int(line.split()[1])
        elif line.startswith("BASELINE_BYTES "):
            baseline = int(line.split()[1])
        elif line.startswith("SECONDS "):
            seconds = float(line.split()[1])
        elif line.startswith("METHOD "):
            method = line.split()[1]
        elif line.startswith("DEVICE "):
            device = line.split()[1]
        elif line.startswith("N_MATCHES "):
            n_matches = int(line.split()[1])

    if completed.returncode != 0 or peak == 0:
        tail = (completed.stderr or "").strip().splitlines()
        error = tail[-1] if tail else f"exit {completed.returncode}"
        # An out-of-memory kill is the interesting outcome, not a failure to report.
        return MemoryMeasurement(
            peak, method, device, seconds, label, ok=False, error=error[:200],
            baseline_bytes=baseline, n_matches=n_matches,
        )
    return MemoryMeasurement(
        peak, method, device, seconds, label,
        baseline_bytes=baseline, n_matches=n_matches,
    )


def describe_measurement_capability() -> str:
    """What this machine can and cannot measure, stated plainly."""
    from lunar_reg.device import get_device

    device = get_device()
    lines = [f"device: {device}"]

    try:
        import torch

        lines.append(f"torch: {torch.__version__} (cuda build: {torch.version.cuda})")
    except ImportError:
        lines.append("torch: not installed")
        return "\n".join(lines)

    if device == "cuda":
        props = torch.cuda.get_device_properties(0)
        free, total = torch.cuda.mem_get_info()
        lines += [
            f"gpu: {props.name}",
            f"vram: {total / 1024**3:.2f} GB total, {free / 1024**3:.2f} GB free right now",
            "",
            "VRAM measurements on this machine are REAL (cuda allocator).",
        ]
    else:
        lines += [
            "",
            "VRAM CANNOT BE MEASURED ON THIS MACHINE.",
            "  - the nvidia kernel module is not loaded, so no CUDA device is visible",
            "  - the installed torch is a CPU-only build, so it could not use one anyway",
            "",
            "Memory figures therefore come from host RSS, which captures activation",
            "tensor sizes and their scaling with tile size faithfully, but is not a",
            "VRAM number. Re-run this benchmark on a working GPU before quoting any",
            "figure as the RTX 4060's actual headroom.",
        ]
    return "\n".join(lines)
