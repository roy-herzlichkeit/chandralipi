"""P2.10 — runner native mode wiring (Phase_2/LLD/runner_gpu_runs.md §P2.10). Protected (G05)."""

from __future__ import annotations

import dataclasses

from _h2 import REPO


def test_site_config_fields():
    from lunar_reg.sites.runner import SiteConfig

    f = {x.name: x.default for x in dataclasses.fields(SiteConfig)}
    assert f["device"] is None and f["precision"] == "auto" and f["native"] is False
    assert f["native_matcher"] == "sift" and f["native_max_drift_coarse_px"] == 1.0


def test_cli_flags():
    text = (REPO / "scripts/run_vikram.py").read_text()
    for flag in ("--device", "--precision", "--native", "--native-matcher", "--native-tile-px"):
        assert flag in text
