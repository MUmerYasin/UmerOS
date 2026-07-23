"""
Umer OS Control Groups (cgroups)
================================
Inspired by Linux cgroups, this subsystem provides resource partitioning
(CPU and Memory) for groups of tasks in the Umer OS kernel.
"""

import logging
from typing import Dict, List, Set, Optional

log = logging.getLogger("UmerOS.CGroup")

class CGroup:
    """A control group that limits resources for a set of tasks."""
    
    def __init__(self, name: str, cpu_limit_pct: float = 100.0, mem_limit_mb: int = 1024):
        self.name = name
        self.cpu_limit_pct = cpu_limit_pct  # Maximum CPU percentage allowed
        self.mem_limit_mb = mem_limit_mb    # Maximum Memory in MB allowed
        
        self.pids: Set[int] = set()
        
        # Track current usage
        self.current_cpu_pct = 0.0
        self.current_mem_mb = 0.0

    def add_task(self, pid: int) -> None:
        self.pids.add(pid)
        log.debug("Added PID %d to cgroup '%s'", pid, self.name)

    def remove_task(self, pid: int) -> None:
        if pid in self.pids:
            self.pids.remove(pid)
            log.debug("Removed PID %d from cgroup '%s'", pid, self.name)

    def can_allocate_memory(self, requested_mb: float) -> bool:
        """Check if allocating requested_mb exceeds the cgroup limit."""
        return (self.current_mem_mb + requested_mb) <= self.mem_limit_mb


class CGroupManager:
    """Manages all control groups in the system."""
    
    def __init__(self):
        self.cgroups: Dict[str, CGroup] = {}
        
        # Pre-create standard cgroups
        self.create_cgroup("system", cpu_limit_pct=100.0, mem_limit_mb=2048)
        self.create_cgroup("user", cpu_limit_pct=80.0, mem_limit_mb=1024)
        self.create_cgroup("ai_background", cpu_limit_pct=40.0, mem_limit_mb=512)
        
        # Map of PID -> cgroup name
        self.pid_map: Dict[int, str] = {}

    def create_cgroup(self, name: str, cpu_limit_pct: float, mem_limit_mb: int) -> CGroup:
        if name in self.cgroups:
            raise ValueError(f"CGroup '{name}' already exists.")
        
        cg = CGroup(name, cpu_limit_pct, mem_limit_mb)
        self.cgroups[name] = cg
        log.info("Created cgroup '%s' (CPU: %d%%, Mem: %d MB)", name, cpu_limit_pct, mem_limit_mb)
        return cg

    def assign_task(self, pid: int, cgroup_name: str) -> None:
        """Assign a task to a control group."""
        if cgroup_name not in self.cgroups:
            raise ValueError(f"Unknown cgroup: {cgroup_name}")
            
        # Remove from old if exists
        if pid in self.pid_map:
            old_cg = self.pid_map[pid]
            self.cgroups[old_cg].remove_task(pid)
            
        self.cgroups[cgroup_name].add_task(pid)
        self.pid_map[pid] = cgroup_name

    def remove_task(self, pid: int) -> None:
        """Remove a task from its cgroup."""
        if pid in self.pid_map:
            cg_name = self.pid_map.pop(pid)
            self.cgroups[cg_name].remove_task(pid)

    def check_memory_limit(self, pid: int, requested_bytes: int) -> bool:
        """Check if a task is allowed to allocate the requested memory."""
        cg_name = self.pid_map.get(pid)
        if not cg_name:
            return True # Not in a cgroup, allow it implicitly or apply a global default
            
        cg = self.cgroups[cg_name]
        requested_mb = requested_bytes / (1024 * 1024)
        return cg.can_allocate_memory(requested_mb)
