#!/usr/bin/env python3
"""
Virtual File System (VFS) Layer

Translates standard POSIX-style paths into QFS content-hash operations.
This is the interface that user-space programs (and the Syscall Shim)
interact with — they never touch QFS directly.

Equivalent to Linux's VFS layer (fs/namei.c, fs/read_write.c).
"""

from fs.qfs import QFS, QuantumFileSystem


class VFSNode:
    """An entry in the virtual directory tree."""
    __slots__ = ('name', 'is_dir', 'children', 'content_hash')

    def __init__(self, name: str, is_dir: bool = False):
        self.name = name
        self.is_dir = is_dir
        self.children: dict = {}  # name -> VFSNode
        self.content_hash: str = ""


class VirtualFileSystem:
    """
    Provides a POSIX-like interface on top of the QFS CAS store.
    Supports mkdir, write, read, ls, stat, and delete.
    """

    def __init__(self, qfs=None):
        # Accept QFS, QuantumFileSystem (same class), or create a new one
        if qfs is None:
            self._qfs = QFS()
        else:
            self._qfs = qfs
        self._root = VFSNode("/", is_dir=True)
        print("[VFS] Virtual File System mounted on QFS.")

    # ------------------------------------------------------------------
    # Path resolution
    # ------------------------------------------------------------------
    def _resolve(self, path: str, create_dirs: bool = False) -> VFSNode:
        """Walk the VFS tree to resolve a path. Optionally create intermediate dirs."""
        parts = [p for p in path.strip("/").split("/") if p]
        node = self._root
        for part in parts:
            if part not in node.children:
                if create_dirs:
                    node.children[part] = VFSNode(part, is_dir=True)
                else:
                    raise FileNotFoundError(f"VFS: '{path}' not found")
            node = node.children[part]
        return node

    def _resolve_parent(self, path: str):
        parts = [p for p in path.strip("/").split("/") if p]
        if len(parts) == 0:
            raise ValueError("Cannot resolve parent of root")
        parent_path = "/" + "/".join(parts[:-1])
        filename = parts[-1]
        parent = self._resolve(parent_path, create_dirs=True)
        return parent, filename

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def mkdir(self, path: str):
        self._resolve(path, create_dirs=True)
        print(f"[VFS] mkdir '{path}'")

    def write_file(self, path: str, data: bytes) -> str:
        parent, filename = self._resolve_parent(path)
        content_hash = self._qfs.write_file(path, data)
        file_node = VFSNode(filename, is_dir=False)
        file_node.content_hash = content_hash
        parent.children[filename] = file_node
        return content_hash

    def read_file(self, path: str) -> bytes:
        return self._qfs.read_file(path)

    def exists(self, path: str) -> bool:
        try:
            self._resolve(path)
            return True
        except FileNotFoundError:
            return False

    def ls(self, path: str = "/") -> list:
        node = self._resolve(path)
        if not node.is_dir:
            return [node.name]
        return list(node.children.keys())

    def delete(self, path: str) -> bool:
        parent, filename = self._resolve_parent(path)
        if filename in parent.children:
            del parent.children[filename]
            self._qfs.delete_file(path)
            return True
        return False

    def stat(self, path: str) -> dict:
        node = self._resolve(path)
        if node.is_dir:
            return {
                "name": node.name,
                "type": "dir",
                "is_dir": True,
                "content_hash": None,
                "children_count": len(node.children),
                "size": 0,
            }
        info = self._qfs.file_info(path) or {}
        return {
            "name": node.name,
            "type": "file",
            "is_dir": False,
            "content_hash": node.content_hash,
            "children_count": 0,
            "size": info.get("size", 0),
        }
