# LLD — viewers (P1.21) and docs/status refresh (P1.22)

## P1.21 — viewers
Closes: A068 (pr-1), A117 (pr-16), A118 (pr-17), A119 (pr-22), A124 (tooling-14 part: relative `sourceDirectory`), A039 caller part (conditioning map model + full-resolution shape). Files: `scripts/export_web_data.py`, `dashboard/app.py`, `src/lunar_reg/viz/figures.py`, `scripts/reindex_results.py`, `scripts/demo.py`.
| item | change |
|---|---|
| A068 | `viz.figures.side_by_side_matches(..., src_scale=1.0, ref_scale=1.0)` replaces the single `scale`; points are multiplied by their own side's scale; both viewers pass `extra["source_scale"]` and `extra["reference_scale"]`. Transforms drawn on thumbnails are conjugated: `S_ref @ T @ inv(S_src)` with `S = diag(scale, scale, 1)`. |
| conditioning map callers | pass `model=result.metrics["model"]` and the full-resolution source shape `round(thumb.shape / source_scale)`; points outside the shape are counted and shown as a caption, not dropped silently. |
| A117 | `scripts/demo.py` and the dashboard's synthetic warning say "this scene is synthetic (generated)"; they no longer claim that no Chandrayaan-2 product exists. |
| A118 | `export_web_data.py` writes `results.json` and `pairs/` into `web/public/data/.export_tmp/`; on success it renames the current `web/public/data/pairs` to `web/public/data/.export_old`, `os.replace`s the temp `pairs` and `results.json` into place, then removes `.export_old` and `.export_tmp` (`shutil.rmtree`, these two paths only); on failure the current export is left untouched. `load_pair` errors of any type are counted and reported, not only `FileNotFoundError`. |
| A124 | `sourceDirectory` = `os.path.relpath(Path(args.results).resolve(), <repo root>)` (repo root = `Path(__file__).resolve().parents[1]`). |
| A119 | `reindex_results.py --exclude-synthetic` refuses to overwrite an existing stash file (suffix `_<created_utc>`), and moves the path returned by `load_all_pairs`' scan, not a reconstructed name. |
| licence (G11) | both viewers show `extra["licence"]` next to the matcher name when present. |
| failures (C05) | the dashboard gains a "Failed runs" table from `load_failures(root)` (status, detail, stage, pair_id, created_utc); the web export adds `failures: [...]` (same fields) and `nFailures`. |
Tests (`tests/test_viewers.py`): scale conjugation on a synthetic PairResult with different thumbnail scales puts a known point on the right pixel; export into `tmp_path` produces valid JSON (`allow_nan=False`) with `nFailures` and a relative `sourceDirectory`; the swap leaves no temp directory behind.

## P1.22 — docs and status refresh (split from the code-text items by review RC30)
Closes: A121 (S17), A122 (tooling-11), A123 (tooling-12), A070 (tooling-13), A120 README part, A023 README part (`README.md:610-611`). Files: `README.md`, `CONTEXT.md`, `CONTEXT_HANDOFF.md`, `docs/results/` (new).
| item | change |
|---|---|
| S17 / A121 | regenerate `web/public/data/results.json` with `scripts/export_web_data.py`; every test count / status claim in README, CONTEXT, CONTEXT_HANDOFF is replaced by a value with its source: `scripts/ci.sh` output saved to `docs/results/ci_<date>.txt` (the count line), `lunar-reg catalog` output, the live index row count — each cited by path; otherwise `[INSERT RESULT]` |
| A122 | README provenance table generated from `lunar-reg fields` output (paste the output block, cite the command); delete known-gap 3; replace the "no CH-2 product" paragraph with the `synthetic` flag explanation |
| A123 | CONTEXT.md provenance counts replaced by the commands that produce them |
| A070 | copy the text of `data/processed/vikram/README.md` and `data/processed/demo_real/README.md` into `docs/results/vikram_2024.md` and `docs/results/jaxa_wac_2026-09-08.md` (text only, no images), and point README/CONTEXT links there |
| A120 (README part) | README lines 390-396 stop claiming PCA in `ohrc_nac_config` |
| A023 | README 610-611: "self-residual sub-pixel" wording (`self_residual_subpixel`, not accuracy) |
Check (`Phase_1/harness/tests/test_P1_22.py`): the stale claims `431 passed`, `431 tests`, `zero real OHRC`, `No Chandrayaan-2 product was available` no longer appear in README/CONTEXT/CONTEXT_HANDOFF; `docs/results/vikram_2024.md` and `docs/results/jaxa_wac_2026-09-08.md` exist; every added line in those three docs that contains the word `tests` or `pairs` together with a number also contains `docs/results/`, `data/processed/`, or `[INSERT RESULT]`.

## P1.23 — code docstrings, script hints, ignore rules (review RC30)
Closes: A069 (tooling-4), A116 (ingest-17), A120 code part (preprocess-8). Files: `scripts/setup.sh`, `scripts/up.sh`, `scripts/run_dashboard.sh`, `.gitignore`, docstrings/comments only in `src/lunar_reg/ingest/{__init__,fieldmap,manifest}.py` and `src/lunar_reg/preprocess/config.py`. No code statement changes (a diff touching anything but comments/docstrings/strings printed as hints fails the check).
| item | change |
|---|---|
| A069 | `setup.sh`, `up.sh`, `run_dashboard.sh` hints name `setup.sh --data <bundle>` or `scripts/run_vikram.py`, not `build_demo_results.py` |
| A116 | ingest docstrings state the current verified status per field (cite `lunar-reg fields`) and reference `constants.moon_datum()` |
| A120 (code part) | `preprocess/config.py` comments/docstrings stop claiming PCA in `ohrc_nac_config` (it sets `band_reduction=False`) |
| `.gitignore` | add `Phase_*/benchmark/out/` only if not already present |
Check (`Phase_1/harness/tests/test_P1_23.py`): setup/up hints no longer point at `build_demo_results.py`; `ingest/__init__.py` docstring mentions `moon_datum`; `config.py` no longer claims PCA for `ohrc_nac_config`; `.gitignore` ignores `Phase_*/benchmark/out/`.
