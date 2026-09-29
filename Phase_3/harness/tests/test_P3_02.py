"""P3.02 — result-file edge cases (Phase_3/LLD/job_outcome.md §P3.02). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest


def test_corrupt_and_missing(tmp_path):
    from lunar_reg.distributed.outcome import (
        JobResult, JobStatus, read_job_result, write_job_result,
    )

    pts = np.zeros((2, 2))
    write_job_result(JobResult("j1", JobStatus.OK, 2, pts, pts, None, "w", "h", "cpu", 0.1, None,
                               1, ""), tmp_path)
    (tmp_path / "j1.npz").unlink()
    with pytest.raises(ValueError, match="npz"):
        read_job_result("j1", tmp_path)
    with pytest.raises(FileNotFoundError):
        read_job_result("nope", tmp_path)


def test_failure_results_have_no_points(tmp_path):
    from lunar_reg.distributed.outcome import JobResult, JobStatus, read_job_result, write_job_result

    empty = np.empty((0, 2))
    write_job_result(JobResult("j2", JobStatus.OOM, 0, empty, empty, None, "gpu0", "h", "cuda:0",
                               1.0, 123, 2, "CUDA out of memory"), tmp_path)
    back = read_job_result("j2", tmp_path)
    assert back.status is JobStatus.OOM and back.status.is_failure and back.attempt == 2
