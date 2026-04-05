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


def test_validate_file_rejects_null_byte_targets(tmp_path: Path):
    """Null bytes in link targets should be rejected for safety."""
    checker = _load_doc_link_checker_module()
    repo_root = tmp_path / "repo"
    md_file = repo_root / "docs" / "null-byte.md"

    _write_text(md_file, "# Security\n[bad](safe.md\x00evil)\n")

    errors, skipped = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert len(errors) == 1
    assert "null byte in link target" in errors[0]


def test_cross_repo_warn_mode_warns_and_counts_without_failing(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Warn mode should emit warning output and keep run non-failing."""
    checker = _load_doc_link_checker_module()
    repo_root = tmp_path / "repo"
    md_file = repo_root / "docs" / "cross-warn.md"

    _write_text(md_file, "# Cross\n[remote](../juniper-ml/docs/README.md)\n")

    errors, skipped = checker._validate_file(md_file, repo_root, cross_repo_mode="warn")
    captured = capsys.readouterr()

    assert errors == []
    assert skipped == 1
    assert "WARN (cross-repo):" in captured.out


def test_validate_file_accepts_repo_root_relative_resolution(tmp_path: Path):
    """A link may resolve from repo root when file-local resolution misses."""
    checker = _load_doc_link_checker_module()
    repo_root = tmp_path / "repo"
    md_file = repo_root / "docs" / "nested" / "guide.md"
    root_target = repo_root / "README.md"

    _write_text(md_file, "# Guide\n[repo-readme](README.md)\n")
    _write_text(root_target, "# Root README")

    errors, skipped = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert errors == []


def test_validate_file_reports_repository_boundary_escape_without_depth_overflow(tmp_path: Path):
    """Escapes outside repo should fail even when traversal depth limit is not exceeded."""
    checker = _load_doc_link_checker_module()
    repo_root = tmp_path / "repo"
    md_file = repo_root / "docs" / "boundary.md"

    # Exactly five traversal segments avoids the depth gate (> 5) and exercises boundary checks.
    _write_text(md_file, "# Boundary\n[escape](../../../../../outside.md)\n")

    errors, skipped = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert len(errors) == 1
    assert "link resolves outside repository boundary" in errors[0]
