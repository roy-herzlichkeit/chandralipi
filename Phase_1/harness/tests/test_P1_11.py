"""P1.11 — sun geometry extras (Phase_1/LLD/sun_geometry.md). Protected (G05)."""

from __future__ import annotations

import numpy as np
import pytest
from _h1 import REPO


def test_shade_shape_and_nan():
    from lunar_reg.ingest.sun import lambert_shade

    dtm = np.random.default_rng(0).normal(0, 5, (32, 32))
    dtm[0, 0] = np.nan
    s = lambert_shade(dtm, 3.0, 90.0, 20.0)
    assert s.dtype == np.float32 and s.shape == dtm.shape
    assert np.isnan(s[0, 0]) and np.nanmin(s) >= 0 and np.nanmax(s) <= 1


def test_flat_dtm_brightness_is_sin_elevation():
    from lunar_reg.ingest.sun import lambert_shade

    s = lambert_shade(np.zeros((8, 8)), 3.0, 45.0, 30.0)
    assert np.allclose(s, np.sin(np.radians(30.0)), atol=1e-6)


def test_east_facing_slope_brightest_under_east_sun():
    from lunar_reg.ingest.sun import lambert_shade

    x = np.arange(64, dtype=float)
    dtm = np.tile(-0.5 * x, (64, 1))  # height falls eastward -> slope faces east
    east = float(np.nanmean(lambert_shade(dtm, 1.0, 90.0, 20.0)))
    west = float(np.nanmean(lambert_shade(dtm, 1.0, 270.0, 20.0)))
    assert east > west


def test_shape_mismatch_raises():
    from lunar_reg.ingest.sun import fit_sun_azimuth

    with pytest.raises(ValueError):
        fit_sun_azimuth(np.zeros((10, 10)), 3.0, np.zeros((10, 11)), 20.0)


def test_sun_from_label_stub():
    from lunar_reg.ingest.sun import sun_from_label
    from lunar_reg.provenance import ValueSource

    class P:
        values = {"sun_azimuth_deg": 303.87, "sun_elevation_deg": 11.53}

        def __getitem__(self, k):
            return self.values.get(k)

    s = sun_from_label(P())
    assert s.as_tuple() == pytest.approx((303.87, 11.53))
    assert s.azimuth_source is ValueSource.DOCUMENTED and s.azimuth_frame == "label_unverified"


def test_script_exists_with_cli():
    text = (REPO / "scripts/fit_reference_sun.py").read_text()
    for flag in ("--nac", "--half-size-m", "--out", "--kernels", "--label-convention"):
        assert flag in text
    assert "edrnac4_vikram_box.json" in text and "run_record" in text
    assert "sun_from_spice" in text and "label_convention.json" in text


def test_north_to_grid_on_central_meridian():
    from lunar_reg.ingest.sun import north_to_grid_azimuth

    proj = "+proj=stere +lat_0=-90 +lat_ts=-69.3 +lon_0=32.3 +R=1737400 +units=m +no_defs"
    assert north_to_grid_azimuth(123.0, -69.37, 32.3, proj) == pytest.approx(123.0, abs=1e-6)
    off = north_to_grid_azimuth(123.0, -69.37, 42.3, proj)
    assert abs(((off - 123.0 + 180) % 360) - 180) > 1.0   # 10 deg off-meridian -> visible rotation


def test_spice_extra_declared():
    import tomllib

    extras = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]["optional-dependencies"]
    assert any("spiceypy" in d for d in extras["spice"])
