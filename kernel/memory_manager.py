class MemoryManager:
    def __init__(self, total_ram_mb=4096):
        self.total_ram = total_ram_mb
        self.allocated = {}

    def allocate(self, pid, size_mb):
        allocated_total = sum(self.allocated.values())
        if allocated_total + size_mb > self.total_ram:
            print(f"[OOM] Cannot allocate {size_mb}MB for PID {pid}")
            return False
        
        self.allocated[pid] = self.allocated.get(pid, 0) + size_mb
        return True

    def free(self, pid):
        if pid in self.allocated:
            del self.allocated[pid]
