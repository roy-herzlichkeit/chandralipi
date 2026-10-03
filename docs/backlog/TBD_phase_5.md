[← back to index](TBDs.md) · prev: [Phase 4](TBD_phase_4.md)

# Phase 5 — Optional: surfacing cluster execution in the dashboards

Not sourced from any existing TBD in the repo — **this phase is this
document's own addition**, because the prior conversation raised it as an open
question with no existing answer: neither `dashboard/app.py` (Streamlit) nor
`web/`'s React `/dashboard` currently has any field for *how* a result was
computed. The per-pair schema (`index.parquet` / `results.json`) is agnostic to
single-machine vs. cluster execution, so nothing here is required for
[Phase 2](TBD_phase_2.md)–[Phase 4](TBD_phase_4.md) to work — it's purely a
demo-presentation nicety, and only worth doing once Phase 3 or 4 actually
produces something to show.

## 5.1 Decide whether to show cluster stats at all
- Candidates, if pursued: worker/GPU count, tiles-processed throughput,
  OOM-retry count (ties into the "an OOM run is telling you the memory model
  needs re-measuring" point in Phase 2.2), a per-job outcome breakdown reusing
  the classified-outcome table from Phase 3.5.
- **This is a decision for whoever's presenting**, not an implementation task
  until decided.

## 5.2 If yes: add a cluster-run panel
- **File(s):** `web/src/pages/Dashboard.jsx` (React) and/or `dashboard/app.py`
  (Streamlit) — both already exist and already read the results store; this
  would be a new panel, not a new page, reusing existing data-loading code.
- **Existing related infrastructure:** `web/src/pages/Architecture.jsx` already
  renders HLD/LLD diagrams as inline SVG (`web/src/components/Diagram.jsx`) —
  the distributed-computing architecture diagram from
  `udocs/70_SYSTEM_DESIGN_distributed_gpu.md` Part 3 could reuse that same
  component rather than being built from scratch.
- **Done when:** whatever was decided in 5.1 renders from real run data (per
  this project's standing rule against invented numbers — `docs/project/CONTEXT.md` §3.3),
  not placeholder figures.

---
[← back to index](TBDs.md) · prev: [Phase 4](TBD_phase_4.md)
