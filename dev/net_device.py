"""
UmerOS /dev/net — Network device nodes.

FHS 3.0 /dev/net:
  /dev/net/tun  — TUN/TAP network device (character 10:200)
  /dev/net/tap  — Alias for tun

 major:minor: tun = 10:200, tap = 10:200 (same device)

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.NetDevice")


class NetDevice:
    """Network device manager — /dev/net/.

    Provides:
      /dev/net/tun — TUN/TAP character device
      /dev/net/tap — Alias for tun
    """

    TUN_MAJOR = 10
    TUN_MINOR = 200

    def __init__(self):
        self._interfaces: Dict[str, Dict[str, Any]] = {}
        self._register_directory()
        self._register_devices()
        log.info("NetDevice created")

    def _register_directory(self) -> None:
        mgr = DeviceManager.get_instance()
        mgr.create_node(DeviceNode(
            name="net", path="/dev/net", dev_type=DeviceType.DIRECTORY,
            description="Network devices",
        ))

    def _register_devices(self) -> None:
        mgr = DeviceManager.get_instance()
        # TUN device
        mgr.create_node(DeviceNode(
            name="tun", path="/dev/net/tun", dev_type=DeviceType.CHAR,
            major=self.TUN_MAJOR, minor=self.TUN_MINOR, mode=0o666,
            description="TUN/TAP network device",
            ioctl_callback=self._on_tun_ioctl,
        ))
        # Tap alias
        mgr.create_node(DeviceNode(
            name="tap", path="/dev/net/tap", dev_type=DeviceType.SYMLINK,
            symlink_target="/dev/net/tun",
            description="TAP network device (alias)",
        ))

    def _on_tun_ioctl(self, cmd: int, arg: Any) -> int:
        """Handle TUN/TAP ioctl commands."""
        return 0

    def create_interface(self, name: str, mode: str = "tap") -> bool:
        """Create a virtual network interface."""
        if name in self._interfaces:
            return False
        self._interfaces[name] = {"mode": mode, "up": False}
        log.info("Net interface created: %s (%s)", name, mode)
        return True

    def set_interface_up(self, name: str) -> bool:
        if name not in self._interfaces:
            return False
        self._interfaces[name]["up"] = True
        return True

    def set_interface_down(self, name: str) -> bool:
        if name not in self._interfaces:
            return False
        self._interfaces[name]["up"] = False
        return True

    def list_interfaces(self) -> Dict[str, bool]:
        return {k: v["up"] for k, v in self._interfaces.items()}

    def get_info(self) -> Dict[str, Any]:
        return {
            "path": "/dev/net",
            "tun": f"/dev/net/tun ({self.TUN_MAJOR}:{self.TUN_MINOR})",
            "interfaces": len(self._interfaces),
            "active": sum(1 for v in self._interfaces.values() if v["up"]),
        }

    def __repr__(self) -> str:
        return f"<NetDevice interfaces={len(self._interfaces)}>"
