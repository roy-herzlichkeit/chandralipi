# LLD — rendered reference preparation and azimuth-frame calibration (P1B.02)

TBD 1.8 step 2 + experiment 3. Uses C10, C11, C13, C21.

## 1. The azimuth-frame problem
**Primary source since review RC17 (G14 revised):** P1.20 writes `data/processed/vikram/reference_sun/label_convention.json` from SPICE (COMPUTED). When that file exists, the bridge uses its convention and converts north-clockwise azimuths to the NAC grid frame with `ingest.sun.north_to_grid_azimuth`. `calibrate_label_azimuth` below is the independent cross-check (and the fallback when the SPICE file is absent); its result is still written and compared.

The OHRC label gives `sun_azimuth` but not its reference direction or sense (`azimuth_frame = "label_unverified"`, C13). The renderer needs the azimuth in the NAC grid frame (clockwise from grid-up). The 2024 anchor strip is registered (P1.19/P2.11), so its OHRC window can be warped onto the NAC grid and its sun azimuth **fitted** there; comparing with its label value decides the convention.

## 2. `pairs.py` additions
```python
AZIMUTH_CONVENTIONS = ("as_is", "plus_180", "mirror", "mirror_plus_180")
# as_is: a ; plus_180: a + 180 ; mirror: 360 − a ; mirror_plus_180: 180 − a   (all mod 360)
@dataclass(frozen=True)
class AzimuthCalibration:
    convention: str; offset_deg: float; fitted_grid_azimuth_deg: float; label_azimuth_deg: float
    residual_deg: float; peak_margin: float; source: ValueSource   # always INFERRED
    def to_grid(self, label_azimuth_deg: float) -> float   # convention(label) + offset, mod 360
def dtm_on_reference_grid(dtm_path, reference_geo: GeoReference, pair: WindowPair) -> tuple[np.ndarray, np.ndarray]
def calibrate_label_azimuth(anchor: PairResult, anchor_pair: WindowPair, dtm_path, reference_geo, label_azimuth_deg, label_elevation_deg) -> AzimuthCalibration
def prepare_rendered_pair(pair: WindowPair, dtm_path, reference_geo, sun_grid: SunGeometry) -> PrepOutcome
```
- `dtm_on_reference_grid`: reproject the DTM GeoTIFF (its own transform; same projection as the NAC) onto the pair's working reference grid: `dst_transform = Affine(fx·psx, 0, x0 + c0·psx, 0, −fy·psy, y0 − r0·psy)` where `(c0, r0)` is `pair.reference_window[:2]` reversed (col, row), `(fx, fy)` the actual resize ratios, `(x0, y0, psx, psy)` from `reference_geo`; bilinear; returns `(heights, valid)` with NaN outside. Posting of the result = `fx · psx` metres.
- `calibrate_label_azimuth`: warp `anchor_pair.source` (the anchor's working-GSD source window, re-prepared with its stored shift — never the stored thumbnail, review RC15) into the reference working grid with `anchor.transform` (`cv2.warpPerspective`, validity mask warped nearest); `fit = ingest.sun.fit_sun_azimuth(heights, posting, warped, label_elevation_deg, valid=mask & valid)`; for each convention compute `c(label)`; choose the convention minimising the circular distance to `fit.azimuth_deg`; `offset = circular_signed(fit.azimuth_deg − c(label))`; `residual_deg = |offset|`. A residual > 20° → still returned, and the caller records it (the doc must say the calibration is weak).
- `prepare_rendered_pair`: heights via `dtm_on_reference_grid`; `render_shaded_relief(heights, posting, sun_grid.azimuth_deg, sun_grid.elevation_deg, nodata=None)`; returns a copy of `pair` with `reference` = the render, `reference_valid` = DTM validity, `provenance["reference"] = "rendered_dtm"`, `provenance["sun"] = sun_grid.azimuth_source.value`; all geometry fields unchanged (same grid). `sun_grid.as_tuple()` is None → `PrepOutcome(PrepStatus.EMPTY_REFERENCE, None, "no sun geometry for rendering")`.

## 3. Tests (`tests/test_rendered_reference.py`)
Synthetic: a terrain DTM written as a GeoTIFF in `tmp_path` in the NAC projection, a `GeoReference` for a 1 m grid covering it, a `WindowPair` built by hand; `dtm_on_reference_grid` returns the right shape and matches a direct resample at 5 random points (±1e-6 relative); `calibrate_label_azimuth` on an "anchor" whose source is the DTM shaded at grid azimuth 120° with a label azimuth of 60° (conventions give as_is 60°, plus_180 240°, mirror 300°, mirror_plus_180 120°, so exactly one matches) → convention `mirror_plus_180`, |offset| ≤ 2°; `prepare_rendered_pair` keeps geometry and swaps the reference.
