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

"""H158 tests — the media mount authorization layer is wired and correct.

The standard flagged ``media/permissions.py`` as an **unwired** authz layer
(``MountPermissionManager``/``GroupPolicy`` were never consulted before
mounting — decorative, same family as H112), plus a ``" optical"`` literal bug
(stray leading space) and a ``require_primary_group`` flag that was never
checked.

The fix: (1) correct the literal to ``"optical"`` and give it a real
``GROUP_MEDIA_MAP`` entry; (2) honour ``require_primary_group`` in
``GroupPolicy``; (3) add ``MountPermissionManager.authorize_mount()``; and
(4) wire a permission check into ``media/mount_ops`` (mount/unmount/remount)
via a module-level manager, fail-closed once one is set.

These tests pin the corrected behaviour and the wiring.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from media import mount_ops as mo  # noqa: E402
from media import permissions as perm  # noqa: E402
from media.permissions import (  # noqa: E402
    GROUP_MEDIA_MAP,
    STANDARD_MOUNT_GROUPS,
    GroupPolicy,
    MountPermissionManager,
)

PERMISSIONS_PY = ROOT / "media" / "permissions.py"
MOUNT_OPS_PY = ROOT / "media" / "mount_ops.py"


class TestLiteralBugFixed(unittest.TestCase):
    """The ``" optical"`` stray-space literal is fixed and functional."""

    def test_no_stray_space_group(self):
        self.assertNotIn(" optical", STANDARD_MOUNT_GROUPS)

    def test_optical_group_present(self):
        self.assertIn("optical", STANDARD_MOUNT_GROUPS)

    def test_optical_group_is_functional(self):
        # The fixed group must actually grant access to optical media.
        self.assertIn("optical", GROUP_MEDIA_MAP)
        gp = GroupPolicy(user_groups={"optical"})
        self.assertTrue(gp.can_access_media_type("u", "cdrom"))
        self.assertFalse(gp.can_access_media_type("u", "usb"))

    def test_source_has_no_stray_literal(self):
        # Pin the *set entry* (trailing comma), not the incidental substring
        # used in the _selftest assertion (" optical" not in ...).
        src = PERMISSIONS_PY.read_text(encoding="utf-8")
        self.assertNotIn('" optical",', src)
        self.assertIn('"optical",', src)


class TestRequirePrimaryGroup(unittest.TestCase):
    """``require_primary_group`` is now actually enforced."""

    def test_default_is_permissive(self):
        gp = GroupPolicy(user_groups={"plugdev"})
        self.assertTrue(gp.can_access_media_type("u", "usb"))

    def test_required_without_primary_denies(self):
        gp = GroupPolicy(user_groups={"plugdev"}, require_primary_group=True)
        self.assertFalse(gp.can_access_media_type("u", "usb"))

    def test_required_with_matching_primary_allows(self):
        gp = GroupPolicy(user_groups={"plugdev"}, require_primary_group=True,
                         primary_group="plugdev")
        self.assertTrue(gp.can_access_media_type("u", "usb"))

    def test_required_with_non_matching_primary_denies(self):
        gp = GroupPolicy(user_groups={"plugdev"}, require_primary_group=True,
                         primary_group="cdrom")
        self.assertFalse(gp.can_access_media_type("u", "usb"))

    def test_allowed_types_honour_primary(self):
        gp = GroupPolicy(user_groups={"plugdev", "cdrom"}, require_primary_group=True,
                         primary_group="cdrom")
        types = gp.get_allowed_media_types()
        self.assertIn("cdrom", types)
        self.assertNotIn("usb", types)

    def test_for_user_forwards_primary(self):
        gp = GroupPolicy.for_user("u", {"plugdev"}, require_primary_group=True,
                                  primary_group="plugdev")
        self.assertTrue(gp.require_primary_group)
        self.assertEqual(gp.primary_group, "plugdev")
        self.assertTrue(gp.can_access_media_type("u", "usb"))


class TestAuthorizeMount(unittest.TestCase):
    """``authorize_mount()`` combines direct permissions and group policy."""

    def test_direct_permission_allows(self):
        mgr = MountPermissionManager()
        mgr.grant("alice", "/media/usb0", owner=True)
        self.assertTrue(mgr.authorize_mount("alice", "/media/usb0"))

    def test_no_permission_denies(self):
        mgr = MountPermissionManager()
        self.assertFalse(mgr.authorize_mount("nobody", "/media/usb0"))

    def test_admin_allows(self):
        mgr = MountPermissionManager()
        self.assertTrue(mgr.authorize_mount("root", "/anything"))

    def test_group_policy_fallback_allows(self):
        mgr = MountPermissionManager()
        self.assertTrue(
            mgr.authorize_mount(
                "bob", "/media/usb0",
                media_type="usb",
                group_policy=GroupPolicy(user_groups={"plugdev"}),
            )
        )

    def test_group_policy_denies_wrong_group(self):
        mgr = MountPermissionManager()
        self.assertFalse(
            mgr.authorize_mount(
                "bob", "/media/usb0",
                media_type="usb",
                group_policy=GroupPolicy(user_groups={"cdrom"}),
            )
        )


class TestMountOpsWiring(unittest.TestCase):
    """``media/mount_ops`` consults the wired permission manager."""

    def setUp(self):
        mo.set_permission_manager(None)
        mo._sim_mounts.clear()  # isolate simulation state between tests

    def tearDown(self):
        mo.set_permission_manager(None)
        mo._sim_mounts.clear()

    def test_no_manager_is_permissive(self):
        r = mo.mount("/dev/sdb1", "/media/h158_a", user="alice")
        self.assertTrue(r.success)

    def test_wired_manager_denies_unpermitted_user(self):
        mo.set_permission_manager(MountPermissionManager())
        r = mo.mount("/dev/sdb1", "/media/h158_b", user="alice")
        self.assertFalse(r.success)
        self.assertEqual(r.error, mo.MountError.PERMISSION_DENIED)

    def test_wired_manager_fails_closed_without_user(self):
        mo.set_permission_manager(MountPermissionManager())
        r = mo.mount("/dev/sdb1", "/media/h158_c")
        self.assertFalse(r.success)
        self.assertEqual(r.error, mo.MountError.PERMISSION_DENIED)

    def test_wired_manager_allows_granted_user(self):
        mgr = MountPermissionManager()
        mgr.grant("alice", "/media/h158_d", owner=True)
        mo.set_permission_manager(mgr)
        r = mo.mount("/dev/sdb1", "/media/h158_d", user="alice")
        self.assertTrue(r.success)

    def test_unmount_denied_for_unpermitted_user(self):
        mo.set_permission_manager(MountPermissionManager())
        r = mo.unmount("/media/h158_e", user="bob")
        self.assertFalse(r.success)
        self.assertEqual(r.error, mo.MountError.PERMISSION_DENIED)

    def test_remount_denied_for_unpermitted_user(self):
        mo.set_permission_manager(MountPermissionManager())
        r = mo.remount("/media/h158_f", ["ro"], user="bob")
        self.assertFalse(r.success)
        self.assertEqual(r.error, mo.MountError.PERMISSION_DENIED)

    def test_setter_getter_roundtrip(self):
        mgr = MountPermissionManager()
        mo.set_permission_manager(mgr)
        self.assertIs(mo.get_permission_manager(), mgr)

    def test_source_invariants(self):
        src = MOUNT_OPS_PY.read_text(encoding="utf-8")
        self.assertIn("def set_permission_manager", src)
        self.assertIn("def _permission_denied", src)
        self.assertIn("_permission_denied(user, mount_point", src)


class TestSelftests(unittest.TestCase):
    def test_permissions_selftest(self):
        self.assertTrue(perm._selftest())

    def test_mount_ops_selftest(self):
        self.assertTrue(mo._selftest())


if __name__ == "__main__":
    unittest.main(verbosity=2)
