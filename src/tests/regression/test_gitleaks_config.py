"""Regression: the ruleset CI's Gitleaks step loads from ``.gitleaks.toml`` must not be empty.

Until 2026-10-25 the file held an ``[allowlist]`` and no ``[extend]`` table, and a gitleaks v8
config without ``[extend] useDefault = true`` loads ONLY its own ``[[rules]]`` -- of which it had
none. The Security Scans job's Gitleaks step therefore ran with zero rules and could not fail: a
fabricated GitHub token passed it while gitleaks' built-in config flags the same token (the
defect juniper-ml#2203 found and fixed there).

The structural tests read the config with ``tomllib``. The real-engine tests run the gitleaks
binary (``GITLEAKS_BIN``, else ``gitleaks`` on PATH) on a token ASSEMBLED AT RUNTIME, so this file
holds no literal that gitleaks or GitHub push protection would flag. They skip without a binary,
except in ci.yml's Security Scans job, which runs this file with ``GITLEAKS_PARITY_REQUIRED=1``
after gitleaks-action has put the binary on PATH: a check that could not run is not a pass.

This module imports nothing from ``src/`` and needs no fixture from ``src/tests/conftest.py``, so
the Security Scans job runs it with ``--noconftest`` and only pytest + PyYAML installed.

The conda cases pin the AND-scoped ``generic-api-key`` allowlist for conda build strings (the
recurring class: every conda-env refresh rewrites those lines under a commit no ``.gitleaksignore``
entry can name in advance), which replaced the global path exemption the conda environment YAML
files had -- that one skipped EVERY rule there. A build string in a conda file is allowlisted; the
same line in any other file still fires; and a real-looking value in a conda file still fires,
both under ``generic-api-key`` (the allowlist's regex is half of the AND) and under any other rule
(the allowlist is on ``generic-api-key`` alone). The spec lines are assembled at runtime too:
outside a conda file a literal one is exactly what the rule flags.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import string
import subprocess  # nosec B404 -- runs the gitleaks binary with a fixed argv, never a shell
import tomllib
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.regression]

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG = REPO_ROOT / ".gitleaks.toml"
IGNORE = REPO_ROOT / ".gitleaksignore"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
THIS_FILE = "src/tests/regression/test_gitleaks_config.py"
#: The engine gitleaks-action v3.0.0 installs by default, pinned in ci.yml as GITLEAKS_VERSION.
ENGINE_VERSION = "8.24.3"
ENTRY = re.compile(r"[0-9a-f]{40}:[^:\s]+:[a-z0-9-]+:[0-9]+")
#: The file side of the AND-scoped conda allowlist, exactly as .gitleaks.toml states it.
CONDA_PATH_REGEXES = (r"(?:^|/)conf/conda_environment[^/]*\.ya?ml$", r"(?:^|/)conf/requirements-conda\.txt$")
#: The global path exemptions that remain. Each skips EVERY rule for the files it matches.
BROAD_PATH_EXEMPTIONS = (r"conf/.*\.lock", r"notes/mcp/.*")
CONDA_FILES = ("conf/conda_environment.yaml", "conf/conda_environment_cpu.yaml", "conf/requirements-conda.txt")
CONDA_TOKEN_FILE = "conf/conda_environment_ci.yaml"
NON_CONDA_FILE = "notes/conda_packages.md"

_ALPHABET = string.ascii_letters + string.digits


def _fabricated_github_pat() -> str:
    """A GitHub-PAT-SHAPED value from a fixed-step walk over the alphabet: deterministic, never a credential."""
    return "gh" + "p_" + "".join(_ALPHABET[(11 + i * 29) % len(_ALPHABET)] for i in range(36))


def _fabricated_generic_value() -> str:
    """A 40-character high-variety value with no conda build-string shape: deterministic, never a credential."""
    return "".join(_ALPHABET[(5 + i * 23) % len(_ALPHABET)] for i in range(40))


def _conda_specs() -> list[str]:
    """``<package>=<version>=<build>`` in conda's three build-string forms, one package name per keyword class.

    Each secret generic-api-key would capture (``<version>=<build>``) clears the rule's 3.5 entropy floor
    (3.63, 3.78, 3.80), so the outside-a-conda-file control fires for the right reason.
    """
    return [
        "key" + "utils=1.6.1=" + "h" + "4bc722e_0",  # compiled: h<7 hex>_<build number>
        "fast" + "api=12.6.77=" + "py" + "hd8ed1ab_1",  # noarch python: pyh<7 hex>_<n>
        "cuda-profiler-" + "api=12.6.77=" + "py312" + "h66e93f0_0",  # CPython-specific: py<NNN>h<7 hex>_<n>
    ]


def _config() -> dict:
    with open(CONFIG, "rb") as fh:
        return tomllib.load(fh)


def test_config_extends_the_default_ruleset() -> None:
    # Without this table gitleaks loads only this file's [[rules]]: the zero-rule config that passed every scan.
    assert _config().get("extend", {}).get("useDefault") is True, "[extend] useDefault = true is missing: gitleaks would load no default rule"


def test_the_conda_allowlist_is_and_scoped_to_generic_api_key() -> None:
    cfg = _config()
    # gitleaks 8.24.3 reads neither a top-level [[allowlists]] nor `targetRules`, and its loader drops unknown
    # tables silently; its global [allowlist] is OR-only, so paths there would exempt every rule in those files.
    assert "allowlists" not in cfg, "gitleaks 8.24.3 has no top-level [[allowlists]]: the table would be silently ignored"
    rules = [r for r in cfg.get("rules", []) if r.get("id") == "generic-api-key"]
    assert len(rules) == 1, "expected exactly one [[rules]] entry for generic-api-key: the conda allowlist"
    assert "regex" not in rules[0], "the entry must only ADD an allowlist to the default rule, never replace its regex"
    (allow,) = rules[0]["allowlists"]
    assert str(allow.get("condition", "")).upper() == "AND", "an OR allowlist would exempt the conda files from generic-api-key outright"
    assert tuple(allow.get("paths", ())) == CONDA_PATH_REGEXES
    assert allow.get("regexes"), "without regexes the AND reduces to a path-only exemption"
    assert allow.get("regexTarget", "secret") == "secret", "the regexes must be tested against the captured secret"


def test_no_global_path_exemption_covers_the_conda_files() -> None:
    paths = tuple(_config().get("allowlist", {}).get("paths", ()))
    for path in CONDA_FILES:
        assert not any(re.search(p, path) for p in paths), f"a global [allowlist].paths entry exempts {path} from EVERY rule; the AND-scoped rule allowlist covers it"
    assert paths == BROAD_PATH_EXEMPTIONS, "a new broad path exemption skips every rule for its files: prefer an AND-scoped rule allowlist"


def _ignore_lines() -> list[str]:
    return [line.strip() for line in IGNORE.read_text(encoding="utf-8").splitlines()]


def test_ignore_entries_are_commit_scoped_and_unique() -> None:
    entries = [line for line in _ignore_lines() if line and not line.startswith("#")]
    assert entries, ".gitleaksignore holds no entry"
    for line in entries:
        assert ENTRY.fullmatch(line), f"{line!r}: an entry must name its 40-hex commit; a file-scoped one would hide FUTURE secrets"
    assert len(entries) == len(set(entries)), "duplicate .gitleaksignore entries"


def test_every_ignore_entry_sits_under_a_class_comment() -> None:
    # Entries may be grouped, but the nearest line above a group must be a comment: a blank line orphans it.
    lines = _ignore_lines()
    for i, line in enumerate(lines):
        if not ENTRY.fullmatch(line):
            continue
        j = i - 1
        while j >= 0 and ENTRY.fullmatch(lines[j]):
            j -= 1
        assert j >= 0 and lines[j].startswith("#"), f".gitleaksignore line {i + 1}: every entry belongs to a group under a comment naming its class"


def test_ci_pins_the_engine_and_requires_the_real_engine_run() -> None:
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["security"]["steps"]
    action = next(i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith("gitleaks/gitleaks-action@"))
    assert str(steps[action].get("env", {}).get("GITLEAKS_VERSION")) == ENGINE_VERSION
    runs = [s for s in steps[action + 1 :] if THIS_FILE in str(s.get("run", ""))]
    assert runs, f"no Security Scans step after the gitleaks action runs {THIS_FILE}"
    assert all(str(s.get("env", {}).get("GITLEAKS_PARITY_REQUIRED")) == "1" for s in runs), "the real-engine run must set GITLEAKS_PARITY_REQUIRED=1"


@pytest.fixture
def gitleaks_bin() -> str:
    found = os.environ.get("GITLEAKS_BIN") or shutil.which("gitleaks")
    if found is None:
        if os.environ.get("GITLEAKS_PARITY_REQUIRED") == "1":
            pytest.fail("GITLEAKS_PARITY_REQUIRED=1 but no gitleaks binary (GITLEAKS_BIN unset, none on PATH)")
        pytest.skip("no gitleaks binary (set GITLEAKS_BIN, or put gitleaks on PATH)")
    return found


@pytest.mark.parametrize("mode", ["auto-discovered", "explicit --config", "built-in default (control)"])
def test_real_engine_fires_on_a_fabricated_token(gitleaks_bin: str, tmp_path: Path, mode: str) -> None:
    scan = tmp_path / "scan"
    scan.mkdir()
    (scan / "sample.txt").write_text("GITHUB_TOKEN=" + _fabricated_github_pat() + "\n", encoding="utf-8")
    report = tmp_path / "report.json"
    argv = [gitleaks_bin, "dir", "--redact", "--no-banner", "--no-color", "--exit-code=0", "--report-format=json", f"--report-path={report}"]
    if mode == "auto-discovered":
        # CI's path: gitleaks-action passes no --config, so the engine reads <source>/.gitleaks.toml.
        shutil.copyfile(CONFIG, scan / ".gitleaks.toml")
    elif mode == "explicit --config":
        argv += ["--config", str(CONFIG)]
    # A GITLEAKS_CONFIG* variable outranks <source>/.gitleaks.toml; scrub it so auto-discovery is what is tested.
    env = {k: v for k, v in os.environ.items() if k not in ("GITLEAKS_CONFIG", "GITLEAKS_CONFIG_TOML")}
    res = subprocess.run([*argv, str(scan)], capture_output=True, text=True, timeout=120, check=False, env=env)  # nosec B603
    assert res.returncode == 0, f"gitleaks exited {res.returncode}: {res.stderr[-400:]}"
    with open(report, encoding="utf-8") as fh:
        findings = json.load(fh)
    assert all(f.get("Secret") == "REDACTED" for f in findings), "the report was not redacted"
    fired = {f["RuleID"] for f in findings if Path(f["File"]).name == "sample.txt"}
    assert "github-pat" in fired, f"{mode}: the built-in github-pat rule did not fire -- the ruleset does not include the default rules"


@pytest.fixture
def conda_scan(gitleaks_bin: str, tmp_path: Path) -> dict[tuple[str, int], set[str]]:
    """One real-engine scan of a tree laid out like this repo, through the auto-discovered config: {(path, line): {RuleID}}."""
    specs = _conda_specs()
    files = {
        # The two formats the conda files use: an environment YAML (live and commented-out lines) and `conda list --export`.
        CONDA_FILES[0]: "".join(f"  - {s}\n" for s in specs) + "".join(f"  # - {s}\n" for s in specs),
        CONDA_FILES[1]: "".join(f"  - {s}\n" for s in specs),
        CONDA_FILES[2]: "".join(f"{s}\n" for s in specs),
        NON_CONDA_FILE: "".join(f"  - {s}\n" for s in specs),
        CONDA_TOKEN_FILE: "  - fast" + "api=" + _fabricated_generic_value() + "\n" + "GITHUB_TOKEN=" + _fabricated_github_pat() + "\n",
    }
    scan = tmp_path / "scan"
    for rel, text in files.items():
        (scan / rel).parent.mkdir(parents=True, exist_ok=True)
        (scan / rel).write_text(text, encoding="utf-8")
    shutil.copyfile(CONFIG, scan / ".gitleaks.toml")
    report = tmp_path / "report.json"
    argv = [gitleaks_bin, "dir", "--redact", "--no-banner", "--no-color", "--exit-code=0", "--report-format=json", f"--report-path={report}", str(scan)]
    env = {k: v for k, v in os.environ.items() if k not in ("GITLEAKS_CONFIG", "GITLEAKS_CONFIG_TOML")}
    res = subprocess.run(argv, capture_output=True, text=True, timeout=120, check=False, env=env)  # nosec B603
    assert res.returncode == 0, f"gitleaks exited {res.returncode}: {res.stderr[-400:]}"
    with open(report, encoding="utf-8") as fh:
        findings = json.load(fh)
    assert all(f.get("Secret") == "REDACTED" for f in findings), "the report was not redacted"
    hits: dict[tuple[str, int], set[str]] = {}
    for f in findings:
        rel = Path(f["File"]).resolve().relative_to(scan.resolve()).as_posix()
        hits.setdefault((rel, f["StartLine"]), set()).add(f["RuleID"])
    return hits


def test_a_conda_build_string_in_a_conda_file_is_allowlisted(conda_scan: dict[tuple[str, int], set[str]]) -> None:
    leaked = sorted(key for key, rules in conda_scan.items() if key[0] in CONDA_FILES and "generic-api-key" in rules)
    assert not leaked, f"generic-api-key fired on a conda build string inside a conda environment file: {leaked}"


def test_the_same_build_string_outside_a_conda_file_still_fires(conda_scan: dict[tuple[str, int], set[str]]) -> None:
    fired = sorted(line for (rel, line), rules in conda_scan.items() if rel == NON_CONDA_FILE and "generic-api-key" in rules)
    assert fired == [1, 2, 3], f"the path is half of the AND: the same spec lines in {NON_CONDA_FILE} must fire (got lines {fired})"


def test_a_real_looking_token_in_a_conda_file_still_fires(conda_scan: dict[tuple[str, int], set[str]]) -> None:
    generic = conda_scan.get((CONDA_TOKEN_FILE, 1), set())
    assert "generic-api-key" in generic, "the regex is half of the AND: a value of any other shape in a conda file must still fire"
    other = conda_scan.get((CONDA_TOKEN_FILE, 2), set())
    assert "github-pat" in other, "the allowlist is on generic-api-key alone: every other rule must still fire in a conda file"
