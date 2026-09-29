# Phase 0 — review focus

Where reviewers should look hardest, and why. Ordered by risk to stored numbers.

| # | where | why it is risky | how to check |
|---|---|---|---|
| 1 | `align/refine.py` `ecc_refine` | The ECC argument convention (template = reference, input = source, init = inverse, invert result) is load-bearing; three of four orderings give wrong answers with a *higher* correlation coefficient (refine.py docstring). The affine path adds a 2×3 ↔ 3×3 conversion that is easy to transpose. | Read the inversion code for both motions; run `Phase_0/harness/tests/test_P0_08.py` and the C07 contract tests; compare against the known-affine scene. |
| 2 | `pipeline.register_pair` mask composition (G34) | Refit runs on the RANSAC-inlier subset; mapping its mask back to raw indices is an index-bookkeeping step where an off-by-order error silently marks the wrong points as inliers. | `test_P0_10.py::test_register_pair_fills_v2_fields` asserts refit ⊆ RANSAC; also inspect one stored pair by hand. |
| 3 | `align/estimate.py` centroid shift | Un-centring must be `T_dst⁻¹ · M · T_src` in float64; the wrong order still fits exact data near the origin. | `test_C06_large_coordinates` uses coordinates around 5×10⁵ px. |
| 4 | `ingest/pds4.py` traversal + predicates | Document order changes which element resolves for every label; ncp labels carry both System_Level and Refined corners. | `test_P0_05.py`; the data-marked real-label test; diff `lunar-reg probe-label` output on one real label before/after. |
| 5 | `results.py` atomic writes and v1 loading | `np.savez_compressed` appends `.npz` to paths without it, which breaks write-then-rename; v1 files must still load. | `test_C04_overwrite_refused`, `test_C04_v1_loads`; no `*.tmp` left. |
| 6 | `eval/uniformity.py` normalisation (G33) | Changes every stored U value; the Phase 1 gate (U ≥ 0.7) depends on it. | `test_P0_12.py::test_uniformity_small_sets_can_pass`; check the U of a clustered set still falls. |
| 7 | `scripts/run_vikram.py` export | Must never write a GeoTIFF from default or missing numbers; the old regex fallback returned (0, 0) silently. | `test_P0_11.py::test_export_classification`. |
| 8 | `scripts/untar_data.py` | Security boundary for data bundles. | Try `../`, absolute, symlink, `src/` members. |
