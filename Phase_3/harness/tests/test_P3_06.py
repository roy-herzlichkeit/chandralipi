"""P3.06 — reducer result (Phase_3/LLD/worker_reducer.md §P3.06). Protected (G05)."""

from __future__ import annotations

import numpy as np
from _h3 import T_TRUE, apply, job_kwargs


def test_pair_result_built(tmp_path):
    from lunar_reg.distributed.job import JobDescriptor
    from lunar_reg.distributed.outcome import JobResult, JobStatus, write_job_result
    from lunar_reg.distributed.reducer import reduce_run

    jobs = [JobDescriptor(**job_kwargs("a.tif", "b.tif", tile_index=i)) for i in range(2)]
    rng = np.random.default_rng(1)
    for j in jobs:
        src = rng.uniform(0, 1000, (60, 2))
        write_job_result(JobResult(j.job_id, JobStatus.OK, 60, src, apply(T_TRUE, src), None, "w",
                                   "h", "cpu", 0.1, None, 1, ""), tmp_path)
    failed = JobDescriptor(**job_kwargs("a.tif", "b.tif", tile_index=9))
    e = np.empty((0, 2))
    write_job_result(JobResult(failed.job_id, JobStatus.NO_MATCHES, 0, e, e, None, "w", "h", "cpu",
                               0.1, None, 1, "none"), tmp_path)
    out = reduce_run(tmp_path, [*jobs, failed])
    r = out.result
    assert r.pair_id == "p1_dist" and r.n_matches == 120
    assert r.extra["n_jobs"] == 3 and r.extra["job_no_matches"] == 1
    assert np.abs(apply(r.transform, [[500.0, 500.0]]) - apply(T_TRUE, [[500.0, 500.0]])).max() < 1e-3
