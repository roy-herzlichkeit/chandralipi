# Phase 2 — assumptions

| contract | used by | proof re-run by P2.00 |
|---|---|---|
| C01, C15 | all RUN prompts | `test_contracts_P0.py -k "C01 or C15"` |
| C02, C03 | P2.05 (adds OOM production, device/precision) | `-k "C02 or C03"` |
| C04, C05 | P2.10, P2.11 | `-k "C04 or C05"` |
| C06, C07 | P2.08 (seeded fit, refit) | `-k "C06 or C07"` |
| C09–C11 | P2.10 (catalog, georeference, window pairs) | `test_contracts_P1.py -k "C09 or C10 or C11"` |
| C12–C14, C20 | P2.10/P2.11 (presets default, sun, agreement, gate) | `test_contracts_P1.py -k "C12 or C13 or C14 or C20"` |

| # | assumption | command | expected | if not |
|---|---|---|---|---|
| A2-1 | `phase-1-approved` exists | `git tag -l phase-1-approved` | tag | BLOCKING |
| A2-2 | CUDA works in the venv | `.venv/bin/python -c "import torch; print(torch.cuda.is_available())"` | `True` | BLOCKING |
| A2-3 | driver/GPU as recorded | `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader` | RTX 4060 Laptop, 8188 MiB | non-blocking (profile slug changes) |
| A2-4 | pretrained weights cached | `ls ~/.cache/torch/hub/checkpoints` | loftr/disk/lightglue files | BLOCKING for P2.04 |
| A2-5 | live v2 store has the anchor | `.venv/bin/python -c "from lunar_reg.results import load_index; i=load_index('data/processed/results'); print(i['pair_id'].str.contains('20240425T1406019344').sum())"` | ≥ 1 | BLOCKING for P2.11 |
