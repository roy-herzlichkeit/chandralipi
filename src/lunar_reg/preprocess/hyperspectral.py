"""IIRS band reduction.

IIRS delivers 256 bands over 0.8-5.0 um. Two separate problems follow:

1. **Memory.** A 2000x2000 IIRS cube at 256 bands is ~4 GB in float32. Which
   path loads it depends on the mode the pipeline's ``band_reduction`` step
   records in ``detail["mode"]``:

   * ``"incremental"`` -- :func:`incremental_band_pca`, chosen when the context
     carries a multi-band rasterio dataset and the method is PCA. It reads row
     blocks from the dataset, so the cube is never held whole by this function
     (the pipeline's ``image`` argument is whatever the caller already loaded).
   * ``"in_memory"`` -- :func:`reduce_bands` on the in-memory cube, for every
     other case (no dataset, ``select`` or ``mean``). The whole cube is in
     memory, and PCA builds a float64 copy of it.
2. **Modality.** Matching a hyperspectral cube against a panchromatic optical
   image is the frontier case in this problem, not a solved one. The reduction
   here (band select or PCA to a single plane) is a reasonable baseline and is
   what the team's deck proposes, but published work suggests it will not close
   the gap alone against a genuinely cross-modal learned matcher.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

#: IIRS bands whose wavelengths sit closest to the panchromatic response of
#: OHRC/TMC-2/LRO NAC. Reflectance-dominated and least affected by the thermal
#: component that takes over past ~3 um.
VNIR_BAND_RANGE = (0, 60)


def select_bands(cube: np.ndarray, band_indices) -> np.ndarray:
    """Extract a subset of bands from a ``(bands, rows, cols)`` cube."""
    return np.asarray(cube)[list(band_indices)]


def iirs_to_panchromatic(
    cube: np.ndarray,
    band_range: tuple[int, int] = VNIR_BAND_RANGE,
) -> np.ndarray:
    """Collapse an IIRS cube to a single pseudo-panchromatic plane.

    Averages the VNIR bands, which is the cheap approximation of the broadband
    response the optical sensors actually integrate. Fast, and a sensible
    default before reaching for PCA.
    """
    lo, hi = band_range
    cube = np.asarray(cube, dtype=np.float32)
    hi = min(hi, cube.shape[0])
    if lo >= hi:
        raise ValueError(f"empty band range ({lo}, {hi}) for cube with {cube.shape[0]} bands")
    return cube[lo:hi].mean(axis=0)


def incremental_band_pca(
    dataset,
    n_components: int = 1,
    block_rows: int = 512,
    max_bands: int | None = None,
) -> np.ndarray:
    """First principal component(s) across bands, computed without loading the cube.

    MEMORY CONSTRAINT: covariance is accumulated over row blocks, so peak host
    memory is ``block_rows * cols * bands * 4`` bytes rather than the full cube.
    At the defaults that is a few hundred MB instead of several GB.

    ``dataset`` is an open rasterio dataset over a multi-band product. Returns
    an array shaped ``(n_components, rows, cols)``.
    """
    from rasterio.windows import Window

    n_bands = dataset.count if max_bands is None else min(dataset.count, max_bands)
    rows, cols = dataset.height, dataset.width

    # Pass 1: accumulate mean and covariance across bands, block by block.
    total = np.zeros(n_bands, dtype=np.float64)
    cov = np.zeros((n_bands, n_bands), dtype=np.float64)
    count = 0

    for row in range(0, rows, block_rows):
        h = min(block_rows, rows - row)
        block = dataset.read(
            list(range(1, n_bands + 1)), window=Window(0, row, cols, h)
        ).astype(np.float64)
        flat = block.reshape(n_bands, -1)
        valid = np.isfinite(flat).all(axis=0)
        flat = flat[:, valid]
        if flat.size == 0:
            continue
        total += flat.sum(axis=1)
        cov += flat @ flat.T
        count += flat.shape[1]

    if count == 0:
        raise ValueError("no valid pixels found in cube")

    mean = total / count
    cov = cov / count - np.outer(mean, mean)

    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1][:n_components]
    components = eigvecs[:, order].T  # (n_components, n_bands)
    logger.info(
        "band PCA over %d bands: top-%d explain %.1f%% of variance",
        n_bands,
        n_components,
        100.0 * eigvals[order].sum() / max(eigvals.sum(), 1e-12),
    )

    # Pass 2: project, still block by block.
    out = np.empty((n_components, rows, cols), dtype=np.float32)
    for row in range(0, rows, block_rows):
        h = min(block_rows, rows - row)
        block = dataset.read(
            list(range(1, n_bands + 1)), window=Window(0, row, cols, h)
        ).astype(np.float64)
        flat = block.reshape(n_bands, -1) - mean[:, None]
        out[:, row : row + h, :] = (components @ flat).reshape(n_components, h, cols)

    return out


def select_reference_band(cube: np.ndarray, band: int | None = None) -> tuple[np.ndarray, int]:
    """Pick one band to drive registration, as the paper's IIRS/WAC track does.

    The paper states the strategy but not the band::

        "From the multi-band dataset, a single, visually clear band was selected
         as the reference for image registration. Once the transformation
         parameters were computed using this band, they were applied uniformly
         to align all other bands accordingly."

    So the *choice* of band is a PLACEHOLDER. With ``band=None`` this picks the
    band of highest standard deviation, i.e. the most contrasty one, which is a
    reasonable reading of "visually clear". Pass an int to pin it.

    Returns ``(plane, band_index)`` -- keep the index: the transform is fitted on
    this band and then applied to all the others.
    """
    cube = np.asarray(cube)
    if cube.ndim != 3:
        raise ValueError(f"expected a (bands, rows, cols) cube, got shape {cube.shape}")
    if band is not None:
        if not 0 <= band < cube.shape[0]:
            raise ValueError(f"band {band} out of range for {cube.shape[0]}-band cube")
        return cube[band].astype(np.float32), band

    stds = [float(np.nanstd(cube[b])) for b in range(cube.shape[0])]
    best = int(np.argmax(stds))
    logger.info("selected band %d of %d by contrast (std=%.4g)", best, cube.shape[0], stds[best])
    return cube[best].astype(np.float32), best


def reduce_bands(
    cube: np.ndarray,
    method: str = "pca",
    n_components: int = 1,
    band: int | None = None,
) -> tuple[np.ndarray, dict]:
    """Collapse a cube to a single matchable plane.

    ``method`` is one of ``"pca"`` (paper 4.2.4), ``"select"`` (paper 4.2 B
    preamble) or ``"mean"`` (VNIR average, this project's own cheap default).
    Returns ``(plane, detail)``.
    """
    cube = np.asarray(cube)
    if cube.ndim != 3:
        raise ValueError(f"expected a (bands, rows, cols) cube, got shape {cube.shape}")

    if method == "select":
        plane, index = select_reference_band(cube, band)
        return plane, {"method": "select", "band": index, "n_bands": int(cube.shape[0])}

    if method == "mean":
        return (
            iirs_to_panchromatic(cube),
            {"method": "mean", "band_range": VNIR_BAND_RANGE, "n_bands": int(cube.shape[0])},
        )

    if method != "pca":
        raise ValueError(f"method must be pca | select | mean, got {method!r}")

    flat = cube.reshape(cube.shape[0], -1).astype(np.float64)
    valid = np.isfinite(flat).all(axis=0)
    if not valid.any():
        raise ValueError("cube has no fully-valid pixels for PCA")

    usable = flat[:, valid]
    mean = usable.mean(axis=1, keepdims=True)
    centred = usable - mean
    covariance = (centred @ centred.T) / max(centred.shape[1] - 1, 1)
    eigvals, eigvecs = np.linalg.eigh(covariance)
    order = np.argsort(eigvals)[::-1][:n_components]
    explained = float(eigvals[order].sum() / max(eigvals.sum(), 1e-12))

    projected = eigvecs[:, order].T @ (flat - mean)
    plane = projected.reshape(n_components, *cube.shape[1:])
    return (
        plane[0] if n_components == 1 else plane,
        {
            "method": "pca",
            "n_components": n_components,
            "explained_variance": round(explained, 4),
            "n_bands": int(cube.shape[0]),
        },
    )
