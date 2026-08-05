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
from .lib_manager import LibraryManager, get_global_lib_manager
from .source_manager import SourceManager, get_global_source_manager
from .doc_browser import DocBrowser, get_global_doc_browser
from .info_pages import InfoPagesManager, get_global_info_manager
from .x11_manager import X11Manager, get_global_x11_manager
from .tmp_manager import TmpManager, get_global_tmp_manager
from .games_manager import GamesManager, get_global_games_manager
from .colors_manager import ColorsManager, get_global_colors_manager
from .fonts_manager import FontsManager, get_global_fonts_manager
from .gcc_manager import GccManager, get_global_gcc_manager
from .i18n_manager import I18nManager, get_global_i18n_manager
from .icons_manager import IconsManager, get_global_icons_manager
from .lib64_manager import Lib64Manager, get_global_lib64_manager
from .libexec_manager import LibexecManager, get_global_libexec_manager
from .locale_manager import LocaleManager, get_global_locale_manager
from .sbin_manager import SbinManager, get_global_sbin_manager
from .sgml_manager import SgmlManager, get_global_sgml_manager
from .zoneinfo_manager import ZoneinfoManager, get_global_zoneinfo_manager
from .x11_modules_manager import X11ModulesManager, get_global_x11_modules_manager
from .x11_fonts_manager import X11FontsManager, get_global_x11_fonts_manager
from .rpm_manager import RPMManager, get_global_rpm_manager
from .kernel_source_manager import KernelSourceManager, get_global_kernel_manager
from .user_help_manager import UserHelpManager, get_global_user_help_manager
from .xdg_manager import XDGSessionManager, get_global_xdg_session_manager
from .wayland_manager import WaylandProtocolManager, get_global_wayland_protocol_manager
from .dconf_manager import DConfManager, get_global_dconf_manager


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
    # lib_manager (/usr/lib)
    "LibraryManager",
    "get_global_lib_manager",
    # src_manager (/usr/src)
    "SourceManager",
    "get_global_source_manager",
    # doc_browser (/usr/share/doc)
    "DocBrowser",
    "get_global_doc_browser",
    # info_pages (/usr/share/info)
    "InfoPagesManager",
    "get_global_info_manager",
    # x11_manager (/usr/X11R6)
    "X11Manager",
    "get_global_x11_manager",
    # tmp_manager (/usr/tmp)
    "TmpManager",
    "get_global_tmp_manager",
    # games_manager (/usr/games)
    "GamesManager",
    "get_global_games_manager",
    # colors_manager (/usr/share/X11/rgb.txt)
    "ColorsManager",
    "get_global_colors_manager",
    # fonts_manager (/usr/share/fonts)
    "FontsManager",
    "get_global_fonts_manager",
    # gcc_manager (/usr/lib/gcc)
    "GccManager",
    "get_global_gcc_manager",
    # i18n_manager (/usr/share/i18n)
    "I18nManager",
    "get_global_i18n_manager",
    # icons_manager (/usr/share/icons)
    "IconsManager",
    "get_global_icons_manager",
    # lib64_manager (/usr/lib64)
    "Lib64Manager",
    "get_global_lib64_manager",
    # libexec_manager (/usr/libexec)
    "LibexecManager",
    "get_global_libexec_manager",
    # locale_manager (/usr/share/locale)
    "LocaleManager",
    "get_global_locale_manager",
    # sbin_manager (/usr/sbin)
    "SbinManager",
    "get_global_sbin_manager",
    # sgml_manager (/usr/share/sgml)
    "SgmlManager",
    "get_global_sgml_manager",
    # zoneinfo_manager (/usr/share/zoneinfo)
    "ZoneinfoManager",
    "get_global_zoneinfo_manager",
    # x11_modules_manager (/usr/X11R6/lib/modules)
    "X11ModulesManager",
    "get_global_x11_modules_manager",
    # x11_fonts_manager (/usr/X11R6/lib/X11/fonts)
    "X11FontsManager",
    "get_global_x11_fonts_manager",
    # rpm_manager (/usr/src/RPM)
    "RPMManager",
    "get_global_rpm_manager",
    # kernel_source_manager (/usr/src/linux)
    "KernelSourceManager",
    "get_global_kernel_manager",
    # user_help_manager (/usr/share/user-help)
    "UserHelpManager",
    "get_global_user_help_manager",
    # xdg_manager (/usr/share/xsessions, /usr/share/wayland-sessions)
    "XDGSessionManager",
    "get_global_xdg_session_manager",
    # wayland_manager (/usr/share/wayland)
    "WaylandProtocolManager",
    "get_global_wayland_protocol_manager",
    # dconf_manager (/usr/share/dconf)
    "DConfManager",
    "get_global_dconf_manager",
]
