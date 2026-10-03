# P1B.02 — rendered reference preparation
DEPENDS ON: P1B.01
LOAD: `docs/plan/CONTRACTS.md` (C10, C11, C13, C21), `Phase_1B/LLD/rendered_reference.md`, `Phase_0/skills/provenance-fields/SKILL.md`, `src/lunar_reg/pairs.py`
GOAL: Prepare a rendered-DTM reference under the source's sun, with the OHRC azimuth convention calibrated on the registered anchor.
DO:
1. Implement LLD §2 in `pairs.py`.
2. Add `tests/test_rendered_reference.py` per LLD §3.
DON'T: change `prepare_window_pair`'s behaviour (C11 frozen).
DONE WHEN: `bash Phase_1B/harness/check_P1B.02.sh` exits 0
HANDOFF: follow root CLAUDE.md §Handoff
