# Phase 4 — two machines (for the human reviewer)

## Goal
Run the same jobs as Phase 3 on two computers at once — the laptop (RTX 4060, 8 GB) and a second machine (RTX 3060, 6 GB) — with a shared to-do list, so a crash on one machine is detected and its work redone, and the final answer is identical to the one-machine run.

## New terms
| term | meaning | example |
|---|---|---|
| **broker** | the program holding the shared to-do list; here Redis, running on the laptop | other machines connect to it by its LAN IP address |
| **Redis Stream** | Redis's built-in append-only list that several workers can read from without taking the same item twice | `lunar:anchor:jobs:t1` |
| **consumer group / pending list** | Redis remembers which worker took which item until the worker says "done" (ACK) | a worker that dies leaves its item pending |
| **XAUTOCLAIM** | the Redis command that finds items pending for too long and hands them back | used to detect a lost worker (WORKER_LOST) |
| **capacity tier** | a bucket of jobs sized for GPUs with at least that much free memory | a 5 GiB job only goes to the laptop's tier |
| **node cache** | a local copy of the input files on each machine, checked against the download manifest | `~/lunar_cache/data/raw/...` |

## What the human must do (runbook)
Answer the second-host questions (OS, network, disk, Python), install Redis on the laptop, set up the repo on the second machine at the same commit, measure its GPU profile, fill `configs/hosts.json`, then run `scripts/cluster_up.sh` — all spelled out in `docs/RUNBOOK_MULTIHOST.md` (written by P4.04).
