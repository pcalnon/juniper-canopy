#!/usr/bin/env python
"""Tests for sidebar contextual visibility callback and configuration."""

import pytest

from frontend.dashboard_manager import (
    SIDEBAR_SECTION_IDS,
    TAB_HEADER_MAP,
    TAB_SIDEBAR_CONFIG,
    DashboardManager,
)


class TestTabSidebarConfig:
    """Test TAB_SIDEBAR_CONFIG structure and completeness."""

    EXPECTED_TABS = [
        "metrics",
        "candidates",
        "topology",
        "boundaries",
        "dataset",
        "snapshots",
        "redis",
        "cassandra",
        "workers",
        "about",
        "parameters",
        "tutorial",
    ]

    def test_config_has_all_12_tabs(self):
        """TAB_SIDEBAR_CONFIG must have entries for all 12 tabs."""
        for tab in self.EXPECTED_TABS:
            assert tab in TAB_SIDEBAR_CONFIG, f"Missing tab: {tab}"

    def test_config_has_no_extra_tabs(self):
        """TAB_SIDEBAR_CONFIG must not have unexpected tab entries."""
        for tab in TAB_SIDEBAR_CONFIG:
            assert tab in self.EXPECTED_TABS, f"Unexpected tab: {tab}"

    @pytest.mark.parametrize("tab", ["snapshots", "redis", "cassandra", "workers", "about", "parameters", "tutorial"])
    def test_minimal_tabs_have_empty_config(self, tab):
        """Tabs with only Training Controls should have empty config dicts."""
        assert TAB_SIDEBAR_CONFIG[tab] == {}

    @pytest.mark.parametrize(
        "tab",
        ["metrics", "candidates", "topology", "boundaries", "dataset"],
    )
    def test_content_tabs_have_meta_params_card_visible(self, tab):
        """All content tabs must show the Meta Parameters card."""
        assert TAB_SIDEBAR_CONFIG[tab].get("sidebar-meta-params-card") is True

    @pytest.mark.parametrize(
        "tab",
        ["metrics", "candidates", "topology", "boundaries", "dataset"],
    )
    def test_content_tabs_have_apply_section_visible(self, tab):
        """All content tabs must show the Apply Parameters section."""
        assert TAB_SIDEBAR_CONFIG[tab].get("sidebar-apply-section") is True

    def test_metrics_tab_shows_nn_section(self):
        """Metrics tab should show Neural Network section."""
        config = TAB_SIDEBAR_CONFIG["metrics"]
        assert config["sidebar-nn-section"] is True
        assert config["sidebar-nn-top-params"] is True
        assert config["sidebar-nn-growth-triggers"] is True

    def test_metrics_tab_hides_cn_section(self):
        """Metrics tab should hide Candidate Nodes section."""
        config = TAB_SIDEBAR_CONFIG["metrics"]
        assert config["sidebar-cn-section"] is False

    def test_candidates_tab_shows_cn_section(self):
        """Candidates tab should show Candidate Nodes section."""
        config = TAB_SIDEBAR_CONFIG["candidates"]
        assert config["sidebar-cn-section"] is True
        assert config["sidebar-cn-pool-params"] is True
        assert config["sidebar-cn-pool-training"] is True

    def test_candidates_tab_hides_nn_section(self):
        """Candidates tab should hide Neural Network section."""
        config = TAB_SIDEBAR_CONFIG["candidates"]
        assert config["sidebar-nn-section"] is False

    def test_candidates_tab_shows_multi_node_layers(self):
        """Candidates tab should show Multi-Node Layers (outside NN collapse)."""
        config = TAB_SIDEBAR_CONFIG["candidates"]
        assert config["sidebar-nn-multi-node-layers"] is True

    def test_dataset_tab_shows_spiral_dataset(self):
        """Dataset tab should show Spiral Dataset section."""
        config = TAB_SIDEBAR_CONFIG["dataset"]
        assert config["sidebar-nn-spiral-dataset"] is True

    def test_boundaries_tab_shows_network_info(self):
        """Boundaries tab should show Network Information."""
        config = TAB_SIDEBAR_CONFIG["boundaries"]
        assert config["sidebar-network-info-section"] is True


class TestSidebarSectionIds:
    """Test SIDEBAR_SECTION_IDS list completeness."""

    def test_section_ids_count(self):
        """Should have 14 section IDs."""
        assert len(SIDEBAR_SECTION_IDS) == 14

    def test_all_config_keys_present_in_section_ids(self):
        """Every key used in TAB_SIDEBAR_CONFIG must be in SIDEBAR_SECTION_IDS."""
        all_keys = set()
        for config in TAB_SIDEBAR_CONFIG.values():
            all_keys.update(config.keys())
        for key in all_keys:
            assert key in SIDEBAR_SECTION_IDS, f"Config key '{key}' not in SIDEBAR_SECTION_IDS"

    def test_no_duplicate_section_ids(self):
        """Section IDs must be unique."""
        assert len(SIDEBAR_SECTION_IDS) == len(set(SIDEBAR_SECTION_IDS))


class TestTabHeaderMap:
    """Test TAB_HEADER_MAP configuration."""

    def test_metrics_header(self):
        assert TAB_HEADER_MAP["metrics"] == "Network Parameters"

    def test_topology_header(self):
        assert TAB_HEADER_MAP["topology"] == "Network Parameters"

    def test_candidates_header(self):
        assert TAB_HEADER_MAP["candidates"] == "Candidate Parameters"

    def test_boundaries_header(self):
        assert TAB_HEADER_MAP["boundaries"] == "Candidate Parameters"

    def test_dataset_header(self):
        assert TAB_HEADER_MAP["dataset"] == "Dataset Parameters"

    def test_default_header_for_unmapped_tabs(self):
        """Unmapped tabs should fall back to 'Meta Parameters'."""
        assert TAB_HEADER_MAP.get("redis", "Meta Parameters") == "Meta Parameters"


class TestSidebarVisibilityCallback:
    """Test the sidebar visibility callback behavior."""

    @pytest.fixture
    def dashboard(self):
        return DashboardManager({})

    def test_sidebar_visibility_callback_registered(self, dashboard):
        """The visibility callback should be registered."""
        callbacks = dashboard.app.callback_map
        sidebar_outputs = [k for k in callbacks if "sidebar-meta-params-card" in k]
        assert len(sidebar_outputs) > 0, "Sidebar visibility callback not registered"

    def test_sidebar_wrapper_ids_in_layout(self, dashboard):
        """All sidebar wrapper IDs should exist in the layout."""
        layout_str = str(dashboard.app.layout)
        for section_id in SIDEBAR_SECTION_IDS:
            assert section_id in layout_str, f"Wrapper ID '{section_id}' not found in layout"
