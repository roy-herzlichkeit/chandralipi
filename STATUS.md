# STATUS

current: P1.11
phase: 1
state: READY
branch: phase-1
last_done: P1.10
notes:
- P1.10: new preprocess/presets.py (C12): PRESET_NAMES, PresetOutcome (+report()), apply_preset, preset_config, choose_default_preset (LLD §3; ValueError on unknown preset names in ablation rows). Output uint8, 0 = nodata, no geometric steps. Failure detail "<side>: <step>: <status>: <reason>". Review fixes: float NaN/inf pixels -> nodata (output 0) whatever nodata/mask; ohrc_nac/clahe_shadow flat output over valid pixels -> degenerate_output (step 'output_check') -> PREPROCESS_FAILED (Q-P1.10-2, non-blocking).
- PipelineConfig.preprocess = "none" (validated in __post_init__). register_pair stage 0 calls presets.apply_preset via module attribute; failure/exception -> PREPROCESS_FAILED, stage "preprocess". PairResult keeps input images. extra["preprocess"] on every RunOutcome and PairResult.extra; extra["preprocess_placeholders"] on PairResult.extra.
- Q-P1.10-1 (non-blocking): after a preset, ECC gets nodata=0 when a mask or config.nodata was given, or a float input has non-finite pixels; beyond LLD §2 (mask case only) -> LLD deviation for the review pack.
- check_P1.10 ~70 s, over G18 30 s budget; cause is existing test_pipeline.py::test_every_available_detector_produces_usable_matches[asift] (~60 s), unchanged by P1.10. scripts/ci.sh: 765 passed (log: scratchpad p1/ci_P1.10.log).
