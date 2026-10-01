# STATUS

current: P0.07
phase: 0
state: READY
branch: phase-0
last_done: P0.06
notes:
- P0.06: fetch_catalogue ISSDC rows write corner* = None + footprint_wkt (polygon_to_wkt of the ring); _corner_columns deleted. overlap.polygon_from_wkt added; footprint_from_row prefers corners > footprint_wkt > bbox.
- Q-P0.06-1 (non-blocking): removed `from __future__ import annotations` from scripts/fetch_catalogue.py so importlib-loaded @dataclass works (py3.12 dataclasses needs sys.modules entry). Same trap likely for run_vikram in P0.11.
- scripts/ci.sh: 471 passed, 6 deselected. Catalogue NOT re-fetched (no network).
- P1.DL may run before Phase 0 approval (Phase_1/prompts/P1.DL_download_session.md).
