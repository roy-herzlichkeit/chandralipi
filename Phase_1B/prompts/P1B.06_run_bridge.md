# P1B.06 — RUN: bridge on 2023 strips + RIFT2 baseline
DEPENDS ON: P1B.05
LOAD: `Phase_1B/LLD/bridge_runner.md` (§P1B.06), `Phase_1/skills/run-prompts/SKILL.md`, `Phase_2/skills/gpu-safety/SKILL.md`, `Phase_0/skills/provenance-fields/SKILL.md`
GOAL: Measure whether the illumination bridge registers the 2023 strips, with RIFT2 as the classical baseline.
DO:
1. Execute LLD §P1B.06 steps 1–3.
2. In `docs/plan/STATUS.md` notes: per strip, whether the TBD 1.8 targets were met (copied from the doc's table, path cited).
DON'T: edit code; quote numbers without paths.
DONE WHEN: `bash Phase_1B/harness/check_P1B.06.sh` exits 0
HANDOFF: follow root CLAUDE.md §Handoff
