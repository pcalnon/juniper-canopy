#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_internal_api_key_rules.py
# File Path:     src/tests/unit/frontend/
#
# Created Date:  2026-09-24
# Last Modified: 2026-09-24
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     #678 follow-up. ``frontend/internal_api.py`` read CANOPY_API_KEY raw for the dashboard's self-calls. A
#     whitespace-only key leaves auth disabled (``security.APIKeyAuth``), yet every self-call sent it, and ``requests``
#     refuses a header value that starts with whitespace, so each one raised ``InvalidHeader``. A PADDED key -- auth
#     enabled -- failed the same way, and that exception's message quotes the whole value: the dashboard's handlers
#     logged the real key. The self-call now sends no key that is blank, and none that ``requests`` refuses to send.
#     tests/regression/test_blank_api_key_warning_boot.py pins the same rules in a fresh canopy process.
#
#####################################################################################################################################################################################################
"""Unit tests: the self-call ``X-API-Key`` follows the blank-key rule and never carries a key ``requests`` refuses."""

import pytest
import requests

from frontend import internal_api

# (id, value) pairs; the ids keep test names stable for the mutation check's expectations.
# Each is empty or whitespace-only by ``str.strip()`` -- the rule ``APIKeyAuth`` applies.
BLANK = [("empty", ""), ("space", " "), ("3-spaces", "   "), ("tab", "\t"), ("space-tab-space", " \t "), ("lf", "\n"), ("crlf", "\r\n"), ("nbsp", "\xa0"), ("nel", "\x85"), ("fs-us", "\x1c\x1f"), ("em-space", "\u2003")]
# Not blank, so auth is ENABLED on them, but ``requests`` refuses to send them and its refusal quotes them: each starts
# with whitespace or holds a line break.
REFUSED_BY_REQUESTS = [
    ("leading-space", " real-key"),
    ("leading-tab", "\treal-key"),
    ("both-sides", "  real-key\t "),
    ("trailing-lf", "real-key\n"),
    ("trailing-crlf", "real-key\r\n"),
    ("inner-crlf", "real\r\nkey"),
    ("inner-lf", "real\nkey"),
    ("leading-nbsp", "\xa0real-key"),
    ("leading-fs", "\x1creal-key"),
    ("leading-em-space", "\u2003real-key"),
]
# ``requests`` sends these as set, so the self-call must present them exactly as set: whatever it presents is compared,
# unstripped, with the key auth was enabled on.
SENT_AS_SET = [("clean", "real-key"), ("inner-space", "real key"), ("inner-tab", "real\tkey"), ("trailing-space", "real-key "), ("trailing-tab", "real-key\t"), ("trailing-nbsp", "real-key\xa0")]


def _values(cases):
    return [value for _, value in cases]


def _ids(cases):
    return [case_id for case_id, _ in cases]


@pytest.fixture
def self_call_headers(monkeypatch):
    """``internal_api_headers()`` for a CANOPY_API_KEY env value, read afresh (the key is cached per process)."""

    def headers_for(value):
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        if value is None:
            monkeypatch.delenv("CANOPY_API_KEY", raising=False)
        else:
            monkeypatch.setenv("CANOPY_API_KEY", value)
        internal_api._canopy_api_key.cache_clear()
        return internal_api.internal_api_headers()

    try:
        yield headers_for
    finally:
        internal_api._canopy_api_key.cache_clear()


def _prepare(headers):
    return requests.Request("GET", "http://127.0.0.1:8050/api/status", headers=headers).prepare()


@pytest.mark.unit
@pytest.mark.parametrize("value", _values(BLANK), ids=_ids(BLANK))
def test_a_blank_key_puts_no_key_on_a_self_call(self_call_headers, value):
    """Exactly as with no key configured: a blank key is no key, and auth is off."""
    assert "X-API-Key" not in self_call_headers(value)


@pytest.mark.unit
@pytest.mark.parametrize("value", _values(BLANK), ids=_ids(BLANK))
def test_a_blank_key_is_no_key_whatever_requests_would_send(self_call_headers, monkeypatch, value):
    """The blank rule stands on its own. Today ``requests`` also refuses every non-empty blank value (each starts with
    whitespace), which would hide the rule's absence; with that refusal taken away, a blank key is still no key."""
    monkeypatch.setattr(internal_api, "_requests_can_send", lambda key: True)
    assert "X-API-Key" not in self_call_headers(value)


@pytest.mark.unit
@pytest.mark.parametrize("value", _values(REFUSED_BY_REQUESTS), ids=_ids(REFUSED_BY_REQUESTS))
def test_a_key_requests_refuses_to_send_is_left_off_the_self_call(self_call_headers, value):
    # The premise, checked rather than assumed: requests refuses it, quoting it.
    with pytest.raises(requests.exceptions.InvalidHeader) as refused:
        _prepare({"X-API-Key": value})
    assert repr(value) in str(refused.value)

    assert "X-API-Key" not in self_call_headers(value)


@pytest.mark.unit
@pytest.mark.parametrize("value", _values(SENT_AS_SET), ids=_ids(SENT_AS_SET))
def test_a_key_requests_sends_goes_on_the_self_call_exactly_as_set(self_call_headers, value):
    assert self_call_headers(value)["X-API-Key"] == value


@pytest.mark.unit
@pytest.mark.parametrize("value", [None, *_values(BLANK), *_values(REFUSED_BY_REQUESTS), *_values(SENT_AS_SET)], ids=["unset", *_ids(BLANK), *_ids(REFUSED_BY_REQUESTS), *_ids(SENT_AS_SET)])
def test_every_self_call_header_set_is_one_requests_can_send(self_call_headers, value):
    """The invariant behind the leak fix. Every self-call sends ``internal_api_headers()``, and ``requests`` raises
    ``InvalidHeader`` while preparing the headers. If it accepts these, no self-call can raise one quoting the key."""
    _prepare(self_call_headers(value))


@pytest.mark.unit
def test_a_key_file_is_stripped_before_the_rules_apply(self_call_headers, monkeypatch, tmp_path):
    secret_file = tmp_path / "canopy_api_key"
    secret_file.write_text("  real-key\t\n", encoding="utf-8")
    headers = self_call_headers("env-key-the-file-overrides")
    assert headers["X-API-Key"] == "env-key-the-file-overrides"
    monkeypatch.setenv("CANOPY_API_KEY_FILE", str(secret_file))
    internal_api._canopy_api_key.cache_clear()
    assert internal_api.internal_api_headers()["X-API-Key"] == "real-key"
