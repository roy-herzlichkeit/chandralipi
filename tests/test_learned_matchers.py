"""Learned matchers: odd-size padding, CUDA LightGlue, input normalisation, licence gate, dedup."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lunar_reg.match.base import MatchResult

WEIGHTS_DIR = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"
LOFTR_WEIGHTS = ("loftr_outdoor.ckpt",)
DISK_LIGHTGLUE_WEIGHTS = ("depth-save.pth", "disk_lightglue_v0-1_arxiv-pth")

#: Integer offset between the two crops: source (x, y) is reference (x + DX, y + DY).
DX, DY = 6, 4


def _have(names: tuple[str, ...]) -> bool:
    return all((WEIGHTS_DIR / n).exists() for n in names)


def _cuda() -> bool:
    import torch

    return bool(torch.cuda.is_available())


def _shifted_pair() -> tuple[np.ndarray, np.ndarray]:
    """Two 250 x 330 crops (not multiples of 8 or 16) of one seeded lunar scene."""
    from lunar_reg.eval.scenes import add_craters, fractal_terrain, hillshade

    height = add_craters(fractal_terrain((300, 380), seed=3), seed=3)
    img = hillshade(height, azimuth_deg=315, elevation_deg=35)
    src = img[20:270, 20:350].copy()
    ref = img[20 - DY : 270 - DY, 20 - DX : 350 - DX].copy()
    return src, ref


def _assert_exact_shift(result: MatchResult, src: np.ndarray, ref: np.ndarray, tol: float):
    assert len(result) >= 20, f"only {len(result)} matches"
    h0, w0 = src.shape
    h1, w1 = ref.shape
    assert (result.src_pts >= 0).all() and (result.dst_pts >= 0).all()
    assert (result.src_pts[:, 0] < w0).all() and (result.src_pts[:, 1] < h0).all()
    assert (result.dst_pts[:, 0] < w1).all() and (result.dst_pts[:, 1] < h1).all()
    err = np.linalg.norm(result.dst_pts - result.src_pts - np.array([DX, DY]), axis=1)
    assert np.median(err) < tol, f"median error {np.median(err):.3f} px"


@pytest.mark.weights
def test_loftr_cpu_odd_size_pads_and_drops_padding_matches():
    if not _have(LOFTR_WEIGHTS):
        pytest.skip("LoFTR outdoor weights not cached in ~/.cache/torch/hub/checkpoints")
    from lunar_reg.match.learned import LoFTRMatcher

    src, ref = _shifted_pair()
    result = LoFTRMatcher(device="cpu").match(src, ref)
    _assert_exact_shift(result, src, ref, tol=1.0)
    assert result.meta["pad_multiple"] == 8
    assert result.meta["device"] == "cpu" and result.meta["precision"] == "fp32"
    assert result.meta["weights"] == "loftr_outdoor"


@pytest.mark.weights
def test_lightglue_cpu_odd_size():
    if not _have(DISK_LIGHTGLUE_WEIGHTS):
        pytest.skip("DISK/LightGlue weights not cached in ~/.cache/torch/hub/checkpoints")
    from lunar_reg.match.learned import LightGlueMatcher

    src, ref = _shifted_pair()
    result = LightGlueMatcher(device="cpu", max_keypoints=512).match(src, ref)
    _assert_exact_shift(result, src, ref, tol=1.0)
    assert result.meta["device"] == "cpu" and result.meta["precision"] == "fp32"
    assert result.meta["weights"] == "disk_depth+lightglue_disk"


@pytest.mark.gpu
@pytest.mark.weights
def test_lightglue_cuda_does_not_crash():
    if not _cuda():
        pytest.skip("CUDA not available")
    if not _have(DISK_LIGHTGLUE_WEIGHTS):
        pytest.skip("DISK/LightGlue weights not cached in ~/.cache/torch/hub/checkpoints")
    from lunar_reg.match.learned import LightGlueMatcher

    src, ref = _shifted_pair()
    result = LightGlueMatcher(device="cuda", max_keypoints=512).match(src, ref)
    assert len(result) >= 20, f"only {len(result)} matches"
    assert result.meta["device"] == "cuda"
    assert result.meta["precision"] == "fp16-disk+fp32-lightglue"


def test_to_tensor_float_input_matches_to_uint8():
    import torch

    from lunar_reg.match.learned import _to_tensor
    from lunar_reg.preprocess.radiometric import to_uint8

    arr = np.random.default_rng(0).uniform(0, 4000, (33, 47)).astype(np.float32)
    got = _to_tensor(arr, "cpu")
    want = torch.from_numpy(to_uint8(arr).astype(np.float32) / 255.0)[None, None]
    assert got.shape == (1, 1, 33, 47) and got.dtype == torch.float32
    assert torch.allclose(got, want, atol=1e-6)

    # A float image already in [0, 1] is stretched the same way, not passed through.
    unit = arr / arr.max()
    assert torch.allclose(_to_tensor(unit, "cpu"), want, atol=1e-6)


def test_to_tensor_uint8_divides_by_255():
    import torch

    from lunar_reg.match.learned import _to_tensor

    u8 = np.random.default_rng(1).integers(0, 256, (20, 30), dtype=np.uint8)
    want = torch.from_numpy(u8.astype(np.float32) / 255.0)[None, None]
    assert torch.allclose(_to_tensor(u8, "cpu"), want, atol=1e-7)


def test_superglue_licence_gate():
    from lunar_reg.match.superglue import SuperGlueMatcher

    with pytest.raises(PermissionError):
        SuperGlueMatcher()


def test_deduplicate_keeps_one_copy_within_tolerance():
    from lunar_reg.match.stitch import deduplicate

    src = np.array([[10.0, 10.0], [10.5, 10.2], [50.0, 50.0]])
    dst = np.array([[20.0, 20.0], [20.4, 20.1], [60.0, 60.0]])
    out, n_removed = deduplicate(MatchResult(src, dst), tolerance_px=1.5)
    assert n_removed == 1 and len(out) == 2


def test_deduplicate_keeps_both_when_destinations_differ():
    from lunar_reg.match.stitch import deduplicate

    src = np.array([[10.0, 10.0], [10.5, 10.2], [50.0, 50.0]])
    dst = np.array([[20.0, 20.0], [90.0, 90.0], [60.0, 60.0]])
    out, n_removed = deduplicate(MatchResult(src, dst), tolerance_px=1.5)
    assert n_removed == 0 and len(out) == 3
