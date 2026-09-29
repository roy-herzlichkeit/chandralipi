"""P0.02 — learned matchers merge (Phase_0/LLD/matchers_learned.md). Protected (G05)."""

from __future__ import annotations

import importlib.util

import numpy as np
import pytest
from _h0 import REPO, cuda_available, have_weights, shifted_pair

LOFTR_W = "loftr_outdoor.ckpt"
DISK_W = ("depth-save.pth", "disk_lightglue_v0-1_arxiv-pth")


def test_loftr_module_deleted():
    assert not (REPO / "src/lunar_reg/match/loftr.py").exists()
    assert importlib.util.find_spec("lunar_reg.match.loftr") is None


def test_superglue_has_no_duplicate_lightglue():
    import lunar_reg.match.superglue as sg
    from lunar_reg.match.learned import LightGlueMatcher

    dup = vars(sg).get("LightGlueMatcher")
    assert dup is None or dup is LightGlueMatcher
    assert hasattr(sg, "SuperGlueMatcher") and hasattr(sg, "licence_report")


def test_superglue_licence_gate(monkeypatch):
    from lunar_reg.match.superglue import SuperGlueMatcher

    monkeypatch.delenv("SUPERGLUE_ACCEPT_NONCOMMERCIAL", raising=False)
    with pytest.raises(PermissionError):
        SuperGlueMatcher()


def test_to_tensor_normalisation():
    import torch

    from lunar_reg.match.learned import _to_tensor
    from lunar_reg.preprocess.radiometric import to_uint8

    arr = np.random.default_rng(0).uniform(0, 1000, (40, 50)).astype(np.float32)
    got = _to_tensor(arr, "cpu")
    want = torch.from_numpy(to_uint8(arr).astype(np.float32) / 255.0)[None, None]
    assert got.shape == (1, 1, 40, 50)
    assert torch.allclose(got, want, atol=1e-6)
    u8 = (arr / 4).astype(np.uint8)
    assert torch.allclose(_to_tensor(u8, "cpu"), torch.from_numpy(u8 / 255.0).float()[None, None])


def _check_shift(result, src, ref, shift, max_median):
    assert len(result) >= 20, f"only {len(result)} matches"
    h0, w0 = src.shape
    h1, w1 = ref.shape
    assert (result.src_pts[:, 0] < w0).all() and (result.src_pts[:, 1] < h0).all()
    assert (result.dst_pts[:, 0] < w1).all() and (result.dst_pts[:, 1] < h1).all()
    err = np.linalg.norm(result.dst_pts - result.src_pts - shift, axis=1)
    assert np.median(err) < max_median, f"median error {np.median(err):.3f} px"


@pytest.mark.weights
def test_loftr_odd_size_cpu():
    if not have_weights(LOFTR_W):
        pytest.skip("LoFTR outdoor weights not cached")
    from lunar_reg.match.learned import LoFTRMatcher

    src, ref, shift = shifted_pair()
    result = LoFTRMatcher(device="cpu").match(src, ref)
    _check_shift(result, src, ref, shift, 1.0)
    for key in ("device", "precision", "weights", "confidence_threshold", "pad_multiple"):
        assert key in result.meta
    assert result.meta["pad_multiple"] == 8


@pytest.mark.weights
def test_lightglue_odd_size_cpu():
    if not have_weights(*DISK_W):
        pytest.skip("DISK/LightGlue weights not cached")
    from lunar_reg.match.learned import LightGlueMatcher

    src, ref, shift = shifted_pair()
    result = LightGlueMatcher(device="cpu", max_keypoints=512).match(src, ref)
    _check_shift(result, src, ref, shift, 1.0)
    assert result.meta["device"] == "cpu" and result.meta["precision"] == "fp32"


@pytest.mark.gpu
@pytest.mark.weights
def test_lightglue_cuda_does_not_crash():
    if not cuda_available():
        pytest.skip("CUDA not available")
    if not have_weights(*DISK_W):
        pytest.skip("DISK/LightGlue weights not cached")
    from lunar_reg.match.learned import LightGlueMatcher

    src, ref, shift = shifted_pair()
    result = LightGlueMatcher(device="cuda", max_keypoints=512).match(src, ref)
    _check_shift(result, src, ref, shift, 1.5)
    assert result.meta["device"] == "cuda"


@pytest.mark.gpu
@pytest.mark.weights
def test_loftr_cuda_fp16():
    if not cuda_available():
        pytest.skip("CUDA not available")
    if not have_weights(LOFTR_W):
        pytest.skip("LoFTR outdoor weights not cached")
    from lunar_reg.match.learned import LoFTRMatcher

    src, ref, shift = shifted_pair()
    result = LoFTRMatcher(device="cuda", precision="fp16").match(src, ref)
    _check_shift(result, src, ref, shift, 1.5)


def test_classical_meta():
    from lunar_reg.match.classical import ClassicalMatcher

    src, ref, _ = shifted_pair()
    for result in (ClassicalMatcher("sift").match(src, ref),
                   ClassicalMatcher("sift").match(np.zeros((64, 64), np.uint8),
                                                  np.zeros((64, 64), np.uint8))):
        for key in ("detector", "ratio", "max_features", "cross_check"):
            assert key in result.meta, f"classical meta lacks {key}"


def test_deduplicate():
    from lunar_reg.match.base import MatchResult
    from lunar_reg.match.stitch import deduplicate

    src = np.array([[10.0, 10.0], [10.5, 10.2], [50.0, 50.0]])
    dst = np.array([[20.0, 20.0], [20.4, 20.1], [60.0, 60.0]])
    out, removed = deduplicate(MatchResult(src, dst), tolerance_px=1.5)
    assert removed == 1 and len(out) == 2
    far = np.array([[20.0, 20.0], [90.0, 90.0], [60.0, 60.0]])
    out, removed = deduplicate(MatchResult(src, far), tolerance_px=1.5)
    assert removed == 0 and len(out) == 3


def test_docstrings_corrected():
    classical = (REPO / "src/lunar_reg/match/classical.py").read_text()
    stitch = (REPO / "src/lunar_reg/match/stitch.py").read_text()
    assert "not buildable here" not in classical
    assert "Score breaks ties" not in stitch
