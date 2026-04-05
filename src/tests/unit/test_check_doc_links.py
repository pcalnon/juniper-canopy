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
"""Regression tests for documentation link checker script."""
"""Unit tests for scripts/check_doc_links.py validation logic."""

import importlib.util
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def check_doc_links_module():
    """Load scripts/check_doc_links.py as a module for direct unit testing."""
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "check_doc_links.py"
    spec = importlib.util.spec_from_file_location("check_doc_links_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_heading_anchor_conversion_and_extraction(check_doc_links_module):
    """Anchor extraction should follow GitHub-style heading normalization."""
    module = check_doc_links_module
    content = "\n".join(
        [
            "# Hello, World!",
            "## Caf\u00e9 au lait",
            "Not a heading",
        ]
    )

    anchors = module._extract_headings(content)

    assert "hello-world" in anchors
    assert "cafe-au-lait" in anchors
    assert "not-a-heading" not in anchors


@pytest.mark.unit
def test_validate_file_skips_links_in_code_blocks_and_inline_code(tmp_path, check_doc_links_module):
    """Links embedded in code should be ignored by validation."""
    module = check_doc_links_module
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)

    existing = docs_dir / "existing.md"
    existing.write_text("# Existing\n", encoding="utf-8")

    md_file = docs_dir / "guide.md"
    md_file.write_text(
        "\n".join(
            [
                "# Guide",
                "```markdown",
                "[ignored](missing-in-code-fence.md)",
                "```",
                "Inline code: `[ignored](missing-inline.md)`",
                "Valid file link: [ok](existing.md)",
            ]
        ),
        encoding="utf-8",
    )

    errors, skipped = module._validate_file(md_file, repo_root, cross_repo_mode="skip")


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_doc_links.py"
_SPEC = spec_from_file_location("check_doc_links_script", SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
check_doc_links = module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_doc_links)


@pytest.mark.unit
def test_validate_file_rejects_absolute_paths_and_deep_traversal(tmp_path):
    repo_root = tmp_path
    md_file = repo_root / "docs.md"
    md_file.write_text("[abs](/etc/passwd)\n[deep](../../../../../../oops.md)\n", encoding="utf-8")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    joined = "\n".join(errors)
    assert "absolute path in documentation link" in joined
    assert "excessive directory traversal in link" in joined
    assert skipped == 0


@pytest.mark.unit
def test_validate_file_rejects_null_byte_targets(tmp_path):
    repo_root = tmp_path
    md_file = repo_root / "docs.md"
    md_file.write_text("[null](bad\x00.md)\n", encoding="utf-8")

    errors, _ = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert any("null byte in link target" in error for error in errors)


@pytest.mark.unit
def test_validate_file_ignores_links_inside_code_fences_and_inline_code(tmp_path):
    repo_root = tmp_path
    target = repo_root / "existing.md"
    target.write_text("# Existing\n", encoding="utf-8")
    md_file = repo_root / "docs.md"
    md_file.write_text(
        "```\n" "[ignored](missing-in-fence.md)\n" "```\n" "`[ignored](missing-inline.md)`\n" "[ok](existing.md)\n",
        encoding="utf-8",
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert errors == []
    assert skipped == 0


@pytest.mark.unit
def test_validate_file_reports_anchor_and_path_security_errors(tmp_path, check_doc_links_module):
    """Validation should reject unsafe paths and broken same-file anchors."""
    module = check_doc_links_module
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)

    md_file = docs_dir / "security.md"
    md_file.write_text(
        "\n".join(
            [
                "# Security",
                "[broken-anchor](#missing-heading)",
                "[absolute](/etc/passwd)",
                "[deep-traversal](../../../../../../outside.md)",
                "[null-byte](bad\x00name.md)",
            ]
        ),
        encoding="utf-8",
    )

    errors, _ = module._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert any("broken anchor #missing-heading" in e for e in errors)
    assert any("absolute path in documentation link" in e for e in errors)
    assert any("excessive directory traversal in link" in e for e in errors)
    assert any("null byte in link target" in e for e in errors)


@pytest.mark.unit
def test_validate_cross_repo_structure_blocks_escape(check_doc_links_module):
    """Cross-repo links must not traverse back out of the target repository."""
    module = check_doc_links_module

    assert module._validate_cross_repo_structure("juniper-cascor/docs/readme.md") is None
    assert "escapes target repository" in module._validate_cross_repo_structure("juniper-cascor/docs/../../secret.md")


@pytest.mark.unit
def test_validate_file_cross_repo_skip_mode_counts_skipped(tmp_path, check_doc_links_module):
    """Cross-repo links in skip mode should be counted and not treated as errors."""
    module = check_doc_links_module
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)

    md_file = docs_dir / "links.md"
    md_file.write_text("# Links\n[external-repo](../juniper-cascor/README.md)\n", encoding="utf-8")

    errors, skipped = module._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert errors == []
    assert skipped == 1


@pytest.mark.unit
def test_validate_file_cross_repo_check_mode_resolves_with_ecosystem_root(tmp_path, check_doc_links_module):
    """Cross-repo check mode should resolve targets against provided ecosystem root."""
    module = check_doc_links_module
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    sibling_repo = ecosystem_root / "juniper-cascor"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)
    sibling_repo.mkdir(parents=True)

    (sibling_repo / "README.md").write_text("# sibling\n", encoding="utf-8")
    md_file = docs_dir / "cross.md"
    md_file.write_text("# Cross\n[ok](../juniper-cascor/README.md)\n[missing](../juniper-cascor/MISSING.md)\n", encoding="utf-8")

    errors, skipped = module._validate_file(md_file, repo_root, cross_repo_mode="check", ecosystem_root=ecosystem_root)

    assert skipped == 0
    assert len(errors) == 1
    assert "file not found in juniper-cascor" in errors[0]
def test_validate_file_reports_broken_same_file_anchor(tmp_path):
    repo_root = tmp_path
    md_file = repo_root / "docs.md"
    md_file.write_text("# Present Header\n[ok](#present-header)\n[bad](#missing-anchor)\n", encoding="utf-8")

    errors, _ = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert len(errors) == 1
    assert "broken anchor #missing-anchor" in errors[0]


@pytest.mark.unit
def test_cross_repo_links_are_counted_as_skipped_in_skip_mode(tmp_path):
    repo_root = tmp_path
    md_file = repo_root / "docs.md"
    md_file.write_text("[x](../juniper-ml/README.md)\n", encoding="utf-8")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert errors == []
    assert skipped == 1


@pytest.mark.unit
def test_cross_repo_structure_escape_is_rejected_even_when_skipping(tmp_path):
    repo_root = tmp_path
    md_file = repo_root / "docs.md"
    md_file.write_text("[x](../juniper-ml/docs/../../escape.md)\n", encoding="utf-8")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert any("cross-repo link escapes target repository" in error for error in errors)


@pytest.mark.unit
def test_cross_repo_check_mode_validates_target_existence(tmp_path):
    repo_root = tmp_path / "juniper-canopy"
    repo_root.mkdir()
    md_file = repo_root / "docs.md"
    md_file.write_text(
        "[ok](../juniper-ml/docs/existing.md)\n" "[missing](../juniper-ml/docs/missing.md)\n",
        encoding="utf-8",
    )

    ecosystem_root = tmp_path
    target_dir = ecosystem_root / "juniper-ml" / "docs"
    target_dir.mkdir(parents=True)
    (target_dir / "existing.md").write_text("# Exists\n", encoding="utf-8")

    errors, skipped = check_doc_links._validate_file(
        md_file,
        repo_root,
        cross_repo_mode="check",
        ecosystem_root=ecosystem_root,
    )

    assert skipped == 0
    assert len(errors) == 1
    assert "file not found in juniper-ml" in errors[0]


@pytest.mark.unit
def test_main_rejects_invalid_cross_repo_mode(monkeypatch, capsys):
    monkeypatch.setattr(check_doc_links.sys, "argv", ["check_doc_links.py", "--cross-repo", "invalid"])

    rc = check_doc_links.main()
    out = capsys.readouterr().out

    assert rc == 1
    assert "ERROR: --cross-repo must be one of:" in out
