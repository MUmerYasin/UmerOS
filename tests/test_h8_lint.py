# UmerOS — H8 lint gate
#
# AST-based check that every broad ``except Exception`` / bare ``except:``
# handler inside ``bin/*.py`` is either:
#   (a) nested inside a ``_selftest()`` function, OR
#   (b) explicitly tagged with a ``# [FIX H8]`` comment on the ``except`` line, OR
#   (c) non-silent — the handler logs the error (``log.exception`` /
#       ``traceback.print_exc`` / ``logger.error`` ...).
#
# Operational code must use narrower exception types (see H8 remediation).
# Self-test / import boundaries are allowed to stay broad because they are
# non-silent (they print the traceback and return a failure sentinel).
#
# Uses stdlib ``unittest`` (the project's test runner). Run with:
#     python -m unittest tests.test_h8_lint -v
from __future__ import annotations

import ast
import pathlib
import unittest

BIN_DIR = pathlib.Path(__file__).resolve().parent.parent / "bin"

# Exception types considered "broad" for H8 purposes.
_BROAD_TYPES = ("Exception", "BaseException")
# Attribute names that indicate the handler is logging (non-silent).
_LOGGING_ATTRS = {"exception", "error", "warning", "print_exc", "print_exception"}


def _inside_selftest(stack: list[ast.AST]) -> bool:
    """True when *node* is nested inside a ``_selftest`` function."""
    return any(
        isinstance(a, ast.FunctionDef) and a.name == "_selftest" for a in stack
    )


def _is_broad_except(node: ast.AST) -> bool:
    if not isinstance(node, ast.ExceptHandler):
        return False
    if node.type is None:  # bare ``except:``
        return True
    return isinstance(node.type, ast.Name) and node.type.id in _BROAD_TYPES


def _is_tagged(source_lines: list[str], node: ast.ExceptHandler) -> bool:
    """True when the ``except`` line carries a ``# [FIX H8]`` marker."""
    if node.lineno is None or node.lineno - 1 >= len(source_lines):
        return False
    return "# [FIX H8]" in source_lines[node.lineno - 1]


def _is_nonsilent(body: list[ast.stmt]) -> bool:
    """True when the handler logs the error (non-silent)."""
    for child in ast.walk(ast.Module(body=list(body))):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            if child.func.attr in _LOGGING_ATTRS:
                return True
    return False


def _find_violations(filepath: pathlib.Path) -> list[dict]:
    source = filepath.read_text(encoding="utf-8", errors="replace")
    source_lines = source.splitlines()
    tree = ast.parse(source, filename=str(filepath))
    violations: list[dict] = []

    def _visit(node: ast.AST, stack: list[ast.AST]) -> None:
        new_stack = stack + [node]
        if _is_broad_except(node):
            if _inside_selftest(new_stack):
                pass  # self-test boundary: allowed to stay broad
            elif _is_tagged(source_lines, node):
                pass  # explicitly reviewed + tagged
            elif _is_nonsilent(node.body):
                pass  # non-silent broad catch is acceptable
            else:
                violations.append(
                    {"file": str(filepath), "line": node.lineno}
                )
        for child in ast.iter_child_nodes(node):
            _visit(child, new_stack)

    _visit(tree, [])
    return violations


class TestH8Lint(unittest.TestCase):
    def test_no_broad_except_outside_selftest(self) -> None:
        """Operational ``bin/*`` code must not swallow broad exceptions silently."""
        violations: list[dict] = []
        for py_file in sorted(BIN_DIR.glob("*.py")):
            violations.extend(_find_violations(py_file))

        if violations:
            lines = [
                "H8 lint violations — silent broad ``except`` outside _selftest():\n"
            ]
            for v in violations:
                rel = (
                    v["file"]
                    .replace(str(BIN_DIR.parent) + "\\", "")
                    .replace("\\", "/")
                )
                lines.append(f"  {rel}:{v['line']}")
            lines.append(
                "\nFix: narrow the exception type (e.g. ``except (OSError, ValueError):``),"
                " add ``# [FIX H8]`` + ``log.exception(...)`` if it must stay broad,"
                " or move it inside ``_selftest()``."
            )
            self.fail("\n".join(lines))


if __name__ == "__main__":
    unittest.main()
