# CLAUDE.md — Chandralipi (implementer sessions)

**Which role you are.** If your system prompt contains the contents of `.fable/ARCHITECT.md` (launched as `claude -n FABLE --append-system-prompt-file .fable/ARCHITECT.md`), you are the architect: follow that file; this file does not apply. Otherwise you are an **implementer** and everything below applies.

As an implementer you execute prompt files from `Phase_<i>/prompts/`, one prompt per session step, exactly as written.

## §Start

1. Read `STATUS.md`. Its `current:` line names one prompt id (`P<i>.<jj>`).
2. `state:` handling:
   | state | action |
   |---|---|
   | `READY` | continue |
   | `REVIEW_GATE` | if the tag named in `notes:` exists (`git tag -l <tag>` prints it): `git checkout main`, set `state: READY`, continue. Otherwise print `notes:` and stop. |
   | `FAILED`, `BLOCKED` | print `notes:` for the human and stop. The human sets `state: READY` after resolving. |
3. Open `Phase_<i>/prompts/INDEX.md`, find the row for that id, open the prompt file it names.
4. Load exactly what the prompt's `LOAD:` line lists (LLD sections, skills, files). Do not read other `Phase_*` folders unless `LOAD:` names them.
5. Execute `DO:` in order. Respect `DON'T:`. Finish with §Handoff.

## §Rules

### Fences
| rule | exact behaviour |
|---|---|
| file fence | Create, modify or delete only the files the prompt's `DO:` names, plus new test files `tests/test_*.py`, plus edits to existing `tests/test_*.py` assertions that encode behaviour the prompt's `DO:` deliberately changes (name each such test in the commit message body). Any other file needs a QUESTIONS entry first. |
| protected: harness + benchmark | Never create, modify, delete or rename anything under `Phase_*/harness/**` or `Phase_*/benchmark/**`. The only exceptions are the files the scripts themselves write when run: `Phase_*/benchmark/score.json` and `Phase_*/benchmark/out/**`. A changed harness file fails `MANIFEST.sha256` and fails the phase. |
| protected: plan | Never edit `AUDIT.md`, `HLD.md`, `DECISIONS.md`, `CONTRACTS.md`, `PHASES.md`, `PLAN_PROGRESS.md`, `Phase_*/LLD/**`, `Phase_*/ASSUMPTIONS.md`, `Phase_*/DECISIONS.md`, `Phase_*/REVIEW_FOCUS.md`, `Phase_*/skills/**`, `Phase_*/prompts/P*.md`, `.fable/**`, `FABLE_NOTES.md`, `FABLE_REVIEW.md`, `CLARIFY.md`. If one of them is wrong, write a QUESTIONS entry. |
| editable process files | `STATUS.md`, `Phase_*/prompts/INDEX.md` (status column only), `Phase_*/QUESTIONS.md`, `Phase_*/REVIEW_PACK_<i>.md`. |
| no scope creep | No refactors, renames, reformatting or "improvements" the prompt does not ask for. `ruff format` only files you modified in this prompt. |
| contracts | Signatures, field names, enum members and file formats in `CONTRACTS.md` are frozen. Match them character for character. |
| network | No network access except in prompts whose `DO:` explicitly runs a download script (P1.DL, the P1.02 run step, the P1.11 `pip install` of the `spice` extra, the P4.00 LAN host probe, the P4.01 `pip install` of the `cluster` extra, P4.06's LAN traffic between the two hosts). PRADAN (ISRO) pages are never automated: the human clicks. |
| data | Never delete or overwrite anything under `data/raw/`. Under `data/processed/`, move (not delete) when a prompt says to archive. |
| docs and numbers | Any number written into any doc must come from a run artefact whose path is cited in the same sentence or table row. Otherwise write `[INSERT RESULT]`. |

### Standing conventions (from `CONTEXT.md` §"Three conventions"; violating them fails review)
1. Provenance is carried in code: every new numeric output carries a `lunar_reg.provenance.ValueSource` field (or an existing provenance enum), never only a comment.
2. Failures are classified, counted and sampled, never skipped: an enum outcome per failure mode, a diagnostics object with per-status counts and the first sample, and a `report()` that the caller prints on every run. Library code logs one summary line; it does not print.
3. No number is written that a run did not produce.

### Environment
- Python: `.venv/bin/python` (3.12). Tests: `.venv/bin/python -m pytest`. Lint: `.venv/bin/ruff`.
- Full CPU suite entry point after P0.01: `scripts/ci.sh`.
- GPU: RTX 4060 Laptop, 8 GB, ~0.75 GB taken by the desktop. Never start two GPU processes at once unless the prompt says so.
- Budgets (DECISIONS G18): check < 30 s, `verify.sh` ≤ 20 min, `benchmark/run.sh` ≤ 45 min, host RAM ≤ 12 GB.

### Doubts
Write to `Phase_<i>/QUESTIONS.md`, one entry per doubt:
```
## Q-P<i>.<jj>-<n> [BLOCKER]?  <one-line title>
context: <file:line or LLD section>
question: <exact question>
what I did meanwhile: <nothing | the choice taken and why it is reversible>
```
Prefix `BLOCKER` when the prompt cannot reach DONE WHEN without an answer. On a BLOCKER: set `STATUS.md` `state: BLOCKED`, commit nothing, stop and summarise for the human. A non-blocking entry does not stop work; take the most reversible choice and record it.

### Git
- Work on branch `phase-<i>` (P<i>.00 creates it). Never commit to `main`, never push, never merge, never delete or move tags.
- One commit per prompt, only after its check passes, message `P<i>.<jj>: <title>` (title from INDEX.md).
- Never `git add` anything under `data/` (it is gitignored), `.venv/`, or large binaries.

## §Handoff (after each prompt)

1. Run the prompt's check: `bash Phase_<i>/harness/check_P<i>.<jj>.sh`.
2. If it fails: fix and re-run, at most 3 further attempts within this session. Still failing → go to step 6.
3. On pass: set the prompt's INDEX.md status to `done`, update `STATUS.md` (step 5), `git add -A` (respecting the Git rules), commit `P<i>.<jj>: <title>`.
4. If any `BLOCKER` entry was written during this prompt → `state: BLOCKED`, stop.
5. `STATUS.md`: `current:` = the next id in INDEX.md order (skip rows whose status is `done` or `skipped`; P1.DL is never "next"); `state: READY`; `last_done:` = this id; `notes:` ≤ 5 lines (what changed, anything the next prompt must know). If this was the last prompt of the phase → do §Phase end instead of opening the next prompt.
6. On failure: INDEX.md status `failed`; `STATUS.md` `state: FAILED`, `current:` unchanged, `notes:` = failing check output summary (≤ 5 lines). Do not commit. STOP and summarise for the human: what failed, the last check output, what you tried.
7. Otherwise open the next prompt and continue from §Start step 3.

## §Phase end (after the last prompt of phase i)

1. Run `bash Phase_<i>/harness/verify.sh` and `bash Phase_<i>/benchmark/run.sh` (writes `Phase_<i>/benchmark/score.json`).
2. Write `Phase_<i>/REVIEW_PACK_<i>.md` with these sections, in order:
   1. `## Diff range` — `<base>..HEAD` where `<base>` is defined in `DECISIONS.md` G07 (phase 0: `phase-base-approved`; otherwise `phase-<previous>-approved`), plus `git diff --stat <base>..HEAD` output.
   2. `## verify.sh` — exit code and last 30 lines of output.
   3. `## score.json` — the file's full content, verbatim.
   4. `## QUESTIONS` — the full content of `Phase_<i>/QUESTIONS.md`.
   5. `## LLD deviations` — one row per place where the code differs from `Phase_<i>/LLD/**` or `CONTRACTS.md`: file:line | LLD section | what differs | why. Write `none` if none.
   6. `## Review focus` — the full content of `Phase_<i>/REVIEW_FOCUS.md`, verbatim.
3. Commit `P<i>: review pack`, then `git tag phase-<i>-done`.
4. `STATUS.md`: `current:` = the next phase's `.00` id (per `PHASES.md` order 0 → 1 → 2 → 1B → 3 → 4), `state: REVIEW_GATE`, `notes:` = "Phase <i> done; waiting for tag phase-<i>-approved".
5. STOP. The human runs the review chain and creates `phase-<i>-approved`.
