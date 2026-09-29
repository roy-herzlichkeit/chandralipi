"""Helpers shared by Phase 0 harness tests (import as `from _h0 import ...`). Protected (G05)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
WEIGHTS_DIR = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"


def terrain_image(shape=(300, 380), seed=3) -> np.ndarray:
    from lunar_reg.eval.scenes import add_craters, fractal_terrain, hillshade

    height = add_craters(fractal_terrain(shape, seed=seed), seed=seed)
    return hillshade(height, azimuth_deg=315, elevation_deg=35)


def shifted_pair():
    """Two crops of one terrain image; source (x, y) maps to reference (x + 6, y + 4) exactly."""
    img = terrain_image()
    src = img[20:270, 20:350].copy()   # 250 x 330: not multiples of 8 or 16
    ref = img[16:266, 14:344].copy()
    return src, ref, np.array([6.0, 4.0])


def textured(shape=(256, 256), seed=7, sigma=2.0) -> np.ndarray:
    import cv2

    g = np.random.default_rng(seed).normal(0, 1, shape).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), sigma)
    g = (g - g.min()) / (g.max() - g.min())
    return (g * 255).astype(np.uint8)


def load_script(name: str):
    path = REPO / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_script_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def have_weights(*names: str) -> bool:
    return all((WEIGHTS_DIR / n).exists() for n in names)


def cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001 - absence of torch/CUDA is an environment fact
        return False


def ohrc_labels() -> list[Path]:
    return sorted(REPO.glob("data/raw/ohrc_vikram/*/data/raw/*/*_d_img_*.xml"))


def exact_matches(n_in=60, n_out=40, seed=11, shape=(400, 400), H=None):
    """MatchResult with n_in exact correspondences under H plus n_out random outliers."""
    from lunar_reg.match.base import MatchResult

    rng = np.random.default_rng(seed)
    if H is None:
        H = np.array([[1.01, 0.02, 12.0], [-0.015, 0.99, -7.0], [1e-5, -2e-5, 1.0]])
    src_in = rng.uniform(10, shape[1] - 10, (n_in, 2))
    hom = np.c_[src_in, np.ones(n_in)] @ H.T
    dst_in = hom[:, :2] / hom[:, 2:3]
    src_out = rng.uniform(10, shape[1] - 10, (n_out, 2))
    dst_out = rng.uniform(10, shape[1] - 10, (n_out, 2))
    return MatchResult(np.vstack([src_in, src_out]), np.vstack([dst_in, dst_out]), matcher="stub"), H
