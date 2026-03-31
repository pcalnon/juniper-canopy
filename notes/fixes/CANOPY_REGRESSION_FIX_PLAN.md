# Canopy Dashboard Regression Fix Plan

**Date**: 2026-03-16
**Regression Introduced By**: Commit `c692a07` — "feat(security): comprehensive security hardening"
**Secondary Factor**: Commit `a894b1c` — Dependabot Dash 3.3.0 → 4.0.0 upgrade (not a direct cause but amplifies CSS issues)

---

## Symptoms

| # | Symptom | Severity |
|---|---------|----------|
| S1 | Left sidebar takes full screen width (no Bootstrap grid) | Critical |
| S2 | Tabs displayed as bulleted list instead of tab bar | Critical |
| S3 | All tab content visible simultaneously on initial page | Critical |
| S4 | Training status displays "Error" | High |
| S5 | Frequent 429 Too Many Requests on API endpoints | High |
| S6 | `Fetched 0 metrics` logged despite demo mode running | Medium |

---

## Root Cause Analysis

### RC-1: Content-Security-Policy Blocks Bootstrap CDN Stylesheet

**Cause**: The `SecurityHeadersMiddleware` (added in `c692a07`) injects a CSP header on **all** responses:

```
default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'
```

The dashboard loads Bootstrap CSS via `dbc.themes.BOOTSTRAP`, which resolves to:

```
https://cdn.jsdelivr.net/npm/bootstrap@5.3.6/dist/css/bootstrap.min.css
```

The CSP's `style-src 'self' 'unsafe-inline'` directive does **not** include `cdn.jsdelivr.net`, so the browser blocks the stylesheet. Without Bootstrap CSS:

- `dbc.Row` / `dbc.Col` render as unstyled `<div>` elements (full width, no grid)
- `dbc.Tabs` / `dbc.Tab` render as unstyled `<ul>` / `<li>` elements (bulleted list)
- Tab content visibility is not managed (all panels visible simultaneously)

**Symptoms explained**: S1, S2, S3

**File**: `src/middleware.py` line 30

### RC-2: Rate Limiting Enabled by Default at 60 req/min

**Cause**: In the same commit (`c692a07`), the rate limiter default was changed from disabled to enabled:

```python
# Before (disabled by default):
enabled = os.environ.get("CANOPY_RATE_LIMIT_ENABLED", "").lower() in ("1", "true", "yes")

# After (enabled by default):
enabled = os.environ.get("CANOPY_RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes")
```

The rate limit is 60 requests per minute (1/second). The dashboard's Dash callbacks make internal HTTP requests to API endpoints via loopback (`127.0.0.1`):

| Callback | Interval | Endpoint | Exempt? |
|----------|----------|----------|---------|
| Status bar | 1s (fast) | `/api/health` | Yes |
| Status bar | 1s (fast) | `/api/status` | **No** |
| Metrics store | 1s (fast) | `/api/metrics/history` | **No** |
| Network info | 5s (slow) | `/api/network/stats` | **No** |
| Network details | 5s (slow) | `/api/network/stats` | **No** |
| Backend params | 5s (slow) | `/api/state` | **No** |
| Topology store | 5s (slow) | `/api/topology` | **No** (when tab active) |
| Dataset store | 5s (slow) | `/api/dataset` | **No** (when tab active) |
| Boundary store | 5s (slow) | `/api/decision_boundary` | **No** (when tab active) |

Conservative estimate: ~3 non-exempt requests/second from fast-interval callbacks alone = 180 req/min, **3x over the 60 req/min limit**.

All internal loopback requests share the same rate-limit bucket (keyed by IP `127.0.0.1`), so the limit is exhausted within seconds of startup.

**Symptoms explained**: S5 (429 errors), S4 (status shows "Error" because `/api/status` returns 429, and the status bar handler treats non-200 as error — `dashboard_manager.py` lines 971-984), S6 (metrics fetch returns 429, handler logs "Fetched 0 metrics")

**Files**: `src/security.py` line 230, `src/settings.py` line 138

### RC-2a: Settings Inconsistency

The module docstring in `security.py` line 6 states the default is `false`, but the code defaults to `"true"`. Additionally, `settings.py` line 138 (`rate_limit_enabled: bool = True`) is not used by `get_rate_limiter()` — the function reads env vars directly, creating a parallel configuration path.

---

## Implementation Plan

### Phase 1: Fix CSP to Allow Bootstrap CDN

**File**: `src/middleware.py`

**Change**: Add `https://cdn.jsdelivr.net` to the `style-src` directive in the default CSP. This is the minimum change needed — the Bootstrap CDN is a trusted, widely-used CDN for serving Bootstrap assets.

```python
# Before:
_DEFAULT_CSP = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'"

# After:
_DEFAULT_CSP = "default-src 'self'; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
```

**Rationale**: The `SecurityHeadersMiddleware` applies CSP to all responses including `/dashboard/*`. Since `dbc.themes.BOOTSTRAP` loads from jsdelivr CDN, the CSP must allow it. Alternative approaches (serving CSS locally, exempting dashboard from CSP) are more invasive and less maintainable.

### Phase 2: Fix Rate Limiting Default

**File**: `src/security.py`

**Change**: Revert the rate limiter default to disabled, matching the module docstring.

```python
# Line 230 — revert to original behavior:
enabled = os.environ.get("CANOPY_RATE_LIMIT_ENABLED", "").lower() in ("1", "true", "yes")
```

**File**: `src/settings.py`

**Change**: Align the Pydantic settings default with the actual behavior.

```python
# Line 138 — change default to False:
rate_limit_enabled: bool = False
```

**Rationale**: The dashboard makes high-frequency internal HTTP requests to its own API. Rate limiting these internal requests is counterproductive. The rate limiter should be opt-in (enabled explicitly when deploying behind a reverse proxy that handles its own rate limiting, or when external API access needs protection). This matches the original behavior and the documented default.

### Phase 3: Regression Tests

Add tests that detect these specific regressions:

**Test 1: CSP allows Bootstrap CDN** (`src/tests/regression/test_csp_bootstrap_cdn.py`)

- Verify that the CSP header in responses to `/dashboard/` includes `cdn.jsdelivr.net` in `style-src`
- Verify that `dbc.themes.BOOTSTRAP` URL domain is allowed by the CSP

**Test 2: Rate limiting disabled by default** (`src/tests/regression/test_rate_limit_default.py`)

- Verify that `get_rate_limiter()` returns a disabled limiter when no env vars are set
- Verify that the settings default for `rate_limit_enabled` is `False`
- Verify that enabling via env var still works

**Test 3: Dashboard status bar handles API responses** (extend existing tests)

- Verify status bar callback does not show "Error" when API is healthy
- Verify graceful handling when API returns 429

### Phase 4: Validation

1. Run all existing unit tests: `pytest -m unit -v`
2. Run all existing integration tests: `pytest -m integration -v`
3. Run regression tests: `pytest -m regression -v`
4. Run pre-commit hooks
5. Manual validation in demo mode: verify sidebar, tabs, status bar, no 429s

---

## Files Modified

| File | Change | Phase |
|------|--------|-------|
| `src/middleware.py` | Add `cdn.jsdelivr.net` to CSP `style-src` | 1 |
| `src/security.py` | Revert rate limit default to disabled | 2 |
| `src/settings.py` | Change `rate_limit_enabled` default to `False` | 2 |
| `src/tests/regression/test_csp_bootstrap_cdn.py` | New regression test | 3 |
| `src/tests/regression/test_rate_limit_default.py` | New regression test | 3 |

## Files NOT Modified

| File | Reason |
|------|--------|
| `src/frontend/dashboard_manager.py` | Layout code is correct; issue is CSS not loading |
| `src/main.py` | Middleware wiring is correct; CSP content is the issue |
| `conf/requirements.txt` | Dash 4.0.0 + dbc 2.0.4 are compatible; not a root cause |
| `src/frontend/assets/*.css` | Custom CSS is fine; Bootstrap CSS is the missing piece |

---

## Risk Assessment

| Change | Risk | Mitigation |
|--------|------|------------|
| CSP modification | Low — only adds a trusted CDN domain | Explicit allowlist (not wildcard) |
| Rate limit default revert | Low — restores previous working behavior | Matches documented default; opt-in activation preserved |
| New regression tests | None — additive only | Standard pytest patterns |

---

## Verification Checklist

- [ ] Bootstrap CSS loads in browser (check DevTools Network tab)
- [ ] Sidebar renders at width=3 (25% of container)
- [ ] Tabs render as horizontal tab bar, not bulleted list
- [ ] Only active tab content is visible
- [ ] No 429 errors in server logs during normal operation
- [ ] Training status shows "Running"/"Stopped"/etc., not "Error"
- [ ] Metrics are fetched successfully (non-zero count in logs)
- [ ] Rate limiting can still be enabled via `CANOPY_RATE_LIMIT_ENABLED=true`
- [ ] All existing tests pass
- [ ] Pre-commit hooks pass
