"""P1B.05 — runner bridge fields (Phase_1B/LLD/bridge_runner.md §P1B.05). Protected (G05)."""

from __future__ import annotations

import dataclasses

from _h1b import REPO


def test_fields_and_flags():
    from lunar_reg.sites.runner import SiteConfig

    f = {x.name: x.default for x in dataclasses.fields(SiteConfig)}
    assert f["bridge"] is False
    assert f["bridge_matchers"] == ("sift", "akaze", "asift", "lightglue", "rift2")
    assert f["bridge_anchor_tag"] == "20240425T1406019344"
    text = (REPO / "scripts/run_vikram.py").read_text()
    for flag in ("--bridge", "--bridge-dtm", "--bridge-matchers"):
        assert flag in text
