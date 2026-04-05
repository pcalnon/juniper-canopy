"""Unit tests for scripts/check_doc_links.py link validation behavior."""

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def check_doc_links_module():
    """Load the standalone link-checking script as a Python module."""
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "check_doc_links.py"
    spec = importlib.util.spec_from_file_location("check_doc_links_script", script_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_heading_anchor_normalization_and_extraction(check_doc_links_module):
    """Headings should normalize to GitHub-style anchors."""
    anchor = check_doc_links_module._heading_to_anchor("  Hello, Wörld!  ")
    assert anchor == "hello-world"

    content = """
# Overview
## API & Usage
###   Mixed_Case Heading
"""
    headings = check_doc_links_module._extract_headings(content)
    assert "overview" in headings
    assert "api--usage" in headings
    assert "mixed_case-heading" in headings


def test_validate_file_rejects_invalid_link_inputs(tmp_path, check_doc_links_module):
    """Input validation should catch high-risk malformed link targets."""
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)

    md_file = docs_dir / "guide.md"
    md_file.write_text(
        "\n".join(
            [
                "# Guide",
                "[absolute](/etc/passwd)",
                "[outside](../../outside.md)",
                "[too-deep](../../../../../../bad.md)",
                "[null-byte](bad\x00path.md)",
                "[missing-anchor](#does-not-exist)",
            ]
        ),
        encoding="utf-8",
    )

    errors, cross_repo_skipped = check_doc_links_module._validate_file(
        md_file=md_file,
        repo_root=repo_root,
        verbose=False,
        cross_repo_mode="skip",
        ecosystem_root=None,
    )

    assert cross_repo_skipped == 0
    assert any("absolute path in documentation link" in err for err in errors)
    assert any("link resolves outside repository boundary" in err for err in errors)
    assert any("excessive directory traversal in link" in err for err in errors)
    assert any("null byte in link target" in err for err in errors)
    assert any("broken anchor #does-not-exist" in err for err in errors)


def test_validate_file_skips_links_in_code_and_inline_code(tmp_path, check_doc_links_module):
    """Links in code blocks/spans should not be treated as real markdown links."""
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)

    (repo_root / "README.md").write_text("# Root", encoding="utf-8")

    md_file = docs_dir / "guide.md"
    md_file.write_text(
        "\n".join(
            [
                "# Guide",
                "`[inline](missing-inline.md)`",
                "```markdown",
                "[in-fence](missing-fence.md)",
                "```",
                "[real-link](README.md)",
            ]
        ),
        encoding="utf-8",
    )

    errors, cross_repo_skipped = check_doc_links_module._validate_file(
        md_file=md_file,
        repo_root=repo_root,
        verbose=False,
        cross_repo_mode="skip",
        ecosystem_root=None,
    )

    assert errors == []
    assert cross_repo_skipped == 0


def test_cross_repo_skip_mode_counts_without_failing(tmp_path, check_doc_links_module):
    """Skip mode should count cross-repo links but not fail valid structure."""
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)

    md_file = docs_dir / "guide.md"
    md_file.write_text("# Guide\n[ecosystem](../juniper-ml/README.md)\n", encoding="utf-8")

    errors, cross_repo_skipped = check_doc_links_module._validate_file(
        md_file=md_file,
        repo_root=repo_root,
        verbose=False,
        cross_repo_mode="skip",
        ecosystem_root=None,
    )

    assert errors == []
    assert cross_repo_skipped == 1


def test_cross_repo_structure_escape_is_rejected_even_when_skipping(tmp_path, check_doc_links_module):
    """Cross-repo links that traverse out of target repo must always fail."""
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)

    md_file = docs_dir / "guide.md"
    md_file.write_text("# Guide\n[bad](../juniper-ml/docs/../../secret.md)\n", encoding="utf-8")

    errors, cross_repo_skipped = check_doc_links_module._validate_file(
        md_file=md_file,
        repo_root=repo_root,
        verbose=False,
        cross_repo_mode="skip",
        ecosystem_root=None,
    )

    assert cross_repo_skipped == 0
    assert any("cross-repo link escapes target repository" in err for err in errors)


def test_cross_repo_check_mode_resolves_against_ecosystem_root(tmp_path, check_doc_links_module):
    """Check mode should validate target existence within the selected sibling repo."""
    ecosystem_root = tmp_path / "eco"
    repo_root = ecosystem_root / "juniper-canopy"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)

    target_repo = ecosystem_root / "juniper-ml"
    target_repo.mkdir(parents=True)
    (target_repo / "README.md").write_text("# Juniper ML", encoding="utf-8")

    md_file = docs_dir / "guide.md"
    md_file.write_text(
        "\n".join(
            [
                "# Guide",
                "[ok](../juniper-ml/README.md)",
                "[missing](../juniper-ml/NOT_FOUND.md)",
            ]
        ),
        encoding="utf-8",
    )

    errors, cross_repo_skipped = check_doc_links_module._validate_file(
        md_file=md_file,
        repo_root=repo_root,
        verbose=False,
        cross_repo_mode="check",
        ecosystem_root=ecosystem_root,
    )

    assert cross_repo_skipped == 0
    assert len(errors) == 1
    assert "file not found in juniper-ml" in errors[0]


def test_discover_ecosystem_root_uses_git_common_dir(monkeypatch, tmp_path, check_doc_links_module):
    """Ecosystem root discovery should honor git common-dir resolution."""
    ecosystem_root = tmp_path / "workspace"
    repo_root = ecosystem_root / "juniper-canopy"
    repo_root.mkdir(parents=True)
    (repo_root / ".git").mkdir()

    # Need >= 3 known repos to satisfy _is_ecosystem_root().
    (ecosystem_root / "juniper-canopy").mkdir(exist_ok=True)
    (ecosystem_root / "juniper-cascor").mkdir(exist_ok=True)
    (ecosystem_root / "juniper-ml").mkdir(exist_ok=True)

    class _Result:
        returncode = 0
        stdout = ".git\n"

    monkeypatch.setattr(check_doc_links_module.subprocess, "run", lambda *args, **kwargs: _Result())

    discovered = check_doc_links_module._discover_ecosystem_root(repo_root)
    assert discovered == ecosystem_root
