"""The publish import smoke is what stops a wheel shipping without modules it imports.

Releases 0.5.0 through 0.8.0 passed ``twine check`` and ``import juniper_canopy`` while
``frontend.dashboard_manager`` died on a missing ``canopy_constants`` (canopy#631).
``[tool.setuptools.packages.find]`` collects packages only, so every bare ``src/<name>.py``
has to be listed in ``py-modules`` or it is absent from the wheel. The image never noticed:
``Dockerfile`` puts ``src/`` on ``PYTHONPATH``. ``util/wheel_import_smoke.py`` is the gate
that runs against the built wheel, from a directory that is not the checkout.

#685 added ``src/outbound_errors.py`` and imported it from ``main`` without listing it.
These tests fail if that happens again, and they fail if the smoke script starts treating
a checkout import or a run from the repository root as success.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "util" / "wheel_import_smoke.py"
WORKFLOW = REPO / ".github" / "workflows" / "publish.yml"

# ``demo_mode`` imports torch. A bare ``pip install juniper-canopy`` does not have it, so the
# smoke must not import it. The module still has to be in the wheel: the demo extra imports it.
BARE_SMOKE_EXCLUSIONS = frozenset({"demo_mode"})

# Scaffold for a stream the adapter does not open yet. Nothing in the shipped tree imports it,
# which is the only reason it is allowed to stay out of the wheel (CHANGELOG, canopy#631).
UNSHIPPED_SCAFFOLD = "adapter_validation"


def _load():
    spec = importlib.util.spec_from_file_location("wheel_import_smoke", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pyproject() -> dict:
    import tomllib

    return tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))


def _py_modules() -> list[str]:
    return list(_pyproject()["tool"]["setuptools"]["py-modules"])


def _production_sources() -> list[Path]:
    files: list[Path] = []
    for base in (REPO / "src", REPO / "juniper_canopy"):
        for path in base.rglob("*.py"):
            if "tests" in path.parts:
                continue
            files.append(path)
    return files


def _imported_roots() -> set[str]:
    """Top-level module names imported by shipped code (not tests, not relative imports)."""
    names: set[str] = set()
    for path in _production_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".", 1)[0])
    return names


def _src_stems() -> set[str]:
    return {path.stem for path in (REPO / "src").glob("*.py") if path.stem != "__init__"}


def _stub_imports(monkeypatch, smoke, kinds: dict[str, str]):
    """``kinds`` maps a module name to ``wheel``, ``checkout``, ``namespace``, or ``missing``."""

    def fake(name):
        kind = kinds.get(name, "wheel")
        if kind == "missing":
            raise ModuleNotFoundError(f"No module named {name!r}")
        if kind == "namespace":
            return types.ModuleType(name)
        module = types.ModuleType(name)
        if kind == "checkout":
            module.__file__ = f"/work/src/{name.replace('.', '/')}.py"
        elif kind == "blank":
            module.__file__ = ""
        else:
            module.__file__ = f"/venv/lib/python3.12/site-packages/{name.replace('.', '/')}.py"
        return module

    monkeypatch.setattr(smoke, "importlib", types.SimpleNamespace(import_module=fake))


def _run(monkeypatch, smoke, tmp_path, modules, kinds, allow_repo=False):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["wheel_import_smoke.py", *(["--allow-repo-cwd"] if allow_repo else [])])
    monkeypatch.setattr(smoke, "MODULES", tuple(modules))
    _stub_imports(monkeypatch, smoke, kinds)
    return smoke.main()


class TestTheWheelListsWhatShippedCodeImports:
    def test_the_only_src_module_left_out_is_the_unimported_scaffold(self):
        # Dropping outbound_errors from py-modules puts it in this set: main imports it, and
        # packages.find will not collect it. Adding a new src/*.py without a py-modules entry
        # does the same. Shipping adapter_validation, or starting to import it, changes the pair.
        unshipped = _src_stems() - set(_py_modules())
        assert unshipped == {UNSHIPPED_SCAFFOLD}
        assert UNSHIPPED_SCAFFOLD not in _imported_roots()

    def test_the_bare_smoke_imports_every_shipped_module_except_demo_mode(self):
        smoke = _load()
        top_level = {name for name in smoke.MODULES if "." not in name}
        assert set(_py_modules()) - BARE_SMOKE_EXCLUSIONS <= top_level
        assert "demo_mode" in _py_modules()
        assert "demo_mode" not in smoke.MODULES
        # The cascor client is an extra. Importing the service backend here fails a correct bare wheel.
        assert "backend.service_backend" not in smoke.MODULES

    def test_package_dir_points_py_modules_at_src(self):
        # py-modules with no package-dir builds a wheel that contains none of them, and the
        # build still succeeds (canopy#631). juniper_canopy lives at the repo root, not under src.
        package_dir = _pyproject()["tool"]["setuptools"]["package-dir"]
        assert package_dir[""] == "src"
        assert package_dir["juniper_canopy"] == "juniper_canopy"

    def test_dotted_smoke_targets_live_in_a_shipped_package(self):
        includes = _pyproject()["tool"]["setuptools"]["packages"]["find"]["include"]
        smoke = _load()
        for name in smoke.MODULES:
            if "." not in name:
                continue
            head = name.split(".", 1)[0]
            assert any(head == pattern.rstrip("*") for pattern in includes), name


class TestTheSmokeRefusesTheWrongTree:
    def test_the_repository_root_is_refused_before_any_import(self, tmp_path, monkeypatch, capsys):
        package = tmp_path / "juniper_canopy"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "src").mkdir()
        smoke = _load()
        imported: list[str] = []
        monkeypatch.setattr(smoke, "importlib", types.SimpleNamespace(import_module=lambda name: imported.append(name)))
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, "argv", ["wheel_import_smoke.py"])
        assert smoke.main() == 2
        assert imported == []
        err = capsys.readouterr().err
        assert "repository root" in err
        assert "checkout" in err

    def test_the_package_alone_is_not_treated_as_the_repository_root(self, tmp_path, monkeypatch, capsys):
        package = tmp_path / "juniper_canopy"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        smoke = _load()
        assert _run(monkeypatch, smoke, tmp_path, ("canopy_constants",), {"canopy_constants": "wheel"}) == 0
        assert "import smoke test OK: 1 modules" in capsys.readouterr().out

    def test_a_src_tree_alone_is_not_treated_as_the_repository_root(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "src").mkdir()
        smoke = _load()
        assert _run(monkeypatch, smoke, tmp_path, ("canopy_constants",), {"canopy_constants": "wheel"}) == 0
        assert "OK" in capsys.readouterr().out

    def test_allow_repo_cwd_imports_even_from_the_root(self, tmp_path, monkeypatch, capsys):
        package = tmp_path / "juniper_canopy"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (tmp_path / "src").mkdir()
        smoke = _load()
        code = _run(monkeypatch, smoke, tmp_path, ("canopy_constants",), {"canopy_constants": "wheel"}, allow_repo=True)
        assert code == 0
        captured = capsys.readouterr()
        assert "refusing" not in captured.err
        assert "OK: 1 modules" in captured.out


class TestACheckoutImportIsNotAPass:
    def test_a_missing_module_and_a_checkout_module_are_both_reported(self, tmp_path, monkeypatch, capsys):
        smoke = _load()
        kinds = {"missing_mod": "missing", "checkout_mod": "checkout", "ok_mod": "wheel"}
        code = _run(monkeypatch, smoke, tmp_path, ("missing_mod", "checkout_mod", "ok_mod"), kinds)
        assert code == 1
        err = capsys.readouterr().err
        assert "missing_mod:" in err
        assert "checkout_mod:" in err and "not from the installed wheel" in err
        assert "ok_mod" not in err
        assert "IMPORT SMOKE TEST FAILED" in err
        assert "py-modules" in err

    def test_a_namespace_module_is_accepted(self, tmp_path, monkeypatch, capsys):
        smoke = _load()
        assert _run(monkeypatch, smoke, tmp_path, ("ns_mod",), {"ns_mod": "namespace"}) == 0
        assert "OK: 1 modules" in capsys.readouterr().out

    def test_an_empty_file_attribute_is_not_read_as_the_checkout(self, tmp_path, monkeypatch, capsys):
        smoke = _load()
        assert _run(monkeypatch, smoke, tmp_path, ("blank_mod",), {"blank_mod": "blank"}) == 0
        assert "FAILED" not in capsys.readouterr().err

    def test_a_clean_wheel_reports_how_many_modules_imported(self, tmp_path, monkeypatch, capsys):
        smoke = _load()
        names = ("canopy_constants", "settings", "outbound_errors")
        assert _run(monkeypatch, smoke, tmp_path, names, {}) == 0
        assert "import smoke test OK: 3 modules imported from the installed wheel" in capsys.readouterr().out


class TestPublishRunsTheSmokeAgainstTheWheel:
    def test_the_build_job_changes_directory_before_the_wheel_interpreter_runs_the_script(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        step = text.split("- name: Import smoke test", 1)[1].split("\n      - name:", 1)[0]
        assert 'mkdir -p "${RUNNER_TEMP}/smoke-cwd"' in step
        assert 'cd "${RUNNER_TEMP}/smoke-cwd"' in step
        assert step.index('cd "${RUNNER_TEMP}/smoke-cwd"') < step.index("wheel_import_smoke.py")
        assert '"${RUNNER_TEMP}/smoke/bin/pip" install' in step
        assert step.index('pip" install') < step.index('cd "${RUNNER_TEMP}/smoke-cwd"')
        invocation = next(line for line in step.splitlines() if "wheel_import_smoke.py" in line)
        assert '"${RUNNER_TEMP}/smoke/bin/python"' in invocation
        assert "${GITHUB_WORKSPACE}/util/wheel_import_smoke.py" in invocation
        assert "--allow-repo-cwd" not in step
        assert "||" not in invocation
        assert "continue-on-error" not in step
        # One invocation, and it happens before the wheel is uploaded for TestPyPI.
        assert text.count("wheel_import_smoke.py") == 1
        assert text.index("wheel_import_smoke.py") < text.index("Upload dist artifacts")
