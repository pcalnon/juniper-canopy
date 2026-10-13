"""PR-1 (Start-Training 401 fix): same-origin browser control-surface auth.

Exercises the *real* auth path end-to-end — the key-exempt middleware tier,
the ``require_browser_control_auth`` dependency on ``/api/train/*``, the
``/api/csrf`` Origin hardening, and the ``/ws/control`` key-gate relaxation —
against the real ``main.app`` and the real ``SecurityMiddleware``. The auth
seam is never stubbed away (the canopy "green tests / dead app" risk class):
enabling API-key auth only configures *which* key is valid and *that* auth is
on; the accept/reject logic under test runs unmodified.

Design of record: notes/JUNIPER_CANOPY_TRAINING-CONTROL-AUTH_DESIGN_2026-06-30.md
"""

import pytest

_ALLOWED_ORIGIN = "http://localhost:8050"  # in the default allowed_origins
_DISALLOWED_ORIGIN = "http://evil.example"
_TEST_KEY = "browser-ctl-test-key"


def _enable_api_key_auth(monkeypatch, key: str = _TEST_KEY) -> str:
    """Turn API-key auth ON against the real app, without stubbing the seam.

    Points BOTH the singleton accessor (``get_api_key_auth`` — used by the REST
    dependency and ``/api/csrf``) and the module-level ``main.api_key_auth``
    (used by ``_authenticate_websocket``) at ONE shared enabled instance, so
    every real auth surface agrees on the configured key. ``reset_singletons``
    (autouse) has already nulled the security singletons at setup, so the first
    ``get_api_key_auth()`` call in the request sees this instance.
    """
    import main
    import security

    auth = security.APIKeyAuth([key])
    monkeypatch.setattr(security, "_api_key_auth", auth)
    monkeypatch.setattr(main, "api_key_auth", auth)
    return key


def _settings_in_use():
    """Return the cached ``Settings`` instance the app reads at request time.

    ``reset_singletons`` clears ``get_settings``'s lru_cache at setup, so the
    first call here materialises the very instance the dependency will read;
    patch attributes on it to steer flag behaviour.
    """
    from settings import get_settings

    return get_settings()


def _mint_csrf(client, origin: str = _ALLOWED_ORIGIN) -> str:
    """Mint a real CSRF token via ``/api/csrf`` (same-origin so hardening passes)."""
    resp = client.get("/api/csrf", headers={"Origin": origin})
    assert resp.status_code == 200, resp.text
    return resp.json()["csrf_token"]


@pytest.mark.unit
class TestKeyExemptTierMiddleware:
    """§8.1: the key-exempt tier is auth-exempt but STILL rate-limited."""

    @staticmethod
    def _make_app(api_keys, rate_limit_enabled=False, rate_limit_rpm=60):
        from fastapi import FastAPI

        from middleware import SecurityMiddleware
        from security import APIKeyAuth, RateLimiter

        app = FastAPI()
        app.add_middleware(
            SecurityMiddleware,
            api_key_auth=APIKeyAuth(api_keys),
            rate_limiter=RateLimiter(requests_per_minute=rate_limit_rpm, enabled=rate_limit_enabled),
        )

        @app.get("/api/csrf")
        def csrf():
            return {"csrf_token": "t", "enabled": True}

        @app.post("/api/train/start")
        def train_start():
            return {"status": "started"}

        @app.get("/v1/protected")
        def protected():
            return {"ok": True}

        return app

    def test_csrf_reachable_without_key(self):
        from fastapi.testclient import TestClient

        client = TestClient(self._make_app(["k"]))
        assert client.get("/api/csrf").status_code == 200  # key-exempt, not 401

    def test_train_prefix_reachable_without_key(self):
        from fastapi.testclient import TestClient

        client = TestClient(self._make_app(["k"]))
        # No 401 from the middleware: the request reaches the route (the real
        # app then hands /api/train/* to require_browser_control_auth).
        assert client.post("/api/train/start").status_code == 200

    def test_v1_still_key_gated(self):
        from fastapi.testclient import TestClient

        client = TestClient(self._make_app(["k"]))
        assert client.get("/v1/protected").status_code == 401  # NOT key-exempt

    def test_csrf_key_exempt_but_still_rate_limited(self):
        from fastapi.testclient import TestClient

        client = TestClient(self._make_app(["k"], rate_limit_enabled=True, rate_limit_rpm=2))
        assert client.get("/api/csrf").status_code == 200
        assert client.get("/api/csrf").status_code == 200
        assert client.get("/api/csrf").status_code == 429  # limiter still runs

    def test_train_key_exempt_but_still_rate_limited(self):
        from fastapi.testclient import TestClient

        client = TestClient(self._make_app(["k"], rate_limit_enabled=True, rate_limit_rpm=1))
        assert client.post("/api/train/start").status_code == 200
        assert client.post("/api/train/start").status_code == 429


@pytest.mark.unit
class TestRequireBrowserControlAuthMatrix:
    """§8.2: the key-OR-(Origin+CSRF) acceptance rule, via the real dependency.

    Drives ``GET /api/train/status`` on the real app (a read-only route carrying
    the dependency) so the middleware tier-split AND the dependency both run.
    """

    _ROUTE = "/api/train/status"

    def test_open_mode_passes_when_auth_disabled(self, client):
        # Default test env has no CANOPY_API_KEY -> auth disabled -> open access.
        assert client.get(self._ROUTE).status_code == 200

    def test_valid_key_no_origin_no_csrf_passes(self, client, monkeypatch):
        key = _enable_api_key_auth(monkeypatch)
        assert client.get(self._ROUTE, headers={"X-API-Key": key}).status_code == 200

    def test_invalid_key_rejected_401(self, client, monkeypatch):
        _enable_api_key_auth(monkeypatch)
        resp = client.get(self._ROUTE, headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid API key."

    def test_no_key_origin_allowed_csrf_valid_passes(self, client, monkeypatch):
        _enable_api_key_auth(monkeypatch)
        token = _mint_csrf(client)
        resp = client.get(self._ROUTE, headers={"Origin": _ALLOWED_ORIGIN, "X-CSRF-Token": token})
        assert resp.status_code == 200

    def test_no_key_reaches_dependency_not_middleware_401(self, client, monkeypatch):
        # Keyless, no Origin/CSRF, auth ON: the middleware no longer 401s
        # (the path is key-exempt); the request reaches the dependency, which
        # fails Origin-closed with a 403 — proving the seam is real, not masked.
        _enable_api_key_auth(monkeypatch)
        resp = client.get(self._ROUTE)
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Origin not allowed."

    def test_no_key_origin_disallowed_rejected_403(self, client, monkeypatch):
        _enable_api_key_auth(monkeypatch)
        token = _mint_csrf(client)
        resp = client.get(self._ROUTE, headers={"Origin": _DISALLOWED_ORIGIN, "X-CSRF-Token": token})
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Origin not allowed."

    def test_no_key_origin_allowed_csrf_missing_rejected_403(self, client, monkeypatch):
        _enable_api_key_auth(monkeypatch)
        resp = client.get(self._ROUTE, headers={"Origin": _ALLOWED_ORIGIN})
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Invalid or missing CSRF token."

    def test_no_key_origin_allowed_csrf_invalid_rejected_403(self, client, monkeypatch):
        _enable_api_key_auth(monkeypatch)
        resp = client.get(self._ROUTE, headers={"Origin": _ALLOWED_ORIGIN, "X-CSRF-Token": "bogus-token"})
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Invalid or missing CSRF token."

    def test_flag_off_preserves_key_requirement_401(self, client, monkeypatch):
        # browser_control_auth_enabled=False: a keyless browser request is
        # rejected 401 even with a valid Origin + CSRF (pre-fix behaviour).
        _enable_api_key_auth(monkeypatch)
        token = _mint_csrf(client)
        monkeypatch.setattr(_settings_in_use(), "browser_control_auth_enabled", False)
        resp = client.get(self._ROUTE, headers={"Origin": _ALLOWED_ORIGIN, "X-CSRF-Token": token})
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Missing API key. Provide X-API-Key header."

    def test_csrf_disabled_origin_only_passes(self, client, monkeypatch):
        # csrf_enabled=False -> Origin-only browser auth (design OQ-6).
        _enable_api_key_auth(monkeypatch)
        monkeypatch.setattr(_settings_in_use(), "csrf_enabled", False)
        resp = client.get(self._ROUTE, headers={"Origin": _ALLOWED_ORIGIN})
        assert resp.status_code == 200


@pytest.mark.unit
class TestApiCsrfOriginHardening:
    """§6: /api/csrf stays key-exempt but is not an off-origin token oracle."""

    def test_anonymous_mint_open_when_auth_disabled(self, client):
        # Default env (auth disabled): anonymously mintable, no Origin needed.
        resp = client.get("/api/csrf")
        assert resp.status_code == 200
        assert len(resp.json()["csrf_token"]) > 20

    def test_same_origin_mint_allowed(self, client, monkeypatch):
        _enable_api_key_auth(monkeypatch)
        resp = client.get("/api/csrf", headers={"Origin": _ALLOWED_ORIGIN})
        assert resp.status_code == 200
        assert len(resp.json()["csrf_token"]) > 20

    def test_off_origin_mint_rejected_403(self, client, monkeypatch):
        _enable_api_key_auth(monkeypatch)
        resp = client.get("/api/csrf", headers={"Origin": _DISALLOWED_ORIGIN})
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Origin not allowed."

    def test_missing_origin_mint_allowed_same_origin(self, client, monkeypatch):
        # A same-origin browser GET omits the Origin header entirely (it sends
        # sec-fetch-site: same-origin instead) — this is the bootstrap the
        # dashboard runs on page load. Missing Origin == same-origin and MUST mint
        # a token, else window.__canopy_csrf never populates and the browser
        # control surface 403s. Regression guard for the shipped-then-fixed
        # /api/csrf same-origin bootstrap defect (browser sends no Origin on GET).
        _enable_api_key_auth(monkeypatch)
        resp = client.get("/api/csrf")
        assert resp.status_code == 200
        assert len(resp.json()["csrf_token"]) > 20

    def test_keyed_caller_bypasses_origin(self, client, monkeypatch):
        # A valid key mints even off-origin (keyed callers are trusted).
        key = _enable_api_key_auth(monkeypatch)
        resp = client.get("/api/csrf", headers={"X-API-Key": key})
        assert resp.status_code == 200
        assert len(resp.json()["csrf_token"]) > 20


@pytest.mark.unit
class TestWsControlBrowserAuthRelaxation:
    """§8.3 (C2): /ws/control accepts the keyless same-origin browser via
    Origin + CSRF first-frame once the key gate is relaxed; keyed still works."""

    def test_keyless_allowed_origin_valid_csrf_accepted(self, client, monkeypatch):
        _enable_api_key_auth(monkeypatch)
        token = _mint_csrf(client)
        with client.websocket_connect("/ws/control", headers={"origin": _ALLOWED_ORIGIN}, _skip_csrf=True) as ws:
            ws.send_json({"type": "auth", "csrf_token": token})
            ws.send_json({"command": "unknown_browser_auth_probe"})
            resp = ws.receive_json()
            assert isinstance(resp, dict)

    def test_keyless_disallowed_origin_closed_4003(self, client, monkeypatch):
        from starlette.websockets import WebSocketDisconnect

        _enable_api_key_auth(monkeypatch)
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/control", headers={"origin": _DISALLOWED_ORIGIN}, _skip_csrf=True):
                pass
        assert exc.value.code == 4003

    def test_keyless_bad_csrf_first_frame_closed_1008(self, client, monkeypatch):
        from starlette.websockets import WebSocketDisconnect

        _enable_api_key_auth(monkeypatch)
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/control", headers={"origin": _ALLOWED_ORIGIN}, _skip_csrf=True) as ws:
                ws.send_json({"type": "auth", "csrf_token": "not-a-valid-token"})
                # Drain the on-connect frame(s), then hit the 1008 close.
                for _ in range(5):
                    ws.receive_json()
        assert exc.value.code == 1008

    def test_valid_key_still_accepted(self, client, monkeypatch):
        key = _enable_api_key_auth(monkeypatch)
        token = _mint_csrf(client)
        with client.websocket_connect("/ws/control", headers={"origin": _ALLOWED_ORIGIN, "X-API-Key": key}, _skip_csrf=True) as ws:
            ws.send_json({"type": "auth", "csrf_token": token})
            ws.send_json({"command": "unknown_browser_auth_probe"})
            resp = ws.receive_json()
            assert isinstance(resp, dict)
