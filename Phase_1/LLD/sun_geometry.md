# LLD — reference sun geometry (P1.11; run by P1.20)

Produces: C13. Decision: G14. TBD 1.8 experiment 2. Evidence: research (`.fable/research_20260929.json`): no LROC PDS4 label (EDR, CDR, ortho) carries sun geometry; ODE metadata carries `Incidence_angle` per product (M1442997156LE 73.84°, M1443025251LE 74.65°); no sub-solar azimuth anywhere.

## 1. `ingest/sun.py` (new, C13)
| function | exact behaviour |
|---|---|
| `lambert_shade(dtm, posting_m, azimuth_deg, elevation_deg)` | `gy, gx = np.gradient(dtm, posting_m)` with rows increasing **southward** (image-down) and columns eastward; slope `s = arctan(hypot(gx, gy))`; aspect `a = arctan2(−gx, gy)` measured clockwise from image-up; sun vector from `azimuth_deg` (clockwise from image-up) and `elevation_deg`; `shade = clip(sin(el)·cos(s) + cos(el)·sin(s)·cos(az − a), 0, 1)`; NaN where `dtm` is NaN; float32. No cast shadows (that is P1B.01). |
| `fit_sun_azimuth(dtm, posting_m, image, elevation_deg, *, valid=None, step_deg=1.0)` | `azimuths = np.arange(0, 360, step_deg)`; for each, `ncc = corr(lambert_shade(...)[m], image[m])` over `m = valid & finite(dtm) & finite(image)`; peak = argmax; `second_peak` = highest NCC at azimuths ≥ 20° (circular distance) from the peak; `peak_margin = ncc_peak − second_peak_ncc`; `n_valid_px = m.sum()`. `image` and `dtm` must have identical shapes (ValueError otherwise). |
| `sun_from_ode_metadata(json_path, product_name)` | load the ODE JSON; records at `doc["ODEResults"]["Products"]["Product"]` (a dict when there is one record — same parsing as `scripts/fetch_catalogue.query_ode`); pick the record whose `Product_name` upper-cased starts with `product_name` upper-cased; `elevation = 90 − float(Incidence_angle)`, `elevation_source = DOCUMENTED`; `azimuth = None`, `azimuth_source = UNKNOWN`, `azimuth_frame = "grid_up_clockwise"`; `note` names the JSON path and record. No match → `SunGeometry(None, None, UNKNOWN, UNKNOWN, "grid_up_clockwise", note="no ODE record for <name>")`. |
| `sun_from_label(product)` | OHRC label fields `sun_azimuth_deg`, `sun_elevation_deg` (field map, VERIFIED present); both sources `DOCUMENTED`; `azimuth_frame = "label_unverified"` (ISRO's azimuth reference direction is not documented in any file we hold); missing field → None + UNKNOWN. |
| `SunGeometry.as_tuple()` | `(azimuth, elevation)` when both are not None, else None. |
| `SunGeometry.as_dict()` | all fields; enum values as strings. |

## 2. `scripts/fit_reference_sun.py` (new; executed in P1.20)
CLI: `python scripts/fit_reference_sun.py [--nac 1|2] [--half-size-m 3000] [--out data/processed/vikram/reference_sun]`.
1. DTM: `data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1.TIF` via rasterio (its own transform is metric and matches the NAC projection — measured 2026-09-29: origin −11046, 638262, 3 m; the NAC ortho's corrected origin is −11043.5, 638258.5, 1 m); nodata → NaN.
2. NAC ortho: label via `lro.georeference_from_label` (C10); window = a square of `2·half_size_m` centred on the Vikram site (lon 32.32, lat −69.37), converted with the GeoReference; read that window only (never the whole 2.2 GB file).
3. Reproject the NAC window onto the DTM grid over the same square (`rasterio.warp.reproject`, bilinear, `src_transform = GeoReference.affine()` of the window, `dst_transform` = DTM window transform, shared proj4). `valid = nac > 0`.
4. Elevation from `sun_from_ode_metadata("data/raw/reference/lro_nac_vikram/ode/edrnac4_vikram_box.json", "M1442997156LE")` (`--nac 2` → `M1443025251LE`). Missing ODE file → exit 2 with the fetch command to run (`scripts/fetch_public.py --only ode_edrnac4_box`).
5. `fit = fit_sun_azimuth(dtm_win, 3.0, nac_on_dtm, elevation, valid=valid)`.
6. Outputs under `--out`: `reference_sun.json` = `{"sun": SunGeometry(azimuth=fit.azimuth_deg, elevation, azimuth_source=INFERRED, elevation_source=DOCUMENTED, azimuth_frame="grid_up_clockwise", note=…).as_dict(), "fit": {azimuth_deg, ncc_peak, second_peak_deg, second_peak_ncc, peak_margin, n_valid_px, step_deg}, "inputs": {...paths...}}`, `ncc_curve.csv` (`azimuth_deg,ncc`), and `run_record.json` (C15). Prints the fit summary.
Grid-up vs north: in this polar stereographic grid, grid-up differs from true north by `lon − lon_0` = 32.32 − 32.3 = 0.02° at the site; the note states that and no correction is applied.

## 3. Tests the prompt adds (`tests/test_sun.py`)
Synthetic: `eval.scenes.fractal_terrain` + `add_craters` as a DTM (scale heights to metres: multiply by 30.0), `image = lambert_shade(dtm, 3.0, 137.0, 16.0)` + small seeded noise → `fit_sun_azimuth(...).azimuth_deg` within 2° of 137 and `peak_margin > 0`; shape mismatch raises `ValueError`; ODE parsing on a hand-written JSON with two records (dict and list forms) → elevation 90 − incidence, azimuth None; no-match case; `sun_from_label` on a stub product.
