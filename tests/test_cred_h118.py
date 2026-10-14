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

"""tests — zero-trust credentials (no uid==0 capability short-circuit).

`Credentials.has_cap` used to return `self.is_root() or cap in self.caps`, so
`euid == 0` implicitly granted **every** capability (even ones outside
`DEFAULT_ROOT_CAPS`). Now `has_cap` consults only the explicit `caps` set, and
root's power comes from `DEFAULT_ROOT_CAPS` — an explicit grant of the full
known vocabulary (`KNOWN_CAPABILITIES`).
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kernel.cred import (  # noqa: E402
    DEFAULT_ROOT_CAPS,
    DEFAULT_USER_CAPS,
    KNOWN_CAPABILITIES,
    ROOT_UID,
    CredentialStore,
    Credentials,
)

# The set root held *implicitly* before the fix (from the old DEFAULT_ROOT_CAPS).
_LEGACY_ROOT_CAPS = frozenset({
    "fs.read", "fs.write", "fs.admin",
    "net.send", "net.recv", "net.admin",
    "proc.spawn", "proc.kill",
    "ai.inference", "ai.train",
})


class TestZeroTrustCredentials(unittest.TestCase):
    # ── vocabulary ────────────────────────────────────────────────────────
    def test_known_capabilities_superset_of_legacy_root(self):
        self.assertTrue(_LEGACY_ROOT_CAPS <= KNOWN_CAPABILITIES)

    def test_default_root_caps_is_the_full_explicit_grant(self):
        self.assertEqual(DEFAULT_ROOT_CAPS, KNOWN_CAPABILITIES)
        self.assertTrue(DEFAULT_USER_CAPS <= KNOWN_CAPABILITIES)

    def test_known_capabilities_covers_repo_vocabulary(self):
        """Every CAP_* string constant in the repo is a known capability."""
        from core import capability_gate as cg
        from kernel import capability_manager as cm

        repo_caps = set()
        for mod in (cm, cg):
            for name in dir(mod):
                if name.startswith("CAP_"):
                    val = getattr(mod, name)
                    if isinstance(val, str):
                        repo_caps.add(val)
        missing = repo_caps - KNOWN_CAPABILITIES
        self.assertEqual(missing, set(), f"unknown capabilities: {missing}")

    # ── default root cred ─────────────────────────────────────────────────
    def test_default_cred_is_root_and_has_every_known_cap(self):
        c = Credentials()
        self.assertTrue(c.is_root())
        for cap in KNOWN_CAPABILITIES:
            self.assertTrue(c.has_cap(cap), f"root should hold {cap}")

    def test_default_root_still_has_fs_read(self):
        # regression guard for tests/test_linux_modules.py
        self.assertTrue(Credentials().has_cap("fs.read"))

    def test_credential_store_root_helper(self):
        self.assertTrue(CredentialStore.root().has_cap("install"))

    # ── the fix: root is NOT a universal bypass ───────────────────────────
    def test_restricted_root_cred_is_restricted(self):
        c = Credentials().with_capabilities({"fs.read"})
        self.assertTrue(c.is_root())          # still uid 0
        self.assertTrue(c.has_cap("fs.read"))
        self.assertFalse(c.has_cap("install"))  # previously True via bypass
        self.assertFalse(c.has_cap("fs.admin"))

    def test_root_with_no_caps_has_no_caps(self):
        c = Credentials().with_capabilities(set())
        self.assertTrue(c.is_root())
        self.assertFalse(c.has_cap("fs.read"))
        self.assertFalse(c.has_cap("install"))

    def test_is_root_does_not_imply_install(self):
        self.assertFalse(Credentials().with_capabilities(set()).has_cap("install"))

    def test_with_euid_zero_does_not_grant_caps(self):
        """Promoting a user cred to euid 0 must NOT grant capabilities."""
        c = CredentialStore.user(uid=1000, gid=1000).with_euid(ROOT_UID)
        self.assertTrue(c.is_root())
        self.assertFalse(c.has_cap("install"))
        self.assertFalse(c.has_cap("fs.admin"))
        self.assertTrue(c.has_cap("fs.read"))  # DEFAULT_USER_CAPS member

    # ── ordinary user ─────────────────────────────────────────────────────
    def test_user_cred_caps(self):
        c = CredentialStore.user(uid=1000, gid=1000)
        self.assertFalse(c.is_root())
        self.assertTrue(c.has_cap("fs.read"))
        self.assertFalse(c.has_cap("install"))


class TestSourceInvariants(unittest.TestCase):
    def test_no_root_shortcircuit(self):
        src = (ROOT / "kernel" / "cred.py").read_text(encoding="utf-8")
        self.assertNotIn("self.is_root() or cap in self.caps", src)
        self.assertIn("return cap in self.caps", src)
        self.assertIn("KNOWN_CAPABILITIES", src)


if __name__ == "__main__":
    unittest.main()
