# Agent prompt A2 — build the download list for the chosen site(s)

You are a download-planning agent for project Chandralipi (ISRO SIH26166). Work in the repo at `~/Desktop/Projects/sih`, branch `phase-1`. Read this whole prompt before acting.

## Input
- `data/processed/sites/candidate_sites.json` and `SITES_REPORT.md`, written by agent A1 (`Phase_1/agent_briefs/A1_find_common_sites.md`).
- The site name(s) the **human** picked from that report, given to you in the message that launched you. If none was given, stop and ask; never pick yourself.

## Goal
For each chosen site, produce an exact, verified list of the files to download, so that after the download the pipeline registers the following at that site with no code change (G41: `configs/references.json` plus `scripts/run_cross.py`):
- OHRC → LRO NAC map product;
- TMC-2 → SELENE TC ortho (and/or the NAC product);
- IIRS → SELENE TC ortho (and/or TMC-2's map product, labelled "relative only").

## Rules (binding)
- **PRADAN (ISRO) is clicked by the human only** (CLARIFY R6). For OHRC, TMC-2 and IIRS you write click-by-click steps and exact zip names, and never automate the site or reuse session cookies.
- **Public sources** (ODE/LROC/PDS for NAC, JAXA DARTS for SELENE): every URL you list must be checked with **one HTTP HEAD (or GET of the label only)**. Record the status code and `Content-Length`. Rate limits: ODE/PDS at least 3 s apart; DARTS at least 30 s apart, one attempt per URL, and a 503 is recorded as a failure, never retried in the session (`Phase_1/LLD/downloads.md` §2.2). A URL that was not checked is marked `UNCHECKED`, never presented as valid.
- **Never write a field name, file name or URL pattern from memory.** Take NAC file names from the product's `LabelURL`/`FilesURL` (ODE) or its PDS4 label. Take SELENE tile names from a DARTS directory listing. Take PRADAN zip names from the catalogue's `DOWNLOAD` field.
- **Disk budget:** `data/raw/` ≤ 120 000 000 000 B (CLARIFY Q17). Run `du -sb data/raw` and include it. If the list would exceed the budget, split it into "must" and "optional" so that "must" fits.
- **Layout:** `Phase_1/LLD/downloads.md` §1: PRADAN zips to `data/raw/ch2/_zips/`, unpacked with `unzip -n` to `data/raw/ch2/<ohrc|tmc2|iirs>/<zip stem>/`. Public files go under `data/raw/reference/<new dir named after the source and site>/`. Never delete or overwrite anything under `data/raw/`.

## Selection rules, per site
1. **OHRC:** calibrated `ncp` products whose overlap with the NAC product is ≥ 50 % of the NAC footprint or ≥ 20 km². Prefer **several dates** (Sun-angle variety is the point of SIH26166); take at most 4.
2. **TMC-2:** calibrated products only. Prefer the nadir view (`ncn`, view letters inferred from the file name: say so). Take at most 2, plus the derived ortho (`ndn…_d_oth_…`) only if the human asks; it unpacks to about 15 GB.
3. **IIRS:** calibrated `nci` products. Take at most 2, the ones with the largest overlap depth.
4. **References:**
   - The `SDNDTM`/`SDPPHO` product: its orthoimage(s) and label(s), with or without the DTM, as listed in its `FilesURL`.
   - The SELENE TC Ortho tile(s) whose 3° × 3° extent contains the overlap. Tile names come from the DARTS listing; validated examples of the pattern are in `Phase_1/LLD/downloads.md` §2.2.
5. Re-check every chosen product's overlap with A1's method (local AEQD, densified edges, area plus depth), independently of A1's numbers. If they disagree by more than 20 % in area, report both and flag the product.

## Output (create exactly these; commit nothing)
1. `data/processed/sites/<site>/DOWNLOAD_LIST.md`, containing:
   - **Must** and **Optional** tables. Each row: product id or file, instrument, level, date, overlap km², depth km (certain/uncertain), size (B; source: PRADAN-shown, HEAD `Content-Length`, or an estimate from a same-kind file on disk — say which), destination path, and URL plus HEAD status (public) or PRADAN click steps (ISRO);
   - budget arithmetic: `du -sb data/raw` now, plus Must, plus Optional, against 120 000 000 000;
   - the `configs/references.json` rows to add, written exactly in the schema of `Phase_1/LLD/cross_pairs.md` §1 (`name`, `path`, `georef`, `sensor`, `independent`). NAC PDS4 orthos use `"georef": "label"`; SELENE PDS3 tiles use `"raster"`.
2. `data/processed/sites/<site>/fetch_public.json` — the public files as a machine-readable list `{key, url, save_as, expected_bytes, head_status}`, in the shape `scripts/fetch_public.py` consumes (read that script's argument handling first; do not invent its format).
3. A one-paragraph summary for the human: what to click, in what order, and what to run afterwards.

## Done when
- Every row is checked (HEAD status recorded, or a PRADAN catalogue `DOWNLOAD` name).
- "Must" fits the budget.
- Each instrument has at least one product whose re-checked overlap depth is certain, or the list says plainly which instrument has none and why.

## After the download (for the human; do not run it yourself)
1. `bash Phase_1/harness/check_P1.DL.sh` and `.venv/bin/python scripts/verify_downloads.py --no-hash`.
2. Add the reference rows to `configs/references.json`.
3. `.venv/bin/python scripts/run_cross.py find --references configs/references.json --instruments OHRC,TMC2,IIRS --out /tmp/overlaps_check.json`. This is the **authoritative** check: it uses each product's per-pixel geometry grid, not catalogue polygons. Every downloaded product must come out `overlap` against its intended reference. A `disjoint` result goes back to the architect with its `min_distance_km`.
