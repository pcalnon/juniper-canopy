# Juniper-Canopy — "Start Training" HTTP 401 "Missing API key" — Findings Audit

**Project**: Juniper
**Sub-Project**: JuniperCanopy
**Application**: juniper_canopy
**Author**: Paul Calnon (audit by Claude Code, Opus 4.8)
**License**: MIT License
**Date**: 2026-06-29
**Repo / commit**: `pcalnon/juniper-canopy` @ `main` `79292bd` (worktree `juniper-canopy--docs--cascor-401-handoff--20260629-2137--79292bdc`)
**Scope**: Root-cause the red banner `Start failed. HTTP 401: Missing API key. Provide X-API-Key header.` on the Canopy dashboard Start Training control (port 8050). Lens: correctness / auth wiring. READ-ONLY; no source changed.
**Screenshot (reference)**: `/home/pcalnon/Pictures/Screenshots/Screenshot From 2026-06-29 21-25-53.png`

> All paths below are **repo-relative** to juniper-canopy (cite e.g. `src/security.py:90`). One cross-repo doc is in `juniper-ml`, explicitly prefixed.

---

## TL;DR

The 401 is raised by **Canopy's own** `SecurityMiddleware` (port 8050), not by juniper-cascor.
With API-key auth **enabled** (a non-empty `CANOPY_API_KEY` is set in the running `juniper-canopy:latest` **Docker** container), the Start button — which under the default `enable_ws_control_buttons = True` (`src/settings.py:325`) runs as a **browser-side `fetch('/api/train/start')`** (`src/frontend/dashboard_manager.py:175`) that carries **no `X-API-Key`** — is rejected at `src/security.py:88-91`.
The `X-API-Key`-injection fix that exists (`internal_api_headers()`) only covers **server-side** self-calls, never browser-originated ones; the WS "happy path" can't save it because the browser control-WS is also closed for lack of a key (`src/main.py:496-500`) and `/api/csrf` itself 401s.

---

## Error & reproduction

- **Symptom**: Dashboard `http://localhost:8050/dashboard/` → click **Start Training** → red dismissable alert `Start failed. HTTP 401: Missing API key. Provide X-API-Key header.`; status stays `Stopped` / `Idle`.
- **Direct API**: `GET http://localhost:8050/v1/` returns the same JSON detail.
- **Live confirmation (read-only curl, this audit, against the running service):**
  - `GET /v1/` → `HTTP/1.1 401` `{"detail":"Missing API key. Provide X-API-Key header."}`
  - `GET /api/train/status` → `HTTP/1.1 401` (same body) — this is the exact route family Start hits.
  - `GET /api/csrf` → `HTTP/1.1 401` (same body) — the control-WS auth dependency.
  - `GET /v1/health` → `HTTP/1.1 200` (an exempt path; proves the server is up and auth is selective).
- **What is actually serving :8050** — a **Docker container**, not the on-host conda process:
  - `docker ps` → `juniper-canopy 127.0.0.1:8050->8050/tcp juniper-canopy:latest`
  - `ss -ltnp` shows `LISTEN 127.0.0.1:8050` with no host PID (containerized).
  - **Consequence for the fresh thread**: the live behaviour is the **juniper-deploy** stack's container. Touching the `JuniperCanopy1` conda env will *not* change what answers :8050; you must inspect / rebuild / re-env the container.

---

## Root-cause analysis (ranked)

### H1 — ROOT CAUSE (verified): browser-originated Start carries no `X-API-Key`

Under the default `enable_ws_control_buttons = True` (`src/settings.py:325`, "D-49: P12b flag-flip — production soak passed"), the training buttons are registered as a **Dash clientside callback** (`src/frontend/dashboard_manager.py:3578-3602`, gated `if getattr(self._settings, "enable_ws_control_buttons", False)`). The JS (`PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS`, defined `:109`, wired `:3580`) runs **in the browser** and, when the control-WS is not connected, falls back to:

```text
fetch('/api/train/' + command, { method: 'POST', credentials: 'same-origin' })   # :175
```

(`fetchOpts` only ever adds `Content-Type` for a one-shot start body — `:170-174`; it **never** sets `X-API-Key` and cannot carry the per-process internal token.) `/api/train/start` is **not** an exempt path, so the request is gated by `SecurityMiddleware` → `APIKeyAuth.__call__` → 401:

- `src/middleware.py:108-116` — non-exempt path → `await self._api_key_auth(request)`
- `src/security.py:82` reads `request.headers.get("X-API-Key")`; `:87-91` raises `HTTPException(401, "Missing API key. Provide X-API-Key header.")`
- `src/middleware.py:120-125` converts it to `JSONResponse({"detail": ...})`

The JS then renders the banner: `reportFailure('HTTP ' + resp.status + (msg ? ': ' + msg : ''))` (`:187`, where `msg` is the parsed `.detail` `:183`) → stored to `training-control-action` (`:154`) → `_surface_training_control_outcome_handler` builds `dbc.Alert([Strong(f"{label} failed. "), Span(detail)])` (`:5482`; label "Start" from `:5462`). This reproduces the exact screenshot string.

**Decisive evidence**: live `GET /api/train/status` → 401, and the banner text can only be produced by a **keyless** call — the alternative server-side handler **does** send the key (see H1-contrast), so it could not have produced "Missing API key".

### H1-contrast — why the same banner from the *server-side* path is impossible

When the flag is **off**, the `else` branch registers a **server-side** `@app.callback` (`src/frontend/dashboard_manager.py:3603-3640` → handler `:5396-5416`) that calls `requests.post(self._api_url('/api/train/{command}'), headers=internal_api_headers())` (`:5400`). `internal_api_headers()` **does** attach `X-API-Key` when configured (`src/frontend/internal_api.py:75-78`). That path would return 200 under auth. Therefore the failure is specifically the **browser** path (flag = True), not this one.

### H1b — compounding (verified): the WS "happy path" cannot authenticate either

The clientside JS prefers `window.cascorControlWS.send()` and only falls back to REST when the socket isn't OPEN (`dashboard_manager.py:203-245`; `send()` rejects if not OPEN, `websocket_client.js:404-409`). Under enabled auth the control-WS can never open:

- `_authenticate_websocket` (`src/main.py:488-501`) — when `api_key_auth.enabled`, reads `X-API-Key` header **or** `?api_key` query param; on miss → `websocket.close(code=4001)` → `False`. `/ws/control` returns immediately (`src/main.py:674-675`).
- The browser builds `ws://<host>/ws/control` with **no** `?api_key` (`src/frontend/assets/websocket_client.js:516-517`); browsers cannot set custom WS headers. So the socket is closed 4001 before the CSRF gate (`src/main.py:708-721`) is even reached.
- Even the CSRF gate would fail: the token comes from `GET /api/csrf` (`websocket_client.js:522-542`), which is itself auth-protected and **401s live**, leaving `window.__canopy_csrf = null` so the auth frame is skipped (`websocket_client.js:79-85`).

Net: WS down → REST fallback → 401, deterministically, on every click.

### H2 — auth activation is confirmed-ON; the source is the deploy container (value unconfirmed)

Auth is enabled iff `get_secret("CANOPY_API_KEY")` is non-empty (`src/security.py:259` → `APIKeyAuth._enabled` `:48`,`:64`). The repo sets this **nowhere**: no `CANOPY_API_KEY` in `.env.dev` / `.env.example` / `.env.prod`, none in `conf/init.conf` (sourced by `util/juniper_canopy.bash:65`), none in any launcher/script (grep empty); no plain `.env` on disk.
It is supplied by the **running container's environment** (most likely `CANOPY_API_KEY_FILE` → a Docker secret; `get_secret` honours `<NAME>_FILE` first — `src/secrets_util.py:55-62`). The exact file/value lives in **juniper-deploy** and was **not** read in this audit (see Open Questions). Same toggle also disables the docs UI (`src/main.py:337`).

### H3 — "key configured but not plumbed into the Start call" — PARTIAL / subsumed by H1

True in spirit but imprecise: the server-side path *is* plumbed (`:5400`); the browser path **structurally cannot** carry the server key.
The real defect is that the `X-API-Key`-injection remedy (Option B, canopy#265 — see notes) only ever covered **server-side** `requests.*` self-calls and was never extended to the browser-originated Phase D control path or the `/api/csrf` XHR. The `enable_ws_control_buttons` default-flip to `True` (D-49) is the change that moved Start onto the uncovered browser path; under enabled auth that is a regression.

### H4 — juniper-cascor (8201) involvement — RULED OUT for this 401

The `/api/train/start` route handler (`src/main.py:2864-2882`) calls `backend.start_training()` (`:2879`), which for a live cascor backend would make an **outbound** call to juniper-cascor (8201, with cascor's own `X-API-Key`).
But that handler runs only **after** the middleware admits the request. The middleware 401s first, so the cascor call never happens. **This 401 is purely Canopy-side (8050).** (The cascor `src/api/security.py:75` and `juniper-ml/juniper-service-core/.../security.py:82` copies of the same string are not in this path.)

---

## The auth activation toggle (exact)

| Aspect                    | Value                                                                                                                                                                                                                          |
|---------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Enabling condition        | `get_secret("CANOPY_API_KEY")` returns non-empty → `APIKeyAuth(enabled=True)` (`src/security.py:48,64,259`)                                                                                                                    |
| Env var (direct)          | `CANOPY_API_KEY` (bare; read via `os.environ`, **not** the `JUNIPER_CANOPY_` pydantic prefix)                                                                                                                                  |
| File indirection          | `CANOPY_API_KEY_FILE` → path → file contents (preferred; `src/secrets_util.py:55-62`)                                                                                                                                          |
| Where it is set live      | The `juniper-canopy:latest` container env (juniper-deploy) — **not** in this repo                                                                                                                                              |
| Header the server expects | `X-API-Key: <value>` (`src/security.py:21,82`)                                                                                                                                                                                 |
| Enforcement               | `SecurityMiddleware` (`src/middleware.py:70`, added `src/main.py:367-369`), runs **before routing**, so even non-existent paths like `/v1/` 401 instead of 404                                                                 |
| Exempt paths              | exact: `/health`, `/api/health`, `/v1/health`, `/v1/health/live`, `/v1/health/ready` (`src/canopy_constants.py:355-362`); prefixes: `/dashboard`, `/metrics` (`:353`). **`/api/train/*`, `/api/csrf`, `/v1/` are NOT exempt.** |
| Side effect               | `_docs_enabled = not get_secret("CANOPY_API_KEY")` → `/docs`,`/redoc`,`/openapi.json` disabled (`src/main.py:337`)                                                                                                             |

---

## The Start-Training call path (file:line)

1. Button: `dbc.Button("▶ Start Training", id="start-button", ...)` — `src/frontend/dashboard_manager.py:811-813`.
2. Active callback (flag True, default): clientside JS `PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS` registered `src/frontend/dashboard_manager.py:3578-3602`; Outputs `training-control-action`,`button-states`.
3. JS maps `start-button → "start"` (`:121`); tries `window.cascorControlWS.send({command:"start",...})` (`:218-222`).
4. Control-WS is closed under auth (`src/main.py:496-500`; browser URL has no key `websocket_client.js:516`) → `send()` rejects / not OPEN → REST fallback `restFallback()` (`:163-201`).
5. **`fetch('/api/train/start', {method:'POST', credentials:'same-origin'})`** — `:175` — **no `X-API-Key`**.
6. Server route `@app.post("/api/train/start")` — `src/main.py:2864`; but the request is intercepted first by `SecurityMiddleware.dispatch` (`src/middleware.py:94-116`) → `APIKeyAuth.__call__` 401 (`src/security.py:87-91`) → JSONResponse (`src/middleware.py:120-125`).
7. JS: `resp.ok` false → `reportFailure('HTTP 401: ' + detail)` (`:177-190`) → `set_props('training-control-action', {success:false, command:"start", detail:"HTTP 401: Missing API key. Provide X-API-Key header."})` (`:151-157`).
8. `surface_training_control_outcome` callback (`:3664-3666`) → `_surface_training_control_outcome_handler` (`:5464-5486`) → `dbc.Alert(["Start failed. ", "HTTP 401: Missing API key. Provide X-API-Key header."])` (`:5482`).

**Endpoint hit (the failing inbound request)**: `POST http://localhost:8050/api/train/start` (Canopy's own API), unauthenticated, from the browser.

---

## Relevant existing notes docs

| Doc | Relevance |
| --- | --- |
| `juniper-ml/notes/observability/JUNIPER_2026-05-10_JUNIPER-CANOPY_DASHBOARD-SELF-CALL-REFACTOR.md` | **Most relevant.** Docs Opt-B (X-API-Key injection in **server-side** self-calls, shipped canopy#265) vs deferred Opt-C (in-process calls). Writes why **browser-originated** calls (this bug) were never covered. Cross-repo. |
| `notes/CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md` | Designs the "`{label} failed.`" danger-alert surfacing that renders this 401; both transports feed `training-control-action`. Explains the banner mechanism (not the auth cause). |
| `notes/fixes/FIX_FRONTEND_REGRESSIONS_2026-05-30.md` | Frontend-regression remediation observed on the **deployed docker stack** (Bug-4 class, canopy↔cascor); same deploy context as this failure. |
| `notes/CANOPY_RUNTIME_CLIENT_FLOOR_DRIFT_ROOT_CAUSE_2026-06-26.md` | Prior "green tests / dead app" root-cause writeup (client-wheel floor drift). Different root cause, but the same "tests pass, runtime breaks" methodology applies. |
| `src/frontend/internal_api.py:18-40` (docstring) | In-code statement that the helper is for **server-side** self-calls only, and points to the self-call refactor doc above. |
| **juniper-deploy** (cross-repo, not read) | Where `CANOPY_API_KEY[_FILE]` for the container is actually set (compose `secrets:` / `secrets/` dir). Must be inspected to obtain the live key. |

---

## Verification commands (for the fresh thread)

```bash
# 0. Confirm WHAT serves :8050 (expect the deploy container, not conda):
docker ps --format '{{.Names}}  {{.Ports}}  {{.Image}}' | grep -i canopy
#   -> juniper-canopy  127.0.0.1:8050->8050/tcp  juniper-canopy:latest

# 1. Reproduce the 401 on the protected routes (no key):
curl -sS -i http://localhost:8050/v1/                 # expect 401 "Missing API key..."
curl -sS -i http://localhost:8050/api/train/status    # expect 401 (the Start route family)
curl -sS -i http://localhost:8050/api/csrf            # expect 401 (why the control-WS can't auth)
curl -sS -i http://localhost:8050/v1/health           # expect 200 (exempt -> proves auth is selective)

# 2. Confirm auth is ENABLED in the running container + find the configured key:
docker exec juniper-canopy printenv | grep -iE 'CANOPY_API_KEY|CANOPY_API_KEY_FILE'
#   if *_FILE is set:  docker exec juniper-canopy sh -c 'cat "$CANOPY_API_KEY_FILE"'
#   (otherwise inspect juniper-deploy compose `secrets:` + ./secrets/ for the value)

# 3. Prove the key is the cure (replace <key> with the value from step 2):
curl -sS -i -H "X-API-Key: <key>" http://localhost:8050/api/train/status   # expect 200
curl -sS -i -X POST -H "X-API-Key: <key>" http://localhost:8050/api/train/start  # expect 200/started

# 4. Confirm the flag that selects the browser (clientside) Start path:
grep -n 'enable_ws_control_buttons' src/settings.py    # = True (src/settings.py:325)

# 5. Confirm the exempt-path set (so you know /api/train + /api/csrf are NOT exempt):
grep -n 'EXEMPT_PATH' src/canopy_constants.py           # :353 prefixes, :355-362 exact paths
```

---

## Open questions for the fresh thread

1. **Exact activation source/value** — which juniper-deploy artifact sets `CANOPY_API_KEY[_FILE]` for the container, and is it an intentional secret or a placeholder/`secrets.example` fallback (prior memory: "secrets.example fallback enables canopy auth")? **Unconfirmed** — read juniper-deploy.
2. **Is the on-host conda (`JuniperCanopy1`) canopy also running?** It did **not** own :8050 (the container does). If the user expects the conda process, that is a separate discrepancy. **Unconfirmed.**
3. **Intended fix direction (design decision — NOT decided here).** Candidates, each with a trade-off:
   - Make same-origin **browser** control endpoints (`/api/train/*`, `/api/csrf`, `/ws/control`) accept the **CSRF/session cookie** instead of `X-API-Key` (the session/CSRF machinery already exists: `SessionMiddleware`, `csrf_enabled` `src/settings.py:331`, `/api/csrf` `src/main.py:474`). But `/api/csrf` is currently behind the same key gate — chicken/egg to resolve.
   - Exempt the browser-control surface from `APIKeyAuth` while keeping CSRF/Origin/session protections (`/ws/control` already enforces Origin + CSRF + per-IP cap, `src/main.py:682-721`).
   - Pursue Option C (in-process calls) for the server-side share; does not by itself fix the **browser** path.
   - Set `enable_ws_control_buttons = False` to revert Start onto the key-injected server-side handler — a mitigation, not a real fix (loses the WS-control UX and leaves `/api/csrf` browser breakage if anything else needs it).
   - Do **not** simply expose the server `X-API-Key` to the browser (defeats the auth boundary).
4. **`ws_auth_enabled` (SEC-06 bearer subprotocol, `src/main.py:507-537`)** offers a browser-usable `Sec-WebSocket-Protocol: bearer,<token>` path, but `websocket_client.js` does not use it and it still needs the token in the browser. Whether it is enabled in the container, and whether it is relevant, is **unconfirmed**.
5. **Precise WS close behaviour** beyond the 4001 X-API-Key gate (CSRF 1008 path `src/main.py:719-720`) was read but not live-traced against the running container; the REST-fallback outcome is what the screenshot proves.

---

## Summary (counts)

- **Verified-fail findings**: H1 (root cause), H1b (WS compounding), live 401s on `/v1/`, `/api/train/status`, `/api/csrf`.
- **Verified-pass / ruled-out**: H4 (cascor not involved); server-side handler path would succeed (H1-contrast); `/v1/health` exempt 200.
- **Could-not-verify (needs fresh thread)**: exact `CANOPY_API_KEY` source/value in the container (juniper-deploy); whether on-host conda canopy is running; chosen fix design.
