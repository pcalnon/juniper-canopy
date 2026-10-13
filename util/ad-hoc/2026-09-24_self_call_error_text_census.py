"""
Census: every dashboard self-call that sends ``internal_api_headers()``, and what the handler that
catches its failure does with the exception's TEXT.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-09-24
Status: ad-hoc -- investigation
Retire when: the #678 follow-up is merged. It closed the leak where every site's key comes from:
    ``frontend/internal_api.py`` no longer hands ``requests`` a key it refuses to send, so no
    self-call raises an ``InvalidHeader`` that quotes the key, and none of the sites listed here
    needed changing. This census is the evidence for putting the fix there: 54 of the 64 sites log
    or return the exception text, so fixing site by site would have left the next new site open.
Related: juniper-canopy #678 follow-up, item 6 -- a padded CANOPY_API_KEY reaches the logs.

Why it exists
-------------
``requests`` validates each header while PREPARING a request, and when it rejects a value it raises
``requests.exceptions.InvalidHeader`` whose message is the whole value, ``repr``-quoted::

    Invalid leading whitespace, reserved character(s), or return character(s) in header value: ' leaked-key'

A dashboard self-call sends ``X-API-Key: <CANOPY_API_KEY>`` (``frontend/internal_api.py``), so a
configured key that ``requests`` rejects -- one with leading whitespace, a line break, a leading
U+00A0 -- is copied verbatim into the exception text. Wherever that text is logged (``%s`` of the
exception, an f-string, ``str(e)``, a traceback via ``exc_info`` / ``logger.exception``), the key is
in the log record, and with ``enable_logs=True`` in Sentry Logs.

What it reports
---------------
For every ``internal_api_headers()`` call under ``src/`` (tests excluded) it finds the innermost
enclosing ``try`` whose handler would catch ``InvalidHeader`` (bare, ``Exception``, ``BaseException``,
``RequestException``, ``ValueError``, ``OSError``, ``InvalidHeader``, or a tuple naming one), and
classifies what that handler does with the exception:

- ``TEXT``       -- the bound exception name is interpolated into a log call (``%s`` arg, f-string,
                    ``str()`` / ``repr()`` / ``format``) or into a value the function returns;
- ``TRACEBACK``  -- the handler logs with ``exc_info=`` or ``.exception(``, or formats a traceback;
- ``TYPE-ONLY``  -- it uses only ``type(e)`` / ``type(e).__name__``;
- ``SILENT``     -- it never references the exception;
- ``RERAISE``    -- it re-raises (the text then travels to whoever catches it);
- ``UNCAUGHT``   -- no enclosing ``try`` in the function catches it.

Usage::

    python util/ad-hoc/2026-09-24_self_call_error_text_census.py            # table
    python util/ad-hoc/2026-09-24_self_call_error_text_census.py --json     # machine-readable

Exit status is 0 (an instrument, not a gate).
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"

# Handler types that catch requests.exceptions.InvalidHeader (MRO: InvalidHeader ->
# RequestException -> OSError -> ... and ValueError). Matched on the LAST dotted component.
CATCHES_INVALID_HEADER = {"Exception", "BaseException", "RequestException", "ValueError", "OSError", "IOError", "EnvironmentError", "InvalidHeader"}
LOG_METHODS = {"debug", "info", "warning", "warn", "error", "critical", "exception", "log", "trace", "verbose", "fatal"}


@dataclass
class Site:
    file: str
    line: int
    function: str
    handler_line: int | None
    handler_type: str | None
    verdict: str
    uses: list[str] = field(default_factory=list)


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _is_headers_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (isinstance(func, ast.Name) and func.id == "internal_api_headers") or (isinstance(func, ast.Attribute) and func.attr == "internal_api_headers")


def _type_names(expr: ast.expr | None) -> list[str]:
    if expr is None:
        return ["<bare>"]
    if isinstance(expr, ast.Tuple):
        out: list[str] = []
        for elt in expr.elts:
            out.extend(_type_names(elt))
        return out
    return [ast.unparse(expr)]


def _catches(handler: ast.ExceptHandler) -> bool:
    names = _type_names(handler.type)
    return any(n == "<bare>" or n.split(".")[-1] in CATCHES_INVALID_HEADER for n in names)


def _inside(child: ast.AST, container: list[ast.stmt], parents: dict[ast.AST, ast.AST]) -> bool:
    node = child
    while node in parents:
        if node in container:
            return True
        node = parents[node]
    return node in container


def _enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST | None:
    while node in parents:
        node = parents[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return node
    return None


def _classify_handler(handler: ast.ExceptHandler, parents: dict[ast.AST, ast.AST]) -> tuple[str, list[str]]:
    uses: list[str] = []
    verdicts: set[str] = set()
    name = handler.name
    for stmt in handler.body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Raise):
                if node.exc is None or (isinstance(node.exc, ast.Name) and node.exc.id == name):
                    verdicts.add("RERAISE")
                    uses.append(f"{node.lineno}: raise")
            if isinstance(node, ast.Call):
                func = node.func
                attr = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")
                if attr == "exception" or any(k.arg == "exc_info" for k in node.keywords):
                    verdicts.add("TRACEBACK")
                    uses.append(f"{node.lineno}: {ast.unparse(node)[:140]}")
                if attr in {"format_exc", "print_exc", "format_exception", "print_exception"}:
                    verdicts.add("TRACEBACK")
                    uses.append(f"{node.lineno}: {ast.unparse(node)[:140]}")
            if name and isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load):
                parent = parents.get(node)
                # type(e) / type(e).__name__ carries no text.
                if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) and parent.func.id == "type":
                    verdicts.add("TYPE-ONLY")
                    uses.append(f"{node.lineno}: type({name})")
                    continue
                # Walk up to the statement to show what the text lands in.
                stmt_node: ast.AST = node
                while stmt_node in parents and not isinstance(stmt_node, ast.stmt):
                    stmt_node = parents[stmt_node]
                verdicts.add("TEXT")
                uses.append(f"{node.lineno}: {ast.unparse(stmt_node)[:160]}")
    if not verdicts:
        return "SILENT", uses
    for v in ("TEXT", "TRACEBACK", "RERAISE", "TYPE-ONLY"):
        if v in verdicts:
            return "+".join(sorted(verdicts, key=["TEXT", "TRACEBACK", "RERAISE", "TYPE-ONLY"].index)), uses
    return "SILENT", uses


def census(src: Path = SRC) -> list[Site]:
    sites: list[Site] = []
    for path in sorted(src.rglob("*.py")):
        rel = path.relative_to(src.parent)
        if "tests" in rel.parts or path.name == "internal_api.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = _parents(tree)
        for node in ast.walk(tree):
            if not _is_headers_call(node):
                continue
            func = _enclosing_function(node, parents)
            func_name = getattr(func, "name", "<lambda>") if func is not None else "<module>"
            found: Site | None = None
            cursor: ast.AST = node
            while cursor in parents:
                cursor = parents[cursor]
                if cursor is func:
                    break
                if isinstance(cursor, ast.Try) and _inside(node, cursor.body, parents):
                    for handler in cursor.handlers:
                        if _catches(handler):
                            verdict, uses = _classify_handler(handler, parents)
                            found = Site(str(rel), node.lineno, func_name, handler.lineno, ast.unparse(handler.type) if handler.type else "<bare>", verdict, uses)
                            break
                    if found:
                        break
            sites.append(found or Site(str(rel), node.lineno, func_name, None, None, "UNCAUGHT"))
    return sites


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    parser.add_argument("--src", type=Path, default=SRC, help="source root to scan (default: this repo's src/)")
    args = parser.parse_args()
    sites = census(args.src)
    if args.json:
        json.dump([asdict(s) for s in sites], sys.stdout, indent=2)
        print()
        return 0
    counts: dict[str, int] = {}
    for s in sites:
        counts[s.verdict] = counts.get(s.verdict, 0) + 1
        print(f"{s.file}:{s.line}  [{s.function}]  handler={s.handler_type}@{s.handler_line}  -> {s.verdict}")
        for use in s.uses:
            print(f"      {use}")
    print()
    print(f"{len(sites)} internal_api_headers() call sites; verdicts: {json.dumps(counts, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
