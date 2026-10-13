"""The §6.4 gate: what to do when a dataset has no validation split.

Project:       Juniper
Sub-Project:   JuniperCanopy
Application:   juniper_canopy
File Name:     validation_gate.py
Author:        Paul Calnon
License:       MIT License

juniper-cascor refuses an artifact with no ``X_val`` (design §6.1 rule 1), because
promoting ``X_test`` to the in-loop signal makes early stopping select on the rows the
final score is reported from. For a **headless** run refusing is the whole answer.
For an **interactive** one it is not: §6.4 requires canopy to explain the problem and
then *refuse to continue until the user chooses*, from four named options.

This module is the decision, kept out of the Dash callback layer on purpose. The
callback's job is to render what these functions return; theirs is to decide, so the
decision can be tested without a browser.

**The tri-state matters.** ``val_samples`` is absent from a cascor older than #623, and
absent is not the same as zero:

===================  ======================================================
``val_samples``      meaning
===================  ======================================================
``> 0``              a validation split exists -- proceed, no gate
``== 0``             the producer reported no validation split -- **gate**
absent               this cascor cannot say -- proceed, but MARK the run
===================  ======================================================

Collapsing "absent" into "zero" would gate every run against an older cascor, which is
wrong and would train users to click through the gate. Collapsing it into "present"
would let a genuinely missing split through unmarked, which is the defect the arc
exists to remove. So it is three states, not two.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

#: Option ids, in the order §6.4 lists them.
OPTION_FILL_SYNTHETICALLY = "fill_synthetically"
OPTION_CONTINUE_WITH_WARNING = "continue_with_warning"
OPTION_BACK_TO_DATASET = "back_to_dataset"
OPTION_CANCEL = "cancel"

#: Why option 0 cannot be offered yet. Shown to the user rather than hidden, so the
#: absence is legible instead of looking like an oversight.
FILL_SYNTHETICALLY_UNAVAILABLE_REASON = "Synthetic fill needs juniper-data's generate-shortfall backend (design §6.2), which is not built yet. Regenerate the dataset from the Datasets tab instead — juniper-data 0.13.0 and later emit a validation split for every generator."

#: The marking §6.1 rule 2 requires when a run proceeds without a real validation split.
CONTINUE_WITH_WARNING_NOTE = "No validation split in this dataset: cascor early-stops on the TEST rows, so the reported f1 / roc_auc are SELECTED-ON rather than held out. They are not comparable with a run made against a three-way dataset."

#: The marking when the producer is simply too old to say either way.
UNKNOWN_SPLIT_NOTE = "This juniper-cascor does not report a validation-split count, so canopy cannot confirm the run early-stopped on held-out rows. Upgrade cascor to get a definite answer."


@dataclass(frozen=True)
class GateOption:
    """One choice offered by the §6.4 gate."""

    option_id: str
    label: str
    description: str
    enabled: bool = True
    disabled_reason: str = ""


@dataclass(frozen=True)
class GateDecision:
    """What canopy should do about a staged dataset's validation split.

    ``show_gate`` and ``warning`` are independent: a run can proceed with a warning
    (unknown producer) without the gate, and the gate never proceeds by itself.
    """

    show_gate: bool
    warning: Optional[str] = None
    options: Tuple[GateOption, ...] = field(default_factory=tuple)


def validation_split_state(dataset_info: Optional[Mapping[str, Any]]) -> Optional[bool]:
    """Tri-state read of a cascor dataset payload's validation split.

    Args:
        dataset_info: the raw mapping from ``GET /v1/dataset``, or ``None``.

    Returns:
        ``True`` when a validation split is present, ``False`` when the producer
        reported none, and ``None`` when it did not report the field at all --
        including when there is no payload to read.
    """
    if not dataset_info:
        return None
    if "val_samples" not in dataset_info:
        return None
    try:
        return int(dataset_info["val_samples"]) > 0
    except (TypeError, ValueError):
        # A non-numeric value is not a claim that the split is absent; it is a payload
        # this code does not understand, which is the "cannot say" state.
        return None


def _options() -> Tuple[GateOption, ...]:
    return (
        GateOption(
            option_id=OPTION_FILL_SYNTHETICALLY,
            label="Fill synthetically",
            description="Generate the missing validation rows from the dataset's own generator and parameters, leaving the training rows untouched.",
            enabled=False,
            disabled_reason=FILL_SYNTHETICALLY_UNAVAILABLE_REASON,
        ),
        GateOption(
            option_id=OPTION_CONTINUE_WITH_WARNING,
            label="Continue with a recorded warning",
            description="Train anyway. Early stopping will read the test rows, so the reported metrics are selected-on. The run is marked for its lifetime and the metrics carry a caveat.",
        ),
        GateOption(
            option_id=OPTION_BACK_TO_DATASET,
            label="Back to dataset selection",
            description="Return to the Datasets tab with this configuration intact, so a dataset with a validation split can be chosen or generated.",
        ),
        GateOption(
            option_id=OPTION_CANCEL,
            label="Cancel the run",
            description="Abort without starting training.",
        ),
    )


def decide(dataset_info: Optional[Mapping[str, Any]]) -> GateDecision:
    """Decide whether to gate a training start, and with what.

    Never returns "proceed silently" for a dataset known to lack the split -- §6.4's
    whole point is that the interactive path must not take option 1 on the user's
    behalf, which is how the two-partition era went unnoticed in the first place.
    """
    state = validation_split_state(dataset_info)
    if state is True:
        return GateDecision(show_gate=False)
    if state is None:
        return GateDecision(show_gate=False, warning=UNKNOWN_SPLIT_NOTE)
    return GateDecision(show_gate=True, options=_options())


def enabled_options(decision: GateDecision) -> Tuple[str, ...]:
    """The option ids a user can actually pick. Useful for asserting the gate is usable."""
    return tuple(o.option_id for o in decision.options if o.enabled)


def resolve_choice(option_id: str) -> Dict[str, Any]:
    """Translate a chosen option into the action canopy takes.

    Returns a mapping with ``proceed`` (start training now), ``navigate_to`` (a tab id
    or ``None``) and ``warning`` (recorded for the run's lifetime, or ``None``).

    Raises:
        ValueError: on an unknown option, or on one that is offered but disabled --
            a disabled option reaching here means the UI let the user pick something
            with no backend, and proceeding would be worse than failing.
    """
    if option_id == OPTION_CONTINUE_WITH_WARNING:
        return {"proceed": True, "navigate_to": None, "warning": CONTINUE_WITH_WARNING_NOTE}
    if option_id == OPTION_BACK_TO_DATASET:
        return {"proceed": False, "navigate_to": "datasets", "warning": None}
    if option_id == OPTION_CANCEL:
        return {"proceed": False, "navigate_to": None, "warning": None}
    if option_id == OPTION_FILL_SYNTHETICALLY:
        raise ValueError(FILL_SYNTHETICALLY_UNAVAILABLE_REASON)
    raise ValueError(f"unknown §6.4 gate option: {option_id!r}")
