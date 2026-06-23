#!/usr/bin/env python3
"""
Quantum File System (QFS) - Content-Addressable Storage Engine

Instead of mapping files to disk blocks like ext4/NTFS, QFS hashes file
contents to derive a unique address. Identical data shares a single
storage slot (automatic deduplication). All data is LZMA-compressed
before storage.

This is equivalent to Linux's fs/ subsystem but built for a
quantum-native, AI-driven operating system.
"""

import hashlib
import lzma
import time
from typing import Dict, Optional


class QFSBlock:
    """A single content-addressed block in the store."""
    __slots__ = ('content_hash', 'data', 'ref_count', 'created_at')

    def __init__(self, content_hash: str, data: bytes):
        self.content_hash = content_hash
        self.data = data
        self.ref_count = 1
        self.created_at = time.time()


class QuantumFileSystem:
    """
    Content-Addressable Storage (CAS) filesystem.

    Write path:
        raw bytes -> LZMA compress -> SHA-256 content hash -> store once
    Read path:
        content hash -> decompress -> raw bytes

    Deduplication is automatic: if two files have identical content,
    they share one block and the reference count increments.
    """

    def __init__(self):
        # content_hash -> QFSBlock
        self._blocks: Dict[str, QFSBlock] = {}
        # path -> content_hash  (the inode table equivalent)
        self._path_index: Dict[str, str] = {}
        self._stats = {'writes': 0, 'reads': 0, 'dedup_hits': 0, 'bytes_saved': 0}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _content_hash(self, data: bytes) -> str:
        """Derive a deterministic address from raw content."""
        return hashlib.sha256(data).hexdigest()

    def _compress(self, data: bytes) -> bytes:
        return lzma.compress(data)

    def _decompress(self, data: bytes) -> bytes:
        return lzma.decompress(data)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def write(self, path: str, data: bytes) -> str:
        """
        Write data to the QFS under the given virtual path.
        Returns the content hash (the CAS address).
        """
        content_hash = self._content_hash(data)
        self._stats['writes'] += 1

        if content_hash in self._blocks:
            # Deduplication hit — same content already stored
            self._blocks[content_hash].ref_count += 1
            self._stats['dedup_hits'] += 1
            self._stats['bytes_saved'] += len(data)
            print(f"[QFS] DEDUP hit for '{path}' -> {content_hash[:12]}… (refs={self._blocks[content_hash].ref_count})")
        else:
            compressed = self._compress(data)
            self._blocks[content_hash] = QFSBlock(content_hash, compressed)
            ratio = len(compressed) / max(len(data), 1) * 100
            print(f"[QFS] Stored '{path}' -> {content_hash[:12]}… ({len(data)}B -> {len(compressed)}B, {ratio:.1f}%)")

        # Update the path index (overwrite if the path already existed)
        old_hash = self._path_index.get(path)
        if old_hash and old_hash != content_hash:
            self._decrement_ref(old_hash)
        self._path_index[path] = content_hash
        return content_hash

    def read(self, path: str) -> bytes:
        """Read raw bytes from a virtual path."""
        if path not in self._path_index:
            raise FileNotFoundError(f"QFS: '{path}' not found")
        content_hash = self._path_index[path]
        block = self._blocks[content_hash]
        self._stats['reads'] += 1
        return self._decompress(block.data)

    def exists(self, path: str) -> bool:
        return path in self._path_index

    def delete(self, path: str) -> bool:
        if path not in self._path_index:
            return False
        content_hash = self._path_index.pop(path)
        self._decrement_ref(content_hash)
        print(f"[QFS] Deleted '{path}'")
        return True

    def list_dir(self, prefix: str = "/") -> list:
        """List all paths under a given prefix."""
        return [p for p in self._path_index if p.startswith(prefix)]

    def stats(self) -> dict:
        return dict(self._stats)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _decrement_ref(self, content_hash: str):
        if content_hash in self._blocks:
            self._blocks[content_hash].ref_count -= 1
            if self._blocks[content_hash].ref_count <= 0:
                del self._blocks[content_hash]