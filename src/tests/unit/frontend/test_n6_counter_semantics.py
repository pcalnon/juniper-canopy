"""N6 (training-runtime-defects plan §4 I-1c / §5 S12): header/tile counter-mapping
regression tests.

Pins canopy's rendered header, Network Info panel and metrics tiles onto the C2b
counter contract (juniper-cascor ``docs/api/JUNIPER_CASCOR_API_REFERENCE.md`` —
"Counter semantics (C2b)", reconciled by cascor#400):

- ``current_epoch`` / ``current_step`` -> "Step" (completed **training steps**),
  never an inner output-training epoch (the S12 "Epoch: 10000 vs 12" confusion).
- ``hidden_units`` / ``max_hidden_units`` -> "Hidden Units" with the reconciled
  denominator (pre-C2b the divergent surfaces showed a stale ``10000``).
- ``grow_iteration`` / ``grow_max`` -> the TRUE "Iteration", distinct from the
  hidden-unit count it was previously conflated with (S12 "Iteration: 0 / 10000").
- ``output_epoch`` / ``candidate_epoch`` -> the phase-qualified within-pass
  "Epoch"; the reset-to-0 at phase entry renders "0 / N (phase)", never a
  blank/regression.
- the "Training Step" tile honours the metrics-row ``kind`` discriminator so a
  within-pass ``output_epoch`` row cannot be shown as the step count, and a
  candidate-phase metrics freeze holds the last step value.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from frontend.components.metrics_panel import MetricsPanel  # noqa: E402
from frontend.dashboard_manager import DashboardManager  # noqa: E402


@pytest.fixture
def dashboard_manager():
    return DashboardManager({})


@pytest.fixture
def metrics_panel():
    return MetricsPanel({}, component_id="test-panel")


def _step_row(epoch, loss=0.1, acc=0.9, hidden=3, phase="output"):
    """A completed-training-step metrics row (C2b ``kind='training_step'``)."""
    return {"epoch": epoch, "kind": "training_step", "metrics": {"loss": loss, "accuracy": acc}, "network_topology": {"hidden_units": hidden}, "phase": phase}


def _output_epoch_row(inner_epoch, loss=0.2, acc=0.8, hidden=3):
    """A throttled within-pass sample (C2b ``kind='output_epoch'``) whose ``epoch``
    is the inner output epoch — must NOT be read as the completed-step count."""
    return {"epoch": inner_epoch, "kind": "output_epoch", "metrics": {"loss": loss, "accuracy": acc}, "network_topology": {"hidden_units": hidden}, "phase": "output"}


# =============================================================================
# _counter_displays — the single source of truth for the mappings
# =============================================================================
@pytest.mark.unit
class TestCounterDisplays:
    """DashboardManager._counter_displays maps the reconciled surface correctly."""

    def test_step_is_completed_training_steps(self):
        # current_epoch = 20 completed passes after 14 units — the monotonic step
        # count, NOT an inner epoch.
        d = DashboardManager._counter_displays({"current_epoch": 20, "hidden_units": 14})
        assert d["step"] == "20"

    def test_step_falls_back_to_current_step_alias(self):
        d = DashboardManager._counter_displays({"current_step": 12})
        assert d["step"] == "12"

    def test_step_defaults_to_zero_when_absent(self):
        assert DashboardManager._counter_displays({})["step"] == "0"

    def test_hidden_units_with_reconciled_denominator(self):
        d = DashboardManager._counter_displays({"hidden_units": 7, "max_hidden_units": 30})
        assert d["hidden_units"] == "7 / 30"

    def test_hidden_units_plain_count_without_max(self):
        d = DashboardManager._counter_displays({"hidden_units": 5})
        assert d["hidden_units"] == "5"

    def test_iteration_is_true_growth_iteration_not_hidden_units(self):
        # The S12 mislabel: "Iteration" must be grow_iteration/grow_max, NOT the
        # hidden-unit count. Here hidden_units=7 but the iteration is 3/28.
        d = DashboardManager._counter_displays({"hidden_units": 7, "max_hidden_units": 30, "grow_iteration": 3, "grow_max": 28})
        assert d["iteration"] == "3 / 28"
        assert d["iteration"] != d["hidden_units"]

    def test_iteration_plain_when_no_grow_max(self):
        assert DashboardManager._counter_displays({"grow_iteration": 4})["iteration"] == "4"

    def test_iteration_placeholder_when_absent(self):
        # Absent growth iteration renders the placeholder — it must NOT silently
        # fall back to the hidden-unit count (the pre-N6 behaviour).
        assert DashboardManager._counter_displays({"hidden_units": 9})["iteration"] == "—"

    def test_phase_epoch_output_phase(self):
        d = DashboardManager._counter_displays({"phase": "output", "output_epoch": 1200, "output_total_epochs": 2000})
        assert d["phase_epoch"] == "1200 / 2000 (output)"

    def test_phase_epoch_candidate_phase(self):
        d = DashboardManager._counter_displays({"phase": "candidate", "candidate_epoch": 45, "candidate_total_epochs": 100})
        assert d["phase_epoch"] == "45 / 100 (candidate)"

    def test_phase_epoch_reset_to_zero_renders_not_blank(self):
        # C2b: within-pass epoch is zeroed at phase entry BY DESIGN. "0 / N" must
        # render (the phase-reset case) — never a blank that reads as a regression.
        d = DashboardManager._counter_displays({"phase": "candidate", "candidate_epoch": 0, "candidate_total_epochs": 100})
        assert d["phase_epoch"] == "0 / 100 (candidate)"
        assert d["phase_epoch"] != "—"

    def test_phase_epoch_idle_is_placeholder(self):
        assert DashboardManager._counter_displays({"phase": "idle"})["phase_epoch"] == "—"

    def test_non_dict_status_is_safe(self):
        d = DashboardManager._counter_displays(None)
        assert d["step"] == "0" and d["iteration"] == "—" and d["phase_epoch"] == "—"


# =============================================================================
# Header status bar
# =============================================================================
@pytest.mark.unit
class TestStatusBarCounterMappings:
    """_build_unified_status_bar_content renders Step + Hidden Units correctly."""

    def _resp(self, **fields):
        base = {"is_running": True, "is_paused": False, "completed": False, "failed": False, "phase": "output"}
        base.update(fields)
        r = Mock()
        r.json.return_value = base
        return r

    def test_header_step_is_current_epoch(self, dashboard_manager):
        result = dashboard_manager._build_unified_status_bar_content(self._resp(current_epoch=42, hidden_units=3), latency_ms=50.0)
        # index 7 == the "Step" segment (top-epoch-display) — completed steps.
        assert result[7] == "42"

    def test_header_hidden_units_carries_reconciled_denominator(self, dashboard_manager):
        result = dashboard_manager._build_unified_status_bar_content(self._resp(current_epoch=42, hidden_units=7, max_hidden_units=30), latency_ms=50.0)
        # index 8 == the "Hidden Units" segment (top-hidden-units-display).
        assert result[8] == "7 / 30"

    def test_header_hidden_units_is_unit_count_not_iteration(self, dashboard_manager):
        # Even when a (different) growth iteration is present, the header's
        # hidden-units segment shows the unit count, not grow_iteration.
        result = dashboard_manager._build_unified_status_bar_content(self._resp(current_epoch=42, hidden_units=7, max_hidden_units=30, grow_iteration=3, grow_max=28), latency_ms=50.0)
        assert result[8] == "7 / 30"


# =============================================================================
# Network Info panel
# =============================================================================
@pytest.mark.unit
class TestNetworkInfoCounterMappings:
    """_update_network_info_handler renders Step / Iteration / Hidden Units / Epoch."""

    def _mock_status(self, mock_get, **fields):
        base = {
            "input_size": 2,
            "output_size": 2,
            "hidden_units": 7,
            "max_hidden_units": 30,
            "current_epoch": 12,
            "grow_iteration": 3,
            "grow_max": 28,
            "phase": "candidate",
            "candidate_epoch": 45,
            "candidate_total_epochs": 100,
            "network_connected": True,
            "monitoring_active": True,
        }
        base.update(fields)
        resp = Mock()
        resp.ok = True
        resp.status_code = 200
        resp.json.return_value = base
        mock_get.return_value = resp

    @patch("requests.get")
    def test_iteration_shows_growth_iteration_not_hidden_units(self, mock_get, dashboard_manager):
        self._mock_status(mock_get)
        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_network_info_handler(n=1)
        rendered = str(result)
        # The mislabel regression: "Iteration" carries grow_iteration/grow_max
        # (3 / 28), NOT the hidden-unit count (7).
        assert "Iteration: " in rendered
        assert "3 / 28" in rendered
        assert "Current Iteration" not in rendered  # the old mislabel is gone

    @patch("requests.get")
    def test_training_step_and_hidden_units_and_phase_epoch(self, mock_get, dashboard_manager):
        self._mock_status(mock_get)
        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_network_info_handler(n=1)
        rendered = str(result)
        assert "Training Step: " in rendered and "12" in rendered
        assert "Hidden Units: " in rendered and "7 / 30" in rendered
        # phase-qualified within-pass epoch ("Epoch 45 / 100 (candidate)").
        assert "Epoch (in phase): " in rendered and "45 / 100 (candidate)" in rendered


# =============================================================================
# Metrics "Training Step" tile — kind discriminator + candidate-phase freeze
# =============================================================================
@pytest.mark.unit
class TestMetricsTileKindDiscriminator:
    """_update_metrics_display_handler: the step tile honours C2b row ``kind``."""

    def test_output_epoch_row_does_not_corrupt_step_tile(self, metrics_panel):
        # Last row is a within-pass output_epoch sample numbered 10000; the step
        # tile must show the completed-step count (12), not 10000 (the S12 bug).
        rows = [_step_row(11), _step_row(12), _output_epoch_row(10000)]
        result = metrics_panel._update_metrics_display_handler(metrics_data=rows, theme="light")
        assert result[2] == "12"

    def test_candidate_phase_freeze_holds_last_step(self, metrics_panel):
        # During a candidate phase no new training_step rows arrive (metrics
        # freeze). The tile holds the last step value; a growing candidates_trained
        # in training_state does not blank or regress it.
        rows = [_step_row(12, phase="output")]
        ts = {"max_hidden_units": 30, "current_epoch": 12, "candidates_trained": 7, "candidates_total": 8}
        result = metrics_panel._update_metrics_display_handler(metrics_data=rows, theme="light", training_state=ts)
        assert result[2] == "12"

    def test_rows_without_kind_default_to_training_step(self, metrics_panel):
        # Back-compat: pre-C2b / demo rows carry no ``kind`` and use step numbering.
        rows = [{"epoch": 1, "metrics": {"loss": 0.5, "accuracy": 0.6}}, {"epoch": 2, "metrics": {"loss": 0.4, "accuracy": 0.7}}]
        result = metrics_panel._update_metrics_display_handler(metrics_data=rows, theme="light")
        assert result[2] == "2"

    def test_falls_back_to_training_state_when_only_output_rows(self, metrics_panel):
        # Only within-pass rows present -> use the authoritative completed-step
        # count from training_state, never the inner epoch.
        rows = [_output_epoch_row(9000)]
        ts = {"current_epoch": 5, "max_hidden_units": 30}
        result = metrics_panel._update_metrics_display_handler(metrics_data=rows, theme="light", training_state=ts)
        assert result[2] == "5"


# =============================================================================
# Service backend get_status — the reconciled surface reaches canopy
# =============================================================================
try:
    from backend.service_backend import ServiceBackend

    _HAS_SERVICE_BACKEND = True
except ImportError:
    _HAS_SERVICE_BACKEND = False


@pytest.mark.unit
@pytest.mark.skipif(not _HAS_SERVICE_BACKEND, reason="juniper-cascor-client not installed")
class TestServiceBackendCounterSurface:
    """ServiceBackend.get_status carries the C2b counter fields through."""

    def _backend(self, ts=None, monitor=None, sm=None):
        adapter = MagicMock()
        adapter.get_training_status.return_value = {
            "state_machine": sm or {"status": "Training", "phase": "candidate"},
            "monitor": monitor or {"current_epoch": 12, "current_hidden_units": 7, "total_metrics": 803},
            "training_state": ts
            or {
                "current_step": 12,
                "grow_iteration": 7,
                "grow_max": 28,
                "output_epoch": 0,
                "output_total_epochs": 2000,
                "candidate_epoch": 45,
                "candidate_total_epochs": 100,
                "max_hidden_units": 30,
                "max_epochs": 114000,
                "learning_rate": 0.01,
            },
            "training_active": True,
            "network_loaded": True,
        }
        return ServiceBackend(adapter)

    def test_get_status_surfaces_reconciled_counter_fields(self):
        status = self._backend().get_status()
        assert status["grow_iteration"] == 7
        assert status["grow_max"] == 28
        assert status["current_step"] == 12
        assert status["output_total_epochs"] == 2000
        assert status["candidate_epoch"] == 45
        assert status["candidate_total_epochs"] == 100
        # the C2b derived display budget is carried through unchanged
        assert status["max_epochs"] == 114000
        assert status["max_hidden_units"] == 30

    def test_get_status_missing_counter_fields_degrade_to_none(self):
        # A pre-C2b cascor without the granular counters -> None (the display
        # helper renders a graceful placeholder rather than raising).
        status = self._backend(ts={"max_hidden_units": 6, "max_epochs": 500}).get_status()
        assert status["grow_iteration"] is None
        assert status["candidate_epoch"] is None
