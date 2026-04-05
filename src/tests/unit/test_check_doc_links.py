"""Unit tests for scripts/check_doc_links.py."""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "check_doc_links.py"
_SPEC = importlib.util.spec_from_file_location("check_doc_links", _SCRIPT_PATH)
assert _SPEC and _SPEC.loader
check_doc_links = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_doc_links)


def _make_repo_with_doc(tmp_path: Path, content: str) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    md_file = repo_root / "docs" / "guide.md"
    md_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text(content, encoding="utf-8")
    return repo_root, md_file


def test_validate_file_rejects_absolute_link_target(tmp_path: Path) -> None:
    repo_root, md_file = _make_repo_with_doc(tmp_path, "[bad](/etc/passwd)\n")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root)

    assert skipped == 0
    assert any("absolute path in documentation link" in error for error in errors)


def test_validate_file_rejects_repository_boundary_escape(tmp_path: Path) -> None:
    repo_root, md_file = _make_repo_with_doc(tmp_path, "[bad](../../outside.md)\n")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root)

    assert skipped == 0
    assert any("outside repository boundary" in error for error in errors)


def test_validate_file_detects_missing_same_file_anchor(tmp_path: Path) -> None:
    content = "# Existing Heading\n\n[ok](#existing-heading)\n[bad](#missing-heading)\n"
    repo_root, md_file = _make_repo_with_doc(tmp_path, content)

    errors, skipped = check_doc_links._validate_file(md_file, repo_root)

    assert skipped == 0
    assert len(errors) == 1
    assert "broken anchor #missing-heading" in errors[0]


def test_validate_file_ignores_links_in_code_fences_and_inline_code(tmp_path: Path) -> None:
    content = (
        "Inline code should be ignored: `[inline](missing.md)`\n\n"
        "```markdown\n"
        "[code-fence](also-missing.md)\n"
        "```\n"
    )
    repo_root, md_file = _make_repo_with_doc(tmp_path, content)

    errors, skipped = check_doc_links._validate_file(md_file, repo_root)

    assert skipped == 0
    assert errors == []


def test_validate_file_cross_repo_skip_mode_counts_skipped_links(tmp_path: Path) -> None:
    repo_root, md_file = _make_repo_with_doc(tmp_path, "[external](../juniper-data/README.md)\n")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert errors == []
    assert skipped == 1


def test_validate_file_cross_repo_structure_escape_is_rejected(tmp_path: Path) -> None:
    repo_root, md_file = _make_repo_with_doc(tmp_path, "[bad](../juniper-data/docs/../secrets.md)\n")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert any("cross-repo link escapes target repository" in error for error in errors)


def test_validate_file_cross_repo_check_reports_missing_target(tmp_path: Path) -> None:
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "repo"
    target_repo = ecosystem_root / "juniper-data"
    target_repo.mkdir(parents=True)

    md_file = repo_root / "docs" / "guide.md"
    md_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text("[external](../juniper-data/README.md)\n", encoding="utf-8")

    errors, skipped = check_doc_links._validate_file(
        md_file,
        repo_root,
        cross_repo_mode="check",
        ecosystem_root=ecosystem_root,
    )

    assert skipped == 0
    assert any("file not found in juniper-data" in error for error in errors)


def test_discover_ecosystem_root_falls_back_to_parent_search(tmp_path: Path) -> None:
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    repo_root.mkdir(parents=True)
    (ecosystem_root / "juniper-cascor").mkdir()
    (ecosystem_root / "juniper-data").mkdir()

    with patch.object(check_doc_links.subprocess, "run", side_effect=FileNotFoundError):
        discovered = check_doc_links._discover_ecosystem_root(repo_root)

    assert discovered == ecosystem_root


def test_main_rejects_invalid_cross_repo_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_doc_links.sys, "argv", ["check_doc_links.py", "--cross-repo", "invalid"])

    result = check_doc_links.main()

    assert result == 1


def test_main_uses_skip_mode_when_ecosystem_root_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(check_doc_links.sys, "argv", ["check_doc_links.py"])
    monkeypatch.setattr(check_doc_links, "_discover_ecosystem_root", lambda _root: None)
    monkeypatch.setattr(check_doc_links, "_find_markdown_files", lambda *_args, **_kwargs: [])

    result = check_doc_links.main()

    assert result == 0
