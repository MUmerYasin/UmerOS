"""
UmerOS System Administration Binaries Manager (/usr/sbin)
=========================================================
System administration programs meant to be run by root.

Reference: Linux Filesystem Hierarchy - /usr/sbin
  /usr/sbin contains programs for administering a system, meant to be
  run by 'root'. Like /sbin, it's not part of a user's $PATH.
  Examples: chroot, useradd, in.tftpd, pppconfig.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ─── Constants ───────────────────────────────────────────────────────────────

SBIN_PATHS = [
    "/usr/sbin",
    "/usr/local/sbin",
]

SBIN_CATEGORIES = {
    "NETWORKING": "Network configuration and management",
    "DISK": "Disk management and partitioning",
    "USER_MGMT": "User and group administration",
    "SERVICE": "Service and daemon management",
    "SYSTEM": "System configuration and maintenance",
    "SECURITY": "Security and authentication",
    "BACKUP": "Backup and restore utilities",
    "MONITORING": "System monitoring and diagnostics",
    "VIRTUALIZATION": "Virtualization management",
    "CONTAINER": "Container management",
}


# ─── Enums ───────────────────────────────────────────────────────────────────

class SbinCategory(IntEnum):
    """System administration binary categories."""
    NETWORKING = 1
    DISK = 2
    USER_MGMT = 3
    SERVICE = 4
    SYSTEM = 5
    SECURITY = 6
    BACKUP = 7
    MONITORING = 8
    VIRTUALIZATION = 9
    CONTAINER = 10
    UNKNOWN = 99


class SbinPrivilege(IntEnum):
    """Required privilege level."""
    ROOT = 0
    SUDO = 1
    WHEEL = 2
    SUPERVISOR = 3
    ANY = 4


class SbinStatus(IntEnum):
    """Binary status."""
    ACTIVE = 1
    DEPRECATED = 2
    REPLACED = 3
    REMOVED = 4
    BROKEN = 5


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class SbinBinary:
    """Represents a system administration binary."""
    name: str
    path: str
    category: SbinCategory = SbinCategory.UNKNOWN
    privilege: SbinPrivilege = SbinPrivilege.ROOT
    status: SbinStatus = SbinStatus.ACTIVE
    description: str = ""
    version: str = ""
    size: int = 0
    dependencies: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    man_page: str = ""
    config_files: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "category": self.category.name,
            "privilege": self.privilege.name,
            "status": self.status.name,
            "description": self.description,
            "version": self.version,
            "size": self.size,
            "dependencies": self.dependencies,
            "provides": self.provides,
            "man_page": self.man_page,
            "config_files": self.config_files,
            "aliases": self.aliases,
        }


@dataclass
class SbinGroup:
    """Group of related sbin binaries."""
    name: str
    category: SbinCategory
    description: str = ""
    binaries: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.name,
            "description": self.description,
            "binaries": self.binaries,
        }


# ─── Global State ────────────────────────────────────────────────────────────

_global_sbin_manager: Optional["SbinManager"] = None


# ─── Main Manager Class ─────────────────────────────────────────────────────

class SbinManager:
    """Manages /usr/sbin - system administration binaries."""

    def __init__(self) -> None:
        self._binaries: Dict[str, SbinBinary] = {}
        self._groups: Dict[str, SbinGroup] = {}
        self._custom_paths: List[str] = []
        self._initialize_default_binaries()
        self._initialize_default_groups()

    def _initialize_default_binaries(self) -> None:
        """Initialize with common sbin binaries."""
        default_bins = [
            ("chroot", "/usr/sbin/chroot", SbinCategory.SYSTEM, "Run command in chroot jail"),
            ("useradd", "/usr/sbin/useradd", SbinCategory.USER_MGMT, "Create a new user"),
            ("userdel", "/usr/sbin/userdel", SbinCategory.USER_MGMT, "Delete a user"),
            ("usermod", "/usr/sbin/usermod", SbinCategory.USER_MGMT, "Modify a user account"),
            ("groupadd", "/usr/sbin/groupadd", SbinCategory.USER_MGMT, "Create a new group"),
            ("groupdel", "/usr/sbin/groupdel", SbinCategory.USER_MGMT, "Delete a group"),
            ("groupmod", "/usr/sbin/groupmod", SbinCategory.USER_MGMT, "Modify a group"),
            ("passwd", "/usr/sbin/passwd", SbinCategory.SECURITY, "Change user password"),
            ("chpasswd", "/usr/sbin/chpasswd", SbinCategory.SECURITY, "Batch password change"),
            ("mount", "/usr/sbin/mount", SbinCategory.DISK, "Mount filesystems"),
            ("umount", "/usr/sbin/umount", SbinCategory.DISK, "Unmount filesystems"),
            ("fdisk", "/usr/sbin/fdisk", SbinCategory.DISK, "Partition table manipulator"),
            ("parted", "/usr/sbin/parted", SbinCategory.DISK, "Partition manipulation tool"),
            ("mkfs", "/usr/sbin/mkfs", SbinCategory.DISK, "Build a Linux filesystem"),
            ("fsck", "/usr/sbin/fsck", SbinCategory.DISK, "Filesystem consistency check"),
            ("tune2fs", "/usr/sbin/tune2fs", SbinCategory.DISK, "Adjust filesystem parameters"),
            ("ifconfig", "/usr/sbin/ifconfig", SbinCategory.NETWORKING, "Configure network interfaces"),
            ("ip", "/usr/sbin/ip", SbinCategory.NETWORKING, "Show/manipulate routing, devices"),
            ("iptables", "/usr/sbin/iptables", SbinCategory.NETWORKING, "Administration tool for IPv4 packet filtering"),
            ("ip6tables", "/usr/sbin/ip6tables", SbinCategory.NETWORKING, "Administration tool for IPv6 packet filtering"),
            ("sshd", "/usr/sbin/sshd", SbinCategory.NETWORKING, "OpenSSH daemon"),
            ("httpd", "/usr/sbin/httpd", SbinCategory.NETWORKING, "Apache HTTP server"),
            ("nginx", "/usr/sbin/nginx", SbinCategory.NETWORKING, "Nginx web server"),
            ("systemctl", "/usr/sbin/systemctl", SbinCategory.SERVICE, "Control the systemd system and service manager"),
            ("service", "/usr/sbin/service", SbinCategory.SERVICE, "Run a SystemV init script"),
            ("crond", "/usr/sbin/crond", SbinCategory.SERVICE, "Daemon to execute scheduled commands"),
            ("atd", "/usr/sbin/atd", SbinCategory.SERVICE, "Daemon for running jobs at scheduled times"),
            ("ntpd", "/usr/sbin/ntpd", SbinCategory.SERVICE, "NTP daemon"),
            ("sshd", "/usr/sbin/sshd", SbinCategory.SERVICE, "OpenSSH daemon"),
            ("rsyslogd", "/usr/sbin/rsyslogd", SbinCategory.SYSTEM, "Reliable system logging daemon"),
            ("syslogd", "/usr/sbin/syslogd", SbinCategory.SYSTEM, "System logging daemon"),
            ("dmesg", "/usr/sbin/dmesg", SbinCategory.MONITORING, "Print kernel ring buffer"),
            ("lsof", "/usr/sbin/lsof", SbinCategory.MONITORING, "List open files"),
            ("tcpdump", "/usr/sbin/tcpdump", SbinCategory.MONITORING, "Dump traffic on a network"),
            ("nmap", "/usr/sbin/nmap", SbinCategory.NETWORKING, "Network exploration and security auditing"),
            ("sudo", "/usr/sbin/sudo", SbinCategory.SECURITY, "Execute a command as another user"),
            ("su", "/usr/sbin/su", SbinCategory.SECURITY, "Run a command with substitute user"),
            ("visudo", "/usr/sbin/visudo", SbinCategory.SECURITY, "Edit the sudoers file"),
            ("pam", "/usr/sbin/pam", SbinCategory.SECURITY, "Pluggable Authentication Modules"),
            ("tar", "/usr/sbin/tar", SbinCategory.BACKUP, "GNU tar archiver"),
            ("dump", "/usr/sbin/dump", SbinCategory.BACKUP, "Ext2 filesystem backup"),
            ("restore", "/usr/sbin/restore", SbinCategory.BACKUP, "Restore files from a backup"),
            ("rsync", "/usr/sbin/rsync", SbinCategory.BACKUP, "Remote file sync"),
            ("docker", "/usr/sbin/docker", SbinCategory.CONTAINER, "Docker container engine"),
            ("podman", "/usr/sbin/podman", SbinCategory.CONTAINER, "Podman container engine"),
            ("lxc", "/usr/sbin/lxc", SbinCategory.CONTAINER, "Linux Containers"),
            ("virsh", "/usr/sbin/virsh", SbinCategory.VIRTUALIZATION, "Libvirt management tool"),
            ("qemu", "/usr/sbin/qemu", SbinCategory.VIRTUALIZATION, "QEMU emulator"),
        ]
        for name, path, cat, desc in default_bins:
            self._binaries[name] = SbinBinary(
                name=name, path=path, category=cat, description=desc
            )

    def _initialize_default_groups(self) -> None:
        """Initialize default sbin groups."""
        self._groups = {
            "user-mgmt": SbinGroup(
                name="user-mgmt", category=SbinCategory.USER_MGMT,
                description="User and group administration",
                binaries=["useradd", "userdel", "usermod", "groupadd", "groupdel", "groupmod"]
            ),
            "disk": SbinGroup(
                name="disk", category=SbinCategory.DISK,
                description="Disk management utilities",
                binaries=["mount", "umount", "fdisk", "parted", "mkfs", "fsck", "tune2fs"]
            ),
            "networking": SbinGroup(
                name="networking", category=SbinCategory.NETWORKING,
                description="Network configuration tools",
                binaries=["ifconfig", "ip", "iptables", "ip6tables", "sshd", "httpd", "nginx", "nmap"]
            ),
            "service": SbinGroup(
                name="service", category=SbinCategory.SERVICE,
                description="Service management",
                binaries=["systemctl", "service", "crond", "atd", "rsyslogd"]
            ),
            "security": SbinGroup(
                name="security", category=SbinCategory.SECURITY,
                description="Security and authentication",
                binaries=["sudo", "su", "visudo", "passwd", "chpasswd", "pam"]
            ),
            "backup": SbinGroup(
                name="backup", category=SbinCategory.BACKUP,
                description="Backup and restore",
                binaries=["tar", "dump", "restore", "rsync"]
            ),
            "container": SbinGroup(
                name="container", category=SbinCategory.CONTAINER,
                description="Container management",
                binaries=["docker", "podman", "lxc"]
            ),
            "virtualization": SbinGroup(
                name="virtualization", category=SbinCategory.VIRTUALIZATION,
                description="Virtualization tools",
                binaries=["virsh", "qemu"]
            ),
        }

    def add_custom_path(self, path: str) -> None:
        """Add a custom sbin search path."""
        if path not in self._custom_paths:
            self._custom_paths.append(path)

    def get_search_paths(self) -> List[str]:
        """Get all sbin search paths."""
        return SBIN_PATHS + self._custom_paths

    def register_binary(self, binary: SbinBinary) -> None:
        """Register a new sbin binary."""
        self._binaries[binary.name] = binary

    def get_binary(self, name: str) -> Optional[SbinBinary]:
        """Get a binary by name."""
        return self._binaries.get(name)

    def list_binaries(self, category: Optional[SbinCategory] = None) -> List[SbinBinary]:
        """List all binaries, optionally filtered by category."""
        bins = list(self._binaries.values())
        if category is not None:
            bins = [b for b in bins if b.category == category]
        return sorted(bins, key=lambda b: b.name)

    def search_binaries(self, query: str) -> List[SbinBinary]:
        """Search binaries by name or description."""
        query_lower = query.lower()
        results = []
        for binary in self._binaries.values():
            if (query_lower in binary.name.lower() or
                query_lower in binary.description.lower()):
                results.append(binary)
        return results

    def get_group(self, name: str) -> Optional[SbinGroup]:
        """Get a group by name."""
        return self._groups.get(name)

    def list_groups(self) -> List[SbinGroup]:
        """List all groups."""
        return sorted(self._groups.values(), key=lambda g: g.name)

    def get_binaries_by_privilege(self, privilege: SbinPrivilege) -> List[SbinBinary]:
        """Get binaries requiring a specific privilege level."""
        return [b for b in self._binaries.values() if b.privilege == privilege]

    def get_statistics(self) -> Dict[str, Any]:
        """Get sbin statistics."""
        by_category: Dict[str, int] = {}
        by_privilege: Dict[str, int] = {}
        for binary in self._binaries.values():
            cat_name = binary.category.name
            priv_name = binary.privilege.name
            by_category[cat_name] = by_category.get(cat_name, 0) + 1
            by_privilege[priv_name] = by_privilege.get(priv_name, 0) + 1
        return {
            "total_binaries": len(self._binaries),
            "total_groups": len(self._groups),
            "by_category": by_category,
            "by_privilege": by_privilege,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize manager to dictionary."""
        return {
            "search_paths": self.get_search_paths(),
            "binaries": {k: v.to_dict() for k, v in self._binaries.items()},
            "groups": {k: v.to_dict() for k, v in self._groups.items()},
            "statistics": self.get_statistics(),
        }


# ─── Singleton Getter ────────────────────────────────────────────────────────

def get_global_sbin_manager() -> SbinManager:
    """Get or create the global SbinManager instance."""
    global _global_sbin_manager
    if _global_sbin_manager is None:
        _global_sbin_manager = SbinManager()
    return _global_sbin_manager


def initialize() -> SbinManager:
    """Initialize and return the global SbinManager."""
    return get_global_sbin_manager()


def refresh() -> SbinManager:
    """Refresh the global SbinManager."""
    global _global_sbin_manager
    _global_sbin_manager = SbinManager()
    return _global_sbin_manager
