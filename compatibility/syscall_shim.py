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

class SyscallShim:
    def __init__(self):
        # Maps legacy Linux/Windows syscalls to Umer OS IPC messages
        self.syscall_table = {
            "sys_read": self._umer_read,
            "sys_write": self._umer_write,
            "NtCreateFile": self._umer_create_file
        }

    def intercept(self, syscall_name, *args):
        print(f"[Syscall Shim] Intercepted legacy syscall: {syscall_name}")
        if syscall_name in self.syscall_table:
            return self.syscall_table[syscall_name](*args)
        else:
            print(f"[Syscall Shim] ERROR: Unimplemented syscall {syscall_name}")
            return None

    def _umer_read(self, fd, buffer_size):
        print(f"  -> Translated to Umer IPC Read (FD: {fd}, Size: {buffer_size})")
        return b"simulated_data"

    def _umer_write(self, fd, data):
        print(f"  -> Translated to Umer IPC Write (FD: {fd})")
        return len(data)

    def _umer_create_file(self, filename):
        print(f"  -> Translated to Umer IPC CreateFile (Name: {filename})")
        return 1  # Simulated File Descriptor
