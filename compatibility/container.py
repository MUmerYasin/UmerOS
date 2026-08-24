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

import logging

from .syscall_shim import SyscallShim

log = logging.getLogger("UmerOS.Compat.Container")


class ZeroTrustContainer:
    def __init__(self, container_id, capability_manager):
        self.container_id = container_id
        self.capabilities = capability_manager
        self.shim = SyscallShim()
        self.running = False

    def execute_binary(self, binary_path, os_type="linux"):
        # [FIX H51] Zero-trust is FAIL-CLOSED. The previous code called
        # capabilities.check() only to *print* a message and then ran the
        # binary unconditionally — the capability result never gated
        # execution (fail-open), and the "hardware restriction" was cosmetic.
        # Now execution is DENIED unless the container holds the required
        # capability. query() is non-raising so denial is graceful.
        if not self.capabilities.query(self.container_id, "HARDWARE"):
            log.warning(
                "[Container %s] DENIED binary execution: missing 'HARDWARE' capability.",
                self.container_id,
            )
            return False

        print(f"[Container {self.container_id}] Initializing zero-trust sandbox for {os_type.upper()} binary: {binary_path}")
        self.running = True

        # Hardware access is permitted (capability held) — perform the syscalls
        if os_type == "linux":
            self.shim.intercept("sys_read", 0, 1024)
        elif os_type == "windows":
            self.shim.intercept("NtCreateFile", "C:\\temp.txt")

        print(f"[Container {self.container_id}] Binary execution complete.")
        self.running = False
        return True