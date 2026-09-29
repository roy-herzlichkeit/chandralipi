"""P3.03 — planner (Phase_3/LLD/planner.md). Protected (G05)."""

from __future__ import annotations

import numpy as np

PRIOR = np.array([[0.25, 0.0, 19.625], [0.0, 0.25, 29.625], [0.0, 0.0, 1.0]])


def _inputs(**over):
    from lunar_reg.distributed.planner import PlanInputs

    base = dict(run_id="r", pair_id="p", source_path="src.tif", reference_path="ref.tif",
                reference_georef={}, source_window=(0, 0, 1024, 1024),
                reference_window=(0, 0, 320, 320), prior_native=tuple(PRIOR.ravel()),
                source_native_gsd_m=0.25, reference_native_gsd_m=1.0)
    base.update(over)
    return PlanInputs(**base)


def test_plan_covers_and_is_stable():
    from lunar_reg.distributed.planner import plan_jobs

    a = plan_jobs(_inputs(), tile_px=128)
    b = plan_jobs(_inputs(), tile_px=128)
    assert [j.job_id for j in a.jobs] == [j.job_id for j in b.jobs]
    assert len({j.job_id for j in a.jobs}) == len(a.jobs) >= 4
    assert a.working_gsd_m == 1.0
    rows = [j.source_window for j in a.jobs]
    assert min(r[0] for r in rows) == 0 and max(r[0] + r[2] for r in rows) >= 1024
    for j in a.jobs:
        P = np.array(j.prior).reshape(3, 3)
        c = P @ np.array([j.tile_px / 2, j.tile_px / 2, 1.0])
        x, y = c[:2] / c[2]
        rr = j.reference_window
        assert 0 <= x <= rr[3] and 0 <= y <= rr[2]


def test_does_not_fit():
    from lunar_reg.distributed.planner import plan_jobs

    rep = plan_jobs(_inputs(matcher="loftr", precision="fp16"), tile_px=512, free_bytes=10 * 2**20)
    assert not rep.jobs and all(reason == "does_not_fit" for _, reason in rep.skipped)
