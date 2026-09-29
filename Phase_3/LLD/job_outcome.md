# LLD — job descriptor (P3.01) and job outcomes/result files (P3.02)

Produces: C22, C23. TBD 3.2, 3.3 (results directory), 3.5, 4.5 (content-hash names). Decision: G23 (all code in `src/lunar_reg/distributed/`, nothing imported by `pipeline.py`).

## P3.01 — `distributed/__init__.py`, `distributed/job.py`
- `__init__.py`: docstring only (package description, G23); no imports (keeps `import lunar_reg.distributed` free of torch/redis).
- `JobDescriptor` exactly C22. Validation in `__post_init__`: `len(prior) == 9`, all finite; windows are 4 non-negative ints with positive height/width; `precision in ("fp16", "fp32")`; `schema == JOB_SCHEMA`; paths are relative POSIX (no leading `/`, no `..`); violations → `ValueError` naming the field.
- Tuples survive JSON: `from_json` converts lists back to tuples so `from_json(to_json(j)) == j`.
- `job_id` = `hashlib.sha256(self.to_json().encode()).hexdigest()`; `seed` = `(base_seed + int(job_id[:8], 16)) % 2**31`.
- `to_json` floats use Python's `repr` (json default) — no rounding, so equal descriptors have equal ids across hosts.

## P3.02 — `distributed/outcome.py`
- `JobStatus`, `JobResult`, `write_job_result`, `read_job_result`, `JobDiagnostics` exactly C23 (including `bytes_read: int = 0`).
- Files: `<results_dir>/<job_id>.npz` (`src_pts`, `dst_pts`, optional `scores`; float64) and `<job_id>.json` (all other fields; `status` as its value). `write_job_result` creates `results_dir` (parents included) when missing. Write order: npz (temp + `os.replace`), then JSON (temp + `os.replace`) — the JSON's presence marks completion. `write_job_result` returns `(json_path, False)` without writing when the JSON already exists.
- `read_job_result`: JSON missing → `FileNotFoundError`; npz missing while JSON exists → `ValueError("corrupt result <job_id>: npz missing")`.
- `JobDiagnostics.record(result, duplicate=False)`: counts by status value; first sample per status = `f"{job_id[:12]}: {detail}"`; `n_duplicates` += 1 when `duplicate`. `report()` per the classified-outcomes skill, plus a `duplicates: <n>` line.
Tests: `tests/test_job.py`, `tests/test_job_outcome.py` — round trips, validation errors, idempotent write (second write returns False and leaves the first bytes untouched), corrupt npz detection, diagnostics report text.
