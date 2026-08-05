"""
Umer OS /boot hierarchy — Boot management modules.

FHS 3.0 /boot requirements:
- Kernel files (vmlinuz, vmlinux)
- Boot loader data (GRUB, systemd-boot)
- initrd/initramfs images
- System.map files
- Configuration files (grub.cfg, etc.)

Author:  Umer OS Project
Licence: Apache 2.0
"""

from boot.boot_manager import BootManager, get_boot_manager
from boot.initrd_manager import InitrdManager, get_initrd_manager

__all__ = [
    "BootManager",
    "get_boot_manager",
    "InitrdManager",
    "get_initrd_manager",
]
