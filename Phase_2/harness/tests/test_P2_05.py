"""P2.05 — device, timing, VRAM, OOM in register_pair (Phase_2/LLD/pipeline_gpu.md). Protected (G05)."""

from __future__ import annotations

import subprocess
import sys

import numpy as np
import pytest
from _h2 import REPO, cuda_available, textured


def test_oom_classified(monkeypatch):
    import torch

    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    class Boom:
        name = "boom"

        def match(self, s, r):
            raise torch.OutOfMemoryError("CUDA out of memory. Tried to allocate 2.00 GiB")

    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name, **kw: Boom())
    img = textured((128, 128))
    out = register_pair(img, img, "oom", PipelineConfig(matcher="boom"))
    assert out.status is RunStatus.OOM and out.extra["stage"] == "match"
    assert "out of memory" in out.detail.lower()


def test_timing_and_device_keys():
    from lunar_reg.pipeline import PipelineConfig, register_pair
    from lunar_reg.eval.scenes import illumination_pair

    src, ref, _, _ = illumination_pair(shape=(256, 256), seed=1, source_sun=(300, 30),
                                       reference_sun=(300, 30))
    out = register_pair(src, ref, "t", PipelineConfig(matcher="sift", device="cpu",
                                                      n_bootstrap=0))
    x = out.result.extra
    assert x["device"] == "cpu" and x["precision"] in ("fp32", "auto")
    assert x["seconds_match"] > 0 and x["seconds_total"] >= x["seconds_match"]
    assert "peak_vram_bytes" not in x or x["peak_vram_bytes"] is None


def test_classical_run_does_not_import_torch():
    code = ("import sys, numpy as np; sys.path.insert(0, 'Phase_2/harness/tests');"
            "from _h2 import textured; from lunar_reg.pipeline import PipelineConfig, register_pair;"
            "a = textured((128, 128)); register_pair(a, a, 'x', PipelineConfig(matcher='sift',"
            " device='cpu', n_bootstrap=0)); print('torch' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True,
                         timeout=120)
    assert out.stdout.strip().endswith("False"), out.stdout + out.stderr


@pytest.mark.gpu
def test_lightglue_records_vram():
    if not cuda_available():
        pytest.skip("CUDA not available")
    from lunar_reg.eval.scenes import illumination_pair
    from lunar_reg.pipeline import PipelineConfig, register_pair

    src, ref, _, _ = illumination_pair(shape=(320, 320), seed=2, source_sun=(300, 30),
                                       reference_sun=(300, 30))
    out = register_pair(src, ref, "g", PipelineConfig(matcher="lightglue", device="cuda",
                                                      n_bootstrap=0))
    assert out.ok, out.detail
    assert out.result.extra["peak_vram_bytes"] > 0
    assert np.isfinite(out.result.extra["seconds_match"])
