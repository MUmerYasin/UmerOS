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
H6 / H55 regression tests — canonical Command base contract.

Locks the adopted convention established by the remediation:
    Command.execute(self, args: Optional[List[str]] = None) -> int
so that the base no longer contradicts the dominant `bin/` signature and
subclasses cannot silently drift back to `execute(*args) -> Any`.
"""

import inspect
import unittest
from typing import List, Optional, get_type_hints

from core.command import Command


class _EchoCommand(Command):
    """A subclass that follows the adopted contract exactly."""
    name = "echo"

    def execute(self, args: Optional[List[str]] = None) -> int:
        self.last_args = args or []
        return 0


class _NotOverriddenCommand(Command):
    """A subclass that deliberately does NOT override execute."""


class TestCommandBaseContract(unittest.TestCase):
    def test_base_execute_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            Command().execute()

    def test_base_execute_with_args_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            Command().execute(["x", "y"])

    def test_base_signature_is_adopted_convention(self):
        """The base must declare exactly `execute(self, args=None) -> int`."""
        sig = inspect.signature(Command.execute)
        params = list(sig.parameters)
        self.assertEqual(params, ["self", "args"])
        self.assertIsNone(sig.parameters["args"].default)
        # Resolve annotations reliably (the module uses `from __future__ import
        # annotations`, so inspect.signature may leave them as strings).
        hints = get_type_hints(Command.execute)
        self.assertIs(hints["return"], int)
        self.assertEqual(hints["args"], Optional[List[str]])

    def test_canonical_subclass_accepts_argv(self):
        cmd = _EchoCommand()
        rc = cmd.execute(["-n", "hello"])
        self.assertEqual(rc, 0)
        self.assertEqual(cmd.last_args, ["-n", "hello"])

    def test_canonical_subclass_accepts_no_args(self):
        cmd = _EchoCommand()
        self.assertEqual(cmd.execute(), 0)
        self.assertEqual(cmd.last_args, [])

    def test_subclass_without_override_still_fails_closed(self):
        """A subclass that forgets to override must fail loudly, not silently."""
        with self.assertRaises(NotImplementedError):
            _NotOverriddenCommand().execute()
        with self.assertRaises(NotImplementedError):
            _NotOverriddenCommand().execute(["anything"])


if __name__ == "__main__":
    unittest.main()
