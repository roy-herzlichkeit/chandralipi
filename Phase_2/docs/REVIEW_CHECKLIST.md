# Phase 2 — review checklist (human)

Diff range: `git diff phase-1-approved..phase-2` (G07).

- [ ] `REVIEW_PACK_2.md`: `verify.sh` exit 0 (GPU tests ran, not skipped — check the skip reasons in `score.json`).
- [ ] `configs/device_profiles/rtx4060-laptop.json` exists and cites its run record.
- [ ] `docs/GPU_RUN.md`: every number next to an artefact path; native refinement status stated.
- [ ] `docs/VRAM_CONSTRAINTS.md`: every figure tagged MEASURED / COMPUTED / CAP.
- [ ] Open the native GeoTIFF of the anchor in QGIS (or `gdalinfo`): its origin and pixel size match the NAC grid at 1 m.
- [ ] `Phase_2/QUESTIONS.md` resolved.
Questions for external reviewers: the tile rectification composition (REVIEW_FOCUS #1); the pixel-centre matrices (#2).
