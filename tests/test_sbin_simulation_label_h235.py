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

"""H235 -- label the simulated ``/sbin`` commands so nothing reads as authoritative.

The row says the commands "masquerade as functional privileged tools
(``halt``/``mount -a``/``shutdown`` print + return 0 but do nothing) -- risk of
false state/deception if treated as authoritative", and the remedy is to
"clearly label simulated commands".

Drift-recon (session 221): premise **true**.  ``halt`` printed
``[*] halt: System halted`` to stderr and returned 0 -- a flat claim that the
machine had halted, with no marker distinguishing it from a real one, and
``SbinManager`` had no way to answer "is this command real?" programmatically.
``mktemp`` was the one exception in the folder: it genuinely calls
``tempfile.mkstemp``/``mkdtemp``.

Fix, in three layers so neither a human nor a caller can be misled:

1. **Output** -- all **61** ``[*]`` claim lines across the six command modules now
   read ``[simulated]``.  Uniform, so it is obvious at a glance and cannot be
   forgotten on a new command that copies an old line.
2. **Audit trail** -- every ``AUDIT START`` record carries ``simulated=True``
   (or ``False`` for a real command), so the log itself is authoritative.
3. **API** -- ``SbinManager.is_simulated()`` / ``list_simulated()`` /
   ``list_real()``, and ``check_compliance()`` reports the split.  A default of
   ``True`` means an un-annotated command is assumed fake, which is the safe
   direction.
"""

from __future__ import annotations

import ast
import logging
import os
import re
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
if str(PROJ) not in sys.path:
    sys.path.insert(0, str(PROJ))

import sbin.command_guard as guard_mod  # noqa: E402
from sbin.sbin_manager import SBIN_COMMAND_REGISTRY, SbinManager  # noqa: E402

SBIN = PROJ / "sbin"

COMMAND_MODULES = [
    "boot.py",
    "filesystem.py",
    "maintenance.py",
    "modules.py",
    "mount.py",
    "system.py",
]

#: The number of claim lines at the time of the fix.  A new one must be labelled.
EXPECTED_CLAIM_LINES = 61

AUDIT_LOGGER = "UmerOS.Sbin.Audit"

_OLD_PREFIX = re.compile(r'\[\*\]')


def _src(name: str) -> str:
    return (SBIN / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Layer 1: the output label
# ---------------------------------------------------------------------------

class TestOutputLabel:
    def test_no_bare_star_prefix_remains(self):
        """`[*]` said nothing about being simulated."""
        offenders = []
        for name in COMMAND_MODULES:
            for i, line in enumerate(_src(name).splitlines(), 1):
                if _OLD_PREFIX.search(line):
                    offenders.append(f"{name}:{i}")
        assert offenders == [], f"old '[*]' prefix still present: {offenders}"

    def test_every_claim_line_is_labelled(self):
        total = sum(_src(name).count("[simulated]") for name in COMMAND_MODULES)
        assert total == EXPECTED_CLAIM_LINES, (
            f"expected {EXPECTED_CLAIM_LINES} labelled claim lines, found {total}"
        )

    def test_labelled_lines_are_print_statements(self):
        """The label must reach the operator, not sit in a comment."""
        for name in COMMAND_MODULES:
            for i, line in enumerate(_src(name).splitlines(), 1):
                if "[simulated]" in line:
                    assert line.lstrip().startswith("print("), (
                        f"{name}:{i} mentions [simulated] outside a print(): "
                        f"{line.strip()[:60]}"
                    )

    def test_halt_really_prints_the_label(self, capsys):
        from sbin.boot import HaltCommand

        assert HaltCommand().execute([]) == 0
        captured = capsys.readouterr()
        assert "[simulated]" in captured.err
        assert "[*]" not in captured.err

    def test_mount_really_prints_the_label(self, capsys):
        from sbin.mount import MountCommand

        assert MountCommand().execute(["/dev/sdb1", "/mnt/h235"]) == 0
        assert "[simulated] mount:" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Layer 3: the programmatic answer
# ---------------------------------------------------------------------------

class TestSimulationFlag:
    def test_default_is_true(self):
        assert guard_mod.DEFAULT_SIMULATED is True

    def test_halt_is_simulated(self):
        assert SbinManager().is_simulated("halt") is True

    def test_mktemp_is_the_only_real_command(self):
        mgr = SbinManager()
        assert mgr.is_simulated("mktemp") is False
        assert mgr.list_real() == ["mktemp"]

    def test_unknown_command_reports_simulated(self):
        """The safe answer: nothing ran, so nothing real happened."""
        assert SbinManager().is_simulated("no-such-command") is True

    def test_simulated_and_real_partition_the_registry(self):
        mgr = SbinManager()
        simulated = set(mgr.list_simulated())
        real = set(mgr.list_real())
        assert simulated & real == set(), "a command is both simulated and real"
        assert simulated | real == set(mgr.list_commands())

    def test_compliance_reports_the_split(self):
        c = SbinManager().check_compliance()
        assert "simulated_commands" in c
        assert "real_commands" in c
        assert c["real_commands"] == ["mktemp"]
        assert c["simulated_commands"] + len(c["real_commands"]) == c["total_commands"]

    def test_every_registry_entry_is_classified(self):
        for name in SBIN_COMMAND_REGISTRY:
            assert isinstance(SbinManager().is_simulated(name), bool)

    def test_mktemp_class_declares_it(self):
        from sbin.maintenance import MktempCommand

        assert MktempCommand.simulated is False


# ---------------------------------------------------------------------------
# Layer 2: the audit trail says which it was
# ---------------------------------------------------------------------------

class TestAuditCarriesSimulation:
    def test_simulated_command_is_marked(self, caplog):
        from sbin.boot import HaltCommand

        caplog.set_level(logging.INFO, logger=AUDIT_LOGGER)
        HaltCommand().execute([])
        assert "simulated=True" in caplog.text

    def test_real_command_is_marked_false(self, caplog):
        """A stand-in avoids creating a real temp file just to test the field."""
        from sbin.boot import SbinCommand

        class _RealProbe(SbinCommand):
            name = "real-probe"
            simulated = False

            def execute(self, args=None):
                return 0

        caplog.set_level(logging.INFO, logger=AUDIT_LOGGER)
        _RealProbe().execute([])
        assert "simulated=False" in caplog.text

    def test_guard_reads_the_class_attribute(self):
        tree = ast.parse(_src("command_guard.py"))
        src = ast.unparse(tree)
        # `ast.unparse` normalises quotes, so match either style.
        assert re.search(
            r"getattr\(cls,\s*['\"]simulated['\"],\s*DEFAULT_SIMULATED\)", src
        ), "the guard does not read the per-class `simulated` attribute"
        assert re.search(r"simulated=simulated", src), (
            "the audit record does not carry the simulated flag"
        )


# ---------------------------------------------------------------------------
# Documentation: the package says it up front
# ---------------------------------------------------------------------------

class TestDocumentation:
    def test_package_docstring_warns(self):
        doc = ast.get_docstring(ast.parse(_src("__init__.py")), clean=False)
        assert "simulation" in doc
        assert "[simulated]" in doc
        assert "mktemp" in doc

    def test_guard_docstring_explains_the_label(self):
        doc = ast.get_docstring(ast.parse(_src("command_guard.py")), clean=False)
        assert "[simulated]" in doc
        # Pin what the docstring *documents*, never an ``H235`` tag: an external
        # process re-saves these sources and strips the cosmetic ``Hxxx``
        # markers (seen again in session 225, which removed "(H235)" from this
        # very heading while leaving "(H233)" above it intact).
        assert "simulated = False" in doc, "the mktemp exception must be documented"
        assert "is_simulated" in doc, "the programmatic API must be documented"

    def test_manager_methods_are_documented(self):
        for method in ("is_simulated", "list_simulated", "list_real"):
            assert f"def {method}(" in _src("sbin_manager.py")
