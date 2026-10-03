"""Free-memory readings (CONTRACTS C17): measured, device-index aware, never a nameplate."""

from __future__ import annotations

import pytest

from lunar_reg import device
from lunar_reg.device import MemoryReading, free_memory_bytes, free_vram_bytes
from lunar_reg.provenance import ValueSource

_FAKE_MEMINFO = """\
MemTotal:       15997032 kB
MemFree:         2821120 kB
MemAvailable:   13183488 kB
Buffers:          123456 kB
HugePages_Total:       0
"""


def test_cpu_reading_from_fake_meminfo(monkeypatch):
    monkeypatch.setattr(device, "_read_proc_meminfo", lambda: _FAKE_MEMINFO)
    r = free_memory_bytes("cpu")
    assert r == MemoryReading("cpu", 13183488 * 1024, 15997032 * 1024, ValueSource.MEASURED)
    assert free_vram_bytes("cpu") == 13183488 * 1024


def test_cpu_reading_is_not_the_nameplate(monkeypatch):
    monkeypatch.setattr(device, "_read_proc_meminfo", lambda: _FAKE_MEMINFO)
    assert free_vram_bytes("cpu") != device.ASSUMED_TOTAL_VRAM_BYTES


def test_cpu_meminfo_missing_field_is_unknown(monkeypatch):
    monkeypatch.setattr(device, "_read_proc_meminfo", lambda: "MemTotal: 1024 kB\n")
    assert free_memory_bytes("cpu") == MemoryReading("cpu", 0, 0, ValueSource.UNKNOWN)


def test_cpu_meminfo_unreadable_is_unknown(monkeypatch):
    def boom() -> str:
        raise OSError("no /proc here")

    monkeypatch.setattr(device, "_read_proc_meminfo", boom)
    r = free_memory_bytes("cpu")
    assert (r.free_bytes, r.total_bytes, r.source) == (0, 0, ValueSource.UNKNOWN)
    assert free_vram_bytes("cpu") == 0


class _FakeCuda:
    """Stands in for ``torch.cuda``; records which index was queried."""

    def __init__(self, current: int = 0, fail: bool = False) -> None:
        self.current = current
        self.fail = fail
        self.queried: list[int] = []

    def current_device(self) -> int:
        return self.current

    def mem_get_info(self, index: int) -> tuple[int, int]:
        self.queried.append(index)
        if self.fail:
            raise RuntimeError("CUDA error: invalid device ordinal")
        return (1000 + index, 8000 + index)


def _patch_cuda(monkeypatch, fake: _FakeCuda) -> None:
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(torch, "cuda", fake)


def test_cuda_index_is_passed_through(monkeypatch):
    fake = _FakeCuda()
    _patch_cuda(monkeypatch, fake)
    r = free_memory_bytes("cuda:0")
    assert r == MemoryReading("cuda:0", 1000, 8000, ValueSource.MEASURED)
    r1 = free_memory_bytes("cuda:1")
    assert r1 == MemoryReading("cuda:1", 1001, 8001, ValueSource.MEASURED)
    assert fake.queried == [0, 1]


def test_bare_cuda_uses_the_current_device(monkeypatch):
    fake = _FakeCuda(current=2)
    _patch_cuda(monkeypatch, fake)
    r = free_memory_bytes("cuda")
    assert (r.free_bytes, r.total_bytes, r.source) == (1002, 8002, ValueSource.MEASURED)
    assert fake.queried == [2]
    assert free_vram_bytes("cuda") == 1002


def test_cuda_failure_is_unknown_with_zero_bytes(monkeypatch):
    _patch_cuda(monkeypatch, _FakeCuda(fail=True))
    r = free_memory_bytes("cuda:0")
    assert r == MemoryReading("cuda:0", 0, 0, ValueSource.UNKNOWN)
    assert free_vram_bytes("cuda:0") == 0


@pytest.mark.parametrize("bad", ["mps", "cuda:x", "cuda:", "gpu:0"])
def test_unrecognised_device_is_unknown(bad):
    r = free_memory_bytes(bad)
    assert (r.device, r.free_bytes, r.total_bytes, r.source) == (bad, 0, 0, ValueSource.UNKNOWN)


def test_real_cpu_reading_is_measured():
    r = free_memory_bytes("cpu")
    assert r.source is ValueSource.MEASURED
    assert 0 < r.free_bytes <= r.total_bytes


@pytest.mark.gpu
def test_real_cuda0_reading():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")
    r = free_memory_bytes("cuda:0")
    free, total = torch.cuda.mem_get_info(0)
    assert r.source is ValueSource.MEASURED
    assert r.total_bytes == total
    assert 0 < r.free_bytes <= r.total_bytes
    assert abs(r.free_bytes - free) < 256 * 1024**2
