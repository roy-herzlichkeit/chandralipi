"""Device profiles (CONTRACTS C16, Phase_2/LLD/device.md §P2.02).

All profiles here are SYNTHETIC test fixtures written to ``tmp_path``; no real
profile is created (P2.04 measures it).
"""

from __future__ import annotations

import json

import pytest

from lunar_reg import device
from lunar_reg.device import (
    MAX_DENSE_TILE_PX,
    MIN_DENSE_TILE_PX,
    DeviceProfile,
    TileBudget,
    load_profile_for,
)
from lunar_reg.provenance import ValueSource

GIB = 2**30
MIB = 2**20


def _profile_dict(**overrides) -> dict:
    d = {
        "schema": 1,
        "slug": "synthetic-gpu",
        "device_name": "Synthetic GPU",
        "total_bytes": 8 * GIB,
        "free_bytes_at_measure": 7 * GIB,
        "torch": "t",
        "cuda": "c",
        "driver": "d",
        "measured_utc": "2026-10-01T00:00:00Z",
        "run_record": "run_record.json",
        "source": "measured",
        "matchers": {
            "loftr": {
                "fp16": {
                    "fixed_bytes": 400_000_000,
                    "bytes_per_px": 1500.0,
                    "max_tile_px": 1024,
                    "points": [[256, 498_304_000], [512, 793_216_000], [768, 1_284_736_000]],
                }
            }
        },
    }
    d.update(overrides)
    return d


def _write(tmp_path, name="synthetic-gpu.json", **overrides):
    path = tmp_path / name
    path.write_text(json.dumps(_profile_dict(**overrides)))
    return path


def test_roundtrip_keeps_every_key(tmp_path):
    src = _write(tmp_path)
    prof = DeviceProfile.load(src)
    assert prof.slug == "synthetic-gpu" and prof.device_name == "Synthetic GPU"
    assert prof.source is ValueSource.MEASURED and prof.path == src
    out = prof.save(tmp_path / "sub" / "copy.json")
    assert json.loads(out.read_text()) == _profile_dict()
    assert list(json.loads(out.read_text()))[:4] == ["schema", "slug", "device_name", "total_bytes"]
    again = DeviceProfile.load(out)
    assert again.matchers == prof.matchers and again.extra == prof.extra


def test_load_profile_for_matches_device_name(tmp_path):
    _write(tmp_path)
    _write(tmp_path, "other.json", slug="other", device_name="Other GPU")
    assert load_profile_for("Synthetic GPU", root=tmp_path).slug == "synthetic-gpu"
    assert load_profile_for("Other GPU", root=str(tmp_path)).slug == "other"
    assert load_profile_for("Absent GPU", root=tmp_path) is None
    assert load_profile_for("Synthetic GPU", root=tmp_path / "missing") is None


def test_load_profile_for_duplicate_prefers_slug_file(tmp_path, caplog):
    _write(tmp_path)  # synthetic-gpu.json, slug synthetic-gpu (canonical)
    _write(tmp_path, "a-copy.json", slug="a-copy-elsewhere")  # sorts first, stem != slug
    with caplog.at_level("WARNING", logger="lunar_reg.device"):
        prof = load_profile_for("Synthetic GPU", root=tmp_path)
    assert prof.slug == "synthetic-gpu"
    assert "2 device profiles" in caplog.text


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"schema": 2}, "schema"),
        ({"source": "guessed"}, "unknown source"),
        ({"matchers": {"loftr": {"fp16": {"fixed_bytes": 1}}}}, "bytes_per_px"),
        ({"source": "inferred"}, "must be 'measured'"),
        ({"source": "unknown"}, "must be 'measured'"),
        ({"matchers": {"loftr": {"fp16": {"fixed_bytes": 1, "bytes_per_px": 0.0}}}}, "> 0"),
        ({"matchers": {"loftr": {"fp16": {"fixed_bytes": 1, "bytes_per_px": -5.0}}}}, "> 0"),
        (
            {
                "matchers": {
                    "loftr": {"fp16": {"fixed_bytes": 1, "bytes_per_px": 1.0, "points": [[256]]}}
                }
            },
            "points",
        ),
    ],
)
def test_invalid_profile_raises(tmp_path, overrides, message):
    path = _write(tmp_path, **overrides)
    with pytest.raises(ValueError, match=message):
        DeviceProfile.load(path)
    with pytest.raises(ValueError, match=message):
        load_profile_for("Synthetic GPU", root=tmp_path)


def test_missing_key_raises(tmp_path):
    d = _profile_dict()
    del d["matchers"]
    path = tmp_path / "x.json"
    path.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="missing"):
        DeviceProfile.load(path)


def test_plan_from_synthetic_profile_is_measured(tmp_path):
    prof = DeviceProfile.load(_write(tmp_path))
    free = 3 * GIB
    b = prof.plan_tile("loftr", "fp16", free_bytes=free)
    assert isinstance(b, TileBudget)
    assert b.source is ValueSource.MEASURED and b.fits
    assert b.tile_px % 64 == 0 and MIN_DENSE_TILE_PX <= b.tile_px <= MAX_DENSE_TILE_PX
    budget = 0.75 * free
    assert 400_000_000 + 1500.0 * b.tile_px**2 <= budget
    nxt = b.tile_px + 64
    assert nxt > MAX_DENSE_TILE_PX or 400_000_000 + 1500.0 * nxt**2 > budget
    assert b.est_peak_bytes == int(400_000_000 + 1500.0 * b.tile_px**2)
    assert b.free_bytes == free and b.matcher == "loftr" and b.precision == "fp16"


def test_plan_capped_at_max_dense_tile(tmp_path):
    prof = DeviceProfile.load(_write(tmp_path))
    b = prof.plan_tile("loftr", "fp16", free_bytes=1024 * GIB)
    assert b.tile_px == MAX_DENSE_TILE_PX and b.fits and b.source is ValueSource.MEASURED


def test_plan_dense_tile_uses_profile(tmp_path, monkeypatch):
    prof = DeviceProfile.load(_write(tmp_path))
    monkeypatch.setattr(device, "free_vram_bytes", lambda d="cuda": 3 * GIB)
    b = device.plan_dense_tile("cuda", "fp16", "loftr", profile=prof)
    assert b == prof.plan_tile("loftr", "fp16", 3 * GIB, device.VRAM_SAFETY_FRACTION)
    assert b.source is ValueSource.MEASURED


def test_analytic_fallback_is_inferred(tmp_path, monkeypatch):
    monkeypatch.setattr(device, "free_vram_bytes", lambda d="cuda": 6 * GIB)
    none = device.plan_dense_tile("cuda", "fp16", "loftr", profile=None)
    assert none.source is ValueSource.INFERRED and none.fits
    assert none.est_peak_bytes == device.dense_matcher_peak_bytes(none.tile_px, "fp16")
    prof = DeviceProfile.load(_write(tmp_path))
    lacking = device.plan_dense_tile("cuda", "fp32", "loftr", profile=prof)  # no fp32 entry
    assert lacking.source is ValueSource.INFERRED
    assert lacking == device.plan_dense_tile("cuda", "fp32", "loftr", profile=None)
    other = prof.plan_tile("lightglue", "fp16", free_bytes=6 * GIB)  # no lightglue entry
    assert other.source is ValueSource.INFERRED


def test_fits_false_when_floor_exceeds_budget(tmp_path, monkeypatch):
    prof = DeviceProfile.load(_write(tmp_path))
    tiny = prof.plan_tile("loftr", "fp16", free_bytes=100 * MIB)  # fixed alone > budget
    assert tiny.fits is False and tiny.tile_px == MIN_DENSE_TILE_PX
    assert tiny.source is ValueSource.MEASURED
    assert "DOES NOT FIT" in str(tiny)

    monkeypatch.setattr(device, "free_vram_bytes", lambda d="cuda": 50 * MIB)
    analytic = device.plan_dense_tile("cuda", "fp16", "loftr")
    assert analytic.fits is False and analytic.tile_px == MIN_DENSE_TILE_PX
    assert analytic.est_peak_bytes > 0.75 * 50 * MIB

    monkeypatch.setattr(device, "free_vram_bytes", lambda d="cuda": 0)  # UNKNOWN reading
    assert device.plan_dense_tile("cuda", "fp16", "loftr").fits is False
    assert prof.plan_tile("loftr", "fp16", free_bytes=0).fits is False


def test_tilebudget_defaults():
    b = TileBudget(256, 1, 10, "loftr", "fp16")
    assert b.fits is True and b.source is ValueSource.INFERRED


def test_negative_intercept_never_plans_negative_peak(tmp_path):
    # A least-squares fit of fixed + k*S^2 to LoFTR's own CPU table
    # (device.py comment, S = 256..1024) has a negative intercept; this entry
    # is that shape (synthetic numbers, not a measurement).
    points = [
        [256, 219_000_000],
        [512, 778_000_000],
        [768, 1_756_000_000],
        [896, 2_750_000_000],
        [1024, 4_500_000_000],
    ]
    entry = {
        "fixed_bytes": -315_013_175.8,
        "bytes_per_px": 4181.47,
        "max_tile_px": 1024,
        "points": points,
    }
    prof = DeviceProfile.load(_write(tmp_path, matchers={"loftr": {"fp32": entry}}))
    for free in (0, 100 * MIB):
        b = prof.plan_tile("loftr", "fp32", free_bytes=free)
        assert b.fits is False and b.tile_px == MIN_DENSE_TILE_PX
        assert b.est_peak_bytes >= 219_000_000  # the measured 256-px peak is a lower bound
    big = prof.plan_tile("loftr", "fp32", free_bytes=6 * GIB)
    assert big.fits and big.est_peak_bytes <= 0.75 * 6 * GIB
    measured_below = max(pk for s, pk in points if s <= big.tile_px)
    assert big.est_peak_bytes >= measured_below


def test_plan_source_follows_profile_source():
    prof = DeviceProfile(
        slug="x",
        device_name="X",
        total_bytes=GIB,
        measured_utc="t",
        source=ValueSource.INFERRED,
        matchers={"loftr": {"fp16": {"fixed_bytes": 1, "bytes_per_px": 1.0}}},
    )
    assert prof.plan_tile("loftr", "fp16", free_bytes=GIB).source is ValueSource.INFERRED
