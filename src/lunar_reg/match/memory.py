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
can never mistake one for the other, and a :class:`MeasureOutcome` so a failed
measurement is classified (OOM, timeout, setup error, no output) rather than
reported as a bare ``ok=False``.
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
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

CUDA_ALLOCATOR = "cuda_allocator"
HOST_RSS = "host_rss"
#: ``method`` / ``device`` when the measuring snippet did not report them. Never
#: substituted with this host's defaults: a figure whose backend is not known
#: must not read as a host-RSS (or a VRAM) number.
UNKNOWN = "unknown"


class MeasureOutcome(str, Enum):
    """How one memory measurement ended (AUDIT A076).

    Parsed from the measuring subprocess, in this order: exit 0 with a
    ``PEAK_BYTES`` line -> ``OK``; stderr carrying an out-of-memory marker
    (:data:`OOM_MARKERS`), or death by SIGKILL -> ``OOM``;
    ``subprocess.TimeoutExpired`` -> ``TIMEOUT``; any other non-zero exit ->
    ``SETUP_ERROR``; exit 0 without ``PEAK_BYTES`` -> ``NO_OUTPUT``.
    """

    OK = "ok"
    #: The run ran out of memory (CUDA allocator, host allocator, or killed by
    #: SIGKILL, which is what the kernel / cgroup OOM killer sends).
    OOM = "oom"
    #: The run did not finish within the timeout.
    TIMEOUT = "timeout"
    #: The run failed for a reason other than memory: import error, missing
    #: CUDA device, a bad snippet, a crash.
    SETUP_ERROR = "setup_error"
    #: The run exited 0 but printed no ``PEAK_BYTES`` line: the snippet is broken.
    NO_OUTPUT = "no_output"

    @property
    def is_failure(self) -> bool:
        return self is not MeasureOutcome.OK


#: Substrings of stderr that mean the run ran out of memory. The first two are
#: torch's CUDA OOM (``torch.OutOfMemoryError: CUDA out of memory``); the last
#: two are the host-side equivalents a CPU run under ``RLIMIT_AS`` raises
#: (Python's ``MemoryError``, torch's CPU allocator failure).
OOM_MARKERS = (
    "OutOfMemoryError",
    "CUDA out of memory",
    "MemoryError",
    "DefaultCPUAllocator: can't allocate memory",
)

#: Return code of a child killed by SIGKILL (the kernel / cgroup OOM killer).
_SIGKILL_RETURNCODE = -9


def _is_oom(returncode: int, stderr: str) -> bool:
    return returncode == _SIGKILL_RETURNCODE or any(m in stderr for m in OOM_MARKERS)


@dataclass
class MeasureDiagnostics:
    """Per-outcome counts and the first sample of each (classified-outcomes pattern)."""

    counts: dict[str, int] = field(default_factory=dict)
    samples: dict[str, str] = field(default_factory=dict)

    def record(self, outcome: MeasureOutcome, sample: str) -> None:
        self.counts[outcome.value] = self.counts.get(outcome.value, 0) + 1
        self.samples.setdefault(outcome.value, sample[:200])

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def n_failures(self) -> int:
        return sum(n for k, n in self.counts.items() if k != MeasureOutcome.OK.value)

    def report(self) -> str:
        """One header line, then ``  <outcome>: <count>  e.g. <sample>`` per outcome."""
        lines = [
            f"memory measurements: {self.total} run, "
            f"{self.counts.get(MeasureOutcome.OK.value, 0)} ok, {self.n_failures} failed"
        ]
        for key in sorted(self.counts):
            lines.append(f"  {key}: {self.counts[key]}  e.g. {self.samples.get(key, '')}")
        return "\n".join(lines)


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
    #: How the measurement ended. ``ok`` above stays for existing callers and
    #: always equals ``outcome is MeasureOutcome.OK`` for results built here.
    outcome: MeasureOutcome = MeasureOutcome.OK

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
        return {
            **asdict(self),
            "outcome": self.outcome.value,
            "peak_gb": self.peak_gb,
            "is_device_measurement": self.is_device_measurement,
        }

    def __str__(self) -> str:
        if not self.ok or self.outcome.is_failure:
            status = self.outcome.value.upper() if self.outcome.is_failure else "FAILED"
            return f"{self.label}: {status} ({self.error})"
        qualifier = "" if self.is_device_measurement else " (host proxy, NOT VRAM)"
        act = f", {self.activation_gb:.3f} GB activations" if self.has_baseline else ""
        return f"{self.label}: {self.peak_gb:.3f} GB peak{qualifier}{act}, {self.seconds:.2f}s"


def _exception_outcome(error: str) -> MeasureOutcome:
    """``OOM`` when an in-process exception text names an out-of-memory error."""
    if any(m in error for m in OOM_MARKERS):
        return MeasureOutcome.OOM
    return MeasureOutcome.SETUP_ERROR


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
            error = f"{type(exc).__name__}: {exc}"
            return None, MemoryMeasurement(
                0,
                CUDA_ALLOCATOR,
                device,
                time.perf_counter() - start,
                label,
                ok=False,
                error=error[:200],
                outcome=_exception_outcome(error),
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
    except Exception as exc:  # noqa: BLE001 - any failure of fn is classified, not raised
        error = f"{type(exc).__name__}: {exc}"
        return None, MemoryMeasurement(
            0,
            HOST_RSS,
            device,
            time.perf_counter() - start,
            label,
            ok=False,
            error=error[:200],
            outcome=_exception_outcome(error),
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
    print ``BASELINE_BYTES <int>`` (memory held before the measured call),
    ``N_MATCHES <int>``, ``METHOD <name>`` and ``DEVICE <name>``. ``method`` and
    ``device`` the snippet did not report are ``"unknown"``.

    Never raises for a failed run: the result's :attr:`~MemoryMeasurement.outcome`
    classifies it (see :class:`MeasureOutcome` for the parsing order) and
    ``error`` holds the last stderr line (at most 200 characters).
    """
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PYTHONWARNINGS": "ignore"},
        )
    except subprocess.TimeoutExpired:
        return MemoryMeasurement(
            0,
            UNKNOWN,
            UNKNOWN,
            time.perf_counter() - start,
            label,
            ok=False,
            error=f"timed out after {timeout}s",
            outcome=MeasureOutcome.TIMEOUT,
        )

    peak, seconds, method, device = 0, 0.0, UNKNOWN, UNKNOWN
    baseline, n_matches = 0, None
    has_peak = False
    for line in (completed.stdout or "").splitlines():
        if line.startswith("PEAK_BYTES "):
            peak = int(line.split()[1])
            has_peak = True
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

    stderr = completed.stderr or ""
    rc = completed.returncode
    if rc == 0 and has_peak:
        return MemoryMeasurement(
            peak,
            method,
            device,
            seconds,
            label,
            baseline_bytes=baseline,
            n_matches=n_matches,
        )
    if _is_oom(rc, stderr):
        outcome = MeasureOutcome.OOM
    elif rc != 0:
        outcome = MeasureOutcome.SETUP_ERROR
    else:
        outcome = MeasureOutcome.NO_OUTPUT

    tail = stderr.strip().splitlines()
    if outcome is MeasureOutcome.NO_OUTPUT:
        error = "exit 0 but no PEAK_BYTES line"
    elif tail:
        error = tail[-1]
    elif rc == _SIGKILL_RETURNCODE:
        error = "killed by SIGKILL (the OOM killer sends it)"
    else:
        error = f"exit {rc}"
    return MemoryMeasurement(
        peak,
        method,
        device,
        seconds,
        label,
        ok=False,
        error=error[:200],
        baseline_bytes=baseline,
        n_matches=n_matches,
        outcome=outcome,
    )


def describe_measurement_capability(device: str | None = None) -> str:
    """What this run can and cannot measure, stated from what torch reports.

    ``device`` is the device the benchmark measures on (default: what
    :func:`lunar_reg.device.get_device` picks). Only facts torch itself reports
    are stated; no claim is made about why CUDA is unavailable.
    """
    from lunar_reg.device import get_device

    device = device or get_device()
    lines = [f"device: {device}"]

    try:
        import torch

        lines.append(f"torch: {torch.__version__} (cuda build: {torch.version.cuda})")
    except ImportError:
        lines.append("torch: not installed")
        return "\n".join(lines)

    cuda_ok = bool(torch.cuda.is_available())
    if device.startswith("cuda") and cuda_ok:
        index = torch.device(device).index
        index = torch.cuda.current_device() if index is None else index
        props = torch.cuda.get_device_properties(index)
        free, total = torch.cuda.mem_get_info(index)
        lines += [
            f"gpu: {props.name}",
            f"vram: {total / 1024**3:.2f} GB total, {free / 1024**3:.2f} GB free right now",
            "",
            "VRAM measurements in this run are REAL (cuda allocator).",
        ]
    elif device.startswith("cuda"):
        lines += [
            "",
            "CUDA WAS REQUESTED BUT torch.cuda.is_available() IS False.",
            "  Every measurement on this device will fail as setup_error.",
        ]
    else:
        reason = (
            "a CUDA device is visible, but this run measures on the CPU by request"
            if cuda_ok
            else "torch.cuda.is_available() is False, so there is no CUDA device to measure"
        )
        lines += [
            "",
            "THESE MEASUREMENTS ARE NOT VRAM.",
            f"  - {reason}",
            "",
            "Memory figures therefore come from host RSS, which captures activation",
            "tensor sizes and their scaling with tile size faithfully, but is not a",
            "VRAM number. Measure with --device cuda before quoting any figure as a",
            "GPU's headroom.",
        ]
    return "\n".join(lines)
