# STATUS

current: P1.07
phase: 1
state: READY
branch: phase-1
last_done: P1.06
notes:
- P1.06: overlap.py adds PriorSource (C11), WindowStatus, WindowOutcome, FootprintPolygon.geometry_grid_path (footprint_from_row copies it), to_fit_plane, footprint_prior_source, pixel_window; grid tried first (lru_cache(8)); unreadable grid -> GRID_UNREADABLE (no fallback); bbox footprint -> BBOX_HAS_NO_PIXEL_ORIENTATION. polygon_to_pixel_window == pixel_window(...).window. crop_to_overlap writes window_status/prior_source, all bands, window_transform, crs, parent's nodata.
- Fixes A046/A047/A048/A050/A051/A052/A105/A106 applied; pseudo_gt.project_to_pixels goes through to_fit_plane; same-sensor scan iterates j>i; duplicate product_id rows -> new OverlapDiagnostics.n_self_pairs_skipped (Q-P1.06-2). Review fix: A047 rewrap shifts each ring as a whole (unwrap, shift mean into (ref-180, ref+180]); per-vertex version gave false OK antipodal overlaps. Q-P1.06-3 records departure from literal LLD A047 wording: list as LLD deviation in review pack.
- Behaviour change: MISSING_FOOTPRINT now counted once per product; test_overlap.py::test_missing_footprint_is_reported_as_metadata_not_as_no_overlap assertion 1 -> 2 (only that line edited, file not formatted).
- overlap.py, pseudo_gt.py, tests/test_overlap_fixes.py ruff-formatted. scripts/ci.sh: 654 passed (log: scratchpad p1/ci_P1.06.log).
- Non-blocking: Q-P1.06-1 (after A047 rewrap, reference footprint in other longitude convention gives OUTSIDE_PRODUCT on corner path), Q-P1.06-2 (<4 corners -> NO_PIXEL_SIZE; self-pair counter), Q-P1.06-3.
