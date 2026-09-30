# LLD — Redis Streams queue (P4.01)

Produces: C27 `RedisJobQueue`. Decisions: G04, G25, G31, G36 (review RC01/04/28/29/33). TBD 4.1. Facts (research, `.fable/research_20260929.json`): redis-py 8.1 defaults to RESP3 (dict replies) — pin `protocol=2`; `XAUTOCLAIM` replies have 2 elements on Redis 6.2 and 3 on ≥ 7.0; Ubuntu 24.04 ships redis-server 7.0.15 (not installed; human installs with sudo); fakeredis 2.38 supports streams and `XAUTOCLAIM` with `version=(7,)`.

## 1. Dependencies (`pyproject.toml`)
New optional extra `cluster = ["redis>=5.0", "fakeredis>=2.20"]`. Nothing in the base install imports redis.

## 2. Keys (prefix `p = f"{stream_prefix}:{run_id}"`)
| key | type | content |
|---|---|---|
| `{p}:jobs:<tier>` | stream | entries `{"job_id", "payload"}`; `<tier>` = a registered P4.03 tier name (`t0`, `t1`, …) or an automatic bucket `b<k>` (C27) |
| `{p}:tiers` | hash | `tier → max_bytes` (every stream that exists is registered here first) |
| `{p}:tier_of` | hash | `job_id → tier` (so reclaim re-adds a job to its own stream) |
| `{p}:state` | hash | `job_id → "pending|leased|done|failed:<status>"` |
| `{p}:attempts` | hash | `job_id → int` |
| `{p}:payload` | hash | `job_id → payload JSON` (needed to re-add a reclaimed job) |
| `{p}:lost` | string counter | number of lost events |
| consumer group | `group` (default `workers`) on every tier stream, created with `XGROUP CREATE <stream> <group> 0 MKSTREAM` when the tier is registered (ignore `BUSYGROUP`); id `0`, not `$`, so entries added before the group exists are still delivered |

## 3. Methods (C24 semantics)
| method | Redis commands |
|---|---|
| `register_tiers(tiers)` | for each `Tier`: `HSET tiers name max_bytes` + group creation; a name already registered with a different `max_bytes` → `ValueError` (programmer error) |
| `put(job, tier=None)` | `HSETNX state job_id pending` → 0 means known → return False; `tier=None` → automatic bucket `b<k>` (C27), registered on first use; a named tier not in `{p}:tiers` → `ValueError`; else `HSET payload`, `HSET attempts 0`, `HSET tier_of`, `XADD {p}:jobs:<tier> * job_id … payload …` → True |
| `claim(worker_id, lease_s, max_bytes=None)` | `HGETALL tiers` → keep tiers with `max_bytes_tier <= max_bytes` (all when None), sorted by `max_bytes` descending; for each: `XREADGROUP GROUP group worker_id COUNT 1 STREAMS <stream> >`; the first entry wins: `HINCRBY attempts`, `HSET state leased`, return `Lease(job, worker_id, lease_id=f"{tier}/{entry_id}", deadline_utc=time.time()+lease_s, attempt)`. An entry whose `state` is no longer `pending` (closed elsewhere) is `XACK`+`XDEL`ed and the next tier is tried — it is removed, never re-added, so claim cannot spin (review RC04). No entry in any allowed tier → `None`. |
| `ack(lease, status)` | `XACK <stream> group <entry_id>` → 0 means already reclaimed → return False; else `XDEL` the entry (review RC28: streams hold only live work), `HSET state done` or `failed:<status>`; return True |
| `renew(lease, lease_s)` | `XPENDING <stream> group <entry_id> <entry_id> 1` → no row, or owner ≠ `lease.worker_id` → False; else `XCLAIM <stream> group <lease.worker_id> 0 <entry_id> JUSTID` → non-empty reply → True (idle time reset, delivery count unchanged) (review RC29). The owner check is mandatory: `XCLAIM` with min-idle 0 takes an entry from *any* consumer, including `__reclaimer__` (measured on fakeredis, 2026-09-30). |
| `reclaim_expired(lease_s=None)` | for every registered tier stream: `XAUTOCLAIM <stream> group __reclaimer__ min_idle_ms 0-0 COUNT 100` (repeat while the cursor ≠ `0-0`); reply parsed accepting length 2 or 3; for each claimed entry: `XACK` + `XDEL` it; `attempts ≥ MAX_ATTEMPTS` → `HSET state failed:worker_lost`; else re-`XADD` the payload to the same stream and `HSET state pending`; `INCR lost`; returns re-queued job ids. `min_idle_ms = int(1000 * (lease_s if lease_s is not None else self.default_lease_s))`. |
| `stats()` | counts over `HVALS state` (`pending`, `leased`, `done`, `failed:*`) + `GET lost` |
| `purge()` | `SCAN MATCH {p}:*` then `DEL` every key; returns the number deleted (review RC28; run by `distributed status --purge` after the reduce) |
Stream growth (review RC28): acked and reclaimed entries are `XDEL`ed, so a stream holds at most the run's live jobs; `MAXLEN` trimming is **not** used because it can drop pending jobs (G36). `purge()` removes the run's keys once its results are reduced.
Transport (review RC33): the URL is passed to redis-py unchanged, so `rediss://` (TLS) works when the broker is configured for TLS; the runbook's default is `requirepass` + `bind <LAN ip> 127.0.0.1`, and it documents an SSH tunnel for untrusted networks. The URL is never logged (log `host:port` only).
The client is `redis.Redis.from_url(url, protocol=2, decode_responses=True)` unless `client` is injected (tests pass `fakeredis.FakeRedis(decode_responses=True, version=(7,))`). Password: taken from the URL (`redis://:<pw>@host:6379/0`), which the runner builds from `configs/hosts.json` `broker` and the env var named by `password_env` (never logged).

## 4. Tests (`tests/test_redis_queue.py`, fakeredis; plus tests named `test_real_server_*`, marked `data`, that connect to `os.environ["REDIS_URL"]` and skip with a reason when it is unset — `Phase_4/harness/verify.sh` starts a throwaway redis-server and sets it)
The C24 behaviour suite of `Phase_3/harness/tests/test_contracts_P3.py` ported to `RedisJobQueue` (dedupe, lease expiry → reclaim + lost counted with a monkeypatched idle via `XAUTOCLAIM` min-idle 0, max attempts → `worker_lost`, `max_bytes` routing, renew before and after reclaim), plus: a claim with no fitting tier returns `None` and leaves every stream length unchanged; after all jobs are acked every stream has length 0; `purge()` leaves no `{p}:*` key; a 2-element `XAUTOCLAIM` reply (monkeypatched client method) parses; the client is created with `protocol=2` (monkeypatch `redis.Redis.from_url` and assert the kwarg).
