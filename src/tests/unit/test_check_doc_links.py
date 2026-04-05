"""Unit tests for scripts/check_doc_links.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _load_check_doc_links_module():
    """Load scripts/check_doc_links.py as a module for direct function testing."""
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "check_doc_links.py"
    spec = importlib.util.spec_from_file_location("check_doc_links_module", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_doc_links = _load_check_doc_links_module()


def test_validate_file_ignores_links_in_code_and_inline_code(tmp_path):
    """Only real markdown links should be validated."""
    repo_root = tmp_path
    md_file = repo_root / "docs.md"
    md_file.write_text(
        "# Title\n"
        "```md\n"
        "[ignored](missing-in-code-fence.md)\n"
        "```\n"
        "Inline code: `[ignored-inline](missing-inline.md)`\n"
        "[real](missing-real.md)\n",
        encoding="utf-8",
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert len(errors) == 1
    assert "missing-real.md" in errors[0]
    assert "missing-in-code-fence.md" not in errors[0]


def test_validate_file_reports_broken_same_file_anchor(tmp_path):
    """Same-file anchors should fail when heading is missing."""
    repo_root = tmp_path
    md_file = repo_root / "anchors.md"
    md_file.write_text(
        "# Existing Heading\n"
        "[ok](#existing-heading)\n"
        "[bad](#missing-heading)\n",
        encoding="utf-8",
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert len(errors) == 1
    assert "broken anchor #missing-heading" in errors[0]


def test_validate_file_rejects_absolute_null_byte_and_excessive_traversal(tmp_path):
    """Input validation should reject unsafe path patterns."""
    repo_root = tmp_path
    md_file = repo_root / "unsafe.md"
    md_file.write_text(
        "[abs](/etc/passwd)\n"
        "[null](bad\x00path.md)\n"
        "[deep](../../../../../../too-deep.md)\n",
        encoding="utf-8",
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert any("absolute path in documentation link" in err for err in errors)
    assert any("null byte in link target" in err for err in errors)
    assert any("excessive directory traversal in link" in err for err in errors)


def test_cross_repo_skip_mode_still_validates_structure(tmp_path):
    """Skip mode should skip valid cross-repo links but still fail escape attempts."""
    repo_root = tmp_path
    md_file = repo_root / "cross_repo.md"
    md_file.write_text(
        "[skip](../juniper-ml/README.md)\n"
        "[escape](../juniper-ml/../../secret.md)\n",
        encoding="utf-8",
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 1
    assert len(errors) == 1
    assert "cross-repo link escapes target repository" in errors[0]


def test_cross_repo_check_mode_validates_target_files(tmp_path):
    """Check mode should verify cross-repo file existence under the target repo."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    target_repo = ecosystem_root / "juniper-ml"
    repo_root.mkdir(parents=True)
    target_repo.mkdir(parents=True)
    (target_repo / "README.md").write_text("# ok\n", encoding="utf-8")

    md_file = repo_root / "cross_repo_check.md"
    md_file.write_text(
        "[ok](../juniper-ml/README.md)\n"
        "[missing](../juniper-ml/MISSING.md)\n",
        encoding="utf-8",
    )

    errors, skipped = check_doc_links._validate_file(
        md_file,
        repo_root,
        cross_repo_mode="check",
        ecosystem_root=ecosystem_root,
    )

    assert skipped == 0
    assert len(errors) == 1
    assert "file not found in juniper-ml" in errors[0]


def test_find_markdown_files_respects_exclusions_and_ignores_broken_symlink(tmp_path):
    """Scanner should exclude configured directories and skip broken symlinks."""
    repo_root = tmp_path
    included = repo_root / "docs" / "good.md"
    excluded_by_skip = repo_root / "node_modules" / "ignored.md"
    excluded_by_flag = repo_root / "templates" / "ignored.md"
    broken_symlink = repo_root / "docs" / "broken.md"

    included.parent.mkdir(parents=True)
    excluded_by_skip.parent.mkdir(parents=True)
    excluded_by_flag.parent.mkdir(parents=True)

    included.write_text("# good\n", encoding="utf-8")
    excluded_by_skip.write_text("# ignored\n", encoding="utf-8")
    excluded_by_flag.write_text("# ignored\n", encoding="utf-8")
    broken_symlink.symlink_to(repo_root / "docs" / "missing-target.md")

    files = check_doc_links._find_markdown_files([repo_root], repo_root, exclude_dirs={"templates"})

    assert included in files
    assert excluded_by_skip not in files
    assert excluded_by_flag not in files
    assert broken_symlink not in files


def test_main_rejects_invalid_cross_repo_mode(monkeypatch):
    """Invalid --cross-repo value should fail fast with exit code 1."""
    monkeypatch.setattr(check_doc_links.sys, "argv", ["check_doc_links.py", "--cross-repo", "invalid-mode"])

    result = check_doc_links.main()

    assert result == 1
