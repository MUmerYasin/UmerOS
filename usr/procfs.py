"""
UmerOS ProcFS Module
=====================
Kernel /proc filesystem interface.
Implements proc entries, read/write, and procfs hierarchy.

Reference: docs.kernel.org/userspace-api/proc.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import threading


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EINVAL: int = 22
ENOENT: int = 2
EACCES: int = 13
EISDIR: int = 21
ENOTDIR: int = 20


class ProcPerm(IntEnum):
    """Proc entry permissions."""
    PROC_PERM_READ: int = 0o444
    PROC_PERM_WRITE: int = 0o222
    PROC_PERM_RW: int = 0o666
    PROC_PERM_EXEC: int = 0o111
    PROC_PERM_WORLD: int = 0o777


class ProcEntryType(IntEnum):
    """Proc entry types."""
    PROC_ENTRY_FILE: int = 0
    PROC_ENTRY_DIR: int = 1
    PROC_ENTRY_LINK: int = 2
    PROC_ENTRY_FIFO: int = 3


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class ProcEntry:
    """A single /proc entry."""
    name: str = ""
    entry_type: ProcEntryType = ProcEntryType.PROC_ENTRY_FILE
    permissions: ProcPerm = ProcPerm.PROC_PERM_READ
    owner: int = 0
    group: int = 0
    size: int = 0
    data: bytes = b""
    read_handler: Optional[Callable[[], bytes]] = None
    write_handler: Optional[Callable[[bytes], int]] = None
    children: Dict[str, ProcEntry] = field(default_factory=dict)
    link_target: str = ""
    timestamp: float = 0.0

    def read(self) -> bytes:
        """Read from this entry."""
        if self.read_handler:
            return self.read_handler()
        return self.data

    def write(self, data: bytes) -> int:
        """Write to this entry."""
        if self.write_handler:
            return self.write_handler(data)
        self.data = data
        self.size = len(data)
        return SUCCESS

    def is_dir(self) -> bool:
        """Check if this is a directory entry."""
        return self.entry_type == ProcEntryType.PROC_ENTRY_DIR

    def is_file(self) -> bool:
        """Check if this is a file entry."""
        return self.entry_type == ProcEntryType.PROC_ENTRY_FILE

    def is_link(self) -> bool:
        """Check if this is a symlink."""
        return self.entry_type == ProcEntryType.PROC_ENTRY_LINK


@dataclass
class ProcPIDEntry:
    """Entry under /proc/[pid]/."""
    pid: int = 0
    entries: Dict[str, ProcEntry] = field(default_factory=dict)

    def add_entry(self, name: str, data: bytes) -> ProcEntry:
        """Add an entry for this PID."""
        entry = ProcEntry(name=name, data=data, size=len(data))
        self.entries[name] = entry
        return entry

    def read_entry(self, name: str) -> Optional[bytes]:
        """Read a PID entry."""
        entry = self.entries.get(name)
        if entry:
            return entry.read()
        return None

    def write_entry(self, name: str, data: bytes) -> int:
        """Write a PID entry."""
        entry = self.entries.get(name)
        if entry:
            return entry.write(data)
        return ENOENT


# ============================================================================
# ProcFS Filesystem
# ============================================================================

class ProcFS:
    """ /proc filesystem simulation."""
    root: ProcEntry = field(default_factory=lambda: ProcEntry(name="/", entry_type=ProcEntryType.PROC_ENTRY_DIR))
    pid_entries: Dict[int, ProcPIDEntry] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self._build_standard_entries()

    def _build_standard_entries(self) -> None:
        """Build standard /proc entries."""
        self.root.children["cpuinfo"] = ProcEntry(
            name="cpuinfo",
            data=b"processor\t: 0\nmodel name\t: UmerOS CPU\n",
            size=40,
        )
        self.root.children["meminfo"] = ProcEntry(
            name="meminfo",
            data=b"MemTotal:       16384000 kB\nMemFree:        8192000 kB\n",
            size=50,
        )
        self.root.children["version"] = ProcEntry(
            name="version",
            data=b"UmerOS version 1.0 (build 2026)",
            size=31,
        )
        self.root.children["uptime"] = ProcEntry(
            name="uptime",
            data=b"0.00 0.00",
            size=9,
        )
        self.root.children["loadavg"] = ProcEntry(
            name="loadavg",
            data=b"0.00 0.00 0.00 1/1 1",
            size=21,
        )
        self.root.children["filesystems"] = ProcEntry(
            name="filesystems",
            data=b"nodev\tsysfs\nnodev\tproc\nnodev\ttmpfs\n",
            size=40,
        )
        self.root.children["mounts"] = ProcEntry(
            name="mounts",
            data=b"rootfs / rootfs rw 0 0\nproc /proc proc rw,nosuid,nodev,noexec 0 0\n",
            size=60,
        )
        self.root.children["cmdline"] = ProcEntry(name="cmdline", data=b"", size=0)
        self.root.children["stat"] = ProcEntry(
            name="stat",
            data=b"cpu  0 0 0 0 0 0 0 0 0 0\n",
            size=25,
        )
        self.root.children["bus"] = ProcEntry(
            name="bus",
            entry_type=ProcEntryType.PROC_ENTRY_DIR,
        )
        self.root.children["sys"] = ProcEntry(
            name="sys",
            entry_type=ProcEntryType.PROC_ENTRY_DIR,
        )

    def create_pid_entry(self, pid: int) -> ProcPIDEntry:
        """Create /proc/[pid]/ directory."""
        with self.lock:
            entry = ProcPIDEntry(pid=pid)
            entry.add_entry("cmdline", b"")
            entry.add_entry("status", f"Name:\tprocess\nState:\tS (sleeping)\nPid:\t{pid}\n".encode())
            entry.add_entry("maps", b"")
            entry.add_entry("fd", b"")
            entry.add_entry("limits", b"Max open files\t1024\t1024\n")
            self.pid_entries[pid] = entry
        return entry

    def read(self, path: str) -> Optional[bytes]:
        """Read a proc entry by path."""
        parts = path.strip("/").split("/")
        if not parts or parts[0] != "proc":
            return None
        if len(parts) == 1:
            return b""
        if parts[1].isdigit():
            pid = int(parts[1])
            entry = self.pid_entries.get(pid)
            if entry and len(parts) > 2:
                return entry.read_entry(parts[2])
            return None
        entry = self.root.children.get(parts[1])
        if entry:
            return entry.read()
        return None

    def write(self, path: str, data: bytes) -> int:
        """Write to a proc entry by path."""
        parts = path.strip("/").split("/")
        if not parts or parts[0] != "proc":
            return EINVAL
        if len(parts) >= 3 and parts[1].isdigit():
            pid = int(parts[1])
            entry = self.pid_entries.get(pid)
            if entry:
                return entry.write_entry(parts[2], data)
            return ENOENT
        entry = self.root.children.get(parts[1]) if len(parts) > 1 else None
        if entry:
            return entry.write(data)
        return ENOENT

    def list_dir(self, path: str) -> List[str]:
        """List entries in a proc directory."""
        parts = path.strip("/").split("/")
        if not parts or parts[0] != "proc":
            return []
        if len(parts) == 1:
            entries = list(self.root.children.keys())
            entries.extend(str(p) for p in self.pid_entries.keys())
            return entries
        if parts[1].isdigit():
            pid = int(parts[1])
            entry = self.pid_entries.get(pid)
            if entry:
                return list(entry.keys())
            return []
        return list(self.root.children.keys())

    def add_entry(self, name: str, data: bytes, perms: ProcPerm = ProcPerm.PROC_PERM_READ) -> ProcEntry:
        """Add a custom entry."""
        entry = ProcEntry(name=name, permissions=perms, data=data, size=len(data))
        self.root.children[name] = entry
        return entry

    def remove_entry(self, name: str) -> int:
        """Remove an entry."""
        self.root.children.pop(name, None)
        return SUCCESS

    def statvfs(self) -> Dict[str, int]:
        """Get filesystem statistics."""
        return {
            "f_bsize": 4096,
            "f_blocks": 0,
            "f_bfree": 0,
            "f_bavail": 0,
            "f_files": len(self.root.children) + len(self.pid_entries),
            "f_ffree": 0,
        }


# ============================================================================
# Global Singleton Accessors
# ============================================================================

_global_procfs: Optional[ProcFS] = None


def get_global_procfs() -> ProcFS:
    """Get global ProcFS instance."""
    global _global_procfs
    if _global_procfs is None:
        _global_procfs = ProcFS()
    return _global_procfs
