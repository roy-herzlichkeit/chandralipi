# Getting ISRO and NASA data for the same patch of the Moon

This document explains how to obtain Chandrayaan-2 imagery (ISRO) and Lunar
Reconnaissance Orbiter imagery (NASA) that cover **the same ground**, which is
the precondition for everything else this project does.

It assumes no background in planetary data archives. Terms are defined where
they first appear.

---

## 1. The mistake this replaces

Until 2026-09-28 the working method was: download products, parse their labels,
then discover where they are. That produced 6.6 GB of Chandrayaan-2 data sitting
in **three disjoint regions** of the Moon — OHRC near −85°, TMC-2 around −2° to
−30°, IIRS around −4° to 31° — with no two instruments closer than about 65° of
longitude. Zero cross-instrument pairs were possible. The recorded fix was to
re-download roughly 975 GB into 832 GB of free space, which cannot complete.

That was never necessary. Both archives publish a **catalogue**: a queryable
index of every product's *footprint* — the outline on the lunar surface that a
product covers — with no image data attached. The entire Chandrayaan-2 optical
catalogue is a few megabytes.

The correct order is therefore:

> **catalogue → intersect → download only what overlaps**

---

## 2. The two archives

### ISRO — ISSDC "Chandrayaan Orbiter Data Map Browse"

<https://chmapbrowse.issdc.gov.in> — a map interface, but underneath it runs a
**GeoServer**, standard geospatial-server software that exposes a **WFS** (Web
Feature Service): an API that returns map features as data rather than pictures.

Layers are named by instrument and projection:

```
moon:ins:ch2_ohr_cal            equatorial   (degrees)
moon:ins:np:ch2_ohr_cal_np      north pole   (metres)
moon:ins:sp:ch2_ohr_cal_sp      south pole   (metres)
```

Substitute `ch2_tmc` (Terrain Mapping Camera 2), `ch2_iir` (Imaging Infrared
Spectrometer), `ch2_sar`. Suffixes: `_cal` calibrated, `_raw`,
`_derived_ortho`, `_derived_dtm`.

Catalogue sizes, measured 2026-09-28:

| Instrument (calibrated) | equatorial | north | south | total |
|---|---|---|---|---|
| OHRC | 76 | 3 | 273 | ~352 |
| TMC-2 | 8,457 | 1,241 | 1,221 | ~10,919 |
| IIRS | 1,358 | 502 | 337 | ~2,197 |

OHRC has only ~352 products in the entire mission and 273 are south polar. Its
coverage is not a representative sample of the Moon; it is a landing-site
instrument.

**The WFS requires your login session.** Anonymous `curl` returns HTTP 302 to a
login page. Run catalogue pulls from the browser console while signed in:

```javascript
const layers = ['moon:ins:ch2_iir_cal','moon:ins:sp:ch2_iir_cal_sp','moon:ins:np:ch2_iir_cal_np'];
for (const L of layers) {
  const u = '/server/moon/wfs?SERVICE=WFS&VERSION=1.1.0&REQUEST=GetFeature'
          + '&typeName=' + encodeURIComponent(L)
          + '&outputFormat=application/json&maxFeatures=20000';
  const j = await (await fetch(u, {credentials:'include'})).text();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([j], {type:'application/json'}));
  a.download = L.replace(/:/g,'_') + '.geojson'; a.click();
  console.log(L, j.length, 'bytes');
}
```

Save the files into `data/raw/catalogue/`.

> Set `maxFeatures` above the expected count and then check that the returned
> `totalFeatures` equals the number of features you actually got. If it is
> larger, the response was truncated and your catalogue is silently incomplete.

### NASA — ODE (Orbital Data Explorer)

<https://oderest.rsl.wustl.edu/live2/> — no account, no login.

Two parameter details that are easy to get wrong:

- the database selector is **`odemetadb=moon`**, not `target=moon`;
- `ihid`, `iid` and `pt` are all **mandatory** together.

Verified LROC product types (`iid=LROC`), from ODE's own `query=iipy` dump:

| `pt` | meaning | count |
|---|---|---|
| `CDRNAC4` | NAC calibrated — **not** map-projected | 2,899,891 |
| `EDRNAC4` | NAC raw — **not** map-projected | 2,903,649 |
| `CDRWAM4` | WAC calibrated, mono | 374,326 |
| `SDNDTM` | NAC terrain model **+ map-projected orthoimages** | 668 |
| `SDPPHO` | NAC map-projected photometric | 765 |
| `BDRNPL` | NAC polar mosaics | 1,752 |

Example footprint query:

```bash
curl -s "https://oderest.rsl.wustl.edu/live2/?query=product&results=m&output=JSON\
&odemetadb=moon&ihid=LRO&iid=LROC&pt=CDRNAC4\
&minlat=-69.9&maxlat=-68.7&westernlon=31.9&easternlon=32.8&limit=1000"
```

Use `results=c` for a count only, `results=m` for metadata. **Avoid
`results=fmp`** on large queries: it appends the per-product file list and
overruns a few megabytes, truncating the JSON mid-string.

---

## 3. Three traps

### 3.1 The polar layers are in metres, not degrees

ISSDC publishes three coordinate reference systems:

| EPSG | meaning | units |
|---|---|---|
| 100009 | equatorial | degrees (lon, lat) |
| 100010 | north polar stereographic | **metres** |
| 100011 | south polar stereographic | **metres** |

A record from a polar layer contains `"UL_LAT": -7284.2642`. That is not a
latitude. Treating it as one puts your footprint somewhere impossible, and
nothing raises an error.

`scripts/fetch_catalogue.py` handles this. Its inverse projection was validated
against three OHRC products this project had already measured independently from
their real PDS4 labels:

| product | measured from label | from catalogue | agreement |
|---|---|---|---|
| `…T0609041371` | −85.37…−84.55, 78.89 km² | −85.36…−84.55, 79.45 km² | 0.008°, 0.7% |
| `…T1005176450` | −85.33…−84.52, 78.96 km² | −85.32…−84.52, 79.47 km² | 0.008°, 0.7% |
| `…T1203563771` | −85.33…−84.53, 79.33 km² | −85.32…−84.52, 79.83 km² | 0.007°, 0.6% |

Small and systematic, consistent with the catalogue polygon being slightly
generalised relative to the label corners. This is agreement, not identity.

### 3.2 ISSDC illumination angles are placeholders

Every ISSDC record sampled returns `INC_ANGLE = EMI_ANGLE = PHA_ANGLE = 0`. An
incidence angle of zero means the Sun directly overhead; at −69° latitude that
is impossible. These are unpopulated fields, not measurements.

`fetch_catalogue.py` drops them and sets `geometry_resolved = False` on every
ISSDC row. **Never condition an illumination result on an ISSDC row.** Real sun
geometry must come from the PDS4 label of a downloaded product, or from ODE,
which does publish real angles.

### 3.3 Near a pole, a lat/lon bounding box overlaps everything

Within about a degree of a pole, a footprint's longitude range spans nearly the
full circle, so bounding-box intersection reports that everything overlaps
everything. An early run of this analysis produced "100 mutual overlaps" for
polar products; it was an artifact.

Work in projected metres near the poles, or use
`lunar_reg.ingest.overlap.PolarFrame`, which exists for exactly this.

A related point: **bounding-box overlap is an upper bound, not a true
intersection.** OHRC strips are long and diagonal, so their axis-aligned boxes
greatly overstate contact — bbox overlaps of 400+ km² were computed between
footprints whose total area is only ~79 km². Use `overlap.py`'s polygon
intersection for real numbers.

---

## 4. Building a manifest

```bash
.venv/bin/python scripts/fetch_catalogue.py \
  --issdc-dir data/raw/catalogue \
  --box -69.9 -68.7 31.9 32.8 \
  --ode-pt CDRNAC4 --ode-pt SDNDTM \
  --output data/processed/manifest_vikram.parquet
```

The script prints a per-outcome diagnostic report on every run, including counts
of records rejected and a sample of each rejection, so an empty result is never
silent.

Catalogue rows are **weaker evidence than parsed labels**. Columns that can only
come from the file itself — `lines`, `samples`, `bands`, `data_type`,
`image_path` — are left `None` and must be filled by rescanning downloaded
labels through `lunar_reg.ingest.manifest.build_manifest`.

---

## 5. The selected region: the Vikram landing site

**lat −69.9…−68.7, lon 31.9…32.8**

Chosen because Chandrayaan-2's own landing site is imaged repeatedly by OHRC,
and NASA has a map-projected NAC product built specifically for it.

- **ISRO:** 21 OHRC products across 11 dates, 2021-10-23 → 2024-04-25.
  Footprints 65.4–95.3 km². IDs in `data/processed/ohrc_vikram_product_ids.txt`.
- **NASA:** 380 NAC frames, incidence 66.6°–104.5°; plus `NAC_DTM_VIKRAMSITE1`.

Eleven epochs of the same ground is real illumination variation, which is what
problem statement SIH26166 asks the pipeline to be invariant to.

### Why the DTM bundle matters

Plain NAC frames (`CDRNAC4`) open with `crs=None` — raw pushbroom camera
geometry, no map projection — so cropping to a lat/lon overlap requires an
ISIS/SPICE projection step this project has not built. The `SDNDTM` bundle
instead ships **map-projected orthoimages** at 1 m/px. Against OHRC's 0.25 m
that is a 4× scale ratio, inside `MAX_SAFE_SCALE_RATIO = 8.0`.

Downloaded to `data/raw/reference/lro_nac_vikram/` (4.5 GB). See its
`PROVENANCE.json`.

> **Unit warning, flagged not fixed.** GDAL reports the orthoimage transform as
> `3.2978e-05` with CRS unit "Metre". The unit is wrong: the values are
> **degrees**. 23003 px × 3.2978e-05° = 0.7586° → 23.00 km → 1.000 m/px, which
> matches the `100CM` in the filename. Read as metres it would be 0.76 m across
> a 23003 px image. Code that trusts the declared unit mis-scales by ~10⁵.

---

## 6. Downloading the products

**NASA:** direct HTTPS, no login. Files serve `accept-ranges: bytes`, so GDAL
can window-read them over the network without downloading — a 512×512 crop from
a 264 MB NAC frame was read this way in seconds. Prefer that to full downloads.

The origin **rate-limits at roughly 20 requests**, then returns HTTP 429 and
hangs any GDAL retry loop. Both `pds.lroc.im-ldi.com` and `pds.lroc.asu.edu`
redirect to the same origin, so switching mirrors does not help. Use
`wget -c` sequentially with a few seconds' spacing, or `aria2c -x1 -s1
--retry-wait=30`. Do **not** parallelise.

**ISRO:** PRADAN requires a login and delivers carts, not URLs. Search by
product ID at <https://pradan.issdc.gov.in/ch2/>, using
`data/processed/ohrc_vikram_product_ids.txt`. Request tens of products, not
hundreds — the earlier 500-product carts are what produced 975 GB of unrelated
data and a 0-byte tar.

---

## 7. Known gaps

- IIRS and TMC-2 catalogues have **not** been pulled; ISSDC became unreachable
  mid-session. Re-run the console snippet in §2 with `ch2_iir` and `ch2_tmc`.
- No OHRC imagery has been downloaded yet, so no Chandrayaan-2 registration
  result exists.
- The polar mosaic `NAC_POLE_PSR_SOUTH` (14.8 GB, covers −90…−80) was found but
  its CRS and resolution are **unverified** — the probe hit the rate limit.
- The two Vikram orthoimages may or may not differ usefully in illumination;
  their sun geometry has not been read from the labels.
