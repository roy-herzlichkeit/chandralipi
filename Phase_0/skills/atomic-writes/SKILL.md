---
name: atomic-writes
description: Write-then-rename pattern for every file a pipeline produces (results store, manifests, run records, job results). Used by P0.07, P0.10, P1.01, P3.02 and later.
---

# Atomic writes

## Pattern
```python
def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
```
| writer | how |
|---|---|
| JSON | `_atomic_write_bytes(path, json.dumps(obj, indent=2, sort_keys=True).encode())` |
| parquet | `frame.to_parquet(tmp, index=False)` then `os.replace(tmp, path)` |
| npz | open `tmp` as a binary file handle and pass the handle to `np.savez_compressed` (a *path* without `.npz` gets `.npz` appended by numpy, which breaks the rename) |

## Rules
- The temp file lives in the **same directory** as the target (so `os.replace` is atomic on one filesystem) and starts with `.` so globbing `*.npz` never picks it up.
- Never delete a target before writing its replacement.
- Refuse-to-overwrite semantics (`FileExistsError`) are checked **before** writing the temp file.
- A failed write leaves the old file intact; remove the temp file in a `finally` only when `os.replace` did not happen.
