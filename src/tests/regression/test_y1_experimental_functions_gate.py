#!/usr/bin/env python
"""Y1 — the experimental-functions gate must not 500 on a backend that lacks it.

``main.py``'s two experimental-functions routes call ``backend.get_experimental_functions`` /
``set_experimental_functions`` UNCONDITIONALLY, and the read runs on **every page mount**.
``BackendProtocol`` never declared either, so the requirement was a de-facto contract that
ServiceBackend, DemoBackend and demo_mode happened to satisfy and ``RecurrenceBackend`` did
not. The route's ``except Exception`` turned the resulting ``AttributeError`` into a **500
with an error_id on every page mount under recurrence**.

These tests pin three things:
  1. RecurrenceBackend answers both calls (the defect itself);
  2. the read is a closed gate rather than an error, and the write REFUSES rather than
     silently reporting success;
  3. **every** backend satisfies the now-declared protocol surface — so the next backend
     added cannot reintroduce the same class of gap silently.
"""

from __future__ import annotations

import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.demo_backend import DemoBackend  # noqa: E402
from backend.protocol import BackendProtocol  # noqa: E402
from backend.recurrence_backend import RecurrenceBackend  # noqa: E402
from backend.service_backend import ServiceBackend  # noqa: E402

#: The gate surface main.py calls unconditionally.
GATE_METHODS = ("get_experimental_functions", "set_experimental_functions")

#: Every backend class routed through ``backend`` in main.py.
ALL_BACKENDS = (ServiceBackend, DemoBackend, RecurrenceBackend)


class TestTheGateSurfaceIsDeclaredAndUniversal:
    """The durable half: the contract is written down and every backend meets it."""

    @pytest.mark.parametrize("name", GATE_METHODS)
    def test_the_protocol_declares_the_method(self, name):
        # Previously undeclared, which is WHY one backend could omit it without any check
        # noticing. A route that calls a method unconditionally is asserting a contract;
        # the protocol is where that assertion belongs.
        assert hasattr(BackendProtocol, name), f"BackendProtocol does not declare {name}"

    @pytest.mark.parametrize("backend_cls", ALL_BACKENDS, ids=lambda c: c.__name__)
    @pytest.mark.parametrize("name", GATE_METHODS)
    def test_every_backend_implements_it(self, backend_cls, name):
        # THE regression. RecurrenceBackend failed this before the fix.
        assert hasattr(backend_cls, name), f"{backend_cls.__name__} is missing {name}; main.py calls it unconditionally on every page mount"
        assert callable(getattr(backend_cls, name))

    @pytest.mark.parametrize("backend_cls", ALL_BACKENDS, ids=lambda c: c.__name__)
    def test_the_setter_takes_the_enabled_argument(self, backend_cls):
        # A no-arg stub would satisfy hasattr and still TypeError at the call site.
        sig = inspect.signature(backend_cls.set_experimental_functions)
        params = [p for p in sig.parameters if p != "self"]
        assert params, f"{backend_cls.__name__}.set_experimental_functions takes no argument"


class TestRecurrenceAnswersTheGateHonestly:
    """The behavioural half: not raising is necessary but not sufficient."""

    @staticmethod
    def _backend():
        # The adapter is never touched by these calls -- the gate is answered locally,
        # because the recurrence tier has no such endpoint to ask.
        return RecurrenceBackend.__new__(RecurrenceBackend)

    def test_the_read_reports_a_closed_gate_without_erroring(self):
        result = self._backend().get_experimental_functions()
        assert result.get("enabled") is False
        # Crucially NOT an error: the route maps ``ok: False`` to a 502, and a 502 on every
        # page mount would trade a 500 for a slightly quieter lie. The gate is genuinely
        # closed here -- that is the F2.10 safe default the route's docstring describes.
        assert result.get("ok", True) is True, "the READ must not report a backend failure; the gate is closed, not broken"

    def test_the_write_refuses_instead_of_reporting_success(self):
        result = self._backend().set_experimental_functions(True)
        assert result.get("ok") is False, "a toggle that cannot be honoured must not report success"
        assert result.get("enabled") is False
        assert result.get("error"), "the refusal must carry a reason the route can surface"

    def test_the_write_refuses_for_both_values(self):
        # Enabling and disabling are equally unhonourable here; neither may silently pass.
        for value in (True, False):
            assert self._backend().set_experimental_functions(value).get("ok") is False

    def test_neither_call_raises(self):
        # The literal defect: AttributeError reaching main.py's ``except Exception``.
        backend = self._backend()
        backend.get_experimental_functions()
        backend.set_experimental_functions(False)
