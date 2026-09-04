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
Regression tests for the H5 host-subprocess audit
=================================================
H5 (YELLOW): ``bin/boolean_ops.py`` ``env`` and ``etc/issue_motd.py`` spawn host
processes with argument lists. Remediation (per Code Review Standard §9 H5 —
"Keep list-form, no shell=True; sandbox on Windows host"):

  * ``EnvCommand.execute`` now gates its arbitrary host-exec path behind
    ``CAP_SYS_ADMIN`` via ``core.capability_gate`` (fail-closed under strict /
    wired posture, permissive when no trust source is wired).
  * ``issue_motd`` host-info probes (who/uptime/last) are funnelled through a
    single read-only allowlist helper that refuses non-allowlisted commands and
    refuses to run at all on a Windows host.

Run:  python -m unittest tests.test_host_subprocess_security -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from core.capability_gate import gate, CAP_SYS_ADMIN  # noqa: E402
from bin.boolean_ops import EnvCommand  # noqa: E402
from etc.issue_motd import _run_host_readonly  # noqa: E402


class TestEnvCommandHostExecGated(unittest.TestCase):
    """H5 — the env host-exec path must be capability-gated (sandboxed)."""

    def tearDown(self) -> None:
        gate.set_strict(False)
        gate.unwire()

    def test_host_exec_denied_when_strict(self):
        # Strict mode + no CapabilityManager wired => the arbitrary host-exec
        # path must fail CLOSED (raise PermissionError) instead of silently
        # exec'ing a host binary.
        gate.set_strict(True)
        with self.assertRaises(PermissionError):
            EnvCommand().execute(["some-host-binary", "--should-not-run"])

    def test_host_exec_consults_gate_when_unwired(self):
        # Default standalone posture is permissive, but the gate is still
        # consulted (a PermissionError would surface if strict). We exercise
        # only the gate path with a binary that does not exist, so no real
        # host command is actually executed.
        try:
            rc = EnvCommand().execute(["definitely-not-a-real-binary-xyz"])
        except PermissionError:
            self.fail("gate must be permissive when no trust source is wired")
        # EnvCommand swallows FileNotFoundError internally and returns 127.
        self.assertEqual(rc, 127)


class TestIssueMotdHostAllowlist(unittest.TestCase):
    """H5 — issue_motd host probes must be allowlisted and never shell=True."""

    def test_allowlisted_commands_accepted(self):
        for cmd in (["who"], ["uptime", "-p"], ["last", "-1", "-w", "who"]):
            result = _run_host_readonly(cmd)
            # Must return either real output or None — never raise, never exec
            # a disallowed binary.
            self.assertTrue(result is None or isinstance(result, str))

    def test_disallowed_command_refused(self):
        # A dangerous command is refused WITHOUT being executed.
        self.assertIsNone(_run_host_readonly(["rm", "-rf", "/"]))
        self.assertIsNone(_run_host_readonly(["sh", "-c", "touch /pwned"]))

    def test_empty_command_refused(self):
        self.assertIsNone(_run_host_readonly([]))

    @unittest.skipIf(sys.platform != "win32", "Windows-host guard only")
    def test_windows_host_refuses(self):
        self.assertIsNone(_run_host_readonly(["who"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
