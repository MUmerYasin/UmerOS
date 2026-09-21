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
H60 regression tests — `DeviceManager.sync_to_filesystem()` zero-trust gate.

Locks the remediation adopted in H60:
  * Materializing device special files is a privileged op gated behind
    ``CAP_SYS_ADMIN`` (fail-closed via the process-global capability gate).
  * Every node path is confined to ``dev_root`` (CWE-22); a node that would
    resolve outside the UmerOS virtual ``/dev`` namespace is refused and
    never materialized.
"""

import os
import tempfile
import unittest

from dev.core import DeviceManager, DeviceNode, DeviceType
from core.capability_gate import gate, CAP_SYS_ADMIN


class _DevManagerGateTest(unittest.TestCase):
    def _save_gate(self):
        return {"strict": gate.strict, "manager": gate._manager}

    def _restore_gate(self, state):
        gate._manager = state["manager"]
        gate.set_strict(state["strict"])

    def test_sync_to_filesystem_gated_fail_closed(self):
        """Strict mode with no trust source must deny sync (fail-closed)."""
        state = self._save_gate()
        try:
            gate.unwire()
            gate.set_strict(True)
            mgr = DeviceManager(dev_root="/dev")
            mgr.create_node(
                DeviceNode(name="null", path="/dev/null",
                           dev_type=DeviceType.CHAR, major=1, minor=3, mode=0o640)
            )
            with self.assertRaises(PermissionError):
                mgr.sync_to_filesystem()
        finally:
            self._restore_gate(state)

    def test_sync_to_filesystem_permissive_when_unwired(self):
        """Default (unwired, non-strict) posture does not raise at the gate.

        Uses a DIRECTORY node so the loop runs without depending on the
        Linux-only ``os.mknod`` (UmerOS targets Linux; this keeps the test
        green on the Windows sandbox while still exercising the gate path).
        """
        state = self._save_gate()
        try:
            gate.unwire()
            gate.set_strict(False)
            with tempfile.TemporaryDirectory() as root:
                mgr = DeviceManager(dev_root=root)
                mgr.create_node(
                    DeviceNode(name="input", path=os.path.join(root, "input"),
                               dev_type=DeviceType.DIRECTORY, mode=0o640)
                )
                result = mgr.sync_to_filesystem()  # PermissionError must NOT fire
                self.assertIsInstance(result, int)
                self.assertEqual(result, 1)
        finally:
            self._restore_gate(state)

    def test_sync_to_filesystem_refuses_escaping_node(self):
        """A node escaping dev_root is refused and never materialized (CWE-22)."""
        state = self._save_gate()
        try:
            gate.unwire()
            gate.set_strict(False)
            with tempfile.TemporaryDirectory() as root:
                mgr = DeviceManager(dev_root=root)
                escape = os.path.join(os.path.dirname(root), "escape_device")
                mgr.create_node(
                    DeviceNode(name="escape", path=escape,
                               dev_type=DeviceType.CHAR, major=1, minor=3, mode=0o640)
                )
                with self.assertLogs("UmerOS.Dev.Core", level="WARNING") as cm:
                    result = mgr.sync_to_filesystem()
                self.assertEqual(result, 0)
                self.assertFalse(os.path.exists(escape))
                self.assertTrue(any("REFUSED" in rec for rec in cm.output))
        finally:
            self._restore_gate(state)


if __name__ == "__main__":
    unittest.main()
