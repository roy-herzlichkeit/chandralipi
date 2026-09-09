# scripts/

Helper scripts. The ones below get a second machine from `git clone` to both
dashboards running.

## `up.sh` — the one-command everything

Runs setup (optional), refreshes the static export, and launches **both** front
ends together — the Streamlit dashboard and the React showcase site — tearing
both down on one Ctrl-C.

```bash
./scripts/up.sh                     # servers only (setup already done)
./scripts/up.sh --setup             # venv + deps first
./scripts/up.sh --setup --data ../chandralipi-data-processed-<date>.tar.zst
./scripts/up.sh --build             # React: production build + preview, not the dev server
./scripts/up.sh --no-web            # Streamlit only
./scripts/up.sh --host              # bind both to 0.0.0.0 for other devices / a projector laptop
```

Streamlit → `http://localhost:8501`, React → `http://localhost:5173`
(`--streamlit-port` / `--web-port` to change). `--no-web` drops the Node
requirement. The React `/dashboard` reads a static snapshot, so `up.sh` re-runs
`export_web_data.py` on every launch to keep the two in sync.

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
bundle, or, if the `.npz` are there but unindexed,
`.venv/bin/python scripts/reindex_results.py`.

## Windows

Use WSL, or run the equivalent commands by hand:
`py -m venv .venv`, `.venv\Scripts\pip install -e ".[dev,dashboard]"`, unpack the
archive with `tar -xf`, then `.venv\Scripts\streamlit run dashboard\app.py`.

## The other scripts

- `build_demo_results.py` — runs the pipeline over generated scenes and writes
  them to `data/processed/results_ch2_synthetic_backup/` (its own store, not the
  live `results/`). It once wrote to `results/` and its index rebuild dropped
  the real pairs from view; `save_results()` now reindexes from every `.npz` on
  disk rather than just its batch, and the separate store keeps the two sets
  from colliding at all.
- `reindex_results.py` — rebuild `index.parquet` from every `pairs/*.npz` on
  disk, ignoring the stale index. `--exclude-synthetic` moves generated scenes
  to `results_ch2_synthetic_backup/` and indexes only the real pairs (the
  showcase state); `--dry-run` reports without writing. Never deletes a result.
- `demo.py` — single-pair registration plus the four figures, e.g.
  `demo.py --case hard-30deg --matcher asift`.
- `export_web_data.py` — exports the results store to JSON for the `web/` site.
- `make_contour_background.py` — one-off asset generation for the site.
