"""
UmerOS /media - Removable Media Subsystem
==========================================

FHS/TLDP-compliant mount-point management for removable devices.

Modules
-------
- **media_types** – ``MediaType`` enum, ``MountNaming``, ``MediaDescriptor``.
- **mount_manager** – Allocate/release numbered mount points and symlinks.
- **device_info** – Device detection via sysfs/blkid or simulation.
- **cleanup** – Stale mount-point cleanup and FHS validation.
- **hotplug** – In-process event bus for connect/disconnect events.

Quick start::

    from media import MountManager, MediaType, scan_devices

    mgr = MountManager()
    mgr.bootstrap()

    devices = scan_devices()
    for desc in devices.descriptors:
        slot = mgr.allocate(desc.media_type, desc.device_path,
                            label=desc.label)
        print(f"Mounted at {slot.mount_point}")
"""

from __future__ import annotations

from .cleanup import CleanupConfig, CleanupResult, cleanup_media, validate_fhs_media
from .device_info import DeviceScanResult, detect_media_type, get_mount_info, scan_devices
from .hotplug import HotplugAction, HotplugBus, HotplugEvent, get_default_bus
from .media_types import (
    MediaDescriptor,
    MediaType,
    MountNaming,
    MOUNT_NAMING,
)
from .mount_manager import MediaConfig, MountManager, mount_point_for, symlink_for

__all__ = [
    # media_types
    "MediaType",
    "MountNaming",
    "MOUNT_NAMING",
    "MediaDescriptor",
    # mount_manager
    "MediaConfig",
    "MountManager",
    "mount_point_for",
    "symlink_for",
    # device_info
    "DeviceScanResult",
    "scan_devices",
    "detect_media_type",
    "get_mount_info",
    # cleanup
    "CleanupConfig",
    "CleanupResult",
    "cleanup_media",
    "validate_fhs_media",
    # hotplug
    "HotplugAction",
    "HotplugEvent",
    "HotplugBus",
    "get_default_bus",
]
