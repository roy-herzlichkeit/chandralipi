# Phase 3 — assumptions

| contract | used by | re-run by P3.00 |
|---|---|---|
| C02, C04–C06, C15 | reducer, runner | `test_contracts_P0.py` |
| C10, C11 | planner (`plan_inputs_from_result`) | `test_contracts_P1.py -k "C10 or C11"` |
| C16–C19 | planner estimates, worker tiling, native lift | `test_contracts_P2.py` |

| # | assumption | command | expected | if not |
|---|---|---|---|---|
| A3-1 | `phase-1B-approved` exists | `git tag -l phase-1B-approved` | tag | BLOCKING |
| A3-2 | anchor v2 result with `crop_geometry_source == "recorded"` in the live store | `.venv/bin/python -c "from lunar_reg.results import load_index; i=load_index('data/processed/results'); print(i[i['pair_id'].str.contains('20240425T1406019344')]['x_crop_geometry_source'].tolist())"` | contains `recorded` | BLOCKING for P3.09 |
| A3-3 | `multiprocessing` spawn works in the venv | `.venv/bin/python -c "import multiprocessing as m; print(m.get_context('spawn'))"` | prints a context | BLOCKING |
