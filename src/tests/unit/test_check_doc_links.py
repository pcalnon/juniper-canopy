"""Unit tests for scripts/check_doc_links.py."""

import importlib.util
from pathlib import Path


def _load_check_doc_links_module():
    """Load scripts/check_doc_links.py as a module for direct unit testing."""
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "check_doc_links.py"
    spec = importlib.util.spec_from_file_location("check_doc_links", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_file_ignores_links_in_code_fences_and_inline_code(tmp_path):
    """Broken links in fenced/inline code should not fail validation."""
    checker = _load_check_doc_links_module()
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)
    (repo_root / "README.md").write_text("# Root README\n", encoding="utf-8")

    md_file = docs_dir / "guide.md"
    md_file.write_text(
        "# Guide\n"
        "Valid link: [root](README.md)\n"
        "Inline code should be ignored: `example [bad](missing-inline.md)`\n"
        "```markdown\n"
        "[also bad](missing-fenced.md)\n"
        "```\n",
        encoding="utf-8",
    )

    errors, skipped = checker._validate_file(md_file, repo_root)
    assert errors == []
    assert skipped == 0


def test_validate_file_reports_missing_same_file_anchor(tmp_path):
    """Missing same-file anchors should be reported as errors."""
    checker = _load_check_doc_links_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)

    md_file = repo_root / "doc.md"
    md_file.write_text(
        "# Existing Heading\n"
        "Jump to [missing](#does-not-exist)\n",
        encoding="utf-8",
    )

    errors, _ = checker._validate_file(md_file, repo_root)
    assert len(errors) == 1
    assert "broken anchor #does-not-exist" in errors[0]


def test_validate_file_rejects_cross_repo_escape_even_in_skip_mode(tmp_path):
    """Cross-repo links that traverse out of target repo are always errors."""
    checker = _load_check_doc_links_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)

    md_file = repo_root / "doc.md"
    md_file.write_text(
        "# Doc\n"
        "[bad](../juniper-ml/../../secrets.md)\n",
        encoding="utf-8",
    )

    errors, skipped = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")
    assert len(errors) == 1
    assert "cross-repo link escapes target repository" in errors[0]
    assert skipped == 0


def test_validate_file_counts_skipped_cross_repo_links(tmp_path):
    """Valid cross-repo links should be counted when skip mode is enabled."""
    checker = _load_check_doc_links_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)

    md_file = repo_root / "doc.md"
    md_file.write_text(
        "# Doc\n"
        "[external sibling](../juniper-ml/README.md)\n",
        encoding="utf-8",
    )

    errors, skipped = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")
    assert errors == []
    assert skipped == 1


def test_main_rejects_invalid_cross_repo_mode(monkeypatch):
    """Unknown --cross-repo modes should fail fast with exit code 1."""
    checker = _load_check_doc_links_module()
    monkeypatch.setattr(checker.sys, "argv", ["check_doc_links.py", "--cross-repo", "invalid-mode"])
    assert checker.main() == 1
