#!/usr/bin/env python3
"""
UmerOS Boot System - Interactive Demo
=======================================
Demonstrates all boot system modules with sample data creation.

Usage:
    python demo_boot.py
    python demo_boot.py --quick
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add boot directory to path
sys.path.insert(0, str(Path(__file__).parent))

from kernel_image import KernelImageManager, KernelArchitecture, KernelCompression
from grub_manager import GrubManager, GrubModuleManager, GrubMenuEntry
from systemd_boot import SystemdBootManager, LoaderConfig, BootEntry
from efi_system import EFISystemManager, SecureBootManager, SecureBootState
from boot_params import BootParamsManager, KernelCommandLine, SysctlManager
from microcode import MicrocodeManager, MicrocodeInstaller
from boot_splash import BootSplashManager, PlymouthManager, FramebufferManager
from crash_kernel import CrashKernelManager, KdumpDumpTarget


BOOT_DIR = Path(__file__).parent / "boot_samples"
SEPARATOR = "=" * 72


def banner(title: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def demo_kernel_image():
    banner("1. Kernel Image Management")
    mgr = KernelImageManager(boot_dir=BOOT_DIR)

    # Create sample vmlinuz
    section("Creating sample kernel image")
    img = mgr.create_sample_kernel(
        version="6.1.0-umeros",
        size_kb=512,
    )
    print(f"  Created: {img.vmlinuz_path}")
    print(f"  Size: {img.vmlinuz_size} bytes")
    print(f"  Compression: {img.compression.value}")
    print(f"  Arch: {img.architecture.value}")
    print(f"  Hash: {img.vmlinuz_hash[:32]}...")

    # List kernels
    section("Listing kernels")
    versions = mgr.list_versions()
    for v in versions:
        k = mgr.get_kernel(v)
        print(f"  vmlinuz-{v}: {k.architecture.value} @ {k.compression.value}")

    return mgr


def demo_grub_manager():
    banner("2. GRUB2 Manager")
    mgr = GrubManager(boot_dir=BOOT_DIR)

    section("Module manager")
    mm = GrubModuleManager()
    modules = mm.list_modules()
    print(f"  Available: {len(modules)}")

    section("Creating menu entry")
    entry = GrubMenuEntry(
        title="UmerOS 1.0",
        linux_path="/boot/vmlinuz-6.1.0-umeros",
        initrd_path="/boot/initrd.img",
        root="/dev/sda1",
        options="root=/dev/sda1 ro quiet",
    )
    print(f"  Title: {entry.title}")
    print(f"  Kernel: {entry.linux_path}")

    section("GRUB config generation")
    config = mgr.generate_grub_cfg()
    print(f"  Config lines: {len(config.splitlines())}")

    section("Status")
    status = mgr.status()
    print(f"  GRUB dir: {status['grub_dir']}")
    print(f"  Modules: {status.get('modules', 'N/A')}")

    return mgr


def demo_systemd_boot():
    banner("3. systemd-boot Manager")
    mgr = SystemdBootManager(boot_dir=BOOT_DIR)

    section("Loader config")
    loader = LoaderConfig()
    loader.default = "umeros.conf"
    loader.timeout = 5
    loader.console_mode = 0
    print(f"  Default: {loader.default}")
    print(f"  Timeout: {loader.timeout}s")

    section("Boot entry")
    entry = BootEntry(
        title="UmerOS 1.0",
        linux="/vmlinuz-6.1.0-umeros",
        initrd="/initrd.img",
        options="root=/dev/sda1 ro quiet splash",
        version="6.1.0-umeros",
    )
    print(f"  Title: {entry.title}")
    print(f"  Linux: {entry.linux}")
    print(f"  Version: {entry.version}")

    section("Status")
    status = mgr.status()
    print(f"  ESP: {status['loader_dir']}")
    print(f"  Entries: {status['total_entries']}")

    return mgr


def demo_efi_system():
    banner("4. EFI System Partition Manager")
    mgr = EFISystemManager(esp_mount=BOOT_DIR / "efi", data_dir=BOOT_DIR / "efi_data")

    section("Secure Boot")
    sb = SecureBootManager(data_dir=BOOT_DIR / "efi_data")
    state = sb.state
    print(f"  State: {state.value}")
    print(f"  Setup mode: {state == SecureBootState.SETUP_MODE}")

    section("Status")
    status = mgr.status()
    print(f"  ESP: {status['esp']['esp_mount']}")
    print(f"  Size: {status['esp'].get('total_size_bytes', 'N/A')}")

    return mgr


def demo_boot_params():
    banner("5. Boot Parameters & Sysctl")
    mgr = BootParamsManager()

    section("Kernel command line")
    cmdline = KernelCommandLine()
    cmdline.set_param("root", "/dev/sda1", is_flag=False)
    cmdline.set_param("ro", is_flag=True)
    cmdline.set_param("quiet", is_flag=True)
    cmdline.set_param("splash", is_flag=True)
    print(f"  Command line: {cmdline.build(cmdline._params)}")

    section("Sysctl manager")
    sysctl = SysctlManager()
    print(f"  Common params loaded: {len(sysctl.list_params())}")

    section("Profiles")
    for name, preset in SysctlManager.PROFILES.items():
        print(f"  {name}: {len(preset)} params")

    section("Status")
    status = mgr.status()
    print(f"  Sysctl params: {status['sysctl']['total_params']}")

    return mgr


def demo_microcode():
    banner("6. Microcode Update Manager")
    mgr = MicrocodeManager()

    section("CPU detection")
    cpu = mgr.detect_cpu()
    print(f"  Vendor: {cpu.vendor.value}")
    print(f"  Model: {cpu.model}")
    print(f"  Family: {cpu.family}, Model: {cpu.model}")

    section("Firmware")
    print(f"  (firmware detection not available in this demo)")

    section("Status")
    status = mgr.status()
    print(f"  Vendor: {status['cpu']['vendor']}")
    print(f"  Current microcode: {status.get('current_microcode', 'N/A')}")

    return mgr


def demo_boot_splash():
    banner("7. Boot Splash Manager")
    mgr = BootSplashManager()

    section("Plymouth themes")
    themes = mgr.plymouth.list_themes()
    for t in themes:
        print(f"  {t.name}: {t.description[:50]}")

    section("Frame buffer")
    fb = FramebufferManager()
    fb_config = fb.detect_framebuffer()
    print(f"  Resolution: {fb_config.resolution}")
    print(f"  Depth: {fb_config.depth}bpp")

    section("GRUB entry with splash")
    print(mgr.generate_grub_entry()[:200] + "...")

    section("Status")
    status = mgr.status()
    print(f"  Technology: {status['technology']}")

    return mgr


def demo_crash_kernel():
    banner("8. Crash Kernel (kdump)")
    mgr = CrashKernelManager(
        boot_dir=BOOT_DIR,
        config_path=BOOT_DIR / "kdump.conf",
    )

    section("Configuration")
    config = mgr.config_manager.get_config()
    print(f"  Kernel: {config.kdump_kernel}")
    print(f"  Path: {config.path}")
    print(f"  Auto reboot: {config.auto_reboot}")

    section("Memory reservation")
    reserve = mgr.kernel_builder.reserve_memory_mb()
    print(f"  Reserved: {reserve}MB")
    print(f"  Cmdline: {mgr.get_cmdline_reservation()}")

    section("GRUB config with kdump")
    print(mgr.get_grub_config()[:200] + "...")

    section("Status")
    status = mgr.status()
    print(f"  State: {status['state']}")
    print(f"  Memory reservation: {status['memory_reservation_mb']}MB")

    return mgr


def demo_integration():
    banner("Integration: Full Boot Configuration")

    section("Combined kernel command line")
    cmdline = KernelCommandLine()
    cmdline.set_param("root", "/dev/sda1", is_flag=False)
    cmdline.set_param("ro", is_flag=True)
    cmdline.set_param("quiet", is_flag=True)
    cmdline.set_param("splash", is_flag=True)
    cmdline.set_param("crashkernel", "512M", is_flag=False)
    cmdline.set_param("systemd.unit", "multi-user.target", is_flag=False)
    print(f"  Final cmdline: {cmdline.build(cmdline._params)}")

    section("GRUB entry")
    entry = GrubMenuEntry(
        title="UmerOS 1.0",
        linux_path="/boot/vmlinuz-6.1.0-umeros",
        initrd_path="/boot/initrd.img",
        uuid="1234-5678-90ab-cdef",
        options=cmdline.build(cmdline._params),
    )
    print(f"  Title: {entry.title}")
    print(f"  Kernel: {entry.linux_path}")
    print(f"  Options: {entry.options}")

    section("Systemd-boot entry")
    sd_entry = BootEntry(
        title="UmerOS 1.0",
        linux="/vmlinuz-6.1.0-umeros",
        initrd="/initrd.img",
        options=cmdline.build(cmdline._params),
        version="6.1.0-umeros",
    )
    print(f"  Title: {sd_entry.title}")
    print(f"  Linux: {sd_entry.linux}")
    print(f"  Options: {sd_entry.options}")

    section("EFI Secure Boot config")
    sb = SecureBootManager(data_dir=BOOT_DIR / "efi")
    print(f"  State: {sb.state.value}")
    print(f"  Keys managed: PK, KEK, db, dbx")


def main():
    parser = argparse.ArgumentParser(description="UmerOS Boot System Demo")
    parser.add_argument("--quick", action="store_true", help="Quick mode (fewer demos)")
    args = parser.parse_args()

    print("\n" + "=" * 72)
    print("  UmerOS Boot System - Complete Demo")
    print("=" * 72)

    # Ensure demo directory exists
    BOOT_DIR.mkdir(parents=True, exist_ok=True)

    # Run all demos
    demo_kernel_image()
    demo_grub_manager()
    demo_systemd_boot()
    demo_efi_system()
    demo_boot_params()
    demo_microcode()
    demo_boot_splash()
    demo_crash_kernel()
    demo_integration()

    banner("Demo Complete!")
    print("\nAll boot system modules demonstrated successfully.")
    print(f"Sample files created in: {BOOT_DIR}")
    print("\nModules implemented:")
    print("  [x] kernel_image.py   - Kernel image management")
    print("  [x] grub_manager.py    - GRUB2 configuration manager")
    print("  [x] systemd_boot.py    - systemd-boot loader manager")
    print("  [x] efi_system.py      - EFI System Partition & Secure Boot")
    print("  [x] boot_params.py     - Kernel cmdline & sysctl")
    print("  [x] microcode.py       - CPU microcode updates")
    print("  [x] boot_splash.py     - Boot splash & framebuffer")
    print("  [x] crash_kernel.py    - kdump crash kernel")
    print("  [x] __init__.py        - Package init")
    print("  [x] demo_boot.py       - This demo")


if __name__ == "__main__":
    main()
