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

"""tests — ``kernel/modules/dev`` rule/device hardening.

The standard flagged three defects in the kernel-space device layer:

* ``udev_rules`` advertised a ``RUN`` action (execute a program) in its docs but
  never implemented it — an over-promise (and a potential injection vector if it
  ever were implemented naively);
* device nodes defaulted to mode ``0o666`` (world read/write);
* ``device_manager.DeviceManager`` used ``self._lock = None`` — no concurrency
  guard around its registry.

corrects the ``RUN`` documentation (and now *warns* when an unsupported
action key is seen, instead of silently dropping it), tightens the default mode
to ``0o660``, and installs a real re-entrant lock around the registry.
"""

import logging
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEV = ROOT / "kernel" / "modules" / "dev"
DM_SRC = DEV / "device_manager.py"
UR_SRC = DEV / "udev_rules.py"

from kernel.modules.dev.device_manager import (  # noqa: E402
    DeviceManager,
    DeviceNode,
    DeviceType,
)
from kernel.modules.dev.udev_rules import (  # noqa: E402
    UdevAction,
    UdevEvent,
    UdevRule,
    UdevRuleAction,
    UdevRulesEngine,
)


def _event(subsystem="tty", kernel="ttyS0"):
    return UdevEvent(subsystem=subsystem, kernel=kernel, action=UdevAction.ADD)


class TestDefaultModeTightened(unittest.TestCase):
    """Device nodes no longer default to world read/write."""

    def test_device_node_default_mode(self):
        node = DeviceNode(name="x", dev_type=DeviceType.CHAR, major=1, minor=3)
        self.assertEqual(node.mode, 0o660)
        self.assertNotEqual(node.mode, 0o666)

    def test_apply_actions_default_mode(self):
        dm = DeviceManager()
        node = UdevRule(matches=[], actions=[]).apply_actions(_event(), dm)
        self.assertEqual(node.mode, 0o660)

    def test_apply_actions_explicit_mode_honoured(self):
        dm = DeviceManager()
        rule = UdevRule(matches=[], actions=[UdevRuleAction("MODE", "0640")])
        self.assertEqual(rule.apply_actions(_event(), dm).mode, 0o640)

    def test_apply_actions_invalid_mode_falls_back_to_tight_default(self):
        dm = DeviceManager()
        rule = UdevRule(matches=[], actions=[UdevRuleAction("MODE", "not-octal")])
        self.assertEqual(rule.apply_actions(_event(), dm).mode, 0o660)

    def test_default_rules_use_tight_modes(self):
        dm = DeviceManager()
        eng = UdevRulesEngine(dm)
        nodes = eng.simulate_hotplug("block", "sda", major=8, minor=0)
        self.assertTrue(nodes)
        self.assertEqual(nodes[0].mode, 0o660)


class TestRunActionNotExecuted(unittest.TestCase):
    """``RUN`` is documented as unsupported and is never executed."""

    def test_run_action_is_not_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = os.path.join(tmp, "pwned")
            dm = DeviceManager()
            rule = UdevRule(matches=[], actions=[
                UdevRuleAction("RUN", f"touch {sentinel}"),
                UdevRuleAction("MODE", "0600"),
            ])
            node = rule.apply_actions(_event(), dm)
            self.assertFalse(os.path.exists(sentinel), "RUN action was executed!")
            self.assertEqual(node.mode, 0o600)  # other actions still applied

    def test_unsupported_key_warns(self):
        dm = DeviceManager()
        rule = UdevRule(matches=[], actions=[UdevRuleAction("RUN", "/bin/true")])
        with self.assertLogs("UmerOS.Dev.UdevRules", level="WARNING") as cm:
            rule.apply_actions(_event(), dm)
        self.assertTrue(any("RUN" in rec for rec in cm.output), cm.output)

    def test_arbitrary_unknown_key_warns(self):
        dm = DeviceManager()
        rule = UdevRule(matches=[], actions=[UdevRuleAction("OPTIONS", "link_priority=10")])
        with self.assertLogs("UmerOS.Dev.UdevRules", level="WARNING") as cm:
            rule.apply_actions(_event(), dm)
        self.assertTrue(any("OPTIONS" in rec for rec in cm.output), cm.output)

    def test_known_keys_do_not_warn(self):
        dm = DeviceManager()
        rule = UdevRule(matches=[], actions=[
            UdevRuleAction("NAME", "tty/%k"),
            UdevRuleAction("SYMLINK", "tty/console"),
            UdevRuleAction("OWNER", "root"),
            UdevRuleAction("GROUP", "dialout"),
            UdevRuleAction("MODE", "0660"),
        ])
        logger = logging.getLogger("UmerOS.Dev.UdevRules")
        records = []

        class _H(logging.Handler):
            def emit(self, r):
                records.append(r)

        h = _H()
        logger.addHandler(h)
        try:
            rule.apply_actions(_event(), dm)
        finally:
            logger.removeHandler(h)
        self.assertEqual([r.getMessage() for r in records], [])


class TestDeviceManagerLock(unittest.TestCase):
    """The registry is guarded by a real (re-entrant) lock."""

    def test_lock_is_a_real_reentrant_lock(self):
        dm = DeviceManager()
        self.assertIsNotNone(dm._lock)
        self.assertIsInstance(dm._lock, type(threading.RLock()))

    def test_get_stats_reentrant_path(self):
        dm = DeviceManager()
        dm.create(DeviceNode(name="a", dev_type=DeviceType.CHAR, major=1, minor=1))
        stats = dm.get_stats()  # get_stats -> list_devices (same lock)
        self.assertEqual(stats["total_devices"], 1)

    def test_concurrent_create_is_consistent(self):
        dm = DeviceManager()
        errors = []

        def worker(i):
            try:
                dm.create(DeviceNode(name=f"d{i}", dev_type=DeviceType.CHAR, major=1, minor=i))
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(80)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(dm.list_devices()), 80)

    def test_concurrent_mixed_ops_do_not_raise(self):
        dm = DeviceManager()
        errors = []

        def churn(i):
            try:
                for j in range(25):
                    dm.create(DeviceNode(name=f"n{i}-{j}", dev_type=DeviceType.CHAR,
                                         major=1, minor=(i * 25 + j) % 256))
                    dm.get_stats()
                    dm.remove(f"n{i}-{j}")
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=churn, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])


class TestSourceInvariants(unittest.TestCase):
    """Pin code facts, not cosmetic tags."""

    def test_no_world_writable_defaults_remain(self):
        for path in (DM_SRC, UR_SRC):
            src = path.read_text(encoding="utf-8")
            self.assertNotIn("0o666", src, f"{path.name} still has 0o666")
            self.assertNotIn("0666", src, f"{path.name} still has 0666")

    def test_run_removed_from_action_key_comment(self):
        src = UR_SRC.read_text(encoding="utf-8")
        self.assertNotIn("# NAME, SYMLINK, OWNER, GROUP, MODE, RUN", src)

    def test_udev_rules_has_logger_and_no_unused_stat(self):
        src = UR_SRC.read_text(encoding="utf-8")
        self.assertIn('log = logging.getLogger("UmerOS.Dev.UdevRules")', src)
        self.assertNotIn("import stat\n", src)

    def test_lock_is_not_none_in_source(self):
        src = DM_SRC.read_text(encoding="utf-8")
        self.assertNotIn("self._lock = None", src)
        self.assertIn("threading.RLock()", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
