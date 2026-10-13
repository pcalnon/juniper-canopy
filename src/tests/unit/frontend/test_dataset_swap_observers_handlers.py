"""P2-7 (Issue #3) — Unit tests for dataset_swap observer handlers.

Three UI deliverables share a single events store
(``dataset-swap-events-store``) populated by DashboardManager's polling
callback. This file tests the four handler methods that consume + write
to the store:

  * ``DashboardManager._poll_dataset_swap_events_handler`` — fetches
    from ``/api/history/dataset_swaps`` and writes the store.
  * ``ReplayPlayerPanel._render_swap_events_graph_handler`` — turns
    the store contents into a Plotly figure + count label for the
    replay timeline marker.
  * ``HDF5SnapshotsPanel._render_dataset_swap_diffs_handler`` —
    renders paired-diff cards for the History collapse.
  * ``HDF5SnapshotsPanel._compute_swap_snapshot_roles`` — builds the
    snapshot-id → role map used to inject Pre-swap / Post-swap badges
    in the snapshots table.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import dash
import dash_bootstrap_components as dbc
import pytest
import requests

from frontend.components.hdf5_snapshots_panel import HDF5SnapshotsPanel
from frontend.components.replay_player_panel import ReplayPlayerPanel
from frontend.dashboard_manager import DashboardManager


def _make_event(i: int = 0, pre_id: str = "snap_pre_0", post_id: str = "snap_post_0", before_type: str = "spirals", after_type: str = "moons"):
    """Helper to build a minimal §3.9-shaped event."""
    return {
        "timestamp": f"2026-05-15T12:00:0{i}+00:00",
        "before_cfg": {"dataset_type": before_type},
        "after_cfg": {"dataset_type": after_type},
        "arch_changes": {"input_delta": 2, "output_delta": 0, "hidden_preserved": 5, "appended_nodes": {"input": 2, "output": 0}, "prepended_layers": [], "abandoned_candidate_pool_size": 0, "active_output_dim": 2},
        "pre_swap_snapshot_id": pre_id,
        "post_swap_snapshot_id": post_id,
    }


# ---------------------------------------------------------------------------
# DashboardManager._poll_dataset_swap_events_handler
# ---------------------------------------------------------------------------


@pytest.fixture
def dm():
    """DashboardManager skeleton for handler-level tests."""
    manager = DashboardManager.__new__(DashboardManager)
    manager.logger = MagicMock()
    manager._api_base_url = "http://test.local"
    return manager


class TestPollDatasetSwapEventsHandler:
    def test_200_response_writes_events_list(self, dm):
        """Happy path: ``/api/history/dataset_swaps`` returns 200 with
        ``data.events`` → store gets ``{"events": [...]}``."""
        events_payload = [_make_event(0), _make_event(1)]
        with patch("frontend.dashboard_manager.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"data": {"events": events_payload}}
            result = dm._poll_dataset_swap_events_handler(n_intervals=1)
        assert result == {"events": events_payload}

    def test_empty_response_writes_empty_list(self, dm):
        with patch("frontend.dashboard_manager.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"data": {"events": []}}
            result = dm._poll_dataset_swap_events_handler(n_intervals=1)
        assert result == {"events": []}

    def test_missing_data_section_falls_back_safely(self, dm):
        """Defensive — if the response is missing the ``data`` envelope
        the handler still returns a structurally-valid store payload."""
        with patch("frontend.dashboard_manager.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {}
            result = dm._poll_dataset_swap_events_handler(n_intervals=1)
        assert result == {"events": []}

    def test_non_200_returns_no_update(self, dm):
        """Backend hiccup must not blow away the prior store value."""
        with patch("frontend.dashboard_manager.requests.get") as mock_get:
            mock_get.return_value.status_code = 502
            result = dm._poll_dataset_swap_events_handler(n_intervals=1)
        assert result is dash.no_update

    def test_request_exception_returns_no_update(self, dm):
        with patch("frontend.dashboard_manager.requests.get", side_effect=requests.RequestException("network down")):
            result = dm._poll_dataset_swap_events_handler(n_intervals=1)
        assert result is dash.no_update


# ---------------------------------------------------------------------------
# ReplayPlayerPanel._render_swap_events_graph_handler
# ---------------------------------------------------------------------------


@pytest.fixture
def replay_panel():
    """ReplayPlayerPanel skeleton — only the handler attrs are needed."""
    panel = ReplayPlayerPanel.__new__(ReplayPlayerPanel)
    panel.logger = MagicMock()
    panel.component_id = "replay-player"
    return panel


class TestRenderSwapEventsGraphHandler:
    def test_no_events_returns_empty_state_annotation(self, replay_panel):
        figure, count_label = replay_panel._render_swap_events_graph_handler(store_data={"events": []})
        assert count_label == "0 events"
        # No scatter traces; annotation explains the empty state.
        assert figure["data"] == []
        ann_text = figure["layout"]["annotations"][0]["text"]
        assert "No dataset swaps recorded" in ann_text

    def test_none_store_data_treated_as_empty(self, replay_panel):
        figure, count_label = replay_panel._render_swap_events_graph_handler(store_data=None)
        assert count_label == "0 events"
        assert figure["data"] == []

    def test_single_event_renders_one_marker(self, replay_panel):
        figure, count_label = replay_panel._render_swap_events_graph_handler(store_data={"events": [_make_event(0)]})
        assert count_label == "1 event"
        assert len(figure["data"]) == 1
        trace = figure["data"][0]
        assert trace["type"] == "scatter"
        assert trace["mode"] == "markers"
        assert len(trace["x"]) == 1
        # Hover text should mention the before→after dataset types.
        hover = trace["hovertext"][0]
        assert "spirals" in hover and "moons" in hover

    def test_multiple_events_render_multiple_markers(self, replay_panel):
        events = [_make_event(0), _make_event(1, before_type="moons", after_type="circles"), _make_event(2)]
        figure, count_label = replay_panel._render_swap_events_graph_handler(store_data={"events": events})
        assert count_label == "3 events"
        assert len(figure["data"][0]["x"]) == 3

    def test_hover_text_includes_arch_deltas(self, replay_panel):
        figure, _ = replay_panel._render_swap_events_graph_handler(store_data={"events": [_make_event(0)]})
        hover = figure["data"][0]["hovertext"][0]
        # arch_changes input_delta=2 and hidden_preserved=5 from _make_event.
        assert "input Δ +2" in hover
        assert "hidden 5 preserved" in hover

    # P2-7 follow-up: augment-render with the loaded snapshot's own
    # history. Both stores are independent; either group may be empty.
    def test_snapshot_store_only_renders_snapshot_trace(self, replay_panel):
        """No live events but a loaded snapshot with swaps → one
        snapshot trace, count label tallies snapshot side only."""
        figure, count_label = replay_panel._render_swap_events_graph_handler(
            store_data={"events": []},
            snapshot_store_data={"events": [_make_event(0), _make_event(1)]},
        )
        assert len(figure["data"]) == 1
        assert figure["data"][0]["name"] == "Snapshot"
        assert count_label == "2 events"

    def test_both_stores_render_two_traces_with_breakdown(self, replay_panel):
        """When both groups have events the figure shows two traces and
        the count label breaks down live vs snapshot — matters because
        a user reviewing a stored snapshot wants to know which markers
        come from the snapshot's own training run vs the live feed."""
        figure, count_label = replay_panel._render_swap_events_graph_handler(
            store_data={"events": [_make_event(0)]},
            snapshot_store_data={"events": [_make_event(1), _make_event(2)]},
        )
        assert len(figure["data"]) == 2
        names = {t["name"] for t in figure["data"]}
        assert names == {"Live", "Snapshot"}
        assert count_label == "3 events (1 live + 2 snapshot)"

    def test_snapshot_marker_uses_distinct_symbol_and_y(self, replay_panel):
        """Live + snapshot traces must render distinguishably — live as
        diamond on y=0.5, snapshot as circle on y=-0.5 so overlapping
        timestamps stay legible."""
        figure, _ = replay_panel._render_swap_events_graph_handler(
            store_data={"events": [_make_event(0)]},
            snapshot_store_data={"events": [_make_event(0)]},
        )
        by_name = {t["name"]: t for t in figure["data"]}
        assert by_name["Live"]["marker"]["symbol"] == "diamond"
        assert by_name["Snapshot"]["marker"]["symbol"] == "circle"
        assert by_name["Live"]["y"] == [0.5]
        assert by_name["Snapshot"]["y"] == [-0.5]

    def test_empty_in_both_renders_no_swaps_annotation(self, replay_panel):
        """Both stores empty (or None) → annotation, not a stale partial figure."""
        figure, count_label = replay_panel._render_swap_events_graph_handler(
            store_data=None,
            snapshot_store_data={"events": []},
        )
        assert count_label == "0 events"
        assert figure["data"] == []

    def test_snapshot_hover_text_labelled(self, replay_panel):
        """Snapshot hover text must include the ``Snapshot`` label so
        users can tell snapshot-history markers from live ones at the
        hover level even without consulting the legend."""
        figure, _ = replay_panel._render_swap_events_graph_handler(
            store_data={"events": []},
            snapshot_store_data={"events": [_make_event(0)]},
        )
        hover = figure["data"][0]["hovertext"][0]
        assert "Snapshot ·" in hover


# ---------------------------------------------------------------------------
# DashboardManager._hydrate_loaded_snapshot_swap_events_handler (P2-7 follow-up)
# ---------------------------------------------------------------------------


class TestHydrateLoadedSnapshotSwapEventsHandler:
    def test_no_session_with_no_prior_returns_no_update(self, dm):
        """Initial render: no active snapshot loaded → leave the store
        at its construction-time default rather than producing an
        empty-events payload that disrupts cache equality."""
        result = dm._hydrate_loaded_snapshot_swap_events_handler(session=None, prior={"events": [], "snapshot_id": None})
        assert result is dash.no_update

    def test_session_with_snapshot_id_fetches_events(self, dm):
        """A new active snapshot triggers a GET against
        ``/api/snapshots/{id}/history/dataset_swaps`` and the store
        captures both the events list and the snapshot_id."""
        events_payload = [_make_event(0), _make_event(1)]
        with patch("frontend.dashboard_manager.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"data": {"events": events_payload}}
            result = dm._hydrate_loaded_snapshot_swap_events_handler(
                session={"snapshot_id": "snap_a", "fsm_state": "Replaying"},
                prior={"events": [], "snapshot_id": None},
            )
        assert result == {"events": events_payload, "snapshot_id": "snap_a"}

    def test_same_snapshot_id_is_a_noop(self, dm):
        """Speed / seek / play-state mutations on the same active
        snapshot leave the store untouched — without this guard the
        snapshot history would re-fetch on every replay control click."""
        result = dm._hydrate_loaded_snapshot_swap_events_handler(
            session={"snapshot_id": "snap_a", "fsm_state": "Replaying", "speed": 2.0},
            prior={"events": [_make_event(0)], "snapshot_id": "snap_a"},
        )
        assert result is dash.no_update

    def test_cleared_session_resets_store_when_prior_loaded(self, dm):
        """When the replay session clears (snapshot_id → None) the
        store flushes to the empty-default so the timeline drops the
        snapshot trace group cleanly."""
        result = dm._hydrate_loaded_snapshot_swap_events_handler(
            session=None,
            prior={"events": [_make_event(0)], "snapshot_id": "snap_a"},
        )
        assert result == {"events": [], "snapshot_id": None}

    def test_non_200_returns_empty_pinned_to_snapshot(self, dm):
        """Backend error (cascor 404, canopy 502, ...) — keep the new
        snapshot_id but record an empty event list. The timeline
        degrades to the live-event-only render rather than displaying
        a stale snapshot's history under the new snapshot's label."""
        with patch("frontend.dashboard_manager.requests.get") as mock_get:
            mock_get.return_value.status_code = 502
            result = dm._hydrate_loaded_snapshot_swap_events_handler(
                session={"snapshot_id": "snap_missing"},
                prior={"events": [_make_event(0)], "snapshot_id": "snap_old"},
            )
        assert result == {"events": [], "snapshot_id": "snap_missing"}

    def test_request_exception_returns_empty_pinned_to_snapshot(self, dm):
        with patch("frontend.dashboard_manager.requests.get", side_effect=requests.RequestException("net down")):
            result = dm._hydrate_loaded_snapshot_swap_events_handler(
                session={"snapshot_id": "snap_a"},
                prior={"events": [], "snapshot_id": None},
            )
        assert result == {"events": [], "snapshot_id": "snap_a"}


# ---------------------------------------------------------------------------
# DashboardManager._merge_ws_dataset_swap_events_handler (P2-7 WS push)
# ---------------------------------------------------------------------------


class TestMergeWsDatasetSwapEventsHandler:
    def test_empty_buffer_returns_no_update(self):
        """Idle fast-update-interval tick — buffer is empty. Returning
        ``dash.no_update`` avoids cache churn and a needless store
        rewrite when there's nothing to merge."""
        result = DashboardManager._merge_ws_dataset_swap_events_handler(
            ws_buffer={"events": []},
            current_store={"events": []},
        )
        assert result is dash.no_update

    def test_buffer_none_returns_no_update(self):
        """Defensive — initial-state buffer dict can be None / missing."""
        result = DashboardManager._merge_ws_dataset_swap_events_handler(ws_buffer=None, current_store=None)
        assert result is dash.no_update

    def test_first_ws_event_appended_to_empty_store(self):
        """WS-push arriving before the first slow-poll completes →
        store gains the event so the timeline / paired-diff / badges
        update inside one fast-update-interval tick."""
        ev = _make_event(0, pre_id="snap_pre_0")
        result = DashboardManager._merge_ws_dataset_swap_events_handler(
            ws_buffer={"events": [ev]},
            current_store={"events": []},
        )
        assert result == {"events": [ev]}

    def test_dedupe_keys_off_timestamp_and_pre_swap_id(self):
        """The slow-poll wrote the event first; the WS push arrives
        immediately after with the same payload. Result must be one
        event, not two."""
        ev = _make_event(0, pre_id="snap_pre_0")
        result = DashboardManager._merge_ws_dataset_swap_events_handler(
            ws_buffer={"events": [ev]},
            current_store={"events": [ev]},
        )
        assert result == {"events": [ev]}

    def test_distinct_events_with_same_timestamp_are_both_kept(self):
        """Synthetic-timestamp edge case: two events sharing a
        timestamp but differing on ``pre_swap_snapshot_id`` are
        distinct swaps and must both survive the merge."""
        ev_a = _make_event(0, pre_id="snap_pre_A")
        ev_b = _make_event(0, pre_id="snap_pre_B")
        result = DashboardManager._merge_ws_dataset_swap_events_handler(
            ws_buffer={"events": [ev_b]},
            current_store={"events": [ev_a]},
        )
        assert result["events"] == [ev_a, ev_b]

    def test_result_sorted_by_timestamp(self):
        """A WS-push event that pre-dates an existing store entry (e.g.
        a delayed broadcast) lands in the right chronological slot so
        the timeline figure renders markers left-to-right correctly."""
        early = _make_event(0, pre_id="snap_pre_early")
        early["timestamp"] = "2026-05-15T10:00:00+00:00"
        late = _make_event(0, pre_id="snap_pre_late")
        late["timestamp"] = "2026-05-15T12:00:00+00:00"
        result = DashboardManager._merge_ws_dataset_swap_events_handler(
            ws_buffer={"events": [early]},
            current_store={"events": [late]},
        )
        timestamps = [e["timestamp"] for e in result["events"]]
        assert timestamps == sorted(timestamps)

    def test_event_without_timestamp_falls_back_to_append(self):
        """Defensive — a malformed event without ``timestamp`` would
        otherwise key off ``(None, pre_id)`` which would alias different
        events. Append unconditionally so a single bad frame doesn't
        suppress real subsequent ones."""
        bad = {"timestamp": None, "pre_swap_snapshot_id": "snap_pre_X", "before_cfg": {}, "after_cfg": {}, "arch_changes": {}}
        result = DashboardManager._merge_ws_dataset_swap_events_handler(
            ws_buffer={"events": [bad]},
            current_store={"events": []},
        )
        assert result == {"events": [bad]}

    def test_non_dict_buffer_entries_skipped_silently(self):
        """Defensive — pathological buffer shouldn't crash the merger."""
        ev = _make_event(0, pre_id="snap_pre_0")
        result = DashboardManager._merge_ws_dataset_swap_events_handler(
            ws_buffer={"events": ["garbage", None, ev]},
            current_store={"events": []},
        )
        assert result == {"events": [ev]}


# ---------------------------------------------------------------------------
# HDF5SnapshotsPanel._compute_swap_snapshot_roles
# ---------------------------------------------------------------------------


@pytest.fixture
def snapshots_panel():
    panel = HDF5SnapshotsPanel.__new__(HDF5SnapshotsPanel)
    panel.logger = MagicMock()
    panel.component_id = "hdf5-snapshots"
    return panel


class TestComputeSwapSnapshotRoles:
    def test_empty_events_returns_empty_map(self, snapshots_panel):
        assert snapshots_panel._compute_swap_snapshot_roles([]) == {}

    def test_single_event_creates_pre_and_post_roles(self, snapshots_panel):
        roles = snapshots_panel._compute_swap_snapshot_roles([_make_event(0, pre_id="A", post_id="B")])
        assert roles == {"A": ("Pre-swap",), "B": ("Post-swap",)}

    def test_snapshot_can_be_both_pre_and_post(self, snapshots_panel):
        """A single snapshot may appear as both pre-swap (one event) and
        post-swap (a different event). Both badges should render in a
        stable order."""
        events = [
            _make_event(0, pre_id="shared", post_id="post1"),
            _make_event(1, pre_id="pre2", post_id="shared"),
        ]
        roles = snapshots_panel._compute_swap_snapshot_roles(events)
        assert roles["shared"] == ("Pre-swap", "Post-swap")

    def test_skips_non_dict_entries_defensively(self, snapshots_panel):
        """A malformed event in the list must not break the badge
        computation for the rest."""
        events = [_make_event(0, pre_id="A", post_id="B"), "not a dict", {"timestamp": "T", "pre_swap_snapshot_id": "C"}]
        roles = snapshots_panel._compute_swap_snapshot_roles(events)
        assert roles == {"A": ("Pre-swap",), "B": ("Post-swap",), "C": ("Pre-swap",)}

    def test_none_snapshot_ids_filtered_out(self, snapshots_panel):
        """Events with None ID fields (P2-2 placeholder branch) don't
        produce empty-string entries in the map."""
        events = [{"pre_swap_snapshot_id": None, "post_swap_snapshot_id": "real"}]
        roles = snapshots_panel._compute_swap_snapshot_roles(events)
        assert roles == {"real": ("Post-swap",)}


# ---------------------------------------------------------------------------
# HDF5SnapshotsPanel._render_dataset_swap_diffs_handler
# ---------------------------------------------------------------------------


class TestRenderDatasetSwapDiffsHandler:
    def test_no_events_returns_muted_placeholder(self, snapshots_panel):
        result = snapshots_panel._render_dataset_swap_diffs_handler(store_data={"events": []})
        # html.Div with "No dataset swaps recorded yet." text.
        assert result.children == "No dataset swaps recorded yet."

    def test_none_store_data_returns_muted_placeholder(self, snapshots_panel):
        result = snapshots_panel._render_dataset_swap_diffs_handler(store_data=None)
        assert result.children == "No dataset swaps recorded yet."

    def test_single_event_renders_one_card(self, snapshots_panel):
        result = snapshots_panel._render_dataset_swap_diffs_handler(store_data={"events": [_make_event(0)]})
        assert isinstance(result, list)
        assert len(result) == 1
        card = result[0]
        assert isinstance(card, dbc.Card)

    def test_card_has_before_and_after_columns(self, snapshots_panel):
        """The paired-diff card body must contain both before_cfg and
        after_cfg side-by-side (Q3 hybrid UX)."""
        result = snapshots_panel._render_dataset_swap_diffs_handler(store_data={"events": [_make_event(0, before_type="X", after_type="Y")]})
        card_str = str(result[0])
        # Both type strings should appear somewhere in the card structure.
        assert "X" in card_str and "Y" in card_str

    def test_card_includes_restore_buttons_for_both_snapshot_ids(self, snapshots_panel):
        """Each card has "Restore from pre-swap" / "Restore from
        post-swap" buttons wired to the existing snapshot-restore
        plumbing via pattern-matched IDs."""
        ev = _make_event(0, pre_id="snap_pre_42", post_id="snap_post_42")
        result = snapshots_panel._render_dataset_swap_diffs_handler(store_data={"events": [ev]})
        card_str = str(result[0])
        assert "snap_pre_42" in card_str
        assert "snap_post_42" in card_str

    def test_card_renders_arch_deltas_as_badges(self, snapshots_panel):
        """The arch_changes ribbon shows input/output deltas + hidden
        preserved count as bootstrap badges."""
        result = snapshots_panel._render_dataset_swap_diffs_handler(store_data={"events": [_make_event(0)]})
        card_str = str(result[0])
        # arch_changes from _make_event: input_delta=2, output_delta=0, hidden_preserved=5
        assert "input Δ +2" in card_str
        assert "output Δ +0" in card_str
        assert "5 hidden preserved" in card_str

    def test_multiple_events_render_in_order(self, snapshots_panel):
        events = [_make_event(0, before_type="A", after_type="B"), _make_event(1, before_type="B", after_type="C"), _make_event(2, before_type="C", after_type="D")]
        result = snapshots_panel._render_dataset_swap_diffs_handler(store_data={"events": events})
        assert len(result) == 3
