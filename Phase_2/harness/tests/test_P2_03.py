"""P2.03 — benchmark CLI (Phase_2/LLD/device.md §P2.03). Protected (G05)."""

from __future__ import annotations

import subprocess

import numpy as np
import pytest


def test_measure_outcomes(monkeypatch):
    from lunar_reg.match import memory

    assert {m.value for m in memory.MeasureOutcome} == {"ok", "oom", "timeout", "setup_error",
                                                         "no_output"}

    def fake(stdout="", stderr="", code=0):
        return subprocess.CompletedProcess([], code, stdout=stdout, stderr=stderr)

    cases = [
        (fake("PEAK_BYTES 100\nSECONDS 1.0\n"), "ok"),
        (fake("", "torch.OutOfMemoryError: CUDA out of memory", 1), "oom"),
        (fake("", "ImportError: x", 1), "setup_error"),
        (fake("hello\n"), "no_output"),
    ]
    for completed, want in cases:
        monkeypatch.setattr(memory.subprocess, "run", lambda *a, _c=completed, **k: _c)
        m = memory.measure_in_subprocess("pass", label="t", timeout=5)
        assert m.outcome.value == want, (want, m)

    def timeout(*a, **k):
        raise subprocess.TimeoutExpired("x", 5)

    monkeypatch.setattr(memory.subprocess, "run", timeout)
    assert memory.measure_in_subprocess("pass", timeout=5).outcome.value == "timeout"


def test_fit_profile():
    from lunar_reg.match.benchmark import BenchmarkRow, fit_profile
    from lunar_reg.match.memory import MeasureOutcome, MemoryMeasurement

    rows = []
    for px in (256, 512, 768, 1024):
        peak = int(400e6 + 1500.0 * px * px)
        mm = MemoryMeasurement(peak, "cuda_allocator", "cuda", 1.0, f"loftr@{px}")
        mm.outcome = MeasureOutcome.OK
        rows.append(BenchmarkRow("loftr", px, mm))
    entry = fit_profile(rows)
    assert entry["fixed_bytes"] == pytest.approx(400e6, rel=1e-3)
    assert entry["bytes_per_px"] == pytest.approx(1500.0, rel=1e-3)
    assert len(entry["points"]) == 4 and entry["max_tile_px"] % 64 == 0
    with pytest.raises(ValueError):
        fit_profile(rows[:2])


def test_cli_has_benchmark():
    from lunar_reg.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["benchmark", "--matcher", "loftr", "--precision", "fp16",
                              "--device", "cpu", "--out", "/tmp/x"])
    assert args.matcher == "loftr" and np.isscalar(args.precision)
