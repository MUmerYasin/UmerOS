"""
UmerOS Userspace API
====================
Linux kernel userspace API modules.
"""

from __future__ import annotations

from .syscalls import (
    UnshareManager,
    Futex2Manager,
    RseqManager,
    MsealManager,
)
from .io_uring import IOUringManager
from .seccomp import SeccompManager
from .landlock import LandlockManager
from .dmabuf import DMABufManager, get_global_dmabuf_manager
from .iommufd import IOMMUFDManager, get_global_iommufd_manager
from .elf_loader import ELFLoader, get_global_elf_loader
from .procfs import ProcFS, get_global_procfs
from .sysfs import SysFS, get_global_sysfs
from .netlink import Netlink, get_global_netlink
from .tee import TEE, get_global_tee
from .perf import Perf, get_global_perf
from .ntsync import NTSync, get_global_ntsync
from .vduse import VDUSE, get_global_vduse
from .filedesc import FileDesc, get_global_filedesc


__all__ = [
    # syscalls
    "UnshareManager",
    "Futex2Manager",
    "RseqManager",
    "MsealManager",
    # io_uring
    "IOUringManager",
    # seccomp
    "SeccompManager",
    # landlock
    "LandlockManager",
    # dmabuf
    "DMABufManager",
    "get_global_dmabuf_manager",
    # iommufd
    "IOMMUFDManager",
    "get_global_iommufd_manager",
    # elf_loader
    "ELFLoader",
    "get_global_elf_loader",
    # procfs
    "ProcFS",
    "get_global_procfs",
    # sysfs
    "SysFS",
    "get_global_sysfs",
    # netlink
    "Netlink",
    "get_global_netlink",
    # tee
    "TEE",
    "get_global_tee",
    # perf
    "Perf",
    "get_global_perf",
    # ntsync
    "NTSync",
    "get_global_ntsync",
    # vduse
    "VDUSE",
    "get_global_vduse",
    # filedesc
    "FileDesc",
    "get_global_filedesc",
]
