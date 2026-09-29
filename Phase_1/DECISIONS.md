# Phase 1 — local decisions

| ID | decision | reason | rejected |
|---|---|---|---|
| D1-1 | NAC upper-left x sign chosen by fitting the raster boundary to the label's own bounding coordinates; the flip is `INFERRED`. | Measured 2026-09-29: flipped sign → 935 m bbox residual, as written → 23.9 km; the DTM GeoTIFF in the same bundle has origin −11046 m (negative). No document states the sign. | Hard-coding −11043.5 (run_vikram today); trusting GDAL |
| D1-2 | Reference sun elevation from ODE's box query (`results=m`), not per-product `results=fmp`. | The box query is the VALIDATED source of `Incidence_angle`; `fmp` returned file lists. | Per-product ODE queries (unvalidated metadata shape) |
| D1-3 | Preset ablation runs into a separate store (`data/processed/ablation/store`); only the default preset's runs enter the live store. | The live store must hold one configuration per pair; ablation variants would collide on `pair_id` or clutter viewers. | Variants in the live store with `_pp-<preset>` ids |
| D1-4 | ECC prefilter is chosen from sun geometry only when both suns share an `azimuth_frame`; today they do not, so `ecc_prefilter` stays the CLI's value (default `none`). | OHRC's azimuth reference direction is undocumented; comparing it with a grid-up azimuth could pick the wrong prefilter silently. | Assuming both azimuths are clockwise from north |
| D1-5 | P1.21 (viewers) and P1.22 (docs) are split from the planned single P1.21. | One prompt = one component (sizing rule); the docs refresh needs the viewers' export. | One large prompt |
| D1-6 | `run_ablation.py` and `run_jaxa.py` are scripts, not library code. | They encode site/data choices, not reusable logic. | `src/lunar_reg/ablation.py` |
| D1-7 | The exp-1 gate is `SKIP_1B` only when **all three** 2023 strips meet every target. | A partial success still leaves strips the bridge could fix (CLARIFY Q2: "a risk we have to take"). | Majority rule |
