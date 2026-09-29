# Phase 1B — review focus

| # | where | why | how to check |
|---|---|---|---|
| 1 | `pairs.calibrate_label_azimuth` | If the convention is wrong, every render is lit from the wrong side and the bridge silently fails; the peak margin says how sharp the fit is. | Read `azimuth_calibration.json` (residual, margin); re-run the synthetic test with another convention. |
| 2 | `eval/render.py` cast shadows | Shadow direction/sense errors are invisible in numbers but obvious in the preview image. | Open the rendered-reference preview next to the OHRC window. |
| 3 | `consensus.pooled_consensus` contributor rule | Decides which matchers' points enter the fit; a lenient rule reintroduces outlier matchers. | `test_C21_*`; inspect `consensus_excluded` in the stored extras. |
| 4 | `docs/ILLUMINATION_BRIDGE.md` | Claims about illumination invariance are panel-facing. | Each number has an artefact path; the target check follows TBD 1.8's definition. |
