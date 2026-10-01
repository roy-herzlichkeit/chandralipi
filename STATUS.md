# STATUS

current: P0.05
phase: 0
state: READY
branch: phase-0
last_done: P0.04
notes:
- P0.04: moon_datum moved to constants.py (verbatim); ingest/footprint.py, tests/test_footprint.py, configs/default.yaml deleted; PyYAML dep and README configs line removed; ingest exports moon_datum from constants.
- Q-P0.04-1 (non-blocking): harness grep forced a comment-only edit in scripts/fetch_catalogue.py:73 (file not in LLD table).
- scripts/ci.sh: 441 passed, 5 deselected (7 legacy footprint tests gone).
- P1.DL (download session) may run before Phase 0 is approved: see Phase_1/prompts/P1.DL_download_session.md.
