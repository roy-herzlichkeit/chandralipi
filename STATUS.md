# STATUS

current: P2.10
phase: 2
state: READY
branch: phase-2
last_done: P2.09
notes:
- P2.09 (src/lunar_reg/align/warp.py): warp_blockwise(src, transform, out, shape, *, dst_transform, dst_crs, nodata=0, block_px, profile_overrides) builds its GTiff profile from scratch (dst crs/transform, nodata, source dtype, tiled 512, deflate); transform may be a Transform or 2x3/3x3 array. Source validity mask (!= src nodata, NaN-aware, or all ones) warped INTER_NEAREST per block; masked pixels / unsupported blocks written as nodata (A083); internal dataset mask written; invalid source pixels filled before the cubic warp; BORDER_REPLICATE.
- save_registered_geotiff: valid_fraction = mean of an INTER_NEAREST-warped ones mask (A130); mask written into the .tif with write_mask (0/255, GDAL_TIFF_INTERNAL_MASK); nodata=0 kept; signature and return keys unchanged except new optional source_valid keyword.
- P2.10 must: pass dst_transform/dst_crs as keywords to warp_blockwise (no caller in src/scripts yet); pass pair.source_valid to save_registered_geotiff at runner.py:623 (Q-P2.09-3a).
- Non-blocking Q-P2.09-1 (choices), Q-P2.09-2 (cubic collar around source nodata; erode the mask instead? open).
- Full CPU suite (not gpu/slow): 1170 passed; check runs in about 1 s; 48 registered-output tests pass; ruff clean.
