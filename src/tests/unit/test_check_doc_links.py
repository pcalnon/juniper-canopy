"""Unit tests for scripts/check_doc_links.py."""

import importlib.util
from pathlib import Path

import pytest


def _load_check_doc_links_module():
    """Load scripts/check_doc_links.py as a testable module."""
    project_root = Path(__file__).resolve().parents[3]
    script_path = project_root / "scripts" / "check_doc_links.py"
    spec = importlib.util.spec_from_file_location("check_doc_links", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def doc_links_module():
    """Fixture returning the loaded documentation-link checker module."""
    return _load_check_doc_links_module()


@pytest.mark.unit
def test_validate_file_ignores_links_in_code_blocks_and_inline_code(tmp_path, doc_links_module):
    """Links inside fenced and inline code must be ignored."""
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)

    (docs_dir / "exists.md").write_text("# Exists\n", encoding="utf-8")
    md_file = docs_dir / "guide.md"
    md_file.write_text(
        "\n".join(
            [
                "# Guide",
                "`[inline-link](missing-inline.md)`",
                "```markdown",
                "[code-link](missing-code.md)",
                "```",
                "[working](exists.md)",
            ]
        ),
        encoding="utf-8",
    )

    errors, skipped = doc_links_module._validate_file(md_file, repo_root)

    assert errors == []
    assert skipped == 0


@pytest.mark.unit
def test_validate_file_reports_anchor_and_file_errors(tmp_path, doc_links_module):
    """Broken same-file anchors and missing files should both be reported."""
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)

    md_file = docs_dir / "readme.md"
    md_file.write_text(
        "\n".join(
            [
                "# Existing Heading",
                "[bad anchor](#missing-heading)",
                "[bad file](does-not-exist.md)",
            ]
        ),
        encoding="utf-8",
    )

    errors, skipped = doc_links_module._validate_file(md_file, repo_root)

    assert skipped == 0
    assert any("broken anchor #missing-heading" in err for err in errors)
    assert any("file not found" in err for err in errors)


@pytest.mark.unit
def test_validate_file_rejects_absolute_nullbyte_and_excessive_traversal(tmp_path, doc_links_module):
    """Security checks should reject dangerous path targets."""
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)

    md_file = docs_dir / "security.md"
    md_file.write_text(
        "\n".join(
            [
                "[absolute](/etc/passwd)",
                "[null-byte](bad\x00path.md)",
                "[too-deep](../../../../../../out.md)",
            ]
        ),
        encoding="utf-8",
    )

    errors, _ = doc_links_module._validate_file(md_file, repo_root)

    assert any("absolute path in documentation link" in err for err in errors)
    assert any("null byte in link target" in err for err in errors)
    assert any("excessive directory traversal in link" in err for err in errors)


@pytest.mark.unit
def test_validate_file_cross_repo_skip_counts_but_still_checks_structure(tmp_path, doc_links_module):
    """Cross-repo skip mode should count valid links and still block escaping paths."""
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True)

    md_file = docs_dir / "cross-repo.md"
    md_file.write_text(
        "\n".join(
            [
                "[valid](juniper-ml/docs/README.md)",
                "[escape](juniper-ml/../secrets.md)",
            ]
        ),
        encoding="utf-8",
    )

    errors, skipped = doc_links_module._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 1
    assert any("cross-repo link escapes target repository" in err for err in errors)


@pytest.mark.unit
def test_validate_file_cross_repo_check_uses_ecosystem_root(tmp_path, doc_links_module):
    """Cross-repo check mode should validate against the provided ecosystem root."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    docs_dir = repo_root / "docs"
    ml_docs_dir = ecosystem_root / "juniper-ml" / "docs"
    docs_dir.mkdir(parents=True)
    ml_docs_dir.mkdir(parents=True)

    (ml_docs_dir / "ok.md").write_text("# OK\n", encoding="utf-8")
    md_file = docs_dir / "cross-repo-check.md"
    md_file.write_text(
        "\n".join(
            [
                "[existing](juniper-ml/docs/ok.md)",
                "[missing](juniper-ml/docs/missing.md)",
            ]
        ),
        encoding="utf-8",
    )

    errors, skipped = doc_links_module._validate_file(
        md_file,
        repo_root,
        cross_repo_mode="check",
        ecosystem_root=ecosystem_root,
    )

    assert skipped == 0
    assert len(errors) == 1
    assert "file not found in juniper-ml" in errors[0]


@pytest.mark.unit
def test_find_markdown_files_respects_skip_dirs_excludes_and_broken_symlinks(tmp_path, doc_links_module):
    """File discovery should skip excluded/ignored dirs and dangling symlinks."""
    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    custom_dir = repo_root / "custom"
    node_modules_dir = repo_root / "node_modules"
    docs_dir.mkdir(parents=True)
    custom_dir.mkdir(parents=True)
    node_modules_dir.mkdir(parents=True)

    good_file = docs_dir / "good.md"
    good_file.write_text("# Good\n", encoding="utf-8")
    (custom_dir / "excluded.md").write_text("# Excluded\n", encoding="utf-8")
    (node_modules_dir / "ignored.md").write_text("# Ignored\n", encoding="utf-8")

    dangling_link = docs_dir / "dangling.md"
    dangling_link.symlink_to(repo_root / "does-not-exist.md")

    found = doc_links_module._find_markdown_files([repo_root], repo_root, exclude_dirs={"custom"})

    assert found == [good_file]
