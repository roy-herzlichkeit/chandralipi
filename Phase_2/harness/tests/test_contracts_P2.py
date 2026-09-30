"""Phase 2 contract tests: C03 (device, precision), C16, C17, C18, C19 (G16). Protected (G05)."""

from __future__ import annotations

import dataclasses
import inspect
import json

import numpy as np
import pytest
from _h2 import apply, cuda_available, similarity, terrain


def test_C03_device_fields():
    from lunar_reg.pipeline import PipelineConfig

    f = {x.name: x.default for x in dataclasses.fields(PipelineConfig)}
    assert f["device"] is None and f["precision"] == "auto"


# --------------------------------------------------------------------- C17


def test_C17_cpu_reading():
    from lunar_reg.device import MemoryReading, free_memory_bytes, free_vram_bytes
    from lunar_reg.provenance import ValueSource

    r = free_memory_bytes("cpu")
    assert isinstance(r, MemoryReading)
    assert [f.name for f in dataclasses.fields(MemoryReading)] == [
        "device", "free_bytes", "total_bytes", "source"]
    assert r.source is ValueSource.MEASURED and 0 < r.free_bytes <= r.total_bytes
    assert r.total_bytes != 8 * 1024**3
    assert free_vram_bytes("cpu") == free_memory_bytes("cpu").free_bytes or \
        abs(free_vram_bytes("cpu") - r.free_bytes) < 512 * 1024**2


def test_C17_failure_is_unknown(monkeypatch):
    from lunar_reg.device import free_memory_bytes
    from lunar_reg.provenance import ValueSource

    r = free_memory_bytes("cuda:7")  # no such device on this host
    if r.source is ValueSource.UNKNOWN:
        assert r.free_bytes == 0 and r.total_bytes == 0
    else:
        pytest.skip("a cuda:7 device exists on this host")


@pytest.mark.gpu
def test_C17_cuda_index():
    if not cuda_available():
        pytest.skip("CUDA not available")
    import torch

    from lunar_reg.device import free_memory_bytes
    from lunar_reg.provenance import ValueSource

    r = free_memory_bytes("cuda:0")
    free, total = torch.cuda.mem_get_info(0)
    assert r.source is ValueSource.MEASURED and r.total_bytes == total
    assert abs(r.free_bytes - free) < 256 * 1024**2


# --------------------------------------------------------------------- C16


def _profile_dict():
    return {"schema": 1, "slug": "test-gpu", "device_name": "Test GPU", "total_bytes": 8 * 2**30,
            "free_bytes_at_measure": 7 * 2**30, "torch": "x", "cuda": "y", "driver": "z",
            "measured_utc": "2026-09-29T00:00:00Z", "run_record": "r.json", "source": "measured",
            "matchers": {"loftr": {"fp16": {"fixed_bytes": 500e6, "bytes_per_px": 2000.0,
                                            "max_tile_px": 1344,
                                            "points": [[256, 631e6], [512, 1024e6],
                                                       [768, 1680e6]]}}}}


def test_C16_roundtrip(tmp_path):
    from lunar_reg.device import DeviceProfile, load_profile_for
    from lunar_reg.provenance import ValueSource

    path = tmp_path / "test-gpu.json"
    path.write_text(json.dumps(_profile_dict()))
    prof = DeviceProfile.load(path)
    assert prof.slug == "test-gpu" and prof.source is ValueSource.MEASURED
    out = prof.save(tmp_path / "copy.json")
    assert json.loads(out.read_text())["matchers"] == _profile_dict()["matchers"]
    assert load_profile_for("Test GPU", root=tmp_path).slug == "test-gpu"
    assert load_profile_for("Other GPU", root=tmp_path) is None


def test_C16_plan_tile_fits_flag(tmp_path):
    from lunar_reg.device import DeviceProfile
    from lunar_reg.provenance import ValueSource

    path = tmp_path / "p.json"
    path.write_text(json.dumps(_profile_dict()))
    prof = DeviceProfile.load(path)
    big = prof.plan_tile("loftr", "fp16", free_bytes=7 * 2**30)
    assert big.fits and big.source is ValueSource.MEASURED and big.tile_px % 64 == 0
    assert 500e6 + 2000.0 * big.tile_px**2 <= 0.75 * 7 * 2**30
    tiny = prof.plan_tile("loftr", "fp16", free_bytes=100 * 2**20)
    assert tiny.fits is False
    other = prof.plan_tile("lightglue", "fp32", free_bytes=7 * 2**30)   # not in the profile
    assert other.source is ValueSource.INFERRED                           # review RC23: no KeyError


# --------------------------------------------------------------------- C18


def test_C18_members():
    from lunar_reg.match.tiled import TiledMatcher, TileDiagnostics, TileOutcome, TileStatus

    assert {m.value for m in TileStatus} == {"ok", "empty", "out_of_reference", "skipped_nodata",
                                             "matcher_error", "oom"}
    assert [f.name for f in dataclasses.fields(TileOutcome)] == [
        "index", "status", "n_matches", "detail", "source_window", "reference_window"]
    params = inspect.signature(TiledMatcher.match_arrays).parameters
    assert list(params)[1:] == ["source", "reference", "prior", "source_valid",
                                "reference_valid", "offset_prior"]
    init = inspect.signature(TiledMatcher.__init__).parameters
    assert init["min_valid_fraction"].default == 0.5 and init["ref_margin_px"].default == 32
    d = TileDiagnostics(outcomes=[])
    d.record(TileOutcome(0, TileStatus.OK, 5, "", (0, 0, 8, 8), (0, 0, 8, 8)))
    d.record(TileOutcome(1, TileStatus.OOM, 0, "x", (0, 8, 8, 8), None))
    assert d.counts == {"ok": 1, "oom": 1} and d.n_failed == 1 and "oom" in d.report()


def test_C18_scaled_prior():
    import cv2

    from lunar_reg.match.classical import ClassicalMatcher
    from lunar_reg.match.tiled import TiledMatcher

    src = terrain((1024, 1024))
    T = similarity(0.8, 15.0, 160.0, 40.0)   # source px -> reference px (scale + rotation)
    ref = cv2.warpAffine(src, T[:2], (1000, 1000), flags=cv2.INTER_AREA)
    prior = T.copy()
    prior[0, 2] += 3.0
    tm = TiledMatcher(ClassicalMatcher("sift"), tile_px=256, progress=False)
    res = tm.match_arrays(src, ref, prior=prior)
    assert len(res) >= 30
    err = np.linalg.norm(apply(T, res.src_pts) - res.dst_pts, axis=1)
    assert np.median(err) < 1.0, np.median(err)
    assert tm.last_diagnostics.counts.get("ok", 0) >= 1


def test_C18_error_tile_counted():
    from lunar_reg.match.base import MatchResult
    from lunar_reg.match.tiled import TiledMatcher

    class Flaky:
        name = "flaky"

        def __init__(self):
            self.calls = 0

        def match(self, s, r):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("tile broke")
            if self.calls == 3:
                return MatchResult.empty("flaky")
            pts = np.array([[10.0, 10.0], [20.0, 30.0], [40.0, 12.0]])
            return MatchResult(pts, pts, matcher="flaky")

    img = terrain((512, 512))
    tm = TiledMatcher(Flaky(), tile_px=256, overlap=0.0, progress=False)
    tm.match_arrays(img, img)
    c = tm.last_diagnostics.counts
    assert c.get("matcher_error") == 1 and c.get("empty") == 1 and sum(c.values()) == 4


# --------------------------------------------------------------------- C19


def test_C19_lift_roundtrip():
    from lunar_reg.align.native import lift_to_native

    coarse = similarity(1.0, 2.0, 5.0, -3.0)
    s2n = np.array([[16.0, 0, 100.0], [0, 16.0, 200.0], [0, 0, 1.0]])
    r2n = np.array([[4.0, 0, 30.0], [0, 4.0, 40.0], [0, 0, 1.0]])
    lifted = lift_to_native(coarse, s2n, r2n)
    p = np.array([[123.0, 456.0]])
    expect = apply(r2n, apply(coarse, apply(np.linalg.inv(s2n), p)))
    np.testing.assert_allclose(apply(lifted, p), expect, atol=1e-9)
    np.testing.assert_allclose(lift_to_native(coarse[:2], s2n, r2n), lifted, atol=1e-12)


def test_C19_synthetic_refine():
    import cv2

    from lunar_reg.align.native import NativeStatus, refine_native_arrays

    src = terrain((2048, 2048), seed=5)                            # 0.25 m "native source"
    at_1m = cv2.resize(src, (512, 512), interpolation=cv2.INTER_AREA)
    # native -> 1 m, pixel-centre convention (CONTRACTS C11): x1 = (xn + 0.5) / 4 - 0.5
    R = np.array([[0.25, 0.0, -0.375], [0.0, 0.25, -0.375], [0.0, 0.0, 1.0]])
    A = similarity(1.0, 1.5, 40.0, 25.0)                            # 1 m -> reference px
    ref = cv2.warpAffine(at_1m, A[:2], (600, 600), flags=cv2.INTER_LINEAR)
    T = A @ R                                                       # truth: native src -> ref px
    prior = T.copy()
    prior[0, 2] += 2.0                                              # 2 ref px = 0.5 coarse (4 m) px
    out = refine_native_arrays(src, ref, prior, source_native_gsd_m=0.25,
                               reference_native_gsd_m=1.0, matcher="sift", tile_px=256)
    assert out.status is NativeStatus.OK, out.detail
    probes = np.array([[200.0, 200.0], [1800.0, 200.0], [200.0, 1800.0], [1800.0, 1800.0]])
    assert np.abs(apply(out.transform, probes) - apply(T, probes)).max() < 0.5
    assert out.drift_coarse_px < 1.0
