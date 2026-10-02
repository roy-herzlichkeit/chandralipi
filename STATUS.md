# STATUS

current: P1.23
phase: 1
state: READY
branch: phase-1
last_done: P1.23
notes:
- P1.23 was the last prompt of phase 1; §Phase end (verify.sh, benchmark/run.sh, REVIEW_PACK_1.md, tag phase-1-done) is pending.
- P1.23: setup.sh/up.sh/run_dashboard.sh hints now say `setup.sh --data <bundle>` or `scripts/run_vikram.py` (no build_demo_results.py); .gitignore already had Phase_*/benchmark/out/ (unchanged).
- ingest/__init__, fieldmap, manifest docstrings state per-field-group status citing `lunar-reg fields` (docs/results/fields_20261002.txt: 27 fields, 5 documented, 2 unverified, 20 verified) and moon_datum(); config.py no longer claims PCA for ohrc_nac_config. Review fixes: manifest.py geometry_resolved docstring splits PDS4 from LRO PDS3 rows; fieldmap.py marks incidence VERIFIED; new tests/test_ingest_status_text.py.
- Docstring/comment/hint-string edits only (the harness AST check passes). config.py was not ruff-formatted because that would reflow existing code lines.
- Q-P1.23-1 (non-blocking): the stale pds4.py docstrings (A116) are outside the P1.23 file fence and were left unchanged.
