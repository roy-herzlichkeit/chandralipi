"""NAC georeference from the PDS4 label (CONTRACTS C10, Phase_1/LLD/lro_georeference.md §6).

Synthetic labels reproduce the ``cart:`` elements of the real Vikram NAC label
(``NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml`` lines 111-160); their bounding
coordinates are computed from a known origin so the sign rule has a right answer.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from lunar_reg.ingest.lro import (
    GeoReference,
    LabelGeoreferenceError,
    georeference_from_label,
    lro_to_row,
    read_lro_label,
)
from lunar_reg.provenance import ValueSource

REPO = Path(__file__).resolve().parents[1]
NAC_LABEL = REPO / "data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml"
NAC_PROJ = "+proj=stere +lat_0=-90 +lat_ts=-69.3 +lon_0=32.3 +R=1737400 +units=m +no_defs"
MOON_GEO = "+proj=longlat +R=1737400 +no_defs"
NS = "http://pds.nasa.gov/pds4/pds/v1"
CART_NS = "http://pds.nasa.gov/pds4/cart/v1"

# 1/100-scale NAC raster (100 m pixels) whose true origin is the NAC's negative x.
X0, Y0, W, H = -11043.5, 638258.5, 230, 476


def _bounds(x0: float, y0: float, width: int, height: int, px: float):
    """(west, east, north, south) of the densified raster boundary, lon in [0, 360)."""
    from rasterio.warp import transform

    t = np.linspace(0, 1, 101)
    cols = np.r_[t * width, np.full(101, width), t * width, np.zeros(101)]
    rows = np.r_[np.zeros(101), t * height, np.full(101, height), t * height]
    lon, lat = transform(NAC_PROJ, MOON_GEO, list(x0 + cols * px), list(y0 - rows * px))
    lon = np.mod(lon, 360)
    return float(lon.min()), float(lon.max()), float(np.max(lat)), float(np.min(lat))


def _label(ul_x: float, px: float = 100.0, *, pixel_scale: bool = True) -> str:
    w, e, n, s = _bounds(X0, Y0, W, H, px)
    scale = (
        f'<cart:pixel_scale_x unit="m/pixel">{px}</cart:pixel_scale_x>'
        f'<cart:pixel_scale_y unit="m/pixel">{px}</cart:pixel_scale_y>'
        if pixel_scale
        else ""
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="{NS}" xmlns:cart="{CART_NS}">
  <Identification_Area><logical_identifier>urn:nasa:pds:test:nac</logical_identifier></Identification_Area>
  <Observation_Area><Discipline_Area><cart:Cartography>
    <cart:Spatial_Domain><cart:Bounding_Coordinates>
      <cart:west_bounding_coordinate unit="deg">{w}</cart:west_bounding_coordinate>
      <cart:east_bounding_coordinate unit="deg">{e}</cart:east_bounding_coordinate>
      <cart:north_bounding_coordinate unit="deg">{n}</cart:north_bounding_coordinate>
      <cart:south_bounding_coordinate unit="deg">{s}</cart:south_bounding_coordinate>
    </cart:Bounding_Coordinates></cart:Spatial_Domain>
    <cart:Spatial_Reference_Information><cart:Horizontal_Coordinate_System_Definition><cart:Planar>
      <cart:Map_Projection><cart:map_projection_name>Polar Stereographic</cart:map_projection_name>
        <cart:Polar_Stereographic>
          <cart:longitude_of_central_meridian unit="deg">32.3</cart:longitude_of_central_meridian>
          <cart:latitude_of_projection_origin unit="deg">-69.3</cart:latitude_of_projection_origin>
        </cart:Polar_Stereographic></cart:Map_Projection>
      <cart:Planar_Coordinate_Information><cart:Coordinate_Representation>
        <cart:pixel_resolution_x unit="deg/pixel">3.3e-05</cart:pixel_resolution_x>
        <cart:pixel_resolution_y unit="deg/pixel">3.3e-05</cart:pixel_resolution_y>
        {scale}
      </cart:Coordinate_Representation></cart:Planar_Coordinate_Information>
      <cart:Geo_Transformation>
        <cart:upperleft_corner_x unit="m">{ul_x}</cart:upperleft_corner_x>
        <cart:upperleft_corner_y unit="m">{Y0}</cart:upperleft_corner_y>
      </cart:Geo_Transformation>
    </cart:Planar>
    <cart:Geodetic_Model>
      <cart:a_axis_radius unit="km">1737.4</cart:a_axis_radius>
    </cart:Geodetic_Model>
    </cart:Horizontal_Coordinate_System_Definition></cart:Spatial_Reference_Information>
  </cart:Cartography></Discipline_Area></Observation_Area>
  <File_Area_Observational><File><file_name>test.IMG</file_name></File>
    <Array_2D_Image><offset unit="byte">0</offset><axes>2</axes>
      <axis_index_order>Last Index Fastest</axis_index_order>
      <Element_Array><data_type>UnsignedLSB2</data_type></Element_Array>
      <Axis_Array><axis_name>Line</axis_name><elements>{H}</elements><sequence_number>1</sequence_number></Axis_Array>
      <Axis_Array><axis_name>Sample</axis_name><elements>{W}</elements><sequence_number>2</sequence_number></Axis_Array>
    </Array_2D_Image></File_Area_Observational>
</Product_Observational>
"""


def _write(tmp_path: Path, text: str, name: str = "nac.xml") -> Path:
    path = tmp_path / name
    path.write_text(text)
    return path


def test_written_sign_wrong_is_flipped_and_inferred(tmp_path):
    geo = georeference_from_label(_write(tmp_path, _label(-X0)))
    assert geo.x0_m < 0
    assert geo.x0_m == pytest.approx(X0)
    assert geo.source is ValueSource.INFERRED
    assert "flipped" in geo.note


def test_unit_pixel_scale_is_read_from_pixel_scale(tmp_path):
    # 1 m pixels like the real NAC ortho (bounds computed at that scale).
    geo = georeference_from_label(_write(tmp_path, _label(-X0, px=1.0)))
    assert geo.pixel_size_x_m == 1.0
    assert geo.x0_m < 0 and geo.source is ValueSource.INFERRED
    assert geo.crs_proj4 == NAC_PROJ


def test_written_sign_right_is_documented(tmp_path):
    geo = georeference_from_label(_write(tmp_path, _label(X0)))
    assert geo.source is ValueSource.DOCUMENTED
    assert geo.x0_m == pytest.approx(X0)
    assert "as written" in geo.note


def test_missing_pixel_scale_names_it(tmp_path):
    path = _write(tmp_path, _label(-X0, pixel_scale=False))
    with pytest.raises(LabelGeoreferenceError, match="pixel_scale_x"):
        georeference_from_label(path)


def test_unsupported_projection_raises(tmp_path):
    text = _label(-X0).replace(">Polar Stereographic<", ">Orthographic<")
    with pytest.raises(LabelGeoreferenceError, match="Orthographic"):
        georeference_from_label(_write(tmp_path, text))


def test_round_trip_pixel_lonlat(tmp_path):
    geo = georeference_from_label(_write(tmp_path, _label(-X0)))
    cols = np.array([0.0, 17.25, 115.5, 230.0])
    rows = np.array([0.0, 400.75, 238.0, 476.0])
    lon, lat = geo.pixel_to_lonlat(col=cols, row=rows)
    assert lon.dtype == np.float64 and lat.dtype == np.float64
    c2, r2 = geo.lonlat_to_pixel(lon=lon, lat=lat)
    np.testing.assert_allclose(c2, cols, atol=1e-6)
    np.testing.assert_allclose(r2, rows, atol=1e-6)


def test_xy_pixel_corner_convention(tmp_path):
    geo = georeference_from_label(_write(tmp_path, _label(-X0)))
    x, y = geo.pixel_to_xy(col=1.0, row=2.0)
    assert (float(x), float(y)) == pytest.approx((X0 + 100.0, Y0 - 200.0))
    c, r = geo.xy_to_pixel(x=x, y=y)
    assert (float(c), float(r)) == pytest.approx((1.0, 2.0))
    a = geo.affine()
    assert (a.a, a.b, a.c, a.d, a.e, a.f) == pytest.approx((100.0, 0.0, X0, 0.0, -100.0, Y0))


def test_positional_coordinates_rejected(tmp_path):
    geo = georeference_from_label(_write(tmp_path, _label(-X0)))
    with pytest.raises(TypeError):
        geo.lonlat_to_pixel(32.3, -69.3)
    with pytest.raises(TypeError):
        geo.pixel_to_lonlat(0.0, 0.0)


def test_as_dict_from_dict_equality(tmp_path):
    geo = georeference_from_label(_write(tmp_path, _label(-X0)))
    d = json.loads(json.dumps(geo.as_dict()))
    assert d["source"] == "inferred"
    assert GeoReference.from_dict(d) == geo


def test_pds4_lro_row_has_size_and_bounds(tmp_path):
    product = read_lro_label(_write(tmp_path, _label(-X0)))
    assert product.georef is not None and product.georef.source is ValueSource.INFERRED
    row = lro_to_row(product)
    assert (row["lines"], row["samples"]) == (H, W)
    for key in ("min_lat", "max_lat", "min_lon", "max_lon"):
        assert row[key] is not None
    assert row["min_lat"] < row["max_lat"]
    assert row["footprint_resolved"] is True


def test_pds4_label_without_cart_has_no_georef(tmp_path):
    text = _label(-X0)
    start = text.index("<cart:Cartography>")
    end = text.index("</cart:Cartography>") + len("</cart:Cartography>")
    product = read_lro_label(_write(tmp_path, text[:start] + text[end:]))
    assert product.georef is None
    assert any(u.startswith("georef:") for u in product.unresolved)
    row = lro_to_row(product)
    assert row["footprint_resolved"] is False
    assert (row["lines"], row["samples"]) == (H, W)


@pytest.mark.parametrize("radius", ["0", "-1737.4"])
def test_non_positive_radius_raises_label_error(tmp_path, radius):
    path = _write(tmp_path, _label(-X0).replace(">1737.4<", f">{radius}<"))
    with pytest.raises(LabelGeoreferenceError, match="a_axis_radius"):
        georeference_from_label(path)
    product = read_lro_label(path)
    assert product.georef is None
    assert any(u.startswith("georef:") and "a_axis_radius" in u for u in product.unresolved)
    assert (product.values["lines"], product.values["samples"]) == (H, W)


def test_proj_rejection_becomes_label_error(tmp_path, monkeypatch):
    from rasterio.errors import CRSError

    import lunar_reg.ingest.lro as lro

    def reject(*args, **kwargs):
        raise CRSError("The PROJ4 dict could not be understood")

    monkeypatch.setattr(lro, "_bbox_residual_m", reject)
    path = _write(tmp_path, _label(-X0))
    with pytest.raises(LabelGeoreferenceError, match="PROJ rejected"):
        georeference_from_label(path)
    product = read_lro_label(path)
    assert product.georef is None
    assert any(u.startswith("georef:") and "PROJ rejected" in u for u in product.unresolved)


@pytest.mark.data
def test_real_nac_label_sign():
    if not NAC_LABEL.exists():
        pytest.skip(f"missing {NAC_LABEL}")
    geo = georeference_from_label(NAC_LABEL)
    assert geo.x0_m == pytest.approx(-11043.5, abs=0.01)
    assert geo.y0_m == pytest.approx(638258.5, abs=0.01)
    assert (geo.width, geo.height) == (23003, 47683)
    assert geo.source is ValueSource.INFERRED


@pytest.mark.data
def test_real_nac_row():
    if not NAC_LABEL.exists():
        pytest.skip(f"missing {NAC_LABEL}")
    row = lro_to_row(read_lro_label(NAC_LABEL))
    assert row["lines"] is not None and row["samples"] is not None
    for key in ("min_lat", "max_lat", "min_lon", "max_lon"):
        assert row[key] is not None
    assert row["footprint_resolved"] is True
