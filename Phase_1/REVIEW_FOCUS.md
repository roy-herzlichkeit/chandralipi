# Phase 1 — review focus

| # | where | why it is risky | how to check |
|---|---|---|---|
| 1 | `ingest/lro.py` `georeference_from_label` | Every absolute position and every NAC crop depends on it; the sign flip is inferred, not documented. | `test_C10_*`; compare against `PROVENANCE.json` corrected transform; compare the DTM GeoTIFF origin (−11046, 638262). |
| 2 | `pairs.py` prior and `reference_to_native` | A half-pixel or factor error shifts every result silently; the prior must match `run_vikram.prepare_pair` so `label_offset_m` keeps its meaning. | `test_P1_13.py` synthetic end-to-end; run `scripts/run_vikram.py --dry-run` and look at the previews. |
| 3 | `sites/runner.py` coarse/prior logic | The 2023 diagnosis hinges on whether the search window covered the right ground (FABLE_NOTES §5 caveat). | Read the `coarse_pass`/`search_prior` extras of the 2023 rows; they must not claim a prior that was not used (A112). |
| 4 | `preprocess/radiometric.py` `valid=None` path | Matchers call `to_uint8`; any change to the unmasked path changes every stored number. | The byte-hash regression tests in `tests/test_preprocess_nodata.py`. |
| 5 | `docs/VIKRAM_2023_DIAGNOSIS.md` | Panel-facing conclusions; every number must cite an artefact, and the cause classes must follow the rule table, not judgement. | Check each number's path; recompute one class from the table. |
| 6 | `ingest/sun.py` azimuth convention | Image-up vs north and clockwise vs counter-clockwise are easy to flip; the fit's peak margin says how trustworthy the azimuth is. | `test_P1_11.py::test_east_facing_slope_brightest_under_east_sun`; read `ncc_curve.csv`. |
| 7 | `scripts/fetch_public.py` pacing | DARTS blocks bursts; unpaced retries can get the IP blocked. | `test_P1_02.py`; read the host-pacing code. |
| 8 | `match/superglue.py` import | Must not leave `sys.path` or `sys.modules` polluted; licence text must reach both viewers. | `test_P1_14.py`. |
