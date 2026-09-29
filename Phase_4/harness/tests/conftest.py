"""pytest configuration for Phase 4 harness tests. Protected (G05).

Implementation modules are imported inside test functions (G15), so a missing
implementation fails the test instead of breaking collection.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _h4 import REPO  # noqa: E402


def pytest_configure(config):
    # Registered here as well as in pyproject (P0.01) so --strict-markers never
    # fails collection before P0.01 has run.
    for line in (
        "gpu: requires a working CUDA device",
        "data: requires real products under data/raw",
        "weights: requires pretrained matcher weights in ~/.cache/torch/hub/checkpoints",
    ):
        config.addinivalue_line("markers", line)


@pytest.fixture(autouse=True)
def _repo_cwd(monkeypatch):
    monkeypatch.chdir(REPO)


@pytest.fixture
def rng():
    return np.random.default_rng(20260929)
