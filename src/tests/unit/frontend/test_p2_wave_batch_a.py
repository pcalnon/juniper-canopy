#!/usr/bin/env python
"""P2 fix wave, batch A — F-CANOPY-001 / -013 / -015 / -034.

Ledger: juniper-ml notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md

Four independent, separately root-caused P2s that share one shape: **a value is read
from, or written to, the wrong place, and the wrong answer is quiet.** Nothing throws;
the UI just reports something false (a stale glyph, `index None`, a V1 badge on a V2
snapshot) or does work nobody consumes.

Verified against the parent commit (9f6fac9): **21 of the 24 tests fail there.** The
three that pass are marked in their own docstrings — they are forward guards against
over-correction (don't fix the glyph by adding a second writer; don't "helpfully" move
the replay fields that were already read correctly; don't remove the live stats interval
as collateral damage), not reproductions of the defects.
"""

import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from frontend.components.network_editor_panel import NetworkEditorPanel  # noqa: E402
from frontend.components.replay_player_panel import ReplayPlayerPanel  # noqa: E402
from frontend.dashboard_manager import DashboardManager  # noqa: E402


@pytest.fixture(scope="module")
def dashboard():
    return DashboardManager({})


def _output_specs(entry):
    """Exact ``id.property`` outputs of one ``app._callback_list`` entry.

    EXACT parsing, never substring matching — Dash renders a multi-output key as
    ``..a.prop...b.prop..`` and appends ``@<hash>`` to allow_duplicate outputs.
    Mirrors the helper in ``test_poll_gating.py``.
    """
    raw = str(entry["output"])
    parts = raw[2:-2].split("...") if raw.startswith("..") and raw.endswith("..") else [raw]
    return {p.split("@", 1)[0] for p in parts if p}


def _entries_writing(dashboard, output):
    return [e for e in dashboard.app._callback_list if output in _output_specs(e)]


# ----------------------------------------------------------------------------------
# F-CANOPY-001 — dark-mode toggle glyph not synced from the persisted store on mount
# ----------------------------------------------------------------------------------


@pytest.mark.unit
class TestF001DarkModeGlyphSurvivesReload:
    """Toggle dark → reload → theme restored dark, but the button still rendered 🌙.

    The glyph was written only by ``toggle_dark_mode``, which is
    ``prevent_initial_call=True`` — so no mount path ever wrote it.
    """

    GLYPH = "dark-mode-toggle.children"

    def test_glyph_is_written_by_a_mount_capable_callback(self, dashboard):
        """The whole fix: something with prevent_initial_call=False must own the glyph."""
        writers = _entries_writing(dashboard, self.GLYPH)
        assert writers, "nothing writes the toggle glyph"
        assert any(w.get("prevent_initial_call") is False for w in writers), "every writer of the toggle glyph is prevent_initial_call=True — the glyph cannot be correct on mount, which is F-CANOPY-001"

    def test_glyph_has_exactly_one_writer(self, dashboard):
        """Forward guard (passes on the parent, which also had exactly one writer).

        The obvious wrong fix is to ADD a mount-time writer alongside the existing
        click-time one. ``dark-mode-toggle.children`` keeps a single owner: a duplicate
        writer is the F-CANOPY-018 / F-CANOPY-027 two-writer class this arc has been
        removing. Paired with ``test_glyph_is_written_by_a_mount_capable_callback``,
        which is the half that fails on the parent, the two pin "exactly one writer,
        and it is the mount-capable one".
        """
        writers = _entries_writing(dashboard, self.GLYPH)
        assert len(writers) == 1, f"the toggle glyph has {len(writers)} writers; it must have exactly one"

    def test_glyph_writer_is_driven_by_the_persisted_store(self, dashboard):
        """Derived from the flag, so a reload paints it from what was persisted."""
        writer = _entries_writing(dashboard, self.GLYPH)[0]
        input_ids = {d["id"] if isinstance(d, dict) else getattr(d, "component_id", None) for d in writer.get("inputs") or []}
        assert "dark-mode-store" in input_ids, f"the glyph writer is not driven by dark-mode-store (inputs: {sorted(i for i in input_ids if i)})"

    def test_toggle_owns_only_the_flag(self, dashboard):
        """The click path writes the store; the glyph follows from it."""
        assert dashboard._toggle_dark_mode_handler(current_dark_mode=False) is True
        assert dashboard._toggle_dark_mode_handler(current_dark_mode=True) is False
        assert dashboard._toggle_dark_mode_handler(current_dark_mode=None) is True

    def test_icon_shows_the_mode_the_click_would_switch_to(self, dashboard):
        """Coverage relocated from the old tuple-returning toggle handler."""
        assert dashboard._dark_mode_icon(True) == "☀️"
        assert dashboard._dark_mode_icon(False) == "🌙"
        assert dashboard._dark_mode_icon(None) == "🌙"

    def test_layout_default_matches_the_light_glyph(self, dashboard):
        """First paint, before any callback settles, renders the layout default.

        It must equal the light-mode glyph, so the pre-hydration frame is not itself a
        lie — and so the mount write is a no-op rather than a visible flicker for the
        common (light) case.
        """
        assert dashboard._dark_mode_icon(False) == "🌙", "the light glyph drifted from the layout default in dashboard_manager.get_layout()"


# ----------------------------------------------------------------------------------
# F-CANOPY-013 — Network Editor success messages read keys off the response ENVELOPE
# ----------------------------------------------------------------------------------


@pytest.mark.unit
class TestF013NetworkEditorUnwrapsTheEnvelope:
    """A successful append reported ``index None (now None hidden units)``.

    ``_post_json`` returns ``{"success": True, "data": <whole body>}`` and cascor's body
    is itself ``{"status":…, "data": {…}, "meta":…}``, so the keys live one level
    deeper than the panel was reading.
    """

    @pytest.fixture
    def panel(self):
        return NetworkEditorPanel({})

    def test_unwraps_the_cascor_success_envelope(self, panel):
        result = {"success": True, "data": {"status": "success", "data": {"unit_index": 3, "num_hidden_units": 4}, "meta": {}}}
        payload = panel._envelope_payload(result)
        assert payload.get("unit_index") == 3
        assert payload.get("num_hidden_units") == 4

    def test_flat_body_passes_through(self, panel):
        """Tolerant: a non-enveloped body must keep working."""
        result = {"success": True, "data": {"unit_index": 7, "num_hidden_units": 8}}
        payload = panel._envelope_payload(result)
        assert payload.get("unit_index") == 7
        assert payload.get("num_hidden_units") == 8

    def test_a_data_key_that_is_not_an_envelope_is_not_unwrapped(self, panel):
        """Only unwrap on the real shape — a dict ``data`` alongside ``status``."""
        result = {"success": True, "data": {"unit_index": 1, "data": {"unrelated": True}}}
        assert panel._envelope_payload(result).get("unit_index") == 1

    @pytest.mark.parametrize("body", [None, [], "text", 0])
    def test_non_dict_bodies_are_safe(self, panel, body):
        assert panel._envelope_payload({"success": True, "data": body}) == {}

    def test_both_call_sites_use_the_helper(self):
        """The finding named a latent SECOND instance (the DELETE path); pin both."""
        src = Path(NetworkEditorPanel.__module__.replace(".", "/") + ".py")
        src = _SRC / src if not src.is_absolute() else src
        text = src.read_text(encoding="utf-8")
        assert text.count("self._envelope_payload(result)") == 2, "both the add-unit and remove-unit success paths must unwrap the envelope"
        assert 'data = result["data"]\n' not in text, "a raw envelope-root read is back in the network editor"


# ----------------------------------------------------------------------------------
# F-CANOPY-015 — replay player reads three session fields one nesting level too shallow
# ----------------------------------------------------------------------------------


@pytest.mark.unit
class TestF015ReplaySessionSummaryNesting:
    """The weights badge reported V1 for a V2 snapshot.

    The panel stores cascor's ``data`` block; ``range`` / ``speed`` /
    ``weights_available`` live in ``data["session"]``, one level deeper. Two of the
    three misreads were masked because their fallbacks coincide with the real values —
    only the badge was visible.
    """

    # The exact shape measured off the running service (finding F-CANOPY-015).
    DATA_BLOCK = {
        "fsm_state": "Replaying",
        "operation": "replay",
        "snapshot_id": "snap-1",
        "status": "ok",
        "time_index": {"current": 5, "snapshot_window": {"start_epoch": 0, "end_epoch": 40}},
        "training_params": {},
        "session": {
            "length": 41,
            "paused": False,
            "range": [3, 37],
            "snapshot_id": "snap-1",
            "speed": 2.0,
            "time_index": 5,
            "weight_sampling": "every",
            "weights_available": True,
        },
    }

    def test_summary_reads_the_nested_session_block(self):
        summary = ReplayPlayerPanel._session_summary(self.DATA_BLOCK)
        assert summary.get("weights_available") is True, "the V2 weights badge reads False from a V2 snapshot"
        assert summary.get("range") == [3, 37]
        assert summary.get("speed") == 2.0

    def test_flat_legacy_shape_still_resolves(self):
        """Matches ``_session_window``'s tolerance for the legacy/test shape."""
        flat = {"range": [1, 2], "speed": 4.0, "weights_available": True}
        assert ReplayPlayerPanel._session_summary(flat) == flat

    @pytest.mark.parametrize("session", [None, {}, [], "text"])
    def test_missing_or_wrong_typed_sessions_are_safe(self, session):
        assert ReplayPlayerPanel._session_summary(session) == ({} if session != {} else {})

    def test_the_correctly_read_fields_stay_on_the_data_block(self):
        """Forward guard (passes on the parent).

        ``fsm_state`` and the ``time_index`` window were already read off the block and
        were CORRECT. The fix must not "helpfully" move them into the nested block —
        that would break the two readouts that always worked.
        """
        assert self.DATA_BLOCK.get("fsm_state") == "Replaying"
        assert ReplayPlayerPanel._session_window(self.DATA_BLOCK) == (0, 40)
        assert ReplayPlayerPanel._session_current_index(self.DATA_BLOCK) == 5


# ----------------------------------------------------------------------------------
# F-CANOPY-034 — an inert store, written by nothing and read by nothing
# ----------------------------------------------------------------------------------


@pytest.mark.unit
class TestF034DeadStoreRemoved:
    """The writer went with the dead poller (canopy#507); the store outlived it."""

    def test_store_is_gone_from_the_layout(self, dashboard):
        assert "metrics-panel-network-stats-store" not in repr(dashboard.metrics_panel.get_layout()), "the inert network-stats store is back in the metrics panel layout"

    def test_dead_handler_is_gone(self, dashboard):
        """It was reachable only from its own five unit tests — the shape that makes
        dead code look live."""
        assert not hasattr(dashboard.metrics_panel, "_fetch_network_stats_handler"), "_fetch_network_stats_handler is back without a callback to call it"

    def test_the_live_stats_interval_was_not_collateral(self, dashboard):
        """Forward guard (passes on the parent).

        ``metrics-panel-stats-update-interval`` shares the dead poller's name-space but
        is NOT dead — it drives the training-state poll. Removing it would be the
        over-correction.
        """
        layout = repr(dashboard.metrics_panel.get_layout())
        assert "metrics-panel-stats-update-interval" in layout, "the live stats interval was removed as collateral damage"
