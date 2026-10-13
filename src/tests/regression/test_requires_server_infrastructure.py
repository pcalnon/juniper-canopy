#!/usr/bin/env python
"""Regression tests for the ``requires_server`` test infrastructure.

Guards against two previously-shipped bugs:

1. ``ScopeMismatch`` on ``test_mvp_functionality.py::TestAPIEndpoints``.
   The class previously defined a class-scoped ``base_url`` fixture that
   collided with the session-scoped fixture supplied by the
   ``pytest-base-url`` plugin (pulled in transitively by ``pytest-playwright``
   via the ``[ui-test]`` extra). The plugin's session-scoped autouse
   ``_verify_url`` fixture tried to access ``base_url`` and triggered
   ``ScopeMismatch`` at every test setup.

2. ``CANOPY_API_KEY`` leaking into the in-process FastAPI test app.
   When a developer had ``CANOPY_API_KEY`` set in their shell (e.g., to talk
   to a real running canopy server), the in-process FastAPI ``TestClient``
   loaded with API key authentication enabled and rejected all WebSocket
   connections with code 4001 ("Authentication required"). The conftest now
   captures ``CANOPY_API_KEY`` for the ``auth_headers`` fixture and removes
   it from ``os.environ`` before any import of ``main``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make src/ importable so the helpers below can introspect conftest internals.
_SRC_DIR = Path(__file__).resolve().parents[2]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


def _load_active_conftest():
    """Return the conftest module that pytest *actually* loaded for this session.

    ``importlib.import_module("tests.conftest")`` is unsafe here: pytest may
    have registered the conftest under a path-derived name (e.g.
    ``src.tests.conftest`` or just ``conftest``), and a fresh
    ``importlib.import_module`` re-executes the module body — but
    ``_CAPTURED_CANOPY_API_KEY`` is captured from ``os.environ`` at module
    body time, and by then the original conftest has already popped the var.
    A fresh load therefore reads ``""``, hiding the real captured value.

    Walk ``sys.modules`` and return the module whose ``__file__`` matches the
    actual ``src/tests/conftest.py`` on disk.
    """
    conftest_path = _SRC_DIR / "tests" / "conftest.py"
    expected_resolved = conftest_path.resolve()
    for module in list(sys.modules.values()):
        module_file = getattr(module, "__file__", None)
        if not module_file:
            continue
        try:
            if Path(module_file).resolve() == expected_resolved:
                return module
        except OSError:
            continue
    raise RuntimeError(f"Could not locate the active conftest module in sys.modules; " f"expected one with __file__ resolving to {expected_resolved}")


# ─────────────────────────────────────────────────────────────────────────────
# Bug #1: pytest-base-url ScopeMismatch
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.regression
@pytest.mark.unit
class TestNoBaseUrlFixtureCollision:
    """Ensure no ``requires_server`` test class redefines ``base_url``.

    The ``pytest-base-url`` plugin (transitively pulled in by
    ``pytest-playwright``) defines a session-scoped ``base_url`` fixture and
    a session-scoped autouse ``_verify_url`` fixture that requests
    ``base_url``. Any test class that overrides ``base_url`` with a narrower
    scope (e.g. ``scope="class"``) causes ``ScopeMismatch`` at setup of every
    test in the class. We guard against this by failing if any
    ``requires_server`` test file defines a non-session ``base_url`` fixture.
    """

    @staticmethod
    def _iter_requires_server_files():
        tests_root = Path(__file__).resolve().parents[1]
        for candidate in tests_root.rglob("test_*.py"):
            if "__pycache__" in candidate.parts:
                continue
            try:
                text = candidate.read_text(encoding="utf-8")
            except OSError:
                continue
            if "requires_server" in text:
                yield candidate, text

    def test_mvp_functionality_does_not_define_base_url_fixture(self):
        """The original offender: regression for ScopeMismatch on TestAPIEndpoints."""
        path = Path(__file__).resolve().parents[1] / "integration" / "test_mvp_functionality.py"
        assert path.exists(), f"Sentinel file missing: {path}"
        text = path.read_text(encoding="utf-8")
        # Reject any ``def base_url(`` whether class-scoped or otherwise.
        # The accepted alternative is the ``api_url`` class attribute.
        assert "def base_url(" not in text, "test_mvp_functionality.py reintroduced the ``base_url`` fixture. " "This collides with the session-scoped fixture from pytest-base-url " "(installed via pytest-playwright) and produces ScopeMismatch at " "every test setup. Use a different name (e.g. ``api_url``) or a " "class attribute."

    def test_no_requires_server_file_redefines_base_url_below_session_scope(self):
        """General lint: scan every ``requires_server`` test for the same trap."""
        import re

        # ``def base_url(`` preceded (within ~120 chars) by a fixture decorator
        # whose scope is anything other than ``"session"``.
        offenders: list[tuple[Path, str]] = []
        decorator_pattern = re.compile(
            r"@pytest\.fixture\s*\(([^)]*)\)\s*\n\s*def\s+base_url\s*\(",
            re.MULTILINE,
        )
        for path, text in self._iter_requires_server_files():
            for match in decorator_pattern.finditer(text):
                args = match.group(1)
                # If the decorator omits ``scope="session"`` (or scope at all),
                # the fixture defaults to ``function`` scope, which collides.
                if 'scope="session"' not in args and "scope='session'" not in args:
                    offenders.append((path, match.group(0)))
        assert not offenders, "Found ``base_url`` fixtures with sub-session scope in " f"``requires_server`` test files: {offenders}. " "Rename the fixture or set scope='session' to avoid the " "pytest-base-url ScopeMismatch."


# ─────────────────────────────────────────────────────────────────────────────
# Bug #2: CANOPY_API_KEY leak into in-process app + auth_headers contract
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.regression
@pytest.mark.unit
class TestCanopyApiKeyIsolation:
    """Ensure ``CANOPY_API_KEY`` does not leak into the in-process FastAPI app.

    The conftest captures ``CANOPY_API_KEY`` for the ``auth_headers`` fixture
    and removes it from ``os.environ`` before any import of ``main``. If this
    isolation breaks, every in-process WebSocket test would close with
    "Authentication required" (code 4001).
    """

    def test_canopy_api_key_absent_from_environ_after_conftest_load(self):
        """``CANOPY_API_KEY`` must be popped from ``os.environ`` at conftest load."""
        # By the time any test runs, conftest.py has executed its module body.
        assert "CANOPY_API_KEY" not in os.environ, "``CANOPY_API_KEY`` is present in os.environ during tests. " "The conftest.py must capture-and-pop it before main is imported. " "Otherwise the in-process FastAPI TestClient enables auth and " "rejects all WebSocket connections with code 4001."

    def test_conftest_captured_canopy_api_key_attribute_exists(self):
        """The capture variable must exist for ``auth_headers`` to read from."""
        conftest = _load_active_conftest()
        assert hasattr(conftest, "_CAPTURED_CANOPY_API_KEY"), "tests.conftest must expose ``_CAPTURED_CANOPY_API_KEY`` for the " "auth_headers fixture to consume."
        # The captured value must be a string (whitespace-stripped).
        assert isinstance(conftest._CAPTURED_CANOPY_API_KEY, str)


@pytest.mark.regression
@pytest.mark.unit
class TestAuthHeadersFixture:
    """Contract tests for the new ``auth_headers`` fixture."""

    def test_fixture_is_registered_in_conftest(self):
        """``auth_headers`` must be defined as a session-scoped fixture in conftest."""
        conftest = _load_active_conftest()
        assert hasattr(conftest, "auth_headers"), "auth_headers fixture missing from conftest"
        # FixtureFunctionDefinition exposes the wrapped function under ``__wrapped__`` or ``func``;
        # checking that it's a callable defined in the conftest module is enough.
        target = conftest.auth_headers
        # Pytest's @fixture wrapper preserves callability — verify it's bound to the conftest module.
        underlying = getattr(target, "__wrapped__", target)
        # The fixture must be defined in the conftest module, not re-exported.
        module_name = getattr(underlying, "__module__", "")
        assert module_name.endswith("conftest"), f"auth_headers defined in {module_name!r}, expected a conftest module"

    def test_fixture_returns_dict(self, auth_headers):
        """``auth_headers`` must always return a dict (never None)."""
        assert isinstance(auth_headers, dict)

    def test_fixture_empty_when_no_key_captured(self, auth_headers):
        """Without ``CANOPY_API_KEY`` in env at conftest load, returns ``{}``.

        Because this test sees the same captured value as the rest of the suite,
        we only assert the structural invariant: either the dict is empty (no key
        captured) or contains exactly the ``X-API-Key`` header (key captured).
        """
        if auth_headers:
            assert set(auth_headers.keys()) == {"X-API-Key"}
            assert isinstance(auth_headers["X-API-Key"], str)
            assert auth_headers["X-API-Key"] == auth_headers["X-API-Key"].strip()
            assert auth_headers["X-API-Key"] != ""
        else:
            assert auth_headers == {}

    def test_fixture_matches_captured_value(self, auth_headers):
        """The fixture output must be derived from the conftest-captured value."""
        conftest = _load_active_conftest()
        captured = conftest._CAPTURED_CANOPY_API_KEY
        if captured:
            assert auth_headers == {"X-API-Key": captured}
        else:
            assert auth_headers == {}


# ─────────────────────────────────────────────────────────────────────────────
# Behavioural regression: in-process app must not require auth even when
# CANOPY_API_KEY *was* in the shell env at pytest invocation time.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.regression
@pytest.mark.integration
class TestInProcessAppAuthDisabled:
    """The in-process FastAPI app must load with auth disabled in tests.

    Even when ``CANOPY_API_KEY`` was set in the developer's shell, the conftest
    pops it from ``os.environ`` before ``main`` is imported. This test asserts
    the resulting app has the API key authenticator disabled, so WebSocket
    tests can connect freely.
    """

    def test_security_apikey_auth_disabled_in_test_process(self):
        """``security.APIKeyAuth`` defaults to disabled when no key is configured."""
        # NEVER importlib.reload(security) here: reload re-executes the module
        # in place, re-minting NonLoopbackBindError / INTERNAL_REQUEST_TOKEN
        # underneath already-collected test modules (test_bind_guard /
        # test_security hold the originals), failing them whenever this file
        # runs before unit/ (bare ``pytest`` orders regression/ first; CI's
        # explicit ``src/tests/unit/ src/tests/regression/`` order masks it).
        # APIKeyAuth reads no env at construction, so a plain import probes
        # the no-keys-means-disabled contract just as well.
        import security as security_module

        auth = security_module.APIKeyAuth()
        assert auth.enabled is False, "APIKeyAuth(api_keys=None) reported enabled=True. " "Either the env leaked a key into the constructor, or the " "no-keys-means-disabled contract changed — the in-process " "WebSocket tests rely on this."

    def test_in_process_health_endpoint_does_not_require_auth(self, client):
        """``/health`` returns 200 from the in-process app without any X-API-Key."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_in_process_websocket_connect_does_not_close_with_4001(self, client):
        """``/ws/training`` must not close with code 4001 in the in-process test app.

        Code 4001 ("Authentication required") is sent when CANOPY_API_KEY leaks
        into the test process and enables auth on the WebSocket router. This
        is the exact failure mode that the conftest CANOPY_API_KEY isolation
        prevents.
        """
        # If the conftest isolation breaks, this with-block raises
        # WebSocketDisconnect with code=4001 immediately.
        with client.websocket_connect("/ws/training") as ws:
            first = ws.receive_json()
            assert first.get("type") == "connection_established", f"Expected 'connection_established' on /ws/training, got {first!r}. " "If you see WebSocketDisconnect(4001) instead, the CANOPY_API_KEY " "isolation in conftest.py has regressed."


# ─────────────────────────────────────────────────────────────────────────────
# Lint: every requires_server test that calls ``/api/state`` (or other
# auth-protected endpoint) should accept the ``auth_headers`` fixture, so
# that tests pass against both ``./demo`` (no auth) and production-config
# servers (auth enabled).
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.regression
@pytest.mark.unit
def test_auth_protected_requires_server_tests_use_auth_headers():
    """``requires_server`` tests that hit auth-protected endpoints must accept ``auth_headers``.

    Auth-protected endpoints include any ``/api/<path>`` URL (the only public
    exemption is the ``/health`` family). When a server has ``CANOPY_API_KEY``
    set, these endpoints return 401 unless the X-API-Key header is sent. The
    fix shipped a session-scoped ``auth_headers`` fixture that tests opt into
    by accepting it as a parameter; this guards against new ``requires_server``
    tests being added without using it.
    """
    # Known sentinels — these are the four tests that originally failed with 401.
    sentinel_files = {
        "regression/test_candidate_visibility.py": [
            "test_state_endpoint_returns_data",
            "test_candidate_pool_becomes_active",
            "test_pool_metrics_available_when_active",
        ],
        "integration/test_parameter_persistence.py": ["test_api_set_params_integration"],
        "integration/test_mvp_functionality.py": [
            "test_health_endpoint",
            "test_status_endpoint",
            "test_metrics_endpoint",
            "test_topology_endpoint",
            "test_dataset_endpoint",
        ],
    }
    tests_root = Path(__file__).resolve().parents[1]
    missing: list[str] = []
    for rel_path, test_names in sentinel_files.items():
        full_path = tests_root / rel_path
        assert full_path.exists(), f"Sentinel test file missing: {full_path}"
        text = full_path.read_text(encoding="utf-8")
        for name in test_names:
            # Locate the def line and verify ``auth_headers`` appears in the signature.
            needle = f"def {name}("
            idx = text.find(needle)
            assert idx != -1, f"Sentinel test {rel_path}::{name} not found"
            # Read until the closing ``)``.
            close_idx = text.find(")", idx)
            assert close_idx != -1, f"Could not parse signature of {rel_path}::{name}"
            signature = text[idx:close_idx]
            if "auth_headers" not in signature:
                missing.append(f"{rel_path}::{name}")
    assert not missing, "These ``requires_server`` tests no longer accept the ``auth_headers`` " "fixture — they will fail with 401 when CANOPY_API_KEY is set on the " f"server: {missing}"


# ─────────────────────────────────────────────────────────────────────────────
# Sanity: ``test_mvp_functionality.py`` uses the renamed ``api_url`` attribute
# (or fixture) — the ScopeMismatch fix.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.regression
@pytest.mark.unit
def test_mvp_test_api_endpoints_class_exposes_api_url():
    """``TestAPIEndpoints`` must expose ``api_url`` to its tests.

    The ScopeMismatch fix renamed the ``base_url`` fixture to an ``api_url``
    class attribute. The 5 test methods rely on ``self.api_url`` to address
    the server. If a refactor renames or removes it, every test in the class
    silently regresses.
    """
    path = Path(__file__).resolve().parents[1] / "integration" / "test_mvp_functionality.py"
    text = path.read_text(encoding="utf-8")
    assert "api_url" in text, "TestAPIEndpoints must reference ``api_url`` after the ScopeMismatch fix"
    # And every test method body must use it (no stragglers still using base_url).
    for method in (
        "test_health_endpoint",
        "test_status_endpoint",
        "test_metrics_endpoint",
        "test_topology_endpoint",
        "test_dataset_endpoint",
    ):
        idx = text.find(f"def {method}(")
        assert idx != -1, f"{method} missing"
        # Find the end of the method (next ``def `` or end of file).
        next_def = text.find("\n    def ", idx + 1)
        body = text[idx : next_def if next_def != -1 else len(text)]
        assert "self.api_url" in body, f"{method} does not use ``self.api_url`` — ScopeMismatch fix incomplete"
