# STATUS

current: P1.04
phase: 1
state: READY
branch: phase-1
last_done: P1.03
notes:
- P1.03: manifest.py has ScanStatus/ScanDiagnostics/product_type_of; scan_directory and lro.scan_lro_directory take with_diagnostics; COLUMNS ends with product_type; scans now parse only "data" labels. New ingest/catalog.py (C09); new `lunar-reg catalog [--raw-root] [--json]` (exit 1 only when an instrument is UNREADABLE). The 3 scan tests in tests/test_ingest_labels.py now use *_d_img_d18.xml fixture names.
- `lunar-reg catalog` on data/raw (EXIT=0; stdout at scratchpad p1/catalog_P1.03.stdout), first 8 lines: OHRC: present, 8 product(s), e.g. ch2_ohr_ncp_20230823T1450475804_d_img_n18 | TMC2: present, 4 product(s), e.g. ch2_tmc_ncf_20231026T0943001971_d_img_d18 | IIRS: present, 2 product(s), e.g. ch2_iir_nci_20221226T0416479474_d_img_d32 | LRO_NAC: present, 2 product(s), e.g. NAC_DTM_VIKRAMSITE1_M1442997156_100CM | LRO_NAC_DTM: present, 1 product(s), e.g. NAC_DTM_VIKRAMSITE1 | SELENE_TC: partial, 9 product(s), e.g. TC1S2B0_01_05600N005E1008.isis  (data file missing next to 7 label(s), e.g. TC1S2B0_01_05600N005E1008.isis.lbl) | label scan: 26 outcome(s), 0 failure(s) | not_a_data_product: 3  e.g. TMC2 .../ch2_tmc_ndn_20231027T1315134884_d_dtm_d18.xml: product_type=other
- Non-blocking: Q-P1.03-1 (SELENE_TC is PARTIAL: the JAXA .lbl files name .img but .tif is on disk, and the .isis.lbl sidecars match the glob); Q-P1.03-2 (DTM and _d_oth_ labels count as "other" under the LLD rules, so products(inst) leaves them out by default). Both go in the review pack's LLD deviations and questions.
- Not ruff-formatted, so other subcommands stay untouched: cli.py and tests/test_ingest_labels.py. ruff check passes on both. scripts/ci.sh: 605 passed.
- Review fixes in catalog.py: (1) unlabelled data files (.img/.qub/.dat, no same-stem label) now make the instrument PARTIAL and are listed in ProductCatalog.unlabelled_data (an attribute, not a field) and in report(); (2) PDS3 .lbl minimal read is binary, first line only; (3) parse_error samples use the path relative to raw_root and keep the error text. The real `lunar-reg catalog` output is unchanged: same 8 report lines, exit 0, and the log shows 'unlabelled data files: {}'. Non-blocking Q-P1.03-3 added (the LLD does not define how 'or the reverse' should be read).
