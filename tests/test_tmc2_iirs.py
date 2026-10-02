"""TMC-2 / IIRS ingest and hyperspectral routing (Phase_1/LLD/tmc2_iirs.md §5)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from lunar_reg.ingest.fieldmap import ALL_FIELDS, FIELDS_BY_NAME, Provenance
from lunar_reg.ingest.pds4 import VIEW_FIELD, read_label

REPO = Path(__file__).resolve().parents[1]
PDS4_NS = "http://pds.nasa.gov/pds4/pds/v1"


def _load_probe_raster():
    spec = importlib.util.spec_from_file_location(
        "probe_raster", REPO / "scripts" / "probe_raster.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _label(axes, array_kind="Array_3D_Spectrum", band_bins: str = "") -> str:
    axis_xml = "\n".join(
        f"      <Axis_Array><axis_name>{n}</axis_name><elements>{e}</elements>"
        f"<sequence_number>{i + 1}</sequence_number>"
        f"{band_bins if n.lower() == 'band' else ''}</Axis_Array>"
        for i, (n, e) in enumerate(axes)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Product_Observational xmlns="{PDS4_NS}">
  <Identification_Area>
    <logical_identifier>urn:isro:isda:test:x</logical_identifier>
  </Identification_Area>
  <File_Area_Observational>
    <File><file_name>x.qub</file_name></File>
    <{array_kind}>
      <offset unit="byte">0</offset>
      <axes>{len(axes)}</axes>
      <axis_index_order>Last Index Fastest</axis_index_order>
      <Element_Array><data_type>IEEE754LSBSingle</data_type></Element_Array>
{axis_xml}
    </{array_kind}>
  </File_Area_Observational>
</Product_Observational>
"""


# --------------------------------------------------------------------------- probe_raster


def _write_tif(path: Path, arr: np.ndarray, nodata=None) -> None:
    import rasterio

    h, w = arr.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=w,
        height=h,
        count=1,
        dtype=arr.dtype.name,
        nodata=nodata,
    ) as ds:
        ds.write(arr, 1)


def test_probe_raster_finds_an_undeclared_zero_border(tmp_path):
    h, w = 3000, 5000
    arr = np.zeros((h, w), np.uint16)
    arr[300:2700, 500:4500] = np.random.default_rng(1).integers(100, 4000, (2400, 4000))
    tif = tmp_path / "big.tif"
    _write_tif(tif, arr)
    out = tmp_path / "probe.json"
    assert _load_probe_raster().main([str(tif), "--out", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert doc["decimation"] == 3
    assert doc["out_shape"] == [1000, 1667]
    assert doc["nodata_declared"] is None
    assert doc["fill_candidate"] == 0
    assert doc["fill_candidate_source"] == "inferred"
    assert 0.0 < doc["fill_fraction"] < 1.0
    assert doc["border_values"][0] == {"value": 0, "count": doc["n_border_samples"]}
    assert doc["status"] == "ok"
    assert doc["res"] == [1.0, 1.0] and doc["count"] == 1 and doc["dtype"] == "uint16"
    assert doc["peak_rss_bytes"] > 0


def test_probe_raster_reports_declared_nodata_and_no_fill_on_a_textured_border(tmp_path):
    arr = np.random.default_rng(2).integers(100, 4000, (300, 400)).astype(np.int16)
    tif = tmp_path / "small.tif"
    _write_tif(tif, arr, nodata=-32768)
    out = tmp_path / "probe.json"
    assert _load_probe_raster().main([str(tif), "--out", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert doc["decimation"] == 1
    assert doc["nodata_declared"] == -32768
    assert doc["fill_candidate"] is None and doc["fill_fraction"] is None
    assert len(doc["border_values"]) == 5


def test_probe_raster_open_failure_is_classified(tmp_path):
    out = tmp_path / "probe.json"
    assert _load_probe_raster().main([str(tmp_path / "missing.tif"), "--out", str(out)]) == 1
    doc = json.loads(out.read_text())
    assert doc["status"] == "open_failed" and doc["error"]


# --------------------------------------------------------------------------- pds4 properties


@pytest.mark.parametrize(
    "axes,expected",
    [
        ((("Band", 3), ("Line", 10), ("Sample", 12)), 0),
        ((("Line", 10), ("Sample", 12), ("Band", 3)), 2),
        ((("BAND", 3), ("LINE", 10), ("SAMPLE", 12)), 0),  # real IIRS labels are upper case
        ((("Line", 10), ("Sample", 12)), None),
    ],
)
def test_band_axis_follows_the_label_axis_order(tmp_path, axes, expected):
    kind = "Array_3D_Spectrum" if len(axes) == 3 else "Array_2D_Image"
    path = tmp_path / "x.xml"
    path.write_text(_label(axes, kind))
    product = read_label(path)
    assert product.band_axis == expected
    assert product.view is None


def test_band_bin_fields_read_the_first_bin(tmp_path):
    bins = (
        "<Band_Bin_Set>"
        '<Band_Bin><band_number>1</band_number><band_width unit="nm">19.8</band_width>'
        '<center_wavelength unit="nm">712.3</center_wavelength></Band_Bin>'
        '<Band_Bin><band_number>2</band_number><band_width unit="nm">19.9</band_width>'
        '<center_wavelength unit="nm">729.2</center_wavelength></Band_Bin>'
        "</Band_Bin_Set>"
    )
    path = tmp_path / "x.xml"
    path.write_text(_label((("BAND", 2), ("LINE", 4), ("SAMPLE", 5)), band_bins=bins))
    product = read_label(path)
    assert product["first_band_center_wavelength"] == pytest.approx(712.3)
    assert product["first_band_width"] == pytest.approx(19.8)


def test_spectral_fields_are_verified_and_no_view_field_is_mapped():
    for name in ("first_band_center_wavelength", "first_band_width"):
        assert FIELDS_BY_NAME[name].provenance is Provenance.VERIFIED
    # No probe of a real TMC-2 label showed a view element (LLD tmc2_iirs §2).
    assert VIEW_FIELD not in {f.name for f in ALL_FIELDS}


# --------------------------------------------------------------------------- band reduction routing


def _cube(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 1, (40, 48)).astype(np.float32)
    return np.stack(
        [base * k + rng.normal(0, 0.01, base.shape).astype(np.float32) for k in (1.0, 2.0, 3.0)]
    )


def _config(method: str = "pca"):
    from lunar_reg.preprocess.config import PreprocessConfig

    return PreprocessConfig(
        georeference=False,
        band_reduction=True,
        band_reduction_method=method,
        resample=False,
        normalize=False,
        clahe=False,
        shadow=False,
    )


def _band_reduction(result):
    return next(r for r in result.history if r.name == "band_reduction")


def _run_with_dataset(cube, config, dataset_cube=None):
    from rasterio.io import MemoryFile

    from lunar_reg.preprocess.pipeline import PreprocessContext, run_pipeline

    dataset_cube = cube if dataset_cube is None else dataset_cube
    count, h, w = dataset_cube.shape
    with MemoryFile() as mem:
        with mem.open(driver="GTiff", width=w, height=h, count=count, dtype="float32") as ds:
            ds.write(dataset_cube)
        with mem.open() as ds:
            return run_pipeline(cube, config, PreprocessContext(src_dataset=ds))


def test_incremental_pca_matches_the_in_memory_component():
    from lunar_reg.preprocess.pipeline import PreprocessContext, StepStatus, run_pipeline

    cube = _cube()
    inc = _run_with_dataset(cube, _config())
    mem = run_pipeline(cube, _config(), PreprocessContext())
    rec_inc, rec_mem = _band_reduction(inc), _band_reduction(mem)
    assert rec_inc.status is StepStatus.RAN and rec_inc.detail["mode"] == "incremental"
    assert rec_mem.detail["mode"] == "in_memory"
    assert inc.image.shape == mem.image.shape == cube.shape[1:]
    corr = np.corrcoef(inc.image.ravel(), mem.image.ravel())[0, 1]
    assert abs(corr) > 0.99


def test_non_pca_method_with_a_dataset_stays_in_memory():
    rec = _band_reduction(_run_with_dataset(_cube(), _config("select")))
    assert rec.detail["mode"] == "in_memory"
    assert "not pca" in rec.detail["incremental_refused"]


def test_dataset_of_another_shape_is_not_used_for_the_window():
    cube = _cube()
    bigger = np.concatenate([cube, cube], axis=1)
    result = _run_with_dataset(cube, _config(), dataset_cube=bigger)
    rec = _band_reduction(result)
    assert rec.detail["mode"] == "in_memory"
    assert "differs" in rec.detail["incremental_refused"]
    assert result.image.shape == cube.shape[1:]


def _run_georeferenced(cube, ref_crs):
    """Run georeference + PCA with a same-size reference grid (review finding P1.15)."""
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    from lunar_reg.preprocess.config import PreprocessConfig
    from lunar_reg.preprocess.pipeline import PreprocessContext, run_pipeline

    count, h, w = cube.shape
    config = PreprocessConfig(
        georeference=True,
        band_reduction=True,
        band_reduction_method="pca",
        resample=False,
        normalize=False,
        clahe=False,
        shadow=False,
    )
    with MemoryFile() as m_src, MemoryFile() as m_ref:
        with m_src.open(
            driver="GTiff", width=w, height=h, count=count, dtype="float32",
            crs="EPSG:32633", transform=from_origin(500000, 100000, 10, 10),
        ) as ds:  # fmt: skip
            ds.write(cube)
        with m_ref.open(
            driver="GTiff", width=w, height=h, count=1, dtype="float32",
            crs=ref_crs, transform=from_origin(-168700, 100500, 10, 10),
        ) as ds:  # fmt: skip
            ds.write(cube[:1])
        with m_src.open() as src, m_ref.open() as ref:
            context = PreprocessContext(src_dataset=src, ref_dataset=ref)
            return run_pipeline(cube, config, context)


def test_georeferenced_cube_of_the_same_shape_is_not_replaced_by_the_raw_dataset():
    from lunar_reg.preprocess.hyperspectral import reduce_bands
    from lunar_reg.preprocess.pipeline import StepStatus

    cube = _cube()
    result = _run_georeferenced(cube, "EPSG:32634")
    geo = next(r for r in result.history if r.name == "georeference")
    assert geo.status is StepStatus.RAN
    assert geo.shape_after == cube.shape  # the shape guard alone would pass
    rec = _band_reduction(result)
    assert rec.detail["mode"] == "in_memory"
    assert "georeference" in rec.detail["incremental_refused"]
    # The output is the reduction of the reprojected cube: its unreached reference
    # pixels stay NaN, which a PCA of the raw source dataset would never produce.
    assert np.isnan(result.image).any()
    raw_pc, _ = reduce_bands(cube)
    finite = np.isfinite(result.image)
    corr = np.corrcoef(result.image[finite], raw_pc[finite])[0, 1]
    assert abs(corr) < 0.9


def test_skipped_georeference_keeps_the_incremental_route():
    from lunar_reg.preprocess.pipeline import StepStatus

    result = _run_georeferenced(_cube(), None)  # reference has no CRS -> georeference skipped
    geo = next(r for r in result.history if r.name == "georeference")
    assert geo.status is not StepStatus.RAN
    assert _band_reduction(result).detail["mode"] == "incremental"


# --------------------------------------------------------------------------- real products


def _first_label(pattern: str) -> Path | None:
    labels = sorted(REPO.glob(pattern))
    return labels[0] if labels else None


@pytest.mark.data
def test_real_iirs_label():
    label = _first_label("data/raw/ch2/iirs/*/data/**/*.xml")
    if label is None:
        pytest.skip("no IIRS product under data/raw/ch2/iirs (G24: absence never blocks)")
    product = read_label(label)
    assert product.bands > 1
    assert product.band_axis is not None
    assert product.axis_order.split(",")[product.band_axis].lower() == "band"
    assert product["first_band_center_wavelength"] is not None
    assert product.view is None


@pytest.mark.data
def test_real_tmc2_label():
    label = _first_label("data/raw/ch2/tmc2/*/data/**/*.xml")
    if label is None:
        pytest.skip("no TMC-2 product under data/raw/ch2/tmc2 (G24: absence never blocks)")
    product = read_label(label)
    assert product.band_axis is None
    assert product.lines and product.samples
    assert product.view is None
