# STATUS

current: P0.02
phase: 0
state: READY
branch: phase-0
last_done: P0.01
notes:
- P0.01: pyproject pytest/mypy config (pythonpath ".", weights marker, no -q); scripts/ci.sh (CPU suite entry point); .github/workflows/ci.yml; scripts/untar_data.py (two-pass, refuses non-data/ and unsafe members; exit 0/2/3); setup.sh uses it + reindex.
- bash scripts/ci.sh: ruff clean, 444 passed, 2 deselected (gpu/data/weights markers).
- Baseline from P0.00: 440 collected, 440 passed (pytest -o addopts="").
- P1.DL (download session) may run before Phase 0 is approved: see Phase_1/prompts/P1.DL_download_session.md.
