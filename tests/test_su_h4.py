"""[FIX H4] su: capability-gated exec + honest not-implemented shell exit."""
from __future__ import annotations
import os, sys, types, unittest
from pathlib import Path
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
try:
    from user_commands import SuCommand  # noqa: E402  (bin/ on sys.path)
    _HAS_SU = True
except Exception:  # pragma: no cover - pwd is POSIX-only
    _HAS_SU = False

_FAKE_USER = types.SimpleNamespace(pw_uid=1000, pw_gid=1000,
                                   pw_dir="/home/u", pw_shell="/bin/sh")

@unittest.skipUnless(_HAS_SU, 'user_commands needs POSIX pwd')
class TestSuH4(unittest.TestCase):
    def setUp(self):
        import core.capability_gate as cg
        self._prev = cg.gate.strict
        self.addCleanup(cg.gate.set_strict, self._prev)

    def test_exec_shell_strict_requires_cap(self):
        import core.capability_gate as cg
        cg.gate.set_strict(True)
        with self.assertRaises(PermissionError):
            SuCommand()._exec_shell("u", _FAKE_USER, False, {}, None)

    def test_exec_shell_honest_nonzero_when_allowed(self):
        import core.capability_gate as cg
        cg.gate.set_strict(False)
        rc = SuCommand()._exec_shell("u", _FAKE_USER, False, {}, None)
        self.assertNotEqual(rc, 0)   # stub no longer fakes success

    def test_exec_command_refuses_on_windows(self):
        if os.name == "posix":
            self.skipTest("POSIX host")
        import core.capability_gate as cg
        cg.gate.set_strict(False)
        rc = SuCommand()._exec_command("u", _FAKE_USER, "id", {}, None)
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
