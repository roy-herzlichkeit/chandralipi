"""Helpers shared by Phase 3 harness tests (import as `from _h3 import ...`). Protected (G05)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
# truth: source-native px (0.25 m) -> reference-native px (1 m)
T_TRUE = np.array([[0.25, 0.0, 20.0 - 0.375], [0.0, 0.25, 30.0 - 0.375], [0.0, 0.0, 1.0]])


def terrain(shape=(1024, 1024), seed=3) -> np.ndarray:
    from lunar_reg.eval.scenes import add_craters, fractal_terrain, hillshade

    h = add_craters(fractal_terrain(shape, seed=seed), n=int(45 * shape[0] * shape[1] / 512**2),
                    seed=seed)
    return np.maximum(hillshade(h, azimuth_deg=315, elevation_deg=35), 1).astype(np.uint8)


def write_pair(tmp: Path, seed: int = 3):
    """Source GeoTIFF (native 0.25 m, 1024^2) and reference GeoTIFF (1 m, 320^2) related by T_TRUE."""
    import cv2
    import rasterio

    src = terrain((1024, 1024), seed)
    at_1m = cv2.resize(src, (256, 256), interpolation=cv2.INTER_AREA)
    ref = np.zeros((320, 320), np.uint8)
    ref[30:286, 20:276] = at_1m
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
                reference_path=ref_rel, source_window=(0, 0, 1024, 1024),
                reference_window=(0, 0, 320, 320),
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
