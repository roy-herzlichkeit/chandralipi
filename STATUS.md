# STATUS

current: P0.06
phase: 0
state: READY
branch: phase-0
last_done: P0.05
notes:
- P0.05: PDS4 resolver walks in document order; Name[child=value] predicate segments (fieldmap.parse_segment, validated in Field.__post_init__); instrument + 8 corner paths updated; _COERCE_FAILED + PDS4Product.coerce_failed + manifest "(coerce_failed)"; resolve_contained + image_path_rejected; LRO ^IMAGE contained.
- No existing assertion needed changing. Deviation to list at phase end: manifest/lro rows write image_path None (not "None") when rejected.
- Q-P0.05-1 (non-blocking): cli.py:39 assumes image_path is not None.
- scripts/ci.sh: 456 passed, 6 deselected. P1.DL may run before Phase 0 approval (Phase_1/prompts/P1.DL_download_session.md).
