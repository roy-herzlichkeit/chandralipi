# P1B.04 — RIFT2 fixes
DEPENDS ON: P1B.00
LOAD: `Phase_1B/LLD/rift2.md`, `src/lunar_reg/match/rift2/mim.py`, `src/lunar_reg/match/rift2/descriptor.py`, `src/lunar_reg/match/rift2/matcher.py`
GOAL: RIFT2's documentation matches its behaviour, and its keypoints and matches have no duplicates.
DO:
1. Apply LLD items A072 and A125.
2. Add `tests/test_rift2_fixes.py`.
3. Run `.venv/bin/python -m pytest tests/test_rift2.py tests/test_rift2_fixes.py`.
DON'T: implement grid rotation.
DONE WHEN: `bash Phase_1B/harness/check_P1B.04.sh` exits 0
HANDOFF: follow root CLAUDE.md §Handoff
