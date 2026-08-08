"""
UmerOS /dev — Memory and I/O port access devices.

Linux /dev/mem, /dev/kmem, /dev/port:
  /dev/mem   — Physical memory access (major 1, minor 1)
  /dev/kmem  — Kernel virtual memory (major 1, minor 2)
  /dev/port  — I/O port access (major 1, minor 4)

Security: CONFIG_STRICT_DEVMEM restricts /dev/mem to only
the first 1MB and non-RAM regions. CONFIG_IO_STRICT_DEVMEM
blocks /dev/mem access to all kernel-owned regions.

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
import os
import struct
from typing import Any, Dict, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.MemoryDevices")


class MemoryDevice:
    """/dev/mem — Physical memory access device.

    Provides raw read/write access to the system's physical address space.
    In a real kernel this is used for low-level hardware probing,
    BIOS flashing, and debugging. Modern kernels enforce strict
    devmem2 restrictions via CONFIG_STRICT_DEVMEM.
    """

    MAJOR = 1
    MINOR = 1
    STRICT_DEVMEM = True  # Restrict to first 1MB + non-RAM regions
    ALLOWED_RANGES = [
        (0x00000000, 0x0009FFFF),  # BIOS, VGA, legacy
        (0x000A0000, 0x000FFFFF),  # Video memory, ROM area
        (0x00100000, 0x001FFFFF),  # APIC, IOAPIC (varies)
    ]

    def __init__(self):
        self._data: Dict[int, int] = {}
        self._register()
        log.info("MemoryDevice /dev/mem created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="mem", path="/dev/mem", dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o640,
            description="Physical memory access",
            read_callback=self._read,
            write_callback=self._write,
            ioctl_callback=self._ioctl,
        ))

    def _check_access(self, offset: int, size: int) -> bool:
        if not self.STRICT_DEVMEM:
            return True
        end = offset + size
        for start, end_range in self.ALLOWED_RANGES:
            if offset >= start and end <= end_range + 1:
                return True
        log.warning("devmem: blocked access to 0x%lx-%lx (STRICT_DEVMEM)", offset, end)
        return False

    def _read(self, size: int, offset: int = 0) -> bytes:
        if not self._check_access(offset, size):
            return b"\x00" * size
        return bytes(self._data.get(offset + i, 0) for i in range(size))

    def _write(self, data: bytes, offset: int = 0) -> int:
        if not self._check_access(offset, len(data)):
            return 0
        for i, byte in enumerate(data):
            self._data[offset + i] = byte
        log.info("devmem: wrote %d bytes at 0x%lx", len(data), offset)
        return len(data)

    def _ioctl(self, request: int, arg: Any) -> int:
        # MEM_GETINFO = 0xCC
        if request == 0xCC:
            return 0x1000000  # 16MB simulated
        return -1

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/mem",
            "major": self.MAJOR,
            "minor": self.MINOR,
            "strict_devmem": self.STRICT_DEVMEM,
            "allowed_ranges": [f"0x{s:08x}-0x{e:08x}" for s, e in self.ALLOWED_RANGES],
        }


class KernelMemoryDevice:
    """/dev/kmem — Kernel virtual memory access device.

    Provides read access to kernel virtual memory. Unlike /dev/mem,
    this maps to the kernel's virtual address space, not physical.
    Modern kernels remove /dev/kmem entirely (CONFIG_DEVKMEM=n).
    """

    MAJOR = 1
    MINOR = 2
    AVAILABLE = False  # Not available in modern kernels

    def __init__(self):
        self._register()
        log.info("MemoryDevice /dev/kmem created (available=%s)", self.AVAILABLE)

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="kmem", path="/dev/kmem", dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o640,
            description="Kernel virtual memory (deprecated)",
            read_callback=self._read,
        ))

    def _read(self, size: int, offset: int = 0) -> bytes:
        if not self.AVAILABLE:
            log.warning("kmem: not available (CONFIG_DEVKMEM=n)")
            return b"\x00" * size
        return b"\x00" * size

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/kmem",
            "major": self.MAJOR,
            "minor": self.MINOR,
            "available": self.AVAILABLE,
            "note": "Removed in modern kernels (since 2.6.26)",
        }


class PortDevice:
    """/dev/port — I/O port access device.

    Provides read/write access to the x86 I/O port address space
    (ports 0x0000-0xFFFF). Used for low-level hardware access
    from userspace (e.g., parallel port, legacy ISA devices).
    """

    MAJOR = 1
    MINOR = 4
    MAX_PORT = 0xFFFF

    def __init__(self):
        self._ports: Dict[int, int] = {}
        self._register()
        log.info("MemoryDevice /dev/port created")

    def _register(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="port", path="/dev/port", dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR, mode=0o640,
            description="I/O port access",
            read_callback=self._read,
            write_callback=self._write,
        ))

    def _read(self, size: int, offset: int = 0) -> bytes:
        result = bytearray()
        for i in range(size):
            port = offset + i
            if port > self.MAX_PORT:
                break
            result.append(self._ports.get(port, 0))
        return bytes(result)

    def _write(self, data: bytes, offset: int = 0) -> int:
        written = 0
        for i, byte in enumerate(data):
            port = offset + i
            if port > self.MAX_PORT:
                break
            self._ports[port] = byte
            written += 1
        log.info("ioport: wrote %d bytes to ports 0x%04x-0x%04x",
                 written, offset, offset + written - 1)
        return written

    def inb(self, port: int) -> int:
        """Read a byte from an I/O port (programmatic API)."""
        if port > self.MAX_PORT:
            return 0
        return self._ports.get(port, 0)

    def outb(self, port: int, value: int) -> None:
        """Write a byte to an I/O port (programmatic API)."""
        if port <= self.MAX_PORT:
            self._ports[port] = value & 0xFF

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/port",
            "major": self.MAJOR,
            "minor": self.MINOR,
            "max_port": f"0x{self.MAX_PORT:04x}",
            "active_ports": len(self._ports),
        }
