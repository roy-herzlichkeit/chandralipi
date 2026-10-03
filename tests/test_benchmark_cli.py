"""`lunar-reg benchmark` (P2.03, Phase_2/LLD/device.md §P2.03).

No real sweep runs here: subprocess results are canned and `measure_in_subprocess`
is monkeypatched for the CLI paths, so every test is CPU-only and fast.
"""

from __future__ import annotations

import json
import re
import subprocess

import numpy as np
import pytest

from lunar_reg.match import benchmark as bm
from lunar_reg.match import memory
from lunar_reg.match.benchmark import BenchmarkRow, fit_profile
from lunar_reg.match.memory import MeasureOutcome, MemoryMeasurement

# --------------------------------------------------------------------------
# outcome parsing (memory.measure_in_subprocess)
# --------------------------------------------------------------------------


def _completed(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess([], code, stdout=stdout, stderr=stderr)


def _measure_with(monkeypatch, completed):
    monkeypatch.setattr(memory.subprocess, "run", lambda *a, **k: completed)
    return memory.measure_in_subprocess("pass", label="t@256px", timeout=5)


OK_STDOUT = (
    "PEAK_BYTES 1000\nMETHOD cuda_allocator\nBASELINE_BYTES 400\nSECONDS 1.5\n"
    "DEVICE cuda\nN_MATCHES 12\n"
)


@pytest.mark.parametrize(
    ("completed", "want"),
    [
        (_completed(OK_STDOUT), MeasureOutcome.OK),
        # exit 0 with PEAK_BYTES is OK even when stderr mentions memory
        (_completed(OK_STDOUT, "warning: CUDA out of memory retried"), MeasureOutcome.OK),
        (
            _completed("", "torch.OutOfMemoryError: CUDA out of memory. Tried", 1),
            MeasureOutcome.OOM,
        ),
        (_completed("", "RuntimeError: CUDA out of memory.", 1), MeasureOutcome.OOM),
        (_completed("", "MemoryError", 1), MeasureOutcome.OOM),
        (
            _completed(
                "", "RuntimeError: [enforce fail] DefaultCPUAllocator: can't allocate memory", 1
            ),
            MeasureOutcome.OOM,
        ),
        (_completed("", "", -9), MeasureOutcome.OOM),
        (
            _completed("", "ModuleNotFoundError: No module named 'kornia'", 1),
            MeasureOutcome.SETUP_ERROR,
        ),
        (_completed("", "", 3), MeasureOutcome.SETUP_ERROR),
        (
            _completed("PEAK_BYTES 5\n", "Traceback ...\nValueError: bad", 1),
            MeasureOutcome.SETUP_ERROR,
        ),
        (_completed("hello\n"), MeasureOutcome.NO_OUTPUT),
        (_completed(""), MeasureOutcome.NO_OUTPUT),
    ],
)
def test_outcome_parsing(monkeypatch, completed, want):
    m = _measure_with(monkeypatch, completed)
    assert m.outcome is want, m
    assert m.ok is (want is MeasureOutcome.OK)
    if want is not MeasureOutcome.OK:
        assert m.error and len(m.error) <= 200


def test_ok_parses_every_reported_field(monkeypatch):
    m = _measure_with(monkeypatch, _completed(OK_STDOUT))
    assert (m.peak_bytes, m.method, m.device, m.baseline_bytes, m.n_matches) == (
        1000,
        "cuda_allocator",
        "cuda",
        400,
        12,
    )
    assert m.seconds == pytest.approx(1.5) and m.is_device_measurement
    assert m.as_dict()["outcome"] == "ok"


def test_unreported_method_and_device_are_unknown_not_host_defaults(monkeypatch):
    m = _measure_with(monkeypatch, _completed("PEAK_BYTES 77\nSECONDS 0.1\n"))
    assert m.outcome is MeasureOutcome.OK
    assert m.method == "unknown" and m.device == "unknown"
    assert not m.is_device_measurement

    failed = _measure_with(monkeypatch, _completed("", "ImportError: x", 1))
    assert failed.method == "unknown" and failed.device == "unknown"


def test_timeout_is_classified(monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired("python", 5)

    monkeypatch.setattr(memory.subprocess, "run", boom)
    m = memory.measure_in_subprocess("pass", label="t", timeout=5)
    assert m.outcome is MeasureOutcome.TIMEOUT and not m.ok
    assert m.method == "unknown" and "5s" in m.error


def test_last_stderr_line_is_the_error(monkeypatch):
    m = _measure_with(
        monkeypatch, _completed("", "Traceback\n  File x\nImportError: no kornia\n", 1)
    )
    assert m.error == "ImportError: no kornia"


def test_diagnostics_report_counts_and_samples():
    diag = memory.MeasureDiagnostics()
    diag.record(MeasureOutcome.OK, "a@256px: fine")
    diag.record(MeasureOutcome.OK, "a@384px: fine")
    diag.record(MeasureOutcome.OOM, "a@512px: CUDA out of memory")
    text = diag.report()
    assert diag.counts == {"ok": 2, "oom": 1} and diag.n_failures == 1
    assert text.splitlines()[0] == "memory measurements: 3 run, 2 ok, 1 failed"
    assert "  oom: 1  e.g. a@512px: CUDA out of memory" in text


def test_capability_text_makes_no_driver_claims_on_cpu():
    text = memory.describe_measurement_capability("cpu")
    assert "nvidia kernel module" not in text and "CPU-only build" not in text
    assert "NOT VRAM" in text


# --------------------------------------------------------------------------
# sweep (benchmark_matcher) and snippet rules
# --------------------------------------------------------------------------


def _fake_measure(
    peaks: dict[int, int],
    fail: dict[int, MeasureOutcome] | None = None,
    method="host_rss",
    device="cpu",
    calls: list | None = None,
):
    fail = fail or {}

    def measure(code, label="", timeout=900):
        size = int(re.search(r"@(\d+)px", label).group(1))
        if calls is not None:
            calls.append((size, code))
        if size in fail:
            return MemoryMeasurement(
                0,
                "unknown",
                "unknown",
                0.0,
                label,
                ok=False,
                error=f"{fail[size].value} at {size}",
                outcome=fail[size],
            )
        return MemoryMeasurement(
            peaks[size], method, device, 0.5, label, baseline_bytes=100, n_matches=3
        )

    return measure


def _peaks(fixed=400_000_000, k=1500.0, sizes=(256, 384, 512, 640, 768, 896, 1024)):
    return {s: int(fixed + k * s * s) for s in sizes}


def test_sweep_stops_at_first_oom_only(monkeypatch):
    calls = []
    fail = {
        384: MeasureOutcome.SETUP_ERROR,
        512: MeasureOutcome.TIMEOUT,
        640: MeasureOutcome.NO_OUTPUT,
        896: MeasureOutcome.OOM,
    }
    monkeypatch.setattr(bm, "measure_in_subprocess", _fake_measure(_peaks(), fail, calls=calls))
    rows = bm.benchmark_matcher("loftr", device="cpu", precision="fp32")
    assert [r.tile_px for r in rows] == [256, 384, 512, 640, 768, 896]  # 1024 never run
    assert [r.outcome.value for r in rows] == [
        "ok",
        "setup_error",
        "timeout",
        "no_output",
        "ok",
        "oom",
    ]
    assert bm.oom_stop_px(rows) == 896
    assert bm.diagnose(rows).counts == {
        "ok": 2,
        "setup_error": 1,
        "timeout": 1,
        "no_output": 1,
        "oom": 1,
    }


def test_rlimit_only_on_cpu():
    cpu = bm.build_snippet("loftr", "fp32", 256, "cpu", budget_bytes=4 * 2**30)
    cuda = bm.build_snippet("loftr", "fp32", 256, "cuda", budget_bytes=4 * 2**30)
    assert f"_budget = {4 * 2**30}" in cpu
    assert "_budget = 0" in cuda
    assert "device = 'cuda'" in cuda and "reset_peak_memory_stats" in cuda
    assert "max_memory_allocated" in cuda


def test_snippets_cover_both_precisions_and_compile():
    for matcher in bm.MATCHERS:
        for precision in bm.PRECISIONS:
            code = bm.build_snippet(matcher, precision, 256, "cpu")
            compile(code, f"{matcher}-{precision}", "exec")
            assert ("autocast" in code) is (precision == "fp16")
    with pytest.raises(ValueError):
        bm.build_snippet("sift", "fp16", 256, "cpu")


# --------------------------------------------------------------------------
# fit_profile
# --------------------------------------------------------------------------


def _rows(
    peaks: dict[int, int], outcomes: dict[int, MeasureOutcome] | None = None, matcher="loftr"
):
    outcomes = outcomes or {}
    rows = []
    for px, peak in peaks.items():
        outcome = outcomes.get(px, MeasureOutcome.OK)
        mm = MemoryMeasurement(
            peak,
            "cuda_allocator",
            "cuda",
            1.0,
            f"{matcher}@{px}",
            ok=outcome is MeasureOutcome.OK,
            outcome=outcome,
        )
        rows.append(BenchmarkRow(matcher, px, mm))
    return rows


def test_fit_recovers_known_fixed_and_slope():
    entry = fit_profile(_rows(_peaks(fixed=512_000_000, k=2200.0, sizes=(256, 512, 768, 1024))))
    assert entry["fixed_bytes"] == pytest.approx(512e6, rel=1e-6)
    assert entry["bytes_per_px"] == pytest.approx(2200.0, rel=1e-6)
    assert entry["max_tile_px"] == 1024
    assert entry["points"] == [[s, int(512e6 + 2200.0 * s * s)] for s in (256, 512, 768, 1024)]
    assert isinstance(entry["fixed_bytes"], int) and isinstance(entry["bytes_per_px"], float)


def test_fit_is_least_squares_with_noise():
    rng = np.random.default_rng(1)
    sizes = (256, 384, 512, 640, 768, 896, 1024)
    peaks = {s: int(300e6 + 1800.0 * s * s + rng.normal(0, 2e6)) for s in sizes}
    entry = fit_profile(_rows(peaks))
    side = np.array(sizes, float)
    want = np.linalg.lstsq(
        np.c_[np.ones_like(side), side**2], np.array([peaks[s] for s in sizes], float), rcond=None
    )[0]
    assert entry["fixed_bytes"] == pytest.approx(want[0], abs=1)
    assert entry["bytes_per_px"] == pytest.approx(want[1], rel=1e-9)


def test_fit_uses_ok_rows_only():
    peaks = _peaks(sizes=(256, 384, 512, 640, 768))
    peaks[640] = 0
    peaks[768] = 0
    rows = _rows(peaks, {640: MeasureOutcome.SETUP_ERROR, 768: MeasureOutcome.OOM})
    entry = fit_profile(rows)
    assert [p[0] for p in entry["points"]] == [256, 384, 512]
    assert entry["max_tile_px"] == 512
    assert entry["bytes_per_px"] == pytest.approx(1500.0, rel=1e-6)


def test_fit_refuses_too_few_or_degenerate_rows():
    with pytest.raises(ValueError, match="need >= 3"):
        fit_profile(_rows(_peaks(sizes=(256, 512))))
    with pytest.raises(ValueError, match="need >= 3"):
        fit_profile(_rows(_peaks(sizes=(256, 512, 768)), {768: MeasureOutcome.TIMEOUT}))
    with pytest.raises(ValueError, match="bytes_per_px"):
        fit_profile(_rows({256: 900, 512: 800, 768: 700}))
    with pytest.raises(ValueError, match="mix matchers"):
        fit_profile(_rows(_peaks(sizes=(256, 512))) + _rows({768: 5}, matcher="lightglue"))


# --------------------------------------------------------------------------
# CLI (dry: measure_in_subprocess monkeypatched, nothing touches a device)
# --------------------------------------------------------------------------


def _run_cli(argv):
    from lunar_reg.cli import main

    return main(argv)


def test_cli_cpu_dry_path_writes_json_and_run_record(tmp_path, monkeypatch, capsys):
    from lunar_reg.runrecord import read_run_record, validate_run_record

    monkeypatch.setattr(
        bm, "measure_in_subprocess", _fake_measure(_peaks(), {896: MeasureOutcome.OOM})
    )
    out = tmp_path / "bench"
    code = _run_cli(
        [
            "benchmark",
            "--matcher",
            "loftr",
            "--precision",
            "fp32",
            "--device",
            "cpu",
            "--out",
            str(out),
        ]
    )
    assert code == 0  # OK rows then an OOM: the sweep did its job

    doc = json.loads((out / "benchmark_loftr_fp32.json").read_text())
    assert doc["outcome_counts"] == {"ok": 5, "oom": 1}
    assert doc["stopped_at_oom_px"] == 896
    assert [r["tile_px"] for r in doc["rows"]] == [256, 384, 512, 640, 768, 896]
    assert (
        doc["rows"][0]["peak_source"] == "measured" and doc["rows"][-1]["peak_source"] == "unknown"
    )
    assert doc["fit"]["bytes_per_px"] == pytest.approx(1500.0, rel=1e-6)
    assert doc["fit_note"] == "host RSS fit (NOT VRAM)"

    rr = out / "run_loftr_fp32" / "run_record.json"
    assert rr.exists() and validate_run_record(rr) == []
    record = read_run_record(rr)
    assert record.outcome_counts == {"ok": 5, "oom": 1}
    assert record.params["device"] == "cpu" and "stopped at OOM at 896px" in record.notes

    printed = capsys.readouterr().out
    assert "memory measurements: 6 run, 5 ok, 1 failed" in printed
    assert "  oom: 1  e.g." in printed and "sweep stopped at the first OOM, 896px" in printed


def test_cli_non_oom_failure_exits_1_and_sweep_continues(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        bm, "measure_in_subprocess", _fake_measure(_peaks(), {384: MeasureOutcome.SETUP_ERROR})
    )
    code = _run_cli(
        [
            "benchmark",
            "--matcher",
            "lightglue",
            "--precision",
            "fp16",
            "--tile-sizes",
            "256,384,512",
            "--device",
            "cpu",
            "--out",
            str(tmp_path),
        ]
    )
    assert code == 1
    doc = json.loads((tmp_path / "benchmark_lightglue_fp16.json").read_text())
    assert doc["outcome_counts"] == {"ok": 2, "setup_error": 1}
    assert doc["fit"] is None and "need >= 3" in doc["fit_error"]
    assert "setup_error: 1" in capsys.readouterr().out


def test_cli_profile_out_refuses_cpu(tmp_path, monkeypatch):
    def never(*a, **k):
        raise AssertionError("no measurement may run")

    monkeypatch.setattr(bm, "measure_in_subprocess", never)
    code = _run_cli(
        [
            "benchmark",
            "--device",
            "cpu",
            "--out",
            str(tmp_path),
            "--profile-out",
            str(tmp_path / "p.json"),
        ]
    )
    assert code == 2 and not (tmp_path / "p.json").exists()


FACTS = {
    "device_name": "Fake GPU 8GB",
    "total_bytes": 8 * 2**30,
    "torch": "2.x",
    "cuda": "13.0",
    "driver": "580.00",
}


def _patch_cuda(monkeypatch, peaks, facts=FACTS):
    monkeypatch.setattr(
        bm, "measure_in_subprocess", _fake_measure(peaks, method="cuda_allocator", device="cuda")
    )
    monkeypatch.setattr(bm, "free_bytes_before_sweep", lambda device: 7 * 2**30)
    monkeypatch.setattr(bm, "cuda_device_facts", lambda device: dict(facts))
    monkeypatch.setattr(
        memory, "describe_measurement_capability", lambda device=None: f"device: {device} (patched)"
    )


def test_cli_profile_out_creates_and_merges_c16(tmp_path, monkeypatch, capsys):
    from lunar_reg.device import DeviceProfile
    from lunar_reg.provenance import ValueSource

    profile_path = tmp_path / "profiles" / "fake-gpu.json"
    out = tmp_path / "bench"
    _patch_cuda(monkeypatch, _peaks(fixed=600_000_000, k=1700.0))
    assert (
        _run_cli(
            [
                "benchmark",
                "--matcher",
                "loftr",
                "--precision",
                "fp16",
                "--device",
                "cuda",
                "--out",
                str(out),
                "--profile-out",
                str(profile_path),
            ]
        )
        == 0
    )
    _patch_cuda(monkeypatch, _peaks(fixed=900_000_000, k=3100.0, sizes=(512, 768, 1024)))
    assert (
        _run_cli(
            [
                "benchmark",
                "--matcher",
                "lightglue",
                "--precision",
                "fp32",
                "--tile-sizes",
                "512,768,1024",
                "--device",
                "cuda",
                "--out",
                str(out),
                "--profile-out",
                str(profile_path),
            ]
        )
        == 0
    )

    prof = DeviceProfile.load(profile_path)
    assert prof.source is ValueSource.MEASURED and prof.slug == "fake-gpu"
    assert prof.device_name == "Fake GPU 8GB" and prof.total_bytes == 8 * 2**30
    loftr = prof.entry("loftr", "fp16")
    assert loftr["fixed_bytes"] == pytest.approx(600e6, rel=1e-6)
    assert loftr["bytes_per_px"] == pytest.approx(1700.0, rel=1e-6)
    assert len(loftr["points"]) == 7 and loftr["max_tile_px"] == 1024
    lg = prof.entry("lightglue", "fp32")
    assert lg["bytes_per_px"] == pytest.approx(3100.0, rel=1e-6) and len(lg["points"]) == 3
    doc = json.loads(profile_path.read_text())
    assert doc["driver"] == "580.00" and doc["free_bytes_at_measure"] == 7 * 2**30
    assert doc["run_record"].endswith("run_lightglue_fp32/run_record.json")
    assert (out / "run_loftr_fp16" / "run_record.json").exists()
    assert "profile " in capsys.readouterr().out


def test_cli_profile_for_another_device_is_not_overwritten(tmp_path, monkeypatch, capsys):
    profile_path = tmp_path / "fake-gpu.json"
    _patch_cuda(monkeypatch, _peaks())
    assert (
        _run_cli(
            [
                "benchmark",
                "--device",
                "cuda",
                "--out",
                str(tmp_path),
                "--profile-out",
                str(profile_path),
            ]
        )
        == 0
    )
    before = profile_path.read_text()

    _patch_cuda(monkeypatch, _peaks(), facts={**FACTS, "device_name": "Other GPU"})
    code = _run_cli(
        [
            "benchmark",
            "--precision",
            "fp32",
            "--device",
            "cuda",
            "--out",
            str(tmp_path),
            "--profile-out",
            str(profile_path),
        ]
    )
    assert code == 1 and profile_path.read_text() == before
    assert "profile NOT updated" in capsys.readouterr().out


def test_cli_parser_defaults():
    from lunar_reg.cli import build_parser

    args = build_parser().parse_args(["benchmark", "--out", "/tmp/x"])
    assert args.tile_sizes == (256, 384, 512, 640, 768, 896, 1024)
    assert (args.matcher, args.precision, args.device, args.timeout) == (
        "loftr",
        "fp16",
        "cuda",
        900,
    )
    assert args.profile_out is None
    with pytest.raises(SystemExit):
        build_parser().parse_args(["benchmark", "--out", "x", "--tile-sizes", "256,-1"])


# --------------------------------------------------------------------------
# --device cuda when torch sees no CUDA device; nvidia-smi free-memory parse
# --------------------------------------------------------------------------


def _no_cuda(monkeypatch):
    torch = pytest.importorskip("torch")

    def _raise():
        raise RuntimeError("No CUDA GPUs are available")

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.cuda, "current_device", _raise)


def test_free_bytes_before_sweep_is_none_without_cuda(monkeypatch):
    _no_cuda(monkeypatch)
    monkeypatch.setattr(bm, "_nvidia_smi", lambda *a: pytest.fail("nvidia-smi must not run"))
    assert bm.free_bytes_before_sweep("cuda") is None
    assert bm.free_bytes_before_sweep("cpu") is None
    assert bm.free_bytes_before_sweep("cuda:x") is None


def test_cli_cuda_unavailable_classifies_setup_error_and_writes_record(
    tmp_path, monkeypatch, capsys
):
    from lunar_reg.runrecord import validate_run_record

    _no_cuda(monkeypatch)
    sizes = (256, 384, 512)
    monkeypatch.setattr(
        bm,
        "measure_in_subprocess",
        _fake_measure(_peaks(sizes=sizes), dict.fromkeys(sizes, MeasureOutcome.SETUP_ERROR)),
    )
    out = tmp_path / "bench"
    code = _run_cli(
        ["benchmark", "--device", "cuda", "--tile-sizes", "256,384,512", "--out", str(out)]
    )
    assert code == 1
    (bench,) = out.glob("benchmark_*.json")
    doc = json.loads(bench.read_text())
    assert doc["outcome_counts"] == {"setup_error": 3}
    assert doc["free_bytes_before"] is None and doc["free_bytes_before_source"] == "unknown"
    (rr,) = out.glob("run_*/run_record.json")
    assert validate_run_record(rr) == []
    printed = capsys.readouterr().out
    assert "setup_error: 3" in printed
    assert "CUDA WAS REQUESTED BUT torch.cuda.is_available() IS False" in printed


@pytest.mark.parametrize(
    ("result", "want"),
    [
        (_completed("7012\n"), 7012 * 1024**2),
        (_completed("7012.5\n"), int(7012.5 * 1024**2)),
        (_completed("[N/A]\n"), None),
        (_completed("", "NVIDIA-SMI has failed", 9), None),
        (_completed(""), None),
        (OSError("nvidia-smi not found"), None),
        (subprocess.TimeoutExpired("nvidia-smi", 30), None),
    ],
)
def test_free_bytes_before_sweep_parses_nvidia_smi(monkeypatch, result, want):
    seen = []

    def run(cmd, **kwargs):
        seen.append(cmd)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(bm.subprocess, "run", run)
    assert bm.free_bytes_before_sweep("cuda:1") == want
    assert seen[0][:3] == ["nvidia-smi", "-i", "1"]
    assert "--query-gpu=memory.free" in seen[0]
