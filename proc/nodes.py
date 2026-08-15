"""Node primitives for the UmerOS procfs (/proc) implementation.

Mirrors the semantics described in the Linux Filesystem Hierarchy docs
for /proc:

* Entries are *virtual*: content is generated on the fly by a read
  handler, never stored on disk.
* Nearly all files report size 0 in stat() — they are "a window into
  the kernel" (TLDP).  The exceptions (``kcore``, ``mtrr``, symlinks)
  override the reported size.
* Most entries are read-only (``r--r--r--``); writable entries live
  under /proc/sys and are root-owned ``rw-r--r--``.
* Writing to a read-only entry raises PermissionError; reading a
  directory raises IsADirectoryError — exactly like the real procfs.
"""
from __future__ import annotations

import time
from typing import Callable, Dict, Optional

ReadHandler = Callable[[], object]
WriteHandler = Callable[[str], None]


class ProcNode:
    """Base class for all /proc tree entries."""

    def __init__(self, name: str, mode: str = "r--r--r--",
                 owner: str = "root", group: str = "root") -> None:
        self.name = name
        self.mode = mode
        self.owner = owner
        self.group = group
        self.mtime = time.time()
        self.atime = time.time()

    @property
    def is_dir(self) -> bool:
        return isinstance(self, ProcDir)

    @property
    def is_symlink(self) -> bool:
        return isinstance(self, ProcSymlink)

    def stat_size(self) -> int:
        raise NotImplementedError

    def touch_access(self) -> None:
        self.atime = time.time()


class ProcFile(ProcNode):
    """A virtual file whose content is produced by ``read_handler``.

    Args:
        name: File name inside its parent directory.
        read: Callable returning the file content (str/bytes coerced
            to str).  When omitted, static ``content`` is served.
        content: Static fallback content.
        write: Callable receiving the raw written string.  When
            omitted the file is read-only.
        mode: 9-character permission string.
        size_zero: Report size 0 in stat (authentic procfs behaviour).
        virtual_size: Explicit stat size override (e.g. ``kcore``).
        owner/group: Owning user/group ("root" for system files).
    """

    def __init__(self, name: str, read: Optional[ReadHandler] = None,
                 content: str = "", write: Optional[WriteHandler] = None,
                 mode: str = "r--r--r--", size_zero: bool = True,
                 virtual_size: Optional[int] = None,
                 owner: str = "root", group: str = "root") -> None:
        super().__init__(name, mode=mode, owner=owner, group=group)
        self._read = read
        self._static = content
        self._write = write
        self._size_zero = size_zero
        self._virtual_size = virtual_size
        self._last_content: str = content

    @property
    def writable(self) -> bool:
        return self._write is not None

    def read(self) -> str:
        if self._read is not None:
            data = self._read()
            content = data if isinstance(data, str) else str(data)
        else:
            content = self._static
        self._last_content = content
        self.touch_access()
        return content

    def write(self, data) -> None:
        if self._write is None:
            raise PermissionError(
                f"/proc entry {self.name!r} is read-only")
        text = data.decode("utf-8") if isinstance(data, bytes) else str(data)
        self._write(text)
        self.mtime = time.time()

    def stat_size(self) -> int:
        if self._virtual_size is not None:
            return self._virtual_size
        if self._size_zero:
            return 0
        return len(self._last_content.encode("utf-8"))


class ProcDir(ProcNode):
    """A virtual directory holding child nodes."""

    def __init__(self, name: str, mode: str = "r-xr-xr-x",
                 owner: str = "root", group: str = "root") -> None:
        super().__init__(name, mode=mode, owner=owner, group=group)
        self.children: Dict[str, ProcNode] = {}

    def add(self, node: ProcNode) -> ProcNode:
        self.children[node.name] = node
        return node

    def get(self, name: str) -> Optional[ProcNode]:
        return self.children.get(name)

    def remove(self, name: str) -> None:
        self.children.pop(name, None)

    def names(self) -> list:
        return sorted(self.children.keys())

    def stat_size(self) -> int:
        return 4096  # directories report the classic block size


class ProcSymlink(ProcNode):
    """A virtual symlink (e.g. /proc/self, /proc/<pid>/cwd).

    The target may be a static string or a callable returning one
    (so /proc/self resolves to the *current* reader's pid).
    """

    def __init__(self, name: str, target,
                 mode: str = "r--r--r--",
                 owner: str = "root", group: str = "root") -> None:
        super().__init__(name, mode=mode, owner=owner, group=group)
        self._target = target

    def readlink(self) -> str:
        target = self._target() if callable(self._target) else self._target
        return str(target)

    def stat_size(self) -> int:
        return len(self.readlink().encode("utf-8"))
