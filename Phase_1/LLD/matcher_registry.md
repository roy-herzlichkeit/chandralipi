# LLD — one matcher registry + SuperGlue opt-in (P1.14)

Closes: A114 (match-13, moved here from P1.17), A109 (match-20). Decision: G11 (CLARIFY Q13).

## 1. Registry in `match/__init__.py`
```python
MATCHER_NAMES = ("sift", "asift", "akaze", "kaze", "orb", "brisk", "rift2", "loftr", "lightglue", "superglue")
ALIASES = {"disk": "lightglue", "lightglue/disk": "lightglue", "loftr/outdoor": "loftr"}
def build_matcher(name: str, *, device: str | None = None, **kwargs) -> Matcher
```
- Name lookup is case-insensitive after `ALIASES`; unknown → `ValueError(f"unknown matcher {name!r}; known: {MATCHER_NAMES}")`.
- `sift … brisk`, `rift2` → `classical.build_classical(name, **kwargs)` (`device` ignored).
- `loftr` → `learned.LoFTRMatcher(device=device, **kwargs)`; `lightglue` → `learned.LightGlueMatcher(device=device, **kwargs)`.
- `superglue` → `superglue.SuperGlueMatcher(device=device, accept_noncommercial_licence=<§2>, **kwargs)`.
- `learned.build_matcher` is deleted; `match/__init__.py` exports the new `build_matcher` and `MATCHER_NAMES`.
- `pipeline._build_matcher(name)` becomes `return build_matcher(name)` (kept as a module-level function because tests monkeypatch it). `LEARNED_MATCHERS` stays (used for lazy-import decisions elsewhere).

## 2. SuperGlue gate (G11)
- Constructor parameter renamed `accept_noncommercial_licence: bool = False`; the old keyword `acknowledge_noncommercial_licence` is still accepted (either True enables).
- The registry enables it when `kwargs.pop("accept_noncommercial_licence", False)` is True **or** `os.environ.get("SUPERGLUE_ACCEPT_NONCOMMERCIAL") == "1"`; otherwise the constructor raises `PermissionError` (unchanged text), which `register_pair` classifies as `MATCHER_ERROR`.
- `weights_dir` default: env `SUPERGLUE_DIR` (path to a local checkout of `magicleap/SuperGluePretrainedNetwork`); None → `ImportError` with the existing explanatory message at first `match()`.
- Every `MatchResult.meta` from SuperGlue carries `licence = "SuperGlue weights: Magic Leap, noncommercial research only"`; `register_pair` copies it into `extra["licence"]` (the `matcher_<k>` copy from P0.09 produces `matcher_licence`; additionally set `extra["licence"]` explicitly when the meta key is present).

## 3. Import without polluting `sys.path` (A109)
`_get_model` loads `<weights_dir>/models` as a package under the unique name `_superglue_models` with `importlib.util.spec_from_file_location("_superglue_models", <dir>/"__init__.py", submodule_search_locations=[str(<dir>)])`, registers it in `sys.modules` only for the duration of `importlib.import_module("_superglue_models.matching")`, then reads `Matching`. `sys.path` is never modified. A missing `__init__.py` → the same `ImportError` message.

## 4. Tests the prompt adds (`tests/test_matcher_registry.py`)
Every name in `MATCHER_NAMES` except `superglue`, `loftr`, `lightglue` builds on CPU; aliases resolve; unknown name raises; `superglue` without env/flag → `PermissionError`; with `SUPERGLUE_ACCEPT_NONCOMMERCIAL=1` and a fake `weights_dir` containing `models/__init__.py` + `models/matching.py` defining a stub `Matching` class → the model loads, `sys.path` is unchanged afterwards; `register_pair(..., PipelineConfig(matcher="superglue"))` without licence → `MATCHER_ERROR` with `"licence"` in the detail (case-insensitive).
