# STATUS

current: P2.07
phase: 2
state: READY
branch: phase-2
last_done: P2.06
notes:
- P2.06: tiled.py implements C18: TileStatus, TileOutcome, TileDiagnostics (counts, samples, n_failed, report), TiledMatcher(min_valid_fraction=0.5, ref_margin_px=32). match_arrays rectifies a tile-sized reference window through the 3x3 prior (cv2.warpPerspective WARP_INVERSE_MAP, tile + 2*margin; no cv2.remap 32767 px limit), classifies every tile, lifts dst through T_t; last_diagnostics set every call; OOM type resolved at except time via _oom_types(). match_datasets uses the same routine with masked windowed reads (Q-P2.06-2).
- Default tile_px = max_tile_px - 2*ref_margin_px when the matcher advertises a limit, so LoFTR's new reference guard fits (Q-P2.06-1). stitch.py unchanged; plan_tiles untouched.
- learned.py: LoFTR size guard covers both inputs (A080); LightGlue passes out["scores"][0] as MatchResult.scores (A127).
- No script calls TiledMatcher yet; the first caller (P2.08/P2.10) must print tm.last_diagnostics.report() on every run (Q-P2.06-3).
- Full CPU suite (scripts/ci.sh): 1104 passed; GPU lightglue scores test passed. Q-P2.04-1 and Q-P2.02-4 (device.py planner cap, budget.fits) still open.
