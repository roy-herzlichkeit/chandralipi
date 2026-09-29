# Phase 1B — assumptions

| contract | used by | proof re-run by P1B.00 (BUILD case) |
|---|---|---|
| C04, C05 | P1B.03, P1B.05, P1B.06 | `test_contracts_P0.py -k "C04 or C05"` |
| C06, C07 | P1B.03 | `-k "C06 or C07"` |
| C10, C11, C13, C14, C20 | P1B.02, P1B.03, P1B.05 | `test_contracts_P1.py -k "C10 or C11 or C13 or C14 or C20"` |
| C18 | P1B.05 (tiling when native mode is combined) | `test_contracts_P2.py -k C18` |

| # | assumption | command | expected | if not |
|---|---|---|---|---|
| A1B-1 | `phase-2-approved` exists | `git tag -l phase-2-approved` | tag | BLOCKING |
| A1B-2 | gate file valid | P1B.00 step 2 | C20-valid | BLOCKING |
| A1B-3 | NAC DTM on disk | `ls data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1.TIF` | path | BLOCKING (BUILD case) |
| A1B-4 | anchor registered in the live v2 store | same command as A2-5 | ≥ 1 | BLOCKING (calibration needs it) |
