# STATUS

current: P1.06
phase: 1
state: READY
branch: phase-1
last_done: P1.05
notes:
- P1.05: geometry_grid.py now has public snap_to_integer (with _snap kept as an alias) and an __all__. find_geometry_files uses *_g_grd_*.csv and filters by the YYYYMMDDTHHMMSSffff token; an id with no token returns [] and logs one warning. The longitude rewrap uses the column-0 median, and the new GeometryGrid.longitude_reference_deg is also applied to lonlat_to_pixel queries. polygon_to_pixel_window takes the union of boundary samples and the grid nodes inside the polygon (PolarFrame at >= POLAR_LATITUDE_DEG; overlap/pseudo_gt are imported lazily to avoid a cycle once P1.06 wires the grid in).
- Real-grid data tests RAN, none skipped: 4 calibrated OHRC ncp grids under data/raw/ch2/ohrc. 8 data tests passed (log: scratchpad p1/pytest_P1.05.log). data/raw/ohrc_vikram has no grid CSVs.
- Non-polar node test also rewraps node longitudes to the same reference as the polygon. This changes nothing when the grid has a reference.
- geometry_grid.py and tests/test_geometry_grid_fixes.py were ruff-formatted. test_geometry_grid.py was only edited in the §5 block (not formatted). scripts/ci.sh: 634 passed (scratchpad p1/ci_P1.05.log).
