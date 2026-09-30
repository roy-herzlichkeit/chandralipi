"""P3.08 — fault tests present and passing (Phase_3/LLD/runner_faults.md §P3.08). Protected (G05)."""

from __future__ import annotations

import dataclasses
import json
import time

from _h3 import REF_WIN, REPO, SRC_WIN, T_TRUE, write_pair


def test_fault_plan_fields():
    from lunar_reg.distributed.faults import FaultPlan

    assert [f.name for f in dataclasses.fields(FaultPlan)] == [
        "kill_after_claims", "oom_jobs", "read_fail_jobs", "duplicate_jobs"]


def test_fault_suite_has_seven_scenarios():
    text = (REPO / "tests/test_distributed_faults.py").read_text()
    assert text.count("\ndef test_") >= 7
    for word in ("kill", "oom", "read", "duplicate", "determinis", "terminal", "aborted"):
        assert word in text.lower(), word


def test_all_workers_dead_does_not_hang(tmp_path):
    """Review RC06 / G36: every worker dies -> run_local returns, aborted set, all jobs terminal."""
    from lunar_reg.distributed.faults import FaultPlan, faulty_worker_main
    from lunar_reg.distributed.planner import PlanInputs, plan_jobs
    from lunar_reg.distributed.runner import run_local

    write_pair(tmp_path)
    plan = plan_jobs(PlanInputs(run_id="dead", pair_id="p", source_path="src.tif",
                                reference_path="ref.tif", reference_georef={},
                                source_window=SRC_WIN, reference_window=REF_WIN,
                                prior_native=tuple(T_TRUE.ravel()), source_native_gsd_m=0.25,
                                reference_native_gsd_m=1.0), tile_px=128)
    fp = FaultPlan(kill_after_claims={"cpu0": 1, "cpu1": 1})
    t0 = time.monotonic()
    rep = run_local(plan, tmp_path / "run", gpu_workers=0, cpu_workers=2, lease_s=600.0,
                    reclaim_every_s=0.5, repo_root=tmp_path,
                    worker_target=faulty_worker_main(json.dumps(dataclasses.asdict(fp),
                                                                default=list)))
    assert time.monotonic() - t0 < 60, "run_local waited for a lease instead of detecting dead workers"
    assert rep.aborted and "unfinished" in rep.aborted
    assert rep.queue.pending == 0 and rep.queue.leased == 0 and rep.queue.failed >= 2
