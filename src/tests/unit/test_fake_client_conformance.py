"""Tests that FakeCascorClient implements all public methods of JuniperCascorClient.

Prevents method drift: if JuniperCascorClient gains a new public method,
this test will fail until FakeCascorClient is updated to match.
"""

import inspect

import pytest

_jcc = pytest.importorskip("juniper_cascor_client", reason="juniper-cascor-client not installed")
if getattr(_jcc, "_is_stub", False):
    pytest.skip("juniper-cascor-client is a test stub, not the real package", allow_module_level=True)

from juniper_cascor_client.client import JuniperCascorClient
from juniper_cascor_client.testing import FakeCascorClient


def _public_methods(cls):
    """Return the set of public method names for a class."""
    return {name for name, obj in inspect.getmembers(cls, predicate=inspect.isfunction) if not name.startswith("_")}


@pytest.mark.unit
class TestFakeCascorClientConformance:
    """Verify FakeCascorClient stays in sync with JuniperCascorClient."""

    def test_fake_implements_all_real_methods(self):
        """Every public method on JuniperCascorClient must exist on FakeCascorClient."""
        real_methods = _public_methods(JuniperCascorClient)
        fake_methods = _public_methods(FakeCascorClient)
        missing = real_methods - fake_methods
        assert not missing, f"FakeCascorClient is missing methods: {sorted(missing)}"

    def test_method_signatures_match(self):
        """Public method signatures must be compatible (same parameter names/defaults)."""
        real_methods = _public_methods(JuniperCascorClient)
        fake_methods = _public_methods(FakeCascorClient)
        shared = real_methods & fake_methods

        mismatches = []
        for name in sorted(shared):
            real_sig = inspect.signature(getattr(JuniperCascorClient, name))
            fake_sig = inspect.signature(getattr(FakeCascorClient, name))
            if real_sig != fake_sig:
                mismatches.append(f"  {name}: real{real_sig} != fake{fake_sig}")

        assert not mismatches, "Signature mismatches:\n" + "\n".join(mismatches)
