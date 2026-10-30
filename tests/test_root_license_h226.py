"""H226 -- pin the canonical GPL-3.0 header across ``root/``.

The row calls this "the single largest single-folder Apache-2.0 cluster in the
tree": 9 ``.py`` modules each carrying a docstring
``Licence: GPL-3.0 (GNU General Public License Version 3)`` line plus
``README.md:78`` declaring the same, contradicting the adopted H7 -> GPL-3.0
decision (same family as mnt H176 / opt H183 / packages H200 / proc H213 /
quantum H215+H223).

Drift-recon (session 213): premise **TRUE**, three details corrected --

* the spelling is ``License`` (American), not ``Licence`` -- the British form
  the row quotes does not appear anywhere under ``root/``;
* the offending phrase is the spelled-out ``Version 3`` suffix;
* the README declaration is on **line 74**, not 78.

Fix: all 9 modules and the README now carry
``License: GPL-3.0 (GNU General Public License v3)`` -- the same literal the
repo-wide ``CANON`` constant uses in ``tests/test_etc_license_headers.py``,
``tests/test_fs_baseline.py``, ``tests/test_feedback_license.py``,
``tests/test_media_license_h160.py`` and ``tests/test_quantum_sim_header_h223``.
Five of the modules had a trailing space after the parenthetical; that is gone
too, so the line is byte-identical everywhere.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "root"
README = ROOT / "README.md"

CANON = "License: GPL-3.0 (GNU General Public License v3)"
AUTHOR = "Author:  Umer OS Project"

#: The nine modules audited in session 213.  A tenth file is a conscious act.
EXPECTED_MODULES = [
    "__init__.py",
    "__main__.py",
    "dotfiles.py",
    "fhs.py",
    "home.py",
    "mail.py",
    "passwd.py",
    "safety.py",
    "shell.py",
]


def _modules() -> list[Path]:
    return sorted(
        p for p in ROOT.glob("*.py") if "__pycache__" not in p.parts
    )


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.fixture(params=EXPECTED_MODULES)
def module(request) -> Path:
    return ROOT / request.param


# ---------------------------------------------------------------------------
# The nine modules
# ---------------------------------------------------------------------------

class TestModuleHeaders:
    def test_module_set_is_pinned(self):
        found = [p.name for p in _modules()]
        assert found == EXPECTED_MODULES, (
            f"root/ module set changed: {found}"
        )

    def test_canonical_license_line(self, module):
        assert CANON in _src(module), f"{module.name} must carry the canonical line"

    def test_no_spelled_out_version_3(self, module):
        assert "Version 3" not in _src(module), (
            f"{module.name} still spells out 'Version 3'"
        )

    def test_no_british_spelling(self, module):
        assert "Licence:" not in _src(module), (
            f"{module.name} has the British 'Licence:' spelling"
        )

    def test_author_trailer_two_spaces(self, module):
        assert AUTHOR in _src(module), (
            f"{module.name} must carry 'Author:  Umer OS Project' (two spaces)"
        )

    def test_gpl_comment_header_block(self, module):
        src = _src(module)
        assert "GNU General Public License" in src
        assert "https://www.gnu.org/licenses/" in src

    def test_exactly_one_license_line(self, module):
        """A second stray header is exactly the H7 defect being fixed."""
        count = _src(module).count("License: GPL-3.0")
        assert count == 1, f"{module.name}: expected 1 License line, found {count}"

    def test_no_trailing_whitespace_on_license_line(self, module):
        for line in _src(module).splitlines():
            if line.startswith("License: GPL-3.0"):
                assert line == line.rstrip(), (
                    f"{module.name}: trailing whitespace on the License line"
                )
                assert line == CANON, f"{module.name}: unexpected License line {line!r}"

    def test_compiles(self, module):
        ast.parse(_src(module))


# ---------------------------------------------------------------------------
# Section 1 per-file baseline (the header work must not break the rest)
# ---------------------------------------------------------------------------

class TestSectionOneBaseline:
    def test_has_module_docstring(self, module):
        assert ast.get_docstring(ast.parse(_src(module))) is not None

    def test_future_annotations_first_after_docstring(self, module):
        tree = ast.parse(_src(module))
        body = tree.body
        assert isinstance(body[0], ast.Expr) and isinstance(
            body[0].value, ast.Constant
        ), f"{module.name} must start with a module docstring"
        assert len(body) > 1, f"{module.name} has no statements after the docstring"
        first = body[1]
        assert isinstance(first, ast.ImportFrom) and first.module == "__future__", (
            f"{module.name}: 'from __future__ import annotations' must be the "
            "first statement after the docstring"
        )
        assert [a.name for a in first.names] == ["annotations"]

    def test_prints_are_confined_to_selftest_and_main(self, module):
        """Library surface must not print; ``__main__`` blocks may."""
        if module.name == "__main__.py":
            # The CLI entry point *is* the output contract -- its `_cmd_*`
            # handlers and `main()` print by design.
            pytest.skip("__main__.py is the CLI surface")
        tree = ast.parse(_src(module))
        for func in tree.body:
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if func.name == "_selftest":
                continue
            for node in ast.walk(func):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "print"
                ):
                    pytest.fail(
                        f"{module.name}:{node.lineno} prints inside {func.name}()"
                    )


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------

class TestReadme:
    def test_exists(self):
        assert README.is_file()

    def test_canonical_license_declaration(self):
        src = _src(README)
        assert CANON in src, "README must declare the canonical license"
        assert "Version 3" not in src, "README still spells out 'Version 3'"
        assert "Licence:" not in src

    def test_license_section_line(self):
        """The declaration lives under '## License' and reads naturally."""
        lines = _src(README).splitlines()
        hits = [ln for ln in lines if ln.startswith("License: GPL-3.0")]
        assert len(hits) == 1, f"expected one declaration, found {hits}"
        assert hits[0] == (
            "License: GPL-3.0 (GNU General Public License v3) - "
            "same as the rest of Umer OS."
        )
        assert "## License" in lines, "README must keep its '## License' heading"

    def test_no_leftover_version_3_anywhere_under_root(self):
        offenders = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix not in (".py", ".md"):
                continue
            if "__pycache__" in path.parts:
                continue
            if "Version 3" in _src(path):
                offenders.append(path.name)
        assert not offenders, f"'Version 3' still present in {offenders}"
