"""
UmerOS /sbin Hierarchy Manager
================================
Central registry for /sbin essential system administration binaries.

According to FHS 3.0 / TLDP:
  - /sbin contains essential system binaries for administration.
  - These are typically only usable by root.
  - Used for system maintenance, recovery, and boot operations.

Required /sbin commands (FSSTND):
  fdisk, fsck, getty, halt, ifconfig, init, insmod, ip, lsmod,
  mkfs, modprobe, mount, poweroff, reboot, rmmod, route, shutdown,
  swapon, sysctl
"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional, Tuple


# ─── Constants ───────────────────────────────────────────────────────────────

SBIN_PATH = "/sbin"

# FHS 3.0 Required /sbin commands
FHS_REQUIRED_SBIN: List[str] = [
    "fdisk", "fsck", "getty", "halt", "ifconfig", "init", "insmod",
    "ip", "lsmod", "mkfs", "modprobe", "poweroff", "reboot", "rmmod",
    "route", "shutdown", "swapon", "sysctl",
]

# Sbin categories per FHS/TLDP
SBIN_CATEGORIES = {
    "BOOT": "Boot and shutdown (halt, init, poweroff, reboot, shutdown)",
    "FILESYSTEM": "Filesystem tools (fdisk, fsck, mkfs, swapon)",
    "NETWORK": "Network tools (ifconfig, ip, route)",
    "MODULE": "Module tools (insmod, lsmod, modprobe, rmmod)",
    "SYSTEM": "System configuration (sysctl, getty)",
}

# Command import registry: maps command name to (module, class_name)
SBIN_COMMAND_REGISTRY: Dict[str, Tuple[str, str]] = {
    # boot.py
    "halt": ("boot", "HaltCommand"),
    "init": ("boot", "InitCommand"),
    "poweroff": ("boot", "PoweroffCommand"),
    "reboot": ("boot", "RebootCommand"),
    "shutdown": ("boot", "ShutdownCommand"),
    "getty": ("boot", "GettyCommand"),
    "lilo": ("boot", "LiloCommand"),
    "fastboot": ("boot", "FastbootCommand"),
    "fasthalt": ("boot", "FasthaltCommand"),
    "update": ("boot", "UpdateCommand"),
    # filesystem.py
    "fdisk": ("filesystem", "FdiskCommand"),
    "fsck": ("filesystem", "FsckCommand"),
    "mkfs": ("filesystem", "MkfsCommand"),
    "swapon": ("filesystem", "SwaponCommand"),
    "swapoff": ("filesystem", "SwapoffCommand"),
    "mkswap": ("filesystem", "MkswapCommand"),
    "chroot": ("filesystem", "ChrootCommand"),
    # network.py
    "ifconfig": ("network", "IfconfigCommand"),
    "ip": ("network", "IpCommand"),
    "route": ("network", "RouteCommand"),
    # modules.py
    "insmod": ("modules", "InsmodCommand"),
    "lsmod": ("modules", "LsmodCommand"),
    "modprobe": ("modules", "ModprobeCommand"),
    "rmmod": ("modules", "RmmodCommand"),
    "depmod": ("modules", "DepmodCommand"),
    # system.py
    "sysctl": ("system", "SysctlCommand"),
    "hwclock": ("system", "HwclockCommand"),
    "ldconfig": ("system", "LdconfigCommand"),
}


# ─── Enums ───────────────────────────────────────────────────────────────────

class SbinCategory(IntEnum):
    """Sbin categories."""
    BOOT = 1
    FILESYSTEM = 2
    NETWORK = 3
    MODULE = 4
    SYSTEM = 5
    UNKNOWN = 99


class SbinPrivilege(IntEnum):
    """Required privilege level."""
    ROOT = 0
    ADMIN = 1
    ANY = 99


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
    """Represents a binary in /sbin."""
    name: str
    path: str
    category: SbinCategory = SbinCategory.UNKNOWN
    privilege: SbinPrivilege = SbinPrivilege.ROOT
    status: SbinStatus = SbinStatus.ACTIVE
    description: str = ""
    version: str = ""
    size: int = 0
    permissions: int = 0o755
    owner_uid: int = 0
    group_gid: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "path": self.path,
            "category": self.category.name,
            "privilege": self.privilege.name,
            "status": self.status.name,
            "description": self.description,
            "version": self.version,
            "size": self.size,
            "permissions": oct(self.permissions),
            "owner_uid": self.owner_uid,
            "group_gid": self.group_gid,
        }


# ─── Sbin Manager ─────────────────────────────────────────────────────────

class SbinManager:
    """
    Central registry for /sbin hierarchy binaries.

    Manages essential system administration binaries required by FHS 3.0,
    provides discovery, validation, and metadata management.
    """

    def __init__(self) -> None:
        self._binaries: Dict[str, SbinBinary] = {}
        self._categories: Dict[SbinCategory, List[str]] = {}
        self._fhs_compliance: Dict[str, bool] = {}

    # ── Initialization ──────────────────────────────────────────────────

    def register_fhs_required(self) -> int:
        """Register all FHS 3.0 required /sbin binaries."""
        count = 0
        for cmd in FHS_REQUIRED_SBIN:
            if cmd not in self._binaries:
                binary = SbinBinary(
                    name=cmd,
                    path=f"/sbin/{cmd}",
                    category=self._categorize_binary(cmd),
                    privilege=SbinPrivilege.ROOT,
                    status=SbinStatus.ACTIVE,
                )
                self._binaries[cmd] = binary
                count += 1
        return count

    # ── Binary Management ───────────────────────────────────────────────

    def register_binary(self, binary: SbinBinary) -> None:
        """Register a binary."""
        self._binaries[binary.name] = binary

    def get_binary(self, name: str) -> Optional[SbinBinary]:
        """Get binary by name."""
        return self._binaries.get(name)

    def remove_binary(self, name: str) -> bool:
        """Remove a binary from registry."""
        if name in self._binaries:
            del self._binaries[name]
            return True
        return False

    def list_binaries(
        self,
        category: Optional[SbinCategory] = None,
        privilege: Optional[SbinPrivilege] = None,
        status: Optional[SbinStatus] = None,
    ) -> List[SbinBinary]:
        """List binaries with optional filtering."""
        results: List[SbinBinary] = []
        for binary in self._binaries.values():
            if category is not None and binary.category != category:
                continue
            if privilege is not None and binary.privilege != privilege:
                continue
            if status is not None and binary.status != status:
                continue
            results.append(binary)
        return results

    # ── Categorization ──────────────────────────────────────────────────

    def _categorize_binary(self, name: str) -> SbinCategory:
        """Categorize a binary by name."""
        boot = {"halt", "init", "poweroff", "reboot", "shutdown", "getty"}
        filesystem = {"fdisk", "fsck", "mkfs", "swapon"}
        network = {"ifconfig", "ip", "route"}
        module = {"insmod", "lsmod", "modprobe", "rmmod"}

        if name in boot:
            return SbinCategory.BOOT
        if name in filesystem:
            return SbinCategory.FILESYSTEM
        if name in network:
            return SbinCategory.NETWORK
        if name in module:
            return SbinCategory.MODULE
        return SbinCategory.SYSTEM

    # ── FHS Compliance ──────────────────────────────────────────────────

    def check_fhs_compliance(self) -> Dict[str, bool]:
        """Check FHS 3.0 compliance for /sbin."""
        compliance: Dict[str, bool] = {}

        for cmd in FHS_REQUIRED_SBIN:
            compliance[f"/sbin/{cmd}"] = cmd in self._binaries

        self._fhs_compliance = compliance
        return compliance

    def get_fhs_report(self) -> Dict[str, Any]:
        """Generate FHS compliance report."""
        compliance = self.check_fhs_compliance()
        missing = [k for k, v in compliance.items() if not v]
        present = [k for k, v in compliance.items() if v]

        return {
            "total_required": len(FHS_REQUIRED_SBIN),
            "present_count": len(present),
            "missing_count": len(missing),
            "missing": missing,
            "is_compliant": len(missing) == 0,
            "details": compliance,
        }

    # ── Statistics ──────────────────────────────────────────────────────

    def get_statistics(self) -> Dict[str, Any]:
        """Get /sbin hierarchy statistics."""
        total = len(self._binaries)
        by_category: Dict[str, int] = {}
        by_privilege: Dict[str, int] = {}

        for binary in self._binaries.values():
            cat_name = binary.category.name
            by_category[cat_name] = by_category.get(cat_name, 0) + 1

            priv_name = binary.privilege.name
            by_privilege[priv_name] = by_privilege.get(priv_name, 0) + 1

        return {
            "total_binaries": total,
            "by_category": by_category,
            "by_privilege": by_privilege,
            "fhs_required_count": len(FHS_REQUIRED_SBIN),
        }

    # ── Command Import ─────────────────────────────────────────────────

    def import_command(self, command_name: str) -> Optional[Any]:
        """
        Import and instantiate a command class by name.

        Args:
            command_name: The command name (e.g., 'halt', 'ip', 'fdisk')

        Returns:
            An instance of the command class, or None if not found
        """
        if command_name not in SBIN_COMMAND_REGISTRY:
            return None

        module_name, class_name = SBIN_COMMAND_REGISTRY[command_name]
        try:
            module = importlib.import_module(f".{module_name}", package=__package__)
            command_class = getattr(module, class_name)
            return command_class()
        except (ImportError, AttributeError) as e:
            print(f"Error importing {command_name}: {e}", file=sys.stderr)
            return None

    def execute_command(self, command_name: str, args: Optional[List[str]] = None) -> int:
        """
        Import and execute a command by name.

        Args:
            command_name: The command name
            args: Command arguments (optional)

        Returns:
            Exit code from the command
        """
        command = self.import_command(command_name)
        if command is None:
            print(f"{command_name}: command not found", file=sys.stderr)
            return 127

        if hasattr(command, "execute"):
            return command.execute(args)
        else:
            print(f"{command_name}: no execute method", file=sys.stderr)
            return 1

    def list_available_commands(self) -> List[str]:
        """List all commands that can be imported."""
        return sorted(SBIN_COMMAND_REGISTRY.keys())

    def get_module_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all command modules.

        Returns:
            Dictionary with module info including available commands
        """
        modules: Dict[str, Dict[str, Any]] = {}
        for cmd_name, (module_name, class_name) in SBIN_COMMAND_REGISTRY.items():
            if module_name not in modules:
                modules[module_name] = {
                    "commands": [],
                    "loaded": False,
                    "error": None,
                }
            modules[module_name]["commands"].append(cmd_name)

        for module_name in modules:
            try:
                importlib.import_module(f".{module_name}", package=__package__)
                modules[module_name]["loaded"] = True
            except ImportError as e:
                modules[module_name]["error"] = str(e)

        return modules

    # ── Import/Export ───────────────────────────────────────────────────

    def export_index(self) -> List[Dict[str, Any]]:
        """Export binary index as list of dictionaries."""
        return [b.to_dict() for b in self._binaries.values()]

    def import_from_dict(self, data: Dict[str, Any]) -> int:
        """Import binaries from dictionary."""
        count = 0
        for name, info in data.items():
            binary = SbinBinary(
                name=name,
                path=info.get("path", f"/sbin/{name}"),
                category=SbinCategory[info.get("category", "UNKNOWN")],
                privilege=SbinPrivilege[info.get("privilege", "ROOT")],
                status=SbinStatus[info.get("status", "ACTIVE")],
                description=info.get("description", ""),
                version=info.get("version", ""),
                size=info.get("size", 0),
            )
            self._binaries[name] = binary
            count += 1
        return count


# ─── Module-Level Singleton ─────────────────────────────────────────────────

_sbin_manager: Optional[SbinManager] = None


def get_sbin_manager() -> SbinManager:
    """Get or create the singleton SbinManager."""
    global _sbin_manager
    if _sbin_manager is None:
        _sbin_manager = SbinManager()
        _sbin_manager.register_fhs_required()
    return _sbin_manager
