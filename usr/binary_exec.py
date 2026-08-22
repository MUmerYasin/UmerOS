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

"""
UmerOS Binary Execution Manager
================================
Binary execution management under /usr/bin and /usr/sbin.

The /usr/bin and /usr/sbin directories contain essential command binaries:
  - /usr/bin  : Essential user command binaries (ls, cat, grep, etc.)
  - /usr/sbin : System administration binaries (sshd, iptables, etc.)

This module provides discovery, metadata management, and execution
tracking for binaries in the /usr hierarchy.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from enum import IntEnum
from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)


# ============================================================================
# Constants
# ============================================================================

DEFAULT_BIN_PATHS: List[str] = [
    "/usr/bin",
    "/usr/sbin",
    "/usr/local/bin",
    "/usr/local/sbin",
]

BINARY_MAGIC: Dict[str, str] = {
    "\x7fELF": "ELF",
    "#!": "SCRIPT",
    "MZ": "PE",
}


# ============================================================================
# Enums
# ============================================================================

class BinaryType(IntEnum):
    """Types of binaries."""
    UNKNOWN = 0
    ELF_EXECUTABLE = 1
    ELF_SHARED_LIB = 2
    ELF_POSITION_INDEP = 3
    SHELL_SCRIPT = 4
    PYTHON_SCRIPT = 5
    PERL_SCRIPT = 6
    RUBY_SCRIPT = 7
    PERL = 8
    SYMLINK = 9
    HARD_LINK = 10


class BinaryArch(IntEnum):
    """Binary architecture."""
    UNKNOWN = 0
    X86_64 = 1
    I386 = 2
    ARM = 3
    AARCH64 = 4
    RISCV64 = 5
    MIPS = 6
    PPC64 = 7
    S390X = 8
    SCRIPT = 9


class BinaryPermission(IntEnum):
    """Binary permission bits."""
    NONE = 0
    OWNER_READ = 1
    OWNER_WRITE = 2
    OWNER_EXEC = 4
    GROUP_READ = 8
    GROUP_WRITE = 16
    GROUP_EXEC = 32
    OTHER_READ = 64
    OTHER_WRITE = 128
    OTHER_EXEC = 256


class ExecutionState(IntEnum):
    """State of binary execution."""
    IDLE = 0
    LOADING = 1
    RUNNING = 2
    SUSPENDED = 3
    FINISHED = 4
    ERROR = 5


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class BinaryMetadata:
    """Metadata for a binary file."""
    name: str = ""
    path: str = ""
    binary_type: BinaryType = BinaryType.UNKNOWN
    architecture: BinaryArch = BinaryArch.UNKNOWN
    size_bytes: int = 0
    permissions: int = 0
    owner_uid: int = 0
    group_gid: int = 0
    modified_at: float = 0.0
    is_setuid: bool = False
    is_setgid: bool = False
    is_sticky: bool = False
    is_symlink: bool = False
    symlink_target: str = ""
    interpreter: str = ""
    description: str = ""
    version: str = ""
    dependencies: List[str] = field(default_factory=list)

    def is_executable(self) -> bool:
        """Check if the binary has execute permission."""
        return bool(self.permissions & stat.S_IXUSR)

    def is_system_binary(self) -> bool:
        """Check if the binary is a system binary."""
        return self.path.startswith("/usr/sbin")

    def has_setid(self) -> bool:
        """Check if the binary has setuid or setgid bit."""
        return self.is_setuid or self.is_setgid


@dataclass
class BinaryExecution:
    """Tracks a binary execution instance."""
    binary_name: str = ""
    binary_path: str = ""
    state: ExecutionState = ExecutionState.IDLE
    pid: int = 0
    return_code: Optional[int] = None
    start_time: float = 0.0
    end_time: float = 0.0
    argv: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    exit_signal: Optional[str] = None

    def is_running(self) -> bool:
        """Check if the binary is currently running."""
        return self.state == ExecutionState.RUNNING

    def duration_seconds(self) -> float:
        """Get execution duration in seconds."""
        if self.end_time > 0 and self.start_time > 0:
            return self.end_time - self.start_time
        return 0.0

    def success(self) -> bool:
        """Check if execution was successful."""
        return self.state == ExecutionState.FINISHED and self.return_code == 0


@dataclass
class BinaryIndex:
    """Index entry for a binary."""
    name: str = ""
    path: str = ""
    metadata: Optional[BinaryMetadata] = None
    alias_for: Optional[str] = None


# ============================================================================
# Binary Exec Manager
# ============================================================================

class BinaryExecManager:
    """
    Manages binary execution under /usr/bin and /usr/sbin.

    Provides discovery, metadata tracking, and execution management
    for system binaries.
    """

    def __init__(self) -> None:
        self._bin_paths: List[str] = list(DEFAULT_BIN_PATHS)
        self._binaries: Dict[str, BinaryMetadata] = {}
        self._executions: List[BinaryExecution] = []
        self._aliases: Dict[str, str] = {}
        self._path_index: Dict[str, List[str]] = {}

    # -- Path Management --

    def add_bin_path(self, path: str) -> None:
        """Add a binary search path."""
        if path not in self._bin_paths:
            self._bin_paths.append(path)

    def get_bin_paths(self) -> List[str]:
        """Get all configured binary paths."""
        return list(self._bin_paths)

    # -- Scanning --

    def scan_binaries(self) -> int:
        """Scan binary directories and index all executables."""
        count = 0
        for bin_path in self._bin_paths:
            if not os.path.isdir(bin_path):
                continue
            count += self._scan_directory(bin_path)
        return count

    def _scan_directory(self, dirpath: str) -> int:
        """Scan a single binary directory."""
        count = 0
        try:
            for entry in os.scandir(dirpath):
                if entry.is_file() or entry.is_symlink():
                    metadata = self._analyze_binary(entry.path, entry.name)
                    if metadata:
                        self._binaries[entry.name] = metadata
                        self._path_index.setdefault(entry.name, []).append(
                            entry.path
                        )
                        count += 1
        except (OSError, PermissionError):
            pass
        return count

    def _analyze_binary(self, filepath: str, name: str) -> Optional[BinaryMetadata]:
        """Analyze a binary file and extract metadata."""
        try:
            st = os.stat(filepath)
        except OSError:
            return None

        metadata = BinaryMetadata(
            name=name,
            path=filepath,
            size_bytes=st.st_size,
            permissions=st.st_mode & 0o7777,
            owner_uid=st.st_uid,
            group_gid=st.st_gid,
            modified_at=st.st_mtime,
            is_setuid=bool(st.st_mode & stat.S_ISUID),
            is_setgid=bool(st.st_mode & stat.S_ISGID),
            is_sticky=bool(st.st_mode & stat.S_ISVTX),
            is_symlink=os.path.islink(filepath),
        )

        if metadata.is_symlink:
            try:
                metadata.symlink_target = os.readlink(filepath)
            except OSError:
                pass

        metadata.binary_type = self._detect_binary_type(filepath, metadata)
        metadata.architecture = self._detect_architecture(filepath)

        return metadata

    def _detect_binary_type(self, filepath: str, metadata: BinaryMetadata) -> BinaryType:
        """Detect the type of a binary."""
        if metadata.is_symlink:
            return BinaryType.SYMLINK
        try:
            with open(filepath, "rb") as f:
                header = f.read(16)
        except (OSError, IOError):
            return BinaryType.UNKNOWN
        if header[:4] == b"\x7fELF":
            ei_type = header[4] if len(header) > 4 else 0
            ei_class = header[5] if len(header) > 5 else 0
            if ei_type == 3:
                if ei_class == 1:
                    return BinaryType.ELF_POSITION_INDEP
                return BinaryType.ELF_EXECUTABLE
            if ei_type == 3:
                return BinaryType.ELF_SHARED_LIB
            return BinaryType.ELF_EXECUTABLE
        if header[:2] == b"#!":
            try:
                shebang = header.decode("utf-8", errors="replace").split("\n")[0]
                if "python" in shebang:
                    return BinaryType.PYTHON_SCRIPT
                if "perl" in shebang:
                    return BinaryType.PERL_SCRIPT
                if "ruby" in shebang:
                    return BinaryType.RUBY_SCRIPT
                return BinaryType.SHELL_SCRIPT
            except Exception:
                return BinaryType.SHELL_SCRIPT
        return BinaryType.UNKNOWN

    def _detect_architecture(self, filepath: str) -> BinaryArch:
        """Detect architecture of an ELF binary."""
        try:
            with open(filepath, "rb") as f:
                header = f.read(20)
        except (OSError, IOError):
            return BinaryArch.UNKNOWN
        if header[:4] != b"\x7fELF":
            return BinaryArch.SCRIPT
        ei_machine = header[18] if len(header) > 18 else 0
        ei_class = header[5] if len(header) > 5 else 0
        if ei_machine == 0x03:
            return BinaryArch.I386
        if ei_machine == 0x3E:
            return BinaryArch.X86_64
        if ei_machine == 0x28:
            return BinaryArch.ARM
        if ei_machine == 0xB7:
            return BinaryArch.AARCH64
        if ei_machine == 0xF3:
            return BinaryArch.RISCV64
        if ei_machine == 0x08:
            return BinaryArch.MIPS
        if ei_machine == 0x15:
            return BinaryArch.PPC64
        if ei_machine == 0x16:
            return BinaryArch.S390X
        return BinaryArch.UNKNOWN

    # -- Binary Access --

    def get_binary(self, name: str) -> Optional[BinaryMetadata]:
        """Get binary metadata by name."""
        return self._binaries.get(name)

    def get_binary_by_path(self, path: str) -> Optional[BinaryMetadata]:
        """Get binary metadata by full path."""
        for metadata in self._binaries.values():
            if metadata.path == path:
                return metadata
        return None

    def find_binary(self, name: str) -> List[BinaryMetadata]:
        """Find all binaries matching a name."""
        results: List[BinaryMetadata] = []
        for metadata in self._binaries.values():
            if metadata.name == name:
                results.append(metadata)
        return results

    def list_binaries(
        self,
        bin_type: Optional[BinaryType] = None,
        system_only: bool = False,
    ) -> List[BinaryMetadata]:
        """List all binaries with optional filtering."""
        results: List[BinaryMetadata] = []
        for metadata in self._binaries.values():
            if bin_type is not None and metadata.binary_type != bin_type:
                continue
            if system_only and not metadata.is_system_binary():
                continue
            results.append(metadata)
        return results

    def list_executables(self) -> List[BinaryMetadata]:
        """List all executable binaries."""
        return [
            m for m in self._binaries.values()
            if m.is_executable()
        ]

    # -- Search --

    def search_by_type(self, bin_type: BinaryType) -> List[BinaryMetadata]:
        """Find binaries by type."""
        return [m for m in self._binaries.values() if m.binary_type == bin_type]

    def search_scripts(self) -> List[BinaryMetadata]:
        """Find all script files."""
        script_types = {
            BinaryType.SHELL_SCRIPT,
            BinaryType.PYTHON_SCRIPT,
            BinaryType.PERL_SCRIPT,
            BinaryType.RUBY_SCRIPT,
        }
        return [
            m for m in self._binaries.values()
            if m.binary_type in script_types
        ]

    def search_by_architecture(self, arch: BinaryArch) -> List[BinaryMetadata]:
        """Find binaries by architecture."""
        return [
            m for m in self._binaries.values()
            if m.architecture == arch
        ]

    def search_setuid(self) -> List[BinaryMetadata]:
        """Find all setuid binaries."""
        return [m for m in self._binaries.values() if m.has_setid()]

    def search_name_prefix(self, prefix: str) -> List[BinaryMetadata]:
        """Find binaries whose names start with a prefix."""
        return [
            m for m in self._binaries.values()
            if m.name.startswith(prefix)
        ]

    # -- Alias Management --

    def add_alias(self, alias: str, target: str) -> None:
        """Add a binary alias."""
        self._aliases[alias] = target

    def get_alias_target(self, alias: str) -> Optional[str]:
        """Resolve an alias to its target binary."""
        return self._aliases.get(alias)

    def list_aliases(self) -> Dict[str, str]:
        """List all aliases."""
        return dict(self._aliases)

    # -- Execution Tracking --

    def start_execution(
        self,
        binary_name: str,
        argv: Optional[List[str]] = None,
        environment: Optional[Dict[str, str]] = None,
    ) -> BinaryExecution:
        """Start tracking a binary execution."""
        execution = BinaryExecution(
            binary_name=binary_name,
            state=ExecutionState.RUNNING,
            argv=argv or [binary_name],
            environment=environment or {},
        )
        self._executions.append(execution)
        return execution

    def finish_execution(
        self,
        execution: BinaryExecution,
        return_code: int = 0,
        exit_signal: Optional[str] = None,
    ) -> None:
        """Mark an execution as finished."""
        execution.state = ExecutionState.FINISHED
        execution.return_code = return_code
        execution.exit_signal = exit_signal

    def get_executions(
        self,
        binary_name: Optional[str] = None,
    ) -> List[BinaryExecution]:
        """Get execution history."""
        if binary_name:
            return [
                e for e in self._executions
                if e.binary_name == binary_name
            ]
        return list(self._executions)

    def get_recent_executions(self, count: int = 10) -> List[BinaryExecution]:
        """Get the most recent executions."""
        return self._executions[-count:]

    # -- Utility --

    def binary_count(self) -> int:
        """Get total number of indexed binaries."""
        return len(self._binaries)

    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about indexed binaries."""
        stats: Dict[str, int] = {
            "total_binaries": self.binary_count(),
            "total_aliases": len(self._aliases),
            "total_executions": len(self._executions),
        }
        for bt in BinaryType:
            stats[f"type_{bt.name}"] = len(self.search_by_type(bt))
        for ba in BinaryArch:
            stats[f"arch_{ba.name}"] = len(self.search_by_architecture(ba))
        return stats

    def clear(self) -> None:
        """Clear all indexed data."""
        self._binaries.clear()
        self._executions.clear()
        self._aliases.clear()
        self._path_index.clear()


# ============================================================================
# Global Singleton
# ============================================================================

_global_binary_exec: Optional[BinaryExecManager] = None


def get_global_binary_exec() -> BinaryExecManager:
    """Get or create the global BinaryExecManager instance."""
    global _global_binary_exec
    if _global_binary_exec is None:
        _global_binary_exec = BinaryExecManager()
    return _global_binary_exec
