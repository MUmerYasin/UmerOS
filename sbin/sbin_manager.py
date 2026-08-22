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
UmerOS /sbin Manager
====================
Central registry for all /sbin commands, FHS compliance enforcement, and command routing.
"""

from __future__ import annotations
import os
import sys
from typing import Any, Dict, List, Optional, Type

# [FIX H233] Gate privileged /sbin command execution behind the zero-trust
# capability bridge. `SbinManager.execute` runs system-level commands (halt,
# reboot, mkfs, chroot, mount, insmod, …) with no capability check or audit, so
# it must require the `sys.admin` capability when a CapabilityManager is wired
# (fail-closed).
try:
    from core.capability_gate import gate, CAP_SYS_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_SYS_ADMIN

# ─── Import all command classes ─────────────────────────────────────────────
from  os import path as _p
import sys as _sys
_this_dir = _p.dirname(_p.abspath(__file__))
if _this_dir not in _sys.path:
    _sys.path.insert(0, _this_dir)

from boot import (
    HaltCommand, InitCommand, PoweroffCommand, RebootCommand,
    ShutdownCommand, GettyCommand, FastbootCommand, FasthaltCommand,
    UpdateCommand,
)
from filesystem import (
    FdiskCommand, FsckCommand, MkfsCommand, SwaponCommand,
    SwapoffCommand, MkswapCommand, ChrootCommand,
)
from modules import (
    InsmodCommand, LsmodCommand, ModprobeCommand, RmmodCommand,
    DepmodCommand,
)
from network import IfconfigCommand, IpCommand, RouteCommand
from system import SysctlCommand, HwclockCommand, LdconfigCommand
from mount import (
    MountCommand, UmountCommand, MknodCommand, LosetupCommand,
    PivotRootCommand,
)
from maintenance import (
    Tune2fsCommand, E2fsckCommand, Mke2fsCommand, CtrlaltdelCommand,
    KbdrateCommand, LoadkeysCommand, DumpCommand, RestoreCommand,
    SlnCommand, MktempCommand, SetfdprmCommand, RdevCommand,
)


# ─── TLDP FHS Required /sbin entries ────────────────────────────────────────
FHS_REQUIRED_SBIN = [
    "fdisk",        # Manipulate disk partition table
    "fsck",         # Check and repair filesystem
    "getty",        # Set terminal type
    "halt",         # Stop the system
    "ifconfig",     # Configure network interfaces
    "init",         # Process control initialization
    "insmod",       # Insert modules into Linux kernel
    "ip",           # Show/manipulate routing, devices, policy
    "lsmod",        # Show loaded kernel modules
    "mkfs",         # Create filesystem on device
    "modprobe",     # Add/remove modules from Linux kernel
    "mount",        # Mount filesystems
    "poweroff",     # Shut down and power off
    "reboot",       # Restart the system
    "rmmod",        # Remove modules from Linux kernel
    "route",        # Show/manipulate IP routing table
    "shutdown",     # Shut down the system
    "swapon",       # Enable swap devices/files
    "sysctl",       # Administer kernel parameters
]

# ─── TLDP FHS Optional /sbin entries ────────────────────────────────────────
FHS_OPTIONAL_SBIN = [
    "fastboot",     # Quick reboot skipping filesystem checks
    "fasthalt",     # Quick halt
    "fsck.ext2",    # Ext2 filesystem check
    "fsck.ext3",    # Ext3 filesystem check
    "fsck.ext4",    # Ext4 filesystem check
    "hwclock",      # Query/set hardware clock
    "ldconfig",     # Configure dynamic linker bindings
    "loadkeys",     # Load keyboard translation tables
    "losetup",      # Set up loop devices
    "mke2fs",       # Create ext2/3/4 filesystem
    "mkfs.ext2",    # Create ext2 filesystem
    "mkfs.ext3",    # Create ext3 filesystem
    "mkfs.ext4",    # Create ext4 filesystem
    "mkswap",       # Set up a swap area
    "pivot_root",   # Change root mount
    "swapoff",      # Disable swap devices/files
    "update",       # Update cron daemon
]

# ─── All /sbin entries combined ─────────────────────────────────────────────
ALL_SBIN_ENTRIES = FHS_REQUIRED_SBIN + FHS_OPTIONAL_SBIN

# ─── Command Registry ───────────────────────────────────────────────────────
SBIN_COMMAND_REGISTRY: Dict[str, Any] = {
    # Boot/Shutdown
    "halt":          HaltCommand,
    "init":          InitCommand,
    "poweroff":      PoweroffCommand,
    "reboot":        RebootCommand,
    "shutdown":      ShutdownCommand,
    "getty":         GettyCommand,
    "fastboot":      FastbootCommand,
    "fasthalt":      FasthaltCommand,
    "update":        UpdateCommand,
    # Filesystem
    "fdisk":         FdiskCommand,
    "fsck":          FsckCommand,
    "mkfs":          MkfsCommand,
    "swapon":        SwaponCommand,
    "swapoff":       SwapoffCommand,
    "mkswap":        MkswapCommand,
    "chroot":        ChrootCommand,
    # Kernel Modules
    "insmod":        InsmodCommand,
    "lsmod":         LsmodCommand,
    "modprobe":      ModprobeCommand,
    "rmmod":         RmmodCommand,
    "depmod":        DepmodCommand,
    # Network
    "ifconfig":      IfconfigCommand,
    "ip":            IpCommand,
    "route":         RouteCommand,
    # System
    "sysctl":        SysctlCommand,
    "hwclock":       HwclockCommand,
    "ldconfig":      LdconfigCommand,
    # Mount
    "mount":         MountCommand,
    "umount":        UmountCommand,
    "mknod":         MknodCommand,
    "losetup":       LosetupCommand,
    "pivot_root":    PivotRootCommand,
    # Maintenance
    "tune2fs":       Tune2fsCommand,
    "e2fsck":        E2fsckCommand,
    "mke2fs":        Mke2fsCommand,
    "fsck.ext2":     E2fsckCommand,
    "fsck.ext3":     E2fsckCommand,
    "fsck.ext4":     E2fsckCommand,
    "mkfs.ext2":     Mke2fsCommand,
    "mkfs.ext3":     Mke2fsCommand,
    "mkfs.ext4":     Mke2fsCommand,
    "ctrlaltdel":    CtrlaltdelCommand,
    "kbdrate":       KbdrateCommand,
    "loadkeys":      LoadkeysCommand,
    "dump":          DumpCommand,
    "restore":       RestoreCommand,
    "sln":           SlnCommand,
    "mktemp":        MktempCommand,
    "setfdprm":      SetfdprmCommand,
    "rdev":          RdevCommand,
}


class SbinManager:
    """Central manager for /sbin commands and FHS compliance."""

    def __init__(self):
        self.registry = SBIN_COMMAND_REGISTRY.copy()

    def get_command(self, name: str) -> Optional[Any]:
        """Get a command instance by name."""
        cmd_cls = self.registry.get(name)
        if cmd_cls:
            return cmd_cls()
        return None

    def has_command(self, name: str) -> bool:
        """Check if a command exists in the registry."""
        return name in self.registry

    def list_commands(self) -> List[str]:
        """List all registered commands."""
        return sorted(self.registry.keys())

    def list_required(self) -> List[str]:
        """List FHS-required /sbin entries."""
        return FHS_REQUIRED_SBIN.copy()

    def list_optional(self) -> List[str]:
        """List FHS-optional /sbin entries."""
        return FHS_OPTIONAL_SBIN.copy()

    def check_compliance(self) -> Dict[str, Any]:
        """Check FHS /sbin compliance."""
        registered = set(self.registry.keys())
        missing_required = [c for c in FHS_REQUIRED_SBIN if c not in registered]
        missing_optional = [c for c in FHS_OPTIONAL_SBIN if c not in registered]
        return {
            "total_commands": len(self.registry),
            "required_total": len(FHS_REQUIRED_SBIN),
            "required_present": len(FHS_REQUIRED_SBIN) - len(missing_required),
            "required_missing": missing_required,
            "optional_total": len(FHS_OPTIONAL_SBIN),
            "optional_present": len(FHS_OPTIONAL_SBIN) - len(missing_optional),
            "optional_missing": missing_optional,
            "compliant": len(missing_required) == 0,
        }

    def execute(self, command: str, args: Optional[List[str]] = None) -> int:
        """Execute a /sbin command."""
        # [FIX H233] Require the system-admin capability before running any
        # privileged /sbin command.  Enforced fail-closed when a CapabilityManager
        # is wired; permissive (warning) when running standalone.
        gate.require(CAP_SYS_ADMIN)
        cmd = self.get_command(command)
        if cmd is None:
            print(f"{command}: not found", file=sys.stderr)
            return 127
        return cmd.execute(args)

    def _selftest(self) -> bool:
        """Verify SbinManager integrity."""
        checks = 0
        failures = 0

        for cmd_name in FHS_REQUIRED_SBIN:
            if cmd_name in self.registry:
                checks += 1
            else:
                failures += 1
                print(f"  MISSING required: {cmd_name}")

        compliance = self.check_compliance()
        if compliance["compliant"]:
            checks += 1
        else:
            failures += 1
            print(f"  Not FHS compliant, missing required: {compliance['required_missing']}")

        print(f"  SbinManager checks: {checks}, failures: {failures}")
        return failures == 0
