from .syscall_shim import SyscallShim

class ZeroTrustContainer:
    def __init__(self, container_id, capability_manager):
        self.container_id = container_id
        self.capabilities = capability_manager
        self.shim = SyscallShim()
        self.running = False

    def execute_binary(self, binary_path, os_type="linux"):
        print(f"[Container {self.container_id}] Initializing zero-trust sandbox for {os_type.upper()} binary: {binary_path}")
        if not self.capabilities.check(self.container_id, "HARDWARE"):
            print(f"[Container {self.container_id}] Restricting direct hardware access.")
        
        self.running = True
        
        # Simulating binary execution calling a legacy syscall
        if os_type == "linux":
            self.shim.intercept("sys_read", 0, 1024)
        elif os_type == "windows":
            self.shim.intercept("NtCreateFile", "C:\\temp.txt")

        print(f"[Container {self.container_id}] Binary execution complete.")
        self.running = False