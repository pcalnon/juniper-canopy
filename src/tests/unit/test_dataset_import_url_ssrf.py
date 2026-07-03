#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_dataset_import_url_ssrf.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-07-03
# Last Modified: 2026-07-03
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   SEC-F08 regression tests: SSRF hardening of the
#                POST /api/dataset/import-url fetch sink.
#####################################################################
"""SEC-F08 hardening tests for ``POST /api/dataset/import-url``.

The URL-import endpoint is a *latent* SSRF sink: it is currently dead in demo
mode (``DemoBackend`` has no ``import_dataset`` so the handler 501s before any
fetch), but the fetch path re-arms the moment that feature is fixed. Per the
security audit (juniper-ml ``notes/JUNIPER_STACK_SECURITY_AUDIT_PLAN_2026-07-02.md``
§4.3 / §5.2, HO-1/HO-7) the sink is hardened *before* the feature is enabled.
These tests do **not** enable the dead import feature — they inject a capable
stub backend so the hardened fetch path can be exercised in isolation.

Coverage:
  * ``_import_url_ip_is_blocked`` — the resolved-IP classifier (loopback /
    private / link-local / metadata / unspecified / multicast / reserved →
    blocked; public → allowed; unparseable → fail-closed);
  * ``_classify_import_url_target`` — resolve-then-classify, incl. DNS-rebind
    (host resolving to an internal IP), unresolvable host, host-less URL, and a
    mixed public+internal resolution;
  * the endpoint — the real off-switch defaults OFF (403); the http/https scheme
    allowlist still rejects ``file://``; an internal-resolving URL is rejected
    *before* any outbound fetch; redirects are not followed; the size cap is
    enforced *during* the streamed download (aborts early); and a public URL
    streams through to the (stubbed) backend import.

All network + DNS is mocked, so the suite is hermetic and never touches :8050.
"""

import pytest

import main

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- helpers


class _StubImportBackend:
    """A demo backend that *does* expose ``import_dataset`` so the handler gets
    past the (production) 501 dead-feature guard and into the hardened fetch
    path. The real ``DemoBackend`` deliberately keeps lacking this method — this
    stub exists only to exercise the sink; it does not re-enable the feature."""

    backend_type = "demo"

    def __init__(self):
        self.calls = []

    def import_dataset(self, inputs, targets, source_label=None):
        self.calls.append((inputs, targets, source_label))
        n = int(getattr(inputs, "shape", (0,))[0])
        return {"status": "imported", "n_samples": n, "source": source_label}


def _enable_and_stub(monkeypatch):
    """Flip the real off-switch ON and swap in the capable stub backend.

    Returns the stub so a test can assert whether ``import_dataset`` ran.
    """
    monkeypatch.setattr(main.settings, "dataset_import_url_enabled", True, raising=True)
    stub = _StubImportBackend()
    monkeypatch.setattr(main, "backend", stub, raising=True)
    return stub


def _patch_dns(monkeypatch, ip):
    """Patch ``socket.getaddrinfo`` (as ``main`` sees it) to resolve every host
    to ``ip``. Returns the list of hostnames the code asked to resolve."""
    import socket as _socket

    asked = []

    def _fake_getaddrinfo(host, port, *args, **kwargs):
        asked.append(host)
        family = _socket.AF_INET6 if ":" in ip else _socket.AF_INET
        return [(family, _socket.SOCK_STREAM, 6, "", (ip, 0))]

    monkeypatch.setattr(main.socket, "getaddrinfo", _fake_getaddrinfo, raising=True)
    return asked


def _install_httpx_tripwire(monkeypatch):
    """Replace ``httpx.AsyncClient`` with a class that explodes on construction,
    proving the handler never attempted an outbound fetch."""
    import httpx

    class _Tripwire:
        def __init__(self, *args, **kwargs):
            raise AssertionError("SSRF guard failed: an outbound fetch was attempted")

    monkeypatch.setattr(httpx, "AsyncClient", _Tripwire, raising=True)


def _install_fake_httpx(monkeypatch, *, status_code, chunks):
    """Replace ``httpx.AsyncClient`` with a streaming fake. Returns a recorder
    dict capturing the client kwargs (``follow_redirects``), the ``stream``
    calls, and how many chunks were actually yielded (for the streaming-cap
    early-abort assertion)."""
    import httpx

    rec = {"client_kwargs": None, "stream_calls": [], "yielded": 0}

    class _FakeStream:
        def __init__(self):
            self.status_code = status_code

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def aiter_bytes(self):
            for chunk in chunks:
                rec["yielded"] += 1
                yield chunk

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            rec["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def stream(self, method, url):
            rec["stream_calls"].append((method, url))
            return _FakeStream()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient, raising=True)
    return rec


# --------------------------------------------------------------------------- classifier (pure unit)


class TestImportUrlIpIsBlocked:
    """Direct tests of the resolved-IP predicate (no DNS)."""

    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",  # IPv4 loopback
            "127.5.5.5",  # anywhere in 127/8
            "10.0.0.5",  # RFC-1918
            "172.16.31.9",  # RFC-1918
            "192.168.1.10",  # RFC-1918
            "169.254.169.254",  # link-local — cloud metadata endpoint
            "169.254.0.1",  # link-local
            "0.0.0.0",  # unspecified
            "224.0.0.1",  # multicast
            "240.0.0.1",  # reserved
            "::1",  # IPv6 loopback
            "fe80::1",  # IPv6 link-local
            "fc00::1",  # IPv6 unique-local
            "::",  # IPv6 unspecified
            "not-an-ip",  # unparseable → fail closed
        ],
    )
    def test_blocked(self, ip):
        assert main._import_url_ip_is_blocked(ip) is True

    @pytest.mark.parametrize(
        "ip",
        [
            "8.8.8.8",
            "93.184.216.34",  # example.com
            "1.1.1.1",
            "2606:2800:220:1:248:1893:25c8:1946",  # public IPv6
        ],
    )
    def test_allowed(self, ip):
        assert main._import_url_ip_is_blocked(ip) is False


class TestClassifyImportUrlTarget:
    """resolve-then-classify, with DNS mocked."""

    def test_public_host_allowed(self, monkeypatch):
        _patch_dns(monkeypatch, "93.184.216.34")
        assert main._classify_import_url_target("https://example.com/data.csv") is None

    @pytest.mark.parametrize(
        "ip",
        ["127.0.0.1", "10.1.2.3", "192.168.0.1", "169.254.169.254", "::1", "fc00::5"],
    )
    def test_internal_resolution_rejected(self, monkeypatch, ip):
        # DNS-rebind shape: a perfectly public-looking hostname that resolves to
        # an internal address. The classifier validates the RESOLVED IP, so it
        # is rejected regardless of how innocent the hostname looks.
        _patch_dns(monkeypatch, ip)
        reason = main._classify_import_url_target("http://totally-legit.example.com/x.csv")
        assert reason is not None
        assert "non-public" in reason

    def test_mixed_resolution_rejected(self, monkeypatch):
        # A host that resolves to BOTH a public and an internal address must be
        # rejected (any internal record is disqualifying).
        import socket as _socket

        def _fake(host, port, *args, **kwargs):
            return [
                (_socket.AF_INET, _socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
                (_socket.AF_INET, _socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
            ]

        monkeypatch.setattr(main.socket, "getaddrinfo", _fake, raising=True)
        reason = main._classify_import_url_target("https://example.com/x.csv")
        assert reason is not None and "non-public" in reason

    def test_unresolvable_host_rejected(self, monkeypatch):
        import socket as _socket

        def _boom(host, port, *args, **kwargs):
            raise _socket.gaierror("name resolution failed")

        monkeypatch.setattr(main.socket, "getaddrinfo", _boom, raising=True)
        reason = main._classify_import_url_target("https://no-such-host.invalid/x.csv")
        assert reason is not None
        assert "resolve" in reason.lower()

    def test_hostless_url_rejected(self):
        # No DNS patch needed: there is no host to resolve.
        reason = main._classify_import_url_target("http:///just-a-path.csv")
        assert reason is not None


# --------------------------------------------------------------------------- endpoint behaviour


class TestImportUrlEndpointGates:
    """End-to-end via the FastAPI TestClient (``client`` fixture from conftest)."""

    def test_disabled_by_default_returns_403(self, client):
        # The real off-switch (SEC-F08) defaults OFF: with no override the
        # endpoint must refuse before doing anything. No backend/DNS/httpx patch
        # — this is the out-of-the-box posture.
        resp = client.post("/api/dataset/import-url", json={"url": "https://example.com/x.csv"})
        assert resp.status_code == 403
        assert "disabled" in resp.json()["error"].lower()

    def test_scheme_allowlist_rejects_file_url(self, client, monkeypatch):
        # Enabled + capable backend so we get past the 403/501 gates; the
        # http/https allowlist must still reject a file:// URL (400) before any
        # resolution/fetch is attempted.
        _enable_and_stub(monkeypatch)
        _install_httpx_tripwire(monkeypatch)  # any fetch attempt fails the test
        resp = client.post("/api/dataset/import-url", json={"url": "file:///etc/passwd"})
        assert resp.status_code == 400
        assert "scheme" in resp.json()["error"].lower()

    @pytest.mark.parametrize(
        "ip",
        ["127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.1", "::1"],
    )
    def test_internal_target_rejected_before_fetch(self, client, monkeypatch, ip):
        stub = _enable_and_stub(monkeypatch)
        asked = _patch_dns(monkeypatch, ip)
        _install_httpx_tripwire(monkeypatch)  # explodes if the handler tries to fetch

        resp = client.post("/api/dataset/import-url", json={"url": "https://attacker.example/x.csv"})

        assert resp.status_code == 400
        assert "non-public" in resp.json()["error"]
        # Proof the guard ran and the fetch did not: DNS was queried, backend
        # import was never reached (tripwire would also have fired).
        assert asked == ["attacker.example"]
        assert stub.calls == []

    def test_redirect_to_internal_not_followed(self, client, monkeypatch):
        # Original URL resolves public (passes the egress guard); the server then
        # returns a 302 (e.g. Location: http://169.254.169.254/). With redirects
        # disabled the handler surfaces the 302 as a 400 and never fetches the
        # redirect target.
        stub = _enable_and_stub(monkeypatch)
        asked = _patch_dns(monkeypatch, "93.184.216.34")
        rec = _install_fake_httpx(monkeypatch, status_code=302, chunks=[])

        resp = client.post("/api/dataset/import-url", json={"url": "https://public.example/redirector.csv"})

        assert resp.status_code == 400
        assert "302" in resp.json()["error"]
        # follow_redirects MUST be disabled...
        assert rec["client_kwargs"].get("follow_redirects") is False
        # ...and only the original host was ever resolved (no internal hop).
        assert asked == ["public.example"]
        assert stub.calls == []

    def test_size_cap_enforced_during_stream(self, client, monkeypatch):
        # Cap enforced WHILE streaming: with a tiny cap and an over-cap body, the
        # download aborts mid-stream (413) rather than buffering the whole body.
        import dataset_import

        _enable_and_stub(monkeypatch)
        _patch_dns(monkeypatch, "93.184.216.34")
        monkeypatch.setattr(dataset_import, "MAX_FILE_BYTES", 10, raising=True)
        # 8 + 8 exceeds the cap on the 2nd chunk; the 3rd sentinel must NOT be read.
        chunks = [b"a" * 8, b"b" * 8, b"SENTINEL_MUST_NOT_BE_READ"]
        rec = _install_fake_httpx(monkeypatch, status_code=200, chunks=chunks)

        resp = client.post("/api/dataset/import-url", json={"url": "https://public.example/big.csv"})

        assert resp.status_code == 413
        assert "too large" in resp.json()["error"].lower()
        # Streaming, not post-buffering: it stopped early (did not read all chunks).
        assert rec["yielded"] < len(chunks)

    def test_public_url_streams_through_to_import(self, client, monkeypatch):
        # Happy path: public resolution + a 200 with a valid CSV body streams
        # through to the (stubbed) backend import.
        stub = _enable_and_stub(monkeypatch)
        _patch_dns(monkeypatch, "93.184.216.34")
        _install_fake_httpx(monkeypatch, status_code=200, chunks=[b"0.1,0.2,0\n0.3,0.4,1\n"])

        resp = client.post("/api/dataset/import-url", json={"url": "https://public.example/data.csv"})

        assert resp.status_code == 200
        body = resp.json()
        assert body.get("status") == "imported"
        assert len(stub.calls) == 1
        # source_label threads the fetched URL through.
        assert stub.calls[0][2] == "url:https://public.example/data.csv"
