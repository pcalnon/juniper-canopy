# `util/ad-hoc/` — Single-use, temporary, and unfinished scripts

This directory is the home for scripts that:

- Will run once (or a handful of times) and then be retired.
- Are work-in-progress and not yet ready for promotion to `util/` proper.
- Support a one-off investigation, migration, or analysis tied to a specific PR / incident.

It exists because the alternative — authoring such scripts in `/tmp/` — caused real, irrecoverable loss in the v1–v4 juniper-ml requirements-snapshot effort (`phase4_consolidate.py`, `v2_citation_validate.py`).

The repo-level rule lives in [`../../AGENTS.md`](../../AGENTS.md#file-placement-rules); the ecosystem-level restatement lives in the parent `Juniper/AGENTS.md` "Cross-Project Conventions" section (one directory above this repo, outside the juniper-canopy git tree).

---

## Conventions

### File header (Python)

Every Python script in this directory should declare its scope and lifecycle inline:

```python
"""
<one-line purpose>

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: <name>
Created: YYYY-MM-DD
Status: ad-hoc — <intent: one-off | wip | migration | investigation>
Retire when: <condition that makes this script obsolete>
Related: <PR #, incident, or notes/ doc>
"""
```

### File header (bash)

```bash
#!/usr/bin/env bash
# <one-line purpose>
#
# Project:    juniper-canopy
# Sub-Project: ad-hoc tooling
# Author:     <name>
# Created:    YYYY-MM-DD
# Status:     ad-hoc — <one-off | wip | migration | investigation>
# Retire when: <condition>
# Related:    <PR #, incident, notes/ doc>
set -euo pipefail
```

### Naming

- Date-prefix optional but useful: `YYYY-MM-DD_<short-purpose>.{py,bash}`.
- Use kebab-case or snake_case consistently — match existing siblings.

---

## Lifecycle

| Stage                                      | Action                                                                                                                                                       |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Created**                                | Place here. Include the header above with `Retire when:` populated.                                                                                          |
| **Used for its purpose**                   | Commit any non-trivial output / log alongside the script (e.g., in `notes/`) so the artifact survives the script.                                            |
| **Graduates to permanent utility**         | Move to `util/<name>` (drop `ad-hoc` from the header `Status:`). Update any docs that referenced the old path.                                               |
| **Retired (purpose complete or obsolete)** | Delete in the same PR that completes the work, OR move to `util/ad-hoc/retired/` with the retirement date in the filename. Don't leave dead scripts behind.  |

---

## Operational: X7 adapter callgraph

`2026-09-04_async_blocking_callgraph.py` is the instrument for sites the committed
`main.py` gate cannot see (adapter `self.*` methods whose body reaches the network).
**Run it when touching `cascor_service_adapter.py` or `service_backend.py`.**

```bash
python util/ad-hoc/2026-09-04_async_blocking_callgraph.py
python util/ad-hoc/2026-09-04_async_blocking_callgraph.py --all
```

Exit status is always 0 (instrument, not a gate). Requires a sibling
`juniper-cascor-client` checkout — a missing corpus prints a confident `0`. See
[Event-loop I/O discipline (X7)](../../docs/AGENTS_REFERENCE.md#event-loop-io-discipline-x7).

The script landed with slice 1a (`#567`).

---

## What does NOT belong here

- Scripts that are part of a documented build / test / release flow → `util/` proper or `scripts/`.
- Scripts called by CI workflows → `util/` proper (CI should never invoke `util/ad-hoc/`).
- Tests → `src/tests/`.
- Generated artifacts (lockfiles, dep docs, build output) → wherever the build tooling expects.
