#!/usr/bin/env python3
"""Negative control for the one-artifact publish: prove the src/tests/unit/test_publish_one_artifact.py cases can FAIL.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-11-15
Status: ad-hoc — investigation (negative control for the port of juniper-cascor#763 and #767, the one-artifact publish;
        the owner's directive of 2026-11-15)
Retire when: the one-artifact template steps in publish.yml are replaced or removed.
Related: .github/workflows/publish.yml (the steps marked "one-artifact publish template", and the republish job);
         src/tests/unit/test_publish_one_artifact.py; adapted from juniper-cascor's
         util/ad-hoc/2026-11-15_verify_publish_one_artifact_tests_are_not_vacuous.py (juniper-cascor#763, #767)

WHY THIS EXISTS
---------------
A test that passes against both the fixed and the broken workflow pins nothing. This copies publish.yml, the test file
and pyproject.toml into a scratch directory, checks that the copy passes, then applies each mutation below: one
exact-match edit, to one place or to every copy of a template step (so that the byte-identity case cannot be what
catches it). It runs the test file under pytest after each, restores the file, and reports any mutation the tests still
pass. The repository itself is never written.

The mutations are juniper-cascor's, retargeted at this repository's single publisher (its sub-package mutations are
replaced by the same properties here), plus this workflow's own: the import smoke test and the build step running
although the artifact is reused, the smoke test made non-blocking, an upload that stops attesting, the artifact's old
name and 30-day retention, an install check with a pypi.org fallback, and a dispatch that builds.

The test file needs only pytest and PyYAML, so it runs with ``--noconftest`` (src/tests/conftest.py imports the
application, which no case here uses). pyproject.toml's addopts pass ``--strict-config``, so the interpreter also
needs the plugins that own its ini keys: pytest-asyncio and pytest-timeout.

    python3 util/ad-hoc/2026-11-15_verify_publish_one_artifact_tests_are_not_vacuous.py [--scratch DIR] [--python PY]

The scratch directory defaults to a new one under the repository's gitignored ``tmp/``. It is left in place.

Exit status: 0 when the baseline passes and every mutation fails the tests; 1 otherwise; 2 when the scratch copy could
not be made or does not pass unmutated.
"""

from __future__ import annotations

import argparse
import datetime
import shutil
import subprocess  # nosec B404 -- runs pytest with a fixed argv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PUBLISH = ".github/workflows/publish.yml"
WORKFLOWS = (PUBLISH,)
TEST = "src/tests/unit/test_publish_one_artifact.py"
COPIED = (*WORKFLOWS, TEST, "pyproject.toml")
REUSE_IF = "        if: steps.reuse.outputs.reuse != 'true'\n"
SMOKE = "      - name: Import smoke test (built wheel, nothing from the checkout)\n"
INSTALL = 'pip install --no-deps --index-url https://test.pypi.org/simple/ "juniper-canopy==${VERSION}"'

#: (label, files, old, new, mode): mode "one" requires exactly one match in each file; "all" replaces every match (at
#: least one in each file); "last" replaces the last match only; an int N replaces the Nth match (0-based) only.
MUTATIONS = (
    ("TestPyPI upload skips an existing file", (PUBLISH,), "          repository-url: https://test.pypi.org/legacy/\n          packages-dir: ${{ env.PUBLISH_DIST_DIR }}/\n", "          repository-url: https://test.pypi.org/legacy/\n          packages-dir: ${{ env.PUBLISH_DIST_DIR }}/\n          skip-existing: true\n", "one"),
    ("the PyPI job builds its own files again", (PUBLISH,), "      - name: Publish to PyPI\n", "      - name: Build package\n        run: python -m build\n\n      - name: Publish to PyPI\n", 0),
    ("one copy of the JSON check drifts", (PUBLISH,), '"HASH_CHECK_ATTEMPTS", "20"', '"HASH_CHECK_ATTEMPTS", "21"', "last"),
    ("a file with another sha256 is not refused", WORKFLOWS, "                  if wrong:\n", "                  if wrong and False:\n", "all"),
    ("a file the run did not build is ignored", WORKFLOWS, "if expected.get(name) != digest)", "if name in expected and expected.get(name) != digest)", "all"),
    ("the dist check ignores an extra file", WORKFLOWS, "if not recorded or present != recorded:", "if not recorded or {k: present.get(k) for k in recorded} != recorded:", "all"),
    ("the record step takes any file", WORKFLOWS, "          if not names or strays:\n", "          if not names:\n", "all"),
    ("the artifact expires before the gate", (PUBLISH,), "          retention-days: 90\n", "          retention-days: 30\n", "one"),
    ("the artifact keeps its old 7-day retention", (PUBLISH,), "          retention-days: 90\n", "          retention-days: 7\n", "one"),
    ("the PyPI check reads TestPyPI", (PUBLISH,), "          INDEX_URL: https://pypi.org\n", "          INDEX_URL: https://test.pypi.org\n", 0),
    ("no TestPyPI check before the PyPI upload", (PUBLISH,), "      - name: Verify TestPyPI still serves exactly these files\n", "      - name: Verify TestPyPI still serves these files\n", "one"),
    ("no TestPyPI check after the TestPyPI upload", (PUBLISH,), "      - name: Verify TestPyPI serves exactly these files\n", "      - name: Verify TestPyPI serves these files\n", "one"),
    ("the PyPI job no longer waits for TestPyPI", (PUBLISH,), "    needs: testpypi\n", "    needs: build\n", "one"),
    ("the JSON check polls without bound", WORKFLOWS, '"HASH_CHECK_ATTEMPTS", "20"', '"HASH_CHECK_ATTEMPTS", "2000"', "all"),
    ("a 404 is not polled through", WORKFLOWS, "except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException) as exc:", "except (ValueError, KeyError, TypeError) as exc:", "all"),
    ("a template step reads a workflow expression", WORKFLOWS, "          # Hash every file the build wrote", "          # ${{ github.repository }}: hash every file the build wrote", "all"),
    ("another package's file is accepted", WORKFLOWS, "if normalized(project) != normalized(package) or not version", "if not version", "all"),
    ("publish.yml also fires on a tag push", (PUBLISH,), "on:\n  release:\n    types: [published]\n", "on:\n  release:\n    types: [published]\n  push:\n    tags: ['v*']\n", "one"),
    ("the build job gains id-token: write", (PUBLISH,), "      actions: read  # the reuse step lists this run's artifacts\n", "      actions: read  # the reuse step lists this run's artifacts\n      id-token: write\n", "one"),
    ("id-token: write goes back to the workflow level", (PUBLISH,), "permissions: {}\n", "permissions:\n  id-token: write\n", "one"),
    ("the TestPyPI job is renamed", (PUBLISH,), "    name: Publish to TestPyPI\n", "    name: Publish to Test PyPI\n", "one"),
    ("the build runs inside the testpypi environment", (PUBLISH,), "    if: startsWith(github.event.release.tag_name, 'v')\n    runs-on: ubuntu-latest\n", "    if: startsWith(github.event.release.tag_name, 'v')\n    runs-on: ubuntu-latest\n    environment: testpypi\n", "one"),
    ("the TestPyPI upload reads another directory", (PUBLISH,), "          repository-url: https://test.pypi.org/legacy/\n          packages-dir: ${{ env.PUBLISH_DIST_DIR }}/\n", "          repository-url: https://test.pypi.org/legacy/\n          packages-dir: dist-other/\n", "one"),
    ("a checkout runs after the PyPI job's download", (PUBLISH,), "      # One-artifact publish template, step 4: before every upload.\n      - name: Verify the dist against SHA256SUMS\n", "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1\n\n      # One-artifact publish template, step 4: before every upload.\n      - name: Verify the dist against SHA256SUMS\n", 1),
    ("the tag guard leaves the build job", (PUBLISH,), "    if: startsWith(github.event.release.tag_name, 'v')\n", "", "one"),
    ("a dispatch builds", (PUBLISH,), "    if: startsWith(github.event.release.tag_name, 'v')\n", "    if: github.event_name == 'workflow_dispatch' || startsWith(github.event.release.tag_name, 'v')\n", "one"),
    ("the install check runs before the sha256 check", (PUBLISH,), "      # One-artifact publish template, step 5: after the TestPyPI upload, before the install check.\n", "      - name: Verify TestPyPI install early\n        run: pip install --no-deps --index-url https://test.pypi.org/simple/ juniper-canopy\n\n      # One-artifact publish template, step 5: after the TestPyPI upload, before the install check.\n", "one"),
    ("the install check falls back to pypi.org", (PUBLISH,), INSTALL, INSTALL.replace(' "juniper-canopy==', ' --extra-index-url https://pypi.org/simple/ "juniper-canopy=='), "one"),
    # The review of juniper-cascor#763's four.
    ("an index answering with zero files passes", WORKFLOWS, "                  if not missing:\n", "                  if not missing or not served:\n", "all"),
    ("the JSON check's request timeout is dropped", WORKFLOWS, "urllib.request.urlopen(request, timeout=30)", "urllib.request.urlopen(request)", "all"),
    ("the dist check counts dotfiles too", WORKFLOWS, '                  if not p.name.startswith("."):\n                      present[p.name]', "                  if True:\n                      present[p.name]", "all"),
    ("the JSON check skips the name and version check", WORKFLOWS, "if normalized(project) != normalized(package) or not version or not re.fullmatch", "if not re.fullmatch", "all"),
    # The reuse step, and the steps it must skip.
    ("the upload runs although the artifact is reused", (PUBLISH,), "      - name: Upload dist artifacts\n" + REUSE_IF, "      - name: Upload dist artifacts\n", "one"),
    ("the build runs although the artifact is reused", (PUBLISH,), "      - name: Build package\n" + REUSE_IF, "      - name: Build package\n", "one"),
    ("the import smoke test runs although the artifact is reused", (PUBLISH,), SMOKE + REUSE_IF, SMOKE, "one"),
    ("the reuse step runs only on the first attempt", (PUBLISH,), "        if: github.run_attempt != '1'\n", "        if: github.run_attempt == '1'\n", "one"),
    ("the reuse step runs in a directory no checkout has made yet", (PUBLISH,), "        working-directory: ${{ github.workspace }}\n", "", "one"),
    ("the reuse step reuses an expired artifact", WORKFLOWS, ' if a["name"] == name and not a["expired"]]', ' if a["name"] == name]', "all"),
    ("the reuse step takes any artifact of the run", WORKFLOWS, ' if a["name"] == name and not a["expired"]]', ' if not a["expired"]]', "all"),
    # What this workflow kept.
    ("the import smoke test may fail without failing the job", (PUBLISH,), SMOKE + REUSE_IF, SMOKE + REUSE_IF + "        continue-on-error: true\n", "one"),
    ("the TestPyPI upload stops attesting", (PUBLISH,), "          attestations: true\n", "          attestations: false\n", 0),
    ("the PyPI upload stops attesting", (PUBLISH,), "          attestations: true\n", "", 1),
    ("the artifact keeps its old name", (PUBLISH,), "          name: ${{ env.PUBLISH_PACKAGE }}-dist\n", "          name: dist\n", 0),
    # The republish job.
    ("the republish job's name says PyPI", WORKFLOWS, "    name: Republish the tested files (dispatch only)\n", "    name: Republish TestPyPI's files to PyPI\n", "all"),
    ("the republish job runs on a release too", WORKFLOWS, "    if: github.event_name == 'workflow_dispatch' && inputs.republish_from_testpypi\n", "    if: inputs.republish_from_testpypi || github.event_name == 'release'\n", "all"),
    ("the republish job uploads bytes it did not check", WORKFLOWS, "              if actual != digest:\n", "              if False:\n", "all"),
    ("the republish job ignores the release run's SHA256SUMS", WORKFLOWS, "              if recorded != digests:\n", "              if False:\n", "all"),
    ("the republish job accepts a branch named like a tag", WORKFLOWS, 'if os.environ.get("GITHUB_REF_TYPE") == "tag" and tag.startswith("v"):', 'if tag.startswith("v"):', "all"),
    ("the republish job takes a foreign file from TestPyPI", WORKFLOWS, "if normalized(project) != normalized(package) or file_version != version:", "if False:", "all"),
    ("the republish job skips the dist check", WORKFLOWS, "      # One-artifact publish template, step 4: before every upload.\n      - name: Verify the dist against SHA256SUMS\n", "      # One-artifact publish template, step 4: before every upload.\n      - name: Verify the dist\n", "last"),
)


def run_tests(python: str, scratch: Path) -> int:
    proc = subprocess.run([python, "-m", "pytest", TEST, "-p", "no:cacheprovider", "--noconftest", "-x", "-q"], cwd=scratch, capture_output=True, text=True, timeout=900, check=False)  # nosec B603 -- fixed argv
    return proc.returncode


def mutate(text: str, old: str, new: str, mode: "str | int") -> "str | None":
    """Return the mutated text, or None when the edit does not apply as its mode requires."""
    count = text.count(old)
    if mode == "one":
        return text.replace(old, new) if count == 1 else None
    if mode == "all":
        return text.replace(old, new) if count >= 1 else None
    nth = count - 1 if mode == "last" else int(mode)
    if not 0 <= nth < count:
        return None
    at = -1
    for _ in range(nth + 1):
        at = text.find(old, at + 1)
    return text[:at] + new + text[at + len(old) :]


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parser.add_argument("--scratch", type=Path, default=REPO / "tmp" / f"verify_publish_one_artifact-{stamp}", help="an empty or absent directory to copy into")
    parser.add_argument("--python", default=sys.executable, help="an interpreter with pytest, pytest-asyncio, pytest-timeout and PyYAML")
    args = parser.parse_args(argv)
    if args.scratch.exists() and any(args.scratch.iterdir()):
        print(f"REFUSED: {args.scratch} is not empty")
        return 2
    for rel in COPIED:
        (args.scratch / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, args.scratch / rel)
    originals = {rel: (args.scratch / rel).read_text(encoding="utf-8") for rel in WORKFLOWS}
    baseline = run_tests(args.python, args.scratch)
    print(f"scratch: {args.scratch}")
    print(f"baseline: pytest exit {baseline}")
    if baseline != 0:
        print("REFUSED: the unmutated copy does not pass")
        return 2
    survivors = []
    for label, files, old, new, mode in MUTATIONS:
        mutated = {rel: mutate(originals[rel], old, new, mode) for rel in files}
        if any(text is None or text == originals[rel] for rel, text in mutated.items()):
            print(f"DID NOT APPLY: {label}")
            survivors.append(label)
            continue
        try:
            for rel, text in mutated.items():
                (args.scratch / rel).write_text(str(text), encoding="utf-8")
            code = run_tests(args.python, args.scratch)
        finally:
            for rel in mutated:
                (args.scratch / rel).write_text(originals[rel], encoding="utf-8")
        print(f"{'caught' if code != 0 else 'SURVIVED'}: {label} (pytest exit {code})")
        if code == 0:
            survivors.append(label)
    print(f"{len(MUTATIONS) - len(survivors)} of {len(MUTATIONS)} mutations caught")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
