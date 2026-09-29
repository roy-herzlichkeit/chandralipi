"""Helpers shared by Phase 1 harness tests (import as `from _h1 import ...`). Protected (G05)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
PDS4_NS = "http://pds.nasa.gov/pds4/pds/v1"
NAC_LABEL = REPO / "data/raw/reference/lro_nac_vikram/NAC_DTM_VIKRAMSITE1_M1442997156_100CM.xml"
NAC_PROJ = "+proj=stere +lat_0=-90 +lat_ts=-69.3 +lon_0=32.3 +R=1737400 +units=m +no_defs"
MOON_GEO = "+proj=longlat +R=1737400 +no_defs"
ANCHOR = "20240425T1406019344"
TAGS_2023 = ("20230823T1450475804", "20230823T1647285085", "20230823T1647285315")


def load_script(name: str):
    path = REPO / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_script_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return False


def pds4_label(lid="urn:isro:isda:ch2_ohr:test_0001", file_name="test.img",
               axes=(("Line", 12), ("Sample", 10)), array_kind="Array_2D_Image",
               data_type="UnsignedByte", geometry: dict | None = None) -> str:
    """Same documented Product_Observational layout as tests/test_ingest_labels.py::_pds4_label."""
    axis_xml = "\n".join(
        f"      <Axis_Array><axis_name>{n}</axis_name>"
        f"<elements>{e}</elements><sequence_number>{i + 1}</sequence_number></Axis_Array>"
        for i, (n, e) in enumerate(axes)
    )
    geom_xml = ""
    if geometry:
        inner = "\n".join(f"      <{k}>{v}</{k}>" for k, v in geometry.items())
        geom_xml = f"    <Discipline_Area>\n{inner}\n    </Discipline_Area>"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="{PDS4_NS}">
  <Identification_Area>
    <logical_identifier>{lid}</logical_identifier>
    <version_id>1.0</version_id>
    <title>Test product</title>
    <information_model_version>1.11.0.0</information_model_version>
    <product_class>Product_Observational</product_class>
  </Identification_Area>
  <Observation_Area>
    <Time_Coordinates>
      <start_date_time>2024-04-25T14:06:01.000Z</start_date_time>
      <stop_date_time>2024-04-25T14:06:18.000Z</stop_date_time>
    </Time_Coordinates>
    <Target_Identification><name>Moon</name><type>Satellite</type></Target_Identification>
    <Observing_System>
      <Observing_System_Component><name>OHRC</name><type>Instrument</type></Observing_System_Component>
    </Observing_System>
{geom_xml}
  </Observation_Area>
  <File_Area_Observational>
    <File><file_name>{file_name}</file_name></File>
    <{array_kind}>
      <offset unit="byte">0</offset>
      <axes>{len(axes)}</axes>
      <axis_index_order>Last Index Fastest</axis_index_order>
      <Element_Array><data_type>{data_type}</data_type></Element_Array>
{axis_xml}
    </{array_kind}>
  </File_Area_Observational>
</Product_Observational>
"""


def cart_label(ul_x: float, ul_y: float, width: int, height: int, px: float,
               bounds: tuple[float, float, float, float], *, pixel_scale=True) -> str:
    """NAC-style PDS4 label with the cart elements seen in the real Vikram label (lines 111-160).

    ``bounds`` = (west, east, north, south) in degrees.
    """
    w, e, n, s = bounds
    scale = (f"<cart:pixel_scale_x unit=\"m/pixel\">{px}</cart:pixel_scale_x>"
             f"<cart:pixel_scale_y unit=\"m/pixel\">{px}</cart:pixel_scale_y>") if pixel_scale else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="{PDS4_NS}" xmlns:cart="http://pds.nasa.gov/pds4/cart/v1">
  <Identification_Area><logical_identifier>urn:nasa:pds:test:nac_dtm_test</logical_identifier></Identification_Area>
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
        <cart:upperleft_corner_y unit="m">{ul_y}</cart:upperleft_corner_y>
      </cart:Geo_Transformation>
    </cart:Planar>
    <cart:Geodetic_Model><cart:latitude_type>Planetocentric</cart:latitude_type>
      <cart:a_axis_radius unit="km">1737.4</cart:a_axis_radius><cart:b_axis_radius unit="km">1737.4</cart:b_axis_radius>
      <cart:c_axis_radius unit="km">1737.4</cart:c_axis_radius><cart:longitude_direction>Positive East</cart:longitude_direction>
    </cart:Geodetic_Model>
    </cart:Horizontal_Coordinate_System_Definition></cart:Spatial_Reference_Information>
  </cart:Cartography></Discipline_Area></Observation_Area>
  <File_Area_Observational><File><file_name>test.IMG</file_name></File>
    <Array_2D_Image><offset unit="byte">0</offset><axes>2</axes>
      <axis_index_order>Last Index Fastest</axis_index_order>
      <Element_Array><data_type>UnsignedLSB2</data_type></Element_Array>
      <Axis_Array><axis_name>Line</axis_name><elements>{height}</elements><sequence_number>1</sequence_number></Axis_Array>
      <Axis_Array><axis_name>Sample</axis_name><elements>{width}</elements><sequence_number>2</sequence_number></Axis_Array>
    </Array_2D_Image></File_Area_Observational>
</Product_Observational>
"""


def raster_bounds(x0, y0, width, height, px):
    """(west, east, north, south) of a raster's densified boundary, degrees east in [0, 360)."""
    from rasterio.warp import transform

    t = np.linspace(0, 1, 101)
    cols = np.r_[t * width, np.full(101, width), t * width, np.zeros(101)]
    rows = np.r_[np.zeros(101), t * height, np.full(101, height), t * height]
    lon, lat = transform(NAC_PROJ, MOON_GEO, list(x0 + cols * px), list(y0 - rows * px))
    lon = np.mod(lon, 360)
    return float(lon.min()), float(lon.max()), float(np.max(lat)), float(np.min(lat))


def write_json(path: Path, obj) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True))
    return path


def illumination(seed=0, shape=(256, 256), dz=0.0):
    from lunar_reg.eval.scenes import illumination_pair

    return illumination_pair(shape=shape, seed=seed, source_sun=(300, 30),
                             reference_sun=(300 + dz, 30))


def write_grid_csv(path: Path, lines: int, samples: int, lonlat, step: int = 100) -> Path:
    """Geometry-grid CSV in the layout of tests/test_geometry_grid.py (header row, 0-based Scan x Pixel
    sampled every `step` with a final short step onto the last index). `lonlat(line, sample)` -> (lon, lat)."""
    scans = list(range(0, lines - 1, step)) + [lines - 1]
    pixels = list(range(0, samples - 1, step)) + [samples - 1]
    rows = ["Longitude,Latitude,Pixel,Scan"]
    for s in scans:
        for p in pixels:
            lon, lat = lonlat(s, p)
            rows.append(f"{lon:.9f},{lat:.9f},{p},{s}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n")
    return path
