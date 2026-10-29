"""Distributed VFS (UmerDFS) — virtual filesystem over SoftBus.

Provides POSIX-like file operations (open, read, write, readdir) over
UmerSoftBus, with LRU chunk caching for repeated reads.
"""
from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

CHUNK_SIZE = 64 * 1024  # 64 KB chunks
CACHE_MAX_ENTRIES = 256


class DistributedVFS:
    """Virtual filesystem adapter implementing POSIX calls over SoftBus."""

    def __init__(self, node_id: str = "local", cache_size: int = CACHE_MAX_ENTRIES) -> None:
        self.node_id = node_id
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._cache_size = cache_size
        self._remote_files: Dict[str, "RemoteFile"] = {}
        self._peers: Dict[str, dict] = {}

    def register_peer(self, peer_id: str, peer_info: dict) -> None:
        self._peers[peer_id] = peer_info

    def evict_peer(self, peer_id: str) -> None:
        self._peers.pop(peer_id, None)
        # Remove cached chunks for this peer
        keys_to_remove = [k for k in self._cache if k.startswith(f"{peer_id}:")]
        for k in keys_to_remove:
            del self._cache[k]

    def _cache_key(self, peer_id: str, path: str, offset: int) -> str:
        return f"{peer_id}:{path}:{offset}"

    def _get_cached(self, key: str) -> Optional[bytes]:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _put_cached(self, key: str, data: bytes) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = data
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    def parse_path(self, path: str) -> Tuple[str, str]:
        """Parse dfs://<peer_id>/path into (peer_id, remote_path)."""
        if path.startswith("dfs://"):
            rest = path[6:]
            if "/" in rest:
                peer_id, remote_path = rest.split("/", 1)
                return peer_id, "/" + remote_path
            return rest, "/"
        return self.node_id, path

    def readdir(self, path: str) -> List[dict]:
        """List directory contents."""
        peer_id, remote_path = self.parse_path(path)
        if peer_id == self.node_id:
            # Local filesystem - return simulated listing
            return [{"name": ".", "type": "dir"}, {"name": "..", "type": "dir"}]
        # Remote: would send request over SoftBus
        # Simulated response
        return [
            {"name": "shared", "type": "dir", "peer": peer_id},
            {"name": "documents", "type": "dir", "peer": peer_id},
        ]

    def read(self, path: str, offset: int = 0, length: Optional[int] = None) -> bytes:
        """Read file data with chunk caching."""
        peer_id, remote_path = self.parse_path(path)
        if peer_id == self.node_id:
            return b""  # Local read handled by normal FS
        read_len = length or CHUNK_SIZE
        key = self._cache_key(peer_id, remote_path, offset)
        cached = self._get_cached(key)
        if cached is not None:
            return cached[:read_len]
        # Simulate remote read (would go over SoftBus)
        data = self._remote_read(peer_id, remote_path, offset, read_len)
        self._put_cached(key, data)
        return data

    def _remote_read(self, peer_id: str, path: str, offset: int, length: int) -> bytes:
        """Simulate remote read over SoftBus."""
        # In production, this sends a chunked read request over UmerSoftBus
        return b""

    def write(self, path: str, data: bytes, offset: int = 0) -> int:
        """Write file data."""
        peer_id, remote_path = self.parse_path(path)
        if peer_id == self.node_id:
            return 0  # Local write handled by normal FS
        # Simulate remote write
        return len(data)

    def exists(self, path: str) -> bool:
        peer_id, remote_path = self.parse_path(path)
        if peer_id == self.node_id:
            return True
        return peer_id in self._peers

    def stat(self, path: str) -> dict:
        peer_id, remote_path = self.parse_path(path)
        return {
            "path": path,
            "peer_id": peer_id,
            "remote_path": remote_path,
            "size": 0,
            "is_dir": remote_path.endswith("/"),
            "modified": time.time(),
        }

    def list_peers(self) -> List[str]:
        return list(self._peers.keys())

    @property
    def cache_size(self) -> int:
        return len(self._cache)