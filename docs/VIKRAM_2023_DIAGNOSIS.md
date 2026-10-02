# Why the three 2023 OHRC strips do not register (exp-1, exp-2) and the Phase 1B gate

Prompt P1.20 (decisions G02, G14, G27). Every number on this page is copied
from the run artefact whose path is given in the same sentence or table row.
The per-strip cause classes are written first to
`data/processed/vikram/exp1/diagnosis.json` and only repeated here.

## Words used on this page

- **OHRC**: the Orbiter High Resolution Camera on Chandrayaan-2. It images a
  narrow strip of the surface, line by line, as the orbiter moves; one such
  image is a **strip**, named here by its acquisition time (**tag**), for
  example `20230823T1450475804` = 2023-08-23 14:50:47.
- **Raw (`nrp`) and calibrated (`ncp`) products**: the same OHRC strip at two
  processing levels from ISRO's archive. The calibrated product comes with a
  **geometry grid**: a table giving the ground position (latitude, longitude)
  of sample pixels, which is a second, independent way to place the strip on
  the map.
- **Reference**: the image the strip is aligned to. Here it is the LRO NAC
  orthoimage of the Vikram landing site (NASA's Lunar Reconnaissance Orbiter
  Narrow Angle Camera, already map-projected).
- **Registration**: finding the geometric transform that lines up the strip
  with the reference, so that every strip pixel gets a map position.
- **Matcher**: the algorithm that finds the same small surface features
  (crater rims, boulders) in both images and pairs them up. Four are tried:
  `sift`, `akaze`, `asift` (hand-designed feature detectors) and `lightglue`
  (a learned neural-network matcher).
- **Raw matches**: feature pairs the matcher proposes.
- **RANSAC inliers**: the proposed pairs that agree with one common transform
  (RANSAC is the robust fitting method that throws out pairs that disagree).
  A homography (the transform used here) needs at least 4 pairs, so 4 inliers
  means "only the minimum the fit itself consumes": no independent support.
- **Final inliers**: the inliers after the refinement stage; they exist only
  for a pair that registered.
- **U (uniformity score, 0 to 1)**: how evenly the inliers are spread over the
  image; near 1 means they cover it evenly.
- **Pre-ECC agreement**: the largest distance, in reference pixels, between
  where two different matchers' transforms put the same probe points, before
  the final intensity-based refinement (ECC). Two independent matchers that
  agree to under 1 pixel are evidence the answer is right.
- **Prior**: the first guess of where the strip sits on the reference, used
  to cut the piece of reference that matching searches. A wrong prior can
  make the right ground fall outside the searched piece. Three priors appear
  here: the strip label's corner coordinates (**label corners**), the same
  plus a fixed **prior shift** (556 m east, 2888 m south, the offset measured
  on the 2024 anchor strip), and the calibrated product's **geometry grid**.
- **Coarse pass**: a first registration at 8 m per pixel over a wider area, used
  to correct the prior before the 4 m per pixel run.
- **Preset**: an image-preprocessing recipe run before matching; `none` means
  the images are matched as read.
- **Sun azimuth / elevation**: the compass direction the sunlight comes from
  (degrees clockwise from north, `north_clockwise`) and its height above the
  horizon. Shadows point away from the sun, so the same crater photographed
  with the sun in a very different direction shows differently placed shadows,
  and feature matchers then find few common features.
- **SPICE**: NASA's toolkit for spacecraft and planet geometry. From the
  planetary ephemeris and the image time it gives the sun direction at a point
  on the Moon; values from it are **COMPUTED**.
- **ODE**: the PDS Orbital Data Explorer, NASA's archive catalogue; its
  metadata for the NAC image gives the incidence angle (elevation = 90° −
  incidence), a **DOCUMENTED** value.
- **DTM fit**: shade the NAC terrain model (DTM = digital terrain model) with a
  trial sun at every azimuth and keep the one whose shading best correlates
  with the NAC image (NCC = normalised cross-correlation). The **peak margin** is
  how much the best correlation exceeds the second-best peak; a small margin
  means the fit barely distinguishes the two directions. Values from it are
  **INFERRED**.
- **Phase 1B / gate**: Phase 1B (an illumination bridge between images with
  different sun directions) is built only if this experiment shows it is
  needed (decision G02). The **gate** file records that decision.

## Question

The three 2023 OHRC strips of the Vikram site (`20230823T1450475804`,
`20230823T1647285085`, `20230823T1647285315`, decision G27) did not register
against the LRO NAC reference in the v1 run (FABLE_NOTES §5: the v1 coarse
pass failed on all 2023 strips), while the 2024 anchor strip
`20240425T1406019344` registers. The v1 live store, archived as
`data/processed/results_archive_20260929/index.parquet`, holds 13 rows and 0
of them for any 2023 tag (`rows_for_tag` in
`data/processed/vikram/exp1/diagnosis.json`). Is the cause a wrong position
prior (fixable here), bad data, or the illumination difference (which needs
Phase 1B)?

## What was run

All from the repository root with `.venv/bin/python`, in this order (console
logs next to each run record):

1. exp-2, reference sun:
   `scripts/fit_reference_sun.py --nac 1 --label-convention --out data/processed/vikram/reference_sun`
   (run record `data/processed/vikram/reference_sun/run_record.json`).
2. exp-1a, corrected prior on the raw strips:
   `scripts/run_vikram.py --only 20230823 --instruments OHRC --levels raw --prior-shift 556,-2888 --margin-m 2000 --matchers sift,akaze,asift,lightglue --min-inliers 8 --results-root data/processed/results --out-dir data/processed/vikram/exp1/raw_prior --overwrite`
   (run record `data/processed/vikram/exp1/raw_prior/run_record.json`, console
   `data/processed/vikram/exp1/raw_prior/console_exp1a.log`; no pair
   registered, and the script returns exit code 1 in that case,
   `scripts/run_vikram.py:422`).
3. exp-1b, geometry-grid prior on the calibrated strips. It was run because the
   catalog lists the `ncp` twin of each 2023 tag as PRESENT (`lunar-reg
   catalog --json data/processed/vikram/exp1/catalog.json`: OHRC `present`
   with 8 products, among them `ch2_ohr_ncp_` for all three 2023 tags; console
   `data/processed/vikram/exp1/console_catalog.log`):
   `scripts/run_vikram.py --only 20230823 --instruments OHRC --levels calibrated --no-coarse --prior-shift '' --margin-m 1000 --matchers sift,akaze,asift,lightglue --min-inliers 8 --results-root data/processed/results --out-dir data/processed/vikram/exp1/cal_grid --overwrite`
   (run record `data/processed/vikram/exp1/cal_grid/run_record.json`, console
   `data/processed/vikram/exp1/cal_grid/console_exp1b.log`; no pair
   registered, exit code 1 as above).
4. Gate: `.venv/bin/python -c` calling
   `sites.runner.compute_exp1_gate("data/processed/results", <3 tags>, <sun of
   reference_sun.json>, "data/processed/vikram/exp1/raw_prior/run_record.json")`
   over the live store, written with `json.dump(..., indent=2, sort_keys=True)`
   to `data/processed/vikram/exp1_gate.json`. The full `-c` program is stored
   verbatim in the `command` field of its run record
   `data/processed/vikram/exp1/run_record.json` (console
   `data/processed/vikram/exp1/console_gate.log`). This step was run twice: the
   first record kept only `["-c"]` as its command, so the step was repeated to
   record the program; the earlier files are kept in
   `data/processed/vikram/p1_20_attempt4_gate_superseded/` and their gate
   content is identical apart from `created_utc`.
5. Classification: the rule table of `Phase_1/LLD/runs.md` §P1.20 step 5
   evaluated on the artefacts above by a `.venv/bin/python -c` program, written
   to `data/processed/vikram/exp1/diagnosis.json` (console
   `data/processed/vikram/exp1/console_diagnosis.log`). The full program is
   stored verbatim in the `command` field of its run record
   `data/processed/vikram/exp1/diagnosis_run/run_record.json`, and every number
   under `rule_inputs` carries a `_source` sibling (`computed`, `measured` or
   `documented`). The first classification was written by a program that was
   not kept and had no run record; it is kept in
   `data/processed/vikram/p1_20_attempt4_diagnosis_superseded/exp1/`, and its
   classes and values are identical to the current file's (open question
   Q-P1.20-2 in `Phase_1/QUESTIONS.md`).

Both exp-1 runs used preset `none` (`params.preprocess` in
`data/processed/vikram/exp1/raw_prior/run_record.json` and
`data/processed/vikram/exp1/cal_grid/run_record.json`): the commands above
pass no `--preprocess`, and the runner's default is `none`, not the pipeline
default `ohrc_nac` chosen in P1.19 (open question Q-P1.19-1, Q-P1.20-1 in
`Phase_1/QUESTIONS.md`).

Run notes. All five run records (the four above plus the
classification's) carry code commit `56a06f0` with
`git_dirty` true (`git_sha`, `git_dirty` in each run record). When this
page was finished, `git status` showed no tracked source file changed against
that commit, only untracked notes (this page's draft among them) and the
process file `Phase_1/QUESTIONS.md`. The exp-1a console
`data/processed/vikram/exp1/raw_prior/console_exp1a.log` shows three PyTorch
CUDA allocator warnings ("memory allocation failed with OOM", stamped
19:26:01, 19:26:20 and 19:26:39 local time); the allocator recovered, since the
run record counts `oom` 0 and `matcher_error` 0 and every LightGlue pair
ended in a classified `too_few_matches` outcome
(`outcome_counts` in `data/processed/vikram/exp1/raw_prior/run_record.json`).
Earlier P1.20 attempts that froze the machine (Q-P1.20-0) are kept apart in
`data/processed/vikram/p1_20_attempt{1,2,3}_untrusted/` and are not used
here.

## Per-strip results

All six window pairs were prepared without error: 3 of 3 `ok` in each run
(`outcome_counts.prep_ok` in both exp-1 run records). The reference crop was
94 %, 94 % and 88 % valid in exp-1a and 99 % for each strip in exp-1b
(`prep_detail` in `data/processed/vikram/exp1/raw_prior/products.json` and
`data/processed/vikram/exp1/cal_grid/products.json`). In exp-1a the coarse
pass failed on every strip (`coarse_failed` 3 in
`data/processed/vikram/exp1/raw_prior/run_record.json`), so the fixed prior
shift was used. No pair registered: 0 `ok` of 12 in each run (same run
records), so the live store gained no result row for a 2023 tag and the 24
failures below are its failure rows.

Table: every registration attempt for the 2023 strips, from the live-store
failure table `data/processed/results/failures.parquet` (the live-store index
`data/processed/results/index.parquet` has no 2023 row). Status is the
pipeline's failure class with the stage it stopped at. A dash means the value
is not produced at that stage: final inliers, U and pre-ECC agreement exist
only for a registered pair, and RANSAC inliers only when matching produced
the minimum of 8 pairs.

| tag | run | matcher | status (stage) | raw matches | RANSAC inliers | final inliers | U | pre-ECC agreement | prior used |
|---|---|---|---|---|---|---|---|---|---|
| 20230823T1450475804 | exp-1a (raw, nrp) | sift | too_few_matches (match) | 4 | — | — | — | — | prior shift 556,-2888 m (E,S) |
| 20230823T1450475804 | exp-1a (raw, nrp) | akaze | too_few_inliers (estimate) | 9 | 4 | — | — | — | prior shift 556,-2888 m (E,S) |
| 20230823T1450475804 | exp-1a (raw, nrp) | asift | too_few_matches (match) | 7 | — | — | — | — | prior shift 556,-2888 m (E,S) |
| 20230823T1450475804 | exp-1a (raw, nrp) | lightglue | too_few_matches (match) | 0 | — | — | — | — | prior shift 556,-2888 m (E,S) |
| 20230823T1450475804 | exp-1b (calibrated, ncp) | sift | too_few_matches (match) | 3 | — | — | — | — | geometry grid |
| 20230823T1450475804 | exp-1b (calibrated, ncp) | akaze | too_few_inliers (estimate) | 9 | 4 | — | — | — | geometry grid |
| 20230823T1450475804 | exp-1b (calibrated, ncp) | asift | too_few_inliers (estimate) | 8 | 4 | — | — | — | geometry grid |
| 20230823T1450475804 | exp-1b (calibrated, ncp) | lightglue | too_few_matches (match) | 2 | — | — | — | — | geometry grid |
| 20230823T1647285085 | exp-1a (raw, nrp) | sift | too_few_matches (match) | 4 | — | — | — | — | prior shift 556,-2888 m (E,S) |
| 20230823T1647285085 | exp-1a (raw, nrp) | akaze | too_few_inliers (estimate) | 10 | 4 | — | — | — | prior shift 556,-2888 m (E,S) |
| 20230823T1647285085 | exp-1a (raw, nrp) | asift | too_few_inliers (estimate) | 11 | 4 | — | — | — | prior shift 556,-2888 m (E,S) |
| 20230823T1647285085 | exp-1a (raw, nrp) | lightglue | too_few_matches (match) | 2 | — | — | — | — | prior shift 556,-2888 m (E,S) |
| 20230823T1647285085 | exp-1b (calibrated, ncp) | sift | too_few_matches (match) | 4 | — | — | — | — | geometry grid |
| 20230823T1647285085 | exp-1b (calibrated, ncp) | akaze | too_few_inliers (estimate) | 10 | 4 | — | — | — | geometry grid |
| 20230823T1647285085 | exp-1b (calibrated, ncp) | asift | too_few_inliers (estimate) | 9 | 4 | — | — | — | geometry grid |
| 20230823T1647285085 | exp-1b (calibrated, ncp) | lightglue | too_few_matches (match) | 1 | — | — | — | — | geometry grid |
| 20230823T1647285315 | exp-1a (raw, nrp) | sift | too_few_matches (match) | 7 | — | — | — | — | prior shift 556,-2888 m (E,S) |
| 20230823T1647285315 | exp-1a (raw, nrp) | akaze | too_few_inliers (estimate) | 8 | 4 | — | — | — | prior shift 556,-2888 m (E,S) |
| 20230823T1647285315 | exp-1a (raw, nrp) | asift | too_few_inliers (estimate) | 12 | 4 | — | — | — | prior shift 556,-2888 m (E,S) |
| 20230823T1647285315 | exp-1a (raw, nrp) | lightglue | too_few_matches (match) | 0 | — | — | — | — | prior shift 556,-2888 m (E,S) |
| 20230823T1647285315 | exp-1b (calibrated, ncp) | sift | too_few_matches (match) | 6 | — | — | — | — | geometry grid |
| 20230823T1647285315 | exp-1b (calibrated, ncp) | akaze | too_few_inliers (estimate) | 11 | 4 | — | — | — | geometry grid |
| 20230823T1647285315 | exp-1b (calibrated, ncp) | asift | too_few_matches (match) | 7 | — | — | — | — | geometry grid |
| 20230823T1647285315 | exp-1b (calibrated, ncp) | lightglue | too_few_matches (match) | 3 | — | — | — | — | geometry grid |

For comparison, the 2024 anchor strip registers with every matcher in the
live store: 167 to 403 final inliers and U 0.83 to 0.87
(`n_inliers`, `u_score` of the four `CH2_OHRC_RAW_20240425T1406019344-*_pp-ohrc_nac`
rows in `data/processed/results/index.parquet`; preset `ohrc_nac`, so this is
not a same-preset comparison).

## Sun geometry

**Reference image sun (SPICE, COMPUTED, `north_clockwise`).** For the NAC image
`M1442997156LE` at 2023-07-03T04:18:08.914Z the sun stood at azimuth
327.09° and elevation 16.17° at the site point (lat −69.2621°, lon 32.1781°)
(`sun` in `data/processed/vikram/reference_sun/reference_sun.json`).

Cross-checks (`cross_checks` in
`data/processed/vikram/reference_sun/reference_sun.json`):

| check | value | source |
|---|---|---|
| ODE elevation (DOCUMENTED, 90° − incidence 73.84°) | 16.16° | `cross_checks.ode_elevation_deg`, `data/processed/vikram/reference_sun/reference_sun.json` |
| ODE − SPICE elevation (COMPUTED) | −0.008° | `cross_checks.elevation_diff_deg`, same file |
| DTM-fit azimuth, map-grid frame (INFERRED) | 323.0° | `cross_checks.dtm_fit.azimuth_grid_deg`, same file |
| SPICE azimuth converted to the same grid frame | 327.21° | `cross_checks.dtm_fit.spice_azimuth_grid_deg`, same file |
| DTM fit − SPICE azimuth | −4.21° | `cross_checks.dtm_fit.fit_minus_spice_deg`, same file |
| DTM-fit NCC peak / second peak (at 303.0°) | 0.805 / 0.759 | `cross_checks.dtm_fit.ncc_peak`, `second_peak_ncc`, `second_peak_deg`, same file |
| DTM-fit peak margin | 0.046 | `cross_checks.dtm_fit.peak_margin`, same file (curve: `data/processed/vikram/reference_sun/ncc_curve.csv`) |

The elevation agrees with the archive to under a hundredth of a degree. The
DTM fit lands 4.21° from SPICE, but its peak margin of 0.046 is small (a
second peak 20° away correlates almost as well), so the fit is weak
confirmation of the azimuth, not an independent measurement of it.

**ISRO label sun azimuth convention.** Comparing each OHRC label's sun azimuth
with SPICE at that strip's time and place, the convention that fits is
`as_is` (the label value is already clockwise from north), with a maximum
azimuth difference of 2.02° and a maximum elevation difference of 0.89° over 8
labels (`convention`, `max_diff_deg`, `elevation_max_diff_deg` in
`data/processed/vikram/reference_sun/label_convention.json`).

**The strips' sun against the anchor's and the reference's.** Label azimuths
(`per_strip[].label_azimuth` in
`data/processed/vikram/reference_sun/label_convention.json`): the three 2023
strips 61.79°, 62.03° and 62.01°, the 2024 anchor strip 303.87°, and the NAC
reference (SPICE) 327.09° (`data/processed/vikram/reference_sun/reference_sun.json`).
The anchor, which registers, is lit from roughly the same side as the
reference; the 2023 strips are lit from the opposite quarter, 117.93°, 118.16°
and 118.14° away from the anchor's label azimuth
(`label_azimuth_diff_from_anchor_deg` in
`data/processed/vikram/exp1/diagnosis.json`), at label elevations of 8.11°,
8.91° and 8.92° (`per_strip[].label_elevation`,
`data/processed/vikram/reference_sun/label_convention.json`).

## Gate decision

`data/processed/vikram/exp1_gate.json`: decision **BUILD_1B**, 0 of 3 strips
passing (`decision`, `n_strips_passing`); each strip row has status
`no_result`, no best matcher and `passes_targets` false, because the live store
holds no registered 2023 pair. The rule, copied from the file: "SKIP_1B iff
every 2023 strip has >=1 matcher with n_inliers>=20 and u_score>=0.7 and
agreement passes (<1 px pre-ECC, >=2 matchers)".

## Per-strip cause classification

Rule table (`Phase_1/LLD/runs.md` §P1.20 step 5), evaluated in this order:
`PRIOR` = fails in the v1 run and passes the targets in exp-1a or exp-1b;
`ILLUMINATION_SUSPECTED` = fails in both exp-1 runs that were executed,
reference valid fraction ≥ 0.5 and label sun azimuth ≥ 90° from the anchor
strip's; `DATA` = prep status not OK or reference valid fraction < 0.5;
`UNRESOLVED` = none of these. The inputs for each strip are stored under
`strips.<tag>.rule_inputs` in `data/processed/vikram/exp1/diagnosis.json`.

### 20230823T1450475804
Classification: ILLUMINATION_SUSPECTED

No v1 row (0 rows in `data/processed/results_archive_20260929/index.parquet`);
both exp-1 runs executed and failed for every matcher (gate `passes_targets`
false, `data/processed/vikram/exp1_gate.json`); prep `ok` in both runs with
reference valid fractions 0.94 (exp-1a) and 0.99 (exp-1b); label sun azimuth
61.79° vs the anchor's 303.87°, 117.93° apart (`rule_inputs`,
`data/processed/vikram/exp1/diagnosis.json`).

### 20230823T1647285085
Classification: ILLUMINATION_SUSPECTED

No v1 row (0 rows in `data/processed/results_archive_20260929/index.parquet`);
both exp-1 runs executed and failed for every matcher (gate `passes_targets`
false, `data/processed/vikram/exp1_gate.json`); prep `ok` in both runs with
reference valid fractions 0.94 (exp-1a) and 0.99 (exp-1b); label sun azimuth
62.03° vs the anchor's 303.87°, 118.16° apart (`rule_inputs`,
`data/processed/vikram/exp1/diagnosis.json`).

### 20230823T1647285315
Classification: ILLUMINATION_SUSPECTED

No v1 row (0 rows in `data/processed/results_archive_20260929/index.parquet`);
both exp-1 runs executed and failed for every matcher (gate `passes_targets`
false, `data/processed/vikram/exp1_gate.json`); prep `ok` in both runs with
reference valid fractions 0.88 (exp-1a) and 0.99 (exp-1b); label sun azimuth
62.01° vs the anchor's 303.87°, 118.14° apart (`rule_inputs`,
`data/processed/vikram/exp1/diagnosis.json`).

## What this does and does not show

- Two different priors (the anchor's measured shift on the raw strips, and the
  calibrated product's own geometry grid) give the same picture: at most 12 raw
  matches and never more than the 4 RANSAC inliers a homography consumes
  (table above, `data/processed/results/failures.parquet`). A prior error alone
  would be expected to recover under at least one of them; it did not.
- The data are usable: every window was prepared and the reference crops are
  at least 88 % valid (`products.json` of both runs).
- The remaining measured difference between the anchor and the 2023 strips is
  the sun: about 118° apart in azimuth and lower in elevation
  (`data/processed/vikram/exp1/diagnosis.json`,
  `data/processed/vikram/reference_sun/label_convention.json`). This is why the
  class is *suspected*: the experiment rules out the prior and the data as far
  as these runs go, it does not prove illumination is the cause.
- Both exp-1 runs used preset `none`; whether preset `ohrc_nac` changes the
  outcome was not measured here (Q-P1.20-1).
