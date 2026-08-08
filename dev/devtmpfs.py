"""
UmerOS devtmpfs — Virtual filesystem population engine.

FHS 3.0 /dev:
  The kernel creates /dev at boot and populates it via devtmpfs.
  In UmerOS, DevTmpFS performs the equivalent: creates all standard
  device nodes, directories, and symlinks in the virtual /dev tree.

  devtmpfs runs at boot time (after kernel init, before init scripts).

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.DevTmpFS")


class DevTmpFS:
    """Populates /dev with standard device nodes at boot.

    Standard nodes created:
      Pseudo:   null, zero, random, urandom, full, tty, console
      PTY:      ptmx, pts/
      FD:       stdin, stdout, stderr, fd/
      Log:      log
      Virtual:  tty0-tty63, ttyS0-ttyS31
      Loop:     loop0-loop7
      Ramdisk:  ram0-ram15
      Block:    sda-sdp, hda-hdd, vda-vdd, sr0, nvme0n1
      TUN:      net/tun, net/tap
      DRI:      dri/, dri/card0, dri/renderD128
      ALSA:     snd/
      USB:      bus/usb/
      Mapper:   mapper/
      SHM:      shm/
      Input:    input/
    """

    # Standard pseudo-device major:minor numbers
    PSEUDO_DEVICES = [
        ("null",      1,   3, "c", 0o666, "Null device"),
        ("zero",      1,   5, "c", 0o666, "Zero device"),
        ("full",      1,   7, "c", 0o666, "Full device"),
        ("random",    1,   8, "c", 0o644, "Entropy pool"),
        ("urandom",   1,   9, "c", 0o644, "Pseudo-random"),
        ("tty",       5,   0, "c", 0o666, "Controlling terminal"),
        ("console",   5,   1, "c", 0o620, "System console"),
        ("ptmx",      5,   2, "c", 0o666, "PTY master"),
        ("log",      10, 229, "c", 0o666, "Syslog"),
    ]

    # Virtual terminals: /dev/tty0-tty63 (major 4, minor 0-63)
    VT_COUNT = 64
    VT_MAJOR = 4
    VT_MINOR_START = 0

    # Serial ports: /dev/ttyS0-ttyS31 (major 4, minor 64-95)
    SERIAL_COUNT = 32
    SERIAL_MAJOR = 4
    SERIAL_MINOR_START = 64

    # Loop devices: /dev/loop0-loop7 (major 7, minor 0-7)
    LOOP_COUNT = 8
    LOOP_MAJOR = 7

    # Ramdisk: /dev/ram0-ram15 (major 1, minor 0-15, already covered)
    RAMDISK_COUNT = 16

    # SCSI/SATA disks: /dev/sda-sdp (major 8, minor 0-255, 16 per controller)
    DISK_COUNT = 16
    DISK_MAJOR = 8

    # IDE disks: /dev/hda-hdd (major 33, minor 0-63)
    IDE_COUNT = 4
    IDE_MAJOR = 33

    # Virtio: /dev/vda-vdd (major 253, minor 0-15)
    VIRTIO_COUNT = 4
    VIRTIO_MAJOR = 253

    # CD-ROM: /dev/sr0 (major 11, minor 0)
    CDROM_MAJOR = 11

    def __init__(self, dev_root: str = "/dev"):
        self.dev_root = dev_root
        self._populated = False
        self._node_count = 0

    def populate(self) -> int:
        """Create all standard /dev nodes. Returns count of nodes created."""
        if self._populated:
            log.warning("devtmpfs already populated")
            return 0

        mgr = DeviceManager.get_instance()
        start = time.time()
        count = 0

        # ── Directories ────────────────────────────────────────────────
        dirs = [
            ("/dev/input",  "Input devices"),
            ("/dev/pts",    "Pseudo-terminal slaves"),
            ("/dev/shm",    "POSIX shared memory"),
            ("/dev/block",  "Block device symlinks"),
            ("/dev/char",   "Character device symlinks"),
            ("/dev/disk",   "Disk symlinks"),
            ("/dev/disk/by-id",    "Disk by ID"),
            ("/dev/disk/by-label", "Disk by label"),
            ("/dev/disk/by-uuid",  "Disk by UUID"),
            ("/dev/disk/by-path",  "Disk by path"),
            ("/dev/net",    "Network devices"),
            ("/dev/bus",    "Bus devices"),
            ("/dev/bus/usb", "USB devices"),
            ("/dev/dri",    "Direct Rendering Interface"),
            ("/dev/snd",    "ALSA sound devices"),
            ("/dev/mapper", "Device-mapper"),
        ]
        for path, desc in dirs:
            node = DeviceNode(
                name=path.split("/")[-1], path=path, dev_type=DeviceType.DIRECTORY,
                description=desc,
            )
            if mgr.create_node(node):
                count += 1

        # ── Pseudo-devices ─────────────────────────────────────────────
        for name, major, minor, typ, mode, desc in self.PSEUDO_DEVICES:
            node = DeviceNode(
                name=name, path=f"/dev/{name}",
                dev_type=DeviceType.CHAR if typ == "c" else DeviceType.BLOCK,
                major=major, minor=minor, mode=mode, description=desc,
            )
            if mgr.create_node(node):
                count += 1

        # ── Virtual terminals /dev/ttyN ────────────────────────────────
        for i in range(self.VT_COUNT):
            node = DeviceNode(
                name=f"tty{i}", path=f"/dev/tty{i}", dev_type=DeviceType.CHAR,
                major=self.VT_MAJOR, minor=self.VT_MINOR_START + i,
                mode=0o620, description=f"Virtual terminal {i}",
            )
            if mgr.create_node(node):
                count += 1

        # ── Serial ports /dev/ttySN ────────────────────────────────────
        for i in range(self.SERIAL_COUNT):
            node = DeviceNode(
                name=f"ttyS{i}", path=f"/dev/ttyS{i}", dev_type=DeviceType.CHAR,
                major=self.SERIAL_MAJOR, minor=self.SERIAL_MINOR_START + i,
                mode=0o620, description=f"Serial port {i}",
            )
            if mgr.create_node(node):
                count += 1

        # ── Loop devices ───────────────────────────────────────────────
        for i in range(self.LOOP_COUNT):
            node = DeviceNode(
                name=f"loop{i}", path=f"/dev/loop{i}", dev_type=DeviceType.BLOCK,
                major=self.LOOP_MAJOR, minor=i, mode=0o660,
                description=f"Loop device {i}",
            )
            if mgr.create_node(node):
                count += 1

        # ── SCSI/SATA disks /dev/sdN ──────────────────────────────────
        for i in range(self.DISK_COUNT):
            letter = chr(ord("a") + i)
            node = DeviceNode(
                name=f"sd{letter}", path=f"/dev/sd{letter}", dev_type=DeviceType.BLOCK,
                major=self.DISK_MAJOR, minor=i * 16, mode=0o660,
                description=f"SCSI/SATA disk {letter}",
            )
            if mgr.create_node(node):
                count += 1

        # ── IDE disks /dev/hdN ─────────────────────────────────────────
        for i in range(self.IDE_COUNT):
            letter = chr(ord("a") + i)
            node = DeviceNode(
                name=f"hd{letter}", path=f"/dev/hd{letter}", dev_type=DeviceType.BLOCK,
                major=self.IDE_MAJOR, minor=i * 64, mode=0o660,
                description=f"IDE disk {letter}",
            )
            if mgr.create_node(node):
                count += 1

        # ── Virtio disks /dev/vdN ──────────────────────────────────────
        for i in range(self.VIRTIO_COUNT):
            letter = chr(ord("a") + i)
            node = DeviceNode(
                name=f"vd{letter}", path=f"/dev/vd{letter}", dev_type=DeviceType.BLOCK,
                major=self.VIRTIO_MAJOR, minor=i, mode=0o660,
                description=f"Virtio disk {letter}",
            )
            if mgr.create_node(node):
                count += 1

        # ── CD-ROM ─────────────────────────────────────────────────────
        node = DeviceNode(
            name="sr0", path="/dev/sr0", dev_type=DeviceType.BLOCK,
            major=self.CDROM_MAJOR, minor=0, mode=0o660,
            description="CD-ROM drive",
        )
        if mgr.create_node(node):
            count += 1

        # ── NVMe ───────────────────────────────────────────────────────
        node = DeviceNode(
            name="nvme0n1", path="/dev/nvme0n1", dev_type=DeviceType.BLOCK,
            major=259, minor=0, mode=0o660,
            description="NVMe namespace 1",
        )
        if mgr.create_node(node):
            count += 1

        # ── TUN/TAP ────────────────────────────────────────────────────
        node = DeviceNode(
            name="tun", path="/dev/net/tun", dev_type=DeviceType.CHAR,
            major=10, minor=200, mode=0o666,
            description="TUN/TAP network device",
        )
        if mgr.create_node(node):
            count += 1

        # ── DRI ────────────────────────────────────────────────────────
        for i in range(4):
            node = DeviceNode(
                name=f"card{i}", path=f"/dev/dri/card{i}", dev_type=DeviceType.CHAR,
                major=226, minor=i, mode=0o660,
                description=f"DRI card {i}",
            )
            if mgr.create_node(node):
                count += 1
            node = DeviceNode(
                name=f"renderD{128+i}", path=f"/dev/dri/renderD{128+i}",
                dev_type=DeviceType.CHAR,
                major=226, minor=128 + i, mode=0o660,
                description=f"DRM render node {128+i}",
            )
            if mgr.create_node(node):
                count += 1

        # ── ALSA ───────────────────────────────────────────────────────
        for i in range(4):
            node = DeviceNode(
                name=f"card{i}", path=f"/dev/snd/card{i}", dev_type=DeviceType.CHAR,
                major=116, minor=i, mode=0o660,
                description=f"ALSA card {i}",
            )
            if mgr.create_node(node):
                count += 1

        # ── File descriptor symlinks ───────────────────────────────────
        for fd_num, name in [(0, "stdin"), (1, "stdout"), (2, "stderr")]:
            node = DeviceNode(
                name=name, path=f"/dev/{name}", dev_type=DeviceType.SYMLINK,
                symlink_target=f"/proc/self/fd/{fd_num}",
                description=f"Standard {name}",
            )
            if mgr.create_node(node):
                count += 1

        self._populated = True
        self._node_count = count
        elapsed = (time.time() - start) * 1000
        log.info("devtmpfs populated: %d nodes in %.1fms", count, elapsed)
        return count

    def get_info(self) -> Dict[str, Any]:
        mgr = DeviceManager.get_instance()
        return {
            "populated": self._populated,
            "total_nodes": self._node_count,
            "registered_nodes": mgr.count(),
            "char_devices": len(mgr.list_characters()),
            "block_devices": len(mgr.list_blocks()),
            "symlinks": len(mgr.list_symlinks()),
            "directories": len(mgr.list_directories()),
        }

    def __repr__(self) -> str:
        return f"<DevTmpFS nodes={self._node_count}>"
