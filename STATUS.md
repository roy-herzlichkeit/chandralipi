# STATUS

current: P1.16
phase: 1
state: READY
branch: phase-1
last_done: P1.15
notes:
- P1.15: TMC2 and IIRS PRESENT; probes docs/probes/ch2_tmc_ncn_20230521T0857294318_d_img_d32.txt, docs/probes/ch2_iir_nci_20221226T0416479474_d_img_d32.txt. No TMC-2 view element (PDS4Product.view always None). fieldmap SPECTRAL_FIELDS: first_band_center_wavelength, first_band_width (first Band_Bin only).
- PDS4Product.band_axis case-insensitive (IIRS axes BAND,LINE,SAMPLE -> 0). _step_band_reduction: mode=incremental only for multi-band rasterio src_dataset with (count,h,w)==image.shape; else mode=in_memory + detail incremental_refused. Review fix: incremental also refused when georeference RAN (new init=False PreprocessContext.steps_applied, filled by run_pipeline); addition to LLD tmc2_iirs §4 route rule -> list under LLD deviations in review pack.
- probe_raster ortho (docs/probes/ch2_tmc_ndn_20231027T1315134884_d_oth_d18_raster.json): nodata_declared null, fill_candidate 0, fill_fraction 0.9424622314551045, peak_rss_bytes 76603392; Q-P1.15-1 asks human to confirm fill. DTM (docs/probes/..._d_dtm_d18_raster.json) declares -32768.
- hyperspectral.py: docstring only, not ruff-formatted (unformatted at HEAD). Q-P1.15-2, Q-P1.15-3 non-blocking design choices.
- scripts/ci.sh: 892 passed (log: scratchpad p1/ci_P1.15.log).
