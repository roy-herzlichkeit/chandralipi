# STATUS

current: P1.25
phase: 1
state: READY
branch: phase-1
last_done: P1.24
notes:
- P1.24: configs/references.json (5 refs: 2 NAC label, 2 SELENE raster, TMC-2 ortho raster non-independent); lro.georeference_from_raster (C10; SELENE DOCUMENTED, TMC-2 ortho INFERRED); prepare_window_pair(centre_sample=) (C11); new lunar_reg/cross.py (C28); SiteConfig reference_georef/name/independent/centres; scripts/run_cross.py find|run.
- Real control (harness data test): every on-disk TMC-2/IIRS strip DISJOINT from the Vikram NAC and SELENE refs (457-664 km); 3 overlaps exist against the TMC-2 ortho (dev run into scratch only; P1.18 step 4 writes the real data/processed/cross/overlaps.json).
- Non-blocking Q-P1.24-1 (choices beyond the LLD). scripts/ci.sh: 941 passed, 18 deselected (log: scratchpad p1/ci_P1.24.log).
- P1.18 steps 1, 3, 5 artefacts stay (uncommitted, data/processed); P1.18 re-runs steps 2 and 4 after P1.25.
