"""P3.05 — worker edge cases (Phase_3/LLD/worker_reducer.md §P3.05). Protected (G05)."""

from __future__ import annotations

import numpy as np
from _h3 import SRC_SHAPE, job_kwargs, write_pair


def test_blank_is_degenerate(tmp_path):
    import rasterio

    from lunar_reg.distributed.job import JobDescriptor
    from lunar_reg.distributed.outcome import JobStatus
    from lunar_reg.distributed.worker import process_job

    write_pair(tmp_path)
    with rasterio.open(tmp_path / "blank.tif", "w", driver="GTiff", width=SRC_SHAPE[1],
                       height=SRC_SHAPE[0], count=1, dtype="uint8") as ds:
        ds.write(np.zeros(SRC_SHAPE, np.uint8), 1)
    job = JobDescriptor(**job_kwargs("blank.tif", "ref.tif"))
    assert process_job(job, "cpu", repo_root=tmp_path).status is JobStatus.DEGENERATE_OVERLAP


def test_matcher_error_classified(tmp_path):
    from lunar_reg.distributed.job import JobDescriptor
    from lunar_reg.distributed.outcome import JobStatus
    from lunar_reg.distributed.worker import process_job

    write_pair(tmp_path)

    class Bad:
        name = "bad"

        def match(self, s, r):
            raise RuntimeError("boom")

    job = JobDescriptor(**job_kwargs("src.tif", "ref.tif"))
    r = process_job(job, "cpu", repo_root=tmp_path, matcher_factory=lambda n, d: Bad())
    assert r.status is JobStatus.MATCHER_ERROR and "boom" in r.detail


def test_run_worker_drains_queue(tmp_path):
    from lunar_reg.distributed.job import JobDescriptor
    from lunar_reg.distributed.queue import LocalJobQueue
    from lunar_reg.distributed.worker import run_worker

    write_pair(tmp_path)
    q = LocalJobQueue(tmp_path / "q.sqlite")
    q.put(JobDescriptor(**job_kwargs("src.tif", "ref.tif")))
    q.put(JobDescriptor(**job_kwargs("missing.tif", "ref.tif", tile_index=1)))
    import os

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        summary = run_worker(q, tmp_path / "results", "w0", "cpu", idle_exit_s=0.5)
    finally:
        os.chdir(cwd)
    assert summary.processed == 2 and summary.counts == {"ok": 1, "read_failed": 1}
    assert q.stats().done == 1 and q.stats().failed == 1
