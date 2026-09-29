# LLD — catalogue footprints as polygons (P0.06)

Closes: A004 (pipeline_results-3). Evidence: `scripts/fetch_catalogue.py:263-282` writes the first four ring vertices as `corner1..4`; `overlap.footprint_from_row` traverses 1,2,4,3 (UL,UR,LR,LL), so ring-ordered vertices become a bow-tie.

## 1. `scripts/fetch_catalogue.py`
- Delete `_corner_columns`. ISSDC rows (`read_issdc_catalogue`) write `corner1_lat … corner4_lon = None` and a new column `footprint_wkt = overlap.polygon_to_wkt(latlon)` where `latlon` is the catalogue's outer ring as `(lat, lon)` pairs in ring order (closing vertex allowed; `polygon_to_wkt` strips it).
- ODE rows already write `footprint_wkt` from `Footprint_C0_geometry`; unchanged.
- `footprint_resolved` stays True only when `footprint_wkt` is not None.

## 2. `ingest/overlap.py::footprint_from_row` (only this function)
Order of preference:
1. four explicit corners (unchanged, ring 1,2,4,3);
2. **new:** `footprint_wkt` when it is a non-empty string → parse with `polygon_from_wkt(text) -> tuple[(lat, lon), ...] | None` (new module-level function next to `polygon_to_wkt`);
3. bounding box (unchanged, `bbox_derived=True`).

`polygon_from_wkt` accepts exactly the form `polygon_to_wkt` writes and ODE's form: `POLYGON((x y, x y, ...))` or `POLYGON ((x y, ...))`, optional whitespace, x = lon, y = lat. It returns only the outer ring (text up to the first `)`), strips the closing duplicate, and returns None for anything else (MULTIPOLYGON, fewer than 3 vertices, non-numeric). A None result falls through to the bounding box.

Do **not** use the ISSDC `UL_LAT`/`UL_LON`/`UR_*`/`BL_*`/`BR_*` feature properties for corners: in the polar layers they are projected metres, not degrees (measured 2026-09-29: `moon_ins_sp_ch2_ohr_cal_sp.geojson` feature 0 has `UL_LAT = -7284.2642`).

## 3. Tests the prompt adds (`tests/test_catalogue_footprints.py`)
| test | asserts |
|---|---|
| WKT round trip | `polygon_from_wkt(polygon_to_wkt(ring)) == ring` within 1e-9 |
| ODE spacing | `"POLYGON ((32.1 -69.2, 32.3 -69.2, 32.3 -69.4, 32.1 -69.4, 32.1 -69.2))"` parses to 4 `(lat, lon)` vertices |
| row with WKT only | `footprint_from_row` returns a polygon with the WKT vertices and `bbox_derived is False` |
| MULTIPOLYGON | falls back to bbox |
| ISSDC reader | a synthetic 5-vertex GeoJSON feature yields `corner*` None and a `footprint_wkt` whose polygon area equals the ring's area (`polygon_area_m2`) within 1e-6 relative |
