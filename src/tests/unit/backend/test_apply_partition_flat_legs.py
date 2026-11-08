"""F-CANOPY-065: a flat second leg must not replace the first leg's partition.

``apply_params`` reads ``applied`` / ``skipped`` from each leg's own result and
unions them. ``test_n5_apply_params_ux.py`` pairs an unwrapped WebSocket result
(partition at the top level) with a REST envelope whose partition sits under
``data``. Those two keys do not collide, so extracting once from the merged
``data`` dict still reports both legs. A flat REST body — the other shape
``_extract_cascor_partition`` accepts, and the shape the unit fakes return —
carries ``applied`` and ``skipped`` at the top level, the same keys the
unwrapped WebSocket result uses. Merging the dicts replaces the first lists.

A ``/ws/control`` ack whose ``data.result`` is not a dict unwraps to ``{}``.
Handing that list to ``dict.update`` raises, and handing the whole frame back
puts the command envelope into the apply response.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.cascor_service_adapter import CascorServiceAdapter

_WS = {
    "learning_rate": 0.05,
    "max_iterations": 3,
    "applied": ["learning_rate", "max_iterations"],
    "skipped": [{"key": "epochs_max", "reason": "not-updatable"}],
}
_PARAMS = {
    "nn_learning_rate": 0.05,
    "nn_max_iterations": 3,
    "nn_max_total_epochs": 5000,
    "cn_training_iterations": 50,
}


def _apply(rest_body, *, ws_result=_WS):
    adapter = CascorServiceAdapter(client=MagicMock())
    adapter._apply_params_hot = MagicMock(return_value=ws_result)
    adapter._client.update_params.return_value = rest_body
    with (
        patch("settings.get_settings", return_value=SimpleNamespace(use_websocket_set_params=True)),
        patch.object(adapter, "_verify_apply_roundtrip", return_value=None),
    ):
        result = adapter.apply_params(**_PARAMS)
    assert adapter._client.update_params.call_args[0][0] == {"candidate_epochs": 50}
    return result


@pytest.mark.unit
class TestFlatLegsKeepBothPartitions:
    def test_a_flat_rest_body_keeps_the_ws_keys_and_appends_its_own(self):
        result = _apply(
            {
                "candidate_epochs": 50,
                "applied": ["learning_rate", "candidate_epochs"],
                "skipped": [{"key": "optimizer_type", "reason": "no-such-attribute"}],
            }
        )
        assert result["ok"] is True
        assert result["applied"] == ["nn_learning_rate", "nn_max_iterations", "cn_training_iterations"]
        assert result["skipped_detail"] == [
            {"key": "nn_max_total_epochs", "reason": "not-updatable"},
            {"key": "nn_optimizer_type", "reason": "no-such-attribute"},
        ]

    def test_an_empty_flat_skip_list_does_not_wipe_the_ws_skip(self):
        result = _apply({"candidate_epochs": 50, "applied": ["candidate_epochs"], "skipped": []})
        assert result["applied"] == ["nn_learning_rate", "nn_max_iterations", "cn_training_iterations"]
        assert result["skipped_detail"] == [{"key": "nn_max_total_epochs", "reason": "not-updatable"}]


def _ack(result):
    return {"type": "command_response", "timestamp": 1760000000.0, "data": {"command": "set_params", "status": "success", "result": result}}


@pytest.mark.unit
class TestUnwrapRejectsANonDictResult:
    @pytest.mark.parametrize("result", [["learning_rate"], "ok", 1])
    def test_a_non_dict_result_unwraps_to_empty(self, result):
        assert CascorServiceAdapter._unwrap_control_ack(_ack(result)) == {}

    def test_an_empty_result_dict_stays_empty(self):
        assert CascorServiceAdapter._unwrap_control_ack(_ack({})) == {}

    def test_a_dict_whose_data_is_not_an_envelope_passes_through(self):
        frame = {"applied": ["learning_rate"], "data": ["not-an-envelope"]}
        assert CascorServiceAdapter._unwrap_control_ack(frame) == frame

    def test_a_list_result_does_not_raise_or_leak_the_envelope(self, monkeypatch):
        adapter = CascorServiceAdapter(client=MagicMock())
        supervisor = MagicMock()
        supervisor.is_connected = True
        supervisor.loop = MagicMock()
        adapter._control_supervisor = supervisor
        future = MagicMock()
        future.result.return_value = _ack(["learning_rate"])

        def _future(coro, loop):
            coro.close()
            return future

        monkeypatch.setattr("backend.cascor_service_adapter.asyncio.run_coroutine_threadsafe", _future)
        adapter._client.update_params.return_value = {"candidate_epochs": 50, "applied": ["candidate_epochs"], "skipped": []}
        with (
            patch("settings.get_settings", return_value=SimpleNamespace(use_websocket_set_params=True, ws_set_params_timeout=1.0)),
            patch.object(adapter, "_verify_apply_roundtrip", return_value=None),
        ):
            result = adapter.apply_params(nn_learning_rate=0.05, cn_training_iterations=50)
        assert result["ok"] is True
        assert result["applied"] == ["cn_training_iterations"]
        assert result["data"].get("type") != "command_response"
        assert "command" not in result["data"].get("data", {})
