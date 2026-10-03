# P1B.03 — pooled multi-matcher consensus
DEPENDS ON: P1B.00
LOAD: `docs/plan/CONTRACTS.md` (C02, C06, C07, C14, C21), `Phase_1B/LLD/consensus.md`, `Phase_0/skills/classified-outcomes/SKILL.md`
GOAL: Fit one transform from the correspondences of every matcher that agrees, and reject disagreement explicitly.
DO:
1. Create `src/lunar_reg/consensus.py` per C21 and LLD §1–§2.
2. Add `tests/test_consensus.py` per LLD §3.
DON'T: average transforms; hide excluded matchers.
DONE WHEN: `bash Phase_1B/harness/check_P1B.03.sh` exits 0
HANDOFF: follow root CLAUDE.md §Handoff
