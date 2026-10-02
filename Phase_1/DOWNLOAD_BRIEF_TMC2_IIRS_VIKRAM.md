# Download brief — TMC-2 and IIRS strips over the Vikram references

For: a download-session agent working with the human. Written by the architect, 2026-10-02.
Evidence tags: **M** = measured by the architect on files on disk · **D** = read in a file · **I** = inference or estimate, not measured.

## 1. Goal
Get Chandrayaan-2 TMC-2 and IIRS products whose ground footprint overlaps the reference maps already on disk at the Vikram landing site (69.37° S, 32.32° E):

| reference on disk | detail | area |
|---|---|---|
| LRO NAC ortho `NAC_DTM_VIKRAMSITE1_M1442997156_100CM` | 1 m/px | 1 097 km², lat −70.08…−68.50, lon 31.23…33.46 (M) |
| SELENE TC ortho tiles `TCO_MAP_02_S66E030S69E033SC`, `…S69E030S72E033SC` | 7.4 m/px | lat −72…−66, lon 30…33 (D, labels) |

With these products the pipeline can register TMC-2 (5 m) and IIRS (80 m) to independent references: SELENE (Japan) and LRO (NASA). The TMC-2/IIRS strips already on disk can't do this, because they are 529–652 km away (Phase_1/QUESTIONS.md Q-P1.18-1, M).

Once the files are on disk, no code changes are needed. P1.24's `scripts/run_cross.py find` discovers the overlaps, and P1.18 step 4 registers them.

## 2. Rules (binding)
- **PRADAN (ISRO) is clicked by the human only** (CLARIFY R6). The agent prepares the exact product list and click steps, and never automates the logged-in site.
- **Disk budget:** `data/raw/` ≤ 120 000 000 000 B (CLARIFY Q17, revised 2026-10-01). It was 56 884 460 885 B on 2026-10-02 (M).
  - Before each download, state the zip size shown by PRADAN. After each unzip, print `du -sb data/raw`.
  - Stop and ask the human before crossing the budget.
- **Layout:** follow `Phase_1/LLD/downloads.md` §1.
  - Zip to `data/raw/ch2/_zips/`.
  - `unzip -n` to `data/raw/ch2/<tmc2|iirs>/<zip stem>/`.
  - Record every file in `data/raw/DOWNLOADS.json` the way §3 does.
- **Never delete or overwrite** anything under `data/raw/`.

## 3. Candidates (from PRADAN's footprint shapefiles on disk)
Source: `data/raw/catalogue/shapefiles/{TMC2,IIRS}_ShapeFiles/*/ch2_{tmc,iir}_*_sp.{shp,dbf}`.
- These are the south-polar layers, in polar stereographic metres (`.prj`: `Stereographic_South_Pole`, sphere R = 1 737 400 m) (D).
- They were read with `.fable/tools/read_esri_shp.py`, which follows the published ESRI shapefile layout.
- Overlap areas were computed in that projection.
- Full table: `.fable/vikram_candidates_20261002.json`.

**The parser is validated on the control set:** the four products already on disk.

| product (on disk) | distance from Vikram: shapefile polygon | distance: per-pixel grid |
|---|---|---|
| TMC-2 `ncf_20231026T0943001971` | 537 km | 529 km |
| TMC-2 `ncn_20230521T0857294318` | 659 km | 652 km |
| IIRS `nci_20230125T1944138897` | 546 km | 538 km |
| IIRS `nci_20221226T0416479474` | 624 km | 617 km |

The polygons are 4-corner shapes, and they differ from the true pixel grid by about 8 km (M). So the "contains the landing point" depths below, 0.5–3.8 km, are **within that error**: a strip may miss the exact landing point. The overlap areas with the references are hundreds to thousands of km², so those are robust.

### TMC-2 (all from one pass, 2023-01-30, orbit start 19:00:13Z)
| priority | product (zip = id + `.zip`) | view (I, from the file name) | overlap NAC | overlap SELENE tiles |
|---|---|---|---|---|
| 1 | `ch2_tmc_ncn_20230130T1900132182_d_img_d32` | nadir, calibrated | 616 km² | 3 715 km² |
| 2 | `ch2_tmc_ncf_20230130T1900132214_d_img_d32` | fore, calibrated | 665 km² | 4 135 km² |
| 3 | `ch2_tmc_nca_20230130T1900132182_d_img_d32` | aft, calibrated | 668 km² | 4 114 km² |
| optional | `ch2_tmc_ndn_20230130T1900132182_d_oth_d32` (+ `_d_dtm_d32`) | ISRO derived ortho (+ DTM) | 653 km² | 3 845 km² |

These are the only TMC-2 calibrated records in the polar layer that overlap the SELENE region (M). The global lon/lat layer adds none (M).

### IIRS (calibrated `nci`)
| priority | product | date | overlap NAC | overlap SELENE tiles |
|---|---|---|---|---|
| 1 | `ch2_iir_nci_20201226T1745264921_d_img_d32` | 2020-12-26 | 730 km² | 1 958 km² |
| 2 | `ch2_iir_nci_20210622T1256344234_d_img_d32` | 2021-06-22 | 400 km² | 4 018 km² |
| 3 | `ch2_iir_nci_20210719T1622353775_d_img_d32` | 2021-07-19 | 584 km² | 1 430 km² |
| 4 | `ch2_iir_nci_20230130T1501406990_d_img_d32` | 2023-01-30 (same day as the TMC-2 pass) | 408 km² | 767 km² |

### Sizes
The shapefiles give no sizes; PRADAN shows them before download. Estimates are taken from the same-kind products already on disk (I):
- TMC-2 calibrated `d32`: zip ≈ 0.9 GB, unpacked ≈ 2.5 GB.
- IIRS calibrated: zip ≈ 2.6–3.5 GB, unpacked ≈ 3.3–4.2 GB.
- TMC-2 derived ortho: zip ≈ 0.4 GB but **unpacked ≈ 14.7 GB**, an uncompressed GeoTIFF. Read it only per G40.

**Recommended set:** TMC-2 priorities 1–2 plus IIRS priorities 1–2. That is about 20 GB of zips plus unpacked data (I: 2 × (0.9 + 2.5) + 2 × (3.0 + 3.8)), which fits the budget with room to spare.

## 4. Pitfall that produced the wrong "90–100 % cover" figures in P1.DL
Strips that pass near the south pole have corner longitudes spanning most of 0–360°. Any coverage test done in longitude/latitude (bounding boxes, or polygons in lon/lat) then "contains" places hundreds of km away. This is the most likely cause (I) of the P1.DL figures, which the per-pixel grids refute.

**Always test coverage in polar stereographic metres** (the `_sp` layers' own projection), or with the product's per-pixel geometry grid after download.

## 5. After the download (acceptance)
1. `bash Phase_1/harness/check_P1.DL.sh` and `.venv/bin/python scripts/verify_downloads.py --no-hash` must both pass.
2. When P1.24 is done, run `.venv/bin/python scripts/run_cross.py find --references configs/references.json --instruments TMC2,IIRS --out /tmp/overlaps_check.json`. It uses each product's per-pixel grid. Every new product should be `overlap` against at least one `lro_nac_*` or `selene_tc_ortho_*` reference.
   - A new product that comes out `disjoint` is reported to the architect with its `min_distance_km`. It is never silently dropped.
3. Write a session summary, `.fable/inbox_P1DL2_<date>.md`, for the architect, with these items:
   - products fetched, zip sizes and unpacked sizes;
   - the `du -sb data/raw` total;
   - the `find` outcome per product;
   - any deviation from this brief.
4. Hand the summary to the architect. If P1.18 is still open, its step 4 picks up the new pairs. If it is already done, the architect adds one RUN prompt that repeats P1.18 step 4. Either way no code changes (G41).
