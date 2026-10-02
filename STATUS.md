# STATUS

current: P1.23
phase: 1
state: READY
branch: phase-1
last_done: P1.22
notes:
- P1.22: new docs/results/ holds saved sources: ci_20261002.txt (984 passed, 21 deselected, ruff clean), fields/params/catalog_20261002.txt, live_store_20261002.txt (16 index rows, 31 failures, all synthetic=False), live_store_pairs_20261002.txt (4 distinct image pairs), vikram_2024.md, jaxa_wac_2026-09-08.md.
- README: provenance table = pasted `lunar-reg fields` block; known-gap 3 (polar) deleted; synthetic-flag explanation replaces "no CH-2 product"; OHRC/NAC row drops PCA; self_residual_subpixel wording; links point to docs/results/.
- CONTEXT.md rewritten with cited sources (Size = [INSERT RESULT]); CONTEXT_HANDOFF.md has "Current status, 2026-10-02" table, sections 0-7 are history (Superseded on §0, §1.4, §3, §4).
- web/public/data/results.json regenerated (16 pairs, 31 failures, 0 load errors).
- For P1.23: src/lunar_reg/preprocess/config.py:11 docstring still says ohrc_nac_config includes PCA, but the code does not.
