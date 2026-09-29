# LLD — native-GSD refinement (P2.08) and georeferenced blockwise warp (P2.09)

Produces: C19. Closes: A083 (align-6), A130 (align-9). Decision: G10. TBD 1.8 step 6.

## P2.08 — `align/native.py` (new, C19)
`lift_to_native(coarse, source_to_native, reference_to_native) = reference_to_native @ coarse @ inv(source_to_native)` (all 3×3; a 2×3 `coarse` is promoted with `[0, 0, 1]`).
`refine_native_arrays(source_native, reference_native, prior_native, *, source_native_gsd_m, reference_native_gsd_m, matcher="sift", tile_px=None, model="homography", coarse_gsd_m=4.0, max_drift_coarse_px=1.0, seed=0)`:
1. `f = reference_native_gsd_m / source_native_gsd_m` (4 for OHRC→NAC). Resample the source to the reference GSD: `src_r = cv2.resize(source_native, (round(w/f), round(h/f)), INTER_AREA)`; `S` = inverse of the CONTRACTS C11 pixel-centre `to_native` matrix for this resize with zero offset (native → resampled), using the actual size ratios `fx = w / src_r.shape[1]`, `fy = h / src_r.shape[0]`.
2. Prior at matching scale: `P = prior_native @ inv(S)`.
3. `TiledMatcher(build_matcher(matcher), tile_px=tile_px or 512, progress=False).match_arrays(src_r, reference_native, prior=P)`; diagnostics kept.
4. Fewer than 8 matches → `TOO_FEW_MATCHES`; `estimate_transform(..., model, threshold_px=3.0, seed=seed)` then `reestimate_on_inliers(..., threshold_px=1.0, seed=seed)`; `ValueError` → `ESTIMATION_FAILED`.
5. `T_native = T_fit @ S` (source-native px → reference-native px).
6. Drift: probes = 5×5 grid over the source window in native px; `drift_coarse_px = max ‖T_native(p) − prior_native(p)‖ · reference_native_gsd_m / coarse_gsd_m`; `> max_drift_coarse_px` → `DRIFT_EXCEEDED` (transform still returned for inspection).
7. More than 50 % of tiles failed (`tiles.n_failed / total > 0.5`) → `TILE_FAILURES`.
8. Otherwise `OK`.
Tests (`tests/test_native.py`): `lift_to_native` round trip against explicit composition; a synthetic 2048² "native source" at 0.25 m and a 512² reference at 1 m related by a known homography, prior = truth + 0.5 coarse px error → `OK`, native transform error < 0.5 reference px at the probes, `drift_coarse_px < 1`; a prior 3 coarse px off with `max_drift_coarse_px=1` still converging → status reflects the drift rule.

## P2.09 — `align/warp.py`
- `warp_blockwise(src_dataset, transform, output_path, output_shape, *, dst_transform, dst_crs, nodata=0, block_px=DEFAULT_BLOCK_PX, profile_overrides=None)`: output profile built from scratch (driver GTiff, `crs=dst_crs`, `transform=dst_transform`, `nodata`, `dtype` of the source, `count=1`, tiled 512, deflate) — nothing copied from the source profile (A083). A validity mask (source valid = `!= src nodata` or all ones) is warped with `INTER_NEAREST` per block; output pixels whose mask is 0 are set to `nodata`.
- `save_registered_geotiff(...)`: warps a validity mask alongside the image (`INTER_NEAREST`); `valid_fraction` = mean of the warped mask (not `warped > 0`); the mask is written into the GeoTIFF with `dataset.write_mask(mask_uint8)`; the profile keeps `nodata=0` for viewers that ignore masks.
Tests (`tests/test_warp_georef.py`): `warp_blockwise` output's transform/crs equal the requested ones (not the source's); identity warp of a small GeoTIFF reproduces the source inside the valid mask; a source with real zeros inside the valid area gives `valid_fraction` = 1.0 (mask-based) where the old rule gave < 1.
