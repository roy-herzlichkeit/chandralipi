# LLD — preprocessing presets inside register_pair, and the ablation rule (P1.10, P1.18, P1.19)

Produces: C12, C03 field `preprocess`. Closes: A061/A062 (S4). Decision: G09. CLARIFY Q8/R1.

## 1. `preprocess/presets.py` (new)
```python
PRESET_NAMES = ("none", "ohrc_nac", "clahe_shadow")
```
| preset | per side (same for source and reference) | reason |
|---|---|---|
| `none` | copy inputs; when not uint8, `to_uint8(x, valid=v)` | today's behaviour |
| `ohrc_nac` | `ohrc_nac_config(resample=False, georeference=False)` → normalize → clahe → invert → dilate | Makharia et al. chain (paper structure; parameters partly PLACEHOLDER) |
| `clahe_shadow` | normalize → shadow (`method="gamma"`) → clahe | the Q8 example: lift shadows, then local contrast |
`apply_preset(name, source, reference, *, source_valid=None, reference_valid=None, nodata=0) -> PresetOutcome`:
- `valid` masks: given masks, else `image != nodata` when `nodata` is not None, else all True.
- runs `preprocess.pipeline.run_pipeline` per side with a `PreprocessContext(valid=…)` (`PreprocessContext.valid` and the handlers passing it are added by P1.09, see `preprocess_geometry.md` §6);
- `ok = not (src_result.failed or ref_result.failed)`; `history` = both sides' records as dicts with `side`; `uses_placeholders` = union of both sides; on failure `source`/`reference` are None and `detail` names the first FAILED/DEGENERATE step;
- output uint8, 0 = nodata, shapes unchanged.
Unknown name → `ValueError(f"unknown preset {name!r}; choose one of {PRESET_NAMES}")`.

## 2. `register_pair` (C03 field `preprocess`)
`PipelineConfig.preprocess: str = "none"` (validated in `__post_init__`: not in `PRESET_NAMES` → `ValueError`).
Stage 0 (before matching): if `config.preprocess != "none"` → `presets.apply_preset(...)` called through the module attribute (`from lunar_reg.preprocess import presets` inside `register_pair`; the harness monkeypatches it); not ok → `RunOutcome(PREPROCESS_FAILED)`, `extra["stage"] = "preprocess"`, detail = preset detail. The preprocessed images feed matching, estimation, ECC and uniformity; `PairResult.source_image/reference_image` keep the **input** images (thumbnails show what was registered, not the filtered view). `extra["preprocess"] = name`, `extra["preprocess_placeholders"] = ",".join(sorted(uses_placeholders))`. When `source_valid`/`reference_valid` are given and `config.nodata is None`, ECC gets `nodata=0` (presets encode nodata as 0).

## 3. Ablation rule (applied by P1.19 to the P1.18 artefact)
`choose_default_preset(ablation: dict) -> tuple[str, str]` in `presets.py` returns `(winner, reason)`. `ablation` is the JSON written by P1.18 (`data/processed/ablation/ablation.json`):
```json
{"anchor": [{"preset": "...", "matcher": "...", "status": "ok", "n_inliers": 0, "u_score": 0.0}],
 "synthetic": [{"preset": "...", "matcher": "...", "azimuth_delta_deg": 0, "seed": 0, "status": "ok", "truth_rms_px": 0.0}]}
```
Rule, in order:
1. `anchor_pass(p)` = number of anchor rows for preset p with `status == "ok"`, `n_inliers ≥ 20`, `u_score ≥ 0.7` (Q18 targets).
2. Candidates = presets with the maximum `anchor_pass`.
3. Tie-break: lowest median `truth_rms_px` over all synthetic rows with `status == "ok"` for that preset; a preset with no OK synthetic row ranks last.
4. Remaining tie → `"none"` if it is among the candidates, else the first in `PRESET_NAMES` order.
5. Guard: if `anchor_pass(winner) < anchor_pass("none")` → `"none"` (cannot happen after step 2, kept as an assertion).
`reason` states the numbers used, e.g. `"anchor passes none=2 ohrc_nac=3 clahe_shadow=1; ohrc_nac wins on anchor"`.
P1.19 sets `PipelineConfig.preprocess`'s default to `winner` and writes `docs/PREPROCESS_ABLATION.md` quoting the table from `ablation.json` with its path (G19).

## 4. Tests the prompt adds (`tests/test_presets.py`)
`none` is identity on uint8 input; each preset keeps shape/dtype and keeps a zero border at 0; an all-zero image → `ok False` with a DEGENERATE detail; unknown name raises; `register_pair` with a monkeypatched `apply_preset` returning `ok=False` → `PREPROCESS_FAILED`; `choose_default_preset` on three hand-made ablation dicts (clear anchor winner; anchor tie broken by synthetic; full tie → none).
