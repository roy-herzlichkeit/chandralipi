# MERGE_PLAN_PLAN — how the Task D decisions were applied

Scope: the adversarial review of the plan (`REVIEW_DECISIONS_PLAN.md`, 38 items).

## Why there is no reviewer diff to merge and no rev prompts
- No phase has started: `STATUS.md` = `P0.00 READY` on `main`, and no `phase-*` branch or `phase-*-done` tag exists. There is no implementation code for the review's findings to apply to.
- The reviewer supplied findings, not patches. Each ACCEPT or ACCEPT_MODIFIED item was written straight into the plan files named in the "docs changed" column of `REVIEW_DECISIONS_PLAN.md`.
- For the same reason no `rev` fix prompts were created: a fix prompt edits code produced by an earlier prompt, and none exists yet. The changed behaviour reaches implementers through the LLDs, prompts and harness tests those prompts already LOAD and run.

## Order applied
1. Global docs: `DECISIONS.md` (G14, G33 revised; G36–G39 new), `CONTRACTS.md` (C02, C07, C10, C13, C21, C24, C27), `HLD.md` (K11), `PHASES.md` (P1.22/P1.23 split, P1.11 spice extra, 74 prompts), `CLAUDE.md` (network exception for the P1.11 `spice` extra install), `AUDIT.md` (A069/A116/A120 re-pointed).
2. Phase 0 → 1 → 2 → 1B → 3 → 4 LLDs and prompts, in dependency order, so that each contract change reached every consumer phase:
   - C07 masks: P0.08 → P0.09 → P1B.05 (runner ECC call).
   - C10 keywords: P1.04 → P1.05 → P3 planner (`reference_georef` dict unchanged).
   - C13 SPICE: P1.11 → P1.16 → P1.20 → P1B.02.
   - C24 renew/close: P3.04 → P3.05/P3.07 → P4.01.
   - C27: P4.01 → P4.03 → P4.04 → P4.06.
3. Harness: only changes that make checks stricter or fix a wrong expectation (a zero-offset fixture, an outdated key set, a missing negative test). Every phase's `harness/MANIFEST.sha256` was regenerated afterwards.
4. Verification: `pytest --co` over every phase harness; `bash -n` on every harness script; the banned-word grep over Opus-facing docs.

## What an implementer sees
Nothing changes in the workflow. `STATUS.md` still names `P0.00`, and every harness check already encodes the adjudicated behaviour. `PLAN_PROGRESS.md` §Fix log lists the Task D rows.

## Human follow-ups (not blocking)
- None of the 38 items needs a human decision (NEEDS_HUMAN = 0).
- New network step: P1.11 installs the `spice` extra (spiceypy) and P1.02 fetches three NAIF generic kernels (public, no login). Both are listed in `CLAUDE.md` §Rules › network.
