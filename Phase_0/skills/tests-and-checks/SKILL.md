---
name: tests-and-checks
description: How implementer sessions write tests, run the per-prompt check, and read a failing harness. Used by every prompt.
---

# Tests and checks

## Running
| what | command |
|---|---|
| the prompt's check | `bash Phase_<i>/harness/check_P<i>.<jj>.sh` (exit 0 = pass; < 30 s) |
| one test file | `.venv/bin/python -m pytest tests/test_x.py` |
| CPU suite | `bash scripts/ci.sh` (after P0.01) |
| lint the files you touched | `.venv/bin/ruff check <files>`; then `.venv/bin/ruff format <files>` (only files you modified, G21) |

## Reading a failing check
- `CHECK FAIL: harness/benchmark files differ from harness/MANIFEST.sha256` → a protected file was changed. Restore it with `git checkout -- Phase_<i>/harness Phase_<i>/benchmark`. Never regenerate the manifest.
- A harness test failure names the contract or LLD rule in its assertion message. Fix the implementation, not the test. If the test contradicts the LLD, write a QUESTIONS entry (BLOCKER if it stops DONE WHEN).

## Writing tests (`tests/test_<slug>.py`)
| rule | exact behaviour |
|---|---|
| markers | `@pytest.mark.gpu` (needs CUDA), `@pytest.mark.data` (needs files under `data/raw`), `@pytest.mark.weights` (needs `~/.cache/torch/hub/checkpoints/*`); each such test also calls `pytest.skip("<reason>")` when the resource is absent |
| no network | tests never touch the network |
| determinism | seed every RNG (`np.random.default_rng(<int>)`); no wall-clock assertions |
| tmp files | use `tmp_path`; never write under `data/` from a test |
| importing a script | `spec = importlib.util.spec_from_file_location("run_vikram", Path("scripts/run_vikram.py")); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)` |
| stubbing a matcher | `monkeypatch.setattr("lunar_reg.pipeline._build_matcher", lambda name, **kw: Stub())` where `Stub` has `name` and `match(src, ref) -> MatchResult` |
| synthetic lunar scene | `from lunar_reg.eval.scenes import fractal_terrain, add_craters, hillshade, illumination_pair` (all seeded) |
| exact-shift ground truth | crop two windows of one image at integer offsets `(dx, dy)`: a source point `(x, y)` maps to `(x + dx, y + dy)` with no interpolation error |
| GPU tests | never run two GPU processes at once (CLAUDE.md); keep inputs ≤ 512 px |
