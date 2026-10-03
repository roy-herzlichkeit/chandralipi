# STATUS

current: P2.05
phase: 2
state: READY
branch: phase-2
last_done: P2.04
notes:
- Profile configs/device_profiles/rtx4060-laptop.json (source measured, device "NVIDIA GeForce RTX 4060 Laptop GPU", driver 580.178.04, torch 2.14.0+cu130; free_bytes_at_measure 7730102272; not hand-edited). max_tile_px: loftr/fp16 1024 (7 points), loftr/fp32 1024 (7 points), lightglue/fp16 2048 (5 points), lightglue/fp32 1536 (4 points; 2048 px was OOM, data/processed/benchmarks/p2_04/console_4.log).
- Runs: LLD §P2.04 commands 1-4 one at a time, each under `systemd-run --user --scope -p MemoryMax=12G -p MemorySwapMax=0` (scope line 1 of data/processed/benchmarks/p2_04/console_1..4.log; run_record `command` holds only the inner lunar-reg argv), all exit 0.
- Artefacts in data/processed/benchmarks/p2_04/: benchmark_<m>_<p>.json, run_<m>_<p>/run_record.json (all 4 validate; profile names run_lightglue_fp32/run_record.json), console_1..4.log.
- Open Q-P2.04-1 (non-blocking): loftr fixed_bytes negative (fp16 -242883933, fp32 -192735154, same profile JSON); growth above 768 px steeper than S^2 (console_1.log, console_2.log), so plan_tile with free_bytes_at_measure plans loftr at 1216/1152 px, beyond measured max 1024. P2.05/P2.06 should read it and decide whether to cap at max_tile_px.
- No code edited; tests/test_device.py CPU pins unchanged.
