"""
UmerOS /media - Removable Media Subsystem
==========================================

FHS/TLDP-compliant mount-point management for removable devices.

Modules
-------
- **media_types** - ``MediaType`` enum, ``MountNaming``, ``MediaDescriptor``.
- **mount_manager** - Allocate/release numbered mount points and symlinks.
- **device_info** - Device detection via sysfs/blkid or simulation.
- **cleanup** - Stale mount-point cleanup and FHS validation.
- **hotplug** - In-process event bus for connect/disconnect events.
- **filesystem** - Filesystem type detection and validation.
- **mount_ops** - Low-level mount/unmount/remount operations.
- **auto_mount** - Auto-mount daemon for removable media.
- **permissions** - User/group access control (plugdev, storage).
- **fstab** - /etc/fstab integration.
- **udisks2** - UDisks2 D-Bus interface simulation.

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
from .filesystem import FsType, detect_fs_type, validate_fs_type, mount_options_for, SUPPORTED_FS
from .mount_ops import (
    MountResult as MountOpResult,
    mount,
    unmount,
    remount,
    is_mounted,
    get_mount_options,
    sync_mount,
    mount_status,
    set_simulation,
    get_sim_mounts,
    clear_sim_mounts,
)
from .auto_mount import (
    AutoMountDaemon,
    AutoMountEvent,
    AutoMountPolicy,
    AutoMountStatus,
    create_default_daemon,
)
from .permissions import (
    AccessLevel,
    GroupPolicy,
    MountPermission,
    MountPermissionManager,
    parse_fstab_uid,
    effective_user,
    STANDARD_MOUNT_GROUPS,
    GROUP_MEDIA_MAP,
)
from .fstab import (
    FstabEntry,
    FstabIssue,
    FstabIssueEntry,
    FstabManager,
    FstabValidator,
    make_removable_entry,
)
from .udisks2 import (
    UDisks2Block,
    UDisks2Client,
    UDisks2Drive,
    UDisks2Object,
    UDisks2ObjectType,
    get_removable_media_info,
)

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
    # filesystem
    "FsType",
    "detect_fs_type",
    "validate_fs_type",
    "mount_options_for",
    "SUPPORTED_FS",
    # mount_ops
    "MountOpResult",
    "mount",
    "unmount",
    "remount",
    "is_mounted",
    "get_mount_options",
    "sync_mount",
    "mount_status",
    "set_simulation",
    "get_sim_mounts",
    "clear_sim_mounts",
    # auto_mount
    "AutoMountDaemon",
    "AutoMountEvent",
    "AutoMountPolicy",
    "AutoMountStatus",
    "create_default_daemon",
    # permissions
    "AccessLevel",
    "GroupPolicy",
    "MountPermission",
    "MountPermissionManager",
    "parse_fstab_uid",
    "effective_user",
    "STANDARD_MOUNT_GROUPS",
    "GROUP_MEDIA_MAP",
    # fstab
    "FstabEntry",
    "FstabIssue",
    "FstabIssueEntry",
    "FstabManager",
    "FstabValidator",
    "make_removable_entry",
    # udisks2
    "UDisks2Block",
    "UDisks2Client",
    "UDisks2Drive",
    "UDisks2Object",
    "UDisks2ObjectType",
    "get_removable_media_info",
]
