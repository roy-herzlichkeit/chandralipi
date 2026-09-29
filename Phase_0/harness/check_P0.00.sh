#!/usr/bin/env bash
# check_P0.00 — exit 0 = pass (< 30 s). Protected (G05).
source "$(dirname "$0")/lib.sh"
manifest_check
require_branch phase-0
require_tag phase-base-approved
git merge-base --is-ancestor phase-base-approved HEAD || fail "phase-base-approved is not an ancestor of HEAD"
require_file Phase_0/prompts/INDEX.md
ok P0.00
