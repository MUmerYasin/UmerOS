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
from .man_page import ManPageManager, get_global_man
from .share_data import ShareDataManager, get_global_share
from .local_software import LocalSoftwareManager, get_global_local_software
from .header_files import HeaderFilesManager, get_global_header_files
from .config_files import ConfigFilesManager, get_global_config_files
from .binary_exec import BinaryExecManager, get_global_binary_exec


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
    # man_page
    "ManPageManager",
    "get_global_man",
    # share_data
    "ShareDataManager",
    "get_global_share",
    # local_software
    "LocalSoftwareManager",
    "get_global_local_software",
    # header_files
    "HeaderFilesManager",
    "get_global_header_files",
    # config_files
    "ConfigFilesManager",
    "get_global_config_files",
    # binary_exec
    "BinaryExecManager",
    "get_global_binary_exec",
]
