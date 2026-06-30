# Juniper-Canopy — Authenticating the Same-Origin Browser Control Surface — Design of Record

**Project**: Juniper
**Sub-Project**: JuniperCanopy
**Application**: juniper_canopy
**Author**: Paul Calnon (design by Claude Code, Opus 4.8)
**License**: MIT License
**Date**: 2026-06-30
**Repo / commit**: `pcalnon/juniper-canopy` @ `main` `d1a13a01` (worktree `juniper-canopy--docs--training-control-auth-design--20260630-1518--d1a13a01`, branch `docs/training-control-auth-design`)
**Status**: Decision-ready design. Recommends a direction (the triad); the owner selects the implementation scope after reading.
**Scope**: Design the fix for the Canopy dashboard **Start Training → `HTTP 401: Missing API key. Provide X-API-Key header.`** failure by
**authenticating the same-origin browser control surface** (`/api/train/*`, `/api/csrf`, `/ws/control`, and the sibling browser WebSockets)
**without disabling API-key auth**. Lens: auth design / security topology. READ-ONLY — no source changed; this is one `notes/` document.
All `src/...` paths are repo-relative to juniper-canopy; cross-repo paths to juniper-ml / juniper-deploy are absolute and explicitly prefixed.

> Companion (read first): [`notes/JUNIPER_CANOPY_CASCOR-TRAINING-401-APIKEY_AUDIT_2026-06-29.md`](JUNIPER_CANOPY_CASCOR-TRAINING-401-APIKEY_AUDIT_2026-06-29.md) — the ranked root-cause audit. This design builds on it and does not re-derive it.

---

## 1. TL;DR

Keep API-key authentication **ON** — the key is a confirmed-intentional, SOPS-managed secret (juniper-deploy `.env.secrets.enc:10` ships an
encrypted `CANOPY_API_KEY`; the `.env.secrets.example:13` template is intentionally empty; the live container reads a 43-byte token from a
Docker secret). The browser **structurally cannot** hold the per-process server key (`src/security.py:31` mints `INTERNAL_REQUEST_TOKEN` fresh
each process start; browsers cannot set custom WebSocket headers and must never be handed the server `X-API-Key`).

The durable fix is therefore **not** "give the browser the key" and **not** "turn auth off." It is to **authenticate the same-origin browser
control surface with the machinery `/ws/control` already uses** — an **Origin allowlist** (`src/ws_security.py:16`, already wired and already
admits `http://localhost:8050` in the deploy) plus a **server-side CSRF token** (`src/csrf.py`, `GET /api/csrf` at `src/main.py:474`) plus the
**session cookie** (`SessionMiddleware`, `src/main.py:375`). Concretely: make `/api/csrf` reachable by the browser (exempt it from the key gate),
add the **Origin+CSRF gate to the `/api/train/*` REST routes that today have none** (the crux — see §7), and relax the **WebSocket key gate** so
`/ws/control` accepts the Origin+CSRF path it already enforces. Programmatic surfaces (`/v1/*`) stay key-gated.

This document recommends the owner's standing **triad** — (1) an immediate deploy-side unblock to restore the dashboard now, (2) the correct
Origin+CSRF browser-auth fix as the durable change, (3) **this** note as the design-of-record — but lays out all four candidate directions so
the owner can pick the implementation scope.

---

## 2. Problem recap & constraints / invariants

**What breaks (from the audit, H1):** Under the default `enable_ws_control_buttons = True` (`src/settings.py:325`), Start Training runs as a Dash
**clientside** callback (`src/frontend/dashboard_manager.py:3578-3602`). When the control WebSocket is not OPEN, the browser JS falls back to
`fetch('/api/train/' + command, { method: 'POST', credentials: 'same-origin' })` (`src/frontend/dashboard_manager.py:175`, opts built at
`:170-174`) carrying **no `X-API-Key`**. `/api/train/start` is not exempt, so `SecurityMiddleware` (`src/middleware.py:115-116`) invokes
`APIKeyAuth.__call__` which raises 401 at `src/security.py:88-91`, serialized to JSON at `src/middleware.py:120-125` and rendered as the red
banner via `_surface_training_control_outcome_handler` (`src/frontend/dashboard_manager.py:5464-5486`).

**Hard constraints (each verified):**

| # | Constraint | Evidence |
|---|---|---|
| C1 | **API-key auth stays ON** — an intentional secret, not an accident; disabling it removes a real control. Off the table. | Encrypted `CANOPY_API_KEY` in juniper-deploy `.env.secrets.enc:10`; empty template `.env.secrets.example:13`; container env `CANOPY_API_KEY_FILE: /run/secrets/canopy_api_key` (`docker-compose.yml:576`); secret def `canopy_api_key.file` (`docker-compose.yml:932-933`); on-disk `./secrets/canopy_api_key.txt` = 43 bytes. |
| C2 | **The browser cannot hold the server key.** The key authenticates *machine* callers; the per-process token is generated per start and never leaves the process. | `src/security.py:30-31`; `_authenticate_websocket` reads `X-API-Key` header or `?api_key` only (`src/main.py:497`); browsers cannot set custom WS headers — the URL is built with no key (`src/frontend/assets/websocket_client.js:516`). |
| C3 | **Do not expose the server `X-API-Key` to the browser.** Shipping the secret to every dashboard visitor defeats the auth boundary. | Design invariant; the server-side injection (`internal_api_headers()`, `src/frontend/internal_api.py:63-79`) runs only in-process. |
| C4 | **Preserve the Phase-D WS-control UX where possible.** `enable_ws_control_buttons = True` was a deliberate D-49 decision after a production soak. | `src/settings.py:325` ("D-49: P12b flag-flip — production soak passed"). |
| C5 | **`/v1/*` and other non-browser API surfaces must remain key-gated.** External / programmatic clients can and do hold a key. | `/v1/*` is not exempt (`src/canopy_constants.py:355-367`); the audit confirms live `GET /v1/` → 401. |

**Non-goals.** (a) Option C (in-process self-calls) from
`juniper-ml/notes/observability/CANOPY_DASHBOARD_SELF_CALL_REFACTOR_2026-05-10.md`
— it addresses the *server-side* self-call cost, not the *browser* path, and does not fix this 401. (b) Enabling the SEC-06 bearer subprotocol
(`ws_auth_enabled`, `src/settings.py:341`) — it still requires the token *in the browser* (§4d). (c) Re-architecting the dashboard to a separate
process. (d) Changing the secret's value or rotation.

---

## 3. Current security topology (grounded)

Every gate below was confirmed by reading the route. "Key" = `APIKeyAuth` via `SecurityMiddleware`; "Origin" = `ws_security.validate_origin`
against `settings.websocket.allowed_origins`; "CSRF" = first-frame token validated against the server-side store; "Per-IP / RL" = the WS
connection cap or the REST fixed-window rate limiter.

| Route | Primary caller | Key gate | Origin gate | CSRF gate | Per-IP / RL | Net effect today | Anchors |
|---|---|---|---|---|---|---|---|
| `/` | browser nav | exempt | — | — | — | 200 → redirect to `/dashboard/` | exempt set `src/canopy_constants.py:357`; handler `src/main.py:459-466` |
| `/dashboard/*` | browser (Dash UI) | exempt (prefix) | — | — | — | UI served anonymously (the page itself) | prefix `src/canopy_constants.py:353`; mount `src/main.py:434` |
| `/metrics` | Prometheus | exempt (prefix) | — | — | IP allowlist | scrape-only; untrusted IP → 403 | prefix `:353`; `MetricsAuthMiddleware` `src/main.py:407` |
| `/health`, `/api/health`, `/v1/health/{live,ready}` | probes | exempt | — | — | — | 200 (selective-auth proof) | `src/canopy_constants.py:355-367` |
| `/v1/*` (non-health) | **programmatic** | **KEY** | — | — | RL | 401 without key — **correct, keep** | middleware `src/middleware.py:115-116`; not exempt |
| `/api/train/{start,pause,resume,stop,reset,status}` | **browser fetch** (`:175`) + server-side handler (`:5403`) | **KEY only** | **none** | **none** | RL | 401 for the browser; **and fully unauthenticated if the key were merely removed** (§7) | handlers `src/main.py:2864,2885,2899,2913,2927,2941` — plain `async def`, no `Depends`, no Origin/CSRF |
| `/api/csrf` | **browser XHR** (`:524`) | **KEY** | none | n/a (it *mints* the token) | RL | 401 → token unobtainable → control-WS auth frame skipped | handler `src/main.py:474-485`; mints via `csrf.get_csrf_store().mint()` `:483-484` |
| `/ws/control` | **browser** `cascorControlWS` | **KEY** (`:674`) | Origin (`:682-694`) | **CSRF first-frame** (`:707-734`) | per-IP cap (`:696-699`) | **double-gated**: closed 4001 for the keyless browser *before* Origin/CSRF even run | `src/main.py:664-734`; SEC-06 no-op `:678` |
| `/ws/training` | browser `cascorWS` | **KEY** (`:556`) | Origin (`:564-576`) | none | per-IP cap (`:578-581`) | closed 4001 for the browser (same defect, read-only push) | `src/main.py:540-587` |
| `/ws` (general) | compat clients | **KEY** (`:2811`) | Origin (`:2819-2831`) | none | per-IP cap | closed 4001 for the browser | `src/main.py:2797-2831` |

**Three observations that shape the fix:**

1. **The browser state-change surface is uniformly key-gated, and the browser cannot pass it.** `/api/train/*`, `/api/csrf`, `/ws/control`,
   `/ws/training`, `/ws` all require the key; the browser holds none. The audit isolated `/api/train/*`; the same root defect silently breaks the
   browser's live-push `/ws/training` and `/ws` too (they close 4001), which is why the dashboard runs on server-side polling rather than WS push.
2. **`/ws/control` already carries the exact browser-appropriate controls we need** — Origin allowlist + CSRF first-frame + per-IP cap
   (`src/main.py:682-734`). The key gate in front of them is redundant for the same-origin browser and is the *only* thing closing the socket.
3. **The Origin allowlist already admits the same-origin browser in production.** `settings.websocket.allowed_origins` defaults to
   `http://localhost:8050`, `http://127.0.0.1:8050` (+ https variants) (`src/settings.py:135-140`) and is **not** overridden for canopy in the
   deploy (the `JUNIPER_CASCOR_WS_CONTROL_ALLOWED_ORIGINS` entries at `docker-compose.yml:234,384` configure **cascor**, not canopy's inbound WS).
   A browser at `http://localhost:8050` sends `Origin: http://localhost:8050`, which is allowlisted. So the Origin half of the durable fix is
   already wired and production-validated for the same-origin case.

**Deploy context (verified):** canopy binds to **loopback** — `${BIND_HOST:-127.0.0.1}:${CANOPY_PORT:-8050}` (`docker-compose.yml:557`); the REST
rate limiter is **ON** — `JUNIPER_CANOPY_RATE_LIMIT_ENABLED: ${CANOPY_RATE_LIMIT_ENABLED:-true}` (`docker-compose.yml:572`), at 60 req/min/key-or-IP
(`src/settings.py:294`, `src/security.py:169-203`); CORS is **off** — `cors_origins` defaults to `[]` (`src/settings.py:290`) and the deploy sets
none, so `CORSMiddleware` is never added (`src/main.py:350-358`). The loopback binding is load-bearing for the security argument in §7.

---

## 4. The four candidate directions

Each option is assessed on: mechanism, exact touch-points, what it fixes, what it does **not** fix, security delta, deploy/rebuild implications,
and reversibility.

### (a) Immediate unblock — flip `enable_ws_control_buttons` off

**Mechanism.** Disable the Phase-D clientside path so Start re-routes onto the pre-Phase-D **server-side** `@app.callback`
(`src/frontend/dashboard_manager.py:3603-3639` → `_handle_training_buttons_handler:5350`), which POSTs `/api/train/{command}` with
`headers=internal_api_headers()` (`:5400,:5403`). `internal_api_headers()` attaches the configured `X-API-Key` (`src/frontend/internal_api.py:76-78`),
so the call is authenticated and returns 200.

**Touch-points.** Two ways to flip it: **(a-env)** set `JUNIPER_CANOPY_ENABLE_WS_CONTROL_BUTTONS=false` in the deploy (the flag binds to that env
name via `env_prefix="JUNIPER_CANOPY_"`, `src/settings.py:165`) — **no rebuild**; or **(a-code)** change the default `True → False` at
`src/settings.py:325` — requires a canopy image rebuild and reverts a deliberate D-49 decision globally.

**Fixes.** The Start/Stop/Pause/Resume/Reset buttons work again (server-side, keyed).

**Does NOT fix.** (i) The browser live-push WebSockets `/ws/training` and `/ws/control` stay closed 4001 (the dashboard remains on server-side
polling — consistent with the "WS:Reconnecting" badge being a known red herring tracking `/api/status` freshness). (ii) `/api/csrf` still 401s for
any other browser XHR. (iii) Loses the Phase-D WS-control UX (C4). It is a **mitigation, not a fix**.

**Security delta.** None — auth stays fully ON; this only changes which in-process path issues the keyed call.

**Reversibility.** (a-env) fully reversible by removing the env var and `docker compose up -d`. (a-code) reversible by a follow-up PR.

### (b) Correct fix — authenticate the browser surface via Origin + CSRF (+ session)  ← **recommended durable change**

**Mechanism.** Treat the same-origin browser as a first-class principal authenticated by **Origin + CSRF token + session cookie**, the controls
`/ws/control` already trusts, *instead of* the `X-API-Key` it cannot hold. Three coordinated changes: **(1)** make `/api/csrf` key-exempt so the
browser can fetch a token (resolves the chicken-and-egg, §6); **(2)** add an **Origin+CSRF dependency to `/api/train/*`** so removing the key
requirement does not leave them open (the crux, §7); **(3)** relax the WebSocket key gate so `/ws/control` (and, read-only, `/ws/training` / `/ws`)
accept the Origin+CSRF path they already enforce.

**Touch-points.** Exempt-tier split in `src/canopy_constants.py:353-367` + `src/middleware.py:110-150`; a new `require_browser_control_auth`
dependency in `src/security.py` applied to the `/api/train/*` handlers in `src/main.py:2864-2948`; an `allow_browser_auth` relaxation of
`_authenticate_websocket` (`src/main.py:488-501`) used by `/ws/control` (`:674`); JS to fetch `/api/csrf` and attach the token to the REST fallback
(`src/frontend/dashboard_manager.py:163-201`) — the WS auth-frame path already sends it (`src/frontend/assets/websocket_client.js:79-85`). Full
file-by-file design in §8.

**Fixes.** Start (REST fallback **and** WS push) under enabled auth; restores `/ws/control` and optionally `/ws/training` browser push; keeps the
Phase-D UX (C4).

**Does NOT fix.** Does not (and should not) authenticate *non-browser* callers to `/api/train/*` by key — by design they would use `/v1/*` or
supply the key (§7 residual risk + §12 OQ-2).

**Security delta.** Net-positive for the browser threat: `/api/train/*` gains Origin+CSRF where it had **neither** today. The key requirement is
dropped only on the same-origin browser surface; `/v1/*` and external surfaces stay keyed (C5). Residual risk (non-browser port-access attacker)
analyzed and bounded in §7.

**Deploy/rebuild.** Requires a canopy image rebuild to land in the running container (it is code). Owner-gated deploy.

**Reversibility.** Standard — revert the PR; the new behavior is additive and flag-guardable (§8 proposes a `browser_control_auth_enabled` setting
defaulting safe).

### (c) Exempt-the-surface variant

**Mechanism.** Framed as "add `/api/train/*` + `/api/csrf` to the exempt set" rather than "add a dependency." Structurally this is the *first half*
of (b).

**Why "exempt only" is unsafe.** The `/api/train/*` handlers are plain `async def` with **no** Origin/CSRF dependency (`src/main.py:2864-2948`).
Exempting them from the key gate without adding Origin+CSRF leaves five **state-changing** routes (start/stop/pause/resume/reset training) **fully
unauthenticated and CSRF-able** — strictly worse than today. The exempt-set add also silently removes the rate limiter, because `_is_exempt`
short-circuits *before both* the key and the limiter (`src/middleware.py:110-111`).

**Convergence.** Done correctly — exemption **plus** the Origin+CSRF dependency — (c) **is** (b). The distinction is purely framing; (b) is the safe
articulation. Treat "exempt only" as a documented anti-pattern, not an option.

### (d) RULED OUT — disable auth / treat the key as accidental

**Mechanism.** Unset `CANOPY_API_KEY` so `APIKeyAuth.enabled` is False (`src/security.py:48`), making everything open.

**Why closed.** The key is a **confirmed-intentional** secret (C1): SOPS-encrypted in the deploy, file-mounted via a Docker secret, 43 bytes of real
entropy. Disabling auth would remove a deliberately-provisioned control across the entire service (`/v1/*` included) and also re-enable the docs UI
as a side effect (`_docs_enabled = not get_secret("CANOPY_API_KEY")`, `src/main.py:337`). **Explicitly off the table.**

### Option comparison

| Option | Restores Start | Restores WS push | `/api/csrf` for browser | Security delta | Rebuild | Owner-gated | Verdict |
|---|---|---|---|---|---|---|---|
| (a) flip flag off | yes (server-side, keyed) | **no** | **no** | none (auth unchanged) | env: no / code: yes | deploy approval | **Mitigation now** |
| (b) Origin+CSRF browser-auth | yes (REST + WS) | yes | yes | **net-positive** (adds Origin+CSRF to `/api/train/*`) | yes | deploy approval | **Durable fix** |
| (c) exempt-only | yes | partial | yes | **negative if naive** (opens `/api/train/*`) | yes | — | Unsafe alone; = (b) when done right |
| (d) disable auth | yes | yes | yes | **removes a real control** | env | — | **Ruled out (C1)** |

---

## 5. Recommended approach — the triad

Recommend the owner's standing **triad** pattern (design-first; immediate-unblock + correct-fix-PR + deferred-design-doc), which fits this
situation exactly:

1. **Immediate unblock (PR-0 / deploy change):** option (a-env) — set `JUNIPER_CANOPY_ENABLE_WS_CONTROL_BUTTONS=false` in the canopy compose
   service to restore the dashboard buttons **now**, with no rebuild, fully reversible. This buys time without touching auth and without committing
   to an implementation shape. (Owner-gated: it is a deploy/env change.)
2. **Correct fix (PR-1 + tests):** option (b) — authenticate the same-origin browser surface with Origin + CSRF + session, dropping the key
   requirement only on `/api/train/*`, `/api/csrf`, and `/ws/control` (and, by the same argument, the read-only browser WebSockets), while `/v1/*`
   stays keyed. This re-enables the Phase-D UX and is the durable answer.
3. **Design-of-record (this note):** the analysis, the security proof, and the implementation surface, so the implementation PR is a faithful
   execution of a ratified design rather than an in-flight improvisation.

**This is a recommendation, not a mandate.** The owner picks the implementation scope: ship only (a) as a standing mitigation; ship (a)+(b); or
ship (b) directly if a brief dashboard outage during rebuild is acceptable. The decision points the owner should weigh are flagged inline (§8 flag
default, §11 test seams, §12 open questions).

---

## 6. The `/api/csrf` chicken-and-egg, resolved

**The bind.** The browser's only way to obtain a CSRF token is `GET /api/csrf` (`src/frontend/assets/websocket_client.js:523-524`). That route is
key-gated today, so it 401s; with no token, `window.__canopy_csrf` stays `null` and the control-WS auth frame is skipped
(`websocket_client.js:79-85`). So CSRF can't protect anything because the browser can't *get* a token — and we can't drop the key on `/api/train/*`
and lean on CSRF until the token is fetchable.

**The resolution.** Make `/api/csrf` **key-exempt** (reachable anonymously by the browser). This is safe because the handler does nothing but mint a
token into a bounded server-side store (`src/main.py:483-484`; `CsrfTokenStore.mint`, `src/csrf.py:35-51`, capped at `max_tokens=10000` with
oldest-eviction). It reads no secret, mutates no training state, and returns only an opaque token.

**Why an anonymously-mintable token is acceptable.** A CSRF token is **not** a bearer credential that authorizes by possession. Its job is to defeat
*ambient-authority* forgery: a malicious page can make the browser send the user's cookies automatically, but it **cannot read a token minted on the
canopy origin** (it is not CORS-readable cross-origin — `cors_origins=[]`, `src/main.py:350-358` — and the `SameSite=strict` session cookie,
`src/main.py:380`, is not attached to cross-site requests). So the token, *paired with the Origin check and the server-side store*, proves "this
request was composed by code running on the canopy origin," which is exactly the property we need. The token alone is worthless to an off-origin
attacker; the protection is **Origin + store-validated token together** (see §7).

**Hardening (recommended):** also apply the **Origin allowlist to `/api/csrf`** itself (reuse `ws_security.validate_origin` / the same allowlist,
`src/settings.py:135-140`). Then even *minting* is restricted to same-origin callers, closing `/api/csrf` as an off-origin token oracle while
keeping it key-exempt. A missing/disallowed Origin → reject (fail-closed, mirroring `src/ws_security.py:29-31`). Keep the exemption **key-only**, not
rate-limit-also: see §8 for the exempt-tier split that preserves the limiter on the anonymous endpoint.

---

## 7. Security analysis of the correct fix (the crux)

**Claim to prove.** Origin allowlist + server-side CSRF token + `SameSite=strict` session + per-IP rate/connection caps is **sufficient** to
authenticate a *same-origin browser* for the state-changing control surface (`/api/train/*`, `/ws/control`) and to **drop the `X-API-Key`
requirement there**, while `/v1/*` and external surfaces remain key-gated — *given* the network-boundary precondition stated below.

### 7.1 Threat actors

| Actor | Capability | Outcome under the fix |
|---|---|---|
| **Malicious website** (canopy open in another tab) | Sends requests with the victim's ambient cookies; **cannot** read cross-origin responses, forge the `Origin` header, or read a canopy-origin CSRF token. | **Blocked.** Cross-site POST to `/api/train/*` → `Origin: https://evil.com` allowlist-rejected, and no readable CSRF token → token-rejected. `/ws/control` is Origin-rejected (4003, `src/main.py:693`) then CSRF-rejected. **The realistic browser threat — fully defeated.** |
| **Passive network eavesdropper** | Reads wire traffic. | **No worse than today.** The `X-API-Key` is itself sent in cleartext over HTTP, so the key gives no confidentiality advantage on the wire. Confidentiality is a TLS concern, terminated by the reverse proxy in prod (`https_only=False  # HTTPS enforced by reverse proxy`, `src/main.py:381`); the deploy binds loopback (`docker-compose.yml:557`), so there is no on-path position by default. |
| **Active non-browser attacker with port access** (curl/script reaching `:8050`) | Can spoof the `Origin` header, mint an anonymous CSRF token, replay the session cookie. | **Partially mitigated, bounded, and gated by the network boundary** — the honest residual risk; see §7.3. |

### 7.2 Why Origin + CSRF is the right pair (not either alone)

- **Origin alone** is a strong CSRF defense for browsers (the browser stamps `Origin` on every cross-origin POST and on WS upgrades; an attacker
  page cannot override it), but it fails open if the allowlist is ever misconfigured too broadly, or if a privacy tool strips `Origin` (we
  fail-closed on missing Origin to cover this).
- **CSRF token alone** defeats ambient-authority forgery but does not, by itself, prove origin if the token can be obtained off-origin.
- **Together** they are belt-and-suspenders and exactly mirror what `/ws/control` already enforces (`src/main.py:682-734`). The `/api/train/*`
  routes get the same standard the WS path is already held to — closing the inconsistency that today leaves the REST twins with **no** Origin/CSRF
  at all.

### 7.3 Residual risk — the anonymous-token / Origin-spoof gap, stated honestly

Because the CSRF token is anonymously mintable (§6) and the `Origin` header is only trustworthy *when set by a browser*, a **non-browser** client
that can reach `:8050` can (1) `GET /api/csrf` to mint a valid token and (2) `POST /api/train/start` with a spoofed `Origin: http://localhost:8050`
and that token — and would pass. The `X-API-Key`, by contrast, is a shared secret such a client does **not** possess. So dropping the key on
`/api/train/*` *does* lower the bar against a non-browser port-access attacker.

**Why this is acceptable, and the precondition that makes it so:**

1. **Network boundary (load-bearing precondition).** The control surface is **loopback-bound** in the deploy (`${BIND_HOST:-127.0.0.1}`,
   `docker-compose.yml:557`). A non-browser attacker who can reach `:8050` is therefore *already a process on the canopy host*, who can also read
   the mounted secret file (`/run/secrets/canopy_api_key`) and is outside the threat model the key defends against. Where canopy is fronted by a
   reverse proxy, the proxy is the trust boundary (and may add network ACLs / mTLS). **The fix must not be shipped on a build that binds the control
   surface to a public interface without a fronting auth layer** — the single most important deployment assumption (§12 OQ-3).
2. **Bounded blast radius.** The key-drop is scoped to `/api/train/*` (training lifecycle control) + `/api/csrf` + `/ws/control`. It is **not**
   applied to `/v1/*` (the data/query API) (C5), so an attacker gains training start/stop, not the full keyed API surface.
3. **Abuse cap.** The REST rate limiter stays in force on the now-keyless routes (anonymous → keyed by client IP, `src/security.py:145-160`, 60/min,
   enabled in deploy `docker-compose.yml:572`), and `/ws/control` keeps the per-IP connection cap of 5 (`src/settings.py:141`, `src/main.py:696-699`).
   These cap brute-force/DoS, though they are not authentication.
4. **No worse than the alternative we cannot take.** The only way to give the browser the *key*-grade barrier is to put the key in the browser,
   which violates C3 and is a strictly larger exposure (every dashboard visitor would hold the secret).

**Conclusion.** For the **browser** threat model — the one that actually applies to a same-origin dashboard — Origin + CSRF + session is
**sufficient** and is a **net security improvement** over today's `/api/train/*` (which has Origin/CSRF = none). The residual non-browser gap is real
but is bounded by scope and **closed in practice by the loopback/proxy network boundary**, and is the deliberate, owner-visible trade for not handing
the browser a secret it cannot safely hold. Surfaces where a client *can* hold a key (`/v1/*`, external/programmatic) keep the key.

---

## 8. Detailed design of the correct fix (file-by-file, design-level)

Design intent and location, not full patches. A new setting **`browser_control_auth_enabled: bool`** (in `Settings`, `src/settings.py`, alongside
the Phase-B-pre-b block at `:330-334`) gates the whole behavior, so it is flag-reversible; **owner decision: default `True` (fix active) vs `False`
(opt-in)** — recommend `True` so the deploy is fixed on rebuild, with the env override available to disable.

### 8.1 Exempt-tier split — `src/canopy_constants.py` + `src/middleware.py`

Today `_is_exempt` (`src/middleware.py:136-150`) returns before **both** the key gate and the rate limiter (`:110-111`). Adding `/api/csrf` to
`EXEMPT_PATHS` (`src/canopy_constants.py:355-367`) would therefore also drop its rate limiting. Introduce a **second tier**: `KEY_EXEMPT_PATHS`
(auth-exempt **but still rate-limited**) distinct from the existing fully-exempt set. In `SecurityMiddleware.dispatch`, a key-exempt path skips
`self._api_key_auth(...)` (`:115-116`) but still runs `self._rate_limiter(...)` (`:118-119`). Put `/api/csrf` and the `/api/train` prefix in
`KEY_EXEMPT_PATHS`. This keeps the anonymous-mint endpoint rate-limited (§6) and lets the per-route dependency (§8.2) own the real authn for
`/api/train/*`.

### 8.2 Origin + CSRF dependency for `/api/train/*` — `src/security.py` + `src/main.py`

Add a FastAPI dependency `require_browser_control_auth(request: Request)` in `src/security.py` (peer of `APIKeyAuth`). It enforces, **when
`browser_control_auth_enabled` and `csrf_enabled`**:

- **Origin:** read `request.headers["origin"]`; reject (403, fail-closed on missing) unless it matches `settings.websocket.allowed_origins` (reuse
  the allowlist + the `validate_origin` comparison semantics, `src/ws_security.py:33-36`).
- **CSRF token:** read it from a request header (e.g. `X-CSRF-Token`) — *not* a body field, so GET `/api/train/status` and bodyless POSTs are
  uniform — and validate against `get_csrf_store().validate(token)` (`src/csrf.py:53-72`, which also slides the TTL).
- **Acceptance rule:** pass if **(valid `X-API-Key`)** OR **(Origin ok AND CSRF ok)**. The key-OR keeps server-side/internal callers and any keyed
  programmatic caller working unchanged (they present the key; the internal self-call path already does, `src/frontend/internal_api.py:76-78`).

Apply it to the six handlers at `src/main.py:2864,2885,2899,2913,2927,2941` via `Depends(require_browser_control_auth)` (or an
`APIRouter(dependencies=[...])` grouping them). Because these paths are now `KEY_EXEMPT` (§8.1), the middleware no longer 401s first, so the
dependency is reached.

> **Decision point:** `/api/train/status` is a **GET** (read-only, `src/main.py:2941`). The owner may choose to require only Origin (not CSRF) for
> the read, reserving CSRF for the state-changing POSTs. Recommend requiring CSRF uniformly for simplicity unless a keyless read is needed by a
> consumer (§12 OQ-2).

### 8.3 WebSocket key-gate relaxation — `src/main.py`

`_authenticate_websocket` (`src/main.py:488-501`) unconditionally closes 4001 when `api_key_auth.enabled` and the key is absent — which is what
kills the browser control socket *before* the Origin/CSRF gates run. Add a parameter `allow_browser_auth: bool = False`: when `True`, a **present**
key is still validated, but an **absent** key returns `True` (accept) and defers to the downstream gates. Call
`_authenticate_websocket(websocket, allow_browser_auth=True)` from `/ws/control` (`:674`). The Origin gate (`:682-694`) and CSRF first-frame
(`:707-734`) — already unconditional when configured — then become the real authn for the keyless browser. No new WS code is needed beyond the
relaxation; the controls already exist.

> **Decision point (read-only push):** `/ws/training` (`:556`) and `/ws` (`:2811`) are read-only metric streams with an Origin gate but no CSRF. The
> same `allow_browser_auth=True` relaxation would restore the browser's live-push metrics (today they silently close 4001). For a read-only stream,
> **Origin alone** is a defensible browser-auth bar (no state change to forge). Recommend including them in scope so the dashboard regains WS push;
> the owner may defer them to keep PR-1 minimal (§12 OQ-4).

### 8.4 Browser JS — `src/frontend/dashboard_manager.py` + `websocket_client.js`

- **REST fallback must send the token.** In `restFallback` (`src/frontend/dashboard_manager.py:163-201`), add the CSRF header to `fetchOpts`
  (`:170`), e.g. `fetchOpts.headers = { ...(fetchOpts.headers||{}), 'X-CSRF-Token': window.__canopy_csrf }`. The token is already fetched and cached
  at page load (`websocket_client.js:513,523-535`); just attach it. `credentials: 'same-origin'` is already set (`:170`) so the session cookie rides
  along.
- **WS path already sends it.** The control-WS auth first-frame already posts `{type:"auth", csrf_token: window.__canopy_csrf}` on open
  (`websocket_client.js:79-85`); once `/api/csrf` returns a token (§6) and the key gate is relaxed (§8.3), this path completes. No change required
  there beyond confirming `_csrfEnabled` is set (it is, via `{csrf:true}`, `websocket_client.js:517`).
- **No new token-fetch code** — the existing bootstrap XHR to `/api/csrf` (`websocket_client.js:522-542`) starts working the moment the endpoint is
  key-exempt.

### 8.5 What stays untouched

`/v1/*` and every non-browser route keep the `SecurityMiddleware` key gate unchanged (C5). `APIKeyAuth` (`src/security.py:34-99`) is not modified.
The secret, its file indirection (`src/secrets_util.py:38-64`), and the deploy secret wiring are untouched. SEC-06 (`ws_auth_enabled`,
`src/main.py:507-537`) remains an independent, default-off path.

---

## 9. Immediate-unblock design (option a)

**Recipe (a-env, recommended for the unblock).** In `/home/pcalnon/Development/python/Juniper/juniper-deploy/docker-compose.yml`, in the
**`juniper-canopy`** service `environment:` block (the same block that sets `CANOPY_API_KEY_FILE` at `:576`, service starts `:545`), add:

```yaml
      JUNIPER_CANOPY_ENABLE_WS_CONTROL_BUTTONS: "false"
```

Then recreate just that service:

```bash
docker compose up -d juniper-canopy
```

The flag binds because `Settings` uses `env_prefix="JUNIPER_CANOPY_"` (`src/settings.py:165`), so `enable_ws_control_buttons` (`:325`) reads
`JUNIPER_CANOPY_ENABLE_WS_CONTROL_BUTTONS`. With it `false`, `_setup_button_action_callbacks` registers the **server-side** branch
(`src/frontend/dashboard_manager.py:3603-3639`), whose POST carries the key (`:5400,:5403`) → 200.

**Pre-flight verification (the image must contain the server-side handler).** The env-flip only helps if the running image has *both* callback
branches. Confirm before relying on it:

```bash
# both branches present in the deployed image?
docker exec juniper-canopy grep -n "enable_ws_control_buttons" src/frontend/dashboard_manager.py   # expect the if/else gate (~:3578) + handler
# the keyed server-side POST helper is present?
docker exec juniper-canopy grep -n "internal_api_headers" src/frontend/internal_api.py             # expect the X-API-Key attach
```

Logically, the image *must* contain the `else` branch: the bug we observe is the clientside branch firing, which only exists in builds that also
added the server-side `else` (they shipped together in the Phase-D change). Still, verify rather than assume.

**Verification after flip.** Reload the dashboard, click Start → expect status `Training`/`Running` and no red banner. The browser live-push
WebSockets remain closed (expected; §4a) — the dashboard runs on server-side polling.

**Reversibility.** Remove the env line and `docker compose up -d juniper-canopy`. Nothing persistent changes.

**Code-default alternative (a-code).** Flipping `src/settings.py:325` to `False` achieves the same but needs a canopy rebuild + redeploy and reverts
the deliberate D-49 default for *all* deployments — not recommended except as a temporary measure if env overrides are unavailable in a given
environment.

---

## 10. Implementation plan / PR breakdown

Each work-unit is independently shippable and verifiable; never merge to `main` directly (worktree + PR per ecosystem convention). Deploy/env
changes are **owner-gated** (Paul approves deployment gates).

| PR | Title | Lands in container via | Content | Gated tests |
|---|---|---|---|---|
| **PR-0** | Unblock: disable Phase-D clientside buttons in deploy | **deploy env** (no rebuild) | Add `JUNIPER_CANOPY_ENABLE_WS_CONTROL_BUTTONS=false` to the canopy service (`docker-compose.yml` ~`:576`) | manual smoke (click Start → 200); compose config validate |
| **PR-1a** | Exempt-tier split (`KEY_EXEMPT_PATHS`) + `/api/csrf` key-exempt (Origin-hardened) | canopy rebuild | §8.1 + §6 hardening | `test_middleware.py` (key-exempt ≠ rate-exempt); `/api/csrf` anonymous-200 + off-origin-reject |
| **PR-1b** | `require_browser_control_auth` dependency on `/api/train/*` | canopy rebuild | §8.2 (key-OR-(Origin+CSRF)) | new dependency unit tests (Origin matrix; CSRF valid/invalid/missing; key-still-works) |
| **PR-1c** | WS key-gate relaxation for `/ws/control` (+ optional `/ws/training`,`/ws`) | canopy rebuild | §8.3 | WS auth tests: keyless+origin+csrf accepted; bad origin 4003; bad csrf 1008; keyed still works |
| **PR-1d** | Browser JS: attach `X-CSRF-Token` on REST fallback | canopy rebuild (assets) | §8.4 | JS asset present; (UI behavior covered by the regression harness, §11) |
| **PR-2** | Deploy: rebuild + roll out PR-1; remove the PR-0 env mitigation | **deploy** | rebuild `juniper-canopy:latest`, `docker compose up -d` | full curl matrix (§11) against the running container |

PR-1a..1d may be a single PR if the owner prefers one reviewable unit; they are split here to show the natural seams. PR-1c's read-only-WS
extension is the one optional scope toggle (§8.3 decision point).

---

## 11. Test & verification plan

**Unit (canopy `tests/`, run under the canopy CI path scope — beware the "green tests / dead app" class):**

- **Exempt-tier:** `/api/csrf` is reachable without a key **and** still rate-limited; `/api/train/*` is no longer 401'd by the middleware but is now
  governed by the dependency.
- **`require_browser_control_auth` matrix:** (Origin ok, CSRF ok) → pass; (Origin bad) → 403; (CSRF missing/invalid) → 403; (valid key, no
  Origin/CSRF) → pass (server-side/programmatic still works); (CSRF disabled) → behavior per flag.
- **WS relaxation:** keyless + allowed-Origin + valid first-frame CSRF → accepted on `/ws/control`; disallowed Origin → 4003; bad/absent CSRF
  first-frame → 1008; **valid key still accepted** (no regression for keyed callers).
- **Negative seam guard:** assert the test does **not** stub the auth dependency in a way that masks a broken control path. The canopy "green tests
  / dead app" risk class (client-wheel floor drift; the `FakeCascorClient` CI-skip seam) means a unit test can pass while the live control path is
  dead — so each auth test must exercise the **real** dependency, and PR-2 must include a **live** curl/browser check (below), not only unit green.

**Curl matrix (against the running container; mirrors the audit "Verification commands"):**

```bash
# token now fetchable (was 401):
curl -sS -i http://localhost:8050/api/csrf                  # expect 200 {"csrf_token": "...", "enabled": true}
TOKEN=$(curl -sS http://localhost:8050/api/csrf | python -c 'import sys,json;print(json.load(sys.stdin)["csrf_token"])')

# same-origin browser-shaped call now authorized (was 401):
curl -sS -i -X POST http://localhost:8050/api/train/start \
  -H "Origin: http://localhost:8050" -H "X-CSRF-Token: $TOKEN"   # expect 200/started

# CSRF/Origin missing → rejected (state surface stays protected):
curl -sS -i -X POST http://localhost:8050/api/train/start         # expect 403 (no Origin/CSRF, no key)
curl -sS -i -X POST http://localhost:8050/api/train/start -H "Origin: http://evil.example" -H "X-CSRF-Token: $TOKEN"  # expect 403 (bad origin)

# programmatic surface UNCHANGED — still keyed:
curl -sS -i http://localhost:8050/v1/                              # expect 401 (no key)
curl -sS -i -H "X-API-Key: <key>" http://localhost:8050/v1/        # expect 200

# exempt health still open:
curl -sS -i http://localhost:8050/v1/health                       # expect 200
```

**Browser re-click:** load `http://localhost:8050/dashboard/`, click Start → expect `Training`, no red banner; DevTools shows the control WS OPEN
(auth frame accepted) and/or the REST fallback returning 200 with `X-CSRF-Token`.

**Regression harness:** route PR-1d/UI changes through the canopy L1/L2 control-graph + behavioral gate; regenerate the panel snapshot if
`get_layout()` changes (per the canopy local-verify guidance — match the CI path scope, `-m "unit or integration"` skips the snapshot suite).

---

## 12. Open questions

1. **Does the deployed image predate the Phase-D plumbing?** PR-0 (env-flip) and the §8.3 WS relaxation assume the running `juniper-canopy:latest`
   contains both callback branches and the `/ws/control` Origin+CSRF gates. Verified by reading the source at `d1a13a01`; **not** verified against
   the bytes in the live image. The §9 `docker exec ... grep` checks settle it before relying on PR-0. (Unverified against the container.)
2. **Does any non-browser consumer call `/api/train/*` and rely on the key?** The key-OR acceptance rule (§8.2) keeps keyed callers working, so this
   is non-breaking, but if a programmatic consumer exists it should be steered to present the key (or to `/v1/*`). Grep of the ecosystem for
   `/api/train` consumers is recommended. (Unverified.)
3. **Reverse-proxy Origin handling in deploy.** The security argument's network-boundary precondition (§7.3) assumes loopback binding (verified,
   `docker-compose.yml:557`) or a trusted proxy. If canopy is ever fronted by a proxy that **rewrites/sets `Origin`** or is exposed on a public
   interface, the Origin gate's trust assumption must be re-validated and the allowlist updated. (Deploy-topology dependent.)
4. **Scope of the WS relaxation.** Whether to include the read-only `/ws/training` and `/ws` in PR-1c (restoring browser metric push, Origin-only)
   or to keep PR-1 minimal to `/ws/control`. Owner decision (§8.3). (Design choice.)
5. **`/api/train/status` GET — CSRF or Origin-only?** A read does not strictly need CSRF; uniform CSRF is simpler. Owner decision (§8.2). (Design
   choice.)
6. **`csrf_enabled = False` interaction.** If CSRF is ever disabled (`src/settings.py:331`), `/api/csrf` returns an empty token
   (`src/main.py:481-482`) and the browser surface would fall back to Origin-only. The dependency must define behavior for that mode (recommend:
   Origin-only when CSRF disabled, documented). (To specify in PR-1b.)

---

## 13. References

**This repo (juniper-canopy @ `d1a13a01`):**

- `src/security.py` — `APIKeyAuth` (`:34-99`; `enabled` `:50-53`; 401 raise `:88-91`), `RateLimiter` (`:102-249`; key derivation `:145-160`), `get_api_key_auth` (`:255-262`, reads `get_secret("CANOPY_API_KEY")` `:259`), internal token (`:30-31`).
- `src/middleware.py` — `SecurityMiddleware.dispatch` (`:94-134`; key gate `:115-116`; 401→JSON `:120-125`), `_is_exempt` (`:136-150`), exempt aliases (`:19-20`).
- `src/canopy_constants.py` — `EXEMPT_PATH_PREFIXES` (`:353`), `EXEMPT_PATHS` (`:355-367`).
- `src/settings.py` — `WebSocketSettings.allowed_origins` (`:135-140`), `max_connections_per_ip` (`:141`), `env_prefix` (`:165`), `cors_origins` (`:290`), `rate_limit_*` (`:293-294`), `enable_ws_control_buttons` (`:325`), CSRF/session block (`:330-334`), `ws_auth_enabled` (`:341`).
- `src/main.py` — `_docs_enabled` (`:337`), `SecurityMiddleware` add (`:367-369`), `SessionMiddleware` (`:375-383`), `/api/csrf` (`:474-485`), `_authenticate_websocket` (`:488-501`), `_authenticate_websocket_token` (SEC-06, `:507-537`), `/ws/training` (`:540-587`), `/ws/control` (`:664-734`), `/ws` (`:2797-2831`), `/api/train/*` (`:2864-2948`).
- `src/csrf.py` — `CsrfTokenStore.mint` (`:35-51`), `validate` (`:53-72`), `get_csrf_store` (`:101-106`).
- `src/ws_security.py` — `validate_origin` (`:16-39`; missing-Origin reject `:29-31`).
- `src/secrets_util.py` — `get_secret` (`:38-64`; `_FILE`-first `:55-62`).
- `src/frontend/internal_api.py` — `internal_api_headers` (`:63-79`; `X-API-Key` attach `:76-78`), `_canopy_api_key` cache (`:52-60`).
- `src/frontend/dashboard_manager.py` — clientside JS `PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS` (`:109-251`; `restFallback`/`fetch` `:163-201`,`:175`), `_setup_button_action_callbacks` (`:3570-3639`), `_handle_training_buttons_handler` (`:5350-5416`; keyed POST `:5400,:5403`), `_surface_training_control_outcome_handler` (`:5464-5486`), `_api_url` (`:1924`).
- `src/frontend/assets/websocket_client.js` — CSRF auth first-frame (`:79-85`), send-guard (`:405-408`), token bootstrap + control-WS URL (`:513-542`,`:516`).

**Companion / cross-repo:**

- [`notes/JUNIPER_CANOPY_CASCOR-TRAINING-401-APIKEY_AUDIT_2026-06-29.md`](JUNIPER_CANOPY_CASCOR-TRAINING-401-APIKEY_AUDIT_2026-06-29.md) — the root-cause audit (H1/H1b, the toggle table, the call path).
- `juniper-ml/notes/observability/CANOPY_DASHBOARD_SELF_CALL_REFACTOR_2026-05-10.md` — Option B (server-side `X-API-Key` injection, shipped canopy#265) vs deferred Option C; §7 explicitly notes browser-side data fetching as out of scope, which is why browser-originated calls were never covered.
- [`notes/CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md`](CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md) — the danger-alert surfacing that renders this 401 (both transports feed `training-control-action`).
- juniper-deploy `/home/pcalnon/Development/python/Juniper/juniper-deploy/docker-compose.yml` — canopy service (`:545`), `CANOPY_API_KEY_FILE` (`:576`), loopback bind (`:557`), rate limit on (`:572`), `secrets: - canopy_api_key` (`:616-617`), secret def (`:932-933`); cascor WS origins (`:234,:384`, **not** canopy inbound).
- juniper-deploy `/home/pcalnon/Development/python/Juniper/juniper-deploy/.env.secrets.enc:10` (encrypted `CANOPY_API_KEY`), `.env.secrets.example:13` (empty template), `./secrets/canopy_api_key.txt` (43 bytes).
