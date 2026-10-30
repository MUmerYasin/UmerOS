"""H223 -- pin the canonical GPL-3.0 header on ``quantum/quantum_sim.py``.

The row claimed a second stray ``Licence: GPL-3.0 (GNU General Public License
Version 3)`` docstring inside ``quantum/`` (same family as H215), and was
already marked resolved in session 102.

Drift-recon (session 210) found the stray is **gone** — line 20 is the
``TODAY:`` section label, not a header — but session 102's fix landed on a
**non-canonical short form**: ``License: GPL-3.0`` with no parenthetical.  The
repo-wide canonical form (pinned by ``tests/test_etc_license_headers.py``,
``tests/test_fs_baseline.py``, ``tests/test_feedback_license.py``) is
``License: GPL-3.0 (GNU General Public License v3)``, so this file was the
outlier among the quantum modules that already carry a trailer
(``cli.py``, ``qkd.py``, ``qrng.py``, ``cloud/auth.py``,
``liboqs_integration.py``).

Note: ``quantum/crypto_pqc.py`` deliberately keeps the short form — its own
test (``tests/test_quantum_security.py::TestCryptoPqcHeader``) pins
``"License: GPL-3.0\\n"`` — so this test does not touch it.
"""

from __future__ import annotations

import ast
from pathlib import Path

QUANTUM = Path(__file__).resolve().parent.parent / "quantum"
SIM_PATH = QUANTUM / "quantum_sim.py"

CANON = "License: GPL-3.0 (GNU General Public License v3)"
AUTHOR = "Author:  Umer OS Project"


def _src() -> str:
    return SIM_PATH.read_text(encoding="utf-8")


class TestCanonicalHeader:
    """The file must carry the repo-wide canonical header."""

    def test_canonical_license_line(self) -> None:
        assert CANON in _src(), (
            "quantum_sim.py must carry the canonical "
            f"'{CANON}' line"
        )

    def test_no_bare_short_form(self) -> None:
        """The session-102 short form must be upgraded, not left behind."""
        assert "License: GPL-3.0\n" not in _src(), (
            "bare 'License: GPL-3.0' (no parenthetical) still present"
        )

    def test_no_version_3_suffix(self) -> None:
        assert "GNU General Public License Version 3" not in _src(), (
            "spelled-out 'Version 3' form must not appear"
        )

    def test_no_british_spelling(self) -> None:
        assert "Licence:" not in _src(), "British 'Licence:' spelling present"

    def test_author_trailer(self) -> None:
        assert AUTHOR in _src(), "Author trailer (two spaces) missing"

    def test_gpl_comment_header_block(self) -> None:
        src = _src()
        assert "GNU General Public License" in src
        assert "https://www.gnu.org/licenses/" in src


class TestNoStrayDuplicateHeader:
    """There must be exactly one header, not a second stray one."""

    def test_single_license_line(self) -> None:
        count = _src().count("License: GPL-3.0")
        assert count == 1, f"expected exactly 1 License line, found {count}"

    def test_single_author_line(self) -> None:
        count = _src().count("Author:")
        assert count == 1, f"expected exactly 1 Author line, found {count}"

    def test_line_20_is_not_a_header(self) -> None:
        """The row pointed at :20; that line is the TODAY section label."""
        lines = _src().splitlines()
        assert len(lines) >= 20
        line20 = lines[19]
        assert "License" not in line20 and "Licence" not in line20, (
            f"line 20 unexpectedly looks like a header: {line20!r}"
        )

    def test_single_module_docstring(self) -> None:
        tree = ast.parse(_src())
        doc_nodes = [
            n
            for n in tree.body
            if isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
        ]
        assert len(doc_nodes) == 1, (
            f"expected 1 module docstring, found {len(doc_nodes)}"
        )


class TestFileBaseline:
    """Section 1 structural baseline."""

    def test_compiles(self) -> None:
        ast.parse(_src())

    def test_future_annotations_first(self) -> None:
        tree = ast.parse(_src())
        body = tree.body
        start = 1 if (
            isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ) else 0
        stmt = body[start]
        assert isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__"
        assert any(a.name == "annotations" for a in stmt.names)

    def test_module_imports(self) -> None:
        import sys

        root = str(QUANTUM.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        from quantum import quantum_sim

        assert hasattr(quantum_sim, "QuantumCircuitSimulator")
        assert hasattr(quantum_sim, "log")


class TestPackageConsistency:
    """Modules that already carry a trailer must stay canonical."""

    def test_other_quantum_modules_canonical(self) -> None:
        for name in ("cli.py", "qkd.py", "qrng.py", "liboqs_integration.py"):
            path = QUANTUM / name
            if not path.exists():
                continue
            assert CANON in path.read_text(encoding="utf-8"), (
                f"quantum/{name} lost the canonical license line"
            )

    def test_auth_module_canonical(self) -> None:
        auth = QUANTUM / "cloud" / "auth.py"
        if auth.exists():
            assert CANON in auth.read_text(encoding="utf-8")

    def test_crypto_pqc_keeps_its_pinned_form(self) -> None:
        """crypto_pqc.py is pinned to the short form by its own test (H215)."""
        pqc = QUANTUM / "crypto_pqc.py"
        if not pqc.exists():
            return
        src = pqc.read_text(encoding="utf-8")
        assert "License: GPL-3.0\n" in src, (
            "crypto_pqc.py's pinned short form changed unexpectedly"
        )
