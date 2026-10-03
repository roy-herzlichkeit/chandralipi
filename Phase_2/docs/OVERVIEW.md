# Phase 2 — what it does and why (for the human reviewer)

Terms from the Phase 0/1 overviews are used as defined there.

## Goal
Run the pipeline on the laptop's GPU (the graphics card, used here for the neural matchers), measure how much GPU memory each matcher really needs, and use that to refine each registration at the reference map's full resolution.

## New terms
| term | meaning | example |
|---|---|---|
| **VRAM** | the GPU's own memory; a matcher that needs more than is free crashes with "out of memory" (OOM) | the RTX 4060 Laptop has 8188 MiB, about 754 MiB used by the desktop (`docs/plan/FABLE_NOTES.md` §9, nvidia-smi 2026-09-29) |
| **device profile** | a measured table of memory use per matcher and tile size for one GPU | `configs/device_profiles/rtx4060-laptop.json` (written by P2.04) |
| **tile** | a small square cut from a large image so a matcher can process it within memory | 512 × 512 pixels |
| **prior-rectified tile** | the reference piece is warped into the source tile's scale and angle before matching, using our current best transform | lets a 0.25 m OHRC tile be compared with a 1 m NAC tile |
| **native resolution** | the finest detail an image actually has | NAC ortho: 1 m per pixel; we refine at 1 m, not at the 4 m working scale |
| **drift** | how far the fine (native) answer moved away from the coarse one | ≤ 1 coarse pixel (4 m) is the acceptance rule |

## Prompts
P2.00 check the GPU → P2.01–P2.04 measure memory and build the profile → P2.05 record device/time/memory in every result and classify OOM → P2.06–P2.07 tiling that handles scale and rotation, memory caps → P2.08–P2.09 native refinement and georeferenced output → P2.10–P2.11 run it all on the GPU and document the numbers from the run.
