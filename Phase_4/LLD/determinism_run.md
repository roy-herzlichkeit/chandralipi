# LLD — cross-worker determinism + idempotence (P4.05) and the two-host run (P4.06)

TBD 4.4, 4.5.

## P4.05 — `distributed/outcome.py`, `distributed/reducer.py`
- `outcome.merge_result_dirs(dirs: list[Path], into: Path) -> JobDiagnostics`: copies every `<job_id>.json/.npz` pair into `into`; when `into` already holds that job id, compares a content hash of the points (sha256 of `src_pts.tobytes() + dst_pts.tobytes()` after rounding to 1e-9) — equal → counted as duplicate; different → new `JobDiagnostics.n_mismatched` += 1 and the sample records both hosts (a determinism failure; the first copy is kept).
- `reducer.reduce_run(..., require_consistent: bool = False)` (new keyword): when True, any mismatched duplicate → `ReduceOutcome.status = RunStatus.EVAL_FAILED` with detail naming the job ids.
- Determinism inputs: every job's matcher runs with its `job.seed`; `torch.manual_seed(job.seed)` and `cv2.setRNGSeed(job.seed)` in `process_job` before matching; `torch.backends.cudnn.deterministic = True` for CUDA workers.
Tests (`tests/test_multihost_semantics.py`): two result dirs with identical content → duplicates counted, 0 mismatches; a perturbed copy → mismatch counted and `require_consistent=True` fails the reduce; `RedisJobQueue` (fakeredis) + two in-process workers named `laptop-gpu0` / `rtx3060-gpu0` (CPU device) over the Phase 3 synthetic pair → the reduced transform equals the Phase 3 local-queue transform byte for byte.

## P4.06 — RUN (gpu, 2 hosts)
Preconditions (each failing one → BLOCKER naming it): `configs/hosts.json` exists and validates; `redis-cli -a … ping` → PONG from the laptop to the broker address; the second host answers `ssh … true`; both hosts at the same git HEAD; the 3060 profile exists.
1. Plan: `lunar-reg distributed plan --pair-id <anchor sift id> --source-label … --reference-label … --tile-px 512 --run-dir data/processed/multihost/anchor --fleet configs/hosts.json --redis-url <url> --run-id anchor` (writes `plan.json` with tiers and puts the jobs into Redis; the `plan`, `worker`, `status` and `reduce` subcommands are added in P4.04).
2. `scripts/cluster_up.sh configs/hosts.json anchor`; wait until `stats()` shows no pending/leased jobs (poll `lunar-reg distributed status --redis-url … --run-id anchor` every 30 s — `status` subcommand also added in P4.04).
3. Fault check: kill the 3060 worker once mid-run (`ssh … pkill -f "worker-id rtx3060-gpu0"`) and restart it; the lost job must be reclaimed and counted.
4. Collect results: `rsync` each host's results dir into `data/processed/multihost/anchor/results_<host>/`; `lunar-reg distributed reduce --run-dir data/processed/multihost/anchor --merge results_laptop results_rtx3060 --require-consistent --redis-url <url> --run-id anchor`. The reduce subcommand's run record `outcome_counts` holds every `JobStatus` count plus `lost_events` (from the queue stats), `duplicates` and `mismatched` (from the merge).
5. `docs/MULTIHOST_RUN.md` (G26): hosts and GPUs, jobs per host, bytes read per host (from `bytes_read`), lost events, duplicates and mismatches, reduced transform vs the Phase 3 single-host transform — each number with its artefact path.
Artefacts checked: run record C15-valid; merged results with 0 mismatches; `lost_events ≥ 1`; the doc citing `data/processed/multihost/anchor/`.
