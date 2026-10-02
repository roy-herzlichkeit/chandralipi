# PHASES — plan of record

Order (G01): **0 → 1 → 2 → 1B → 3 → 4**. Each phase ends at a human review gate (tag `phase-<i>-approved`, G29). Contract IDs → `CONTRACTS.md`. Defect IDs (A###) → `AUDIT.md`. The file-ownership table (§3) is binding: a prompt may create, modify or delete only the files listed for it, plus new test files `tests/test_*.py`.

## 1. Summary

| phase | goal | TBDs | components (HLD) | prompts | depends on | contracts produced | contracts consumed | benchmark focus |
|---|---|---|---|---|---|---|---|---|
| 0 | Green reproducible baseline; fix every defect that changes stored numbers; freeze results schema v2 | 1.7 (dead code), 4.4 (seed) | K1–K4 | 13 (P0.00–P0.12) | — | C01–C07, C15 | — | suite green; count and ratio semantics on synthetic pairs with injected outliers; ECC model fidelity; determinism |
| 1 | Real Chandrayaan-2 pipeline: downloads, catalog, NAC georeference, geometry grid, datum, preprocessing presets, sun geometry, agreement, SuperGlue, TMC-2/IIRS skip-if-absent, v2 re-run, 2023 diagnosis | 1.1, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8 exp-1/exp-2 | K5–K13, K20 | 26 (P1.00–P1.24 + P1.DL) | 0 | C08–C14, C20, C28 | C01–C07, C15 | 2024 anchor registers (≥ 20 inliers, U ≥ 0.7, agreement < 1 px); every 2023 failure classified and diagnosed; SYNTHETIC axis separate |
| 2 | GPU integration: CUDA env, measured device profile, benchmark CLI, device/timing/VRAM/OOM in results, prior-driven tiling, native-GSD refinement, georeferenced warp, GPU end-to-end run | 2.1, 2.2, 2.3, 1.8 step 6 | K14–K16 | 12 (P2.00–P2.11) | 1 | C16–C19 | C01–C15 | measured VRAM profile; zero unclassified tile failures; native refinement within 1 coarse px of the 4 m transform |
| 1B | Illumination bridge (gated by C20): DTM shaded-relief reference, pooled multi-matcher consensus, RIFT2 fixes and baseline | 1.8 steps 2–5, exp-3/4 | K17 | 7 (P1B.00–P1B.06) | 1, 2 | C21 | C04, C10–C14, C18–C20 | 2023 strips against the TBD 1.8 targets |
| 3 | Single-host distributed: job descriptor, outcomes, planner, local queue, workers, reducer, fault injection, determinism | 3.1–3.5, 4.4 | K18 | 10 (P3.00–P3.09) | 2, 1B (built or skipped) | C22–C26 | C01–C06, C11, C15–C19 | 100 % correct classification under injected faults; reducer ≡ single-process within tolerance; order-independent transform |
| 4 | Two hosts: Redis Streams transport, node cache, capacity routing, host config + runbook, idempotence, two-host run | 4.1–4.5 | K19 | 7 (P4.00–P4.06) | 3 | C27 | C15, C16, C22–C26 | WORKER_LOST reclaimed and counted; duplicate job → one result; bytes read per strip reported; heterogeneous fleet without OOM |

Total prompts: **75** (13 + 26 + 12 + 7 + 10 + 7). P1.DL is out of sequence and never "next" in STATUS.

## 2. Phase gates and special prompts

| item | rule |
|---|---|
| review gate | After the last prompt of phase i, Opus runs §Phase end of `CLAUDE.md` and stops. Phase i+1's `.00` preflight fails unless tag `phase-<i>-approved` exists. 1B needs `phase-2-approved`. Phase 3 needs `phase-1B-approved` (given after a built 1B, or after the one-commit skip branch of G02). |
| P1.DL | Out-of-sequence, human-in-the-loop download session (G12). Runs at any time once `Phase_1/` exists, including before Phase 0 is approved. Writes only `data/raw/**` and `data/raw/DOWNLOADS.json`; never changes `STATUS.md` or git. |
| RUN prompts | P1.18, P1.19, P1.20, P2.04, P2.11, P1B.06, P3.09, P4.06 execute pipelines on real data (G22). Their checks validate `run_record.json` (C15) and artefacts, never wall-clock. |
| GPU prompts | P2.04, P2.11, P3.09, P4.06 need CUDA. If `torch.cuda.is_available()` is False they write a BLOCKER and stop. |
| data prompts | P1.18, P1.19 and P1.20 need the 4 OHRC `nrp` strips + NAC ortho + NAC DTM on disk (present 2026-09-29). Missing IIRS / TMC-2 / OHRC `ncp` never blocks (G24); tests needing them are `@pytest.mark.data` and skip with a reason. |
| network | Only P1.DL, the P1.02 run step, P1.11's `pip install` of the `spice` extra, P4.00's host probe (LAN), P4.01's `pip install` of the `cluster` extra, and P4.06 (LAN between the hosts) touch a network. |

## 3. Prompt list and file ownership

`+` creates, `~` modifies, `−` deletes. Audit IDs closed by the prompt are in `AUDIT.md` (column `prompt`).

### Phase 0
| id | title | files |
|---|---|---|
| P0.00 | preflight | STATUS.md ~ |
| P0.01 | test runner + CI baseline | pyproject.toml ~, scripts/ci.sh +, .github/workflows/ci.yml +, scripts/untar_data.py +, scripts/setup.sh ~ |
| P0.02 | learned matchers merge | src/lunar_reg/match/learned.py ~, src/lunar_reg/match/loftr.py −, src/lunar_reg/match/superglue.py ~, src/lunar_reg/match/__init__.py ~, src/lunar_reg/match/classical.py ~, src/lunar_reg/match/stitch.py ~ (docstring only) |
| P0.03 | dedupe shadow_mask and scale_ratio | src/lunar_reg/preprocess/radiometric.py ~, src/lunar_reg/preprocess/__init__.py ~, src/lunar_reg/constants.py ~, src/lunar_reg/ingest/pseudo_gt.py ~ |
| P0.04 | remove footprint.py and default.yaml | src/lunar_reg/ingest/footprint.py −, tests/test_footprint.py −, src/lunar_reg/ingest/__init__.py ~, src/lunar_reg/ingest/overlap.py ~ (import only), src/lunar_reg/constants.py ~, configs/default.yaml −, pyproject.toml ~, README.md ~ |
| P0.05 | PDS4 resolver document order | src/lunar_reg/ingest/pds4.py ~, src/lunar_reg/ingest/fieldmap.py ~ (`instrument` and corner paths only), src/lunar_reg/ingest/lro.py ~ (image-path containment only), src/lunar_reg/ingest/manifest.py ~ (`unresolved_fields` text only) |
| P0.06 | catalogue footprints as polygons | scripts/fetch_catalogue.py ~, src/lunar_reg/ingest/overlap.py ~ (`footprint_from_row` only) |
| P0.07 | provenance enum, run record, seeded fit | src/lunar_reg/provenance.py +, src/lunar_reg/runrecord.py +, src/lunar_reg/align/estimate.py ~ |
| P0.08 | ECC model fidelity, no mutation, gate, mask | src/lunar_reg/align/refine.py ~ |
| P0.09 | counts, refit threshold, classification | src/lunar_reg/pipeline.py ~, src/lunar_reg/eval/metrics.py ~, src/lunar_reg/match/classical.py ~, src/lunar_reg/match/rift2/matcher.py ~ (empty_reason only) |
| P0.10 | results schema v2 + persisted failures | src/lunar_reg/results.py ~, src/lunar_reg/pipeline.py ~ (`run_batch`, `register_pair` PairResult construction), scripts/reindex_results.py ~, scripts/run_vikram.py ~ (`save_results` call site only), scripts/build_demo_results.py ~ (`save_results` call site only) |
| P0.11 | run_vikram numeric crop geometry | scripts/run_vikram.py ~ |
| P0.12 | eval correctness | src/lunar_reg/eval/error_budget.py ~, src/lunar_reg/eval/conditioning.py ~, src/lunar_reg/eval/uniformity.py ~ |

### Phase 1
| id | title | files |
|---|---|---|
| P1.00 | preflight | STATUS.md ~ |
| P1.DL | download session (out of sequence) | data/raw/** +, data/raw/DOWNLOADS.json + |
| P1.01 | downloads manifest + verifier | src/lunar_reg/ingest/downloads.py +, scripts/verify_downloads.py + |
| P1.02 | public fetch script (+ run step) | scripts/fetch_public.py +, data/raw/** + (run step) |
| P1.03 | product catalog + scan diagnostics | src/lunar_reg/ingest/catalog.py +, src/lunar_reg/ingest/manifest.py ~, src/lunar_reg/cli.py ~ (`catalog` subcommand only) |
| P1.04 | NAC georeference from label | src/lunar_reg/ingest/lro.py ~ |
| P1.05 | geometry grid fixes | src/lunar_reg/ingest/geometry_grid.py ~, tests/test_geometry_grid.py ~ |
| P1.06 | overlap: grid wiring + fixes | src/lunar_reg/ingest/overlap.py ~, src/lunar_reg/ingest/pseudo_gt.py ~ |
| P1.07 | datum convention + data test | src/lunar_reg/constants.py ~, docs/DATUM.md + |
| P1.08 | nodata in radiometric + shadow | src/lunar_reg/preprocess/radiometric.py ~, src/lunar_reg/preprocess/shadow.py ~ |
| P1.09 | preprocess geometry + StepStatus | src/lunar_reg/preprocess/pipeline.py ~, src/lunar_reg/preprocess/resample.py ~, src/lunar_reg/preprocess/georeference.py ~, src/lunar_reg/constants.py ~ |
| P1.10 | presets inside register_pair | src/lunar_reg/preprocess/presets.py +, src/lunar_reg/pipeline.py ~ |
| P1.11 | reference sun geometry (SPICE + cross-checks) | src/lunar_reg/ingest/sun.py +, scripts/fit_reference_sun.py +, pyproject.toml ~ (`spice` extra) |
| P1.12 | cross-matcher agreement | src/lunar_reg/eval/agreement.py + |
| P1.13 | window-pair preparation | src/lunar_reg/pairs.py + |
| P1.14 | matcher registry + SuperGlue opt-in | src/lunar_reg/match/superglue.py ~, src/lunar_reg/match/__init__.py ~, src/lunar_reg/pipeline.py ~ (`_build_matcher` only) |
| P1.15 | TMC-2 + IIRS skip-if-absent | src/lunar_reg/ingest/pds4.py ~, src/lunar_reg/ingest/fieldmap.py ~ (append-only, probed fields only), src/lunar_reg/preprocess/hyperspectral.py ~, src/lunar_reg/preprocess/pipeline.py ~, docs/probes/*.txt + |
| P1.16 | site runner | src/lunar_reg/sites/__init__.py +, src/lunar_reg/sites/runner.py +, scripts/run_vikram.py ~ |
| P1.17 | run_jaxa, ablation driver, cli register/inspect | scripts/run_jaxa.py +, scripts/run_ablation.py +, src/lunar_reg/cli.py ~ |
| P1.24 | cross-instrument pairs at any site (G41; runs before P1.18) | configs/references.json +, src/lunar_reg/cross.py +, src/lunar_reg/ingest/lro.py ~, src/lunar_reg/pairs.py ~, src/lunar_reg/sites/runner.py ~, scripts/run_cross.py +, tests/test_cross_pairs.py + |
| P1.18 | RUN: archive v1, re-run v2, preset ablation | data/processed/** (artefacts only) |
| P1.19 | RUN: apply preset default + anchor into live store | src/lunar_reg/pipeline.py ~, docs/PREPROCESS_ABLATION.md +, data/processed/** (artefacts only) |
| P1.20 | RUN: 2023 diagnosis + exp-1 gate | data/processed/vikram/** +, docs/VIKRAM_2023_DIAGNOSIS.md + |
| P1.21 | viewers | scripts/export_web_data.py ~, dashboard/app.py ~, src/lunar_reg/viz/figures.py ~, scripts/reindex_results.py ~, scripts/demo.py ~ |
| P1.22 | docs + status refresh | README.md ~, CONTEXT.md ~, CONTEXT_HANDOFF.md ~, docs/results/ + |
| P1.23 | code docstrings + script hints | scripts/setup.sh ~, scripts/up.sh ~, scripts/run_dashboard.sh ~, .gitignore ~, src/lunar_reg/ingest/__init__.py ~, src/lunar_reg/ingest/fieldmap.py ~, src/lunar_reg/ingest/manifest.py ~, src/lunar_reg/preprocess/config.py ~ (docstrings/comments only) |

### Phase 2
| id | title | files |
|---|---|---|
| P2.00 | preflight (CUDA live) | STATUS.md ~ |
| P2.01 | CUDA setup + free memory | scripts/setup.sh ~, src/lunar_reg/device.py ~, README.md ~, scripts/README.md ~ |
| P2.02 | device profiles | src/lunar_reg/device.py ~, configs/device_profiles/README.md + |
| P2.03 | benchmark CLI | src/lunar_reg/cli.py ~, src/lunar_reg/match/benchmark.py ~, src/lunar_reg/match/memory.py ~ |
| P2.04 | RUN (gpu): measure RTX 4060 profile | configs/device_profiles/rtx4060-laptop.json +, data/processed/benchmarks/** + |
| P2.05 | device, timing, VRAM, OOM in register_pair | src/lunar_reg/pipeline.py ~, src/lunar_reg/match/learned.py ~ |
| P2.06 | prior-driven tiling + tile outcomes | src/lunar_reg/match/tiled.py ~, src/lunar_reg/match/stitch.py ~, src/lunar_reg/match/learned.py ~ |
| P2.07 | classical caps + RIFT2 memory guard | src/lunar_reg/match/classical.py ~, src/lunar_reg/match/rift2/matcher.py ~, src/lunar_reg/preprocess/radiometric.py ~ |
| P2.08 | native-GSD refinement | src/lunar_reg/align/native.py + |
| P2.09 | georeferenced blockwise warp | src/lunar_reg/align/warp.py ~ |
| P2.10 | site runner: GPU + native mode | src/lunar_reg/sites/runner.py ~, scripts/run_vikram.py ~ |
| P2.11 | RUN (gpu): end-to-end GPU run | data/processed/gpu_run/** +, docs/GPU_RUN.md +, docs/VRAM_CONSTRAINTS.md ~ |

### Phase 1B
| id | title | files |
|---|---|---|
| P1B.00 | preflight + exp-1 gate | STATUS.md ~, Phase_1B/SKIPPED.md + (only when the gate says SKIP_1B) |
| P1B.01 | DTM shaded-relief renderer | src/lunar_reg/eval/render.py +, src/lunar_reg/eval/scenes.py ~ |
| P1B.02 | rendered reference preparation | src/lunar_reg/pairs.py ~ |
| P1B.03 | pooled multi-matcher consensus | src/lunar_reg/consensus.py + |
| P1B.04 | RIFT2 fixes | src/lunar_reg/match/rift2/mim.py ~, src/lunar_reg/match/rift2/descriptor.py ~, src/lunar_reg/match/rift2/matcher.py ~ |
| P1B.05 | site runner: bridge mode | src/lunar_reg/sites/runner.py ~, scripts/run_vikram.py ~ (bridge flags only) |
| P1B.06 | RUN: bridge on 2023 strips + RIFT2 baseline | data/processed/bridge/** +, docs/ILLUMINATION_BRIDGE.md + |

### Phase 3
| id | title | files |
|---|---|---|
| P3.00 | preflight | STATUS.md ~ |
| P3.01 | job descriptor | src/lunar_reg/distributed/__init__.py +, src/lunar_reg/distributed/job.py + |
| P3.02 | job outcomes + result files | src/lunar_reg/distributed/outcome.py + |
| P3.03 | planner | src/lunar_reg/distributed/planner.py + |
| P3.04 | queue protocol + local queue | src/lunar_reg/distributed/queue.py + |
| P3.05 | worker | src/lunar_reg/distributed/worker.py + |
| P3.06 | reducer | src/lunar_reg/distributed/reducer.py + |
| P3.07 | local runner + CLI | src/lunar_reg/distributed/runner.py +, src/lunar_reg/cli.py ~ (`distributed` subcommand only) |
| P3.08 | fault injection + determinism | src/lunar_reg/distributed/faults.py + |
| P3.09 | RUN (gpu): single-host distributed run | data/processed/distributed/** +, docs/DISTRIBUTED_RUN.md + |

### Phase 4
| id | title | files |
|---|---|---|
| P4.00 | preflight (hosts + redis) | STATUS.md ~ |
| P4.01 | Redis Streams queue | src/lunar_reg/distributed/redis_queue.py +, pyproject.toml ~ |
| P4.02 | node-local cache + byte accounting | src/lunar_reg/distributed/cache.py +, src/lunar_reg/distributed/worker.py ~ |
| P4.03 | capacity-aware routing | src/lunar_reg/distributed/scheduler.py +, src/lunar_reg/distributed/planner.py ~ |
| P4.04 | host config + runbook + distributed CLI | configs/hosts.example.json +, scripts/cluster_up.sh +, docs/RUNBOOK_MULTIHOST.md +, src/lunar_reg/cli.py ~ (`distributed` subcommand only), scripts/pack_data.sh ~, scripts/README.md ~, scripts/setup.sh ~ |
| P4.05 | cross-worker determinism + idempotence | src/lunar_reg/distributed/reducer.py ~, src/lunar_reg/distributed/outcome.py ~ |
| P4.06 | RUN (gpu, 2 hosts): two-host run | data/processed/multihost/** +, docs/MULTIHOST_RUN.md + |

## 4. TBD → phase map

| TBD | phase / prompt |
|---|---|
| 1.1 geometry grid | P1.05 (grid fixes), P1.06 (wiring into overlap) |
| 1.2 region | done (Vikram, G27); P1.DL fetches the calibrated counterparts |
| 1.3 NAC via lro.py | P1.04 (georeference), P1.13 (used by pair preparation), P1.16 (runner) |
| 1.4 IIRS | P1.15 (skip-if-absent ingest), P1.DL (download) |
| 1.5 datum | P1.07 |
| 1.6 self-pair double count | P1.06 |
| 1.7 decisions | SuperGlue → P1.14; PLACEHOLDER params → P1.18/P1.19 (measured preset choice); synthetic vs real → P1.21/P1.22/P1.23 (real results lead, synthetic labelled); missing angles → P1.15 (reported as UNVERIFIED) |
| 1.8 hybrid | exp-1 → P1.20; exp-2 → P1.11 + P1.20; step 1 prior → P1.06/P1.13; step 5 agreement → P1.12; steps 2–5, exp-3/4 → P1B; step 6 native → P2.08/P2.10 |
| 2.1 CUDA | P2.01 (driver already live, FABLE_NOTES §9) |
| 2.2 VRAM constants | P2.02–P2.04 |
| 2.3 e2e GPU | P2.05, P2.11 |
| 3.1 worker | P3.05 |
| 3.2 job descriptor | P3.01 |
| 3.3 queue + results dir | P3.02, P3.04 |
| 3.4 reducer | P3.06 |
| 3.5 classified outcomes | P3.02, P3.08 |
| 4.1 broker | P4.01 |
| 4.2 storage | P4.02 |
| 4.3 scheduling | P4.03 |
| 4.4 determinism | P0.07 (seed), P3.08, P4.05 |
| 4.5 at-least-once | P3.02 (content-hash names), P4.05 |
| 5.x | dropped (Q6) |
