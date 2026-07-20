#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_cascor_service_adapter_gate_coverage.py
# Author:        Paul Calnon
# License:       MIT License
# Description:   Per-file coverage-gate tests for backend.cascor_service_adapter
#####################################################################
"""Statement-coverage tests for ``CascorServiceAdapter`` and helpers.

The adapter dominates the ``src/backend`` sub-module coverage pool. This
suite drives the branches the existing ``test_cascor_service_adapter*``
files leave uncovered:

* ``_ServiceTrainingMonitor`` non-dict fallbacks.
* ``ControlStreamSupervisor.set_params`` + the auto-reconnect connect loop.
* Property accessors, the network TTL-cache hit, REST error envelopes.
* ``apply_params`` REST-error + verify-mismatch paths and
  ``_verify_apply_roundtrip`` float-coercion edge.
* Dataset staging / cancel / peek pass-throughs and their error arms.
* ``_coerce_scalar_target`` numeric branches and ``get_dataset_data``.
* Snapshot save/load/replay/resume/retrain error re-raises.
* The async metrics-relay loop (validation hook, seq-gap detection,
  ping/pong, cascade topology broadcast, state/candidate/event callback
  dispatch and their error arms, disconnect, OSError backoff) driven
  through a fake ``CascorTrainingStream``.

The relay loop and control-stream connect loop are genuinely async — they
are driven with fake streams so the real message-dispatch code executes
in-process (no live cascor service or WebSocket is contacted).
"""

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub-compatible: this suite mocks every juniper-cascor-client seam (the client
# instance, CascorTrainingStream / CascorControlStream are patched), so it runs
# under BOTH the real package and canopy's conftest test stub (which provides the
# client classes as MagicMocks and the exception classes as real Exception
# subclasses). It therefore does NOT skip on the stub — required so the per-file
# coverage gate can cover src/backend/cascor_service_adapter.py in CI, where only
# the stub client is installed (juniper-ml per-file rollout C-5, scoping §6:
# lift must be measured against the suite CI actually runs).
from juniper_cascor_client import JuniperCascorClientError  # noqa: E402
from juniper_cascor_client.exceptions import JuniperCascorConnectionError  # noqa: E402

from backend.cascor_service_adapter import (  # noqa: E402
    CascorServiceAdapter,
    ControlStreamSupervisor,
    _ServiceTrainingMonitor,
)

_CTS = "backend.cascor_service_adapter.CascorTrainingStream"
_CCS = "backend.cascor_service_adapter.CascorControlStream"
_WSM_TARGET = "communication.websocket_manager.websocket_manager"
_SETTINGS = "settings.get_settings"


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.is_alive.return_value = True
    client.get_training_status.return_value = {"is_training": False, "status": "idle"}
    client.get_network.return_value = {"input_size": 2, "output_size": 1}
    return client


@pytest.fixture
def adapter(mock_client):
    a = CascorServiceAdapter(service_url="http://localhost:8200")
    a._client = mock_client
    a.training_monitor = _ServiceTrainingMonitor(mock_client)
    return a


# =========================================================================
# _ServiceTrainingMonitor non-dict fallbacks
# =========================================================================


@pytest.mark.unit
class TestServiceTrainingMonitorFallbacks:
    def test_is_training_false_when_data_not_dict(self, mock_client):
        mock_client.get_training_status.return_value = {"data": "not-a-dict"}
        assert _ServiceTrainingMonitor(mock_client).is_training is False

    def test_current_metrics_returns_result_when_data_not_dict(self, mock_client):
        payload = {"data": "not-a-dict"}
        mock_client.get_metrics.return_value = payload
        assert _ServiceTrainingMonitor(mock_client).get_current_metrics() == payload

    def test_recent_metrics_returns_list_result(self, mock_client):
        mock_client.get_metrics_history.return_value = [{"epoch": 1}]
        assert _ServiceTrainingMonitor(mock_client).get_recent_metrics() == [{"epoch": 1}]

    def test_recent_metrics_empty_when_non_list(self, mock_client):
        mock_client.get_metrics_history.return_value = 42
        assert _ServiceTrainingMonitor(mock_client).get_recent_metrics() == []


# =========================================================================
# ControlStreamSupervisor
# =========================================================================


class _FakeControlStream:
    """Fake CascorControlStream with a truthy ``_ws`` so ``is_connected`` is True."""

    def __init__(self, *args, **kwargs):
        self._ws = object()
        self.connected = False
        self.disconnected = False

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.disconnected = True


@pytest.mark.unit
class TestControlStreamSupervisor:
    async def test_set_params_raises_when_not_connected(self):
        sup = ControlStreamSupervisor(ws_url="ws://localhost:8200")
        with pytest.raises(JuniperCascorConnectionError):
            await sup.set_params({"learning_rate": 0.1})

    async def test_set_params_delegates_to_stream(self):
        sup = ControlStreamSupervisor(ws_url="ws://localhost:8200")
        sup._stream = SimpleNamespace(_ws=object(), set_params=AsyncMock(return_value={"applied": {"learning_rate": 0.1}}))
        result = await sup.set_params({"learning_rate": 0.1}, timeout=0.5)
        assert result == {"applied": {"learning_rate": 0.1}}
        sup._stream.set_params.assert_awaited_once()

    async def test_set_params_coerces_non_dict_result_to_empty(self):
        sup = ControlStreamSupervisor(ws_url="ws://localhost:8200")
        sup._stream = SimpleNamespace(_ws=object(), set_params=AsyncMock(return_value="not-a-dict"))
        assert await sup.set_params({"learning_rate": 0.1}) == {}

    async def test_connect_loop_connects_and_stops(self):
        fake = _FakeControlStream()
        with patch(_CCS, return_value=fake):
            sup = ControlStreamSupervisor(ws_url="ws://localhost:8200", api_key=None, ws_origin="http://localhost:8050")
            await sup.start()
            await asyncio.sleep(0.05)
            assert sup.is_connected is True
            assert fake.connected is True
            await sup.stop()
        assert sup._shutdown is True
        assert fake.disconnected is True


# =========================================================================
# Properties, network TTL cache, simple REST error envelopes
# =========================================================================


@pytest.mark.unit
class TestPropertiesAndControlErrors:
    def test_service_url_property(self, adapter):
        assert adapter.service_url == "http://localhost:8200"

    def test_client_property(self, adapter, mock_client):
        assert adapter.client is mock_client

    def test_network_property_serves_cached_value(self, adapter, mock_client):
        mock_client.get_network.return_value = {"input_size": 2}
        first = adapter.network
        assert first is not None
        # A second access within the 30s TTL must NOT re-query the client.
        mock_client.get_network.return_value = {"error": "gone"}
        second = adapter.network
        assert second is first
        assert mock_client.get_network.call_count == 1

    def test_is_training_in_progress_false_when_data_not_dict(self, adapter, mock_client):
        mock_client.get_training_status.return_value = {"data": "nope"}
        assert adapter.is_training_in_progress() is False

    def test_resume_training_error_envelope(self, adapter, mock_client):
        mock_client.resume_training.side_effect = JuniperCascorClientError("resume boom")
        assert adapter.resume_training() == {"ok": False, "error": "resume boom"}

    def test_reset_training_error_envelope(self, adapter, mock_client):
        mock_client.reset_training.side_effect = JuniperCascorClientError("reset boom")
        assert adapter.reset_training() == {"ok": False, "error": "reset boom"}


# =========================================================================
# apply_params REST + verify roundtrip
# =========================================================================


def _settings_no_ws():
    return patch(_SETTINGS, return_value=SimpleNamespace(use_websocket_set_params=False))


@pytest.mark.unit
class TestApplyParamsRestAndVerify:
    def test_rest_error_returns_error_envelope(self, adapter, mock_client):
        mock_client.update_params.side_effect = JuniperCascorClientError("patch failed")
        with _settings_no_ws():
            result = adapter.apply_params(nn_learning_rate=0.1)
        assert result["ok"] is False
        assert "patch failed" in result["error"]

    def test_verify_mismatch_returns_verification_failed(self, adapter, mock_client):
        mock_client.update_params.return_value = {}
        mock_client.get_training_params.return_value = {"data": {"learning_rate": 0.9}}
        with _settings_no_ws():
            result = adapter.apply_params(nn_learning_rate=0.1)
        assert result["ok"] is False
        assert result["error"] == "verification_failed"
        assert "learning_rate" in result["mismatches"]

    def test_verify_call_failure_is_non_fatal(self, adapter, mock_client):
        mock_client.update_params.return_value = {"learning_rate": 0.1}
        mock_client.get_training_params.side_effect = JuniperCascorClientError("get failed")
        with _settings_no_ws():
            result = adapter.apply_params(nn_learning_rate=0.1)
        assert result["ok"] is True

    def test_verify_roundtrip_float_coercion_fallback(self, adapter, mock_client):
        # A float-tolerant param whose reported value cannot be coerced falls
        # through to the strict comparison and is flagged as a mismatch.
        mock_client.get_training_params.return_value = {"data": {"learning_rate": "unparseable"}}
        result = adapter._verify_apply_roundtrip({"learning_rate": 0.1})
        assert result is not None
        assert "learning_rate" in result


# =========================================================================
# Dataset staging pass-throughs (POST/DELETE/GET via client._request)
# =========================================================================


@pytest.mark.unit
class TestDatasetStaging:
    def test_stage_dataset_success(self, adapter, mock_client):
        mock_client._request.return_value = {"data": {"staged": True}}
        result = adapter.stage_dataset(nn_dataset_type="xor", nn_dataset_elements=100)
        assert result["ok"] is True
        assert result["data"] == {"staged": True}
        assert result["config"] == {"dataset_type": "xor", "n_samples": 100}
        mock_client._request.assert_called_once_with("POST", "/training/dataset", json={"dataset_type": "xor", "n_samples": 100})

    def test_stage_dataset_error(self, adapter, mock_client):
        mock_client._request.side_effect = JuniperCascorClientError("stage boom")
        assert adapter.stage_dataset(nn_dataset_type="xor") == {"ok": False, "error": "stage boom"}

    def test_cancel_pending_dataset_success(self, adapter, mock_client):
        mock_client._request.return_value = {"data": {"cancelled": True}}
        assert adapter.cancel_pending_dataset() == {"ok": True, "data": {"cancelled": True}}

    def test_cancel_pending_dataset_error(self, adapter, mock_client):
        mock_client._request.side_effect = JuniperCascorClientError("cancel boom")
        assert adapter.cancel_pending_dataset() == {"ok": False, "error": "cancel boom"}

    def test_get_pending_dataset_success(self, adapter, mock_client):
        mock_client._request.return_value = {"data": {"pending": {"dataset_type": "xor"}}}
        assert adapter.get_pending_dataset() == {"ok": True, "pending": {"dataset_type": "xor"}}

    def test_get_pending_dataset_error(self, adapter, mock_client):
        mock_client._request.side_effect = JuniperCascorClientError("pending boom")
        assert adapter.get_pending_dataset() == {"ok": False, "error": "pending boom", "pending": None}


# =========================================================================
# _coerce_scalar_target + get_dataset_data
# =========================================================================


@pytest.mark.unit
class TestScalarTargetAndDatasetData:
    def test_coerce_scalar_target_branches(self):
        f = CascorServiceAdapter._coerce_scalar_target
        assert f(None) == 0  # TypeError → 0
        assert f("nan-ish") == 0  # ValueError → 0
        assert f(3.0) == 3  # integer-valued
        assert f(0.7) == 1  # in [0,1] → threshold high
        assert f(0.2) == 0  # in [0,1] → threshold low
        assert f(2.3) == 2  # >1 → round
        assert f(-1.4) == -1  # <0 → round

    def test_get_dataset_data_missing_client_method(self, adapter):
        client = MagicMock()
        del client.get_dataset_data
        adapter._client = client
        assert adapter.get_dataset_data() is None

    def test_get_dataset_data_empty_result(self, adapter, mock_client):
        mock_client.get_dataset_data.return_value = {}
        assert adapter.get_dataset_data() is None

    def test_get_dataset_data_multiclass_with_empty_row(self, adapter, mock_client):
        mock_client.get_dataset_data.return_value = {"data": {"train_x": [[0, 0], [1, 1]], "train_y": [[0.1, 0.9], []]}}
        result = adapter.get_dataset_data()
        assert result["inputs"] == [[0, 0], [1, 1]]
        # argmax([0.1, 0.9]) == 1 ; empty row falls back to class 0
        assert result["targets"] == [1, 0]


# =========================================================================
# Topology non-dict fallbacks
# =========================================================================


@pytest.mark.unit
class TestTopologyFallbacks:
    def test_extract_topology_returns_none_for_non_dict(self, adapter, mock_client):
        mock_client.get_topology.return_value = None
        assert adapter.extract_network_topology() is None

    def test_raw_topology_returns_dict(self, adapter, mock_client):
        mock_client.get_topology.return_value = {"data": {"input_size": 2, "hidden_units": []}}
        assert adapter.get_raw_topology() == {"input_size": 2, "hidden_units": []}

    def test_raw_topology_none_for_non_dict(self, adapter, mock_client):
        mock_client.get_topology.return_value = None
        assert adapter.get_raw_topology() is None


# =========================================================================
# Snapshot delegation error re-raises
# =========================================================================


@pytest.mark.unit
class TestSnapshotDelegation:
    def test_save_snapshot_success(self, adapter, mock_client):
        mock_client.save_snapshot.return_value = None
        adapter.save_snapshot("/tmp/x.snap", description="checkpoint")
        mock_client.save_snapshot.assert_called_once_with(description="checkpoint")

    def test_save_snapshot_error_reraises(self, adapter, mock_client):
        mock_client.save_snapshot.side_effect = JuniperCascorClientError("save boom")
        with pytest.raises(JuniperCascorClientError):
            adapter.save_snapshot("/tmp/x.snap")

    def test_load_snapshot_success_uses_stem(self, adapter, mock_client):
        mock_client.load_snapshot.return_value = None
        adapter.load_snapshot("/tmp/snap-123.snap")
        mock_client.load_snapshot.assert_called_once_with("snap-123")

    def test_load_snapshot_error_reraises(self, adapter, mock_client):
        mock_client.load_snapshot.side_effect = JuniperCascorClientError("load boom")
        with pytest.raises(JuniperCascorClientError):
            adapter.load_snapshot("/tmp/snap-9.snap")

    def test_replay_control_error_reraises(self, adapter, mock_client):
        mock_client._post.side_effect = JuniperCascorClientError("ctrl boom")
        with pytest.raises(JuniperCascorClientError):
            adapter.replay_control("snap-1", "play")

    def test_resume_snapshot_error_reraises(self, adapter, mock_client):
        mock_client._post.side_effect = JuniperCascorClientError("resume boom")
        with pytest.raises(JuniperCascorClientError):
            adapter.resume_snapshot("snap-1")

    def test_retrain_snapshot_error_reraises(self, adapter, mock_client):
        mock_client._post.side_effect = JuniperCascorClientError("retrain boom")
        with pytest.raises(JuniperCascorClientError):
            adapter.retrain_snapshot("snap-1")


# =========================================================================
# Metrics-relay loop — driven with a fake CascorTrainingStream
# =========================================================================


class _FakeStream:
    """Fake CascorTrainingStream: yields controlled messages then stops.

    ``connect_exc`` raised from ``connect()`` drives the reconnect/backoff
    branches; ``block`` makes ``connect()`` hang so the relay task can be
    cancelled externally.
    """

    def __init__(self, messages=None, connect_exc=None, block=False, ws=None):
        self.messages = messages or []
        self.connect_exc = connect_exc
        self.block = block
        self._ws = ws
        self.disconnected = False

    async def connect(self):
        if self.block:
            await asyncio.sleep(30)
        if self.connect_exc is not None:
            raise self.connect_exc

    async def disconnect(self):
        self.disconnected = True

    async def stream(self):
        for message in self.messages:
            yield message


class _WSM:
    """Fake websocket_manager recording broadcast payloads."""

    def __init__(self, raise_on_topology=False):
        self.payloads = []
        self._raise_on_topology = raise_on_topology

    async def broadcast(self, payload):
        self.payloads.append(payload)
        if self._raise_on_topology and isinstance(payload, dict) and payload.get("type") == "topology":
            raise RuntimeError("topology broadcast boom")


def _stream_factory(*streams):
    queue = list(streams)

    def _make(*args, **kwargs):
        return queue.pop(0)

    return _make


async def _drive_relay(adapter, streams, wsm=None):
    """Run the relay loop to natural completion with the given fake streams."""
    wsm = wsm or _WSM()
    with patch(_CTS, _stream_factory(*streams)), patch(_WSM_TARGET, wsm), patch(_SETTINGS, return_value=SimpleNamespace(use_websocket_set_params=False)):
        await adapter.start_metrics_relay()
        await asyncio.wait_for(adapter._relay_task, timeout=5)
    return wsm


def _cancel_stream():
    """A stream whose connect raises CancelledError so the relay loop exits."""
    return _FakeStream(connect_exc=asyncio.CancelledError())


@pytest.mark.unit
class TestMetricsRelayLoop:
    async def test_happy_path_metrics_and_event(self, adapter):
        callback = MagicMock()
        adapter.set_state_update_callback(callback)
        messages = [
            {"type": "metrics", "data": {"epoch": 1, "loss": 0.5, "accuracy": 0.8}, "seq": 1},
            {"type": "event", "data": {"event": "training_complete"}},
        ]
        first = _FakeStream(messages=messages)
        wsm = await _drive_relay(adapter, [first, _cancel_stream()])

        # First stream drained → disconnect() was called before reconnect.
        assert first.disconnected is True
        # Every non-ping frame is broadcast.
        assert any(p.get("type") == "metrics" for p in wsm.payloads)
        assert any(p.get("type") == "event" for p in wsm.payloads)
        # training_complete drove a Completed state update.
        callback.assert_any_call(status="Completed", phase="Idle")

    async def test_ping_frame_is_not_manually_ponged(self, adapter):
        # CL2 (training-runtime defects plan §7): the relay's manual heartbeat-pong
        # workaround is retired — cascor-client >=0.7.0 auto-pongs and consumes
        # ``ping`` frames at the transport layer, so a ping never reaches the relay
        # and, were one to, the relay no longer reaches into ``stream._ws`` to
        # answer it. (That the client itself consumes pings is pinned in
        # test_stream_liveness.py::TestPongRetirement.)
        pong_ws = SimpleNamespace(send=AsyncMock())
        first = _FakeStream(messages=[{"type": "ping"}], ws=pong_ws)
        await _drive_relay(adapter, [first, _cancel_stream()])
        pong_ws.send.assert_not_awaited()  # manual pong retired in CL2

    async def test_cascade_add_broadcasts_topology_and_survives_error(self, adapter):
        adapter.extract_network_topology = MagicMock(return_value={"nodes": ["n0"]})
        wsm = _WSM(raise_on_topology=True)
        first = _FakeStream(messages=[{"type": "cascade_add"}])
        await _drive_relay(adapter, [first, _cancel_stream()], wsm=wsm)

        adapter.extract_network_topology.assert_called()
        # Both the cascade_add frame and the follow-up topology frame were attempted.
        assert any(p.get("type") == "cascade_add" for p in wsm.payloads)
        assert any(p.get("type") == "topology" for p in wsm.payloads)

    async def test_state_candidate_event_callback_errors_are_swallowed(self, adapter):
        def _boom(**kwargs):
            raise RuntimeError("callback boom")

        adapter.set_state_update_callback(_boom)
        messages = [
            {"type": "state", "data": {"status": "training", "phase": "output"}},
            {"type": "candidate_progress", "data": {"epoch": 1, "total_epochs": 10, "correlation": 0.5}},
            {"type": "event", "data": {"event": "training_complete"}},
        ]
        first = _FakeStream(messages=messages)
        wsm = await _drive_relay(adapter, [first, _cancel_stream()])
        # Loop survived all three raising callbacks and drained the stream.
        assert first.disconnected is True
        assert len(wsm.payloads) == 3

    async def test_validation_hook_error_is_swallowed(self, adapter):
        first = _FakeStream(messages=[{"type": "metrics", "data": {"loss": 0.1}, "seq": 1}])
        with patch("juniper_cascor_protocol.envelope.validate_envelope", side_effect=RuntimeError("validate boom")):
            wsm = await _drive_relay(adapter, [first, _cancel_stream()])
        # Frame still dispatched despite the validation hook raising.
        assert any(p.get("type") == "metrics" for p in wsm.payloads)

    async def test_seq_gap_detection_and_hook_error(self, adapter):
        messages = [
            {"type": "metrics", "data": {}, "seq": 1},
            {"type": "metrics", "data": {}, "seq": 5},  # gap: 5 != 1 + 1
        ]
        first = _FakeStream(messages=messages)
        with patch("observability.inc_ws_seq_gap_detected", side_effect=RuntimeError("gap hook boom")) as gap:
            await _drive_relay(adapter, [first, _cancel_stream()])
        # The gap branch fired (and its error was swallowed).
        gap.assert_called_once_with("training")

    async def test_oserror_triggers_backoff_then_cancel(self, adapter):
        first = _FakeStream(connect_exc=OSError("connection reset"))
        with patch(_CTS, _stream_factory(first, _FakeStream(block=True))), patch(_WSM_TARGET, _WSM()), patch(_SETTINGS, return_value=SimpleNamespace(use_websocket_set_params=False)):
            await adapter.start_metrics_relay()
            # Let the loop hit the OSError handler and enter its backoff sleep.
            await asyncio.sleep(0.1)
            adapter._relay_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await adapter._relay_task
        assert adapter._relay_task is not None  # not yet nulled (stop_metrics_relay not called)

    async def test_stop_metrics_relay_cancels_running_task(self, adapter):
        blocking = _FakeStream(block=True)
        with patch(_CTS, _stream_factory(blocking, _FakeStream(block=True))), patch(_WSM_TARGET, _WSM()), patch(_SETTINGS, return_value=SimpleNamespace(use_websocket_set_params=False)):
            await adapter.start_metrics_relay()
            await asyncio.sleep(0.05)
            assert adapter._relay_task is not None
            assert not adapter._relay_task.done()
            await adapter.stop_metrics_relay()
        assert adapter._relay_task is None


# =========================================================================
# _ServiceTrainingMonitor — remaining is_training / metrics branches
# =========================================================================


@pytest.mark.unit
class TestServiceTrainingMonitorMore:
    def test_is_training_true_from_top_level_flag(self, mock_client):
        mock_client.get_training_status.return_value = {"is_training": True}
        assert _ServiceTrainingMonitor(mock_client).is_training is True

    def test_is_training_true_from_nested_training_active(self, mock_client):
        mock_client.get_training_status.return_value = {"data": {"training_active": True}}
        assert _ServiceTrainingMonitor(mock_client).is_training is True

    def test_is_training_false_on_client_exception(self, mock_client):
        mock_client.get_training_status.side_effect = RuntimeError("down")
        assert _ServiceTrainingMonitor(mock_client).is_training is False

    def test_current_metrics_normalizes_dict_data(self, mock_client):
        mock_client.get_metrics.return_value = {"data": {"epoch": 3, "loss": 0.5, "accuracy": 0.9}}
        result = _ServiceTrainingMonitor(mock_client).get_current_metrics()
        # Normalized + dashboard-shaped: nested metrics + network_topology.
        assert result["epoch"] == 3
        assert result["metrics"]["loss"] == 0.5
        assert result["metrics"]["accuracy"] == 0.9

    def test_current_metrics_returns_empty_for_non_dict_result(self, mock_client):
        mock_client.get_metrics.return_value = "not-a-dict"
        assert _ServiceTrainingMonitor(mock_client).get_current_metrics() == {}

    def test_current_metrics_returns_dict_without_data_key(self, mock_client):
        mock_client.get_metrics.return_value = {"no_data_here": 1}
        assert _ServiceTrainingMonitor(mock_client).get_current_metrics() == {"no_data_here": 1}

    def test_current_metrics_empty_on_exception(self, mock_client):
        mock_client.get_metrics.side_effect = RuntimeError("boom")
        assert _ServiceTrainingMonitor(mock_client).get_current_metrics() == {}

    def test_recent_metrics_from_data_list(self, mock_client):
        mock_client.get_metrics_history.return_value = {"data": [{"epoch": 1, "loss": 0.2}]}
        result = _ServiceTrainingMonitor(mock_client).get_recent_metrics()
        assert isinstance(result, list) and len(result) == 1
        assert result[0]["epoch"] == 1
        assert result[0]["metrics"]["loss"] == 0.2

    def test_recent_metrics_from_data_history(self, mock_client):
        mock_client.get_metrics_history.return_value = {"data": {"history": [{"epoch": 2, "loss": 0.3}]}}
        result = _ServiceTrainingMonitor(mock_client).get_recent_metrics()
        assert isinstance(result, list) and len(result) == 1
        assert result[0]["epoch"] == 2

    def test_recent_metrics_empty_on_exception(self, mock_client):
        mock_client.get_metrics_history.side_effect = RuntimeError("boom")
        assert _ServiceTrainingMonitor(mock_client).get_recent_metrics() == []


# =========================================================================
# _NetworkSentinel + connect / attach lifecycle
# =========================================================================


@pytest.mark.unit
class TestConnectAndAttach:
    def test_network_sentinel_truthy_and_repr(self):
        from backend.cascor_service_adapter import _NetworkSentinel

        sentinel = _NetworkSentinel()
        assert bool(sentinel) is True
        assert "RemoteNetwork" in repr(sentinel)

    async def test_connect_success(self, adapter, mock_client):
        mock_client.is_alive.return_value = True
        assert await adapter.connect() is True

    async def test_connect_failure_returns_false(self, adapter, mock_client):
        mock_client.is_alive.side_effect = RuntimeError("unreachable")
        assert await adapter.connect() is False

    def test_attach_to_existing_success(self, adapter, mock_client):
        mock_client.get_network.return_value = {"input_size": 2, "output_size": 1}
        assert adapter.attach_to_existing() is True
        assert adapter._attached_to_existing is True

    def test_attach_to_existing_no_network(self, adapter, mock_client):
        mock_client.get_network.return_value = {"error": "no network"}
        assert adapter.attach_to_existing() is False
        assert adapter._attached_to_existing is False

    def test_attach_to_existing_exception(self, adapter, mock_client):
        mock_client.get_network.side_effect = RuntimeError("boom")
        assert adapter.attach_to_existing() is False
        assert adapter._attached_to_existing is False


# =========================================================================
# network property miss/error + _training_stop_requested
# =========================================================================


@pytest.mark.unit
class TestNetworkPropertyMissAndStopFlag:
    def test_network_property_none_on_error_result(self, adapter, mock_client):
        mock_client.get_network.return_value = {"error": "gone"}
        assert adapter.network is None
        assert adapter._network_cache is None

    def test_network_property_none_on_exception(self, adapter, mock_client):
        mock_client.get_network.side_effect = RuntimeError("boom")
        assert adapter.network is None
        assert adapter._network_cache is None

    def test_training_stop_requested_is_false(self, adapter):
        assert adapter._training_stop_requested is False


# =========================================================================
# Network creation + training-control success/error envelopes
# =========================================================================


@pytest.mark.unit
class TestNetworkAndTrainingControl:
    def test_create_network_success(self, adapter, mock_client):
        mock_client.create_network.return_value = {"created": True}
        assert adapter.create_network({"input_size": 2}) == {"created": True}
        mock_client.create_network.assert_called_once_with(input_size=2)

    def test_create_network_error(self, adapter, mock_client):
        mock_client.create_network.side_effect = JuniperCascorClientError("create boom")
        assert adapter.create_network() == {"error": "create boom"}

    def test_start_training_background_success(self, adapter, mock_client):
        mock_client.start_training.return_value = None
        assert adapter.start_training_background(epochs=5) == (True, None)
        mock_client.start_training.assert_called_once_with(epochs=5)

    def test_start_training_background_error(self, adapter, mock_client):
        # PR-B2: the failure detail rides back alongside the flag.
        mock_client.start_training.side_effect = JuniperCascorClientError("start boom")
        started, error = adapter.start_training_background()
        assert started is False
        assert "start boom" in error

    def test_is_training_in_progress_true_top_flag(self, adapter, mock_client):
        mock_client.get_training_status.return_value = {"is_training": True}
        assert adapter.is_training_in_progress() is True

    def test_is_training_in_progress_true_nested(self, adapter, mock_client):
        mock_client.get_training_status.return_value = {"data": {"training_active": True}}
        assert adapter.is_training_in_progress() is True

    def test_is_training_in_progress_error(self, adapter, mock_client):
        mock_client.get_training_status.side_effect = JuniperCascorClientError("status boom")
        assert adapter.is_training_in_progress() is False

    def test_request_training_stop_success(self, adapter, mock_client):
        mock_client.stop_training.return_value = None
        assert adapter.request_training_stop() is True

    def test_request_training_stop_error(self, adapter, mock_client):
        mock_client.stop_training.side_effect = JuniperCascorClientError("stop boom")
        assert adapter.request_training_stop() is False

    def test_pause_training_success(self, adapter, mock_client):
        mock_client.pause_training.return_value = {"paused": True}
        assert adapter.pause_training() == {"ok": True, "data": {"paused": True}}

    def test_pause_training_error(self, adapter, mock_client):
        mock_client.pause_training.side_effect = JuniperCascorClientError("pause boom")
        assert adapter.pause_training() == {"ok": False, "error": "pause boom"}

    def test_resume_training_success(self, adapter, mock_client):
        mock_client.resume_training.return_value = {"resumed": True}
        assert adapter.resume_training() == {"ok": True, "data": {"resumed": True}}

    def test_reset_training_success_clears_attach_flag(self, adapter, mock_client):
        adapter._attached_to_existing = True
        mock_client.reset_training.return_value = {"reset": True}
        assert adapter.reset_training() == {"ok": True, "data": {"reset": True}}
        assert adapter._attached_to_existing is False


# =========================================================================
# apply_params — skipped-warn, no-mappable short-circuit, unclassified,
# and the WS hot path (both fallback arms)
# =========================================================================


@pytest.mark.unit
class TestApplyParamsMoreBranches:
    def test_skipped_unmapped_key_is_warned_and_reported(self, adapter, mock_client):
        mock_client.update_params.return_value = {}
        mock_client.get_training_params.return_value = {}
        with _settings_no_ws():
            result = adapter.apply_params(nn_learning_rate=0.1, totally_bogus_key=7)
        assert result["ok"] is True
        assert "totally_bogus_key" in result["skipped"]

    def test_no_mappable_params_short_circuits(self, adapter, mock_client):
        # A canopy-local param maps to nothing on cascor and is NOT reported skipped.
        # N5 (I-4/T3): the early-return shape additionally carries the always-present
        # C2a ``applied`` / ``skipped_detail`` partition (empty — no cascor call).
        with _settings_no_ws():
            result = adapter.apply_params(nn_spiral_rotations=3)
        assert result == {"ok": True, "data": {}, "skipped": [], "applied": [], "skipped_detail": [], "message": "No cascor-mappable params provided"}
        mock_client.update_params.assert_not_called()

    def test_unclassified_param_defaults_to_rest(self, adapter, mock_client):
        mock_client.update_params.return_value = {"totally_unclassified": 5}
        mock_client.get_training_params.return_value = {}
        extended_map = {**CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP, "nn_fake": "totally_unclassified"}
        with patch.object(CascorServiceAdapter, "_CANOPY_TO_CASCOR_PARAM_MAP", extended_map), _settings_no_ws():
            result = adapter.apply_params(nn_fake=5)
        assert result["ok"] is True
        mock_client.update_params.assert_called_once_with({"totally_unclassified": 5})

    def test_ws_hot_path_success_merges_result(self, adapter, mock_client):
        adapter._apply_params_hot = MagicMock(return_value={"learning_rate": 0.1})
        mock_client.get_training_params.return_value = {"data": {"learning_rate": 0.1}}
        with patch(_SETTINGS, return_value=SimpleNamespace(use_websocket_set_params=True)):
            result = adapter.apply_params(nn_learning_rate=0.1)
        assert result["ok"] is True
        assert result["data"] == {"learning_rate": 0.1}
        adapter._apply_params_hot.assert_called_once()
        # Hot path succeeded → no REST PATCH for the hot param.
        mock_client.update_params.assert_not_called()

    def test_ws_hot_path_failure_falls_back_to_rest(self, adapter, mock_client):
        adapter._apply_params_hot = MagicMock(return_value=None)
        mock_client.update_params.return_value = {}
        mock_client.get_training_params.return_value = {}
        with patch(_SETTINGS, return_value=SimpleNamespace(use_websocket_set_params=True)):
            result = adapter.apply_params(nn_learning_rate=0.1)
        assert result["ok"] is True
        # WS failed → hot param routed through REST as a cold fallback.
        mock_client.update_params.assert_called_once_with({"learning_rate": 0.1})


# =========================================================================
# _verify_apply_roundtrip — non-dict applied, absent key, float match
# =========================================================================


@pytest.mark.unit
class TestVerifyRoundtripEdges:
    def test_verify_returns_none_when_applied_not_dict(self, adapter, mock_client):
        mock_client.get_training_params.return_value = {"data": "not-a-dict"}
        assert adapter._verify_apply_roundtrip({"learning_rate": 0.1}) is None

    def test_verify_skips_key_absent_from_applied(self, adapter, mock_client):
        mock_client.get_training_params.return_value = {"data": {"other": 1}}
        assert adapter._verify_apply_roundtrip({"learning_rate": 0.1}) is None

    def test_verify_float_tolerant_match_is_not_a_mismatch(self, adapter, mock_client):
        mock_client.get_training_params.return_value = {"data": {"learning_rate": 0.1}}
        assert adapter._verify_apply_roundtrip({"learning_rate": 0.1}) is None

    def test_verify_strict_mismatch_for_non_float_param(self, adapter, mock_client):
        mock_client.get_training_params.return_value = {"data": {"max_hidden_units": 9}}
        result = adapter._verify_apply_roundtrip({"max_hidden_units": 3})
        assert result == {"max_hidden_units": {"requested": 3, "applied": 9}}


# =========================================================================
# Experimental-functions gate (GET/POST via client._request)
# =========================================================================


@pytest.mark.unit
class TestExperimentalFunctions:
    def test_get_experimental_functions_success(self, adapter, mock_client):
        mock_client._request.return_value = {"data": {"enabled": True}}
        assert adapter.get_experimental_functions() == {"ok": True, "enabled": True}

    def test_get_experimental_functions_error(self, adapter, mock_client):
        mock_client._request.side_effect = JuniperCascorClientError("gate boom")
        assert adapter.get_experimental_functions() == {"ok": False, "error": "gate boom", "enabled": False}

    def test_set_experimental_functions_success(self, adapter, mock_client):
        mock_client._request.return_value = {"data": {"experimental_functions_enabled": True}}
        assert adapter.set_experimental_functions(True) == {"ok": True, "enabled": True}
        mock_client._request.assert_called_once_with("POST", "/admin/experimental_functions", json={"enabled": True})

    def test_set_experimental_functions_error(self, adapter, mock_client):
        mock_client._request.side_effect = JuniperCascorClientError("set boom")
        assert adapter.set_experimental_functions(False) == {"ok": False, "error": "set boom", "enabled": False}


# =========================================================================
# Live dataset swap + dataset-swap event feeds
# =========================================================================


@pytest.mark.unit
class TestLiveSwapAndSwapEvents:
    def test_swap_dataset_live_success(self, adapter, mock_client):
        mock_client._request.return_value = {"data": {"status": "swapped"}}
        result = adapter.swap_dataset_live(nn_dataset_type="xor", nn_dataset_elements=200)
        assert result["ok"] is True
        assert result["data"] == {"status": "swapped"}
        assert result["config"] == {"dataset_type": "xor", "n_samples": 200}

    def test_swap_dataset_live_error(self, adapter, mock_client):
        mock_client._request.side_effect = JuniperCascorClientError("swap boom")
        assert adapter.swap_dataset_live(nn_dataset_type="xor") == {"ok": False, "error": "swap boom"}

    def test_cancel_swap_dataset_live_success(self, adapter, mock_client):
        mock_client._request.return_value = {"data": {"status": "cancelled"}}
        assert adapter.cancel_swap_dataset_live() == {"ok": True, "data": {"status": "cancelled"}}

    def test_cancel_swap_dataset_live_error(self, adapter, mock_client):
        mock_client._request.side_effect = JuniperCascorClientError("cancel boom")
        assert adapter.cancel_swap_dataset_live() == {"ok": False, "error": "cancel boom"}

    def test_get_dataset_swap_events_success_no_since(self, adapter, mock_client):
        mock_client._request.return_value = {"data": {"events": [{"timestamp": "t0"}]}}
        assert adapter.get_dataset_swap_events() == {"ok": True, "events": [{"timestamp": "t0"}]}
        mock_client._request.assert_called_once_with("GET", "/history/dataset_swaps", params=None)

    def test_get_dataset_swap_events_success_with_since(self, adapter, mock_client):
        mock_client._request.return_value = {"data": {"events": []}}
        assert adapter.get_dataset_swap_events(since="2026-07-04") == {"ok": True, "events": []}
        mock_client._request.assert_called_once_with("GET", "/history/dataset_swaps", params={"since": "2026-07-04"})

    def test_get_dataset_swap_events_error(self, adapter, mock_client):
        mock_client._request.side_effect = JuniperCascorClientError("events boom")
        assert adapter.get_dataset_swap_events() == {"ok": False, "error": "events boom", "events": []}

    def test_get_snapshot_dataset_swaps_success(self, adapter, mock_client):
        mock_client._request.return_value = {"data": {"events": [{"timestamp": "t1"}]}}
        assert adapter.get_snapshot_dataset_swaps("snap-1") == {"ok": True, "events": [{"timestamp": "t1"}]}
        mock_client._request.assert_called_once_with("GET", "/snapshots/snap-1/history/dataset_swaps")

    def test_get_snapshot_dataset_swaps_error(self, adapter, mock_client):
        mock_client._request.side_effect = JuniperCascorClientError("snap boom")
        assert adapter.get_snapshot_dataset_swaps("snap-1") == {"ok": False, "error": "snap boom", "events": []}


# =========================================================================
# _apply_params_hot — not-connected guard + connected success (bg loop)
# =========================================================================


@pytest.mark.unit
class TestApplyParamsHot:
    def test_returns_none_when_supervisor_not_connected(self, adapter):
        # A freshly-built supervisor has no stream → is_connected is False.
        assert adapter._apply_params_hot({"learning_rate": 0.1}) is None

    def test_connected_success_routes_over_ws(self, adapter):
        import threading

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        try:
            supervisor = SimpleNamespace(
                is_connected=True,
                loop=loop,
                set_params=AsyncMock(return_value={"applied": {"learning_rate": 0.1}}),
            )
            adapter._control_supervisor = supervisor
            with patch(_SETTINGS, return_value=SimpleNamespace(ws_set_params_timeout=1.0)):
                result = adapter._apply_params_hot({"learning_rate": 0.1})
            assert result == {"applied": {"learning_rate": 0.1}}
            supervisor.set_params.assert_awaited_once()
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=2)
            loop.close()

    def test_connected_failure_returns_none(self, adapter):
        import threading

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        try:
            supervisor = SimpleNamespace(
                is_connected=True,
                loop=loop,
                set_params=AsyncMock(side_effect=RuntimeError("ws down")),
            )
            adapter._control_supervisor = supervisor
            with patch(_SETTINGS, return_value=SimpleNamespace(ws_set_params_timeout=0.2)):
                result = adapter._apply_params_hot({"learning_rate": 0.1})
            assert result is None
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=2)
            loop.close()


# =========================================================================
# get_canopy_params — nested params, flat fallback, error
# =========================================================================


@pytest.mark.unit
class TestGetCanopyParams:
    def test_nested_params_mapped_to_canopy_namespace(self, adapter, mock_client):
        mock_client.get_training_params.return_value = {"data": {"params": {"learning_rate": 0.1, "max_hidden_units": 8}}}
        result = adapter.get_canopy_params()
        assert result["nn_learning_rate"] == 0.1
        assert result["nn_max_hidden_units"] == 8

    def test_flat_data_fallback_excludes_meta_keys(self, adapter, mock_client):
        mock_client.get_training_params.return_value = {"data": {"learning_rate": 0.2, "epochs": 5, "status": "idle"}}
        result = adapter.get_canopy_params()
        assert result == {"nn_learning_rate": 0.2}

    def test_error_returns_empty(self, adapter, mock_client):
        mock_client.get_training_params.side_effect = JuniperCascorClientError("params boom")
        assert adapter.get_canopy_params() == {}


# =========================================================================
# is_cascor_nested public + private
# =========================================================================


@pytest.mark.unit
class TestNestedDetection:
    def test_public_wrapper_and_private_detect_nested(self):
        assert CascorServiceAdapter.is_cascor_nested({"state_machine": {}}) is True
        assert CascorServiceAdapter.is_cascor_nested({"training_active": True}) is True
        assert CascorServiceAdapter.is_cascor_nested({"loss": 0.1}) is False
        assert CascorServiceAdapter._is_cascor_nested("not-a-dict") is False


# =========================================================================
# get_training_status / get_network_data via circuit breaker
# =========================================================================


@pytest.mark.unit
class TestStatusAndNetworkData:
    def test_get_training_status_success_unwraps(self, adapter, mock_client):
        mock_client.get_training_status.return_value = {"data": {"is_training": True}}
        assert adapter.get_training_status() == {"is_training": True}

    def test_get_training_status_error_envelope(self, adapter, mock_client):
        mock_client.get_training_status.side_effect = JuniperCascorClientError("status boom")
        result = adapter.get_training_status()
        assert result["is_training"] is False
        assert result["error"] == "status boom"

    def test_get_network_data_success_unwraps(self, adapter, mock_client):
        mock_client.get_statistics.return_value = {"data": {"hidden_units": 3}}
        assert adapter.get_network_data() == {"hidden_units": 3}

    def test_get_network_data_error_returns_empty(self, adapter, mock_client):
        mock_client.get_statistics.side_effect = JuniperCascorClientError("stats boom")
        assert adapter.get_network_data() == {}


# =========================================================================
# _is_complete_topology + _transform_topology
# =========================================================================


@pytest.mark.unit
class TestTopologyTransforms:
    def test_is_complete_topology_non_dict(self):
        assert CascorServiceAdapter._is_complete_topology(None) is False

    def test_is_complete_topology_graph_format(self):
        assert CascorServiceAdapter._is_complete_topology({"input_units": 2, "nodes": []}) is True

    def test_is_complete_topology_cascor_format(self):
        assert CascorServiceAdapter._is_complete_topology({"hidden_units": []}) is True
        assert CascorServiceAdapter._is_complete_topology({"hidden_units": 3}) is False

    def test_transform_topology_graph_passthrough(self):
        raw = {"input_units": 2, "nodes": [{"id": "input_0"}]}
        assert CascorServiceAdapter._transform_topology(raw) is raw

    def test_transform_topology_full_cascor_to_graph(self):
        raw = {
            "input_size": 2,
            "output_size": 1,
            "hidden_units": [
                {"weights": [0.1, 0.2]},
                {"weights": [0.3, 0.4, 0.5]},
            ],
            "output_weights": [[0.6], [0.7], [0.8], [0.9]],
        }
        result = CascorServiceAdapter._transform_topology(raw)
        assert result["input_units"] == 2
        assert result["output_units"] == 1
        assert result["hidden_units"] == 2
        node_ids = {n["id"] for n in result["nodes"]}
        assert {"input_0", "input_1", "hidden_0", "hidden_1", "output_0"} <= node_ids
        # A cascade connection from hidden_0 → hidden_1 exists (prior-unit wiring).
        assert any(c["from"] == "hidden_0" and c["to"] == "hidden_1" for c in result["connections"])
        # Output receives from both inputs and both hidden units.
        assert any(c["from"] == "hidden_1" and c["to"] == "output_0" for c in result["connections"])

    def test_transform_topology_1d_output_weights_fallback(self):
        raw = {
            "input_size": 1,
            "output_size": 1,
            "hidden_units": [],
            "output_weights": [0.5],
        }
        result = CascorServiceAdapter._transform_topology(raw)
        assert result["hidden_units"] == 0
        assert any(c["from"] == "input_0" and c["to"] == "output_0" for c in result["connections"])


# =========================================================================
# _cb lazy accessor + topology extract/get success paths
# =========================================================================


@pytest.mark.unit
class TestCbAndTopologyExtract:
    def test_cb_lazy_creates_on_missing_circuit(self):
        from backend.circuit_breaker import CircuitBreaker

        bare = CascorServiceAdapter.__new__(CascorServiceAdapter)
        cb = bare._cb  # AttributeError path: no _circuit on a __new__ instance.
        assert isinstance(cb, CircuitBreaker)
        # Second access returns the now-cached instance.
        assert bare._cb is cb

    def test_extract_network_topology_transforms_dict(self, adapter, mock_client):
        mock_client.get_topology.return_value = {"data": {"input_size": 2, "output_size": 1, "hidden_units": []}}
        result = adapter.extract_network_topology()
        assert result["input_units"] == 2
        assert result["hidden_units"] == 0

    def test_get_network_topology_delegates_to_extract(self, adapter, mock_client):
        mock_client.get_topology.return_value = {"data": {"input_size": 3, "output_size": 2, "hidden_units": []}}
        result = adapter.get_network_topology()
        assert result["input_units"] == 3
        assert result["output_units"] == 2


# =========================================================================
# get_dataset_info + get_dataset_data scalar/binary + decision boundary
# =========================================================================


@pytest.mark.unit
class TestDatasetInfoBoundary:
    def test_get_dataset_info_success(self, adapter, mock_client):
        mock_client.get_dataset.return_value = {"data": {"n_samples": 100}}
        assert adapter.get_dataset_info() == {"n_samples": 100}

    def test_get_dataset_info_error(self, adapter, mock_client):
        mock_client.get_dataset.side_effect = JuniperCascorClientError("dataset boom")
        assert adapter.get_dataset_info() is None

    def test_get_dataset_data_binary_single_output(self, adapter, mock_client):
        mock_client.get_dataset_data.return_value = {"data": {"train_x": [[0, 0], [1, 1]], "train_y": [[0.7], [0.2]]}}
        result = adapter.get_dataset_data()
        assert result["inputs"] == [[0, 0], [1, 1]]
        assert result["targets"] == [1, 0]

    def test_get_dataset_data_scalar_labels(self, adapter, mock_client):
        mock_client.get_dataset_data.return_value = {"data": {"train_x": [[0, 0], [1, 1], [2, 2]], "train_y": [0, 1, 0]}}
        result = adapter.get_dataset_data()
        assert result["targets"] == [0, 1, 0]

    def test_get_decision_boundary_success(self, adapter, mock_client):
        mock_client.get_decision_boundary.return_value = {
            "data": {
                "grid_x": [[0.0, 1.0]],
                "grid_y": [[0.0], [1.0]],
                "predictions": [[0, 1]],
                "resolution": 50,
            }
        }
        result = adapter.get_decision_boundary()
        assert result["xx"] == [[0.0, 1.0]]
        assert result["Z"] == [[0, 1]]
        assert result["x_min"] == 0.0
        assert result["x_max"] == 1.0
        assert result["resolution"] == 50

    def test_get_decision_boundary_empty_data(self, adapter, mock_client):
        mock_client.get_decision_boundary.return_value = {"data": {}}
        assert adapter.get_decision_boundary() is None

    def test_get_prediction_function_is_none(self, adapter):
        assert adapter.get_prediction_function() is None


# =========================================================================
# Snapshot operation success paths (replay/resume/retrain/control)
# =========================================================================


@pytest.mark.unit
class TestSnapshotSuccessPaths:
    def test_replay_snapshot_success(self, adapter, mock_client):
        mock_client._post.return_value = {"operation": "replay", "fsm_state": "Replaying"}
        assert adapter.replay_snapshot("snap-1") == {"operation": "replay", "fsm_state": "Replaying"}
        mock_client._post.assert_called_once_with("/snapshots/snap-1/replay")

    def test_replay_snapshot_error_reraises(self, adapter, mock_client):
        mock_client._post.side_effect = JuniperCascorClientError("replay boom")
        with pytest.raises(JuniperCascorClientError):
            adapter.replay_snapshot("snap-1")

    def test_replay_control_success(self, adapter, mock_client):
        mock_client._post.return_value = {"action": "seek"}
        result = adapter.replay_control("snap-1", "seek", time_index=5, value=None)
        assert result == {"action": "seek"}
        # None-valued params are dropped from the body.
        mock_client._post.assert_called_once_with("/snapshots/snap-1/replay/control", json={"action": "seek", "time_index": 5})

    def test_resume_snapshot_success(self, adapter, mock_client):
        mock_client._post.return_value = {"resume_point_epoch": 12}
        assert adapter.resume_snapshot("snap-1") == {"resume_point_epoch": 12}

    def test_retrain_snapshot_success(self, adapter, mock_client):
        mock_client._post.return_value = {"operation": "retrain"}
        assert adapter.retrain_snapshot("snap-1") == {"operation": "retrain"}


# =========================================================================
# Network-mutation endpoints (patch/add/remove)
# =========================================================================


@pytest.mark.unit
class TestNetworkMutations:
    def test_patch_weights_success_with_hidden_index(self, adapter, mock_client):
        mock_client._patch.return_value = {"patched": True}
        result = adapter.patch_weights("hidden_unit", "weights", [0.1, 0.2], hidden_unit_index=0)
        assert result == {"patched": True}
        mock_client._patch.assert_called_once_with(
            "/network/weights",
            json={"target": "hidden_unit", "field": "weights", "values": [0.1, 0.2], "dtype": "float32", "hidden_unit_index": 0},
        )

    def test_patch_weights_success_without_hidden_index(self, adapter, mock_client):
        mock_client._patch.return_value = {"patched": True}
        result = adapter.patch_weights("output", "bias", [0.5])
        assert result == {"patched": True}
        # No hidden_unit_index key when target is output.
        _, kwargs = mock_client._patch.call_args
        assert "hidden_unit_index" not in kwargs["json"]

    def test_patch_weights_error_reraises(self, adapter, mock_client):
        mock_client._patch.side_effect = JuniperCascorClientError("patch boom")
        with pytest.raises(JuniperCascorClientError):
            adapter.patch_weights("output", "weights", [0.1])

    def test_add_hidden_unit_success(self, adapter, mock_client):
        mock_client._post.return_value = {"added": True}
        result = adapter.add_hidden_unit([0.1, 0.2], bias=0.3, activation="Sigmoid")
        assert result == {"added": True}
        mock_client._post.assert_called_once_with(
            "/network/hidden-units",
            json={"weights": [0.1, 0.2], "bias": 0.3, "activation": "Sigmoid", "position": "tail"},
        )

    def test_add_hidden_unit_error_reraises(self, adapter, mock_client):
        mock_client._post.side_effect = JuniperCascorClientError("add boom")
        with pytest.raises(JuniperCascorClientError):
            adapter.add_hidden_unit([0.1])

    def test_remove_hidden_unit_success(self, adapter, mock_client):
        mock_client._delete.return_value = {"removed": True}
        assert adapter.remove_hidden_unit(2) == {"removed": True}
        mock_client._delete.assert_called_once_with("/network/hidden-units/2")

    def test_remove_hidden_unit_error_reraises(self, adapter, mock_client):
        mock_client._delete.side_effect = JuniperCascorClientError("remove boom")
        with pytest.raises(JuniperCascorClientError):
            adapter.remove_hidden_unit(2)


# =========================================================================
# Monitoring/remote-worker no-ops + shutdown
# =========================================================================


@pytest.mark.unit
class TestNoOpsAndShutdown:
    def test_monitoring_noops(self, adapter):
        assert adapter.install_monitoring_hooks() is True
        assert adapter.start_monitoring_thread() is None
        assert adapter.stop_monitoring() is None
        assert adapter.restore_original_methods() is None
        assert adapter.create_monitoring_callback("state", lambda: None) is None

    def test_remote_worker_noops(self, adapter):
        status = adapter.get_remote_worker_status()
        assert status["available"] is False
        assert status["connected"] is False
        assert adapter.connect_remote_workers(("host", 1), b"key") is False
        assert adapter.start_remote_workers(2) is False
        assert adapter.stop_remote_workers(5) is False
        assert adapter.disconnect_remote_workers() is False

    def test_shutdown_closes_client(self, adapter, mock_client):
        mock_client.close.return_value = None
        adapter.shutdown()
        mock_client.close.assert_called_once_with()

    def test_shutdown_swallows_close_error(self, adapter, mock_client):
        mock_client.close.side_effect = RuntimeError("close boom")
        # Must not raise — shutdown logs and continues.
        adapter.shutdown()


# =========================================================================
# Metrics-relay loop — candidate-pool phase mapping + control supervisor
# =========================================================================


@pytest.mark.unit
class TestMetricsRelayStateAndSupervisor:
    async def test_state_phase_detail_training_candidates(self, adapter):
        callback = MagicMock()
        adapter.set_state_update_callback(callback)
        messages = [
            {"type": "state", "data": {"status": "training", "phase_detail": "training_candidates", "best_candidate_id": 3, "second_candidate_id": 5}},
            {"type": "state", "data": {"status": "training", "phase_detail": "adding_candidate"}},
        ]
        first = _FakeStream(messages=messages)
        await _drive_relay(adapter, [first, _cancel_stream()])
        # Both state frames drove callbacks with the mapped candidate-pool status.
        pool_statuses = [c.kwargs.get("candidate_pool_status") for c in callback.call_args_list if "candidate_pool_status" in c.kwargs]
        assert "Training" in pool_statuses
        assert "Selecting Best" in pool_statuses

    async def test_control_supervisor_started_when_ws_enabled(self, adapter):
        blocking = _FakeStream(block=True)
        fake_ctrl = _FakeControlStream()
        with patch(_CTS, _stream_factory(blocking, _FakeStream(block=True))), patch(_CCS, return_value=fake_ctrl), patch(_WSM_TARGET, _WSM()), patch(_SETTINGS, return_value=SimpleNamespace(use_websocket_set_params=True)):
            await adapter.start_metrics_relay()
            await asyncio.sleep(0.05)
            # Control supervisor connect loop reached CONNECTED via the fake stream.
            assert adapter._control_supervisor.is_connected is True
            await adapter.stop_metrics_relay()
        assert adapter._relay_task is None
