#!/usr/bin/env python
# ---------------------------------------------------------------------------
# Project     : Juniper
# Sub-Project : JuniperCanopy
# Application : juniper_canopy
# Author      : Paul Calnon
# Version     : 0.1.0
# License     : MIT License
# ---------------------------------------------------------------------------
"""Prove a built wheel carries every module it imports, before it is published.

Releases 0.5.0 through 0.8.0 each published a wheel whose dashboard could not be
imported (canopy#631): ``frontend/dashboard_manager.py`` opens with
``from canopy_constants import ...`` and no wheel shipped ``canopy_constants.py``.
The top-level ``src/*.py`` files are **py-modules**, and
``[tool.setuptools.packages.find]`` collects **packages** only, so every one of them was
dropped while the packages that import them shipped fine.

Nothing in the pipeline could see it:

* ``twine check`` validates the metadata and the README, never the code;
* ``pip check`` validates the dependency graph, never importability -- it passes on a
  wheel that cannot import itself;
* the TestPyPI step's ``from juniper_canopy import __version__`` passes on **all four**
  broken wheels, because that one module was always shipped. A smoke test has to import
  something the defect can actually reach.

And the container never noticed, because ``Dockerfile`` copies ``src/`` in and sets
``PYTHONPATH=/app/src``, so the running service resolves these from source and shadows
site-packages entirely. The deployed image was healthy the whole time; only the artifact
on PyPI was broken.

**Run this from a directory that is not the repository root.** ``juniper_canopy/`` sits at
the repo root, so a run from there imports it out of the checkout and the wheel is never
exercised. The workflow does the ``cd``; this module also refuses if it detects it.

Usage:
    python -m venv "$TMP/smoke"
    "$TMP/smoke/bin/pip" install dist/*.whl
    mkdir -p "$TMP/cwd" && cd "$TMP/cwd"
    "$TMP/smoke/bin/python" /abs/path/to/util/wheel_import_smoke.py

Exit 0 = every module imported. Exit 1 = a module the wheel should carry is missing.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

# Every shipped package and top-level module that a BARE install can import.
#
# Deliberately excluded, and they must stay excluded: ``backend.service_backend`` needs
# ``juniper_cascor_client`` (the ``juniper-cascor`` extra) and ``demo_mode`` needs
# ``torch`` (the ``demo`` extra). A bare install is correctly without those, so importing
# them here would fail for a reason that is not a packaging defect -- and a guard that
# cries wolf is a guard someone deletes.
MODULES: tuple[str, ...] = (
    # packages
    "juniper_canopy",
    "backend",
    "communication",
    "frontend",
    "logger",
    # the module every broken release died on, and the consumers that prove it resolves
    "canopy_constants",
    "settings",
    "frontend.dashboard_manager",
    "frontend.components.candidate_metrics_panel",
    "communication.websocket_manager",
    "logger.logger",
    # the remaining top-level modules the wheel must carry
    "audit_log",
    "config_manager",
    "csrf",
    "dataset_import",
    "dataset_schema",
    "discovery",
    "health",
    "main",
    "middleware",
    "model_registry",
    "observability",
    "provenance",
    "secrets_util",
    "security",
    "validation_gate",
    "ws_security",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-repo-cwd",
        action="store_true",
        help="skip the cwd guard (for testing this script itself; never in CI)",
    )
    args = parser.parse_args()

    cwd = Path.cwd()
    if not args.allow_repo_cwd and (cwd / "juniper_canopy" / "__init__.py").is_file() and (cwd / "src").is_dir():
        # One f-string with embedded newlines rather than implicit concatenation: black
        # joins adjacent string literals onto a single 512-column line, and the repo's
        # pinned hook version need not match whatever black is installed locally.
        print(
            f"refusing to run from what looks like the repository root ({cwd}).\njuniper_canopy/ would be imported from the checkout instead of the wheel,\nand the defect this guards against would be invisible. cd to an empty\ndirectory first.",
            file=sys.stderr,
        )
        return 2

    failures: list[str] = []
    for name in MODULES:
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError as exc:
            failures.append(f"{name}: {exc}")
            continue
        origin = getattr(module, "__file__", None) or "<namespace>"
        if origin != "<namespace>" and "site-packages" not in origin:
            failures.append(f"{name}: resolved from {origin}, not from the installed wheel")

    if failures:
        print("IMPORT SMOKE TEST FAILED -- the wheel does not carry what it imports:", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        print(
            "\nIf a module was added under src/ as a top-level file, add it to [tool.setuptools]\npy-modules in pyproject.toml and to MODULES here.",
            file=sys.stderr,
        )
        return 1

    print(f"import smoke test OK: {len(MODULES)} modules imported from the installed wheel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
