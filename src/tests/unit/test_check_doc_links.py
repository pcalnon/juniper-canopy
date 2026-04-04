"""Regression tests for documentation link checker script."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_doc_links.py"
_SPEC = spec_from_file_location("check_doc_links_script", SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
check_doc_links = module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_doc_links)


@pytest.mark.unit
def test_validate_file_rejects_absolute_paths_and_deep_traversal(tmp_path):
    repo_root = tmp_path
    md_file = repo_root / "docs.md"
    md_file.write_text("[abs](/etc/passwd)\n[deep](../../../../../../oops.md)\n", encoding="utf-8")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    joined = "\n".join(errors)
    assert "absolute path in documentation link" in joined
    assert "excessive directory traversal in link" in joined
    assert skipped == 0


@pytest.mark.unit
def test_validate_file_rejects_null_byte_targets(tmp_path):
    repo_root = tmp_path
    md_file = repo_root / "docs.md"
    md_file.write_text("[null](bad\x00.md)\n", encoding="utf-8")

    errors, _ = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert any("null byte in link target" in error for error in errors)


@pytest.mark.unit
def test_validate_file_ignores_links_inside_code_fences_and_inline_code(tmp_path):
    repo_root = tmp_path
    target = repo_root / "existing.md"
    target.write_text("# Existing\n", encoding="utf-8")
    md_file = repo_root / "docs.md"
    md_file.write_text(
        "```\n"
        "[ignored](missing-in-fence.md)\n"
        "```\n"
        "`[ignored](missing-inline.md)`\n"
        "[ok](existing.md)\n",
        encoding="utf-8",
    )

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert errors == []
    assert skipped == 0


@pytest.mark.unit
def test_validate_file_reports_broken_same_file_anchor(tmp_path):
    repo_root = tmp_path
    md_file = repo_root / "docs.md"
    md_file.write_text("# Present Header\n[ok](#present-header)\n[bad](#missing-anchor)\n", encoding="utf-8")

    errors, _ = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert len(errors) == 1
    assert "broken anchor #missing-anchor" in errors[0]


@pytest.mark.unit
def test_cross_repo_links_are_counted_as_skipped_in_skip_mode(tmp_path):
    repo_root = tmp_path
    md_file = repo_root / "docs.md"
    md_file.write_text("[x](../juniper-ml/README.md)\n", encoding="utf-8")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert errors == []
    assert skipped == 1


@pytest.mark.unit
def test_cross_repo_structure_escape_is_rejected_even_when_skipping(tmp_path):
    repo_root = tmp_path
    md_file = repo_root / "docs.md"
    md_file.write_text("[x](../juniper-ml/docs/../../escape.md)\n", encoding="utf-8")

    errors, skipped = check_doc_links._validate_file(md_file, repo_root, cross_repo_mode="skip")

    assert skipped == 0
    assert any("cross-repo link escapes target repository" in error for error in errors)


@pytest.mark.unit
def test_cross_repo_check_mode_validates_target_existence(tmp_path):
    repo_root = tmp_path / "juniper-canopy"
    repo_root.mkdir()
    md_file = repo_root / "docs.md"
    md_file.write_text(
        "[ok](../juniper-ml/docs/existing.md)\n"
        "[missing](../juniper-ml/docs/missing.md)\n",
        encoding="utf-8",
    )

    ecosystem_root = tmp_path
    target_dir = ecosystem_root / "juniper-ml" / "docs"
    target_dir.mkdir(parents=True)
    (target_dir / "existing.md").write_text("# Exists\n", encoding="utf-8")

    errors, skipped = check_doc_links._validate_file(
        md_file,
        repo_root,
        cross_repo_mode="check",
        ecosystem_root=ecosystem_root,
    )

    assert skipped == 0
    assert len(errors) == 1
    assert "file not found in juniper-ml" in errors[0]


@pytest.mark.unit
def test_main_rejects_invalid_cross_repo_mode(monkeypatch, capsys):
    monkeypatch.setattr(check_doc_links.sys, "argv", ["check_doc_links.py", "--cross-repo", "invalid"])

    rc = check_doc_links.main()
    out = capsys.readouterr().out

    assert rc == 1
    assert "ERROR: --cross-repo must be one of:" in out
