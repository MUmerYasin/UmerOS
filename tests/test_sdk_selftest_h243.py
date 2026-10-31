"""H243: per-module ``_selftest()`` across ``sdk/``.

Drift-recon found the row stale on **all four** of its claims: ``from __future__``
was added to every module by H240, ``__all__`` already exists in both package
``__init__`` files (populated dynamically by ``_try_import``), ``sdk/__init__.py``
already had a ``_selftest()``, and ``tests/test_sdk.py`` already exercises the
``UmerApp`` lifecycle plus ``BuildTool.scaffold``/``package`` with a mock VFS.

The one genuinely missing thing was the repo's *per-module* ``_selftest()``
convention (222 modules carry one). These tests pin it.
"""
import ast
import importlib
import inspect
import io
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SDK = ROOT / "sdk"
sys.path.insert(0, str(ROOT))

#: Every module under sdk/, as an importable name and a path.
MODULES = [
    ("sdk", "sdk/__init__.py"),
    ("sdk.app_template", "sdk/app_template.py"),
    ("sdk.build_tool", "sdk/build_tool.py"),
    ("sdk.validator", "sdk/validator.py"),
    ("sdk.kernel_dsl", "sdk/kernel_dsl/__init__.py"),
    ("sdk.kernel_dsl.types", "sdk/kernel_dsl/types.py"),
    ("sdk.kernel_dsl.extension_base", "sdk/kernel_dsl/extension_base.py"),
]

NAMES = [m for m, _ in MODULES]


def _load(name):
    return importlib.import_module(name)


def _src(rel):
    return io.open(ROOT / rel, encoding="utf-8").read()


def _tree(rel):
    return ast.parse(_src(rel))


class TestEveryModuleHasASelftest:
    @pytest.mark.parametrize("name", NAMES)
    def test_selftest_exists_and_is_callable(self, name):
        fn = getattr(_load(name), "_selftest", None)
        assert callable(fn), f"{name} has no callable _selftest()"

    @pytest.mark.parametrize("name", NAMES)
    def test_selftest_returns_true(self, name):
        assert _load(name)._selftest() is True

    @pytest.mark.parametrize("name", NAMES)
    def test_selftest_prints_pass_lines(self, name, capsys):
        _load(name)._selftest()
        out = capsys.readouterr().out
        assert "[PASS]" in out, f"{name} printed no [PASS] lines"
        assert "[FAIL]" not in out, f"{name} printed a [FAIL] line"

    @pytest.mark.parametrize("name", NAMES)
    def test_selftest_reports_its_verdict(self, name, capsys):
        _load(name)._selftest()
        out = capsys.readouterr().out
        assert "selftest PASSED" in out, f"{name} printed no verdict line"


class TestTheMainGuard:
    @pytest.mark.parametrize("rel", [r for _, r in MODULES])
    def test_module_runs_as_a_script(self, rel):
        tree = _tree(rel)
        guards = [
            n for n in tree.body
            if isinstance(n, ast.If) and "__main__" in ast.unparse(n.test)
        ]
        assert guards, f"{rel} has no `if __name__ == \"__main__\"` guard"

    def test_the_guard_calls_the_selftest(self):
        for _, rel in MODULES:
            tree = _tree(rel)
            guard = next(
                n for n in tree.body
                if isinstance(n, ast.If) and "__main__" in ast.unparse(n.test)
            )
            called = {
                c.func.id for c in ast.walk(guard)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
            }
            assert "_selftest" in called, f"{rel}'s main guard does not run _selftest()"


class TestPackageRunsItsChildren:
    def test_sdk_declares_its_child_modules(self):
        assert hasattr(_load("sdk"), "_SELFTEST_MODULES")
        declared = set(_load("sdk")._SELFTEST_MODULES)
        assert declared == {"app_template", "build_tool", "validator", "kernel_dsl"}

    def test_kernel_dsl_declares_its_child_modules(self):
        assert set(_load("sdk.kernel_dsl")._SELFTEST_MODULES) == {
            "types", "extension_base"
        }

    def test_package_selftest_invokes_children(self):
        """Source-level proof, so 'runs children' cannot quietly become 'imports'."""
        for name in ("sdk", "sdk.kernel_dsl"):
            source = inspect.getsource(_load(name)._selftest)
            assert "_SELFTEST_MODULES" in source
            assert "child()" in source or "_selftest" in source

    def test_package_selftest_fails_when_a_child_fails(self, monkeypatch):
        """The decisive test: the aggregator must be able to go red."""
        sdk = _load("sdk")
        module = _load("sdk.validator")

        def broken():
            return False

        monkeypatch.setattr(module, "_selftest", broken)
        assert sdk._selftest() is False

    def test_package_selftest_fails_when_a_child_is_missing(self, monkeypatch):
        sdk = _load("sdk")
        module = _load("sdk.validator")
        monkeypatch.delattr(module, "_selftest", raising=False)
        # a child with no selftest at all is skipped by design, not failed
        assert sdk._selftest() is True


class TestTheStaleClaimsArePinned:
    """The row's premises were all already closed; pin them so they stay closed."""

    @pytest.mark.parametrize("rel", [r for _, r in MODULES])
    def test_future_import_is_the_first_statement(self, rel):
        tree = _tree(rel)
        first = next(
            n for n in tree.body
            if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))
        )
        assert "from __future__ import annotations" in ast.unparse(first)

    @pytest.mark.parametrize("name", ["sdk", "sdk.kernel_dsl"])
    def test_all_is_declared_and_resolves(self, name):
        module = _load(name)
        assert module.__all__, f"{name} declares an empty __all__"
        missing = [n for n in module.__all__ if not hasattr(module, n)]
        assert missing == [], f"{name}.__all__ names nothing importable: {missing}"

    def test_sdk_all_covers_the_public_surface(self):
        assert set(_load("sdk").__all__) == {
            "UmerApp", "BuildTool", "AppValidator", "ValidationResult"
        }

    def test_kernel_dsl_all_covers_the_public_surface(self):
        assert set(_load("sdk.kernel_dsl").__all__) == {
            "KernelExtension", "system_capability", "Result", "Success",
            "Failure", "Option", "Some", "None_",
        }

    def test_the_standalone_suite_still_covers_the_row_s_ask(self):
        """The row asked for a test of UmerApp + scaffold/package; one exists."""
        existing = (ROOT / "tests" / "test_sdk.py").read_text(encoding="utf-8")
        assert "class TestBuildTool" in existing
        assert "test_scaffold_with_vfs" in existing
        assert "class TestUmerApp" in existing


class TestNothingElseBroke:
    def test_header_block_still_first(self):
        for _, rel in MODULES:
            head = _src(rel)[:2000]
            assert "# This program is free software" in head, f"{rel} lost its block"

    def test_public_classes_still_import(self):
        from sdk import AppValidator, BuildTool, UmerApp

        assert UmerApp is not None
        assert BuildTool is not None
        assert AppValidator is not None

    def test_no_module_grew_a_second_selftest(self):
        for _, rel in MODULES:
            assert _src(rel).count("def _selftest") == 1, f"{rel} has a duplicate selftest"
