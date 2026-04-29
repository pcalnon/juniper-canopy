"""CAN-019: tests for the walkthrough tutorial config + JS asset wiring.

Source-level invariant tests (matching the pattern used elsewhere in
``test_phase_b_bridge.py`` etc.) — these don't try to drive the live JS
overlay, but they catch the most common regressions:

- A walkthrough step pointing at an ID that no longer exists in the layout
- The JS asset losing its public ``window._juniperWalkthrough`` API
- The dashboard manager forgetting to register the launch / driver
  clientside callbacks
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2]


@pytest.fixture
def steps():
    from frontend.walkthrough_steps import WALKTHROUGH_STEPS, get_walkthrough_steps

    return WALKTHROUGH_STEPS, get_walkthrough_steps


@pytest.fixture
def js_source():
    return (_SRC / "frontend" / "assets" / "tutorial_walkthrough.js").read_text(encoding="utf-8")


@pytest.fixture
def dashboard_manager_source():
    return (_SRC / "frontend" / "dashboard_manager.py").read_text(encoding="utf-8")


@pytest.fixture
def tutorial_panel_source():
    return (_SRC / "frontend" / "components" / "tutorial_panel.py").read_text(encoding="utf-8")


class TestWalkthroughStepConfig:
    """Schema invariants on the static step list."""

    def test_step_list_non_empty(self, steps):
        steps_const, _ = steps
        assert len(steps_const) >= 3, "Walkthrough should have at least a few steps to be useful"

    def test_every_step_has_required_keys(self, steps):
        steps_const, _ = steps
        required = {"target", "title", "body", "placement"}
        for i, step in enumerate(steps_const):
            missing = required - set(step.keys())
            assert not missing, f"Step {i} ({step.get('title')!r}) missing keys: {missing}"

    def test_placements_are_valid(self, steps):
        steps_const, _ = steps
        valid = {"top", "bottom", "left", "right", "center"}
        for step in steps_const:
            assert step["placement"] in valid, f"Bad placement {step['placement']!r}"

    def test_titles_and_bodies_non_empty(self, steps):
        steps_const, _ = steps
        for step in steps_const:
            assert step["title"].strip(), "Empty title"
            assert step["body"].strip(), "Empty body"

    def test_get_walkthrough_steps_returns_a_copy(self, steps):
        """Defensive — callers serialize to JSON; mutation on the returned
        list must not bleed back into the module-level constant."""
        steps_const, get = steps
        copy = get()
        copy.append({"target": "x", "title": "x", "body": "x", "placement": "top"})
        assert len(copy) == len(steps_const) + 1
        # Original list unchanged.
        recheck = get()
        assert len(recheck) == len(steps_const)


class TestWalkthroughTargetsExistInLayout:
    """Every step's `target` ID must appear somewhere in the dashboard
    layout source (or be the special ``__center__`` sentinel). Catches
    drift when an ID gets renamed without updating the walkthrough."""

    def test_targets_present_in_layout_source(self, steps, dashboard_manager_source, tutorial_panel_source):
        steps_const, _ = steps
        # The dashboard layout is split across dashboard_manager.py and
        # individual component files. Concatenate the relevant sources.
        haystack = dashboard_manager_source + "\n" + tutorial_panel_source
        for fname in ("dataset_plotter.py", "network_visualizer.py", "connection_indicator.py"):
            path = _SRC / "frontend" / "components" / fname
            if path.exists():
                haystack += "\n" + path.read_text(encoding="utf-8")

        # Component IDs are sometimes built via f-strings like
        # ``f"{self.component_id}-depth-slider-container"``. Substring matching
        # the full ``"network-visualizer-depth-slider-container"`` would miss
        # those — but the suffix after the component prefix is always present
        # as a literal in the layout source. Match by stripping each known
        # component-id prefix and looking for the remainder.
        known_component_prefixes = (
            "network-visualizer-",
            "dataset-plotter-",
            "metrics-panel-",
            "candidate-metrics-panel-",
            "decision-boundary-",
            "tutorial-panel-",
            "ws-",
        )
        for step in steps_const:
            tgt = step["target"]
            if tgt == "__center__":
                continue
            if tgt in haystack:
                continue
            # Try to match a known suffix.
            matched = False
            for prefix in known_component_prefixes:
                if tgt.startswith(prefix):
                    suffix = tgt[len(prefix) - 1 :]  # keep leading "-"
                    if suffix and suffix in haystack:
                        matched = True
                        break
            assert matched, f"Walkthrough target {tgt!r} not found in any layout source (full or suffix match)"


class TestWalkthroughJsAsset:
    """Source-level invariants on the JS asset."""

    def test_public_api_exposed(self, js_source):
        assert "window._juniperWalkthrough" in js_source
        assert "show:" in js_source or "show: function" in js_source
        assert "hide:" in js_source or "hide: function" in js_source

    def test_iife_wrapper(self, js_source):
        """The asset must be wrapped in an IIFE so its locals don't leak."""
        assert js_source.lstrip().startswith("/**") or js_source.lstrip().startswith("(function()")
        assert "(function()" in js_source

    def test_strict_mode(self, js_source):
        assert '"use strict"' in js_source

    def test_esc_dismisses(self, js_source):
        """Esc must dismiss the overlay — accessibility expectation."""
        assert '"Escape"' in js_source or "'Escape'" in js_source

    def test_text_content_used_for_user_strings(self, js_source):
        """User-supplied step strings must be set via .textContent, not
        innerHTML, so a malicious config can't inject markup."""
        assert ".textContent =" in js_source

    def test_localstorage_persistence(self, js_source):
        """Skipping marks the tour completed in localStorage so we don't
        auto-prompt the same user repeatedly on subsequent loads."""
        assert "localStorage" in js_source
        assert "STORAGE_KEY" in js_source

    def test_target_retry_for_async_render(self, js_source):
        """findTarget retries — covers the case where the step targets an
        element that hasn't mounted yet (e.g. a tab content not yet active)."""
        assert "TARGET_RETRY_MS" in js_source
        assert "TARGET_RETRY_MAX_ATTEMPTS" in js_source


class TestWalkthroughDashboardWiring:
    """The dashboard manager must register both clientside callbacks."""

    def test_steps_store_present(self, dashboard_manager_source):
        assert "walkthrough-steps-store" in dashboard_manager_source

    def test_state_store_present(self, dashboard_manager_source):
        assert "walkthrough-state-store" in dashboard_manager_source

    def test_launch_button_callback_registered(self, dashboard_manager_source):
        assert "walkthrough-launch-btn" in dashboard_manager_source

    def test_driver_callback_calls_show_and_hide(self, dashboard_manager_source):
        """The state→overlay driver must call both .show() and .hide()."""
        assert "_juniperWalkthrough.show" in dashboard_manager_source
        assert "_juniperWalkthrough.hide" in dashboard_manager_source

    def test_steps_loaded_from_python_helper(self, dashboard_manager_source):
        """``walkthrough-steps-store`` should pull from the Python helper
        rather than embedding the steps as a literal — single source of truth."""
        assert "_walkthrough_steps()" in dashboard_manager_source or "get_walkthrough_steps" in dashboard_manager_source


class TestWalkthroughTutorialPanelButton:
    """The Tutorial tab must expose the launch button."""

    def test_button_id_present(self, tutorial_panel_source):
        assert "walkthrough-launch-btn" in tutorial_panel_source

    def test_button_label_human_readable(self, tutorial_panel_source):
        assert "Take a guided tour" in tutorial_panel_source
