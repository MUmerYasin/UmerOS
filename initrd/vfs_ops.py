"""
Umer OS Initrd VFS operations
=============================
A tiny in-memory virtual filesystem used by the rest of the ``initrd``
package.  It is *not* meant to replace the real ``fs.vfs`` in UmerOS;
this is a focused, dependency-free model so the initrd runtime can be
tested without spinning up the rest of the OS.

API (all paths use forward slashes and start with ``/``)::

    root = VfsRoot()
    root.mkdir("/etc")
    root.touch("/etc/hostname", data=b"umer-os\n", mode=0o644)
    root.symlink("/bin/sh", "/bin/busybox")
    root.write_file("/etc/hosts", b"127.0.0.1 localhost\n")
    root.listdir("/")          -> ["bin", "etc", ...]
    root.find("/etc/hostname") -> VfsNode
    root.read_file("/etc/hostname") -> b"umer-os\n"

The model supports directories, regular files and symlinks.  Special
nodes (devices, FIFOs, sockets) are represented as empty regular
files with the matching mode bits set so that mode round-trips are
stable.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger("UmerOS.Initrd.VfsOps")


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

@dataclass
class VfsNode:
    """A node in the in-memory VFS tree."""

    name: str
    is_dir: bool = False
    data: bytes = b""
    mode: int = 0o644
    symlink_target: Optional[str] = None
    mtime: float = field(default_factory=time.time)
    children: Dict[str, "VfsNode"] = field(default_factory=dict)

    @property
    def is_symlink(self) -> bool:
        return self.symlink_target is not None

    @property
    def size(self) -> int:
        if self.is_dir:
            # Linux reports dir size as a fixed 4096 in stat.
            return 4096
        return len(self.data)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        kind = "d" if self.is_dir else ("l" if self.is_symlink else "-")
        return f"<VfsNode {kind} {oct(self.mode)} {self.name!r}>"


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

class VfsRoot:
    """A rooted in-memory VFS tree."""

    def __init__(self, name: str = "/") -> None:
        self.root = VfsNode(name=name, is_dir=True, mode=0o755)
        self._now = time.time

    # -- path helpers -----------------------------------------------------

    @staticmethod
    def _split(path: str) -> List[str]:
        if not path or path == "/":
            return []
        parts: List[str] = []
        for chunk in path.replace("\\", "/").split("/"):
            if chunk in ("", "."):
                continue
            if chunk == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(chunk)
        return parts

    # -- navigation -------------------------------------------------------

    def _walk(self, path: str, create_missing: bool = False) -> Optional[VfsNode]:
        parts = self._split(path)
        node = self.root
        for chunk in parts:
            if not node.is_dir:
                return None
            if chunk in node.children:
                node = node.children[chunk]
                continue
            if not create_missing:
                return None
            new = VfsNode(name=chunk, is_dir=True, mode=0o755)
            node.children[chunk] = new
            node = new
        return node

    # -- mutation ---------------------------------------------------------

    def mkdir(self, path: str, mode: int = 0o755, parents: bool = True) -> VfsNode:
        if path in ("", "/"):
            return self.root
        parts = self._split(path)
        node = self.root
        for chunk in parts:
            if not node.is_dir:
                raise NotADirectoryError(path)
            if chunk in node.children:
                child = node.children[chunk]
                if not child.is_dir:
                    raise NotADirectoryError(f"{path}: {chunk} is not a dir")
                node = child
                continue
            if not parents:
                raise FileNotFoundError(f"{path}: missing parent for {chunk!r}")
            new = VfsNode(name=chunk, is_dir=True, mode=mode)
            node.children[chunk] = new
            node = new
        return node

    def touch(self, path: str, data: bytes = b"", mode: int = 0o644) -> VfsNode:
        parts = self._split(path)
        if not parts:
            raise ValueError("touch: empty path")
        *dirs, leaf = parts
        node = self.root
        for chunk in dirs:
            if chunk in node.children:
                node = node.children[chunk]
                if not node.is_dir:
                    raise NotADirectoryError(f"{path}: {chunk} is not a dir")
            else:
                new = VfsNode(name=chunk, is_dir=True, mode=0o755)
                node.children[chunk] = new
                node = new
        if leaf in node.children and node.children[leaf].is_dir:
            raise IsADirectoryError(path)
        node.children[leaf] = VfsNode(
            name=leaf, is_dir=False, data=data, mode=mode
        )
        return node.children[leaf]

    def write_file(self, path: str, data: bytes, mode: int = 0o644) -> VfsNode:
        return self.touch(path, data=data, mode=mode)

    def read_file(self, path: str) -> bytes:
        node = self.find(path)
        if node is None:
            raise FileNotFoundError(path)
        if node.is_dir:
            raise IsADirectoryError(path)
        return node.data

    def symlink(self, path: str, target: str) -> VfsNode:
        parts = self._split(path)
        if not parts:
            raise ValueError("symlink: empty path")
        *dirs, leaf = parts
        node = self.root
        for chunk in dirs:
            if chunk in node.children:
                node = node.children[chunk]
                if not node.is_dir:
                    raise NotADirectoryError(path)
            else:
                new = VfsNode(name=chunk, is_dir=True, mode=0o755)
                node.children[chunk] = new
                node = new
        node.children[leaf] = VfsNode(
            name=leaf, is_dir=False, data=b"", mode=0o777 | 0o120000,
            symlink_target=target,
        )
        return node.children[leaf]

    def unlink(self, path: str) -> bool:
        parts = self._split(path)
        if not parts:
            return False
        *dirs, leaf = parts
        node = self._walk("/" + "/".join(dirs)) if dirs else self.root
        if node is None or leaf not in node.children:
            return False
        del node.children[leaf]
        return True

    def rmdir(self, path: str) -> bool:
        node = self.find(path)
        if node is None or not node.is_dir or node.children:
            return False
        return self.unlink(path)

    # -- read helpers -----------------------------------------------------

    def find(self, path: str) -> Optional[VfsNode]:
        return self._walk(path, create_missing=False)

    def listdir(self, path: str = "/") -> List[str]:
        node = self.find(path)
        if node is None:
            raise FileNotFoundError(path)
        if not node.is_dir:
            raise NotADirectoryError(path)
        return sorted(node.children.keys())

    def exists(self, path: str) -> bool:
        return self.find(path) is not None

    def walk(self, path: str = "/"):
        """Recursive generator yielding (dirpath, dirnames, filenames)."""
        node = self.find(path)
        if node is None or not node.is_dir:
            return
        dirs, files = [], []
        for name, child in node.children.items():
            (dirs if child.is_dir else files).append(name)
        yield path, sorted(dirs), sorted(files)
        for d in dirs:
            yield from self.walk(f"{'/' if path == '/' else path}/{d}")

    # -- stats ------------------------------------------------------------

    def node_count(self) -> int:
        total = 0
        for _ in self.walk("/"):
            total += 1
        return total

    def total_size(self) -> int:
        total = 0
        for _, _, files in self.walk("/"):
            for f in files:
                node = self.find(f"/{f}")
                # the walk yields relative paths; reconstruct properly:
                if node is not None:
                    total += node.size
        return total

    def snapshot(self) -> Dict[str, dict]:
        """Return ``{path: {kind, mode, size, target}}`` for every node."""
        out: Dict[str, dict] = {}
        for dirpath, dirs, files in self.walk("/"):
            for d in dirs:
                p = f"{dirpath}/{d}"
                node = self.find(p)
                if node is not None:
                    out[p] = {
                        "kind": "dir",
                        "mode": oct(node.mode),
                        "size": node.size,
                    }
            for f in files:
                p = f"{dirpath}/{f}"
                node = self.find(p)
                if node is not None:
                    out[p] = {
                        "kind": "link" if node.is_symlink else "file",
                        "mode": oct(node.mode),
                        "size": node.size,
                        "target": node.symlink_target,
                    }
        return out


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    root = VfsRoot()
    root.mkdir("/etc")
    root.touch("/etc/hostname", data=b"umer-os\n")
    root.symlink("/bin/sh", "/bin/busybox")
    root.write_file("/var/log/dmesg.log", b"")
    if root.read_file("/etc/hostname") != b"umer-os\n":
        return False
    if root.find("/bin/sh").symlink_target != "/bin/busybox":
        return False
    listing = root.listdir("/")
    return {"bin", "etc", "var"}.issubset(set(listing))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("vfs_ops selftest:", "OK" if _selftest() else "FAIL")
