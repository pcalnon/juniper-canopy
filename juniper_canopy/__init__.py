"""Juniper Canopy - Real-time monitoring dashboard for Cascade Correlation Neural Network."""

import importlib.metadata

__author__ = "Paul Calnon"
__description__ = "Real-time monitoring frontend for Cascade Correlation neural networks"

# D-11 (canopy E2E arc): resolve the version from the installed package metadata -- the same
# source as ``/v1/health`` and the About panel (``canopy_constants.resolve_app_version``) -- so
# this literal can never drift from ``pyproject.toml`` the way the old hardcoded ``"0.5.0"`` did.
# The fallback tracks ``pyproject.toml`` for a source checkout that was never ``pip install``ed.
try:
    __version__ = importlib.metadata.version("juniper-canopy")
except importlib.metadata.PackageNotFoundError:  # pragma: no cover - source checkout only
    __version__ = "0.6.0"
