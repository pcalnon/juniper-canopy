"""F-CANOPY-014 regression: the replay player must build ABSOLUTE control URLs
when the runtime config omits ``api_base_url`` -- which it does.

Found live in the canopy E2E arc (juniper-ml evidence note): the panel
initialised ``_api_base_url`` with an empty-string fallback, so every control
POST targeted ``"/api/v1/snapshots/<id>/replay/control"`` and ``requests``
rejected it verbatim (``Invalid URL ...: No scheme supplied``) -- play / pause /
seek / speed / range / stop were all dead while the backend was fine. Its two
sibling panels fall back to this service's own port; the replay player now does
the same.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

import pytest

from frontend.components.replay_player_panel import ReplayPlayerPanel
from settings import get_settings


def _expected_base() -> str:
    return f"http://127.0.0.1:{get_settings().server.port}"


@pytest.mark.unit
class TestF014ReplayApiBaseUrl:
    def test_default_api_base_url_uses_configured_server_port(self):
        # Same contract the network editor already pins for itself.
        panel = ReplayPlayerPanel({}, component_id="rp-f014")
        assert panel._api_base_url == _expected_base()
        assert panel._api_base_url.startswith("http://")

    def test_explicit_api_base_url_still_wins(self):
        panel = ReplayPlayerPanel({"api_base_url": "http://cfg.local:9"}, component_id="rp-f014")
        assert panel._api_base_url == "http://cfg.local:9"

    @pytest.mark.parametrize("action", ["play", "pause", "seek", "speed", "range", "stop"])
    def test_every_control_posts_to_an_absolute_url_by_default(self, action):
        panel = ReplayPlayerPanel({}, component_id="rp-f014")
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"ok": True}
        with patch("requests.post", return_value=resp) as post:
            result = panel._invoke_replay_control("snap_1", action, index=3)
        assert result == {"success": True, "data": {"ok": True}}
        url = post.call_args.args[0]
        # The parent produced "/api/v1/snapshots/snap_1/replay/control" -- no scheme, no host.
        assert url == f"{_expected_base()}/api/v1/snapshots/snap_1/replay/control"
