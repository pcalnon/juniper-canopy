#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Helper for canopy dashboard server-side self-calls under API-key auth
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     internal_api.py
#
# Created Date:  2026-05-10
# Last Modified: 2026-05-10
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#####################################################################################################################################################################################################
"""Helpers for canopy frontend's server-side self-calls.

The Dash dashboard makes server-side HTTP requests to canopy's own
FastAPI routes — e.g. ``requests.get("http://127.0.0.1:8050/api/status")``
fired from a callback handler. When a non-empty ``CANOPY_API_KEY`` is
configured (the deploy-stack and production default), those routes
enforce the API key via ``SecurityMiddleware`` and reject anonymous
requests with 401, breaking every dashboard panel.

This module supplies the matching ``X-API-Key`` header so the
dashboard's self-calls succeed under production auth. Call sites should
add ``headers=internal_api_headers()`` to every ``requests.{get,post,
put,delete,patch}(...)`` that targets ``self._api_url(...)`` /
``self._api_base_url`` URLs.

Long-term direction (Option C, deferred — see
juniper-ml/notes/observability/JUNIPER_2026-05-10_JUNIPER-CANOPY_DASHBOARD-SELF-CALL-REFACTOR.md):
the HTTP self-call indirection should be replaced with direct in-process
function calls into the FastAPI route handlers, eliminating the
serialize/deserialize round-trip and the metric-noise contribution. This
helper is a stepping stone — it closes the immediate auth-enabled
breakage and remains useful for any sites Option C cannot easily
migrate (async/sync impedance, FastAPI dependency injection).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict

from secrets_util import get_secret
from security import INTERNAL_REQUEST_HEADER, INTERNAL_REQUEST_TOKEN


@lru_cache(maxsize=1)
def _canopy_api_key() -> str | None:
    """Read the canopy API key once per process.

    Cached to avoid re-reading the docker-secret file on every panel
    refresh. Process restart picks up rotations.
    """
    key = get_secret("CANOPY_API_KEY")
    return key or None


def internal_api_headers() -> Dict[str, str]:
    """Headers required for server-side self-calls into canopy's own API.

    Always includes the per-process internal-request token
    (``INTERNAL_REQUEST_HEADER``) so canopy's own rate limiter exempts these
    self-calls (#2a) — the dashboard's high-frequency polling must not drain the
    shared bucket that real user actions depend on. Adds ``X-API-Key`` when
    ``CANOPY_API_KEY`` is configured (production / deploy-stack); the token is
    sent in open-access mode too (it's harmless and the rate limiter can be
    enabled independently of API-key auth). Merge with any other headers via
    ``{**headers, **other}`` if a call site already passes a ``headers=`` kwarg.
    """
    headers: Dict[str, str] = {INTERNAL_REQUEST_HEADER: INTERNAL_REQUEST_TOKEN}
    key = _canopy_api_key()
    if key:
        headers["X-API-Key"] = key
    return headers
