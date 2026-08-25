"""Phase D §S10.3 (P12b): clientside training-button routing.

Verifies that when ``settings.enable_ws_control_buttons`` is True the
DashboardManager registers a clientside callback that routes training
button clicks through ``window.cascorControlWS.send(...)`` with an
automatic REST fallback. When the flag is off (default) the existing
server-side handler remains wired so all pre-Phase-D tests and fixtures
stay green.

These tests focus on *wiring* — verifying the JS string is registered
as a Dash clientside callback, that the server-side handler method
still exists for legacy tests to invoke directly, and that the JS body
contains the structural contract points (send(), fetch fallback,
command_id, debouncing). Browser-level end-to-end coverage lives in
Playwright (§S10.4 tests flagged "Playwright").
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault("JUNIPER_CANOPY_DEMO_MODE", "1")


# =====================================================================
# JS string contract — purely static, no Dash instantiation required.
# =====================================================================


@pytest.mark.unit
class TestClientsideJsContract:
    """The JS string is the contract — assert it carries the §S10 pieces."""

    def test_module_exports_constant(self):
        from frontend.dashboard_manager import PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

        assert isinstance(PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS, str)
        assert PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS.strip().startswith("function(")

    def test_js_routes_through_cascor_control_ws_send(self):
        from frontend.dashboard_manager import PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

        assert "window.cascorControlWS" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS
        assert "ws.send(" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS
        assert "command_id" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

    def test_js_includes_rest_fallback_on_rejection(self):
        from frontend.dashboard_manager import PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

        assert "restFallback" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS
        assert "/api/train/" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS
        # F-CANOPY-005: the fallback fires ONLY on transport-class failures
        # (err.transport, set by websocket_client.js); a business rejection is
        # surfaced to the operator instead of re-POSTing an adjudicated
        # state-changing command (the observed resume->409 double-fire).
        assert "err.transport" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS
        assert "WS transport failure" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS
        assert "WS business rejection" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS
        assert "WS rejected" not in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

    def test_js_maps_all_five_training_buttons(self):
        from frontend.dashboard_manager import PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

        for button in ("start-button", "pause-button", "stop-button", "resume-button", "reset-button"):
            assert button in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

    def test_js_preserves_500ms_debounce(self):
        from frontend.dashboard_manager import PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

        # 0.5 second debounce guard, same as server-side.
        assert "sinceLast < 0.5" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS
        assert "last_click.button" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

    def test_js_marks_transport_for_observability(self):
        from frontend.dashboard_manager import PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

        # Return payload must flag which transport was used so the
        # downstream `update_last_click` + button-timeout sweeper can
        # reason about WS-vs-REST button lifecycle.
        assert "transport: 'ws'" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS
        assert "transport: 'rest'" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

    def test_js_sets_optimistic_loading_state(self):
        from frontend.dashboard_manager import PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

        assert "disabled: true" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS
        assert "loading: true" in PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

    def test_js_reports_failure_via_set_props(self):
        """The async outcome must be pushed back into ``training-control-action``
        via ``set_props`` so a rejected command surfaces a UI alert rather than
        only a console.warn ("dead button" class). See
        notes/CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md."""
        from frontend.dashboard_manager import PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

        js = PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS
        assert "function reportFailure" in js
        assert "set_props" in js
        assert "'training-control-action'" in js
        assert "success: false" in js

    def test_js_report_failure_invoked_from_rest_fallback(self):
        """``reportFailure`` must actually be wired into the REST-fallback failure
        branches (non-OK response and network catch), not merely defined."""
        from frontend.dashboard_manager import PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

        js = PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS
        # Defined once, invoked at least twice (non-OK body branch + .catch).
        assert js.count("reportFailure(") >= 3  # 1 definition + >=2 call sites
        # Surfaces the HTTP status on a non-OK response.
        assert "'HTTP ' + resp.status" in js

    def test_js_forwards_oneshot_dataset_ref_body(self):
        """A1-iv-3c: a one-shot (recurrence) Start must carry the dataset-ref body on BOTH the
        WS send (as the control-message ``params``) and the REST fallback (as the JSON body);
        every other command and a live (cascor/demo) Start send none. The resolved body arrives
        as the callback's trailing ``oneshot_start_body`` State, so the JS never re-resolves the
        registry params client-side."""
        from frontend.dashboard_manager import PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS

        js = PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS
        # The resolved body arrives as the trailing positional arg (the new State).
        assert "oneshot_start_body" in js
        # Gated to the start command only (present in both the WS and REST branches).
        assert js.count("command === 'start' && oneshot_start_body") >= 2
        # WS transport attaches it as the control-message ``params``.
        assert "sendMsg.params = oneshot_start_body" in js
        # REST fallback attaches it as a JSON body with the matching content type.
        assert "JSON.stringify(oneshot_start_body)" in js
        assert "'Content-Type': 'application/json'" in js


# =====================================================================
# Registration behavior — flag-gated clientside vs server-side.
# =====================================================================


def _build_dashboard(monkeypatch, *, flag: bool):
    """Instantiate a fresh DashboardManager with ``enable_ws_control_buttons`` forced."""
    import frontend.dashboard_manager as dm_module
    from settings import Settings

    # Build a fresh Settings instance so pydantic validators run once and
    # the instance isn't shared with ``get_settings()``'s cached singleton.
    base = Settings()
    object.__setattr__(base, "enable_ws_control_buttons", flag)

    monkeypatch.setattr(dm_module, "get_settings", lambda: base, raising=True)
    return dm_module.DashboardManager({})


def _phase_d_js_inlined(dm) -> bool:
    """Return True iff the Phase D JS body is present in Dash's inline scripts."""
    for script in dm.app._inline_scripts:
        body = str(script)
        if "cascorControlWS" in body and "buttonMap" in body:
            return True
    return False


@pytest.mark.unit
class TestCallbackRegistration:
    """D-49: flag gates whether the clientside callback is wired."""

    def test_default_off_server_side_handler_still_wired(self, monkeypatch):
        dm = _build_dashboard(monkeypatch, flag=False)

        assert _phase_d_js_inlined(dm) is False
        # The Python handler stays on the class regardless — used by the
        # server-side callback AND by the existing unit/integration tests.
        assert callable(dm._handle_training_buttons_handler)

    def test_flag_on_registers_clientside_js(self, monkeypatch):
        dm = _build_dashboard(monkeypatch, flag=True)

        assert _phase_d_js_inlined(dm) is True
        # Python handler still exists — tests that hit it directly
        # (test_button_state.py, test_button_responsiveness.py) keep
        # working because they bypass Dash callback dispatch.
        assert callable(dm._handle_training_buttons_handler)

    def test_training_control_action_output_registered_either_way(self, monkeypatch):
        """Whichever branch fires, the same Output contract holds."""
        for flag in (False, True):
            dm = _build_dashboard(monkeypatch, flag=flag)
            keys = list(dm.app.callback_map.keys())
            assert any("training-control-action" in k for k in keys), f"flag={flag}: callback_map missing training-control-action"
            assert any("button-states.data" in k for k in keys), f"flag={flag}: callback_map missing button-states"

    def test_outcome_alert_render_callback_registered_either_way(self, monkeypatch):
        """The outcome-alert render callback is wired regardless of the transport
        flag — both the server-side handler and the clientside JS feed it via the
        training-control-action store."""
        for flag in (False, True):
            dm = _build_dashboard(monkeypatch, flag=flag)
            keys = list(dm.app.callback_map.keys())
            assert any("training-control-outcome-alert.children" in k for k in keys), f"flag={flag}: callback_map missing training-control-outcome-alert render callback"


# =====================================================================
# Server-side handler regression — MUST still work when flag is off.
# =====================================================================


@pytest.mark.unit
class TestServerSideHandlerStillFunctional:
    """Guarantees the REST path keeps working for the non-browser test
    harness and for the pre-flag-flip default configuration."""

    def test_start_button_maps_to_start_command(self, monkeypatch):
        import frontend.dashboard_manager as dm_module

        dm = _build_dashboard(monkeypatch, flag=False)

        # Fake a click trigger + a successful POST.
        fake_ctx = MagicMock()
        fake_ctx.get_triggered_id.return_value = "start-button"
        monkeypatch.setattr(dm_module, "get_callback_context", lambda: fake_ctx, raising=True)

        fake_response = MagicMock()
        fake_response.raise_for_status.return_value = None
        monkeypatch.setattr(dm_module.requests, "post", MagicMock(return_value=fake_response), raising=True)

        button_states = {
            "start": {"disabled": False, "loading": False, "timestamp": 0},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
            "stop": {"disabled": False, "loading": False, "timestamp": 0},
            "resume": {"disabled": False, "loading": False, "timestamp": 0},
            "reset": {"disabled": False, "loading": False, "timestamp": 0},
        }
        action, new_states = dm._handle_training_buttons_handler(
            start_clicks=1,
            pause_clicks=None,
            stop_clicks=None,
            resume_clicks=None,
            reset_clicks=None,
            last_click={"button": None, "timestamp": 0},
            button_states=button_states,
        )
        assert action["last"] == "start-button"
        assert action["success"] is True
        assert new_states["start"]["loading"] is True
        dm_module.requests.post.assert_called_once()
        called_url = dm_module.requests.post.call_args[0][0]
        assert "/api/train/start" in called_url
