# LLD — test runner, CI, safe data unpack (P0.01)

Closes: A011 (tooling-2), A012 (tooling-5), A085/A086 (S10), A087 (S19), A088 (tooling-15).

## 1. `pyproject.toml`
| key | value after P0.01 |
|---|---|
| `[tool.pytest.ini_options].addopts` | `"-ra --strict-markers"` (no `-q`) |
| `[tool.pytest.ini_options].pythonpath` | `["."]` (fixes `from tests.test_ingest_labels import _pds4_label` under bare `pytest`) |
| `[tool.pytest.ini_options].markers` | exactly three entries: `"gpu: requires a working CUDA device"`, `"data: requires real products under data/raw"`, `"weights: requires pretrained matcher weights in ~/.cache/torch/hub/checkpoints"` |
| `[tool.mypy].python_version` | `"3.12"` |
| `[tool.mypy]` | remove `packages`; add `files = ["src/lunar_reg"]`; keep `ignore_missing_imports = true` |
Nothing else in `pyproject.toml` changes in P0.01 (PyYAML removal is P0.04).

## 2. `scripts/ci.sh` (new, mode 0755)
Exact behaviour:
```bash
#!/usr/bin/env bash
# CI entry point (DECISIONS G21): lint + CPU test suite. Extra args go to pytest.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"
"$PY" -m ruff check src tests scripts dashboard
"$PY" -m pytest -m "not gpu and not data and not weights" "$@"
```

## 3. `.github/workflows/ci.yml` (new)
One job `test` on `ubuntu-24.04`, triggers `push` and `pull_request`. Steps: `actions/checkout@v4`; `actions/setup-python@v5` with `python-version: "3.12"`; `pip install torch --index-url https://download.pytorch.org/whl/cpu`; `pip install -e ".[dev]"`; `bash scripts/ci.sh` with env `PYTHON: python`.

## 4. `scripts/untar_data.py` (new)
CLI: `python scripts/untar_data.py ARCHIVE [--dest DIR] [--force]`; `DIR` default `.`.
| input | handling |
|---|---|
| `*.tar`, `*.tar.gz`, `*.tgz` | `tarfile.open(ARCHIVE, "r:*")` |
| `*.tar.zst`, `*.tzst` | stream `zstd -dc ARCHIVE` (subprocess, argument list) into `tarfile.open(fileobj=proc.stdout, mode="r|")`; `zstd` missing → exit 3 with message |
| anything else | exit 3 |

Two passes. Pass 1 lists members and classifies each:
```python
class MemberStatus(str, Enum):
    EXTRACTED = "extracted"
    SKIPPED_EXISTS = "skipped_exists"            # target file exists and --force not given
    REFUSED_OUTSIDE_DATA = "refused_outside_data" # normalised name does not start with "data/"
    REFUSED_UNSAFE = "refused_unsafe"             # absolute path, ".." component, symlink, hardlink, device, fifo
```
Name normalisation: strip one leading `./`. Directories named exactly `data` or `data/...` are allowed.
If any member is REFUSED_*: print the report and exit 2 **without extracting anything**.
Pass 2 (reopen the archive): extract every file member whose target does not exist (or all with `--force`) using `tar.extract(member, dest, filter="data")`; count SKIPPED_EXISTS.
Report (always printed, one line per status with count and first member name as sample), then exit 0.
The `data` filter requires Python ≥ 3.12 (the project venv is 3.12).

## 5. `scripts/setup.sh`
Replace the archive `case` block (the three `tar ...` lines and the `*)` fallback) with:
```bash
"$VPY" scripts/untar_data.py "$DATA_SRC" --dest . || die "data bundle refused or failed: $DATA_SRC"
```
After any `--data` import (archive or directory), when `data/processed/results/pairs` exists, run `"$VPY" scripts/reindex_results.py` instead of trusting an unpacked `index.parquet`. The rsync/cp directory branch gets `--ignore-existing` (rsync) / `cp -an` (cp) so existing files are never overwritten. No other change to setup.sh in P0.01 (the `--cuda` index is P2.01).

## 6. Tests the prompt adds (`tests/test_untar_data.py`)
| test | asserts |
|---|---|
| good archive | `data/a.txt` extracted, exit 0 |
| `../evil` member | exit 2, nothing written anywhere under dest |
| member `src/x.py` | exit 2 (REFUSED_OUTSIDE_DATA) |
| symlink member | exit 2 (REFUSED_UNSAFE) |
| existing file | not overwritten, exit 0, report shows `skipped_exists: 1` |
| `--force` | existing file overwritten |
