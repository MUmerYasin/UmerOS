"""H240: every module under ``sdk/`` carries the canonical GPL-3.0 header.

The row claimed "all 3 .py modules" had "ZERO GPL strings".  The folder
actually holds 7 modules across two packages, and four of them already
carried the block.  These tests pin the *substance* so the count can't
silently drift back, and pin the recursive sweep so a new subpackage
(``kernel_dsl`` was added after the survey) can't slip in headerless.
"""
import ast
import io
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SDK = ROOT / "sdk"

sys.path.insert(0, str(ROOT))
from legal.licenses import LicenseManager  # noqa: E402

BLOCK = LicenseManager.GPL_HEADER_TEMPLATE
AUTHOR = "Author:  Umer OS Project"
CANON = "License: GPL-3.0 (GNU General Public License v3)"
FUTURE = "from __future__ import annotations"

# The survey said 3; the live tree has 7.  Pinned deliberately.
MODULES = [
    "sdk/__init__.py",
    "sdk/app_template.py",
    "sdk/build_tool.py",
    "sdk/validator.py",
    "sdk/kernel_dsl/__init__.py",
    "sdk/kernel_dsl/extension_base.py",
    "sdk/kernel_dsl/types.py",
]

# Line-ending convention is per-file and pre-existing; don't normalise it.
CRLF_MODULES = {"sdk/__init__.py", "sdk/app_template.py", "sdk/build_tool.py"}


def _raw(rel):
    return io.open(ROOT / rel, encoding="utf-8", newline="").read()


def _src(rel):
    return io.open(ROOT / rel, encoding="utf-8").read()


def _nl(text):
    return "\r\n" if "\r\n" in text else "\n"


def _doc(rel):
    return ast.get_docstring(ast.parse(_src(rel)), clean=False)


def _first_statement(rel):
    tree = ast.parse(_src(rel))
    for node in tree.body:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        return node
    return None


@pytest.fixture(params=MODULES)
def module(request):
    return request.param


class TestModuleSet:
    def test_every_sdk_module_is_pinned(self):
        """A new module must be added here *and* given a header."""
        on_disk = {
            str(p.relative_to(ROOT)).replace("\\", "/")
            for p in SDK.rglob("*.py")
        }
        assert on_disk == set(MODULES), (
            f"unpinned sdk modules: {sorted(on_disk - set(MODULES))}; "
            f"stale pins: {sorted(set(MODULES) - on_disk)}"
        )

    def test_the_subpackage_is_covered(self):
        """The decisive drift: the gap was in ``kernel_dsl/``, not the top level."""
        subpackage = [m for m in MODULES if "/kernel_dsl/" in m]
        assert len(subpackage) == 3, "the kernel_dsl subpackage must stay covered"


class TestCanonicalBlock:
    def test_block_is_present_byte_for_byte(self, module):
        text = _raw(module)
        expected = BLOCK.replace("\n", _nl(text))
        assert expected in text, f"{module} is missing the canonical GPL-3.0 block"

    def test_block_starts_at_the_top(self, module):
        """Line 1 for every module -- no prose banner above it."""
        lines = _raw(module).split(_nl(_raw(module)))
        assert lines[0] == "# This program is free software: you can redistribute it and/or modify", (
            f"{module} does not start with the licence block"
        )

    def test_block_is_complete_not_truncated(self, module):
        """``validator.py`` carried a 4-line stub; a partial block is not a header."""
        text = _raw(module)
        nl = _nl(text)
        for line in BLOCK.rstrip("\n").split("\n"):
            assert line + nl in text or line == text.split(nl)[-1], (
                f"{module} is missing block line: {line!r}"
            )


class TestSectionOneBaseline:
    def test_docstring_exists(self, module):
        assert _doc(module) is not None, f"{module} has no module docstring"

    def test_author_trailer_uses_two_spaces(self, module):
        doc = _doc(module)
        assert AUTHOR in doc, f"{module} must carry the two-space Author trailer"
        # the single-space form is the retired spelling, not the convention
        assert "Author: UmerOS Project" not in doc, (
            f"{module} uses the retired single-space 'UmerOS Project' spelling"
        )

    def test_canonical_license_line(self, module):
        doc = _doc(module)
        assert CANON in doc, f"{module} must carry the canonical License line"
        assert "Version 3)" not in doc, (
            f"{module} spells out 'Version 3'; the canonical form is 'v3'"
        )

    def test_trailer_is_the_last_thing_in_the_docstring(self, module):
        tail = [l for l in _doc(module).rstrip().splitlines() if l.strip()][-2:]
        assert tail == [AUTHOR, CANON], f"{module} docstring tail is {tail}"

    def test_future_import_is_the_first_statement(self, module):
        first = _first_statement(module)
        assert first is not None, f"{module} has no statements"
        assert FUTURE in ast.unparse(first), (
            f"{module}'s first statement is {ast.unparse(first)[:60]!r}, not the __future__ import"
        )

    def test_future_import_is_the_real_import_not_a_string(self, module):
        tree = ast.parse(_src(module))
        imports = [
            n for n in tree.body
            if isinstance(n, ast.ImportFrom) and n.module == "__future__"
        ]
        assert len(imports) == 1, f"{module} has {len(imports)} __future__ imports"
        assert [a.name for a in imports[0].names] == ["annotations"]


class TestRetiredFormsAreGone:
    def test_no_single_space_author_anywhere(self, module):
        assert "Author: UmerOS Project" not in _src(module)

    def test_no_spelled_out_version(self, module):
        assert "GNU General Public License Version 3" not in _src(module)

    def test_exactly_one_license_declaration(self, module):
        """A banner plus a docstring trailer would be two sources of truth."""
        src = _src(module)
        assert src.count("License: GPL-3.0") == 1, (
            f"{module} declares the licence {src.count('License: GPL-3.0')} times"
        )


class TestLineEndingsPreserved:
    def test_crlf_modules_stay_crlf(self, module):
        if module not in CRLF_MODULES:
            pytest.skip(f"{module} is an LF file")
        raw = io.open(ROOT / module, "rb").read()
        assert raw.count(b"\r\n") == raw.count(b"\n"), (
            f"{module} has mixed line endings"
        )

    def test_lf_modules_have_no_crlf(self, module):
        if module in CRLF_MODULES:
            pytest.skip(f"{module} is a CRLF file")
        raw = io.open(ROOT / module, "rb").read()
        assert raw.count(b"\r\n") == 0, f"{module} picked up CRLF"


class TestRepoAudit:
    def test_scanner_reports_full_compliance(self):
        """The repo's own fail-closed audit is the authority, not a grep."""
        result = LicenseManager().scan_directory("sdk")
        assert result.total_files_scanned == len(MODULES)
        assert result.compliant_files == len(MODULES)
        assert result.missing_license_files == []
        assert result.is_fully_compliant is True

    def test_folder_sweep_finds_no_headerless_module(self):
        offenders = []
        for path in sorted(SDK.rglob("*.py")):
            head = io.open(path, encoding="utf-8").read()[:2000]
            if BLOCK.split("\n")[0] not in head:
                offenders.append(str(path.relative_to(ROOT)))
        assert offenders == [], f"headerless sdk modules: {offenders}"


class TestStillWorks:
    def test_sdk_imports(self):
        import sdk

        assert sdk.__version__ == "1.0.0"

    def test_kernel_dsl_surface(self):
        from sdk.kernel_dsl import Failure, None_, Success

        assert Success(1).unwrap() == 1
        assert Failure("e").is_failure() is True
        assert None_().is_none() is True

    def test_public_classes_import(self):
        from sdk.app_template import UmerApp
        from sdk.validator import AppValidator

        assert UmerApp is not None
        assert AppValidator is not None
