"""
Umer OS Initrd Archivers
========================
Compression / decompression wrappers for initramfs images.

Supports the formats commonly used:

* gzip  (.gz)     - the classic; the bootloader's built-in decompressor
                    handles this without external tools.
* xz    (.xz)     - highest compression ratio; modern default for
                    initramfs-tools / dracut on Debian, Arch, Fedora.
* lz4   (.lz4)    - fastest decompress; sometimes used on slow hardware.
* zstd  (.zst)    - best speed/ratio trade-off; used by mkinitcpio on
                    Arch since 2020.
* none  (raw)     - useful for in-memory or debug builds.

Each archiver exposes a uniform interface::

    Archiver.compress(data: bytes) -> bytes
    Archiver.decompress(data: bytes) -> bytes
    Archiver.magic: bytes            # first few bytes of compressed output
    Archiver.extension: str          # recommended file extension

The kernel/bootloader side of UmerOS detects the compression by looking
at the magic bytes. On the host (this module), we use Python's stdlib
where possible and fall back to optional ``lz4`` / ``zstandard`` wheels
if they are installed.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import gzip
import io
import lzma
import logging
import zlib
from abc import ABC, abstractmethod
from typing import Optional

log = logging.getLogger("UmerOS.Initrd.Archivers")


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class Archiver(ABC):
    """Common interface for every supported compression scheme."""

    #: First few bytes of a valid compressed stream (used for autodetect).
    magic: bytes = b""
    #: File extension suggested when writing a new image.
    extension: str = ""

    @classmethod
    @abstractmethod
    def compress(cls, data: bytes, level: int = 6) -> bytes:
        """Return ``data`` compressed with this algorithm."""

    @classmethod
    @abstractmethod
    def decompress(cls, blob: bytes) -> bytes:
        """Return the original bytes from a compressed ``blob``."""


# ---------------------------------------------------------------------------
# gzip
# ---------------------------------------------------------------------------

class GzipArchiver(Archiver):
    """gzip (RFC 1952) - the de-facto initramfs default."""

    magic = b"\x1f\x8b"
    extension = "gz"

    @classmethod
    def compress(cls, data: bytes, level: int = 6) -> bytes:
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=level) as gz:
            gz.write(data)
        return buf.getvalue()

    @classmethod
    def decompress(cls, blob: bytes) -> bytes:
        return gzip.decompress(blob)


# ---------------------------------------------------------------------------
# xz  (LZMA2)
# ---------------------------------------------------------------------------

class XzArchiver(Archiver):
    """xz / LZMA2 - smallest initramfs images; the modern kernel default."""

    magic = b"\xfd7zXZ\x00"
    extension = "xz"

    @classmethod
    def compress(cls, data: bytes, level: int = 6) -> bytes:
        return lzma.compress(data, format=lzma.FORMAT_XZ, preset=level | lzma.PRESET_DEFAULT)

    @classmethod
    def decompress(cls, blob: bytes) -> bytes:
        return lzma.decompress(blob)


# ---------------------------------------------------------------------------
# lz4  (optional - depends on the lz4 package)
# ---------------------------------------------------------------------------

class Lz4Archiver(Archiver):
    """lz4 - extremely fast decompress, used on low-power devices.

    Requires the optional ``lz4`` PyPI package. If it is not installed
    the archiver raises ``RuntimeError`` and the builder will fall back
    to xz automatically.
    """

    magic = b"\x04\x22\x4d\x18"
    extension = "lz4"

    @classmethod
    def _lib(cls):
        try:
            import lz4.block  # type: ignore
            return lz4.block
        except ImportError as exc:  # pragma: no cover - optional dep
            raise RuntimeError(
                "lz4 Python package is not installed; install with "
                "`pip install lz4` to enable Lz4Archiver."
            ) from exc

    @classmethod
    def compress(cls, data: bytes, level: int = 6) -> bytes:
        lib = cls._lib()
        return lib.compress(data, store_size=False, compression=level)

    @classmethod
    def decompress(cls, blob: bytes) -> bytes:
        lib = cls._lib()
        return lib.decompress(blob)


# ---------------------------------------------------------------------------
# zstd  (optional - depends on the zstandard package)
# ---------------------------------------------------------------------------

class ZstdArchiver(Archiver):
    """zstd - best ratio/speed trade-off, used by Arch's mkinitcpio."""

    magic = b"\x28\xb5\x2f\xfd"
    extension = "zst"

    @classmethod
    def _lib(cls):
        try:
            import zstandard  # type: ignore
            return zstandard.ZstdCompressor(), zstandard.ZstdDecompressor()
        except ImportError as exc:  # pragma: no cover - optional dep
            raise RuntimeError(
                "zstandard Python package is not installed; install with "
                "`pip install zstandard` to enable ZstdArchiver."
            ) from exc

    @classmethod
    def compress(cls, data: bytes, level: int = 6) -> bytes:
        cctx, _ = cls._lib()
        return cctx.compress(data, level)

    @classmethod
    def decompress(cls, blob: bytes) -> bytes:
        _, dctx = cls._lib()
        return dctx.decompress(blob)


# ---------------------------------------------------------------------------
# none - raw pass-through
# ---------------------------------------------------------------------------

class RawArchiver(Archiver):
    """No compression. Useful for in-memory or debug builds."""

    magic = b""
    extension = ""

    @classmethod
    def compress(cls, data: bytes, level: int = 0) -> bytes:
        return data

    @classmethod
    def decompress(cls, blob: bytes) -> bytes:
        return blob


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[Archiver]] = {
    "gzip": GzipArchiver,
    "gz":   GzipArchiver,
    "xz":   XzArchiver,
    "lzma": XzArchiver,
    "lz4":  Lz4Archiver,
    "zstd": ZstdArchiver,
    "zst":  ZstdArchiver,
    "none": RawArchiver,
    "raw":  RawArchiver,
    "":     RawArchiver,
}


def get_archiver(name: str) -> type[Archiver]:
    """Return the archiver class for ``name`` (case-insensitive)."""
    key = name.strip().lower()
    if key not in _REGISTRY:
        raise KeyError(
            f"Unknown archiver '{name}'. "
            f"Supported: {', '.join(sorted({k for k in _REGISTRY if k}))}"
        )
    return _REGISTRY[key]


def detect_archiver(blob: bytes) -> type[Archiver]:
    """Return the archiver whose ``magic`` matches the start of ``blob``.

    Falls back to :class:`RawArchiver` if no signature matches.
    """
    for archiver in (GzipArchiver, XzArchiver, Lz4Archiver, ZstdArchiver):
        if blob.startswith(archiver.magic):
            return archiver
    return RawArchiver


def list_archivers() -> list[str]:
    """Return the list of registered archiver names."""
    return sorted(_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Round-trip a small payload through every available archiver.

    Returns True when every registered archiver decompresses back to
    the original bytes, False otherwise. Used by the build pipeline to
    catch broken optional dependencies before they ruin an image.
    """
    payload = b"UmerOS Initrd selftest " * 64
    payload += bytes(range(256))
    ok = True
    for name in list_archivers():
        try:
            cls = get_archiver(name)
            compressed = cls.compress(payload)
            roundtrip = cls.decompress(compressed)
            if roundtrip != payload:
                log.error("archiver %s roundtrip mismatch", name)
                ok = False
        except RuntimeError as exc:
            # optional dependency missing - fine
            log.debug("archiver %s unavailable: %s", name, exc)
        except Exception as exc:  # pragma: no cover - defensive
            log.error("archiver %s selftest failed: %s", name, exc)
            ok = False
    return ok


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Archivers available:", list_archivers())
    print("Selftest:", "OK" if _selftest() else "FAIL")
