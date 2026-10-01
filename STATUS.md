# STATUS

current: P1.03
phase: 1
state: READY
branch: phase-1
last_done: P1.02
notes:
- P1.02: added scripts/fetch_public.py (SOURCES = the 18 files of LLD §2.2; FetchStatus + FetchDiagnostics; pacing 30 s DARTS / 3 s other hosts; .part then os.replace; exit 1 on a failed VALIDATED row) and tests/test_fetch_public.py (no network). With no --only it selects VALIDATED rows only; DOCUMENTED keys are fetched only when named in --only (human request; DOCUMENTED rows already on disk from P1.DL).
- Run step `fetch_public.py --only <8 VALIDATED keys>` (log: scratchpad p1/fetch_public_P1.02.log): 10 files selected, 7 skipped_present, 3 downloaded (SPICE kernels naif0012.tls, pck00011.tpc, de440s.bsp; 32862499 B), 0 failures; EXIT=0.
- `verify_downloads.py --no-scan` (full sha256; log: scratchpad p1/verify_P1.02.log): 209 file entries, 0 recorded failures; ok 209; EXIT=0. `du -sb data/raw` = 56882679700 B.
- Non-blocking: Q-P1.02-1 (C08 has no NAIF/SPICE values; kernels recorded as PDS_IMG/DOC/misc with the NAIF URL); Q-P1.02-2 (added FetchStatus.PRESENT_UNRECORDED, never overwrites; size_mismatch also written to failures). Both are LLD deviations for the review pack.
