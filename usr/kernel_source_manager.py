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
UmerOS Kernel Source Manager (/usr/src/)
====================================================
Kernel source code, headers, and build configuration.

Reference: Filesystem Hierarchy - /usr/src/
  /usr/src/ contains the source code for the kernel.

  Key files:
  - .config           - Last kernel source configuration
  - .depend/.hdepend  - Dependency files from 'make dep'
  - COPYING           - GNU License
  - CREDITS           - Contributors file
  - MAINTAINERS       - List of maintainers
  - Makefile          - Build configuration
  - README            - Release notes
  - REPORTING-BUGS    - Bug reporting procedure
  - Rules.make        - Shared Makefile rules
  - Documentation/    - Kernel documentation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional


# ─── Constants ───────────────────────────────────────────────────────────────

KERNEL_SOURCE_PATH = "/usr/src/"

KERNEL_FILES = {
    "config": ".config",
    "depend": ".depend",
    "hdepend": ".hdepend",
    "copying": "COPYING",
    "credits": "CREDITS",
    "maintainers": "MAINTAINERS",
    "makefile": "Makefile",
    "readme": "README",
    "reporting_bugs": "REPORTING-BUGS",
    "rules_make": "Rules.make",
}

KERNEL_CONFIG_OPTIONS = [
    "CONFIG_SMP", "CONFIG_PREEMPT", "CONFIG_HZ",
    "CONFIG_MODULES", "CONFIG_MODULE_UNLOAD",
    "CONFIG_EXT4_FS", "CONFIG_BTRFS", "CONFIG_XFS_FS",
    "CONFIG_NETFILTER", "CONFIG_IPV6",
    "CONFIG_USB", "CONFIG_BT", "CONFIG_WIRELESS",
    "CONFIG_DRM", "CONFIG_FB",
    "CONFIG_SOUND", "CONFIG_SND",
    "CONFIG_SECURITY_SELINUX", "CONFIG_SECURITY_APPARMOR",
    "CONFIG_CGROUPS", "CONFIG_NAMESPACES",
    "CONFIG_VIRT", "CONFIG_KVM",
]

DEFAULT_SUBSYSTEMS = [
    ("arch", "Architecture-specific code"),
    ("block", "Block layer"),
    ("crypto", "Cryptographic API"),
    ("Documentation", "Kernel documentation"),
    ("drivers", "Device drivers"),
    ("firmware", "Firmware files"),
    ("fs", "Filesystems"),
    ("include", "Kernel headers"),
    ("init", "Kernel initialization"),
    ("ipc", "Inter-process communication"),
    ("kernel", "Core kernel"),
    ("lib", "Library routines"),
    ("mm", "Memory management"),
    ("net", "Networking"),
    ("samples", "Sample code"),
    ("scripts", "Build scripts"),
    ("security", "Security modules"),
    ("sound", "Sound subsystem"),
    ("tools", "Utility tools"),
    ("usr", "Early userspace support"),
    ("virt", "Virtualization support"),
]


# ─── Enums ───────────────────────────────────────────────────────────────────

class KernelSubsystem(IntEnum):
    """Kernel subsystems."""
    ARCH = 1
    BLOCK = 2
    CRYPTO = 3
    DOCUMENTATION = 4
    DRIVERS = 5
    FIRMWARE = 6
    FS = 7
    INCLUDE = 8
    INIT = 9
    IPC = 10
    KERNEL = 11
    LIB = 12
    MM = 13
    NET = 14
    SAMPLES = 15
    SCRIPTS = 16
    SECURITY = 17
    SOUND = 18
    TOOLS = 19
    USR = 20
    VIRT = 21


class KernelConfigStatus(IntEnum):
    """Kernel configuration status."""
    ENABLED = 1
    DISABLED = 2
    MODULE = 3
    NOT_SET = 4


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class KernelConfig:
    """A kernel configuration option."""
    name: str
    value: str = ""
    status: KernelConfigStatus = KernelConfigStatus.NOT_SET
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "value": self.value,
            "status": self.status.name, "description": self.description,
        }


@dataclass
class KernelSubsystemEntry:
    """A kernel subsystem definition."""
    name: str
    path: str
    description: str = ""
    files_count: int = 0
    subsystem: KernelSubsystem = KernelSubsystem.KERNEL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "path": self.path,
            "description": self.description, "files_count": self.files_count,
            "subsystem": self.subsystem.name,
        }


@dataclass
class KernelVersion:
    """Kernel version information."""
    major: int = 0
    minor: int = 0
    patch: int = 0
    sublevel: int = 0
    extra: str = ""

    def to_string(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.sublevel > 0:
            base += f".{self.sublevel}"
        if self.extra:
            base += f"-{self.extra}"
        return base

    def to_dict(self) -> Dict[str, Any]:
        return {
            "major": self.major, "minor": self.minor,
            "patch": self.patch, "sublevel": self.sublevel,
            "extra": self.extra, "string": self.to_string(),
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_kernel_manager: Optional["KernelSourceManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class KernelSourceManager:
    """Manages /usr/src/ kernel sources."""

    def __init__(self) -> None:
        self._configs: Dict[str, KernelConfig] = {}
        self._subsystems: Dict[str, KernelSubsystemEntry] = {}
        self._version = KernelVersion(major=6, minor=8, patch=0)
        self._initialize_default_configs()
        self._initialize_subsystems()

    def _initialize_default_configs(self) -> None:
        defaults = [
            ("CONFIG_SMP", "y", KernelConfigStatus.ENABLED, "Symmetric multiprocessing"),
            ("CONFIG_PREEMPT", "y", KernelConfigStatus.ENABLED, "Preemptible kernel"),
            ("CONFIG_HZ", "1000", KernelConfigStatus.ENABLED, "Timer frequency"),
            ("CONFIG_MODULES", "y", KernelConfigStatus.ENABLED, "Loadable module support"),
            ("CONFIG_MODULE_UNLOAD", "y", KernelConfigStatus.ENABLED, "Module unloading"),
            ("CONFIG_EXT4_FS", "y", KernelConfigStatus.ENABLED, "Ext4 filesystem"),
            ("CONFIG_BTRFS_FS", "m", KernelConfigStatus.MODULE, "Btrfs filesystem"),
            ("CONFIG_XFS_FS", "y", KernelConfigStatus.ENABLED, "XFS filesystem"),
            ("CONFIG_NETFILTER", "y", KernelConfigStatus.ENABLED, "Netfilter support"),
            ("CONFIG_IPV6", "y", KernelConfigStatus.ENABLED, "IPv6 support"),
            ("CONFIG_USB", "y", KernelConfigStatus.ENABLED, "USB support"),
            ("CONFIG_BT", "m", KernelConfigStatus.MODULE, "Bluetooth support"),
            ("CONFIG_WIRELESS", "y", KernelConfigStatus.ENABLED, "Wireless support"),
            ("CONFIG_DRM", "y", KernelConfigStatus.ENABLED, "Direct Rendering Manager"),
            ("CONFIG_FB", "y", KernelConfigStatus.ENABLED, "Frame buffer support"),
            ("CONFIG_SOUND", "y", KernelConfigStatus.ENABLED, "Sound support"),
            ("CONFIG_SECURITY_SELINUX", "y", KernelConfigStatus.ENABLED, "SELinux support"),
            ("CONFIG_SECURITY_APPARMOR", "y", KernelConfigStatus.ENABLED, "AppArmor support"),
            ("CONFIG_CGROUPS", "y", KernelConfigStatus.ENABLED, "Control groups"),
            ("CONFIG_NAMESPACES", "y", KernelConfigStatus.ENABLED, "Namespaces support"),
            ("CONFIG_VIRT", "y", KernelConfigStatus.ENABLED, "Virtualization support"),
            ("CONFIG_KVM", "m", KernelConfigStatus.MODULE, "KVM virtualization"),
        ]
        for name, value, status, desc in defaults:
            self._configs[name] = KernelConfig(name=name, value=value, status=status, description=desc)

    def _initialize_subsystems(self) -> None:
        for name, desc in DEFAULT_SUBSYSTEMS:
            self._subsystems[name] = KernelSubsystemEntry(
                name=name, path=f"{KERNEL_SOURCE_PATH}/{name}",
                description=desc,
            )

    def get_config(self, name: str) -> Optional[KernelConfig]:
        return self._configs.get(name)

    def list_configs(self, status: Optional[KernelConfigStatus] = None) -> List[KernelConfig]:
        configs = list(self._configs.values())
        if status is not None:
            configs = [c for c in configs if c.status == status]
        return sorted(configs, key=lambda c: c.name)

    def set_config(self, name: str, value: str, status: KernelConfigStatus) -> None:
        self._configs[name] = KernelConfig(name=name, value=value, status=status)

    def get_subsystem(self, name: str) -> Optional[KernelSubsystemEntry]:
        return self._subsystems.get(name)

    def list_subsystems(self) -> List[KernelSubsystemEntry]:
        return sorted(self._subsystems.values(), key=lambda s: s.name)

    def get_version(self) -> KernelVersion:
        return self._version

    def set_version(self, version: KernelVersion) -> None:
        self._version = version

    def get_statistics(self) -> Dict[str, Any]:
        by_status: Dict[str, int] = {}
        for c in self._configs.values():
            s = c.status.name
            by_status[s] = by_status.get(s, 0) + 1
        return {
            "total_configs": len(self._configs),
            "total_subsystems": len(self._subsystems),
            "by_status": by_status,
            "version": self._version.to_string(),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self._version.to_dict(),
            "configs": {k: v.to_dict() for k, v in self._configs.items()},
            "subsystems": {k: v.to_dict() for k, v in self._subsystems.items()},
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_kernel_manager() -> KernelSourceManager:
    global _global_kernel_manager
    if _global_kernel_manager is None:
        _global_kernel_manager = KernelSourceManager()
    return _global_kernel_manager


def initialize() -> KernelSourceManager:
    return get_global_kernel_manager()


def refresh() -> KernelSourceManager:
    global _global_kernel_manager
    _global_kernel_manager = KernelSourceManager()
    return _global_kernel_manager
