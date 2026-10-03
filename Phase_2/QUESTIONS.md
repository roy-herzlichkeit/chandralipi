# Phase 2 — questions

Implementers append entries here (format in root `CLAUDE.md` §Doubts). Empty at plan time.

## Q-P2.02-1  DeviceProfile carries an appended `extra: dict` field (not in the C16 dataclass)
context: CONTRACTS.md C16 (`DeviceProfile` fields `slug, device_name, total_bytes, matchers, measured_utc, source, path`); src/lunar_reg/device.py `DeviceProfile`
question: C16's JSON has `free_bytes_at_measure`, `torch`, `cuda`, `driver`, `run_record` but the dataclass has no field for them, so `load` then `save` would drop them and write a file that is no longer C16-complete. Is an appended `extra: dict = field(default_factory=dict)` (holding every non-dataclass key, written back by `save` in C16 key order) acceptable, or should these become named fields?
what I did meanwhile: appended `extra` after `path` (all C16 fields keep their names, order and defaults), plus helper methods `to_dict()` and `entry(matcher, precision)`. Reversible: P2.03 can read/write the same keys through `extra`; promoting them to named fields later only changes the dataclass.

## Q-P2.02-2  Should the profile planner also cap the tile at the entry's `max_tile_px`?
context: Phase_2/LLD/device.md §P2.02 ("largest multiple of 64 ≤ MAX_DENSE_TILE_PX"); C16 entry key `max_tile_px`
question: the fitted model `fixed + bytes_per_px * S^2` has no S^4 term, so above the largest measured tile it can under-estimate LoFTR's peak. Should `DeviceProfile.plan_tile` cap at `min(MAX_DENSE_TILE_PX, entry["max_tile_px"])` to avoid extrapolating beyond the measured range?
what I did meanwhile: followed the LLD literally (cap at `MAX_DENSE_TILE_PX` only; `max_tile_px` is stored but not used by the planner). Reversible: a one-line `min(...)` in `DeviceProfile.plan_tile`.

## Q-P2.02-3  `load_profile_for` with several files for the same device
context: Phase_2/harness/tests/test_contracts_P2.py::test_C16_roundtrip (saves `copy.json` next to `test-gpu.json`, both device "Test GPU", then expects `load_profile_for` to return a profile); src/lunar_reg/device.py `load_profile_for`
question: the LLD says "the profile whose device_name equals the CUDA device name" without saying what happens when two files match. The harness test rules out raising. Is "the canonical `<slug>.json` (file stem == slug) wins, then file-name order, plus one WARNING listing all matches" the intended rule?
what I did meanwhile: implemented that rule. Invalid profile files raise `ValueError` (not skipped). A relative `root` that does not exist under the CWD is also tried under the repo root, so the default `configs/device_profiles` works from any working directory. Reversible: local to `load_profile_for`.

## Q-P2.02-4  `LoFTRMatcher.max_tile_px` drops `TileBudget.fits` (AUDIT A126 caller side)
context: src/lunar_reg/match/learned.py:112 (`return plan_dense_tile(self.device, self.precision, self.name).tile_px`); AUDIT.md A126 ("have callers refuse or warn loudly when it is False"); Phase_2/LLD/device.md §P2.02
question: P2.02 adds `fits` but its DO fence covers only device.py, the profile README and tests, and no later Phase 2 LLD or prompt names this caller. On a GPU with too little free memory LoFTR still gets the 256-px floor tile with no warning. Which prompt should make `max_tile_px` (or `TiledMatcher`/`register_pair`, which P2.05/P2.06 touch) log a WARNING or classify the run (e.g. `RunStatus.OOM`/a `TileStatus`) when `not budget.fits`?
what I did meanwhile: nothing in learned.py (outside the fence). `plan_dense_tile` and `DeviceProfile.plan_tile` return `fits=False` (also for a 0-byte, i.e. UNKNOWN, reading) and `TileBudget.__str__` says "DOES NOT FIT". Reversible: a few lines in the caller.

## Q-P2.02-5  Negative fitted `fixed_bytes` and non-measured profile sources
context: src/lunar_reg/device.py `_validate_matchers`, `DeviceProfile.load`, `DeviceProfile.plan_tile`; Phase_2/LLD/device.md §P2.03 (`fit_profile`: least squares of `peak = fixed + k*S^2`)
question: (a) An unconstrained fit over data with an S^4 term can give `fixed_bytes < 0`. Should P2.03's `fit_profile` constrain `fixed >= 0` (or fit through the measured points differently), or is it enough that the planner guards against it? (b) Is refusing a profile whose `source` is not `"measured"` (ValueError on load) the intended reading of C16/G19?
what I did meanwhile: (a) `load` accepts a negative `fixed_bytes` but rejects `bytes_per_px <= 0` and malformed `points`; `plan_tile` estimates `max(fixed + k*S^2, largest measured points peak at tile_px <= S, 1)`, picks the largest multiple of 64 whose estimate fits (identical to the LLD rule whenever the measured points do not exceed the fit), and returns `fits=False` whenever `free_bytes <= 0`. (b) `load` refuses any source other than `measured`; a directly constructed `DeviceProfile` labels its plans with its own `source`, not a hard-coded MEASURED. Reversible: local to device.py.
