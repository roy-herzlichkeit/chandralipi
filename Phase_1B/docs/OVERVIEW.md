# Phase 1B — the illumination bridge (for the human reviewer)

Built only if Phase 1 showed that fixing the search area was not enough for the 2023 strips (`data/processed/vikram/exp1_gate.json`).

## The idea in plain words
The 2023 OHRC pictures were taken with the sun on the other side from the NASA map, so the same crater looks different (a dark crescent on one side vs the other). NASA also published a **DTM** (digital terrain model: a height map of the ground, 3 m per pixel). From heights we can **render** what the ground would look like under *any* sun direction. Rendering the DTM under the OHRC sun gives a reference picture lit like the OHRC one — same shadows, same bright slopes — so matchers can find the same features again.

## New terms
| term | meaning | example |
|---|---|---|
| **shaded relief** | a picture computed from a height map for a chosen sun direction | the Vikram DTM rendered with the sun at 62° azimuth, 8° elevation |
| **cast shadow** | ground hidden from the sun by a higher point between it and the sun | a crater rim's shadow across the crater floor |
| **azimuth convention** | how a label measures the sun's compass direction (from north or east, clockwise or not) | ISRO's convention is not documented to us, so it is calibrated on the 2024 strip |
| **consensus** | fitting one transform from the points of every matcher that agrees with the others | SIFT, AKAZE and LightGlue agree within 1 px, RIFT2 does not → RIFT2 is excluded |

## Prompts
P1B.00 gate → P1B.01 renderer → P1B.02 rendered reference + azimuth calibration → P1B.03 consensus → P1B.04 RIFT2 fixes → P1B.05 runner bridge mode → P1B.06 run on the 2023 strips and document.
