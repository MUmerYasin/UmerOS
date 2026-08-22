# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""UmerOS procfs — the /proc virtual filesystem.

``ProcFileSystem`` is the root of the entire /proc tree.  It:
  * lazily builds per-PID directories (cached with signature-based
    invalidation, so a new ``tick()`` refreshes stale entries)
  * resolves ``/proc/<path>`` requests through its node tree
  * implements ``read`` / ``write`` / ``list`` with Linux procfs
    semantics (zero-size stat, read-only enforcement, permission
    checks)
  * can mount as a bridge into the kernel's ``VirtualFileSystem``,
    intercepting all ``/proc/*`` VFS operations so ``cat /proc/meminfo``
    in the shell reads live data instead of stale static content

**Mount mode** — calling ``mount_into_vfs(vfs)`` removes the old
static /proc files from the kernel VFS and installs a proxy node
that delegates every /proc access to the live ``ProcFileSystem``.

Usage::

    from proc.procfs import ProcFileSystem
    from proc.kernel_adapter import KernelAdapter

    adapter = KernelAdapter(kernel=some_kernel)
    procfs = ProcFileSystem(adapter)
    procfs.read("/proc/meminfo")   # live memory stats
    procfs.list("/proc")           # [cpuinfo, meminfo, 1000, sys, net, ...]
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from proc.nodes import ProcDir, ProcFile, ProcSymlink

log = logging.getLogger("UmerOS.ProcFS")


class ProcFileSystem:
    """Complete /proc virtual filesystem backed by a KernelAdapter.

    On construction the root directory, /proc/self symlink, and all
    system subdirectories are populated.  Per-PID directories are
    built lazily on first access and cached until the underlying
    task signature changes.
    """

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter
        self.root = ProcDir("/", mode="r-xr-xr-x")
        self._pid_cache: Dict[int, ProcDir] = {}
        self._pid_sigs: Dict[int, tuple] = {}
        self._init_time = time.time()

        from proc.system_files import register_system_entries
        register_system_entries(self)

        from proc.net_files import register_net_entries
        register_net_entries(self)

        from proc.sysctl_fs import register_sysctl_entries
        register_sysctl_entries(self)

        from proc.sysvipc import register_sysvipc_entries
        register_sysvipc_entries(self)

        from proc.tty_files import register_tty_entries
        register_tty_entries(self)

        # /proc/self → current init task (refreshed on every resolve)
        self.root.add(ProcSymlink("self", self._self_target))

        log.debug("procfs initialised with %d top-level entries",
                   len(self.root.names()))

    # ── /proc/self ─────────────────────────────────────────────────

    def _self_target(self) -> str:
        pid = self.adapter.current_pid()
        return str(pid)

    # ── PID directory management ────────────────────────────────────

    def _refresh_pid_dirs(self) -> None:
        """Rebuild / refresh cached per-PID directories."""
        live_pids = set(self.adapter.pids())
        cached = set(self._pid_cache.keys())

        # Remove directories for exited PIDs
        for gone in cached - live_pids:
            self.root.remove(str(gone))
            self._pid_cache.pop(gone, None)
            self._pid_sigs.pop(gone, None)

        # Build or refresh live PID directories
        for pid in live_pids:
            sig = self._pid_signature(pid)
            if sig is None:
                self.root.remove(str(pid))
                self._pid_cache.pop(pid, None)
                self._pid_sigs.pop(pid, None)
                continue
            if pid in self._pid_cache and self._pid_sigs.get(pid) == sig:
                continue
            self.root.remove(str(pid))
            try:
                from proc.pid_entries import build_pid_dir
                pid_dir = build_pid_dir(self.adapter, pid)
                self.root.add(pid_dir)
                self._pid_cache[pid] = pid_dir
                self._pid_sigs[pid] = sig
            except FileNotFoundError:
                self._pid_cache.pop(pid, None)
                self._pid_sigs.pop(pid, None)

    def _pid_signature(self, pid: int):
        task = self.adapter.task(pid)
        if task is None:
            return None
        return (pid, task["name"], task["state"])

    # ── path resolution ────────────────────────────────────────────

    def _resolve(self, path: str):
        """Resolve a /proc-relative path to a (ProcNode, resolved_path).

        Returns ``(None, None)`` if the path does not exist.
        """
        if not path or path == "/":
            return self.root, "/"
        path = path.rstrip("/")

        # Strip leading /proc/ if present
        if path.startswith("/proc/"):
            path = path[6:]
        elif path.startswith("/proc"):
            path = path[5:].lstrip("/")

        parts = [p for p in path.split("/") if p and p != "."]
        curr: Any = self.root
        resolved = []
        for part in parts:
            if part == "..":
                if resolved:
                    resolved.pop()
                continue
            if isinstance(curr, ProcSymlink):
                target = curr.readlink()
                rest = "/".join(parts[len(resolved):])
                return self._resolve("/" + "/".join([target, rest])
                                       if rest else "/" + target)
            if not isinstance(curr, ProcDir) or part not in curr.children:
                return None, None
            curr = curr.children[part]
            resolved.append(part)
        abs_path = "/" + "/".join(resolved) if resolved else "/"
        return curr, abs_path

    # ── public API ─────────────────────────────────────────────────

    def read(self, path: str) -> str:
        """Read a /proc file — returns its dynamic content."""
        # Refresh PID dirs before resolving so new tasks appear
        self._refresh_pid_dirs()
        node, _ = self._resolve(path)
        if node is None:
            raise FileNotFoundError(f"No such file or directory: {path}")
        if isinstance(node, ProcSymlink):
            target = node.readlink()
            return self.read("/" + target.lstrip("/"))
        if isinstance(node, ProcDir):
            raise IsADirectoryError(f"Is a directory: {path}")
        if not isinstance(node, ProcFile):
            raise FileNotFoundError(f"Cannot read: {path}")
        return node.read()

    def write(self, path: str, data: Any) -> None:
        """Write to a /proc file (typically /proc/sys/*)."""
        self._refresh_pid_dirs()
        node, _ = self._resolve(path)
        if node is None:
            raise FileNotFoundError(f"No such file or directory: {path}")
        if isinstance(node, ProcDir):
            raise IsADirectoryError(f"Is a directory: {path}")
        if isinstance(node, ProcSymlink):
            raise PermissionError(f"Cannot write through symlink: {path}")
        if not isinstance(node, ProcFile):
            raise FileNotFoundError(f"Cannot write: {path}")
        node.write(data)

    def list(self, path: str = "/") -> List[str]:
        """List entries in a /proc directory."""
        self._refresh_pid_dirs()
        node, _ = self._resolve(path)
        if node is None:
            raise FileNotFoundError(f"No such file or directory: {path}")
        if not isinstance(node, ProcDir):
            return [node.name]
        return node.names()

    def exists(self, path: str) -> bool:
        self._refresh_pid_dirs()
        node, _ = self._resolve(path)
        return node is not None

    def stat(self, path: str) -> Optional[Dict[str, Any]]:
        """Return a dict with node metadata (Linux-style)."""
        self._refresh_pid_dirs()
        node, resolved = self._resolve(path)
        if node is None:
            return None
        is_dir = node.is_dir
        is_symlink = node.is_symlink
        return {
            "name": node.name,
            "path": resolved,
            "is_dir": is_dir,
            "is_symlink": is_symlink,
            "size": node.stat_size(),
            "owner": node.owner,
            "group": node.group,
            "mode": node.mode,
            "mtime": node.mtime,
            "atime": node.atime,
        }

    def readlink(self, path: str) -> str:
        """Read symlink target."""
        self._refresh_pid_dirs()
        node, _ = self._resolve(path)
        if node is None:
            raise FileNotFoundError(f"No such file or directory: {path}")
        if isinstance(node, ProcSymlink):
            return node.readlink()
        raise ValueError(f"Not a symlink: {path}")

    # ── VFS bridge ───────────────────────────────────────────────

    def mount_into_vfs(self, vfs: Any) -> None:
        """Install the procfs into the kernel's VirtualFileSystem.

        Replaces the old static /proc files with a live procfs proxy
        so every ``vfs.read_file("/proc/meminfo")`` returns current data.
        """
        # Remove old static /proc content
        proc_node, _ = vfs._resolve("/proc")
        if proc_node is not None and isinstance(proc_node, VFSNodeProxy):
            pass  # Already mounted
        elif proc_node is not None and proc_node.is_dir:
            # Clear stale static children (cpuinfo, meminfo, etc.)
            for child_name in list(proc_node.children.keys()):
                del proc_node.children[child_name]

        # Install a special proxy node that intercepts VFS access
        proxy = VFSNodeProxy(self)
        # Replace the /proc node in the VFS tree
        parts = ["proc"]
        curr = vfs.root
        for part in parts:
            if part in curr.children:
                curr = curr.children[part]
            else:
                break
        curr.children.clear()
        # Reparent: copy proxy's directory structure markers
        # Actually, we just need to make the VFS node redirect
        curr.__class__ = type(curr)  # keep as-is, but add hook
        _orig_read = vfs.read_file
        _orig_write = vfs.write_file
        _orig_ls = vfs.ls

        def _hooked_read_file(path, *args, **kwargs):
            if self._is_proc_path(path):
                return self.read(path)
            return _orig_read(path, *args, **kwargs)

        def _hooked_write_file(path, data, *args, **kwargs):
            if self._is_proc_path(path):
                self.write(path, data)
                return
            _orig_write(path, data, *args, **kwargs)

        def _hooked_ls(path=None, *args, **kwargs):
            p = path if path else vfs.cwd
            if self._is_proc_path(p):
                return self.list(p)
            return _orig_ls(p, *args, **kwargs)

        vfs.read_file = _hooked_read_file
        vfs.write_file = _hooked_write_file
        vfs.ls = _hooked_ls
        log.info("procfs mounted into kernel VFS (live /proc bridge)")

    @staticmethod
    def _is_proc_path(path: str) -> bool:
        p = path.lstrip("/").split("/")[0] if path else ""
        return p == "proc"

    # ── utility ────────────────────────────────────────────────────

    def top_level_names(self) -> List[str]:
        self._refresh_pid_dirs()
        return self.root.names()

    def all_pids(self) -> List[int]:
        return self.adapter.pids()

    def tree_snapshot(self, prefix: str = "", max_depth: int = 2
                     ) -> str:
        """Return a text tree of the procfs (for debugging)."""
        lines = []
        self._refresh_pid_dirs()

        def _walk(node, path, depth):
            if depth > max_depth:
                lines.append(f"{path}/ ...")
                return
            kind = "/" if node.is_dir else ("@" if node.is_symlink else "")
            extra = ""
            if isinstance(node, ProcFile) and node.writable:
                extra = " [w]"
            lines.append(f"{path}{kind}{extra}")
            if isinstance(node, ProcDir):
                for name in node.names():
                    _walk(node.children[name], f"{path}/{name}", depth + 1)

        _walk(self.root, "", 0)
        return "\n".join(lines)


# ── VFS bridge helper ─────────────────────────────────────────────

class VFSNodeProxy:
    """Marker class to detect an already-mounted procfs proxy."""

    def __init__(self, procfs: ProcFileSystem) -> None:
        self.procfs = procfs
        self.name = "proc"
        self.is_dir = True
        self.children = {}
