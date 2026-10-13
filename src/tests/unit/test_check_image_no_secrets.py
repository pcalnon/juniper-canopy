"""
Pin ``util/check_image_no_secrets.py`` and its two publish-image arms.

The script is the only defence that looks at the built image rather than at a
``.dockerignore`` pattern. An empty scan used to pass: ``/app`` can be a runtime
directory while the code lives in site-packages, and a root that exists but
contains no files has inspected nothing. Both of those must exit 2. A
credential-shaped name must exit 1, including the ``.env.prod`` / ``.env.dev``
spellings a bare ``.env`` rule misses, while the template suffixes stay legal.
Caches are pruned so they cannot hide a sibling credential and cannot
themselves fail the build.

These tests build no image. The workflow assertions pin that both the PR smoke
arm and the publish arm pipe this script into the image and keep its exit
status.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "util" / "check_image_no_secrets.py"
WORKFLOW = REPO / ".github" / "workflows" / "publish-image.yml"
SCRIPT_REL = "util/check_image_no_secrets.py"
BUILD_ONLY_IF = "github.event_name != 'release' && !inputs.push"
PUBLISH_IF = "github.event_name == 'release' || inputs.push"

BAD_NAMES = (
    ".env",
    ".env.prod",
    ".env.dev",
    ".env.example.bak",
    "server.key",
    "server.pem",
    "server.p12",
    "server.pfx",
    "server.jks",
    "server.keystore",
    "id_rsa",
    "id_rsa.pub",
    "id_ecdsa",
    "id_ed25519",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "vault.kdbx",
    ".env.example.key",
)
ALLOWED_NAMES = (
    ".env.example",
    ".env.sample",
    ".env.template",
    ".env.dist",
    "id_rsa.template",
    "server.pem.example",
    "credentials.example",
    "readme.md",
)
BAD_DIRS = ("secrets", ".git", ".ssh", ".aws", ".gnupg", "private")


def _load():
    spec = importlib.util.spec_from_file_location("check_image_no_secrets", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _workflow() -> dict:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML (YAML 1.1) reads the bare `on:` key as boolean True.
    data["on"] = data.pop(True, data.get("on"))
    return data


def _step(name_prefix: str) -> dict:
    matches = [s for s in _workflow()["jobs"]["build"]["steps"] if str(s.get("name", "")).startswith(name_prefix)]
    assert len(matches) == 1, f"expected exactly one step named {name_prefix!r}..., found {len(matches)}"
    return matches[0]


@pytest.fixture
def scanner():
    return _load()


def _main(scanner, monkeypatch, roots: list[Path], capsys) -> tuple[int, str]:
    monkeypatch.setattr(scanner, "scan_roots", lambda: list(roots))
    code = scanner.main()
    return code, capsys.readouterr().out


class TestCredentialNames:
    @pytest.mark.parametrize("name", BAD_NAMES)
    def test_credential_shaped_names_fail(self, scanner, name):
        assert scanner.is_bad_file(name) is True

    @pytest.mark.parametrize("name", ALLOWED_NAMES)
    def test_template_suffixes_and_ordinary_files_pass(self, scanner, name):
        assert scanner.is_bad_file(name) is False


class TestScanRoots:
    def _map(self, scanner, monkeypatch, app: Path, site: Path | None):
        real = scanner.Path

        def mapped(value, *args, **kwargs):
            text = str(value)
            if text == "/app":
                return app
            if site is not None and text == str(site):
                return site
            return real(value, *args, **kwargs)

        monkeypatch.setattr(scanner, "Path", mapped)

    def test_keeps_app_and_every_shipped_juniper_tree(self, scanner, monkeypatch, tmp_path):
        """A dist-info directory is shipped code. Dropping the prefix match would stop scanning it."""
        app = tmp_path / "app"
        app.mkdir()
        site = tmp_path / "site"
        site.mkdir()
        kept = ("candidate_unit", "cascade_correlation", "juniper_canopy", "juniper_canopy-0.8.1.dist-info")
        for name in kept:
            (site / name).mkdir()
        (site / "numpy").mkdir()
        (site / "Juniper").mkdir()
        (site / "juniper_canopy.py").write_text("x", encoding="utf-8")
        self._map(scanner, monkeypatch, app, site)
        monkeypatch.setattr(scanner.sysconfig, "get_paths", lambda: {"purelib": str(site)})

        roots = scanner.scan_roots()

        assert roots[0] == app
        assert [path.name for path in roots[1:]] == list(kept)

    def test_a_missing_app_still_scans_site_packages(self, scanner, monkeypatch, tmp_path):
        app = tmp_path / "absent-app"
        site = tmp_path / "site"
        site.mkdir()
        (site / "juniper_canopy").mkdir()
        self._map(scanner, monkeypatch, app, site)
        monkeypatch.setattr(scanner.sysconfig, "get_paths", lambda: {"purelib": str(site)})

        roots = scanner.scan_roots()

        assert [path.name for path in roots] == ["juniper_canopy"]

    def test_a_missing_site_packages_still_scans_app(self, scanner, monkeypatch, tmp_path):
        app = tmp_path / "app"
        app.mkdir()
        self._map(scanner, monkeypatch, app, None)
        monkeypatch.setattr(scanner.sysconfig, "get_paths", lambda: {})

        assert scanner.scan_roots() == [app]

    def test_no_root_at_all_is_an_empty_scan(self, scanner, monkeypatch, tmp_path):
        app = tmp_path / "absent-app"
        missing_site = tmp_path / "missing-site"
        self._map(scanner, monkeypatch, app, missing_site)
        monkeypatch.setattr(scanner.sysconfig, "get_paths", lambda: {"purelib": str(missing_site)})

        assert scanner.scan_roots() == []


class TestScanVerdict:
    def test_no_root_refuses_instead_of_passing(self, scanner, monkeypatch, capsys):
        code, out = _main(scanner, monkeypatch, [], capsys)
        assert code == 2
        assert "no scan root found" in out
        assert "inspected NOTHING" in out

    def test_an_empty_root_refuses_even_when_it_holds_an_empty_secrets_dir(self, scanner, monkeypatch, tmp_path, capsys):
        """Zero files has proved nothing. An empty secrets directory must not turn that into a pass."""
        root = tmp_path / "app"
        (root / "secrets").mkdir(parents=True)
        code, out = _main(scanner, monkeypatch, [root], capsys)
        assert code == 2
        assert "ZERO files" in out
        assert "proved nothing" in out

    def test_a_clean_tree_passes_and_names_the_root(self, scanner, monkeypatch, tmp_path, capsys):
        root = tmp_path / "app"
        (root / "pkg").mkdir(parents=True)
        (root / "pkg" / "mod.py").write_text("x", encoding="utf-8")
        code, out = _main(scanner, monkeypatch, [root], capsys)
        assert code == 0
        assert "scanned 1 files across 1 root(s)" in out
        assert str(root) in out
        assert "no credential-shaped file" in out

    def test_a_credential_file_fails_and_counts_the_finding(self, scanner, monkeypatch, tmp_path, capsys):
        root = tmp_path / "app"
        root.mkdir()
        (root / ".env.prod").write_text("TOKEN=1", encoding="utf-8")
        (root / "mod.py").write_text("x", encoding="utf-8")
        code, out = _main(scanner, monkeypatch, [root], capsys)
        assert code == 1
        assert "1 credential-shaped path(s)" in out
        assert ".env.prod" in out

    @pytest.mark.parametrize("dirname", BAD_DIRS)
    def test_a_forbidden_directory_is_reported_and_so_is_a_file_inside_it(self, scanner, monkeypatch, tmp_path, capsys, dirname):
        root = tmp_path / "app"
        nested = root / dirname
        nested.mkdir(parents=True)
        (nested / "a.key").write_text("k", encoding="utf-8")
        (root / "mod.py").write_text("x", encoding="utf-8")
        code, out = _main(scanner, monkeypatch, [root], capsys)
        assert code == 1
        assert f"{dirname}/  (directory)" in out
        assert f"{dirname}/a.key" in out

    def test_findings_are_sorted(self, scanner, monkeypatch, tmp_path, capsys):
        root = tmp_path / "app"
        (root / "src").mkdir(parents=True)
        (root / "src" / "b.pem").write_text("pem", encoding="utf-8")
        (root / "secrets").mkdir()
        (root / "secrets" / "a.key").write_text("k", encoding="utf-8")
        (root / "ok.py").write_text("x", encoding="utf-8")
        code, out = _main(scanner, monkeypatch, [root], capsys)
        assert code == 1
        finding_block = out.split("credential-shaped path(s) in the image:\n", 1)[1]
        finding_lines = [line.strip() for line in finding_block.splitlines() if line.strip()]
        assert finding_lines == sorted(finding_lines)
        assert any(line.endswith("secrets/  (directory)") for line in finding_lines)
        assert any(line.endswith("secrets/a.key") for line in finding_lines)
        assert any(line.endswith("src/b.pem") for line in finding_lines)

    @pytest.mark.parametrize("dirname", sorted(_load().PRUNE_DIRS))
    def test_a_pruned_cache_does_not_hide_a_sibling_credential_or_fail_on_its_own(self, scanner, monkeypatch, tmp_path, capsys, dirname):
        root = tmp_path / "app"
        cache = root / dirname
        cache.mkdir(parents=True)
        (cache / ".env").write_text("SECRET=1", encoding="utf-8")
        (root / "keep.py").write_text("x", encoding="utf-8")
        code, out = _main(scanner, monkeypatch, [root], capsys)
        assert code == 0, out
        assert ".env" not in out
        assert "scanned 1 files" in out

        (root / ".env").write_text("SECRET=1", encoding="utf-8")
        code, out = _main(scanner, monkeypatch, [root], capsys)
        assert code == 1
        assert f"{dirname}/.env" not in out
        assert out.count(".env") >= 1


class TestPublishWorkflowKeepsTheExitStatus:
    def test_paths_filter_covers_the_script(self):
        assert SCRIPT_REL in _workflow()["on"]["pull_request"]["paths"]

    @pytest.mark.parametrize(
        ("name", "image", "guard"),
        [
            ("Smoke test (build-only runs)", "${img}", BUILD_ONLY_IF),
            ("Verify pushed image is CPU-only (publish runs)", "${ref}", PUBLISH_IF),
        ],
    )
    def test_both_arms_pipe_the_script_and_do_not_swallow_its_exit(self, name, image, guard):
        step = _step(name)
        assert step["if"] == guard
        run = step["run"]
        invocations = [line.strip() for line in run.splitlines() if SCRIPT_REL in line]
        assert invocations == [f'docker run --rm -i "{image}" python - < {SCRIPT_REL}']
        assert "set +e" not in run
        assert "|| true" not in run
        assert "|| :" not in run
