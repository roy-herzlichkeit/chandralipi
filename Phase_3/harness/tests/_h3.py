"""Helpers shared by Phase 3 harness tests (import as `from _h3 import ...`). Protected (G05)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
# Windows sit at non-zero offsets inside larger rasters so a double-applied offset cannot
# cancel out (review RC13, G37). Order: (row_off, col_off, height, width), native px.
SRC_SHAPE = (1536, 1280)
SRC_WIN = (512, 256, 1024, 1024)
REF_SHAPE = (400, 380)
REF_WIN = (40, 30, 320, 320)
# truth: full-raster source-native px (0.25 m) -> full-raster reference-native px (1 m)
# col: 0.25*(c-256) - 0.375 + 20 + 30 ; row: 0.25*(r-512) - 0.375 + 30 + 40
T_TRUE = np.array([[0.25, 0.0, -14.375], [0.0, 0.25, -58.375], [0.0, 0.0, 1.0]])


def terrain(shape=(1024, 1024), seed=3) -> np.ndarray:
    from lunar_reg.eval.scenes import add_craters, fractal_terrain, hillshade

    h = add_craters(fractal_terrain(shape, seed=seed), n=int(45 * shape[0] * shape[1] / 512**2),
                    seed=seed)
    return np.maximum(hillshade(h, azimuth_deg=315, elevation_deg=35), 1).astype(np.uint8)


def write_pair(tmp: Path, seed: int = 3):
    """Source GeoTIFF (native 0.25 m, SRC_SHAPE) and reference GeoTIFF (1 m, REF_SHAPE) related by
    T_TRUE; the textured content fills SRC_WIN and sits inside REF_WIN."""
    import cv2
    import rasterio

    tex = terrain((1024, 1024), seed)
    at_1m = cv2.resize(tex, (256, 256), interpolation=cv2.INTER_AREA)
    src = np.zeros(SRC_SHAPE, np.uint8)
    src[512:1536, 256:1280] = tex
    ref = np.zeros(REF_SHAPE, np.uint8)
    ref[40 + 30:40 + 286, 30 + 20:30 + 276] = at_1m
    paths = {}
    for name, arr in (("src.tif", src), ("ref.tif", ref)):
        p = tmp / name
        with rasterio.open(p, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0],
                           count=1, dtype="uint8") as ds:
            ds.write(arr, 1)
        paths[name] = p
    return paths["src.tif"], paths["ref.tif"]


def job_kwargs(src_rel: str, ref_rel: str, **over):
    base = dict(run_id="r1", pair_id="p1", tile_index=0, source_path=src_rel,
                reference_path=ref_rel, source_window=SRC_WIN,
                reference_window=REF_WIN,
                prior=tuple(float(v) for v in np.array([[1.0, 0, 20.0], [0, 1.0, 30.0],
                                                         [0, 0, 1.0]]).ravel()),
                working_gsd_m=1.0, source_native_gsd_m=0.25, reference_native_gsd_m=1.0,
                preprocess="none", matcher="sift", precision="fp32", tile_px=256,
                est_vram_bytes=0, base_seed=0, reference_georef=None)
    base.update(over)
    return base


def apply(H, pts):
    pts = np.asarray(pts, float)
    h = np.c_[pts, np.ones(len(pts))] @ np.asarray(H).T
    return h[:, :2] / h[:, 2:3]
