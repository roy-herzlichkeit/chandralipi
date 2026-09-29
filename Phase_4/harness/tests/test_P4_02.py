"""P4.02 — node cache (Phase_4/LLD/cache_scheduler.md §P4.02). Protected (G05)."""

from __future__ import annotations

import hashlib
import json

from _h4 import T_TRUE, apply, job, write_pair


def _manifest(tmp, src_root, rel, good=True):
    data = (src_root / rel).read_bytes()
    doc = {"schema": 1, "failures": [], "files": [{
        "path": rel, "bytes": len(data),
        "sha256": hashlib.sha256(data if good else b"x").hexdigest(), "source": "LOCAL",
        "url": None, "product_id": "p", "instrument": "DOC", "role": "data",
        "downloaded_utc": "2026-09-29T00:00:00Z", "recorded_by": "manual"}]}
    (tmp / "DOWNLOADS.json").write_text(json.dumps(doc))
    return tmp / "DOWNLOADS.json"


def test_statuses(tmp_path):
    from lunar_reg.distributed.cache import CacheStatus, NodeCache

    src_root = tmp_path / "shared"
    src_root.mkdir()
    write_pair(src_root)
    cache = NodeCache(tmp_path / "cache", src_root, _manifest(tmp_path, src_root, "src.tif"))
    p, s = cache.resolve("src.tif")
    assert s is CacheStatus.COPIED and p.exists()
    assert cache.resolve("src.tif")[1] is CacheStatus.HIT
    assert cache.resolve("nope.tif")[1] is CacheStatus.MISSING
    bad = NodeCache(tmp_path / "cache2", src_root,
                    _manifest(tmp_path, src_root, "src.tif", good=False))
    p, s = bad.resolve("src.tif")
    assert s is CacheStatus.HASH_MISMATCH and p is None
    assert not (tmp_path / "cache2" / "src.tif").exists()


def test_job_through_cache_counts_bytes(tmp_path):
    import numpy as np

    from lunar_reg.distributed.cache import NodeCache
    from lunar_reg.distributed.outcome import JobStatus
    from lunar_reg.distributed.worker import process_job

    src_root = tmp_path / "shared"
    src_root.mkdir()
    write_pair(src_root)
    cache = NodeCache(tmp_path / "cache", src_root, tmp_path / "none.json")
    r = process_job(job(0), "cpu", repo_root=tmp_path, cache=cache)
    assert r.status is JobStatus.OK, r.detail
    assert r.bytes_read == 1024 * 1024 + 320 * 320
    err = np.linalg.norm(apply(T_TRUE, r.src_pts) - r.dst_pts, axis=1)
    assert np.median(err) < 0.5
