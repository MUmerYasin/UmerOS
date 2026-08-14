"""
UmerOS MAKEDEV — Device node creation script.

FHS 3.0 /dev:
  /dev/MAKEDEV — Shell script for creating device nodes manually.
  In, it's a symlink to /dev/null (devtmpfs handles creation).
  In UmerOS, we provide a Python implementation.

  Usage: MAKEDEV <device> [<device> ...]
  Example: MAKEDEV ttyS0 loop0 sda

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.MAKEDEV")


# ─── Known device definitions ────────────────────────────────────────────────

DEVICE_TABLE: Dict[str, Dict[str, Any]] = {
    # Pseudo-devices
    "null":    {"major": 1,   "minor": 3,   "mode": "c", "desc": "Null device"},
    "zero":    {"major": 1,   "minor": 5,   "mode": "c", "desc": "Zero device"},
    "full":    {"major": 1,   "minor": 7,   "mode": "c", "desc": "Full device"},
    "random":  {"major": 1,   "minor": 8,   "mode": "c", "desc": "Entropy pool"},
    "urandom": {"major": 1,   "minor": 9,   "mode": "c", "desc": "Pseudo-random"},
    "tty":     {"major": 5,   "minor": 0,   "mode": "c", "desc": "Controlling terminal"},
    "console": {"major": 5,   "minor": 1,   "mode": "c", "desc": "System console"},
    "ptmx":    {"major": 5,   "minor": 2,   "mode": "c", "desc": "PTY master"},
    "log":     {"major": 10,  "minor": 229, "mode": "c", "desc": "Syslog"},
    # TTY
    "tty0":    {"major": 4,   "minor": 0,   "mode": "c", "desc": "Virtual terminal 0"},
    "ttyS0":   {"major": 4,   "minor": 64,  "mode": "c", "desc": "Serial port 0"},
    # Loop
    "loop0":   {"major": 7,   "minor": 0,   "mode": "b", "desc": "Loop device 0"},
    # SCSI
    "sda":     {"major": 8,   "minor": 0,   "mode": "b", "desc": "SCSI disk a"},
    # IDE
    "hda":     {"major": 33,  "minor": 0,   "mode": "b", "desc": "IDE disk a"},
    # Virtio
    "vda":     {"major": 253, "minor": 0,   "mode": "b", "desc": "Virtio disk a"},
    # CD-ROM
    "sr0":     {"major": 11,  "minor": 0,   "mode": "b", "desc": "CD-ROM"},
    # NVMe
    "nvme0n1": {"major": 259, "minor": 0,   "mode": "b", "desc": "NVMe namespace 1"},
    # Network
    "tun":     {"major": 10,  "minor": 200, "mode": "c", "desc": "TUN/TAP"},
}


class MAKEDEVCommand:
    """MAKEDEV — Create device nodes.

    Usage:
        MAKEDEV <device> [<device> ...]
        MAKEDEV --list          List all known devices
        MAKEDEV --help          Show help
    """

    def __init__(self):
        self._created: List[str] = []
        self._errors: List[str] = []

    def execute(self, args: List[str], stdin=None, stdout=None) -> int:
        if not args or "--help" in args or "-h" in args:
            self._print_help(stdout)
            return 0
        if "--list" in args:
            self._print_list(stdout)
            return 0

        mgr = DeviceManager.get_instance()
        for dev_name in args:
            if dev_name in DEVICE_TABLE:
                info = DEVICE_TABLE[dev_name]
                node = DeviceNode(
                    name=dev_name,
                    path=f"/dev/{dev_name}",
                    dev_type=DeviceType.CHAR if info["mode"] == "c" else DeviceType.BLOCK,
                    major=info["major"],
                    minor=info["minor"],
                    mode=0o666,
                    description=info["desc"],
                )
                if mgr.create_node(node):
                    self._created.append(dev_name)
                else:
                    self._errors.append(f"{dev_name}: already exists")
            else:
                self._errors.append(f"{dev_name}: unknown device")

        if stdout:
            for c in self._created:
                stdout.write(f"created /dev/{c}\n")
            for e in self._errors:
                stdout.write(f"error: {e}\n")
            stdout.write(f"\nCreated: {len(self._created)}  Errors: {len(self._errors)}\n")

        log.info("MAKEDEV: created=%d errors=%d", len(self._created), len(self._errors))
        return 0 if not self._errors else 1

    def create_device(self, name: str, major: int, minor: int,
                      mode: str = "c", perms: int = 0o666) -> bool:
        """Programmatic device creation."""
        mgr = DeviceManager.get_instance()
        node = DeviceNode(
            name=name, path=f"/dev/{name}",
            dev_type=DeviceType.CHAR if mode == "c" else DeviceType.BLOCK,
            major=major, minor=minor, mode=perms,
            description=f"MAKEDEV: {name}",
        )
        return mgr.create_node(node)

    def _print_help(self, stdout) -> None:
        if stdout:
            stdout.write("MAKEDEV — Create device nodes\n\n")
            stdout.write("Usage: MAKEDEV <device> [<device> ...]\n")
            stdout.write("       MAKEDEV --list          List all known devices\n")
            stdout.write("       MAKEDEV --help          Show this help\n\n")
            stdout.write("Known devices:\n")
            for name, info in sorted(DEVICE_TABLE.items()):
                stdout.write(f"  {name:<12} {info['mode']} {info['major']:>3},{info['minor']:<3}  {info['desc']}\n")

    def _print_list(self, stdout) -> None:
        if stdout:
            for name, info in sorted(DEVICE_TABLE.items()):
                stdout.write(f"{name}\t{info['mode']}\t{info['major']},{info['minor']}\t{info['desc']}\n")

    def get_info(self) -> Dict[str, Any]:
        return {
            "known_devices": len(DEVICE_TABLE),
            "created": self._created,
            "errors": self._errors,
        }

    def __repr__(self) -> str:
        return f"<MAKEDEVCommand devices={len(DEVICE_TABLE)}>"
