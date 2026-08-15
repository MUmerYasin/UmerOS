"""
UmerOS /sbin - System Binaries
================================
FHS-compliant implementation of the /sbin hierarchy containing system
admin, maintenance, boot, hardware config, and filesystem management programs.


Modules
-------
boot        - halt, init, poweroff, reboot, shutdown, getty, fastboot, fasthalt, update
filesystem  - fdisk, fsck, mkfs, swapon, swapoff, mkswap, chroot
modules     - insmod, lsmod, modprobe, rmmod, depmod
network     - ifconfig, ip, route
system      - sysctl, hwclock, ldconfig
mount       - mount, umount, mknod, losetup, pivot_root
maintenance - tune2fs, e2fsck, mke2fs, ctrlaltdel, kbdrate, loadkeys,
              dump, restore, sln, mktemp, setfdprm, rdev
manager     - SbinManager, FHS compliance, command registry
"""

from __future__ import annotations

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
from sbin_manager import (
    SbinManager, FHS_REQUIRED_SBIN, FHS_OPTIONAL_SBIN,
    ALL_SBIN_ENTRIES, SBIN_COMMAND_REGISTRY,
)

__all__ = [
    # Boot/Shutdown
    "HaltCommand", "InitCommand", "PoweroffCommand", "RebootCommand",
    "ShutdownCommand", "GettyCommand", "FastbootCommand", "FasthaltCommand",
    "UpdateCommand",
    # Filesystem
    "FdiskCommand", "FsckCommand", "MkfsCommand", "SwaponCommand",
    "SwapoffCommand", "MkswapCommand", "ChrootCommand",
    # Kernel Modules
    "InsmodCommand", "LsmodCommand", "ModprobeCommand", "RmmodCommand",
    "DepmodCommand",
    # Network
    "IfconfigCommand", "IpCommand", "RouteCommand",
    # System
    "SysctlCommand", "HwclockCommand", "LdconfigCommand",
    # Mount
    "MountCommand", "UmountCommand", "MknodCommand", "LosetupCommand",
    "PivotRootCommand",
    # Maintenance
    "Tune2fsCommand", "E2fsckCommand", "Mke2fsCommand", "CtrlaltdelCommand",
    "KbdrateCommand", "LoadkeysCommand", "DumpCommand", "RestoreCommand",
    "SlnCommand", "MktempCommand", "SetfdprmCommand", "RdevCommand",
    # Manager
    "SbinManager", "FHS_REQUIRED_SBIN", "FHS_OPTIONAL_SBIN",
    "ALL_SBIN_ENTRIES", "SBIN_COMMAND_REGISTRY",
]
