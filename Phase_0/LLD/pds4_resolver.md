# LLD — PDS4 resolver in document order (P0.05)

Closes: A003 (ingest-1), A092 (ingest-14), A093 (ingest-20).

## 1. Traversal order
`_iter_with_ancestors(root)` must yield elements in **document order** (pre-order, children left to right). Replace `stack.extend((child, chain) for child in el)` with `stack.extend((child, chain) for child in reversed(list(el)))`. It keeps yielding `(element, ancestor_localname_tuple)`; additionally keep a parallel tuple of ancestor **elements** (needed by §2): yield `(element, ancestor_names, ancestor_elements)` and update `_resolve` accordingly. `_resolve` returns the **first** match in document order for the first path that matches anything (unchanged semantics otherwise).

## 2. Predicate path segments
A path segment may carry one predicate: `Name[child=value]`. It matches an ancestor element whose local name is `Name` **and** which has a direct child with local name `child` whose stripped text equals `value` exactly. Only one predicate per segment, no quoting, no wildcards. `_chain_contains` compares against ancestor elements when a segment has a predicate and against names otherwise. A malformed segment (unbalanced brackets, no `=`) raises `ValueError` at `Field` construction time (validate in `Field.__post_init__` in `fieldmap.py`).

## 3. Field map changes (`fieldmap.py`, only these)
| field | new `paths` (in order) |
|---|---|
| `instrument` | `("Observing_System_Component[type=Instrument]/name", "Observing_System_Component/name")` |
| `corner{1..4}_{lat,lon}` | `("System_Level_Coordinates/<position>_<full>", "<position>_<full>", "<corner_N>_<full>")` — i.e. the current two paths, preceded by the `System_Level_Coordinates/` form |
Provenance values are unchanged. Reason: the real OHRC label lists the spacecraft component first and the camera second (`data/raw/ohrc_vikram/*20240425*/data/raw/*/*.xml:36-54`); document order alone would now return the spacecraft.

## 4. Coercion failures
`_coerce` returns a module-level sentinel `_COERCE_FAILED` on `TypeError`/`ValueError`. In `read_label`:
- a field whose raw text matched but failed coercion → `values[name] = None`, `coerce_failed[name] = raw_text`, **not** in `resolved`, **not** in `unresolved`.
- `PDS4Product` gains `coerce_failed: dict[str, str] = field(default_factory=dict)` (last field, default empty).
- `manifest.product_to_row` appends `"<name>(coerce_failed)"` entries to the `unresolved_fields` text, after the unresolved names, comma-separated.

## 5. Image path containment
New helper in `pds4.py`:
```python
def resolve_contained(label_path: Path, file_name: str) -> Path | None:
    """label_path.parent / file_name, or None when file_name is absolute or resolves outside label_path.parent."""
```
Uses `Path(file_name).is_absolute()` and `(parent / file_name).resolve()` relative to `parent.resolve()` (`is_relative_to`).
- `_find_image`: when `file_name` is given and `resolve_contained` returns None → return None and log one warning.
- `PDS4Product.image_path` becomes `Path | None`; `PDS4Product` gains `image_path_rejected: str | None = None` holding the raw `file_name` when rejected.
- `lro.py` PDS3 `^IMAGE` pointer path (`_pds3_image_path`, lines ~245-262): route through `resolve_contained`; a rejected pointer yields `image_path=None`.

## 6. Expected consequences
Existing tests that encoded reverse-order results may change; update only assertions that encode the old last-match behaviour, and name them in the commit body (CLAUDE.md file fence). `tests/test_ingest_labels.py` must stay green otherwise.

## 7. Tests the prompt adds (`tests/test_pds4_resolver.py`)
| test | asserts |
|---|---|
| two matching elements | first in document order returned |
| predicate path | `Comp[type=Instrument]/name` picks the second component when the first has `type=Spacecraft` |
| malformed predicate | `Field(..., paths=("A[b/c",))` raises `ValueError` |
| coercion failure | `coerce_failed == {"g": "abc"}`, `"g"` in neither `resolved` nor `unresolved` |
| `../x.img`, `/etc/passwd` | `image_path is None`, `image_path_rejected` equals the raw text |
| real OHRC label (`data`) | `instrument == "orbiter high resolution camera"`; `resolved["corner1_lat"]` starts with `"System_Level_Coordinates/"` |
