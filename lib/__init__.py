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
UmerOS /lib - Shared Libraries and Kernel Modules
===================================================
Public API for everything related to the FHS /lib hierarchy in UmerOS.

This package now covers the full TLDP/FHS spec for /lib and all of the
companion directories that show up in the same conversation:

  /lib                         Essential shared libraries + /lib/cpp
    modules/<ver>              Kernel modules + depmod artefacts
    iptables                   iptables shared extensions
    kbd                        Keymaps, fonts, console translations
    security                   PAM modules
    oss                        Open Sound System drivers
    firmware                   Firmware blobs (modern)
    <machine-architecture>     Multi-arch libraries
    <qual> (32/64/x32/sf)      Alternate-format variants

  /usr/lib                     User-space libraries
    gconv                      Charset conversion modules
    locale/locale-archive      Compiled locale data
    charmaps                   Charmap definitions
    libexec                    Internal binaries
    X11                        Symlink → /usr/X11R6/lib/X11

  /usr/include                 Header files for compilation
    <package>                  Per-package headers
    X11                        Symlink → /usr/X11R6/include/X11

  /var/lib                     Per-host state
    <application>              Per-app state (rpm, dpkg, apt, ...)
    misc                       Miscellaneous state
    alternatives               The alternatives system

  /etc/ld.so.conf              Dynamic linker config
  /etc/ld.so.cache             Built by ldconfig

The high-level entry points:

  * ``KernelModuleManager`` — modprobe / rmmod / depmod
  * ``LibHierarchyManager`` — TLDP/FHS /lib audit + bootstrap
  * ``LibraryManager``     — /lib essential libraries + symlinks
  * ``EssentialLibraryManager`` — FHS-required stubs (libc, ld, libm, ...)
  * ``DynamicLinkerManager``  — ldconfig, ld.so.conf parser, ld.so.cache
  * ``LibQualifierManager``  — /lib<qual> helpers
  * ``IptablesLibraryManager`` — /lib/iptables extensions
  * ``KbdManager``           — /lib/kbd keymaps / fonts / translations
  * ``PamLibraryManager``    — /lib/security PAM modules
  * ``OssManager``           — /lib/oss drivers
  * ``FirmwareManager``      — /lib/firmware blobs
  * ``ArchLibraryManager``   — /lib/<machine-architecture> layout
  * ``MultiarchManager``     — /lib<qual> policy
  * ``UsrLibManager``        — /usr/lib + gconv + charmap + libexec
  * ``UsrIncludeManager``    — /usr/include header catalogue
  * ``VarLibManager``        — /var/lib state + alternatives system
  * ``lib_summary``          — one-shot /lib summary (libinfo)

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

from .library_manager import LibraryManager, LibraryInfo
from .fhs import (
    LibHierarchyManager,
    LibAuditReport,
    LibAuditIssue,
    LibIssueSeverity,
    LibRequirement,
)
from .kernel_modules import (
    KernelModuleManager,
    KernelModule,
    ModuleDependency,
    ModuleState,
    ModuleLoadResult,
    DEFAULT_KERNEL_VERSION,
)
from .essential_libs import EssentialLibraryManager, ESSENTIAL_LIBRARIES, SharedLibrary
from .dynamic_linker import (
    DynamicLinkerManager,
    LdSoConfParser,
    LdSoCache,
    LibQualifierManager,
    LinkerConfig,
    CacheEntry,
)
from .iptables_libs import (
    IptablesLibraryManager,
    IptablesExtension,
    ExtensionFamily,
    ExtensionKind,
)
from .kbd import KbdManager, KbdFile, KbdFileKind
from .security import PamLibraryManager, PamModule, PamModuleType, PamControlFlag, PamService
from .oss import OssManager, OssDriver, OssBusType, OssDriverKind
from .firmware import (
    FirmwareManager,
    FirmwareBlob,
    FirmwareSubsystem,
    FirmwareLicense,
)
from .arch import (
    ArchLibraryManager,
    ArchDir,
    ARCHITECTURES,
)
from .multiarch import (
    MultiarchManager,
    LibQualifier,
    LibVariant,
)
from .usr_lib import (
    UsrLibManager,
    GconvManager,
    GconvModule,
    CharmapManager,
    CharmapEntry,
    LibexecManager,
    LibexecProgram,
    UsrLibSubdir,
)
from .usr_include import (
    UsrIncludeManager,
    HeaderFile,
    HeaderPackage,
    HeaderLanguage,
    HeaderCategory,
)
from .var_lib import (
    VarLibManager,
    VarLibEntry,
    StateKind,
    AlternativesManager,
    Alternative,
)
from .libinfo import LibSummary, lib_summary
from .elf_parser import (
    ElfParser,
    ElfBinary,
    ElfParseError,
    ElfClass,
    ElfData,
    ElfType,
    ElfMachine,
    ElfHeader,
    SectionHeader,
    DynamicEntry,
    SymbolEntry,
    ShtType,
    DynamicTag,
    is_elf,
    read_needed,
    read_soname,
)
from .ldd import (
    Ldd,
    LddConfig,
    DependencyTree,
    ResolvedDep,
)
from .iconv import (
    Iconv,
    ConversionPair,
    ConversionResult,
    GconvModuleInfo,
)
from .ssl_libs import (
    SslManager,
    CertInfo,
    KeyInfo,
    CaBundleInfo,
    SslStoreStats,
    CertFormat,
    CertPurpose,
)
from .tmpfiles import (
    TmpfilesManager,
    TmpfilesConfig,
    TmpfilesEntry,
    TmpfilesType,
    AgeSpec,
    CleanupResult,
)


__all__ = [
    # TLDP/FHS hierarchy
    "LibHierarchyManager", "LibAuditReport", "LibAuditIssue",
    "LibIssueSeverity", "LibRequirement",
    # Library + essential
    "LibraryManager", "LibraryInfo",
    "EssentialLibraryManager", "ESSENTIAL_LIBRARIES", "SharedLibrary",
    # Dynamic linker
    "DynamicLinkerManager", "LdSoConfParser", "LdSoCache",
    "LibQualifierManager", "LinkerConfig", "CacheEntry",
    # Kernel modules
    "KernelModuleManager", "KernelModule", "ModuleDependency",
    "ModuleState", "ModuleLoadResult", "DEFAULT_KERNEL_VERSION",
    # iptables
    "IptablesLibraryManager", "IptablesExtension",
    "ExtensionFamily", "ExtensionKind",
    # kbd
    "KbdManager", "KbdFile", "KbdFileKind",
    # security / PAM
    "PamLibraryManager", "PamModule", "PamModuleType", "PamControlFlag", "PamService",
    # OSS
    "OssManager", "OssDriver", "OssBusType", "OssDriverKind",
    # firmware
    "FirmwareManager", "FirmwareBlob", "FirmwareSubsystem", "FirmwareLicense",
    # arch
    "ArchLibraryManager", "ArchDir", "ARCHITECTURES",
    # multiarch
    "MultiarchManager", "LibQualifier", "LibVariant",
    # usr/lib
    "UsrLibManager", "GconvManager", "GconvModule",
    "CharmapManager", "CharmapEntry", "LibexecManager", "LibexecProgram",
    "UsrLibSubdir",
    # usr/include
    "UsrIncludeManager", "HeaderFile", "HeaderPackage",
    "HeaderLanguage", "HeaderCategory",
    # var/lib
    "VarLibManager", "VarLibEntry", "StateKind",
    "AlternativesManager", "Alternative",
    # one-shot summary
    "LibSummary", "lib_summary",
    # elf_parser
    "ElfParser", "ElfBinary", "ElfParseError",
    "ElfClass", "ElfData", "ElfType", "ElfMachine",
    "ElfHeader", "SectionHeader", "DynamicEntry", "SymbolEntry",
    "ShtType", "DynamicTag", "is_elf", "read_needed", "read_soname",
    # ldd
    "Ldd", "LddConfig", "DependencyTree", "ResolvedDep",
    # iconv
    "Iconv", "ConversionPair", "ConversionResult", "GconvModuleInfo",
    # ssl_libs
    "SslManager", "CertInfo", "KeyInfo", "CaBundleInfo",
    "SslStoreStats", "CertFormat", "CertPurpose",
    # tmpfiles
    "TmpfilesManager", "TmpfilesConfig", "TmpfilesEntry",
    "TmpfilesType", "AgeSpec", "CleanupResult",
]
