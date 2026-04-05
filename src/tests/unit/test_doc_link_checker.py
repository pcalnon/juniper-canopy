#!/usr/bin/env python
"""Unit tests for documentation link checker hardening paths."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_checker_module():
    script_path = Path(__file__).resolve().parents[3] / "scripts" / "check_doc_links.py"
    spec = importlib.util.spec_from_file_location("check_doc_links", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_doc_links = _load_checker_module()


@pytest.mark.unit
def test_heading_to_anchor_normalizes_unicode_and_punctuation():
    """Anchor conversion should match GitHub-style normalized IDs."""
    assert check_doc_links._heading_to_anchor("Café API: v1.0!") == "cafe-api-v10"


@pytest.mark.unit
def test_extract_headings_collects_expected_anchors():
    """Only markdown headings should produce anchor IDs."""
    anchors = check_doc_links._extract_headings("# Title\n## API Reference\nnot a heading\n### Café Mode\n")
    assert anchors == {"title", "api-reference", "cafe-mode"}


@pytest.mark.unit
def test_discover_ecosystem_root_falls_back_to_parent_scan(tmp_path):
    """Fallback discovery should find a parent with sibling ecosystem repos."""
    ecosystem_root = tmp_path
    (ecosystem_root / "juniper-canopy").mkdir()
    (ecosystem_root / "juniper-cascor").mkdir()
    (ecosystem_root / "juniper-data").mkdir()

    found = check_doc_links._discover_ecosystem_root(ecosystem_root / "juniper-canopy")
    assert found == ecosystem_root


@pytest.mark.unit
def test_cross_repo_structure_rejects_escape_sequences():
    """Cross-repo links must not traverse back out of target repo."""
    error = check_doc_links._validate_cross_repo_structure("../juniper-data/docs/../../secrets.md")
    assert error is not None
    assert "escapes target repository" in error


@pytest.mark.unit
def test_validate_file_ignores_inline_and_fenced_links(tmp_path):
    """Links in inline code/fenced blocks should not be validated."""
    repo_root = tmp_path
    md_file = repo_root / "docs" / "guide.md"
    md_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text(
        "\n".join(
            [
                "This inline sample should be ignored: `[bad](inline-missing.md)`",
                "```markdown",
                "[also-bad](fenced-missing.md)",
                "```",
                "[real-bad](missing.md)",
            ]
        ),
        encoding="utf-8",
    )

    errors, cross_repo_skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert cross_repo_skipped == 0
    assert len(errors) == 1
    assert "missing.md" in errors[0]


@pytest.mark.unit
def test_validate_file_rejects_absolute_null_and_excessive_traversal(tmp_path):
    """Security validation should reject unsafe path forms early."""
    repo_root = tmp_path
    md_file = repo_root / "docs" / "security.md"
    md_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text(
        "\n".join(
            [
                "[abs](/etc/passwd)",
                "[null](bad\x00name.md)",
                "[deep](../../../../../../a.md)",
            ]
        ),
        encoding="utf-8",
    )

    errors, _ = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert any("absolute path in documentation link" in error for error in errors)
    assert any("null byte in link target" in error for error in errors)
    assert any("excessive directory traversal" in error for error in errors)


@pytest.mark.unit
def test_validate_file_cross_repo_skip_counts_without_error(tmp_path):
    """Skip mode should classify cross-repo links without failing validation."""
    repo_root = tmp_path
    md_file = repo_root / "docs" / "cross_repo.md"
    md_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text("[cross](../juniper-data/docs/README.md)\n", encoding="utf-8")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert errors == []
    assert skipped == 1


@pytest.mark.unit
def test_validate_file_cross_repo_check_resolves_existing_target(tmp_path):
    """Check mode should validate cross-repo links against ecosystem root."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    target_repo = ecosystem_root / "juniper-data"
    md_file = repo_root / "docs" / "cross_repo.md"
    target_file = target_repo / "docs" / "README.md"

    md_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text("[cross](../juniper-data/docs/README.md)\n", encoding="utf-8")
    target_file.write_text("# target\n", encoding="utf-8")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="check", ecosystem_root=ecosystem_root)

    assert errors == []
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
