"""P4.03 — capacity tiers (Phase_4/LLD/cache_scheduler.md §P4.03). Protected (G05)."""

from __future__ import annotations

from _h4 import job

GiB = 2**30


def _fleet():
    from lunar_reg.distributed.scheduler import WorkerCapacity

    return [WorkerCapacity("laptop-gpu0", "laptop", "cuda:0", int(7.4 * GiB), "rtx4060-laptop"),
            WorkerCapacity("rtx3060-gpu0", "rtx3060", "cuda:0", int(5.5 * GiB), "rtx3060")]


def test_tiers_and_assignment():
    from lunar_reg.distributed.scheduler import assign, capacity_tiers, tier_for, tiers_for_worker

    tiers = capacity_tiers(_fleet())
    assert [t.name for t in tiers] == ["t0", "t1"] and tiers[0].max_bytes < tiers[1].max_bytes
    big = job(0, est_vram_bytes=5 * GiB)
    small = job(1, est_vram_bytes=1 * GiB)
    huge = job(2, est_vram_bytes=9 * GiB)
    assert tier_for(big, tiers).name == "t1" and tier_for(small, tiers).name == "t0"
    assert tier_for(huge, tiers) is None
    a = assign([big, small, huge], tiers)
    assert a.unschedulable == [huge.job_id] and big.job_id in a.by_tier["t1"]
    assert tiers_for_worker(_fleet()[1], tiers) == ["t0"]
    assert tiers_for_worker(_fleet()[0], tiers) == ["t1", "t0"]
    assert "unschedulable" in a.report()
