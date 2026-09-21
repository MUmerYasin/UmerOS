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

"""Zero-trust, hardware-gated container for the Linux/Android compat path.

``ZeroTrustContainer`` runs a *single* foreign/legacy binary and enforces the
``HARDWARE`` capability (fail-closed - see before executing it,
then translates the binary's syscalls through ``SyscallShim``. It is the
hardware-access execution path and is intentionally distinct from
``ContainerEngine`` (in ``container_engine``), which is the general
foreign-binary compatibility launcher enforcing ``container.launch`` instead.
The two are complementary zero-trust paths; do not merge their capability
gates or syscall shims.
"""

from __future__ import annotations

import logging

from .syscall_shim import SyscallShim

log = logging.getLogger("UmerOS.Compat.Container")


# [TODAY] Universal Compatibility Layer - zero-trust foreign-binary container (H53 baseline).

class ZeroTrustContainer:
    def __init__(self, container_id, capability_manager):
        """Create a zero-trust container bound to a capability manager.

        Args:
            container_id: Opaque identifier used in audit logs and capability
                queries for this container.
            capability_manager: Manager exposing ``query(cap)`` used to gate
                binary execution in a fail-closed manner.

        Returns:
            None
        """
        self.container_id = container_id
        self.capabilities = capability_manager
        self.shim = SyscallShim()
        self.running = False

    def execute_binary(self, binary_path, os_type="linux"):
        """Execute a foreign binary inside the zero-trust container.

        Execution is DENIED unless the container holds the ``HARDWARE``
        capability (fail-closed). When permitted, the requested legacy syscalls
        are translated through the syscall shim.

        Args:
            binary_path: Path or identifier of the binary to run.
            os_type: Target OS family, either ``"linux"`` or ``"windows"``.

        Returns:
            ``True`` if execution was permitted and completed, ``False`` if it
            was denied by the capability gate.
        """
        # [FIX H51] Fail-closed: execution is denied unless the container holds
        # the required capability; the capability result now gates execution
        # (it no longer merely prints and runs).
        if not self.capabilities.query(self.container_id, "HARDWARE"):
            log.warning(
                "[Container %s] DENIED binary execution: missing 'HARDWARE' capability.",
                self.container_id,
            )
            return False

        log.info(
            "[Container %s] Initializing zero-trust sandbox for %s binary: %s",
            self.container_id, os_type.upper(), binary_path,
        )
        self.running = True

        # Hardware access is permitted (capability held) - perform the syscalls
        if os_type == "linux":
            self.shim.intercept("sys_read", 0, 1024)
        elif os_type == "windows":
            self.shim.intercept("NtCreateFile", "C:\\temp.txt")

        log.info("[Container %s] Binary execution complete.", self.container_id)
        self.running = False
        return True
