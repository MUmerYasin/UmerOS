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
UmerOS Boot System
===================
Complete /boot filesystem implementation for UmerOS, covering the
FHS 3.0 ``/boot`` requirements (ch03s05), the Linux/x86 boot
protocol, the UAPI Boot Loader Specification (BLS, UAPI.1) and the
Unified Kernel Image specification (UKI, UAPI.5).

Modules
-------

* :mod:`boot.kernel_image`  - kernel image management (vmlinuz, System.map, config)
* :mod:`boot.grub_manager`  - complete GRUB2 configuration manager
* :mod:`boot.systemd_boot`  - systemd-boot / BLS Type #1 entries
* :mod:`boot.efi_system`   - EFI System Partition, Secure Boot, NVRAM
* :mod:`boot.boot_params`   - kernel command line and sysctl parameters
* :mod:`boot.microcode`     - CPU microcode update management
* :mod:`boot.boot_splash`   - boot splash and framebuffer graphics
* :mod:`boot.crash_kernel`  - kdump / crash kernel for post-mortem
* :mod:`boot.bootloader`    - generic boot loader abstraction
* :mod:`boot.boot_manager`  - top-level /boot manager
* :mod:`boot.initrd_manager` - initramfs / initrd management
* :mod:`boot.bzimage`       - Linux/x86 bzImage header parser
* :mod:`boot.efi_stub`      - EFI stub / UKI (PE/COFF) detection
* :mod:`boot.cmdline`       - kernel command line parser/builder
* :mod:`boot.info`          - one-shot /boot summary
* :mod:`boot.fhs`           - FHS 3.0 /boot audit
* :mod:`boot.memtest`       - Memtest86+ integration and result parsing
* :mod:`boot.boot_log`      - Boot event logging and analytics
* :mod:`boot.kernel_signing` - Secure Boot and UEFI kernel signing
* :mod:`boot.__main__`      - ``python -m boot`` CLI

References
----------

* https://refspecs.linuxfoundation.org/FHS_3.0/fhs/ch03s05.html
* https://uapi-group.org/specifications/specs/boot_loader_specification/
* https://uapi-group.org/specifications/specs/unified_kernel_image/
* https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html
* Linux/Documentation/x86/boot.txt

Quick start
-----------

::

    from boot import (
        KernelImageManager, GrubManager, SystemdBootManager,
        BzImageInspector, EfiStubInspector, parse_cmdline,
        boot_summary, FHSBootAuditor,
    )

    # What's installed?
    s = boot_summary("/boot")
    print(s.render_table())

    # Parse the running kernel's bzImage header
    bh = BzImageInspector("/boot").inspect("vmlinuz-6.8.0-umerOS")
    print(bh.protocol_string())        # e.g. "2.0e"

    # Audit FHS 3.0 conformance
    audit = FHSBootAuditor("/boot").audit()
    if not audit.ok:
        for issue in audit.issues:
            print(issue)

    # Or use the CLI:
    #   python -m boot selftest
    #   python -m boot info /boot
    #   python -m boot audit /boot
    #   python -m boot bzimage /boot/vmlinuz-6.8.0-umerOS

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

__version__ = "2.0.0"
__author__ = "UmerOS Development Team"

# Core imports
from .kernel_image import (
    KernelImage,
    KernelArchitecture,
    KernelCompression,
    KernelImageManager,
)
from .grub_manager import (
    GrubEnv,
    GrubModuleManager,
    GrubMenuEntry,
    GrubTheme,
    GrubConfig,
    GrubManager,
)
from .systemd_boot import (
    LoaderConfig,
    BootEntry,
    SystemdBootManager,
)
from .efi_system import (
    EFISystemPartition,
    NVRAMManager,
    SecureBootManager,
    EFISystemManager,
    SecureBootState,
)
from .boot_params import (
    KernelCommandLine,
    SysctlManager,
    BootParamsManager,
)
from .microcode import (
    CPUVendor,
    MicrocodeSignificance,
    MicrocodeUpdate,
    CPUInfo,
    MicrocodeParser,
    MicrocodeManager,
    MicrocodeInstaller,
)
from .boot_splash import (
    PlymouthManager,
    FramebufferManager,
    BootSplashManager,
    SplashTechnology,
    SplashTheme,
)
from .crash_kernel import (
    KdumpConfig,
    KdumpConfigManager,
    KdumpKernelBuilder,
    KdumpServiceManager,
    VmcoreManager,
    CrashKernelManager,
    KdumpDumpTarget,
    KdumpServiceState,
)
from .bzimage import (
    BzImageHeader,
    BzImageInspector,
    BzImageType,
    HDRS_MAGIC,
    parse_bzimage_header,
)
from .efi_stub import (
    EfiImage,
    EfiImageType,
    EfiStubInspector,
    UKI_SECTIONS,
    parse_efi_image,
)
from .cmdline import (
    CmdParam,
    CmdParamKind,
    CmdlineIssue,
    KNOWN_KEYS,
    PRESETS,
    ParsedCmdline,
    build_cmdline,
    parse_cmdline,
    preset,
    validate,
)
from .info import BootSummary, boot_summary
from .fhs import FHSBootAuditor, FHSIssue, FHSIssueSeverity, FHSReport
from .memtest import (
    MemtestVersion,
    MemtestStatus,
    MemtestTestType,
    MemoryErrorType,
    MemtestConfig,
    MemtestResult,
    MemoryError,
    MemtestBinary,
    MemtestDetector,
    MemtestCommandBuilder,
    MemtestResultParser,
    MemtestManager,
)
from .boot_log import (
    BootLogLevel,
    BootPhase,
    BootEventType,
    BootEvent,
    BootSession,
    BootStats,
    BootLogger,
    BootAnalyzer,
)
from .kernel_signing import (
    SecureBootState as KernelSecureBootState,
    SignatureStatus,
    KeyType,
    KeyAlgorithm,
    SignatureFormat,
    SigningKey,
    Signature,
    UKISection,
    KernelSignatureInfo,
    SigningConfig,
    PEParser,
    SignatureVerifier,
    MOKManager,
    SigningCommandBuilder,
    SecureBootManager as KernelSecureBootManager,
)


__all__ = [
    # Version
    "__version__",
    "__author__",
    # kernel_image
    "KernelImage",
    "KernelArchitecture",
    "KernelCompression",
    "KernelImageManager",
    # grub_manager
    "GrubEnv",
    "GrubModuleManager",
    "GrubMenuEntry",
    "GrubTheme",
    "GrubConfig",
    "GrubManager",
    # systemd_boot
    "LoaderConfig",
    "BootEntry",
    "SystemdBootManager",
    # efi_system
    "EFISystemPartition",
    "NVRAMManager",
    "SecureBootManager",
    "EFISystemManager",
    "SecureBootState",
    # boot_params
    "KernelCommandLine",
    "SysctlManager",
    "BootParamsManager",
    # microcode
    "CPUVendor",
    "MicrocodeSignificance",
    "MicrocodeUpdate",
    "CPUInfo",
    "MicrocodeParser",
    "MicrocodeManager",
    "MicrocodeInstaller",
    # boot_splash
    "PlymouthManager",
    "FramebufferManager",
    "BootSplashManager",
    "SplashTechnology",
    "SplashTheme",
    # crash_kernel
    "KdumpConfig",
    "KdumpConfigManager",
    "KdumpKernelBuilder",
    "KdumpServiceManager",
    "VmcoreManager",
    "CrashKernelManager",
    "KdumpDumpTarget",
    "KdumpServiceState",
    # bzimage
    "BzImageHeader",
    "BzImageInspector",
    "BzImageType",
    "HDRS_MAGIC",
    "parse_bzimage_header",
    # efi_stub
    "EfiImage",
    "EfiImageType",
    "EfiStubInspector",
    "UKI_SECTIONS",
    "parse_efi_image",
    # cmdline
    "CmdParam",
    "CmdParamKind",
    "CmdlineIssue",
    "KNOWN_KEYS",
    "PRESETS",
    "ParsedCmdline",
    "build_cmdline",
    "parse_cmdline",
    "preset",
    "validate",
    # info
    "BootSummary",
    "boot_summary",
    # fhs
    "FHSBootAuditor",
    "FHSIssue",
    "FHSIssueSeverity",
    "FHSReport",
    # memtest
    "MemtestVersion",
    "MemtestStatus",
    "MemtestTestType",
    "MemoryErrorType",
    "MemtestConfig",
    "MemtestResult",
    "MemoryError",
    "MemtestBinary",
    "MemtestDetector",
    "MemtestCommandBuilder",
    "MemtestResultParser",
    "MemtestManager",
    # boot_log
    "BootLogLevel",
    "BootPhase",
    "BootEventType",
    "BootEvent",
    "BootSession",
    "BootStats",
    "BootLogger",
    "BootAnalyzer",
    # kernel_signing
    "KernelSecureBootState",
    "SignatureStatus",
    "KeyType",
    "KeyAlgorithm",
    "SignatureFormat",
    "SigningKey",
    "Signature",
    "UKISection",
    "KernelSignatureInfo",
    "SigningConfig",
    "PEParser",
    "SignatureVerifier",
    "MOKManager",
    "SigningCommandBuilder",
    "KernelSecureBootManager",
]
