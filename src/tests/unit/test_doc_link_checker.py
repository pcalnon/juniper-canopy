#!/usr/bin/env python
"""Regression-focused tests for scripts/check_doc_links.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

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


@pytest.mark.unit
def test_discover_ecosystem_root_uses_git_common_dir(monkeypatch, tmp_path):
    """Git common-dir discovery should resolve ecosystem root from repo path."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    repo_root.mkdir(parents=True, exist_ok=True)
    (ecosystem_root / "juniper-cascor").mkdir(parents=True, exist_ok=True)
    (ecosystem_root / "juniper-data").mkdir(parents=True, exist_ok=True)

    def _fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=".git\n")

    monkeypatch.setattr(check_doc_links.subprocess, "run", _fake_run)

    found = check_doc_links._discover_ecosystem_root(repo_root)

    assert found == ecosystem_root


@pytest.mark.unit
def test_validate_file_anchor_checks_ignore_external_and_data_urls(tmp_path):
    """Anchor validation should still skip external and data URI links."""
    repo_root = tmp_path
    md_file = repo_root / "docs" / "anchors.md"
    md_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text(
        "\n".join(
            [
                "# Valid Heading",
                "[ok](#valid-heading)",
                "[broken](#missing-heading)",
                "[external](https://example.com/docs)",
                "[badge](data:image/png;base64,abc123)",
            ]
        ),
        encoding="utf-8",
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert len(errors) == 1
    assert "broken anchor #missing-heading" in errors[0]


@pytest.mark.unit
def test_validate_file_cross_repo_warn_reports_without_error(tmp_path, capsys):
    """Warn mode should classify cross-repo links and print warning only."""
    repo_root = tmp_path
    md_file = repo_root / "docs" / "cross_repo_warn.md"
    md_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text("[cross](../juniper-data/docs/README.md)\n", encoding="utf-8")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="warn")
    captured = capsys.readouterr()

    assert errors == []
    assert skipped == 1
    assert "WARN (cross-repo)" in captured.out


@pytest.mark.unit
def test_main_rejects_invalid_cross_repo_mode(monkeypatch, capsys):
    """CLI should fail fast for unsupported --cross-repo values."""
    monkeypatch.setattr(check_doc_links.sys, "argv", ["check_doc_links.py", "--cross-repo", "invalid-mode"])

    result = check_doc_links.main()
    captured = capsys.readouterr()

    assert result == 1
    assert "--cross-repo must be one of" in captured.out


@pytest.mark.unit
def test_main_falls_back_to_skip_when_ecosystem_not_found(monkeypatch, capsys, tmp_path):
    """CLI should degrade from check to skip mode when ecosystem root is unavailable."""
    monkeypatch.setattr(check_doc_links.sys, "argv", ["check_doc_links.py"])
    monkeypatch.setattr(check_doc_links, "_discover_ecosystem_root", lambda _repo_root: None)
    monkeypatch.setattr(check_doc_links, "_find_markdown_files", lambda *_args, **_kwargs: [])

    script_path = tmp_path / "scripts" / "check_doc_links.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("# test script path\n", encoding="utf-8")
    monkeypatch.setattr(check_doc_links, "__file__", str(script_path))

    result = check_doc_links.main()
    captured = capsys.readouterr()

    assert result == 0
    assert "Ecosystem root not found" in captured.out
    assert "Cross-repo links: skip" in captured.out
