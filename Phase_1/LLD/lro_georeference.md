# LLD — NAC georeference from the PDS4 label (P1.04)

Produces: C10. Closes: A007 (S11), A008 (ingest-2). Evidence: `data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml:111-160` (cart block, read 2026-09-29), `PROVENANCE.json` (`MEASURED_2026-09-28_UNIT_WARNING`), AUDIT header (S12 refuted).

## 1. Label fields (element local names seen in the real label)
| quantity | element (under `cart:Cartography`) | unit |
|---|---|---|
| projection name | `map_projection_name` | text, e.g. `Polar Stereographic` |
| central meridian | `Polar_Stereographic/longitude_of_central_meridian` | deg |
| latitude of true scale | `Polar_Stereographic/latitude_of_projection_origin` | deg (acts as `lat_ts`; `lat_0 = -90` when negative, `+90` when positive) |
| pixel size | `pixel_scale_x`, `pixel_scale_y` | m/pixel — **never** `pixel_resolution_x` (deg/pixel, GDAL's mistake) |
| origin | `upperleft_corner_x`, `upperleft_corner_y` | m |
| radius | `a_axis_radius` | km (× 1000) |
| bounds | `west_/east_/north_/south_bounding_coordinate` | deg |
| raster size | `Axis_Array` `Line`/`Sample` elements | px |
Read with `pds4._resolve` (document order, P0.05) on the parsed XML root; any missing field → `LabelGeoreferenceError` listing every missing local name. Only `Polar Stereographic` and `Equirectangular` projection names are supported; anything else → `LabelGeoreferenceError`.

## 2. proj4 strings
- Polar Stereographic: `+proj=stere +lat_0=<±90> +lat_ts=<latitude_of_projection_origin> +lon_0=<central meridian> +R=<a*1000> +units=m +no_defs`.
- Equirectangular (`Equirectangular` name; fields `Equirectangular/longitude_of_central_meridian`, `Equirectangular/standard_parallel_1`): `+proj=eqc +lat_ts=<standard_parallel_1> +lon_0=<cm> +R=<a*1000> +units=m +no_defs`.

## 3. Upper-left x sign rule (the S12 question, decided by data)
Candidates `x0 ∈ {+upperleft_corner_x, −upperleft_corner_x}` (y0 as written). For each candidate: sample the raster boundary (100 points per edge, pixel-corner convention), convert to lon/lat with the proj4 string (`pyproj`, via `rasterio.warp.transform` with `+proj=longlat +R=<R> +no_defs`), take the lon/lat bounding box, and compute `residual_m = max(|Δwest|, |Δeast|) · R · cos(mean_lat) · π/180` combined with `max(|Δnorth|, |Δsouth|) · R · π/180` as `hypot`. Choose the candidate with the smaller residual.
- Chosen = as written → `source = ValueSource.DOCUMENTED`.
- Chosen = flipped → `source = ValueSource.INFERRED`.
- `note` = `f"ul_x sign {'as written' if … else 'flipped'}; bbox residual {chosen:.1f} m (other sign {other:.1f} m)"`.
Longitudes are compared after mapping both sides into [0, 360).

## 4. `GeoReference` methods (C10)
Pixel-corner convention: `x = x0 + col · psx`, `y = y0 − row · psy`. `lonlat_to_pixel` / `pixel_to_lonlat` go through the proj4 string with the sphere `+proj=longlat +R=<R> +no_defs`, vectorised, returning float64 arrays. `affine()` returns `Affine(psx, 0, x0, 0, −psy, y0)`. `as_dict()` / `from_dict()` round-trip every field (`source` as its value string).

## 5. `lro.py` changes
- `georeference_from_label(label_path) -> GeoReference` (module-level, C10).
- `read_lro_label` PDS4 branch (A008): after `read_label`, set `values["lines"]`, `values["samples"]`, `values["bands"]` from the parsed axes, and `min_lat/max_lat/min_lon/max_lon` from the four `*_bounding_coordinate` fields; `LROProduct` gains `georef: GeoReference | None` (None when the label has no cart block, with the error text appended to `unresolved`).
- `lro_to_row` fills `lines`, `samples`, `min/max lat/lon` from those values; `footprint_resolved` True when all four bounds resolved.
- `open_lro_product` unchanged; callers that need geometry use `LROProduct.georef`, never `dataset.transform` (add one warning line to the docstring saying so).

## 6. Tests the prompt adds (`tests/test_lro_georeference.py`)
| test | asserts |
|---|---|
| synthetic polar label (tmp XML with the §1 elements; ul_x written positive, bounds computed from the negative origin) | `x0_m` is negative, `source == INFERRED`, `pixel_size_x_m == 1.0` |
| synthetic label whose bounds match the written sign | `source == DOCUMENTED` |
| `pixel_resolution_x` present but `pixel_scale_x` missing | `LabelGeoreferenceError` naming `pixel_scale_x` |
| round trip | `lonlat_to_pixel(pixel_to_lonlat(c, r)) == (c, r)` within 1e-6 px |
| `as_dict` / `from_dict` | equality |
| real NAC label (`data`) | `x0_m == -11043.5 ± 0.01`, `y0_m == 638258.5 ± 0.01`, `width == 23003`, `height == 47683`, `source == INFERRED` |
| real NAC row (`data`) | `lro_to_row(read_lro_label(...))` has non-null `lines`, `samples`, and the four bounds |
