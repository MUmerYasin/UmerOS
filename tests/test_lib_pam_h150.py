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

"""H150 tests — ``lib/security.py`` marks ``pam_permit.so`` as fail-open.

The standard flagged the PAM registry for listing ``pam_permit.so`` ("Always
permit") as a stock module: if the security subsystem ever consulted the
registry for auth it could fail open (💭 H150).  The remedy is to mark it
non-default and document that it must never be auto-selected.

These tests pin: ``pam_permit`` carries ``is_fail_open`` and is listed in
``FAIL_OPEN_PAM_MODULES``; the safe selectors exclude it; and adding it to an
``auth``/``password`` rule logs a warning.  ``pam_deny`` (fail-closed) is NOT
flagged.
"""

from __future__ import annotations

import logging
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEC_SRC = ROOT / "lib" / "security.py"

from lib.security import (  # noqa: E402
    FAIL_OPEN_PAM_MODULES,
    PamLibraryManager,
    PamModuleType,
    PamService,
)


class TestPamPermitFlagged(unittest.TestCase):
    def setUp(self):
        self.mgr = PamLibraryManager()

    def test_pam_permit_is_flagged_fail_open(self):
        m = self.mgr.find_module("pam_permit.so")
        self.assertIsNotNone(m)
        self.assertTrue(m.is_fail_open)

    def test_fail_open_registry_constant(self):
        self.assertIn("pam_permit.so", FAIL_OPEN_PAM_MODULES)

    def test_pam_deny_is_not_fail_open(self):
        m = self.mgr.find_module("pam_deny.so")
        self.assertIsNotNone(m)
        self.assertFalse(m.is_fail_open)  # deny is fail-CLOSED

    def test_summary_counts_fail_open_modules(self):
        self.assertEqual(self.mgr.get_summary()["fail_open_modules"], 1)


class TestSafeAuthSelectors(unittest.TestCase):
    def setUp(self):
        self.mgr = PamLibraryManager()

    def test_raw_auth_list_includes_permit(self):
        names = {m.name for m in self.mgr.modules_for_auth()}
        self.assertIn("pam_permit.so", names)

    def test_safe_only_excludes_permit(self):
        names = {m.name for m in self.mgr.modules_for_auth(safe_only=True)}
        self.assertNotIn("pam_permit.so", names)

    def test_default_auth_modules_excludes_permit(self):
        mods = self.mgr.default_auth_modules()
        names = {m.name for m in mods}
        self.assertNotIn("pam_permit.so", names)
        # Still a useful, non-empty default set (e.g. pam_unix).
        self.assertIn("pam_unix.so", names)
        self.assertTrue(all(not m.is_fail_open for m in mods))


class TestRuleWarning(unittest.TestCase):
    def test_auth_rule_with_pam_permit_warns(self):
        svc = PamService(service="sshd")
        with self.assertLogs("UmerOS.Lib.Security", level="WARNING") as cm:
            svc.add_rule(PamModuleType.AUTH, "sufficient", "pam_permit.so")
        self.assertTrue(any("fail-open" in line.lower() for line in cm.output))

    def test_password_rule_with_pam_permit_warns(self):
        svc = PamService(service="passwd")
        with self.assertLogs("UmerOS.Lib.Security", level="WARNING"):
            svc.add_rule("password", "sufficient", "pam_permit.so")

    def test_normal_auth_rule_does_not_warn(self):
        svc = PamService(service="sshd")
        logger = logging.getLogger("UmerOS.Lib.Security")
        with self.assertNoLogs(logger, level="WARNING"):
            svc.add_rule(PamModuleType.AUTH, "required", "pam_unix.so")
        self.assertEqual(len(svc.rules), 1)


class TestSourceInvariants(unittest.TestCase):
    def test_docstring_documents_fail_open(self):
        src = SEC_SRC.read_text(encoding="utf-8")
        self.assertIn("Fail-open modules (H150)", src)
        self.assertIn("must not be auto-selected", src)

    def test_pam_permit_entry_flags_fail_open(self):
        src = SEC_SRC.read_text(encoding="utf-8")
        self.assertIn("is_fail_open=True", src)
        self.assertIn('FAIL_OPEN_PAM_MODULES', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
