class CapabilityManager:
    def __init__(self):
        # Capabilities: NET, FS_READ, FS_WRITE, HARDWARE
        self.permissions = {}

    def grant(self, pid, capability):
        if pid not in self.permissions:
            self.permissions[pid] = set()
        self.permissions[pid].add(capability)

    def revoke(self, pid, capability):
        if pid in self.permissions and capability in self.permissions[pid]:
            self.permissions[pid].remove(capability)

    def check(self, pid, capability):
        return pid in self.permissions and capability in self.permissions[pid]
