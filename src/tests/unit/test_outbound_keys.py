#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_outbound_keys.py
# File Path:     src/tests/unit/
#
# Created Date:  2026-09-24
# Last Modified: 2026-09-24
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     #683 validation, item 1. canopy sends three outbound keys (juniper-cascor, juniper-data, recurrence), read raw
#     from the environment. A key with padding or a character an HTTP client cannot carry made the client refuse to
#     send it and QUOTE it in the exception, which canopy logged at ERROR, Sentry received, and canopy returned in API
#     bodies an anonymous caller could read. ``secrets_util.get_outbound_secret`` now refuses such a value where it is
#     read, records the variable NAME for a boot WARNING, and ``bind_outbound_key`` stops the client libraries from
#     reading the same variables again on their own. These tests pin the rule, the WARNING, and -- against the REAL
#     client classes -- that no refused key is ever handed to one.
#
#####################################################################################################################################################################################################
"""Unit tests: an outbound key no HTTP client can carry is refused where it is read, reported by name, and never sent."""

import asyncio
import logging
from types import SimpleNamespace

import pytest
import requests

import secrets_util
from secrets_util import bind_outbound_key, get_outbound_secret, is_sendable_key, report_refused_outbound_keys, reset_outbound_key_findings, screen_outbound_key

_jcc = pytest.importorskip("juniper_cascor_client", reason="juniper-cascor-client not installed")
if getattr(_jcc, "_is_stub", False):
    pytest.skip("juniper-cascor-client is a test stub, not the real package", allow_module_level=True)

import juniper_cascor_client.ws_client as _cascor_ws_client  # noqa: E402
import juniper_data_client  # noqa: E402
from juniper_cascor_client import CascorControlStream, CascorTrainingStream, JuniperCascorClient  # noqa: E402
from juniper_cascor_client.exceptions import JuniperCascorConnectionError  # noqa: E402

# The REAL data client, captured at collection: the session-wide ``mock_juniper_data_client`` fixture replaces
# ``juniper_data_client.JuniperDataClient`` with a MagicMock before any test runs, and a mock has no env fallback to undo.
# CI's unit lane installs no ``[juniper-data]`` extra, so there it is canopy's conftest stub: the tests that need the
# real class skip, and ``TestDemoModeBindsTheDataClient`` below pins canopy's own call sites with a stand-in instead.
JuniperDataClient = juniper_data_client.JuniperDataClient
requires_real_data_client = pytest.mark.skipif(getattr(juniper_data_client, "__version__", "") == "0.0.0-stub", reason="juniper-data-client is canopy's conftest stub here")

# Written out rather than imported: an expectation imported from the module under test moves with any mutant that
# rewrites it, and passes.
ENV_WARNING = (
    "{var} holds a key canopy does not send: it has leading or trailing whitespace, or a character outside printable ASCII (0x21-0x7E) such as a line break, a space or a non-ASCII character. " + "HTTP clients refuse such a header value, and the error they raise quotes it. " + "Canopy treats {var} as empty instead, so no client is handed the key: a request it would have authenticated carries the next key canopy falls back to, or none. Remove the whitespace, line break or non-ASCII character from {var}."
)
FILE_WARNING = (
    "The file named by {var} holds a key canopy does not send: with its leading and trailing whitespace stripped, the key still holds a character outside printable ASCII (0x21-0x7E) such as a line break, a space or a non-ASCII character. "
    + "HTTP clients refuse such a header value, and the error they raise quotes it. "
    + "Canopy treats the key as empty instead, so no client is handed it: a request it would have authenticated carries the next key canopy falls back to, or none. Write the key into that file on one line, with no space or non-ASCII character in it."
)

# (id, value): every one is refused. The ids keep test names stable for the mutation check.
REFUSED = [
    ("leading-space", " LEAKME-key"),
    ("trailing-space", "LEAKME-key "),
    ("leading-tab", "\tLEAKME-key"),
    ("trailing-lf", "LEAKME-key\n"),
    ("trailing-crlf", "LEAKME-key\r\n"),
    ("inner-lf", "LEAKME\nkey"),
    ("inner-vt", "LEAKME\x0bkey"),
    ("inner-space", "LEAKME key"),
    ("inner-tab", "LEAKME\tkey"),
    ("del", "LEAKME-key\x7f"),
    ("unit-separator", "LEAKME\x1fkey"),
    ("nbsp", "LEAKME-key\xa0"),
    ("latin1", "LEAKME-cl\xe9"),
    ("euro", "LEAKME-euro€"),
    ("whitespace-only", "   "),
]
# Every printable ASCII character other than space, and a typical generated key.
SENDABLE = [("token", "k9-Xy_Z.~abc123"), ("urlsafe", "jJ3kWq8Yt0vN-r5_bCd2eFgHiJkLmNoP"), ("every-printable", "".join(chr(c) for c in range(0x21, 0x7F)))]

ALL_OUTBOUND_VARS = (
    "JUNIPER_CASCOR_API_KEY",
    "JUNIPER_CASCOR_API_KEY_FILE",
    "JUNIPER_DATA_API_KEY",
    "JUNIPER_DATA_API_KEY_FILE",
    "JUNIPER_CANOPY_JUNIPER_DATA_API_KEY",
    "JUNIPER_CANOPY_JUNIPER_DATA_API_KEY_FILE",
    "JUNIPER_RECURRENCE_API_KEY",
    "JUNIPER_RECURRENCE_API_KEY_FILE",
    "JUNIPER_CANOPY_RECURRENCE_API_KEY",
    "JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE",
)


def _ids(cases):
    return [case_id for case_id, _ in cases]


def _values(cases):
    return [value for _, value in cases]


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def clean(monkeypatch):
    """No outbound key in the environment, and no refusal recorded, before and after."""
    for name in ALL_OUTBOUND_VARS:
        monkeypatch.delenv(name, raising=False)
    reset_outbound_key_findings()
    yield monkeypatch
    reset_outbound_key_findings()


@pytest.fixture
def report_log():
    log = logging.getLogger("tests.unit.test_outbound_keys")
    log.setLevel(logging.DEBUG)
    log.propagate = False
    handler = _ListHandler()
    log.addHandler(handler)
    try:
        yield log, handler.records
    finally:
        log.removeHandler(handler)


@pytest.mark.unit
class TestTheRule:
    @pytest.mark.parametrize("value", _values(REFUSED), ids=_ids(REFUSED))
    def test_a_value_some_client_cannot_carry_is_not_sendable(self, value):
        assert is_sendable_key(value) is False

    @pytest.mark.parametrize("value", _values(SENDABLE), ids=_ids(SENDABLE))
    def test_printable_ascii_other_than_space_is_sendable(self, value):
        assert is_sendable_key(value) is True

    def test_the_empty_string_is_not_a_sendable_key(self):
        assert is_sendable_key("") is False

    def test_a_nul_is_not_sendable(self):
        """Not in REFUSED only because no environment variable can hold one."""
        assert is_sendable_key("LEAKME\x00key") is False

    @pytest.mark.parametrize("value", _values(SENDABLE), ids=_ids(SENDABLE))
    def test_every_sendable_key_is_one_requests_will_send(self, value):
        """The rule is at least as strict as the client canopy uses most: what it passes, ``requests`` sends."""
        requests.Request("GET", "http://127.0.0.1/", headers={"X-API-Key": value}).prepare()


@pytest.mark.unit
class TestReadWhereRead:
    @pytest.mark.parametrize("value", _values(REFUSED), ids=_ids(REFUSED))
    def test_a_refused_env_value_reads_as_none_and_is_recorded_by_name(self, clean, report_log, value):
        log, records = report_log
        clean.setenv("JUNIPER_DATA_API_KEY", value)
        assert get_outbound_secret("JUNIPER_DATA_API_KEY") is None
        assert report_refused_outbound_keys(log) == 1
        assert [(r.levelno, r.getMessage()) for r in records] == [(logging.WARNING, ENV_WARNING.format(var="JUNIPER_DATA_API_KEY"))]

    @pytest.mark.parametrize("value", _values(SENDABLE), ids=_ids(SENDABLE))
    def test_a_sendable_env_value_is_returned_exactly(self, clean, report_log, value):
        log, records = report_log
        clean.setenv("JUNIPER_CASCOR_API_KEY", value)
        assert get_outbound_secret("JUNIPER_CASCOR_API_KEY") == value
        assert report_refused_outbound_keys(log) == 0
        assert records == []

    def test_a_key_file_is_stripped_and_then_screened(self, clean, report_log, tmp_path):
        """A key file loses its ends to the strip, so only a character INSIDE the key can be refused -- worded for the file."""
        log, records = report_log
        good = tmp_path / "good"
        good.write_text("  real-key-1\n", encoding="utf-8")
        clean.setenv("JUNIPER_RECURRENCE_API_KEY_FILE", str(good))
        assert get_outbound_secret("JUNIPER_RECURRENCE_API_KEY") == "real-key-1"
        two_lines = tmp_path / "two-lines"
        two_lines.write_text("LEAKME-first\nsecond\n", encoding="utf-8")
        clean.setenv("JUNIPER_RECURRENCE_API_KEY_FILE", str(two_lines))
        # The env var holds a real key, and the file still wins: a refused file is an EMPTY file, not an unset one.
        clean.setenv("JUNIPER_RECURRENCE_API_KEY", "real-env-key")
        assert get_outbound_secret("JUNIPER_RECURRENCE_API_KEY") is None
        assert report_refused_outbound_keys(log) == 1
        assert [r.getMessage() for r in records] == [FILE_WARNING.format(var="JUNIPER_RECURRENCE_API_KEY_FILE")]

    @pytest.mark.parametrize("value", [None, ""], ids=["unset", "empty"])
    def test_unset_and_empty_are_the_absence_of_a_key_not_a_finding(self, clean, report_log, value):
        log, records = report_log
        if value is not None:
            clean.setenv("JUNIPER_DATA_API_KEY", value)
        assert get_outbound_secret("JUNIPER_DATA_API_KEY") == value
        assert report_refused_outbound_keys(log) == 0
        assert records == []

    def test_screening_an_already_read_value_records_the_name_given(self, clean, report_log):
        log, records = report_log
        assert screen_outbound_key("real-key", "SOME_VAR") == "real-key"
        assert screen_outbound_key(" LEAKME", "JUNIPER_CANOPY_JUNIPER_DATA_API_KEY") is None
        assert report_refused_outbound_keys(log) == 1
        assert [r.getMessage() for r in records] == [ENV_WARNING.format(var="JUNIPER_CANOPY_JUNIPER_DATA_API_KEY")]


@pytest.mark.unit
class TestTheReport:
    def test_each_variable_is_reported_once_however_often_it_is_read(self, clean, report_log):
        """Settings are rebuilt, and the lifespan reports twice: each refused variable is ONE WARNING per process."""
        log, records = report_log
        clean.setenv("JUNIPER_DATA_API_KEY", " LEAKME-data")
        clean.setenv("JUNIPER_CASCOR_API_KEY", "LEAKME-cascor\n")
        outcomes = []
        for _ in range(3):
            get_outbound_secret("JUNIPER_DATA_API_KEY")
            get_outbound_secret("JUNIPER_CASCOR_API_KEY")
            outcomes.append(report_refused_outbound_keys(log))
        assert outcomes == [2, 0, 0]
        assert [r.getMessage() for r in records] == [ENV_WARNING.format(var="JUNIPER_DATA_API_KEY"), ENV_WARNING.format(var="JUNIPER_CASCOR_API_KEY")]

    def test_a_variable_first_read_after_a_report_is_reported_by_the_next(self, clean, report_log):
        """The lifespan reports after the import-time reads, and again after ``create_backend`` reads the cascor key."""
        log, records = report_log
        clean.setenv("JUNIPER_DATA_API_KEY", " LEAKME-data")
        get_outbound_secret("JUNIPER_DATA_API_KEY")
        assert report_refused_outbound_keys(log) == 1
        clean.setenv("JUNIPER_CASCOR_API_KEY", " LEAKME-cascor")
        get_outbound_secret("JUNIPER_CASCOR_API_KEY")
        assert report_refused_outbound_keys(log) == 1
        assert [r.getMessage() for r in records] == [ENV_WARNING.format(var="JUNIPER_DATA_API_KEY"), ENV_WARNING.format(var="JUNIPER_CASCOR_API_KEY")]

    def test_the_report_carries_names_never_a_key_or_a_path(self, clean, report_log, tmp_path):
        log, records = report_log
        key_file = tmp_path / "leaked-path-QRS"
        key_file.write_text("LEAKME-file\nkey", encoding="utf-8")
        clean.setenv("JUNIPER_DATA_API_KEY_FILE", str(key_file))
        clean.setenv("JUNIPER_CASCOR_API_KEY", " LEAKME-env-TUV")
        get_outbound_secret("JUNIPER_DATA_API_KEY")
        get_outbound_secret("JUNIPER_CASCOR_API_KEY")
        assert report_refused_outbound_keys(log) == 2
        rendered = [r.getMessage() + repr(r.__dict__) for r in records]
        assert not [text for text in rendered if "LEAKME" in text or "leaked-path-QRS" in text]

    def test_the_report_needs_no_second_read_of_the_secret(self, clean, report_log):
        log, records = report_log
        clean.setenv("JUNIPER_RECURRENCE_API_KEY", " LEAKME")
        get_outbound_secret("JUNIPER_RECURRENCE_API_KEY")
        clean.delenv("JUNIPER_RECURRENCE_API_KEY")
        assert report_refused_outbound_keys(log) == 1
        assert [r.getMessage() for r in records] == [ENV_WARNING.format(var="JUNIPER_RECURRENCE_API_KEY")]

    def test_reset_forgets_every_refusal(self, clean, report_log):
        log, records = report_log
        clean.setenv("JUNIPER_DATA_API_KEY", " LEAKME")
        get_outbound_secret("JUNIPER_DATA_API_KEY")
        reset_outbound_key_findings()
        assert report_refused_outbound_keys(log) == 0
        get_outbound_secret("JUNIPER_DATA_API_KEY")
        assert report_refused_outbound_keys(log) == 1
        assert len(records) == 1

    def test_conftest_resets_the_findings_between_tests(self):
        """``_reset_all_singletons`` owns this state too; a refusal recorded by one test must not report in the next."""
        import sys

        # The conftest pytest already loaded -- importing it again would register its fixtures twice.
        conftest = next(module for name, module in sys.modules.items() if name.endswith("conftest") and hasattr(module, "_reset_all_singletons"))
        secrets_util.screen_outbound_key(" LEAKME", "JUNIPER_DATA_API_KEY")
        conftest._reset_all_singletons()
        assert secrets_util._refused_outbound_keys == {}


# ---------------------------------------------------------------------------------------------------------------------
# The client libraries' own env fallback. Handed a falsy key, every juniper client reads the SAME variables itself
# (``api_key or os.environ.get(...)``) -- raw, bypassing the screen. ``bind_outbound_key`` undoes that. These use the
# real classes, so a client release that changes where it keeps the key fails here rather than silently re-opening.
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.unit
class TestTheClientsReadTheirOwnFallback:
    """The precondition: without ``bind_outbound_key`` each client WOULD send the raw env value. Guards vacuity."""

    def test_the_cascor_rest_client_reads_the_env_var_when_handed_no_key(self, clean):
        clean.setenv("JUNIPER_CASCOR_API_KEY", " LEAKME-cascor")
        client = JuniperCascorClient(base_url="http://127.0.0.1:9", api_key=None)
        assert client.api_key == " LEAKME-cascor"
        assert client.session.headers.get("X-API-Key") == " LEAKME-cascor"

    @pytest.mark.parametrize("stream_class", [CascorTrainingStream, CascorControlStream], ids=["training", "control"])
    def test_the_cascor_streams_read_the_env_var_when_handed_no_key(self, clean, stream_class):
        clean.setenv("JUNIPER_CASCOR_API_KEY", "LEAKME-cascor\n")
        assert stream_class(base_url="ws://127.0.0.1:9", api_key=None).api_key == "LEAKME-cascor\n"

    @requires_real_data_client
    def test_the_data_client_reads_the_env_var_when_handed_no_key(self, clean):
        clean.setenv("JUNIPER_DATA_API_KEY", " LEAKME-data")
        client = JuniperDataClient(base_url="http://127.0.0.1:9", api_key=None)
        assert client.session.headers.get("X-API-Key") == " LEAKME-data"


@pytest.mark.unit
class TestBindOutboundKey:
    def test_the_cascor_rest_client_sends_no_key_it_read_itself(self, clean):
        clean.setenv("JUNIPER_CASCOR_API_KEY", " LEAKME-cascor")
        client = bind_outbound_key(JuniperCascorClient(base_url="http://127.0.0.1:9", api_key=None), None)
        assert client.api_key is None
        assert "X-API-Key" not in client.session.headers

    @pytest.mark.parametrize("stream_class", [CascorTrainingStream, CascorControlStream], ids=["training", "control"])
    def test_the_cascor_websocket_streams_send_no_key_they_read_themselves(self, clean, stream_class):
        clean.setenv("JUNIPER_CASCOR_API_KEY", "LEAKME-cascor\n")
        stream = bind_outbound_key(stream_class(base_url="ws://127.0.0.1:9", api_key=None), None)
        assert stream.api_key is None

    @requires_real_data_client
    def test_the_data_client_sends_no_key_it_read_itself(self, clean, tmp_path):
        key_file = tmp_path / "key"
        key_file.write_text("LEAKME-data\nkey", encoding="utf-8")
        clean.setenv("JUNIPER_DATA_API_KEY_FILE", str(key_file))
        client = bind_outbound_key(JuniperDataClient(base_url="http://127.0.0.1:9", api_key=None), None)
        assert "X-API-Key" not in client.session.headers

    def test_a_key_canopy_resolved_is_sent_exactly(self, clean):
        clean.setenv("JUNIPER_CASCOR_API_KEY", " LEAKME-env")
        rest = bind_outbound_key(JuniperCascorClient(base_url="http://127.0.0.1:9", api_key="real-key"), "real-key")
        assert rest.api_key == "real-key"
        assert rest.session.headers["X-API-Key"] == "real-key"
        stream = bind_outbound_key(CascorControlStream(base_url="ws://127.0.0.1:9", api_key="real-key"), "real-key")
        assert stream.api_key == "real-key"

    @requires_real_data_client
    def test_a_data_key_canopy_resolved_is_sent_exactly(self, clean):
        clean.setenv("JUNIPER_DATA_API_KEY", " LEAKME-env")
        data = bind_outbound_key(JuniperDataClient(base_url="http://127.0.0.1:9", api_key="real-data-key"), "real-data-key")
        assert data.session.headers["X-API-Key"] == "real-data-key"

    @pytest.mark.parametrize("stream_class", [CascorTrainingStream, CascorControlStream], ids=["training", "control"])
    def test_the_websocket_handshake_carries_no_refused_key(self, clean, monkeypatch, stream_class):
        """At the wire seam: what ``websockets.connect`` is asked to send, for a real stream. websockets 16.0 SENDS a
        line break raw (header injection); 17.1 refuses it and quotes the key in ``InvalidHeaderValue``."""
        sent = []

        async def fake_connect(url, **kwargs):
            sent.append(dict(kwargs.get("additional_headers") or {}))
            raise OSError("refused")

        monkeypatch.setattr(_cascor_ws_client.websockets, "connect", fake_connect)
        clean.setenv("JUNIPER_CASCOR_API_KEY", "LEAKME-cascor\n")
        stream = bind_outbound_key(stream_class(base_url="ws://127.0.0.1:9", api_key=None), None)
        with pytest.raises(JuniperCascorConnectionError):
            asyncio.run(stream.connect())
        assert sent == [{}]


# ---------------------------------------------------------------------------------------------------------------------
# canopy's own call sites. ``create_backend`` refuses the padded key and hands the adapter None; every client the
# adapter builds must then send nothing -- the REST client, the /ws/control supervisor's stream and the metrics relay's
# stream -- and the stream-health reason /api/stream_health serves must not carry the refusal's text.
# ---------------------------------------------------------------------------------------------------------------------


def _recording_connect(sent: list, on_call=None):
    async def fake_connect(url, **kwargs):
        sent.append(dict(kwargs.get("additional_headers") or {}))
        if on_call is not None:
            on_call()
        # The refusal a real websockets 17.1 raises for such a key, text and all.
        raise OSError(f"invalid X-API-Key header: {' LEAKME-cascor'}")

    return fake_connect


@pytest.mark.unit
class TestTheAdapterBindsEveryClient:
    def test_create_backend_hands_the_adapter_no_refused_key(self, clean):
        from backend import create_backend

        clean.setenv("JUNIPER_CASCOR_API_KEY", " LEAKME-cascor")
        backend = create_backend(service_url="http://127.0.0.1:9", demo_mode=False)
        adapter = backend._adapter
        assert adapter._api_key is None
        assert adapter._client.api_key is None
        assert "X-API-Key" not in adapter._client.session.headers
        assert adapter._control_supervisor._api_key is None

    def test_a_refused_cascor_key_falls_back_to_the_data_key_as_an_empty_one_does(self, clean):
        from backend import create_backend

        clean.setenv("JUNIPER_CASCOR_API_KEY", " LEAKME-cascor")
        clean.setenv("JUNIPER_DATA_API_KEY", "real-shared-key")
        adapter = create_backend(service_url="http://127.0.0.1:9", demo_mode=False)._adapter
        assert adapter._api_key == "real-shared-key"
        assert adapter._client.session.headers["X-API-Key"] == "real-shared-key"

    async def test_the_control_supervisor_sends_no_key_and_serves_no_refusal_text(self, clean, monkeypatch):
        from backend.cascor_service_adapter import ControlStreamSupervisor

        clean.setenv("JUNIPER_CASCOR_API_KEY", " LEAKME-cascor")
        supervisor = ControlStreamSupervisor(ws_url="ws://127.0.0.1:9", api_key=None)
        sent: list = []

        def stop():
            supervisor._shutdown = True

        async def no_sleep(_delay):
            return None

        monkeypatch.setattr(_cascor_ws_client.websockets, "connect", _recording_connect(sent, stop))
        monkeypatch.setattr(asyncio, "sleep", no_sleep)
        await supervisor._connect_loop()
        assert sent == [{}]
        assert supervisor.health.snapshot()["last_disconnect_reason"] == "JuniperCascorConnectionError"

    async def test_the_metrics_relay_sends_no_key_and_serves_no_refusal_text(self, clean, monkeypatch):
        from backend.cascor_service_adapter import CascorServiceAdapter

        clean.setenv("JUNIPER_CASCOR_API_KEY", " LEAKME-cascor")
        adapter = CascorServiceAdapter(service_url="http://127.0.0.1:9", api_key=None)
        sent: list = []
        monkeypatch.setattr(_cascor_ws_client.websockets, "connect", _recording_connect(sent))
        await adapter.start_metrics_relay()
        try:
            for _ in range(500):
                if adapter.relay_health.snapshot()["last_disconnect_reason"] is not None:
                    break
                await asyncio.sleep(0.01)
        finally:
            await adapter.stop_metrics_relay()
        assert sent and all(headers == {} for headers in sent)
        assert adapter.relay_health.snapshot()["last_disconnect_reason"] == "JuniperCascorConnectionError"


class _EnvFallbackDataClient:
    """Stand-in for juniper-data-client 0.5.0's constructor: a falsy key falls back to the environment, raw.

    canopy's call sites are pinned with this rather than the real class because CI installs no juniper-data-client
    (canopy's conftest stubs it); ``TestTheClientsReadTheirOwnFallback`` pins the real class's fallback where it exists.
    """

    seen: list = []

    def __init__(self, base_url, api_key=None, on_request=None, **_kwargs):
        import os

        self.session = requests.Session()
        resolved = api_key or os.environ.get("JUNIPER_DATA_API_KEY")
        if resolved:
            self.session.headers["X-API-Key"] = resolved

    def create_dataset(self, *args, **kwargs):
        type(self).seen.append(self.session.headers.get("X-API-Key"))
        from juniper_data_client.exceptions import JuniperDataClientError

        raise JuniperDataClientError("stop here")


@pytest.mark.unit
class TestDemoModeBindsTheDataClient:
    @pytest.fixture
    def fake_client(self, monkeypatch):
        _EnvFallbackDataClient.seen = []
        monkeypatch.setattr(juniper_data_client, "JuniperDataClient", _EnvFallbackDataClient)
        return _EnvFallbackDataClient

    def _self(self):
        from demo_mode import DemoMode

        return SimpleNamespace(logger=logging.getLogger("tests.unit.test_outbound_keys.demo"), _user_friendly_data_error=DemoMode._user_friendly_data_error)

    def test_the_spiral_fetch_sends_no_key_the_client_read_itself(self, clean, fake_client):
        from juniper_data_client.exceptions import JuniperDataClientError

        from demo_mode import DemoMode

        clean.setenv("JUNIPER_DATA_API_KEY", " LEAKME-data")
        with pytest.raises(JuniperDataClientError):
            DemoMode._generate_spiral_dataset_from_juniper_data(self._self(), 200, "http://127.0.0.1:9", juniper_data_api_key=None)
        assert fake_client.seen == [None]

    def test_the_generator_fetch_sends_no_refused_key(self, clean, fake_client):
        """Here the key comes from ``settings``, which refuses it; the client's own fallback must not bring it back."""
        from juniper_data_client.exceptions import JuniperDataClientError

        from demo_mode import DemoMode

        clean.setenv("JUNIPER_DATA_API_KEY", " LEAKME-data")
        clean.setenv("JUNIPER_DATA_URL", "http://127.0.0.1:9")
        with pytest.raises(JuniperDataClientError):
            DemoMode.regenerate_dataset_from_generator(self._self(), "xor")
        assert fake_client.seen == [None]

    def test_a_resolved_data_key_is_sent(self, clean, fake_client):
        from juniper_data_client.exceptions import JuniperDataClientError

        from demo_mode import DemoMode

        clean.setenv("JUNIPER_DATA_API_KEY", "real-data-key")
        clean.setenv("JUNIPER_DATA_URL", "http://127.0.0.1:9")
        with pytest.raises(JuniperDataClientError):
            DemoMode.regenerate_dataset_from_generator(self._self(), "xor")
        assert fake_client.seen == ["real-data-key"]
