# STATUS

current: P1.17
phase: 1
state: READY
branch: phase-1
last_done: P1.16
notes:
- P1.16: new lunar_reg.sites.runner (SiteConfig, ProductRun, SiteReport, run_site, compute_exp1_gate); scripts/run_vikram.py thin CLI (keeps export_stored, prepare_pair, geometry_extra, _stored_shift, ExportStatus; drops coarse_shift, centre_offset_m); not ruff-formatted (nor at HEAD). Review fixes: exp-1 gate passes strip if any comparable group (source, reference, sensors, variant) passes; per-component *_azimuth_source/*_elevation_source sun keys written after register_pair (source_sun_source gone); unsaved results never rewrite GeoTIFF; GeoTIFF write failures in report(); gate load failures classified ('load_failed' / 'not loaded').
- Dry run (`run_vikram.py --dry-run --only 20240425T1406019344 --out-dir data/processed/vikram/runs/p1_16_dry`), from data/processed/vikram/runs/p1_16_dry/products.json and run_record.json: prep_ok 2, 0 failed. OHRC raw: source 750x750, reference 1330x1343 at 4 m/px, prior label_corners. OHRC calibrated: reference 1323x1346, prior geometry_grid. Both: search prior "prior shift 556,-2888 m (E,S)", reference valid 99%. TMC2/IIRS present but 0 selected; CLI exit 1 (dry run, Q-P1.16-2).
- Runner output under out_dir: run_record.json, products.json, preview/<SENSOR>_<tag>_{src,ref}.png, registered/<pair_id>.tif. Run-record notes carry "<inst>: <status>, not run" for each requested instrument that is not PRESENT.
- Non-blocking QUESTIONS: Q-P1.16-1 (extras beyond the LLD; (f) updated), Q-P1.16-2 (dry-run exit code), Q-P1.16-3 (which results the exp-1 agreement uses; updated), Q-P1.16-4 (prior shift on grid-prior calibrated OHRC).
- scripts/ci.sh: 912 passed, 18 deselected (log: scratchpad p1/ci_P1.16.log).
