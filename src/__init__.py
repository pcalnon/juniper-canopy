"""
Juniper Canopy Package

A real-time monitoring frontend for Cascade Correlation neural networks.
"""

import importlib.metadata

__author__ = "Paul Calnon"
__description__ = "Real-time monitoring frontend for Cascade Correlation neural networks"

# D-11 (canopy E2E arc): single-source the version from installed package metadata (the same
# source as ``/v1/health`` and the About panel) so it cannot drift from ``pyproject.toml``.
# This shim's ``__version__`` had rotted to ``"0.5.0"`` while ``pyproject.toml`` was ``0.6.0``.
try:
    __version__ = importlib.metadata.version("juniper-canopy")
except importlib.metadata.PackageNotFoundError:  # pragma: no cover - source checkout only
    __version__ = "0.6.0"
