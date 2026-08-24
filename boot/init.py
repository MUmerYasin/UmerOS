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
            response = input("Type 'I AGREE' to boot: ")
            if response.strip() != "I AGREE":
                print("Boot aborted.")
                sys.exit(1)
            return

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
        print(f"[BOOT] Initializing UEFI stubs via ctypes (Simulated)")
        
    async def load_kernel(self):
        print("[BOOT] Handing off to Umer Microkernel...")
        kernel = UmerKernel()
        await kernel.boot()

def boot(accept_eula: bool = False):
    loader = Bootloader()
    loader.display_waiver(accept_eula=accept_eula)
    loader.check_hardware()
    asyncio.run(loader.load_kernel())

if __name__ == "__main__":
    # [FIX H29] Explicit opt-in flag for non-interactive boot consent.
    # No flag (and no TTY) => display_waiver() fails-closed and aborts.
    _accept = "--accept-eula" in sys.argv[1:]
    boot(accept_eula=_accept)