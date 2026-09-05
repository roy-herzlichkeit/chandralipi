# Memory constraints on an 8 GB RTX 4060

Every point where the 8 GB budget shapes a design decision, with the arithmetic.
The model lives in `src/lunar_reg/device.py` and is pinned by `tests/test_device.py`.

Two things about the target card beyond the nameplate number:

- **8 GB is total, not free.** A desktop session typically holds 0.5–1.5 GB, and
  the PyTorch allocator fragments on top. Plan against `free_vram_bytes()`;
  `VRAM_SAFETY_FRACTION = 0.75` reserves the rest.
- **It is a Max-Q mobile part.** Sustained clocks are power-limited, so on long
  OHRC strips throughput is bounded by thermals as much as by memory. Prefer
  fewer large tiles over many small ones once a tile fits.

---

## 1. Product size — the binding constraint

A full OHRC strip is ~12,000 samples × 90,000 lines:

| | bytes |
|---|---|
| on disk, 16-bit | ~2.2 GB |
| in memory, float32 | ~4.3 GB |
| **source + reference pair** | **~8.6 GB** |

One strip would fit alone. Registration needs both resident, and that pair
already exceeds the card before model weights or activations. An IIRS cube is
the same trap by a different route: 2000 × 2000 × 256 bands × 4 B ≈ 4.1 GB from
a spatially small raster.

**Consequence:** nothing in this pipeline loads a full product. `ingest/tiling.py`
plans windowed reads and `match/tiled.py` processes one tile pair at a time, so
peak memory is set by tile size, not product size. `align/warp.py` writes the
registered output block by block for the same reason.

Guarded by `test_full_ohrc_pair_does_not_fit_in_vram`.

## 2. Dense matchers — cost grows as the 4th power of tile side

LoFTR-family matchers build an N×N confidence matrix over coarse tokens taken at
1/8 input resolution. For a square tile of side S, N = (S/8)², so that one matrix
grows as S⁴:

| tile side | tokens N | N² × 4 B (fp32) |
|---|---|---|
| 640 | 6,400 | 0.16 GB |
| 1024 | 16,384 | 1.07 GB |
| 1408 | 30,976 | 3.84 GB |
| 1600 | 40,000 | **6.40 GB → OOM** |

Backbone activations add roughly another 1.5× (`_DENSE_ACTIVATION_OVERHEAD = 2.5`).

**Practical ceiling on this card: ~1216 px in fp32, ~1408 px under autocast fp16.**
`plan_dense_tile()` derives it from free memory and rounds down to a multiple of
64 for the feature pyramid. `LoFTRMatcher.match` refuses oversized input with a
message pointing at `TiledMatcher` rather than letting CUDA OOM.

fp16 autocast and `torch.inference_mode()` are load-bearing here, not incidental
optimisations — fp16 alone doubles the workable tile area.

## 3. Sparse matchers — cost is in keypoints, not pixels

SuperGlue/LightGlue attend over keypoints, so cost is O(K²) in keypoint count and
independent of image area. 2048 keypoints per tile is comfortable on 8 GB; 4096
roughly quadruples the attention working set.

`plan_keypoint_budget()` returns 2048 at ≥5 GB free, 4096 at ≥10 GB, 1024 below.

**Consequence:** when a scene needs large tiles, prefer `LightGlueMatcher` over
`LoFTRMatcher` — it tolerates far larger inputs at the same VRAM, at the cost of
sparser correspondences.

## 4. Hyperspectral PCA — a host-RAM constraint

Band PCA over a 256-band IIRS cube would need the whole cube in host memory.
`incremental_band_pca` accumulates the band covariance over row blocks instead,
so peak host memory is `block_rows × cols × bands × 4` — a few hundred MB at the
default 512-row block, rather than several GB. Two passes over the file, one to
accumulate and one to project.

## 5. Fallbacks when the budget is exceeded

In order of preference:

1. **Reduce tile size.** `plan_dense_tile()` already picks the maximum; going
   smaller trades context for headroom and is nearly free.
2. **Switch fp32 → fp16.** Roughly doubles workable tile area.
3. **Switch LoFTR → LightGlue.** Moves cost from image area to keypoint count.
4. **Fall back to `ClassicalMatcher`.** SIFT/ASIFT run entirely on CPU and are
   unaffected by VRAM. Slower and less robust across modalities, but it always
   completes — this is the shadow-fallback track.

## 6. What is *not* VRAM-bound

Worth knowing so effort goes to the right place:

- Footprint overlap detection (`ingest/footprint.py`) — pure geometry.
- All metrics (`eval/`) — operate on point arrays, never on imagery.
- Preprocessing (`preprocess/radiometric.py`) — OpenCV on CPU, per tile.
- Block-wise warping (`align/warp.py`) — host memory and disk I/O bound.

## 7. Current machine

At the time of scaffolding, `nvidia-smi` on this machine fails and the `nvidia`
kernel module is not loaded, though the RTX 4060 Mobile is present on the PCI bus
(`01:00.0 AD107M`). `lunar-reg env` therefore reports `cpu`, and learned matchers
will run roughly 30–50× slower until the driver is restored. Nothing in the
pipeline breaks — the CPU path is exercised by the test suite — but no GPU
timing or VRAM figure in this document has been measured on the actual card yet.
They are derived from the cost model, not observed.
