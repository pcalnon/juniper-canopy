"""
Pin the backend contract in the direction it actually drifts: ``main.py`` gains a call before
``BackendProtocol`` gains the declaration.

This is the general form of Y1 (canopy#633) and of the four live-dataset-swap methods that
followed it. The shape every time:

1. ``main.py`` calls ``backend.<something>()`` with no ``hasattr`` guard.
2. ``BackendProtocol`` never declares it, so nothing says the method is required.
3. ServiceBackend and DemoBackend happen to have it; RecurrenceBackend does not.
4. The route's bare ``except Exception`` turns the ``AttributeError`` into a 500 + error_id.

**Why a protocol-conformance test alone is not enough, and would have caught neither.** Measured
on ``main`` before this change: ``BackendProtocol`` declared 22 methods and *every* backend
implemented all 22 — zero missing. The four broken methods were invisible to that check because
they were never declared. A conformance test would have passed, green and vacuous, while
``/api/history/dataset_swaps`` returned a 500 every five seconds under recurrence.

So the load-bearing test here is ``TestMainCallsOnlyDeclaredOrExemptMethods``: it reads the
requirement from the CALLER, which is where the requirement is actually created.
``TestEveryBackendImplementsTheWholeProtocol`` is the cheaper second half, kept because it is
the half that fails if a backend is added or a method dropped.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
MAIN = SRC / "main.py"

if str(SRC) not in sys.path:  # pragma: no cover - import side effect
    sys.path.insert(0, str(SRC))

from backend.demo_backend import DemoBackend  # noqa: E402
from backend.protocol import BackendProtocol  # noqa: E402
from backend.recurrence_backend import RecurrenceBackend  # noqa: E402
from backend.service_backend import ServiceBackend  # noqa: E402

BACKENDS = (DemoBackend, ServiceBackend, RecurrenceBackend)

# Attributes ``main.py`` reads off ``backend`` that are deliberately NOT part of the protocol.
# Every entry needs a reason a caller can check, because the cost of a wrong entry here is the
# 500 this file exists to prevent. "Guarded" means main.py cannot reach the attribute on a
# backend that lacks it -- either an explicit ``hasattr`` or a ``backend_type`` branch.
CONDITIONAL_BY_DESIGN = {
    "_adapter": "private handle; hasattr-guarded at main.py:2573 and :2818",
    "_demo": "private handle; reached only under `backend_type == 'demo'` (main.py:255)",
    "import_dataset": "hasattr-guarded at main.py:1701 and :1795",
    "regenerate_dataset": "hasattr-guarded at main.py:1638",
    "regenerate_dataset_from_generator": "hasattr-guarded at main.py:1663",
    "stage_dataset": "hasattr-guarded at main.py:4299",
    "get_synced_state": "inside `elif backend_type == 'service'` (main.py:266)",
    "set_state_update_callback": "inside `elif backend_type == 'service'` (main.py:285); the recurrence branch documents why it has none",
}


def _protocol_methods() -> set[str]:
    return {name for name in vars(BackendProtocol) if not name.startswith("_")}


def _attributes_read_off_backend() -> set[str]:
    """Every ``backend.<attr>`` in main.py, however it is then used."""
    tree = ast.parse(MAIN.read_text(encoding="utf-8"))
    return {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "backend"}


@pytest.mark.regression
class TestMainCallsOnlyDeclaredOrExemptMethods:
    """The caller creates the requirement; the protocol must record it."""

    def test_the_scan_finds_a_plausible_number_of_attributes(self):
        """Guard the instrument: a broken parser would make the real check pass vacuously."""
        found = _attributes_read_off_backend()
        assert len(found) >= 20, f"Only {len(found)} attributes scanned off `backend` in main.py ({sorted(found)}); the AST scan is broken and the check below would be vacuous."
        assert "get_status" in found, "`backend.get_status` was not found by the scan, though main.py certainly calls it."

    def test_every_attribute_is_declared_or_explicitly_conditional(self):
        undeclared = sorted(_attributes_read_off_backend() - _protocol_methods() - set(CONDITIONAL_BY_DESIGN))
        assert not undeclared, (
            "main.py reads these off `backend`, but BackendProtocol does not declare them and they are not " f"recorded as conditional: {', '.join(undeclared)}. If the call is unguarded, DECLARE it in " "BackendProtocol and implement it on every backend -- an undeclared requirement is how Y1 and the " "four live-dataset-swap methods each became a 500 with an error_id. If the call genuinely cannot " "reach a backend that lacks it, add it to CONDITIONAL_BY_DESIGN with the guard that makes that true."
        )

    @pytest.mark.parametrize("name,reason", sorted(CONDITIONAL_BY_DESIGN.items()))
    def test_each_exemption_still_describes_a_real_attribute(self, name, reason):
        """An exemption for an attribute main.py no longer reads is stale cover for the next one."""
        assert name in _attributes_read_off_backend(), f"CONDITIONAL_BY_DESIGN still exempts `{name}` ({reason}), but main.py no longer reads it off `backend`. Drop the entry."


@pytest.mark.regression
class TestEveryBackendImplementsTheWholeProtocol:
    """The second half: a backend must not fall behind the protocol."""

    def test_the_protocol_is_not_empty(self):
        """Guard the instrument."""
        assert len(_protocol_methods()) >= 20, f"BackendProtocol exposes only {len(_protocol_methods())} public names; the introspection is wrong and the check below would be vacuous."

    @pytest.mark.parametrize("backend_cls", BACKENDS, ids=lambda c: c.__name__)
    def test_backend_implements_every_declared_method(self, backend_cls):
        missing = sorted(name for name in _protocol_methods() if not hasattr(backend_cls, name))
        assert not missing, f"{backend_cls.__name__} does not implement {', '.join(missing)}, which BackendProtocol declares. main.py calls protocol methods unguarded, so a missing one is a 500 with an error_id, not a type error."


@pytest.mark.regression
class TestRecurrenceAnswersTheSwapSurfaceHonestly:
    """The four methods this file was written for: refuse writes, answer reads truthfully."""

    @pytest.fixture
    def backend(self):
        return RecurrenceBackend.__new__(RecurrenceBackend)

    def test_a_live_swap_is_refused_rather_than_reported_successful(self, backend):
        result = backend.swap_dataset_live(dataset_type="spirals")
        assert result["ok"] is False, "a swap that cannot happen must not report success"
        assert "live dataset swap" in result["error"]

    def test_cancelling_is_refused_rather_than_reported_cancelled(self, backend):
        result = backend.cancel_swap_dataset_live()
        assert result["ok"] is False
        assert "cancel" in result["error"]

    def test_the_event_feed_is_an_empty_success_not_an_error(self, backend):
        """`ok: False` here would make the route emit a 502 every 5s -- the defect in 502 form."""
        result = backend.get_dataset_swap_events()
        assert result["ok"] is True, "an empty feed is the TRUE answer for a tier that records no swaps, not a failure"
        assert result["events"] == []

    def test_the_snapshot_feed_answers_the_same_way(self, backend):
        result = backend.get_snapshot_dataset_swaps("snap-123")
        assert result["ok"] is True
        assert result["events"] == []

    def test_the_event_feed_accepts_the_since_argument_main_passes(self, backend):
        """main.py:4492 calls this with `since=`; a signature mismatch is the same 500."""
        assert backend.get_dataset_swap_events(since="2026-09-21T00:00:00Z")["ok"] is True

    def test_none_of_the_four_raise(self, backend):
        """The route wraps these in a bare `except Exception`; anything raised becomes a 500."""
        backend.swap_dataset_live()
        backend.cancel_swap_dataset_live()
        backend.get_dataset_swap_events()
        backend.get_snapshot_dataset_swaps("s")
