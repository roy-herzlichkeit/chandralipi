# STATUS

current: P1.12
phase: 1
state: READY
branch: phase-1
last_done: P1.11
notes:
- P1.11: new ingest/sun.py (C13: SunGeometry, AzimuthFit, lambert_shade, fit_sun_azimuth, sun_from_ode_metadata, sun_from_label, azimuth_elevation_from_vector, sun_from_spice with lazy spiceypy + once-per-process furnsh, north_to_grid_azimuth); AzimuthFit provenance = module constant AZIMUTH_FIT_SOURCE (INFERRED).
- pyproject: optional extra spice = ["spiceypy>=8.0"]; installed via `pip install -e ".[dev,spice]"` (PyPI, spiceypy 8.2.0).
- New scripts/fit_reference_sun.py (LLD §2), NOT run on real data (P1.20 runs it); classified StepOutcome counts + report(); exit 2 on missing kernels/spiceypy/ODE JSON; tested on SYNTHETIC rasters. Review fix: failed/missing DTM fit or label convention keeps every key = None, source=unknown (fit_minus_spice_deg=None, no KeyError).
- Q-P1.11-1 (non-blocking): extra output keys (per_strip product_id since raw+calibrated share a tag; *_source/note keys in reference_sun.json), trailing-Z strip before str2et, grid conversion at the SPICE point -> list as LLD deviations in the review pack.
- scripts/ci.sh: 803 passed (log: scratchpad p1/ci_P1.11.log); check_P1.11 ~11 s.
