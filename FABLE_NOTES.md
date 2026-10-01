# FABLE_NOTES — architect memory (not for humans)

Session A · 2026-09-29 · HEAD `bbf9585` + uncommitted (see REPO_TREE §0). Read-only session; only this file + CLARIFY.md written.
Evidence tags: **R** = I read the code line · **M** = measured by a command this session or recorded in REPO_TREE §3 · **D** = repo doc says so, not re-verified · **I** = my inference, untested.

## 0. Environment facts
| fact | tag |
|---|---|
| Laptop: RTX 4060 **Max-Q Mobile** (AD107M) on PCIe; NVIDIA kernel module NOT loaded; `nvidia-smi` fails | M (`lspci`, `lsmod`) |
| torch 2.14.0+cpu, kornia 0.8.3, cv2 4.14.0 (pinned <5: AKAZE), py 3.12.3 venv `.venv` | M |
| 24 cores, 15 GB RAM, 817 GB free disk | M |
| Full suite: 434 pass, 4 fail, 1 skip, 268 s. ruff check clean; `ruff format --check` 60 files dirty; mypy config unusable | M (REPO_TREE §3) |
| `~/.claude/CLAUDE.md` == project `CLAUDE.md` (architect role) → every Claude session for this user, incl. Opus implementers, loads "You are the principal architect" | M (`head ~/.claude/CLAUDE.md`) |
| `.claude/settings.local.json`: `defaultMode: bypassPermissions`; no `.claude/settings.json` exists | R |
| Whether `permissions.deny` is honoured under bypassPermissions: UNVERIFIED → plan a PreToolUse hook as second guard | I |
| No deadline/round date anywhere in repo | M (grep) |

## 1. Architecture: actual vs claimed
| claim (where) | actual | tag |
|---|---|---|
| "Illumination handled in `preprocess/`" (README:11-13) | `pipeline.register_pair` (pipeline.py:97-204) never calls preprocess. Only `cli register` (cli.py:66-69, `standard_chain` per tile) and `lunar-reg preprocess` use it. Every stored real result used `stretch_u8` (run_vikram.py:78) or script-local prep | R |
| `configs/default.yaml` = "validated defaults" (README layout) | never loaded; zero `yaml` refs in src/scripts/dashboard. `refine_threshold_px: 1.0` there is dead | R |
| Tiled full-res matching is the OHRC path | `TiledMatcher` used only by `cli register`. `register_pair` = whole-image match. Vikram ran at 4 m/px on 3 km windows (750 px) | R |
| Pipeline = ingest→overlap→crop→preprocess→match→align→eval | Real end-to-end path is `scripts/run_vikram.py`: label corners (bilinear) + hard-coded NAC transform → crop → resize → `register_pair`. `ingest/overlap.py`, `geometry_grid.py`, `lro.py`, `manifest.py` are NOT on the path that produced any real result | R |
| "zero real OHRC pairs" (CONTEXT.md:38, HANDOFF §0/§7) | stale: 4 OHRC↔NAC results exist (index.parquet 13 rows) | M |
| "save_results footgun not fixed" (HANDOFF §7) | fixed: `save_results` reindexes from disk (results.py:314-327) | R |
| `results_ch2_synthetic_backup/` (CONTEXT, dashboard/app.py:91) | not in `data/processed/` | M |
| 431 tests | 439 collected | M |
| geometry_grid replaces 4-corner homography | code exists; raw `nrp` Vikram products ship NO `_g_grd_d18.csv` (only .img/.xml + misc .oat/.oath/.spm/.lbr) → cannot be exercised on data on disk; the ncp products it was validated on are no longer in `data/raw` | M (`find`) |

## 2. Module map (public surface, path:line)
| module | key API | notes |
|---|---|---|
| `pipeline.py` | `RunStatus`:28 (OK, TOO_FEW_MATCHES, ESTIMATION_FAILED, TOO_FEW_INLIERS, MATCHER_ERROR) · `RunOutcome`:47 · `PipelineConfig`:61 (matcher=akaze, model=homography, ransac 3.0, use_ecc, ecc_prefilter=none, min_matches 8, min_inliers 8, n_bootstrap 40, gsd_m, extra) · `register_pair`:97 · `BatchReport`:208 (`report()`) · `run_batch`:240 | failures never persisted |
| `results.py` | `PairResult`:53 · `index_row`:115 (prefixes m_/u_/c_/x_) · `save_pair`:191 · `load_pair`:224 · `write_index`:264 · `load_index`:277 · `load_all_pairs`:287 · `reindex`:306 · `save_results`:314 · `SCHEMA_VERSION=1`:49 | store = `data/processed/results/{index.parquet,pairs/<pair_id>.npz}`; thumbnails ≤1024 px |
| `match/base.py` | `MatchResult`:18 (float64 N×2, `inliers()`, `concatenate`) · `Matcher` Protocol:93 (`name`, `match(src,ref)`) | the cross-matcher currency |
| `match/classical.py` | `ClassicalMatcher`:129 · `build_classical`:228 (also routes rift2) · `DETECTORS`:41 | |
| `match/learned.py` | `LoFTRMatcher`:71 · `LightGlueMatcher`:151 (DISK) · `build_matcher`:232 | canonical (exported by match/__init__) |
| `match/loftr.py`, `match/superglue.py` | duplicate `LoFTRMatcher`:76, duplicate `LightGlueMatcher`:76, `SuperGlueMatcher`:156 (licence-gated `PermissionError`) | duplicates; not exported |
| `match/tiled.py` | `TiledMatcher`:43 (`match_arrays`, `match_datasets`, `_paired_tile`:218 translation-only prior) | |
| `match/stitch.py` | `stitch_tiles`:156 · `StitchStats`:49 (no failed-tile count) | |
| `match/rift2/*` | `RIFT2Matcher` (matcher.py:94) clean-room | never run on real data (D) |
| `match/benchmark.py`, `match/memory.py` | `benchmark_matcher`:161 · `scaling_exponent`:199 · `measure_in_subprocess`:165 · `MemoryMeasurement`:48 (`CUDA_ALLOCATOR`/`HOST_RSS`) | |
| `device.py` | `get_device`:33 · `free_vram_bytes`:55 (returns 8 GiB nameplate on CPU) · `TileBudget`:69 · `dense_matcher_peak_bytes`:146 · `plan_dense_tile`:163 · `plan_keypoint_budget`:213 · consts `BACKBONE_BYTES_PER_PX=3203`:132 (host RSS), `FP16_BACKBONE_FACTOR=0.6`:138 (ESTIMATED), `MAX_DENSE_TILE_PX=1408`:142, `VRAM_SAFETY_FRACTION=0.75`:30 | |
| `align/estimate.py` | `Transform`:31 (`apply`) · `estimate_transform`:53 (homography=USAC_MAGSAC, affine/partial=RANSAC; no seed arg) | |
| `align/refine.py` | `reestimate_on_inliers`:132 · `choose_ecc_prefilter`:169 · `local_contrast_normalize`:221 · `refine_transform_ecc`:241 (always MOTION_HOMOGRAPHY) · `refine_full`:360 | ECC direction convention verified in docstring; do not rearrange |
| `align/warp.py` | `warp_array`:27 · `warp_blockwise`:60 · `save_registered_geotiff`:120 | |
| `eval/metrics.py` | `compute_metrics`:69 → `RegistrationMetrics` (self-residual RMSE) | |
| `eval/uniformity.py` | `compute_uniformity`:230 · `UNIFORMITY_GATE=0.7`:102 · `enforce_uniformity`:271 (no callers) | U demoted to descriptive (D HANDOFF §2.5) |
| `eval/conditioning.py` | `bootstrap_conditioning`:136 (seeded, on post-RANSAC inliers) · `EXTRAPOLATION_GATE_PX=1.0`:86 · `conditioning_map`:224 | gate the pipeline actually uses (D) |
| `eval/error_budget.py`, `eval/scenes.py` | `attribute_error`:148 · `hillshade`:126 · `_cast_shadow_mask`:96 · `illumination_pair`:173 | hillshade `relief` is unitless exaggeration (I: DTM reuse needs relief = 1/posting_m) |
| `ingest/pds4.py` | `read_label`:249 → `PDS4Product`:130 · `open_product`:334 | |
| `ingest/fieldmap.py` | `Provenance`:35 (VERIFIED/DOCUMENTED/UNVERIFIED) · `Field`:50 · field tuples | |
| `ingest/manifest.py` | `COLUMNS`:37 (incl. corner1..4 lat/lon) · `build_manifest`:106 · `scan_directory`:126 | |
| `ingest/overlap.py` (1186 L) | `OverlapStatus`:113 · `PolarFrame`:184 · `FootprintPolygon`:232 · `intersect`:581 · `footprint_from_row`:676 (ring 1,2,4,3) · `OverlapDiagnostics`:744 · `find_overlapping_pairs`:822 · `geographic_to_pixel_transform`:916 · `polygon_to_pixel_window`:967 · `crop_to_overlap`:1023 · `find_cross_sensor_pairs`:1112 (no callers) | |
| `ingest/geometry_grid.py` (972 L) | `GridStatus`:108 · `GeometryGrid`:226 · `read_geometry_grid`:405 · `pixel_to_lonlat`:683 · `PixelLookup`:724 · `lonlat_to_pixel`:744 (KD-tree + Newton inverse bilinear) · `polygon_to_pixel_window`:914 (same contract as overlap's; deliberately not re-exported) | |
| `ingest/lro.py` | `read_lro_label`:173 · `open_lro_product`:265 · `scan_lro_directory`:325 | trusts GDAL transform → wrong for Vikram NAC |
| `ingest/pseudo_gt.py` | `build_pseudo_gt`:428 · `estimate_confidence`:312 (total=None while UNKNOWN terms) · `loop_closure_residual_m`:565 (tautologically 0) | no production callers |
| `ingest/footprint.py` | `Footprint`:47 · `find_pairs`:103 | legacy parallel footprint system; `find_pairs` no callers |
| `preprocess/*` | `run_pipeline` (pipeline.py:136) · `PreprocessConfig` (config.py:66) presets `ohrc_nac_config`:139 / `iirs_wac_config`:155 · `params.py` `ParamSource`:35 | not on register_pair path |
| `cli.py` | subcommands env, inspect, register, probe-label, fields, manifest, overlap, params, preprocess (build_parser:245) | no `benchmark` subcommand though device.py:137 cites `lunar-reg benchmark` |
| `scripts/run_vikram.py` | `prepare_pair`:118 · `coarse_shift`:178 · `export_stored`:217 · `main`:267; consts NAC_X0/Y0/PROJ:61-62, `DEFAULT_MIN_INLIERS=5`:53, `DEFAULT_PRIOR_SHIFT="556,-2888"`:59 | the only real CH-2 path |
| `scripts/export_web_data.py` | → `web/public/data/results.json` | React site reads only this JSON |
| `dashboard/app.py` | Streamlit, reads results store directly | |

## 3. Data on disk
| item | state | tag |
|---|---|---|
| `data/raw/ohrc_vikram/` 4 × OHRC **raw nrp** (2023-08-23 ×3, 2024-04-25 ×1), 4.2 GB | no geometry grid; misc has orbit/attitude `.oat/.oath`, `.spm`, `.lbr` | M |
| `data/processed/ohrc_vikram_product_ids.txt` | 21 calibrated **ncp** IDs over Vikram, none downloaded | M |
| `data/raw/reference/lro_nac_vikram/` 2 NAC orthos (1 m, 23003×47683 u16, epochs ~8 h apart) + DTM TIF (~3 m) | GDAL geotransform wrong (units); corrected in PROVENANCE.json; UL-x sign flip INFERRED; absolute georef ~1 km | D (PROVENANCE.json) |
| JAXA TC ×3 pairs, LRO WAC crops | used for 9 real non-CH2 results | D |
| `data/processed/results/` 13 rows: 4 OHRC↔NAC (2024 strip; sift/akaze/asift/lightglue) + 9 JAXA | all `synthetic=False` | M |
| `web/public/data/results.json` nPairs 9 | stale (no Vikram) | M |
| `dist/*.tar.zst`, `web/dist/` (130 pair files, old synthetic build) | stale artefacts | M |

## 4. Invariants (load-bearing; any design must keep them)
1. Provenance in code: `Provenance` enum (fieldmap), `ParamSource` (params), `TermSource` (pseudo_gt), `synthetic` flag on `PairResult`. New numbers carry a provenance field, not prose.
2. Failure = classified enum outcome + count + first sample, `report()` printed every run; library logs one line, caller prints report (overlap.py:884-894 pattern).
3. No number without a run; `[INSERT RESULT]` placeholders in docs/REPORT_SECTION.md, gdocs/*, docs/DEMO_SCRIPT.md must stay placeholders until filled from a run.
4. Corner ring order 1,2,4,3 (UL,UR,LL,LR numbering) — pinned by `test_corner_numbering_is_not_ring_order`.
5. ECC arg convention (refine.py:255-267): template=reference, input=source, init=inv(H), invert result.
6. Two RMSEs: `eval/metrics.py` self-residual vs `eval/error_budget.py` truth-based (differ 12.7–58.6× synthetic). Real pairs have no truth → never call self-RMSE "accuracy".
7. Point coords float64, never rounded (base.py, results.py).
8. Polar path: area on sphere, clipping in `PolarFrame` plane.
9. `web/` never affects results; reads JSON only.

## 5. Hidden coupling / gotchas
- `export_stored` rebuilds the reference crop by **regex over free-text provenance** (`x_coarse_pass`, `x_search_prior`; run_vikram.py:205-214). Regex miss → returns (0,0) silently → wrong crop origin → misregistered GeoTIFF exported with no error. R
- `pair_id` is the filename and the only key; format `SENSOR_TAG-REFSENSOR_matcher[_model]` is parsed back by string slicing (run_vikram.py:239). R
- `free_vram_bytes("cpu")` returns 8 GiB → LoFTR tile cap on CPU is computed from a GPU assumption (device.py:57-58). R
- `index_row` flattens `extra` with `x_` prefix; heterogeneous extras → NaN columns → export needed a NaN guard (uncommitted diff). R
- `register_pair` passes `ransac_threshold_px` as the refit threshold (pipeline.py:158-161) → "tight 1 px refit" never happens in the pipeline. R
- Inlier semantics: after `refine_full`, stored `n_matches` = first-pass inliers, `n_inliers` = second-pass inliers; raw matcher count is lost; `m_inlier_ratio` ≈1 (index shows 144/144, 2180/2183). R+M
- Logs: README says min inliers 8 (stored 2024 results were produced at 8); code default now 5 (run_vikram.py:53). D/R
- `run_vikram --dry-run` writes `/tmp/vikram_*`. R
- `vikram_2023_priorshift.log`: TBD-1.8 experiment 1 was started and aborted (1 strip, SIFT 5 / AKAZE 7 matches at ~2 km margin, others not run). Weak evidence that prior is not the only cause. M
- Coarse 8 m/px LightGlue succeeded only on the 2024 strip (106 inliers, shift +556,−2888 m); failed on all 2023 strips. M (logs)

## 6. Suspected bugs / smells (ID for cross-ref)
| ID | issue | evidence | tag | severity |
|---|---|---|---|---|
| S1 | ECC always `MOTION_HOMOGRAPHY`; `model=affine` result silently becomes a homography while `Transform.model` stays "affine"; conditioning then refits affine | refine.py:305-308,340-341; pipeline.py:170-173 | R | H (breaks `--model affine`, TBD 1.8 "prefer affine") |
| S2 | raw match count lost; inlier ratio meaningless post-refine | refine.py:141-143, pipeline.py:158-165,182-184; index rows | R+M | H (problem statement asks inlier ratio) |
| S3 | refit threshold = RANSAC threshold | pipeline.py:160 | R | M |
| S4 | `register_pair` skips preprocessing; README claims otherwise | §1 | R | M |
| S5 | same-sensor overlap scan includes self-pairs, counts each pair twice | overlap.py:839-874 | R | L (TBD 1.6) |
| S6 | `crop_to_overlap` copies parent profile without `window_transform` → crop GeoTIFF carries parent origin | overlap.py:1088-1093 | R (impact untested) | M for georeferenced inputs |
| S7 | `TiledMatcher` swallows per-tile exceptions (incl. OOM) with only a log line; `StitchStats` has no failed-tile count | tiled.py:125-129,186-190; stitch.py:49-70 | R | H for Phase 3 (violates invariant 2) |
| S8 | tile pairing prior is translation-only; cannot pair OHRC(0.25 m) with NAC(1 m) or rotated strips | tiled.py:218-238 | R | H for native-res + Phase 3 |
| S9 | LoFTR raises when input > planned tile; `register_pair` has no tiling → MATCHER_ERROR on large inputs | learned.py:111-118 | R | M |
| S10 | 4 tests fail under bare `pytest` (`from tests.test_ingest_labels import`; no `tests/__init__.py` / `pythonpath`) | test_overlap.py:665,735,774,799 | M | L (trivial) |
| S11 | `ingest/lro.py` trusts GDAL transform → reproduces NAC unit bug | PROVENANCE.json "status" | D | M |
| S12 | NAC UL-x sign flip inferred, ~1 km residual. Hypothesis: PDS3→PDS4 LROC projection-offset sign convention, or `lat_ts` vs `lat_0` reading of "latitude_of_origin −69.3" | PROVENANCE.json; run_vikram.py:61-62 | I | M (absolute georef only) |
| S13 | classified failures printed, never stored → dashboards show only successes | run_vikram.py:393-396; results store has OK rows only | R | M |
| S14 | `reindex` load failures go to logger only; not returned by `save_results` | results.py:306-311 | R | L |
| S15 | `estimate_transform` has no seed; cv2 USAC/RANSAC determinism unverified | estimate.py:53-98 | R | M for Phase 4.4 |
| S16 | duplicates: LoFTR×2, LightGlue×2, `shadow_mask`×2 (radiometric/shadow), `scale_ratio`×2 (constants:78, pseudo_gt:86), `polygon_to_pixel_window`×2, footprint.py vs overlap.py | §2 | R | L |
| S17 | stale web export (9 vs 13 pairs); stale docs (CONTEXT, HANDOFF, gdocs "431 tests") | §1 | M | L (but panel-facing) |
| S18 | global `~/.claude/CLAUDE.md` = architect role → Opus role confusion | §0 | M | H (process) |
| S19 | mypy `python_version=3.10` vs numpy stubs needing 3.12; no `py.typed` | REPO_TREE §3 | M | L |

## 7. TBD summary → modules → difficulty
Difficulty: S ≤1 prompt · M 2–4 prompts · L ≥5 prompts or needs hardware/data/human.
| TBD | modules touched | real state (vs TBD text) | diff | blocker |
|---|---|---|---|---|
| 1.1 wire `lonlat_to_pixel` into overlap | overlap.py:916-1013, geometry_grid.py:744/914, pseudo_gt.py:209/588, crop callers, tests | on-disk Vikram data has no grid → needs ncp download to validate on real data | M | Q: download ncp? |
| 1.2 region | data only | DONE (Vikram) | — | — |
| 1.3 NAC via `ingest/lro.py` | lro.py (transform override from PDS4 cart fields), run_vikram.py:44-63 | NAC on disk; code path unused; GDAL bug | M | datum/sign (S12) |
| 1.4 IIRS | preprocess/hyperspectral.py, pds4.py | zero cubes; no Vikram IIRS chosen | L | data + human scope |
| 1.5 datum convention | constants.py:16-20, geometry_grid.py, lro.py, run_vikram MOON_GEO | unstated in ISRO label | M (doc research + test) | needs source doc |
| 1.6 self-pair double count | overlap.py:867-874, test_overlap.py | trivial | S | — |
| 1.7 human decisions (SuperGlue licence, PLACEHOLDER params, synthetic vs real, missing angles) | params.py, superglue.py | decisions | — | CLARIFY |
| 1.8 illumination-bridged hybrid | new: DTM render (reuse scenes.hillshade/_cast_shadow_mask), multi-reference match, pooled consensus, cross-matcher agreement check (new eval), native-res tiled refine (needs S8 fix), run_vikram refactor | experiments 1–2 gate it; exp 1 aborted; exp 2 needs SPICE (LRO reference sun azimuth) | L | SPICE access, compute |
| 2.1 CUDA torch | env: driver load (sudo, possibly Secure Boot MOK), `setup.sh --cuda` (cu124) | Max-Q laptop GPU present, driver not loaded | S code / human env | human |
| 2.2 re-measure VRAM consts | device.py:128-143, benchmark.py, memory.py, add `benchmark` CLI | needs 2.1 | M | 2.1 |
| 2.3 e2e GPU run with timings | pipeline.py (timing + peak VRAM fields in `extra`), run_vikram | needs 2.1 | S–M | 2.1 |
| 3.1 GPU worker | new `lunar_reg/distributed/worker.py` | none exists | M | 2.x |
| 3.2 job descriptor | new; must add prior transform + target GSD + preprocessing id (S8), not just windows | design gap vs udocs/70 | M | — |
| 3.3 queue + results dir | new | — | M | 3.1/3.2 |
| 3.4 reducer | stitch.py, estimate/refine, eval | reuse | M | 3.3 |
| 3.5 classified outcomes | new enum; extends RunStatus; fix S7 | — | M | 3.3 |
| 4.1 broker | Ray vs Redis undecided | — | M | Q |
| 4.2 storage/locality | windowed reads over network | — | L | multi-machine availability |
| 4.3 capacity-aware scheduling | planner | simulate caps | M | 3.x |
| 4.4 determinism | estimate.py seed (S15), reducer sort | — | M | — |
| 4.5 at-least-once | results writer | verify only | S | — |
| 5.x dashboard cluster panel | Dashboard.jsx, app.py, export_web_data.py | optional | S–M | decision |

## 8. Design implications noted for Task B
- Nothing in TBD phases 2–4 can be **measured** on this machine until a human loads the NVIDIA driver. Harnesses for P2–P4 must run on CPU with simulated workers/VRAM caps and mark GPU-only checks `gpu`-marked + SKIP-with-reason, never PASS.
- Phase-3 job descriptor must carry: source window, reference window, source→reference prior (3×3), working GSD, preprocessing config id, matcher, precision, tile_px, est_vram_bytes, seed. udocs/70 descriptor (windows only) is insufficient because of S8.
- Fix S1/S2/S3/S7/S13 before any benchmark that reports inlier ratio or affine results; they change stored numbers.
- Benchmark ground truth options: synthetic (`eval/scenes.py`, truth known), real pairs (no truth → only cross-matcher pre-ECC agreement + bootstrap conditioning), Vikram 2024 strip as regression anchor (label offset 2939 m, SIFT–LightGlue pre-ECC corner agreement 2.2 m — D, from vikram README).
- Harness/benchmark protection needs `.claude/settings.json` deny + hook, and root CLAUDE.md must become the Opus-facing file; architect role must move out of `~/.claude/CLAUDE.md` and project CLAUDE.md (see CLARIFY Q-process).

## 9. Session A2 (2026-09-29) — CLARIFY round-1 answers + new facts
| fact | tag |
|---|---|
| Ubuntu 24.04.5, running kernel 7.0.0-34; Secure Boot **disabled** (no MOK needed) | M |
| Installed `nvidia-driver-580-open` 580.126.09, but kernel modules exist only for 6.17.0-20 → root cause of "driver not loaded". Fix: `apt install --only-upgrade linux-modules-nvidia-580-open-generic-hwe-24.04` (candidate 7.0.0-34.34~24.04.1+1) | M (dpkg/apt-cache) |
| `scripts/setup.sh --cuda` hard-codes the cu124 wheel index; whether torch 2.14 has cu124 wheels is UNVERIFIED → pick the index from pytorch.org, ≤ the CUDA version the `nvidia-smi` header reports | R + I |
| Second host exists: RTX 3060 6 GB (user, CLARIFY Q4). OS/LAN unknown (R3) | D (user) |
| Deadline: Phase 1+2 pipeline "today", YouTube demo video recorded 2026-09-30 | D (user Q15) |
| User scope changes: IIRS + TMC-2 in scope with skip-if-absent; SuperGlue allowed with a licence disclaimer; Phase 5 dropped; no deny rules, bypassPermissions stays; Opus may edit all docs; delete dead/duplicate files | D (user) |
| On a sphere (flattening 0, constants.py:17), planetocentric latitude == planetographic latitude → the datum question reduces to radius + longitude direction/range | I (standard geometry; no project run) |
| Review chain: Opus implements → Fable reviews → external models (GPT/Gemini/opencode) review → consolidated report → human merge/redo | D (user Q21) |
| Driver now live: `nvidia-smi` → RTX 4060 Laptop GPU, driver 580.178.04, CUDA 13.0, 8188 MiB total, **754 MiB already used by the desktop** (≈7.4 GiB free at idle) | M |
| torch 2.14.0 wheels for cp312 exist on download.pytorch.org for **cu130** and cu126 (not cu129/cu128). Only `torch` needs replacing (no torchvision/torchaudio installed). `setup.sh --cuda` (cu124) is stale → fix to cu130 in Phase 2 | M (curl index) |
| torch 2.14.0+cu130 installed in `.venv`; `torch.cuda.is_available()` True; kornia still imports. Phase 2 prerequisite (TBD 2.1) DONE 2026-09-29 | M |
| Role split done: architect instructions in `.fable/ARCHITECT.md`; launch Fable with `claude -n FABLE --append-system-prompt-file .fable/ARCHITECT.md` (flag confirmed in `claude --help`). Root `CLAUDE.md` = implementer stub, to be completed in Task B | M |
| CLARIFY still open: R2 (ISRO OHRC SIS PDF), R3b (3060 host details) | — |

## 10. Session B1 (2026-09-29) — Task B progress + audit outcomes
Resume point: `PLAN_PROGRESS.md` (RESUME NEEDED). Written: HLD.md, DECISIONS.md (G01–G29), PHASES.md (62 prompts, file-ownership §3), CLAUDE.md (implementer), STATUS.md. Not written: AUDIT.md, CONTRACTS.md, all Phase_* folders.
Audit workflow output (6 subsystem auditors + adversarial verify + 2 research agents): `.fable/audit_20260929.json` (full), `.fable/module_facts_20260929.txt` (exact signatures per subsystem, for CONTRACTS/LLD), `.fable/research_20260929.json` (validated ODE/PDS/JAXA/PRADAN URLs, Redis/fakeredis/torch API facts — not yet read by me).

| new fact | tag |
|---|---|
| S12 partly refuted: corrected NAC transform matches the label's own cart bounds to ≤~2 m in x, ≤~7 m in y; label W/E bounds are top-edge corner longitudes. UL-x flip consistent with label; absolute accuracy vs terrain still unestablished. Replace "~1 km" wording. | M (auditor) |
| NEW-match-1 (H): learned.LightGlueMatcher crashes on every CUDA call (autocast fp16 into kornia LightGlue fp32 posenc) → every lightglue row MATCHER_ERROR, coarse pass always falls back. GPU now live, so this is live. | M |
| NEW-match-2 (H): canonical learned.LoFTRMatcher does not pad to /8 → 3.04 px median error vs 0.17 px; duplicate loftr.py pads. Dedup must MERGE padding in, not just delete loftr.py. superglue.py LightGlue lacks /16 padding. | M |
| NEW-ingest-1 (H): pds4._resolve returns LAST match (reverse DFS) → DTM label file_name → .LBL; 2 Observing_System_Component → second; corners from Refined not System_Level. | M |
| NEW-ingest-2 (H): LRO PDS4 rows get lines/samples/min_lat None → footprint never resolved. NEW-ingest-3 (H): geometry_grid.polygon_to_pixel_window ignores interior nodes → wrong/None window. | M |
| NEW-pipeline_results-3 (H): fetch_catalogue writes ring vertices as corner1..4 → all 21 catalogue rows are bow-ties. | M |
| S1 confirmed in store: 9/13 rows model=affine with non-zero perspective row. S2 confirmed (m_inlier_ratio 1.0 on 6/13). | M |
| 9 JAXA/WAC results have NO producing script in repo (NEW-pipeline_results-12) → P1.14 needs `scripts/run_jaxa.py` or mark legacy. | M |
| Preprocess not safe to wire as-is: no nodata handling (NEW-preprocess-1), geometric steps return no pixel transform (-2, H), source-centric GSD from nominal SENSORS (-3). | M |
| Others: refine_full ValueError uncaught (NEW-align-1); min_inliers not re-checked after refit (align-2); ECC mutates caller float32 arrays (align-3); ECC accepted without displacement gate (align-4); is_subpixel is self-residual (eval-1); pair_id unsanitised path (pr-9); reindex can overwrite good index with 0 rows (pr-7); thumbnail ref scale ignored in viewers (pr-1); save_pair silently overwrites (pr-2); free_vram_bytes wrong for 'cuda:0' (match-3); benchmark RLIMIT_AS breaks torch import on CUDA (match-6); RIFT2 not rotation-invariant (match-8). | R/M |

Planned plan changes (apply when resuming):
- Phase 0 additions (critical/high, independent of later components): NEW-match-1, NEW-match-2 (merge padding during P0.02 dedup), NEW-ingest-1, NEW-pipeline_results-3, NEW-align-1/2/3/4 (with P0.06/P0.07), NEW-eval-1 + pr-9 + pr-7 + pr-2 + pr-11 (with P0.08 schema v2). Expect Phase 0 ≈ 13 prompts.
- Phase 1: P1.04 absorbs NEW-ingest-2; P1.05 absorbs NEW-ingest-3, S5, S6, ingest-11 (grid suffix `*_g_grd_*.csv`); split P1.07 into (a) preprocess nodata mask + pixel_transform + reference-side GSD, (b) presets in register_pair; P1.14 adds `scripts/run_jaxa.py`; P1.17 absorbs pr-1, pr-16, pr-21.
- Phase 2: match-3/5/6/7/11/12, S7, S8, S9, align-6/7.
- Phase 1B: eval-7 (shadow steps), match-8/16 (RIFT2).

## 11. Session B2 (2026-09-29) — revised plan (apply to PHASES.md/HLD/DECISIONS on resume)
AUDIT.md written; its `prompt` column uses the numbering below (binding). PHASES.md still shows the OLD 62-prompt numbering → rewrite §1/§3 to this list first.
- P0 (13): 00 preflight · 01 test runner+CI (S10,S19,tooling-2/5/15; move _pds4_label to conftest) · 02 learned matchers merge (loftr.py −, superglue LightGlue −, match-1/2/9/10/14/15) · 03 dedupe shadow_mask/scale_ratio · 04 remove footprint.py (moon_datum→constants) + default.yaml · 05 PDS4 resolver doc-order (ingest-1/14/20) · 06 fetch_catalogue corners (pr-3) · 07 provenance enum + seeded fit + float64 origin (S15, align-7/8) · 08 ECC model fidelity + no mutation + displacement gate + valid mask (S1, align-3/4/5) · 09 counts/refit/classification (S2,S3, align-1/2, pr-10, eval-1, match-19) · 10 results schema v2 (S13,S14, pr-2/7/8/9/11/18) · 11 run_vikram numeric crop geometry + tests (pr-5/6/20, tooling-3) · 12 eval correctness (eval-2..6/8/9, preprocess-6).
- P1 (22 + DL): 00 · DL · 01 downloads manifest · 02 public fetch · 03 catalog (+manifest ingest-9/10) · 04 NAC georef (S11, ingest-2) · 05 geometry grid fixes (ingest-3/11/16, tooling-16) · 06 overlap wiring + fixes (TBD1.1, S5,S6, ingest-4..8/12/15/18) · 07 datum · 08 nodata/NaN radiometric+shadow (preprocess-1/12/13) · 09 preprocess pipeline geometry+StepStatus (preprocess-2..5/7/9, ingest-13) · 10 presets in register_pair (S4) · 11 sun geometry · 12 agreement · 13 pairs.py · 14 SuperGlue opt-in (match-20) · 15 TMC-2/IIRS (ingest-19, preprocess-10) · 16 site runner (pr-13/14/15/21) · 17 run_jaxa.py + cli register/inspect (pr-4/12/19, match-13, tooling-1) · 18 RUN re-run v2 + ablation · 19 apply default · 20 RUN 2023 diagnosis + gate · 21 viewers + docs (pr-1/16/17/22, S17, tooling-4/11..14, ingest-17, preprocess-8).
- P2 (12): 00 · 01 CUDA env + free_memory_bytes (match-3, tooling-7) · 02 device profiles (match-4) · 03 benchmark CLI (match-6/7) · 04 RUN measure profile · 05 device/timing/VRAM/OOM (match-5) · 06 prior tiling + tile outcomes (S7,S8,S9, match-11/18) · 07 classical caps + RIFT2 memory guard (match-12/17, preprocess-11) · 08 native refine · 09 warp georef (align-6/9) · 10 runner GPU+native · 11 RUN GPU e2e + VRAM doc (tooling-10).
- P1B (7): 00 gate · 01 DTM renderer (eval-7) · 02 rendered reference prep · 03 pooled consensus · 04 RIFT2 fixes (match-8/16) · 05 runner bridge · 06 RUN.
- P3 (10) unchanged; P4 (7) unchanged, P4.04 absorbs tooling-6/8. Total 72.
Decision changes (add to DECISIONS): G14 revised — NAC EDR/CDR/ortho labels carry NO sun geometry (research M); reference sun azimuth = fit of DTM hillshade to NAC ortho over azimuth 0–359° (ValueSource.INFERRED), elevation = 90 − ODE incidence (DOCUMENTED; ODE metadata incidence 73.8/74.7 for the two epochs); no SPICE. G30 phase-0 scope rule (text in AUDIT header). G31 redis-py pinned protocol=2; XAUTOCLAIM reply len 2 or 3; redis+fakeredis in `cluster` extra; redis-server not installed (apt 7.0.15, human sudo). G32 JAXA TC ortho: TCO_MAP_02_S66E030S69E033SC + S69E030S72E033SC from DARTS (VALIDATED, no range reads, 288 MB each, pace ≥30 s); DTM/morning/evening tiles DOCUMENTED only. ODE productid form `nac.m1442997156le` (lowercase). NAC 3M orthos/CONF available in SDNDTM, not needed.
Next steps on resume: rewrite PHASES.md → update HLD component list (K-ids for sun fit in K11) → DECISIONS G14/G30–G32 + reorder G27 → CONTRACTS.md → Phase_0 folder.

## 12. Session B3 (2026-09-29) — Task B completed
Written: CONTRACTS.md (C01–C27), PHASES.md rewritten (73 prompts), DECISIONS G30–G35 (+ G14 revised, G27 reordered), all six Phase folders (prompts, LLDs, skills, harness with MANIFEST, verify, benchmark, docs). Consistency pass in `PLAN_PROGRESS.md`.
| new fact / decision | tag |
|---|---|
| NAC ul-x sign rule (fit raster boundary to cart bounds): flipped 935 m vs as-written 23.9 km residual; DTM GeoTIFF origin −11046/638262 at 3 m in the same projection | M |
| ISSDC polar catalogue layers store `UL_LAT…` properties in projected metres, not degrees → P0.06 uses the ring (WKT), never those properties | M |
| ISSDC ring order is UL, UR, BR, BL → the old corner1..4 writer made bow-ties (A004 confirmed) | M |
| Real OHRC label lists Observing_System_Component spacecraft first, camera second → P0.05 adds predicate paths `Name[child=value]` | R |
| LoFTR on a 250×330 crop: median error 2.0 px unpadded, 0.31 px padded to /8 (architect check, not a benchmark) | M |
| Prior-rectified tiling prototype (scale 0.8, rot 15°, prior +3 px, SIFT, 256 px tiles): 604 raw matches, median 0.10 px | M |
| cv2.resize is centre-aligned → every resampling matrix uses `to_native = [[fx,0,x0+(fx−1)/2],[0,fy,y0+(fy−1)/2]]` (C11) | I (standard geometry; used in tests) |
| ODE `results=m` box query is the VALIDATED source of `Incidence_angle`; per-product `fmp` returns file lists | M (research) |
| Uniformity with log(g²) normalisation made U ≥ 0.7 unreachable for < 45 points → G33 min(n, g²) | I (arithmetic) |
| 1B skip = one-commit branch + human tag, so the STATUS/branch flow never loops | design |
Open: R2 (SIS PDFs), R3b (second host). Next session (FABLE review role): review Phase 0 once `phase-0-done` exists.

## 13. Session D (2026-09-30) — external review adjudicated
`REVIEW_DECISIONS_PLAN.md`: 38 items, 23 ACCEPT, 13 ACCEPT_MODIFIED, 2 REJECT (RC31 native upsampling, RC32 Ray), 0 NEEDS_HUMAN. New decisions G36–G39; G14, G33 revised.
Patterns the reviewer caught that my own B3 consistency pass missed (check these explicitly in future plan passes):
| pattern | instance | check to add |
|---|---|---|
| Fixture values that make a bug invisible | zero window offsets hid a double-added offset (RC13) | every coordinate test uses non-zero offsets and non-unit scales |
| Prose that "calls" a matrix or composes an offset twice | `to_native_tile(p) + (col_off, row_off)` (RC02/16) | write coordinate lifts as `h(M, p)` with the frame of every matrix named |
| A loop whose exit condition depends on processes that can die | `run_local`, P4 status poll (RC01/06) | every wait loop names its no-progress exit and the classified outcome |
| Queue operations that re-insert to skip | Redis `max_bytes` skip (RC04) | routing never re-adds; unfit work is reported unschedulable at plan time |
| Benchmarks that pass on absence | missing run records, skipped data tests, substring verdicts, zero OOMs with zero OKs (RC12/22/27/35/36) | every score requires the artefact to exist and a positive count of the thing measured |
| Launch commands missing the paths the callee needs | `cluster_up.sh` worker line (RC03/05/25) | trace each CLI flag the callee requires back to a config key |
| Contract text disagreeing with its own harness | C02 member timing (RC08), C21 consumers (RC19) | diff CONTRACTS comments against `test_contracts_*` after edits |
| Treating a heuristic fit as primary when an exact computation is available | sun azimuth via NCC fit (RC17) | ask "is there a deterministic source?" before designing a fit |
Measured this session (M): cv2 4.14 `findTransformECCWithMask` masked affine ECC error 0.022 px; adaptive uniformity spread 0.946 vs quadrant 0.336; NAIF LSK/PCK/DE440s URLs HTTP 200; spiceypy 8.2.0 on PyPI; fakeredis `XCLAIM … JUSTID` with min-idle 0 takes an entry back from another consumer (→ renew checks `XPENDING` owner first).

## 14. 2026-10-01 — P1.DL disk overrun resolved
P1.DL added 47.3 GB under `data/raw/` against the 20 GB budget of CLARIFY Q17 (implementer's report: `.fable/inbox_P1DL_20260930.md`). The human raised the budget to 60 GB and kept everything, then doubled it to 120 GB the same day. Architect measurement (M): `du -sb data/raw` = 56 849 815 846 B. A decimated nearest read (`f = 87`, 479 × 2030) of the 14.7 GB TMC-2 derived ortho took 16.1 s with 234 MiB peak RSS, so the G40 probe is feasible inside the RAM budget.
Pattern: a download procedure needs a running total compared with the budget, not only a free-space check; per-row pick limits need an explicit human override step. Now in downloads LLD §3 step 1.
