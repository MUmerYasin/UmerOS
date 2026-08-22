"""
UmerOS /tmp — In-Memory Temporary Filesystem (TmpFS)
===================================================

Provides a high-performance RAM-backed virtual temporary filesystem layer
for UmerOS kernel, quantum simulator, and fast process scratch spaces.

Features:
---------
* Pure in-memory virtual filesystem with byte quotas.
* Atomic file creation, reading, truncation, and deletion.
* Snapshot export to physical disk /tmp and import from disk.
* Zero disk I/O overhead for ephemeral process buffers.

Author: UmerOS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import io
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# [FIX H282] Guard against path traversal (CWE-22) when syncing virtual files
# to disk — a node name like "../../etc/passwd" could otherwise write anywhere.
try:
    from core.path_guard import safe_join, PathTraversalError
except Exception:  # pragma: no cover - standalone fallback
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.path_guard import safe_join, PathTraversalError

log = logging.getLogger("UmerOS.Tmp.TmpFS")

DEFAULT_TMPFS_MAX_BYTES = 512 * 1024 * 1024  # 512 MB


@dataclass
class TmpFSNode:
    """Virtual in-memory node representing a temporary file or buffer."""
    name: str
    data: bytearray = field(default_factory=bytearray)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    mode: int = 0o600

    @property
    def size(self) -> int:
        return len(self.data)


class TmpFSQuotaExceededError(Exception):
    """Raised when in-memory tmpfs exceeds quota."""
    pass


class TmpFS:
    """
    In-memory virtual temporary filesystem (RAM-disk).
    """

    def __init__(self, max_bytes: int = DEFAULT_TMPFS_MAX_BYTES) -> None:
        self.max_bytes = max_bytes
        self._nodes: Dict[str, TmpFSNode] = {}

    @property
    def used_bytes(self) -> int:
        return sum(node.size for node in self._nodes.values())

    @property
    def free_bytes(self) -> int:
        return max(0, self.max_bytes - self.used_bytes)

    def write_file(self, name: str, data: bytes | str, mode: int = 0o600) -> TmpFSNode:
        """Writes data into an in-memory temporary file."""
        data_bytes = data.encode("utf-8") if isinstance(data, str) else bytearray(data)
        needed = len(data_bytes)
        current_size = self._nodes[name].size if name in self._nodes else 0
        delta = needed - current_size

        if (self.used_bytes + delta) > self.max_bytes:
            raise TmpFSQuotaExceededError(
                f"TmpFS quota exceeded: requested {needed} bytes, free {self.free_bytes} bytes."
            )

        now = time.time()
        if name in self._nodes:
            node = self._nodes[name]
            node.data = bytearray(data_bytes)
            node.modified_at = now
            node.mode = mode
        else:
            node = TmpFSNode(
                name=name,
                data=bytearray(data_bytes),
                created_at=now,
                modified_at=now,
                mode=mode,
            )
            self._nodes[name] = node

        return node

    def read_file(self, name: str) -> bytes:
        """Reads data from an in-memory temporary file."""
        if name not in self._nodes:
            raise FileNotFoundError(f"Virtual file '{name}' not found in TmpFS.")
        return bytes(self._nodes[name].data)

    def delete_file(self, name: str) -> bool:
        """Deletes a virtual file from TmpFS."""
        if name in self._nodes:
            del self._nodes[name]
            return True
        return False

    def list_files(self) -> List[Dict[str, Any]]:
        """Lists all files in TmpFS with metadata."""
        return [
            {
                "name": node.name,
                "size_bytes": node.size,
                "created_at": node.created_at,
                "modified_at": node.modified_at,
                "mode": oct(node.mode),
            }
            for node in self._nodes.values()
        ]

    def clear(self) -> None:
        """Clears all in-memory files."""
        self._nodes.clear()

    def sync_to_disk(self, target_dir: Path | str) -> int:
        """Dumps all virtual files to a physical disk directory."""
        target_path = Path(target_dir).resolve()
        target_path.mkdir(parents=True, exist_ok=True)
        count = 0
        for name, node in self._nodes.items():
            # [FIX H282] Contain each virtual-file name inside target_path. A
            # name like "../../etc/passwd" would otherwise let a stored buffer
            # be written anywhere on disk; we refuse it (fail-closed).
            try:
                dest = safe_join(target_path, name)
            except PathTraversalError:
                log.error("Refusing unsafe tmpfs node name on sync: %r", name)
                continue
            dest.write_bytes(bytes(node.data))
            count += 1
        return count
