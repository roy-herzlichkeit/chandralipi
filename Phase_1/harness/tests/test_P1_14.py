"""P1.14 — matcher registry + SuperGlue opt-in (Phase_1/LLD/matcher_registry.md). Protected (G05)."""

from __future__ import annotations

import sys

import numpy as np
import pytest

NAMES = ("sift", "asift", "akaze", "kaze", "orb", "brisk", "rift2", "loftr", "lightglue",
         "superglue")


def test_names_and_classical_build():
    import lunar_reg.match as m

    assert m.MATCHER_NAMES == NAMES
    for name in ("sift", "akaze", "orb", "rift2", "SIFT"):
        assert hasattr(m.build_matcher(name), "match")
    with pytest.raises(ValueError):
        m.build_matcher("nope")


def test_learned_build_matcher_removed():
    import lunar_reg.match.learned as learned

    assert not hasattr(learned, "build_matcher")


def test_aliases(monkeypatch):
    import lunar_reg.match as m
    import lunar_reg.match.learned as learned

    seen = []
    monkeypatch.setattr(learned, "LightGlueMatcher", lambda **kw: seen.append(kw) or "lg")
    assert m.build_matcher("disk", device="cpu") == "lg"
    assert m.build_matcher("lightglue/disk", device="cpu") == "lg"
    assert seen[0]["device"] == "cpu"


def test_superglue_gate(monkeypatch):
    import lunar_reg.match as m

    monkeypatch.delenv("SUPERGLUE_ACCEPT_NONCOMMERCIAL", raising=False)
    with pytest.raises(PermissionError):
        m.build_matcher("superglue")


def test_superglue_loads_without_syspath(monkeypatch, tmp_path):
    import lunar_reg.match as m

    pkg = tmp_path / "sg" / "models"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "matching.py").write_text(
        "class Matching:\n    def __init__(self, config=None):\n        self.config = config\n"
        "    def eval(self):\n        return self\n    def to(self, device):\n        return self\n")
    monkeypatch.setenv("SUPERGLUE_ACCEPT_NONCOMMERCIAL", "1")
    monkeypatch.setenv("SUPERGLUE_DIR", str(tmp_path / "sg"))
    before = list(sys.path)
    matcher = m.build_matcher("superglue", device="cpu")
    model = matcher._get_model()
    assert type(model).__name__ == "Matching"
    assert sys.path == before
    assert "_superglue_models" not in sys.modules


def test_register_pair_licence_error(monkeypatch):
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    monkeypatch.delenv("SUPERGLUE_ACCEPT_NONCOMMERCIAL", raising=False)
    img = np.zeros((64, 64), np.uint8)
    out = register_pair(img, img, "sg", PipelineConfig(matcher="superglue"))
    assert out.status is RunStatus.MATCHER_ERROR and "licen" in out.detail.lower()
