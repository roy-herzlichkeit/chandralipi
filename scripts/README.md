# scripts/

Helper scripts. The three below get a second machine from `git clone` to a
running dashboard.

## Standing up another device

On the machine that **has** the data:

```bash
./scripts/pack_data.sh            # -> dist/chandralipi-data-processed-<date>.tar.zst  (~80 MB)
```

`data/` is git-ignored (large, ISSDC redistribution terms), so it travels as an
archive. Modes:

| command | contents | size | use |
|---|---|---|---|
| `pack_data.sh --results-only` | `data/processed/results/` | ~20 MB | smallest set the dashboard needs |
| `pack_data.sh` *(default)* | `data/processed/` | ~80 MB | dashboard + demo/`demo_real` figures |
| `pack_data.sh --full` | all of `data/` | ~300 MB | also lets you re-run the pipeline (adds `data/raw` reference imagery) |

Copy the archive across (USB, `scp`, whatever), then on the **new** machine:

```bash
git clone <this repo> && cd <repo>
./scripts/setup.sh --data /path/to/chandralipi-data-processed-<date>.tar.zst
./scripts/run_dashboard.sh
```

## `setup.sh` — venv → deps → data → verify

Idempotent; re-running only does the missing work. Options:

- `--data <archive|dir>` — unpack a `pack_data.sh` archive, or copy a `data/`
  directory (e.g. `--data /media/usb/sih/data`).
- `--cuda` — install the CUDA (cu124) build of torch before everything else.
  Default torch is CPU-only, which is what every result so far was produced on.
- `--extras "dev,dashboard"` — pip extras to install (default `dev,dashboard`;
  `notebooks` also available).
- `--python <path>` — interpreter to build the venv from (default `python3`,
  must be ≥3.10).
- `--force` — delete and rebuild `.venv`.
- `--run` — launch the dashboard when setup finishes.

## `run_dashboard.sh` — launch the Streamlit browser

Assumes `setup.sh` has run. Extra args pass through to streamlit:

```bash
./scripts/run_dashboard.sh --server.port 8600 --server.headless true
```

Warns (doesn't fail) if `data/processed/results/` is empty — populate it with a
bundle, or regenerate locally with `.venv/bin/python scripts/build_demo_results.py`.

## Windows

Use WSL, or run the equivalent commands by hand:
`py -m venv .venv`, `.venv\Scripts\pip install -e ".[dev,dashboard]"`, unpack the
archive with `tar -xf`, then `.venv\Scripts\streamlit run dashboard\app.py`.

## The other scripts

- `build_demo_results.py` — runs the pipeline and (re)populates
  `data/processed/results/`. **Footgun:** it rebuilds `index.parquet` from only
  its own batch, so running it after real results exist drops them from the
  index (see `data/processed/demo_real/README.md`).
- `demo.py` — single-pair registration plus the four figures, e.g.
  `demo.py --case hard-30deg --matcher asift`.
- `export_web_data.py` — exports the results store to JSON for the `web/` site.
- `make_contour_background.py` — one-off asset generation for the site.
