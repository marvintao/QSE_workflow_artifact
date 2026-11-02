# Copyright (c) 2026 QJump.ai
# SPDX-License-Identifier: MIT

"""Static safety check for generated code.

Walks the AST of stage-4-generated code and blocks non-whitelisted
top-level imports and dangerous builtins. This is a static gate
ahead of sandbox execution; the rlimit sandbox remains the last line
of defense.
"""
import ast

# Allow-list of top-level modules for import: required quantum libs +
# a safe subset of the standard library.
# `os` is allowed conditionally: codegen output needs os.environ to
# read SUB_INSTANCE_JSON, but os.system / os.popen / os.exec* /
# os.spawn* are still blocked via _FORBIDDEN_CALLS.
_ALLOWED_IMPORTS = frozenset({
    "qiskit", "qiskit_aer",
    "numpy", "scipy",
    "json", "math", "fractions", "itertools", "collections", "cmath",
    "os",
})

# Forbidden builtin call names (matched whether they appear as Name or Attribute).
# os.system / popen / exec* / spawn* are blocked by attribute name —
# even though `os` itself is allowed to import.
_FORBIDDEN_CALLS = frozenset({
    "eval", "exec", "compile", "__import__", "open", "input",
    "system", "popen",
    "execv", "execve", "execvp", "execvpe",
    "execl", "execle", "execlp", "execlpe",
    "spawnv", "spawnve", "spawnvp", "spawnvpe",
    "spawnl", "spawnle", "spawnlp", "spawnlpe",
})


def _line_context(code: str, lineno: int, context: int = 3) -> str:
    """Return ±context lines around the 1-based lineno as a string with line-number prefix, helping the agent locate syntax/indentation/structural issues."""
    lines = code.splitlines()
    start = max(1, lineno - context)
    end = min(len(lines), lineno + context)
    out = []
    for i in range(start, end + 1):
        marker = "→" if i == lineno else " "
        out.append(f"{marker} L{i:>3} | {lines[i - 1]}")
    return "\n".join(out)


class UnsafeCodeError(Exception):
    """Generated code contains a forbidden import or dangerous call, or cannot be parsed."""


def check_code_safety(code: str,
                      extra_allowed_imports: set[str] | None = None) -> None:
    """Run an AST-based static safety check on the code; raise UnsafeCodeError on any issue.

    Args:
        code: Python source code to check.
        extra_allowed_imports: Additional top-level module names to
            allow (e.g. building-block module names injected by the
            knowledge package).
    """
    allowed = _ALLOWED_IMPORTS | (extra_allowed_imports or set())
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        # Show the agent ±3 lines of context (with line numbers) so it
        # can spot structural issues instead of editing only the
        # exact reported line.
        ctx = _line_context(code, exc.lineno or 0)
        raise UnsafeCodeError(
            f"code cannot be parsed as valid Python: {exc}\n"
            f"context (line {exc.lineno} ±3):\n{ctx}"
        ) from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in allowed:
                    raise UnsafeCodeError(f"forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if top not in allowed:
                raise UnsafeCodeError(
                    f"forbidden import: from {node.module}")
        elif isinstance(node, ast.Call):
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in _FORBIDDEN_CALLS:
                raise UnsafeCodeError(f"forbidden call: {name}")
