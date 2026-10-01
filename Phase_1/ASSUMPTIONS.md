# Phase 1 — assumptions

Contracts relied on (all produced in Phase 0; P1.00 re-runs their tests):

| contract | used by | proof re-run by P1.00 |
|---|---|---|
| C01 `ValueSource` | P1.04, P1.07, P1.09, P1.11, P1.13 | `test_contracts_P0.py -k C01` |
| C02 `RunStatus`/`RunOutcome` | P1.10, P1.16, P1.17 | `-k C02` |
| C03 `PipelineConfig`/`register_pair` | P1.10, P1.14, P1.16, P1.17 | `-k C03` |
| C04 `PairResult` v2 | P1.12, P1.16, P1.18–P1.21 | `-k C04` |
| C05 failures + `StoreReport` | P1.16–P1.21 | `-k C05` |
| C06 seeded fit | P1.16 (determinism of re-runs) | `-k C06` |
| C07 ECC detail | P1.16 (`pre_ecc_transform`) | `-k C07` |
| C15 run record | P1.11, P1.16–P1.20 | `-k C15` |

Environment / data (each row checked by P1.00 with the command shown):

| # | assumption | command | expected | if not |
|---|---|---|---|---|
| A1-1 | tag `phase-0-approved` exists | `git tag -l phase-0-approved` | prints the tag | BLOCKING |
| A1-2 | four OHRC `nrp` strips on disk (G27) | `ls data/raw/ohrc_vikram/*/data/raw/*/*_d_img_*.xml \| wc -l` | `4` | BLOCKING for P1.18–P1.20 |
| A1-3 | NAC ortho labels + DTM on disk | `ls data/raw/reference/lro_nac_vikram/*_100CM.xml data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1.TIF` | 3 paths | BLOCKING for P1.04 data tests and P1.18–P1.20 |
| A1-4 | JAXA/WAC inputs of the v1 results on disk | `ls data/raw/reference/jaxa_selene_tc_pair2 data/raw/reference/jaxa_selene_tc data/raw/reference/lro_wac` | three listings | non-blocking (P1.17/P1.18 report INPUT_MISSING) |
| A1-5 | calibrated OHRC `ncp`, TMC-2, IIRS | `ls data/raw/ch2` | may be absent | non-blocking (G24); `data` tests skip with a reason |
| A1-6 | free disk ≥ 20 GB | `df -h data/` | ≥ 20 GB avail | non-blocking warning |
| A1-6b | `data/raw/` total within the revised budget (CLARIFY Q17, 2026-10-01) | `du -sb data/raw` | ≤ 60 000 000 000 B | non-blocking warning; any new download that would cross it needs the human first |
| A1-7 | network is not needed except P1.02's run step (and P1.DL) | — | — | — |
