"""
UmerOS SysFS Module
====================
Linux kernel /sys filesystem interface.
Implements sysfs attributes, kobjects, and bus/model hierarchy.

Reference: docs.kernel.org/userspace-api/sysfs.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Callable, Dict, List, Optional
import threading


# ============================================================================
# Constants
# ============================================================================

SUCCESS: int = 0
ERROR: int = 1
EINVAL: int = 22
ENOENT: int = 2
EACCES: int = 13
ENODATA: int = 61


class SysFSPerm(IntEnum):
    """SysFS permissions."""
    SYSFS_PERM_READ: int = 0o444
    SYSFS_PERM_WRITE: int = 0o222
    SYSFS_PERM_RW: int = 0o666
    SYSFS_PERM_WORLD: int = 0o777


class SysFSAttrType(IntEnum):
    """SysFS attribute types."""
    SYSFS_ATTR_REGULAR: int = 0
    SYSFS_ATTR_BINARY: int = 1
    SYSFS_ATTR_LINK: int = 2


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class SysFSAttribute:
    """A single sysfs attribute file."""
    name: str = ""
    permissions: SysFSPerm = SysFSPerm.SYSFS_PERM_READ
    value: bytes = b""
    show_handler: Optional[Callable[[], bytes]] = None
    store_handler: Optional[Callable[[bytes], int]] = None
    attr_type: SysFSAttrType = SysFSAttrType.SYSFS_ATTR_REGULAR

    def show(self) -> bytes:
        """Read the attribute value."""
        if self.show_handler:
            return self.show_handler()
        return self.value

    def store(self, data: bytes) -> int:
        """Write the attribute value."""
        if self.store_handler:
            return self.store_handler(data)
        self.value = data
        return SUCCESS

    def is_readable(self) -> bool:
        """Check if attribute is readable."""
        return bool(self.permissions.value & 0o444)

    def is_writable(self) -> bool:
        """Check if attribute is writable."""
        return bool(self.permissions.value & 0o222)


@dataclass
class SysFSKObject:
    """A sysfs kobject representation."""
    name: str = ""
    parent: Optional[SysFSKObject] = None
    path: str = ""
    attributes: Dict[str, SysFSAttribute] = field(default_factory=dict)
    children: Dict[str, SysFSKObject] = field(default_factory=dict)
    ktype: str = ""
    ref_count: int = 1

    def add_attribute(self, name: str, value: bytes, perms: SysFSPerm = SysFSPerm.SYSFS_PERM_READ) -> SysFSAttribute:
        """Add an attribute to this kobject."""
        attr = SysFSAttribute(name=name, permissions=perms, value=value)
        self.attributes[name] = attr
        return attr

    def add_child(self, name: str) -> SysFSKObject:
        """Add a child kobject."""
        child = SysFSKObject(name=name, parent=self, path=f"{self.path}/{name}")
        self.children[name] = child
        return child

    def read_attr(self, name: str) -> Optional[bytes]:
        """Read an attribute."""
        attr = self.attributes.get(name)
        if attr:
            return attr.show()
        return None

    def write_attr(self, name: str, data: bytes) -> int:
        """Write an attribute."""
        attr = self.attributes.get(name)
        if attr:
            return attr.store(data)
        return ENOENT

    def list_attrs(self) -> List[str]:
        """List attribute names."""
        return list(self.attributes.keys())

    def list_children(self) -> List[str]:
        """List child kobject names."""
        return list(self.children.keys())


@dataclass
class SysFSBus:
    """Sysfs bus representation."""
    name: str = ""
    devices: Dict[str, SysFSKObject] = field(default_factory=dict)
    drivers: Dict[str, SysFSKObject] = field(default_factory=dict)
    kobject: SysFSKObject = field(default_factory=SysFSKObject)

    def add_device(self, name: str) -> SysFSKObject:
        """Add a device to this bus."""
        dev = self.kobject.add_child(name)
        dev.ktype = "device"
        self.devices[name] = dev
        return dev

    def add_driver(self, name: str) -> SysFSKObject:
        """Add a driver to this bus."""
        drv = self.kobject.add_child(name)
        drv.ktype = "driver"
        self.drivers[name] = drv
        return drv

    def bind(self, device_name: str, driver_name: str) -> int:
        """Bind a device to a driver."""
        if device_name not in self.devices or driver_name not in self.drivers:
            return ENOENT
        return SUCCESS

    def unbind(self, device_name: str) -> int:
        """Unbind a device from its driver."""
        self.devices.get(device_name)
        return SUCCESS


@dataclass
class SysFSClass:
    """Sysfs device class."""
    name: str = ""
    devices: Dict[str, SysFSKObject] = field(default_factory=dict)
    kobject: SysFSKObject = field(default_factory=SysFSKObject)

    def add_device(self, name: str) -> SysFSKObject:
        """Add a device to this class."""
        dev = self.kobject.add_child(name)
        dev.ktype = "class_device"
        self.devices[name] = dev
        return dev

    def remove_device(self, name: str) -> int:
        """Remove a device from this class."""
        self.devices.pop(name, None)
        self.kobject.children.pop(name, None)
        return SUCCESS

    def get_device(self, name: str) -> Optional[SysFSKObject]:
        """Get a device by name."""
        return self.devices.get(name)


# ============================================================================
# SysFS Filesystem
# ============================================================================

class SysFS:
    """Linux /sys filesystem simulation."""
    root: SysFSKObject = field(default_factory=lambda: SysFSKObject(name="/sys", path="/sys"))
    buses: Dict[str, SysFSBus] = field(default_factory=dict)
    classes: Dict[str, SysFSClass] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self._build_standard_entries()

    def _build_standard_entries(self) -> None:
        """Build standard sysfs entries."""
        self.root.add_attribute("kernel", b"UmerOS\n")
        self.root.add_attribute("version", b"1.0\n")
        self.root.add_attribute("hostname", b"umeros\n")
        bus = self.root.add_child("bus")
        dev = self.root.add_child("class")
        dev = self.root.add_child("devices")
        dev = self.root.add_attribute("vm.stat", b"nr_free_pages 0\n")
        self.root.add_attribute("power", b"")
        self.root.add_attribute("firmware", b"")

    def create_bus(self, name: str) -> SysFSBus:
        """Create a bus entry."""
        with self.lock:
            bus_kobj = self.root.add_child(name)
            bus = SysFSBus(name=name, kobject=bus_kobj)
            self.buses[name] = bus
        return bus

    def create_class(self, name: str) -> SysFSClass:
        """Create a class entry."""
        with self.lock:
            cls_kobj = self.root.add_child(name)
            cls = SysFSClass(name=name, kobject=cls_kobj)
            self.classes[name] = cls
        return cls

    def read(self, path: str) -> Optional[bytes]:
        """Read a sysfs attribute by path."""
        parts = path.strip("/").split("/")
        current = self.root
        for i, part in enumerate(parts[1:], 1):
            if part in current.attributes:
                return current.attributes[part].show()
            if part in current.children:
                current = current.children[part]
            else:
                return None
        return None

    def write(self, path: str, data: bytes) -> int:
        """Write to a sysfs attribute by path."""
        parts = path.strip("/").split("/")
        current = self.root
        for i, part in enumerate(parts[1:], 1):
            if part in current.attributes:
                return current.attributes[part].store(data)
            if part in current.children:
                current = current.children[part]
            else:
                return ENOENT
        return EINVAL

    def list_dir(self, path: str) -> List[str]:
        """List entries in a sysfs directory."""
        parts = path.strip("/").split("/")
        current = self.root
        for part in parts[1:]:
            if part in current.children:
                current = current.children[part]
            else:
                return []
        entries = list(current.children.keys())
        entries.extend(current.attributes.keys())
        return entries

    def symlink(self, target: str, link_name: str) -> int:
        """Create a symlink."""
        self.root.add_attribute(link_name, target.encode(), SysFSPerm.SYSFS_PERM_READ)
        return SUCCESS

    def unlink(self, path: str) -> int:
        """Remove a symlink or attribute."""
        parts = path.strip("/").split("/")
        current = self.root
        for part in parts[1:-1]:
            if part in current.children:
                current = current.children[part]
            else:
                return ENOENT
        last = parts[-1]
        current.attributes.pop(last, None)
        current.children.pop(last, None)
        return SUCCESS

    def statvfs(self) -> Dict[str, int]:
        """Get filesystem statistics."""
        return {"f_bsize": 4096, "f_blocks": 0, "f_bfree": 0, "f_bavail": 0}


# ============================================================================
# Global Singleton Accessors
# ============================================================================

_global_sysfs: Optional[SysFS] = None


def get_global_sysfs() -> SysFS:
    """Get global SysFS instance."""
    global _global_sysfs
    if _global_sysfs is None:
        _global_sysfs = SysFS()
    return _global_sysfs
