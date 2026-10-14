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

"""H116 tests — GUI shell launch: capability gate + Flutter-first resolution.

`UmerKernel.start_gui_shell` used to spawn a subprocess with **no capability
check**, and its comments wrongly called `ui/launch_gui.py` the "retired Tkinter
launcher" (it actually runs `flutter run --release`; the Tkinter DE is
`ui/umer_de.py`). Now the launch is gated behind `CAP_SYS_ADMIN` and prefers the
*built* Flutter executable, falling back to the SDK launcher only if absent.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.capability_gate import CAP_SYS_ADMIN, gate  # noqa: E402
from kernel.umer_kernel import (  # noqa: E402
    _CAP_SYS_ADMIN as KERNEL_CAP,
    UmerKernel,
    _gate as kernel_gate,
)


class _FakeManager:
    def __init__(self, allow=()):
        self.allow = set(allow)

    def query(self, pid, cap):
        return cap in self.allow


class TestGuiLaunchGating(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._prev = gate.snapshot()
        # Build the kernel without running __init__ (no boot side effects).
        self.kernel = UmerKernel.__new__(UmerKernel)
        gate.unwire()
        gate.set_strict(False)

    async def asyncTearDown(self):
        gate.restore(self._prev)

    # ── wiring ────────────────────────────────────────────────────────────
    async def test_module_gate_is_the_shared_singleton(self):
        self.assertIs(kernel_gate, gate)
        self.assertEqual(KERNEL_CAP, CAP_SYS_ADMIN)
        self.assertEqual(CAP_SYS_ADMIN, "sys.admin")

    # ── fail-closed ───────────────────────────────────────────────────────
    async def test_denied_in_strict_mode(self):
        gate.set_strict(True)
        with mock.patch("subprocess.Popen") as popen:
            with self.assertRaises(PermissionError):
                await self.kernel.start_gui_shell()
            popen.assert_not_called()

    async def test_denied_when_wired_without_cap(self):
        gate.wire(_FakeManager(allow=()))
        with mock.patch("subprocess.Popen") as popen:
            with self.assertRaises(PermissionError):
                await self.kernel.start_gui_shell()
            popen.assert_not_called()

    async def test_denial_happens_before_any_subprocess(self):
        gate.set_strict(True)
        with mock.patch.object(UmerKernel, "_find_flutter_binary") as finder:
            with self.assertRaises(PermissionError):
                await self.kernel.start_gui_shell()
            finder.assert_not_called()

    # ── allowed: Flutter-first resolution ─────────────────────────────────
    async def test_prefers_built_flutter_binary(self):
        gate.wire(_FakeManager(allow={CAP_SYS_ADMIN}))
        with mock.patch.object(UmerKernel, "_find_flutter_binary",
                               return_value="/opt/umer/flutter_ui.exe"):
            with mock.patch("subprocess.Popen") as popen:
                popen.return_value.pid = 4242
                await self.kernel.start_gui_shell()
        popen.assert_called_once()
        args, _kwargs = popen.call_args
        self.assertEqual(args[0], ["/opt/umer/flutter_ui.exe"])

    async def test_falls_back_to_sdk_launcher(self):
        gate.wire(_FakeManager(allow={CAP_SYS_ADMIN}))
        with mock.patch.object(UmerKernel, "_find_flutter_binary", return_value=None):
            with mock.patch("subprocess.Popen") as popen:
                proc = popen.return_value
                proc.pid = 7
                await self.kernel.start_gui_shell(mode="web")
        args, kwargs = popen.call_args
        self.assertEqual(args[0][0], sys.executable)
        self.assertTrue(args[0][1].endswith("launch_gui.py"))
        self.assertEqual(kwargs.get("stdin"), __import__("subprocess").PIPE)
        proc.stdin.write.assert_called_once()  # mode handshake over stdin

    async def test_allowed_with_cap_does_not_raise(self):
        gate.wire(_FakeManager(allow={CAP_SYS_ADMIN}))
        with mock.patch.object(UmerKernel, "_find_flutter_binary", return_value=None):
            with mock.patch("subprocess.Popen") as popen:
                popen.return_value.pid = 1
                await self.kernel.start_gui_shell()  # must not raise

    # ── helper contract ───────────────────────────────────────────────────
    def test_find_flutter_binary_contract(self):
        found = UmerKernel._find_flutter_binary()
        self.assertTrue(found is None or isinstance(found, str))
        if found is not None:
            self.assertTrue(Path(found).is_file())

    def test_find_flutter_binary_detects_shipped_windows_build(self):
        # The repo ships ui/flutter_ui/build/windows/x64/runner/Release/flutter_ui.exe
        exe = ROOT / "ui" / "flutter_ui" / "build" / "windows" / "x64" / "runner" / "Release" / "flutter_ui.exe"
        if exe.is_file():
            self.assertEqual(UmerKernel._find_flutter_binary(), str(exe))


class TestSourceInvariants(unittest.TestCase):
    def test_gui_launch_gated_and_flutter_first(self):
        src = (ROOT / "kernel" / "umer_kernel.py").read_text(encoding="utf-8")
        self.assertIn("_gate.require(_CAP_SYS_ADMIN)", src)
        self.assertIn("def _find_flutter_binary", src)

    def test_no_tkinter_in_launch_path(self):
        # launch_gui.py is the Flutter SDK launcher, NOT the Tkinter DE.
        launcher = (ROOT / "ui" / "launch_gui.py").read_text(encoding="utf-8")
        self.assertIn("flutter", launcher.lower())
        self.assertNotIn("import tkinter", launcher)
        self.assertNotIn("from tkinter", launcher)


if __name__ == "__main__":
    unittest.main()
