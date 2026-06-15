"""Regression: ``.dockerignore`` must exclude *nested* egg-info / dist-info dirs.

The juniper-canopy image once reported a stale version on ``/v1/health``
(0.4.0 while ``pyproject.toml`` was 0.5.0) because a stale
``src/juniper_canopy.egg-info`` build artifact was COPYed into the image and,
sitting on ``PYTHONPATH`` (``/app/src``) ahead of site-packages, shadowed the
installed package's metadata version. The existing ``*.egg-info/`` pattern only
matched the *context root*, silently missing the nested dir.

This test pins the ``**/``-prefixed nested-exclusion forms so the version-drift
cannot silently return (e.g. if someone "tidies" the file back to the root-only
form). Surfaced by the build-provenance ``make doctor`` work — see juniper-ml
``notes/BUILD_PROVENANCE_DESIGN_2026-06-14.md``.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCKERIGNORE = REPO_ROOT / ".dockerignore"


def _patterns() -> list[str]:
    """Return the non-comment, non-blank pattern lines from ``.dockerignore``."""
    text = DOCKERIGNORE.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def test_dockerignore_exists() -> None:
    assert DOCKERIGNORE.is_file(), f".dockerignore must exist at the repo root ({REPO_ROOT})."


def test_dockerignore_excludes_nested_egg_info() -> None:
    """A bare ``*.egg-info/`` only matches the context root; the ``**/``-prefixed
    form is required to exclude ``src/juniper_canopy.egg-info`` (the version-shadow bug)."""
    assert "**/*.egg-info/" in _patterns(), "`.dockerignore` must contain `**/*.egg-info/` to exclude a nested src/*.egg-info build artifact; a root-only `*.egg-info/` is insufficient and lets it shadow the installed package version on PYTHONPATH."


def test_dockerignore_excludes_nested_dist_info() -> None:
    assert "**/*.dist-info/" in _patterns(), "`.dockerignore` must exclude nested `**/*.dist-info/` for the same reason."
