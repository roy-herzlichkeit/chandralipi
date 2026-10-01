# Phase 1 — questions

Implementers append entries here (format in root `CLAUDE.md` §Doubts). Empty at plan time.

## Q-P1.01-1  DownloadStatus has no member for a recorded file that exists but cannot be read
context: CONTRACTS.md C08 (`DownloadStatus`); src/lunar_reg/ingest/downloads.py `verify_downloads` (the `except OSError` branch)
question: A recorded file that is present but unreadable (permission denied, I/O error while hashing, removed mid-run) used to raise out of `verify_downloads`, so the CLI never printed `report()`. C08 freezes the enum, so there is no `UNREADABLE` member. Should C08 gain `UNREADABLE = "unreadable"` (is_failure), as C09 `InstrumentStatus` already has?
what I did meanwhile: such entries are recorded as `MISSING` (a failure, so the CLI exits 1) with the sample `"<path>: unreadable: <OSError>"`, and the MISSING description now reads "recorded but not on disk or unreadable (see sample)". Reversible: adding the member later only changes which status that branch records.

## Q-P1.02-1  C08 has no source/instrument/role values for the NAIF SPICE kernels
context: CONTRACTS.md C08 (`source`, `instrument`, `role` lists); Phase_1/LLD/downloads.md §2.2 rows `spice_lsk`, `spice_pck`, `spice_de440s`; scripts/fetch_public.py `_RECORD_AS`
question: `record_file` rejects values outside the frozen C08 lists, and none of them names NAIF (source), SPICE kernels (instrument) or a kernel (role). Should C08 gain `source "NAIF"`, `instrument "SPICE"` and `role "kernel"` (or which existing values should the kernels carry)?
what I did meanwhile: the three kernels are recorded with `source "PDS_IMG"` (NAIF is a PDS node; the only generic PDS value), `instrument "DOC"`, `role "misc"`, `product_id` = file stem, and the real `naif.jpl.nasa.gov` URL in `url`, so the true origin is in every entry. No code reads these fields today. Reversible: change `_RECORD_AS["spice_"]` and re-record the three files with `record_file` (which replaces an entry with the same path).

## Q-P1.02-2  FetchStatus gains PRESENT_UNRECORDED (not in LLD §5's member list)
context: Phase_1/LLD/downloads.md §5 (outcome enum, resume rule); CLAUDE.md §Rules "data" (never overwrite under data/raw/)
question: LLD §5 defines SKIPPED_PRESENT only for a destination that DOWNLOADS.json records with a matching size. A destination that exists but has no entry, or a different size, cannot be downloaded again without overwriting a file under `data/raw/`. Is a separate member right, and should it fail the run (exit 1 on a VALIDATED row)?
what I did meanwhile: added `FetchStatus.PRESENT_UNRECORDED = "present_unrecorded"` (is_failure; no request is made, the file is left untouched, the report says "NOT overwritten"). Also: a Content-Length mismatch is recorded in `failures` via `record_failure(url, <HTTP status>, "size_mismatch: ...")` and the `.part` is removed (atomic-writes skill), so it shows up later as `http_error` in `verify_downloads.py`. Reversible: drop the member / the recording; no file on disk depends on either. Not hit in the real run (7 skipped_present, 3 downloaded; log scratchpad p1/fetch_public_P1.02.log).
