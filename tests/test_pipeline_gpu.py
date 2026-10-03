"""register_pair records device, precision, timing and peak VRAM; OOM is classified (P2.05)."""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from lunar_reg.match.base import MatchResult
from lunar_reg.pipeline import PRECISIONS, PipelineConfig, RunStatus, register_pair

REPO = Path(__file__).resolve().parents[1]


def _texture(seed: int = 3, shape=(256, 256)) -> np.ndarray:
    noise = np.random.default_rng(seed).normal(0, 1, shape).astype(np.float32)
    blurred = cv2.GaussianBlur(noise, (0, 0), 2.0)
    scaled = (blurred - blurred.min()) / (blurred.max() - blurred.min())
    return (1 + scaled * 254).astype(np.uint8)


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001 - any torch/driver problem means "no CUDA here"
        return False


def _shifted_matches(n: int = 60, shift=(4.0, -3.0), seed: int = 5) -> MatchResult:
    src = np.random.default_rng(seed).uniform(10, 240, (n, 2))
    return MatchResult(src, src + np.array(shift), matcher="stub", meta={"detector": "stub"})


class _Stub:
    name = "stub"

    def __init__(self, result: MatchResult | None = None, exc: BaseException | None = None):
        self._result, self._exc = result, exc

    def match(self, source, reference) -> MatchResult:
        if self._exc is not None:
            raise self._exc
        return self._result


# --------------------------------------------------------------- fields, defaults


def test_config_fields_and_defaults():
    fields = {f.name: f.default for f in dataclasses.fields(PipelineConfig)}
    assert fields["device"] is None and fields["precision"] == "auto"
    names = [f.name for f in dataclasses.fields(PipelineConfig)]
    assert names[-2:] == ["device", "precision"]  # appended after the P1.10 field
    assert PRECISIONS == ("auto", "fp16", "fp32")


def test_unknown_precision_rejected():
    with pytest.raises(ValueError, match="precision"):
        PipelineConfig(precision="bf16")


# --------------------------------------------------------------- device / precision routing


@pytest.mark.parametrize(
    ("matcher", "device", "precision", "want_device", "want_precision"),
    [
        ("loftr", "cpu", "auto", "cpu", "fp32"),
        ("loftr", "cuda", "auto", "cuda", "fp16"),
        ("loftr", "cuda", "fp32", "cuda", "fp32"),
        ("loftr", "cpu", "fp16", "cpu", "fp32"),
        ("lightglue", "cpu", "fp16", "cpu", "fp32"),
        # Indexed CUDA device strings (C17; Phase 4 workers run with cuda:<i>).
        ("loftr", "cuda:0", "auto", "cuda:0", "fp16"),
        ("loftr", "cuda:1", "fp32", "cuda:1", "fp32"),
        ("lightglue", "cuda:0", "auto", "cuda:0", "fp16-disk+fp32-lightglue"),
    ],
)
def test_device_and_precision_reach_the_matcher(
    monkeypatch, matcher, device, precision, want_device, want_precision
):
    seen = {}

    def build(name, **kw):
        seen.update(kw, name=name)
        return _Stub(exc=ValueError("stop after build"))

    # The stub raises inside match(); on "cuda" only the peak reset would touch
    # the GPU, so it is stubbed out too.
    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", build)
    cfg = PipelineConfig(matcher=matcher, device=device, precision=precision, preprocess="none")
    if want_device.startswith("cuda"):
        torch = pytest.importorskip("torch")
        monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda *a, **k: None)
    img = _texture()
    out = register_pair(img, img, "route", cfg)
    assert seen["name"] == matcher
    assert seen["device"] == want_device and seen["precision"] == want_precision
    assert out.status is RunStatus.MATCHER_ERROR
    assert out.extra["device"] == want_device and out.extra["precision"] == want_precision


@pytest.mark.parametrize("device", ["cuda", "cuda:0", "cuda:1"])
def test_loftr_keeps_fp16_on_every_cuda_device_string(device):
    # Constructing the matcher touches no GPU: the model and tile plan are lazy.
    from lunar_reg.match.learned import LoFTRMatcher, _is_cuda

    assert _is_cuda(device)
    assert LoFTRMatcher(device=device, precision="fp16").precision == "fp16"
    assert LoFTRMatcher(device=device, precision="fp32").precision == "fp32"


@pytest.mark.parametrize("device", ["cpu", "mps", "cudax"])
def test_loftr_downgrades_to_fp32_off_cuda(device):
    from lunar_reg.match.learned import LoFTRMatcher, _is_cuda

    assert not _is_cuda(device)
    assert LoFTRMatcher(device=device, precision="fp16").precision == "fp32"


def test_lightglue_precision_is_recorded_not_passed():
    from lunar_reg.pipeline import _build_matcher

    m = _build_matcher("lightglue", device="cpu", precision="fp16")  # no precision kwarg reaches it
    assert m.device == "cpu"


def test_classical_matcher_records_cpu_even_when_cuda_is_asked(monkeypatch):
    seen = {}

    def build(name, **kw):
        seen.update(kw)
        return _Stub(_shifted_matches())

    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", build)
    img = _texture()
    cfg = PipelineConfig(
        matcher="sift", device="cuda", use_ecc=False, n_bootstrap=0, preprocess="none"
    )
    out = register_pair(img, img, "c", cfg)
    assert out.ok, out.detail
    assert seen["device"] == "cpu"
    assert out.result.extra["device"] == "cpu" and out.result.extra["precision"] == "fp32"
    assert "peak_vram_bytes" not in out.result.extra


# --------------------------------------------------------------- OOM


def test_oom_is_classified_before_matcher_error(monkeypatch):
    torch = pytest.importorskip("torch")
    calls = []
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: calls.append(1))
    exc = torch.OutOfMemoryError("CUDA out of memory. Tried to allocate 2.00 GiB\nsecond line")
    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name, **kw: _Stub(exc=exc))
    img = _texture()
    out = register_pair(img, img, "oom", PipelineConfig(matcher="boom", device="cpu"))
    assert out.status is RunStatus.OOM and out.status.is_failure
    assert out.extra["stage"] == "match"
    assert out.detail == "CUDA out of memory. Tried to allocate 2.00 GiB"
    assert calls == [1]  # the cache is emptied once, after the OOM
    for key in ("device", "precision", "seconds_total", "matcher", "source_id"):
        assert key in out.extra


def test_plain_runtime_error_stays_matcher_error(monkeypatch):
    exc = RuntimeError("CUDA out of memory (simulated, not torch.OutOfMemoryError)")
    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name, **kw: _Stub(exc=exc))
    img = _texture()
    out = register_pair(img, img, "rt", PipelineConfig(matcher="boom", device="cpu"))
    assert out.status is RunStatus.MATCHER_ERROR


# --------------------------------------------------------------- timing


def test_timing_keys_on_ok_and_failure(monkeypatch):
    img = _texture()
    cfg = PipelineConfig(matcher="sift", device="cpu", n_bootstrap=0)
    out = register_pair(img, np.roll(img, (3, -2), axis=(0, 1)), "t", cfg)
    assert out.ok, out.detail
    x = out.result.extra
    assert x["device"] == "cpu" and x["precision"] == "fp32"
    assert x["seconds_match"] > 0 and x["seconds_total"] >= x["seconds_match"]
    assert x["timing_source"] == "measured"
    assert "peak_vram_bytes" not in x
    assert out.extra["seconds_total"] >= out.extra["seconds_match"] > 0

    empty = MatchResult(np.empty((0, 2)), np.empty((0, 2)), matcher="stub")
    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name, **kw: _Stub(empty))
    fail = register_pair(img, img, "f", PipelineConfig(matcher="stub", device="cpu"))
    assert fail.status is RunStatus.TOO_FEW_MATCHES
    assert fail.extra["seconds_total"] >= fail.extra["seconds_match"] > 0


# --------------------------------------------------------------- learned.py finally


def _count_empty_cache(monkeypatch):
    torch = pytest.importorskip("torch")
    calls = []
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: calls.append(1))
    return torch, calls


def test_loftr_empties_cache_only_when_the_forward_pass_raises(monkeypatch):
    pytest.importorskip("kornia")
    torch, calls = _count_empty_cache(monkeypatch)
    from lunar_reg.match.learned import LoFTRMatcher

    m = LoFTRMatcher(device="cpu")
    pts = torch.tensor([[10.0, 10.0], [20.0, 30.0]])
    m._model = lambda batch: {"keypoints0": pts, "keypoints1": pts + 1, "confidence": torch.ones(2)}
    res = m.match(_texture(shape=(64, 64)), _texture(shape=(64, 64)))
    assert len(res) == 2 and calls == []  # success path keeps the allocator warm (A077)

    def boom(batch):
        raise torch.OutOfMemoryError("CUDA out of memory (stub)")

    m._model = boom
    with pytest.raises(torch.OutOfMemoryError):
        m.match(_texture(shape=(64, 64)), _texture(shape=(64, 64)))
    assert calls == [1]


def test_lightglue_empties_cache_only_when_the_forward_pass_raises(monkeypatch):
    pytest.importorskip("kornia")
    torch, calls = _count_empty_cache(monkeypatch)
    from lunar_reg.match.learned import LightGlueMatcher

    def extractor(*a, **k):
        raise torch.OutOfMemoryError("CUDA out of memory (stub)")

    m = LightGlueMatcher(device="cpu", max_keypoints=64)
    m._extractor, m._matcher = extractor, object()
    with pytest.raises(torch.OutOfMemoryError):
        m.match(_texture(shape=(64, 64)), _texture(shape=(64, 64)))
    assert calls == [1]


# --------------------------------------------------------------- lazy torch import


def test_classical_run_does_not_import_torch():
    code = (
        "import sys, numpy as np\n"
        "from lunar_reg.pipeline import PipelineConfig, register_pair\n"
        "rng = np.random.default_rng(0)\n"
        "a = (rng.random((128, 128)) * 255).astype(np.uint8)\n"
        "register_pair(a, a, 'x', PipelineConfig(matcher='sift', n_bootstrap=0))\n"
        "print('torch' in sys.modules)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, timeout=120
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == "False", out.stdout + out.stderr


# --------------------------------------------------------------- GPU


@pytest.mark.gpu
def test_lightglue_records_peak_vram():
    if not _cuda_available():
        pytest.skip("CUDA not available")
    import torch

    from lunar_reg.eval.scenes import illumination_pair

    src, ref, _, _ = illumination_pair(
        shape=(320, 320), seed=2, source_sun=(300, 30), reference_sun=(300, 30)
    )
    try:
        out = register_pair(
            src, ref, "g", PipelineConfig(matcher="lightglue", device="cuda", n_bootstrap=0)
        )
        assert out.ok, out.detail
        x = out.result.extra
        assert x["device"] == "cuda" and x["precision"] == "fp16-disk+fp32-lightglue"
        assert isinstance(x["peak_vram_bytes"], int) and x["peak_vram_bytes"] > 0
        assert x["peak_vram_source"] == "measured"
        assert x["seconds_total"] >= x["seconds_match"] > 0
    finally:
        torch.cuda.empty_cache()
