"""
UmerOS /dev — Miscellaneous system control devices.

Linux misc system device files:
  /dev/btrfs-control — Btrfs filesystem control (major 10, minor 234)
  /dev/dax0.0-N      — DAX (Direct Access) devices (major 241)
  /dev/vga_arbiter    — VGA arbitration (major 10, minor 229)

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.MiscSystemDevices")


class BtrfsControlDevice:
    """Btrfs control device — /dev/btrfs-control.

    Used by btrfs-progs to manage Btrfs filesystems:
      - Create subvolumes
      - Manage snapshots
      - Device add/remove

    Major 10, minor 234.
    """

    MAJOR = 10
    MINOR = 234

    # ioctl commands
    BTRFS_IOC_SCAN_DEV = 0xc0109403
    BTRFS_IOC_RM_DEV = 0xc0109404
    BTRFS_IOC_BALANCE = 0xc0409405
    BTRFS_IOC_SNAP_CREATE = 0xc0409401
    BTRFS_IOC_DEFRAG = 0xc0009402
    BTRFS_IOC_RESIZE = 0xc0109406
    BTRFS_IOC_CLONE = 0x80089409
    BTRFS_IOC_ADD_DEV = 0xc010940a
    BTRFS_IOC_SNAP_CREATE_V2 = 0xc0409410
    BTRFS_IOC_SUBVOL_CREATE = 0xc0409411
    BTRFS_IOC_SNAP_DESTROY = 0xc0409412
    BTRFS_IOC_DEFRAG_RANGE = 0xc0109416
    BTRFS_IOC_TREE_SEARCH = 0xc0009417
    BTRFS_IOC_TREE_SEARCH_V2 = 0xc0009417
    BTRFS_IOC_INO_LOOKUP = 0xc0089418

    def __init__(self):
        self._create_device()
        log.info("BtrfsControlDevice created")

    def _create_device(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="btrfs-control", path="/dev/btrfs-control",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR,
            mode=0o600,
            description="Btrfs filesystem control",
            ioctl_callback=lambda req, arg: self._on_ioctl(req, arg),
        ))

    def _on_ioctl(self, request: int, arg: Any) -> int:
        """Handle btrfs ioctl commands."""
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {"major": self.MAJOR, "minor": self.MINOR, "path": "/dev/btrfs-control"}

    def __repr__(self) -> str:
        return "<BtrfsControlDevice>"


class DAXDevice:
    """DAX (Direct Access) devices — /dev/dax*.

    Persistent Memory (PMEM) direct access devices:
      /dev/dax0.0, /dev/dax0.1, ... — DAX regions
      /dev/dax1.0, /dev/dax1.1, ...

    Major 241: dax0.0 = 241:0, dax0.1 = 241:1, ...

    DAX allows byte-addressable access to persistent memory,
    bypassing the page cache for ultra-low-latency I/O.
    """

    DAX_MAJOR = 241
    MAX_DEVICES = 8

    def __init__(self):
        self._create_devices()
        log.info("DAXDevice created (%d devices)", self.MAX_DEVICES)

    def _create_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        for i in range(self.MAX_DEVICES):
            name = f"dax{i}.0"
            path = f"/dev/{name}"
            mgr.create_node(DeviceNode(
                name=name, path=path, dev_type=DeviceType.CHAR,
                major=self.DAX_MAJOR, minor=i,
                mode=0o660,
                description=f"DAX region {i}",
                ioctl_callback=lambda req, arg: self._on_ioctl(req, arg),
            ))

    def _on_ioctl(self, request: int, arg: Any) -> int:
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {"major": self.DAX_MAJOR, "max_devices": self.MAX_DEVICES}

    def __repr__(self) -> str:
        return f"<DAXDevice devices={self.MAX_DEVICES}>"


class VGAArbiterDevice:
    """VGA arbiter device — /dev/vga_arbiter.

    VGA arbitration for multi-GPU systems:
      Controls which GPU owns VGA legacy I/O ports.
      Used by X.org for multi-head configurations.

    Major 10, minor 229.
    """

    MAJOR = 10
    MINOR = 229

    # ioctl commands
    VGA_ARB_GET_VERSION = 0x40046100
    VGA_ARB_GET_STATE = 0x40046101
    VGA_ARB_SET_STATE = 0x40046102

    def __init__(self):
        self._create_device()
        log.info("VGAArbiterDevice created")

    def _create_device(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="vga_arbiter", path="/dev/vga_arbiter",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=self.MINOR,
            mode=0o600,
            description="VGA arbitration",
            ioctl_callback=lambda req, arg: self._on_ioctl(req, arg),
        ))

    def _on_ioctl(self, request: int, arg: Any) -> int:
        if request == self.VGA_ARB_GET_VERSION:
            return 1  # version 1
        return 0

    def get_info(self) -> Dict[str, Any]:
        return {"major": self.MAJOR, "minor": self.MINOR, "path": "/dev/vga_arbiter"}

    def __repr__(self) -> str:
        return "<VGAArbiterDevice>"
