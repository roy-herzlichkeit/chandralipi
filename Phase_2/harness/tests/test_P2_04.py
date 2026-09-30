"""P2.04 — measured RTX 4060 profile artefact. Protected (G05)."""

from __future__ import annotations

import json

import pytest
from _h2 import PROFILE, REPO

pytestmark = [pytest.mark.data, pytest.mark.gpu]


def test_profile_measured():
    from lunar_reg.device import DeviceProfile
    from lunar_reg.provenance import ValueSource

    doc = json.loads(PROFILE.read_text())
    assert doc["source"] == "measured" and "4060" in doc["device_name"]
    prof = DeviceProfile.load(PROFILE)
    assert prof.source is ValueSource.MEASURED
    for matcher, precision in (("loftr", "fp16"), ("loftr", "fp32"), ("lightglue", "fp16"),
                               ("lightglue", "fp32")):
        entry = doc["matchers"][matcher][precision]
        assert len(entry["points"]) >= 3 and entry["max_tile_px"] > 0
    rr = REPO / doc["run_record"]
    from lunar_reg.runrecord import validate_run_record

    assert rr.exists() and validate_run_record(rr) == []
