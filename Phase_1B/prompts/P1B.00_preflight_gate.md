# P1B.00 — preflight + exp-1 gate
DEPENDS ON: P2 approved
LOAD: `CLAUDE.md`, `docs/plan/DECISIONS.md` (G02, G07, G29), `docs/plan/CONTRACTS.md` (C20), `Phase_1B/ASSUMPTIONS.md`, `Phase_0/skills/tests-and-checks/SKILL.md`
GOAL: Decide from the exp-1 gate whether Phase 1B is built, and set up the branch or record the skip.
DO:
1. `git tag -l phase-2-approved` must print the tag, else BLOCKER.
2. Read `data/processed/vikram/exp1_gate.json` and validate it with `.venv/bin/python -m pytest -o addopts="" -p no:cacheprovider Phase_1/harness/tests/test_contracts_P1.py -k C20`; missing/invalid → BLOCKER.
3. If `decision == "SKIP_1B"`: `git checkout main`; `git checkout -b phase-1B`; write `Phase_1B/SKIPPED.md` (the gate JSON verbatim in a code block, plus one sentence: "Phase 1B skipped per DECISIONS G02"); set INDEX status `skipped` for P1B.01–P1B.06 and `done` for P1B.00; run `bash Phase_1B/harness/check_P1B.00.sh` (must exit 0; on failure follow CLAUDE.md §Handoff step 6); then set `docs/plan/STATUS.md` `current: P3.00`, `state: REVIEW_GATE`, `last_done: P1B.00`, `notes: Phase 1B skipped per exp1_gate (DECISIONS G02); waiting for tag phase-1B-approved`; commit `P1B.00: preflight + exp-1 gate (skip)`; `git tag phase-1B-done`; stop (no REVIEW_PACK is needed for a skip; review RC37).
4. If `decision == "BUILD_1B"`: `git checkout main`; `git checkout -b phase-1B`; `git status --porcelain` empty; re-run consumed contract tests (P0, P1, P2 contract files); check `Phase_1B/ASSUMPTIONS.md`; continue with §Handoff.
DON'T: edit anything except `docs/plan/STATUS.md`, `Phase_1B/prompts/INDEX.md`, and (skip case only) `Phase_1B/SKIPPED.md`.
DONE WHEN: `bash Phase_1B/harness/check_P1B.00.sh` exits 0
HANDOFF: follow root CLAUDE.md §Handoff (P1B.00 skip case: the DO step replaces it)
