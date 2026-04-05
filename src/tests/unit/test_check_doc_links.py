#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# File Name:     test_check_doc_links.py
# Author:        Paul Calnon
# Version:       0.1.0
#
# Date Created:  2026-04-04
# Last Modified: 2026-04-04
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Unit tests for scripts/check_doc_links.py.
#    Focuses on security-sensitive link validation paths and parser edge cases
#    added in CI hardening changes.
#
#####################################################################################################################################################################################################
"""Unit tests for documentation link checker script."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "check_doc_links.py"
_SPEC = importlib.util.spec_from_file_location("check_doc_links", _SCRIPT_PATH)
check_doc_links = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
_SPEC.loader.exec_module(check_doc_links)


def _write_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.unit
def test_validate_file_ignores_links_in_code_fences_and_inline_code(tmp_path):
    """Links in fenced/inline code should not be validated."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "guide.md",
        "# Guide\n\n```md\n[broken](missing.md)\n```\n\nUse `[ignored](still-missing.md)` in code.\n\n[ok](existing.md)\n",
    )
    _write_file(repo_root / "docs" / "existing.md", "# Existing\n")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert errors == []
    assert skipped == 0


@pytest.mark.unit
def test_validate_file_reports_missing_same_file_anchor(tmp_path):
    """Broken same-file anchor links should be reported deterministically."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "anchors.md",
        "# Valid Heading\n\n[good](#valid-heading)\n[bad](#missing-heading)\n",
    )

    errors, _ = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert len(errors) == 1
    assert "broken anchor #missing-heading" in errors[0]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("link_target", "expected_error"),
    [
        ("/etc/passwd", "absolute path in documentation link"),
        ("../../../../../../outside.md", "excessive directory traversal in link"),
        ("bad\x00.md", "null byte in link target"),
    ],
)
def test_validate_file_rejects_dangerous_link_inputs(tmp_path, link_target, expected_error):
    """Security input validation should reject absolute/traversal/null-byte paths."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "security.md",
        f"# Security\n\n[danger]({link_target})\n",
    )

    errors, _ = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert len(errors) == 1
    assert expected_error in errors[0]


@pytest.mark.unit
def test_validate_file_in_skip_mode_counts_cross_repo_links_without_failure(tmp_path):
    """Cross-repo links should be counted and skipped in skip mode."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "cross_repo.md",
        "# Cross Repo\n\n[other](../juniper-cascor/README.md)\n",
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert errors == []
    assert skipped == 1


@pytest.mark.unit
def test_validate_file_in_check_mode_validates_cross_repo_target_exists(tmp_path):
    """Cross-repo check mode should validate sibling repo paths."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    md_file = _write_file(
        repo_root / "docs" / "cross_repo_check.md",
        "# Cross Repo\n\n[target](../juniper-cascor/README.md)\n",
    )
    _write_file(ecosystem_root / "juniper-cascor" / "README.md", "# Cascor\n")

    errors, skipped = check_doc_links._validate_file(
        md_file,
        repo_root,
        cross_repo_mode="check",
        ecosystem_root=ecosystem_root,
    )

    assert errors == []
    assert skipped == 0


@pytest.mark.unit
def test_validate_cross_repo_structure_rejects_escape_from_target_repo():
    """Cross-repo paths must not traverse out of the target repository."""
    error = check_doc_links._validate_cross_repo_structure("../juniper-cascor/../secrets.md")
    assert error is not None
    assert "escapes target repository" in error


@pytest.mark.unit
def test_main_rejects_invalid_cross_repo_mode(monkeypatch, capsys):
    """Invalid --cross-repo mode should fail fast with exit code 1."""
    monkeypatch.setattr(check_doc_links.sys, "argv", ["check_doc_links.py", "--cross-repo", "invalid"])

    result = check_doc_links.main()
    output = capsys.readouterr().out

    assert result == 1
    assert "--cross-repo must be one of" in output


@pytest.mark.unit
def test_main_falls_back_to_skip_when_ecosystem_root_missing(monkeypatch, capsys):
    """When cross-repo check mode cannot resolve root, tool should fallback to skip."""
    monkeypatch.setattr(check_doc_links.sys, "argv", ["check_doc_links.py", "--cross-repo", "check"])
    monkeypatch.setattr(check_doc_links, "_discover_ecosystem_root", lambda _: None)
    monkeypatch.setattr(check_doc_links, "_find_markdown_files", lambda *_args, **_kwargs: [])

    result = check_doc_links.main()
    output = capsys.readouterr().out

    assert result == 0
    assert "Ecosystem root not found" in output
    assert "Cross-repo links: skip" in output


@pytest.mark.unit
def test_validate_file_warn_mode_emits_warning_and_counts_skip(tmp_path, capsys):
    """Warn mode should report cross-repo links without failing."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "warn.md",
        "# Warn\n\n[target](../juniper-cascor/README.md)\n",
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="warn")
    output = capsys.readouterr().out

    assert errors == []
    assert skipped == 1
    assert "WARN (cross-repo):" in output
    assert "../juniper-cascor/README.md" in output


@pytest.mark.unit
def test_validate_file_reports_cross_repo_escape_integration(tmp_path):
    """Cross-repo links that traverse out of target repo should fail validation."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "escape.md",
        "# Escape\n\n[bad](../juniper-cascor/../secret.md)\n",
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert len(errors) == 1
    assert "cross-repo link escapes target repository" in errors[0]


@pytest.mark.unit
def test_validate_file_reports_cross_repo_missing_target_in_check_mode(tmp_path):
    """Check mode should fail when cross-repo target file is missing."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    md_file = _write_file(
        repo_root / "docs" / "missing_cross_repo.md",
        "# Missing\n\n[target](../juniper-cascor/README.md)\n",
    )
    (ecosystem_root / "juniper-cascor").mkdir(parents=True, exist_ok=True)

    errors, skipped = check_doc_links._validate_file(
        md_file,
        repo_root,
        cross_repo_mode="check",
        ecosystem_root=ecosystem_root,
    )

    assert skipped == 0
    assert len(errors) == 1
    assert "file not found in juniper-cascor" in errors[0]


@pytest.mark.unit
def test_validate_file_reports_repository_boundary_escape(tmp_path):
    """Links resolving outside repo boundary should be rejected."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "bounds.md",
        "# Bounds\n\n[bad](../../../outside.md)\n",
    )

    errors, _ = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert len(errors) == 1
    assert "link resolves outside repository boundary" in errors[0]


@pytest.mark.unit
def test_validate_file_reports_missing_local_file(tmp_path):
    """Missing in-repo file links should be reported."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "missing_local.md",
        "# Missing Local\n\n[broken](missing.md)\n",
    )

    errors, _ = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert len(errors) == 1
    assert "file not found" in errors[0]


@pytest.mark.unit
def test_find_markdown_files_honors_skip_and_exclude_dirs(tmp_path):
    """Markdown discovery should skip ignored dirs and excluded trees."""
    repo_root = tmp_path / "repo"
    docs_file = _write_file(repo_root / "docs" / "guide.md", "# Guide\n")
    _write_file(repo_root / ".git" / "internal.md", "# Internal\n")
    _write_file(repo_root / "templates" / "template.md", "# Template\n")
    _write_file(repo_root / "outside_docs" / "readme.rst", "Heading\n")

    files = check_doc_links._find_markdown_files(
        [repo_root],
        repo_root,
        exclude_dirs={"templates"},
    )

    assert docs_file in files
    assert all(".git" not in str(p) for p in files)
    assert all("templates" not in str(p) for p in files)


@pytest.mark.unit
def test_discover_ecosystem_root_uses_git_common_dir(monkeypatch, tmp_path):
    """Git common-dir discovery should resolve ecosystem parent when present."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / ".git").mkdir(exist_ok=True)
    (ecosystem_root / "juniper-cascor").mkdir(exist_ok=True)
    (ecosystem_root / "juniper-data").mkdir(exist_ok=True)

    monkeypatch.setattr(
        check_doc_links.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=".git\n"),
    )

    discovered = check_doc_links._discover_ecosystem_root(repo_root)
    assert discovered == ecosystem_root


@pytest.mark.unit
def test_discover_ecosystem_root_falls_back_when_git_missing(monkeypatch, tmp_path):
    """Discovery should fallback to parent walk when git executable is unavailable."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    repo_root.mkdir(parents=True, exist_ok=True)
    (ecosystem_root / "juniper-cascor").mkdir(exist_ok=True)
    (ecosystem_root / "juniper-data").mkdir(exist_ok=True)

    def _raise_file_not_found(*_args, **_kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(check_doc_links.subprocess, "run", _raise_file_not_found)

    discovered = check_doc_links._discover_ecosystem_root(repo_root)
    assert discovered == ecosystem_root


@pytest.mark.unit
def test_main_reports_broken_links_and_warned_cross_repo(monkeypatch, capsys):
    """Main should aggregate file errors and cross-repo warning counts."""
    monkeypatch.setattr(
        check_doc_links.sys,
        "argv",
        [
            "check_doc_links.py",
            "--cross-repo=warn",
            "--exclude=history",
            "--exclude",
            "templates",
            "docs",
        ],
    )

    def _fake_find_markdown_files(search_paths, _repo_root, exclude_dirs):
        assert "history" in exclude_dirs
        assert "templates" in exclude_dirs
        assert len(search_paths) == 1
        return [Path("docs/a.md"), Path("docs/b.md")]

    results = iter(
        [
            (["  docs/a.md:3: broken link [x](missing.md) -> file not found"], 0),
            ([], 2),
        ]
    )

    monkeypatch.setattr(check_doc_links, "_find_markdown_files", _fake_find_markdown_files)
    monkeypatch.setattr(check_doc_links, "_validate_file", lambda *_args, **_kwargs: next(results))

    result = check_doc_links.main()
    output = capsys.readouterr().out

    assert result == 1
    assert "Excluding directories: history, templates" in output
    assert "Cross-repo links: warn" in output
    assert "Cross-repo links warned: 2" in output
    assert "FOUND 1 broken link(s) in 1 file(s)" in output
    assert "FAILED: Documentation link validation" in output
