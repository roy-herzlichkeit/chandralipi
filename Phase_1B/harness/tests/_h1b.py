"""Helpers shared by Phase 1B harness tests (import as `from _h1b import ...`). Protected (G05)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
TAGS_2023 = ("20230823T1450475804", "20230823T1647285085", "20230823T1647285315")


def dtm(shape=(256, 256), seed=2, scale=30.0) -> np.ndarray:
    from lunar_reg.eval.scenes import add_craters, fractal_terrain

    return add_craters(fractal_terrain(shape, seed=seed), seed=seed).astype(np.float64) * scale


def matches_under(H, n=80, noise=0.2, seed=0, shape=(400, 400), offset=(0.0, 0.0)):
    from lunar_reg.match.base import MatchResult

    rng = np.random.default_rng(seed)
    src = rng.uniform(10, shape[1] - 10, (n, 2))
    h = np.c_[src, np.ones(n)] @ H.T
    dst = h[:, :2] / h[:, 2:3] + rng.normal(0, noise, (n, 2)) + np.asarray(offset)
    return MatchResult(src, dst, matcher="stub")
