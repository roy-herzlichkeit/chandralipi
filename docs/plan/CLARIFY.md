# CLARIFY — answers are binding for Task B

Reply per question with `default`, or a replacement. Evidence behind each question: `docs/plan/FABLE_NOTES.md` (section / bug ID in brackets).
Format: `Q<n> | question | YOUR DEFAULT | why | impact if wrong (L/M/H)`

## Scope & priorities

Q1 | Priority order for building phases? | Phase 1 first and must reach DONE before Phase 2 starts. Then 2 → 3 → 4. Phase 5 is dropped (see Q6). All phases are still designed up front. | Phase 1 is the only one that changes what can be claimed about Chandrayaan-2. Phases 2–4 can't be measured without a GPU run, and none has ever happened [§0, §8]. | H
ANSWER: Phase 1 and 2 are of upmost priority. RANSAC can be reduced as per jury since we are UG students. Phase 3 is questionable as a single host in our cluster has only 1 GPU, 4 is necessary but not urgent. Our team has fairly less knowledge regarding CLuster Computing for now. 

Q2 | How to structure TBD 1.8 (the illumination-bridged hybrid)? | Split Phase 1. **1A:** correctness fixes, NAC ingest, geometry-grid wiring, and the two gating experiments (rerun the 2023 strips with the corrected prior; get the reference sun azimuth). **1B:** DTM-rendered reference plus pooled multi-matcher consensus. 1B is built only if 1A exp-1 still fails on the 2023 strips. | Exp-1 was started and aborted after one strip [§5]. Building 1B before exp-1 runs may be solving the wrong problem. | H
ANSWER: SPlit it, it's a risk we have to take.

Q3 | Native-resolution target for Phase 1? | Tiled 0.25 m refinement of the 3 km window only, seeded by the 4 m transform. Full 25 km strips are deferred to Phase 3. | The current tiled path can't pair across GSD or rotation, so it needs a transform-prior redesign [S8]. That is sized for one window, not for a whole-strip run on CPU. | H
ANSWER: Phase 1 and 2 are going to be done together so we do need the GPU, hence we can do those calculations.

Q4 | Phase 4 ("many machines"): real multi-host demo, or several worker processes plus a broker on one host? | Single host, simulated nodes (separate processes, separate cache dirs, broker on localhost). Real multi-host is optional and runs from a documented runbook. | There is no evidence that a second machine is available [§0]. A harness must be runnable on this laptop. | H
ANSWER: Multi host as we have another machine consisting of RTX3060 6GB vRAM available.

Q5 | Are IIRS (TBD 1.4) and TMC-2 in scope for this design cycle? | Out of scope. That code is left untouched; the only work is a docs note that it is deferred. | The TBD 1.2 update already defers both for the demo. No Vikram IIRS or TMC-2 is on disk [§3]. | M
ANSWER: Yes they are in our scope but they are yet to be downloaded. Make the pipeline in such a way, if they are not available we do not do their calculations. The data will be fetched tonight but the data pipeline must be ready.

Q6 | Phase 5 (cluster panel in the dashboards)? | Drop it. The Phase 3/4 report is a printed text plus a JSON file under the run directory. | Optional, and it depends on Phase 3/4 producing real runs. | L
ANSWER: Drop it.

## Tech decisions

Q7 | Fix bugs S1 (ECC forces homography), S2 (raw match count and inlier ratio lost) and S3 (refit threshold is not tightened), then re-run and replace the 13 stored real results? | Yes. Fix them in Phase 1A. Move the current store to `data/processed/results_archive_20260929/` (not deleted). Re-run Vikram + JAXA, and add `schema_version=2` with a `n_raw_matches` field. | These change the stored numbers and the inlier ratio the problem statement asks for. Leaving them in place means every Phase-1 benchmark is built on wrong fields [§6]. | H
ANSWER: Do it then to do what the problem statement asks for.

Q8 | `register_pair` skips `preprocess/`, although README says it applies it. Which way do we resolve that? | Add `PipelineConfig.preprocess: str | None` (preset name, default `None` = today's behaviour), benchmark the presets as an ablation, and correct the README wording. | The default keeps the existing numbers comparable, and the ablation measures whether the Makharia chain actually helps on real data [S4]. | M
ANSWER: Please do the preprocessing and use the first choice but i do need clarification regd this question. What do you mean, expln me with example. If in any question i write i do not understand, please do explain me those, then i will answer.

Q9 | Download the calibrated `ncp` counterparts of the 4 raw Vikram tags (~1.2 GB each, which include `_g_grd_d18.csv`)? | Yes, all 4. A human runs the download; Opus writes the fetch script. Without these, TBD 1.1 (geometry-grid wiring) can't be validated on real data. | The raw `nrp` products have no geometry grid, and the only grid test is skipped [§1, §3]. | H
ANSWER: Okay, the data will be downloaded tonight with an Opus 5.5 probe with access to the logged in page, please do create a session prompt or harness for it as it will also be used to download LRO and JAXA terrain, infrared, high quality data.

Q10 | Where should the LRO reference sun azimuth for NAC M1442997156 (TBD 1.8 exp-2) come from? | Fetch that frame's PDS label via ODE, discover its fields with `probe-label` (no guessed names), and record the value with provenance. SPICE/spiceypy only if the label carries no sun geometry. | A label is small and needs no kernels. SPICE adds a dependency plus a multi-GB kernel set. | M
ANSWER:I do not understand.

Q11 | Which broker for Phase 4? | Redis Streams, using consumer groups and XAUTOCLAIM leases for WORKER_LOST. The job descriptor stays plain JSON. | Fewer moving parts. Lease expiry maps directly onto the required WORKER_LOST outcome, and it can be simulated on one host. Ray hides retries, which works against the classified-outcome rule. | M
ANSWER:I do not understand the pros and cons

Q12 | Datum convention (TBD 1.5) until an ISRO document states it? | Working assumption: planetocentric coordinates on a sphere with R = 1,737,400 m, the same as `constants.py` and the NAC projection. Flag it UNVERIFIED in code, and add a test on one real ncp↔NAC pair that asserts agreement within a tolerance the test prints. | This is the only convention consistent across the code today [§2 constants, run_vikram]. Guessing a different one would not be backed by a document either. | M
ANSWER:Can't we find it? → Round 2: explained; user: "Got it".

Q13 | SuperGlue (noncommercial licence)? | Don't accept it. LightGlue only. `SuperGlueMatcher` stays licence-gated, with no benchmark row. | It can't ship in a submission, and it would not reproduce Makharia's number anyway (D, HANDOFF §2.9). | L
ANSWER: We will use SuperGlue but in demo we will provide the Jury disclaimer of it's license.

## Constraints (perf, hardware, cost, deadlines)

Q14 | Will you load the NVIDIA driver on this laptop (sudo; Secure Boot may need MOK enrolment) before Phase 2? Is the RTX 4060 Max-Q the only GPU for Phases 2–4? | Yes, a human does the driver install. This is the only GPU. Phase 3's "N GPUs" is shown with N=1 real plus CPU workers, and GPU-only checks are marked `gpu` and SKIP with a reason, never PASS. | The card is on the bus but the driver is not loaded [§0]. Opus can't do a driver install. | H
ANSWER: Okay, provide me the procedure in detail, and I will do it.

Q15 | Next hard date (SIH round / submission) and what must be demo-ready by then? | No date is known, so the design is paced by phase. If a date exists, Phase 1A is cut to whatever fits before it. | No deadline appears anywhere in the repo [§0]. | H
ANSWER: Phase 1 and 2 (till GPU run) by today atleast the pipeline. I will record the YT demo video tommorow.

Q16 | Runtime budgets on this laptop (CPU)? | `check_P*.sh` < 30 s each (fixed by CLAUDE.md), `verify.sh` ≤ 15 min, `benchmark/run.sh` ≤ 30 min, peak RAM ≤ 10 GB. | The full pytest run already takes 268 s. LightGlue on CPU costs ~2–3 KB per reference pixel (D, TBD 1.8), so benchmark inputs must be sized to fit. | M
ANSWER: Use as much as possible without crashing the system.

Q17 | May Opus sessions download data or reach the network? What is the extra disk budget? | No network for Opus. Downloads are scripts that Opus writes and a human runs. Extra disk ≤ 20 GB. | The PRADAN sessions use live cookies, and earlier carts overran the disk (D, HANDOFF §1.4). Harnesses must be offline-deterministic. | M
ANSWER: ISRO limits the download to human hands, but it is commendable to do downloads by human hands if Opus provides procedure and names of files to be downloaded from NASA and SELENE (validated paths)
ANSWER (2026-10-01, disk budget revised): the P1.DL session added 47.3 GB under `data/raw/` (implementer `du -sb`, `.fable/inbox_P1DL_20260930.md` §2), exceeding the 20 GB limit. The human chose to **raise the extra-disk budget to 60 GB for `data/raw/` as a whole and keep every download, zips included**. `du -sb data/raw` = 56 849 815 846 B on 2026-10-01 (architect, M).
ANSWER (2026-10-01, later): budget doubled to **120 GB** (120 000 000 000 B) for `data/raw/` as a whole.

## Quality bar & benchmark metrics

Q18 | Phase-1 quality thresholds, and what happens if the 2023 strips never register? | Adopt the TBD 1.8 targets: ≥ 20 inliers, uniformity ≥ 0.7, pre-ECC cross-matcher corner agreement < 1 px at the working GSD. The 2024 strip is the regression anchor. If the 2023 strips still fail, a classified failure with count + sample + diagnostics scores as spec-conformant, not as a quality pass, and the phase can still close. | There is no ground truth on real pairs. Agreement and conditioning are the only independent signals [§4 inv 6]. Failing to register must not become a pass. | H
ANSWER: We need to clarify why they did not register and it will certainly be confirmed after the whole data test

Q19 | Can synthetic truth-based error (eval/scenes.py, azimuth sweep 0/15/30/60°) be a scored benchmark axis? | Yes, as a separate axis labelled SYNTHETIC in `score.json`, never merged with the real-data axes. | It is the only truth-based accuracy available. Invariant 3 needs it kept visibly apart. | M
ANSWER: Separate axis

## Process (Opus autonomy, what the human approves)

Q20 | The architect role is in both `~/.claude/CLAUDE.md` and the project `CLAUDE.md`, so Opus sessions would load "You are the principal architect". How should that be resolved? | You remove it from `~/.claude/CLAUDE.md`. In Task B I move it to `.fable/ARCHITECT.md`, which is loaded explicitly for Fable sessions. Root `CLAUDE.md` becomes the Opus-facing file (rules, §Handoff, protected paths). | CLAUDE.md template requires root CLAUDE.md to carry §Handoff and the benchmark fence for Opus [S18]. | H
ANSWER: It needs to be separated as this session will only be the architect and will be called FABLE.

Q21 | Git workflow and approval points? | Opus works on branch `phase-<i>`, with one commit per prompt only after its `check_*.sh` exits 0. Opus never pushes or merges. The human reviews at phase end with REVIEW_CHECKLIST.md and merges. Any QUESTIONS.md entry pauses that prompt. | This keeps each prompt revertible and gives a single human gate per phase. | H
ANSWER: opus agents will do the work, you will review the work, after that diff model like GPT or Gemini or OPencode based ones will review it and create a overall report for me. which I will read and then ask to merge or redo somethings.

Q22 | How strictly are the harness/benchmark fences enforced? | `.claude/settings.json` deny on Edit/Write/Bash writes to `Phase_*/harness/**` and `Phase_*/benchmark/**`, plus a PreToolUse hook that blocks the same paths. Opus sessions run with `defaultMode: acceptEdits` instead of today's `bypassPermissions`. | I haven't verified whether deny rules hold under bypassPermissions. The hook is the backstop [§0]. | M
ANSWER: Please do remove those rules, they were enforced bby mistake, follow bypass permissions

Q23 | Which docs may Opus edit? | Code, tests, `scripts/README.md`, and status tables in `docs/project/CONTEXT.md` / `docs/project/CONTEXT_HANDOFF.md` / `README.md`, with numbers only from runs. It never edits `gdocs/`, `udocs/`, `docs/REPORT_SECTION.md`, `docs/DEMO_SCRIPT.md`, `[INSERT RESULT]` cells, or `FABLE_*`. | Panel-facing prose is the human's. Stale status tables are the ones that mislead [S17]. | M
ANSWER: Everything.

## Repo issues (fix / keep / ask)

Q24 | The uncommitted changes (CONTEXT, HANDOFF, DEMO_SCRIPT, `export_web_data.py` NaN guard, udocs, `results.json`) plus the untracked `gdocs/`, `docs/project/REPO_TREE.md` and `CLAUDE.md`: what happens to them before Phase 1? | You commit them as a baseline snapshot on `main` before P1.00. `P1.00_preflight` then asserts a clean tree. | The preflight needs a known green baseline. The NaN-guard fix is real code that is currently uncommitted. | M
ANSWER: Yes they must be commited

Q25 | Dead or duplicate code (S16, unused `configs/default.yaml`, no-caller `find_cross_sensor_pairs` / `enforce_uniformity` / `footprint.find_pairs`, the 4 failing tests S10, 60 unformatted files)? | Fix S10 in P1.01. Delete the duplicate LoFTR/LightGlue classes in `match/loftr.py` and `match/superglue.py` (keeping `SuperGlueMatcher`), and `ingest/footprint.py` if no tests depend on it after the move. Delete `configs/default.yaml`. Keep the no-caller library functions (documented features). Run `ruff format` only on files a prompt touches. | This shrinks what Opus has to read without touching validated logic. A whole-repo reformat would bury the real diffs. | L
ANSWER:DELETE DEAD AND DUP FILES.

---

# Round 2 — explanations you asked for, plus follow-ups

Answers from round 1 are recorded and binding. Below: plain explanations for Q8, Q10, Q11, Q12, then follow-up questions (R1–R9). These exist where two answers conflict or leave a gap the design can't fill. Same reply format: `default` or your own answer.

## Explanations

### Q8 — preprocessing: what the choice actually is
**Today.** `register_pair` takes the two images exactly as given and matches them. A library of "cleanup" steps already exists in `preprocess/`, but the registration code never calls it:
- CLAHE: boosts local contrast, so detail inside dark areas becomes visible.
- Shadow suppression: lifts the darkest 5% of pixels.
- Histogram matching: makes both images use a similar brightness range.

**Example.** The 2023 OHRC strip has the sun 8° above the horizon, so long black shadows hide half of each crater. The NAC image has the sun much higher. Raw, the same crater looks like "black crescent on the left" in one image and "grey bowl" in the other, and a matcher sees two different objects. After CLAHE and shadow suppression, both show rim edges more clearly, and the matcher has a better chance. Nobody has measured whether it helps on *real* lunar data. The paper we follow (Makharia et al.) says it helped on theirs.

**The choice you already made ("first choice").** Add a setting `preprocess = <preset name> | none` to each run. That leaves two follow-on options:
- **A.** The default stays `none`, and preprocessing is switched on per run.
- **B.** The default becomes `ohrc_nac` (the paper's recipe), so it is always on unless switched off.

**My recommendation.** Run both on every benchmark pair. Make the default whichever wins on the 2024 anchor strip plus the synthetic lighting sweep, and record the numbers. Since Q7 re-runs everything anyway, nothing old is lost. → confirm as R1 below.

### Q10 — where the LRO picture's sun direction comes from
**Why we need it.** Our leading explanation for the 2023 failures is "the sun lit the ground from opposite sides in the two pictures". The OHRC files record the sun direction. The NAC map we match against does **not**, so right now "opposite lighting" is a guess based on the date.

The NAC map was built from an original NAC photograph with ID `M1442997156`. NASA keeps a small text description file (a "label") for every such photograph. Such labels normally list the sun's position at the moment of capture, but we must read the real file rather than assume which fields it has.

There are two ways to get the value:
- **A. (default)** Download that one label from NASA's ODE search service (Orbital Data Explorer, a public website at Washington University that indexes NASA planetary data). It is a few KB and needs no login. Our `probe-label` tool lists every field in it, and we read the sun azimuth from there.
- **B. (fallback)** SPICE: NASA's toolkit that computes where the spacecraft and sun were at any instant, using "kernel" files. It is exact, but needs a new Python package and gigabytes of kernel files. We use it only if the label turns out to have no sun fields.

Nothing to decide except "OK". → R1 bundles this.

### Q11 — broker: what it is, and Redis Streams vs Ray
**What a broker is.** It is the to-do list shared between machines. The laptop (the "planner") cuts the job into thousands of small tasks, like "match tile 812 of OHRC against tile 812 of NAC". It puts them on the list, and each GPU worker (the RTX 4060 laptop and the RTX 3060 machine) takes one task at a time and writes back the answer. If a worker crashes mid-task, the broker must notice and hand that task to someone else.

**Example.** The 3060 machine loses Wi-Fi while holding task 812. With Redis, task 812 sits "claimed but unfinished". After 60 s our code reclaims it, logs `WORKER_LOST` once, and gives it to the 4060. With Ray, Ray retries it automatically, and unless we wrap it, the report just says "done", not "done after a lost worker".

| | **Redis Streams** (my default) | **Ray** |
|---|---|---|
| what it is | a tiny database server with a built-in shared queue | a full Python framework for running functions across machines |
| setup | run `redis-server` on one machine; both connect by IP | `pip install ray` on both, same Python + Ray version; `ray start --head` on one, `ray start --address=…` on the other |
| code we write | more (~150 lines): claiming tasks, reclaiming lost ones, retries | less: `@ray.remote` on a function, Ray does scheduling and retries |
| failure visibility | every outcome is explicit in our code, so the project rule (every failure classified, counted, sampled) is easy to meet | retries are hidden by default; we must add wrappers to still count `WORKER_LOST` / `OOM` separately |
| explaining it to a jury | simple: "a shared to-do list, and workers take tasks" | "Ray handles it", which is harder to explain in depth |
| learning curve for a team new to clusters | lower concepts, more code | less code, more "magic" to understand when it breaks |
| Windows support on the second machine | the Redis *server* wants Linux (or WSL); clients work anywhere | limited/experimental on Windows |

**My recommendation stays Redis Streams**, mainly because of the failure-visibility rule and because it is easier to explain. It depends on the second machine's OS → R3.

### Q12 — datum ("can't we find it?")
**What the question is.** Every lat/lon number assumes a model of the Moon's shape and a convention for measuring angles on it. If ISRO's numbers and NASA's numbers use different conventions, the same point gets different coordinates, and our "where should the OHRC picture sit on the NAC map" prediction is off before matching even starts.

**Good news, found while re-checking.** Our code models the Moon as a perfect sphere (radius 1,737,400 m, no flattening: `constants.py:16-17`). On a perfect sphere the two latitude conventions people argue about (planetocentric vs planetographic) give **identical numbers**. So the big open question mostly disappears. What remains:
1. **The sphere radius** ISRO used. Radius differences shift heights, and barely shift positions.
2. **The longitude direction** (east-positive or west-positive) and **range** (0–360 or −180…+180). Our code already handles the range, and the Vikram labels read as east-positive.

**Can we find it?**
- Partly, yes. ISRO publishes a data-format document (a "SIS", software interface specification) for each instrument on PRADAN, their download portal. It sits behind your login, so I can't read it. If you can download the OHRC SIS PDF tonight, I will read it and cite it.
- Independently, once the calibrated OHRC products (Q9) arrive, a test can measure it: map a crater through ISRO's per-pixel lat/lon grid and through NASA's map. If they agree to within the ~1 km uncertainty we already know about, the convention is consistent. If they are off by a pattern (for example, mirrored in longitude), we will see it.

→ R2.

## Follow-up questions

R1 | Confirm the defaults from the explanations: Q8 = setting added, both options benchmarked, winner becomes the default; Q10 = the label from ODE first, SPICE only as fallback. | default | Explained above. | M
ANSWER: default

R2 | Can you download the ISRO **OHRC SIS / data product document** (and the TMC-2 and IIRS ones if listed) from PRADAN tonight, into `docs/external/`? | Yes, if it exists on PRADAN. Q12 is otherwise settled by the measurement test only. | It is the only primary source for ISRO's datum, and it may also resolve the 3 unresolved label fields. | M
ANSWER: ____

R3 | Second machine (RTX 3060 6 GB): OS and version? Same local network as the laptop, reachable by IP/SSH? Free disk space? Python version? | Assumed: Ubuntu/Linux, same LAN, SSH works, ≥ 100 GB free. If it is Windows, I switch the Phase-4 design to Redis on the laptop plus a client-only worker on Windows. | This decides the broker, the install script, and how data reaches the second machine. | H
ANSWER: MERGED (with R4). Host details still needed: OS, LAN/SSH, disk, Python — see R3b.

R4 | Each host has one GPU, so "one machine, N GPUs" (Phase 3) can't be shown. Merge Phase 3 into Phase 4? | Yes. **New Phase 3** = the job format + queue + GPU worker + reducer on the laptop alone (1 GPU worker + CPU workers). **New Phase 4** = the same code across both hosts, 4060 + 3060. Only the queue transport changes between them. | This matches your Q1 answer ("3 questionable, 4 necessary"), and the 3060 host makes a real two-machine run possible. | H
ANSWER: MERGED. New Phase 3 = single-host queue/worker/reducer; new Phase 4 = both hosts.

R5 | What must exist **by tonight / for tomorrow's video**? Phase 1 + 2 in full is several days of prompts. | Tonight: (1) bug fixes S1–S3 + preprocessing setting; (2) the download session prompt (R6); (3) a skip-if-absent ingest for OHRC-ncp/TMC-2/IIRS/NAC/JAXA; (4) GPU bring-up after your driver fix, re-running the Vikram 2024 strip on GPU with timing and VRAM recorded; (5) the 2023-strip diagnosis run. **After the video:** the DTM-rendered reference (1B), native-resolution tiling, and Phases 3–4. | Your Q15 answer gives about one day. This is what fits without shipping half-built parts. | H
ANSWER: User: can be done today; Phase 1 is mostly built, Phase 2 is GPU integration. (Fable note: S1–S3 fixes, preprocess setting, skip-if-absent ingest and NAC ingest are not built yet; 1B stays gated.)

R6 | The download session tonight. Q9 says "an Opus probe with access to the logged-in page", but Q17 says "ISRO limits the download to human hands". Which is it for **PRADAN (ISRO)**? | **PRADAN:** Opus prepares the exact product list (IDs, expected sizes, footprints over Vikram) and a click-by-click checklist, and you click. Opus never uses your PRADAN login. Afterwards a verify script checks every file against its label (size, checksum, footprint). **NASA (LRO) and JAXA (SELENE):** public, no login. Opus downloads from validated URLs with a script, resumable and rate-limited. | This respects ISRO's rule, and downloads from the public archives can be automated. | H
ANSWER: User downloads PRADAN data personally. The Opus session only sees the webpage and tells the user which products to download.

R7 | Which datasets exactly, tonight? You wrote "LRO and JAXA terrain, infrared, high quality". | CH-2: OHRC calibrated ×4 (Q9), plus TMC-2 and IIRS whose footprints cover Vikram (found from the catalogue first, then downloaded). LRO: the NAC photograph label for M1442997156 (Q10), plus any further NAC ortho/DTM over Vikram the catalogue lists. JAXA: SELENE Terrain Camera (and its terrain model) over Vikram, if the catalogue shows coverage. **"Infrared" = ISRO's IIRS**; I know of no NASA/JAXA infrared product planned. Say if you meant one. | The session prompt must name every product; it can't "find high quality data" without a concrete list. | H
ANSWER: default

R8 | Q22: which rules did you mean were "enforced by mistake"? If there are no tool-level fences, benchmark integrity relies on instructions. | No `deny` rules; keep `bypassPermissions`. Protect the harness a different way: a checksum list `Phase_*/harness/MANIFEST.sha256`, checked by `verify.sh` and by my review. Any change to a harness or benchmark file fails the phase, whoever made it. | This works under bypass mode, and it catches edits after the fact instead of blocking them. | M
ANSWER: OKAY (default).

R9 | Housekeeping authority. (a) Q24: shall **I** make the baseline commit now, or will you? (b) Q20: may I edit `~/.claude/CLAUDE.md` (remove the architect role) and create `.fable/ARCHITECT.md`, or will you edit your global file? (c) Q25 vs Q5: `find_cross_sensor_pairs` and `pseudo_gt.py` have no callers today but are needed for TMC-2/IIRS (Q5 now in scope). Keep them? | (a) I commit, once you reply "go". (b) I do both. (c) Keep both. Delete only true duplicates (the LoFTR/LightGlue copies, the second `shadow_mask`, the second `scale_ratio`), `ingest/footprint.py` (after moving its one used helper), and `configs/default.yaml`. | "Delete dead code" would otherwise remove code that Q5 now needs. | M
ANSWER: yes to all. Done 2026-09-29: architect role moved to `.fable/ARCHITECT.md`; `~/.claude/CLAUDE.md` removed (backup `~/.claude/CLAUDE.md.bak-20260929`); root `CLAUDE.md` is now an implementer stub; baseline commit made on main.

R3b | Second host (RTX 3060 6 GB): OS + version, same LAN as laptop with SSH, free disk, Python version? | Assume Ubuntu, same LAN, SSH, ≥100 GB, Python 3.12 | Decides broker install and data transport for Phase 4 | H
ANSWER: ____
