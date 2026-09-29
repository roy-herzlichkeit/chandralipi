"""P3.04 — concurrent claims (Phase_3/LLD/queue.md). Protected (G05)."""

from __future__ import annotations

import multiprocessing as mp

from _h3 import job_kwargs


def _claimer(path, worker, out_q):
    from lunar_reg.distributed.outcome import JobStatus
    from lunar_reg.distributed.queue import LocalJobQueue

    q = LocalJobQueue(path)
    got = []
    while True:
        lease = q.claim(worker, 30.0)
        if lease is None:
            break
        got.append(lease.job.job_id)
        q.ack(lease, JobStatus.OK)
    out_q.put(got)


def test_no_double_claims(tmp_path):
    from lunar_reg.distributed.job import JobDescriptor
    from lunar_reg.distributed.queue import LocalJobQueue

    path = tmp_path / "q.sqlite"
    q = LocalJobQueue(path)
    for i in range(50):
        q.put(JobDescriptor(**job_kwargs("a.tif", "b.tif", tile_index=i)))
    ctx = mp.get_context("spawn")
    out_q = ctx.Queue()
    procs = [ctx.Process(target=_claimer, args=(path, f"w{k}", out_q)) for k in range(2)]
    for p in procs:
        p.start()
    results = [out_q.get(timeout=120) for _ in procs]
    for p in procs:
        p.join(timeout=60)
    claimed = results[0] + results[1]
    assert len(claimed) == 50 and len(set(claimed)) == 50
    assert q.stats().done == 50
