"""Phase 3 contract tests: C22-C26 (G16). Protected (G05)."""

from __future__ import annotations

import dataclasses
import json

import numpy as np
import pytest
from _h3 import T_TRUE, apply, job_kwargs, write_pair

# --------------------------------------------------------------------- C22

C22_FIELDS = ["run_id", "pair_id", "tile_index", "source_path", "reference_path", "source_window",
              "reference_window", "prior", "working_gsd_m", "source_native_gsd_m",
              "reference_native_gsd_m", "preprocess", "matcher", "precision", "tile_px",
              "est_vram_bytes", "base_seed", "reference_georef", "schema"]


def test_C22_roundtrip():
    from lunar_reg.distributed.job import JOB_SCHEMA, JobDescriptor

    assert JOB_SCHEMA == 1
    assert [f.name for f in dataclasses.fields(JobDescriptor)] == C22_FIELDS
    j = JobDescriptor(**job_kwargs("a.tif", "b.tif"))
    assert JobDescriptor.from_json(j.to_json()) == j
    assert json.loads(j.to_json())["schema"] == 1


def test_C22_job_id_stable():
    import hashlib

    from lunar_reg.distributed.job import JobDescriptor

    j = JobDescriptor(**job_kwargs("a.tif", "b.tif"))
    assert j.job_id == hashlib.sha256(j.to_json().encode()).hexdigest()
    assert j.seed == (0 + int(j.job_id[:8], 16)) % 2**31
    other = JobDescriptor(**job_kwargs("a.tif", "b.tif", tile_index=1))
    assert other.job_id != j.job_id


def test_C22_key_order_irrelevant():
    from lunar_reg.distributed.job import JobDescriptor

    j = JobDescriptor(**job_kwargs("a.tif", "b.tif"))
    shuffled = json.dumps(dict(reversed(list(json.loads(j.to_json()).items()))))
    assert JobDescriptor.from_json(shuffled).job_id == j.job_id
    with pytest.raises(ValueError):
        JobDescriptor(**job_kwargs("/abs.tif", "b.tif"))
    with pytest.raises(ValueError):
        JobDescriptor(**job_kwargs("a.tif", "b.tif", prior=(1.0,) * 8))


# --------------------------------------------------------------------- C23


def _result(job_id="abc", status=None, n=5):
    from lunar_reg.distributed.outcome import JobResult, JobStatus

    pts = np.arange(2 * n, dtype=float).reshape(n, 2)
    return JobResult(job_id, status or JobStatus.OK, n, pts, pts + 1, None, "w0", "h", "cpu",
                     0.5, None, 1, "")


def test_C23_roundtrip(tmp_path):
    from lunar_reg.distributed.outcome import JobStatus, read_job_result, write_job_result

    assert {m.value for m in JobStatus} == {"ok", "no_matches", "degenerate_overlap",
                                            "read_failed", "oom", "worker_lost", "timeout",
                                            "matcher_error"}
    r = _result()
    path, new = write_job_result(r, tmp_path)
    assert new and path == tmp_path / "abc.json" and (tmp_path / "abc.npz").exists()
    back = read_job_result("abc", tmp_path)
    assert back.status is JobStatus.OK and back.bytes_read == 0
    np.testing.assert_array_equal(back.dst_pts, r.dst_pts)


def test_C23_idempotent_write(tmp_path):
    from lunar_reg.distributed.outcome import JobDiagnostics, write_job_result

    write_job_result(_result(), tmp_path)
    before = (tmp_path / "abc.npz").read_bytes()
    _, new = write_job_result(_result(n=9), tmp_path)
    assert new is False and (tmp_path / "abc.npz").read_bytes() == before
    d = JobDiagnostics()
    d.record(_result(), duplicate=True)
    assert d.n_duplicates == 1 and "duplicates" in d.report()
    assert not list(tmp_path.glob(".*"))


# --------------------------------------------------------------------- C24


def _job(i):
    from lunar_reg.distributed.job import JobDescriptor

    return JobDescriptor(**job_kwargs("a.tif", "b.tif", tile_index=i, est_vram_bytes=100 * i))


def test_C24_put_dedupe(tmp_path):
    from lunar_reg.distributed.queue import JobQueue, LocalJobQueue

    q = LocalJobQueue(tmp_path / "q.sqlite")
    assert isinstance(q, JobQueue)
    assert q.put(_job(0)) is True and q.put(_job(0)) is False
    assert q.stats().pending == 1


def test_C24_lease_expiry_counts_lost(tmp_path):
    from lunar_reg.distributed.outcome import JobStatus
    from lunar_reg.distributed.queue import LocalJobQueue

    now = [1000.0]
    q = LocalJobQueue(tmp_path / "q.sqlite", clock=lambda: now[0])
    q.put(_job(1))
    lease = q.claim("w0", lease_s=10.0)
    assert lease is not None and lease.attempt == 1
    now[0] += 11.0
    assert q.reclaim_expired() == [lease.job.job_id]
    assert q.ack(lease, JobStatus.OK) is False
    lease2 = q.claim("w1", lease_s=10.0)
    assert lease2.attempt == 2 and q.ack(lease2, JobStatus.OK) is True
    s = q.stats()
    assert (s.done, s.lost_events, s.leased) == (1, 1, 0)


def test_C24_max_attempts(tmp_path):
    from lunar_reg.distributed.queue import MAX_ATTEMPTS, LocalJobQueue

    assert MAX_ATTEMPTS == 3
    now = [0.0]
    q = LocalJobQueue(tmp_path / "q.sqlite", clock=lambda: now[0])
    q.put(_job(2))
    for _ in range(MAX_ATTEMPTS):
        assert q.claim("w", lease_s=1.0) is not None
        now[0] += 2.0
        q.reclaim_expired()
    s = q.stats()
    assert s.failed == 1 and s.pending == 0 and q.claim("w", 1.0) is None


def test_C24_max_bytes(tmp_path):
    from lunar_reg.distributed.queue import LocalJobQueue

    q = LocalJobQueue(tmp_path / "q.sqlite")
    q.put(_job(5))   # est 500
    q.put(_job(1))   # est 100
    lease = q.claim("small", 10.0, max_bytes=200)
    assert lease.job.tile_index == 1
    assert q.claim("small", 10.0, max_bytes=200) is None


# --------------------------------------------------------------------- C25


def test_C25_process_job_synthetic(tmp_path):
    from lunar_reg.distributed.job import JobDescriptor
    from lunar_reg.distributed.outcome import JobStatus
    from lunar_reg.distributed.worker import process_job

    write_pair(tmp_path)
    job = JobDescriptor(**job_kwargs("src.tif", "ref.tif"))
    r = process_job(job, "cpu", repo_root=tmp_path)
    assert r.status is JobStatus.OK, r.detail
    err = np.linalg.norm(apply(T_TRUE, r.src_pts) - r.dst_pts, axis=1)
    assert np.median(err) < 0.5
    assert r.bytes_read > 0 and r.device == "cpu"


def test_C25_read_failed_classified(tmp_path):
    from lunar_reg.distributed.job import JobDescriptor
    from lunar_reg.distributed.outcome import JobStatus
    from lunar_reg.distributed.worker import process_job

    job = JobDescriptor(**job_kwargs("missing.tif", "ref.tif"))
    assert process_job(job, "cpu", repo_root=tmp_path).status is JobStatus.READ_FAILED


# --------------------------------------------------------------------- C26


def _write_results(tmp_path, jobs, order):
    from lunar_reg.distributed.outcome import JobResult, JobStatus, write_job_result

    rng = np.random.default_rng(0)
    for k in order:
        j = jobs[k]
        src = rng.uniform(0, 1000, (40, 2))
        dst = apply(T_TRUE, src) + rng.normal(0, 0.1, (40, 2))
        write_job_result(JobResult(j.job_id, JobStatus.OK, 40, src, dst, None, "w", "h", "cpu",
                                   0.1, None, 1, ""), tmp_path)


def test_C26_order_independent(tmp_path):
    from lunar_reg.distributed.reducer import reduce_run
    from lunar_reg.pipeline import RunStatus

    jobs = [_job(i) for i in range(3)]
    a, b = tmp_path / "a", tmp_path / "b"
    _write_results(a, jobs, [0, 1, 2])
    _write_results(b, jobs, [2, 0, 1])
    ra, rb = reduce_run(a, jobs), reduce_run(b, jobs)
    assert ra.status is RunStatus.OK
    assert ra.transform.tobytes() == rb.transform.tobytes()


def test_C26_missing_jobs_reported(tmp_path):
    from lunar_reg.distributed.reducer import reduce_run

    jobs = [_job(i) for i in range(3)]
    _write_results(tmp_path, jobs[:2], [0, 1])
    out = reduce_run(tmp_path, jobs)
    assert out.missing_jobs == [jobs[2].job_id]
