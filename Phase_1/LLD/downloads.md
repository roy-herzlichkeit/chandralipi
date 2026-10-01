# LLD — downloads: session, manifest, verifier, public fetch (P1.DL, P1.01, P1.02)

Produces: C08. Decisions: G12, G32. Sources for every URL: `.fable/research_20260929.json` (VALIDATED = fetched with HTTP 200 on 2026-09-29; DOCUMENTED = URL taken from ODE's file list, never fetched successfully).

## 1. On-disk layout (binding for every download)
| instrument | directory | unpack rule |
|---|---|---|
| OHRC calibrated (`ncp`) | `data/raw/ch2/ohrc/<zip stem>/` | `unzip -n <zip> -d data/raw/ch2/ohrc/<zip stem>/`; keep the zip under `data/raw/ch2/_zips/` |
| TMC-2 | `data/raw/ch2/tmc2/<zip stem>/` | same |
| IIRS | `data/raw/ch2/iirs/<zip stem>/` | same |
| OHRC raw (`nrp`, already on disk) | `data/raw/ohrc_vikram/` | unchanged |
| LRO NAC ortho + DTM (on disk) | `data/raw/reference/lro_nac_vikram/` | unchanged |
| ODE metadata JSON | `data/raw/reference/lro_nac_vikram/ode/edrnac4_vikram_box.json` | as fetched |
| NAIF generic SPICE kernels (G14) | `data/raw/reference/spice/<name>` | as fetched |
| LRO NAC EDR labels | `data/raw/reference/lro_nac_vikram/edr/<NAME>.xml` | as fetched |
| SELENE TC Ortho Map tiles | `data/raw/reference/selene_tc_ortho/<NAME>.img` + `.lbl` | as fetched |
| SELENE TC DTM / morning / evening tiles | `data/raw/reference/selene_tc_dtm/`, `.../selene_tc_morning/`, `.../selene_tc_evening/` | as fetched |
| ISRO SIS documents | `docs/external/<zip stem>/` | `unzip -n` (R2) |
| PRADAN footprint shapefiles ("Other Downloads") | `data/raw/catalogue/shapefiles/<TMC2\|IIRS>_ShapeFiles/` | `unzip -n`; recorded in the manifest (added after P1.DL, which used them instead of §2.3's GeoJSON) |
| PRADAN keep-alive page | `data/raw/ch2/_pradan/payload.xhtml` | written by PRADAN's own script; not data; P1.01's scan reports it UNRECORDED (expected, never deleted) |
Never delete or overwrite anything already under `data/raw/` (CLAUDE.md).

## 2. Products
### 2.1 PRADAN (human clicks; G12) — priority order
| # | product (zip name) | instrument | why | size (source) |
|---|---|---|---|---|
| 1 | `ch2_ohr_ncp_20240425T1406019344_d_img_d18.zip` | OHRC | calibrated twin of the anchor strip (G27); carries the geometry grid needed by P1.05–P1.07 | ~1.2 GB (CLARIFY Q9) |
| 2 | `ch2_ohr_ncp_20230823T1450475804_d_img_n18.zip` | OHRC | twin of a failing 2023 strip | ~1.2 GB |
| 3 | `ch2_ohr_ncp_20230823T1647285085_d_img_n18.zip` | OHRC | same | ~1.2 GB |
| 4 | `ch2_ohr_ncp_20230823T1647285315_d_img_n18.zip` | OHRC | same | ~1.2 GB |
| 5 | TMC-2 products whose footprint intersects the Vikram box (§2.3) — at most 2, calibrated level first (P1.DL took 4; accepted, §2.4) | TMC2 | Q5 scope | unknown until the catalogue is read |
| 6 | IIRS products whose footprint intersects the Vikram box — at most 1, calibrated level first (P1.DL took 2; accepted, §2.4) | IIRS | Q5 scope | unknown |
| 7 | SIS documents `OHR.zip`, `TMC.zip`, `IIR.zip` under PRADAN "Other Downloads" | DOC | datum and field definitions (R2) | small |
The four OHRC ids are rows 10–12 and 20 of `data/processed/ohrc_vikram_product_ids.txt` (from the ISSDC catalogue on disk).

### 2.2 Public, scripted (P1.DL by `curl`, P1.02 by `scripts/fetch_public.py`)
| key | URL | save as | status | size |
|---|---|---|---|---|
| ode_edrnac4_box | `https://oderest.rsl.wustl.edu/live2/?query=product&results=m&output=JSON&odemetadb=moon&ihid=LRO&iid=LROC&pt=EDRNAC4&minlat=-69.9&maxlat=-68.7&westernlon=31.9&easternlon=32.8&limit=1000` | `ode/edrnac4_vikram_box.json` | VALIDATED (HTTP 200, 1 786 728 B, 380 products with `Product_name`, `Incidence_angle`, `UTC_start_time`) | 1.8 MB |
| edr_le_label | `https://pds.lroc.im-ldi.com/data/LRO-L-LROC-2-EDR-V1.0/LROLRC_0056A/DATA/ESM5/2023184/NAC/M1442997156LE.xml` (follows a 302) | `edr/M1442997156LE.xml` | VALIDATED | 12 497 B |
| edr_re_label | same directory, `M1442997156RE.xml` | `edr/M1442997156RE.xml` | VALIDATED | 12 499 B |
| tc_ortho_n | `https://data.darts.isas.jaxa.jp/pub/pds3/sln-l-tc-5-ortho-map-v2.0/lon030/data/TCO_MAP_02_S66E030S69E033SC.img` and `.lbl` | `selene_tc_ortho/` | VALIDATED | 301 989 888 B + 3.4 KB |
| tc_ortho_s | same directory, `TCO_MAP_02_S69E030S72E033SC.img` and `.lbl` | `selene_tc_ortho/` | VALIDATED | 301 989 888 B + 3 512 B |
| tc_dtm_s | `https://data.darts.isas.jaxa.jp/pub/pds3/sln-l-tc-5-dtm-map-v2.0/lon030/data/DTM_MAP_02_S69E030S72E033SC.img` and `.lbl` | `selene_tc_dtm/` | DOCUMENTED | ODE lists 288 001 KB |
| tc_dtm_n | same directory, `DTM_MAP_02_S66E030S69E033SC.img` and `.lbl` | `selene_tc_dtm/` | DOCUMENTED | same |
| tc_morning_s | `https://data.darts.isas.jaxa.jp/pub/pds3/sln-l-tc-5-morning-map-v4.0/lon030/data/TCO_MAPm04_S69E030S72E033SC.img` and `.lbl` | `selene_tc_morning/` | DOCUMENTED | same |
| spice_lsk | `https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls` | `data/raw/reference/spice/naif0012.tls` | VALIDATED (HTTP 200, 5 257 B, architect HEAD 2026-09-30) | 5 KB |
| spice_pck | `https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc` | `data/raw/reference/spice/pck00011.tpc` | VALIDATED (HTTP 200, 131 226 B, 2026-09-30) | 128 KB |
| spice_de440s | `https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp` | `data/raw/reference/spice/de440s.bsp` | VALIDATED (HTTP 200, 32 726 016 B, 2026-09-30) | 31 MB |
| tc_evening_s | `https://data.darts.isas.jaxa.jp/pub/pds3/sln-l-tc-5-evening-map-v4.0/lon030/data/TCO_MAPe04_S69E030S72E033SC.img` and `.lbl` | `selene_tc_evening/` | DOCUMENTED | same |
Rules: DARTS serves no range requests (whole-file downloads only) and rate-limits bursts with HTTP 503 → **≥ 30 s between any two DARTS requests**, one attempt per URL per session, a 503 is recorded as a failure (C08 `failures`) and not retried in the same session. ODE/PDS requests: ≥ 3 s apart. All `save as` paths are relative to `data/raw/reference/` except `ode/` and `edr/`, which are under `data/raw/reference/lro_nac_vikram/`.

### 2.3 Finding TMC-2 / IIRS products over Vikram
Vikram box (PROVENANCE.json `target_box_deg`): lat −69.9 … −68.7, lon 31.9 … 32.8 (east-positive). Landing site ≈ 69.37 °S, 32.32 °E.
The human saves the ISSDC map-browse catalogue layers for TMC-2 and IIRS as GeoJSON into `data/raw/catalogue/` (same method as the three OHRC layers already there). The session then lists intersecting products with:
```bash
.venv/bin/python - <<'PY'
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location("fc", "scripts/fetch_catalogue.py"); fc = importlib.util.module_from_spec(spec); spec.loader.exec_module(fc)
for path in sorted(pathlib.Path("data/raw/catalogue").glob("*.geojson")):
    diag = fc.Diagnostics()
    rows = list(fc.read_issdc_catalogue(path, path.stem, diag, box=(-69.9, -68.7, 31.9, 32.8)))
    print(path.name, len(rows)); [print("  ", r["product_id"], r["download_name"], r["start_time"]) for r in rows]
    print(diag.report())
PY
```
Products are listed newest first per instrument; the human picks from that list.

### 2.4 What P1.DL fetched (2026-09-30; accepted by the human 2026-10-01)
Source: the implementer's measurements (`du -sb`, rasterio metadata) in `.fable/inbox_P1DL_20260930.md`, M. The manifest records 206 files, 0 failures; `check_P1.DL.sh` passed.
| product / path | bytes on disk (unpacked) | note |
|---|---|---|
| 4 OHRC `ncp` (§2.1 rows 1–4) | 4 501 254 471 total | ≈ 1.1 GB each; zips 0.64–0.88 GB |
| TMC-2 `ch2_tmc_ncn_20230521T0857294318_d_img_d32` | 2 503 368 021 | calibrated nadir; covers ≈ 90 % of the Vikram box (no calibrated nadir strip covers all of it) |
| TMC-2 `ch2_tmc_ncf_20231026T0943001971_d_img_d18` | 1 538 596 989 | calibrated fore view, 100 % cover |
| TMC-2 `ch2_tmc_ndn_20231027T1315134884_d_oth_d18` | 14 725 094 611 | derived ortho: one GeoTIFF 176 604 × 41 628 px, uint16, 1-row strips, uncompressed, **no declared nodata**, 5 m — read only per G40 |
| TMC-2 `ch2_tmc_ndn_20231027T1315134884_d_dtm_d18` | 3 694 054 398 | derived DTM: 88 302 × 20 813 px, int16, 1-row strips, nodata −32768, 10 m — read only per G40 |
| IIRS `ch2_iir_nci_20230125T1944138897_d_img_d32`, `ch2_iir_nci_20221226T0416479474_d_img_d32` | 3 330 518 673 + 4 204 408 890 | calibrated, both 100 % cover |
| `data/raw/ch2/_zips/` | 10 912 061 125 | every PRADAN zip (§1 rule) |
| SELENE TC tiles, shapefiles, ODE JSON, EDR labels | 1 811 960 315 + 38 037 528 + 1 811 724 | §2.2 / §1 |
Other P1.DL deviations (for the Phase 1 review pack): products were found from PRADAN's footprint shapefiles rather than §2.3's GeoJSON; the session drove PRADAN's logged-in pages and generated PRADAN's bulk-download scripts, which the human ran — beyond CLARIFY R6, chosen by the human in that session; CLARIFY R7's further NAC ortho/DTM search was not run.

## 3. P1.DL session procedure (human-in-the-loop, no code changes, no git)
1. Print §2.1 and ask the human to confirm free disk ≥ 20 GB (`df -h data/raw`). Print `du -sb data/raw`. **Budget (CLARIFY Q17, revised 2026-10-01):** `data/raw/` total ≤ 60 000 000 000 B. Before each download, state its zip size; after each unpack, print `du -sb data/raw`; if the total exceeds the budget, or the next download would make it exceed, stop and ask the human before continuing. A pick outside §2.1's per-row limits also needs the human's explicit yes, recorded in the session summary.
2. PRADAN: tell the human, step by step: open `https://pradan.issdc.gov.in/ch2/` → log in → "Browse" → OHRC (`https://pradan.issdc.gov.in/ch2/protected/browse.xhtml?id=ohrc`) → search each zip name of §2.1 rows 1–4 → download → move the zip to `data/raw/ch2/_zips/`. The session never uses the human's login and never automates the page; it reads only what the human pastes or shows.
3. For TMC-2/IIRS: ask the human to save the catalogue GeoJSON layers (§2.3), run the snippet, show the list, and name at most 2 TMC-2 and 1 IIRS product to download the same way.
4. Unpack every zip per §1 (`unzip -n`).
5. Public files: run, one at a time with the pacing in §2.2, `curl -fL --retry 2 --retry-delay 30 -o <dest> <url>`; on failure record it (step 6) and continue.
6. Record every file (including every unpacked file of each product) in `data/raw/DOWNLOADS.json` per C08. Save this script once as `data/raw/.tools/record_download.py` (under `data/raw`, gitignored; it creates the manifest when absent and replaces an existing entry with the same path):
```python
import hashlib, json, os, sys, datetime, pathlib
man = pathlib.Path("data/raw/DOWNLOADS.json")
doc = json.loads(man.read_text()) if man.exists() else {"schema": 1, "files": [], "failures": []}
path, source, product_id, instrument, role, url = sys.argv[1:7]
p = pathlib.Path(path); h = hashlib.sha256()
if role == "auto":
    n = p.name.lower()
    role = ("geometry" if "_g_grd_" in n else "browse" if n.endswith((".png", ".jpg", ".jpeg"))
            else "label" if n.endswith((".xml", ".lbl")) else "data" if n.endswith((".img", ".qub", ".tif", ".dat"))
            else "misc")
with open(p, "rb") as fh:
    for chunk in iter(lambda: fh.read(1 << 20), b""): h.update(chunk)
entry = {"path": p.as_posix(), "bytes": p.stat().st_size, "sha256": h.hexdigest(), "source": source,
         "url": None if url in ("", "-") else url, "product_id": product_id, "instrument": instrument,
         "role": role, "downloaded_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "recorded_by": "P1.DL"}
doc["files"] = [f for f in doc["files"] if f["path"] != entry["path"]] + [entry]
tmp = man.with_name(".DOWNLOADS.json.tmp"); tmp.write_text(json.dumps(doc, indent=2, sort_keys=True)); os.replace(tmp, man)
print("recorded", entry["path"], entry["bytes"])
```
Invocation: `.venv/bin/python data/raw/.tools/record_download.py <path> <source> <product_id> <instrument> <role> <url or ->`; for an unpacked product: `find data/raw/ch2/ohrc/<stem> -type f -print0 | while IFS= read -r -d '' f; do .venv/bin/python data/raw/.tools/record_download.py "$f" PRADAN <stem> OHRC auto -; done` (`auto` applies the role rule). Role rule: `.img`/`.qub`/`.tif` = `data`, `.xml`/`.lbl` = `label`, `*_g_grd_*` = `geometry`, browse PNG/JPG = `browse`, zip = `misc`.
7. Print a final table: file count and bytes per instrument, failures, and what is still missing from §2.1.
The session writes only under `data/raw/**` and `docs/external/**`; it does not edit `STATUS.md`, commit, or touch code.

## 4. P1.01 — `src/lunar_reg/ingest/downloads.py` + `scripts/verify_downloads.py`
- `DEFAULT_MANIFEST = Path("data/raw/DOWNLOADS.json")`.
- `DownloadEntry` dataclass with exactly the C08 file keys; `DownloadManifest(files: list[DownloadEntry], failures: list[dict], schema: int = 1)` with `load(path)` (missing file → empty manifest) and `save(path)` (atomic, `indent=2`, `sort_keys=True`).
- `record_file(...)`: computes size + sha256 streaming 1 MiB chunks; `path` stored relative to the current working directory (the repo root in normal use) as POSIX — a path outside the cwd raises `ValueError`; replaces an existing entry with the same path; `downloaded_utc` = now in `%Y-%m-%dT%H:%M:%SZ`.
- `record_failure(url, http_status, error, manifest)`: appends to `failures`.
- `verify_downloads(...)`: per entry → OK / MISSING / SIZE_MISMATCH / HASH_MISMATCH (hash only when `check_hash`); each `failures` entry → one HTTP_ERROR record; when `scan_unrecorded`, every regular file under `raw_root` (excluding `DOWNLOADS.json`, `.gitkeep`, `data/raw/.tools/**`, and anything under `data/raw/ohrc_vikram/`, `data/raw/reference/jaxa_selene_tc*`, `data/raw/reference/lro_wac/`, `data/raw/reference/lro_nac_vikram/*.IMG|*.xml|*.TIF|PROVENANCE.json`, `data/raw/catalogue/` — the pre-plan files) that no entry names → UNRECORDED. Returns `DownloadDiagnostics` (classified-outcomes skill: counts, first sample per status, `report()`).
- CLI `scripts/verify_downloads.py [--manifest PATH] [--no-hash] [--no-scan]`: prints `report()`; exit 1 if any `is_failure` status was recorded, else 0.
- Nothing is ever deleted or moved by the verifier.

## 5. P1.02 — `scripts/fetch_public.py`
CLI: `python scripts/fetch_public.py [--only KEY[,KEY]] [--dry-run] [--manifest PATH]`. The URL table is a module-level tuple `SOURCES` of `(key, url, dest, status, host)` holding exactly the §2.2 rows (one row per file; `.img` and `.lbl` of one tile share the key, e.g. `tc_ortho_n`, so `--only tc_ortho_n` fetches both). `dest` is the full repo-relative path (e.g. `data/raw/reference/selene_tc_ortho/TCO_MAP_02_S66E030S69E033SC.img`); `status` is `"VALIDATED"` or `"DOCUMENTED"`; `host` is the URL's host name. The module imports `urllib.request` and `time` at top level and exposes `main(argv: list[str] | None = None) -> int` (test seams).
| rule | behaviour |
|---|---|
| HTTP | `urllib.request` with `User-Agent: lunar-reg-fetch/1 (SIH26166)`, timeout 120 s, streaming to `<dest>.part`, then `os.replace` |
| resume | a complete `dest` already recorded in DOWNLOADS.json with matching size → `SKIPPED_PRESENT`; no range requests (DARTS has none) |
| pacing | `time.sleep` so that consecutive requests to the same host are ≥ 30 s apart for `data.darts.isas.jaxa.jp` and ≥ 3 s otherwise |
| outcome enum | `FetchStatus`: `DOWNLOADED`, `SKIPPED_PRESENT`, `HTTP_ERROR`, `NETWORK_ERROR`, `SIZE_MISMATCH` (Content-Length vs bytes written), `DRY_RUN` |
| recording | every DOWNLOADED file → `downloads.record_file(..., recorded_by="fetch_public")`; every HTTP/network error → `downloads.record_failure(...)` |
| report | counts per `FetchStatus` + first sample, printed every run; exit 1 when any HTTP_ERROR/NETWORK_ERROR/SIZE_MISMATCH occurred on a VALIDATED row, else 0 |
| `--dry-run` | prints the plan (key, url, dest, pacing) and makes no request |
Tests (`tests/test_fetch_public.py`) monkeypatch `urllib.request.urlopen` and `time.sleep`; they never touch the network.
**Run step (network, allowed by CLAUDE.md):** after the check passes, run `.venv/bin/python scripts/fetch_public.py --only ode_edrnac4_box,edr_le_label,edr_re_label,tc_ortho_n,tc_ortho_s,spice_lsk,spice_pck,spice_de440s`, then `.venv/bin/python scripts/verify_downloads.py --no-scan`, and paste both reports into `STATUS.md` notes (≤ 5 lines). The DOCUMENTED rows are fetched only when the human asks.
