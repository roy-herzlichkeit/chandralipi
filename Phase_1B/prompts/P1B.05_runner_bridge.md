# P1B.05 — site runner: bridge mode
DEPENDS ON: P1B.02, P1B.03, P1B.04
LOAD: `Phase_1B/LLD/bridge_runner.md` (§P1B.05), `Phase_0/skills/classified-outcomes/SKILL.md`, `Phase_0/skills/provenance-fields/SKILL.md`, `src/lunar_reg/sites/runner.py`, `scripts/run_vikram.py`
GOAL: The site runner can register each strip against both the NAC and the rendered DTM by consensus, and keep the better-conditioned result.
DO:
1. Implement LLD §P1B.05.
2. Add `tests/test_runner_bridge.py`.
DON'T: change non-bridge behaviour.
DONE WHEN: `bash Phase_1B/harness/check_P1B.05.sh` exits 0
HANDOFF: follow root CLAUDE.md §Handoff
