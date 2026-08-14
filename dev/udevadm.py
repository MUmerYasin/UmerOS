"""
UmerOS udevadm — Device manager query/control command.

FHS 3.0 /dev:
  udevadm — Query and control udevd. it's used to:
    - Query device properties:  udevadm info --query=property /dev/sda
    - Monitor device events:    udevadm monitor
    - Trigger device events:    udevadm trigger
    - Settle (wait):            udevadm settle
    - Test device:              udevadm test /dev/sda

  In UmerOS, udevadm queries the DeviceManager and drivers/ registry.

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode

log = logging.getLogger("UmerOS.Dev.Udevadm")


class UdevadmCommand:
    """udevadm — Device manager query and control.

    Usage:
        udevadm info --query=property /dev/NAME
        udevadm info --name=NAME
        udevadm monitor
        udevadm trigger
        udevadm settle
        udevadm test /dev/NAME
        udevadm --help
    """

    def __init__(self):
        self._events: List[Dict[str, Any]] = []

    def execute(self, args: List[str], stdin=None, stdout=None) -> int:
        if not args or "--help" in args or "-h" in args:
            self._print_help(stdout)
            return 0

        cmd = args[0]
        if cmd == "info":
            return self._cmd_info(args[1:], stdout)
        elif cmd == "monitor":
            return self._cmd_monitor(stdout)
        elif cmd == "trigger":
            return self._cmd_trigger(stdout)
        elif cmd == "settle":
            return self._cmd_settle(stdout)
        elif cmd == "test":
            return self._cmd_test(args[1:], stdout)
        elif cmd == "trigger":
            return self._cmd_trigger(stdout)
        else:
            if stdout:
                stdout.write(f"udevadm: unknown command '{cmd}'\n")
            return 1

    def _cmd_info(self, args: List[str], stdout) -> int:
        query = "property"
        name = None
        for a in args:
            if a.startswith("--query="):
                query = a.split("=", 1)[1]
            elif a.startswith("--name="):
                name = a.split("=", 1)[1]
            elif not a.startswith("-"):
                name = a

        if not name:
            if stdout:
                stdout.write("udevadm info: specify device path\n")
            return 1

        path = name if name.startswith("/dev/") else f"/dev/{name}"
        mgr = DeviceManager.get_instance()
        node = mgr.get_node(path)
        if not node:
            if stdout:
                stdout.write(f"udevadm info: '{path}' not found\n")
            return 1

        if query == "property":
            props = self._get_properties(node)
            if stdout:
                for k, v in sorted(props.items()):
                    stdout.write(f"{k}={v}\n")
        elif query == "name":
            if stdout:
                stdout.write(f"{node.path}\n")
        elif query == "symlink":
            if stdout:
                stdout.write(f"{node.path}\n")
        elif query == "path":
            if stdout:
                stdout.write(f"{node.path}\n")
        return 0

    def _cmd_monitor(self, stdout) -> int:
        if stdout:
            stdout.write("udevadm monitor — watching for device events...\n")
            stdout.write("(In UmerOS simulation — no live events)\n")
        return 0

    def _cmd_trigger(self, stdout) -> int:
        if stdout:
            stdout.write("udevadm trigger — re-triggering device events\n")
        mgr = DeviceManager.get_instance()
        nodes = mgr.list_all()
        for node in nodes:
            self._events.append({
                "action": "add",
                "devpath": node.path,
                "subsystem": node.dev_type.value,
                "timestamp": time.time(),
            })
        if stdout:
            stdout.write(f"Triggered {len(nodes)} device events\n")
        return 0

    def _cmd_settle(self, stdout) -> int:
        if stdout:
            stdout.write("udevadm settle — waiting for events to settle\n")
            stdout.write("(In UmerOS simulation — no pending events)\n")
        return 0

    def _cmd_test(self, args: List[str], stdout) -> int:
        if not args:
            if stdout:
                stdout.write("udevadm test: specify device path\n")
            return 1

        path = args[0] if args[0].startswith("/dev/") else f"/dev/{args[0]}"
        mgr = DeviceManager.get_instance()
        node = mgr.get_node(path)
        if not node:
            if stdout:
                stdout.write(f"udevadm test: '{path}' not found\n")
            return 1

        if stdout:
            stdout.write(f"udevadm test: {path}\n")
            props = self._get_properties(node)
            for k, v in sorted(props.items()):
                stdout.write(f"  {k}={v}\n")
            stdout.write(f"udevadm test: {path} — passed\n")
        return 0

    def _get_properties(self, node: DeviceNode) -> Dict[str, str]:
        props = {
            "DEVPATH": node.path,
            "DEVNAME": node.name,
            "DEVTYPE": node.dev_type.value,
            "MAJOR": str(node.major),
            "MINOR": str(node.minor),
            "MODE": oct(node.mode),
            "SUBSYSTEM": "char" if node.is_character else "block",
        }
        if node.description:
            props["ID_MODEL"] = node.description
        return props

    def query_device(self, path: str) -> Optional[Dict[str, str]]:
        """Programmatic query — returns properties dict."""
        mgr = DeviceManager.get_instance()
        node = mgr.get_node(path)
        return self._get_properties(node) if node else None

    def _print_help(self, stdout) -> None:
        if stdout:
            stdout.write("udevadm — Device manager query and control\n\n")
            stdout.write("Commands:\n")
            stdout.write("  info --query=property /dev/NAME  Query device properties\n")
            stdout.write("  info --name=NAME                 Query by name\n")
            stdout.write("  monitor                         Watch for device events\n")
            stdout.write("  trigger                         Re-trigger device events\n")
            stdout.write("  settle                          Wait for events to settle\n")
            stdout.write("  test /dev/NAME                  Test device setup\n")

    def get_info(self) -> Dict[str, Any]:
        return {"events_pending": len(self._events)}

    def __repr__(self) -> str:
        return "<UdevadmCommand>"
