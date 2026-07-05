# HANDOFF — Canopy "Start Training" → HTTP 401 "Missing API key"

**Sub-Project**: JuniperCanopy · **Date**: 2026-06-29 · **Type**: Debugging handoff (CRITICAL, unresolved)
**Repo / commit**: `pcalnon/juniper-canopy` @ `main` `79292bd`
**Prior work**: root-cause audit COMPLETE (read-only); this thread must DECIDE the fix, implement it, and verify.

> Paste this as the opening prompt of a fresh Claude Code thread. It follows
> [`notes/THREAD_HANDOFF_PROCEDURE.md`](../../notes/THREAD_HANDOFF_PROCEDURE.md) (Debugging template).
> Re-read any file before editing it; spot-check (don't re-derive) the `file:line` anchors below.

---

## Mission (one line)

**Diagnose & fix: Canopy "Start Training" fails with `HTTP 401 Missing API key`.** The audit is done; pick a fix direction, implement, verify.

## The error (verbatim)

Dashboard `http://localhost:8050/dashboard/` → click **Start Training** → red dismissable banner:

```text
Start failed. HTTP 401: Missing API key. Provide X-API-Key header.
```

`GET http://localhost:8050/v1/` returns the same `{"detail":"Missing API key. Provide X-API-Key header."}`.
Screenshot: `/home/pcalnon/Pictures/Screenshots/Screenshot From 2026-06-29 21-25-53.png`.

> **Naming note**: the branch/filename say "cascor", but the audit **ruled cascor out** (H4). The 401 is **purely Canopy-side (port 8050)**.

## CRITICAL FRAMING — what is actually serving :8050

The live failing service is the **juniper-deploy Docker container** (`juniper-canopy 127.0.0.1:8050->8050/tcp juniper-canopy:latest`), **not** the on-host `JuniperCanopy1` conda process. Editing/restarting the conda env will **not** change what answers :8050 — you must inspect / re-env / rebuild the container, and the `CANOPY_API_KEY` value lives in **juniper-deploy**, not this repo. Confirm with `docker ps` before touching anything (see Verification step 0).

---

## Completed so far

- **Full root-cause audit** (READ-ONLY, no source changed): [`notes/JUNIPER_CANOPY_CASCOR-TRAINING-401-APIKEY_AUDIT_2026-06-29.md`](../../notes/JUNIPER_CANOPY_CASCOR-TRAINING-401-APIKEY_AUDIT_2026-06-29.md). Read it first — it has the full ranked analysis, the toggle table, and the call-path with every `file:line`.
- Root cause **verified** (H1) with live curls: the 401 is raised by **Canopy's own** `SecurityMiddleware` (8050), not cascor.
- Ruled out: cascor (8201) involvement (H4 — middleware 401s before any outbound cascor call).

## Remaining work

1. **Decide the fix direction** (see "Fix options" — this is an owner/design decision; do NOT just pick the smallest patch). Consider the triad: immediate-unblock PR + correct-fix PR + a deferred design note if the correct fix is large.
2. **Confirm the unconfirmed items first** (juniper-deploy `CANOPY_API_KEY` source; whether on-host conda canopy is also up).
3. **Implement** the chosen fix in a **new worktree / branch** (this is a code work-unit, separate from the docs branch).
4. **Verify** against the running container (curls below should flip 401 → 200) and re-click Start in the browser.

## Key context (root cause, in brief)

- **Auth toggle**: enabled iff `get_secret("CANOPY_API_KEY")` is non-empty → `APIKeyAuth(api_keys=[…])` whose derived `.enabled` property is then `True` (`src/security.py:48,64,259`; `enabled` is computed from `len(api_keys) > 0`, not a constructor kwarg).
  Bare env `CANOPY_API_KEY` (read via `os.environ`, **not** the `JUNIPER_CANOPY_` pydantic prefix); file form `CANOPY_API_KEY_FILE` preferred (`src/secrets_util.py:55-62`). Set **nowhere in this repo** — supplied by the container env (juniper-deploy). It is currently **ON**.
- **Why Start fails**: under the default `enable_ws_control_buttons = True` (`src/settings.py:325`, "D-49"), Start runs as a **browser** `fetch('/api/train/start', {method:'POST', credentials:'same-origin'})` (`src/frontend/dashboard_manager.py:170-175`) that carries **no `X-API-Key`** (browsers can't get the per-process server token) → rejected at `src/security.py:82,87-91` → serialised to JSON at `src/middleware.py:116,120-125`.
- **The existing remedy doesn't cover this path**: `internal_api_headers()` injects `X-API-Key` (`src/frontend/internal_api.py:75-78`) but **only for server-side self-calls** (e.g. `dashboard_manager.py:5400`, the `enable_ws_control_buttons=False` branch). That the banner reads "Missing API key" proves the **keyless browser path** fired, not the server path.
- **WS happy-path can't save it** (H1b): the browser control-WS is closed `code=4001` for lack of a key (`src/main.py:496-500`; browser URL has no `?api_key`), forcing the REST fallback that 401s; and `/api/csrf` (the WS CSRF dependency) **also 401s**.
- **Call path**: `start-button` (`dashboard_manager.py:811-813`) → clientside JS (`:3578-3602`; JS body `:109`, fetch `:170-175`) → WS attempt (`:218-222`) closed (`main.py:496-500`) → REST `POST /api/train/start` (`:175`) → `SecurityMiddleware` (`middleware.py:94-116`) → 401 (`security.py:87-91`) → `reportFailure` (`:187`) → `surface_training_control_outcome` (`:3664-3666`) → `dbc.Alert(["{label} failed. ", detail])` (`:5482`).
- **Exempt paths** (`src/canopy_constants.py:353-362`): prefixes `/dashboard`, `/metrics`; exact health endpoints (`/health`, `/api/health`, `/v1/health[/live|/ready]`) plus bare `/`. **`/api/train/*`, `/api/csrf`, and `/v1/` are NOT exempt** — hence the 401s.

---

## Fix options (owner decides — frame as trade-offs, do NOT prescribe one)

| # | Option | Trade-off |
|---|---|---|
| **(a)** | **Immediate unblock**: set `enable_ws_control_buttons = False` (`src/settings.py:325`) so Start reverts to the **server-side** handler that already injects the key (`dashboard_manager.py:5400` + `internal_api_headers()`). | Fast, low-risk mitigation — **not a real fix**. Loses the WS-control button UX (D-49) and still leaves `/api/csrf` / any other browser XHR 401-ing under auth. |
| **(b)** | **Correct fix**: authenticate the **same-origin browser** control surface — accept the CSRF/session cookie (`csrf_enabled` `src/settings.py:331`, `/api/csrf` `src/main.py:474`) instead of `X-API-Key`, or have the JS attach a key, or extend the deferred **Option C** (self-call refactor doc). | Durable fix. Larger; resolve the chicken-and-egg that `/api/csrf` is itself behind the key gate. Do **not** expose the server `X-API-Key` to the browser. |
| **(c)** | **Exempt the browser-control surface** (`/api/train/*`, `/api/csrf`, `/ws/control`) from `APIKeyAuth` while keeping CSRF/Origin/session/per-IP protections (`/ws/control` already enforces Origin + CSRF + cap, `src/main.py:682-721`). | Surgical, preserves UX. Widens the unauthenticated surface — must prove the remaining CSRF/Origin/session controls are sufficient. |
| **(d)** | **Confirm / adjust juniper-deploy provisioning**: verify whether `CANOPY_API_KEY[_FILE]` is an intentional secret or a `secrets.example` placeholder that *accidentally* enabled auth (prior memory: "secrets.example fallback enables canopy auth"). | If accidental, the "fix" may be deploy-side, not code. Must not silently disable a real security control. |

Recommended: confirm (d) first, then choose between (a) as an immediate unblock and (b)/(c) as the correct fix; capture any large design in a deferred note.

---

## Verification commands

```bash
# 0. Confirm WHAT serves :8050 (expect the deploy container, not conda):
docker ps --format '{{.Names}}  {{.Ports}}  {{.Image}}' | grep -i canopy
#   -> juniper-canopy  127.0.0.1:8050->8050/tcp  juniper-canopy:latest

# 1. Reproduce the 401 on the protected routes (no key):
curl -sS -i http://localhost:8050/api/train/status   # expect 401 (the Start route family)
curl -sS -i http://localhost:8050/api/csrf           # expect 401 (why the control-WS can't auth)
curl -sS -i http://localhost:8050/v1/                 # expect 401 "Missing API key..."
curl -sS -i http://localhost:8050/v1/health          # expect 200 (exempt -> auth is selective)

# 2. Confirm auth is ENABLED in the running container + find the key (juniper-deploy):
docker exec juniper-canopy printenv | grep -iE 'CANOPY_API_KEY'
#   if *_FILE is set:  docker exec juniper-canopy sh -c 'cat "$CANOPY_API_KEY_FILE"'
#   else inspect juniper-deploy compose `secrets:` + ./secrets/ for the value

# 3. Prove the key is the cure (replace <key> with the value from step 2):
curl -sS -i -H "X-API-Key: <key>" http://localhost:8050/api/train/status   # expect 200

# 4. Confirm the flag that selects the browser (clientside) Start path:
grep -n 'enable_ws_control_buttons' src/settings.py    # = True (src/settings.py:325)
```

---

## Unconfirmed — verify first

1. **Exact juniper-deploy artifact/value** that sets `CANOPY_API_KEY[_FILE]` for the container — and whether it is an intentional secret or a `secrets.example` placeholder. (Not read in the audit.)
2. **Is the on-host conda `JuniperCanopy1` canopy also running?** It did **not** own :8050 (the container does). If the user expects the conda process, that's a separate discrepancy.
3. **Relevance of `ws_auth_enabled`** (SEC-06 bearer subprotocol, `src/main.py:507-537`) — offers a browser-usable `Sec-WebSocket-Protocol: bearer,<token>` path, but `websocket_client.js` doesn't use it and it still needs the token in the browser. Enabled in the container? Relevant?

---

## Reference docs

- [`notes/JUNIPER_CANOPY_CASCOR-TRAINING-401-APIKEY_AUDIT_2026-06-29.md`](../../notes/JUNIPER_CANOPY_CASCOR-TRAINING-401-APIKEY_AUDIT_2026-06-29.md) — **primary source**: full ranked root-cause, toggle table, call-path.
- `juniper-ml/notes/observability/JUNIPER_2026-05-10_JUNIPER-CANOPY_DASHBOARD-SELF-CALL-REFACTOR.md` (cross-repo) — **most relevant**: Option B (server-side `X-API-Key` injection, shipped canopy#265) vs deferred Option C; explains why **browser-originated** calls were never covered.
- [`src/frontend/internal_api.py`](../../src/frontend/internal_api.py) (module docstring) — states the helper is for **server-side** self-calls only; points to the refactor doc above.
- [`notes/CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md`](../../notes/CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md) — designs the "`{label} failed.`" danger-alert that renders this 401 (the banner mechanism, not the auth cause).
- [`notes/fixes/FIX_FRONTEND_REGRESSIONS_2026-05-30.md`](../../notes/fixes/FIX_FRONTEND_REGRESSIONS_2026-05-30.md) — frontend-regression remediation on the **deployed docker stack** (same deploy context).
- [`notes/CANOPY_RUNTIME_CLIENT_FLOOR_DRIFT_ROOT_CAUSE_2026-06-26.md`](../../notes/CANOPY_RUNTIME_CLIENT_FLOOR_DRIFT_ROOT_CAUSE_2026-06-26.md) — prior "green tests / dead app" root-cause (different cause; same "tests pass, runtime breaks" methodology).
- **juniper-deploy** (cross-repo, not read) — where the container's `CANOPY_API_KEY[_FILE]` is set (compose `secrets:` / `secrets/` dir).

---

## Git status / starting state

- **`main` @ `79292bd`** is the baseline.
- The **audit doc + this handoff** live on branch **`docs/canopy-cascor-401-handoff`** (worktree `juniper-canopy--docs--cascor-401-handoff--20260629-2137--79292bdc`), **not yet merged**. Read the audit from that branch/worktree (or after it merges).
- The **fix is a separate code work-unit** — start it in a **new worktree off `main`** with its own branch, not on the docs branch.

## Standing rules (reminders — do not duplicate CLAUDE.md)

- **Worktree isolation**: do the fix in a dedicated worktree (`notes/WORKTREE_SETUP_PROCEDURE.md`); never inside the repo dir.
- **One PR per work-unit**; open a PR — **never merge** (owner merges).
- **Never auto-approve deploy / env / PyPI gates** — drive to the gate, then hand off to the owner.
- Verify against the **running container** (juniper-deploy), and re-confirm any `file:line` before editing.
