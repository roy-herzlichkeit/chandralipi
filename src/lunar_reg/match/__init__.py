"""Correspondence finding, classical and learned.

:func:`build_matcher` is the one place that turns a matcher name into a
matcher object; the pipeline, the CLI and the scripts all go through it.
"""

from __future__ import annotations

import os

from lunar_reg.match.base import Matcher, MatchResult
from lunar_reg.match.classical import (
    DETECTORS,
    PAPER_BASELINES,
    ClassicalMatcher,
    RIFT2Matcher,
    available_detectors,
    build_classical,
    paper_baseline_status,
)
from lunar_reg.match.learned import LightGlueMatcher, LoFTRMatcher
from lunar_reg.match.tiled import TiledMatcher

__all__ = [
    "DETECTORS",
    "PAPER_BASELINES",
    "ClassicalMatcher",
    "RIFT2Matcher",
    "available_detectors",
    "build_classical",
    "paper_baseline_status",
    "LightGlueMatcher",
    "LoFTRMatcher",
    "MatchResult",
    "Matcher",
    "TiledMatcher",
    "ALIASES",
    "MATCHER_NAMES",
    "build_matcher",
]

#: Every matcher name :func:`build_matcher` accepts (after :data:`ALIASES`).
MATCHER_NAMES = (
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

#: Alternative spellings, mapped to their canonical :data:`MATCHER_NAMES` entry.
ALIASES = {"disk": "lightglue", "lightglue/disk": "lightglue", "loftr/outdoor": "loftr"}

#: Matchers built by :func:`lunar_reg.match.classical.build_classical`.
_CLASSICAL = ("sift", "asift", "akaze", "kaze", "orb", "brisk", "rift2")

#: Environment switch that accepts SuperGlue's noncommercial licence (DECISIONS G11).
SUPERGLUE_ACCEPT_ENV = "SUPERGLUE_ACCEPT_NONCOMMERCIAL"


def build_matcher(name: str, *, device: str | None = None, **kwargs) -> Matcher:
    """Construct any matcher by name.

    The lookup is case-insensitive and resolves :data:`ALIASES` first; an
    unknown name raises ``ValueError`` listing :data:`MATCHER_NAMES`. ``device``
    is ignored by the classical (OpenCV) matchers. SuperGlue is built only when
    ``accept_noncommercial_licence=True`` is passed or the environment sets
    ``SUPERGLUE_ACCEPT_NONCOMMERCIAL=1``; otherwise its constructor raises
    ``PermissionError``.
    """
    # Module attributes, looked up at call time, so tests can monkeypatch them.
    from lunar_reg.match import classical, learned, superglue

    key = name.lower()
    key = ALIASES.get(key, key)
    if key not in MATCHER_NAMES:
        raise ValueError(f"unknown matcher {name!r}; known: {MATCHER_NAMES}")
    if key in _CLASSICAL:
        return classical.build_classical(key, **kwargs)
    if key == "loftr":
        return learned.LoFTRMatcher(device=device, **kwargs)
    if key == "lightglue":
        return learned.LightGlueMatcher(device=device, **kwargs)
    accept = bool(kwargs.pop("accept_noncommercial_licence", False)) or (
        os.environ.get(SUPERGLUE_ACCEPT_ENV) == "1"
    )
    return superglue.SuperGlueMatcher(device=device, accept_noncommercial_licence=accept, **kwargs)
