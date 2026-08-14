"""
UmerOS Boot System
===================
Complete /boot filesystem implementation for UmerOS.

Modules:
    - kernel_image: Kernel image management (vmlinuz, System.map, config)
    - grub_manager: Complete GRUB2 configuration manager
    - systemd_boot: systemd-boot loader manager
    - efi_system: EFI System Partition, Secure Boot, NVRAM
    - boot_params: Kernel command line and sysctl parameters
    - microcode: CPU microcode update management
    - boot_splash: Boot splash and framebuffer graphics
    - crash_kernel: kdump/crash kernel for post-mortem debugging

Usage:
    from umeros_boot import BootParamsManager, GRUBManager, EFISystemManager
"""

__version__ = "1.0.0"
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
    MicrocodeManager,
    MicrocodeInstaller,
    MicrocodeVendor,
    CPUInfo,
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
    "MicrocodeManager",
    "MicrocodeInstaller",
    "MicrocodeVendor",
    "CPUInfo",
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
]
