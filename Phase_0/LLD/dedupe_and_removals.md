# LLD — duplicates and dead files (P0.03, P0.04)

Closes: A090 (S16 shadow_mask), A091 (S16 footprint/scale_ratio), A017 (tooling-9). Scope from DECISIONS G20.

## P0.03 — one `shadow_mask`, one scale-ratio limit
| file | change |
|---|---|
| `preprocess/radiometric.py` | delete `def shadow_mask`; `suppress_shadows` calls `lunar_reg.preprocess.shadow.shadow_mask` (import at module top: `from lunar_reg.preprocess.shadow import shadow_mask`). `shadow.py` imports nothing from `radiometric`, so there is no cycle. Behaviour of `suppress_shadows` is unchanged (both implementations compute `image <= percentile(finite, p)`). |
| `preprocess/__init__.py` | import `shadow_mask` from `lunar_reg.preprocess.shadow`, not from `radiometric`; `__all__` unchanged |
| `constants.py` | delete `def scale_ratio` (no callers; its only test is in `tests/test_footprint.py`, deleted in P0.04 — delete that one test function in P0.03 so the suite stays green). Keep `MAX_SAFE_SCALE_RATIO = 8.0`. |
| `ingest/pseudo_gt.py` | replace the literal `MAX_DIRECT_SCALE_RATIO: float = 8.0` with `from lunar_reg.constants import MAX_SAFE_SCALE_RATIO as MAX_DIRECT_SCALE_RATIO` (keeps the name that `overlap.find_cross_sensor_pairs` imports; one value in one place). `pseudo_gt.scale_ratio` stays. |

## P0.04 — remove `ingest/footprint.py`, `configs/default.yaml`, PyYAML
| file | change |
|---|---|
| `constants.py` | add `moon_datum()` (body moved verbatim from `footprint.py`, including `@lru_cache(maxsize=1)` and its docstring) directly after `MOON_DATUM_NAME` |
| `ingest/overlap.py` | change only the import of `moon_datum` to `from lunar_reg.constants import moon_datum` |
| `ingest/__init__.py` | remove the `from lunar_reg.ingest.footprint import ...` line and the names `Footprint`, `overlap` from `__all__`; keep `moon_datum` in `__all__`, imported from `lunar_reg.constants` |
| `ingest/footprint.py` | delete |
| `tests/test_footprint.py` | delete (its remaining tests cover only the deleted legacy `Footprint`/`overlap`/`find_pairs`) |
| `configs/default.yaml` | delete; delete `configs/` if it becomes empty |
| `pyproject.toml` | remove the `"PyYAML>=6.0",` dependency line |
| `README.md` | line 47 `configs/  default.yaml — the validated defaults` → remove the line; any other README sentence naming `configs/default.yaml` is removed |

Before deleting, run `grep -rn "footprint import\|ingest.footprint\|default.yaml\|import yaml" src scripts dashboard tests notebooks` and fix every hit named above; a hit in a file not listed here → QUESTIONS entry (non-blocking), do not edit that file.
