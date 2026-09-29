# LLD — queue protocol + local queue (P3.04)

Produces: C24. TBD 3.3.

`LocalJobQueue(path, *, clock=time.time)` backed by SQLite (`sqlite3`, `isolation_level=None`, `PRAGMA journal_mode=WAL`, `timeout=30`), process-safe.
```sql
CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, payload TEXT NOT NULL, est_vram_bytes INTEGER NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('pending','leased','done','failed')), attempts INTEGER NOT NULL DEFAULT 0,
  lease_id TEXT, worker_id TEXT, deadline REAL, status TEXT, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('put','claim','ack','lost','closed_lost')), worker_id TEXT, t REAL NOT NULL);
```
| method | behaviour (each in one `BEGIN IMMEDIATE` transaction) |
|---|---|
| `put(job)` | `INSERT OR IGNORE`; returns `rowcount == 1`; event `put` |
| `claim(worker_id, lease_s, max_bytes=None)` | first `pending` row by `job_id` (with `est_vram_bytes <= max_bytes` when given) → `leased`, `lease_id = uuid4().hex`, `attempts += 1`, `deadline = clock() + lease_s`; returns `Lease(JobDescriptor.from_json(payload), worker_id, lease_id, deadline, attempts)`; none → `None`; event `claim` |
| `ack(lease, status)` | `UPDATE … WHERE job_id=? AND lease_id=? AND state='leased'` → `done` (status OK) or `failed` (any failure) with `status` value; returns `rowcount == 1`; event `ack` |
| `reclaim_expired()` | every `leased` row with `deadline < clock()`: `attempts >= MAX_ATTEMPTS` → `failed`, `status = 'worker_lost'`, event `closed_lost`; else → `pending`, `lease_id = NULL`, event `lost`; returns the job ids set back to pending |
| `stats()` | `QueueStats(pending, leased, done, failed, lost_events)` from counts; `lost_events` = number of `lost` + `closed_lost` events |
`MAX_ATTEMPTS = 3`. `JobQueue` is a `typing.Protocol` (runtime_checkable) with the four C24 methods plus `stats`.
Tests (`tests/test_local_queue.py`): put dedupe; claim order; lease expiry with an injected clock → reclaimed and counted; third expiry closes as `worker_lost`; an ack after reclaim returns False; `max_bytes` filtering; two processes claiming concurrently never get the same job (multiprocessing, 50 jobs, 2 workers).
