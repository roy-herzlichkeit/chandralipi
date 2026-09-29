"""Helpers shared by Phase 4 harness tests (import as `from _h4 import ...`). Protected (G05)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "Phase_3" / "harness" / "tests"))
from _h3 import T_TRUE, apply, job_kwargs, write_pair  # noqa: E402,F401


def fake_client():
    import fakeredis

    return fakeredis.FakeRedis(decode_responses=True, version=(7,))


def job(i=0, **over):
    from lunar_reg.distributed.job import JobDescriptor

    return JobDescriptor(**job_kwargs("src.tif", "ref.tif", tile_index=i, **over))
