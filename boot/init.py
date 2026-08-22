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
        
    def display_waiver(self):
        print("="*60)
        print(f"               WELCOME TO {self.os_name}               ")
        print("="*60)
        print("WARNING: You are booting a highly experimental, AI-orchestrated")
        print("hybrid operating system. This software acts as a hypervisor and")
        print("has the capability to modify hardware states and manage resources.")
        print("By proceeding, you assume ALL legal and technical liability.")
        print("="*60)
        
        if sys.stdin.isatty():
            response = input("Type 'I AGREE' to boot: ")
            if response.strip() != "I AGREE":
                print("Boot aborted.")
                sys.exit(1)
        else:
            print("[Non-interactive mode: Auto-accepting waiver for tests]")

    def check_hardware(self):
        print(f"[BOOT] Checking hardware...")
        print(f"[BOOT] Architecture: {platform.machine()}")
        print(f"[BOOT] OS Platform: {platform.system()} {platform.release()}")
        print(f"[BOOT] Initializing UEFI stubs via ctypes (Simulated)")
        
    async def load_kernel(self):
        print("[BOOT] Handing off to Umer Microkernel...")
        kernel = UmerKernel()
        await kernel.boot()

def boot():
    loader = Bootloader()
    loader.display_waiver()
    loader.check_hardware()
    asyncio.run(loader.load_kernel())

if __name__ == "__main__":
    boot()