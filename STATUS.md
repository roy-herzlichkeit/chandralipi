# STATUS

current: P2.03
phase: 2
state: READY
branch: phase-2
last_done: P2.02
notes:
- device.py: TileBudget gains fits (default True) + source (default INFERRED); __str__ shows [source] and "DOES NOT FIT". plan_dense_tile(device, precision, matcher, profile=None): profile entry -> MEASURED plan via DeviceProfile.plan_tile; else analytic _analytic_tile (INFERRED). MIN floor sets fits=False when est_peak > safety*free (incl. 0-byte UNKNOWN reading). profile=None never auto-loads a profile.
- DeviceProfile (C16) + appended `extra: dict` for torch/cuda/driver/run_record/free_bytes_at_measure (Q-P2.02-1), helpers to_dict()/entry(); load validates schema==1, required keys, numeric fixed_bytes/bytes_per_px (ValueError otherwise). Planner caps at MAX_DENSE_TILE_PX only, entry max_tile_px unused (Q-P2.02-2).
- load_profile_for: exact device_name match in root/*.json; invalid file raises; duplicates -> canonical <slug>.json wins + WARNING (harness test_C16_roundtrip requires tolerance, Q-P2.02-3); relative root falls back to repo root.
- configs/device_profiles/README.md written (schema, lunar-reg benchmark, measured-only); no profile JSON written. New tests/test_device_profiles.py (13 tests). CPU suite (scripts/ci.sh): 1017 passed, 22 deselected.
- P2.02 review fixes: profile load refuses non-'measured' source, bytes_per_px<=0 and bad points; plan_tile never plans a negative peak (measured-points floor), fits=False at 0 free bytes. Open non-blocking: Q-P2.02-4 (learned.py max_tile_px ignores fits, A126 caller side) and Q-P2.02-5 (P2.03 fit_profile may give negative intercept; source rule).
