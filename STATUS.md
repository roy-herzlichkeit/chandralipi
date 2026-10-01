# STATUS

current: P1.02
phase: 1
state: READY
branch: phase-1
last_done: P1.01
notes:
- P1.01: added src/lunar_reg/ingest/downloads.py (C08: DownloadEntry/DownloadManifest/DownloadStatus/record_file/record_failure/verify_downloads/DownloadDiagnostics) and scripts/verify_downloads.py. record_file rejects source/instrument/role/recorded_by values outside the C08 lists with a ValueError.
- `verify_downloads.py --no-scan` (full sha256, 6m59s; log: scratchpad p1/verify_P1.01.log): manifest data/raw/DOWNLOADS.json present; 206 file entries, 0 recorded failures; ok 206; EXIT=0.
- `verify_downloads.py --no-hash` (with scan): ok 206, unrecorded 1 (ch2/_pradan/payload.xhtml, expected per LLD §1); EXIT=0.
- The full-hash verify takes about 7 min on the current 206 files. Use --no-hash for quick checks.
- Review fix: unreadable recorded file -> MISSING with sample 'unreadable: <OSError>'; non-blocking Q-P1.01-1 proposes UNREADABLE in C08; UNRECORDED scan still skips unreadable dirs/files silently.
