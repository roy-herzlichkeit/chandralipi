# REPO_TREE

Snapshot generated 2026-09-28 23:49 IST at commit `bbf9585` ("Register Chandrayaan-2 OHRC to LRO NAC at the Vikram site; export registered GeoTIFFs"). This file records facts only. It contains no analysis and proposes no fixes.

The working tree had uncommitted changes when this snapshot was taken (`git status --short`, excluding this file):

```
 M docs/project/CONTEXT.md
 M docs/project/CONTEXT_HANDOFF.md
 M docs/DEMO_SCRIPT.md
 M scripts/export_web_data.py
 M udocs/50_findings.md
 M web/public/data/results.json
?? CLAUDE.md
?? gdocs/
```

## 1. Directory tree (depth 4)

Only `.git/`, `.venv/`, `web/node_modules/` and tool caches are skipped. Each skipped directory appears on one collapsed line with its file count and size. `__pycache__/` directories are omitted entirely.

Everything else is included, whether gitignored or not:

- data products under `data/`
- the packed archive in `dist/`
- the Vite build in `web/dist/`
- the generated `web/public/data/`
- `udocs/` and `gdocs/`

Directories at depth 4 whose contents lie deeper show a file count instead. Every file still appears in section 2.

```
./
├── .claude/
│   ├── launch.json
│   └── settings.local.json
├── .git/  [skipped: git metadata; 62 files, 23M]
├── .pytest_cache/  [skipped: cache; 5 files, 64K]
├── .ruff_cache/  [skipped: cache; 7 files, 36K]
├── .venv/  [skipped: virtualenv; 27237 files, 2.2G]
├── configs/
│   └── default.yaml
├── dashboard/
│   └── app.py
├── data/
│   ├── processed/
│   │   ├── demo_real/
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_akaze_01_matches.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_akaze_02_checkerboard.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_akaze_03_blend.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_asift_01_matches.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_asift_02_checkerboard.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_asift_03_blend.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue_01_matches.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue_02_checkerboard.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue_03_blend.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_loftr_01_matches.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_loftr_02_checkerboard.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_loftr_03_blend.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_sift_01_matches.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_sift_02_checkerboard.png
│   │   │   ├── JAXA_SELENE_TC-JAXA_SELENE_TC_sift_03_blend.png
│   │   │   ├── JAXA_SELENE_TC-LRO_WAC_asift_01_matches.png
│   │   │   ├── JAXA_SELENE_TC-LRO_WAC_asift_02_checkerboard.png
│   │   │   ├── JAXA_SELENE_TC-LRO_WAC_asift_03_blend.png
│   │   │   ├── JAXA_SELENE_TC-LRO_WAC_lightglue_01_matches.png
│   │   │   ├── JAXA_SELENE_TC-LRO_WAC_lightglue_02_checkerboard.png
│   │   │   ├── JAXA_SELENE_TC-LRO_WAC_lightglue_03_blend.png
│   │   │   ├── JAXA_SELENE_TC-LRO_WAC_loftr_01_matches.png
│   │   │   ├── JAXA_SELENE_TC-LRO_WAC_loftr_02_checkerboard.png
│   │   │   ├── JAXA_SELENE_TC-LRO_WAC_loftr_03_blend.png
│   │   │   ├── JAXA_SELENE_TC-LRO_WAC_sift_01_matches.png
│   │   │   ├── JAXA_SELENE_TC-LRO_WAC_sift_02_checkerboard.png
│   │   │   ├── JAXA_SELENE_TC-LRO_WAC_sift_03_blend.png
│   │   │   └── README.md
│   │   ├── logs/
│   │   │   ├── vikram_2023_priorshift.log
│   │   │   ├── vikram_classical_coarse_4m.log
│   │   │   ├── vikram_lightglue_5m.log
│   │   │   ├── vikram_lightglue_coarse_4m.log
│   │   │   └── vikram_sift.log
│   │   ├── results/
│   │   │   ├── pairs/
│   │   │   │   └── … (13 files below depth 4)
│   │   │   └── index.parquet
│   │   ├── vikram/
│   │   │   ├── registered/
│   │   │   │   └── … (8 files below depth 4)
│   │   │   ├── 2024_lightglue_checkerboard.png
│   │   │   ├── 2024_lightglue_matches.png
│   │   │   └── README.md
│   │   ├── .gitkeep
│   │   ├── manifest_vikram.parquet
│   │   └── ohrc_vikram_product_ids.txt
│   └── raw/
│       ├── catalogue/
│       │   ├── moon_ins_ch2_ohr_cal.geojson
│       │   ├── moon_ins_np_ch2_ohr_cal_np.geojson
│       │   └── moon_ins_sp_ch2_ohr_cal_sp.geojson
│       ├── ohrc_vikram/
│       │   ├── ch2_ohr_nrp_20230823T1450475804_d_img_n18/
│       │   │   └── … (9 files below depth 4)
│       │   ├── ch2_ohr_nrp_20230823T1647285085_d_img_n18/
│       │   │   └── … (9 files below depth 4)
│       │   ├── ch2_ohr_nrp_20230823T1647285315_d_img_n18/
│       │   │   └── … (9 files below depth 4)
│       │   └── ch2_ohr_nrp_20240425T1406019344_d_img_d18/
│       │       └── … (9 files below depth 4)
│       ├── reference/
│       │   ├── jaxa_selene_tc/
│       │   │   └── … (11 files below depth 4)
│       │   ├── jaxa_selene_tc_pair2/
│       │   │   └── … (6 files below depth 4)
│       │   ├── jaxa_selene_tc_pair3/
│       │   │   └── … (3 files below depth 4)
│       │   ├── lro_nac_vikram/
│       │   │   └── … (7 files below depth 4)
│       │   └── lro_wac/
│       │       └── … (6 files below depth 4)
│       └── .gitkeep
├── dist/
│   └── chandralipi-data-processed-20260909.tar.zst
├── docs/
│   ├── CROSS_MODAL_IIRS.md
│   ├── DATA_ACQUISITION.md
│   ├── DEMO_SCRIPT.md
│   ├── INTERNALS_QNA.md
│   ├── INTERNALS_SCRIPT.md
│   ├── MAKHARIA_PARITY.md
│   ├── REPORT_SECTION.md
│   └── VRAM_CONSTRAINTS.md
├── gdocs/
│   ├── 01_WHY_THIS_PROBLEM_STATEMENT_EXISTS.md
│   ├── 02_PURPOSE_OF_THE_PROJECT.md
│   ├── 03_WHY_I_CHOSE_THIS_PROJECT.md
│   ├── 04_APPROACH_BENEFITS_ALTERNATIVES_ISRO_ALIGNMENT.md
│   └── 05_FEASIBILITY.md
├── notebooks/
│   └── .gitkeep
├── old_assets/
│   ├── assets/
│   │   ├── chandrayaan2.png
│   │   ├── chandrayaan2_orbiter.jpg
│   │   ├── cuda.png
│   │   ├── gdal.png
│   │   ├── gdal.svg
│   │   ├── isro.png
│   │   ├── isro.svg
│   │   ├── jaxa.png
│   │   ├── jaxa.svg
│   │   ├── nasa.png
│   │   ├── nasa.svg
│   │   ├── numpy.png
│   │   ├── numpy.svg
│   │   ├── nvidia.png
│   │   ├── nvidia.svg
│   │   ├── ohrc_vikram.png
│   │   ├── opencv.png
│   │   ├── opencv.svg
│   │   ├── python.png
│   │   ├── python.svg
│   │   ├── pytorch.png
│   │   ├── pytorch.svg
│   │   ├── SOURCES.md
│   │   ├── streamlit.png
│   │   └── streamlit.svg
│   ├── P26083.txt
│   ├── P26142.txt
│   ├── P26166.txt
│   ├── P26166_report.md
│   ├── P26166_SIH_Idea_PPT.pptx
│   ├── P26166_slide_idea.md
│   ├── P26167.txt
│   ├── sih_guidelines.pdf
│   └── sih_pptx_template.pptx
├── scripts/
│   ├── build_demo_results.py
│   ├── demo.py
│   ├── export_web_data.py
│   ├── fetch_catalogue.py
│   ├── make_contour_background.py
│   ├── pack_data.sh
│   ├── README.md
│   ├── reindex_results.py
│   ├── run_dashboard.sh
│   ├── run_vikram.py
│   ├── setup.sh
│   └── up.sh
├── src/
│   └── lunar_reg/
│       ├── align/
│       │   ├── __init__.py
│       │   ├── estimate.py
│       │   ├── refine.py
│       │   └── warp.py
│       ├── eval/
│       │   ├── __init__.py
│       │   ├── conditioning.py
│       │   ├── error_budget.py
│       │   ├── metrics.py
│       │   ├── scenes.py
│       │   └── uniformity.py
│       ├── ingest/
│       │   ├── __init__.py
│       │   ├── fieldmap.py
│       │   ├── footprint.py
│       │   ├── geometry_grid.py
│       │   ├── lro.py
│       │   ├── manifest.py
│       │   ├── overlap.py
│       │   ├── pds4.py
│       │   ├── probe.py
│       │   ├── pseudo_gt.py
│       │   └── tiling.py
│       ├── match/
│       │   ├── rift2/
│       │   │   └── … (5 files below depth 4)
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── benchmark.py
│       │   ├── classical.py
│       │   ├── learned.py
│       │   ├── loftr.py
│       │   ├── memory.py
│       │   ├── rift2_status.py
│       │   ├── stitch.py
│       │   ├── superglue.py
│       │   └── tiled.py
│       ├── preprocess/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── georeference.py
│       │   ├── hyperspectral.py
│       │   ├── params.py
│       │   ├── pipeline.py
│       │   ├── radiometric.py
│       │   ├── resample.py
│       │   └── shadow.py
│       ├── viz/
│       │   ├── __init__.py
│       │   ├── figures.py
│       │   └── plots.py
│       ├── __init__.py
│       ├── cli.py
│       ├── constants.py
│       ├── device.py
│       ├── pipeline.py
│       └── results.py
├── tests/
│   ├── conftest.py
│   ├── test_align.py
│   ├── test_conditioning.py
│   ├── test_device.py
│   ├── test_eval.py
│   ├── test_footprint.py
│   ├── test_geometry_grid.py
│   ├── test_ingest_labels.py
│   ├── test_match_base.py
│   ├── test_matchers_and_refinement.py
│   ├── test_overlap.py
│   ├── test_pipeline.py
│   ├── test_preprocess.py
│   ├── test_preprocess_pipeline.py
│   ├── test_pseudo_gt.py
│   ├── test_registered_export.py
│   ├── test_results_and_pipeline.py
│   ├── test_rift2.py
│   ├── test_scenes_and_budget.py
│   └── test_tiling.py
├── udocs/
│   ├── 00_ROADMAP.md
│   ├── 01_WHAT_AND_WHY.md
│   ├── 10_PRIMER_geodesy.md
│   ├── 11_PRIMER_projections.md
│   ├── 12_PRIMER_footprints.md
│   ├── 13_PRIMER_sensors.md
│   ├── 20_PRIMER_transforms.md
│   ├── 21_PRIMER_matching.md
│   ├── 22_PRIMER_robust_fitting.md
│   ├── 23_PRIMER_metrics.md
│   ├── 30_PRIMER_pds4_and_pradan.md
│   ├── 31_PRIMER_instruments.md
│   ├── 40_the_pipeline.md
│   ├── 50_findings.md
│   ├── 60_MATHS.md
│   ├── 61_ML_and_where_it_fits.md
│   ├── 70_SYSTEM_DESIGN_distributed_gpu.md
│   └── 90_GLOSSARY.md
├── web/
│   ├── dist/
│   │   ├── assets/
│   │   │   ├── Architecture-pAxC-Q5-.js
│   │   │   ├── Dashboard-DPqDAF7A.js
│   │   │   ├── Home-B1J8BPZl.js
│   │   │   ├── index-BeecwOhy.js
│   │   │   ├── index-Y1zyM-mB.css
│   │   │   ├── Resources-DquSNZ6N.js
│   │   │   └── Reveal-oXfXj1tH.js
│   │   ├── data/
│   │   │   ├── pairs/
│   │   │   │   └── … (130 files below depth 4)
│   │   │   └── results.json
│   │   ├── textures/
│   │   │   ├── lunar-contours.svg
│   │   │   ├── moon_color_2k.jpg
│   │   │   └── moon_displacement.jpg
│   │   └── index.html
│   ├── node_modules/  [skipped: npm deps; 10110 files, 259M]
│   ├── public/
│   │   ├── data/
│   │   │   ├── pairs/
│   │   │   │   └── … (45 files below depth 4)
│   │   │   └── results.json
│   │   └── textures/
│   │       ├── lunar-contours.svg
│   │       ├── moon_color_2k.jpg
│   │       └── moon_displacement.jpg
│   ├── src/
│   │   ├── components/
│   │   │   ├── Diagram.jsx
│   │   │   ├── Moon.jsx
│   │   │   ├── Reveal.jsx
│   │   │   └── theme.js
│   │   ├── pages/
│   │   │   ├── Architecture.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Home.jsx
│   │   │   └── Resources.jsx
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── DESIGN.md
│   ├── index.html
│   ├── package-lock.json
│   ├── package.json
│   ├── README.md
│   └── vite.config.js
├── .env
├── .gitignore
├── CLAUDE.md
├── docs/project/CONTEXT.md
├── docs/project/CONTEXT_HANDOFF.md
├── docs/plan/FABLE_REVIEW.md
├── pyproject.toml
├── README.md
├── docs/project/README_TITLE.md
├── docs/backlog/TBD_phase_1.md
├── docs/backlog/TBD_phase_2.md
├── docs/backlog/TBD_phase_3.md
├── docs/backlog/TBD_phase_4.md
├── docs/backlog/TBD_phase_5.md
├── docs/backlog/TBDs.md
└── docs/project/TIMELINE.md
```

## 2. Files

One row per file, excluding the skipped directories (516 files).

- **lines** is the output of `wc -l`, which counts newline characters. A file with content but no trailing newline therefore shows `0`. `binary` means `grep -I` classified the file as binary.
- **purpose** without a marker is paraphrased from the file's own module docstring, header comment, or first Markdown heading.
- A purpose starting with `*` means the file has no such header. These purposes come from one of:
  - reading the file
  - its filename or directory
  - the script that writes that path
  - an accompanying readme or `PROVENANCE.json`

  The source is named in the row where it is not the file itself.

| path | lines | purpose |
|---|---|---|
| `.claude/launch.json` | 11 | * Claude desktop preview launch config (one configuration, `dashboard`: Streamlit on port 8501) |
| `.claude/settings.local.json` | 11 | * Claude Code local settings (single top-level key: `permissions`) |
| `configs/default.yaml` | 36 | Default pipeline configuration (per its header comment) |
| `CLAUDE.md` | 73 | * Instructions file for Claude sessions (sections: ROLE, MEMORY, TOKEN ECONOMY, …); untracked, created 23:47:56 during this snapshot |
| `docs/project/CONTEXT_HANDOFF.md` | 677 | Chandralipi — context handoff |
| `docs/project/CONTEXT.md` | 129 | docs/project/CONTEXT.md — Chandralipi |
| `dashboard/app.py` | 321 | Interactive browser for the registration pipeline's outputs |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_akaze_01_matches.png` | binary | * matches figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_akaze` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_akaze_02_checkerboard.png` | binary | * checkerboard figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_akaze` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_akaze_03_blend.png` | binary | * blend figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_akaze` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_asift_01_matches.png` | binary | * matches figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_asift` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_asift_02_checkerboard.png` | binary | * checkerboard figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_asift` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_asift_03_blend.png` | binary | * blend figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_asift` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue_01_matches.png` | binary | * matches figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue_02_checkerboard.png` | binary | * checkerboard figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue_03_blend.png` | binary | * blend figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_loftr_01_matches.png` | binary | * matches figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_loftr` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_loftr_02_checkerboard.png` | binary | * checkerboard figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_loftr` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_loftr_03_blend.png` | binary | * blend figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_loftr` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_sift_01_matches.png` | binary | * matches figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_sift` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_sift_02_checkerboard.png` | binary | * checkerboard figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_sift` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-JAXA_SELENE_TC_sift_03_blend.png` | binary | * blend figure for result `JAXA_SELENE_TC-JAXA_SELENE_TC_sift` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-LRO_WAC_asift_01_matches.png` | binary | * matches figure for result `JAXA_SELENE_TC-LRO_WAC_asift` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-LRO_WAC_asift_02_checkerboard.png` | binary | * checkerboard figure for result `JAXA_SELENE_TC-LRO_WAC_asift` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-LRO_WAC_asift_03_blend.png` | binary | * blend figure for result `JAXA_SELENE_TC-LRO_WAC_asift` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-LRO_WAC_lightglue_01_matches.png` | binary | * matches figure for result `JAXA_SELENE_TC-LRO_WAC_lightglue` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-LRO_WAC_lightglue_02_checkerboard.png` | binary | * checkerboard figure for result `JAXA_SELENE_TC-LRO_WAC_lightglue` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-LRO_WAC_lightglue_03_blend.png` | binary | * blend figure for result `JAXA_SELENE_TC-LRO_WAC_lightglue` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-LRO_WAC_loftr_01_matches.png` | binary | * matches figure for result `JAXA_SELENE_TC-LRO_WAC_loftr` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-LRO_WAC_loftr_02_checkerboard.png` | binary | * checkerboard figure for result `JAXA_SELENE_TC-LRO_WAC_loftr` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-LRO_WAC_loftr_03_blend.png` | binary | * blend figure for result `JAXA_SELENE_TC-LRO_WAC_loftr` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-LRO_WAC_sift_01_matches.png` | binary | * matches figure for result `JAXA_SELENE_TC-LRO_WAC_sift` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-LRO_WAC_sift_02_checkerboard.png` | binary | * checkerboard figure for result `JAXA_SELENE_TC-LRO_WAC_sift` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/JAXA_SELENE_TC-LRO_WAC_sift_03_blend.png` | binary | * blend figure for result `JAXA_SELENE_TC-LRO_WAC_sift` (filenames match `scripts/demo.py` figure names) |
| `data/processed/demo_real/README.md` | 149 | Real cross-mission matches, 2026-09-08/09 |
| `data/processed/.gitkeep` | 0 | * Empty placeholder keeping the directory in git |
| `data/processed/logs/vikram_2023_priorshift.log` | 4 | * Text log of a Vikram registration run (per filename and content) |
| `data/processed/logs/vikram_classical_coarse_4m.log` | 36 | * Text log of a Vikram registration run (per filename and content) |
| `data/processed/logs/vikram_lightglue_5m.log` | 18 | * Text log of a Vikram registration run (per filename and content) |
| `data/processed/logs/vikram_lightglue_coarse_4m.log` | 22 | * Text log of a Vikram registration run (per filename and content) |
| `data/processed/logs/vikram_sift.log` | 17 | * Text log of a Vikram registration run (per filename and content) |
| `data/processed/manifest_vikram.parquet` | binary | * Parquet product manifest for the Vikram site (per filename) |
| `data/processed/ohrc_vikram_product_ids.txt` | 21 | * List of OHRC product IDs, one per line |
| `data/processed/results/index.parquet` | binary | * Results index, one row per registered pair (per `src/lunar_reg/results.py` docstring) |
| `data/processed/results/pairs/CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_akaze.npz` | binary | * Stored per-pair result `CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_akaze` (`.npz` store, see `src/lunar_reg/results.py`) |
| `data/processed/results/pairs/CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_asift.npz` | binary | * Stored per-pair result `CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_asift` (`.npz` store, see `src/lunar_reg/results.py`) |
| `data/processed/results/pairs/CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_lightglue.npz` | binary | * Stored per-pair result `CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_lightglue` (`.npz` store, see `src/lunar_reg/results.py`) |
| `data/processed/results/pairs/CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_sift.npz` | binary | * Stored per-pair result `CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_sift` (`.npz` store, see `src/lunar_reg/results.py`) |
| `data/processed/results/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_akaze.npz` | binary | * Stored per-pair result `JAXA_SELENE_TC-JAXA_SELENE_TC_akaze` (`.npz` store, see `src/lunar_reg/results.py`) |
| `data/processed/results/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_asift.npz` | binary | * Stored per-pair result `JAXA_SELENE_TC-JAXA_SELENE_TC_asift` (`.npz` store, see `src/lunar_reg/results.py`) |
| `data/processed/results/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue.npz` | binary | * Stored per-pair result `JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue` (`.npz` store, see `src/lunar_reg/results.py`) |
| `data/processed/results/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_loftr.npz` | binary | * Stored per-pair result `JAXA_SELENE_TC-JAXA_SELENE_TC_loftr` (`.npz` store, see `src/lunar_reg/results.py`) |
| `data/processed/results/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_sift.npz` | binary | * Stored per-pair result `JAXA_SELENE_TC-JAXA_SELENE_TC_sift` (`.npz` store, see `src/lunar_reg/results.py`) |
| `data/processed/results/pairs/JAXA_SELENE_TC-LRO_WAC_asift.npz` | binary | * Stored per-pair result `JAXA_SELENE_TC-LRO_WAC_asift` (`.npz` store, see `src/lunar_reg/results.py`) |
| `data/processed/results/pairs/JAXA_SELENE_TC-LRO_WAC_lightglue.npz` | binary | * Stored per-pair result `JAXA_SELENE_TC-LRO_WAC_lightglue` (`.npz` store, see `src/lunar_reg/results.py`) |
| `data/processed/results/pairs/JAXA_SELENE_TC-LRO_WAC_loftr.npz` | binary | * Stored per-pair result `JAXA_SELENE_TC-LRO_WAC_loftr` (`.npz` store, see `src/lunar_reg/results.py`) |
| `data/processed/results/pairs/JAXA_SELENE_TC-LRO_WAC_sift.npz` | binary | * Stored per-pair result `JAXA_SELENE_TC-LRO_WAC_sift` (`.npz` store, see `src/lunar_reg/results.py`) |
| `data/processed/vikram/2024_lightglue_checkerboard.png` | binary | * PNG figure (checkerboard) from the 2024 LightGlue Vikram run (per filename) |
| `data/processed/vikram/2024_lightglue_matches.png` | binary | * PNG figure (matches) from the 2024 LightGlue Vikram run (per filename) |
| `data/processed/vikram/README.md` | 108 | Chandrayaan-2 OHRC ↔ LRO NAC: Vikram landing site, 2026-09-28 |
| `data/processed/vikram/registered/CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_akaze.png` | binary | * Registered PNG preview for `CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_akaze` (`REGISTERED_DIR` in `scripts/run_vikram.py`) |
| `data/processed/vikram/registered/CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_akaze.tif` | binary | * Registered GeoTIFF for `CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_akaze` (`REGISTERED_DIR` in `scripts/run_vikram.py`) |
| `data/processed/vikram/registered/CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_asift.png` | binary | * Registered PNG preview for `CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_asift` (`REGISTERED_DIR` in `scripts/run_vikram.py`) |
| `data/processed/vikram/registered/CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_asift.tif` | binary | * Registered GeoTIFF for `CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_asift` (`REGISTERED_DIR` in `scripts/run_vikram.py`) |
| `data/processed/vikram/registered/CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_lightglue.png` | binary | * Registered PNG preview for `CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_lightglue` (`REGISTERED_DIR` in `scripts/run_vikram.py`) |
| `data/processed/vikram/registered/CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_lightglue.tif` | binary | * Registered GeoTIFF for `CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_lightglue` (`REGISTERED_DIR` in `scripts/run_vikram.py`) |
| `data/processed/vikram/registered/CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_sift.png` | binary | * Registered PNG preview for `CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_sift` (`REGISTERED_DIR` in `scripts/run_vikram.py`) |
| `data/processed/vikram/registered/CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_sift.tif` | binary | * Registered GeoTIFF for `CH2_OHRC_RAW_20240425T1406019344-LRO_NAC_ORTHO_sift` (`REGISTERED_DIR` in `scripts/run_vikram.py`) |
| `data/raw/catalogue/moon_ins_ch2_ohr_cal.geojson` | 0 | * ISSDC Chandrayaan-2 OHRC catalogue footprints, GeoJSON on a single line (per filename) |
| `data/raw/catalogue/moon_ins_np_ch2_ohr_cal_np.geojson` | 0 | * ISSDC Chandrayaan-2 OHRC catalogue footprints, GeoJSON on a single line (per filename) |
| `data/raw/catalogue/moon_ins_sp_ch2_ohr_cal_sp.geojson` | 0 | * ISSDC Chandrayaan-2 OHRC catalogue footprints, GeoJSON on a single line (per filename) |
| `data/raw/.gitkeep` | 0 | * Empty placeholder keeping the directory in git |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1450475804_d_img_n18/browse/raw/20230823/ch2_ohr_nrp_20230823T1450475804_b_brw_n18.png` | binary | * OHRC browse image |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1450475804_d_img_n18/browse/raw/20230823/ch2_ohr_nrp_20230823T1450475804_b_brw_n18.xml` | 89 | * PDS4 label (`Product_Observational`) for the browse product |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1450475804_d_img_n18/data/raw/20230823/ch2_ohr_nrp_20230823T1450475804_d_img_n18.img` | binary | * OHRC raw image data (PDS4 data file) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1450475804_d_img_n18/data/raw/20230823/ch2_ohr_nrp_20230823T1450475804_d_img_n18.xml` | 126 | * PDS4 label (`Product_Observational`) for the data product |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1450475804_d_img_n18/miscellaneous/raw/20230823/ch2_ohr_nrp_20230823T1450475804_d_img_n18.lbr` | 648 | * Libration angle data file (readme spells it "Liberation angle") (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1450475804_d_img_n18/miscellaneous/raw/20230823/ch2_ohr_nrp_20230823T1450475804_d_img_n18.oat` | 648 | * Orbit and Attitude Data file (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1450475804_d_img_n18/miscellaneous/raw/20230823/ch2_ohr_nrp_20230823T1450475804_d_img_n18.oath` | 1 | * Orbit and Attitude Header file (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1450475804_d_img_n18/miscellaneous/raw/20230823/ch2_ohr_nrp_20230823T1450475804_d_img_n18.spm` | 648 | * Sun Angle file (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1450475804_d_img_n18/miscellaneous/readme.txt` | 183 | * Product readme describing the miscellaneous-collection file formats (.oath/.oat/.lbr/.spm) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285085_d_img_n18/browse/raw/20230823/ch2_ohr_nrp_20230823T1647285085_b_brw_n18.png` | binary | * OHRC browse image |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285085_d_img_n18/browse/raw/20230823/ch2_ohr_nrp_20230823T1647285085_b_brw_n18.xml` | 89 | * PDS4 label (`Product_Observational`) for the browse product |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285085_d_img_n18/data/raw/20230823/ch2_ohr_nrp_20230823T1647285085_d_img_n18.img` | binary | * OHRC raw image data (PDS4 data file) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285085_d_img_n18/data/raw/20230823/ch2_ohr_nrp_20230823T1647285085_d_img_n18.xml` | 126 | * PDS4 label (`Product_Observational`) for the data product |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285085_d_img_n18/miscellaneous/raw/20230823/ch2_ohr_nrp_20230823T1647285085_d_img_n18.lbr` | 518 | * Libration angle data file (readme spells it "Liberation angle") (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285085_d_img_n18/miscellaneous/raw/20230823/ch2_ohr_nrp_20230823T1647285085_d_img_n18.oat` | 518 | * Orbit and Attitude Data file (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285085_d_img_n18/miscellaneous/raw/20230823/ch2_ohr_nrp_20230823T1647285085_d_img_n18.oath` | 1 | * Orbit and Attitude Header file (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285085_d_img_n18/miscellaneous/raw/20230823/ch2_ohr_nrp_20230823T1647285085_d_img_n18.spm` | 518 | * Sun Angle file (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285085_d_img_n18/miscellaneous/readme.txt` | 183 | * Product readme describing the miscellaneous-collection file formats (.oath/.oat/.lbr/.spm) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285315_d_img_n18/browse/raw/20230823/ch2_ohr_nrp_20230823T1647285315_b_brw_n18.png` | binary | * OHRC browse image |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285315_d_img_n18/browse/raw/20230823/ch2_ohr_nrp_20230823T1647285315_b_brw_n18.xml` | 89 | * PDS4 label (`Product_Observational`) for the browse product |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285315_d_img_n18/data/raw/20230823/ch2_ohr_nrp_20230823T1647285315_d_img_n18.img` | binary | * OHRC raw image data (PDS4 data file) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285315_d_img_n18/data/raw/20230823/ch2_ohr_nrp_20230823T1647285315_d_img_n18.xml` | 126 | * PDS4 label (`Product_Observational`) for the data product |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285315_d_img_n18/miscellaneous/raw/20230823/ch2_ohr_nrp_20230823T1647285315_d_img_n18.lbr` | 648 | * Libration angle data file (readme spells it "Liberation angle") (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285315_d_img_n18/miscellaneous/raw/20230823/ch2_ohr_nrp_20230823T1647285315_d_img_n18.oat` | 648 | * Orbit and Attitude Data file (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285315_d_img_n18/miscellaneous/raw/20230823/ch2_ohr_nrp_20230823T1647285315_d_img_n18.oath` | 1 | * Orbit and Attitude Header file (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285315_d_img_n18/miscellaneous/raw/20230823/ch2_ohr_nrp_20230823T1647285315_d_img_n18.spm` | 648 | * Sun Angle file (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20230823T1647285315_d_img_n18/miscellaneous/readme.txt` | 183 | * Product readme describing the miscellaneous-collection file formats (.oath/.oat/.lbr/.spm) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20240425T1406019344_d_img_d18/browse/raw/20240425/ch2_ohr_nrp_20240425T1406019344_b_brw_d18.png` | binary | * OHRC browse image |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20240425T1406019344_d_img_d18/browse/raw/20240425/ch2_ohr_nrp_20240425T1406019344_b_brw_d18.xml` | 89 | * PDS4 label (`Product_Observational`) for the browse product |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20240425T1406019344_d_img_d18/data/raw/20240425/ch2_ohr_nrp_20240425T1406019344_d_img_d18.img` | binary | * OHRC raw image data (PDS4 data file) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20240425T1406019344_d_img_d18/data/raw/20240425/ch2_ohr_nrp_20240425T1406019344_d_img_d18.xml` | 126 | * PDS4 label (`Product_Observational`) for the data product |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20240425T1406019344_d_img_d18/miscellaneous/raw/20240425/ch2_ohr_nrp_20240425T1406019344_d_img_d18.lbr` | 518 | * Libration angle data file (readme spells it "Liberation angle") (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20240425T1406019344_d_img_d18/miscellaneous/raw/20240425/ch2_ohr_nrp_20240425T1406019344_d_img_d18.oat` | 518 | * Orbit and Attitude Data file (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20240425T1406019344_d_img_d18/miscellaneous/raw/20240425/ch2_ohr_nrp_20240425T1406019344_d_img_d18.oath` | 1 | * Orbit and Attitude Header file (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20240425T1406019344_d_img_d18/miscellaneous/raw/20240425/ch2_ohr_nrp_20240425T1406019344_d_img_d18.spm` | 518 | * Sun Angle file (per the collection's readme.txt) |
| `data/raw/ohrc_vikram/ch2_ohr_nrp_20240425T1406019344_d_img_d18/miscellaneous/readme.txt` | 183 | * Product readme describing the miscellaneous-collection file formats (.oath/.oat/.lbr/.spm) |
| `data/raw/reference/jaxa_selene_tc_pair2/TC1S2B0_01_05504N194E0230/TC1S2B0_01_05504N194E0230.jpg` | binary | * SELENE Terrain Camera image (JPEG) |
| `data/raw/reference/jaxa_selene_tc_pair2/TC1S2B0_01_05504N194E0230/TC1S2B0_01_05504N194E0230.lbl` | 147 | * PDS label for a SELENE TC image |
| `data/raw/reference/jaxa_selene_tc_pair2/TC1S2B0_01_05504N194E0230/TC1S2B0_01_05504N194E0230.tif` | binary | * SELENE Terrain Camera image (GeoTIFF) |
| `data/raw/reference/jaxa_selene_tc_pair2/TC1S2B0_01_05505N193E0219/TC1S2B0_01_05505N193E0219.jpg` | binary | * SELENE Terrain Camera image (JPEG) |
| `data/raw/reference/jaxa_selene_tc_pair2/TC1S2B0_01_05505N193E0219/TC1S2B0_01_05505N193E0219.lbl` | 147 | * PDS label for a SELENE TC image |
| `data/raw/reference/jaxa_selene_tc_pair2/TC1S2B0_01_05505N193E0219/TC1S2B0_01_05505N193E0219.tif` | binary | * SELENE Terrain Camera image (GeoTIFF) |
| `data/raw/reference/jaxa_selene_tc_pair3/TC1S2B0_01_05660N099E0382/TC1S2B0_01_05660N099E0382.jpg` | binary | * SELENE Terrain Camera image (JPEG) |
| `data/raw/reference/jaxa_selene_tc_pair3/TC1S2B0_01_05660N099E0382/TC1S2B0_01_05660N099E0382.lbl` | 147 | * PDS label for a SELENE TC image |
| `data/raw/reference/jaxa_selene_tc_pair3/TC1S2B0_01_05660N099E0382/TC1S2B0_01_05660N099E0382.tif` | binary | * SELENE Terrain Camera image (GeoTIFF) |
| `data/raw/reference/jaxa_selene_tc/PROVENANCE.json` | 38 | * Provenance record for the downloaded reference data (source, URL, access method) |
| `data/raw/reference/jaxa_selene_tc/TC1S2B0_01_05600N005E1008/TC1S2B0_01_05600N005E1008.caminfo.pvl` | 154 | * ISIS caminfo PVL for a SELENE TC image |
| `data/raw/reference/jaxa_selene_tc/TC1S2B0_01_05600N005E1008/TC1S2B0_01_05600N005E1008.isis.lbl` | 470 | * ISIS label for a SELENE TC image |
| `data/raw/reference/jaxa_selene_tc/TC1S2B0_01_05600N005E1008/TC1S2B0_01_05600N005E1008.jpg` | binary | * SELENE Terrain Camera image (JPEG) |
| `data/raw/reference/jaxa_selene_tc/TC1S2B0_01_05600N005E1008/TC1S2B0_01_05600N005E1008.lbl` | 147 | * PDS label for a SELENE TC image |
| `data/raw/reference/jaxa_selene_tc/TC1S2B0_01_05600N005E1008/TC1S2B0_01_05600N005E1008.tif` | binary | * SELENE Terrain Camera image (GeoTIFF) |
| `data/raw/reference/jaxa_selene_tc/TC1S2B0_01_05601N004E0998/TC1S2B0_01_05601N004E0998.caminfo.pvl` | 154 | * ISIS caminfo PVL for a SELENE TC image |
| `data/raw/reference/jaxa_selene_tc/TC1S2B0_01_05601N004E0998/TC1S2B0_01_05601N004E0998.isis.lbl` | 470 | * ISIS label for a SELENE TC image |
| `data/raw/reference/jaxa_selene_tc/TC1S2B0_01_05601N004E0998/TC1S2B0_01_05601N004E0998.jpg` | binary | * SELENE Terrain Camera image (JPEG) |
| `data/raw/reference/jaxa_selene_tc/TC1S2B0_01_05601N004E0998/TC1S2B0_01_05601N004E0998.lbl` | 147 | * PDS label for a SELENE TC image |
| `data/raw/reference/jaxa_selene_tc/TC1S2B0_01_05601N004E0998/TC1S2B0_01_05601N004E0998.tif` | binary | * SELENE Terrain Camera image (GeoTIFF) |
| `data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.IMG` | binary | * LROC NAC_DTM VIKRAMSITE1 data product (per PROVENANCE.json source) |
| `data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml` | 238 | * PDS4 label for an LROC NAC_DTM VIKRAMSITE1 product |
| `data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1443025251_100CM.IMG` | binary | * LROC NAC_DTM VIKRAMSITE1 data product (per PROVENANCE.json source) |
| `data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1443025251_100CM.xml` | 238 | * PDS4 label for an LROC NAC_DTM VIKRAMSITE1 product |
| `data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1.TIF` | binary | * LROC NAC_DTM VIKRAMSITE1 data product (per PROVENANCE.json source) |
| `data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1.xml` | 248 | * PDS4 label for an LROC NAC_DTM VIKRAMSITE1 product |
| `data/raw/reference/lro_nac_vikram/PROVENANCE.json` | 70 | * Provenance record for the downloaded reference data (source, URL, access method) |
| `data/raw/reference/lro_wac/lro_wac_100m_lon21-24E_lat18-21N.json` | 15 | * LRO WAC 100 m mosaic crop sidecar JSON (source URL, target box) |
| `data/raw/reference/lro_wac/lro_wac_100m_lon21-24E_lat18-21N.tif` | binary | * LRO WAC 100 m mosaic crop GeoTIFF |
| `data/raw/reference/lro_wac/lro_wac_100m_lon37.5-39E_lat8.9-10.9N.json` | 14 | * LRO WAC 100 m mosaic crop sidecar JSON (source URL, target box) |
| `data/raw/reference/lro_wac/lro_wac_100m_lon37.5-39E_lat8.9-10.9N.tif` | binary | * LRO WAC 100 m mosaic crop GeoTIFF |
| `data/raw/reference/lro_wac/lro_wac_100m_lon99.3-101.4E_lat-0.5-1.3N.json` | 16 | * LRO WAC 100 m mosaic crop sidecar JSON (source URL, target box) |
| `data/raw/reference/lro_wac/lro_wac_100m_lon99.3-101.4E_lat-0.5-1.3N.tif` | binary | * LRO WAC 100 m mosaic crop GeoTIFF |
| `dist/chandralipi-data-processed-20260909.tar.zst` | binary | * zstd tar archive of `data/` (named per `scripts/pack_data.sh` output pattern) |
| `docs/CROSS_MODAL_IIRS.md` | 249 | Matching IIRS against panchromatic imagery: architecture and plan |
| `docs/DATA_ACQUISITION.md` | 262 | Getting ISRO and NASA data for the same patch of the Moon |
| `docs/DEMO_SCRIPT.md` | 142 | 2–3 minute demo video script |
| `docs/INTERNALS_QNA.md` | 206 | Internals Q&A — anticipated attacks and direct answers |
| `docs/INTERNALS_SCRIPT.md` | 131 | 5-minute pitch script (spoken, casual) |
| `docs/MAKHARIA_PARITY.md` | 189 | Benchmark reconciliation against Makharia et al. (arXiv:2509.04775) |
| `docs/REPORT_SECTION.md` | 147 | Results, and how they relate to prior work |
| `docs/VRAM_CONSTRAINTS.md` | 111 | Memory constraints on an 8 GB RTX 4060 |
| `.env` | 1 | * Local environment variables (gitignored; contents not reproduced) |
| `docs/plan/FABLE_REVIEW.md` | 467 | Review brief for Fable |
| `gdocs/01_WHY_THIS_PROBLEM_STATEMENT_EXISTS.md` | 226 | 01 · Why this problem statement exists |
| `gdocs/02_PURPOSE_OF_THE_PROJECT.md` | 201 | 02 · The purpose of this project |
| `gdocs/03_WHY_I_CHOSE_THIS_PROJECT.md` | 137 | 03 · Why we chose this project — the story we tell, and why it is true |
| `gdocs/04_APPROACH_BENEFITS_ALTERNATIVES_ISRO_ALIGNMENT.md` | 244 | 04 · Our approach, its benefits, the alternatives, and alignment with ISRO's requirement |
| `gdocs/05_FEASIBILITY.md` | 173 | 05 · Feasibility of the project |
| `.gitignore` | 41 | * Git ignore rules |
| `notebooks/.gitkeep` | 0 | * Empty placeholder keeping `notebooks/` in git |
| `old_assets/assets/chandrayaan2_orbiter.jpg` | binary | * Image (Chandrayaan-2 orbiter) |
| `old_assets/assets/chandrayaan2.png` | binary | * Image (Chandrayaan-2) |
| `old_assets/assets/cuda.png` | binary | * Logo image (CUDA) |
| `old_assets/assets/gdal.png` | binary | * Logo image (GDAL) |
| `old_assets/assets/gdal.svg` | 0 | * Logo SVG (GDAL); single line, no trailing newline |
| `old_assets/assets/isro.png` | binary | * Logo image (ISRO) |
| `old_assets/assets/isro.svg` | 32 | * Logo SVG (ISRO) |
| `old_assets/assets/jaxa.png` | binary | * Logo image (JAXA) |
| `old_assets/assets/jaxa.svg` | 34 | * Logo SVG (JAXA) |
| `old_assets/assets/nasa.png` | binary | * Logo image (NASA) |
| `old_assets/assets/nasa.svg` | 52 | * Logo SVG (NASA) |
| `old_assets/assets/numpy.png` | binary | * Logo image (NumPy) |
| `old_assets/assets/numpy.svg` | 0 | * Logo SVG (NumPy); single line, no trailing newline |
| `old_assets/assets/nvidia.png` | binary | * Logo image (NVIDIA) |
| `old_assets/assets/nvidia.svg` | 0 | * Logo SVG (NVIDIA); single line, no trailing newline |
| `old_assets/assets/ohrc_vikram.png` | binary | * Image (OHRC / Vikram) |
| `old_assets/assets/opencv.png` | binary | * Logo image (OpenCV) |
| `old_assets/assets/opencv.svg` | 0 | * Logo SVG (OpenCV); single line, no trailing newline |
| `old_assets/assets/python.png` | binary | * Logo image (Python) |
| `old_assets/assets/python.svg` | 0 | * Logo SVG (Python); single line, no trailing newline |
| `old_assets/assets/pytorch.png` | binary | * Logo image (PyTorch) |
| `old_assets/assets/pytorch.svg` | 0 | * Logo SVG (PyTorch); single line, no trailing newline |
| `old_assets/assets/SOURCES.md` | 33 | assets/ — logo sources |
| `old_assets/assets/streamlit.png` | binary | * Logo image (Streamlit) |
| `old_assets/assets/streamlit.svg` | 0 | * Logo SVG (Streamlit); single line, no trailing newline |
| `old_assets/P26083.txt` | 18 | * SIH problem statement 26083 text (Extreme Heatwave Early Warning and Human Thermal Stress Index) |
| `old_assets/P26142.txt` | 18 | * SIH problem statement 26142 text (Deep Learning Based Super Resolution Mapping) |
| `old_assets/P26166_report.md` | 213 | P26166 — Multi-modal, Sun-Angle and Scale-Invariant Image Correspondence Using Chandrayaan-2 Optical Images |
| `old_assets/P26166_SIH_Idea_PPT.pptx` | binary | * PowerPoint deck (P26166 idea presentation) |
| `old_assets/P26166_slide_idea.md` | 88 | P26166 — SIH 2026 Idea Presentation: Slide-by-Slide Content |
| `old_assets/P26166.txt` | 29 | * SIH problem statement 26166 text (this project's problem statement) |
| `old_assets/P26167.txt` | 75 | * SIH problem statement 26167 text (SatQuery AI) |
| `old_assets/sih_guidelines.pdf` | binary | * PDF (SIH guidelines) |
| `old_assets/sih_pptx_template.pptx` | binary | * PowerPoint template (SIH) |
| `pyproject.toml` | 72 | * Python package metadata (`lunar-reg` 0.1.0), deps, pytest/ruff/mypy config |
| `README.md` | 751 | lunar-reg — Illumination-Robust Multi-Sensor Lunar Image Registration |
| `docs/project/README_TITLE.md` | 1823 | SIH26166 — Understanding the Problem Statement |
| `scripts/build_demo_results.py` | 130 | Run the pipeline over a spread of generated scenes and persist the results |
| `scripts/demo.py` | 156 | One-pair end-to-end demo, for the video and the internal-round submission |
| `scripts/export_web_data.py` | 207 | Export stored pipeline results for the showcase site |
| `scripts/fetch_catalogue.py` | 483 | Build a product manifest from archive *catalogues*, without downloading imagery |
| `scripts/make_contour_background.py` | 131 | Generate the site's background: real lunar contour lines |
| `scripts/pack_data.sh` | 77 | Bundle the data/ tree into a single archive to carry to another machine |
| `scripts/README.md` | 99 | scripts/ |
| `scripts/reindex_results.py` | 88 | Rebuild ``data/processed/results/index.parquet`` from the ``.npz`` files on disk |
| `scripts/run_dashboard.sh` | 25 | Launch the Streamlit results browser |
| `scripts/run_vikram.py` | 401 | First real Chandrayaan-2 OHRC <-> LRO NAC registration: the Vikram landing site |
| `scripts/setup.sh` | 148 | One-shot bootstrap for a fresh machine: virtualenv -> dependencies -> data -> verification |
| `scripts/up.sh` | 125 | One command: optional venv + deps + data, fresh static export, then the Streamlit dashboard and React showcase site side by side (paraphrased from header comment) |
| `src/lunar_reg/align/estimate.py` | 115 | Geometric transform estimation |
| `src/lunar_reg/align/__init__.py` | 25 | Transform estimation, sub-pixel refinement, and product generation |
| `src/lunar_reg/align/refine.py` | 395 | Sub-pixel refinement of the geometric transform |
| `src/lunar_reg/align/warp.py` | 172 | Applying a transform to produce the registered product |
| `src/lunar_reg/cli.py` | 319 | Command-line entry point |
| `src/lunar_reg/constants.py` | 90 | Physical and mission constants |
| `src/lunar_reg/device.py` | 254 | Device selection and VRAM budgeting |
| `src/lunar_reg/eval/conditioning.py` | 277 | How well a correspondence set pins down the transform, measured in pixels |
| `src/lunar_reg/eval/error_budget.py` | 341 | Stage-by-stage attribution of registration error |
| `src/lunar_reg/eval/__init__.py` | 53 | Evaluation metrics: accuracy, robustness, and spatial distribution |
| `src/lunar_reg/eval/metrics.py` | 89 | Registration accuracy metrics |
| `src/lunar_reg/eval/scenes.py` | 245 | Synthetic lunar scenes with controllable illumination |
| `src/lunar_reg/eval/uniformity.py` | 302 | Spatial-uniformity metric for correspondence sets |
| `src/lunar_reg/ingest/fieldmap.py` | 272 | Declarative map from PDS4 label elements to manifest fields |
| `src/lunar_reg/ingest/footprint.py` | 120 | Footprint geometry and overlap detection between products |
| `src/lunar_reg/ingest/geometry_grid.py` | 972 | The per-observation GEOMETRY grid that ships inside every Chandrayaan-2 product |
| `src/lunar_reg/ingest/__init__.py` | 114 | Reading PDS4/PDS3 products and turning them into tractable work units |
| `src/lunar_reg/ingest/lro.py` | 349 | LRO NAC reference products |
| `src/lunar_reg/ingest/manifest.py` | 201 | One table describing every product available to the pipeline |
| `src/lunar_reg/ingest/overlap.py` | 1186 | Footprint-overlap detection between manifests, and cropping to the shared region |
| `src/lunar_reg/ingest/pds4.py` | 369 | PDS4 product access for OHRC / TMC-2 / IIRS |
| `src/lunar_reg/ingest/probe.py` | 182 | Discover a real label's structure instead of guessing at it |
| `src/lunar_reg/ingest/pseudo_gt.py` | 642 | Weak ground truth for cross-sensor pairs, from georeferencing alone |
| `src/lunar_reg/ingest/tiling.py` | 130 | Tiling large products into matcher-sized work units |
| `src/lunar_reg/__init__.py` | 10 | Illumination-robust multi-sensor lunar image registration (SIH26166) |
| `src/lunar_reg/match/base.py` | 100 | Common matcher interface |
| `src/lunar_reg/match/benchmark.py` | 300 | Memory benchmark for the learned matchers |
| `src/lunar_reg/match/classical.py` | 244 | Training-free matchers behind one interface |
| `src/lunar_reg/match/__init__.py` | 30 | Correspondence finding, classical and learned |
| `src/lunar_reg/match/learned.py` | 243 | Learned matchers (LoFTR, DISK+LightGlue) via kornia |
| `src/lunar_reg/match/loftr.py` | 188 | LoFTR: detector-free dense matching, via kornia |
| `src/lunar_reg/match/memory.py` | 255 | Empirical memory measurement for matcher inference |
| `src/lunar_reg/match/rift2/descriptor.py` | 124 | RIFT feature description: the 6x6 x N_o MIM histogram descriptor |
| `src/lunar_reg/match/rift2/__init__.py` | 43 | RIFT2: Radiation-variation Insensitive Feature Transform, version 2 |
| `src/lunar_reg/match/rift2/matcher.py` | 216 | RIFT2 detection and matching, wired to this project's Matcher interface |
| `src/lunar_reg/match/rift2/mim.py` | 126 | Maximum Index Map, and RIFT2's rotation-invariant recoding |
| `src/lunar_reg/match/rift2/phase.py` | 236 | Log-Gabor filter bank, phase congruency, and PC moments |
| `src/lunar_reg/match/rift2_status.py` | 73 | Decision record: why RIFT2 is a clean-room implementation |
| `src/lunar_reg/match/stitch.py` | 194 | Stitching tile-wise matches into one whole-image correspondence set |
| `src/lunar_reg/match/superglue.py` | 289 | SuperPoint + SuperGlue, and its Apache-2.0 alternative |
| `src/lunar_reg/match/tiled.py` | 238 | Tile-wise matching orchestration |
| `src/lunar_reg/pipeline.py` | 267 | End-to-end registration of one pair, from images to a stored result |
| `src/lunar_reg/preprocess/config.py` | 197 | Per-step configuration for the preprocessing pipeline |
| `src/lunar_reg/preprocess/georeference.py` | 153 | Georeferencing: put source and reference into one spatial frame |
| `src/lunar_reg/preprocess/hyperspectral.py` | 203 | IIRS band reduction |
| `src/lunar_reg/preprocess/__init__.py` | 104 | Preprocessing: the Makharia et al. (arXiv:2509.04775) pipeline, ablatable |
| `src/lunar_reg/preprocess/params.py` | 244 | Preprocessing parameters, each tagged with where its value came from |
| `src/lunar_reg/preprocess/pipeline.py` | 316 | The Makharia et al. preprocessing pipeline, step by step and fully ablatable |
| `src/lunar_reg/preprocess/radiometric.py` | 218 | Intensity conditioning: normalisation, CLAHE, and the paper's enhancement steps |
| `src/lunar_reg/preprocess/resample.py` | 100 | Scale alignment between sensors |
| `src/lunar_reg/preprocess/shadow.py` | 184 | Shadow normalisation for extreme sun-angle cases |
| `src/lunar_reg/results.py` | 341 | Per-pair result persistence |
| `src/lunar_reg/viz/figures.py` | 201 | Rendered views of a registered pair, as plain RGB arrays |
| `src/lunar_reg/viz/__init__.py` | 5 | Diagnostic and reporting figures |
| `src/lunar_reg/viz/plots.py` | 129 | Diagnostic figures |
| `docs/backlog/TBD_phase_1.md` | 198 | Phase 1 — Close out classical/neural results (pre-cluster) |
| `docs/backlog/TBD_phase_2.md` | 47 | Phase 2 — Cluster computing, Stage 1: one machine, one real GPU |
| `docs/backlog/TBD_phase_3.md` | 69 | Phase 3 — Cluster computing, Stage 2: one machine, N GPUs |
| `docs/backlog/TBD_phase_4.md` | 71 | Phase 4 — Cluster computing, Stage 3: many machines |
| `docs/backlog/TBD_phase_5.md` | 37 | Phase 5 — Optional: surfacing cluster execution in the dashboards |
| `docs/backlog/TBDs.md` | 47 | TBDs — remaining work, phase by phase |
| `tests/conftest.py` | 39 | Shared fixtures |
| `tests/test_align.py` | 77 | Transform estimation and the sub-pixel path |
| `tests/test_conditioning.py` | 160 | Stress tests for the conditioning metric, including the layouts that broke U |
| `tests/test_device.py` | 77 | The VRAM budget model is what stops the pipeline OOMing; check it holds |
| `tests/test_eval.py` | 120 | Metrics are the submission's deliverable, so they need to be right |
| `tests/test_footprint.py` | 53 | Footprint overlap gates which pairs are worth matching at all |
| `tests/test_geometry_grid.py` | 545 | The per-observation geometry grid: parsing, failure taxonomy, and inversion |
| `tests/test_ingest_labels.py` | 473 | Label parsing, manifest building, and the provenance machinery |
| `tests/test_match_base.py` | 59 | MatchResult is the common currency between every matcher and the metrics |
| `tests/test_matchers_and_refinement.py` | 460 | Classical matchers, sub-pixel refinement, and the uniformity metric |
| `tests/test_overlap.py` | 826 | Footprint overlap, its degenerate cases, and cropping |
| `tests/test_pipeline.py` | 136 | End-to-end pipeline runs on synthetic data |
| `tests/test_preprocess_pipeline.py` | 478 | The Makharia et al. pipeline: step behaviour, toggling, and provenance |
| `tests/test_preprocess.py` | 102 | Preprocessing defaults come from the benchmark paper; pin their behaviour |
| `tests/test_pseudo_gt.py` | 175 | Tests for georeference-derived pseudo ground truth |
| `tests/test_registered_export.py` | 62 | Writing a registered product as a georeferenced GeoTIFF |
| `tests/test_results_and_pipeline.py` | 300 | Per-pair persistence, the end-to-end runner, and the shared figure renderers |
| `tests/test_rift2.py` | 353 | RIFT2: clean-room implementation checks |
| `tests/test_scenes_and_budget.py` | 137 | Synthetic illumination scenes and the error-attribution harness |
| `tests/test_tiling.py` | 75 | Tiling is what keeps OHRC inside the memory budget, so its edges matter |
| `docs/project/TIMELINE.md` | 195 | Development timeline |
| `udocs/00_ROADMAP.md` | 97 | Roadmap — how to understand this project |
| `udocs/01_WHAT_AND_WHY.md` | 150 | 01 · What this project does, and why |
| `udocs/10_PRIMER_geodesy.md` | 160 | 10 · Latitude and longitude are not x and y |
| `udocs/11_PRIMER_projections.md` | 120 | 11 · Flattening a sphere, and what it costs |
| `udocs/12_PRIMER_footprints.md` | 167 | 12 · Footprints — where an image actually is |
| `udocs/13_PRIMER_sensors.md` | 167 | 13 · How these cameras actually work |
| `udocs/20_PRIMER_transforms.md` | 150 | 20 · Transforms — the thing registration actually produces |
| `udocs/21_PRIMER_matching.md` | 172 | 21 · Finding the same point in two pictures |
| `udocs/22_PRIMER_robust_fitting.md` | 171 | 22 · Fitting a transform when some of your data is wrong |
| `udocs/23_PRIMER_metrics.md` | 236 | 23 · Why RMSE lies, and what we measure instead |
| `udocs/30_PRIMER_pds4_and_pradan.md` | 181 | 30 · How the data arrives: PDS4 and PRADAN |
| `udocs/31_PRIMER_instruments.md` | 171 | 31 · The four cameras |
| `udocs/40_the_pipeline.md` | 196 | 40 · Walking through the code |
| `udocs/50_findings.md` | 291 | 50 · What we actually measured |
| `udocs/60_MATHS.md` | 494 | 60 · Every piece of mathematics this project uses |
| `udocs/61_ML_and_where_it_fits.md` | 240 | 61 · Is there machine learning in this? Where could more of it go? |
| `udocs/70_SYSTEM_DESIGN_distributed_gpu.md` | 365 | 70 · System design — running this on many GPUs |
| `udocs/90_GLOSSARY.md` | 120 | 90 · Glossary |
| `web/DESIGN.md` | 158 | Chandralipi — design system |
| `web/dist/assets/Architecture-pAxC-Q5-.js` | 1 | * Vite build output: bundled JS chunk (`Architecture`) |
| `web/dist/assets/Dashboard-DPqDAF7A.js` | 2 | * Vite build output: bundled JS chunk (`Dashboard`) |
| `web/dist/assets/Home-B1J8BPZl.js` | 3873 | * Vite build output: bundled JS chunk (`Home`) |
| `web/dist/assets/index-BeecwOhy.js` | 68 | * Vite build output: bundled JS chunk (`index`) |
| `web/dist/assets/index-Y1zyM-mB.css` | 1 | * Vite build output: bundled CSS (`index`) |
| `web/dist/assets/Resources-DquSNZ6N.js` | 1 | * Vite build output: bundled JS chunk (`Resources`) |
| `web/dist/assets/Reveal-oXfXj1tH.js` | 1 | * Vite build output: bundled JS chunk (`Reveal`) |
| `web/dist/data/pairs/IIRS-LRO_WAC_hard-30deg_akaze_checker.jpg` | binary | * checkerboard overlay JPEG for result `IIRS-LRO_WAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_hard-30deg_akaze_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `IIRS-LRO_WAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_hard-30deg_akaze_matches.jpg` | binary | * side-by-side matches JPEG for result `IIRS-LRO_WAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_hard-30deg_akaze_ref.jpg` | binary | * reference image JPEG for result `IIRS-LRO_WAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_hard-30deg_akaze_src.jpg` | binary | * source image JPEG for result `IIRS-LRO_WAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_hard-30deg_asift_checker.jpg` | binary | * checkerboard overlay JPEG for result `IIRS-LRO_WAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_hard-30deg_asift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `IIRS-LRO_WAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_hard-30deg_asift_matches.jpg` | binary | * side-by-side matches JPEG for result `IIRS-LRO_WAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_hard-30deg_asift_ref.jpg` | binary | * reference image JPEG for result `IIRS-LRO_WAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_hard-30deg_asift_src.jpg` | binary | * source image JPEG for result `IIRS-LRO_WAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_akaze_checker.jpg` | binary | * checkerboard overlay JPEG for result `IIRS-LRO_WAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_akaze_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `IIRS-LRO_WAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_akaze_matches.jpg` | binary | * side-by-side matches JPEG for result `IIRS-LRO_WAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_akaze_ref.jpg` | binary | * reference image JPEG for result `IIRS-LRO_WAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_akaze_src.jpg` | binary | * source image JPEG for result `IIRS-LRO_WAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_asift_checker.jpg` | binary | * checkerboard overlay JPEG for result `IIRS-LRO_WAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_asift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `IIRS-LRO_WAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_asift_matches.jpg` | binary | * side-by-side matches JPEG for result `IIRS-LRO_WAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_asift_ref.jpg` | binary | * reference image JPEG for result `IIRS-LRO_WAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_asift_src.jpg` | binary | * source image JPEG for result `IIRS-LRO_WAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_sift_checker.jpg` | binary | * checkerboard overlay JPEG for result `IIRS-LRO_WAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_sift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `IIRS-LRO_WAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_sift_matches.jpg` | binary | * side-by-side matches JPEG for result `IIRS-LRO_WAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_sift_ref.jpg` | binary | * reference image JPEG for result `IIRS-LRO_WAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_mild-15deg_sift_src.jpg` | binary | * source image JPEG for result `IIRS-LRO_WAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_akaze_checker.jpg` | binary | * checkerboard overlay JPEG for result `IIRS-LRO_WAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_akaze_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `IIRS-LRO_WAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_akaze_matches.jpg` | binary | * side-by-side matches JPEG for result `IIRS-LRO_WAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_akaze_ref.jpg` | binary | * reference image JPEG for result `IIRS-LRO_WAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_akaze_src.jpg` | binary | * source image JPEG for result `IIRS-LRO_WAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_asift_checker.jpg` | binary | * checkerboard overlay JPEG for result `IIRS-LRO_WAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_asift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `IIRS-LRO_WAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_asift_matches.jpg` | binary | * side-by-side matches JPEG for result `IIRS-LRO_WAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_asift_ref.jpg` | binary | * reference image JPEG for result `IIRS-LRO_WAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_asift_src.jpg` | binary | * source image JPEG for result `IIRS-LRO_WAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_sift_checker.jpg` | binary | * checkerboard overlay JPEG for result `IIRS-LRO_WAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_sift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `IIRS-LRO_WAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_sift_matches.jpg` | binary | * side-by-side matches JPEG for result `IIRS-LRO_WAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_sift_ref.jpg` | binary | * reference image JPEG for result `IIRS-LRO_WAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/IIRS-LRO_WAC_same-sun_sift_src.jpg` | binary | * source image JPEG for result `IIRS-LRO_WAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_akaze_checker.jpg` | binary | * checkerboard overlay JPEG for result `OHRC-LRO_NAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_akaze_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `OHRC-LRO_NAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_akaze_matches.jpg` | binary | * side-by-side matches JPEG for result `OHRC-LRO_NAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_akaze_ref.jpg` | binary | * reference image JPEG for result `OHRC-LRO_NAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_akaze_src.jpg` | binary | * source image JPEG for result `OHRC-LRO_NAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_asift_checker.jpg` | binary | * checkerboard overlay JPEG for result `OHRC-LRO_NAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_asift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `OHRC-LRO_NAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_asift_matches.jpg` | binary | * side-by-side matches JPEG for result `OHRC-LRO_NAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_asift_ref.jpg` | binary | * reference image JPEG for result `OHRC-LRO_NAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_asift_src.jpg` | binary | * source image JPEG for result `OHRC-LRO_NAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_sift_checker.jpg` | binary | * checkerboard overlay JPEG for result `OHRC-LRO_NAC_hard-30deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_sift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `OHRC-LRO_NAC_hard-30deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_sift_matches.jpg` | binary | * side-by-side matches JPEG for result `OHRC-LRO_NAC_hard-30deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_sift_ref.jpg` | binary | * reference image JPEG for result `OHRC-LRO_NAC_hard-30deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_hard-30deg_sift_src.jpg` | binary | * source image JPEG for result `OHRC-LRO_NAC_hard-30deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_akaze_checker.jpg` | binary | * checkerboard overlay JPEG for result `OHRC-LRO_NAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_akaze_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `OHRC-LRO_NAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_akaze_matches.jpg` | binary | * side-by-side matches JPEG for result `OHRC-LRO_NAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_akaze_ref.jpg` | binary | * reference image JPEG for result `OHRC-LRO_NAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_akaze_src.jpg` | binary | * source image JPEG for result `OHRC-LRO_NAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_asift_checker.jpg` | binary | * checkerboard overlay JPEG for result `OHRC-LRO_NAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_asift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `OHRC-LRO_NAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_asift_matches.jpg` | binary | * side-by-side matches JPEG for result `OHRC-LRO_NAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_asift_ref.jpg` | binary | * reference image JPEG for result `OHRC-LRO_NAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_asift_src.jpg` | binary | * source image JPEG for result `OHRC-LRO_NAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_sift_checker.jpg` | binary | * checkerboard overlay JPEG for result `OHRC-LRO_NAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_sift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `OHRC-LRO_NAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_sift_matches.jpg` | binary | * side-by-side matches JPEG for result `OHRC-LRO_NAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_sift_ref.jpg` | binary | * reference image JPEG for result `OHRC-LRO_NAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_mild-15deg_sift_src.jpg` | binary | * source image JPEG for result `OHRC-LRO_NAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_akaze_checker.jpg` | binary | * checkerboard overlay JPEG for result `OHRC-LRO_NAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_akaze_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `OHRC-LRO_NAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_akaze_matches.jpg` | binary | * side-by-side matches JPEG for result `OHRC-LRO_NAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_akaze_ref.jpg` | binary | * reference image JPEG for result `OHRC-LRO_NAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_akaze_src.jpg` | binary | * source image JPEG for result `OHRC-LRO_NAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_asift_checker.jpg` | binary | * checkerboard overlay JPEG for result `OHRC-LRO_NAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_asift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `OHRC-LRO_NAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_asift_matches.jpg` | binary | * side-by-side matches JPEG for result `OHRC-LRO_NAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_asift_ref.jpg` | binary | * reference image JPEG for result `OHRC-LRO_NAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_asift_src.jpg` | binary | * source image JPEG for result `OHRC-LRO_NAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_sift_checker.jpg` | binary | * checkerboard overlay JPEG for result `OHRC-LRO_NAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_sift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `OHRC-LRO_NAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_sift_matches.jpg` | binary | * side-by-side matches JPEG for result `OHRC-LRO_NAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_sift_ref.jpg` | binary | * reference image JPEG for result `OHRC-LRO_NAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/OHRC-LRO_NAC_same-sun_sift_src.jpg` | binary | * source image JPEG for result `OHRC-LRO_NAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_akaze_checker.jpg` | binary | * checkerboard overlay JPEG for result `TMC2-LRO_NAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_akaze_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `TMC2-LRO_NAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_akaze_matches.jpg` | binary | * side-by-side matches JPEG for result `TMC2-LRO_NAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_akaze_ref.jpg` | binary | * reference image JPEG for result `TMC2-LRO_NAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_akaze_src.jpg` | binary | * source image JPEG for result `TMC2-LRO_NAC_hard-30deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_asift_checker.jpg` | binary | * checkerboard overlay JPEG for result `TMC2-LRO_NAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_asift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `TMC2-LRO_NAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_asift_matches.jpg` | binary | * side-by-side matches JPEG for result `TMC2-LRO_NAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_asift_ref.jpg` | binary | * reference image JPEG for result `TMC2-LRO_NAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_asift_src.jpg` | binary | * source image JPEG for result `TMC2-LRO_NAC_hard-30deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_sift_checker.jpg` | binary | * checkerboard overlay JPEG for result `TMC2-LRO_NAC_hard-30deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_sift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `TMC2-LRO_NAC_hard-30deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_sift_matches.jpg` | binary | * side-by-side matches JPEG for result `TMC2-LRO_NAC_hard-30deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_sift_ref.jpg` | binary | * reference image JPEG for result `TMC2-LRO_NAC_hard-30deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_hard-30deg_sift_src.jpg` | binary | * source image JPEG for result `TMC2-LRO_NAC_hard-30deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_akaze_checker.jpg` | binary | * checkerboard overlay JPEG for result `TMC2-LRO_NAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_akaze_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `TMC2-LRO_NAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_akaze_matches.jpg` | binary | * side-by-side matches JPEG for result `TMC2-LRO_NAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_akaze_ref.jpg` | binary | * reference image JPEG for result `TMC2-LRO_NAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_akaze_src.jpg` | binary | * source image JPEG for result `TMC2-LRO_NAC_mild-15deg_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_asift_checker.jpg` | binary | * checkerboard overlay JPEG for result `TMC2-LRO_NAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_asift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `TMC2-LRO_NAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_asift_matches.jpg` | binary | * side-by-side matches JPEG for result `TMC2-LRO_NAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_asift_ref.jpg` | binary | * reference image JPEG for result `TMC2-LRO_NAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_asift_src.jpg` | binary | * source image JPEG for result `TMC2-LRO_NAC_mild-15deg_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_sift_checker.jpg` | binary | * checkerboard overlay JPEG for result `TMC2-LRO_NAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_sift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `TMC2-LRO_NAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_sift_matches.jpg` | binary | * side-by-side matches JPEG for result `TMC2-LRO_NAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_sift_ref.jpg` | binary | * reference image JPEG for result `TMC2-LRO_NAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_mild-15deg_sift_src.jpg` | binary | * source image JPEG for result `TMC2-LRO_NAC_mild-15deg_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_akaze_checker.jpg` | binary | * checkerboard overlay JPEG for result `TMC2-LRO_NAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_akaze_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `TMC2-LRO_NAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_akaze_matches.jpg` | binary | * side-by-side matches JPEG for result `TMC2-LRO_NAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_akaze_ref.jpg` | binary | * reference image JPEG for result `TMC2-LRO_NAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_akaze_src.jpg` | binary | * source image JPEG for result `TMC2-LRO_NAC_same-sun_akaze` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_asift_checker.jpg` | binary | * checkerboard overlay JPEG for result `TMC2-LRO_NAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_asift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `TMC2-LRO_NAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_asift_matches.jpg` | binary | * side-by-side matches JPEG for result `TMC2-LRO_NAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_asift_ref.jpg` | binary | * reference image JPEG for result `TMC2-LRO_NAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_asift_src.jpg` | binary | * source image JPEG for result `TMC2-LRO_NAC_same-sun_asift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_sift_checker.jpg` | binary | * checkerboard overlay JPEG for result `TMC2-LRO_NAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_sift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `TMC2-LRO_NAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_sift_matches.jpg` | binary | * side-by-side matches JPEG for result `TMC2-LRO_NAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_sift_ref.jpg` | binary | * reference image JPEG for result `TMC2-LRO_NAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/pairs/TMC2-LRO_NAC_same-sun_sift_src.jpg` | binary | * source image JPEG for result `TMC2-LRO_NAC_same-sun_sift` (Vite build copy of a `web/public/data/pairs/` export) |
| `web/dist/data/results.json` | 710 | * Vite build copy of a `results.json` snapshot |
| `web/dist/index.html` | 36 | * Vite build output: HTML entry |
| `web/dist/textures/lunar-contours.svg` | 0 | * Vite build copy of `web/public/textures/lunar-contours.svg` |
| `web/dist/textures/moon_color_2k.jpg` | binary | * Vite build copy of `web/public/textures/moon_color_2k.jpg` |
| `web/dist/textures/moon_displacement.jpg` | binary | * Vite build copy of `web/public/textures/moon_displacement.jpg` |
| `web/index.html` | 35 | * Vite HTML entry point for the showcase site |
| `web/package.json` | 28 | * npm manifest for `lunar-reg-showcase` (scripts: dev, build, preview) |
| `web/package-lock.json` | 2718 | * npm lockfile |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_akaze_checker.jpg` | binary | * checkerboard overlay JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_akaze` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_akaze_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_akaze` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_akaze_matches.jpg` | binary | * side-by-side matches JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_akaze` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_akaze_ref.jpg` | binary | * reference image JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_akaze` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_akaze_src.jpg` | binary | * source image JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_akaze` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_asift_checker.jpg` | binary | * checkerboard overlay JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_asift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_asift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_asift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_asift_matches.jpg` | binary | * side-by-side matches JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_asift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_asift_ref.jpg` | binary | * reference image JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_asift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_asift_src.jpg` | binary | * source image JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_asift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue_checker.jpg` | binary | * checkerboard overlay JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue_matches.jpg` | binary | * side-by-side matches JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue_ref.jpg` | binary | * reference image JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue_src.jpg` | binary | * source image JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_lightglue` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_loftr_checker.jpg` | binary | * checkerboard overlay JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_loftr` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_loftr_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_loftr` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_loftr_matches.jpg` | binary | * side-by-side matches JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_loftr` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_loftr_ref.jpg` | binary | * reference image JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_loftr` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_loftr_src.jpg` | binary | * source image JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_loftr` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_sift_checker.jpg` | binary | * checkerboard overlay JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_sift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_sift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_sift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_sift_matches.jpg` | binary | * side-by-side matches JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_sift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_sift_ref.jpg` | binary | * reference image JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_sift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-JAXA_SELENE_TC_sift_src.jpg` | binary | * source image JPEG for result `JAXA_SELENE_TC-JAXA_SELENE_TC_sift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_asift_checker.jpg` | binary | * checkerboard overlay JPEG for result `JAXA_SELENE_TC-LRO_WAC_asift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_asift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `JAXA_SELENE_TC-LRO_WAC_asift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_asift_matches.jpg` | binary | * side-by-side matches JPEG for result `JAXA_SELENE_TC-LRO_WAC_asift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_asift_ref.jpg` | binary | * reference image JPEG for result `JAXA_SELENE_TC-LRO_WAC_asift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_asift_src.jpg` | binary | * source image JPEG for result `JAXA_SELENE_TC-LRO_WAC_asift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_lightglue_checker.jpg` | binary | * checkerboard overlay JPEG for result `JAXA_SELENE_TC-LRO_WAC_lightglue` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_lightglue_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `JAXA_SELENE_TC-LRO_WAC_lightglue` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_lightglue_matches.jpg` | binary | * side-by-side matches JPEG for result `JAXA_SELENE_TC-LRO_WAC_lightglue` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_lightglue_ref.jpg` | binary | * reference image JPEG for result `JAXA_SELENE_TC-LRO_WAC_lightglue` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_lightglue_src.jpg` | binary | * source image JPEG for result `JAXA_SELENE_TC-LRO_WAC_lightglue` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_loftr_checker.jpg` | binary | * checkerboard overlay JPEG for result `JAXA_SELENE_TC-LRO_WAC_loftr` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_loftr_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `JAXA_SELENE_TC-LRO_WAC_loftr` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_loftr_matches.jpg` | binary | * side-by-side matches JPEG for result `JAXA_SELENE_TC-LRO_WAC_loftr` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_loftr_ref.jpg` | binary | * reference image JPEG for result `JAXA_SELENE_TC-LRO_WAC_loftr` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_loftr_src.jpg` | binary | * source image JPEG for result `JAXA_SELENE_TC-LRO_WAC_loftr` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_sift_checker.jpg` | binary | * checkerboard overlay JPEG for result `JAXA_SELENE_TC-LRO_WAC_sift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_sift_cond.jpg` | binary | * conditioning heatmap overlay JPEG for result `JAXA_SELENE_TC-LRO_WAC_sift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_sift_matches.jpg` | binary | * side-by-side matches JPEG for result `JAXA_SELENE_TC-LRO_WAC_sift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_sift_ref.jpg` | binary | * reference image JPEG for result `JAXA_SELENE_TC-LRO_WAC_sift` (`scripts/export_web_data.py` output) |
| `web/public/data/pairs/JAXA_SELENE_TC-LRO_WAC_sift_src.jpg` | binary | * source image JPEG for result `JAXA_SELENE_TC-LRO_WAC_sift` (`scripts/export_web_data.py` output) |
| `web/public/data/results.json` | 251 | * Static results snapshot for the showcase site (`scripts/export_web_data.py` default `--out`) |
| `web/public/textures/lunar-contours.svg` | 0 | * Contour-line SVG background; single line, no trailing newline (default `--out` of `scripts/make_contour_background.py`) |
| `web/public/textures/moon_color_2k.jpg` | binary | * Moon colour texture image |
| `web/public/textures/moon_displacement.jpg` | binary | * Moon displacement texture image |
| `web/README.md` | 119 | Chandralipi — showcase site |
| `web/src/App.jsx` | 131 | * React root component (routes, theme handling) |
| `web/src/components/Diagram.jsx` | 137 | Inline SVG diagram primitives |
| `web/src/components/Moon.jsx` | 139 | The Moon, rendered as a plate rather than a hero |
| `web/src/components/Reveal.jsx` | 61 | Scroll reveal |
| `web/src/components/theme.js` | 42 | Theme selection |
| `web/src/main.jsx` | 16 | * React entry point (mounts app under HashRouter) |
| `web/src/pages/Architecture.jsx` | 225 | * Page component: Architecture |
| `web/src/pages/Dashboard.jsx` | 318 | * Page component: Dashboard (results view) |
| `web/src/pages/Home.jsx` | 191 | * Page component: Home |
| `web/src/pages/Resources.jsx` | 212 | * Page component: Resources |
| `web/src/styles.css` | 536 | Chandralipi — see DESIGN.md for the reasoning behind every rule here |
| `web/vite.config.js` | 10 | * Vite config (relative base path for static builds) |

## 3. Build / test commands and current results

Run on 2026-09-28 at commit `bbf9585`, on Linux with Python 3.12.3 (`.venv`), pytest 9.1.1, ruff 0.16.6, mypy 2.3.1 and Node v24.19.0. Caches and build output were redirected outside the repo, using `-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`, `--no-cache`, `--cache-dir` and `--outDir`.

| # | command | exit | time | result (tool's own summary line) |
|---|---|---|---|---|
| 1 | `.venv/bin/pytest -p no:cacheprovider -rsf` | 1 | 271 s | `4 failed, 434 passed, 1 skipped, 2 warnings in 268.12s (0:04:28)` |
| 2 | `.venv/bin/python -m pytest -p no:cacheprovider tests/test_overlap.py` | 0 | 3 s | `60 passed, 8 warnings in 1.98s` |
| 3 | `.venv/bin/ruff check --no-cache .` | 0 | 1 s | `All checks passed!` |
| 4 | `.venv/bin/ruff format --check --no-cache .` | 1 | 1 s | `60 files would be reformatted, 55 files already formatted` |
| 5 | `.venv/bin/mypy --cache-dir <scratch>` (uses `[tool.mypy] packages = ["lunar_reg"]`) | 2 | 2 s | `Package 'lunar_reg' cannot be type checked due to missing py.typed marker.` |
| 6 | `.venv/bin/mypy --cache-dir <scratch> src/lunar_reg` | 2 | 1 s | `.venv/lib/python3.12/site-packages/numpy/__init__.pyi:737: error: Type statement is only supported in Python 3.12 and greater  [syntax]` / `Found 1 error in 1 file (errors prevented further checking)` |
| 7 | `cd web && npx vite build --outDir <scratch> --emptyOutDir` (`npm run build` with output redirected) | 0 | 20 s | `✓ 1034 modules transformed.` … `✓ built in 12.37s` |

**Run 1: failed tests.** All four raised `ModuleNotFoundError: No module named 'tests'` at `from tests.test_ingest_labels import _pds4_label`:

- `tests/test_overlap.py:665` in `test_crop_writes_both_sides`
- `tests/test_overlap.py:735` in `test_crop_filenames_encode_the_pair_not_just_the_product`
- `tests/test_overlap.py:774` in `test_crop_output_is_a_readable_geotiff`
- `tests/test_overlap.py:799` in `test_lid_with_colons_produces_a_safe_filename`

**Run 1: skipped test.** `SKIPPED [1] tests/test_geometry_grid.py:516: no extracted *_g_grd_d18.csv under data/`

**Run 1: warnings.** Both are `rasterio NotGeoreferencedWarning: The given matrix is equal to Affine.identity or its flipped counterpart.`, raised by:

- `tests/test_registered_export.py::test_provenance_tags_travel_with_the_file`
- `tests/test_registered_export.py::test_affine_2x3_matrix_is_accepted`

**Run 2** re-ran only the file containing the four failures, invoked as `python -m pytest`. It was not a full-suite run.

**Run 7: output size.** The largest emitted chunk was `Home-*.js` at 833.57 kB (226.14 kB gzip).

**Documented but not run**, because each would modify the venv, write into the repo, start long-running servers or download data:

- `pip install -e ".[dev]"` (README.md)
- `./scripts/setup.sh`
- `./scripts/up.sh`
- `./scripts/run_dashboard.sh`
- `./scripts/pack_data.sh` (writes `dist/`)
- `scripts/fetch_catalogue.py`
- `scripts/run_vikram.py`
- `npm run dev`
- `npm run preview`
- Python wheel build (writes `dist/`)

## 4. TODO / FIXME

Command: `grep -InwE 'TODO|FIXME'` over every text file in section 2, run before this file was written. `CLAUDE.md`, which appeared afterwards, was checked separately and has none. There is 1 match in total. A substring search (`grep -IE 'TODO|FIXME'`) matched the same single line.

| location | text |
|---|---|
| `src/lunar_reg/ingest/pseudo_gt.py:183` | `# TODO: build the grid in the pair's PolarFrame instead.` |
