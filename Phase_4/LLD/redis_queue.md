# LLD — Redis Streams queue (P4.01)

Produces: C27 `RedisJobQueue`. Decisions: G04, G25, G31. TBD 4.1. Facts (research, `.fable/research_20260929.json`): redis-py 8.1 defaults to RESP3 (dict replies) — pin `protocol=2`; `XAUTOCLAIM` replies have 2 elements on Redis 6.2 and 3 on ≥ 7.0; Ubuntu 24.04 ships redis-server 7.0.15 (not installed; human installs with sudo); fakeredis 2.38 supports streams and `XAUTOCLAIM` with `version=(7,)`.

## 1. Dependencies (`pyproject.toml`)
New optional extra `cluster = ["redis>=5.0", "fakeredis>=2.20"]`. Nothing in the base install imports redis.

## 2. Keys (prefix `p = f"{stream_prefix}:{run_id}"`)
| key | type | content |
|---|---|---|
| `{p}:jobs:<tier>` | stream | entries `{"job_id", "payload"}`; `<tier>` = `default` unless P4.03 routing is used |
| `{p}:state` | hash | `job_id → "pending|leased|done|failed:<status>"` |
| `{p}:attempts` | hash | `job_id → int` |
| `{p}:payload` | hash | `job_id → payload JSON` (needed to re-add a reclaimed job) |
| `{p}:lost` | string counter | number of lost events |
| consumer group | `group` (default `workers`) on every tier stream, created with `XGROUP CREATE … $ MKSTREAM` at construction (ignore `BUSYGROUP`) |

## 3. Methods (C24 semantics)
| method | Redis commands |
|---|---|
| `put(job, tier="default")` | `HSETNX state job_id pending` → 0 means known → return False; else `HSET payload`, `HSET attempts 0`, `XADD {p}:jobs:<tier> * job_id … payload …` → True |
| `claim(worker_id, lease_s, max_bytes=None)` | for each tier stream this worker may read (P4.03; default `[default]`): `XREADGROUP GROUP group worker_id COUNT 1 STREAMS stream >`; an entry whose job's `est_vram_bytes > max_bytes` is re-added (`XADD` same fields) and acknowledged (`XACK`) without counting an attempt, then the next entry is tried (at most 16 skips per call); on success `HINCRBY attempts`, `HSET state leased`, return `Lease(job, worker_id, lease_id=<entry id>, deadline=time.time()+lease_s, attempt)` |
| `ack(lease, status)` | `XACK stream group lease_id` → 0 means already reclaimed → return False; else `HSET state done` or `failed:<status>`; return True |
| `reclaim_expired(lease_s=None)` | `XAUTOCLAIM stream group __reclaimer__ min_idle_ms 0-0 COUNT 100` (repeat while the cursor ≠ `0-0`); reply parsed accepting length 2 or 3; for each claimed entry: `XACK` it; `attempts ≥ MAX_ATTEMPTS` → `HSET state failed:worker_lost`; else re-`XADD` the payload and `HSET state pending`; `INCR lost`; returns re-queued job ids. `min_idle_ms = int(1000 * (lease_s or self.default_lease_s))`. |
| `stats()` | counts over `HVALS state` (`pending`, `leased`, `done`, `failed:*`) + `GET lost` |
The client is `redis.Redis.from_url(url, protocol=2, decode_responses=True)` unless `client` is injected (tests pass `fakeredis.FakeRedis(decode_responses=True, version=(7,))`). Password: taken from the URL (`redis://:<pw>@host:6379/0`), which the runner builds from `configs/hosts.json` `broker` and the env var named by `password_env` (never logged).

## 4. Tests (`tests/test_redis_queue.py`, fakeredis; plus tests named `test_real_server_*`, marked `data`, that connect to `os.environ["REDIS_URL"]` and skip with a reason when it is unset — `Phase_4/harness/verify.sh` starts a throwaway redis-server and sets it)
The C24 behaviour suite of `Phase_3/harness/tests/test_contracts_P3.py` ported to `RedisJobQueue` (dedupe, lease expiry → reclaim + lost counted with a monkeypatched idle via `XAUTOCLAIM` min-idle 0, max attempts → `worker_lost`, `max_bytes` skip), plus: a 2-element `XAUTOCLAIM` reply (monkeypatched client method) parses; the client is created with `protocol=2` (monkeypatch `redis.Redis.from_url` and assert the kwarg).
