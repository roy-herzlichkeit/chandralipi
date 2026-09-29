"""P4.01 — Redis client details (Phase_4/LLD/redis_queue.md). Protected (G05)."""

from __future__ import annotations

import tomllib

from _h4 import REPO, fake_client, job


def test_cluster_extra():
    extras = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]["optional-dependencies"]
    names = " ".join(extras["cluster"]).lower()
    assert "redis" in names and "fakeredis" in names


def test_protocol_pinned(monkeypatch):
    import redis

    from lunar_reg.distributed.redis_queue import RedisJobQueue

    seen = {}

    def fake_from_url(url, **kw):
        seen.update(kw)
        return fake_client()

    monkeypatch.setattr(redis.Redis, "from_url", staticmethod(fake_from_url))
    RedisJobQueue("redis://:pw@127.0.0.1:6379/0", "r")
    assert seen.get("protocol") == 2 and seen.get("decode_responses") is True


def test_two_element_autoclaim_reply(monkeypatch):
    from lunar_reg.distributed.redis_queue import RedisJobQueue

    client = fake_client()
    q = RedisJobQueue("redis://unused", "r2", client=client)
    q.put(job(0))
    lease = q.claim("w", 0.0)
    real = client.xautoclaim

    def two(*a, **k):
        reply = real(*a, **k)
        return reply[:2]

    monkeypatch.setattr(client, "xautoclaim", two)
    assert q.reclaim_expired(lease_s=0.0) == [lease.job.job_id]


def test_base_install_does_not_import_redis():
    import subprocess
    import sys

    out = subprocess.run([sys.executable, "-c", "import sys, lunar_reg.distributed.queue, "
                          "lunar_reg.pipeline; print('redis' in sys.modules)"], cwd=REPO,
                         capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "False"
