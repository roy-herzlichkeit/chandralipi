# Phase 0 — assumptions

Phase 0 consumes no contracts (it produces C01–C07, C15). It relies on these environment and repository facts; P0.00 checks each row with the command shown. A row that fails is a BLOCKER.

| # | assumption | command | expected |
|---|---|---|---|
| A0-1 | project venv is Python 3.12 | `.venv/bin/python -V` | `Python 3.12.x` |
| A0-2 | OpenCV 4.x (AKAZE pin, pyproject) | `.venv/bin/python -c "import cv2; print(cv2.__version__)"` | starts with `4.` |
| A0-3 | torch + kornia import | `.venv/bin/python -c "import torch, kornia; print(torch.__version__, kornia.__version__)"` | prints two versions |
| A0-4 | ruff available | `.venv/bin/ruff --version` | prints a version |
| A0-5 | plan committed on `main` | `git ls-files docs/plan/CONTRACTS.md docs/plan/PHASES.md Phase_0/harness/MANIFEST.sha256` | three paths printed |
| A0-6 | harness intact | `(cd Phase_0 && sha256sum --quiet --strict -c harness/MANIFEST.sha256)` | exit 0 |
| A0-7 | live results store readable (v1) | `.venv/bin/python -c "from lunar_reg.results import load_index; print(len(load_index('data/processed/results')))"` | an integer (13 on 2026-09-29) |
| A0-8 | stored pair ids satisfy C04's pattern | `.venv/bin/python -c "import re; from lunar_reg.results import load_index; print([i for i in load_index('data/processed/results')['pair_id'] if not re.fullmatch(r'^[A-Za-z0-9][A-Za-z0-9._-]*\$', i)])"` | `[]` |
| A0-9 | pretrained weights cached (for `weights` tests) | `ls ~/.cache/torch/hub/checkpoints/` | `loftr_outdoor.ckpt`, `depth-save.pth`, `disk_lightglue_v0-1_arxiv-pth` — absent → tests skip with reason, not a BLOCKER |
| A0-10 | OHRC labels on disk (for `data` tests) | `ls data/raw/ohrc_vikram/*/data/raw/*/*_d_img_*.xml \| wc -l` | `4` — absent → tests skip with reason, not a BLOCKER |
