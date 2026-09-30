# LLD — node cache + byte accounting (P4.02) and capacity routing (P4.03)

TBD 4.2, 4.3. Uses C08, C16, C22–C25.

## P4.02 — `distributed/cache.py`, `distributed/worker.py`
```python
class CacheStatus(str, Enum): HIT = "hit"; COPIED = "copied"; MISSING = "missing"; HASH_MISMATCH = "hash_mismatch"
@dataclass
class NodeCache:
    cache_dir: Path; source_root: Path; manifest: Path = Path("data/raw/DOWNLOADS.json")
    def resolve(self, rel_path: str) -> tuple[Path | None, CacheStatus]
    def report(self) -> str        # counts per CacheStatus + first sample
```
- A missing manifest file is treated as an empty manifest (every file is "unlisted").
- `resolve`: `cache_dir/rel_path` exists and its size equals the C08 entry's `bytes` → HIT; else `source_root/rel_path` exists → copy to the cache (temp + rename), verify sha256 against C08 → COPIED or HASH_MISMATCH (the bad copy is deleted — cache files only); no source → MISSING. Files not listed in C08 are copied without hash check and reported as COPIED with `detail="unlisted"`.
- `worker.process_job(..., cache: NodeCache | None = None)` (new keyword): when given, paths resolve through the cache; MISSING / HASH_MISMATCH → `READ_FAILED` with the cache status in `detail`. `bytes_read` = bytes of both windows actually read (`window.height · window.width · itemsize` per band read).
- Labels next to images (PDS4 `.xml` + `.img`) are resolved as a pair (same directory in the cache).
Tests (`tests/test_node_cache.py`): HIT/COPIED/MISSING/HASH_MISMATCH with a tmp manifest; a job through a cache reads identical pixels; `bytes_read` equals the expected product of window sizes.

## P4.03 — `distributed/scheduler.py`, `distributed/planner.py`
```python
@dataclass(frozen=True)
class WorkerCapacity:
    worker_id: str; host: str; device: str; free_bytes: int; profile_slug: str | None
@dataclass(frozen=True)
class Tier:
    name: str; max_bytes: int
def capacity_tiers(fleet: list[WorkerCapacity], safety: float = 0.75) -> list[Tier]   # one tier per distinct floor(safety*free), ascending; names "t0", "t1", …
def tier_for(job: JobDescriptor, tiers: list[Tier]) -> Tier | None                   # smallest tier with max_bytes >= est_vram_bytes
def tiers_for_worker(worker: WorkerCapacity, tiers: list[Tier], safety: float = 0.75) -> list[str]   # every tier whose max_bytes <= this worker's safety*free, largest first
@dataclass
class Assignment:
    by_tier: dict[str, list[str]]; unschedulable: list[str]
    def report(self) -> str
def assign(jobs: list[JobDescriptor], tiers: list[Tier]) -> Assignment
```
- `planner.plan_jobs(..., fleet: list[WorkerCapacity] | None = None)` (new keyword): when given, jobs whose estimate exceeds every tier are listed as skipped `"unschedulable"` (never silently dropped).
- `distributed plan --fleet` calls `queue.register_tiers(capacity_tiers(fleet))` before any `put(job, tier=tier_for(job, tiers).name)` (C27: tier streams registered with their `max_bytes`; review RC04). A worker started with `--max-bytes N` reads only tiers with `max_bytes <= N`, largest first (the same set `tiers_for_worker` returns), so bigger GPUs also drain smaller-tier work and no small GPU ever receives a job that does not fit (no OOM by construction; any OOM is still classified). No entry is ever skipped and re-added.
Tests (`tests/test_scheduler.py`): fleet {4060 laptop 7.4 GiB free, 3060 5.5 GiB free} → 2 tiers; a job of 5 GiB goes to the larger tier only; a 9 GiB job is unschedulable; `tiers_for_worker` for the 3060 excludes the larger tier.
