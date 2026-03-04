# Pull Request: Security Hardening — Middleware, WebSocket Auth, Dash CSP, and Scanning

**Date:** 2026-03-03
**Version(s):** 0.3.0 → 0.4.0
**Author:** Paul Calnon
**Status:** READY_FOR_MERGE

---

## Summary

Comprehensive security hardening for juniper-canopy as part of the cross-ecosystem security audit. Adds Dash-compatible security headers (CSP with `'unsafe-inline'`), request body limits, error sanitization, conditional CORS, rate limiting by default, WebSocket authentication with message size limits and idle timeout, /metrics auth, conditional docs, build attestations, and scheduled security scanning.

---

## Context / Motivation

A full security audit of the Juniper ecosystem identified 24 findings across 7 repositories. This PR addresses the juniper-canopy portion, including WebSocket security for the real-time training dashboard.

---

## Changes

### Security

- Added `SecurityHeadersMiddleware` with Dash-compatible CSP (allows `'unsafe-inline'` required by Dash/Plotly)
- Added `RequestBodyLimitMiddleware` (default 10MB)
- Sanitized error responses — generic messages; internal details at DEBUG level
- Changed CORS to conditional (restricted when origins configured)
- Changed rate limiting default to enabled
- Added WebSocket authentication at connection accept
- Added WebSocket message size limits (64KB control, 1MB data)
- Added WebSocket idle connection timeout (5 minutes)
- Added `/metrics` authentication
- Added conditional API docs
- Enabled build attestations in publish workflow

### Added

- `.github/workflows/security-scan.yml` — Weekly Bandit and pip-audit scanning

### Changed

- `conftest.py` — Disabled rate limiting during tests
- `test_cascor_ws_control.py` — Updated assertion for sanitized error messages

---

## Impact & SemVer

- **SemVer impact:** MINOR (0.3.0 → 0.4.0)
- **User-visible behavior change:** YES — Rate limiting enabled; CORS conditional; API docs may be hidden
- **Breaking changes:** NO — All configurable via environment variables
- **Performance impact:** NONE
- **Security/privacy impact:** HIGH — Addresses WebSocket auth bypass and 8+ findings
- **Guarded by feature flag:** YES — All features configurable via env vars

---

## Testing & Results

### Test Summary

| Test Type   | Passed | Failed | Skipped | Notes                                     |
| ----------- | ------ | ------ | ------- | ----------------------------------------- |
| Unit        | ~2,500 | 0      | 0       | All unit tests passing                    |
| Integration | ~800   | 0      | 19      | Skipped require CasCor/server/display     |
| Regression  | 30+    | 0      | 0       | All regression tests passing              |

**Total**: 3,373 passed, 0 failed, 19 skipped

### Environments Tested

- JuniperPython conda environment: All tests pass
- Demo mode: All features functional
- Python 3.14: Compatible

---

## Verification Checklist

- [x] Security headers present (including Dash-compatible CSP)
- [x] Error responses do not leak internal details
- [x] Rate limiting active by default (disabled in tests via conftest.py)
- [x] WebSocket connections validated
- [x] `/metrics` requires authentication
- [x] Build attestations enabled
- [x] All 3,373 tests pass

---

## Files Changed

### New Components

- `.github/workflows/security-scan.yml` — Scheduled security scanning

### Modified Components

**Backend:**

- `src/main.py` — Registered middleware, WebSocket auth/size/timeout, sanitized errors, conditional docs, /metrics auth
- `src/middleware.py` — Added SecurityHeadersMiddleware, RequestBodyLimitMiddleware
- `src/security.py` — Rate limiting default changed
- `src/settings.py` — Added security settings

**CI/CD:**

- `.github/workflows/publish.yml` — Enabled build attestations

**Tests:**

- `src/tests/conftest.py` — Disabled rate limiting in test environment
- `src/tests/integration/test_cascor_ws_control.py` — Updated error assertion for sanitized responses

---

## Risks & Rollback Plan

- **Key risks:** Rate limiting may cause 429 responses in high-traffic test environments; CORS restrictions may affect cross-origin dashboard access
- **Rollback plan:** Set `CANOPY_RATE_LIMIT_ENABLED=false`, `CORS_ORIGINS=*` to restore previous behavior

---

## Related Issues / Tickets

- Related PRs: Security hardening PRs across all 7 Juniper repositories
- Phase Documentation: `juniper-ml/notes/SECURITY_AUDIT_PLAN.md`

---

## Notes for Release

**v0.4.0** — Security hardening release. Adds Dash-compatible security headers, WebSocket authentication, rate limiting, and scheduled scanning. Part of cross-ecosystem audit addressing 24 findings.
