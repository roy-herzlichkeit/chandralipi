"""Helpers shared by Phase 2 harness tests (import as `from _h2 import ...`). Protected (G05)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
PROFILE = REPO / "configs/device_profiles/rtx4060-laptop.json"


def cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return False


def load_script(name: str):
    path = REPO / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_script_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def textured(shape=(512, 512), seed=7, sigma=2.0) -> np.ndarray:
    import cv2

    g = np.random.default_rng(seed).normal(0, 1, shape).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), sigma)
    return (1 + (g - g.min()) / (g.max() - g.min()) * 254).astype(np.uint8)


def terrain(shape=(1024, 1024), seed=3) -> np.ndarray:
    from lunar_reg.eval.scenes import add_craters, fractal_terrain, hillshade

    h = add_craters(fractal_terrain(shape, seed=seed), n=int(45 * shape[0] * shape[1] / 512**2),
                    seed=seed)
    img = hillshade(h, azimuth_deg=315, elevation_deg=35)
    return np.maximum(img, 1).astype(np.uint8)


def similarity(scale, angle_deg, tx, ty) -> np.ndarray:
    a = np.radians(angle_deg)
    c, s = scale * np.cos(a), scale * np.sin(a)
    return np.array([[c, -s, tx], [s, c, ty], [0.0, 0.0, 1.0]])


def apply(H, pts):
    pts = np.asarray(pts, float)
    h = np.c_[pts, np.ones(len(pts))] @ H.T
    return h[:, :2] / h[:, 2:3]
