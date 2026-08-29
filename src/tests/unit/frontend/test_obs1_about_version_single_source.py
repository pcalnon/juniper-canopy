"""OBS-1 (canopy E2E arc, segment 2 observation): the About panel rendered
``App Version: 2.2.0`` while ``/v1/health`` served the installed package version.

Root cause: ``about_panel.py`` carried its own hardcoded ``APP_VERSION = "2.2.0"``
literal ("should match pyproject.toml" -- it never did), while ``main.py``
resolves the version from ``importlib.metadata`` for ``/v1/health`` and the
build-info metric. The About panel now reads ``canopy_constants.APP_VERSION``,
resolved the same way, so the two surfaces cannot drift again.
"""

import importlib.metadata
import tomllib
from pathlib import Path

import pytest

import canopy_constants
from frontend.components import about_panel
from frontend.components.about_panel import AboutPanel

PYPROJECT_VERSION = tomllib.loads((Path(__file__).resolve().parents[4] / "pyproject.toml").read_text())["project"]["version"]


@pytest.mark.unit
class TestAboutVersionSingleSource:
    def test_about_panel_exports_the_shared_constant(self):
        assert about_panel.APP_VERSION is canopy_constants.APP_VERSION
        assert about_panel.APP_VERSION != "2.2.0"

    def test_resolves_from_installed_metadata_or_falls_back_to_pyproject(self):
        try:
            installed = importlib.metadata.version("juniper-canopy")
        except importlib.metadata.PackageNotFoundError:
            installed = None
        expected = installed if installed is not None else PYPROJECT_VERSION
        assert canopy_constants.APP_VERSION == expected

    def test_fallback_literal_tracks_pyproject(self):
        # The only literal left is the source-checkout fallback; pin it to pyproject
        # so it cannot rot the way the About panel's own literal did.
        assert canopy_constants.resolve_app_version.__defaults__ == (PYPROJECT_VERSION,)

    def test_rendered_about_version_matches_the_health_route_source(self):
        panel = AboutPanel({}, component_id="about-obs1")
        assert panel.version == canopy_constants.APP_VERSION
        # The header renders "Version X" statically; the "App Version: X" line is
        # built by the System Info callback when its collapse opens. Dash's
        # component repr elides deep children, so walk the trees for strings.
        header_strings = _rendered_strings(panel.get_layout())
        assert f"Version {canopy_constants.APP_VERSION}" in header_strings
        assert "Version 2.2.0" not in header_strings
        panel.register_callbacks(_DummyApp())
        info_strings = _rendered_strings(panel._cb_update_system_info(True))
        assert f"App Version: {canopy_constants.APP_VERSION}" in info_strings
        assert "App Version: 2.2.0" not in info_strings


class _DummyApp:
    def callback(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


def _rendered_strings(node) -> list:
    """Every string child in a Dash component tree, in render order."""
    found: list = []
    if isinstance(node, str):
        found.append(node)
    elif isinstance(node, (list, tuple)):
        for child in node:
            found.extend(_rendered_strings(child))
    elif hasattr(node, "children"):
        found.extend(_rendered_strings(node.children))
    return found
