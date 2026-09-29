"""P3.09 — single-host distributed run artefacts. Protected (G05)."""

from __future__ import annotations

import json
import sqlite3

import pytest
from _h3 import REPO

pytestmark = [pytest.mark.data, pytest.mark.gpu]
RUN = REPO / "data/processed/distributed/anchor"


def test_artefacts():
    from lunar_reg.runrecord import validate_run_record

    assert validate_run_record(RUN / "run_record.json") == []
    assert (RUN / "plan.json").exists() and (RUN / "single_process.json").exists()
    con = sqlite3.connect(RUN / "queue.sqlite")
    assert con.execute("SELECT COUNT(*) FROM jobs WHERE state='leased'").fetchone()[0] == 0
    json.loads((RUN / "single_process.json").read_text())


def test_reduced_row_and_doc():
    from lunar_reg.results import load_index

    idx = load_index(REPO / "data/processed/results")
    assert idx["pair_id"].str.endswith("_dist").any()
    assert "data/processed/distributed/anchor" in (REPO / "docs/DISTRIBUTED_RUN.md").read_text()
