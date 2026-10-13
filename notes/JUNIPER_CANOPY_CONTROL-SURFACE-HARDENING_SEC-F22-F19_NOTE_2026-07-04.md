# Juniper-Canopy — Control-Surface Hardening (SEC-F22 bind-guard + SEC-F19 WS caps) — Implementation Note

**Project**: Juniper
**Sub-Project**: JuniperCanopy
**Application**: juniper_canopy
**Author**: Paul Calnon (implementation by Claude Code, Opus 4.8)
**License**: MIT License
**Date**: 2026-07-04
**Status**: Implemented — Phases 1–2 of the design of record. **Updated 2026-07-06:** the SEC-F22 bind-guard now uses the owner-ratified **two-flag** bind-posture attestation (`JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED` / `JUNIPER_CANOPY_AUTH_PROXY_ATTESTED`), replacing the original single `JUNIPER_CANOPY_FRONTING_AUTH_ATTESTED` flag (design OQ-1). Owner-gated for any deploy roll-out; do not auto-merge.
**Scope**: Records the two now-enforced control-surface invariants shipped in this PR and, explicitly, what remains deferred.

> Design of record (read first): juniper-ml
> [`notes/JUNIPER_CANOPY_CONTROL_SURFACE_AUTH_AND_NAT_DESIGN_2026-07-03.md`](https://github.com/pcalnon/juniper-ml/blob/main/notes/JUNIPER_2026-07-03_JUNIPER-CANOPY_CONTROL-SURFACE-AUTH-AND-NAT-DESIGN.md)
> — §4 (SEC-F22 Option A), §5 (SEC-F19 Option B), §7 Phases 1–2, §8 decisions D2 + D4, §9 testing.
> Companion: [`JUNIPER_CANOPY_TRAINING-CONTROL-AUTH_DESIGN_2026-06-30.md`](JUNIPER_CANOPY_TRAINING-CONTROL-AUTH_DESIGN_2026-06-30.md)
> §7.3 stated the load-bearing loopback precondition this PR now enforces.

---

## 1. What changed

This PR is a defensive hardening of the platform owner's own containerized stack. It implements the two app-local,
proxy-free remediation steps from the design of record and changes no deploy / env / secret file.

### 1.1 SEC-F22 (D2) — the loopback bind is now an enforced invariant

canopy's browser training-control gate (`/api/train/*`, `/ws/control`) authenticates the same-origin browser by
`Origin` + CSRF. Both are forgeable by an in-network **non-browser** client — the `Origin` header is a spoofable
string and the CSRF token is anonymously mintable (audit HO-6) — so the **only** effective control is the loopback
bind: an in-network foothold cannot reach a `127.0.0.0/8` port. Until now that loopback bind was an implicit default,
not an enforced invariant: flipping `BIND_HOST=0.0.0.0` silently converted SEC-F22 from same-host-only to
in-network- (or internet-) reachable, with no guard rail.

A **startup bind-guard** now converts that precondition into a fail-closed invariant. At canopy startup, before it
serves any request, canopy **refuses to start** when `settings.server.host`
(`JUNIPER_CANOPY_SERVER__HOST`) is a **non-loopback** interface — anything not in `127.0.0.0/8`, not `::1`, not
`localhost` — **unless** the operator attests the deployment perimeter via one of **two** bind-posture flags (both
default `False`):

- `JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED` (`settings.loopback_publish_attested`) — the service is reachable **only**
  via a loopback-only host publish (the containerized default: `127.0.0.1:8050:8050` in front of the in-container
  `0.0.0.0` bind). This is the one attestation a deploy-layer preflight can actually **verify**.
- `JUNIPER_CANOPY_AUTH_PROXY_ATTESTED` (`settings.auth_proxy_attested`) — a fronting authenticating reverse proxy
  terminates access in front of the control surface (the Phase-4 milestone); attestation only.

A loopback host always starts. A non-loopback bind is permitted when **either** flag is `True` (the guard logs
**which** one permitted it, at WARNING); with **neither** set the refusal is fail-loud (a CRITICAL log naming both
flags) and fail-closed (raises `NonLoopbackBindError`, so uvicorn exits). The hard fail is **uniform** — there is no
warning-only mode that lets an unattested non-loopback bind proceed. Each flag is an operator **attestation**, not a
verification. (This two-flag scheme is the owner-ratified refinement of the original single
`JUNIPER_CANOPY_FRONTING_AUTH_ATTESTED` flag — design OQ-1.)

Implemented **inline in canopy** (no new dependency):

- `src/security.py` — `is_loopback_host`, `enforce_loopback_bind_guard`, `NonLoopbackBindError`.
- `src/main.py` — the `lifespan` startup calls the guard (mirrors the existing E-8 `enforce_dependency_floors`
  fail-loud idiom), before backend init.
- `src/settings.py` — the `loopback_publish_attested` and `auth_proxy_attested` fields.

> **Deploy roll-out caveat (owner-gated).** The containerized deploy sets
> `JUNIPER_CANOPY_SERVER__HOST=0.0.0.0` *inside* the container
> (`juniper-deploy/docker-compose.yml:570`) — the standard Docker pattern where
> the real perimeter is the host-side **loopback publish**
> (`127.0.0.1:8050:8050`, `:557`), not the in-container bind. Because the guard
> keys on `settings.server.host`, rolling this code out to that deploy will make
> canopy **refuse to start** until the owner sets
> `JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED=true` — the attestation that matches
> exactly the deploy's posture (reachable only via the host-side loopback
> publish), and the one a deploy-layer preflight can verify.
> `JUNIPER_CANOPY_AUTH_PROXY_ATTESTED=true` is the alternative, reserved for when
> the Phase-4 fronting authenticating proxy lands. That is the intended effect:
> the guard converts the silent `0.0.0.0` bind into a documented, deliberate
> choice. This is a deploy/env change and is therefore owner-gated (not part of
> this merge).

### 1.2 SEC-F19 (D4) — global + per-session WS caps; the per-IP cap is re-scoped honestly

Docker NAT collapses every WS client to the bridge-gateway IP (audit HO-3), so the existing per-IP cap
(`max_connections_per_ip=5`) is shared across **all** users behind the gateway — one client's five sockets exhaust
the cap for everyone (the live self-DoS). Two caps are added alongside it, in
`src/communication/websocket_manager.py`:

- **Global cap** — the stack-absolute `max_connections` (=50) enforced in `WebSocketManager.connect()`, the single
  admission choke point shared by every WS endpoint (`/ws/training`, `/ws/control`, `/ws`). It bounds total server
  resource and backstops the cookieless case; the N+1th connection stack-wide is rejected with close code `1013`.
- **Per-session cap** — `max_connections_per_session` (=5), keyed on the anonymous `canopy_session` cookie read from
  the WS handshake. It restores per-client fairness where the per-IP cap is inert: one browser session can no longer
  monopolize the shared cap and starve another session behind the same gateway. A cookieless first connection is
  allowed and left to the global cap as the backstop (§9 R2). Over-cap → close `1013`.

The three WS endpoints now call `check_connection_limits(...)` (per-IP then per-session, with the per-IP slot rolled
back on a per-session rejection so a rejected attempt cannot leak the per-IP counter). Each endpoint keeps its
existing close-reason string — `/ws/control` stays opaque (`Policy violation`, M-SEC-06).

## 2. Honest security labeling (state this, don't drift from it)

- **Loopback bind (bind-guard)** — the real perimeter for the single-user / trusted-LAN research posture, now an
  **enforced invariant** rather than an implicit default.
- **Per-IP cap** — DoS-dampening only, and **inert behind NAT** (every client presents as the bridge gateway). It was
  **never** authentication and must not be documented as such. Kept because it still dampens a single-IP flood
  off-NAT. Annotated as such in `WebSocketSettings.max_connections_per_ip` and `check_per_ip_limit`.
- **Global connection cap** — availability / DoS-dampening (best-effort), not authentication.
- **Per-session cap** — per-client fairness / DoS-dampening (best-effort), not authentication (a determined attacker
  rotates cookies).

## 3. Explicitly deferred (Phase 4 — owner-gated, NOT in this PR)

The structural pieces of both findings converge on one component and are **not** built here:

- **D6 — X-Forwarded-For** trusted-proxy client-IP resolution (the only mechanism that restores genuine per-client
  identity for the caps and the metrics allowlist). Deferred; the invariant "trust XFF only from the configured proxy
  IP" is written down now.
- **D7 — a real dashboard login** / fronting authenticating reverse proxy (the only robust close of SEC-F22 for the
  remote / multi-user case). A page-injected token (design B1) was rejected in the design record as insufficient (it
  relocates the anonymous mint from `/api/csrf` to the anonymously-served `/dashboard/`).

These are justified only when genuine remote or multi-user access becomes a requirement.

## 4. Verification

- New unit tests: `src/tests/unit/test_bind_guard.py` (SEC-F22/D2 — non-loopback + neither attest refuses to start;
  non-loopback + either attest binds; loopback binds regardless; fail-loud logging) and
  `src/tests/unit/test_ws_connection_caps.py` (SEC-F19/D4 — global cap rejects the N+1th stack-wide; two sessions from
  one peer IP each keep their per-session allocation; a legit single user is unaffected; cookieless allowed;
  per-IP-slot rollback on per-session rejection).
- Run the CI-equivalent unit + regression scope (per the canopy "green tests / dead app" caveat — CI selects by
  path, not just marker):

```bash
cd src && pytest -m "not requires_cascor and not requires_server and not slow" tests/unit/ tests/regression/
```

- Per the design §9, the deploy roll-out still owes a **live** curl / WS probe matrix on an isolated stack
  (unit-green alone is not sufficient for this class). That is an owner-gated deploy step, not part of this merge.
