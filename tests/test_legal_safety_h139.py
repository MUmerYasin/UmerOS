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

"""H139 tests — the pre-execution safety gate is fail-CLOSED for HIGH/CRITICAL.

The standard flagged ``legal/safety_check.py``: ``verify_safety`` defaulted
``is_safe=True`` and only flipped to ``False`` on <500 MB free or a *CRITICAL*-level
backup failure — a failed backup on a HIGH operation (disk partition, kernel
module) yielded only a warning while the op was still reported "safe"
(soft/fail-open gate, same family as H29/H99/H131).

H139 requires a successful checkpoint backup for HIGH/CRITICAL before
``is_safe=True``.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAFETY_SRC = ROOT / "legal" / "safety_check.py"

from legal.disclaimer import RiskLevel  # noqa: E402
from legal.safety_check import SafetyChecker  # noqa: E402


def _disk(free_bytes):
    """A stand-in for ``shutil.disk_usage`` returning an object with ``.free``."""
    return mock.Mock(free=free_bytes, total=10 ** 12, used=0)


class TestFailClosedGate(unittest.TestCase):
    """HIGH/CRITICAL are only 'safe' once a checkpoint backup was created."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "critical_data"
        self.dir.mkdir()
        (self.dir / "config.sys").write_text("boot", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_high_with_successful_backup_is_safe(self):
        r = SafetyChecker.verify_safety("flash", RiskLevel.HIGH, self.dir, create_backup=True)
        self.assertTrue(r.is_safe)
        self.assertTrue(r.backup_created)
        self.assertIsNotNone(r.backup_path)
        self.assertTrue(Path(r.backup_path).exists())

    def test_critical_with_successful_backup_is_safe(self):
        r = SafetyChecker.verify_safety("kernel_module", RiskLevel.CRITICAL, self.dir, create_backup=True)
        self.assertTrue(r.is_safe)
        self.assertTrue(r.backup_created)

    def test_high_without_backup_request_is_blocked(self):
        r = SafetyChecker.verify_safety("flash", RiskLevel.HIGH, self.dir, create_backup=False)
        self.assertFalse(r.is_safe)
        self.assertFalse(r.backup_created)
        self.assertTrue(any("requires a successful pre-execution checkpoint backup" in w
                            for w in r.warnings))

    def test_high_with_missing_target_is_blocked(self):
        r = SafetyChecker.verify_safety("flash", RiskLevel.HIGH, Path(self._tmp.name) / "nope")
        self.assertFalse(r.is_safe)

    def test_high_with_no_target_is_blocked(self):
        r = SafetyChecker.verify_safety("flash", RiskLevel.HIGH, None)
        self.assertFalse(r.is_safe)

    def test_high_backup_failure_is_blocked(self):
        with mock.patch("legal.safety_check.shutil.copytree", side_effect=OSError("disk full")):
            r = SafetyChecker.verify_safety("flash", RiskLevel.HIGH, self.dir, create_backup=True)
        self.assertFalse(r.is_safe)
        self.assertFalse(r.backup_created)

    def test_critical_backup_failure_is_blocked(self):
        f = Path(self._tmp.name) / "file.bin"
        f.write_text("x", encoding="utf-8")
        with mock.patch("legal.safety_check.shutil.copy2", side_effect=OSError("io")):
            r = SafetyChecker.verify_safety("kernel_module", RiskLevel.CRITICAL, f, create_backup=True)
        self.assertFalse(r.is_safe)

    def test_summary_surfaces_missing_checkpoint(self):
        r = SafetyChecker.verify_safety("flash", RiskLevel.HIGH, self.dir, create_backup=False)
        s = r.summary()
        self.assertIn("BLOCKED", s)
        self.assertIn("NONE (required for HIGH/CRITICAL)", s)


class TestLowerRiskStillSoft(unittest.TestCase):
    """SAFE/MODERATE are unchanged — no checkpoint is mandated."""

    def test_safe_without_target(self):
        r = SafetyChecker.verify_safety("read", RiskLevel.SAFE)
        self.assertTrue(r.is_safe)
        self.assertFalse(r.backup_created)

    def test_moderate_without_target(self):
        r = SafetyChecker.verify_safety("cfg", RiskLevel.MODERATE)
        self.assertTrue(r.is_safe)


class TestDiskSpaceCheck(unittest.TestCase):
    """The existing disk-headroom block is preserved."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "d"
        self.dir.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_low_disk_blocks(self):
        with mock.patch("legal.safety_check.shutil.disk_usage", return_value=_disk(100 * 1024 * 1024)):
            r = SafetyChecker.verify_safety("op", RiskLevel.MODERATE, self.dir, create_backup=False)
        self.assertFalse(r.is_safe)

    def test_healthy_disk_passes(self):
        with mock.patch("legal.safety_check.shutil.disk_usage", return_value=_disk(500 * 1024 ** 3)):
            r = SafetyChecker.verify_safety("op", RiskLevel.MODERATE, self.dir, create_backup=False)
        self.assertTrue(r.is_safe)


class TestSourceInvariants(unittest.TestCase):
    """Pin code facts, never cosmetic tags."""

    def test_gate_requires_backup_for_high_and_critical(self):
        src = SAFETY_SRC.read_text(encoding="utf-8")
        self.assertIn("not result.backup_created", src)
        self.assertIn("RiskLevel.HIGH, RiskLevel.CRITICAL", src)
        self.assertIn("backup_created", src)

    def test_critical_only_check_removed(self):
        src = SAFETY_SRC.read_text(encoding="utf-8")
        self.assertNotIn("if risk_level == RiskLevel.CRITICAL:", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
