# Phase 2 — local decisions

| ID | decision | reason | rejected |
|---|---|---|---|
| D2-1 | Tiling rectifies each reference window into the source tile's frame through the 3×3 prior (`warpPerspective` with `WARP_INVERSE_MAP`) before matching. | Handles scale and rotation (S8) for every matcher; the architect's prototype on the C18 scene gave a 0.10 px median raw-match error (`Phase_2/LLD/tiling.md`). | Scaling tiles only; per-matcher scale handling |
| D2-2 | Resampling matrices use the pixel-centre convention that matches `cv2.resize` (CONTRACTS C11). | A corner-convention matrix would add a (f−1)/2-pixel bias — 0.375 reference px for f = 4 — to every native refinement. | Corner convention |
| D2-3 | Device profiles are fitted as `peak = fixed + k · tile²` by least squares over ≥ 3 OK sizes. | Matches the analytic model's dominant term; a fixed term absorbs weights and context. | Adding the quartic score-matrix term (not identifiable from 3–7 points) |
| D2-4 | A failed free-memory reading returns 0 bytes with `UNKNOWN`, and planners then report `fits = False`. | The old 8 GiB nameplate fallback silently over-planned (A073). | Nameplate fallback |
| D2-5 | Native refinement runs once per strip with `native_matcher` (default SIFT). | Cost; ECC already equalises matchers at the coarse level (TBD 1.8 measurement). | Native refinement per matcher |
