"""P4.06 — two-host run artefacts. Protected (G05)."""

from __future__ import annotations

import pytest
from _h4 import REPO

pytestmark = [pytest.mark.data, pytest.mark.gpu]
RUN = REPO / "data/processed/multihost/anchor"


def test_artefacts():
    import json

    from lunar_reg.runrecord import validate_run_record

    assert validate_run_record(RUN / "run_record.json") == []
    rec = json.loads((RUN / "run_record.json").read_text())
    assert rec["outcome_counts"].get("lost_events", 0) >= 1
    assert rec["outcome_counts"].get("mismatched", 0) == 0
    assert (RUN / "results_laptop").is_dir() and (RUN / "results_rtx3060").is_dir()
    assert "data/processed/multihost/anchor" in (REPO / "docs/MULTIHOST_RUN.md").read_text()
