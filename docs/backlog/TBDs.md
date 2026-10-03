# TBDs — remaining work, phase by phase

**Purpose of this file.** A backlog for turning into design docs, not a design
doc itself. Intended flow: this backlog → an HLD, then an LLD granular enough
that Opus or Sonnet can implement a phase without re-deriving context →
implementation. Split into one file per phase so each can be handed to the
HLD/LLD pass independently. Each item names the file(s) it touches, its current
state, and what "done" looks like, so a design pass can start from a fact
rather than a guess.

**Provenance note, per this project's own convention** (see `docs/project/CONTEXT.md` §3):
every item in these files is either (a) copied from an existing open item in
`docs/project/CONTEXT_HANDOFF.md` / `docs/project/CONTEXT.md` / `udocs/70_SYSTEM_DESIGN_distributed_gpu.md`
— cited inline — or (b) this document's own phase grouping/sequencing, which is
a planning judgment call, not a fact from those sources. Nothing here is a new
finding; these files organize existing, already-recorded gaps.

## How the phases relate to the demo plan

The stated plan is: show classical + neural results first, then build out
cluster computing. That maps to:

- **[Phase 1](TBD_phase_1.md)** — closes gaps that affect the
  credibility/completeness of the classical+neural results shown first.
  Independent of cluster work.
- **[Phase 2](TBD_phase_2.md) → [Phase 3](TBD_phase_3.md) →
  [Phase 4](TBD_phase_4.md)** — the cluster computing build-out itself, staged
  cheapest-first exactly as `udocs/70_SYSTEM_DESIGN_distributed_gpu.md` Part 6
  lays out. **None of it has been started.** The design doc is explicit:
  *"Status: this is a design, not a description... no run on a GPU of any kind
  has happened yet."*
- **[Phase 5](TBD_phase_5.md)** — optional, only relevant once Phase 2+
  produces something to show.

Phases 2→3→4 are strictly sequential (each stage's own doc says the next stage
reuses the prior stage's boundary rather than redesigning it). Phase 1 can run
in parallel with the start of Phase 2, since they touch mostly disjoint files.

## Files

| Phase | Topic | Blocked on | Status |
|---|---|---|---|
| [docs/backlog/TBD_phase_1.md](TBD_phase_1.md) | Classical/neural result gaps | — | Partially open, several human decisions pending |
| [docs/backlog/TBD_phase_2.md](TBD_phase_2.md) | Stage 1: one real GPU | — | Not started (no GPU run has ever happened) |
| [docs/backlog/TBD_phase_3.md](TBD_phase_3.md) | Stage 2: one machine, N GPUs | Phase 2 | Not started (design only) |
| [docs/backlog/TBD_phase_4.md](TBD_phase_4.md) | Stage 3: many machines | Phase 3 | Not started (design only) |
| [docs/backlog/TBD_phase_5.md](TBD_phase_5.md) | Dashboard cluster panel | Phase 3 or 4 | Not started, not yet decided whether wanted |
