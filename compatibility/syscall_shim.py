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
