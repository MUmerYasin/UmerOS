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

"""End-to-end boot smoke test for the documented non-interactive entry point.

The individual kernel subsystems are unit-tested, but nothing exercised
``UmerKernel.boot()`` from start to finish — so two fatal bugs sat on the
primary entry point undetected:

* ``self.vfs.mkdir("/tmp")`` raised ``FileExistsError`` because the VFS
  constructor had already created ``/tmp``;
* ``self.crypto.decrypt(nonce, ciphertext)`` passed two arguments to a method
  that unpacks ``(nonce, ciphertext)`` from one.

Both killed ``python main.py`` on every run while the suite stayed green.  This
test runs the real entry point in a subprocess with stdin closed (so the shell
receives EOF and the kernel shuts down gracefully) and asserts a clean exit.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

_BOOT_TIMEOUT_S = 180


def test_non_interactive_boot_runs_to_completion():
    """`python -m boot.init --accept-eula` must boot, idle, and exit 0."""
    result = subprocess.run(
        [sys.executable, "-m", "boot.init", "--accept-eula"],
        cwd=str(_ROOT),
        stdin=subprocess.DEVNULL,     # immediate EOF -> shell requests shutdown
        capture_output=True,
        text=True,
        timeout=_BOOT_TIMEOUT_S,
    )

    assert "Traceback" not in result.stderr, (
        "boot raised an unhandled exception:\n" + result.stderr[-4000:]
    )
    assert result.returncode == 0, (
        f"boot exited {result.returncode}\n"
        f"--- stdout tail ---\n{result.stdout[-2000:]}\n"
        f"--- stderr tail ---\n{result.stderr[-2000:]}"
    )

    out = result.stdout
    # Checkpoints across the boot sequence, in order.
    for marker in (
        "[KERNEL] Boot sequence initiated.",
        "[QFS] Mounted at /",
        "[KERNEL] Crypto round-trip verification: PASS",
        "[KERNEL] Entering main execution loop...",
    ):
        assert marker in out, f"boot never reached: {marker}"


def test_boot_wires_the_capability_gate_and_detaches_on_shutdown():
    """H113 end-to-end: the running kernel must enforce, then release the gate."""
    probe = (
        "import asyncio, sys;"
        "from core.capability_gate import gate;"
        "from kernel.umer_kernel import UmerKernel;"
        "k = UmerKernel();"
        "assert gate.enforcing, 'gate not wired after construction';"
        "assert gate.principal == 0, 'kernel is not the system principal';"
        "asyncio.run(k.shutdown());"
        "assert not gate.enforcing, 'gate still enforcing after shutdown';"
        "print('GATE_OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=str(_ROOT),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=_BOOT_TIMEOUT_S,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-4000:]
    assert "GATE_OK" in result.stdout
