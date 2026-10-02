# Agent prompt A1 — find sites where OHRC, TMC-2, IIRS and an independent reference all overlap

You are a research agent for project Chandralipi (ISRO SIH26166: register Chandrayaan-2 OHRC, TMC-2 and IIRS images to lunar reference images). Work in the repo at `~/Desktop/Projects/sih`, branch `phase-1`. Read this whole prompt before acting.

## Goal
Produce a ranked list of **sites**. A site is a patch of lunar ground that all of these see:
1. at least one **OHRC** product (0.25 m/px, footprint about 12 km × 30–90 km);
2. at least one **TMC-2** product (5 m/px);
3. at least one **IIRS** product (80 m/px);
4. an **independent reference map** at a scale each instrument can be matched against:
   - for OHRC: an LRO NAC **map-projected** product (1–2 m/px) — ODE product types `SDNDTM` (NAC DTM + orthoimages, 668 products) or `SDPPHO` (NAC map-projected photometric, 765), or a NAC polar mosaic `BDRNPL` (1 752) near the poles;
   - for TMC-2 and IIRS: SELENE TC Ortho Map tiles (7.4 m/px, 3° × 3° tiles from JAXA DARTS) or the same NAC product.

Plain NAC frames (`EDRNAC4`, `CDRNAC4`) do **not** count. They have no map projection, and this project has no ISIS/SPICE step to project them (`docs/DATA_ACQUISITION.md` §5).

The current anchor site, Vikram, fails rule 2–3: the TMC-2/IIRS products on disk are 529–652 km away (`Phase_1/QUESTIONS.md` Q-P1.18-1). The best Vikram candidates in `Phase_1/DOWNLOAD_BRIEF_TMC2_IIRS_VIKRAM.md` overlap the references but sit only 0.5–3.8 km inside their footprint edges. Find better sites, and include Vikram in your ranking for comparison.

## Architect's preview (a starting point, not an answer: confirm or refute it)
On 2026-10-02 the architect ran a quick version of this search. It used `SDNDTM` only, catalogue polygons only, no depth, no deduplication across the global and polar OHRC layers, and a 40 × 40 point grid on each NAC label bounding box. Inputs: `.fable/ode_sdndtm_20261002.json` (the ODE query, M); output: `.fable/site_overlaps_preview_20261002.json`. Of the 668 `SDNDTM` products, 25 overlap at least one OHRC footprint and 11 overlap all three instruments (M, ±8 km polygon error). Top rows, with all-three overlap area inside the NAC bounding box:

| NAC product | centre lat, lon | all-3 km² | OHRC / TMC-2 / IIRS km² |
|---|---|---|---|
| `NAC_DTM_NOBILE04` | −84.47, 32.67 | 283 | 974 / 2 802 / 1 367 |
| `NAC_DTM_VIKRAMSITE1` | −69.29, 32.34 | 227 | 283 / 672 / 1 110 |
| `NAC_DTM_BOOSTIMPCT1` | 5.31, 234.52 | 219 | 219 / 661 / 661 |
| `NAC_DTM_NFRIGORIS01` | 60.46, 355.41 | 156 | 156 / 694 / 708 |
| `NAC_DTM_SIMPELIUS01` | −70.80, 22.71 | 93 | 93 / 238 / 238 |
| `NAC_DTM_SHACKRDGE02`, `ESALL_CR1`, `ESALL_SR12` | about −89.5 | 40–61 | whole site (polar; long shadows) |
| `NAC_DTM_THEOPHILUS3`, `THEOPHILUS` | −13.3, 25.2 | 23–30 | |

Your job:
- confirm these numbers with the full method below (depth, deduplication, controls);
- extend the search to `SDPPHO` and `BDRNPL`;
- add the SELENE TC reference;
- rank.

Two notes:
- The OHRC counts in the preview include each product once per layer it appears in. The Vikram row's "42" is 21 products twice (`docs/DATA_ACQUISITION.md` §5 lists 21).
- Equatorial and mid-latitude sites (`BOOSTIMPCT1`, `NFRIGORIS01`, `THEOPHILUS`) avoid the near-polar long shadows. Weigh that in your ranking and say how.

## Inputs already on disk (read, never modify)
| what | path | format and CRS |
|---|---|---|
| OHRC calibrated footprints | `data/raw/catalogue/moon_ins_ch2_ohr_cal.geojson`, `…_sp_ch2_ohr_cal_sp.geojson`, `…_np_ch2_ohr_cal_np.geojson` | ISSDC WFS GeoJSON. EPSG:100009 = lon/lat degrees; 100011 = south polar stereographic **metres**; 100010 = north polar stereographic metres. Read with `scripts/fetch_catalogue.py` (`read_issdc_catalogue`, `_ring_to_latlon`). |
| TMC-2 and IIRS footprints | `data/raw/catalogue/shapefiles/{TMC2,IIRS}_ShapeFiles/*/ch2_{tmc,iir}_{cal,raw,derived_*}{,_sp,_np}.{shp,dbf,prj}` | ESRI shapefile. The `.prj` gives the CRS: plain = lon/lat; `_sp`/`_np` = polar stereographic metres, sphere R = 1 737 400 m. Reader: `.fable/tools/read_esri_shp.py` (follows the published ESRI layout). The `.dbf` corner fields (`UL_LAT`, `UL_LON`, `UR_LAT`, …, `BR_LON`) hold **projected metres** in the polar layers, not degrees: use the polygon geometry. |
| Vikram reference set | `data/raw/reference/lro_nac_vikram/`, `data/raw/reference/selene_tc_ortho/` | see `configs/references.json` |
| ODE query rules | `docs/DATA_ACQUISITION.md` §2 | `odemetadb=moon`, `ihid=LRO`, `iid=LROC`, `pt=…` are all mandatory; use `results=m` (never `results=fmp` on large queries) |

ODE `SDNDTM` records carry `Footprint_geometry` (WKT, lon 0–360), `Center_latitude/longitude`, `LabelURL` and `Map_resolution`. Their footprints are the **PDS label bounding box** (`Footprint_souce` field), so they overstate the area that has valid pixels.

## Network (read-only, public catalogues only)
- Allowed: ODE REST (`https://oderest.rsl.wustl.edu/live2/?…`) metadata queries, at least 3 s apart; JAXA DARTS directory listings, at least 30 s apart, one attempt per URL.
- Forbidden: downloading any image product; any automation of PRADAN/ISSDC (ISRO pages are clicked by the human only, CLARIFY R6).
- Not on disk: an OHRC "Other Downloads" shapefile. If you believe the on-disk OHRC layers are incomplete, write the exact click steps for the human. Never fetch it yourself.

## Method (binding: these rules exist because of real past errors)
1. **Never test overlap in longitude/latitude.** Polar strips span most of 0–360° of longitude, so lon/lat boxes "contain" places hundreds of km away; that is how a past session reported 90–100 % coverage for strips 529–652 km from the site.
   - Project every polygon into a local azimuthal equidistant projection centred on the candidate site (`+proj=aeqd +lat_0=<lat> +lon_0=<lon> +R=1737400`), or into polar stereographic for |lat| > 60°.
   - Densify every polygon edge to at least 10 points in its native CRS before projecting.
2. **Measure overlap as an area, not a yes/no.** Sample the reference footprint with a grid of at least 40 × 40 points. Count points inside the union of each instrument's polygons, and inside all of them. Report km².
3. **Measure depth.** Depth is the largest distance from any all-instrument overlap point to the nearest edge of that overlap. A registration window needs depth ≥ 2 km for OHRC/NAC and ≥ 10 km for IIRS. Footprint polygons here are 4-corner shapes that differ from the true pixel grids by about 8 km (architect, measured). Any depth below 8 km is **uncertain**: label it so.
4. **Controls must pass before you trust any number.** Write a control table into your report:
   - the four TMC-2/IIRS products on disk (`ch2_tmc_ncf_20231026T0943001971`, `ch2_tmc_ncn_20230521T0857294318`, `ch2_iir_nci_20230125T1944138897`, `ch2_iir_nci_20221226T0416479474`) must come out ≥ 500 km from Vikram (−69.37°, 32.32°) (truth from their per-pixel grids: 529–652 km);
   - the four OHRC `ncp` products at Vikram (`ch2_ohr_ncp_20240425T1406019344`, `…20230823T1450475804`, `…20230823T1647285085`, `…20230823T1647285315`) must overlap `NAC_DTM_VIKRAMSITE1`.

   If a control fails, stop and report the failure; do not produce a ranking.
5. **Illumination diversity counts.** SIH26166 asks for Sun-angle invariance. Per site, report how many distinct OHRC dates and TMC-2/IIRS dates there are, and the incidence angles when a catalogue gives a real value. ISSDC publishes `INC_ANGLE = 0`, which is a placeholder, not a measurement: say "unknown".
6. **Classify every site; never drop silently.** Each candidate gets one status:

   | status | meaning |
   |---|---|
   | `ALL4` | OHRC + TMC-2 + IIRS + independent reference |
   | `OHRC_REF_ONLY` | OHRC and a reference, but TMC-2/IIRS missing |
   | `TMC_IIRS_REF_ONLY` | TMC-2, IIRS and a reference, but no OHRC |
   | `NO_OHRC` | no OHRC product overlaps |
   | `FOOTPRINT_UNREADABLE` | a footprint could not be read |

   Report counts per status, with the first example of each.

## Output (create exactly these; commit nothing)
1. `data/processed/sites/candidate_sites.json` — one object per evaluated site:
   `{site_name, reference_type ("SDNDTM"|"SDPPHO"|"BDRNPL"|"SELENE_TC"), reference_id, reference_label_url, centre_lat, centre_lon, site_km2, ohrc_km2, tmc2_km2, iirs_km2, all_km2, all_depth_km, depth_certain (bool), n_ohrc_products, n_ohrc_dates, n_tmc2_products, n_iirs_products, ohrc_ids[], tmc2_ids[], iirs_ids[], status, notes}`.
2. `data/processed/sites/SITES_REPORT.md`:
   - the control table;
   - status counts;
   - the top 10 `ALL4` sites ranked by `all_km2`, then `all_depth_km`, then `n_ohrc_dates`;
   - Vikram's row for comparison;
   - for each top-3 site, two sentences on why it is or is not a good demo site.

   Every number carries its evidence tag: **M** = computed by you from a file or query whose path or URL you cite in the same row; **D** = read in a document; **I** = inference. No number without a source.
3. The script you used, `data/processed/sites/find_sites.py`. It is self-contained, reads only the inputs above plus cached ODE JSON under `data/processed/sites/ode_cache/`, and re-runs offline.

## Done when
The controls pass, the JSON validates against the field list above, and the report ranks at least one `ALL4` site — or states, with the status counts as evidence, that none exists.
