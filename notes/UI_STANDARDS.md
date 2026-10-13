# Juniper-Canopy UI Standards

**Version**: 0.1.0 (initial — born from `notes/FRONTEND_ISSUES_PLAN_2026-05-09.md` §6)
**Source of truth**: [`src/frontend/ui_standards.py`](../src/frontend/ui_standards.py)
**Doc-vs-code drift gate**: [`src/tests/regression/test_ui_standards_doc_in_sync.py`](../src/tests/regression/test_ui_standards_doc_in_sync.py)

This document is the human-readable companion to `src/frontend/ui_standards.py`.
The code is authoritative — every rule below is pinned by a test that reads
from `ui_standards.py` and fails if the rendered DOM (or this doc) disagrees.

---

## Layout grid

- Bootstrap 12-column grid.
- Every sidebar/visualization width pair must sum to `GRID_COLUMNS` (12).
- Pinned by `tests/regression/test_tab_sidebar_widths.py`.

---

## Sidebar widths per tab class

Two width classes ship today (PR-9). Intermediate widths may be added once
the Training-Metrics narrowing experiment (open question below) maps the
empirical break-point for the longest sidebar label.

| Class | Width | Tabs |
|-------|------:|------|
| wide | 3 | metrics, candidates, network-editor, topology, dataset |
| narrow | 2 | boundaries, evolution, parameters, snapshots, replay, workers, about, tutorial, redis, cassandra |

The full per-tab map lives at `TAB_SIDEBAR_WIDTH` in `ui_standards.py`.
`test_ui_standards_doc_in_sync.py` parses the table above on every CI
run and fails if any cell drifts from the constants module.

---

## Numeric input UX

- **Debounce**: `DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS = 350` (PR-8 §2.5 B). Typed values commit ~350 ms after the last keystroke without requiring blur.
- **Force blur on Apply**: clientside callback fires on `apply-params-button` click, blurring `document.activeElement` so any pending debounced numeric value commits *before* the server-side `State()` reads (PR-8 §2.5 C).
- **Out-of-range entries**: per-field validation styling via Dash's `is-invalid` class (deferred to a follow-up — id migration + pattern-matching MATCH callback; see plan §2.5 D).

Regression net: `tests/regression/test_numeric_input_debounce_uniform.py`
fails if any new `dbc.Input` reverts to the boolean `debounce=True`/`False`
form. Use `DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS`.

---

## Color, typography, spacing

TBD — placeholder for the next round of UX work. Each new section here
must include both a human-readable rule and a corresponding
machine-checkable assertion under `src/tests/`.

---

## Open questions

### Training-Metrics narrowing experiment (deferred)

The Training Metrics tab carries the longest sidebar label
("Maximum Hidden Units:" — ~22 ch) and currently sits in the **wide**
class as a safe default. Spec §6.4 calls for a Playwright width-experiment
to find the empirical break-point — likely involves shrinking the input
control width too. If that experiment shows `NARROW_SIDEBAR` is viable on
Training Metrics:

1. Move `"metrics": NARROW_SIDEBAR` in `ui_standards.TAB_SIDEBAR_WIDTH`.
2. Update the table above (or rely on the doc-sync test to flag the
   stale entry).
3. Document the input-control-width adjustment under "Color, typography,
   spacing" with its own constant + test.

The experiment is intentionally not run in PR-9.5 — it requires hands-on
visual review of label-wrap behavior and is better tracked as a separate
tuning PR.

---

## Adding to this document

1. Edit `src/frontend/ui_standards.py` (add the constant — code is the
   source of truth).
2. Edit this file (describe the rule for humans).
3. Add an assertion under `src/tests/regression/` or `src/tests/ui/`
   that reads from `ui_standards.py` and fails if the rendered DOM
   disagrees. The doc-sync test (above) covers the table; new
   constants need their own test.

The order matters: if you forget step 3, future drift goes
undetected; if you forget step 2, the doc lies; if you forget step 1,
the code is your spec and that's a different problem entirely.
