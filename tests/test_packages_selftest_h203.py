# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
H203 - the row asks for ``_selftest()`` in ``packages/repository.py`` and
``packages/umer_pkg.py``, and for ``repository.py``'s
``print("[REPO] …")`` in ``__init__`` to become ``log.info``
(cf. opt H192).

Drift-recon first (per the standard):

* the print had drifted to line 51 (H200's licence header + H202's
  future-import shifted it from the row's ``:33``), and the row
  *understated* the gap - ``repository.py`` carried no ``import
  logging`` and no module logger at all, so both were added with the
  fix (the logger follows ``umer_pkg.py``'s ``UmerOS.*`` naming).
* ``repository.py`` is a pure simulated catalog (no install / verify /
  remove), so its selftest exercises the catalog surface; the
  install/verify/remove selftest lands in ``umer_pkg.py``, whose
  library surface was already print-free (``main()``'s prints are the
  CLI contract and stay).

These tests pin: both modules keep a passing ``_selftest()`` covering
their surface (signed build -> verify -> install -> remove, unsigned
refusal, capability gating; catalog search/get/list_all), the selftests
are re-runnable (fresh temp root per call), ``repository.py`` stays
print-free outside its selftest banner and logs through a module
logger, ``umer_pkg.py``'s library surface stays print-free, and
``umer_pkg``'s ``__main__`` runs the selftest before the CLI.
"""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MODULES = ("packages.repository", "packages.umer_pkg")

# Surface each selftest must exercise - the [PASS] line text is the
# contract, so a selftest that silently drops a case fails here.
SECURITY_LINES = {
    "packages.repository": (
        "catalog is non-empty with unique names",
        "search matches by name",
        "search matches by description",
        "get returns the entry, None for unknown",
        "PackageInfo repr",
    ),
    "packages.umer_pkg": (
        "signed build verifies against the pinned key",
        "install lands the payload inside the install dir",
        "remove clears the package and the DB entry",
        "unsigned package is refused fail-closed",
        "install / remove are capability-gated",
    ),
}


def _load(name: str):
    return importlib.import_module(name)


def _print_calls(path: Path, allowed_functions: set) -> list:
    """Return linenos of print() calls NOT inside *allowed_functions*."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    inside = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in allowed_functions:
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Call)
                            and isinstance(sub.func, ast.Name)
                            and sub.func.id == "print"):
                        inside.add(sub.lineno)
    outside = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
                and node.lineno not in inside):
            outside.append(node.lineno)
    return outside


@pytest.mark.parametrize("name", MODULES)
def test_module_defines_a_selftest(name: str):
    module = _load(name)
    selftest = getattr(module, "_selftest", None)
    assert callable(selftest), f"{name} has no callable _selftest()"


@pytest.mark.parametrize("name", MODULES)
def test_selftest_passes_and_covers_the_surface(name: str, capsys):
    module = _load(name)
    result = module._selftest()
    captured = capsys.readouterr().out
    assert result is True, f"{name}._selftest() returned {result!r}"
    assert "[PASS]" in captured, f"{name} selftest printed no [PASS] lines"
    for expected in SECURITY_LINES[name]:
        assert expected in captured, (
            f"{name} selftest no longer covers its surface "
            f"({expected!r} not in output)"
        )


@pytest.mark.parametrize("name", MODULES)
def test_selftest_is_re_runnable(name: str):
    # Each call must build its own throwaway temp root, so running the
    # selftest twice (``python -m`` plus a test run) stays green.
    module = _load(name)
    assert module._selftest() is True
    assert module._selftest() is True


def test_repository_logs_instead_of_printing():
    # The selftest banner is the only legitimate printer in the module.
    path = REPO_ROOT / "packages" / "repository.py"
    assert _print_calls(path, {"_selftest"}) == [], (
        "repository.py is a library module: print() outside _selftest()"
    )
    module = _load("packages.repository")
    assert hasattr(module, "log"), "repository.py exposes no module logger"
    assert module.log.name.startswith("UmerOS")


def test_umer_pkg_library_surface_is_print_free():
    # The CLI (main + its nested emit) and the selftest banner are the
    # only legitimate printers; the library surface must log instead.
    path = REPO_ROOT / "packages" / "umer_pkg.py"
    assert _print_calls(path, {"main", "emit", "_selftest"}) == [], (
        "umer_pkg.py library surface must log, not print"
    )


def test_umer_pkg_main_runs_the_selftest_first():
    source = (REPO_ROOT / "packages" / "umer_pkg.py").read_text(encoding="utf-8")
    marker = 'if __name__ == "__main__":'
    assert marker in source
    block = source.split(marker, 1)[1]
    assert "_selftest()" in block, (
        "umer_pkg __main__ no longer runs the selftest before main()"
    )
    assert block.index("_selftest()") < block.index("main()"), (
        "umer_pkg __main__ must run the selftest BEFORE the CLI"
    )


def test_repository_main_runs_the_selftest():
    source = (REPO_ROOT / "packages" / "repository.py").read_text(encoding="utf-8")
    marker = 'if __name__ == "__main__":'
    assert marker in source
    assert "_selftest()" in source.split(marker, 1)[1], (
        "repository.py __main__ no longer runs the selftest"
    )
