# Phase 1 — what it does and why (for the human reviewer)

Terms from Phase 0's overview (registration, correspondence, transform, RANSAC, ECC, inlier, uniformity) are used as defined there.

## Goal in one sentence
Turn the one-off script that registered one Chandrayaan-2 strip into a real pipeline: it knows what data is on disk, places each picture on the Moon using documented metadata, prepares matching windows, runs every matcher, stores successes **and** failures, and explains why the 2023 strips did not register.

## New terms
| term | meaning | example |
|---|---|---|
| **nrp / ncp** | ISRO product levels seen in file names: `nrp` = raw, `ncp` = calibrated (meaning inferred from the PRADAN FAQ examples; the full definition is in ISRO's SIS document) | `ch2_ohr_nrp_20240425T1406019344_d_img_d18` is the raw 2024 strip |
| **geometry grid** | a CSV shipped with calibrated ISRO products giving latitude/longitude for a grid of image pixels | lets us place pixel (line 5000, sample 6000) on the Moon without guessing from 4 corners |
| **georeference** | the rule that turns a map pixel into map coordinates (metres) | NAC pixel (0, 0) is at x = −11 043.5 m, y = 638 258.5 m (`data/raw/reference/lro_nac_vikram/PROVENANCE.json`, corrected transform) |
| **datum** | the model of the Moon's shape and the angle conventions used for latitude/longitude | a sphere of radius 1 737 400 m, longitudes counted eastward |
| **prior** | our best guess of where the source window lands in the reference, before matching | from label corners or the geometry grid |
| **preset** | a named list of image clean-up steps run before matching | `clahe_shadow`: brighten shadows, then boost local contrast |
| **ablation** | running the same test with and without one ingredient to see if it helps | the anchor strip with presets `none`, `ohrc_nac`, `clahe_shadow` |
| **agreement** | how far apart two matchers' transforms put the image corners *before* ECC (which would otherwise pull them together) | SIFT and LightGlue differ by 0.6 px → they agree |
| **sun azimuth / elevation** | the compass direction the sunlight comes from / how high the sun is | OHRC 2023 strips: sun azimuth ≈ 62°; the 2024 strip: ≈ 304° (label values, recorded in `TBD_phase_1.md` §1.8) |

## What changes
| block | prompts |
|---|---|
| downloads (human session tonight + verifier + public fetch) | P1.DL, P1.01, P1.02 |
| knowing what is on disk; skipping absent instruments | P1.03 |
| placing images on the Moon correctly | P1.04 (NAC map), P1.05–P1.06 (ISRO grid), P1.07 (datum) |
| image clean-up that ignores empty borders; presets | P1.08–P1.10 |
| reference sun, agreement, window pairs, matcher registry, TMC-2/IIRS | P1.11–P1.15 |
| one runner for the site; JAXA re-run; ablation driver; CLI | P1.16–P1.17 |
| real runs: archive old store, ablation, default preset, 2023 diagnosis, 1B gate | P1.18–P1.20 |
| viewers and docs | P1.21–P1.22 |

## What decides Phase 1B
`data/processed/vikram/exp1_gate.json`: if all three 2023 strips register once the search window is corrected (≥ 20 inliers, uniformity ≥ 0.7, agreement < 1 px), Phase 1B (the shaded-relief "illumination bridge") is skipped; otherwise it is built after Phase 2.

## Honest limits
No ground truth exists for real pairs; "accuracy" on real data is never claimed from the fit's own residual. The sun directions are computed with NASA's SPICE toolkit from public ephemeris files (COMPUTED); the NASA incidence angle and a terrain-shading fit are shown next to them as independent checks. TMC-2/IIRS fields are added only from a probe of a real product.
