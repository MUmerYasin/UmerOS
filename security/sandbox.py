import hashlib
from dataclasses import dataclass, field
from typing import Dict, Set


@dataclass
class ProcessRecord:
    pid: int
    name: str
    permissions: Set[str] = field(default_factory=set)


class SecuritySandbox:
    def __init__(self):
        self.processes: Dict[int, ProcessRecord] = {}

    def register_process(self, pid: int, name: str):
        self.processes[pid] = ProcessRecord(pid=pid, name=name, permissions={"read"})

    def verify_process(self, pid: int, signature: str) -> bool:
        expected = hashlib.sha3_512(f"{pid}".encode()).hexdigest()
        return signature == expected

    def allow(self, pid: int, permission: str) -> bool:
        if pid not in self.processes:
            return False
        return permission in self.processes[pid].permissions