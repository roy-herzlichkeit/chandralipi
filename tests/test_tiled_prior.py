"""Prior-rectified tiling and classified tile outcomes (C18, Phase_2/LLD/tiling.md §P2.06)."""

from __future__ import annotations

import sys

import cv2
import numpy as np
import pytest

from lunar_reg.eval.scenes import add_craters, fractal_terrain, hillshade
from lunar_reg.match.base import MatchResult
from lunar_reg.match.classical import ClassicalMatcher
from lunar_reg.match.tiled import TileDiagnostics, TiledMatcher, TileOutcome, TileStatus


def _terrain(shape=(1024, 1024), seed=3) -> np.ndarray:
    heights = add_craters(
        fractal_terrain(shape, seed=seed), n=int(45 * shape[0] * shape[1] / 512**2), seed=seed
    )
    return np.maximum(hillshade(heights, azimuth_deg=315, elevation_deg=35), 1).astype(np.uint8)


def _similarity(scale: float, angle_deg: float, tx: float, ty: float) -> np.ndarray:
    a = np.radians(angle_deg)
    c, s = scale * np.cos(a), scale * np.sin(a)
    return np.array([[c, -s, tx], [s, c, ty], [0.0, 0.0, 1.0]])


def _apply(h: np.ndarray, pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, float)
    hom = np.c_[pts, np.ones(len(pts))] @ h.T
    return hom[:, :2] / hom[:, 2:3]


class _Points:
    """Stub matcher returning the same three tile-local points on both sides."""

    name = "points"

    def __init__(self, fail_on: dict[int, BaseException | str] | None = None):
        self.fail_on = fail_on or {}
        self.calls = 0
        self.shapes: list[tuple[tuple[int, ...], tuple[int, ...]]] = []

    def match(self, source, reference):
        self.calls += 1
        self.shapes.append((source.shape, reference.shape))
        action = self.fail_on.get(self.calls)
        if isinstance(action, BaseException):
            raise action
        if action == "empty":
            return MatchResult.empty(self.name)
        pts = np.array([[10.0, 10.0], [20.0, 30.0], [40.0, 12.0]])
        return MatchResult(pts, pts + 32.0, matcher=self.name)


@pytest.fixture(scope="module")
def scene():
    return _terrain((1024, 1024))


# ------------------------------------------------------------------ recovery


def test_scaled_rotated_prior_recovers_transform(scene):
    """Reference = source x0.25, rotated 20 deg; prior off by 3 px -> < 0.5 reference px."""
    truth = _similarity(0.25, 20.0, 120.0, 20.0)
    ref = cv2.warpAffine(scene, truth[:2], (400, 400), flags=cv2.INTER_AREA)
    prior = truth.copy()
    prior[0, 2] += 3.0

    tm = TiledMatcher(ClassicalMatcher("sift"), tile_px=256, progress=False)
    res = tm.match_arrays(scene, ref, prior=prior)

    assert len(res) >= 30
    fit, inliers = cv2.estimateAffinePartial2D(
        res.src_pts, res.dst_pts, method=cv2.RANSAC, ransacReprojThreshold=1.0
    )
    assert fit is not None and inliers.sum() >= 20
    probe = np.array([[x, y] for x in (128.0, 512.0, 896.0) for y in (128.0, 512.0, 896.0)])
    est = probe @ fit[:, :2].T + fit[:, 2]
    err = np.linalg.norm(est - _apply(truth, probe), axis=1)
    assert err.max() < 0.5, err
    assert tm.last_diagnostics.counts.get("ok", 0) >= 1
    assert tm.last_diagnostics.n_failed == 0


def test_lift_applies_the_rectifier_projectively():
    """A stub's patch-local dst points come back through T_t into reference px."""
    src = np.full((256, 256), 100, np.uint8)
    ref = np.full((300, 300), 100, np.uint8)
    prior = _similarity(0.5, 30.0, 150.0, 10.0)
    tm = TiledMatcher(
        _Points(), tile_px=256, overlap=0.0, progress=False, deduplicate_overlaps=False
    )
    res = tm.match_arrays(src, ref, prior=prior)
    # Stub: src (x, y) -> patch (x + 32, y + 32), i.e. the margin offset, so the
    # lifted dst must equal prior(src) exactly.
    np.testing.assert_allclose(res.dst_pts, _apply(prior, res.src_pts), atol=1e-9)
    assert tm.matcher.shapes == [((256, 256), (320, 320))]


# ------------------------------------------------------------------ outcomes


def test_error_and_empty_tiles_are_counted(scene):
    img = scene[:512, :512]
    stub = _Points(fail_on={2: RuntimeError("tile broke"), 3: "empty"})
    tm = TiledMatcher(stub, tile_px=256, overlap=0.0, progress=False)
    res = tm.match_arrays(img, img)
    n = 4
    diag = tm.last_diagnostics
    assert diag.counts == {"ok": n - 2, "matcher_error": 1, "empty": 1}
    assert diag.n_failed == 1
    assert diag.samples["matcher_error"].detail == "RuntimeError: tile broke"
    assert diag.samples["matcher_error"].index == 1
    assert len(res) == 3 * (n - 2)
    report = diag.report()
    assert "matcher_error: 1" in report and "empty: 1" in report and "found nothing" in report


def test_oom_tile_is_classified_and_cache_emptied(scene, monkeypatch):
    torch = pytest.importorskip("torch")
    emptied = []
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: emptied.append(1))
    stub = _Points(fail_on={1: torch.OutOfMemoryError("CUDA out of memory. Tried 2 GiB\nmore")})
    tm = TiledMatcher(stub, tile_px=256, overlap=0.0, progress=False)
    tm.match_arrays(scene[:256, :512], scene[:256, :512])
    assert tm.last_diagnostics.counts == {"oom": 1, "ok": 1}
    assert tm.last_diagnostics.samples["oom"].detail == "CUDA out of memory. Tried 2 GiB"
    assert emptied == [1]


def test_oom_from_lazily_imported_torch_is_classified(scene, monkeypatch):
    """A matcher that imports torch inside match() still gets OOM on its first tile."""
    torch = pytest.importorskip("torch")
    emptied = []
    monkeypatch.setattr(torch.cuda, "empty_cache", lambda: emptied.append(1))
    monkeypatch.delitem(sys.modules, "torch")  # restored by monkeypatch afterwards

    class LazyTorch(_Points):
        def match(self, source, reference):
            if self.calls == 0:
                self.calls += 1
                sys.modules["torch"] = torch  # what `import torch` does on first use
                raise torch.OutOfMemoryError("CUDA out of memory. Tried 2 GiB")
            return super().match(source, reference)

    tm = TiledMatcher(LazyTorch(), tile_px=256, overlap=0.0, progress=False)
    assert "torch" not in sys.modules
    tm.match_arrays(scene[:256, :512], scene[:256, :512])
    assert tm.last_diagnostics.counts == {"oom": 1, "ok": 1}
    assert tm.last_diagnostics.samples["oom"].index == 0
    assert emptied == [1]


def test_reference_taller_than_shrt_max_is_windowed():
    """cv2.remap rejects sides >= 32767 px; match_arrays must only warp a window."""
    src = np.full((256, 256), 100, np.uint8)
    ref = np.full((33000, 256), 100, np.uint8)
    stub = _Points()
    tm = TiledMatcher(stub, tile_px=256, overlap=0.0, progress=False)
    res = tm.match_arrays(src, ref, offset_prior=(32700, 0))
    assert tm.last_diagnostics.counts == {"ok": 1}
    assert stub.shapes == [((256, 256), (320, 320))]
    np.testing.assert_allclose(res.dst_pts, res.src_pts + (0.0, 32700.0), atol=1e-9)


def test_nodata_source_tiles_are_skipped(scene):
    img = scene[:512, :512]
    src = img.copy()
    src[256:, :] = 0
    tm = TiledMatcher(ClassicalMatcher("sift"), tile_px=256, overlap=0.0, progress=False)
    tm.match_arrays(src, img)
    assert tm.last_diagnostics.counts == {"ok": 2, "skipped_nodata": 2}
    assert "source valid" in tm.last_diagnostics.samples["skipped_nodata"].detail


def test_reference_valid_mask_skips_tiles(scene):
    img = scene[:512, :512]
    ref_valid = np.ones(img.shape, bool)
    ref_valid[:, :256] = False
    stub = _Points()
    tm = TiledMatcher(stub, tile_px=256, overlap=0.0, progress=False)
    tm.match_arrays(img, img, reference_valid=ref_valid)
    c = tm.last_diagnostics.counts
    assert c == {"ok": 2, "skipped_nodata": 2}
    assert stub.calls == 2


def test_source_valid_mask_overrides_default(scene):
    img = scene[:256, :256]
    valid = np.zeros(img.shape, bool)
    tm = TiledMatcher(_Points(), tile_px=256, progress=False)
    tm.match_arrays(img, img, source_valid=valid)
    assert tm.last_diagnostics.counts == {"skipped_nodata": 1}


def test_out_of_reference_tiles(scene):
    img = scene[:256, :512]
    tm = TiledMatcher(_Points(), tile_px=256, overlap=0.0, progress=False)
    tm.match_arrays(img, img[:, :256], offset_prior=(0, -300))
    diag = tm.last_diagnostics
    assert diag.counts.get("out_of_reference") == 1
    oor = diag.samples["out_of_reference"]
    assert oor.reference_window is None and oor.source_window == (0, 0, 256, 256)
    assert "data gap" in diag.report()


def test_offset_prior_matches_translation_prior(scene):
    img = scene[:512, :512]
    ref = np.zeros((560, 560), np.uint8)
    ref[20:532, 30:542] = img
    tm = TiledMatcher(ClassicalMatcher("sift"), tile_px=256, progress=False)
    a = tm.match_arrays(img, ref, offset_prior=(20, 30))
    counts_a = tm.last_diagnostics.counts
    b = tm.match_arrays(img, ref, prior=np.array([[1.0, 0, 30], [0, 1.0, 20], [0, 0, 1.0]]))
    assert len(a) == len(b) > 20
    np.testing.assert_array_equal(a.src_pts, b.src_pts)
    np.testing.assert_array_equal(a.dst_pts, b.dst_pts)
    assert counts_a == tm.last_diagnostics.counts
    assert np.median(np.abs(a.dst_pts - a.src_pts - (30, 20))) < 0.5


def test_prior_and_offset_prior_together_is_an_error(scene):
    tm = TiledMatcher(_Points(), tile_px=256, progress=False)
    with pytest.raises(ValueError):
        tm.match_arrays(scene, scene, prior=np.eye(3), offset_prior=(0, 0))


def test_reference_window_is_prior_bbox_plus_margin():
    src = np.full((256, 256), 50, np.uint8)
    ref = np.full((1000, 1000), 50, np.uint8)
    tm = TiledMatcher(_Points(), tile_px=256, progress=False, ref_margin_px=32)
    tm.match_arrays(src, ref, prior=np.array([[2.0, 0, 100], [0, 2.0, 40], [0, 0, 1]]))
    (outcome,) = tm.last_diagnostics.outcomes
    # corners (0..256) * 2 + offset -> cols 100..612, rows 40..552; +-32, clipped.
    assert outcome.reference_window == (8, 68, 576, 576)


def test_default_tile_px_leaves_room_for_margins():
    class Limited(_Points):
        max_tile_px = 640

    assert TiledMatcher(Limited(), ref_margin_px=32).tile_px == 576
    assert TiledMatcher(_Points()).tile_px == 640
    assert TiledMatcher(Limited(), tile_px=300).tile_px == 300


def test_diagnostics_report_lists_every_status():
    d = TileDiagnostics(outcomes=[])
    d.record(TileOutcome(0, TileStatus.OK, 5, "", (0, 0, 8, 8), (0, 0, 8, 8)))
    d.record(TileOutcome(1, TileStatus.SKIPPED_NODATA, 0, "source valid 0.10", (0, 8, 8, 8), None))
    d.record(TileOutcome(2, TileStatus.SKIPPED_NODATA, 0, "source valid 0.20", (8, 0, 8, 8), None))
    assert d.counts == {"ok": 1, "skipped_nodata": 2}
    assert d.samples["skipped_nodata"].index == 1
    assert d.n_failed == 0
    lines = d.report().splitlines()
    assert lines[0].startswith("tiles: 3 total, 1 ok, 0 failed")
    assert lines[2].startswith("  skipped_nodata: 2") and "tile 1: source valid 0.10" in lines[2]


# ------------------------------------------------------------- windowed path


def _write_tif(path, array, nodata=None):
    rasterio = pytest.importorskip("rasterio")
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype=array.dtype,
        nodata=nodata,
    ) as dst:
        dst.write(array, 1)


@pytest.mark.parametrize("scale", [0.6, 1.7])
def test_match_datasets_equals_match_arrays(tmp_path, scene, scale):
    rasterio = pytest.importorskip("rasterio")
    src = scene[:512, :512]
    truth = _similarity(scale, 12.0, 60.0, 30.0)
    size = int(np.ceil(512 * scale * 1.4)) + 80
    ref = cv2.warpAffine(src, truth[:2], (size, size), flags=cv2.INTER_LINEAR)
    _write_tif(tmp_path / "src.tif", src)
    _write_tif(tmp_path / "ref.tif", ref)

    prior = truth.copy()
    prior[1, 2] += 2.0
    tm = TiledMatcher(ClassicalMatcher("sift"), tile_px=256, progress=False)
    from_arrays = tm.match_arrays(src, ref, prior=prior)
    counts_arrays = tm.last_diagnostics.counts
    with rasterio.open(tmp_path / "src.tif") as s, rasterio.open(tmp_path / "ref.tif") as r:
        from_sets = tm.match_datasets(s, r, prior=prior)
    assert counts_arrays == tm.last_diagnostics.counts
    assert len(from_sets) == len(from_arrays) > 20
    np.testing.assert_allclose(from_sets.src_pts, from_arrays.src_pts)
    np.testing.assert_allclose(from_sets.dst_pts, from_arrays.dst_pts, atol=1e-6)


def test_match_datasets_honours_nodata(tmp_path, scene):
    rasterio = pytest.importorskip("rasterio")
    src = scene[:512, :512].copy()
    src[:, 256:] = 7
    _write_tif(tmp_path / "src.tif", src, nodata=7)
    _write_tif(tmp_path / "ref.tif", scene[:512, :512])
    tm = TiledMatcher(_Points(), tile_px=256, overlap=0.0, progress=False)
    with rasterio.open(tmp_path / "src.tif") as s, rasterio.open(tmp_path / "ref.tif") as r:
        tm.match_datasets(s, r)
    assert tm.last_diagnostics.counts == {"ok": 2, "skipped_nodata": 2}
