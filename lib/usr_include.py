"""
UmerOS /usr/include — Header File Manager
===========================================
Implements the FHS directory ``/usr/include`` which holds header files
needed for compiling user-space source code.

Per FHS:

  * ``/usr/include`` — top-level headers
  * ``/usr/include/<package>`` — per-package headers (mandatory placement)
  * ``/usr/include/X11`` — symlink → /usr/X11R6/include/X11 (when X11R6
    exists; for user convenience only, not for software)

Each ``/usr/include/<package>`` directory follows the "package name"
convention; large libraries may use a deeper namespace like
``/usr/include/boost/graph/...``.

This module models the catalogue so the package manager / compiler can
discover which headers are present.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

log = logging.getLogger("UmerOS.Lib.UsrInclude")


class HeaderLanguage(str, Enum):
    C        = "c"
    CPP      = "cpp"
    C_HEADER = "c_header"
    OBJECTIVEC = "objc"
    FORTRAN  = "fortran"
    ASSEMBLY = "asm"
    GO       = "go"
    RUST     = "rust"


class HeaderCategory(str, Enum):
    """Why this header lives here."""
    POSIX          = "posix"
    ISO_C          = "iso_c"
    GNU            = "gnu"             # GNU extension
    X11            = "x11"
    QT             = "qt"
    BOOST          = "boost"
    GLIBC_INTERNAL = "glibc_internal"
    LINUX_KERNEL_UAPI = "linux_kernel_uapi"  # /usr/include/linux
    LINUX_GENERIC  = "linux_generic"
    APPLICATION    = "application"     # /usr/include/<package>
    THIRD_PARTY    = "third_party"


@dataclass
class HeaderFile:
    """A single header file."""
    name: str
    package: str                # the /usr/include/<package> directory
    path: str                   # full path
    language: HeaderLanguage = HeaderLanguage.C
    category: HeaderCategory = HeaderCategory.APPLICATION
    size: int = 0
    includes: List[str] = field(default_factory=list)
    defines: List[str] = field(default_factory=list)
    version: str = ""
    description: str = ""
    md5: str = ""


@dataclass
class HeaderPackage:
    """A logical group of headers under /usr/include/<package>."""
    name: str
    package: str
    path: str
    description: str
    category: HeaderCategory = HeaderCategory.APPLICATION
    version: str = ""
    headers: List[HeaderFile] = field(default_factory=list)
    is_x11_symlink: bool = False
    symlink_target: Optional[str] = None


# Stock header packages shipped by a typical Linux distribution
_STOCK_PACKAGES: List[HeaderPackage] = [
    # POSIX / ISO C / GNU — the kernel of the system headers
    HeaderPackage(
        name="stdio.h", package="stdio.h", path="/usr/include/stdio.h",
        description="Standard I/O", category=HeaderCategory.ISO_C,
        version="2.39",
        headers=[HeaderFile(
            "stdio.h", "stdio.h", "/usr/include/stdio.h",
            HeaderLanguage.C, HeaderCategory.ISO_C,
            version="ISO C17", size=24_576,
            includes=["<stddef.h>", "<stdarg.h>"],
            defines=["BUFSIZ", "EOF", "NULL", "FILENAME_MAX"],
        )],
    ),
    HeaderPackage(
        name="stdlib.h", package="stdlib.h", path="/usr/include/stdlib.h",
        description="Standard library", category=HeaderCategory.ISO_C, version="2.39",
        headers=[HeaderFile(
            "stdlib.h", "stdlib.h", "/usr/include/stdlib.h",
            HeaderLanguage.C, HeaderCategory.ISO_C, size=28_672,
        )],
    ),
    HeaderPackage(
        name="string.h", package="string.h", path="/usr/include/string.h",
        description="String handling", category=HeaderCategory.ISO_C, version="2.39",
        headers=[HeaderFile(
            "string.h", "string.h", "/usr/include/string.h",
            HeaderLanguage.C, HeaderCategory.ISO_C, size=16_384,
        )],
    ),
    HeaderPackage(
        name="unistd.h", package="unistd.h", path="/usr/include/unistd.h",
        description="POSIX operating system API", category=HeaderCategory.POSIX, version="2.39",
        headers=[HeaderFile(
            "unistd.h", "unistd.h", "/usr/include/unistd.h",
            HeaderLanguage.C, HeaderCategory.POSIX, size=24_576,
        )],
    ),
    HeaderPackage(
        name="pthread.h", package="pthread.h", path="/usr/include/pthread.h",
        description="POSIX threads", category=HeaderCategory.POSIX, version="2.39",
        headers=[HeaderFile(
            "pthread.h", "pthread.h", "/usr/include/pthread.h",
            HeaderLanguage.C, HeaderCategory.POSIX, size=24_576,
        )],
    ),
    HeaderPackage(
        name="sys/types.h", package="sys/types.h", path="/usr/include/sys/types.h",
        description="System data types", category=HeaderCategory.POSIX, version="2.39",
        headers=[HeaderFile(
            "sys/types.h", "sys", "/usr/include/sys/types.h",
            HeaderLanguage.C, HeaderCategory.POSIX, size=16_384,
        )],
    ),
    HeaderPackage(
        name="sys/socket.h", package="sys/socket.h", path="/usr/include/sys/socket.h",
        description="Berkeley sockets", category=HeaderCategory.POSIX, version="2.39",
        headers=[HeaderFile(
            "sys/socket.h", "sys", "/usr/include/sys/socket.h",
            HeaderLanguage.C, HeaderCategory.POSIX, size=24_576,
        )],
    ),
    HeaderPackage(
        name="netinet/in.h", package="netinet/in.h", path="/usr/include/netinet/in.h",
        description="Internet address family", category=HeaderCategory.POSIX, version="2.39",
        headers=[HeaderFile(
            "netinet/in.h", "netinet", "/usr/include/netinet/in.h",
            HeaderLanguage.C, HeaderCategory.POSIX, size=16_384,
        )],
    ),
    HeaderPackage(
        name="arpa/inet.h", package="arpa/inet.h", path="/usr/include/arpa/inet.h",
        description="Internet operations", category=HeaderCategory.POSIX, version="2.39",
        headers=[HeaderFile(
            "arpa/inet.h", "arpa", "/usr/include/arpa/inet.h",
            HeaderLanguage.C, HeaderCategory.POSIX, size=8_192,
        )],
    ),
    # GNU extensions
    HeaderPackage(
        name="getopt.h", package="getopt.h", path="/usr/include/getopt.h",
        description="GNU getopt", category=HeaderCategory.GNU, version="2.39",
        headers=[HeaderFile(
            "getopt.h", "getopt.h", "/usr/include/getopt.h",
            HeaderLanguage.C, HeaderCategory.GNU, size=4_096,
        )],
    ),
    HeaderPackage(
        name="gnu/stubs.h", package="gnu/stubs.h", path="/usr/include/gnu/stubs.h",
        description="GNU stub library macros", category=HeaderCategory.GLIBC_INTERNAL,
        version="2.39",
        headers=[HeaderFile(
            "gnu/stubs.h", "gnu", "/usr/include/gnu/stubs.h",
            HeaderLanguage.C, HeaderCategory.GLIBC_INTERNAL, size=2_048,
        )],
    ),
    # Linux kernel UAPI (under /usr/include/linux and /usr/include/asm)
    HeaderPackage(
        name="linux/", package="linux", path="/usr/include/linux",
        description="Linux kernel UAPI (uapi)", category=HeaderCategory.LINUX_KERNEL_UAPI,
        version="6.6",
        headers=[
            HeaderFile("linux/ioctl.h", "linux", "/usr/include/linux/ioctl.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=8_192),
            HeaderFile("linux/socket.h", "linux", "/usr/include/linux/socket.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=12_288),
            HeaderFile("linux/if.h", "linux", "/usr/include/linux/if.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=8_192),
            HeaderFile("linux/if_ether.h", "linux", "/usr/include/linux/if_ether.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=8_192),
            HeaderFile("linux/if_packet.h", "linux", "/usr/include/linux/if_packet.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=8_192),
            HeaderFile("linux/in.h", "linux", "/usr/include/linux/in.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=8_192),
            HeaderFile("linux/in6.h", "linux", "/usr/include/linux/in6.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=12_288),
            HeaderFile("linux/virtio_net.h", "linux", "/usr/include/linux/virtio_net.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=8_192),
            HeaderFile("linux/errno.h", "linux", "/usr/include/linux/errno.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=4_096),
            HeaderFile("linux/fcntl.h", "linux", "/usr/include/linux/fcntl.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=4_096),
            HeaderFile("linux/fs.h", "linux", "/usr/include/linux/fs.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=8_192),
            HeaderFile("linux/stat.h", "linux", "/usr/include/linux/stat.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=8_192),
            HeaderFile("linux/poll.h", "linux", "/usr/include/linux/poll.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=4_096),
            HeaderFile("linux/eventpoll.h", "linux", "/usr/include/linux/eventpoll.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=4_096),
            HeaderFile("linux/mman.h", "linux", "/usr/include/linux/mman.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=4_096),
            HeaderFile("linux/signal.h", "linux", "/usr/include/linux/signal.h",
                HeaderLanguage.C, HeaderCategory.LINUX_KERNEL_UAPI, size=4_096),
        ],
    ),
    HeaderPackage(
        name="asm-generic/", package="asm-generic", path="/usr/include/asm-generic",
        description="Generic asm UAPI", category=HeaderCategory.LINUX_GENERIC,
        version="6.6",
        headers=[
            HeaderFile("asm-generic/ioctl.h", "asm-generic", "/usr/include/asm-generic/ioctl.h",
                HeaderLanguage.C, HeaderCategory.LINUX_GENERIC, size=2_048),
            HeaderFile("asm-generic/errno.h", "asm-generic", "/usr/include/asm-generic/errno.h",
                HeaderLanguage.C, HeaderCategory.LINUX_GENERIC, size=2_048),
            HeaderFile("asm-generic/int-ll64.h", "asm-generic", "/usr/include/asm-generic/int-ll64.h",
                HeaderLanguage.C, HeaderCategory.LINUX_GENERIC, size=2_048),
            HeaderFile("asm-generic/siginfo.h", "asm-generic", "/usr/include/asm-generic/siginfo.h",
                HeaderLanguage.C, HeaderCategory.LINUX_GENERIC, size=4_096),
        ],
    ),
    # X11 — symlink to /usr/X11R6/include/X11 per FHS
    HeaderPackage(
        name="X11/", package="X11", path="/usr/include/X11",
        description="X11 (symlink to /usr/X11R6/include/X11 per FHS)",
        category=HeaderCategory.X11, version="X11R7.9",
        is_x11_symlink=True, symlink_target="/usr/X11R6/include/X11",
        headers=[
            HeaderFile("X11/Xlib.h", "X11", "/usr/include/X11/Xlib.h",
                HeaderLanguage.C, HeaderCategory.X11, size=49_152),
            HeaderFile("X11/Xutil.h", "X11", "/usr/include/X11/Xutil.h",
                HeaderLanguage.C, HeaderCategory.X11, size=24_576),
            HeaderFile("X11/Xatom.h", "X11", "/usr/include/X11/Xatom.h",
                HeaderLanguage.C, HeaderCategory.X11, size=16_384),
            HeaderFile("X11/X.h", "X11", "/usr/include/X11/X.h",
                HeaderLanguage.C, HeaderCategory.X11, size=12_288),
            HeaderFile("X11/XKBlib.h", "X11", "/usr/include/X11/XKBlib.h",
                HeaderLanguage.C, HeaderCategory.X11, size=16_384),
            HeaderFile("X11/extensions/XInput.h", "X11", "/usr/include/X11/extensions/XInput.h",
                HeaderLanguage.C, HeaderCategory.X11, size=12_288),
        ],
    ),
    # Third-party libraries
    HeaderPackage(
        name="openssl/", package="openssl", path="/usr/include/openssl",
        description="OpenSSL (libssl/libcrypto)", category=HeaderCategory.THIRD_PARTY,
        version="3.3",
        headers=[
            HeaderFile("openssl/ssl.h", "openssl", "/usr/include/openssl/ssl.h",
                HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=180_224),
            HeaderFile("openssl/crypto.h", "openssl", "/usr/include/openssl/crypto.h",
                HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=327_680),
            HeaderFile("openssl/evp.h", "openssl", "/usr/include/openssl/evp.h",
                HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=49_152),
            HeaderFile("openssl/x509.h", "openssl", "/usr/include/openssl/x509.h",
                HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=81_920),
            HeaderFile("openssl/rsa.h", "openssl", "/usr/include/openssl/rsa.h",
                HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=24_576),
            HeaderFile("openssl/ec.h", "openssl", "/usr/include/openssl/ec.h",
                HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=49_152),
            HeaderFile("openssl/sha.h", "openssl", "/usr/include/openssl/sha.h",
                HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=8_192),
            HeaderFile("openssl/bn.h", "openssl", "/usr/include/openssl/bn.h",
                HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=49_152),
        ],
    ),
    HeaderPackage(
        name="zlib.h", package="zlib.h", path="/usr/include/zlib.h",
        description="zlib compression", category=HeaderCategory.THIRD_PARTY, version="1.3",
        headers=[HeaderFile(
            "zlib.h", "zlib.h", "/usr/include/zlib.h",
            HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=98_304,
        )],
    ),
    HeaderPackage(
        name="curl/", package="curl", path="/usr/include/curl",
        description="libcurl", category=HeaderCategory.THIRD_PARTY, version="8.7",
        headers=[
            HeaderFile("curl/curl.h", "curl", "/usr/include/curl/curl.h",
                HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=212_992),
            HeaderFile("curl/easy.h", "curl", "/usr/include/curl/easy.h",
                HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=16_384),
            HeaderFile("curl/multi.h", "curl", "/usr/include/curl/multi.h",
                HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=12_288),
        ],
    ),
    HeaderPackage(
        name="sqlite3.h", package="sqlite3.h", path="/usr/include/sqlite3.h",
        description="SQLite embedded database", category=HeaderCategory.THIRD_PARTY, version="3.46",
        headers=[HeaderFile(
            "sqlite3.h", "sqlite3.h", "/usr/include/sqlite3.h",
            HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=2_457_600,
        )],
    ),
    HeaderPackage(
        name="python3.12/", package="python3.12", path="/usr/include/python3.12",
        description="CPython 3.12", category=HeaderCategory.THIRD_PARTY, version="3.12",
        headers=[HeaderFile(
            "python3.12/Python.h", "python3.12", "/usr/include/python3.12/Python.h",
            HeaderLanguage.C, HeaderCategory.THIRD_PARTY, size=98_304,
        )],
    ),
    HeaderPackage(
        name="Qt6/", package="Qt6", path="/usr/include/x86_64-linux-gnu/qt6",
        description="Qt6", category=HeaderCategory.QT, version="6.7",
        headers=[
            HeaderFile("Qt6/QtCore/qglobal.h", "Qt6", "/usr/include/x86_64-linux-gnu/qt6/QtCore/qglobal.h",
                HeaderLanguage.CPP, HeaderCategory.QT, size=49_152),
            HeaderFile("Qt6/QtGui/qguiapplication.h", "Qt6", "/usr/include/x86_64-linux-gnu/qt6/QtGui/qguiapplication.h",
                HeaderLanguage.CPP, HeaderCategory.QT, size=8_192),
            HeaderFile("Qt6/QtWidgets/QApplication", "Qt6", "/usr/include/x86_64-linux-gnu/qt6/QtWidgets/QApplication",
                HeaderLanguage.CPP, HeaderCategory.QT, size=2_048),
        ],
    ),
    HeaderPackage(
        name="boost/", package="boost", path="/usr/include/boost",
        description="Boost C++ libraries", category=HeaderCategory.BOOST, version="1.84",
        headers=[
            HeaderFile("boost/any.hpp", "boost", "/usr/include/boost/any.hpp",
                HeaderLanguage.CPP, HeaderCategory.BOOST, size=4_096),
            HeaderFile("boost/variant.hpp", "boost", "/usr/include/boost/variant.hpp",
                HeaderLanguage.CPP, HeaderCategory.BOOST, size=8_192),
            HeaderFile("boost/filesystem.hpp", "boost", "/usr/include/boost/filesystem.hpp",
                HeaderLanguage.CPP, HeaderCategory.BOOST, size=12_288),
            HeaderFile("boost/asio.hpp", "boost", "/usr/include/boost/asio.hpp",
                HeaderLanguage.CPP, HeaderCategory.BOOST, size=8_192),
        ],
    ),
]


class UsrIncludeManager:
    """
    Manages the ``/usr/include`` header-file tree.
    """

    def __init__(self, usr_path: str = "/usr") -> None:
        self.usr_path = Path(usr_path)
        self.include_path = self.usr_path / "include"
        self._packages: Dict[str, HeaderPackage] = {
            p.name: p for p in _STOCK_PACKAGES
        }
        self._all_headers: Dict[str, HeaderFile] = {}
        for p in self._packages.values():
            for h in p.headers:
                self._all_headers[h.path] = h

    # ── package-level ─────────────────────────────────────────────

    def list_packages(self) -> List[HeaderPackage]:
        return list(self._packages.values())

    def get_package(self, name: str) -> Optional[HeaderPackage]:
        return self._packages.get(name)

    def by_category(self, category: HeaderCategory) -> List[HeaderPackage]:
        return [p for p in self._packages.values() if p.category == category]

    def register_package(self, package: HeaderPackage) -> None:
        self._packages[package.name] = package
        for h in package.headers:
            self._all_headers[h.path] = h

    # ── header-level ──────────────────────────────────────────────

    def find_header(self, name_or_path: str) -> Optional[HeaderFile]:
        # Direct path
        if name_or_path in self._all_headers:
            return self._all_headers[name_or_path]
        # Try basename match
        for h in self._all_headers.values():
            if h.name == name_or_path or Path(h.path).name == name_or_path:
                return h
        return None

    def list_headers(self) -> List[HeaderFile]:
        return list(self._all_headers.values())

    def find_includes(self, header_name: str) -> List[str]:
        h = self.find_header(header_name)
        return list(h.includes) if h else []

    # ── X11 symlink rule ──────────────────────────────────────────

    def x11_package(self) -> Optional[HeaderPackage]:
        return self._packages.get("X11/")

    def ensure_x11_symlink(self) -> Path:
        """Enforce the FHS rule: /usr/include/X11 → /usr/X11R6/include/X11."""
        x11 = self.include_path / "X11"
        target = self.usr_path.parent / "X11R6" / "include" / "X11"
        if x11.exists() and not x11.is_symlink():
            try:
                x11.unlink()
            except IsADirectoryError:
                pass
        x11.parent.mkdir(parents=True, exist_ok=True)
        try:
            x11.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError) as e:
            log.warning("X11 symlink: %s", e)
        return x11

    # ── summary ──────────────────────────────────────────────────

    def get_summary(self) -> Dict:
        packages = list(self._packages.values())
        headers  = list(self._all_headers.values())
        return {
            "total_packages": len(packages),
            "total_headers": len(headers),
            "by_category": {
                c.value: len(self.by_category(c)) for c in HeaderCategory
            },
            "x11_is_symlink": (
                self.x11_package() is not None and self.x11_package().is_x11_symlink
            ),
            "total_size_bytes": sum(h.size for h in headers),
            "directory": str(self.include_path),
        }


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = UsrIncludeManager(usr_path=tmpdir)
        summary = mgr.get_summary()
        assert "total_headers" in summary, "summary should have total_headers"

    print("selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
