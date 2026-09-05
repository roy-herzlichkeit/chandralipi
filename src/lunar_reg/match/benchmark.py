"""Memory benchmark for the learned matchers.

Answers one question: **at what tile size does a matcher stop fitting?**

Every figure is measured, never assumed. On a machine with a working CUDA device
the numbers come from the CUDA allocator and are real VRAM. On a machine without
one -- which includes this project's development machine, where the nvidia
kernel module is not loaded and torch is a CPU-only build -- they come from host
RSS and are explicitly labelled as *not* VRAM. See :mod:`lunar_reg.match.memory`.

Each tile size runs in a **fresh subprocess**. On CPU, ``ru_maxrss`` is a
process-lifetime high-water mark that never falls, so measuring several sizes in
one process would report the largest for every one of them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from lunar_reg.match.memory import MemoryMeasurement, measure_in_subprocess

logger = logging.getLogger(__name__)

#: Tile sides to sweep. Multiples of 64 so they stay compatible with LoFTR's
#: 1/8-then-1/2 feature pyramid.
DEFAULT_TILE_SIZES = (256, 384, 512, 640, 768, 896, 1024)

_SUBPROCESS_TEMPLATE = '''
import sys, gc, time, resource, warnings
warnings.filterwarnings("ignore")

# Emulate a fixed-capacity device. Without this a host run just swaps and slows
# to a crawl instead of failing, so "where does it break" would have no answer
# short of an OOM kill. Verified not to false-fail: a 256px LoFTR pass still
# succeeds under a 4 GB cap. Must precede the torch import, which reserves
# address space of its own.
_budget = {budget}
if _budget:
    resource.setrlimit(resource.RLIMIT_AS, (_budget, _budget))

import numpy as np, torch

def peak_bytes():
    p = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return p * 1024 if sys.platform.startswith("linux") else p

device = "cuda" if torch.cuda.is_available() else "cpu"
size = {size}
rng = np.random.default_rng(0)
a = rng.random((size, size)).astype(np.float32)
b = rng.random((size, size)).astype(np.float32)

{setup}

# Baseline: everything already resident before the forward pass -- interpreter,
# torch, model weights, inputs. Reporting it separately is what lets the caller
# isolate the activation term, which is the only part that grows with tile size.
gc.collect()
if device == "cuda":
    torch.cuda.synchronize()
    baseline = int(torch.cuda.memory_allocated())
    torch.cuda.reset_peak_memory_stats()
else:
    # ru_maxrss is a high-water mark, so this also covers any transient spike
    # during weight loading. That makes the derived activation figure a lower
    # bound, never an inflated one.
    baseline = peak_bytes()

start = time.perf_counter()
{run}
if device == "cuda":
    torch.cuda.synchronize()
elapsed = time.perf_counter() - start

if device == "cuda":
    print("PEAK_BYTES", int(torch.cuda.max_memory_allocated()))
    print("METHOD cuda_allocator")
else:
    print("PEAK_BYTES", peak_bytes())
    print("METHOD host_rss")
print("BASELINE_BYTES", baseline)
print("SECONDS", elapsed)
print("DEVICE", device)
print("N_MATCHES", n_matches)
'''

_LOFTR_SETUP = '''
import kornia.feature as KF
model = KF.LoFTR(pretrained="outdoor").to(device).eval()
t0 = torch.from_numpy(a)[None, None].to(device)
t1 = torch.from_numpy(b)[None, None].to(device)
'''

_LOFTR_RUN = '''
with torch.inference_mode():
    out = model({"image0": t0, "image1": t1})
n_matches = int(out["keypoints0"].shape[0])
'''

_LIGHTGLUE_SETUP = '''
import kornia.feature as KF
extractor = KF.DISK.from_pretrained("depth").to(device).eval()
matcher = KF.LightGlue("disk").to(device).eval()
t0 = torch.from_numpy(a)[None, None].to(device).repeat(1, 3, 1, 1)
t1 = torch.from_numpy(b)[None, None].to(device).repeat(1, 3, 1, 1)
'''

_LIGHTGLUE_RUN = '''
with torch.inference_mode():
    f0 = extractor(t0, n=2048, window_size=5, score_threshold=0.0)[0]
    f1 = extractor(t1, n=2048, window_size=5, score_threshold=0.0)[0]
    s0 = torch.tensor([a.shape[1], a.shape[0]], device=device)[None]
    s1 = torch.tensor([b.shape[1], b.shape[0]], device=device)[None]
    out = matcher({
        "image0": {"keypoints": f0.keypoints[None],
                   "descriptors": f0.descriptors[None], "image_size": s0},
        "image1": {"keypoints": f1.keypoints[None],
                   "descriptors": f1.descriptors[None], "image_size": s1},
    })
n_matches = int(out["matches"][0].shape[0])
'''

# Half precision. On CUDA this is the fp16 autocast the matchers actually use;
# on a CPU-only host the nearest available equivalent is bf16 autocast. Both are
# 2-byte, so the *ratio* against fp32 is a defensible proxy for how much
# autocast saves -- but it is a proxy, measured on a different backend, and the
# constants derived from it are labelled as such in :mod:`lunar_reg.device`.
_LOFTR_HALF_RUN = '''
_amp = (torch.autocast("cuda", dtype=torch.float16) if device == "cuda"
        else torch.autocast("cpu", dtype=torch.bfloat16))
with torch.inference_mode(), _amp:
    out = model({"image0": t0, "image1": t1})
n_matches = int(out["keypoints0"].shape[0])
'''

MATCHER_SNIPPETS = {
    "loftr": (_LOFTR_SETUP, _LOFTR_RUN),
    "loftr-half": (_LOFTR_SETUP, _LOFTR_HALF_RUN),
    "lightglue": (_LIGHTGLUE_SETUP, _LIGHTGLUE_RUN),
}


@dataclass
class BenchmarkRow:
    """One (matcher, tile size) measurement."""

    matcher: str
    tile_px: int
    measurement: MemoryMeasurement

    @property
    def ok(self) -> bool:
        return self.measurement.ok

    @property
    def peak_gb(self) -> float:
        return self.measurement.peak_gb


def benchmark_matcher(
    matcher: str = "loftr",
    tile_sizes=DEFAULT_TILE_SIZES,
    timeout: int = 900,
    budget_bytes: int | None = None,
) -> list[BenchmarkRow]:
    """Measure peak memory for one matcher across tile sizes.

    ``budget_bytes`` caps each subprocess's address space, which is how a
    CPU-only host can answer "where would an 8 GB card break?" at all -- an
    unbounded host run swaps rather than failing. The cap is address space, not
    VRAM, so the resulting break point is indicative, not a device measurement.

    Stops early once a size fails: past the first failure the larger sizes will
    fail too, and on a real GPU each failed attempt is an OOM that can leave the
    allocator fragmented.
    """
    if matcher not in MATCHER_SNIPPETS:
        raise ValueError(f"unknown matcher {matcher!r}; expected one of {sorted(MATCHER_SNIPPETS)}")

    setup, run = MATCHER_SNIPPETS[matcher]
    rows: list[BenchmarkRow] = []
    for size in tile_sizes:
        code = _SUBPROCESS_TEMPLATE.format(
            size=size, setup=setup, run=run, budget=int(budget_bytes or 0)
        )
        measurement = measure_in_subprocess(code, label=f"{matcher}@{size}px", timeout=timeout)
        rows.append(BenchmarkRow(matcher, size, measurement))
        logger.info("%s", measurement)
        if not measurement.ok:
            logger.warning(
                "%s failed at %dpx; stopping the sweep -- larger sizes cannot succeed",
                matcher, size,
            )
            break
    return rows


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


def format_report(rows: list[BenchmarkRow], budget_bytes: int | None = None) -> str:
    """Render a benchmark as a table, with the measurement caveat attached."""
    from lunar_reg.match.memory import describe_measurement_capability

    lines = [describe_measurement_capability(), "", "=" * 78]
    lines += [
        f"{'matcher':<11} {'tile':>6} {'peak':>9} {'base':>9} {'activ':>9} "
        f"{'time':>8} {'matches':>8}  status",
        "-" * 78,
    ]

    for row in rows:
        m = row.measurement
        if not m.ok:
            lines.append(
                f"{row.matcher:<11} {row.tile_px:>6} {'--':>9} {'--':>9} {'--':>9} "
                f"{'--':>8} {'--':>8}  FAILED: {m.error[:34]}"
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

    failed = [r for r in rows if not r.ok]
    if failed:
        lines += ["", f"first failure at {failed[0].tile_px}px: {failed[0].measurement.error}"]

    if rows and not rows[0].measurement.is_device_measurement:
        lines += [
            "",
            "These are HOST memory figures, not VRAM. They capture activation tensor",
            "sizes and their scaling faithfully, but the absolute numbers include the",
            "interpreter, torch, and the model weights, and the CUDA caching allocator",
            "behaves differently. Re-run on a working GPU before quoting a headroom.",
        ]
    return "\n".join(lines)
