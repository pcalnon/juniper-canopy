#!/usr/bin/env python
"""F-CANOPY-017 — a ``None`` numeric State must refuse the apply, not default it.

An ``<input type="number">`` whose content fails HTML5 validity reports no
usable value, so Dash hands the callback ``None``. ``_apply_parameters_handler``
used to translate that into ``TrainingConstants.DEFAULT_*``, which silently
replaced the operator's live backend value with a hardcoded constant.

Observed live on the isolated stack (juniper-ml canopy E2E arc, Phase 1
segment 8): ``/api/state`` held ``nn_learning_rate = 0.0789``; the operator
typed ``0.0733`` into ``#nn-learning-rate-input``; the callback carried ``None``
(the field's ``min=0.0001, step=0.001`` grid made every plausible learning rate
``stepMismatch``); Apply POSTed ``nn_learning_rate: 0.01`` — neither the typed
value nor the live one. The Apply button had been enabled and ``#params-status``
read "Unsaved changes", so it presented as a pending edit rather than a fault.

These tests pin the corrected contract:

* a ``None`` numeric State refuses the whole apply, POSTs nothing, and names
  the offending field(s);
* an OMITTED optional kwarg is NOT a ``None`` State — it keeps its documented
  default, so existing callers that pass only the required arguments are
  unaffected (the ``_UNSET`` sentinel);
* a fully-valid call still applies normally.
"""

from unittest.mock import Mock, patch

import dash
import pytest
from werkzeug.test import EnvironBuilder

VALID_ARGS = {
    "n_clicks": 1,
    "nn_max_iter": 1000,
    "nn_max_epochs": 600,
    "nn_lr": 0.015,
    "nn_max_hu": 25,
    "nn_multi_node": [],
    "nn_growth_trigger": "convergence",
    "nn_growth_epochs": 50,
    "nn_growth_conv_thresh": 0.001,
    "nn_patience": 50,
    "nn_spiral_rot": 1.5,
    "nn_spiral_num": 2,
    "nn_dataset_elem": 1000,
    "nn_dataset_noise": 0.25,
    "cn_pool_size": 100,
    "cn_corr_thresh": 0.001,
    "cn_selected": 1,
    "cn_training_complete": "preset_epochs",
    "cn_training_iter": 500,
    "cn_training_conv_thresh": 0.0001,
    "cn_patience": 30,
    "cn_multi_cand": [],
    "cn_cand_selection": None,
    "cn_top_cands": 1,
    "cn_random_cands": 1,
}


def _run(manager, **overrides):
    """Drive the handler inside a request context with ``requests.post`` stubbed."""
    args = dict(VALID_ARGS)
    args.update(overrides)
    with patch("requests.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response

        builder = EnvironBuilder(method="GET", base_url="http://localhost:8050/dashboard/", path="/dashboard/")
        with manager.app.server.request_context(builder.get_environ()):
            result, status = manager._apply_parameters_handler(**args)
        return result, status, mock_post


@pytest.fixture
def manager(reset_singletons):
    from frontend.dashboard_manager import DashboardManager

    return DashboardManager({})


class TestInvalidNumericRefusesApply:
    @pytest.mark.integration
    def test_none_learning_rate_refuses_and_posts_nothing(self, manager):
        """The live case: a None learning rate must not become 0.01."""
        result, status, mock_post = _run(manager, nn_lr=None)

        assert result is dash.no_update, "a refused apply must not update the applied-params store"
        assert mock_post.call_count == 0, "a refused apply must not POST /api/set_params at all"
        assert "Learning Rate" in status, status
        assert "Nothing applied" in status, status

    @pytest.mark.integration
    def test_refusal_names_every_invalid_field(self, manager):
        result, status, mock_post = _run(manager, nn_lr=None, cn_pool_size=None, nn_patience=None)

        assert mock_post.call_count == 0
        assert "3 field(s)" in status, status
        for label in ("Learning Rate", "Candidate Pool Size", "Patience"):
            assert label in status, f"{label!r} missing from: {status}"

    @pytest.mark.integration
    def test_non_numeric_garbage_is_also_refused(self, manager):
        """A value that cannot be cast is invalid input, not a default trigger."""
        _, status, mock_post = _run(manager, nn_max_hu="not-a-number")

        assert mock_post.call_count == 0
        assert "Maximum Hidden Units" in status, status


class TestOmittedOptionalKwargStillDefaults:
    @pytest.mark.integration
    def test_omitting_output_epochs_does_not_refuse(self, manager):
        """``_UNSET`` (omitted) is a signature contract, not an invalid widget.

        Existing callers pass only the required arguments; they must keep
        working and still receive the documented default.
        """
        result, status, mock_post = _run(manager)

        assert mock_post.call_count == 1, status
        assert result is not dash.no_update
        posted = mock_post.call_args.kwargs["json"]
        from canopy_constants import TrainingConstants

        assert posted["nn_output_epochs"] == TrainingConstants.DEFAULT_OUTPUT_EPOCHS
        assert posted["nn_optimizer_type"] == TrainingConstants.DEFAULT_OPTIMIZER_TYPE

    @pytest.mark.integration
    def test_explicit_none_output_epochs_is_refused(self, manager):
        """But an explicitly-None output epochs IS an invalid widget value."""
        _, status, mock_post = _run(manager, nn_output_epochs=None)

        assert mock_post.call_count == 0
        assert "Output Epochs (per pass)" in status, status


class TestValidApplyUnaffected:
    @pytest.mark.integration
    def test_all_valid_values_still_apply(self, manager):
        result, status, mock_post = _run(manager, nn_lr=0.0733)

        assert mock_post.call_count == 1, status
        assert result is not dash.no_update
        posted = mock_post.call_args.kwargs["json"]
        assert posted["nn_learning_rate"] == pytest.approx(0.0733), "the typed value must survive verbatim"
