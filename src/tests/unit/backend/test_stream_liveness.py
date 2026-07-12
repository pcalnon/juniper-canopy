"""N2 (training-runtime defects plan §4 I-1 / §5 T2/T5): stream liveness + supervised reconnect.

Regression suite for the 2026-07-10 incident class: cascor closed canopy's control WS
40 s after connect and the supervisor — whose liveness notion was ``_ws is not None``
(blind to half-open / peer-closed sockets) — never noticed for 12+ hours, with zero
reconnect log lines all session. The metrics relay likewise had no liveness bound, no
throughput counters, and permanently died on a single failed reconnect because
``connect()`` raises ``JuniperCascorConnectionError`` (not an ``OSError``) which fell
into the generic ``except Exception: ... break`` arm.

Covers:
- ``_ws_open`` real-state liveness helper (half-open detection).
- ``StreamHealth`` classification (healthy / degraded / reconnecting) + counters.
- ``ControlStreamSupervisor``: half-open detection, keepalive probe, logged reconnect.
- Relay loop: liveness expiry → logged reconnect; frame counters by type; connect-failure
  and unexpected-exception classes reconnect with backoff instead of dying.
- Periodic relay summary emission (zero-counts included — silence becomes visible).
- ``get_stream_health()`` combined snapshot + overall classification.
"""

import asyncio
import logging
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_jcc = pytest.importorskip("juniper_cascor_client", reason="juniper-cascor-client not installed")
if getattr(_jcc, "_is_stub", False):
    pytest.skip("juniper-cascor-client is a test stub, not the real package", allow_module_level=True)

from juniper_cascor_client.exceptions import JuniperCascorConnectionError

from backend.cascor_service_adapter import CascorServiceAdapter, ControlStreamSupervisor, StreamHealth, _ws_open

ADAPTER_LOGGER = "juniper_canopy.backend.cascor_service_adapter"


def _make_settings(**overrides):
    """Mock settings namespace for the relay/supervisor settings reads."""
    defaults = {
        "use_websocket_set_params": False,
        "ws_set_params_timeout": 1.0,
        "ws_stream_liveness_timeout_seconds": 90.0,
        "ws_stream_probe_interval_seconds": 30.0,
        "ws_relay_summary_interval_seconds": 0.0,  # summary task off unless a test opts in
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _patch_settings(**overrides):
    return patch("settings.get_settings", return_value=_make_settings(**overrides))


class _FakeWs:
    """Minimal stand-in for a ``websockets`` ClientConnection (state + close_code)."""

    def __init__(self, state_name="OPEN", close_code=None):
        self.state = SimpleNamespace(name=state_name)
        self.close_code = close_code

    def close(self, state_name="CLOSED", close_code=1011):
        self.state = SimpleNamespace(name=state_name)
        self.close_code = close_code


# ===================================================================
# _ws_open — the half-open detection primitive
# ===================================================================


@pytest.mark.unit
class TestWsOpen:
    def test_none_is_closed(self):
        assert _ws_open(None) is False

    def test_open_state_is_open(self):
        assert _ws_open(_FakeWs("OPEN")) is True

    def test_closed_state_is_closed(self):
        """THE incident regression: a peer-closed socket keeps a non-None ``_ws``
        object whose state is CLOSED — the pre-fix ``_ws is not None`` read it
        as connected for 12+ hours."""
        assert _ws_open(_FakeWs("CLOSED")) is False

    def test_closing_state_is_not_open(self):
        assert _ws_open(_FakeWs("CLOSING")) is False

    def test_object_without_state_surface_falls_back_to_presence(self):
        """Fakes / future CL1 client objects without a ``state`` attr: presence wins."""
        assert _ws_open(SimpleNamespace()) is True


# ===================================================================
# StreamHealth
# ===================================================================


@pytest.mark.unit
class TestStreamHealth:
    def test_never_connected_is_reconnecting(self):
        health = StreamHealth("t")
        assert health.status() == "reconnecting"
        snap = health.snapshot()
        assert snap["connected"] is False
        assert snap["last_activity_age_seconds"] is None
        assert snap["frames_forwarded_total"] == 0

    def test_connected_with_recent_activity_is_healthy(self):
        health = StreamHealth("t", stale_after_seconds=60.0)
        health.mark_connected()
        health.mark_activity("metrics")
        assert health.status() == "healthy"

    def test_connected_but_stale_is_degraded(self):
        health = StreamHealth("t", stale_after_seconds=60.0)
        health.mark_connected()
        health._last_activity = time.monotonic() - 3600.0
        assert health.status() == "degraded"

    def test_no_stale_bound_means_connected_is_healthy(self):
        """Control-stream posture: quiet-but-open is its normal state."""
        health = StreamHealth("control")
        health.mark_connected()
        health._last_activity = time.monotonic() - 3600.0
        assert health.status() == "healthy"

    def test_disconnect_records_reason_and_reconnect_counts(self):
        health = StreamHealth("t")
        health.mark_connected()
        health.mark_disconnected("liveness expired")
        assert health.status() == "reconnecting"
        assert health.snapshot()["last_disconnect_reason"] == "liveness expired"
        health.mark_connected()
        assert health.snapshot()["reconnect_count"] == 1

    def test_frame_counters_by_type(self):
        health = StreamHealth("t")
        health.mark_connected()
        for t in ("metrics", "metrics", "ping", "state"):
            health.mark_activity(t)
        snap = health.snapshot()
        assert snap["frames_forwarded_total"] == 4
        assert snap["frames_by_type"] == {"metrics": 2, "ping": 1, "state": 1}

    def test_take_interval_counts_returns_and_resets(self):
        health = StreamHealth("t")
        health.mark_activity("metrics")
        health.mark_activity("ping")
        first = health.take_interval_counts()
        assert first == {"metrics": 1, "ping": 1}
        assert health.take_interval_counts() == {}
        # Cumulative totals survive the interval reset.
        assert health.snapshot()["frames_forwarded_total"] == 2

    def test_activity_without_type_only_feeds_liveness_clock(self):
        health = StreamHealth("t")
        health.mark_activity()
        snap = health.snapshot()
        assert snap["frames_forwarded_total"] == 0
        assert snap["last_activity_age_seconds"] is not None


# ===================================================================
# ControlStreamSupervisor — half-open detection + supervised reconnect
# ===================================================================


@pytest.mark.unit
class TestSupervisorLiveness:
    def test_is_connected_false_when_no_stream(self):
        supervisor = ControlStreamSupervisor(ws_url="ws://fake:8200")
        assert supervisor.is_connected is False

    def test_is_connected_false_when_ws_none(self):
        supervisor = ControlStreamSupervisor(ws_url="ws://fake:8200")
        supervisor._stream = SimpleNamespace(_ws=None)
        assert supervisor.is_connected is False

    def test_is_connected_true_when_socket_open(self):
        supervisor = ControlStreamSupervisor(ws_url="ws://fake:8200")
        supervisor._stream = SimpleNamespace(_ws=_FakeWs("OPEN"))
        assert supervisor.is_connected is True

    def test_is_connected_false_for_half_open_socket(self):
        """THE incident regression: peer-closed socket, ``_ws`` still non-None."""
        supervisor = ControlStreamSupervisor(ws_url="ws://fake:8200")
        supervisor._stream = SimpleNamespace(_ws=_FakeWs("CLOSED", close_code=1011))
        assert supervisor.is_connected is False

    async def test_probe_liveness_pong_ok_marks_activity(self):
        supervisor = ControlStreamSupervisor(ws_url="ws://fake:8200")

        class _PingWs(_FakeWs):
            async def ping(self):
                fut = asyncio.get_running_loop().create_future()
                fut.set_result(None)
                return fut

        supervisor._stream = SimpleNamespace(_ws=_PingWs())
        before = supervisor.health.snapshot()["last_activity_age_seconds"]
        assert await supervisor._probe_liveness() is True
        after = supervisor.health.snapshot()["last_activity_age_seconds"]
        assert before is None and after is not None

    async def test_probe_liveness_send_failure_is_dead(self):
        supervisor = ControlStreamSupervisor(ws_url="ws://fake:8200")

        class _DeadWs(_FakeWs):
            async def ping(self):
                raise OSError("send failed")

        supervisor._stream = SimpleNamespace(_ws=_DeadWs())
        assert await supervisor._probe_liveness() is False

    async def test_probe_liveness_missed_pong_is_dead(self):
        supervisor = ControlStreamSupervisor(ws_url="ws://fake:8200")
        supervisor._probe_pong_timeout = 0.01

        class _SilentWs(_FakeWs):
            async def ping(self):
                return asyncio.get_running_loop().create_future()  # never resolves

        supervisor._stream = SimpleNamespace(_ws=_SilentWs())
        assert await supervisor._probe_liveness() is False

    async def test_probe_liveness_without_ping_surface_defers_to_state(self):
        supervisor = ControlStreamSupervisor(ws_url="ws://fake:8200")
        supervisor._stream = SimpleNamespace(_ws=_FakeWs("OPEN"))  # no ping attr
        assert await supervisor._probe_liveness() is True

    async def test_half_open_socket_triggers_logged_reconnect(self, caplog):
        """The full incident loop: socket dies half-open → one WARNING with the
        reason → stream closed → reconnect attempted. Pre-fix: the inner loop
        span forever on ``_ws is not None`` with zero log lines."""
        supervisor = ControlStreamSupervisor(ws_url="ws://fake:8200")
        supervisor._probe_interval = 0  # pure state-based detection here

        fake_ws = _FakeWs("OPEN")
        stream1 = MagicMock()
        stream1._ws = fake_ws
        stream1.connect = AsyncMock()
        stream1.disconnect = AsyncMock()

        stream2 = MagicMock()
        stream2._ws = _FakeWs("OPEN")
        stream2.disconnect = AsyncMock()

        async def _second_connect():
            supervisor._shutdown = True  # stop the loop after the reconnect

        stream2.connect = AsyncMock(side_effect=_second_connect)

        async def fake_sleep(delay):
            # First inner-loop tick: the peer closes the socket under us.
            fake_ws.close(close_code=1011)

        with patch("backend.cascor_service_adapter.CascorControlStream", side_effect=[stream1, stream2]), patch("asyncio.sleep", side_effect=fake_sleep), caplog.at_level(logging.INFO, logger=ADAPTER_LOGGER):
            await supervisor._connect_loop()

        assert "Control stream liveness lost" in caplog.text
        assert "close_code=1011" in caplog.text
        stream1.disconnect.assert_awaited()
        stream2.connect.assert_awaited()
        # The second successful connect registers as a reconnect.
        assert supervisor.health.snapshot()["reconnect_count"] == 1

    async def test_failed_probe_triggers_logged_reconnect(self, caplog):
        supervisor = ControlStreamSupervisor(ws_url="ws://fake:8200")
        supervisor._probe_interval = 0.000001  # probe on the first tick

        class _DeadWs(_FakeWs):
            async def ping(self):
                raise OSError("send failed")

        stream1 = MagicMock()
        stream1._ws = _DeadWs("OPEN")
        stream1.connect = AsyncMock()
        stream1.disconnect = AsyncMock()

        stream2 = MagicMock()
        stream2._ws = _FakeWs("OPEN")
        stream2.disconnect = AsyncMock()

        async def _second_connect():
            supervisor._shutdown = True

        stream2.connect = AsyncMock(side_effect=_second_connect)

        async def fake_sleep(delay):
            return None

        with patch("backend.cascor_service_adapter.CascorControlStream", side_effect=[stream1, stream2]), patch("asyncio.sleep", side_effect=fake_sleep), caplog.at_level(logging.INFO, logger=ADAPTER_LOGGER):
            await supervisor._connect_loop()

        assert "keepalive probe failed" in caplog.text
        stream2.connect.assert_awaited()

    async def test_set_params_ack_marks_activity(self):
        supervisor = ControlStreamSupervisor(ws_url="ws://fake:8200")
        stream = MagicMock()
        stream._ws = _FakeWs("OPEN")
        stream.set_params = AsyncMock(return_value={"data": {"status": "ok"}})
        supervisor._stream = stream
        result = await supervisor.set_params({"learning_rate": 0.01})
        assert result == {"data": {"status": "ok"}}
        assert supervisor.health.snapshot()["last_activity_age_seconds"] is not None


# ===================================================================
# Relay loop — liveness, counters, reconnect classes
# ===================================================================


def _make_stream(frames=None, connect_exc=None, hang_after_frames=False):
    """Scripted CascorTrainingStream stand-in for the relay loop."""
    stream = MagicMock()
    stream._ws = None  # the relay's ping-pong branch skips the send when falsy
    stream.disconnect = AsyncMock()
    if connect_exc is not None:
        stream.connect = AsyncMock(side_effect=connect_exc)
    else:
        stream.connect = AsyncMock()

    async def _gen():
        for f in frames or []:
            yield f
        if hang_after_frames:
            await asyncio.Event().wait()  # half-open simulation: never yields again

    stream.stream = _gen
    return stream


async def _wait_until(predicate, timeout=5.0, step=0.01):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(step)
    return False


@pytest.mark.unit
class TestRelayLiveness:
    @pytest.fixture
    def adapter(self):
        return CascorServiceAdapter(service_url="http://localhost:8200", client=MagicMock())

    async def test_frames_counted_by_type(self, adapter):
        frames = [
            {"type": "metrics", "data": {"loss": 0.1}, "seq": 1},
            {"type": "ping"},
            {"type": "state", "data": {"status": "training"}, "seq": 2},
        ]
        stream1 = _make_stream(frames=frames, hang_after_frames=True)

        with _patch_settings(), patch("backend.cascor_service_adapter.CascorTrainingStream", side_effect=[stream1]):
            await adapter.start_metrics_relay()
            try:
                assert await _wait_until(lambda: adapter.relay_health.snapshot()["frames_forwarded_total"] >= 3)
                snap = adapter.relay_health.snapshot()
                assert snap["frames_by_type"] == {"metrics": 1, "ping": 1, "state": 1}
                assert snap["status"] == "healthy"
                assert snap["connected"] is True
            finally:
                await adapter.stop_metrics_relay()

    async def test_liveness_expiry_reconnects_with_log(self, adapter, caplog):
        """A half-open socket (frames stop, connection never closes) must not
        starve the relay silently: the bounded wait expires, one WARNING is
        logged, and a reconnect is attempted."""
        stream1 = _make_stream(frames=[{"type": "metrics", "data": {}}], hang_after_frames=True)
        stream2 = _make_stream(frames=[], hang_after_frames=True)

        with _patch_settings(ws_stream_liveness_timeout_seconds=0.05), patch("backend.cascor_service_adapter.CascorTrainingStream", side_effect=[stream1, stream2]), caplog.at_level(logging.WARNING, logger=ADAPTER_LOGGER):
            await adapter.start_metrics_relay()
            try:
                assert await _wait_until(lambda: stream2.connect.await_count >= 1)
            finally:
                await adapter.stop_metrics_relay()

        assert "liveness expired" in caplog.text
        assert "Reconnecting in" in caplog.text
        stream1.disconnect.assert_awaited()

    async def test_connect_failure_class_reconnects_instead_of_dying(self, adapter, caplog):
        """Regression for the permanent-death defect: ``connect()`` raises
        ``JuniperCascorConnectionError`` (NOT an OSError); the pre-fix generic
        arm logged once and ``break``-ed — the relay never tried again."""
        stream1 = _make_stream(connect_exc=JuniperCascorConnectionError("Failed to connect to ws://fake"))
        stream2 = _make_stream(frames=[], hang_after_frames=True)

        with _patch_settings(), patch("backend.cascor_service_adapter.CascorTrainingStream", side_effect=[stream1, stream2]), caplog.at_level(logging.WARNING, logger=ADAPTER_LOGGER):
            await adapter.start_metrics_relay()
            try:
                assert await _wait_until(lambda: stream2.connect.await_count >= 1), "relay died after a single failed reconnect (pre-N2 defect)"
            finally:
                await adapter.stop_metrics_relay()

        assert "Reconnecting in" in caplog.text

    async def test_unexpected_exception_reconnects_instead_of_dying(self, adapter, caplog):
        stream1 = _make_stream(connect_exc=RuntimeError("boom"))
        stream2 = _make_stream(frames=[], hang_after_frames=True)

        with _patch_settings(), patch("backend.cascor_service_adapter.CascorTrainingStream", side_effect=[stream1, stream2]), caplog.at_level(logging.ERROR, logger=ADAPTER_LOGGER):
            await adapter.start_metrics_relay()
            try:
                assert await _wait_until(lambda: stream2.connect.await_count >= 1), "relay died on an unexpected exception (pre-N2 defect)"
            finally:
                await adapter.stop_metrics_relay()

        assert "Unexpected error in relay loop" in caplog.text
        assert "reconnecting" in caplog.text.lower()

    async def test_stream_end_reconnects_with_log(self, adapter, caplog):
        """The peer-closed path used to reconnect silently with no backoff."""
        stream1 = _make_stream(frames=[{"type": "ping"}])  # generator ends after one frame
        stream2 = _make_stream(frames=[], hang_after_frames=True)

        with _patch_settings(), patch("backend.cascor_service_adapter.CascorTrainingStream", side_effect=[stream1, stream2]), caplog.at_level(logging.WARNING, logger=ADAPTER_LOGGER):
            await adapter.start_metrics_relay()
            try:
                assert await _wait_until(lambda: stream2.connect.await_count >= 1)
            finally:
                await adapter.stop_metrics_relay()

        assert "stream ended" in caplog.text

    async def test_summary_emitted_with_zero_counts(self, adapter, caplog):
        """§5 T5: the periodic INFO summary makes silence visible — it emits
        even when nothing was forwarded, and core types show explicit zeros
        (the heartbeat-only incident signature is ``ping=N, metrics=0``)."""
        stream1 = _make_stream(frames=[{"type": "ping"}], hang_after_frames=True)

        with _patch_settings(ws_relay_summary_interval_seconds=0.05), patch("backend.cascor_service_adapter.CascorTrainingStream", side_effect=[stream1]), caplog.at_level(logging.INFO, logger=ADAPTER_LOGGER):
            await adapter.start_metrics_relay()
            try:
                assert await _wait_until(lambda: "Metrics relay summary" in caplog.text)
            finally:
                await adapter.stop_metrics_relay()

        assert "metrics=0" in caplog.text  # zero-count core type is explicit
        assert "ping=1" in caplog.text

    async def test_stop_metrics_relay_cancels_summary_task(self, adapter):
        stream1 = _make_stream(frames=[], hang_after_frames=True)
        with _patch_settings(ws_relay_summary_interval_seconds=60.0), patch("backend.cascor_service_adapter.CascorTrainingStream", side_effect=[stream1]):
            await adapter.start_metrics_relay()
            assert adapter._relay_summary_task is not None
            await adapter.stop_metrics_relay()
            assert adapter._relay_summary_task is None


# ===================================================================
# get_stream_health — combined snapshot for /api/stream_health + badge
# ===================================================================


@pytest.mark.unit
class TestGetStreamHealth:
    @pytest.fixture
    def adapter(self):
        return CascorServiceAdapter(service_url="http://localhost:8200", client=MagicMock())

    def test_shape_and_never_connected_overall(self, adapter):
        with _patch_settings(use_websocket_set_params=False):
            health = adapter.get_stream_health()
        assert set(health.keys()) == {"overall", "relay", "control"}
        assert health["overall"] == "reconnecting"
        assert health["relay"]["status"] == "reconnecting"
        assert health["control"]["enabled"] is False

    def test_healthy_relay_is_overall_healthy(self, adapter):
        adapter.relay_health.mark_connected()
        adapter.relay_health.mark_activity("metrics")
        with _patch_settings(use_websocket_set_params=False):
            health = adapter.get_stream_health()
        assert health["overall"] == "healthy"

    def test_stale_relay_is_overall_degraded(self, adapter):
        adapter.relay_health.mark_connected()
        adapter.relay_health._last_activity = time.monotonic() - 3600.0
        with _patch_settings(use_websocket_set_params=False):
            health = adapter.get_stream_health()
        assert health["overall"] == "degraded"
        assert health["relay"]["status"] == "degraded"

    def test_unhealthy_enabled_control_degrades_healthy_overall(self, adapter):
        adapter.relay_health.mark_connected()
        adapter.relay_health.mark_activity("metrics")
        with _patch_settings(use_websocket_set_params=True):
            health = adapter.get_stream_health()
        assert health["control"]["enabled"] is True
        assert health["control"]["status"] == "reconnecting"
        assert health["overall"] == "degraded"

    def test_unhealthy_disabled_control_does_not_degrade(self, adapter):
        adapter.relay_health.mark_connected()
        adapter.relay_health.mark_activity("metrics")
        with _patch_settings(use_websocket_set_params=False):
            health = adapter.get_stream_health()
        assert health["overall"] == "healthy"

    def test_relay_health_lazy_property_for_new_created_instances(self):
        adapter = CascorServiceAdapter.__new__(CascorServiceAdapter)
        assert isinstance(adapter.relay_health, StreamHealth)
