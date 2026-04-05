"""Unit tests for scripts/check_doc_links.py."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

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
    content = "Inline code should be ignored: `[inline](missing.md)`\n\n" "```markdown\n" "[code-fence](also-missing.md)\n" "```\n"
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
    assert "Ecosystem root not found" in output
    assert "Cross-repo links: skip" in output


@pytest.mark.unit
def test_validate_file_warn_mode_emits_warning_and_counts_skip(tmp_path, capsys):
    """Warn mode should report cross-repo links without failing."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "warn.md",
        "# Warn\n\n[target](../juniper-cascor/README.md)\n",
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="warn")
    output = capsys.readouterr().out

    assert errors == []
    assert skipped == 1
    assert "WARN (cross-repo):" in output
    assert "../juniper-cascor/README.md" in output


@pytest.mark.unit
def test_validate_file_reports_cross_repo_escape_integration(tmp_path):
    """Cross-repo links that traverse out of target repo should fail validation."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "escape.md",
        "# Escape\n\n[bad](../juniper-cascor/../secret.md)\n",
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert len(errors) == 1
    assert "cross-repo link escapes target repository" in errors[0]


@pytest.mark.unit
def test_validate_file_reports_cross_repo_missing_target_in_check_mode(tmp_path):
    """Check mode should fail when cross-repo target file is missing."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    md_file = _write_file(
        repo_root / "docs" / "missing_cross_repo.md",
        "# Missing\n\n[target](../juniper-cascor/README.md)\n",
    )
    (ecosystem_root / "juniper-cascor").mkdir(parents=True, exist_ok=True)

    errors, skipped = check_doc_links._validate_file(
        md_file,
        repo_root,
        cross_repo_mode="check",
        ecosystem_root=ecosystem_root,
    )

    assert skipped == 0
    assert len(errors) == 1
    assert "file not found in juniper-cascor" in errors[0]


@pytest.mark.unit
def test_validate_file_reports_repository_boundary_escape(tmp_path):
    """Links resolving outside repo boundary should be rejected."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "bounds.md",
        "# Bounds\n\n[bad](../../../outside.md)\n",
    )

    errors, _ = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert len(errors) == 1
    assert "link resolves outside repository boundary" in errors[0]


@pytest.mark.unit
def test_validate_file_reports_missing_local_file(tmp_path):
    """Missing in-repo file links should be reported."""
    repo_root = tmp_path / "repo"
    md_file = _write_file(
        repo_root / "docs" / "missing_local.md",
        "# Missing Local\n\n[broken](missing.md)\n",
    )

    errors, _ = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert len(errors) == 1
    assert "file not found" in errors[0]


@pytest.mark.unit
def test_find_markdown_files_honors_skip_and_exclude_dirs(tmp_path):
    """Markdown discovery should skip ignored dirs and excluded trees."""
    repo_root = tmp_path / "repo"
    docs_file = _write_file(repo_root / "docs" / "guide.md", "# Guide\n")
    _write_file(repo_root / ".git" / "internal.md", "# Internal\n")
    _write_file(repo_root / "templates" / "template.md", "# Template\n")
    _write_file(repo_root / "outside_docs" / "readme.rst", "Heading\n")

    files = check_doc_links._find_markdown_files(
        [repo_root],
        repo_root,
        exclude_dirs={"templates"},
    )

    assert docs_file in files
    assert all(".git" not in str(p) for p in files)
    assert all("templates" not in str(p) for p in files)


@pytest.mark.unit
def test_discover_ecosystem_root_uses_git_common_dir(monkeypatch, tmp_path):
    """Git common-dir discovery should resolve ecosystem parent when present."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / ".git").mkdir(exist_ok=True)
    (ecosystem_root / "juniper-cascor").mkdir(exist_ok=True)
    (ecosystem_root / "juniper-data").mkdir(exist_ok=True)

    monkeypatch.setattr(
        check_doc_links.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=".git\n"),
    )

    discovered = check_doc_links._discover_ecosystem_root(repo_root)
    assert discovered == ecosystem_root


@pytest.mark.unit
def test_discover_ecosystem_root_falls_back_when_git_missing(monkeypatch, tmp_path):
    """Discovery should fallback to parent walk when git executable is unavailable."""
    ecosystem_root = tmp_path / "ecosystem"
    repo_root = ecosystem_root / "juniper-canopy"
    repo_root.mkdir(parents=True, exist_ok=True)
    (ecosystem_root / "juniper-cascor").mkdir(exist_ok=True)
    (ecosystem_root / "juniper-data").mkdir(exist_ok=True)

    def _raise_file_not_found(*_args, **_kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(check_doc_links.subprocess, "run", _raise_file_not_found)

    discovered = check_doc_links._discover_ecosystem_root(repo_root)
    assert discovered == ecosystem_root


@pytest.mark.unit
def test_main_reports_broken_links_and_warned_cross_repo(monkeypatch, capsys):
    """Main should aggregate file errors and cross-repo warning counts."""
    monkeypatch.setattr(
        check_doc_links.sys,
        "argv",
        [
            "check_doc_links.py",
            "--cross-repo=warn",
            "--exclude=history",
            "--exclude",
            "templates",
            "docs",
        ],
    )

    def _fake_find_markdown_files(search_paths, _repo_root, exclude_dirs):
        assert "history" in exclude_dirs
        assert "templates" in exclude_dirs
        assert len(search_paths) == 1
        return [Path("docs/a.md"), Path("docs/b.md")]

    results = iter(
        [
            (["  docs/a.md:3: broken link [x](missing.md) -> file not found"], 0),
            ([], 2),
        ]
    )

    monkeypatch.setattr(check_doc_links, "_find_markdown_files", _fake_find_markdown_files)
    monkeypatch.setattr(check_doc_links, "_validate_file", lambda *_args, **_kwargs: next(results))

    result = check_doc_links.main()
    output = capsys.readouterr().out

    assert result == 1
    assert "Excluding directories: history, templates" in output
    assert "Cross-repo links: warn" in output
    assert "Cross-repo links warned: 2" in output
    assert "FOUND 1 broken link(s) in 1 file(s)" in output
    assert "FAILED: Documentation link validation" in output
