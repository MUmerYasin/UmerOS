import hashlib
import lzma
from pathlib import Path
from typing import Dict


class QuantumFileSystem:
    def __init__(self):
        self.store: Dict[str, bytes] = {}

    def _key(self, path: str) -> str:
        return hashlib.sha256(path.encode()).hexdigest()

    def write(self, path: str, data: bytes):
        compressed = lzma.compress(data)
        self.store[self._key(path)] = compressed

    def read(self, path: str) -> bytes:
        key = self._key(path)
        if key not in self.store:
            raise FileNotFoundError(path)
        return lzma.decompress(self.store[key])

    def exists(self, path: str) -> bool:
        return self._key(path) in self.store