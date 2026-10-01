# Phase 1 — questions

Implementers append entries here (format in root `CLAUDE.md` §Doubts). Empty at plan time.

## Q-P1.01-1  DownloadStatus has no member for a recorded file that exists but cannot be read
context: CONTRACTS.md C08 (`DownloadStatus`); src/lunar_reg/ingest/downloads.py `verify_downloads` (the `except OSError` branch)
question: A recorded file that is present but unreadable (permission denied, I/O error while hashing, removed mid-run) used to raise out of `verify_downloads`, so the CLI never printed `report()`. C08 freezes the enum, so there is no `UNREADABLE` member. Should C08 gain `UNREADABLE = "unreadable"` (is_failure), as C09 `InstrumentStatus` already has?
what I did meanwhile: such entries are recorded as `MISSING` (a failure, so the CLI exits 1) with the sample `"<path>: unreadable: <OSError>"`, and the MISSING description now reads "recorded but not on disk or unreadable (see sample)". Reversible: adding the member later only changes which status that branch records.
