"""Phase D §S10: control-button routing and /ws/control envelope tests.

Covers the canopy-side upgrades that ship the server half of Phase D:

1. ``create_command_response_message`` helper — envelope shape, command_id
   echo, ``code`` field, and legacy compat fields for pre-Phase-D callers.
2. ``enable_ws_control_buttons`` feature flag defaults and coexistence with
   ``use_websocket_set_params`` (Phase C).
3. ``/ws/control`` endpoint behavior via ``TestClient``: ``command_id`` echo,
   ``code:"unknown_command"`` on rejection, ``set_params`` command routing
   through the adapter.
4. Per-command timeouts (start=10s, stop/pause/resume/reset=2s,
   set_params=1s) enforced by ``asyncio.wait_for``; hanging commands emit
   ``command_response{status:"error", error:"...timed out..."}`` while
   leaving the connection open for the next command.

The cascor half of Phase D lives in
``juniper-cascor/src/tests/unit/api/test_control_stream_timeouts.py``
(shipped in P11); this file is the canopy mirror for P12.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure src/ is importable when tests are run from the repo root.
SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Force demo mode so main.py's backend is the demo backend rather than
# trying to connect to a live cascor instance.
os.environ.setdefault("JUNIPER_CANOPY_DEMO_MODE", "1")


# =====================================================================
# 1. create_command_response_message helper
# =====================================================================


@pytest.mark.unit
class TestCommandResponseHelper:
    """§S10: canonical command_response envelope shape."""

    def test_success_envelope_minimum_fields(self):
        from communication.websocket_manager import create_command_response_message

        msg = create_command_response_message("start", "success")
        assert msg["type"] == "command_response"
        assert msg["data"]["command"] == "start"
        assert msg["data"]["status"] == "success"

    def test_command_id_echo(self):
        from communication.websocket_manager import create_command_response_message

        msg = create_command_response_message("start", "success", command_id="abc-123")
        assert msg["data"]["command_id"] == "abc-123"

    def test_result_payload_under_data(self):
        from communication.websocket_manager import create_command_response_message

        msg = create_command_response_message("start", "success", data={"is_running": True})
        assert msg["data"]["result"] == {"is_running": True}

    def test_error_envelope_includes_error_and_code(self):
        from communication.websocket_manager import create_command_response_message

        msg = create_command_response_message(
            "explode",
            "error",
            error="Unknown command: explode",
            code="unknown_command",
            command_id="reject-1",
        )
        assert msg["data"]["status"] == "error"
        assert msg["data"]["error"] == "Unknown command: explode"
        assert msg["data"]["code"] == "unknown_command"
        assert msg["data"]["command_id"] == "reject-1"

    def test_legacy_compat_fields_for_pre_phase_d_callers(self):
        """``ok``/``command``/``state`` top-level fields keep old tests green."""
        from communication.websocket_manager import create_command_response_message

        msg = create_command_response_message("start", "success", data={"is_running": True})
        assert msg["ok"] is True
        assert msg["command"] == "start"
        assert msg["state"] == {"is_running": True}

    def test_legacy_compat_on_error(self):
        from communication.websocket_manager import create_command_response_message

        msg = create_command_response_message("stop", "error", error="boom")
        assert msg["ok"] is False
        assert msg["error"] == "boom"


# =====================================================================
# 2. enable_ws_control_buttons feature flag
# =====================================================================


@pytest.mark.unit
class TestFeatureFlag:
    """D-49: post-P12b flip, default is ON — browser buttons route through
    /ws/control on the happy path with REST fallback. Kill switch is
    ``JUNIPER_CANOPY_ENABLE_WS_CONTROL_BUTTONS=false`` per §S10.7 rollback.
    """

    def test_enable_ws_control_buttons_default_on_after_flip(self):
        """Post-production-soak: code default is True (P12b flag flip)."""
        from settings import get_settings

        settings = get_settings()
        assert settings.enable_ws_control_buttons is True

    def test_kill_switch_env_var_disables_flag(self, monkeypatch):
        """§S10.7 rollback path: env var false forces back to REST."""
        from settings import Settings

        monkeypatch.setenv("JUNIPER_CANOPY_ENABLE_WS_CONTROL_BUTTONS", "false")
        fresh = Settings()
        assert fresh.enable_ws_control_buttons is False

    def test_per_command_timeouts_match_spec(self):
        from settings import get_settings

        settings = get_settings()
        assert settings.ws_control_start_timeout == 10.0
        assert settings.ws_control_stop_timeout == 2.0
        assert settings.ws_control_set_params_timeout == 1.0

    def test_phase_c_and_phase_d_flags_independent(self):
        """Phase C and Phase D flags can be toggled independently."""
        from settings import get_settings

        settings = get_settings()
        # The two flags are distinct settings — flipping one should not
        # require the other. Both are now default-on post-canary flip.
        assert hasattr(settings, "use_websocket_set_params")
        assert hasattr(settings, "enable_ws_control_buttons")


# =====================================================================
# 3. /ws/control endpoint: envelope + command_id + unknown_command code
# =====================================================================


@pytest.fixture
def demo_app():
    """Load main.py in demo mode and return the FastAPI app."""
    os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"
    # Force a re-import so environment changes take effect when tests run
    # in isolation, but reuse the cached module otherwise.
    if "main" in sys.modules:
        return sys.modules["main"].app
    from main import app

    return app


def _skip_connection_message(websocket):
    """Consume the initial connection_established frame."""
    conn = websocket.receive_json()
    assert conn.get("type") == "connection_established"
    return conn


def _next_command_response(websocket, max_messages: int = 50):
    """Return the next ``command_response`` frame, skipping broadcasts."""
    for _ in range(max_messages):
        msg = websocket.receive_json()
        if msg.get("type") == "command_response":
            return msg
    raise TimeoutError("No command_response within the scan window")


@pytest.mark.unit
class TestWsControlEnvelope:
    """§S10.3: browser contract on canopy's /ws/control."""

    def test_command_id_echoed_on_success(self, demo_app):
        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            with client.websocket_connect("/ws/control") as ws:
                _skip_connection_message(ws)
                ws.send_json({"command": "start", "command_id": "btn-start-1", "reset": True})
                resp = _next_command_response(ws)
                assert resp["data"]["status"] == "success"
                assert resp["data"]["command"] == "start"
                assert resp["data"]["command_id"] == "btn-start-1"

    def test_unknown_command_rejected_with_code(self, demo_app):
        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            with client.websocket_connect("/ws/control") as ws:
                _skip_connection_message(ws)
                ws.send_json({"command": "explode", "command_id": "bad-1"})
                resp = _next_command_response(ws)
                assert resp["data"]["status"] == "error"
                assert resp["data"]["code"] == "unknown_command"
                assert resp["data"]["command_id"] == "bad-1"

    def test_stop_after_start_survives_unknown_command(self, demo_app):
        """§S10: connection stays open after an unknown_command rejection."""
        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            with client.websocket_connect("/ws/control") as ws:
                _skip_connection_message(ws)
                ws.send_json({"command": "not-a-command"})
                err = _next_command_response(ws)
                assert err["data"]["status"] == "error"
                ws.send_json({"command": "stop", "command_id": "recovery-1"})
                ok = _next_command_response(ws)
                assert ok["data"]["status"] == "success"
                assert ok["data"]["command_id"] == "recovery-1"

    def test_invalid_json_returns_error_envelope(self, demo_app):
        from fastapi.testclient import TestClient

        with TestClient(demo_app) as client:
            with client.websocket_connect("/ws/control") as ws:
                _skip_connection_message(ws)
                ws.send_text("not json at all")
                resp = _next_command_response(ws)
                assert resp["data"]["status"] == "error"


# =====================================================================
# 4. Per-command timeouts via asyncio.wait_for
# =====================================================================


@pytest.mark.unit
class TestPerCommandTimeouts:
    """§S10.1: per-command budgets enforced on canopy's /ws/control."""

    def _patch_timeouts_to(self, main_module, seconds: float):
        """Shrink every /ws/control per-command budget to ``seconds``.

        The dict is mutable and read on every command, so tests can force
        ``asyncio.wait_for`` to trip without disturbing the pydantic
        Settings model.
        """
        original = dict(main_module._PHASE_D_CONTROL_TIMEOUTS)
        for key in main_module._PHASE_D_CONTROL_TIMEOUTS:
            main_module._PHASE_D_CONTROL_TIMEOUTS[key] = seconds
        return original

    def _restore_timeouts(self, main_module, original):
        main_module._PHASE_D_CONTROL_TIMEOUTS.clear()
        main_module._PHASE_D_CONTROL_TIMEOUTS.update(original)

    def test_stop_timeout_trips_on_hanging_backend(self, demo_app):
        """Backend that blocks longer than the timeout yields timeout error."""
        from fastapi.testclient import TestClient

        import main as main_module

        def _hang(*args, **kwargs):
            import time

            time.sleep(0.5)  # Longer than the 0.1s patched budget
            return {"is_running": False}

        original = self._patch_timeouts_to(main_module, 0.1)
        try:
            with TestClient(main_module.app) as client:
                # main.backend is None until lifespan startup runs — patch
                # inside the TestClient context after the real instance is set.
                saved_stop = main_module.backend.stop_training
                main_module.backend.stop_training = _hang
                try:
                    with client.websocket_connect("/ws/control") as ws:
                        _skip_connection_message(ws)
                        ws.send_json({"command": "stop", "command_id": "hang-1"})
                        resp = _next_command_response(ws)
                        assert resp["data"]["status"] == "error"
                        assert "timed out" in resp["data"]["error"].lower()
                        assert resp["data"]["command_id"] == "hang-1"
                finally:
                    main_module.backend.stop_training = saved_stop
        finally:
            self._restore_timeouts(main_module, original)

    def test_timeout_keeps_connection_open(self, demo_app):
        """After a timeout error the socket stays open for the next command."""
        from fastapi.testclient import TestClient

        import main as main_module

        call_count = {"n": 0}

        def _hang_then_succeed(*args, **kwargs):
            import time

            call_count["n"] += 1
            if call_count["n"] == 1:
                time.sleep(0.5)
            return {"current_epoch": 0}

        original = self._patch_timeouts_to(main_module, 0.1)
        try:
            with TestClient(main_module.app) as client:
                saved_reset = main_module.backend.reset_training
                main_module.backend.reset_training = _hang_then_succeed
                try:
                    with client.websocket_connect("/ws/control") as ws:
                        _skip_connection_message(ws)
                        ws.send_json({"command": "reset", "command_id": "reset-hang"})
                        first = _next_command_response(ws)
                        assert first["data"]["status"] == "error"
                        ws.send_json({"command": "reset", "command_id": "reset-ok"})
                        second = _next_command_response(ws)
                        assert second["data"]["status"] == "success"
                        assert second["data"]["command_id"] == "reset-ok"
                finally:
                    main_module.backend.reset_training = saved_reset
        finally:
            self._restore_timeouts(main_module, original)
