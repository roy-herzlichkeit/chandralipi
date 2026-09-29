# P1B.01 — DTM shaded-relief renderer
DEPENDS ON: P1B.00
LOAD: `CONTRACTS.md` (C21 render), `Phase_1B/LLD/render.md`, `src/lunar_reg/ingest/sun.py`, `src/lunar_reg/eval/scenes.py`
GOAL: Render the NAC DTM as shaded relief with cast shadows under any sun direction.
DO:
1. Create `src/lunar_reg/eval/render.py` per LLD §1.
2. Apply LLD §2 to `eval/scenes.py`.
3. Add `tests/test_render.py` per LLD §3.
DON'T: change `lambert_shade`'s conventions.
DONE WHEN: `bash Phase_1B/harness/check_P1B.01.sh` exits 0
HANDOFF: follow root CLAUDE.md §Handoff
