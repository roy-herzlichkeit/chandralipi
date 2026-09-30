# Phase 1 benchmark rubric

Produced by `bash Phase_1/benchmark/run.sh` → `Phase_1/benchmark/score.json` (same schema as Phase 0's RUBRIC). Every value is MEASURED by that run from the repo state and the RUN artefacts of P1.18–P1.20; nothing is typed in by hand.

| axis | weight | metric (exact definition) | threshold | why |
|---|---|---|---|---|
| correctness | 0.35 | min(pass fraction of `Phase_1/harness/tests`, pass fraction of `tests -m "not gpu and not data and not weights"`) | 1.0 | green pipeline |
| spec_conformance | 0.25 | pass fraction of `test_contracts_P1.py` + `test_contracts_P0.py` (C01–C14, C15, C20) | 1.0 | contracts consumed by Phases 2, 1B, 3 |
| quality | 0.4 | fraction of the four real-data checks below that pass | 1.0 | CLARIFY Q18 targets |
| synthetic | 0 (reported, gates `pass`) | median `truth_rms_px` of the default preset over the ablation's synthetic rows with azimuth Δ ≤ 30° (`data/processed/ablation/ablation.json`) | ≤ 0.5 px | only truth-based accuracy; SYNTHETIC, never merged (Q19) |

Quality checks (real data; no ground truth exists, so only consistency signals are used — FABLE_NOTES §4.6):
| check | definition | threshold |
|---|---|---|
| anchor | in the live v2 store, the 2024 anchor strip `20240425T1406019344` has a result with ≥ 20 final inliers and U ≥ 0.7, and the pre-ECC agreement of its OK matchers is < 1 px with ≥ 2 matchers (C14) | 1 |
| diagnosed_2023 | fraction of the three 2023 strips that pass the targets in `exp1_gate.json` or carry a class other than `UNRESOLVED` in `data/processed/vikram/exp1/diagnosis.json`, **and** whose `Classification:` line under `### <tag>` in `docs/VIKRAM_2023_DIAGNOSIS.md` equals that class (review RC12) | 1.0 |
| failures_persisted | both the P1.19 and P1.20 run records exist, and `failures.parquet` rows ≥ their failure counts (C05, invariant 2; review RC35) | 1 |
| skip_if_absent | the catalog has a status for every instrument and none is UNREADABLE, and `data/processed/cross/run_record.json` (P1.18) is C15-valid with an `instrument_<name>_<status>` key for TMC2 and IIRS (G24; review RC22) | 1 |
| datum_checked | `tests/test_datum.py -m data` ran (not skipped) and passed — i.e. the calibrated OHRC product was on disk (review RC27; a skip scores 0 and names the missing product) | 1 |

A failing quality check does not by itself block the human review; the reviewer reads `score.json` together with the diagnosis doc.
