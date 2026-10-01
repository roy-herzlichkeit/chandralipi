# Datum: what "a position on the Moon" means in this project

This page explains the coordinate convention every lunar position in this
project uses, where each part of it comes from, and how it is checked. It
assumes no background in geodesy; every term is defined where it first appears.

Decision record: `DECISIONS.md` G13. Design: `Phase_1/LLD/datum.md`. Code:
`src/lunar_reg/constants.py`. Test: `tests/test_datum.py`.

---

## 1. What a datum is

A **datum** is the agreement that turns a pair of numbers (latitude, longitude)
into one exact place on a body. It fixes three things: the **shape** used to
model the body (here a **sphere**, a perfect ball with one radius), the
**latitude type** (how "degrees north or south" is measured), and the
**longitude direction** (whether longitude grows towards the east or towards
the west, and in which range it is written).

- **Latitude** is the angle north (+) or south (−) of the equator.
- **Longitude** is the angle around the equator from the prime meridian, the
  agreed zero line.
- **Planetocentric latitude** is measured from the centre of the body.
  **Planetographic latitude** is measured from the local surface normal (the
  direction straight "up" from the ground). On a flattened body the two differ;
  on a sphere the surface normal points exactly through the centre, so the two
  are **identical**. That is why this project's latitude type is not an open
  question as long as the Moon is modelled as a sphere.
- **East-positive** longitude grows towards the east; **west-positive**
  longitude grows towards the west. The same point has different numbers in the
  two systems.

Example (illustrative arithmetic, not a measurement): a crater at 32.32 °E in
an east-positive system is written 327.68 °W in a west-positive 0–360 system,
because 360 − 32.32 = 327.68. Read with the wrong convention, the same pair of
numbers names a place on the other side of the prime meridian, tens of degrees
away. Getting this wrong does not produce a small error; it puts the image on
a different part of the Moon.

Two ways of writing an east-positive longitude are in use:

- the **0–360 range**: every longitude is in [0, 360);
- the **−180–180 range**: every longitude is in [−180, 180).

They name the same points; `lon_to_360` and `lon_to_180` in
`src/lunar_reg/constants.py` convert between them.

---

## 2. What this project assumes

Every item carries a `ValueSource` (the project's provenance enum,
`src/lunar_reg/provenance.py`): `DOCUMENTED` means read from an external
document or label; `INFERRED` means reasoned or chosen by this project, not
confirmed by an external document or a test; `MEASURED` means produced by a run
in this repo.

| item | value | `ValueSource` | where it comes from |
|---|---|---|---|
| shape | sphere, flattening 0 | DOCUMENTED for the NAC; INFERRED for Chandrayaan-2 | `MOON_FLATTENING` in `src/lunar_reg/constants.py`; NAC label `cart:Geodetic_Model` has equal a/b/c axes (`data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml`) |
| radius | 1737400 m | DOCUMENTED for the NAC; INFERRED for Chandrayaan-2 | `MOON_RADIUS_M` in `src/lunar_reg/constants.py`; NAC label `cart:a_axis_radius` = 1737.4 km (`data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml`) |
| latitude type | planetocentric = planetographic (sphere) | DOCUMENTED for the NAC; INFERRED for Chandrayaan-2 | NAC label `cart:latitude_type` = Planetocentric (same NAC label); on a sphere the two latitude types coincide, so the Chandrayaan-2 side follows from the shape row |
| longitude direction | east-positive (`LONGITUDE_DIRECTION = "east"`) | INFERRED (`DATUM_SOURCE`) | NAC label `cart:longitude_direction` = Positive East (same NAC label); the OHRC labels carry no datum block, so the Chandrayaan-2 side is inferred until the §3 test or an ISRO document confirms it |
| internal longitude range | [0, 360) (`LONGITUDE_RANGE = "0_360"`) | INFERRED (a project convention, not taken from an external document) | `src/lunar_reg/constants.py`; values are converted with `lon_to_360` / `lon_to_180` at input and output |

In code, the whole assumption is summarised by `DATUM_SOURCE =
ValueSource.INFERRED` and `DATUM_NOTE` in `src/lunar_reg/constants.py`.
`DATUM_SOURCE` stays `INFERRED` until an ISRO Software Interface Specification
(SIS) or the §3 test confirms the Chandrayaan-2 side (G13).

---

## 3. How the data test checks it

`tests/test_datum.py::test_east_positive_longitudes_on_real_ohrc_grid_and_nac`
is marked `@pytest.mark.data`: it runs only when the real products are on disk
and skips, naming the missing path, otherwise. Run it with
`.venv/bin/python -m pytest tests/test_datum.py -s`.

Inputs: the calibrated OHRC product `ch2_ohr_ncp_20240425T1406019344_d_img_d18`
(its geometry grid CSV and its image label, under `data/raw/ch2/ohrc/`) and the
LRO NAC orthoimage label
`data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml`.

- A **geometry grid** is a table shipped with each calibrated Chandrayaan-2
  product that gives the ground (latitude, longitude) of image positions on a
  regular grid of lines and samples.
- An **orthoimage** is an image resampled onto a map projection, so every
  pixel has a known ground position; the NAC orthoimage's georeference is read
  from its own label (`lunar_reg.ingest.lro.georeference_from_label`).

Steps:

1. Take the 25 nodes of a 5×5 sub-grid of the OHRC geometry grid.
2. Map their (longitude, latitude) into NAC pixel positions with
   `GeoReference.lonlat_to_pixel`.
3. Assert that all 25 land inside the NAC raster: read east-positive, the
   OHRC strip sits on the NAC image.
4. **Mirror test**: map (−longitude, latitude) and (360 − longitude, latitude),
   the readings a west-positive convention would give, and assert that every
   mirrored point lands **outside** the NAC raster. Steps 3 and 4 together are
   what distinguishes east-positive from west-positive.
5. Compare two predictions of where the strip lies in the NAC: the geometry
   grid's, and the bilinear interpolation of the four label corner coordinates
   that `scripts/run_vikram.py` uses as its starting guess. The test prints one
   line starting `MEASURED grid-vs-corner offset (m)`: the median distance in
   metres over the 25 sub-grid image positions, and the distance at the strip
   centre. It asserts only a loose sanity bound (`MAX_GRID_VS_CORNER_OFFSET_M`
   in the test); the label corners are known to be off, so this number is a
   measure of the label-corner error, not of the datum.

Measured grid-vs-corner offset: [INSERT RESULT] (recorded by P1.20 with the
artefact path it is read from).

---

## 4. What would change the assumption

- An ISRO SIS or other Chandrayaan-2 document stating a different radius, an
  ellipsoid (a flattened shape) instead of a sphere, or west-positive
  longitudes. Place such a document under `docs/external/` (CLARIFY R2) and
  raise it through `QUESTIONS.md`; the constants in
  `src/lunar_reg/constants.py` and this page change only through that route.
- The §3 data test failing on a strip: an OHRC grid that lands outside the NAC
  raster read east-positive, or a mirrored reading that lands inside it.
- Either confirmation (a document or a passing §3 test recorded by a later
  prompt) is what moves `DATUM_SOURCE` away from `INFERRED`.
