"""N7 (canopy training-runtime defects plan, I-7 / U-6 / I-5-UX) — dataset-panel handlers.

Direct-invocation tests for the schema-driven dataset-panel handlers extracted onto
``DashboardManager``: ``_render_dataset_params_handler`` (U-6 per-type section title + spiral-block
visibility + schema-driven inputs), ``_gate_dataset_options_handler`` (model-compat gate composed
with the availability gate + flag-absent fallback), and ``_apply_dataset_handler`` (spiral keeps its
typed fields; a non-spiral generator forwards schema params through the generic ``nn_dataset_params``
staging channel). Follows the repo pattern: ``DashboardManager.__new__`` skips ``__init__`` so we
exercise branch logic without the full Dash app; ``requests`` is patched at the module.

The pure schema->fields / availability core is tested in ``tests/unit/test_dataset_schema.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import dash
import pytest

from frontend.dashboard_manager import DashboardManager

MNIST_SCHEMA = {
    "properties": {
        "dataset": {"type": "string", "enum": ["mnist", "fashion_mnist"], "default": "mnist", "title": "Dataset"},
        "n_samples": {"anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}], "default": None, "title": "N Samples"},
        "flatten": {"type": "boolean", "default": True, "title": "Flatten"},
        "seed": {"type": "integer", "default": 0, "title": "Seed"},
    }
}
MOON_SCHEMA = {
    "properties": {
        "n_samples": {"type": "integer", "minimum": 2, "default": 200, "title": "N Samples"},
        "noise": {"type": "number", "minimum": 0.0, "default": 0.1, "title": "Noise"},
        "seed": {"type": "integer", "default": 0, "title": "Seed"},
    }
}
GENERATORS = [
    {"name": "spiral", "available": True, "schema": {"properties": {}}},
    {"name": "mnist", "available": False, "schema": MNIST_SCHEMA},
    {"name": "moon", "available": True, "schema": MOON_SCHEMA},
]


@pytest.fixture
def dm():
    manager = DashboardManager.__new__(DashboardManager)
    manager.logger = MagicMock()
    manager._api_base_url = "http://test.local"
    return manager


def _text(component):
    """Flatten a Dash/dbc component tree to its concatenated text."""
    if component is None:
        return ""
    if isinstance(component, str):
        return component
    if isinstance(component, (list, tuple)):
        return "".join(_text(c) for c in component)
    return _text(getattr(component, "children", None))


def _ids(children):
    """Collect the pattern-matching ids of the rendered schema-param inputs."""
    found = []
    for child in children:
        cid = getattr(child, "id", None)
        if isinstance(cid, dict) and cid.get("type") == "nn-gen-param":
            found.append(cid["name"])
    return found


# ---------------------------------------------------------------------------
# U-6 section title
# ---------------------------------------------------------------------------


def test_section_title_is_per_type(dm):
    assert dm._dataset_section_title("spirals") == "Current Dataset — Spirals"
    assert dm._dataset_section_title("mnist") == "Current Dataset — MNIST"
    assert dm._initial_dataset_section_title() == "Current Dataset — Spirals"
    # Unknown value degrades to a bare title (never renders "None").
    assert dm._dataset_section_title("") == "Current Dataset"


# ---------------------------------------------------------------------------
# _render_dataset_params_handler
# ---------------------------------------------------------------------------


def test_render_spiral_shows_typed_block_no_schema_children(dm):
    title, style, children = dm._render_dataset_params_handler("spirals", generators=GENERATORS)
    assert title == "Current Dataset — Spirals"
    assert style == {"display": "block"}  # typed spiral fields visible
    assert children == []  # spiral uses the typed fields, not the schema container


def test_render_non_spiral_hides_typed_block_and_renders_schema_fields(dm):
    title, style, children = dm._render_dataset_params_handler("mnist", generators=GENERATORS)
    assert title == "Current Dataset — MNIST"
    assert style == {"display": "none"}  # I-7: spiral typed fields hidden for MNIST
    # Schema-driven inputs rendered with pattern ids; infra field (seed) excluded.
    assert _ids(children) == ["dataset", "n_samples", "flatten"]


def test_render_unavailable_generator_shows_reworded_reason(dm):
    _title, _style, children = dm._render_dataset_params_handler("mnist", generators=GENERATORS)
    text = _text(children)
    # I-5: the unavailable note carries the reworded reason, not a raw pip hint.
    assert "unavailable" in text.lower() or "extra" in text.lower()


def test_render_available_non_spiral_has_no_unavailable_note(dm):
    _title, _style, children = dm._render_dataset_params_handler("moons", generators=GENERATORS)
    assert _ids(children) == ["n_samples", "noise"]  # moon schema, seed excluded
    assert "unavailable" not in _text(children).lower()


def test_render_flag_absent_treats_generator_available(dm):
    # Older data service: entries carry no `available` key and no schema.
    gens = [{"name": "mnist"}]
    _title, _style, children = dm._render_dataset_params_handler("mnist", generators=gens)
    assert "unavailable" not in _text(children).lower()  # flag-absent -> available
    # No schema -> a friendly "no adjustable parameters" note, not a crash.
    assert "no adjustable parameters" in _text(children).lower()


# ---------------------------------------------------------------------------
# _gate_dataset_options_handler (model-compat + availability composition)
# ---------------------------------------------------------------------------


def test_gate_composes_availability_over_model_options(dm):
    dm._fetch_generators = lambda: GENERATORS  # mnist unavailable
    options, value = dm._gate_dataset_options_handler("cascor", "spirals")
    by_value = {o["value"]: o for o in options}
    # cascor is 2-D: spirals/xor/mnist/circles/moons compatible; equities_seq 3-D -> model-disabled.
    assert by_value["mnist"]["disabled"] is True  # availability gate
    assert not by_value["spirals"].get("disabled")  # available + compatible
    assert by_value["equities_seq"]["disabled"] is True  # model-incompat gate preserved
    assert value is dash.no_update  # current selection (spirals) still enabled -> no snap


def test_gate_snaps_away_from_a_disabled_current_selection(dm):
    dm._fetch_generators = lambda: GENERATORS
    options, value = dm._gate_dataset_options_handler("cascor", "mnist")  # mnist now unavailable
    enabled = [o["value"] for o in options if not o.get("disabled")]
    assert value in enabled and value != "mnist"  # snapped to a usable dataset


def test_gate_ungates_without_model(dm):
    # INVERTED by N11. The pre-N7 contract ("no model yet -> no dropdown write") was safe only
    # while the model axis could not be cleared; once it can, that early return freezes the list
    # at the OLD model's gate. The availability composition still applies -- this ungates the
    # MODEL-compatibility gate, not the deployment-availability one.
    options, value = dm._gate_dataset_options_handler("", "spirals", generators=[])
    assert options is not dash.no_update
    assert len(options) == len(dm._gate_dataset_options_handler("cascor", "spirals", generators=[])[0])
    assert value is dash.no_update


def test_gate_flag_absent_leaves_all_available_enabled(dm):
    dm._fetch_generators = lambda: [{"name": "mnist"}, {"name": "spiral"}]  # no availability flags
    options, _value = dm._gate_dataset_options_handler("cascor", "spirals")
    by_value = {o["value"]: o for o in options}
    assert by_value["mnist"].get("disabled") in (None, False)  # flag-absent -> not availability-gated


# ---------------------------------------------------------------------------
# _apply_dataset_handler (staging round-trip; dialect preserved)
# ---------------------------------------------------------------------------


def _ok_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.text = ""
    return resp


def test_apply_spiral_sends_typed_fields_only(dm):
    with patch("frontend.dashboard_manager.requests") as mock_requests:
        mock_requests.post.return_value = _ok_response()
        mock_requests.RequestException = Exception
        is_open, alert = dm._apply_dataset_handler(1, "spirals", 500, 0.3, 2.5, 3, gen_values=[], gen_ids=[])
    assert is_open is True and alert is None
    payload = mock_requests.post.call_args.kwargs["json"]
    assert payload["nn_dataset_type"] == "spirals"
    assert payload["nn_dataset_elements"] == 500 and payload["nn_dataset_noise"] == 0.3
    assert payload["nn_spiral_rotations"] == 2.5 and payload["nn_spiral_number"] == 3
    assert "nn_dataset_params" not in payload  # spiral never uses the generic channel


def test_apply_non_spiral_routes_generic_params_and_drops_typed_fields(dm):
    gen_ids = [{"type": "nn-gen-param", "name": "dataset"}, {"type": "nn-gen-param", "name": "n_samples"}, {"type": "nn-gen-param", "name": "flatten"}]
    gen_values = ["fashion_mnist", 512, True]
    with patch("frontend.dashboard_manager.requests") as mock_requests:
        mock_requests.post.return_value = _ok_response()
        mock_requests.RequestException = Exception
        # The now-hidden typed inputs still carry stale spiral values — they MUST be dropped.
        is_open, _alert = dm._apply_dataset_handler(1, "mnist", 200, 0.1, 3.0, 2, gen_values=gen_values, gen_ids=gen_ids)
    assert is_open is True
    payload = mock_requests.post.call_args.kwargs["json"]
    assert payload["nn_dataset_type"] == "mnist"
    assert payload["nn_dataset_params"] == {"dataset": "fashion_mnist", "n_samples": 512, "flatten": True}
    # Staging dialect preserved: no typed spiral/common fields leak for a non-spiral generator.
    for typed in ("nn_dataset_elements", "nn_dataset_noise", "nn_spiral_rotations", "nn_spiral_number"):
        assert typed not in payload


def test_apply_non_spiral_omits_params_when_all_blank(dm):
    gen_ids = [{"type": "nn-gen-param", "name": "n_samples"}, {"type": "nn-gen-param", "name": "noise"}]
    gen_values = [None, ""]  # cleared / blank -> use generator defaults
    with patch("frontend.dashboard_manager.requests") as mock_requests:
        mock_requests.post.return_value = _ok_response()
        mock_requests.RequestException = Exception
        dm._apply_dataset_handler(1, "moons", 200, 0.1, 3.0, 2, gen_values=gen_values, gen_ids=gen_ids)
    payload = mock_requests.post.call_args.kwargs["json"]
    assert payload == {"nn_dataset_type": "moons"}  # no params key when every field is blank


def test_apply_no_clicks_is_noop(dm):
    out = dm._apply_dataset_handler(None, "spirals", 200, 0.1, 3.0, 2, gen_values=[], gen_ids=[])
    assert out == (dash.no_update, dash.no_update)


def test_apply_surfaces_backend_rejection_detail(dm):
    resp = MagicMock()
    resp.status_code = 422
    resp.text = "generator 'mnist' is not available in this deployment"
    with patch("frontend.dashboard_manager.requests") as mock_requests:
        mock_requests.post.return_value = resp
        mock_requests.RequestException = Exception
        is_open, alert = dm._apply_dataset_handler(1, "mnist", None, None, None, None, gen_values=[], gen_ids=[])
    assert is_open is dash.no_update
    assert "not available" in _text(alert)  # upstream detail surfaced (T1)


# ---------------------------------------------------------------------------
# _collect_generator_params
# ---------------------------------------------------------------------------


def test_collect_generator_params_zips_and_drops_blanks(dm):
    ids = [{"type": "nn-gen-param", "name": "a"}, {"type": "nn-gen-param", "name": "b"}, {"type": "nn-gen-param", "name": "c"}, {"type": "nn-gen-param", "name": "d"}]
    values = [1, None, "", "keep"]
    assert dm._collect_generator_params(values, ids) == {"a": 1, "d": "keep"}


def test_collect_generator_params_empty(dm):
    assert dm._collect_generator_params([], []) == {}
    assert dm._collect_generator_params(None, None) == {}
