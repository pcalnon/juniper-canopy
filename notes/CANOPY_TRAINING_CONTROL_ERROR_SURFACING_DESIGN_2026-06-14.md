# Canopy Training-Control Error Surfacing — Design & Root Cause

**Project**: juniper-canopy — Real-time monitoring dashboard
**Author**: Paul Calnon
**License**: MIT License
**Status**: Implemented (PR pending review) — clientside path requires live browser verification before merge
**Last Updated**: 2026-06-14

---

## 1. Problem — the "dead button" class

Clicking a training-control button (**Start / Pause / Stop / Resume / Reset**)
that the backend then **rejects** produces no user-visible feedback. The button
flips to its optimistic "pending" state, the command fails, the button silently
re-enables a moment later, and the user is left with no idea *that* it failed —
let alone *why*.

This surfaced acutely while verifying cascor dual-path growth (#319): a live
dataset swap was 401/502-ing because of the cascor secret-indirection bug
(cascor#331), and a training **Start** that depended on it was being rejected by
the cascor FSM with a 409. From the dashboard, all of this was invisible — the
button just bounced back. The backend half of that incident is fixed in
cascor#331 (the `secrets_util` import bug) and cascor#332 (auto-start default +
**409 detail now names the specific reason**, e.g. `Training cannot be started:
Training data not provided`). This document covers the **canopy half**: making
the dashboard actually *show* the rejection — and the now-specific reason — to
the operator.

This is a recurring failure class ("dead button"): a control action whose error
path terminates in a log line / `console.warn` with no UI surface.

---

## 2. Root cause — both transports are silent

Canopy has **two** training-button transports, gated by
`settings.enable_ws_control_buttons` (`src/settings.py:304`). **The production
default is `True`** → the clientside WS path is what real users hit. Both paths
swallow failures:

### 2.1 Clientside WS path (production default) — `PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS` (`dashboard_manager.py:108`)

- The callback returns `success: true` **synchronously** on every click
  (`dashboard_manager.py:194` / `:202`) — *before* the real outcome is known.
- The real outcome resolves **asynchronously**:
  - `window.cascorControlWS.send()` returns a Promise that **rejects** when
    cascor acks an error (`assets/websocket_client.js:442-446`:
    `data.status === 'error'` → `reject(new Error(data.error))`, with
    `err.code = data.code`) — i.e. a genuine 409/command rejection rejects the
    promise — and also rejects on disconnect/timeout.
  - On rejection the JS calls `restFallback(...)`, which re-issues the command
    over REST (`fetch('/api/train/<cmd>')`).
  - **Every failure branch dead-ends at `console.warn` / `console.error`**
    (`:147`, `:153`, `:157`, `:160`, `:184`, `:191`). Nothing reaches the DOM.

### 2.2 Server-side REST path (non-default) — `_handle_training_buttons_handler` (`dashboard_manager.py:4668`)

- On failure it logs a WARNING (`:4717`), re-enables the button (`:4720`), and
  stores `success: False` into the `training-control-action` store (`:4721`).
- **Nothing consumes `success`.** The only reader of that store is
  `update_last_click` (`:3027`), which uses `last` + `ts` for debounce and
  ignores `success`. The response body (the *reason*) is discarded entirely.

So the failure signal either never leaves the browser console (WS path) or is
computed-then-dropped (REST path).

---

## 3. Design — one shared outcome surface, fed by both transports

Mirror the **established** canopy idiom for control-action outcomes — the live
dataset-swap uses a fixed-position `html.Div` filled with a dismissable
`dbc.Alert` (`live-switch-outcome-alert`, `dashboard_manager.py:1818`) — and the
**established** Phase D §S10 mechanism for pushing async clientside results into
a Dash store: `dash_clientside.set_props(store_id, {data: ...})` (already used in
`assets/context_menus.js`, `assets/tutorial_walkthrough.js`,
`assets/snapshot_context_menu.js`). Nothing here is novel; it is the union of two
patterns already in the codebase.

Four additive changes, all on currently-dead failure branches (the success path
is untouched):

1. **Layout** — add a fixed-position alert surface
   `training-control-outcome-alert` next to the `training-control-action` store
   (`dashboard_manager.py:1821`), offset from `live-switch-outcome-alert` so they
   never overlap.

2. **Server-side handler** — capture the rejection *detail* (parse the cascor
   error JSON / status, falling back to `str(exc)`) and store it as
   `{success: False, command, detail}` in `training-control-action`. A new
   `_extract_training_error_detail()` helper isolates the parse so it is
   unit-testable and never itself raises.

3. **Render callback** — a single, unconditionally-registered callback
   `Input("training-control-action", "data") → Output("training-control-outcome-alert", "children")`
   (`_surface_training_control_outcome_handler`). On `success is False` it renders
   `dbc.Alert([Strong("<Label> failed. "), Span(detail)], color="danger",
   dismissable=True, duration=8000)`; on success it clears the surface (returns
   `None`) so a later success dismisses a stale error. Both transports feed this
   one callback.

4. **Clientside JS** — add a `reportFailure(cmd, detail)` helper that writes the
   **real** async outcome into the same store via
   `dash_clientside.set_props('training-control-action', {data:{...success:false, command, detail}})`,
   and call it from `restFallback`'s two failure branches (non-OK response — body
   read for the reason — and network `.catch`). Because the WS-reject path already
   routes through `restFallback`, this one reporting site covers WS rejections,
   WS-down→REST, and pure-REST failures. The synchronous `success:true` return is
   unchanged, so the optimistic UI is preserved; the store is simply *corrected*
   to `success:false` when the command actually fails.

### Resolution / precedence summary

| Transport                         | Failure detection                                   | Surfaced via                |
| --------------------------------- | --------------------------------------------------- | --------------------------- |
| WS command rejected (409/error)   | `send()` Promise rejects → `restFallback` → non-OK  | `set_props` → render cb     |
| WS down / timeout                 | `send()` rejects → `restFallback` (REST) → outcome  | `set_props` → render cb     |
| Pure REST (flag off / WS absent)  | `fetch` non-OK or `.catch`                          | `set_props` → render cb     |
| Server-side handler (flag off)    | `requests.post` raises / non-2xx                    | store `success:False` → cb  |

---

## 4. Test strategy

- **Unit (Python, fully covered):**
  - `_extract_training_error_detail()` — HTTPError-with-JSON-body, HTTPError
    with plain text, bare connection error, never raises.
  - `_handle_training_buttons_handler` failure now returns `command` + `detail`
    in the action dict (extends existing `test_handle_training_buttons_failure`).
  - `_surface_training_control_outcome_handler` — `None`/success → clear;
    `success:False` → `dbc.Alert` with `color="danger"` and the detail text.
  - The render callback is registered exactly once regardless of the flag.
- **JS contract (static string assertions, mirrors
  `test_phase_d_button_clientside.py`):** the JS now contains a `set_props` call
  targeting `training-control-action` with `success: false`, invoked from the
  REST-fallback failure branches.
- **Browser end-to-end:** the actual `set_props`→render round-trip can only be
  verified in a live browser (consistent with canopy's documented Playwright /
  clientside limitations). **This PR must be live-verified on the deployed stack
  before merge** — force a Start while the FSM will reject it and confirm the red
  alert appears with the cascor reason.

---

## 5. Risk

Low-to-medium. All edits are **additive on failure branches that today dead-end
in the console**; the success path, optimistic button states, debounce, and
timeout sweeper are untouched. The clientside mechanism (`set_props` into a
store) is already load-bearing elsewhere in canopy. The one residual is that the
`set_props`→render round-trip is not Python-unit-testable, hence the
live-verification gate above.

---

## 6. Noted follow-ups (out of scope, trigger-conditioned)

- **WS-reject double-send.** A *definitive* command rejection (`err.code` set
  from a cascor error ack) still triggers a REST re-send via `restFallback`
  (pre-existing behavior). For non-idempotent commands this double-sends. A
  future change could short-circuit `restFallback` when `err.code` indicates a
  definitive rejection and report `err.message` directly (it is the most precise
  reason). Deferred because it changes existing fallback behavior; surfacing the
  error is the higher-value, lower-risk half and is what this PR ships.
- **Success confirmation.** This PR intentionally surfaces only *failures* — the
  optimistic button state + status broadcast already convey success. A brief
  green confirmation could be layered later if operators want positive ack.
