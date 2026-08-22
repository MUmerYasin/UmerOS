"""
UmerOS /var Directory Management
==================================
Manages additional /var subdirectories required by FHS 3.0.

FHS 3.0:
  /var/local    — Variable data for /usr/local
  /var/lock     — Lock files (symlink to /run/lock)
  /var/opt      — Variable data for /opt
  /var/run      — Runtime data (now /run, symlink)
  /var/tmp      — Temporary files preserved between reboots

Author:  Umer OS Project
License: GPL-3.0
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# [FIX H303] Shared guard that keeps caller-supplied names inside the
# manager-owned root (defeats directory-traversal / cron-RCE, CWE-22).
from ._path_guard import safe_child, PathTraversalError

# [FIX H304] Gate privileged /var FHS filesystem mutation behind the zero-trust
# capability bridge. Creating/removing directories, lock/PID files, and reaping
# /var/tmp are privileged operations that must require the `fs.admin`
# capability when a CapabilityManager is wired (fail-closed); when no manager is
# wired the gate stays permissive (warning) so existing flows keep working.
try:
    from core.capability_gate import gate, CAP_FS_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    import sys
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_FS_ADMIN

log = logging.getLogger("UmerOS.Var.DirectoryManager")


@dataclass
class LockInfo:
    """Represents a lock file."""
    name: str
    path: str
    pid: Optional[int] = None
    created: float = 0.0
    description: str = ""


class VarDirectoryManager:
    """
    Manages /var subdirectories required by FHS 3.0.

    Handles /var/local, /var/lock, /var/opt, /var/run, and /var/tmp.
    """

    def __init__(self, var_path: str = "/var") -> None:
        self.var_path = Path(var_path)
        self.local_path = self.var_path / "local"
        self.lock_path = self.var_path / "lock"
        self.opt_path = self.var_path / "opt"
        self.run_path = self.var_path / "run"
        self.tmp_path = self.var_path / "tmp"

    # ── /var/local ──────────────────────────────────────────────────────

    def list_local_contents(self) -> List[Dict[str, str]]:
        """List contents of /var/local (variable data for /usr/local)."""
        if not self.local_path.exists():
            return []
        items = []
        for item in self.local_path.iterdir():
            entry = {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "path": str(item),
            }
            if item.is_file():
                entry["size"] = str(item.stat().st_size)
            items.append(entry)
        return items

    def create_local_directory(self, name: str) -> bool:
        """Create a subdirectory in /var/local."""
        # [FIX H304] privileged FHS mutation -> requires fs.admin when wired.
        gate.require(CAP_FS_ADMIN)
        try:
            # [FIX H303] contain the caller-supplied name inside /var/local.
            target = safe_child(self.local_path, name)
            target.mkdir(parents=True, exist_ok=True)
            log.info("Created /var/local/%s", name)
            return True
        except PathTraversalError as e:
            # Refuse the traversal attempt; do NOT touch anything outside root.
            log.error("Refused path-traversal in create_local_directory: %s", e)
            return False
        except Exception as e:
            log.error("Failed to create /var/local/%s: %s", name, e)
            return False

    def remove_local_item(self, name: str) -> bool:
        """Remove an item from /var/local."""
        # [FIX H304] privileged FHS delete -> requires fs.admin when wired.
        gate.require(CAP_FS_ADMIN)
        try:
            # [FIX H303] contain the caller-supplied name inside /var/local.
            target = safe_child(self.local_path, name)
        except PathTraversalError as e:
            log.error("Refused path-traversal in remove_local_item: %s", e)
            return False
        if not target.exists():
            return False
        try:
            if target.is_file():
                target.unlink()
            else:
                shutil.rmtree(target)
            log.info("Removed /var/local/%s", name)
            return True
        except Exception as e:
            log.error("Failed to remove /var/local/%s: %s", name, e)
            return False

    # ── /var/lock ───────────────────────────────────────────────────────

    def acquire_lock(self, name: str, pid: Optional[int] = None,
                     description: str = "") -> bool:
        """Create a lock file in /var/lock."""
        # [FIX H304] privileged FHS mutation -> requires fs.admin when wired.
        gate.require(CAP_FS_ADMIN)
        try:
            # [FIX H303] contain the caller-supplied name inside /var/lock.
            lock_file = safe_child(self.lock_path, name)
        except PathTraversalError as e:
            log.error("Refused path-traversal in acquire_lock: %s", e)
            return False
        try:
            self.lock_path.mkdir(parents=True, exist_ok=True)
            pid_str = str(pid or os.getpid())
            content = f"Lock: {name}\nPID: {pid_str}\n"
            if description:
                content += f"Description: {description}\n"
            content += f"Created: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            lock_file.write_text(content, encoding="utf-8")
            log.info("Acquired lock: %s (PID %s)", name, pid_str)
            return True
        except Exception as e:
            log.error("Failed to acquire lock %s: %s", name, e)
            return False

    def release_lock(self, name: str) -> bool:
        """Release a lock file."""
        # [FIX H304] privileged FHS delete -> requires fs.admin when wired.
        gate.require(CAP_FS_ADMIN)
        try:
            # [FIX H303] contain the caller-supplied name inside /var/lock.
            lock_file = safe_child(self.lock_path, name)
        except PathTraversalError as e:
            log.error("Refused path-traversal in release_lock: %s", e)
            return False
        if not lock_file.exists():
            return False
        try:
            lock_file.unlink()
            log.info("Released lock: %s", name)
            return True
        except Exception as e:
            log.error("Failed to release lock %s: %s", name, e)
            return False

    def list_locks(self) -> List[LockInfo]:
        """List all lock files."""
        if not self.lock_path.exists():
            return []
        locks = []
        for item in self.lock_path.iterdir():
            if item.is_file():
                info = LockInfo(
                    name=item.name,
                    path=str(item),
                    created=item.stat().st_ctime,
                )
                # Try to extract PID from lock file
                try:
                    content = item.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        if line.startswith("PID:"):
                            info.pid = int(line.split(":", 1)[1].strip())
                        elif line.startswith("Description:"):
                            info.description = line.split(":", 1)[1].strip()
                except Exception as e:
                    # [FIX H305] fail-closed: a malformed lock file is a
                    # best-effort metadata parse, not a silent swallow.
                    log.debug("Could not parse lock metadata: %s", e)
                locks.append(info)
        return locks

    def check_lock(self, name: str) -> bool:
        """Check if a lock exists."""
        try:
            # [FIX H303] contain the caller-supplied name inside /var/lock.
            lock_file = safe_child(self.lock_path, name)
        except PathTraversalError:
            # A traversal attempt is never a valid existing lock.
            return False
        return lock_file.exists()

    # ── /var/opt ────────────────────────────────────────────────────────

    def list_opt_contents(self) -> List[Dict[str, str]]:
        """List contents of /var/opt (variable data for /opt)."""
        if not self.opt_path.exists():
            return []
        items = []
        for item in self.opt_path.iterdir():
            entry = {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "path": str(item),
            }
            if item.is_file():
                entry["size"] = str(item.stat().st_size)
            items.append(entry)
        return items

    def create_opt_directory(self, name: str) -> bool:
        """Create a subdirectory in /var/opt."""
        # [FIX H304] privileged FHS mutation -> requires fs.admin when wired.
        gate.require(CAP_FS_ADMIN)
        try:
            # [FIX H303] contain the caller-supplied name inside /var/opt.
            target = safe_child(self.opt_path, name)
            target.mkdir(parents=True, exist_ok=True)
            log.info("Created /var/opt/%s", name)
            return True
        except PathTraversalError as e:
            log.error("Refused path-traversal in create_opt_directory: %s", e)
            return False
        except Exception as e:
            log.error("Failed to create /var/opt/%s: %s", name, e)
            return False

    # ── /var/run ────────────────────────────────────────────────────────

    def list_run_contents(self) -> List[Dict[str, str]]:
        """List contents of /var/run (runtime data)."""
        if not self.run_path.exists():
            return []
        items = []
        for item in self.run_path.iterdir():
            entry = {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "path": str(item),
            }
            if item.is_file():
                entry["size"] = str(item.stat().st_size)
            items.append(entry)
        return items

    def create_pid_file(self, name: str, pid: Optional[int] = None) -> bool:
        """Create a PID file in /var/run."""
        # [FIX H304] privileged FHS mutation -> requires fs.admin when wired.
        gate.require(CAP_FS_ADMIN)
        try:
            # [FIX H303] contain the caller-supplied name inside /var/run.
            pid_file = safe_child(self.run_path, name)
        except PathTraversalError as e:
            log.error("Refused path-traversal in create_pid_file: %s", e)
            return False
        try:
            self.run_path.mkdir(parents=True, exist_ok=True)
            pid_file.write_text(str(pid or os.getpid()), encoding="utf-8")
            log.info("Created PID file: /var/run/%s", name)
            return True
        except Exception as e:
            log.error("Failed to create PID file %s: %s", name, e)
            return False

    def read_pid_file(self, name: str) -> Optional[int]:
        """Read a PID file."""
        try:
            # [FIX H303] contain the caller-supplied name inside /var/run.
            pid_file = safe_child(self.run_path, name)
        except PathTraversalError:
            return None
        if not pid_file.exists():
            return None
        try:
            return int(pid_file.read_text(encoding="utf-8").strip())
        except (ValueError, Exception):
            return None

    def remove_pid_file(self, name: str) -> bool:
        """Remove a PID file."""
        # [FIX H304] privileged FHS delete -> requires fs.admin when wired.
        gate.require(CAP_FS_ADMIN)
        try:
            # [FIX H303] contain the caller-supplied name inside /var/run.
            pid_file = safe_child(self.run_path, name)
        except PathTraversalError as e:
            log.error("Refused path-traversal in remove_pid_file: %s", e)
            return False
        if not pid_file.exists():
            return False
        try:
            pid_file.unlink()
            return True
        except Exception as e:
            log.error("Failed to remove PID file %s: %s", name, e)
            return False

    # ── /var/tmp ────────────────────────────────────────────────────────

    def create_tmp_file(self, prefix: str = "tmp",
                        suffix: str = "") -> Optional[str]:
        """Create a temporary file in /var/tmp."""
        # [FIX H304] privileged FHS mutation -> requires fs.admin when wired.
        gate.require(CAP_FS_ADMIN)
        try:
            self.tmp_path.mkdir(parents=True, exist_ok=True)
            fd, path = tempfile.mkstemp(
                dir=str(self.tmp_path),
                prefix=prefix,
                suffix=suffix,
            )
            os.close(fd)
            log.info("Created temp file: %s", path)
            return path
        except Exception as e:
            log.error("Failed to create temp file: %s", e)
            return None

    def create_tmp_directory(self, prefix: str = "tmp") -> Optional[str]:
        """Create a temporary directory in /var/tmp."""
        # [FIX H304] privileged FHS mutation -> requires fs.admin when wired.
        gate.require(CAP_FS_ADMIN)
        try:
            self.tmp_path.mkdir(parents=True, exist_ok=True)
            path = tempfile.mkdtemp(
                dir=str(self.tmp_path),
                prefix=prefix,
            )
            log.info("Created temp directory: %s", path)
            return path
        except Exception as e:
            log.error("Failed to create temp directory: %s", e)
            return None

    def cleanup_tmp(self, max_age_hours: int = 24) -> int:
        """Remove temporary files older than max_age_hours."""
        # [FIX H304] privileged FHS delete -> requires fs.admin when wired.
        gate.require(CAP_FS_ADMIN)
        if not self.tmp_path.exists():
            return 0
        cutoff = time.time() - (max_age_hours * 3600)
        removed = 0
        for item in self.tmp_path.iterdir():
            if item.stat().st_mtime < cutoff:
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                    removed += 1
                except Exception as e:
                    log.error("Failed to remove temp item %s: %s", item.name, e)
        return removed

    def list_tmp_files(self) -> List[Dict[str, str]]:
        """List contents of /var/tmp."""
        if not self.tmp_path.exists():
            return []
        items = []
        for item in self.tmp_path.iterdir():
            entry = {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "path": str(item),
                "size": str(item.stat().st_size) if item.is_file() else "0",
                "modified": time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime(item.stat().st_mtime),
                ),
            }
            items.append(entry)
        return items

    # ── Summary ─────────────────────────────────────────────────────────

    def get_summary(self) -> Dict[str, int]:
        """Get summary of managed /var directories."""
        return {
            "local_entries": len(self.list_local_contents()),
            "active_locks": len(self.list_locks()),
            "opt_entries": len(self.list_opt_contents()),
            "run_entries": len(self.list_run_contents()),
            "tmp_files": len(self.list_tmp_files()),
        }
