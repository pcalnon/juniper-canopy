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
def test_is_ecosystem_root_requires_minimum_repo_count(tmp_path):
    """Ecosystem root detection should require at least three sibling repos."""
    candidate = tmp_path / "ecosystem"
    (candidate / "juniper-canopy").mkdir(parents=True)
    (candidate / "juniper-cascor").mkdir(parents=True)
    assert check_doc_links._is_ecosystem_root(candidate) is False

    (candidate / "juniper-data").mkdir(parents=True)
    assert check_doc_links._is_ecosystem_root(candidate) is True


@pytest.mark.unit
def test_discover_ecosystem_root_uses_relative_git_common_dir(monkeypatch, tmp_path):
    """Discovery should resolve relative git-common-dir paths from repo root."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    (repo_root / ".git").mkdir(parents=True)
    (ecosystem_root / "juniper-cascor").mkdir(parents=True)
    (ecosystem_root / "juniper-data").mkdir(parents=True)

    def _fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=".git\n")

    monkeypatch.setattr(check_doc_links.subprocess, "run", _fake_run)
    discovered = check_doc_links._discover_ecosystem_root(repo_root)

    assert discovered == ecosystem_root


@pytest.mark.unit
def test_discover_ecosystem_root_fallback_walks_parent_dirs(monkeypatch, tmp_path):
    """Discovery should fallback to parent walking when git lookup fails."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    repo_root.mkdir(parents=True)
    (ecosystem_root / "juniper-cascor").mkdir(parents=True)
    (ecosystem_root / "juniper-data").mkdir(parents=True)

    def _fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="")

    monkeypatch.setattr(check_doc_links.subprocess, "run", _fake_run)
    discovered = check_doc_links._discover_ecosystem_root(repo_root)

    assert discovered == ecosystem_root


@pytest.mark.unit
def test_find_markdown_files_handles_exclusions_and_outside_paths(tmp_path):
    """Markdown discovery should apply skips and still include outside explicit paths."""
    repo_root = tmp_path / "repo"
    docs = repo_root / "docs"
    ignored = repo_root / ".git"
    excluded = repo_root / "templates"
    external_dir = tmp_path / "external"

    _write_file(docs / "keep.md", "# keep\n")
    _write_file(ignored / "ignore.md", "# ignored\n")
    _write_file(excluded / "excluded.md", "# excluded\n")
    outside = _write_file(external_dir / "outside.md", "# outside\n")
    _write_file(external_dir / "nested.md", "# nested\n")

    files = check_doc_links._find_markdown_files(
        [repo_root, outside, external_dir],
        repo_root,
        exclude_dirs={"templates"},
    )

    assert docs / "keep.md" in files
    assert outside in files
    assert external_dir / "nested.md" in files
    assert ignored / "ignore.md" not in files
    assert excluded / "excluded.md" not in files


@pytest.mark.unit
def test_validate_file_verbose_skips_external_data_and_cross_repo_links(tmp_path, capsys):
    """Verbose mode should report external/cross-repo skips and keep validation clean."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "verbose.md",
        (
            "# Title\n\n"
            "[external](https://example.com)\n"
            "[data](data:image/png;base64,abc)\n"
            "[protocol-relative](//cdn.example.com/a)\n"
            "[anchor](#title)\n"
            "[cross](../juniper-cascor/README.md)\n"
        ),
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, verbose=True, cross_repo_mode="skip")
    output = capsys.readouterr().out

    assert errors == []
    assert skipped == 1
    assert "SKIP (external)" in output
    assert "OK (anchor)" in output
    assert "SKIP (cross-repo)" in output


@pytest.mark.unit
def test_validate_file_reports_cross_repo_structure_error_in_skip_mode(tmp_path):
    """Cross-repo structural validation must fail even when skip mode is active."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "cross_repo_escape.md",
        "# Escape\n\n[bad](../juniper-cascor/../secrets.md)\n",
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert len(errors) == 1
    assert "cross-repo link escapes target repository" in errors[0]


@pytest.mark.unit
def test_validate_file_detects_cross_repo_symlink_boundary_escape(tmp_path):
    """Resolved cross-repo targets must not escape target repo via symlinks."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    target_repo = ecosystem_root / "juniper-cascor"
    outside = tmp_path / "outside"
    outside.mkdir(parents=True)
    target_repo.mkdir(parents=True)
    (repo_root / "docs").mkdir(parents=True)

    escape_link = target_repo / "escape.md"
    escape_link.symlink_to(outside / "escape.md")

    md_file = _write_file(
        repo_root / "docs" / "cross_repo_symlink.md",
        "# Cross Repo\n\n[target](../juniper-cascor/escape.md)\n",
    )

    errors, skipped = check_doc_links._validate_file(
        md_file,
        repo_root,
        cross_repo_mode="check",
        ecosystem_root=ecosystem_root,
    )

    assert skipped == 0
    assert len(errors) == 1
    assert "cross-repo link escapes target repository boundary" in errors[0]


@pytest.mark.unit
def test_validate_file_reports_when_path_resolves_outside_repo_boundary(tmp_path):
    """Non-cross-repo links that escape repo bounds should be rejected."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "bounds.md",
        "# Bounds\n\n[escape](../../../../../outside.md)\n",
    )

    errors, _ = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert len(errors) == 1
    assert "link resolves outside repository boundary" in errors[0]


@pytest.mark.unit
def test_main_supports_exclude_and_cross_repo_equals_and_reports_failures(monkeypatch, capsys):
    """main() should parse equals-style args and report warning/failed summary deterministically."""
    recorded = {}

    def _fake_find(search_paths, _repo_root, exclude_dirs):
        recorded["search_paths"] = search_paths
        recorded["exclude_dirs"] = exclude_dirs
        return [Path("a.md"), Path("b.md")]

    def _fake_validate(md_file, *_args, **_kwargs):
        if md_file.name == "a.md":
            return ["  a.md:1: broken link [x](y) -> file not found"], 1
        return [], 0

    monkeypatch.setattr(
        check_doc_links.sys,
        "argv",
        ["check_doc_links.py", "--exclude=templates", "--cross-repo=warn", "docs"],
    )
    monkeypatch.setattr(check_doc_links, "_find_markdown_files", _fake_find)
    monkeypatch.setattr(check_doc_links, "_validate_file", _fake_validate)

    result = check_doc_links.main()
    output = capsys.readouterr().out

    assert result == 1
    assert recorded["exclude_dirs"] == {"templates"}
    assert len(recorded["search_paths"]) == 1
    assert "Excluding directories: templates" in output
    assert "Cross-repo links: warn" in output
    assert "Cross-repo links warned: 1" in output
    assert "FOUND 1 broken link(s) in 1 file(s):" in output


@pytest.mark.unit
def test_main_supports_exclude_space_flag(monkeypatch, capsys):
    """main() should parse space-delimited --exclude values."""
    monkeypatch.setattr(check_doc_links.sys, "argv", ["check_doc_links.py", "--exclude", "templates", "--cross-repo", "skip"])
    monkeypatch.setattr(check_doc_links, "_find_markdown_files", lambda *_args, **_kwargs: [])

    result = check_doc_links.main()
    output = capsys.readouterr().out

    assert result == 0
    assert "Excluding directories: templates" in output


@pytest.mark.unit
def test_main_rejects_invalid_cross_repo_mode_equals(monkeypatch, capsys):
    """Invalid equals-style --cross-repo values should fail fast."""
    monkeypatch.setattr(check_doc_links.sys, "argv", ["check_doc_links.py", "--cross-repo=invalid"])

    result = check_doc_links.main()
    output = capsys.readouterr().out

    assert result == 1
    assert "--cross-repo must be one of" in output
