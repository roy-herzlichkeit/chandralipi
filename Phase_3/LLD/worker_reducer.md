# LLD — worker (P3.05) and reducer (P3.06)

Produces: C25, C26. TBD 3.1, 3.4.

## P3.05 — `distributed/worker.py`
`process_job(job, device, *, matcher_factory=None, repo_root=".") -> JobResult` (never raises for a bad job):
1. Source window: open `repo_root/job.source_path` (PDS4 label via `pds4.open_product`, otherwise `rasterio.open`), read band 1 `Window(col_off, row_off, width, height)`; any exception → `READ_FAILED`.
2. Resample to `working_gsd_m` with `cv2.resize(INTER_AREA)` to `(round(w/f), round(h/f))`, `f = working_gsd_m / source_native_gsd_m`; `to_native_tile` per the C11 pixel-centre rule; `valid = source > 0` resampled nearest.
3. Reference window: `rasterio.open(repo_root/job.reference_path)` band 1, `boundless=True, fill_value=0`; exception → `READ_FAILED`. (The NAC's GDAL transform is never used; only pixel windows are read.)
4. Valid fraction of the source tile or the rectified reference < 0.5 → `DEGENERATE_OVERLAP`.
5. Rectify the reference window into the tile frame with `job.prior` exactly as C18 step 2 (margin 32) and match: `matcher_factory(job.matcher, device)` (default `lunar_reg.match.build_matcher(name, device=device)`); `torch.OutOfMemoryError` → `OOM` (checked before other exceptions, with lazy `import torch` guarded so CPU workers need no torch); other exception → `MATCHER_ERROR`; zero matches → `NO_MATCHES`.
6. Lift to native coordinates: `src_native = to_native_tile(src_tile_px) + (col_off, row_off)` offset already in `to_native_tile`; `dst_native = T_rect(dst) + (ref col_off, ref row_off)`.
7. Timing (`seconds`), `peak_vram_bytes` on CUDA (reset/max_memory_allocated), `host = socket.gethostname()`, `bytes_read = source window bytes + reference window bytes`.
`run_worker(queue, results_dir, worker_id, device, *, lease_s=120.0, max_jobs=None, idle_exit_s=5.0, matcher_factory=None, max_bytes=None)`: loop `claim` → `process_job` → `write_job_result` → `ack(lease, result.status)`; no job for `idle_exit_s` seconds → return; logs one line per job at DEBUG and one summary at INFO; returns `WorkerSummary`. A `KeyboardInterrupt` stops without acking (the lease expires and is reclaimed — that is the WORKER_LOST path).

## P3.06 — `distributed/reducer.py`
`reduce_run(results_dir, jobs, *, model="homography", threshold_px=3.0, refit_threshold_px=1.0, seed=0) -> ReduceOutcome`:
1. For each job (sorted by `job_id`): `read_job_result`; missing → `missing_jobs`; record into `JobDiagnostics`.
2. Concatenate OK results' points in `(job_id, point index)` order → `MatchResult` (native coordinates).
3. Stages and statuses mirror `register_pair` (C02): `< 8` points → `TOO_FEW_MATCHES`; `estimate_transform(seed=seed)` `ValueError` → `ESTIMATION_FAILED`; `< 8` RANSAC inliers → `TOO_FEW_INLIERS`; `reestimate_on_inliers(threshold_px=refit_threshold_px, seed=seed)`; exceptions → `REFINEMENT_FAILED`. No ECC (native imagery is not loaded whole).
4. Metrics: `compute_metrics` (raw/RANSAC/refit counts as G34), `compute_uniformity` over the union source window shape (points shifted to the window origin), `bootstrap_conditioning` with `n_bootstrap=40, seed=seed`.
5. `PairResult(pair_id=f"{jobs[0].pair_id}_dist", …, matcher=jobs[0].matcher, src_pts/dst_pts = native points, transform = refit matrix, extra={"run_id", "n_jobs", "n_missing", "job_<status>" counts, "n_duplicates", "working_gsd_m", "native_frame": "source-native px -> reference-native px"})`; no thumbnails (`source_image=None`).
Tests: `tests/test_worker.py` (synthetic GeoTIFF source/reference in `tmp_path`, one job → OK with points mapping through the known transform within 0.5 px; unreadable path → READ_FAILED; blank → DEGENERATE_OVERLAP); `tests/test_reducer.py` (three synthetic result files → same transform whatever the order they were written in, byte-identical matrices; missing job listed).
