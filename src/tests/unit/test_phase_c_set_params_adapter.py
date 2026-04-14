"""Phase C: Unit tests for set_params adapter with hot/cold routing.

§S9 — Tests for apply_params feature flag, hot/cold param classification,
WS routing, REST fallback, and control stream supervisor.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.cascor_service_adapter import CascorServiceAdapter, ControlStreamSupervisor

# ===================================================================
# Fixtures
# ===================================================================


def _make_settings(**overrides):
    """Create a mock settings object with Phase C defaults."""
    defaults = {"use_websocket_set_params": False, "ws_set_params_timeout": 1.0}
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def mock_client():
    """Mock JuniperCascorClient for REST calls."""
    client = MagicMock()
    client.update_params.return_value = {"learning_rate": 0.01}
    client.get_training_params.return_value = {"data": {"params": {}}}
    return client


@pytest.fixture
def adapter(mock_client):
    """CascorServiceAdapter with mock client."""
    return CascorServiceAdapter(service_url="http://localhost:8200", client=mock_client)


def _patch_settings(**overrides):
    """Return a patch context that mocks get_settings() with given overrides."""
    return patch("settings.get_settings", return_value=_make_settings(**overrides))


# ===================================================================
# Tests — Phase C (§S9)
# ===================================================================


@pytest.mark.unit
class TestPhaseC:
    """Unit tests for Phase C set_params adapter."""

    # ------------------------------------------------------------------
    # 1. Feature flag default off
    # ------------------------------------------------------------------

    def test_apply_params_feature_flag_default_off(self, adapter, mock_client):
        """With use_websocket_set_params=False (default), all params go to REST."""
        with _patch_settings(use_websocket_set_params=False):
            result = adapter.apply_params(nn_learning_rate=0.05)

        assert result["ok"] is True
        mock_client.update_params.assert_called_once()
        call_args = mock_client.update_params.call_args[0][0]
        assert "learning_rate" in call_args

    # ------------------------------------------------------------------
    # 2. Hot keys go to WebSocket
    # ------------------------------------------------------------------

    def test_apply_params_hot_keys_go_to_websocket(self, adapter, mock_client):
        """With flag on, hot params route through WS set_params."""
        loop = asyncio.new_event_loop()
        adapter._control_supervisor = MagicMock()
        adapter._control_supervisor.is_connected = True
        adapter._control_supervisor.loop = loop

        mock_future = MagicMock()
        mock_future.result.return_value = {"learning_rate": 0.05}

        with _patch_settings(use_websocket_set_params=True, ws_set_params_timeout=1.0), patch("asyncio.run_coroutine_threadsafe", return_value=mock_future) as mock_rcts:
            result = adapter.apply_params(nn_learning_rate=0.05)

        assert result["ok"] is True
        mock_rcts.assert_called_once()
        mock_client.update_params.assert_not_called()
        loop.close()

    # ------------------------------------------------------------------
    # 3. Cold keys go to REST
    # ------------------------------------------------------------------

    def test_apply_params_cold_keys_go_to_rest(self, adapter, mock_client):
        """Cold params always go through REST, even with flag on."""
        adapter._control_supervisor = MagicMock()
        adapter._control_supervisor.is_connected = True

        with _patch_settings(use_websocket_set_params=True):
            result = adapter.apply_params(nn_init_output_weights="zero")

        assert result["ok"] is True
        mock_client.update_params.assert_called_once()
        call_args = mock_client.update_params.call_args[0][0]
        assert "init_output_weights" in call_args

    # ------------------------------------------------------------------
    # 4. Mixed batch split
    # ------------------------------------------------------------------

    def test_apply_params_mixed_batch_split(self, adapter, mock_client):
        """Mixed hot+cold params are split correctly."""
        loop = asyncio.new_event_loop()
        adapter._control_supervisor = MagicMock()
        adapter._control_supervisor.is_connected = True
        adapter._control_supervisor.loop = loop

        mock_future = MagicMock()
        mock_future.result.return_value = {"learning_rate": 0.05}

        with _patch_settings(use_websocket_set_params=True, ws_set_params_timeout=1.0), patch("asyncio.run_coroutine_threadsafe", return_value=mock_future):
            result = adapter.apply_params(nn_learning_rate=0.05, nn_init_output_weights="random")

        assert result["ok"] is True
        mock_client.update_params.assert_called_once()
        rest_args = mock_client.update_params.call_args[0][0]
        assert "init_output_weights" in rest_args
        assert "learning_rate" not in rest_args
        loop.close()

    # ------------------------------------------------------------------
    # 5. Hot falls back to REST on timeout
    # ------------------------------------------------------------------

    def test_apply_params_hot_falls_back_to_rest_on_timeout(self, adapter, mock_client):
        """WS timeout triggers REST fallback for hot params."""
        loop = asyncio.new_event_loop()
        adapter._control_supervisor = MagicMock()
        adapter._control_supervisor.is_connected = True
        adapter._control_supervisor.loop = loop

        mock_future = MagicMock()
        mock_future.result.side_effect = TimeoutError("WS timeout")

        with _patch_settings(use_websocket_set_params=True, ws_set_params_timeout=1.0), patch("asyncio.run_coroutine_threadsafe", return_value=mock_future):
            result = adapter.apply_params(nn_learning_rate=0.05)

        assert result["ok"] is True
        mock_client.update_params.assert_called_once()
        rest_args = mock_client.update_params.call_args[0][0]
        assert "learning_rate" in rest_args
        loop.close()

    # ------------------------------------------------------------------
    # 6. Hot falls back to REST on disconnect
    # ------------------------------------------------------------------

    def test_apply_params_hot_falls_back_to_rest_on_disconnect(self, adapter, mock_client):
        """Disconnected supervisor triggers REST fallback for hot params."""
        adapter._control_supervisor = MagicMock()
        adapter._control_supervisor.is_connected = False

        with _patch_settings(use_websocket_set_params=True):
            result = adapter.apply_params(nn_learning_rate=0.05)

        assert result["ok"] is True
        mock_client.update_params.assert_called_once()

    # ------------------------------------------------------------------
    # 7. Unclassified keys default to REST with warning
    # ------------------------------------------------------------------

    def test_apply_params_unclassified_keys_default_to_rest_with_warning(self, adapter, mock_client, caplog):
        """Keys not in hot or cold sets fall through to REST with WARNING (C-09)."""
        # Add a temporary unclassified key
        original_map = dict(CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP)
        CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP["nn_test_unclassified"] = "test_unclassified"

        try:
            with _patch_settings(use_websocket_set_params=True):
                result = adapter.apply_params(nn_test_unclassified=42)

            assert result["ok"] is True
            mock_client.update_params.assert_called_once()
            rest_args = mock_client.update_params.call_args[0][0]
            assert "test_unclassified" in rest_args
            assert "Unclassified params defaulting to REST" in caplog.text
        finally:
            CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP = original_map

    # ------------------------------------------------------------------
    # 8. Hot/cold classification covers all mapped params
    # ------------------------------------------------------------------

    def test_all_mapped_params_classified(self):
        """Every cascor param in the mapping is classified as hot or cold."""
        all_cascor_params = set(CascorServiceAdapter._CANOPY_TO_CASCOR_PARAM_MAP.values())
        classified = CascorServiceAdapter._HOT_CASCOR_PARAMS | CascorServiceAdapter._COLD_CASCOR_PARAMS
        unclassified = all_cascor_params - classified
        assert not unclassified, f"Unclassified cascor params: {unclassified}"

    # ------------------------------------------------------------------
    # 9. Hot param count matches spec (11)
    # ------------------------------------------------------------------

    def test_hot_param_count(self):
        """Exactly 11 hot params per §S9."""
        assert len(CascorServiceAdapter._HOT_CASCOR_PARAMS) == 11

    # ------------------------------------------------------------------
    # 10. Supervisor reconnects with backoff
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_control_stream_supervisor_reconnects_with_backoff(self):
        """Supervisor retries with increasing backoff on failure."""
        supervisor = ControlStreamSupervisor(ws_url="ws://fake:8200")
        sleeps = []

        async def mock_sleep(delay):
            sleeps.append(delay)
            if len(sleeps) >= 3:
                supervisor._shutdown = True
                raise asyncio.CancelledError

        with patch("backend.cascor_service_adapter.CascorControlStream") as MockStream:
            instance = MockStream.return_value
            instance.connect = AsyncMock(side_effect=OSError("refused"))
            instance._ws = None

            with patch("asyncio.sleep", side_effect=mock_sleep):
                try:
                    await supervisor._connect_loop()
                except asyncio.CancelledError:
                    pass

        assert len(sleeps) >= 2
        assert sleeps[0] == 1
        assert sleeps[1] == 2

    # ------------------------------------------------------------------
    # 11. Supervisor shutdown cleans up
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_control_stream_supervisor_shutdown_cancels_pending(self):
        """Stopping the supervisor cleans up the stream."""
        supervisor = ControlStreamSupervisor(ws_url="ws://fake:8200")
        mock_stream = MagicMock()
        mock_stream.disconnect = AsyncMock()
        supervisor._stream = mock_stream
        supervisor._connect_task = asyncio.create_task(asyncio.sleep(100))

        await supervisor.stop()

        assert supervisor._shutdown is True
        mock_stream.disconnect.assert_awaited_once()
