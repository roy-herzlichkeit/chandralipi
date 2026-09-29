# Phase 4 — review checklist (human)

Diff range: `git diff phase-3-approved..phase-4` (G07).
- [ ] `REVIEW_PACK_4.md`: verify exit 0; real redis-server tests ran (not skipped) if Redis is installed.
- [ ] `docs/MULTIHOST_RUN.md`: jobs per host, bytes read per host, lost events, mismatches, and the transform vs Phase 3 — each with a path.
- [ ] `git ls-files configs/` shows `hosts.example.json` only (no real addresses or secrets).
- [ ] Redis bound to the LAN address with a password (runbook step 2).
- [ ] `Phase_4/QUESTIONS.md`: R3b answered.
