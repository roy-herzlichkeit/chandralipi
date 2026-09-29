# Phase 3 — distributed processing on one machine (for the human reviewer)

## Goal
Split one big registration (a full-resolution OHRC window against the NASA map) into many small **jobs** that several **workers** can do at the same time, survive a worker crashing, and put the pieces back together into exactly the same answer as doing it in one go.

## New terms
| term | meaning | example |
|---|---|---|
| **job** | one self-contained piece of work: which image windows to read and how to match them | "match OHRC tile 12 against the NAC window around (5300, 8100)" |
| **job id** | a fingerprint (SHA-256) of the job's exact description; the same job always has the same id | used as the result's file name, so a job done twice still has one result |
| **worker** | a process that takes a job, does it, writes the result | 1 GPU worker + 2 CPU workers on the laptop |
| **queue** | the shared to-do list of jobs (here a small database file) | `run_dir/queue.sqlite` |
| **lease** | a time-limited claim on a job; if the worker does not finish in time, the job goes back on the list | a killed worker's job is re-done by another worker and counted as WORKER_LOST |
| **reducer** | the step that collects all job results and fits the final transform | sorts points by job id so the answer does not depend on who finished first |

## Prompts
P3.00 preflight → P3.01 job → P3.02 outcomes/results → P3.03 planner → P3.04 queue → P3.05 worker → P3.06 reducer → P3.07 local runner + CLI → P3.08 fault injection and determinism tests → P3.09 real run on the anchor strip.
