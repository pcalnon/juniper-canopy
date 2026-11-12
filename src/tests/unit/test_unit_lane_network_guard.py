"""
Pin the unit-lane network guard (``src/tests/conftest.py``, UNIT-LANE NETWORK GUARD).

A unit test that connects to whatever listens on the host passes or fails by
host state, and on a developer machine it talks to a live service such as the
canopy on :8050. The guard refuses a connect to a Juniper service port while a
unit-lane test runs, and fails that test even when the code under test
swallowed the refusal. These tests pin both halves: what is refused (the
service ports, over ``connect`` and ``connect_ex``, IPv4 and IPv6) and what is
not (the ports either side of each range, a test's own ephemeral server, a Unix
socket, the opt-out marker), which tests are armed, and that the report hook
fails a phase whose refusal was swallowed. That failure must survive an xfail,
and it must not blame the running test: a refusal made off the main thread is
recorded with the thread's name, because a thread or task an earlier test left
running fails whichever test is running when it connects.

No case here can reach a live listener: ``no_real_connect`` replaces the
guard's pass-through with a recorder, so a guard that failed to refuse would
record the address instead of connecting to it.
"""

from __future__ import annotations

import contextlib
import errno
import socket
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

TESTS_ROOT = Path(__file__).resolve().parents[1]
REFUSED = [("127.0.0.1", 8050), ("localhost", 8055), ("127.0.0.1", 8059), ("127.0.0.1", 8200), ("0.0.0.0", 8201), ("127.0.0.1", 8202), ("127.0.0.1", 8210), ("127.0.0.1", 8211)]  # nosec B104 - a connect destination, never bound
NOT_REFUSED = [8049, 8060, 8199, 8203, 8209, 8212]


@pytest.fixture
def no_real_connect(service_port_guard, monkeypatch):
    """Record what the guard lets through instead of connecting, so no case can reach a live listener."""
    passed_through = []
    monkeypatch.setattr(service_port_guard, "real_connect", lambda sock, address: passed_through.append(("connect", address)))
    monkeypatch.setattr(service_port_guard, "real_connect_ex", lambda sock, address: passed_through.append(("connect_ex", address)) or 0)
    return passed_through


class _FakeItem:
    """The two attributes ``ServicePortGuard.applies_to`` reads from a pytest item."""

    def __init__(self, relpath: str, *markers: str) -> None:
        self.path = TESTS_ROOT / relpath
        self._markers = set(markers)

    def get_closest_marker(self, name: str):
        return name if name in self._markers else None


def test_this_test_is_armed(service_port_guard, request):
    assert service_port_guard.armed_for == request.node.nodeid
    assert service_port_guard.applies_to(request.node)


@pytest.mark.parametrize("address", REFUSED)
def test_a_service_port_connect_is_refused(service_port_guard, no_real_connect, address):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(ConnectionRefusedError, match="unit-lane network guard") as refused:
            sock.connect(address)
    assert refused.value.errno == errno.ECONNREFUSED
    assert service_port_guard.take() == [f"{address[0]}:{address[1]}"]
    assert no_real_connect == []


def test_an_ipv6_service_port_connect_is_refused(service_port_guard, no_real_connect):
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
        with pytest.raises(ConnectionRefusedError, match="unit-lane network guard"):
            sock.connect(("::1", 8050, 0, 0))
    assert service_port_guard.take() == ["::1:8050"]
    assert no_real_connect == []


def test_connect_ex_reports_econnrefused(service_port_guard, no_real_connect):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        assert sock.connect_ex(("127.0.0.1", 8201)) == errno.ECONNREFUSED
    assert service_port_guard.take() == ["127.0.0.1:8201"]
    assert no_real_connect == []


def test_a_refusal_off_the_main_thread_names_the_thread(service_port_guard, no_real_connect):
    """A thread an earlier test left running fails whichever test is running when it connects, so the record names it."""

    def connect_off_the_main_thread():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock, contextlib.suppress(OSError):
            sock.connect(("127.0.0.1", 8050))

    worker = threading.Thread(target=connect_off_the_main_thread, name="left-running-by-an-earlier-test")
    worker.start()
    worker.join(timeout=10)
    assert not worker.is_alive()
    assert service_port_guard.take() == ["127.0.0.1:8050 (thread left-running-by-an-earlier-test)"]
    assert no_real_connect == []


@pytest.mark.parametrize("port", NOT_REFUSED)
def test_a_port_beside_a_service_range_passes_through(service_port_guard, no_real_connect, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(("127.0.0.1", port))
        assert sock.connect_ex(("127.0.0.1", port)) == 0
    assert no_real_connect == [("connect", ("127.0.0.1", port)), ("connect_ex", ("127.0.0.1", port))]
    assert service_port_guard.take() == []


def test_a_unix_socket_passes_through(service_port_guard, no_real_connect):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect("juniper-canopy-8050.sock")
    assert no_real_connect == [("connect", "juniper-canopy-8050.sock")]
    assert service_port_guard.take() == []


def test_the_tests_own_ephemeral_server_is_reachable(service_port_guard):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        assert port not in service_port_guard.ports
        with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
            accepted, _ = server.accept()
            with accepted:
                client.sendall(b"ping")
                assert accepted.recv(4) == b"ping"
    assert service_port_guard.take() == []


@pytest.mark.allow_service_ports
def test_the_opt_out_marker_disarms_the_guard(service_port_guard, no_real_connect):
    assert service_port_guard.armed_for is None
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(("127.0.0.1", 8050))
    assert no_real_connect == [("connect", ("127.0.0.1", 8050))]
    assert service_port_guard.take() == []


@pytest.mark.parametrize(
    ("relpath", "markers", "armed"),
    [
        ("unit/test_x.py", (), True),
        ("unit/frontend/test_x.py", (), True),
        ("regression/test_x.py", (), True),
        ("contract/test_x.py", (), True),
        ("performance/test_x.py", (), True),
        ("regression/test_x.py", ("integration",), True),
        ("integration/test_x.py", ("unit",), True),
        ("integration/test_x.py", (), False),
        ("integration/test_x.py", ("integration",), False),
        ("integration/test_x.py", ("unit", "integration"), False),
        ("ui/test_x.py", ("ui",), False),
        ("unit/test_x.py", ("e2e",), False),
        ("unit/test_x.py", ("ui",), False),
        ("unit/test_x.py", ("requires_server",), False),
        ("unit/test_x.py", ("requires_cascor",), False),
        ("unit/test_x.py", ("allow_service_ports",), False),
    ],
)
def test_the_guard_is_armed_for_the_unit_lane_only(service_port_guard, relpath, markers, armed):
    assert service_port_guard.applies_to(_FakeItem(relpath, *markers)) is armed


def test_flag_fails_a_passing_report_whose_refusal_was_swallowed(service_port_guard, no_real_connect):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock, contextlib.suppress(OSError):
        sock.connect(("127.0.0.1", 8050))
    report = SimpleNamespace(outcome="passed", failed=False, longrepr=None, sections=[])
    service_port_guard.flag(report)
    assert report.outcome == "failed"
    assert "127.0.0.1:8050" in report.longrepr
    assert report.sections == [("unit-lane network guard", report.longrepr)]
    assert service_port_guard.take() == []


def test_flag_keeps_a_failed_reports_own_traceback(service_port_guard, no_real_connect):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock, contextlib.suppress(OSError):
        sock.connect(("127.0.0.1", 8211))
    report = SimpleNamespace(outcome="failed", failed=True, longrepr="the test's own failure", sections=[])
    service_port_guard.flag(report)
    assert report.outcome == "failed"
    assert report.longrepr == "the test's own failure"
    assert "127.0.0.1:8211" in report.sections[0][1]


def test_flag_leaves_a_report_without_refusals_alone(service_port_guard):
    report = SimpleNamespace(outcome="passed", failed=False, longrepr=None, sections=[])
    service_port_guard.flag(report)
    assert report == SimpleNamespace(outcome="passed", failed=False, longrepr=None, sections=[])


def test_the_failure_message_does_not_blame_the_running_test(service_port_guard, no_real_connect):
    """The connect may come from a thread or task an earlier test left running, so the message must not say this test made it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock, contextlib.suppress(OSError):
        sock.connect(("127.0.0.1", 8050))
    report = SimpleNamespace(outcome="passed", failed=False, longrepr=None, sections=[])
    service_port_guard.flag(report)
    assert "this test connected" not in report.longrepr
    assert "a connect to 127.0.0.1:8050, a Juniper service port, was refused while this test ran" in report.longrepr
    assert "made by this test, or by a thread or task an earlier test left running" in report.longrepr


def test_flag_fails_an_xfailed_report_too(service_port_guard, no_real_connect):
    """pytest counts no failure for a report that still carries ``wasxfail``: the run would exit 0 and junit would say "skipped"."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock, contextlib.suppress(OSError):
        sock.connect(("127.0.0.1", 8050))
    report = SimpleNamespace(outcome="skipped", failed=False, longrepr="the expected failure", sections=[], wasxfail="an expected failure")
    service_port_guard.flag(report)
    assert report.outcome == "failed"
    assert not hasattr(report, "wasxfail")
    assert "127.0.0.1:8050" in report.longrepr


def test_flag_leaves_an_xfailed_report_without_refusals_alone(service_port_guard):
    report = SimpleNamespace(outcome="skipped", failed=False, longrepr="the expected failure", sections=[], wasxfail="an expected failure")
    service_port_guard.flag(report)
    assert report == SimpleNamespace(outcome="skipped", failed=False, longrepr="the expected failure", sections=[], wasxfail="an expected failure")


def test_the_report_hook_fails_a_phase_that_swallowed_a_refusal(request, no_real_connect):
    """The real ``pytest_runtest_makereport`` chain, on a synthetic phase of this test."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock, contextlib.suppress(OSError):
        sock.connect(("127.0.0.1", 8050))
    phase = pytest.CallInfo.from_call(lambda: None, when="call")
    report = request.config.hook.pytest_runtest_makereport(item=request.node, call=phase)
    assert report.failed
    assert "127.0.0.1:8050" in str(report.longrepr)
    assert no_real_connect == []


def test_the_report_hook_fails_an_xfailed_phase_too(request, no_real_connect):
    """The real chain again, on a phase pytest's own xfail handling has already turned into a skip carrying ``wasxfail``."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock, contextlib.suppress(OSError):
        sock.connect(("127.0.0.1", 8050))
    phase = pytest.CallInfo.from_call(lambda: pytest.xfail("an expected failure"), when="call")
    report = request.config.hook.pytest_runtest_makereport(item=request.node, call=phase)
    assert report.failed
    assert not hasattr(report, "wasxfail")  # pytest counts a failure only for a failed report without it
    assert "127.0.0.1:8050" in str(report.longrepr)
    assert no_real_connect == []
