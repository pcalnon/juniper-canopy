"""The §6.4 gate decides; these pin what it decides.

Project:       Juniper
Sub-Project:   JuniperCanopy
Application:   juniper_canopy
File Name:     test_validation_gate.py
Author:        Paul Calnon
License:       MIT License

The decision lives outside the Dash callbacks so it can be tested without a browser --
which matters here more than usual, because canopy never reaches DOM stability and its
widgets resist synthetic events, so a browser-level test of this gate would be slow,
flaky, and no more convincing.
"""

from __future__ import annotations

import pytest

from validation_gate import (
    CONTINUE_WITH_WARNING_NOTE,
    OPTION_BACK_TO_DATASET,
    OPTION_CANCEL,
    OPTION_CONTINUE_WITH_WARNING,
    OPTION_FILL_SYNTHETICALLY,
    UNKNOWN_SPLIT_NOTE,
    decide,
    enabled_options,
    resolve_choice,
    validation_split_state,
)

pytestmark = pytest.mark.unit


class TestValidationSplitState:
    """Three states, because two would be wrong in one direction or the other."""

    def test_present_when_val_samples_positive(self):
        assert validation_split_state({"val_samples": 20}) is True

    def test_absent_when_val_samples_zero(self):
        assert validation_split_state({"val_samples": 0}) is False

    def test_unknown_when_field_missing(self):
        """A cascor older than #623 does not report the field at all.

        Reading that as zero would gate every run against an older cascor and train the
        user to click through the gate; reading it as present would let a genuinely
        missing split through unmarked. Neither is acceptable, so it is its own state.
        """
        assert validation_split_state({"train_samples": 100, "test_samples": 20}) is None

    def test_unknown_when_no_payload(self):
        assert validation_split_state(None) is None
        assert validation_split_state({}) is None

    def test_unknown_when_value_is_not_a_number(self):
        """A payload this code does not understand is 'cannot say', not 'no split'."""
        assert validation_split_state({"val_samples": "twenty"}) is None
        assert validation_split_state({"val_samples": None}) is None


class TestDecide:
    def test_no_gate_and_no_warning_when_the_split_exists(self):
        decision = decide({"val_samples": 20})
        assert decision.show_gate is False
        assert decision.warning is None

    def test_gate_when_the_producer_reports_no_split(self):
        decision = decide({"val_samples": 0})
        assert decision.show_gate is True
        assert len(decision.options) == 4, "§6.4 names four options"

    def test_unknown_producer_proceeds_but_is_marked(self):
        """Proceeding silently here is exactly how the two-partition era went unnoticed."""
        decision = decide({"train_samples": 100})
        assert decision.show_gate is False
        assert decision.warning == UNKNOWN_SPLIT_NOTE

    def test_option_zero_is_offered_but_disabled_with_a_reason(self):
        """Synthetic fill has no backend yet (§6.2 / Chunk 5).

        It is shown disabled rather than hidden so the absence is legible instead of
        looking like an oversight -- and a disabled option carries the reason, so the
        user is told what to do instead.
        """
        decision = decide({"val_samples": 0})
        fill = next(o for o in decision.options if o.option_id == OPTION_FILL_SYNTHETICALLY)
        assert fill.enabled is False
        assert "§6.2" in fill.disabled_reason
        assert fill.disabled_reason.strip(), "a disabled option with no reason is just a missing option"

    def test_the_gate_is_actually_usable(self):
        """Three live options. A gate whose every option is disabled is a dead end.

        §6.4's requirement is 'refuse to continue until the user chooses' -- which needs
        a choice to exist. This is the check that the disabled option 0 has not left the
        user stuck.
        """
        decision = decide({"val_samples": 0})
        assert enabled_options(decision) == (
            OPTION_CONTINUE_WITH_WARNING,
            OPTION_BACK_TO_DATASET,
            OPTION_CANCEL,
        )


class TestResolveChoice:
    def test_continue_proceeds_and_carries_the_marking(self):
        result = resolve_choice(OPTION_CONTINUE_WITH_WARNING)
        assert result["proceed"] is True
        assert result["warning"] == CONTINUE_WITH_WARNING_NOTE
        assert "SELECTED-ON" in result["warning"], "the user must be told what the number means, not just that something is wrong"

    def test_back_navigates_without_proceeding(self):
        result = resolve_choice(OPTION_BACK_TO_DATASET)
        assert result["proceed"] is False
        assert result["navigate_to"] == "datasets"
        assert result["warning"] is None

    def test_cancel_neither_proceeds_nor_navigates(self):
        result = resolve_choice(OPTION_CANCEL)
        assert result == {"proceed": False, "navigate_to": None, "warning": None}

    def test_the_disabled_option_raises_rather_than_proceeding(self):
        """If the UI ever lets a user pick option 0, failing is better than pretending.

        Silently falling through to 'continue' would start a run the user believed had
        been repaired -- the worst of the four outcomes.
        """
        with pytest.raises(ValueError, match="§6.2"):
            resolve_choice(OPTION_FILL_SYNTHETICALLY)

    def test_unknown_option_raises(self):
        with pytest.raises(ValueError, match="unknown"):
            resolve_choice("proceed_quietly")

    def test_no_option_both_proceeds_and_navigates_away(self):
        """Proceed and navigate are mutually exclusive; a pair that did both would race."""
        for option_id in (OPTION_CONTINUE_WITH_WARNING, OPTION_BACK_TO_DATASET, OPTION_CANCEL):
            result = resolve_choice(option_id)
            assert not (result["proceed"] and result["navigate_to"]), f"{option_id} both proceeds and navigates"
