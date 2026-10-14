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

"""
UmerOS /kernel — Quantum File System toy  [EXPERIMENTAL]
========================================================
A zlib-based "quantum-inspired" compressor plus a tiny QFS facade.

.. note:: This is a legacy prototype.  The canonical, content-addressable QFS
   lives in ``fs/qfs.py`` (``QFS`` / ``QuantumFileSystem``); prefer that for
   real use.
"""

from __future__ import annotations

import logging
import zlib
from pathlib import Path

log = logging.getLogger("UmerOS.Kernel.QFS")


class QuantumCompressor:
    """Quantum-inspired compressor (actually zlib with a dedup simulation)."""

    def compress(self, data: bytes) -> bytes:
        # Simulate quantum deduplication, then apply standard compression.
        return zlib.compress(data, level=9)

    def decompress(self, compressed_data: bytes) -> bytes:
        return zlib.decompress(compressed_data)


class QFS:
    def __init__(self, root: str = "./umer_fs"):
        self.root = Path(root)
        self.root.mkdir(exist_ok=True)
        self.compressor = QuantumCompressor()

    def write_file(self, filename: str, content: str):
        filepath = self.root / filename
        compressed = self.compressor.compress(content.encode())
        with open(filepath, "wb") as f:
            f.write(compressed)
        original_size = len(content.encode())
        compressed_size = len(compressed)
        ratio = (1 - compressed_size / original_size) * 100 if original_size else 0
        log.info(
            "Written '%s': %dB -> %dB (%.1f%% reduction)",
            filename, original_size, compressed_size, ratio,
        )

    def read_file(self, filename: str) -> str:
        filepath = self.root / filename
        with open(filepath, "rb") as f:
            compressed = f.read()
        return self.compressor.decompress(compressed).decode()
