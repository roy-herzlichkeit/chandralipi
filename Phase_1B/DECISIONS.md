# Phase 1B — local decisions

| ID | decision | reason | rejected |
|---|---|---|---|
| D1B-1 | The OHRC label azimuth convention comes from SPICE (`label_convention.json`, COMPUTED, G14 revised after review RC17); the DTM-shading calibration on the registered 2024 anchor is kept as an independent cross-check and fallback (`INFERRED`). | ISRO's azimuth reference direction is undocumented in any file we hold; SPICE computes the true sun direction at each label time. | Assuming clockwise-from-north; DTM calibration as the only source |
| D1B-2 | RIFT2 rotation-invariance claims are removed rather than implemented. | Bridge pairs are rotation-normalised by the prior-rectified tiling (D2-1); implementing grid rotation is unmeasured risk. | Implementing rotated sampling |
| D1B-3 | Both reference variants (NAC, rendered) are stored; the one with lower conditioning p95 is flagged `bridge_selected`. | TBD 1.8 step 2: "keep whichever gives the better-conditioned solution", and keeping both preserves the evidence. | Storing the winner only |
| D1B-4 | Consensus contributors are matchers within 1 px (probe max) of the per-probe median of all fitted matchers. | Median is robust to one bad matcher; 1 px is the TBD 1.8 agreement target. | Pairwise voting; RANSAC over transforms |
