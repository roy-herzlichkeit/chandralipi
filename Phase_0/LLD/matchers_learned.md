# LLD — learned matchers merge (P0.02)

Closes: A001 (match-1), A002 (match-2), A013 (S16 matchers), A014 (match-9, matcher side), A015 (match-10), A016 (match-15, P0 part), A089 (match-14).
Evidence for every bug: `AUDIT.md` rows above; kornia facts: `.fable/research_20260929.json` entry "kornia 0.8.3 LoFTR / DISK / LightGlueMatcher".

## 1. Files
| file | action |
|---|---|
| `src/lunar_reg/match/loftr.py` | delete |
| `src/lunar_reg/match/superglue.py` | delete class `LightGlueMatcher` and its helpers used only by it; keep `SuperGlueMatcher` and `licence_report()`; import `_to_tensor` from `learned` when needed |
| `src/lunar_reg/match/learned.py` | the fixes in §2 |
| `src/lunar_reg/match/__init__.py` | exports unchanged except nothing refers to `loftr.py` |
| `src/lunar_reg/match/classical.py` | `meta` per §3; docstring at line 43 per §4 |
| `src/lunar_reg/match/stitch.py` | docstring per §4 (no code change) |

## 2. `learned.py`
### 2.1 `_to_tensor(image, device)`
| input dtype | tensor value |
|---|---|
| `uint8` | `image / 255.0` as float32 |
| anything else | `lunar_reg.preprocess.radiometric.to_uint8(image) / 255.0` as float32 |
3-D input: mean over the last axis first (unchanged). Output shape `(1, 1, H, W)`.

### 2.2 `LoFTRMatcher.match(source, reference)`
1. Size guard on `source` unchanged (reference guard is P2.06).
2. Build both tensors, then zero-pad each on bottom/right to a multiple of 8 with `_pad_to_multiple(t, 8)`.
3. Run the model exactly as today (autocast only when `device == "cuda"` and `precision == "fp16"`).
4. Drop every match whose source point has `x >= w_src or y >= h_src` or whose reference point has `x >= w_ref or y >= h_ref` (unpadded sizes).
5. Confidence filter unchanged.
6. `meta = {"device": self.device, "precision": self.precision, "weights": f"loftr_{self.weights}", "confidence_threshold": self.confidence, "pad_multiple": 8}`.

### 2.3 `LightGlueMatcher.match(source, reference)`
1. DISK extraction for both images inside `torch.inference_mode()` and, on CUDA only, `torch.autocast("cuda", dtype=torch.float16)`; padding to 16 and `_drop_outside` unchanged.
2. **Outside** the autocast context (still inside `inference_mode`), call the LightGlue matcher with `keypoints`, `descriptors` cast by `.float()` and `image_size` as today. This is the fix for A001: kornia's LightGlue positional encoding is fp32, and feeding it fp16 under an outer autocast raises on every CUDA call.
3. `meta = {"device": self.device, "precision": "fp16-disk+fp32-lightglue" if cuda else "fp32", "weights": "disk_depth+lightglue_disk", "max_keypoints": self.max_keypoints}`.
4. Empty result → `MatchResult.empty(self.name)` with `meta` set as in 3 plus `"empty_reason": "no_lightglue_matches"`.

### 2.4 Not in P0.02
Passing LightGlue scores through (A127) and the reference-size guard (A080) are P2.06. `torch.cuda.empty_cache` placement (A077) is P2.05.

## 3. `ClassicalMatcher.match` meta
Every returned `MatchResult` (including empty ones) carries `meta` with at least `{"detector": <name>, "ratio": <float>, "max_features": <int>, "cross_check": <bool>}`. Empty-result reasons are P0.09.

## 4. Docstring corrections (text only)
| location | current claim | replace with |
|---|---|---|
| `classical.py:43` comment | "RIFT2 is not buildable here" | "RIFT2 is available as the clean-room implementation in `lunar_reg.match.rift2`." |
| `stitch.py:27` | "Score breaks ties." | "Equal priorities keep the copy with the highest original index; when no priority is passed, the match score is the priority (zeros when there are no scores)." |
| `learned.py` module docstring lines 15-16 | LightGlue runs under fp16 autocast | "DISK runs under fp16 autocast on CUDA; LightGlue always runs in fp32 (kornia's positional encoding is fp32)." |

## 5. Tests the prompt adds (`tests/test_learned_matchers.py`)
| test | marker | asserts |
|---|---|---|
| LoFTR CPU odd size (250×330, known shift) | `weights` | ≥ 20 matches, all points inside both images, median error < 1.0 px |
| LightGlue CPU odd size | `weights` | same |
| LightGlue CUDA | `gpu`, `weights` | no exception, ≥ 20 matches, `meta["device"] == "cuda"` |
| `_to_tensor` float vs uint8 | — | float input equals `to_uint8(input)/255` |
| SuperGlue licence gate | — | `SuperGlueMatcher()` without flag raises `PermissionError` |
| `stitch.deduplicate` | — | two copies of one correspondence within tolerance → 1 kept, `n_removed == 1`; copies with far-apart destinations → both kept |
Scene for the shift tests: crop two windows of one `eval.scenes.hillshade(add_craters(fractal_terrain(...)))` image, offset by an integer `(dx, dy)`, so ground truth is exact without interpolation.
