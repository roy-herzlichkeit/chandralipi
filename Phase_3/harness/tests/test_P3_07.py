"""P3.07 — local runner end to end on CPU (Phase_3/LLD/runner_faults.md §P3.07). Protected (G05)."""

from __future__ import annotations

import numpy as np
from _h3 import REF_WIN, SRC_WIN, T_TRUE, apply, write_pair


def test_run_local_cpu(tmp_path):
    from lunar_reg.distributed.planner import PlanInputs, plan_jobs
    from lunar_reg.distributed.runner import run_local
    from lunar_reg.pipeline import RunStatus

    write_pair(tmp_path)
    inputs = PlanInputs(run_id="t", pair_id="p", source_path="src.tif", reference_path="ref.tif",
                        reference_georef={}, source_window=SRC_WIN,
                        reference_window=REF_WIN, prior_native=tuple(T_TRUE.ravel()),
                        source_native_gsd_m=0.25, reference_native_gsd_m=1.0)
    plan = plan_jobs(inputs, tile_px=128)
    rep = run_local(plan, tmp_path / "run", gpu_workers=0, cpu_workers=2, lease_s=60,
                    reclaim_every_s=0.5, repo_root=tmp_path)
    assert rep.reduce.status is RunStatus.OK, rep.reduce.detail
    assert rep.queue.leased == 0 and rep.queue.pending == 0
    probe = [[768.0, 1024.0], [400.0, 700.0]]   # inside SRC_WIN (x=col, y=row), away from the origin
    assert np.abs(apply(rep.reduce.transform, probe) - apply(T_TRUE, probe)).max() < 0.5
    assert rep.aborted is None
    assert (tmp_path / "run" / "run_record.json").exists() and (tmp_path / "run" / "plan.json").exists()


def test_cli_subcommand():
    from lunar_reg.cli import build_parser

    args = build_parser().parse_args(["distributed", "run", "--pair-id", "x", "--source-label", "a",
                                      "--reference-label", "b", "--run-dir", "d"])
    assert args.pair_id == "x"
