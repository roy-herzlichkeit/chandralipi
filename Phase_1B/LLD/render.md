# LLD — DTM shaded-relief renderer (P1B.01)

Produces: C21 `render_shaded_relief`. Closes: A071 (eval-7). TBD 1.8 step 2.

## 1. `eval/render.py` (new)
`render_shaded_relief(dtm, posting_m, azimuth_deg, elevation_deg, *, cast_shadows=True, ambient=0.04, nodata=None) -> np.ndarray` (uint8):
1. `valid = isfinite(dtm)` and, when `nodata` is not None, `dtm != nodata`; invalid heights are filled with the median of valid ones for the computation only.
2. `lam = ingest.sun.lambert_shade(dtm_filled, posting_m, azimuth_deg, elevation_deg)` (P1.11 conventions: azimuth clockwise from image-up, rows southward).
3. Cast shadows (when enabled): `t = tan(radians(elevation_deg))`; unit step toward the sun in pixels `(dx, dy) = (sin az, −cos az)`; `n_steps = min(ceil((max(dtm) − min(dtm)) / (posting_m · t)), ceil(hypot(h, w)))`; for `k = 1 … n_steps`: sample `dtm` at `(x + k·dx, y + k·dy)` with `cv2.remap` (bilinear, border = replicate); `shadow |= sampled > dtm + k · posting_m · t`. Pixels whose ray leaves the image stop contributing (border replicate keeps them unshadowed only by terrain inside the image; stated in the docstring).
4. `shade = ambient + (1 − ambient) · lam · (~shadow)`; output `uint8 = clip(1 + 254 · shade, 1, 255)`; invalid → 0.
Deterministic; no randomness.

## 2. `eval/scenes.py` (A071)
`_cast_shadow_mask(height, azimuth_deg, elevation_deg, relief, steps=None)`: `steps=None` → `min(ceil(relief_range / tan(elevation)), ceil(diagonal))` with `relief_range = relief · (height.max() − height.min())` (the function's own relief scaling); an explicit integer keeps today's behaviour. `hillshade` passes `steps=None`. Existing tests that pinned values produced with 64 steps are updated (named in the commit body).

## 3. Tests (`tests/test_render.py`)
A flat DTM renders uniform `1 + 254·(ambient + (1−ambient)·sin(el))` ± 1; a single tall pillar casts a shadow of length ≈ `height / (posting · tan el)` px on the side away from the sun (±2 px), for azimuths 90° and 180°; `nodata` pixels → 0; the shadow fraction of `scenes.hillshade` at elevation 5° converges (steps=None equals steps=2000 within 0.5 %).
