# STATUS

current: P1.22
phase: 1
state: READY
branch: phase-1
last_done: P1.21
notes:
- P1.21: side_by_side_matches takes src_scale/ref_scale; new figures.thumbnail_transform (S_ref@T@inv(S_src)) and points_outside used by both viewers; conditioning maps use metrics['model'] and the full-resolution shape.
- export_web_data.py swaps .export_tmp in atomically (rollback if the results.json rename fails; recovery finishes a swap killed between the renames), exports failures/nFailures/licence/nLoadErrors and a relative sourceDirectory. Live export: 16 pairs, 31 failures, 0 load errors, sourceDirectory data/processed/results (web/public/data/results.json).
- Dashboard has a "Failed runs" table and a licence pill. Synthetic wording is now "this scene is synthetic (generated)" in demo.py and app.py. reindex --exclude-synthetic never overwrites a stash file (_<created_utc> suffix, otherwise refuses).
- Open: Q-P1.21-1 (web/src cannot show the licence or failures without a source change) and Q-P1.21-2 (load_all_pairs returns no paths; the scan is replayed).
- 5 touched files were ruff-formatted in full, which reformats some lines that were already there. CI: 976 passed.
