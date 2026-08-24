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

"""Tests for compatibility.ZeroTrustContainer (H51 fail-closed execution).

Verifies that a container may only execute a binary when it holds the
required capability, and is DENIED (not silently run) otherwise.
"""
from __future__ import annotations

import unittest

from compatibility.container import ZeroTrustContainer
from kernel.capability_manager import CapabilityManager


class _FakeCaps:
    """Minimal capability manager stub used to drive the container gate.

    Mirrors the real CapabilityManager contract: ``query`` returns a bool and
    never raises; ``check`` raises PermissionError when the cap is absent.
    """

    def __init__(self, granted=None):
        self._granted = set(granted or [])

    def query(self, pid, cap):
        return cap in self._granted

    def check(self, pid, cap):
        if cap in self._granted:
            return True
        raise PermissionError(f"PID {pid} lacks {cap}")


class TestZeroTrustContainerExecute(unittest.TestCase):

    def test_execute_denied_without_hardware_cap(self):
        # [FIX H51] Fail-closed: no HARDWARE capability => no execution.
        c = ZeroTrustContainer(1, _FakeCaps(granted=[]))
        result = c.execute_binary("/bin/app", os_type="linux")
        self.assertFalse(result)
        self.assertFalse(c.running)

    def test_execute_allowed_with_hardware_cap(self):
        # [FIX H51] Holding the required capability permits execution.
        c = ZeroTrustContainer(2, _FakeCaps(granted=["HARDWARE"]))
        result = c.execute_binary("/bin/app", os_type="linux")
        self.assertTrue(result)
        self.assertFalse(c.running)

    def test_execute_denied_unregistered_container(self):
        # [FIX H51] An unknown/unregistered container id has no capability and
        # must be denied (zero-trust default-deny).
        caps = CapabilityManager()  # only SYSTEM_PID=0 is omnipotent
        c = ZeroTrustContainer(99999, caps)
        self.assertFalse(c.execute_binary("/bin/app"))

    def test_execute_windows_with_hardware(self):
        c = ZeroTrustContainer(3, _FakeCaps(granted=["HARDWARE"]))
        self.assertTrue(c.execute_binary("C:\\app.exe", os_type="windows"))

    def test_execute_windows_without_hardware_denied(self):
        c = ZeroTrustContainer(4, _FakeCaps(granted=[]))
        self.assertFalse(c.execute_binary("C:\\app.exe", os_type="windows"))


if __name__ == "__main__":
    unittest.main()
