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

#!/usr/bin/env python3
"""
Runner for the Umer OS ``/lib`` test suite.

Usage::

    python tests/run_lib_tests.py
    python tests/run_lib_tests.py TestLibSummary
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "tests"))

import test_lib_cli  # noqa: E402
import test_lib_fhs  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    loader = unittest.TestLoader()
    if argv:
        names = []
        for arg in argv:
            for mod in (test_lib_cli, test_lib_fhs):
                names.append(f"{mod.__name__}.{arg}")
        suite = loader.loadTestsFromNames(names)
    else:
        suite = unittest.TestSuite()
        for mod in (test_lib_cli, test_lib_fhs):
            suite.addTests(loader.loadTestsFromModule(mod))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
