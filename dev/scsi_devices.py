"""
UmerOS /dev — SCSI/SATA/SCSI Generic/Tape/BSG block and char devices.

  /dev structure:
  /dev/sda, /dev/sdb, ... /dev/sdz     — SCSI/SATA block devices
  /dev/sda1, /dev/sda2, ...             — Partitions
  /dev/sg0, /dev/sg1, ...               — SCSI generic (char 21:0-31)
  /dev/st0, /dev/st1, ...               — SCSI tape (char 9:0-31)
  /dev/nst0, /dev/nst1, ...             — Non-rewinding tape
  /dev/bsg/0:0:0:0                      — SCSI BSG (char 243:0+)

Major:Minor numbers:
  sd*     = 8:0+  (sda=8:0, sdb=8:16, ... sdz=8:208)
  sg*     = 21:0-21:31
  st*     = 9:0-9:31
  nst*    = 9:128-9:159
  bsg/*   = 243:0+

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.SCSIDevices")


class SCSIBlockDevice:
    """/dev/sd* — SCSI/SATA/USB block devices.

    Provides:
      /dev/sda through /dev/sdz — Up to 26 block devices
      /dev/sda1 through /dev/sda15 — Partitions per device

     major = 8, minor = (letter_index * 16) + partition
    sda  = 8:0,  sda1 = 8:1,  sda2 = 8:2,  ... sda15 = 8:15
    sdb  = 8:16, sdb1 = 8:17, sdb2 = 8:18, ... sdb15 = 8:31
    """

    MAJOR = 8
    MAX_DEVICES = 26   # sda-sdz
    MAX_PARTITIONS = 15

    def __init__(self):
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._register_devices()
        log.info("SCSIBlockDevice: registered %d sd* devices", self.MAX_DEVICES)

    def _register_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        for idx in range(self.MAX_DEVICES):
            letter = chr(ord("a") + idx)
            minor_base = idx * self.MAX_PARTITIONS

            # Whole disk device
            mgr.create_node(DeviceNode(
                name=f"sd{letter}", path=f"/dev/sd{letter}",
                dev_type=DeviceType.BLOCK,
                major=self.MAJOR, minor=minor_base, mode=0o660,
                description=f"SCSI disk {letter}",
                read_callback=lambda sz, n=idx: self._on_read(sz, n),
                write_callback=lambda d, n=idx: self._on_write(d, n),
                ioctl_callback=lambda r, a, n=idx: self._on_ioctl(r, a, n),
            ))

            # Partitions
            for part in range(1, self.MAX_PARTITIONS + 1):
                mgr.create_node(DeviceNode(
                    name=f"sd{letter}{part}",
                    path=f"/dev/sd{letter}{part}",
                    dev_type=DeviceType.BLOCK,
                    major=self.MAJOR, minor=minor_base + part,
                    mode=0o660,
                    description=f"SCSI disk {letter} partition {part}",
                    read_callback=lambda sz, n=idx, p=part: self._on_read_part(sz, n, p),
                    write_callback=lambda d, n=idx, p=part: self._on_write_part(d, n, p),
                ))

            self._devices[f"sd{letter}"] = {
                "partitions": [f"sd{letter}{p}" for p in range(1, self.MAX_PARTITIONS + 1)],
                "attached": False,
            }

    def _on_read(self, size: int, dev_idx: int) -> bytes:
        return b"\x00" * size

    def _on_write(self, data: bytes, dev_idx: int) -> int:
        return len(data)

    def _on_read_part(self, size: int, dev_idx: int, part: int) -> bytes:
        return b"\x00" * size

    def _on_write_part(self, data: bytes, dev_idx: int, part: int) -> int:
        return len(data)

    def _on_ioctl(self, request: int, arg: Any, dev_idx: int) -> int:
        # BLKGETSIZE = 0x1260
        if request == 0x1260:
            return 500 * 1024 * 1024  # 500GB simulated
        # BLKSSZGET = 0x1268
        if request == 0x1268:
            return 512  # sector size
        # HDIO_GETGEO = 0x0301
        if request == 0x0301:
            return 0
        return -1

    def attach_device(self, letter: str, size_bytes: int = 0) -> bool:
        key = f"sd{letter}"
        if key not in self._devices:
            return False
        self._devices[key]["attached"] = True
        self._devices[key]["size"] = size_bytes
        log.info("SCSI: attached %s (%d bytes)", key, size_bytes)
        return True

    def detach_device(self, letter: str) -> bool:
        key = f"sd{letter}"
        if key not in self._devices:
            return False
        self._devices[key]["attached"] = False
        log.info("SCSI: detached %s", key)
        return True

    def get_info(self) -> Dict[str, Any]:
        attached = [k for k, v in self._devices.items() if v["attached"]]
        return {
            "max_devices": self.MAX_DEVICES,
            "max_partitions": self.MAX_PARTITIONS,
            "attached": attached,
            "total_partitions": self.MAX_DEVICES * self.MAX_PARTITIONS,
        }


class SCSIGenericDevice:
    """/dev/sg* — SCSI generic character devices.

    Provides passthrough access to SCSI devices for commands like
    INQUIRY, READ CAPACITY, MODE SENSE, etc. Used by tools like
    sg_utils, lsscsi, and smartmontools.

    major 21, minor 0-31
    """

    MAJOR = 21
    MAX_SG = 32

    def __init__(self):
        self._devices: Dict[int, Dict[str, Any]] = {}
        self._register_devices()
        log.info("SCSIGenericDevice: registered %d sg* devices", self.MAX_SG)

    def _register_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        for i in range(self.MAX_SG):
            mgr.create_node(DeviceNode(
                name=f"sg{i}", path=f"/dev/sg{i}",
                dev_type=DeviceType.CHAR,
                major=self.MAJOR, minor=i, mode=0o660,
                description=f"SCSI generic device {i}",
                read_callback=lambda sz, n=i: self._on_read(sz, n),
                write_callback=lambda d, n=i: self._on_write(d, n),
            ))
            self._devices[i] = {"active": False}

    def _on_read(self, size: int, sg_num: int) -> bytes:
        return b"\x00" * size

    def _on_write(self, data: bytes, sg_num: int) -> int:
        return len(data)

    def get_info(self) -> Dict[str, Any]:
        return {
            "count": self.MAX_SG,
            "major": self.MAJOR,
            "active": sum(1 for v in self._devices.values() if v["active"]),
        }


class SCSITapeDevice:
    """/dev/st*, /dev/nst* — SCSI tape devices.

    Provides:
      /dev/st0-st31    — SCSI tape (rewinding on close)
      /dev/nst0-nst31  — Non-rewinding tape

    major 9, minor 0-31 (st*) and 128-159 (nst*)
    """

    MAJOR = 9
    MAX_TAPES = 32

    def __init__(self):
        self._tapes: Dict[str, Dict[str, Any]] = {}
        self._register_devices()
        log.info("SCSITapeDevice: registered %d tape devices", self.MAX_TAPES * 2)

    def _register_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        for i in range(self.MAX_TAPES):
            # Rewinding
            mgr.create_node(DeviceNode(
                name=f"st{i}", path=f"/dev/st{i}",
                dev_type=DeviceType.CHAR,
                major=self.MAJOR, minor=i, mode=0o660,
                description=f"SCSI tape {i} (rewind)",
                read_callback=lambda sz, n=i: self._on_read(sz, n, "st"),
                write_callback=lambda d, n=i: self._on_write(d, n, "st"),
            ))
            # Non-rewinding
            mgr.create_node(DeviceNode(
                name=f"nst{i}", path=f"/dev/nst{i}",
                dev_type=DeviceType.CHAR,
                major=self.MAJOR, minor=128 + i, mode=0o660,
                description=f"SCSI tape {i} (non-rewind)",
                read_callback=lambda sz, n=i: self._on_read(sz, n, "nst"),
                write_callback=lambda d, n=i: self._on_write(d, n, "nst"),
            ))
            self._tapes[f"st{i}"] = {"position": 0, "rewind_on_close": True}
            self._tapes[f"nst{i}"] = {"position": 0, "rewind_on_close": False}

    def _on_read(self, size: int, tape_num: int, prefix: str) -> bytes:
        key = f"{prefix}{tape_num}"
        tape = self._tapes.get(key, {})
        pos = tape.get("position", 0)
        tape["position"] = pos + size
        return b"\x00" * size

    def _on_write(self, data: bytes, tape_num: int, prefix: str) -> int:
        key = f"{prefix}{tape_num}"
        tape = self._tapes.get(key, {})
        tape["position"] = tape.get("position", 0) + len(data)
        return len(data)

    def get_info(self) -> Dict[str, Any]:
        return {
            "max_tapes": self.MAX_TAPES,
            "rewinding": [f"st{i}" for i in range(self.MAX_TAPES)],
            "non_rewinding": [f"nst{i}" for i in range(self.MAX_TAPES)],
        }


class SCSIBSGDevice:
    """/dev/bsg/* — SCSI BSG (Block SCSI Generic) devices.

    Provides userspace access to SCSI commands via the BSG framework.
    Unlike /dev/sg, BSG supports both block and character device
    access patterns and is the modern interface for SCSI passthrough.

    Devices named by SCSI address: 0:0:0:0, 0:0:1:0, etc.
    major 243, minor 0+
    """

    MAJOR = 243
    MAX_BSG = 256

    def __init__(self):
        self._devices: Dict[str, Dict[str, Any]] = {}
        self._register_directory()
        self._register_default_devices()
        log.info("SCSIBSGDevice: created /dev/bsg/")

    def _register_directory(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="bsg", path="/dev/bsg", dev_type=DeviceType.DIRECTORY,
            description="SCSI BSG devices",
        ))

    def _register_default_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        default_addrs = [
            "0:0:0:0", "0:0:1:0", "0:0:2:0", "0:0:3:0",
            "1:0:0:0", "1:0:1:0",
        ]
        for minor, addr in enumerate(default_addrs):
            mgr.create_node(DeviceNode(
                name=addr, path=f"/dev/bsg/{addr}",
                dev_type=DeviceType.CHAR,
                major=self.MAJOR, minor=minor, mode=0o660,
                description=f"SCSI BSG {addr}",
            ))
            self._devices[addr] = {"minor": minor, "active": False}

    def add_device(self, host: int, channel: int, target: int, lun: int) -> str:
        addr = f"{host}:{channel}:{target}:{lun}"
        if addr in self._devices:
            return addr
        minor = len(self._devices)
        if minor >= self.MAX_BSG:
            return ""
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name=addr, path=f"/dev/bsg/{addr}",
            dev_type=DeviceType.CHAR,
            major=self.MAJOR, minor=minor, mode=0o660,
            description=f"SCSI BSG {addr}",
        ))
        self._devices[addr] = {"minor": minor, "active": False}
        log.info("BSG: added device %s (minor %d)", addr, minor)
        return addr

    def remove_device(self, addr: str) -> bool:
        if addr not in self._devices:
            return False
        mgr = DeviceManager.get_instance()
        mgr.remove_node(f"/dev/bsg/{addr}")
        del self._devices[addr]
        return True

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/bsg",
            "max_devices": self.MAX_BSG,
            "devices": list(self._devices.keys()),
        }
