#!/usr/bin/env python
"""
Capture juniper-data's parameter schemas for the generators canopy's recurrence backend can reach.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-10-08
Status: ad-hoc — wip (re-run whenever juniper-data changes a sequence generator's parameters)
Retire when: juniper-data publishes its generator parameter schemas as a versioned artifact canopy can depend on
Related: juniper-ml plan notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md,
         W1.2 (F-C2, F-C3, ruling R7)

Why a capture, not an import
----------------------------
canopy does not depend on juniper-data, and the copy installed in ``JuniperCanopy1`` is 0.6.0,
which predates ``equities_seq`` -- the same reason ``model_registry.KNOWN_UPSTREAM_GENERATORS`` is a
dated snapshot. So this script runs under juniper-data's OWN interpreter, against a juniper-data
source tree, and writes what canopy needs as data:

1. ``src/tests/fixtures/juniper_data_sequence_generator_schemas.json`` -- for each generator, exactly
   the ``schema`` field ``GET /v1/generators`` serves (``params_class.model_json_schema()``), with its
   ``name`` and ``version``, plus the commit it was captured from. The tests render canopy's
   dataset form from it and pin ``dataset_schema.DECLARED_PARAM_DEFAULTS`` against it.
2. On stdout, the ``DECLARED_PARAM_DEFAULTS`` literal for ``src/dataset_schema.py``.

Usage (from the canopy repo root)::

    /opt/miniforge3/envs/JuniperData/bin/python -I util/ad-hoc/2026-10-08_capture_sequence_generator_schemas.py \\
        --juniper-data-src ../juniper-data

``-I`` keeps the interpreter from importing anything from this directory or the user site; the
juniper-data tree is put on ``sys.path`` explicitly. The capture refuses a dirty juniper-data tree
unless ``--allow-dirty`` is given, because a snapshot of uncommitted code names a commit that does
not contain it.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import pprint
import subprocess  # nosec B404 -- fixed argv, no shell; reads the commit of a local checkout
import sys

# The generators canopy's recurrence (one-shot, rank-3) backend can be staged with: every
# ``DatasetTypeSpec`` with ``ndim == 3`` in ``src/model_registry.py``. None is aliased, so the canopy
# value IS the juniper-data name. ``TestEveryRecurrenceSeedIsDeclared`` fails if a rank-3 seed is
# added without re-running this capture.
SEQUENCE_GENERATORS: tuple[str, ...] = ("multi_sine", "mackey_glass", "irregular_sine", "ar_p", "delay_product", "equities_seq")

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "src" / "tests" / "fixtures" / "juniper_data_sequence_generator_schemas.json"


def _git(src: pathlib.Path, *args: str) -> str:
    """Run a read-only git command in ``src`` and return its stripped stdout."""
    return subprocess.run(["git", "-C", str(src), *args], check=True, capture_output=True, text=True).stdout.strip()  # nosec B603 B607


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--juniper-data-src", type=pathlib.Path, required=True, help="path to a juniper-data checkout")
    parser.add_argument("--allow-dirty", action="store_true", help="capture from a tree with uncommitted changes")
    parser.add_argument("--fixture", type=pathlib.Path, default=FIXTURE, help="where to write the JSON snapshot")
    args = parser.parse_args(argv)

    src = args.juniper_data_src.resolve()
    commit = _git(src, "rev-parse", "HEAD")
    dirty = bool(_git(src, "status", "--porcelain", "--", "juniper_data"))
    if dirty and not args.allow_dirty:
        print(f"refusing: {src} has uncommitted changes under juniper_data/ (pass --allow-dirty to capture anyway)", file=sys.stderr)
        return 2

    sys.path.insert(0, str(src))
    from juniper_data.api.routes.generators import GENERATOR_REGISTRY  # noqa: E402 -- needs the path above

    entries = []
    declared: dict[str, dict[str, object]] = {}
    for name in SEQUENCE_GENERATORS:
        info = GENERATOR_REGISTRY[name]
        schema = info["params_class"].model_json_schema()
        entries.append({"name": name, "version": info["version"], "schema": schema})
        declared[name] = {field: prop.get("default") for field, prop in schema["properties"].items()}

    snapshot = {
        "_provenance": {
            "source": "juniper-data",
            "commit": commit,
            "dirty": dirty,
            "captured": _dt.date.today().isoformat(),
            "what": "GENERATOR_REGISTRY[name]['params_class'].model_json_schema() -- the `schema` field of each GET /v1/generators entry",
            "tool": "util/ad-hoc/2026-10-08_capture_sequence_generator_schemas.py",
        },
        "generators": entries,
    }
    args.fixture.parent.mkdir(parents=True, exist_ok=True)
    args.fixture.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"# wrote {args.fixture} from juniper-data {commit[:8]}{' (DIRTY)' if dirty else ''}", file=sys.stderr)
    print("DECLARED_PARAM_DEFAULTS: dict[str, dict[str, Any]] = " + pprint.pformat(declared, width=500, sort_dicts=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
