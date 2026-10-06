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
Umer OS Boot Init  [TODAY]
====================
"""

from __future__ import annotations

import sys
import platform
import asyncio
from kernel.umer_kernel import UmerKernel

class Bootloader:
    def __init__(self):
        self.os_name = "Umer OS"
        self.version = "2.0.0-Quantum"
        
    def display_waiver(self, accept_eula: bool = False):
        print("="*60)
        print(f"               WELCOME TO {self.os_name}               ")
        print("="*60)
        print("WARNING: You are booting a highly experimental, AI-orchestrated")
        print("hybrid operating system. This software acts as a hypervisor and")
        print("has the capability to modify hardware states and manage resources.")
        print("By proceeding, you assume ALL legal and technical liability.")
        print("="*60)

        # [FIX H29] Fail-closed consent for the §4.2 installer legal mandate.
        # The prior code silently auto-accepted the EULA in non-TTY mode
        # ("[Non-interactive mode: Auto-accepting waiver for tests]"), which
        # bypassed the "no silent accept" rule. Consent is now granted ONLY via:
        #   (a) an explicit interactive "I AGREE" typed at a real TTY, or
        #   (b) an explicit opt-in flag (``accept_eula=True`` / ``--accept-eula``
        #       passed to boot()), i.e. a signed/recorded consent token.
        # Any non-interactive run without explicit opt-in is ABORTED — never
        # silently booted. This mirrors the installer EULA mandate and the
        # project-wide zero-trust "default-deny" convention (H17/H27/H28 family).
        if accept_eula:
            print("[Waiver accepted via explicit opt-in flag]")
            return

        if sys.stdin.isatty():
            # [FIX] ``isatty()`` can report True for a stdin that is nonetheless
            # unreadable — the Windows NUL device, a TTY whose peer has closed,
            # or Ctrl-C (KeyboardInterrupt). Previously that let EOFError escape
            # as an unhandled traceback from `python main.py`. Treat "could not
            # read an answer" as the non-interactive case and fail closed
            # through the shared message below.
            try:
                response = input("Type 'I AGREE' to boot: ")
            except (EOFError, KeyboardInterrupt):
                response = ""
            if response.strip() == "I AGREE":
                return
            if response.strip():
                print("Boot aborted.")
                sys.exit(1)

        # Non-interactive and no explicit opt-in: fail-closed — do NOT boot.
        print(
            "Boot aborted: non-interactive boot requires explicit consent. "
            "Pass --accept-eula (or call boot(accept_eula=True))."
        )
        sys.exit(1)

    def check_hardware(self):
        print(f"[BOOT] Checking hardware...")
        print(f"[BOOT] Architecture: {platform.machine()}")
        print(f"[BOOT] OS Platform: {platform.system()} {platform.release()}")
        # [FIX H32] The C hardware layer (boot/uefi_stub.c) is a non-functional
        # placeholder with NO ctypes binding — do not claim UEFI init happened.
        print("[BOOT] UEFI hardware layer not wired (placeholder scaffold only)")
        
    async def load_kernel(self, exit_after_boot: bool = False):
        print("[BOOT] Handing off to Umer Microkernel...")
        kernel = UmerKernel()
        await kernel.boot(exit_after_boot=exit_after_boot)

def boot(accept_eula: bool = False, exit_after_boot: bool = False):
    """Boot UmerOS.

    Args:
        accept_eula:     Record explicit consent to the liability waiver and
            skip the interactive prompt. Required when stdin is not a TTY —
            without it the boot aborts fail-closed.
        exit_after_boot: Shut down once boot completes instead of idling. Use
            for CI / verification runs that need a deterministic exit; an
            ordinary headless run stays up until SIGINT/SIGTERM.
    """
    loader = Bootloader()
    loader.display_waiver(accept_eula=accept_eula)
    loader.check_hardware()
    asyncio.run(loader.load_kernel(exit_after_boot=exit_after_boot))

if __name__ == "__main__":
    # [FIX H29] Explicit opt-in flag for non-interactive boot consent.
    # No flag (and no TTY) => display_waiver() fails-closed and aborts.
    _accept = "--accept-eula" in sys.argv[1:]
    _exit_after = "--exit-after-boot" in sys.argv[1:]
    boot(accept_eula=_accept, exit_after_boot=_exit_after)