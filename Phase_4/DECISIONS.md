# Phase 4 — local decisions

| ID | decision | reason | rejected |
|---|---|---|---|
| D4-1 | A reclaimed Redis job is acknowledged and re-added as a new stream entry (state and attempts live in hashes). | Keeps `XREADGROUP >` as the only claim path and makes attempts explicit, mirroring the local queue. | `XCLAIM` to the next worker (hides the loss inside the PEL) |
| D4-2 | Capacity tiers = distinct `0.75 × free` of the fleet's GPUs; a worker reads its own and every smaller tier, largest first. | No job can reach a GPU it does not fit (TBD 4.3) while large GPUs still drain small work. | Central assignment per worker; trial-and-OOM |
| D4-3 | Data reaches each host by `rsync --ignore-existing` of only the plan's input files into a node cache verified against DOWNLOADS.json. | Two hosts on a LAN; no shared filesystem assumed (R3b open). | NFS mount; HTTP range reads |
| D4-4 | Results come back by rsync of each host's result directory and are merged by content hash; any mismatch is a classified determinism failure. | At-least-once delivery must end in exactly one result per job (TBD 4.5), and cross-host non-determinism must be visible. | Results stored in Redis |
