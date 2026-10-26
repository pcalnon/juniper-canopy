#!/usr/bin/env python
"""
Capture juniper-data's parameter schemas from a PUBLISHED juniper-data wheel, for the generators canopy's cascor path filters.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-10-26
Status: ad-hoc — wip (re-run whenever a juniper-data release changes a captured generator's parameters)
Retire when: juniper-data publishes its generator parameter schemas as a versioned artifact canopy can depend on
Related: juniper-canopy#736 (flat ``equities`` on the cascor staging path), juniper-canopy#737 (drift detection),
         util/ad-hoc/2026-10-08_capture_sequence_generator_schemas.py (the source-tree sibling that captured the six
         sequence generators)

Why a published wheel, not a source tree
----------------------------------------
The sequence capture reads a juniper-data checkout at a commit. What a deployment runs is a juniper-data RELEASE, so
this capture reads the release itself: the wheel PyPI serves, installed into a throwaway virtualenv. It writes the
same JSON shape as the sequence fixture -- a ``_provenance`` block and a ``generators`` list of ``{name, version,
schema}`` -- so one comparison over fixture entries covers both files.

The provenance it records is checked, not asserted:

* ``version`` is the installed distribution's, and must equal the version in the wheel's file name.
* ``wheel_sha256`` is the wheel's own digest, and must equal the archive hash pip recorded when it installed the
  distribution (``direct_url.json``), which proves the schemas were read from that file. Compare it with PyPI's
  (``https://pypi.org/pypi/juniper-data/<version>/json``) before trusting the wheel.
* ``commit`` is the commit of juniper-data's release tag ``v<version>``, resolved in a juniper-data checkout, and
  every file the wheel installed under ``juniper_data/`` must be byte-identical to that commit's copy. So ``commit``
  names source that contains exactly what was captured.

Usage (from the canopy repo root; everything lives under the gitignored ``tmp/``, never ``/tmp``)::

    python3 -m venv tmp/jd-wheel/venv
    tmp/jd-wheel/venv/bin/pip download --no-deps --only-binary=:all: juniper-data==0.17.1 -d tmp/jd-wheel/wheel
    tmp/jd-wheel/venv/bin/pip install "$PWD/tmp/jd-wheel/wheel/juniper_data-0.17.1-py3-none-any.whl[api]"
    tmp/jd-wheel/venv/bin/python -I util/ad-hoc/2026-10-26_capture_published_generator_schemas.py \\
        --wheel tmp/jd-wheel/wheel/juniper_data-0.17.1-py3-none-any.whl --juniper-data-src ../juniper-data

``-I`` keeps the interpreter from importing anything from this directory or the user site. On stdout it prints the
``DECLARED_PARAM_DEFAULTS`` entries for ``src/dataset_schema.py``.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import importlib.metadata as metadata
import json
import pathlib
import pprint
import re
import subprocess  # nosec B404 -- fixed argv, no shell; reads a local juniper-data checkout
import sys

# The generators canopy's CASCOR path filters by declaration: rank-2 seeds with a ``DECLARED_PARAM_DEFAULTS`` entry.
# Only flat ``equities`` today (juniper-canopy#736). Its canopy value IS its juniper-data name.
DEFAULT_GENERATORS: tuple[str, ...] = ("equities",)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "src" / "tests" / "fixtures" / "juniper_data_tabular_generator_schemas.json"
TOOL = "util/ad-hoc/2026-10-26_capture_published_generator_schemas.py"
WHEEL_NAME = re.compile(r"^juniper_data-(?P<version>[^-]+)-[^-]+-[^-]+-[^-]+\.whl$")


def _git(src: pathlib.Path, *args: str, text: bool = True):
    """Run a read-only git command in ``src`` and return its stdout (stripped text, or raw bytes)."""
    out = subprocess.run(["git", "-C", str(src), *args], check=True, capture_output=True, text=text).stdout  # nosec B603 B607
    return out.strip() if text else out


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _refuse(message: str) -> int:
    print(f"refusing: {message}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--wheel", type=pathlib.Path, required=True, help="the juniper-data wheel the running interpreter's juniper-data was installed from")
    parser.add_argument("--juniper-data-src", type=pathlib.Path, required=True, help="a juniper-data checkout that has the release tag v<version>")
    parser.add_argument("--generators", nargs="+", default=list(DEFAULT_GENERATORS), help="juniper-data generator names to capture")
    parser.add_argument("--fixture", type=pathlib.Path, default=FIXTURE, help="where to write the JSON snapshot")
    args = parser.parse_args(argv)

    wheel = args.wheel.resolve()
    match = WHEEL_NAME.match(wheel.name)
    if not match:
        return _refuse(f"{wheel.name} is not a juniper-data wheel file name")
    distribution = metadata.distribution("juniper-data")
    version = distribution.version
    if version != match["version"]:
        return _refuse(f"the running interpreter has juniper-data {version}, but the wheel is {match['version']}")

    wheel_sha256 = _sha256(wheel)
    direct_url = json.loads(distribution.read_text("direct_url.json") or "{}")
    installed_hash = (direct_url.get("archive_info") or {}).get("hashes", {}).get("sha256")
    if installed_hash != wheel_sha256:
        return _refuse(f"juniper-data was not installed from {wheel.name}: pip recorded sha256 {installed_hash}, the wheel is {wheel_sha256}")

    src = args.juniper_data_src.resolve()
    commit = _git(src, "rev-parse", f"v{version}^{{commit}}")
    mismatched = []
    compared = 0
    for file in distribution.files or ():
        path = str(file)
        if not path.startswith("juniper_data/") or "__pycache__" in path or path.endswith(".pyc"):
            continue
        compared += 1
        if pathlib.Path(file.locate()).read_bytes() != _git(src, "show", f"{commit}:{path}", text=False):
            mismatched.append(path)
    if not compared or mismatched:
        return _refuse(f"the wheel does not match juniper-data {commit[:8]} (tag v{version}): {mismatched or 'no package files compared'}")

    from juniper_data.api.routes.generators import GENERATOR_REGISTRY  # noqa: E402 -- after the provenance checks, by design

    entries = []
    declared: dict[str, dict[str, object]] = {}
    for name in args.generators:
        info = GENERATOR_REGISTRY[name]
        schema = info["params_class"].model_json_schema()
        entries.append({"name": name, "version": info["version"], "schema": schema})
        declared[name] = {field: prop.get("default") for field, prop in schema["properties"].items()}

    snapshot = {
        "_provenance": {
            "source": "juniper-data",
            "commit": commit,
            # A published wheel cannot carry uncommitted code; ``commit`` is its release tag, verified file by file above.
            "dirty": False,
            "captured": _dt.date.today().isoformat(),
            "what": "GENERATOR_REGISTRY[name]['params_class'].model_json_schema() -- the `schema` field of each GET /v1/generators entry",
            "tool": TOOL,
            "distribution": "juniper-data",
            "version": version,
            "wheel": wheel.name,
            "wheel_sha256": wheel_sha256,
        },
        "generators": entries,
    }
    args.fixture.parent.mkdir(parents=True, exist_ok=True)
    args.fixture.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"# wrote {args.fixture} from juniper-data {version} (wheel sha256 {wheel_sha256[:12]}, tag v{version} = {commit[:8]}, {compared} package files identical)", file=sys.stderr)
    print("DECLARED_PARAM_DEFAULTS entries: " + pprint.pformat(declared, width=500, sort_dicts=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
