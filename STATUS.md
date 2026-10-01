# STATUS

current: P1.05
phase: 1
state: READY
branch: phase-1
last_done: P1.04
notes:
- P1.04: lro.py has GeoReference, LabelGeoreferenceError and georeference_from_label (C10): reads the cart block through pds4._resolve, uses pixel_scale_x/y (never pixel_resolution), fits the ul_x sign to Bounding_Coordinates (LLD §3) via rasterio.warp.transform (pyproj not installed). LROProduct.georef added; PDS4 branch of read_lro_label fills lines/samples/bands and min/max lat/lon; footprint_resolved needs all four bounds; open_lro_product docstring warns against GDAL's transform. Review fix: non-positive a_axis_radius and PROJ CRSError/ValueError become LabelGeoreferenceError (product kept, georef=None).
- Real NAC labels (M1442997156 and M1443025251; scratchpad p1/georef_P1.04.txt): source=inferred, x0_m=-11043.49999999978, y0_m=638258.4999999872, 23003x47683, note "ul_x sign flipped; bbox residual 935.4 m (other sign 23887.2 m)".
- Non-blocking Q-P1.04-1: the chosen sign still leaves a 935.4 m bbox residual (label bounds are not the exact raster boundary). Implemented §3 as written, with no threshold.
- Georef failure text goes into LROProduct.unresolved as "georef: ..." and may contain commas (unresolved_fields is comma-joined). `lunar-reg catalog` still exits 0 with unchanged LRO lines (scratchpad p1/catalog_P1.04.stdout). scripts/ci.sh: 621 passed (scratchpad p1/ci_P1.04.log).
- lro.py and tests/test_lro_georeference.py ruff-formatted. scripts/run_vikram.py not touched.
