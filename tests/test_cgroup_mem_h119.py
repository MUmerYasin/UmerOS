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

"""tests — fail-closed cgroup memory gate for ungrouped PIDs.

`CGroupManager.check_memory_limit` used to `return True` for any PID not in a
cgroup (a silent fail-open resource gate). It now applies an explicit,
auditable `ungrouped_policy` that **defaults to fail-closed** (`"deny"`); the
legacy implicit-allow behaviour is available only by opting into `"allow"`.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kernel.cgroup import (  # noqa: E402
    UNGROUPED_POLICY_ALLOW,
    UNGROUPED_POLICY_DEFAULT_CGROUP,
    UNGROUPED_POLICY_DENY,
    _VALID_UNGROUPED_POLICIES,
    CGroup,
    CGroupManager,
)

MB = 1024 * 1024


class TestUngroupedPolicyDefaults(unittest.TestCase):
    # ── fail-closed default ───────────────────────────────────────────────
    def test_ungrouped_pid_is_denied_by_default(self):
        mgr = CGroupManager()
        self.assertFalse(mgr.check_memory_limit(pid=1234, requested_bytes=1 * MB))

    def test_ungrouped_pid_denied_even_for_tiny_allocation(self):
        mgr = CGroupManager()
        self.assertFalse(mgr.check_memory_limit(pid=42, requested_bytes=1))

    def test_default_policy_is_deny(self):
        mgr = CGroupManager()
        self.assertEqual(mgr.ungrouped_policy, UNGROUPED_POLICY_DENY)
        self.assertIsNone(mgr.default_cgroup)

    def test_valid_policies_constant(self):
        self.assertEqual(
            _VALID_UNGROUPED_POLICIES,
            frozenset(
                {
                    UNGROUPED_POLICY_DENY,
                    UNGROUPED_POLICY_ALLOW,
                    UNGROUPED_POLICY_DEFAULT_CGROUP,
                }
            ),
        )


class TestUngroupedPolicyValidation(unittest.TestCase):
    def test_unknown_policy_raises_value_error(self):
        with self.assertRaises(ValueError):
            CGroupManager(ungrouped_policy="permit-all")

    def test_explicit_deny_policy_accepted(self):
        mgr = CGroupManager(ungrouped_policy=UNGROUPED_POLICY_DENY)
        self.assertFalse(mgr.check_memory_limit(1, MB))


class TestUngroupedPolicyAllow(unittest.TestCase):
    def test_allow_policy_permits_ungrouped_pid(self):
        mgr = CGroupManager(ungrouped_policy=UNGROUPED_POLICY_ALLOW)
        self.assertTrue(mgr.check_memory_limit(pid=7, requested_bytes=1 * MB))

    def test_allow_policy_is_audited(self):
        """The opt-in allow path must log a warning (documented, audited)."""
        mgr = CGroupManager(ungrouped_policy=UNGROUPED_POLICY_ALLOW)
        with self.assertLogs("UmerOS.CGroup", level="WARNING") as cm:
            mgr.check_memory_limit(pid=7, requested_bytes=1 * MB)
        self.assertTrue(any("allow" in line for line in cm.output))


class TestUngroupedPolicyDefaultCgroup(unittest.TestCase):
    def test_default_cgroup_policy_consults_fallback(self):
        mgr = CGroupManager(
            ungrouped_policy=UNGROUPED_POLICY_DEFAULT_CGROUP,
            default_cgroup="user",
        )
        # "user" has a 1024 MB limit -> small allocation is allowed.
        self.assertTrue(mgr.check_memory_limit(pid=99, requested_bytes=16 * MB))
        # Over the fallback limit -> denied.
        self.assertFalse(mgr.check_memory_limit(pid=99, requested_bytes=4096 * MB))

    def test_default_cgroup_missing_fails_closed(self):
        mgr = CGroupManager(
            ungrouped_policy=UNGROUPED_POLICY_DEFAULT_CGROUP,
            default_cgroup="does-not-exist",
        )
        self.assertFalse(mgr.check_memory_limit(pid=99, requested_bytes=1 * MB))


class TestGroupedPidStillHonoursLimit(unittest.TestCase):
    def test_grouped_pid_uses_its_cgroup_limit(self):
        mgr = CGroupManager()
        mgr.assign_task(pid=555, cgroup_name="ai_background")  # 512 MB cap
        self.assertTrue(mgr.check_memory_limit(pid=555, requested_bytes=256 * MB))
        self.assertFalse(mgr.check_memory_limit(pid=555, requested_bytes=1024 * MB))

    def test_removed_task_falls_back_to_policy(self):
        mgr = CGroupManager()
        mgr.assign_task(pid=556, cgroup_name="user")
        mgr.remove_task(pid=556)
        # No longer grouped -> fail-closed default.
        self.assertFalse(mgr.check_memory_limit(pid=556, requested_bytes=1 * MB))


class TestCGroupPrimitiveUnchanged(unittest.TestCase):
    def test_can_allocate_memory_boundary(self):
        cg = CGroup("t", cpu_limit_pct=100.0, mem_limit_mb=100)
        self.assertTrue(cg.can_allocate_memory(100.0))
        self.assertFalse(cg.can_allocate_memory(100.1))

    def test_precreated_cgroups(self):
        mgr = CGroupManager()
        self.assertEqual(set(mgr.cgroups), {"system", "user", "ai_background"})


if __name__ == "__main__":
    unittest.main()
