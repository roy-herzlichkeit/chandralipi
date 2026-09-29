---
name: provenance-fields
description: How to attach provenance to every new number (ValueSource, C01) and how to write numbers into docs (G19). Used by P0.07, P0.08, P0.12 and every prompt that adds a constant, a measured value or a doc number.
---

# Provenance in code, numbers only from runs (CONTEXT.md conventions 1 and 3)

## ValueSource (`lunar_reg.provenance`, C01)
| member | use when |
|---|---|
| `MEASURED` | a run in this repo on this project's data or hardware produced it |
| `COMPUTED` | deterministic arithmetic on measured/documented inputs |
| `DOCUMENTED` | read from a cited external document or archive metadata (label field, ODE metadata) |
| `INFERRED` | a fit, a heuristic, a chosen threshold, or reasoning not written down anywhere external |
| `UNKNOWN` | not known; never substitute a nameplate or default value for an unknown |

## Patterns
- A new tunable constant: keep the plain value (callers do arithmetic) and add a sibling `NAME_SOURCE = ValueSource.<member>`; or use `Sourced(value, source, note)` when no caller does arithmetic on it.
- A new result field that is a number: add a sibling `<name>_source: str` (the `ValueSource` value) or put a `Sourced(...).as_dict()` in `extra`.
- Existing enums (`fieldmap.Provenance`, `params.ParamSource`, `pseudo_gt.TermSource`) stay as they are (G17).
- A missing value is `None` plus `ValueSource.UNKNOWN`, never `0` or a default.

## Numbers in docs (G19)
- Every number written in any doc must be read from a run artefact, and the artefact path goes in the same sentence or table row: `… 106 inliers (data/processed/vikram/exp1/summary.json)`.
- No artefact → write `[INSERT RESULT]`.
- Self-residual RMSE is never called "accuracy"; real pairs have no ground truth (FABLE_NOTES §4.6).
- Synthetic results are always labelled SYNTHETIC next to the number.
