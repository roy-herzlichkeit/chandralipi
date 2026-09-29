# LLD — geometry grid fixes (P1.05)

Closes: A009 (ingest-3), A045 (ingest-11), A103 (ingest-16), A104 (tooling-16). TBD 1.1 part 1 (the grid itself; wiring into overlap is P1.06).

## 1. Public snap helper (used by P1.06)
Rename `_snap` → `snap_to_integer(value: float, tolerance: float = PIXEL_SNAP_TOLERANCE) -> float` (same body); keep `_snap = snap_to_integer` as a module alias so internal callers do not change. Export it in `__all__`.

## 2. `find_geometry_files(root, product_id=None)` (A045)
Pattern `*_g_grd_*.csv`. When `product_id` is given, extract its timestamp token with `re.search(r"\d{8}T\d{10}", product_id)` and keep only CSVs whose name contains that token (not the whole id — the grid file's level/version tokens differ from the image's). No token in `product_id` → match nothing and log one warning. Return shape unchanged: `[(csv_path, label_or_None)]`, sorted.

## 3. Longitude unwrapping (A103)
`_maybe_unwrap_longitude(lon, diag)` → rewrap relative to a reference: `ref = median of the finite values in column 0` (the first sample column), then `lon = ref + ((lon - ref + 180) % 360) - 180` over finite values. Return True and append the existing note only when at least one value changed by more than 1e-9. `GeometryGrid` gains `longitude_reference_deg: float | None` (the `ref` used, None when no rewrap). `lonlat_to_pixel(grid, lat, lon, ...)`: when `grid.longitude_reference_deg` is not None, rewrap the query longitudes with the same formula before solving.

## 4. `polygon_to_pixel_window(grid, polygon, densify=8)` (A009)
Candidate pixel positions = union of:
1. densified boundary samples that land inside the grid (current behaviour), and
2. every grid node `(scan_lines[i], pixels[j])` whose `(lat, lon)` lies inside the polygon.
Point-in-polygon for step 2: when `max(|lat|) ≥ overlap.POLAR_LATITUDE_DEG` over the polygon, test in `overlap.PolarFrame(±90).plane_ring(...)` coordinates; otherwise in (lon, lat) after rewrapping polygon longitudes to the grid's longitude reference (or to the polygon's first vertex when the grid has none). Use `pseudo_gt.point_in_ring` (existing, `pseudo_gt.py:125`). Window arithmetic, snapping and clipping stay as today. Returns None only when both sets are empty.

## 5. Test file fixes (A104) — `tests/test_geometry_grid.py`
The `data` test resolves roots from `Path(__file__).resolve().parents[1] / "data"` (not the cwd), searches `data/raw/ch2/ohrc/**` and `data/raw/ohrc_vikram/**` with the `*_g_grd_*.csv` pattern, and its skip reason lists the roots searched. After P1.DL the calibrated OHRC products provide real grids; the test must then run (not skip).

## 6. Tests the prompt adds (`tests/test_geometry_grid_fixes.py`)
| test | asserts |
|---|---|
| polygon inside the grid, no boundary sample inside (a small polygon strictly inside a coarse grid cell region) | window is not None and contains the polygon's interior nodes |
| polygon larger than the product | window equals the full product |
| antimeridian grid (lon 179.5 … −179.5 as −180…180 input) | `longitude_reference_deg` set; a query at lon −179.9 returns an inside pixel |
| non-wrapping grid | no note appended, `longitude_reference_deg is None` |
| `find_geometry_files` with `_g_grd_n18.csv` and `_g_grd_d18.csv` names | both found; product-id filter uses the timestamp token |
| real ncp grid (`data`) | `covers_full_image` True; pixel → lon/lat → pixel round trip < 0.01 px at 25 sample points |
Synthetic grids: build a `GeometryGrid` directly (constructor fields per `geometry_grid.py:226`) with a smooth analytic lat/lon field.
