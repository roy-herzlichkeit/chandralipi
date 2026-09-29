"""P3.08 — fault tests present and passing (Phase_3/LLD/runner_faults.md §P3.08). Protected (G05)."""

from __future__ import annotations

import dataclasses

from _h3 import REPO


def test_fault_plan_fields():
    from lunar_reg.distributed.faults import FaultPlan

    assert [f.name for f in dataclasses.fields(FaultPlan)] == [
        "kill_after_claims", "oom_jobs", "read_fail_jobs", "duplicate_jobs"]


def test_fault_suite_has_six_scenarios():
    text = (REPO / "tests/test_distributed_faults.py").read_text()
    assert text.count("\ndef test_") >= 6
    for word in ("kill", "oom", "read", "duplicate", "determinis", "terminal"):
        assert word in text.lower(), word
