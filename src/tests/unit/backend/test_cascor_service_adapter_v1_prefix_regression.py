#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Application:   juniper-canopy
# File Name:     test_cascor_service_adapter_v1_prefix_regression.py
# Author:        Paul Calnon
#
# Date Created:  2026-05-28
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Static (AST-level) regression guard against the ``/v1/v1/...`` URL
#    class-of-bug that hit nine call sites in
#    ``src/backend/cascor_service_adapter.py`` on 2026-05-27.
#
#    ``juniper-cascor-client.JuniperCascorClient._request(method, path, …)``
#    builds ``url = self.api_url + path`` where ``self.api_url`` already
#    includes the ``/v1`` version prefix.  Therefore every ``path`` passed
#    to ``_request`` MUST NOT begin with ``/v1/`` — doing so produces a
#    ``/v1/v1/...`` URL on the wire which cascor returns either as 404
#    (router miss) or, in the current asymmetric-mount state, as 401
#    (middleware fires first).
#
#    This regression test walks the AST of every **cascor-client-based
#    adapter** under ``src/backend/`` (defect #7: scoped by import — only
#    files that import ``juniper_cascor_client`` can exhibit the bug) and
#    asserts that no ``_request("GET"|"POST"|…, "/v1/...", …)`` or
#    ``_request(…, f"/v1/...", …)`` call exists.
#    Catches the bug class at PR-merge time rather than at runtime
#    (where the ``except`` clauses swallow the 404 into a warning log
#    and a graceful empty payload, masking the regression).
#
#    Scoping (defect #7): the ``/v1/v1/...`` double-prefix is specific to
#    ``JuniperCascorClient`` (its ``api_url`` already carries ``/v1``).
#    Other backend adapters — e.g. ``recurrence_service_adapter.py``, which
#    speaks raw ``httpx`` against a plain ``base_url`` and legitimately
#    passes ``/v1/...`` paths through its own ``_call`` — must NOT be
#    guarded. Walking *every* file false-positived on the recurrence
#    adapter during A1-i (forcing a ``_request`` -> ``_call`` rename); the
#    guard now applies only to files that import the cascor client.
#
#####################################################################################################################################################################################################

import ast
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = REPO_ROOT / "src" / "backend"

# The cascor-client methods we're guarding against double-prefixing on.
# Wrappers ``_get`` / ``_post`` / ``_put`` / ``_patch`` / ``_delete`` all
# delegate to ``_request`` (which prepends ``/v1``), so every call to any
# of them with a ``/v1/...``-prefixed path produces the same ``/v1/v1/...``
# regression.
GUARDED_METHODS = frozenset({"_request", "_get", "_post", "_put", "_patch", "_delete"})


def _imports_cascor_client(py_path: Path) -> bool:
    """Return True when ``py_path`` imports ``juniper_cascor_client`` (defect #7 scoping).

    The ``/v1/v1/...`` double-prefix bug is specific to ``JuniperCascorClient._request`` — its
    ``api_url`` already carries the ``/v1`` version prefix. Only files that actually use the cascor
    client can exhibit it; other backend adapters (e.g. the recurrence service adapter, which speaks
    raw ``httpx`` against a plain ``base_url`` and legitimately passes ``/v1/...`` paths) must NOT be
    guarded. Detected at the AST level so a comment/docstring mention of the client does not count.
    """
    tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == "juniper_cascor_client":
                return True
        elif isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == "juniper_cascor_client" for alias in node.names):
                return True
    return False


def _iter_backend_py_files() -> Iterator[Path]:
    """Backend ``.py`` files that import the cascor client — the only ones the guard applies to.

    Defect #7: previously this yielded EVERY file under ``src/backend/``, which false-positived on
    adapters that define their own ``_request``/``_post`` and legitimately use ``/v1/...`` paths
    against a client whose base url has no ``/v1`` (the recurrence service adapter, A1-i). The guard
    now applies only to cascor-client-based adapters — the sole place the double-prefix can occur.
    """
    return (p for p in BACKEND_DIR.rglob("*.py") if p.is_file() and _imports_cascor_client(p))


def _path_arg_str_value(call: ast.Call) -> str | None:
    """Return the literal string value of the path argument to a
    cascor-client method call, if statically determinable, else
    ``None``.

    For ``_request(method, path, …)`` the path is the second positional
    arg.  For ``_get(path, …)`` / ``_post(path, …)`` / ``_put`` /
    ``_patch`` / ``_delete`` it is the first.

    Handles both bare-string and ``f"..."``-form path args.  For
    f-strings we look at the *prefix* (the leading literal segment)
    since that is what controls the ``/v1/`` doubling.
    """
    method_name = call.func.attr if isinstance(call.func, ast.Attribute) else (call.func.id if isinstance(call.func, ast.Name) else None)
    if method_name == "_request":
        if len(call.args) < 2:
            return None
        path_node = call.args[1]
    else:
        if len(call.args) < 1:
            return None
        path_node = call.args[0]
    if isinstance(path_node, ast.Constant) and isinstance(path_node.value, str):
        return path_node.value
    if isinstance(path_node, ast.JoinedStr):
        # f-string: the leading FormattedValue / Constant nodes form the
        # prefix.  Return the leading literal segment so we can guard
        # against ``f"/v1/snapshots/{snapshot_id}/..."``.
        for value in path_node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
            return None
    return None


def _find_guarded_calls_in_file(py_path: Path) -> list[tuple[int, str]]:
    """Return [(line_no, path_arg)] for every ``_request`` call in the
    file whose path argument starts with ``/v1/`` (literal or f-string
    prefix).
    """
    source = py_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(py_path))
    offenders: list[tuple[int, str]] = []

    class _Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            method_name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else None)
            if method_name in GUARDED_METHODS:
                arg_value = _path_arg_str_value(node)
                if arg_value is not None and arg_value.startswith("/v1/"):
                    offenders.append((node.lineno, arg_value))
            self.generic_visit(node)

    _Visitor().visit(tree)
    return offenders


def test_no_request_call_passes_v1_prefix() -> None:
    """Walk ``src/backend/**/*.py`` and assert that no
    ``self._client._request(…, "/v1/...", …)`` call exists.

    Closes the 2026-05-27 ``/v1/v1/...`` regression that broke
    ``stage_dataset``, ``cancel_pending_dataset``, ``get_pending_dataset``,
    ``get_experimental_functions``, ``set_experimental_functions``,
    ``swap_dataset_live``, ``cancel_swap_dataset_live``,
    ``get_dataset_swap_events``, and ``get_snapshot_dataset_swaps`` —
    9 callsites in ``cascor_service_adapter.py``.

    The fix strips the ``/v1`` prefix from each path; the
    cascor-client's ``self.api_url`` (which already includes ``/v1``)
    re-applies it.
    """
    all_offenders: dict[str, list[tuple[int, str]]] = {}
    for py_file in _iter_backend_py_files():
        offenders = _find_guarded_calls_in_file(py_file)
        if offenders:
            rel = py_file.relative_to(REPO_ROOT)
            all_offenders[str(rel)] = offenders

    if all_offenders:
        lines = ["The following _request(...) calls pass a /v1/-prefixed path. " "Strip the /v1 — the cascor-client's api_url already includes it."]
        for rel_path, offenders in sorted(all_offenders.items()):
            for line_no, arg in offenders:
                lines.append(f"  {rel_path}:{line_no} -> path={arg!r}")
        raise AssertionError("\n".join(lines))


def test_cascor_service_adapter_specifically_clean() -> None:
    """Spot-check the file the 2026-05-27 incident was traced to."""
    adapter_path = BACKEND_DIR / "cascor_service_adapter.py"
    assert adapter_path.exists(), f"{adapter_path} not found — regression test cannot run; check repo layout."
    offenders = _find_guarded_calls_in_file(adapter_path)
    assert not offenders, "cascor_service_adapter.py contains /v1/-prefixed _request calls: " f"{offenders}. Strip the /v1 prefix; juniper-cascor-client's _request prepends /v1 itself."


# --------------------------------------------------------------------------- defect #7: scoping


def test_imports_cascor_client_detects_real_imports_only(tmp_path) -> None:
    """``_imports_cascor_client`` keys on AST imports, not comment/docstring mentions."""
    importer = tmp_path / "uses_cascor.py"
    importer.write_text("from juniper_cascor_client import JuniperCascorClient\n\nx = JuniperCascorClient\n")
    submodule_importer = tmp_path / "uses_cascor_exc.py"
    submodule_importer.write_text("from juniper_cascor_client.exceptions import JuniperCascorClientError\n")
    plain = tmp_path / "no_cascor.py"
    # Mentions the client in a docstring and even calls a guarded method with a /v1 path — but does
    # NOT import the client, so it is out of scope (the defect-#7 false-positive class).
    plain.write_text('"""Speaks raw httpx, not the cascor client."""\n\n\nclass A:\n    def f(self):\n        self._post("/v1/train", json={})\n')
    assert _imports_cascor_client(importer) is True
    assert _imports_cascor_client(submodule_importer) is True
    assert _imports_cascor_client(plain) is False


def test_guard_scope_includes_cascor_excludes_non_cascor_adapters() -> None:
    """Defect #7: the guard walks ONLY cascor-client-based adapters.

    ``cascor_service_adapter.py`` (imports ``JuniperCascorClient``) stays in scope; the recurrence
    service adapter (raw httpx, legitimately uses ``/v1/...`` paths through its own ``_call``) is
    excluded — so a non-cascor adapter's own ``_request``/``_post`` with a ``/v1/`` path can never
    false-positive (the A1-i regression class that forced the ``_request`` -> ``_call`` rename).
    """
    scoped = {p.name for p in _iter_backend_py_files()}
    assert "cascor_service_adapter.py" in scoped
    assert "recurrence_service_adapter.py" not in scoped
