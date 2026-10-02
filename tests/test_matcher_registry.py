"""One matcher registry + SuperGlue opt-in (Phase_1/LLD/matcher_registry.md §4)."""

from __future__ import annotations

import sys

import numpy as np
import pytest

_STUB_MATCHING = (
    "class Matching:\n"
    "    def __init__(self, config=None):\n"
    "        self.config = config\n"
    "    def eval(self):\n"
    "        return self\n"
    "    def to(self, device):\n"
    "        self.device = device\n"
    "        return self\n"
)


def _fake_checkout(root, *, with_init: bool = True):
    models = root / "models"
    models.mkdir(parents=True)
    if with_init:
        (models / "__init__.py").write_text("")
    (models / "matching.py").write_text(_STUB_MATCHING)
    return root


@pytest.mark.parametrize(
    "name", ["sift", "asift", "akaze", "kaze", "orb", "brisk", "rift2", "SIFT", "Rift2"]
)
def test_classical_names_build_on_cpu(name):
    from lunar_reg.match import build_matcher

    matcher = build_matcher(name, device="cpu")
    assert hasattr(matcher, "match")


def test_matcher_names_cover_registry():
    from lunar_reg.match import ALIASES, MATCHER_NAMES

    assert MATCHER_NAMES == (
        "sift",
        "asift",
        "akaze",
        "kaze",
        "orb",
        "brisk",
        "rift2",
        "loftr",
        "lightglue",
        "superglue",
    )
    assert set(ALIASES.values()) <= set(MATCHER_NAMES)


@pytest.mark.parametrize(
    ("alias", "attr"),
    [
        ("disk", "LightGlueMatcher"),
        ("lightglue/disk", "LightGlueMatcher"),
        ("LightGlue", "LightGlueMatcher"),
        ("loftr/outdoor", "LoFTRMatcher"),
        ("loftr", "LoFTRMatcher"),
    ],
)
def test_aliases_resolve_to_learned(monkeypatch, alias, attr):
    import lunar_reg.match.learned as learned
    from lunar_reg.match import build_matcher

    seen = []
    monkeypatch.setattr(learned, attr, lambda **kw: seen.append(kw) or attr)
    assert build_matcher(alias, device="cpu") == attr
    assert seen == [{"device": "cpu"}]


def test_unknown_name_raises_with_known_list():
    from lunar_reg.match import build_matcher

    with pytest.raises(ValueError, match="unknown matcher 'nope'; known:"):
        build_matcher("nope")


def test_learned_build_matcher_is_gone():
    import lunar_reg.match.learned as learned

    assert not hasattr(learned, "build_matcher")


def test_superglue_refused_without_env_or_flag(monkeypatch):
    from lunar_reg.match import build_matcher

    monkeypatch.delenv("SUPERGLUE_ACCEPT_NONCOMMERCIAL", raising=False)
    with pytest.raises(PermissionError, match="(?i)licen"):
        build_matcher("superglue", device="cpu")
    monkeypatch.setenv("SUPERGLUE_ACCEPT_NONCOMMERCIAL", "yes")  # only "1" accepts
    with pytest.raises(PermissionError):
        build_matcher("superglue", device="cpu")


def test_superglue_flag_and_old_keyword(monkeypatch):
    from lunar_reg.match import build_matcher
    from lunar_reg.match.superglue import SuperGlueMatcher

    monkeypatch.delenv("SUPERGLUE_ACCEPT_NONCOMMERCIAL", raising=False)
    assert build_matcher("superglue", device="cpu", accept_noncommercial_licence=True)
    assert SuperGlueMatcher(device="cpu", acknowledge_noncommercial_licence=True)
    assert SuperGlueMatcher(device="cpu", accept_noncommercial_licence=True)


def test_superglue_loads_from_env_dir_without_touching_sys_path(monkeypatch, tmp_path):
    from lunar_reg.match import build_matcher

    checkout = _fake_checkout(tmp_path / "sg")
    monkeypatch.setenv("SUPERGLUE_ACCEPT_NONCOMMERCIAL", "1")
    monkeypatch.setenv("SUPERGLUE_DIR", str(checkout))
    before = list(sys.path)
    matcher = build_matcher("superglue", device="cpu")
    model = matcher._get_model()
    assert type(model).__name__ == "Matching"
    assert model.config["superglue"]["weights"] == "outdoor"
    assert model.device == "cpu"
    assert sys.path == before
    assert not [n for n in sys.modules if n.startswith("_superglue_models")]
    assert matcher._get_model() is model  # cached


def test_superglue_missing_init_or_dir_is_import_error(monkeypatch, tmp_path):
    from lunar_reg.match.superglue import SuperGlueMatcher

    monkeypatch.delenv("SUPERGLUE_DIR", raising=False)
    no_dir = SuperGlueMatcher(device="cpu", accept_noncommercial_licence=True)
    with pytest.raises(ImportError, match="does not vendor"):
        no_dir._get_model()

    checkout = _fake_checkout(tmp_path / "sg", with_init=False)
    no_init = SuperGlueMatcher(
        device="cpu", accept_noncommercial_licence=True, weights_dir=str(checkout)
    )
    with pytest.raises(ImportError, match="does not vendor"):
        no_init._get_model()
    assert not [n for n in sys.modules if n.startswith("_superglue_models")]


def test_register_pair_superglue_without_licence_is_matcher_error(monkeypatch):
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    monkeypatch.delenv("SUPERGLUE_ACCEPT_NONCOMMERCIAL", raising=False)
    img = np.zeros((64, 64), np.uint8)
    out = register_pair(img, img, "sg", PipelineConfig(matcher="superglue", preprocess="none"))
    assert out.status is RunStatus.MATCHER_ERROR
    assert "licence" in out.detail.lower()


def test_register_pair_copies_licence_into_extra(monkeypatch):
    from lunar_reg.match.base import MatchResult
    from lunar_reg.match.superglue import LICENCE_TAG
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    class _Stub:
        def match(self, source, reference):
            return MatchResult(
                np.empty((0, 2)),
                np.empty((0, 2)),
                matcher="superglue/outdoor",
                meta={"licence": LICENCE_TAG},
            )

    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name: _Stub())
    img = np.zeros((64, 64), np.uint8)
    out = register_pair(img, img, "sg", PipelineConfig(matcher="superglue", preprocess="none"))
    assert out.status is RunStatus.TOO_FEW_MATCHES
    assert out.extra["licence"] == LICENCE_TAG


def test_successful_superglue_pair_records_licence(monkeypatch):
    import cv2

    from lunar_reg.match.base import MatchResult
    from lunar_reg.match.superglue import LICENCE_TAG
    from lunar_reg.pipeline import PipelineConfig, RunStatus, register_pair

    rng = np.random.default_rng(5)
    noise = cv2.GaussianBlur(rng.normal(0, 1, (300, 300)).astype(np.float32), (0, 0), 2.0)
    img = ((noise - noise.min()) / (noise.max() - noise.min()) * 255).astype(np.uint8)
    src = rng.uniform(10, 290, (60, 2))
    dst = src + np.array([4.0, -3.0])

    class _Stub:
        def match(self, source, reference):
            return MatchResult(
                src,
                dst,
                matcher="superglue/outdoor",
                meta={"detector": "superglue", "licence": LICENCE_TAG},
            )

    monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name: _Stub())
    config = PipelineConfig(matcher="superglue", use_ecc=False, n_bootstrap=0)
    out = register_pair(img, img, "sg", config)
    assert out.status is RunStatus.OK, out.detail
    assert out.result.extra["licence"] == LICENCE_TAG
    assert out.result.extra["matcher_licence"] == LICENCE_TAG
    assert out.extra["licence"] == LICENCE_TAG
