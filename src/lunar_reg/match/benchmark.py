"""Memory benchmark for the learned matchers (``lunar-reg benchmark``).

Answers one question: **at what tile size does a matcher stop fitting?**

Every figure is measured, never assumed. With ``device="cuda"`` the numbers come
from the CUDA allocator (``torch.cuda.reset_peak_memory_stats`` before the
forward pass, ``torch.cuda.max_memory_allocated`` after it) and are real VRAM.
With ``device="cpu"`` they come from host RSS and are explicitly labelled as
*not* VRAM. See :mod:`lunar_reg.match.memory`.

Each tile size runs in a **fresh subprocess**. On CPU, ``ru_maxrss`` is a
process-lifetime high-water mark that never falls, so measuring several sizes in
one process would report the largest for every one of them. Every measurement
is classified (:class:`~lunar_reg.match.memory.MeasureOutcome`); the sweep stops
at the first ``OOM`` only, and other failures are recorded and the sweep goes on.

:func:`fit_profile` turns the ``OK`` rows into a CONTRACTS C16 per-precision
entry (``peak_bytes = fixed_bytes + bytes_per_px * tile_px**2``, least squares).
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

from lunar_reg.match.memory import (
    MeasureDiagnostics,
    MeasureOutcome,
    MemoryMeasurement,
    measure_in_subprocess,
)

logger = logging.getLogger(__name__)

#: Tile sides to sweep. Multiples of 64 so they stay compatible with LoFTR's
#: 1/8-then-1/2 feature pyramid.
DEFAULT_TILE_SIZES = (256, 384, 512, 640, 768, 896, 1024)

#: Matchers and precisions the benchmark can measure.
MATCHERS = ("loftr", "lightglue")
PRECISIONS = ("fp16", "fp32")

#: DISK keypoints per image in the LightGlue snippet (``DEFAULT_MAX_KEYPOINTS``
#: in :mod:`lunar_reg.device`, the cap ``plan_keypoint_budget`` gives a GPU with
#: 5-10 GB free).
LIGHTGLUE_KEYPOINTS = 2048

_SUBPROCESS_TEMPLATE = """
import sys, gc, time, resource, warnings
warnings.filterwarnings("ignore")

device = {device!r}

# CPU only (AUDIT A075): emulate a fixed-capacity device. Without this a host
# run just swaps and slows to a crawl instead of failing, so "where does it
# break" would have no answer short of an OOM kill. Must precede the torch
# import, which reserves address space of its own. Never applied on CUDA: an
# address-space cap there limits the CUDA runtime's mappings, not VRAM.
_budget = {budget}
if _budget and device == "cpu":
    resource.setrlimit(resource.RLIMIT_AS, (_budget, _budget))

import numpy as np, torch

if device.startswith("cuda") and not torch.cuda.is_available():
    sys.exit("SETUP: device " + device + " requested but torch.cuda.is_available() is False")

def peak_bytes():
    p = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return p * 1024 if sys.platform.startswith("linux") else p

size = {size}
rng = np.random.default_rng(0)
a = rng.random((size, size)).astype(np.float32)
b = rng.random((size, size)).astype(np.float32)

{setup}

# Baseline: everything already resident before the forward pass -- interpreter,
# torch, model weights, inputs. Reporting it separately is what lets the caller
# isolate the activation term, which is the only part that grows with tile size.
gc.collect()
if device.startswith("cuda"):
    torch.cuda.synchronize(device)
    baseline = int(torch.cuda.memory_allocated(device))
    torch.cuda.reset_peak_memory_stats(device)
else:
    # ru_maxrss is a high-water mark, so this also covers any transient spike
    # during weight loading. That makes the derived activation figure a lower
    # bound, never an inflated one.
    baseline = peak_bytes()

start = time.perf_counter()
{run}
if device.startswith("cuda"):
    torch.cuda.synchronize(device)
elapsed = time.perf_counter() - start

if device.startswith("cuda"):
    print("PEAK_BYTES", int(torch.cuda.max_memory_allocated(device)))
    print("METHOD cuda_allocator")
else:
    print("PEAK_BYTES", peak_bytes())
    print("METHOD host_rss")
print("BASELINE_BYTES", baseline)
print("SECONDS", elapsed)
print("DEVICE", device)
print("N_MATCHES", n_matches)
"""

_LOFTR_SETUP = """
import kornia.feature as KF
model = KF.LoFTR(pretrained="outdoor").to(device).eval()
t0 = torch.from_numpy(a)[None, None].to(device)
t1 = torch.from_numpy(b)[None, None].to(device)
"""

_LOFTR_RUN = """
with torch.inference_mode():
    out = model({"image0": t0, "image1": t1})
n_matches = int(out["keypoints0"].shape[0])
"""

_LIGHTGLUE_SETUP = """
import kornia.feature as KF
extractor = KF.DISK.from_pretrained("depth").to(device).eval()
matcher = KF.LightGlue("disk").to(device).eval()
t0 = torch.from_numpy(a)[None, None].to(device).repeat(1, 3, 1, 1)
t1 = torch.from_numpy(b)[None, None].to(device).repeat(1, 3, 1, 1)
"""

_LIGHTGLUE_RUN = """
with torch.inference_mode():
    f0 = extractor(t0, n={n_kp}, window_size=5, score_threshold=0.0)[0]
    f1 = extractor(t1, n={n_kp}, window_size=5, score_threshold=0.0)[0]
    s0 = torch.tensor([a.shape[1], a.shape[0]], device=device)[None]
    s1 = torch.tensor([b.shape[1], b.shape[0]], device=device)[None]
    out = matcher({
        "image0": {"keypoints": f0.keypoints[None],
                   "descriptors": f0.descriptors[None], "image_size": s0},
        "image1": {"keypoints": f1.keypoints[None],
                   "descriptors": f1.descriptors[None], "image_size": s1},
    })
n_matches = int(out["matches"][0].shape[0])
"""

# Half precision. On CUDA this is the fp16 autocast the matchers actually use;
# on CPU the nearest available equivalent is bf16 autocast. Both are 2-byte, so
# the *ratio* against fp32 is a defensible proxy for how much autocast saves --
# but it is a proxy, measured on a different backend, and only a CUDA run is a
# device measurement.
_HALF_AUTOCAST = """
_amp = (torch.autocast("cuda", dtype=torch.float16) if device.startswith("cuda")
        else torch.autocast("cpu", dtype=torch.bfloat16))
"""

_LOFTR_HALF_RUN = (
    _HALF_AUTOCAST
    + """
with torch.inference_mode(), _amp:
    out = model({"image0": t0, "image1": t1})
n_matches = int(out["keypoints0"].shape[0])
"""
)

# As in ``lunar_reg.match.learned.LightGlueMatcher``: DISK under half autocast,
# LightGlue outside it in fp32 (kornia's LightGlue positional encoding is fp32,
# and fp16 input under an outer autocast raises on CUDA).
_LIGHTGLUE_HALF_RUN = (
    _HALF_AUTOCAST
    + """
with torch.inference_mode():
    with _amp:
        f0 = extractor(t0, n={n_kp}, window_size=5, score_threshold=0.0)[0]
        f1 = extractor(t1, n={n_kp}, window_size=5, score_threshold=0.0)[0]
    s0 = torch.tensor([a.shape[1], a.shape[0]], device=device)[None]
    s1 = torch.tensor([b.shape[1], b.shape[0]], device=device)[None]
    out = matcher({
        "image0": {"keypoints": f0.keypoints.float()[None],
                   "descriptors": f0.descriptors.float()[None], "image_size": s0},
        "image1": {"keypoints": f1.keypoints.float()[None],
                   "descriptors": f1.descriptors.float()[None], "image_size": s1},
    })
n_matches = int(out["matches"][0].shape[0])
"""
)

#: ``(matcher, precision) -> (setup, run)`` snippets.
SNIPPETS = {
    ("loftr", "fp32"): (_LOFTR_SETUP, _LOFTR_RUN),
    ("loftr", "fp16"): (_LOFTR_SETUP, _LOFTR_HALF_RUN),
    ("lightglue", "fp32"): (_LIGHTGLUE_SETUP, _LIGHTGLUE_RUN),
    ("lightglue", "fp16"): (_LIGHTGLUE_SETUP, _LIGHTGLUE_HALF_RUN),
}


def build_snippet(
    matcher: str, precision: str, size: int, device: str, budget_bytes: int | None = None
) -> str:
    """The measuring program for one ``(matcher, precision, size, device)``."""
    if (matcher, precision) not in SNIPPETS:
        raise ValueError(
            f"unknown matcher/precision {matcher!r}/{precision!r}; "
            f"expected matcher in {MATCHERS}, precision in {PRECISIONS}"
        )
    setup, run = SNIPPETS[(matcher, precision)]
    budget = int(budget_bytes or 0) if device == "cpu" else 0
    return _SUBPROCESS_TEMPLATE.format(
        device=device,
        budget=budget,
        size=int(size),
        setup=setup,
        run=run.replace("{n_kp}", str(LIGHTGLUE_KEYPOINTS)),
    )


@dataclass
class BenchmarkRow:
    """One (matcher, tile size) measurement."""

    matcher: str
    tile_px: int
    measurement: MemoryMeasurement

    @property
    def outcome(self) -> MeasureOutcome:
        return self.measurement.outcome

    @property
    def ok(self) -> bool:
        return self.measurement.outcome is MeasureOutcome.OK and self.measurement.ok

    @property
    def peak_gb(self) -> float:
        return self.measurement.peak_gb

    def as_dict(self) -> dict:
        """JSON row: the measurement plus the provenance of ``peak_bytes``."""
        from lunar_reg.provenance import ValueSource

        m = self.measurement
        return {
            "matcher": self.matcher,
            "tile_px": int(self.tile_px),
            "outcome": m.outcome.value,
            "peak_bytes": int(m.peak_bytes),
            "baseline_bytes": int(m.baseline_bytes),
            "activation_bytes": int(m.activation_bytes) if self.ok else 0,
            # A failed run produced no figure; its zero is a placeholder.
            "peak_source": (ValueSource.MEASURED if self.ok else ValueSource.UNKNOWN).value,
            "method": m.method,
            "device": m.device,
            "is_device_measurement": m.is_device_measurement,
            "seconds": float(m.seconds),
            "n_matches": m.n_matches,
            "error": m.error,
        }


def diagnose(rows: list[BenchmarkRow]) -> MeasureDiagnostics:
    """Per-outcome counts and the first sample of each, over a sweep's rows."""
    diag = MeasureDiagnostics()
    for row in rows:
        m = row.measurement
        detail = m.error or f"{m.peak_bytes} bytes peak via {m.method}"
        diag.record(row.outcome, f"{m.label or f'{row.matcher}@{row.tile_px}px'}: {detail}")
    return diag


def benchmark_matcher(
    matcher: str = "loftr",
    tile_sizes=DEFAULT_TILE_SIZES,
    timeout: int = 900,
    budget_bytes: int | None = None,
    *,
    device: str | None = None,
    precision: str = "fp32",
) -> list[BenchmarkRow]:
    """Measure peak memory for one matcher and precision across tile sizes.

    ``device`` is ``"cpu"``, ``"cuda"`` or ``"cuda:<n>"`` (default: what
    :func:`lunar_reg.device.get_device` picks). ``budget_bytes`` caps each
    subprocess's address space with ``RLIMIT_AS`` on CPU only, which is how a
    host run can answer "where would an N GB device break?" at all -- an
    unbounded host run swaps rather than failing. The cap is address space, not
    VRAM, so the resulting break point is indicative, not a device
    measurement. On CUDA ``budget_bytes`` is ignored (AUDIT A075).

    Every size is classified. The sweep stops at the first ``OOM`` only: past
    it the larger sizes cannot fit, and on a GPU each failed attempt is an OOM.
    A ``TIMEOUT``, ``SETUP_ERROR`` or ``NO_OUTPUT`` is recorded and the sweep
    goes on. Logs one summary line.
    """
    from lunar_reg.device import get_device

    device = device or get_device()
    if (matcher, precision) not in SNIPPETS:
        raise ValueError(
            f"unknown matcher/precision {matcher!r}/{precision!r}; "
            f"expected matcher in {MATCHERS}, precision in {PRECISIONS}"
        )
    if budget_bytes and device != "cpu":
        logger.warning(
            "budget_bytes=%d ignored on %s: RLIMIT_AS applies to CPU runs only",
            budget_bytes,
            device,
        )

    rows: list[BenchmarkRow] = []
    for size in tile_sizes:
        code = build_snippet(matcher, precision, size, device, budget_bytes)
        label = f"{matcher}-{precision}@{size}px"
        measurement = measure_in_subprocess(code, label=label, timeout=timeout)
        rows.append(BenchmarkRow(matcher, int(size), measurement))
        logger.debug("%s", measurement)
        if measurement.outcome is MeasureOutcome.OOM:
            break

    diag = diagnose(rows)
    stopped = rows[-1].tile_px if rows and rows[-1].outcome is MeasureOutcome.OOM else None
    logger.info(
        "benchmark %s %s on %s: %d sizes, %s%s",
        matcher,
        precision,
        device,
        len(rows),
        ", ".join(f"{k} {v}" for k, v in sorted(diag.counts.items())) or "nothing run",
        f"; stopped at OOM at {stopped}px" if stopped is not None else "",
    )
    return rows


def oom_stop_px(rows: list[BenchmarkRow]) -> int | None:
    """Tile size at which the sweep stopped on ``OOM``; ``None`` when it did not."""
    for row in rows:
        if row.outcome is MeasureOutcome.OOM:
            return row.tile_px
    return None


#: OK rows :func:`fit_profile` needs (two unknowns, one spare to over-determine).
MIN_FIT_ROWS = 3


def fit_profile(rows: list[BenchmarkRow]) -> dict:
    """Least-squares fit of ``peak_bytes = fixed + k * tile_px**2`` over the ``OK`` rows.

    Returns the CONTRACTS C16 per-precision entry: ``fixed_bytes`` (int, the
    intercept; it may be negative when the data curve upwards, which
    :meth:`lunar_reg.device.DeviceProfile.plan_tile` guards against),
    ``bytes_per_px`` (``k``), ``max_tile_px`` (the largest measured ``OK`` tile,
    floored to a multiple of 64) and ``points`` (the ``[tile_px, peak_bytes]``
    pairs the fit used).

    Raises ``ValueError`` when fewer than :data:`MIN_FIT_ROWS` rows are ``OK``,
    when the rows mix matchers, when the ``OK`` rows have fewer than two
    distinct tile sizes, or when the fitted ``k`` is not positive (a profile
    with ``bytes_per_px <= 0`` is refused by ``DeviceProfile.load``).
    """
    import numpy as np

    matchers = {r.matcher for r in rows}
    if len(matchers) > 1:
        raise ValueError(f"fit_profile: rows mix matchers {sorted(matchers)}")
    ok = sorted((r for r in rows if r.ok), key=lambda r: r.tile_px)
    if len(ok) < MIN_FIT_ROWS:
        raise ValueError(
            f"fit_profile: {len(ok)} OK rows, need >= {MIN_FIT_ROWS} "
            f"(outcomes: {[r.outcome.value for r in rows]})"
        )
    if len({r.tile_px for r in ok}) < 2:
        raise ValueError("fit_profile: the OK rows need at least two distinct tile sizes")

    side = np.array([float(r.tile_px) for r in ok])
    peak = np.array([float(r.measurement.peak_bytes) for r in ok])
    design = np.column_stack([np.ones_like(side), side**2])
    (fixed, per_px), *_ = np.linalg.lstsq(design, peak, rcond=None)
    if not np.isfinite(per_px) or per_px <= 0:
        raise ValueError(f"fit_profile: fitted bytes_per_px {per_px!r} is not > 0")

    largest = max(r.tile_px for r in ok)
    return {
        "fixed_bytes": int(round(float(fixed))),
        "bytes_per_px": float(per_px),
        "max_tile_px": int(largest // 64 * 64),
        "points": [[int(r.tile_px), int(r.measurement.peak_bytes)] for r in ok],
    }


def scaling_exponent(rows: list[BenchmarkRow]) -> float | None:
    """Least-squares fit of ``log(activation bytes)`` against ``log(tile side)``.

    Fitting all points rather than dividing the endpoints matters: a single
    anomalous size (a padding step, an allocator plateau) would otherwise set the
    whole exponent. Returns ``None`` when fewer than two sizes succeeded.
    """
    import math

    pts = [
        (math.log(r.tile_px), math.log(r.measurement.activation_bytes))
        for r in rows
        if r.ok and r.measurement.activation_bytes > 0
    ]
    if len(pts) < 2:
        return None
    n = len(pts)
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    denom = sum((x - mx) ** 2 for x, _ in pts)
    if denom == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in pts) / denom


def format_report(
    rows: list[BenchmarkRow], budget_bytes: int | None = None, device: str | None = None
) -> str:
    """Render a benchmark as a table, with the measurement caveat attached.

    ``device`` is the device the rows were measured on (passed to
    :func:`~lunar_reg.match.memory.describe_measurement_capability`). On CUDA
    that call queries free memory, which creates a CUDA context in this
    process, so call it after the sweep, never during it.
    """
    from lunar_reg.match.memory import describe_measurement_capability

    lines = [describe_measurement_capability(device), "", "=" * 78]
    lines += [
        f"{'matcher':<11} {'tile':>6} {'peak':>9} {'base':>9} {'activ':>9} "
        f"{'time':>8} {'matches':>8}  status",
        "-" * 78,
    ]

    for row in rows:
        m = row.measurement
        if not row.ok:
            lines.append(
                f"{row.matcher:<11} {row.tile_px:>6} {'--':>9} {'--':>9} {'--':>9} "
                f"{'--':>8} {'--':>8}  {row.outcome.value.upper()}: {m.error[:30]}"
            )
            continue
        note = ""
        if budget_bytes and m.peak_bytes > budget_bytes:
            note = " OVER BUDGET"
        base = f"{m.baseline_bytes / 1024**3:>8.3f}G" if m.has_baseline else f"{'--':>9}"
        act = f"{m.activation_gb:>8.3f}G" if m.has_baseline else f"{'--':>9}"
        matches = "--" if m.n_matches is None else str(m.n_matches)
        lines.append(
            f"{row.matcher:<11} {row.tile_px:>6} {m.peak_gb:>8.3f}G {base} {act} "
            f"{m.seconds:>7.1f}s {matches:>8}  ok{note}"
        )

    ok_rows = [r for r in rows if r.ok and r.measurement.activation_bytes > 0]
    if len(ok_rows) >= 3:
        import math

        lines += ["", "local exponent between adjacent sizes (a single global fit hides a"]
        lines += ["regime change, and for a dense matcher there is one):"]
        for prev, cur in zip(ok_rows, ok_rows[1:], strict=False):
            side_ratio = cur.tile_px / prev.tile_px
            mem_ratio = cur.measurement.activation_bytes / prev.measurement.activation_bytes
            local = math.log(mem_ratio) / math.log(side_ratio)
            lines.append(
                f"  {prev.tile_px:>5} -> {cur.tile_px:<5} "
                f"{prev.measurement.activation_gb:6.3f}G -> {cur.measurement.activation_gb:6.3f}G"
                f"   side^{local:.2f}"
            )

    exponent = scaling_exponent(rows)
    if exponent is not None:
        lines += [
            "",
            f"activation scaling: memory ~ side^{exponent:.2f} "
            f"(least-squares fit over {sum(1 for r in rows if r.ok)} sizes)",
            "  note this is fitted on peak MINUS baseline. Fitting raw peak would",
            "  read far too low, because the fixed interpreter/weights term",
            "  dominates at small tiles and flattens the curve.",
        ]

    lines += [
        "",
        "The matches column is a liveness check only. Inputs are independent random",
        "noise, so any correspondence found is spurious; memory is what is measured",
        "here, not matching quality.",
    ]

    stopped = oom_stop_px(rows)
    if stopped is not None:
        lines += ["", f"sweep stopped at the first OOM, {stopped}px; larger sizes not run"]
    failed = [r for r in rows if not r.ok and r.outcome is not MeasureOutcome.OOM]
    if failed:
        first = failed[0]
        lines += [
            "",
            f"{len(failed)} non-OOM failure(s) recorded, sweep continued; first at "
            f"{first.tile_px}px ({first.outcome.value}): {first.measurement.error}",
        ]

    if any(r.ok and not r.measurement.is_device_measurement for r in rows):
        lines += [
            "",
            "These are HOST memory figures, not VRAM. They capture activation tensor",
            "sizes and their scaling faithfully, but the absolute numbers include the",
            "interpreter, torch, and the model weights, and the CUDA caching allocator",
            "behaves differently. Re-run on a working GPU before quoting a headroom.",
        ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Device facts and the C16 profile merge (``lunar-reg benchmark --profile-out``)
# ---------------------------------------------------------------------------


def _cuda_index(device: str) -> int:
    """Device index of ``"cuda"`` (current device) or ``"cuda:<n>"``."""
    if ":" in device:
        return int(device.split(":")[1])
    import torch

    return int(torch.cuda.current_device())


def _nvidia_smi(index: int, fields: str) -> list[str] | None:
    """One ``nvidia-smi --query-gpu=<fields>`` row for GPU ``index``; ``None`` on failure."""
    try:
        done = subprocess.run(
            [
                "nvidia-smi",
                "-i",
                str(index),
                f"--query-gpu={fields}",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("nvidia-smi --query-gpu=%s failed: %s", fields, exc)
        return None
    lines = done.stdout.strip().splitlines()
    if done.returncode != 0 or not lines:
        logger.warning(
            "nvidia-smi --query-gpu=%s exit %d: %s",
            fields,
            done.returncode,
            (done.stderr.strip() or "no output")[:200],
        )
        return None
    return [v.strip() for v in lines[0].split(",")]


def free_bytes_before_sweep(device: str) -> int | None:
    """Free device memory from ``nvidia-smi`` (MiB -> bytes), or ``None`` when unreadable.

    Read from the driver rather than ``torch.cuda.mem_get_info``: the latter
    creates a CUDA context in this (parent) process, which would hold device
    memory for the whole sweep and shrink what each measuring subprocess can use.

    Never raises: when torch sees no CUDA device (or the index cannot be
    resolved) this returns ``None`` (``UNKNOWN``), and the sweep itself then
    classifies every size as ``setup_error``.
    """
    if not device.startswith("cuda"):
        return None
    try:
        if ":" not in device:
            import torch

            if not torch.cuda.is_available():
                logger.warning("free memory before sweep: torch sees no CUDA device")
                return None
        index = _cuda_index(device)
    except (ImportError, RuntimeError, AssertionError, ValueError) as exc:
        logger.warning("free memory before sweep: cannot resolve %r: %s", device, exc)
        return None
    row = _nvidia_smi(index, "memory.free")
    try:
        return int(float(row[0]) * 1024**2) if row else None
    except ValueError:
        return None


def cuda_device_facts(device: str) -> dict:
    """``device_name``, ``total_bytes``, ``torch``, ``cuda`` and ``driver`` for a C16 profile.

    ``device_name`` is ``torch.cuda.get_device_name`` (what
    :func:`lunar_reg.device.load_profile_for` matches), ``total_bytes`` the
    device's ``total_memory``; ``driver`` comes from ``nvidia-smi
    --query-gpu=driver_version`` and is ``"unknown"`` when that fails. Raises
    ``RuntimeError`` when torch sees no CUDA device.
    """
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError(f"no CUDA device visible to torch for {device!r}")
    index = _cuda_index(device)
    props = torch.cuda.get_device_properties(index)
    row = _nvidia_smi(index, "driver_version")
    return {
        "device_name": str(props.name),
        "total_bytes": int(props.total_memory),
        "torch": str(torch.__version__),
        "cuda": str(torch.version.cuda),
        "driver": row[0] if row else "unknown",
    }


def merge_profile_entry(
    path,
    matcher: str,
    precision: str,
    entry: dict,
    *,
    facts: dict,
    measured_utc: str,
    run_record: str,
    free_bytes_at_measure: int | None,
):
    """Merge one fitted entry into the C16 profile at ``path`` and write it.

    A missing file is created (``slug`` = the file stem) from ``facts``
    (:func:`cuda_device_facts`). An existing file is loaded and validated
    (``DeviceProfile.load``); its ``device_name`` must equal
    ``facts["device_name"]`` (``ValueError`` otherwise: a profile describes one
    device). The ``(matcher, precision)`` entry is replaced; ``measured_utc``,
    ``run_record``, ``free_bytes_at_measure``, ``torch``, ``cuda`` and ``driver``
    describe the latest run. The written file is re-loaded to prove it is
    C16-valid. Returns the :class:`~lunar_reg.device.DeviceProfile`.
    """
    from pathlib import Path

    from lunar_reg.device import DeviceProfile
    from lunar_reg.provenance import ValueSource

    path = Path(path)
    if path.exists():
        profile = DeviceProfile.load(path)
        if profile.device_name != facts["device_name"]:
            raise ValueError(
                f"{path}: profile is for {profile.device_name!r}, this run measured "
                f"{facts['device_name']!r}; write a separate profile per device"
            )
        changed = {
            k: (profile.extra.get(k), facts[k])
            for k in ("torch", "cuda", "driver")
            if k in profile.extra and profile.extra.get(k) != facts[k]
        }
        if changed:
            logger.warning(
                "%s: versions changed since earlier entries were measured %s; the file "
                "records the latest run's",
                path,
                changed,
            )
    else:
        profile = DeviceProfile(
            slug=path.stem,
            device_name=facts["device_name"],
            total_bytes=int(facts["total_bytes"]),
            matchers={},
            measured_utc=measured_utc,
            source=ValueSource.MEASURED,
            path=path,
        )
    profile.matchers.setdefault(matcher, {})[precision] = dict(entry)
    profile.total_bytes = int(facts["total_bytes"])
    profile.measured_utc = measured_utc
    profile.extra.update(
        {
            "free_bytes_at_measure": free_bytes_at_measure,
            "torch": facts["torch"],
            "cuda": facts["cuda"],
            "driver": facts["driver"],
            "run_record": run_record,
        }
    )
    profile.save(path)
    return DeviceProfile.load(path)
