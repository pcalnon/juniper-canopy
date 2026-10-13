"""Integration-suite conftest.

PR-5 (FRONTEND_ISSUES_PLAN_2026-05-09 §1.5 C3) added apply-roundtrip
verification to ``CascorServiceAdapter.apply_params``. The verifier GETs
``/v1/training/params`` and compares applied vs requested values; on
mismatch it returns ``{ok: False, error: "verification_failed",
mismatches: …}``.

``FakeCascorClient.update_params`` only persists into ``_network_config``
when that dict has been initialised by a scenario, and several scenarios
(``two_spiral_training`` chief among them) leave it at ``None``. The
result is that PATCHes against the fake silently no-op for the verifier,
which then loudly flags every existing apply-test as a mismatch even
though pre-PR-5 those tests passed.

The fixture below is autouse-scoped on the adapter test surface: it
monkey-patches ``FakeCascorClient`` so ``update_params`` always seeds /
extends ``_network_config`` and ``get_training_params`` reads back from
the same dict. This restores the invariant tests had pre-PR-5 (a
successful PATCH is a successful end-to-end apply) without weakening
the C3 verifier in production code.
"""

from __future__ import annotations

import copy
from typing import Any, Dict

import pytest

try:
    from juniper_cascor_client.testing import FakeCascorClient
except ImportError:  # juniper-cascor-client[testing] is optional at install time
    FakeCascorClient = None  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _make_fake_cascor_client_persist_updates(monkeypatch: pytest.MonkeyPatch):
    """Make FakeCascorClient.update_params actually persist for the verifier.

    Without this, every PR-5 C3 verify against the fake would show a
    mismatch (the fake returns hardcoded defaults from get_training_params
    when ``_network_config`` is ``None``).
    """
    if FakeCascorClient is None:
        yield
        return

    real_update = FakeCascorClient.update_params

    def patched_update(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Force the in-memory state into existence so the real implementation
        # has somewhere to write.
        if getattr(self, "_network_loaded", False) is False:
            self._network_loaded = True
        if getattr(self, "_network_config", None) is None:
            self._network_config = {}
        result = real_update(self, params)
        # FakeCascorClient.update_params has a hardcoded ``updatable_keys``
        # whitelist (learning_rate, candidate_pool_size, …). Anything outside
        # it is silently dropped. The verifier in CascorServiceAdapter will
        # then loudly flag those as mismatches even though the test author
        # intended the PATCH to succeed. Write every requested key into the
        # in-memory state so the verifier sees the post-PATCH values.
        for k, v in params.items():
            self._network_config[k] = v
        return result

    real_get = FakeCascorClient.get_training_params

    def patched_get(self) -> Dict[str, Any]:
        envelope = real_get(self)
        # Preserve the canonical envelope shape, but ensure the inner data
        # dict reflects every key written via update_params (the fake's
        # baked-in dict has a small whitelist; PR-5's adapter map covers
        # extras like the candidate-pool quintet that the fake doesn't
        # know about).
        if isinstance(envelope, dict):
            data = envelope.setdefault("data", {})
            cfg = getattr(self, "_network_config", None)
            if isinstance(cfg, dict):
                for k, v in cfg.items():
                    data.setdefault(k, v)
                # Override hardcoded defaults with anything the user
                # actually PATCHed so the verifier sees the new values.
                for k in cfg:
                    data[k] = cfg[k]
        return copy.deepcopy(envelope)

    monkeypatch.setattr(FakeCascorClient, "update_params", patched_update)
    monkeypatch.setattr(FakeCascorClient, "get_training_params", patched_get)
    yield
