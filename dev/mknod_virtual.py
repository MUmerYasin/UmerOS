"""
UmerOS mknod (virtual) — Create device nodes.

FHS 3.0 /dev:
  mknod — Create block or character special files.
  In UmerOS, this creates device nodes in the virtual /dev filesystem
  without touching the host OS.

  Usage: mknod [options] NAME TYPE [MAJOR MINOR]
  Types: c (char), b (block), p (FIFO)

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dev.core import DeviceManager, DeviceNode, DeviceType

log = logging.getLogger("UmerOS.Dev.MknodVirtual")


class MknodVirtualCommand:
    """mknod — Create device nodes in UmerOS virtual filesystem.

    Usage:
        mknod [-m mode] NAME TYPE [MAJOR MINOR]
        mknod [-m mode] NAME p           (FIFO)
        mknod --help                      Show help
    """

    def __init__(self):
        self._created: List[str] = []
        self._errors: List[str] = []

    def execute(self, args: List[str], stdin=None, stdout=None) -> int:
        if not args or "--help" in args or "-h" in args:
            self._print_help(stdout)
            return 0

        mode = 0o666
        i = 0

        # Parse -m flag
        if args[0] == "-m" and len(args) >= 2:
            try:
                mode = int(args[1], 8)
            except ValueError:
                if stdout:
                    stdout.write(f"mknod: invalid mode '{args[1]}'\n")
                return 1
            i = 2

        if i >= len(args):
            self._print_help(stdout)
            return 1

        name = args[i]
        i += 1

        if i >= len(args):
            if stdout:
                stdout.write("mknod: missing TYPE\n")
            return 1

        dev_type_str = args[i]
        i += 1

        if dev_type_str == "p":
            # FIFO
            return self._create_fifo(name, mode, stdout)

        if dev_type_str not in ("c", "b", "u"):
            if stdout:
                stdout.write(f"mknod: invalid type '{dev_type_str}' (use c, b, or p)\n")
            return 1

        dev_type = DeviceType.CHAR if dev_type_str in ("c", "u") else DeviceType.BLOCK

        if i >= len(args) or i + 1 >= len(args):
            if stdout:
                stdout.write("mknod: missing MAJOR MINOR\n")
            return 1

        try:
            major = int(args[i])
            minor = int(args[i + 1])
        except ValueError:
            if stdout:
                stdout.write("mknod: invalid MAJOR or MINOR\n")
            return 1

        path = name if name.startswith("/dev/") else f"/dev/{name}"
        mgr = DeviceManager.get_instance()
        node = DeviceNode(
            name=name.split("/")[-1], path=path, dev_type=dev_type,
            major=major, minor=minor, mode=mode,
            description=f"Created by mknod",
        )

        if mgr.create_node(node):
            self._created.append(path)
            if stdout:
                stdout.write(f"mknod: created '{path}' {dev_type_str} {major},{minor}\n")
            log.info("mknod: created %s %s %d,%d", path, dev_type_str, major, minor)
            return 0
        else:
            self._errors.append(f"{path}: already exists")
            if stdout:
                stdout.write(f"mknod: cannot create '{path}': File exists\n")
            return 1

    def _create_fifo(self, name: str, mode: int, stdout) -> int:
        path = name if name.startswith("/dev/") else f"/dev/{name}"
        mgr = DeviceManager.get_instance()
        node = DeviceNode(
            name=name.split("/")[-1], path=path, dev_type=DeviceType.FIFO,
            mode=mode, description="FIFO (named pipe)",
        )
        if mgr.create_node(node):
            self._created.append(path)
            if stdout:
                stdout.write(f"mknod: created FIFO '{path}'\n")
            return 0
        else:
            if stdout:
                stdout.write(f"mknod: cannot create '{path}': File exists\n")
            return 1

    def create_device(self, name: str, dev_type: DeviceType,
                      major: int, minor: int, mode: int = 0o666) -> bool:
        """Programmatic device node creation."""
        path = name if name.startswith("/dev/") else f"/dev/{name}"
        mgr = DeviceManager.get_instance()
        node = DeviceNode(
            name=name.split("/")[-1], path=path, dev_type=dev_type,
            major=major, minor=minor, mode=mode,
            description="mknod virtual",
        )
        return mgr.create_node(node)

    def _print_help(self, stdout) -> None:
        if stdout:
            stdout.write("mknod — Create device nodes in UmerOS\n\n")
            stdout.write("Usage: mknod [-m mode] NAME TYPE [MAJOR MINOR]\n\n")
            stdout.write("Types:\n")
            stdout.write("  c, u    Character (unbuffered) device\n")
            stdout.write("  b       Block (buffered) device\n")
            stdout.write("  p       FIFO (named pipe)\n\n")
            stdout.write("Examples:\n")
            stdout.write("  mknod null c 1 3\n")
            stdout.write("  mknod -m 0644 zero c 1 5\n")
            stdout.write("  mypipe p\n")

    def get_info(self) -> Dict[str, Any]:
        return {"created": self._created, "errors": self._errors}

    def __repr__(self) -> str:
        return "<MknodVirtualCommand>"
