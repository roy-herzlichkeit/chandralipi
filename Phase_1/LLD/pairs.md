# LLD — window-pair preparation (P1.13)

Produces: C11 (except `PriorSource`, which P1.06 defines). TBD 1.3 / 1.8 step 1. Replaces the logic of `scripts/run_vikram.prepare_pair` with a library function that records its geometry numerically (the P0.11 keys) and uses the label georeference (C10) and, when present, the geometry grid (P1.05/P1.06).

## 1. Inputs and steps of `prepare_window_pair`
Arguments per C11. `source_label` = OHRC PDS4 label; `reference_path` = NAC label path; `reference_geo` = `lro.georeference_from_label(reference_path)`.
1. `read_label(source_label)`; failure → `LABEL_UNREADABLE`.
2. Source window (native px): `win = round(window_m / src_gsd)` lines, `win_s = min(win, samples)` samples, centred on `centre_line` (default `lines // 2`) and the middle sample; `src_gsd = constants.SENSORS[product.sensor].gsd_m` (OHRC 0.25, TMC2 5.0, IIRS 80.0; DOCUMENTED nominal, recorded in `provenance`). Unknown sensor → `LABEL_UNREADABLE` with detail `"no nominal GSD for sensor <s>"`.
3. Ground position of the four window corners, per `PriorSource`:
   - `GEOMETRY_GRID` when `geometry_grid_path` is given (or found with `geometry_grid.find_geometry_files(label dir parent, product_id)`): `geometry_grid.pixel_to_lonlat` at the window corners;
   - else `LABEL_CORNERS`: bilinear interpolation of the four label corners (the `run_vikram.interp_latlon` formula: `top = (1−u)·UL + u·UR`, `bot = (1−u)·LL + u·LR`, `p = (1−v)·top + v·bot`, u = sample fraction, v = line fraction);
   - no corners and no grid → `NO_FOOTPRINT`.
4. Reference pixels of those corners: `reference_geo.lonlat_to_pixel(lon, lat)`; add `shift_m` converted to reference px (east → +col, south → +row: `Δcol = shift_e / psx`, `Δrow = shift_s / psy`).
5. Reference window (native px) = bounding box of the four shifted corners ± `margin_m / psx`, integer floor/ceil; if it does not intersect the raster → `OUTSIDE_REFERENCE`.
6. Read both windows with rasterio (`boundless=True, fill_value=0` for the reference; the source via `pds4.open_product`); read failure → `READ_FAILED`. Multi-band source (`dataset.count > 1`): read all bands of the window and reduce per `band_reduction` — `"first"` = band 1, `"mean"` = nan-mean over bands, `"pca"` = `preprocess.hyperspectral.reduce_bands(cube, method="pca", n_components=1)`; the method is recorded in `provenance["band_reduction"]`.
7. Resample both to `gsd_m` with `cv2.resize(..., INTER_AREA)`: source factor `gsd_m / src_gsd`, reference factor `gsd_m / psx`; sizes `round(w / factor)`, `round(h / factor)`.
8. `valid` masks = native `> 0` resampled with `INTER_NEAREST`; images stretched with `radiometric.to_uint8(x, valid=valid)` (P1.08: 0 = nodata).
9. Reference valid fraction < 0.05 → `EMPTY_REFERENCE`.
10. `prior` = perspective transform from the working-source window corners `(0,0), (w,0), (0,h), (w,h)` to the **unshifted** corner reference pixels expressed in working-reference px (`(col − c0)/ref_factor`, `(row − r0)/ref_factor`), exactly as `run_vikram.prepare_pair` does today (so `label_offset_m` keeps its meaning).
11. `source_to_native` and `reference_to_native` follow the pixel-centre convention in CONTRACTS C11: `fx = native_width / working_width`, `fy = native_height / working_height` (actual sizes, not the nominal factor), `to_native = [[fx, 0, x0 + (fx − 1)/2], [0, fy, y0 + (fy − 1)/2], [0, 0, 1]]` with `(x0, y0) = (s0, l0)` for the source and `(c0, r0)` for the reference. The label-corner `prior` of step 10 stays in run_vikram's corner convention (it is a km-level guess; the half-pixel difference is irrelevant to it).
12. `provenance` = `{"src_gsd": "documented", "reference_georef": reference_geo.source.value, "corners": "documented", "shift_m": "inferred" if shift_m != (0, 0) else "computed"}` (label corners and geometry grids are both ISRO data, hence DOCUMENTED).
`WindowPair.geometry_extra()` returns the C04 crop-geometry keys: `ref_crop_c0=c0, ref_crop_r0=r0, ref_factor, shift_e_m, shift_s_m, src_win_l0=l0, src_win_s0=s0, src_win_lines=win, src_win_samples=win_s, gsd_m, crop_geometry_source="recorded"` plus `prior_source`.

## 2. Tests the prompt adds (`tests/test_pairs.py`)
Synthetic end-to-end with no real data: write a small PDS4-like source label + raw image (`tmp_path`, 400×300 uint8, corners chosen so the window maps inside), a synthetic reference GeoTIFF + a `GeoReference` built directly (C10 constructor), then: OK outcome; prior maps the source window centre to within 1 working px of the known position; `geometry_extra()` keys exactly the C04 set + `prior_source`; shifting by `(40, 0)` m moves `ref_crop_c0` by `40 / psx`; a reference far away → `OUTSIDE_REFERENCE`; a label without corners and no grid → `NO_FOOTPRINT`. Reuse `tests/test_ingest_labels.py`'s label helper for the label XML (read it; do not invent element names).
