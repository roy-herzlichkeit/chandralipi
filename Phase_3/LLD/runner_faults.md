# LLD — local runner + CLI (P3.07), fault injection + determinism (P3.08), single-host run (P3.09)

TBD 3.1–3.5, 4.4.

## P3.07 — `distributed/runner.py`, `cli.py` (`distributed` subcommand)
```python
@dataclass
class LocalRunReport:
    run_dir: Path; plan: PlanReport; queue: QueueStats; workers: list[WorkerSummary]
    reduce: ReduceOutcome; run_record_path: Path
    def report(self) -> str
def run_local(plan: PlanReport, run_dir, *, gpu_workers: int = 1, cpu_workers: int = 2,
              lease_s: float = 120.0, reclaim_every_s: float = 5.0, repo_root=".",
              matcher_factory=None, worker_target=None) -> LocalRunReport
```
- `run_dir/queue.sqlite` (LocalJobQueue), `run_dir/results/`, `run_dir/plan.json` (list of job JSONs), `run_dir/run_record.json`.
- Workers are `multiprocessing.get_context("spawn").Process(target=worker_target or _worker_main, args=(queue_path, results_dir, worker_id, device, lease_s, repo_root))` (the target must be picklable: a module-level function or a `functools.partial` of one); each worker `os.chdir(repo_root)` before claiming; worker ids `gpu0`, `cpu0`, `cpu1`, …; GPU workers get `device="cuda:0"` (only when CUDA is available — else they are started as CPU workers and the report says so); CPU workers get `"cpu"`.
- Main loop every `reclaim_every_s`: `reclaim_expired()`; exits when `pending + leased == 0`. **All workers dead** (review RC06, G36): when no worker process is alive while `pending + leased > 0`, the loop calls `reclaim_expired()` once more, then `queue.close_unfinished(JobStatus.WORKER_LOST)` (a `LocalJobQueue` method: every pending/leased job → `failed` with status `worker_lost`, one `closed_lost` event each, returns the count), sets `LocalRunReport.aborted = "all workers exited with <n> job(s) unfinished"`, and continues to the reducer with what exists; the CLI then exits 1. `LocalRunReport` gains `aborted: str | None = None`. Then it joins workers (terminate after 30 s), `reduce_run`, writes the run record (counts per `JobStatus` + `lost_events` + reducer status) and returns the report.
- CLI: `lunar-reg distributed run --pair-id ID --results-root data/processed/results --source-label PATH --reference-label PATH --tile-px 512 --matcher sift --gpu-workers 1 --cpu-workers 2 --run-dir DIR`: loads the stored result, `plan_inputs_from_result`, `plan_jobs`, `run_local`, saves the reduced `PairResult` into `--results-root` (`save_results`, overwrite with `--overwrite`), prints the report; exit 0 when the reducer is OK.

## P3.08 — `distributed/faults.py` + `tests/test_distributed_faults.py`
```python
@dataclass
class FaultPlan:
    kill_after_claims: dict[str, int] = field(default_factory=dict)  # worker_id -> exit (os._exit(1)) right after its n-th claim, before acking
    oom_jobs: set[int] = field(default_factory=set)                   # tile indices whose matcher raises torch.OutOfMemoryError
    read_fail_jobs: set[int] = field(default_factory=set)             # tile indices whose source path is replaced by a missing file
    duplicate_jobs: set[int] = field(default_factory=set)             # tile indices written twice (second write must be a no-op)
def faulty_worker_main(fault_plan_json: str) -> Callable   # returns functools.partial(_faulty_worker, fault_plan_json): picklable, used as run_local's worker_target
def faulty_matcher_factory(fault_plan: FaultPlan, base_factory) -> Callable
```
Tests (all CPU, synthetic GeoTIFFs, SIFT, ≤ 30 s each; fixtures use non-zero window offsets, G37): (1) killing `cpu0` after its first claim → the job is reclaimed (`lost_events ≥ 1`) and finished by another worker; the final queue has no `leased` rows; (2) OOM-injected tiles → `oom` count equals the injected count and the reducer still succeeds from the rest; (3) read failures → `read_failed` counted; (4) duplicates → `n_duplicates` equals the injected count and each job has exactly one result file pair; (5) determinism: the same plan run with (1 worker) and (3 workers, reversed claim order via a planted clock) gives byte-identical reduced transforms; (6) every job ends in exactly one terminal state (done/failed) — 100 % classification; (7) every worker killed after its first claim → `run_local` returns (no hang), `aborted` is set and every job is terminal.

## P3.09 — RUN (gpu): single-host distributed run
Preconditions: CUDA; anchor v2 result with recorded crop geometry in the live store; native source/reference readable.
1. `lunar-reg distributed run --pair-id <anchor sift pair id from the live index> --source-label <anchor OHRC label> --reference-label data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml --tile-px 512 --matcher sift --gpu-workers 1 --cpu-workers 2 --run-dir data/processed/distributed/anchor --results-root data/processed/results --overwrite`
2. Single-process comparison: `refine_native_arrays` (C19) on the same windows and prior (a small script inline with `python -c`, output JSON `data/processed/distributed/anchor/single_process.json` = `{"transform": [9 floats, row-major, source-native px -> reference-native px], "status": <NativeStatus value>, "n_matches": int}`); record the max probe difference between the two transforms in reference px.
3. `docs/DISTRIBUTED_RUN.md` (G26): what a job, worker, queue, lease and reducer are; the run's counts per status (from the run record), lost events, duplicates, the transform comparison — each number with its artefact path.
Artefacts checked: run record C15-valid, `plan.json`, no `leased` rows left in `queue.sqlite`, reduced row `<pair>_dist` in the live store, `single_process.json`, the doc citing `data/processed/distributed/anchor/`.
