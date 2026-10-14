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

"""tests — de-duplicated `kernel/bootloader.py` header + EOF-safe EULA.

The standard flagged a copy-paste artifact: `#!/usr/bin/env python3` + the
module docstring defined three times (two byte-identical *active* blocks plus a
commented-out third), a ~108-line commented-out duplicate of the whole module
at the tail, and a fragile kernel-space `input()` EULA prompt.

H121 collapsed the header to one canonical copy, dropped the dead duplicate,
and made the EULA prompt fail CLOSED (graceful abort) when there is no TTY.
"""

import builtins
import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SRC_PATH = ROOT / "kernel" / "bootloader.py"


def _read_src() -> str:
    return SRC_PATH.read_text(encoding="utf-8")


class TestHeaderDeduplicated(unittest.TestCase):
    def test_exactly_one_shebang(self):
        self.assertEqual(_read_src().count("#!/usr/bin/env python3"), 1)

    def test_exactly_one_module_docstring(self):
        # Only the active docstring's title line should remain.
        self.assertEqual(_read_src().count("Umer OS Bootloader\n"), 1)

    def test_no_commented_out_shebang_copy(self):
        self.assertNotIn("# #!/usr/bin/env python3", _read_src())

    def test_no_commented_out_docstring_copy(self):
        self.assertNotIn("# Umer OS Bootloader Simulation", _read_src())

    def test_gpl_header_present(self):
        src = _read_src()
        self.assertIn("GNU General Public License as published by", src)
        self.assertTrue(src.startswith("# This program is free software"))

    def test_header_is_the_first_statement(self):
        # Shebang (if any) precedes the docstring, which precedes imports.
        src = _read_src()
        self.assertLess(src.index("#!/usr/bin/env python3"), src.index("import sys"))


class TestDeadDuplicateRemoved(unittest.TestCase):
    def test_no_dead_marker(self):
        self.assertNotIn("# -----------------------------------------------------", _read_src())

    def test_no_commented_out_duplicate_functions(self):
        src = _read_src()
        self.assertNotIn("# def show_legal_warning():", src)
        self.assertNotIn("# def system_check():", src)
        self.assertNotIn("# async def main():", src)
        self.assertNotIn("#         traceback.print_exc3()", src)

    def test_no_long_dead_comment_run(self):
        longest = run = 0
        for line in _read_src().splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                run += 1
                longest = max(longest, run)
            else:
                run = 0
        self.assertLess(longest, 100, f"{longest}-line dead comment run remains")


class TestModuleSurface(unittest.TestCase):
    def test_module_imports(self):
        import importlib

        bl = importlib.import_module("kernel.bootloader")
        self.assertTrue(hasattr(bl, "show_legal_warning"))
        self.assertTrue(hasattr(bl, "main"))
        self.assertTrue(hasattr(bl, "system_check"))


class TestEulaPromptEofSafe(unittest.TestCase):
    """The flagged `input()` prompt must fail CLOSED without a TTY."""

    def setUp(self):
        import importlib

        self.bl = importlib.import_module("kernel.bootloader")
        self._orig_input = builtins.input
        self._orig_sleep = self.bl.time.sleep
        self.bl.time.sleep = lambda *_a, **_k: None  # no 1s sleep in tests

    def tearDown(self):
        builtins.input = self._orig_input
        self.bl.time.sleep = self._orig_sleep

    def _run(self):
        buf = io.StringIO()
        code = "returned"
        with contextlib.redirect_stdout(buf):
            try:
                self.bl.show_legal_warning()
            except SystemExit as e:
                code = e.code
        return code, buf.getvalue()

    def test_eof_aborts_gracefully(self):
        def _eof(prompt=""):
            raise EOFError()

        builtins.input = _eof
        code, out = self._run()
        self.assertEqual(code, 0)  # clean abort, not an unhandled EOFError
        self.assertIn("non-interactive", out.lower())
        self.assertNotIn("Consent recorded", out)

    def test_no_response_aborts(self):
        builtins.input = lambda p="": "no"
        code, out = self._run()
        self.assertEqual(code, 0)
        self.assertIn("aborted", out.lower())

    def test_yes_response_proceeds(self):
        builtins.input = lambda p="": "YES"
        code, out = self._run()
        self.assertEqual(code, "returned")
        self.assertIn("Consent recorded", out)

    def test_input_is_guarded_in_source(self):
        src = _read_src()
        # The input() call must sit inside a try/except EOFError.
        idx = src.index('input("Do you agree and wish to continue?')
        window = src[max(0, idx - 80) : idx + 400]
        self.assertIn("try:", window)
        self.assertIn("except EOFError:", window)


if __name__ == "__main__":
    unittest.main()
