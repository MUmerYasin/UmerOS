"""
UmerOS /tmp — Directory Hierarchy and Provisioning Engine
==========================================================

Provisions and manages the physical directory structure of ``/tmp``
in UmerOS, supporting standard UNIX socket subdirectories, private
per-process namespaces, and per-user temporary runtimes.

Standard FHS Socket Subdirectories:
-----------------------------------
- /tmp/.X11-unix/     (Mode 1777, X11 Display Sockets)
- /tmp/.ICE-unix/     (Mode 1777, Session Exchange Sockets)
- /tmp/.font-unix/    (Mode 1777, X Font Server Sockets)
- /tmp/.rpc-unix/     (Mode 1777, RPC Sockets)
- /tmp/.Test-unix/    (Mode 1777, Testing & Mock Sockets)
- /tmp/user/<uid>/    (Mode 0700, User-Specific Isolated Runtime)

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fhs import (
    DEFAULT_TMP_ROOT,
    PROTECTED_SOCKET_DIRS,
    FHSValidator,
)

log = logging.getLogger("UmerOS.Tmp.Hierarchy")


class TmpHierarchy:
    """
    Manages physical directory structure creation, verification, and inspection
    for the /tmp filesystem hierarchy.
    """

    def __init__(self, tmp_root: Path | str = DEFAULT_TMP_ROOT) -> None:
        self.root = Path(tmp_root).resolve()
        self._ensure_root()

    def _ensure_root(self) -> None:
        """Ensures the /tmp root directory exists with 1777 permissions."""
        self.root.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            try:
                os.chmod(self.root, 0o1777)
            except OSError as e:
                log.warning(f"Could not set 1777 permissions on {self.root}: {e}")

    def bootstrap(self) -> Dict[str, Path]:
        """
        Provisions standard socket directories and system skeletons in /tmp.
        """
        self._ensure_root()
        created: Dict[str, Path] = {"root": self.root}

        # 1. Standard UNIX Socket Directories (1777)
        for sock_dir_name in PROTECTED_SOCKET_DIRS:
            sock_path = self.root / sock_dir_name
            sock_path.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                try:
                    os.chmod(sock_path, 0o1777)
                except OSError:
                    pass
            created[sock_dir_name] = sock_path

        # 2. Per-User Isolated Runtime Directory Root
        user_root = self.root / "user"
        user_root.mkdir(parents=True, exist_ok=True)
        created["user"] = user_root

        return created

    def get_user_temp_dir(self, uid: int | str = "1000", create: bool = True) -> Path:
        """
        Returns an isolated per-user temporary directory (e.g. /tmp/user/<uid>) with 0700 mode.
        """
        user_dir = self.root / "user" / str(uid)
        if create:
            user_dir.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                try:
                    os.chmod(user_dir, 0o700)
                except OSError:
                    pass
        return user_dir

    def get_stats(self) -> Dict[str, Any]:
        """
        Calculates storage and file statistics across /tmp.
        """
        total_size = 0
        total_files = 0
        total_dirs = 0
        file_types: Dict[str, int] = {}

        if not self.root.exists():
            return {
                "root": str(self.root),
                "total_size_bytes": 0,
                "total_files": 0,
                "total_dirs": 0,
                "file_types": {},
            }

        for root, dirs, files in os.walk(self.root):
            total_dirs += len(dirs)
            for f in files:
                total_files += 1
                fp = os.path.join(root, f)
                try:
                    total_size += os.path.getsize(fp)
                except OSError:
                    pass

                ext = Path(f).suffix.lower() or "no_ext"
                file_types[ext] = file_types.get(ext, 0) + 1

        return {
            "root": str(self.root),
            "total_size_bytes": total_size,
            "total_files": total_files,
            "total_dirs": total_dirs,
            "file_types": file_types,
        }

    def list_entries(self, include_hidden: bool = True) -> List[Dict[str, Any]]:
        """
        Lists all immediate entries in /tmp with metadata.
        """
        entries = []
        if not self.root.exists():
            return entries

        for item in sorted(self.root.iterdir()):
            if not include_hidden and item.name.startswith("."):
                continue

            try:
                st = item.stat()
                is_protected = FHSValidator.is_protected_directory(item.name)
                entries.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "size_bytes": st.st_size if item.is_file() else 0,
                    "mtime": st.st_mtime,
                    "atime": st.st_atime,
                    "is_protected": is_protected,
                })
            except OSError:
                continue

        return entries
