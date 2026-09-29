# LLD — provenance enum, run record, seeded fit (P0.07)

Produces: C01, C06, C15. Closes: A094 (S15), A095 (align-7), A096 (align-8).

## 1. `src/lunar_reg/provenance.py` (new)
Exactly C01. Module docstring: one paragraph stating G17 (new numbers carry `ValueSource`; the older `Provenance`, `ParamSource`, `TermSource` enums stay). No other symbols.

## 2. `src/lunar_reg/runrecord.py` (new)
Exactly C15. Details:
| item | rule |
|---|---|
| `started_utc`, `finished_utc` | `datetime.now(timezone.utc).isoformat(timespec="seconds")` with `+00:00` replaced by `Z` |
| git | `git -C <repo> rev-parse HEAD` and `git -C <repo> status --porcelain` via `subprocess.run([...], capture_output=True, text=True, check=False)`; `<repo>` = `Path(lunar_reg.__file__).resolve().parents[2]`. On failure `git_sha = ""`, `git_dirty = True`, and `notes` gets `"git unavailable: <stderr first line>"`. |
| `host` | `socket.gethostname()` |
| `device` | `"cuda:<i> <torch.cuda.get_device_name(i)>"` when torch is importable and CUDA is available (i = current device), else `"cpu"`. torch import failure → `"cpu"`. |
| `versions` | keys `python, numpy, cv2, torch, kornia`; a missing package → `"absent"` |
| `artefacts` | stored as repo-relative POSIX strings when under the repo, else absolute POSIX |
| `write_run_record` | writes `<out_dir>/run_record.json` via temp file + `os.replace`, `indent=2`, `sort_keys=True`; creates `out_dir` |
| `validate_run_record` | returns human-readable problem strings; never raises for a malformed file (a JSON error is one problem) |

## 3. `align/estimate.py` — seeded, float64-safe fit (C06)
```python
def estimate_transform(result, model="homography", threshold_px=DEFAULT_THRESHOLD_PX,
                       max_iters=10_000, confidence=0.9999, seed: int = 0)
```
Steps (replacing the float32 cast at lines 81-82):
1. `cs = result.src_pts.mean(axis=0)`, `cd = result.dst_pts.mean(axis=0)` (float64).
2. `src = (result.src_pts - cs).astype(np.float32)`, `dst = (result.dst_pts - cd).astype(np.float32)`.
3. `cv2.setRNGSeed(int(seed))` immediately before the OpenCV estimator call.
4. Estimators unchanged: homography `cv2.USAC_MAGSAC` (`estimator="USAC_MAGSAC"`), affine `cv2.estimateAffine2D(method=cv2.RANSAC)` and partial `cv2.estimateAffinePartial2D(method=cv2.RANSAC)` (`estimator="RANSAC"`).
5. Un-centre in float64: with `Ts = [[1,0,-cs_x],[0,1,-cs_y],[0,0,1]]`, `Td_inv = [[1,0,cd_x],[0,1,cd_y],[0,0,1]]`, `M3` = fitted matrix as 3×3 (append `[0,0,1]` for 2×3): `M = Td_inv @ M3 @ Ts`; homography → `M / M[2,2]`; affine models → `M[:2]` (2×3).
6. `Transform(..., estimator=..., seed=seed)`.
Module docstring: replace the MAGSAC++ paragraph so it says MAGSAC++ applies to homographies only and affine models use RANSAC (A096 "correct the docstring" option; the switch to USAC for affine is not made).

`Transform` gains `estimator: str = "unknown"` and `seed: int | None = None` as its last two fields.

## 4. Tests the prompt adds (`tests/test_estimate_seeded.py`)
| test | asserts |
|---|---|
| repeat | two calls on 200 points with 30 % outliers → `np.array_equal` matrices and masks |
| subprocess | same fit in `subprocess.run([sys.executable, "-c", ...])` → identical `matrix.tobytes().hex()` |
| large coordinates | 100 exact correspondences around (5e5, 5e5), pure translation (12.25, −7.5): max residual < 1e-3 px for homography, affine and partial_affine |
| affine shape | affine and partial_affine return 2×3, homography 3×3 |
| run record | `start_run`/`finish_run`/`write_run_record`/`validate_run_record` round trip in `tmp_path` |
