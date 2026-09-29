# Phase 0 benchmark rubric

Produced by `bash Phase_0/benchmark/run.sh` → `Phase_0/benchmark/score.json` (schema below). Every value is MEASURED by that run; nothing is typed in by hand.

| axis | weight | metric (exact definition) | threshold | why |
|---|---|---|---|---|
| correctness | 0.4 | min(pass fraction of all `Phase_0/harness/tests`, pass fraction of `tests -m "not gpu and not data and not weights"`); skips excluded from the denominator | 1.0 | Phase 0's job is a green, reproducible baseline |
| spec_conformance | 0.3 | pass fraction of `Phase_0/harness/tests/test_contracts_P0.py` (C01–C07, C15) | 1.0 | contracts are consumed by every later phase |
| quality | 0.3 | fraction of the four checks below that pass | 1.0 | behaviours that change stored numbers |
| synthetic | 0 (reported, gates `pass`) | median `transform_rms_px` (truth-based, `eval/error_budget.py`) of SIFT registrations on 10 same-illumination `illumination_pair` scenes, seeds 0–9, 384×384 | ≤ 0.5 px | only truth-based accuracy available; kept separate from real-data axes (CLARIFY Q19) |

Quality checks:
| check | definition | threshold |
|---|---|---|
| counts | fraction of the 10 synthetic pairs where `n_matches ≥ n_ransac_inliers ≥ n_inliers`, `inlier_ratio = n_inliers / n_matches`, and refit inliers ⊆ RANSAC inliers (G34) | 1.0 |
| no_unclassified_exceptions | `register_pair` raised on none of the 10 pairs (C02) | 0 exceptions |
| ecc_affine | fraction of 10 random affine scenes (256², blurred noise, start perturbed ≤ 0.8 px) where `ecc_refine` returns APPLIED, a 2×3 matrix, and max probe error < 0.1 px (G35) | 0.9 |
| determinism | two in-process runs and one subprocess run of `register_pair` on the same pair give byte-identical transforms (C06) | 1.0 |

`score.json`:
```json
{"schema": 1, "phase": "0", "created_utc": "...", "git_sha": "...", "provenance": "measured",
 "axes": {"<axis>": {"weight": 0.4, "value": 0.0, "threshold": 1.0, "direction": ">=", "pass": false, "detail": {}}},
 "skips": {"count": 0, "reasons": {"<reason>": 0}},
 "weighted_total": 0.0, "pass": false}
```
`pass` = every axis passes (including `synthetic`). `weighted_total` = Σ weight × (1 if the axis passes else its value clipped to [0, 1]). Skips are never counted as passes; their reasons are listed.
