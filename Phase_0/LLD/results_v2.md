# LLD — results store v2 + persisted failures (P0.10)

Produces: C04, C05. Closes: A028 (pr-2), A029 (S13), A030 (pr-7), A031 (pr-8), A032 (pr-9), A033 (pr-11), A098 (S14), A099 (pr-18). Decisions: G08, G34.

## 1. `PairResult` (C04)
- New fields appended in this order: `ransac_mask`, `pre_ecc_transform`, `schema_version`.
- `__post_init__`: validate `pair_id` with `re.fullmatch(PAIR_ID_PATTERN, pair_id)` → else `ValueError(f"invalid pair_id {pair_id!r}: must match {PAIR_ID_PATTERN}")`; coerce `ransac_mask` like `inlier_mask` and check its length; `pre_ecc_transform` → float64 array or None.
- Properties `n_ransac_inliers` (None when `ransac_mask` is None) and `inlier_ratio` (`n_inliers / n_matches`, 0.0 when N = 0) are added.

## 2. `index_row` (C04)
Top-level keys in the C04 order. `schema_version` is `self.schema_version`. Group flattening uses `_plain_for_index(key, value)`:
| value | stored as |
|---|---|
| `np.generic` | `.item()` |
| `None`, `bool`, `int`, `float`, `str` | as is |
| `np.ndarray` | `json.dumps(value.tolist())` |
| `list`, `tuple`, `dict` | `json.dumps(value, sort_keys=True, default=_json_default)` |
| anything else | `TypeError(f"{prefix}_{key}: cannot store {type(value).__name__} in the index")` |
`_json_default` converts `np.generic` and `np.ndarray`; other objects raise `TypeError` (json propagates it).

## 3. `.npz` write/read
- `save_pair(result, root, overwrite=False)`: path `root/pairs/<pair_id>.npz`; exists and not overwrite → `FileExistsError`; write to `root/pairs/.<pair_id>.npz.tmp` with `np.savez_compressed(open file handle, ...)` then `os.replace`. Note: `np.savez_compressed` appends `.npz` to a *path* without that suffix, so write through an open binary file handle.
- New npz keys `ransac_mask`, `pre_ecc_transform` when not None. `meta.schema_version = result.schema_version`.
- `load_pair`: reads v1 and v2. Missing keys → None. `schema_version = meta.get("schema_version", 1)`. Remove the version-mismatch warning for version 1 (v1 is supported); keep a warning for versions > `SCHEMA_VERSION`.
- `write_index`: parquet written to `root/.index.parquet.tmp` then `os.replace`.

## 4. Failures (C05)
`save_failures(outcomes, root)`: rows from non-OK outcomes; columns per C05; `created_utc` = now (UTC, seconds); `schema_version = SCHEMA_VERSION`; `n_raw_matches`/`n_ransac_inliers` from `outcome.extra` or None; other scalar extra keys → `x_<key>` (non-scalars JSON-encoded as in §2). Read existing `failures.parquet` (if any), concatenate, write atomically. Returns the path.

## 5. `StoreReport`, `reindex`, `save_results` (C05)
`reindex(root, force=False)`:
1. `rows_before = len(load_index(root))`.
2. `results, failures = load_all_pairs(root)`.
3. If `failures` and `len(results) < rows_before` and not `force` → do not write; log one warning; `index_written=False`, `frame = load_index(root)`.
4. Else `frame = write_index(results, root)`, `index_written=True`.
`save_results(results, root, reindex_all=True, overwrite=False)`: `save_pair(r, root, overwrite)` for each; then `reindex(root)` (or `write_index(results)` when `reindex_all` is False, `index_written=True`); `n_saved = len(results)`.
`StoreReport.report()` lines: `store <root>: saved <n>, index rows <before> -> <after> (written|KEPT)`, then one line per load failure (count + first sample), or `  no load failures`.

## 6. Callers updated in this prompt
| caller | change |
|---|---|
| `pipeline.register_pair` | pass `ransac_mask=`, `pre_ecc_transform=detail["pre_ecc_matrix"]` |
| `pipeline.run_batch` | when `root` is given: `save_results(report.results, root)` and `save_failures(report.failures, root)`; `BatchReport` gains `store: StoreReport | None = None` |
| `scripts/reindex_results.py` | print `reindex(root, force=args.force).report()`; add `--force`; exit 1 when `index_written` is False |
| `scripts/run_vikram.py:391` | `store = save_results(results, RESULTS_ROOT)`; print `store.report()` |
| `scripts/build_demo_results.py:115` | same pattern |
| `tests/test_results_and_pipeline.py` | update assertions that used the returned frame (`frame = reindex(...)` → `.frame`) |

## 7. Tests the prompt adds (`tests/test_results_v2.py`)
C04/C05 behaviours: pair_id rejection list (`"../x"`, `".x"`, `"a/b"`, `""`, `"a b"`), overwrite refusal and no `*.tmp` left, v1 file loads, index JSON-encodes a list extra, object extra raises `TypeError` naming `x_<key>`, failures parquet columns, reindex keeps the index when a file is corrupt, `run_batch` writes `failures.parquet`.
