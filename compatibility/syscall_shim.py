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

from __future__ import annotations

import logging

log = logging.getLogger("UmerOS.Compat.SyscallShim")

# [TODAY] Universal Compatibility Layer - legacy syscall translation shim (H53 baseline).

class SyscallShim:
    def __init__(self):
        """Build the syscall shim with a closed allow-list of translations.

        The ``syscall_table`` maps only trusted internal handlers (``_umer_*``)
        to legacy Linux/Windows syscall names. It is never extended with
        user-supplied callables, so ``intercept`` cannot be tricked into
        invoking arbitrary code.

        Returns:
            None
        """
        # Maps legacy Linux/Windows syscalls to Umer OS IPC messages
        self.syscall_table = {
            "sys_read": self._umer_read,
            "sys_write": self._umer_write,
            "NtCreateFile": self._umer_create_file
        }

    def intercept(self, syscall_name, *args):
        """Translate and dispatch a legacy syscall by allow-listed name.

        Args:
            syscall_name: Legacy syscall name (e.g. ``"sys_read"``), looked up
                in the closed ``syscall_table`` only.
            *args: Arguments forwarded to the matched handler.

        Returns:
            The handler's result, or ``None`` if the syscall is unimplemented.
        """
        log.info("[Syscall Shim] Intercepted legacy syscall: %s", syscall_name)
        handler = self.syscall_table.get(syscall_name)
        if handler is None:
            log.error("[Syscall Shim] Unimplemented syscall %s", syscall_name)
            return None
        return handler(*args)

    def _umer_read(self, fd, buffer_size):
        """Translate ``sys_read`` into a Umer IPC read.

        Args:
            fd: Source file descriptor.
            buffer_size: Maximum bytes to read.

        Returns:
            Simulated payload bytes.
        """
        log.info("  -> Translated to Umer IPC Read (FD: %s, Size: %s)", fd, buffer_size)
        return b"simulated_data"

    def _umer_write(self, fd, data):
        """Translate ``sys_write`` into a Umer IPC write.

        Args:
            fd: Destination file descriptor.
            data: Bytes to write.

        Returns:
            Number of bytes written (simulated).
        """
        log.info("  -> Translated to Umer IPC Write (FD: %s)", fd)
        return len(data)

    def _umer_create_file(self, filename):
        """Translate ``NtCreateFile`` into a Umer IPC create-file.

        Args:
            filename: Path or name of the file to create.

        Returns:
            Simulated file descriptor (``1``).
        """
        log.info("  -> Translated to Umer IPC CreateFile (Name: %s)", filename)
        return 1  # Simulated File Descriptor
