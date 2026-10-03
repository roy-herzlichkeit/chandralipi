---
name: run-prompts
description: How to execute a RUN prompt (a prompt that runs the pipeline on real data) — preconditions, commands, artefacts, run records, what goes into STATUS and docs. Used by P1.18–P1.20, P2.04, P2.11, P1B.06, P3.09, P4.06.
---

# RUN prompts (DECISIONS G22)

## Before running
| step | exact behaviour |
|---|---|
| preconditions | run every precondition listed in the LLD section; a failing one is a BLOCKER — do not "try anyway" |
| GPU | `nvidia-smi --query-gpu=memory.used,memory.total --format=csv` before a GPU run; nothing else of yours may be using the GPU (CLAUDE.md: never two GPU processes at once) |
| disk | `df -h data/` ≥ 10 GB free, else BLOCKER |
| code state | the working tree is clean except `docs/plan/STATUS.md`/INDEX; RUN prompts never edit code unless their LLD names the file |

## While running
- Run the commands **exactly** as written in the LLD, one at a time, from the repo root, with `.venv/bin/python`.
- Keep each command's console output: `<command> 2>&1 | tee <out_dir>/console_<step>.log` (the `out_dir` named by the LLD).
- A command that exits non-zero is not retried with different settings. Record it, finish the remaining steps that do not depend on it, then decide per the LLD (usually BLOCKER or a classified row in the doc).
- Never delete or overwrite `data/raw/**`; never overwrite an archive directory.

## After running
- Every RUN step leaves a `run_record.json` (C15) in its `out_dir`; validate each with `.venv/bin/python -c "from lunar_reg.runrecord import validate_run_record as v; import sys; p = v(sys.argv[1]); print(p); sys.exit(1 if p else 0)" <path>`.
- Numbers in `docs/plan/STATUS.md` notes and in any doc are copied from artefacts, with the artefact path next to them (G19). Unknown → `[INSERT RESULT]`.
- Self-residual RMSE is never reported as accuracy; synthetic numbers are labelled SYNTHETIC.
- `git add` never includes `data/` (gitignored); commit only the doc/code files the prompt names plus STATUS/INDEX.
