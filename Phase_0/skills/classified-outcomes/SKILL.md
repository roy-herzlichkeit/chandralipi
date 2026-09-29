---
name: classified-outcomes
description: The project's pattern for any batch or per-item operation that can fail — enum outcome, diagnostics with counts + first sample, report() printed by the caller every run. Used by P0.09, P0.10, P0.11 and every later phase.
---

# Classified outcomes (CONTEXT.md convention 2)

## Shape
```python
class ThingStatus(str, Enum):
    OK = "ok"
    SOME_FAILURE = "some_failure"        # one member per distinct cause; never a catch-all "error"
    @property
    def is_failure(self) -> bool: return self is not ThingStatus.OK
    # optional: is_suspicious for outcomes that are not failures but look like bugs

@dataclass
class ThingDiagnostics:
    counts: dict[str, int] = field(default_factory=dict)
    samples: dict[str, str] = field(default_factory=dict)   # first sample per status
    def record(self, status: ThingStatus, sample: str) -> None:
        self.counts[status.value] = self.counts.get(status.value, 0) + 1
        self.samples.setdefault(status.value, sample)
    def report(self) -> str:   # one header line, then "  <status>: <count>  e.g. <sample>" per status, sorted
        ...
```

## Rules
| rule | exact behaviour |
|---|---|
| library never raises for a bad item | return the classified outcome; exceptions only for programmer error (wrong type, calling an accessor on a failed outcome) |
| catching | catch the narrowest exception that the stage can raise; when a stage can raise anything (a matcher), catch `Exception` with `# noqa: BLE001` and a comment naming why |
| OOM ordering | `except torch.OutOfMemoryError` **before** `except RuntimeError` (OOM subclasses RuntimeError) |
| logging | library code logs **one** summary line (`logger.info`/`warning`); it never `print`s |
| printing | the caller (script / CLI) prints `report()` on **every** run, success or not |
| sample text | `"<item id>: <detail>"`, ≤ 200 chars |
| data gap vs bug | when "input missing" and "operation found nothing" can look alike, they are separate members, and `report()` says which one it is in words |
| exit codes (scripts) | 0 when every item is OK or an expected non-result; 1 when any failure member was recorded (unless the prompt defines otherwise) |

## Existing examples to copy from
`src/lunar_reg/ingest/overlap.py` (`OverlapStatus`, `OverlapDiagnostics`, lines 113 and 744), `src/lunar_reg/pipeline.py` (`BatchReport.report`), `scripts/fetch_catalogue.py` (`RowOutcome`, `Diagnostics`).
