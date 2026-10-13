#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       What canopy may say about a failed outbound call where a caller can read it
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     outbound_errors.py
#
# Created Date:  2026-09-24
# Last Modified: 2026-09-24
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#####################################################################################################################################################################################################
"""What canopy may say about a failed outbound call in anything a caller can read.

canopy reaches juniper-cascor, juniper-data and the recurrence service through client libraries whose exceptions
carry TRANSPORT text: the URL, the underlying socket or protocol error, and -- when a client refuses to send a header
value -- the value itself, which for ``X-API-Key`` is the key (``requests``' ``InvalidHeader``, httpx's ``Illegal
header value b'...'``, websockets' ``invalid X-API-Key header: ...``). canopy put ``str(e)`` of those exceptions into
API bodies, WebSocket broadcasts, the ``/api/status`` envelope, ``/api/stream_health`` and a failed recurrence fit's
``completion_reason`` -- surfaces an anonymous caller can read when auth is enabled (the key-exempt browser control
surface, the keyless WebSocket routes). ``secrets_util.get_outbound_secret`` stops canopy handing a client a key it
would refuse; this module is the second half (#683 validation, item 1b): none of that text reaches a caller, whatever
it holds.

The rule, :func:`outbound_error_text`:

* an exception that carries an HTTP ``status_code`` is the upstream's ANSWER -- the request reached it, so every
  header was sendable, and the text is what the upstream chose to reply (cascor's 409 "Training data not provided",
  a 422's field errors). That text passes, as PR-B2, N4 and CAN-015h deliberately surface it;
* anything else -- a client refusing to send, a connection or timeout failure, a malformed reply, any other exception
  -- is named by its TYPE only.

The full text still goes to canopy's own logs, where the operator reads it. It can no longer hold a key there: a key no
client can carry is refused where it is read.
"""

from __future__ import annotations


def outbound_error_text(exc: BaseException) -> str:
    """Describe a failed outbound call for an API body, a broadcast or a status field.

    Args:
        exc: The exception an outbound call raised.

    Returns:
        ``str(exc)`` when ``exc`` carries an integer ``status_code`` (the upstream answered, and its reply is the
        text), else -- and for an answer with no text -- ``type(exc).__name__``. It never raises: a ``status_code``
        that cannot be read counts as none.
    """
    try:
        status = getattr(exc, "status_code", None)
    except Exception:  # noqa: BLE001 -- a describer must not raise; a property that raises counts as no status
        status = None
    if isinstance(status, int) and not isinstance(status, bool):
        return str(exc) or type(exc).__name__
    return type(exc).__name__
