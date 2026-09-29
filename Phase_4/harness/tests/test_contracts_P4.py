"""Phase 4 contract tests: C27 (G16). Protected (G05)."""

from __future__ import annotations

import json

from _h4 import REPO, fake_client, job


def test_C27_fakeredis_protocol_conformance():
    from lunar_reg.distributed.outcome import JobStatus
    from lunar_reg.distributed.queue import JobQueue, MAX_ATTEMPTS
    from lunar_reg.distributed.redis_queue import RedisJobQueue

    q = RedisJobQueue("redis://unused", "run1", client=fake_client())
    assert isinstance(q, JobQueue)
    assert q.put(job(0)) is True and q.put(job(0)) is False
    lease = q.claim("w0", lease_s=0.0)
    assert lease is not None and lease.attempt == 1
    requeued = q.reclaim_expired(lease_s=0.0)
    assert requeued == [lease.job.job_id]
    assert q.ack(lease, JobStatus.OK) is False
    for _ in range(MAX_ATTEMPTS - 1):
        lz = q.claim("w1", lease_s=0.0)
        assert lz is not None
        q.reclaim_expired(lease_s=0.0)
    s = q.stats()
    assert s.failed == 1 and s.pending == 0 and s.lost_events == MAX_ATTEMPTS
    q.put(job(1))
    lease = q.claim("w2", lease_s=60.0)
    assert q.ack(lease, JobStatus.OK) is True and q.stats().done == 1


def test_C27_max_bytes_skip():
    from lunar_reg.distributed.redis_queue import RedisJobQueue

    q = RedisJobQueue("redis://unused", "run2", client=fake_client())
    q.put(job(0, est_vram_bytes=5 * 2**30))
    q.put(job(1, est_vram_bytes=1 * 2**30))
    lease = q.claim("small", 60.0, max_bytes=2 * 2**30)
    assert lease is not None and lease.job.tile_index == 1
    assert q.stats().pending == 1


def test_C27_hosts_example_schema():
    doc = json.loads((REPO / "configs/hosts.example.json").read_text())
    assert doc["schema"] == 1 and set(doc["broker"]) == {"host", "port", "password_env"}
    assert len(doc["hosts"]) == 2
    keys = {"name", "address", "ssh_user", "repo_path", "python", "cache_dir", "max_workers", "gpus"}
    for h in doc["hosts"]:
        assert set(h) == keys
        for g in h["gpus"]:
            assert set(g) == {"index", "name", "profile"}
    assert {h["name"] for h in doc["hosts"]} == {"laptop", "rtx3060"}
