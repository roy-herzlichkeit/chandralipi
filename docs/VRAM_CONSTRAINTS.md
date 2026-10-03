# Memory constraints on the RTX 4060 Laptop GPU

This page lists every place where GPU memory (VRAM, the graphics card's own
memory) shapes a design decision. It was rewritten in P2.11 (AUDIT A084) from
the measured device profile `configs/device_profiles/rtx4060-laptop.json`. The
earlier version mixed estimates with observations and described a machine whose
driver was not loaded.

Every figure carries one of three tags, with its path next to it:

| tag | meaning |
|---|---|
| **MEASURED** | read on this card by a run: the profile `configs/device_profiles/rtx4060-laptop.json` (P2.04 benchmark, its own run record is `data/processed/benchmarks/p2_04/run_lightglue_fp32/run_record.json`), or a P2.11 run artefact under `data/processed/gpu_run/` |
| **COMPUTED** | arithmetic on MEASURED figures and CAP constants, written to `data/processed/gpu_run/vram_computed.json` by `data/processed/gpu_run/vram_computed.py` |
| **CAP** | a constant in `src/lunar_reg/device.py` (line given) |

The code that uses these figures is in `src/lunar_reg/device.py`
(`free_memory_bytes`, `plan_dense_tile`, `DeviceProfile.plan_tile`,
`plan_keypoint_budget`). A *tile* is a square piece of the image, `tile_px`
pixels on a side, that a matcher processes in one pass.

---

## 1. The card

| figure | value | tag, path |
|---|---|---|
| device | NVIDIA GeForce RTX 4060 Laptop GPU | MEASURED, `configs/device_profiles/rtx4060-laptop.json` (`device_name`) |
| total VRAM | 8161198080 bytes | MEASURED, `configs/device_profiles/rtx4060-laptop.json` (`total_bytes`) |
| free VRAM when profiled | 7730102272 bytes | MEASURED, `configs/device_profiles/rtx4060-laptop.json` (`free_bytes_at_measure`) |
| held by the desktop when profiled (total − free) | 431095808 bytes | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`desktop_bytes_at_measure`) |
| software | torch 2.14.0+cu130, CUDA 13.0, driver 580.178.04 | MEASURED, `configs/device_profiles/rtx4060-laptop.json` (`torch`, `cuda`, `driver`) |

The nameplate capacity `ASSUMED_TOTAL_VRAM_BYTES` (CAP, src/lunar_reg/device.py:33,
tagged DOCUMENTED in code) is never used as a fallback. A free-memory reading
that fails is `UNKNOWN` with 0 bytes, and every plan then has `fits = False`.

## 2. The budget rule

A single matcher call plans against a fraction of the **free** memory at the
start of the run, never against the total (DECISIONS G18).

| figure | value | tag, path |
|---|---|---|
| `VRAM_SAFETY_FRACTION` | 0.75 | CAP, src/lunar_reg/device.py:38 |
| budget at profiling time (0.75 × free) | 5797576704 bytes | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`budget_bytes_at_measure`) |
| 0.75 × total (the Phase 2 scorer's headroom limit) | 6120898560 bytes | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`budget_bytes_of_total`) |
| dense tile ceiling `MAX_DENSE_TILE_PX` | 1408 px | CAP, src/lunar_reg/device.py:236 |
| dense tile floor `MIN_DENSE_TILE_PX` | 256 px | CAP, src/lunar_reg/device.py:237 |

The remaining 25 % absorbs allocator fragmentation and transient copies. That
rationale is the code comment at src/lunar_reg/device.py:36-37; no run has
measured it.

## 3. Measured peak memory per tile

The P2.04 benchmark ran each learned matcher on square tiles of growing size and
recorded the peak `torch.cuda.max_memory_allocated`. All rows are MEASURED,
`configs/device_profiles/rtx4060-laptop.json` (`matchers.<name>.<precision>.points`).

| matcher / precision | tile px → peak bytes |
|---|---|
| loftr / fp16 | 256 → 267968000; 384 → 457464832; 512 → 721701888; 640 → 1060293632; 768 → 1472941568; 896 → 2499055616; 1024 → 4106506240 |
| loftr / fp32 | 256 → 320229376; 384 → 579803648; 512 → 935627264; 640 → 1400670720; 768 → 1962328064; 896 → 2928562176; 1024 → 4794372096 |
| lightglue / fp16 | 512 → 458401280; 768 → 963170304; 1024 → 1669370368; 1536 → 3690632704; 2048 → 6515367424 |
| lightglue / fp32 | 512 → 702326272; 768 → 1507968000; 1024 → 2639832576; 1536 → 5872829952 |

The benchmark fitted `peak = fixed_bytes + bytes_per_px × tile_px²` per entry
(MEASURED fit, written by the benchmark into `configs/device_profiles/rtx4060-laptop.json`):

| matcher / precision | fixed_bytes | bytes_per_px | largest measured tile |
|---|---|---|---|
| loftr / fp16 | −242883933 | 3694.0158200416076 | 1024 |
| loftr / fp32 | −192735154 | 4290.723203450068 | 1024 |
| lightglue / fp16 | 54651133 | 1540.5091766488745 | 2048 |
| lightglue / fp32 | 54635886 | 2465.9173245729635 | 1536 |

The LoFTR intercepts are negative because LoFTR's peak grows faster than
`tile_px²` above 768 px. The fit therefore underestimates large tiles. This is
open as Q-P2.04-1.

How fp16 compares with fp32:

| comparison | ratio | tag, path |
|---|---|---|
| LoFTR fp16 peak / fp32 peak at 1024 px | 0.8565263933990659 | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`fp16_over_fp32.loftr_peak_at_1024`) |
| LightGlue fp16 peak / fp32 peak at 1536 px | 0.628424921914034 | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`fp16_over_fp32.lightglue_peak_at_1536`) |
| LightGlue fp16 / fp32 `bytes_per_px` | 0.6247205294750313 | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`fp16_over_fp32.lightglue_bytes_per_px`) |

So, on this card, half precision saves LoFTR much less than the "fp16 halves the
memory" rule of thumb that the old version of this page relied on.

## 4. What the planner picks from the profile

`DeviceProfile.plan_tile` picks the largest multiple of 64 px, within the CAP
limits of §2, whose estimate `fixed + bytes_per_px × tile²` is at most
0.75 × free. The estimate is never below the largest measured peak at or below
that tile. Applied to the profile's own free-memory reading:

| matcher / precision | planned tile | estimated peak | above the largest measured tile? | tag, path |
|---|---|---|---|---|
| loftr / fp16 | 1216 px | 5219294723 bytes | yes (largest measured: 1024) | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`entries."loftr/fp16"`) |
| loftr / fp32 | 1152 px | 5501500772 bytes | yes (largest measured: 1024) | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`entries."loftr/fp32"`) |
| lightglue / fp16 | 1408 px (the CAP) | 3108655117 bytes | no | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`entries."lightglue/fp16"`) |
| lightglue / fp32 | 1408 px (the CAP) | 4943228208 bytes | no | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`entries."lightglue/fp32"`) |

The two LoFTR plans extrapolate past the measured range using a fit known to
underestimate there (Q-P2.04-1). Until that question is answered, an OOM
(out-of-memory) during matching is classified (`RunStatus.OOM`), not prevented.

Measured peaks against the budget:

| figure | value | tag, path |
|---|---|---|
| LightGlue fp16 at 2048 px, peak / (0.75 × free) | 1.1238087491804576 | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`entries."lightglue/fp16"`) |
| LightGlue fp32 at 1536 px, peak / (0.75 × free) | 1.0129801211509766 | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`entries."lightglue/fp32"`) |
| LoFTR fp16 at 1024 px, peak / (0.75 × free) | 0.7083142577771749 | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`entries."loftr/fp16"`) |
| LoFTR fp32 at 1024 px, peak / (0.75 × free) | 0.8269613910743353 | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`entries."loftr/fp32"`) |

## 5. Where the profile is *not* used yet

`LoFTRMatcher.max_tile_px` (src/lunar_reg/match/learned.py:122) calls
`plan_dense_tile` **without** a profile. It therefore uses the analytic model in
device.py, which the code labels `ValueSource.INFERRED`. That model's constants:

| constant | value | tag, path |
|---|---|---|
| `BACKBONE_BYTES_PER_PX` | 3203.0 | CAP, src/lunar_reg/device.py:225 (fitted on CPU before the driver worked; not a GPU measurement) |
| `FP16_BACKBONE_FACTOR` | 0.6 | CAP, src/lunar_reg/device.py:232 (code comment: "ESTIMATED, NOT MEASURED") |

With the profile's free-memory reading, the analytic model plans:

| precision | analytic tile | tag, path |
|---|---|---|
| fp16 | 1408 px | COMPUTED from the INFERRED model, `data/processed/gpu_run/vram_computed.json` (`analytic_inferred."loftr/fp16"`) |
| fp32 | 1088 px | COMPUTED from the INFERRED model, `data/processed/gpu_run/vram_computed.json` (`analytic_inferred."loftr/fp32"`) |

The analytic fp16 plan (1408 px) is larger than the profile's (1216 px, §4). It
is also larger than the largest tile ever measured (1024 px,
`configs/device_profiles/rtx4060-laptop.json`).

In the P2.11 GPU run, this guard limited LoFTR to 896 px (COMPUTED at run time
by the INFERRED analytic `plan_dense_tile` model above, from its CAP constants and
the free-VRAM reading of that moment; not a measurement and not in
`vram_computed.json`; the value is reported in
`data/processed/gpu_run/anchor/console_step1.log`).
The untiled 1343 × 1330 px reference crop was then refused as `matcher_error`
(`data/processed/gpu_run/anchor/products.json`). The free VRAM at that moment is
in no artefact: `[INSERT RESULT]`. Whether the guard should consult the profile,
and whether the runner should tile LoFTR, is open as Q-P2.11-2 (see also
Q-P2.02-4).

## 6. Sparse matchers: the keypoint cap

LightGlue attends over keypoints (distinctive points), so its attention cost
grows with the number of keypoints, not with image area. The keypoint cap is a
step function of free VRAM (`plan_keypoint_budget`, src/lunar_reg/device.py:591):

| free VRAM | keypoints per tile | tag, path |
|---|---|---|
| ≥ 10 GiB | 4096 (`SAFE_MAX_KEYPOINTS`) | CAP, src/lunar_reg/device.py:588 and :595 |
| ≥ 5 GiB | 2048 (`DEFAULT_MAX_KEYPOINTS`) | CAP, src/lunar_reg/device.py:587 and :597 |
| below | 1024 | CAP, src/lunar_reg/device.py:598 |

This card's total (8161198080 bytes, MEASURED, profile) is below 10 GiB, so the
4096 branch is never reached here.

## 7. The P2.11 end-to-end GPU run

| figure | value | tag, path |
|---|---|---|
| LightGlue peak VRAM on the anchor window (4 m/px) | 2830844416 bytes | MEASURED, `data/processed/gpu_run/anchor/store_rows.json` (`x_peak_vram_bytes`, lightglue row) |
| that peak / (0.75 × total) | 0.46248837294895473 | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`gpu_run.max_peak_over_0p75_total`) |
| that peak / (0.75 × free at profiling) | 0.48828063181068004 | COMPUTED, `data/processed/gpu_run/vram_computed.json` (`gpu_run.max_peak_over_budget_at_measure`) |
| OOM outcomes | 0 | MEASURED, `data/processed/gpu_run/anchor/run_record.json` (`outcome_counts.oom`) |

The full run write-up is `docs/GPU_RUN.md`.

## 8. Design rules that follow (no figure attached)

- **Never load a whole product.** OHRC strips and the reference rasters are read
  through windows (`ingest/tiling.py`, DECISIONS G40). Matching works tile by tile
  (`match/tiled.py`), and the registered output is written block by block
  (`align/warp.py`, `warp_blockwise`). Peak memory then depends on tile size, not
  product size.
- **Classify memory failures; never skip them.** `torch.OutOfMemoryError` becomes
  `RunStatus.OOM` / `TileStatus.OOM`, followed by `torch.cuda.empty_cache()`
  (Phase_2/skills/gpu-safety/SKILL.md).
- **Fallback order when a tile does not fit:** a smaller tile, then fp16, then
  LightGlue instead of LoFTR (§3: LightGlue's measured peak per pixel is lower),
  then a classical CPU matcher (`sift`, `akaze`, `asift`), which uses no VRAM.
- **Not VRAM-bound:** footprint geometry (`ingest/footprint.py`), metrics
  (`eval/`), preprocessing (`preprocess/`, OpenCV on the CPU) and block-wise
  warping. Their limit is host RAM (≤ 12 GB, DECISIONS G18) and disk I/O.
