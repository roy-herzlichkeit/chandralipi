# CLAUDE.md — Chandralipi (implementer sessions)

**Which role you are.** If your system prompt contains the contents of `.fable/ARCHITECT.md` (launched as `claude -n FABLE --append-system-prompt-file .fable/ARCHITECT.md`), you are the architect: follow that file, and the rest of this file does not apply to you. Otherwise you are an **implementer**, and everything below applies.

As an implementer you execute one prompt file from `Phase_<i>/prompts/` per session, exactly as written.

- The architect writes the designs. Do not follow `.fable/ARCHITECT.md`, and do not edit `.fable/**`, `FABLE_NOTES.md`, or `CLARIFY.md`.
- Phase folders, the §Handoff procedure, and the full rules for this file are being written (architect Task B). Until `Phase_1/prompts/INDEX.md` exists, do not start any phase work. Stop and tell the user.
- Standing project rules (see `CONTEXT.md` §"Three conventions"): provenance is carried in code; failures are classified, counted, and sampled, never skipped; no number is written that a run did not produce.
