"""
UmerOS Device Manager
Based on Greg Kroah-Hartman's udev paper (OLS 2003)

The device manager handles:
- Device node creation and removal in /dev
- Major/minor number allocation
- Device type tracking (block, char, FIFO, socket, symlink, directory)
- Symlink management for device aliases
"""

from __future__ import annotations

import logging
import stat
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """Device types."""
    BLOCK = "block"
    CHAR = "char"
    FIFO = "fifo"
    SOCKET = "socket"
    SYMLINK = "symlink"
    DIRECTORY = "directory"


@dataclass
class DeviceNode:
    """
    Represents a device node in /dev.

    Each device node has:
    - name: The device name (e.g., "sda", "tty0")
    - dev_type: The type of device
    - major/minor: Device numbers for kernel identification
    - mode: Permission bits
    - uid/gid: Ownership
    - symlinks: Alternative paths to this device
    """
    name: str
    dev_type: DeviceType
    major: int = 0
    minor: int = 0
    mode: int = 0o666
    uid: int = 0
    gid: int = 0
    symlinks: list[Path] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.name:
            raise ValueError("Device node name cannot be empty")
        if self.dev_type in (DeviceType.BLOCK, DeviceType.CHAR):
            if self.major < 0 or self.minor < 0:
                raise ValueError(f"Invalid major/minor: {self.major}:{self.minor}")

    @property
    def dev_number(self) -> int:
        """Get device number (major << 8 | minor)."""
        return (self.major << 8) | self.minor

    @property
    def is_block(self) -> bool:
        return self.dev_type == DeviceType.BLOCK

    @property
    def is_char(self) -> bool:
        return self.dev_type == DeviceType.CHAR

    def symlink_to(self, target: Path):
        """Add a symlink pointing to this device."""
        if target not in self.symlinks:
            self.symlinks.append(target)

    def remove_symlink(self, target: Path):
        """Remove a symlink."""
        if target in self.symlinks:
            self.symlinks.remove(target)

    def to_dict(self) -> dict[str, Any]:
        """Serialize device node to dictionary."""
        return {
            "name": self.name,
            "type": self.dev_type.value,
            "major": self.major,
            "minor": self.minor,
            "mode": oct(self.mode),
            "uid": self.uid,
            "gid": self.gid,
            "dev_number": self.dev_number,
            "symlinks": [str(s) for s in self.symlinks],
            "attributes": self.attributes,
        }


class DeviceManager:
    """
    Manages device nodes in /dev.

    Based on the udev model:
    - Maintains a registry of all device nodes
    - Provides create/remove/query operations
    - Manages symlinks for device aliases
    - Handles major/minor number allocation
    """

    def __init__(self, dev_path: Path | None = None):
        self.dev_path = dev_path or Path("/dev")
        self._devices: dict[str, DeviceNode] = {}
        self._by_devnum: dict[int, str] = {}
        self._symlink_map: dict[Path, str] = {}
        self._major_allocators: dict[int, MinorAllocator] = {}
        self._lock = None  # Would use threading.Lock in real implementation

    def create(self, device: DeviceNode) -> DeviceNode:
        """
        Create a device node.

        If the device already exists, update it. Otherwise, create new.
        """
        if device.name in self._devices:
            logger.warning(f"Device {device.name} already exists, updating")
            old = self._devices[device.name]
            # Update symlinks
            for symlink in old.symlinks:
                if symlink in self._symlink_map:
                    del self._symlink_map[symlink]

        self._devices[device.name] = device
        self._by_devnum[device.dev_number] = device.name

        # Register symlinks
        for symlink in device.symlinks:
            self._symlink_map[symlink] = device.name

        logger.debug(f"Created device: {device.name} ({device.dev_type.value}) "
                     f"major={device.major} minor={device.minor}")

        return device

    def remove(self, name: str) -> DeviceNode | None:
        """Remove a device node and its symlinks."""
        device = self._devices.pop(name, None)
        if device:
            self._by_devnum.pop(device.dev_number, None)
            for symlink in device.symlinks:
                self._symlink_map.pop(symlink, None)
            logger.debug(f"Removed device: {name}")
        return device

    def get(self, name: str) -> DeviceNode | None:
        """Get device node by name."""
        return self._devices.get(name)

    def get_by_devnum(self, major: int, minor: int) -> DeviceNode | None:
        """Get device node by major/minor number."""
        devnum = (major << 8) | minor
        name = self._by_devnum.get(devnum)
        return self._devices.get(name) if name else None

    def get_by_symlink(self, symlink: Path) -> DeviceNode | None:
        """Get device node by symlink path."""
        name = self._symlink_map.get(symlink)
        return self._devices.get(name) if name else None

    def list_devices(
        self,
        dev_type: DeviceType | None = None,
        subsystem: str | None = None,
    ) -> list[DeviceNode]:
        """List all devices, optionally filtered by type or subsystem."""
        devices = list(self._devices.values())

        if dev_type:
            devices = [d for d in devices if d.dev_type == dev_type]

        if subsystem:
            # Filter by subsystem attribute
            devices = [
                d for d in devices
                if d.attributes.get("subsystem") == subsystem
            ]

        return devices

    def list_block_devices(self) -> list[DeviceNode]:
        """List all block devices."""
        return self.list_devices(dev_type=DeviceType.BLOCK)

    def list_char_devices(self) -> list[DeviceNode]:
        """List all character devices."""
        return self.list_devices(dev_type=DeviceType.CHAR)

    def allocate_major_minor(
        self,
        dev_type: DeviceType = DeviceType.CHAR,
        requested_major: int | None = None,
    ) -> tuple[int, int]:
        """
        Allocate major/minor numbers.

        - Block devices: major 8 (sd*), 253 (dm-*), 259 (nvme*), etc.
        - Char devices: major 4 (tty), 13 (input), 188 (usb-serial), etc.
        """
        if requested_major:
            major = requested_major
        else:
            major = 8 if dev_type == DeviceType.BLOCK else 188

        if major not in self._major_allocators:
            self._major_allocators[major] = MinorAllocator(major)

        minor = self._major_allocators[major].allocate()
        return major, minor

    def free_major_minor(self, major: int, minor: int):
        """Free major/minor numbers."""
        if major in self._major_allocators:
            self._major_allocators[major].free(minor)

    def get_stats(self) -> dict[str, Any]:
        """Get device manager statistics."""
        block_count = len(self.list_block_devices())
        char_count = len(self.list_char_devices())
        total_symlinks = sum(len(d.symlinks) for d in self._devices.values())

        return {
            "total_devices": len(self._devices),
            "block_devices": block_count,
            "char_devices": char_count,
            "total_symlinks": total_symlinks,
            "symlink_map_size": len(self._symlink_map),
        }


class MinorAllocator:
    """
    Allocates minor numbers for a given major number.

    Minor numbers are managed per-major:
    - sd* (major 8): minors 0-255 for sda-sdz, 256+ for partitions
    - tty (major 4): minors 0-63 for tty0-tty63
    """

    def __init__(self, major: int, max_minor: int = 256):
        self.major = major
        self.max_minor = max_minor
        self._allocated: set[int] = set()
        self._next_minor = 0

    def allocate(self) -> int:
        """Allocate next available minor number."""
        if len(self._allocated) >= self.max_minor:
            raise RuntimeError(f"No more minor numbers for major {self.major}")

        # Find next available
        minor = self._next_minor
        while minor in self._allocated:
            minor = (minor + 1) % self.max_minor

        self._allocated.add(minor)
        self._next_minor = (minor + 1) % self.max_minor
        return minor

    def free(self, minor: int):
        """Free a minor number."""
        self._allocated.discard(minor)

    def is_allocated(self, minor: int) -> bool:
        """Check if a minor number is allocated."""
        return minor in self._allocated

    @property
    def allocated_count(self) -> int:
        return len(self._allocated)

    @property
    def free_count(self) -> int:
        return self.max_minor - len(self._allocated)
