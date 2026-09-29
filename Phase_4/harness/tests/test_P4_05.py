"""P4.05 — merge + consistency (Phase_4/LLD/determinism_run.md §P4.05). Protected (G05)."""

from __future__ import annotations

import numpy as np
from _h4 import job


def _write(d, j, shift=0.0):
    from lunar_reg.distributed.outcome import JobResult, JobStatus, write_job_result

    pts = np.arange(20, dtype=float).reshape(10, 2)
    write_job_result(JobResult(j.job_id, JobStatus.OK, 10, pts, pts * 0.25 + shift, None, "w",
                               d.name, "cpu", 0.1, None, 1, ""), d)


def test_merge_duplicates_and_mismatch(tmp_path):
    from lunar_reg.distributed.outcome import merge_result_dirs

    j = job(0)
    a, b, c = tmp_path / "a", tmp_path / "b", tmp_path / "c"
    _write(a, j)
    _write(b, j)
    diag = merge_result_dirs([a, b], tmp_path / "m1")
    assert diag.n_duplicates == 1 and diag.n_mismatched == 0
    _write(c, j, shift=0.5)
    diag = merge_result_dirs([a, c], tmp_path / "m2")
    assert diag.n_mismatched == 1


def test_require_consistent_fails(tmp_path):
    from lunar_reg.distributed.outcome import merge_result_dirs
    from lunar_reg.distributed.reducer import reduce_run
    from lunar_reg.pipeline import RunStatus

    j = job(0)
    a, c = tmp_path / "a", tmp_path / "c"
    _write(a, j)
    _write(c, j, shift=0.5)
    merge_result_dirs([a, c], tmp_path / "m")
    out = reduce_run(tmp_path / "m", [j], require_consistent=True)
    assert out.status is RunStatus.EVAL_FAILED and j.job_id[:8] in out.detail
