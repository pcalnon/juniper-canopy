#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-10-05_recurrence_wire_contract_probe.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-05
# Last Modified: 2026-10-05
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Drive canopy's REAL recurrence adapter against the REAL
#                juniper-recurrence app, in process: 401, 429 +
#                Retry-After, the restored state, and the version surfaces.
#####################################################################
"""Canopy's recurrence adapter against the real juniper-recurrence app, in one process (W1.6 / W1.7 evidence).

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-10-05
Status: ad-hoc -- investigation
Retire when: the W1.6 / W1.7 PR is merged and its CHANGELOG entry is released
Related: juniper-ml notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md
    (v1.3.0), items W1.6 / W1.7, findings F-C5 .. F-C8.

The unit tests feed the adapter hand-written replies. This probe feeds it the service's own: it builds the recurrence
FastAPI app with ``build_app`` and hands the adapter Starlette's synchronous test transport, so every request goes
through the real ``SecurityMiddleware`` (API-key auth, rate limiter) and the real routes. Nothing listens on a port.

It answers four questions, each against what the service actually sends:

1. What does a wrong key produce, and does the remedy name the variables an operator sets?  (F-C5)
2. What does a rate-limited request produce, and does the ``Retry-After`` value reach the message?  (F-C7)
3. Does a model restored from a snapshot read as present?  (F-C6) -- the route is driven through ``set_restored``;
   a sentinel stands in for the model, because the route reads only the state's markers.
4. Where does the service report its version?  (F-C8) -- ``/v1/health``, ``GET /`` and ``/openapi.json`` raw, then the
   adapter's ``service_version`` when the tree has it.

It needs an interpreter with juniper-recurrence installed; canopy's own env does not have it. The adapter module is
loaded from ``TREE`` by path (it imports only the standard library and httpx), so canopy's package need not import::

    /opt/miniforge3/envs/JuniperCascor1/bin/python -s util/ad-hoc/2026-10-05_recurrence_wire_contract_probe.py [TREE]

``TREE`` is a canopy checkout (default: this one). Run it against the pre-change tree and this one for before / after.
Exit status is 0 (an instrument, not a gate).
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

_DEFAULT_TREE = Path(__file__).resolve().parents[2]
_KEY = "probe-key"


def _load_adapter(tree: Path):
    """Load ``src/backend/recurrence_service_adapter.py`` from ``tree`` by path, registered before it executes."""
    path = tree / "src" / "backend" / "recurrence_service_adapter.py"
    spec = importlib.util.spec_from_file_location("probe_recurrence_service_adapter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # @dataclass resolves its module through sys.modules
    spec.loader.exec_module(module)
    return module


def _app(rate_limit: int):
    from juniper_recurrence.app import build_app
    from juniper_recurrence.settings import Settings

    return build_app(Settings(api_keys=[_KEY], rate_limit_enabled=True, rate_limit_requests_per_minute=rate_limit, metrics_enabled=False))


def _describe(exc: BaseException) -> str:
    retry_after = getattr(exc, "retry_after", "<no attribute>")
    return f"{type(exc).__name__} status={getattr(exc, 'status_code', None)} retry_after={retry_after!r}\n      message: {exc}"


def main(argv: list[str]) -> int:
    tree = Path(argv[1]).resolve() if len(argv) > 1 else _DEFAULT_TREE
    os.environ.setdefault("JUNIPER_SKIP_AUTH_POSTURE_CHECK", "1")
    from fastapi.testclient import TestClient

    import juniper_recurrence

    adapter_module = _load_adapter(tree)
    adapter_cls = adapter_module.RecurrenceServiceAdapter
    print(f"canopy tree: {tree}")
    print(f"juniper-recurrence: {juniper_recurrence.__version__} ({Path(juniper_recurrence.__file__).parent})")

    app = _app(rate_limit=1000)
    client = TestClient(app)
    print("\n[F-C8] version surfaces, raw")
    health = client.get("/v1/health")
    print(f"  GET /v1/health            -> {health.status_code} {health.json()}")
    root = client.get("/")
    print(f"  GET /                     -> {root.status_code} {root.text[:80]}")
    keyless = client.get("/openapi.json")
    print(f"  GET /openapi.json (no key) -> {keyless.status_code} {keyless.text[:80]}")
    keyed = client.get("/openapi.json", headers={"X-API-Key": _KEY})
    print(f"  GET /openapi.json (key)   -> {keyed.status_code} info={keyed.json().get('info')} ({len(keyed.content)} bytes)")

    adapter = adapter_cls("http://testserver", _KEY, transport=client._transport)
    if hasattr(adapter, "service_version"):
        print(f"  adapter.service_version() -> {adapter.service_version()!r}")
    else:
        print("  adapter.service_version   -> (not in this tree)")

    print("\n[F-C5] a wrong key")
    wrong = adapter_cls("http://testserver", "not-the-key", transport=client._transport)
    try:
        wrong.training_status()
    except Exception as exc:  # noqa: BLE001 -- an instrument reports whatever is raised
        print(f"  {_describe(exc)}")

    print("\n[F-C6] status: idle, then a model restored from a snapshot")
    status = adapter.training_status()
    print(f"  idle     -> state={status.state!r} restored_from={getattr(status, 'restored_from', '<no field>')!r} model_present={getattr(status, 'model_present', '<no property>')!r}")
    app.state.app_state.set_restored(object(), "snap-probe-0001")
    status = adapter.training_status()
    print(f"  restored -> state={status.state!r} restored_from={getattr(status, 'restored_from', '<no field>')!r} model_present={getattr(status, 'model_present', '<no property>')!r}")

    print("\n[F-C7] rate limit: 2 requests per minute, the third is refused")
    limited_client = TestClient(_app(rate_limit=2))
    limited = adapter_cls("http://testserver", _KEY, transport=limited_client._transport)
    for attempt in range(1, 4):
        try:
            limited.training_status()
            print(f"  request {attempt}: ok")
        except Exception as exc:  # noqa: BLE001 -- an instrument reports whatever is raised
            print(f"  request {attempt}: {_describe(exc)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
