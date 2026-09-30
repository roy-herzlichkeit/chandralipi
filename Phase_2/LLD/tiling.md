# LLD — prior-rectified tiling and tile outcomes (P2.06); classical caps and RIFT2 memory (P2.07)

Produces: C18. Closes: A078 (S7), A079 (S8), A080 (S9), A127 (match-11), A128 (match-18), A081 (match-12), A129 (match-17), A082 (preprocess-11), A016 rest (TiledMatcher failure-path test).

## P2.06 — `match/tiled.py`, `match/stitch.py`, `match/learned.py`
### Prior-rectified pairing (S8)
For each source tile `t` (from `plan_tiles`, unchanged):
1. `corners_ref = prior(t corners)`; reference window = their bounding box ± `ref_margin_px`, clipped; empty → `OUT_OF_REFERENCE`.
2. Rectify: with `m = ref_margin_px` and `T_t = prior @ [[1, 0, t.col_off − m], [0, 1, t.row_off − m], [0, 0, 1]]` (rectified-patch px → reference px), `R_t = cv2.warpPerspective(reference, T_t, (t.width + 2m, t.height + 2m), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderValue=0)`. The rectified patch is at the source tile's scale and orientation (source tile pixel `(x, y)` ≈ patch pixel `(x + m, y + m)`), so any matcher sees a near-identity pair. Prototype on the C18 test scene (1024² terrain, scale 0.8, rotation 15°, prior off by 3 px, SIFT, 256 px tiles): 604 raw matches, median error 0.10 px (architect's check, 2026-09-29; not a benchmark figure).
3. Valid fraction of the source tile (`source_valid`, default `source > 0`) and of `R_t` (warped `reference_valid`) — either below `min_valid_fraction` → `SKIPPED_NODATA`.
4. `res = matcher.match(src_patch, R_t)`; exceptions: `torch.OutOfMemoryError` → `OOM` (then `torch.cuda.empty_cache()`), anything else → `MATCHER_ERROR`; `len(res) == 0` → `EMPTY`; else `OK`.
5. Lift: `src_pts += (t.col_off, t.row_off)`; `dst_pts = T_t(dst_pts)` applied projectively in float64 (rectified px → reference px; the margin is already inside `T_t`).
6. `TileDiagnostics.record(TileOutcome(...))` for every tile, including skipped ones; `last_diagnostics` set; one summary log line; `last_stats` kept.
`prior=None` → identity; `offset_prior=(row, col)` → `[[1, 0, col], [0, 1, row], [0, 0, 1]]`. `match_datasets` is rebuilt on the same per-tile routine with windowed reads (reads the reference window bounding box, not the whole raster).
### Learned-matcher fixes
- `LoFTRMatcher.match`: size guard applies to **both** inputs (A080) — a reference larger than the plan raises `ValueError` (TiledMatcher classifies it).
- `LightGlueMatcher.match`: pass `out["scores"][0]` through as `MatchResult.scores` (A127).
### Tests (`tests/test_tiled_prior.py`)
Synthetic source 1024² and reference = source scaled by 0.25 and rotated 20° (`cv2.warpAffine`), prior = the true similarity + 3 px error → sift through `TiledMatcher(tile_px=256)` recovers the transform to < 0.5 reference px; a stub matcher raising on tile 2 and returning empty on tile 3 → counts `{"ok": n−2, "matcher_error": 1, "empty": 1}`; a stub raising `torch.OutOfMemoryError` → `oom`; nodata tiles → `skipped_nodata`; `offset_prior` equivalence with the translation prior.

## P2.07 — `classical.py`, `rift2/matcher.py`, `radiometric.py`
- A081: inside `ClassicalMatcher.detect`, before it returns, when the detector has no native feature cap (akaze, kaze, brisk), keep the `max_features` keypoints with the highest `response` (stable sort; ties by index) and record `meta["max_features_applied"] = True`.
- A129: `RIFT2Matcher(max_tile_px: int | None = None)`; default from host RAM: `floor(sqrt(0.25 · MemAvailable / 300))` rounded down to a multiple of 64 (300 B/px = the audit's per-pixel bank estimate, `ValueSource.INFERRED`); an input side above it → `ValueError` naming the cap (so `TiledMatcher` or `register_pair` classifies it); `max_tile_px` exposed as a property like LoFTR's.
- A082: `to_uint8(image, percentiles, valid=None, *, sample_step: int | None = None, lo_hi: tuple[float, float] | None = None)`: `lo_hi` given → use it (consistent stretch across tiles); else percentiles from a strided subsample `image[::s, ::s]` when `image.size > 4e7` (`s = ceil(sqrt(size / 4e7))`), else from all pixels; the stretch is applied row-block by row-block (4096 rows) in float32. `valid=None` results for images ≤ 4e7 px are byte-identical to P1.08's. With `valid` given, `lo_hi` maps valid pixels into 1…255 and keeps 0 for nodata (the P1.08 rule); without `valid` it maps into 0…255 exactly like the unmasked P1.08 path (review RC24: no conflict, only this clarification).
- Tests (`tests/test_caps_and_memory.py`): akaze on a textured 512² image with `max_features=100` returns ≤ 100 keypoints' worth of matches' sources; RIFT2 with `max_tile_px=128` raises on a 256² input; `to_uint8(..., lo_hi=(10, 20))` maps 10 → 0 and 20 → 255 without masks; a 7000×7000 float32 image stretches without allocating a float64 copy (check `tracemalloc` peak < 2 × input bytes).
