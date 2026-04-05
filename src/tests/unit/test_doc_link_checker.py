#!/usr/bin/env python
"""Regression-focused tests for scripts/check_doc_links.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _load_doc_link_checker_module():
    """Load the standalone link-checker script as a Python module."""
    module_path = Path(__file__).resolve().parents[3] / "scripts" / "check_doc_links.py"
    spec = importlib.util.spec_from_file_location("check_doc_links", module_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_text(path: Path, content: str) -> None:
    """Create parent directories and write text content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_validate_file_ignores_code_fences_and_inline_code_links(tmp_path: Path):
    """Broken links inside fenced or inline code should be ignored."""
    checker = _load_doc_link_checker_module()
    repo_root = tmp_path / "repo"
    md_file = repo_root / "docs" / "guide.md"
    existing = repo_root / "docs" / "existing.md"

    _write_text(
        md_file,
        """# Guide
Inline code: `[broken-inline](missing-inline.md)`

```markdown
[broken-fence](missing-fence.md)
```

See [existing](existing.md).
""",
    )
    _write_text(existing, "# Existing")

    errors, skipped = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert errors == []


def test_validate_file_reports_broken_same_file_anchor(tmp_path: Path):
    """Same-file anchors should fail when heading is missing."""
    checker = _load_doc_link_checker_module()
    repo_root = tmp_path / "repo"
    md_file = repo_root / "docs" / "anchors.md"

    _write_text(md_file, "# Title\n\nJump to [missing](#not-present).\n")

    errors, _ = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert len(errors) == 1
    assert "broken anchor #not-present" in errors[0]


def test_validate_file_rejects_absolute_paths_and_excessive_traversal(tmp_path: Path):
    """Absolute paths and too many '..' segments must be rejected."""
    checker = _load_doc_link_checker_module()
    repo_root = tmp_path / "repo"
    md_file = repo_root / "docs" / "security.md"

    _write_text(
        md_file,
        """# Security
[absolute](/etc/passwd)
[deep](../../../../../../outside.md)
""",
    )

    errors, _ = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert len(errors) == 2
    assert any("absolute path in documentation link" in err for err in errors)
    assert any("excessive directory traversal in link" in err for err in errors)


def test_cross_repo_skip_mode_counts_and_skips_links(tmp_path: Path):
    """Cross-repo links should be skipped (not failed) in skip mode."""
    checker = _load_doc_link_checker_module()
    repo_root = tmp_path / "repo"
    md_file = repo_root / "docs" / "cross.md"

    _write_text(md_file, "# Cross\n[remote](../juniper-ml/docs/README.md)\n")

    errors, skipped = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert errors == []
    assert skipped == 1


def test_cross_repo_structure_validation_blocks_escape_paths(tmp_path: Path):
    """Cross-repo links cannot traverse back out of target repository."""
    checker = _load_doc_link_checker_module()
    repo_root = tmp_path / "repo"
    md_file = repo_root / "docs" / "cross-escape.md"

    _write_text(md_file, "# Cross\n[escape](../juniper-ml/docs/../private.md)\n")

    errors, skipped = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert len(errors) == 1
    assert "cross-repo link escapes target repository" in errors[0]


def test_cross_repo_check_mode_validates_existing_target(tmp_path: Path):
    """Cross-repo check mode should validate against discovered ecosystem root."""
    checker = _load_doc_link_checker_module()
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    md_file = repo_root / "docs" / "cross-check.md"
    target = ecosystem_root / "juniper-ml" / "docs" / "README.md"

    _write_text(md_file, "# Cross\n[target](../juniper-ml/docs/README.md)\n")
    _write_text(target, "# Target")

    errors, skipped = checker._validate_file(
        md_file,
        repo_root,
        cross_repo_mode="check",
        ecosystem_root=ecosystem_root,
    )

    assert skipped == 0
    assert errors == []


def test_cross_repo_check_mode_reports_missing_target(tmp_path: Path):
    """Cross-repo check mode should fail when target file is absent."""
    checker = _load_doc_link_checker_module()
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    md_file = repo_root / "docs" / "cross-missing.md"

    _write_text(md_file, "# Cross\n[missing](../juniper-ml/docs/MISSING.md)\n")

    errors, skipped = checker._validate_file(
        md_file,
        repo_root,
        cross_repo_mode="check",
        ecosystem_root=ecosystem_root,
    )

    assert skipped == 0
    assert len(errors) == 1
    assert "file not found in juniper-ml" in errors[0]


def test_find_markdown_files_skips_excluded_and_broken_symlink(tmp_path: Path):
    """File discovery should skip excluded dirs, skip dirs, and broken symlinks."""
    checker = _load_doc_link_checker_module()
    repo_root = tmp_path / "repo"

    keep_file = repo_root / "docs" / "keep.md"
    excluded_file = repo_root / "docs" / "templates" / "excluded.md"
    skip_dir_file = repo_root / "node_modules" / "ignored.md"
    broken_symlink = repo_root / "docs" / "broken.md"

    _write_text(keep_file, "# Keep")
    _write_text(excluded_file, "# Excluded")
    _write_text(skip_dir_file, "# Ignored")
    broken_symlink.parent.mkdir(parents=True, exist_ok=True)
    broken_symlink.symlink_to(repo_root / "does-not-exist.md")

    files = checker._find_markdown_files([repo_root], repo_root, exclude_dirs={"templates"})

    assert files == [keep_file]


def test_discover_ecosystem_root_uses_relative_git_common_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ecosystem root discovery should resolve relative git common dir output."""
    checker = _load_doc_link_checker_module()
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    repo_root.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    (ecosystem_root / "juniper-cascor").mkdir()
    (ecosystem_root / "juniper-data").mkdir()
    (ecosystem_root / "juniper-ml").mkdir()

    class _Result:
        returncode = 0
        stdout = ".git\n"

    def _fake_run(*_args, **_kwargs):
        return _Result()

    monkeypatch.setattr(checker.subprocess, "run", _fake_run)

    discovered = checker._discover_ecosystem_root(repo_root)
    assert discovered == ecosystem_root


def test_main_rejects_invalid_cross_repo_mode(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    """CLI should fail fast for invalid --cross-repo values."""
    checker = _load_doc_link_checker_module()
    monkeypatch.setattr(checker.sys, "argv", ["check_doc_links.py", "--cross-repo", "invalid-mode"])

    rc = checker.main()
    out = capsys.readouterr().out

    assert rc == 1
    assert "ERROR: --cross-repo must be one of" in out


def test_main_falls_back_to_skip_when_ecosystem_root_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """CLI should downgrade check->skip when ecosystem root cannot be discovered."""
    checker = _load_doc_link_checker_module()
    modes_seen: list[str] = []

    def _fake_validate_file(_md_file, _repo_root, verbose=False, cross_repo_mode="check", ecosystem_root=None):
        assert verbose is False
        assert ecosystem_root is None
        modes_seen.append(cross_repo_mode)
        return [], 0

    monkeypatch.setattr(checker.sys, "argv", ["check_doc_links.py"])
    monkeypatch.setattr(checker, "_discover_ecosystem_root", lambda _repo_root: None)
    monkeypatch.setattr(checker, "_find_markdown_files", lambda *_args, **_kwargs: [Path("/workspace/README.md")])
    monkeypatch.setattr(checker, "_validate_file", _fake_validate_file)

    rc = checker.main()
    out = capsys.readouterr().out

    assert rc == 0
    assert "WARNING: Ecosystem root not found." in out
    assert "Cross-repo links: skip" in out
    assert modes_seen == ["skip"]
