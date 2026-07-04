#!/usr/bin/env python
"""Per-file coverage-gate tests for ``frontend.components.parameters_panel``.

Targets the baseline-missing statement lines: the ``_build_table`` helper
(pinned + non-pinned columns, bool/list value coercion) and the
``update_parameters_tables`` callback body. Real assertions on the produced
Dash structures — no ``assert True`` line-execution stubs.
"""

import dash_bootstrap_components as dbc
import pytest
from dash import html

from frontend.components.parameters_panel import (
    CANDIDATE_TRAINING_PARAMS,
    DATASET_PARAMS,
    NETWORK_TRAINING_PARAMS,
    ParametersPanel,
    _build_table,
)


class _StubApp:
    """Records callbacks (identity decorator) instead of running Dash."""

    def __init__(self):
        self.callbacks = []

    def callback(self, *outputs, **kwargs):
        def decorator(fn):
            self.callbacks.append((outputs, kwargs, fn))
            return fn

        return decorator


@pytest.fixture
def panel():
    return ParametersPanel({}, component_id="params-gate")


@pytest.fixture
def callbacks(panel):
    app = _StubApp()
    panel.register_callbacks(app)
    return {fn.__name__: fn for _, _, fn in app.callbacks}


def _count_cells(row):
    """Number of <Td> cells in an html.Tr."""
    children = row.children
    if not isinstance(children, (list, tuple)):
        children = [children]
    return len(children)


class TestBuildTablePinnedColumn:
    def test_pinned_keys_adds_pin_header_and_cell(self):
        table = _build_table(NETWORK_TRAINING_PARAMS, {}, pinned_keys=["max_iterations"])
        assert isinstance(table, dbc.Table)
        thead, tbody = table.children
        header_row = thead.children
        header_cells = header_row.children
        # Pin + Parameter + Current Value + Min + Max + Default == 6 columns.
        assert len(header_cells) == 6
        assert header_cells[0].children == "Pin"
        # Every body row also carries the leading pin cell (6 cells).
        first_row = tbody.children[0]
        assert _count_cells(first_row) == 6

    def test_pinned_checkbox_reflects_membership(self):
        table = _build_table(NETWORK_TRAINING_PARAMS, {}, pinned_keys=["max_iterations"])
        tbody = table.children[1]
        # First param is max_iterations -> its pin checkbox is checked.
        pin_cell = tbody.children[0].children[0]
        checkbox = pin_cell.children
        assert isinstance(checkbox, dbc.Checkbox)
        assert checkbox.value is True
        assert checkbox.id == {"type": "param-pin", "key": "max_iterations"}

    def test_empty_pinned_list_still_renders_pin_column(self):
        # pinned_keys=[] is *not* None, so the pin column is present but empty.
        table = _build_table(DATASET_PARAMS, {}, pinned_keys=[])
        thead = table.children[0]
        assert len(thead.children.children) == 6
        tbody = table.children[1]
        pin_cell = tbody.children[0].children[0]
        assert pin_cell.children.value is False


class TestBuildTableNoPinColumn:
    def test_pinned_keys_none_omits_pin_column(self):
        table = _build_table(NETWORK_TRAINING_PARAMS, {})
        thead, tbody = table.children
        # No Pin column -> 5 header cells.
        assert len(thead.children.children) == 5
        assert _count_cells(tbody.children[0]) == 5


class TestBuildTableValueCoercion:
    def test_bool_true_renders_enabled(self):
        table = _build_table(CANDIDATE_TRAINING_PARAMS, {"multi_candidate": True}, pinned_keys=[])
        assert "Enabled" in str(table)

    def test_bool_false_renders_disabled(self):
        table = _build_table(CANDIDATE_TRAINING_PARAMS, {"multi_candidate": False}, pinned_keys=[])
        assert "Disabled" in str(table)

    def test_list_with_enabled_token_renders_enabled(self):
        table = _build_table(NETWORK_TRAINING_PARAMS, {"multi_node_layers": ["enabled"]})
        assert "Enabled" in str(table)

    def test_list_without_enabled_token_renders_disabled(self):
        table = _build_table(NETWORK_TRAINING_PARAMS, {"multi_node_layers": ["something_else"]})
        assert "Disabled" in str(table)

    def test_scalar_value_rendered_via_strong(self):
        table = _build_table(NETWORK_TRAINING_PARAMS, {"max_iterations": 42})
        assert "42" in str(table)

    def test_missing_value_defaults_to_dash(self):
        # A key not present in ``data`` falls back to the em-dash placeholder.
        table = _build_table(DATASET_PARAMS, {})
        assert "—" in str(table)  # em dash


class TestUpdateParametersTablesCallback:
    def test_callback_registered(self, callbacks):
        assert "update_parameters_tables" in callbacks

    def test_none_data_uses_defaults(self, callbacks):
        network, dataset, candidate = callbacks["update_parameters_tables"](None, None)
        assert isinstance(network, dbc.Table)
        assert isinstance(dataset, dbc.Table)
        assert isinstance(candidate, dbc.Table)

    def test_populated_data_flows_into_tables(self, callbacks):
        data = {"max_iterations": 7, "spiral_rotations": 3, "pool_size": 11}
        pinned = ["max_iterations", "pool_size"]
        network, dataset, candidate = callbacks["update_parameters_tables"](data, pinned)
        # Value from data appears in the network table.
        assert "7" in str(network)
        assert "11" in str(candidate)
        # Pin column present because pinned list was passed through.
        assert "param-pin" in str(network)

    def test_empty_pinned_list_renders_pin_column(self, callbacks):
        network, _dataset, _candidate = callbacks["update_parameters_tables"]({}, [])
        assert "param-pin" in str(network)
