"""Per-file coverage gate: the API-key-configured branch of internal_api_headers.

``src/frontend/internal_api.py`` line 78 — the ``headers["X-API-Key"] = key``
branch taken when a non-empty ``CANOPY_API_KEY`` is configured (the deploy-stack
/ production default) — was uncovered because existing tests only exercised the
open-access (no key) path. This real test drives the configured path and asserts
the header is added alongside the always-present internal-request token, giving
the per-file coverage gate (juniper-ml per-file rollout C-5) margin on this small
module.
"""

from __future__ import annotations

from frontend import internal_api
from security import INTERNAL_REQUEST_HEADER, INTERNAL_REQUEST_TOKEN


def test_internal_api_headers_includes_api_key_when_configured(monkeypatch) -> None:
    """When CANOPY_API_KEY resolves to a value, X-API-Key is added to the headers."""
    monkeypatch.setattr(internal_api, "get_secret", lambda name: "secret-key-123" if name == "CANOPY_API_KEY" else None)
    # _canopy_api_key is lru_cache'd; clear so the patched get_secret is read.
    internal_api._canopy_api_key.cache_clear()
    try:
        headers = internal_api.internal_api_headers()
        assert headers.get("X-API-Key") == "secret-key-123"
        # The internal-request token is always present (rate-limiter exemption).
        assert headers[INTERNAL_REQUEST_HEADER] == INTERNAL_REQUEST_TOKEN
    finally:
        internal_api._canopy_api_key.cache_clear()


def test_internal_api_headers_omits_api_key_when_unset(monkeypatch) -> None:
    """With no CANOPY_API_KEY, only the internal-request token is present (no X-API-Key)."""
    monkeypatch.setattr(internal_api, "get_secret", lambda name: None)
    internal_api._canopy_api_key.cache_clear()
    try:
        headers = internal_api.internal_api_headers()
        assert "X-API-Key" not in headers
        assert headers[INTERNAL_REQUEST_HEADER] == INTERNAL_REQUEST_TOKEN
    finally:
        internal_api._canopy_api_key.cache_clear()
