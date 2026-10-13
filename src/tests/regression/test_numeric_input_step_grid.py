"""F-CANOPY-017 — numeric ``dbc.Input`` widgets must not carry a coarse ``step``.

HTML5 evaluates ``step`` validity **relative to ``min``**, not to zero: the
admissible values of an ``<input type="number" min=M step=S>`` are ``M + n*S``.
So ``#nn-learning-rate-input`` with ``min=0.0001, step=0.001`` accepted only
0.0001, 0.0011, 0.0021 … — no learning rate an operator would ever type (0.1,
0.01, 0.05) was on that grid, and ``el.validity.stepMismatch`` was true for all
of them.

That mattered because an invalid number input reports no usable value, so Dash
delivered ``None`` as the component's State. The Apply handler then substituted
``TrainingConstants.DEFAULT_*`` for the ``None`` — silently POSTing 0.01 when
the operator typed 0.0733 over a live 0.0789. The dirty tracker had already
enabled Apply and rendered "Unsaved changes", so it looked like a pending edit.

Live evidence (juniper-ml canopy E2E arc, Phase 1 segment 8): a DOM sweep of
the running dashboard found **7 of 22** sidebar number inputs whose own
backend-seeded value failed their own step grid, plus two of the restart
modal's granular fields.

The convention this pins:

* float-valued params use ``step="any"`` (no grid; ``min``/``max`` still bound),
* integer-valued params use ``step=1`` (integer-ness enforced, every integer
  in range reachable).

A coarse ``step`` is only ever a spinner-increment convenience, and that
convenience is not worth silently rewriting an operator's training parameter.
The companion guard is in ``_apply_parameters_handler``: a ``None`` numeric
State now refuses the apply and names the field instead of substituting a
default.

Scope: this gate covers ``dashboard_manager.py`` — the training-parameter
surface, where the Apply path lives and where the live evidence was gathered.
Coarse steps also exist in ``dataset_plotter.py`` (:165 step=10, :184 step=0.1,
:191 step=0.01), ``metrics_panel.py`` (:408 step=10) and
``network_editor_panel.py`` (:270 step=0.01). Those are NOT swept here: a
coarse step is only a defect when the grid excludes plausible input, and
``metrics-panel-window-size`` (min=10, step=10, value=500) is presently valid.
They are recorded as follow-ups rather than changed blind, since none of them
feeds the Apply handler whose default-substitution made this severe.
"""

import ast
from pathlib import Path

import pytest

_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
_GATED_FILES = ("dashboard_manager.py",)

# ``step`` values that are legitimate under the convention.
_ALLOWED_STEPS = ("any", 1)


def _step_offenders(path: Path) -> list[str]:
    """Every ``dbc.Input(type="number", ...)`` whose ``step`` is coarse.

    AST-based rather than regex: the widgets span many lines and their
    ``min``/``max`` are constant references, so a textual match would be both
    fragile and unable to tell a literal ``step`` from a passed-through one.
    """
    tree = ast.parse(path.read_text())
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name != "Input":
            continue

        kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        type_node = kwargs.get("type")
        if not (isinstance(type_node, ast.Constant) and type_node.value == "number"):
            continue
        step_node = kwargs.get("step")
        if step_node is None:
            continue
        # A non-literal step (e.g. the restart modal's ``step=step`` builder
        # parameter) is checked at its call sites instead.
        if not isinstance(step_node, ast.Constant):
            continue
        if step_node.value in _ALLOWED_STEPS:
            continue

        id_node = kwargs.get("id")
        widget_id = id_node.value if isinstance(id_node, ast.Constant) else "<dynamic id>"
        offenders.append(f"{path.name}:{step_node.lineno}: id={widget_id!r} step={step_node.value!r}")

    return offenders


def _builder_call_offenders(path: Path) -> list[str]:
    """Coarse literal ``step`` passed to a local numeric-input builder.

    The restart modal builds its granular fields through a ``_num(label, id,
    step, minimum)`` helper, so the coarse value lives at the call site rather
    than on the ``dbc.Input``. Those calls hit exactly the same grid rule —
    ``restart-ds-samples`` was seeded 1000 against ``min=1, step=100``.
    """
    tree = ast.parse(path.read_text())
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "_num"):
            continue
        if len(node.args) < 3:
            continue
        step_node = node.args[2]
        if not isinstance(step_node, ast.Constant):
            continue
        if step_node.value in _ALLOWED_STEPS:
            continue
        target = node.args[1]
        widget_id = target.value if isinstance(target, ast.Constant) else "<dynamic id>"
        offenders.append(f"{path.name}:{step_node.lineno}: _num(id={widget_id!r}, step={step_node.value!r})")

    return offenders


@pytest.mark.regression
def test_numeric_inputs_use_any_or_unit_step():
    paths = [_FRONTEND_DIR / name for name in _GATED_FILES]
    missing = [p for p in paths if not p.is_file()]
    assert not missing, f"gated file(s) moved or renamed: {missing}"

    offenders: list[str] = []
    for path in paths:
        offenders.extend(_step_offenders(path))
        offenders.extend(_builder_call_offenders(path))

    assert not offenders, 'Numeric ``dbc.Input`` widgets must use ``step="any"`` (float params) or ' "``step=1`` (integer params). HTML5 evaluates step validity relative to " "``min``, so a coarse step makes ordinary typed values stepMismatch — the " "widget then hands Dash ``None`` and the Apply handler used to substitute " "a hardcoded default, silently overwriting the operator's value " "(F-CANOPY-017). Offenders:\n  " + "\n  ".join(offenders)
