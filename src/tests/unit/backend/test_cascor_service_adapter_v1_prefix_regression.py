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
#    This regression test walks the AST of every ``.py`` file under
#    ``src/backend/`` and asserts that no ``_request("GET"|"POST"|…,
#    "/v1/...", …)`` or ``_request(…, f"/v1/...", …)`` call exists.
#    Catches the bug class at PR-merge time rather than at runtime
#    (where the ``except`` clauses swallow the 404 into a warning log
#    and a graceful empty payload, masking the regression).
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


def _iter_backend_py_files() -> Iterator[Path]:
    return (p for p in BACKEND_DIR.rglob("*.py") if p.is_file())


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
