# LLD — datum convention + data test (P1.07)

Closes: TBD 1.5. Decision: G13. Evidence: `constants.py:16-17` (sphere R = 1 737 400 m, flattening 0); NAC label `cart:Geodetic_Model` (Planetocentric, a = b = c = 1737.4 km, Positive East — read 2026-09-29); OHRC nrp label corner longitudes ≈ 32 °E at Vikram (east-positive reading, FABLE_NOTES §3). On a sphere planetocentric and planetographic latitudes are identical (FABLE_NOTES §9, standard geometry), so the open items are only radius and longitude direction/range.

## 1. `constants.py` additions
```python
LONGITUDE_DIRECTION = "east"            # positive east
LONGITUDE_RANGE = "0_360"               # internal storage range
DATUM_SOURCE = ValueSource.INFERRED     # until an ISRO SIS or the §3 test confirms it (G13)
DATUM_NOTE = "sphere R=1737400 m; planetocentric=planetographic on a sphere; east-positive; see docs/DATUM.md"
def lon_to_360(lon) -> np.ndarray | float   # ((lon % 360) + 360) % 360, vectorised, NaN preserved
def lon_to_180(lon) -> np.ndarray | float   # ((lon + 180) % 360) - 180, vectorised, NaN preserved
```
No existing constant changes value.

## 2. `docs/DATUM.md` (new, human-facing, G26: define every term)
Sections: what a datum is (one paragraph + example: the same crater at 32.32 °E written as 327.68 °W); what this project assumes (§1 table with `ValueSource` per item); how the §3 test checks it and what its printed numbers mean; what would change the assumption (an ISRO SIS stating another radius or west-positive longitudes; place the SIS under `docs/external/` per R2). Numbers only with artefact paths (G19); the §3 offset is `[INSERT RESULT]` until P1.20 records it.

## 3. Data test (`tests/test_datum.py`, `@pytest.mark.data`)
Inputs: the calibrated OHRC product `ch2_ohr_ncp_20240425T1406019344_d_img_d18` (grid + label) and the NAC ortho label. Skip with a reason naming the missing path when either is absent.
1. Read the geometry grid; take the 25 nodes of a 5×5 sub-grid of image positions.
2. Map their (lon, lat) through `GeoReference.lonlat_to_pixel` of the NAC (C10).
3. Assert all 25 land inside the NAC raster.
4. Mirror test: map `(−lon, lat)` and `(360 − lon, lat)`; assert every mirrored point lands **outside** the raster (this is what distinguishes east-positive from west-positive at 32 °E).
5. Compute the median distance in metres between the grid-predicted NAC position of the strip centre and the label-corner (bilinear) prediction used by `scripts/run_vikram.py`; print it with the label "MEASURED grid-vs-corner offset (m)"; assert it is < 5000 m (sanity only — the label corners are known to be ~2.9 km off, FABLE_NOTES §5).
The printed number is not written into any doc by this prompt.
