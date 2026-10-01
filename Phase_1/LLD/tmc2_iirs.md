# LLD — TMC-2 and IIRS ingest, skip-if-absent (P1.15)

Closes: A063 (ingest-19), A064 (preprocess-10). Decision: G24 (CLARIFY Q5). Standing rule (user memory `no-invented-schema-fields`): no field name or band layout is written from memory.

## 1. Probe first
1. `.venv/bin/python -m lunar_reg.cli catalog` (P1.03). For each of TMC2 and IIRS:
   - PRESENT → run `.venv/bin/python -m lunar_reg.cli probe-label <label> --all --suggest > docs/probes/<product_id>.txt` for **one** product and use that output as the only source for §2.
   - ABSENT/PARTIAL → skip §2 for that instrument; write a non-blocking QUESTIONS entry `Q-P1.15-<n>` "TMC-2|IIRS fields not probed: no product on disk"; §3 and §4 still apply.
`docs/probes/` is created by this prompt (add `docs/probes/*.txt` to its file list; they are generated artefacts, committed for review).
2. **Raster probe for every derived TMC-2 product present** (`*_d_oth_*`, `*_d_dtm_*`; G40). Add `scripts/probe_raster.py PATH --out docs/probes/<product_id>_raster.json` and run it once per such product. It opens the raster with rasterio and never calls `read()` without `out_shape`. JSON keys (all required): `path` (repo-relative), `width`, `height`, `count`, `dtype`, `block_shapes` (list), `compression` (string or null), `nodata_declared` (number or null), `crs_wkt`, `res` (`[x, y]`), `decimation` (`f = ceil(max(width, height) / 2048)`), `border_values` (the 5 most common values, with counts, on the outermost 2 % of rows and columns of the `out_shape=(ceil(h/f), ceil(w/f))`, `Resampling.nearest` read), `fill_candidate` (the most common border value when it covers ≥ 50 % of the border samples, else null), `fill_candidate_source` (`"inferred"`), `fill_fraction` (share of decimated pixels equal to `fill_candidate`, or null), `peak_rss_bytes` (`resource.getrusage(RUSAGE_SELF).ru_maxrss * 1024` at exit). When `nodata_declared` is null and `fill_candidate` is not null, write a non-blocking QUESTIONS entry `Q-P1.15-<n>` naming the value, so the human can confirm it against the SIS document in `docs/external/tmc/`. Nothing downstream uses a fill value unless it is confirmed.

## 2. Field map additions (only from a probe)
For each field the probe shows (e.g. a TMC-2 view identifier, IIRS band centre wavelengths), add a `Field` to `fieldmap.py` with the exact element path from the probe and `Provenance.VERIFIED`. Fields the probe does not show are **not** added. If `fieldmap.py` needs editing, it is allowed in this prompt (append-only; existing fields unchanged).

## 3. `pds4.py`
- `PDS4Product.view: str | None` property: the value of a probed view field when present, else None (no filename parsing).
- `PDS4Product.band_axis: int | None`: index of the axis named `Band` in `axis_order` order (0-based), None for 2-D products. Used by callers to read cubes in the label's own interleave (never assumed).
- `guess_sensor` unchanged.

## 4. Hyperspectral routing (A064)
In `preprocess/pipeline.py::_step_band_reduction`: when `context.src_dataset` is a rasterio dataset with `count > 1` and `config.band_reduction_method == "pca"`, call `hyperspectral.incremental_band_pca(context.src_dataset, n_components=config.pca_n_components, block_rows=512)` instead of reducing the in-memory cube, and record `detail["mode"] = "incremental"`; otherwise keep the in-memory path with `detail["mode"] = "in_memory"`. Correct the module docstring claim ("never loaded whole") to state which path each mode takes.

## 5. Tests the prompt adds (`tests/test_tmc2_iirs.py`)
`probe_raster.py` on a synthetic 3000 × 5000 GeoTIFF with a 0-valued border and no declared nodata → `fill_candidate == 0`, `decimation == 3`, `fill_fraction` between 0 and 1;
`band_axis` on synthetic labels with `Band,Line,Sample` and `Line,Sample,Band` axis orders; `view` is None without a probed field; incremental PCA path chosen for a 3-band in-memory rasterio dataset (MemoryFile) and gives the same first component sign-insensitively (|corr| > 0.99) as the in-memory path on a small cube; a `data`-marked test per instrument that reads one real product's label when PRESENT.
