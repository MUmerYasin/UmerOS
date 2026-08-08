"""
UmerOS /dev Core — Device types, nodes, and central manager.

Provides the foundation for all /dev device files:
  DeviceType   — Enum (char, block, fifo, socket, symlink)
  DeviceNode   — Dataclass representing a single device file
  DeviceManager — Central registry for all /dev nodes

Author:  Umer OS Project
Licence: GPLv3
"""

from __future__ import annotations

import enum
import logging
import os
import stat as stat_mod
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

log = logging.getLogger("UmerOS.Dev.Core")


# ─── Device Type Enum ────────────────────────────────────────────────────────


class DeviceType(enum.Enum):
    """FHS-specified device file types."""
    CHAR = "char"           # c — Character (unbuffered) device
    BLOCK = "block"         # b — Block (buffered) device
    FIFO = "fifo"           # p — FIFO / named pipe
    SOCKET = "socket"       # s — Unix domain socket
    SYMLINK = "symlink"     # l — Symbolic link
    DIRECTORY = "directory" # d — Directory (e.g. /dev/input/)

    @property
    def stat_type(self) -> int:
        return {
            DeviceType.CHAR: stat_mod.S_IFCHR,
            DeviceType.BLOCK: stat_mod.S_IFBLK,
            DeviceType.FIFO: stat_mod.S_IFIFO,
            DeviceType.SOCKET: stat_mod.S_IFSOCK,
            DeviceType.SYMLINK: stat_mod.S_IFLNK,
            DeviceType.DIRECTORY: stat_mod.S_IFDIR,
        }[self]

    @classmethod
    def from_mknod_char(cls, c: str) -> "DeviceType":
        return {"c": cls.CHAR, "u": cls.CHAR, "b": cls.BLOCK, "p": cls.FIFO}.get(c, cls.CHAR)


# ─── Device Node Dataclass ───────────────────────────────────────────────────


@dataclass
class DeviceNode:
    """Represents a single device file under /dev."""
    name: str                               # e.g. "null", "sda", "tty0"
    path: str                               # e.g. "/dev/null"
    dev_type: DeviceType
    major: int = 0
    minor: int = 0
    mode: int = 0o666                       # default permissions
    uid: int = 0                            # root
    gid: int = 0                            # root
    symlink_target: str = ""                # for symlinks
    description: str = ""
    created_at: float = field(default_factory=time.time)
    read_callback: Optional[Callable] = None
    write_callback: Optional[Callable] = None
    ioctl_callback: Optional[Callable] = None

    @property
    def dev_number(self) -> int:
        return os.makedev(self.major, self.minor) if self.major or self.minor else 0

    @property
    def is_character(self) -> bool:
        return self.dev_type == DeviceType.CHAR

    @property
    def is_block(self) -> bool:
        return self.dev_type == DeviceType.BLOCK

    @property
    def permissions_str(self) -> str:
        return oct(self.mode)[-3:]

    def to_ls_entry(self) -> str:
        """Format as `ls -l` output line."""
        type_char = {
            DeviceType.CHAR: "c", DeviceType.BLOCK: "b", DeviceType.FIFO: "p",
            DeviceType.SOCKET: "s", DeviceType.SYMLINK: "l", DeviceType.DIRECTORY: "d",
        }[self.dev_type]
        perms = self._format_mode(self.mode, self.dev_type)
        dev_str = f"{self.major:>3},{self.minor:<3}" if self.dev_type in (DeviceType.CHAR, DeviceType.BLOCK) else "        "
        if self.dev_type == DeviceType.SYMLINK:
            return f"lrwxrwxrwx  1 root root  {dev_str} {self.permissions_str} {self.path} -> {self.symlink_target}"
        return f"{type_char}{perms}  1 root root {dev_str} {self.name}"

    @staticmethod
    def _format_mode(mode: int, dev_type: DeviceType) -> str:
        chars = ["-rwxrwxrwx"]
        if dev_type == DeviceType.DIRECTORY:
            chars[0] = "d"
        elif dev_type == DeviceType.CHAR:
            chars[0] = "c"
        elif dev_type == DeviceType.BLOCK:
            chars[0] = "b"
        elif dev_type == DeviceType.FIFO:
            chars[0] = "p"
        elif dev_type == DeviceType.SOCKET:
            chars[0] = "s"
        return "".join(chars)


# ─── Device Manager (Singleton) ─────────────────────────────────────────────


class DeviceManager:
    """Central registry for all /dev device nodes.

    Tracks every device node in the virtual /dev filesystem.
    Provides create, remove, lookup, list, and path operations.
    """

    _instance: Optional["DeviceManager"] = None

    def __init__(self, dev_root: str = "/dev"):
        self.dev_root = dev_root
        self._nodes: Dict[str, DeviceNode] = {}       # path -> DeviceNode
        self._by_major: Dict[int, List[DeviceNode]] = {}
        self._by_name: Dict[str, DeviceNode] = {}     # name -> DeviceNode
        self._symlinks: Dict[str, str] = {}            # symlink_path -> target
        log.info("DeviceManager initialized (root=%s)", dev_root)

    @classmethod
    def get_instance(cls) -> "DeviceManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── CRUD ──────────────────────────────────────────────────────────────

    def create_node(self, node: DeviceNode) -> bool:
        if node.path in self._nodes:
            log.warning("Device node already exists: %s", node.path)
            return False
        self._nodes[node.path] = node
        self._by_name[node.name] = node
        if node.major:
            self._by_major.setdefault(node.major, []).append(node)
        if node.dev_type == DeviceType.SYMLINK:
            self._symlinks[node.path] = node.symlink_target
        log.debug("Created device node: %s (%s %d,%d)", node.path, node.dev_type.value, node.major, node.minor)
        return True

    def remove_node(self, path: str) -> bool:
        node = self._nodes.pop(path, None)
        if node is None:
            return False
        self._by_name.pop(node.name, None)
        if node.major and node.major in self._by_major:
            self._by_major[node.major] = [n for n in self._by_major[node.major] if n.path != path]
            if not self._by_major[node.major]:
                del self._by_major[node.major]
        self._symlinks.pop(path, None)
        log.debug("Removed device node: %s", path)
        return True

    def get_node(self, path: str) -> Optional[DeviceNode]:
        return self._nodes.get(path)

    def get_node_by_name(self, name: str) -> Optional[DeviceNode]:
        return self._by_name.get(name)

    def get_by_major(self, major: int) -> List[DeviceNode]:
        return self._by_major.get(major, [])

    # ── Queries ───────────────────────────────────────────────────────────

    def list_all(self) -> List[DeviceNode]:
        return sorted(self._nodes.values(), key=lambda n: n.path)

    def list_by_type(self, dev_type: DeviceType) -> List[DeviceNode]:
        return [n for n in self._nodes.values() if n.dev_type == dev_type]

    def list_characters(self) -> List[DeviceNode]:
        return self.list_by_type(DeviceType.CHAR)

    def list_blocks(self) -> List[DeviceNode]:
        return self.list_by_type(DeviceType.BLOCK)

    def list_symlinks(self) -> List[DeviceNode]:
        return self.list_by_type(DeviceType.SYMLINK)

    def list_directories(self) -> List[DeviceNode]:
        return self.list_by_type(DeviceType.DIRECTORY)

    def count(self) -> int:
        return len(self._nodes)

    def resolve_symlink(self, path: str) -> Optional[str]:
        return self._symlinks.get(path)

    # ── Physical filesystem sync ──────────────────────────────────────────

    def sync_to_filesystem(self) -> int:
        """Create actual files in the VFS for all registered nodes."""
        created = 0
        for node in self._nodes.values():
            p = Path(node.path)
            if node.dev_type == DeviceType.DIRECTORY:
                p.mkdir(parents=True, exist_ok=True)
                created += 1
            elif node.dev_type == DeviceType.SYMLINK:
                if not p.exists():
                    try:
                        p.symlink_to(node.symlink_target)
                        created += 1
                    except OSError as e:
                        log.warning("Cannot create symlink %s -> %s: %s", node.path, node.symlink_target, e)
            elif not p.exists():
                try:
                    if node.dev_type == DeviceType.FIFO:
                        os.mkfifo(str(p), node.mode)
                    elif node.dev_type in (DeviceType.CHAR, DeviceType.BLOCK):
                        os.mknod(str(p), node.mode | node.dev_type.stat_type, node.dev_number)
                    else:
                        p.touch(mode=node.mode)
                    created += 1
                except OSError as e:
                    log.warning("Cannot create device node %s: %s", node.path, e)
        return created


# ─── Singleton accessor ──────────────────────────────────────────────────────


def get_device_manager() -> DeviceManager:
    return DeviceManager.get_instance()
