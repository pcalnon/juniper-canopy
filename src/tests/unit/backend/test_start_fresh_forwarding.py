"""N3 (canopy training-runtime defects plan, Q4 / cascor C5) — start_fresh wiring.

Covers the ``start_fresh`` toggle's path through every backend layer plus the
demo-FSM start-from-terminal fix (folded finding 1):

* ``CascorServiceAdapter.start_training_background`` posts the top-level
  ``start_fresh`` body field through the client transport when set (cascor#408),
  and keeps the plain ``start_training()`` call when not — the CL2 swap seam.
* ``ServiceBackend`` / ``DemoBackend`` forward / translate the flag.
* ``DemoMode.start(reset=False)`` from a COMPLETED run now starts instead of being
  silently refused (the demo FSM auto-resets from a terminal state, matching the
  cascor engine FSM).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from juniper_cascor_client.constants import ENDPOINT_TRAINING_START

from backend.cascor_service_adapter import CascorServiceAdapter
from backend.demo_backend import DemoBackend
from backend.service_backend import ServiceBackend
from backend.training_state_machine import Command
from demo_mode import DemoMode

# ---------------------------------------------------------------------------
# Adapter — the CL2 swap seam
# ---------------------------------------------------------------------------


class TestAdapterStartFreshTransport:
    def _adapter(self):
        return CascorServiceAdapter(service_url="http://test.local:8200", client=MagicMock())

    def test_start_fresh_true_posts_body_field(self):
        adapter = self._adapter()
        started, error = adapter.start_training_background(start_fresh=True)
        assert started is True
        assert error is None
        # cascor-client 0.7.0 start_training() can't carry start_fresh, so the
        # fresh path posts through the client transport (reusing auth/headers).
        adapter._client._post.assert_called_once_with(ENDPOINT_TRAINING_START, json={"start_fresh": True})
        adapter._client.start_training.assert_not_called()

    def test_start_fresh_false_uses_plain_start(self):
        adapter = self._adapter()
        started, error = adapter.start_training_background(start_fresh=False, epochs=5)
        assert started is True
        adapter._client.start_training.assert_called_once_with(epochs=5)
        adapter._client._post.assert_not_called()

    def test_start_fresh_failure_rides_back_as_message(self):
        from juniper_cascor_client import JuniperCascorClientError

        adapter = self._adapter()
        adapter._client._post.side_effect = JuniperCascorClientError("boom")
        started, error = adapter.start_training_background(start_fresh=True)
        assert started is False
        assert "boom" in error


# ---------------------------------------------------------------------------
# ServiceBackend / DemoBackend translation
# ---------------------------------------------------------------------------


class TestServiceBackendForwardsStartFresh:
    def _backend(self):
        adapter = MagicMock()
        adapter.is_training_in_progress.return_value = False
        adapter.network = object()  # not None → skip first-start staging
        adapter.start_training_background.return_value = (True, None)
        return ServiceBackend(adapter=adapter), adapter

    def test_forwards_start_fresh_true(self):
        backend, adapter = self._backend()
        result = backend.start_training(reset=True, start_fresh=True)
        assert result["ok"] is True
        assert adapter.start_training_background.call_args.kwargs["start_fresh"] is True

    def test_defaults_start_fresh_false(self):
        backend, adapter = self._backend()
        backend.start_training(reset=False)
        assert adapter.start_training_background.call_args.kwargs["start_fresh"] is False


class TestDemoBackendTranslatesStartFresh:
    def test_start_fresh_maps_to_reset(self):
        demo = MagicMock()
        DemoBackend(demo=demo).start_training(reset=False, start_fresh=True)
        demo.start.assert_called_once_with(reset=True)

    def test_continue_keeps_reset_false(self):
        demo = MagicMock()
        DemoBackend(demo=demo).start_training(reset=False, start_fresh=False)
        demo.start.assert_called_once_with(reset=False)


# ---------------------------------------------------------------------------
# Demo FSM — start-from-terminal (folded finding 1) end-to-end at DemoMode
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_demo_continue_from_completed_starts():
    """DemoMode.start(reset=False) from COMPLETED now starts (was silently refused).

    Pre-N3 the demo FSM had no COMPLETED branch, so a converged demo run could not
    be continued/restarted without a full reset — the asymmetry that turned
    canopy's CI UI leg red (§13 N2 addendum). The FSM now auto-resets from a
    terminal state, matching the cascor engine FSM.
    """
    demo = DemoMode(update_interval=0.1)
    try:
        demo.state_machine.handle_command(Command.START)
        demo.state_machine.mark_completed()
        assert demo.state_machine.is_completed()

        demo.start(reset=False)

        assert demo.state_machine.is_started()
        assert demo.is_running
    finally:
        demo.stop()
