"""Unit tests for scripts/check_doc_links.py helper behavior."""

import importlib.util
from pathlib import Path

import pytest


def _load_doc_link_checker_module():
    """Load scripts/check_doc_links.py as a module for testing."""
    module_path = Path(__file__).resolve().parents[3] / "scripts" / "check_doc_links.py"
    spec = importlib.util.spec_from_file_location("check_doc_links_script", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = _load_doc_link_checker_module()


@pytest.mark.unit
def test_heading_to_anchor_normalizes_punctuation():
    """Heading text should be converted to stable GitHub-style anchor IDs."""
    assert checker._heading_to_anchor("Network Topology (v2)!") == "network-topology-v2"


@pytest.mark.unit
def test_extract_headings_collects_anchor_ids():
    """Markdown headings should be extracted as anchor IDs."""
    content = "# Main Title\n## Child Section\nNot a heading\n### Sub Topic"
    anchors = checker._extract_headings(content)
    assert anchors == {"main-title", "child-section", "sub-topic"}


@pytest.mark.unit
def test_validate_cross_repo_structure_rejects_escape_sequence():
    """Cross-repo links that traverse out of target repo must be rejected."""
    error = checker._validate_cross_repo_structure("../juniper-cascor/docs/../secrets.md")
    assert error is not None
    assert "escapes target repository" in error


@pytest.mark.unit
def test_validate_file_ignores_links_in_code_and_inline_code(tmp_path):
    """Links inside code fences/inline code should not be validated."""
    repo_root = tmp_path
    docs_dir = repo_root / "docs"
    docs_dir.mkdir()
    (docs_dir / "existing.md").write_text("# Existing\n", encoding="utf-8")

    md_file = docs_dir / "index.md"
    md_file.write_text(
        ("# Title\n" "`[inline](missing.md)`\n\n" "```markdown\n" "[fenced](missing.md)\n" "```\n\n" "[ok](existing.md)\n"),
        encoding="utf-8",
    )

    errors, skipped = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")
    assert errors == []
    assert skipped == 0


@pytest.mark.unit
def test_validate_file_reports_broken_same_file_anchor(tmp_path):
    """Broken same-file anchors should be reported."""
    repo_root = tmp_path
    md_file = repo_root / "README.md"
    md_file.write_text("# Top\n[bad](#missing-anchor)\n", encoding="utf-8")

    errors, skipped = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")
    assert skipped == 0
    assert len(errors) == 1
    assert "broken anchor #missing-anchor" in errors[0]


@pytest.mark.unit
def test_validate_file_counts_cross_repo_links_in_skip_mode(tmp_path):
    """Cross-repo links should be counted and skipped in skip mode."""
    repo_root = tmp_path
    md_file = repo_root / "README.md"
    md_file.write_text("[external-doc](../juniper-cascor/docs/README.md)\n", encoding="utf-8")

    errors, skipped = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")
    assert errors == []
    assert skipped == 1


@pytest.mark.unit
def test_validate_file_rejects_absolute_path_targets(tmp_path):
    """Absolute-path links should fail validation for safety."""
    repo_root = tmp_path
    md_file = repo_root / "README.md"
    md_file.write_text("[bad](/etc/passwd)\n", encoding="utf-8")

    errors, skipped = checker._validate_file(md_file, repo_root, cross_repo_mode="skip")
    assert skipped == 0
    assert len(errors) == 1
    assert "absolute path" in errors[0]
