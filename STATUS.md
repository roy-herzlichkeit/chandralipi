# STATUS

current: P1.15
phase: 1
state: READY
branch: phase-1
last_done: P1.14
notes:
- P1.14: one registry `lunar_reg.match.build_matcher(name, *, device=None, **kw)` plus MATCHER_NAMES/ALIASES (case-insensitive; unknown name -> ValueError). learned.build_matcher deleted; pipeline._build_matcher and cli.cmd_register now call the registry (cli: import line only).
- SuperGlue: needs `accept_noncommercial_licence=True` (old `acknowledge_...` keyword still accepted) or env SUPERGLUE_ACCEPT_NONCOMMERCIAL=1. weights_dir defaults to env SUPERGLUE_DIR. Loaded as `_superglue_models` without touching sys.path. meta["licence"] = LICENCE_TAG.
- register_pair copies the licence into PairResult.extra["licence"] (and matcher_licence) and also into RunOutcome.extra after matching, so failure rows get x_licence. A refused SuperGlue -> MATCHER_ERROR.
- Q-P1.14-1 (non-blocking): check passes but takes about 73 s (> G18 30 s). Cause: existing test_pipeline asift parametrisation, 62-67 s, independent of P1.14.
- scripts/ci.sh: 880 passed (log: scratchpad p1/ci_P1.14.log).
