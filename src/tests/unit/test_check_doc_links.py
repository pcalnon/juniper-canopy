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
