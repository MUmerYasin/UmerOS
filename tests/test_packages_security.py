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
Regression test for packages/umer_pkg.py RED finding H198.

install / remove / update mutate the shared package tree and registry —
they must sit behind the zero-trust capability gate (fail-closed when
strict mode is on and no CapabilityManager is wired).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import core.capability_gate as cg                    # noqa: E402
from packages.umer_pkg import UmerPackageManager as UmerPkg                # noqa: E402


class TestPackageLifecycleGated(unittest.TestCase):
    """[FIX H198] strict mode => PermissionError before any FS mutation."""

    def setUp(self) -> None:
        self._prev_strict = cg.gate.strict
        self.addCleanup(cg.gate.set_strict, self._prev_strict)
        cg.gate.set_strict(True)
        self.pkg = UmerPkg()

    def test_install_gated(self):
        with self.assertRaises(PermissionError):
            self.pkg.install("somepkg")

    def test_remove_gated(self):
        with self.assertRaises(PermissionError):
            self.pkg.remove("somepkg")

    def test_update_gated(self):
        with self.assertRaises(PermissionError):
            self.pkg.update("somepkg")

    def test_permissive_when_not_strict(self):
        # Without strict mode and without a wired manager the gate only
        # warns (documented permissive fallback) — ops must not raise.
        cg.gate.set_strict(False)
        try:
            self.assertFalse(self.pkg.remove("never-installed"))
        except PermissionError:  # pragma: no cover
            self.fail("gate must stay permissive when unwired and non-strict")


if __name__ == "__main__":
    unittest.main()
