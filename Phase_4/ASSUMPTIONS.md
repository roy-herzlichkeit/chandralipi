# Phase 4 — assumptions

| contract | used by | re-run by P4.00 |
|---|---|---|
| C22–C26 | every Phase 4 prompt | `test_contracts_P3.py` |
| C08 | node cache (P4.02) | `test_contracts_P1.py -k C08` |
| C16 | routing (P4.03) | `test_contracts_P2.py -k C16` |

| # | assumption | command | expected | if not |
|---|---|---|---|---|
| A4-1 | `phase-3-approved` exists | `git tag -l phase-3-approved` | tag | BLOCKING |
| A4-2 | second host details (CLARIFY R3b: OS, LAN, SSH, disk, Python) | the runbook's step 1 commands, run by the human on that host | answered in `Phase_4/QUESTIONS.md` | non-blocking until P4.06 |
| A4-3 | redis-server ≥ 6.2 on the broker host | `redis-server --version` | 7.0.x (Ubuntu 24.04 candidate 7.0.15) | non-blocking until P4.06; verify.sh skips real-server tests with a reason |
| A4-4 | PyPI reachable once for the `cluster` extra | `.venv/bin/python -m pip download redis --no-deps -d /tmp/x -q` | succeeds | BLOCKING for P4.01 |
| A4-5 | RTX 3060 profile produced on the second host | `ls configs/device_profiles/rtx3060.json` | exists | BLOCKING for P4.06 |
