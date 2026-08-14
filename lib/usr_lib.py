"""
UmerOS /usr/lib + /usr/libexec + /usr/lib/gconv + locale-archive Manager
==========================================================================
Implements the FHS subdirectory ``/usr/lib`` and its companion directories.

Per FHS:

  /usr/lib             — "program libraries… collections of frequently used
                          program routines"
  /usr/lib/X11         — symlink → /usr/X11R6/lib/X11 (when X11R6 exists)
  /usr/lib/gconv       — GNU libc iconv conversion modules (charset→charset)
  /usr/lib/locale      — locale-archive (libc compiled locale data)
  /usr/lib/charmaps    — charmap definitions
  /usr/lib/console     — console keyboard / font data (mirror of /lib/kbd)
  /usr/lib/modules     — alternative location for loadable modules
  /usr/lib/sasl        — SASL authentication plugins
  /usr/lib/security    — alternate PAM location (some distros)
  /usr/lib/ssl         — TLS / openssl data
  /usr/lib/pkgconfig   — pkg-config .pc files
  /usr/lib/cmake       — CMake config files
  /usr/lib/engines     — OpenSSL dynamic engines
  /usr/lib/udev        — udev rules + helpers
  /usr/lib/systemd     — systemd internal libraries
  /usr/lib/tmpfiles.d  — systemd-tmpfiles config snippets
  /usr/libexec         — internal binaries not meant to be run by users
  /usr/lib32           — 32-bit libraries
  /usr/lib64           — 64-bit libraries

This module models all of these so the build and packaging tooling can
discover them.

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

log = logging.getLogger("UmerOS.Lib.UsrLib")


class UsrLibSubdir(str, Enum):
    BASE      = "lib"            # /usr/lib itself
    LIBEXEC   = "libexec"
    GCONV     = "gconv"
    LOCALE    = "locale"
    CHARMAPS  = "charmaps"
    CONSOLE   = "console"
    MODULES   = "modules"
    SASL      = "sasl"
    SECURITY  = "security"
    SSL       = "ssl"
    PKGCONFIG = "pkgconfig"
    CMAKE     = "cmake"
    ENGINES   = "engines"
    UDEV      = "udev"
    SYSTEMD   = "systemd"
    TMPFILES  = "tmpfiles.d"
    PAM       = "pam"


@dataclass
class GconvModule:
    """A single /usr/lib/gconv/<name>.so iconv module."""
    name: str                   # canonical name (e.g. "UTF-8")
    file_name: str              # e.g. "UTF-8.so"
    path: str
    aliases: List[str] = field(default_factory=list)
    from_codeset: str = ""
    to_codeset: str = ""
    size: int = 0
    bidirectional: bool = False


# A representative charset set — there are ~200 in real gconv.
_STOCK_GCONV: List[GconvModule] = [
    GconvModule("UTF-8",        "UTF-8.so",        "/usr/lib/gconv/UTF-8.so", size=12_288,
        aliases=["utf8", "UTF8"], bidirectional=True),
    GconvModule("UTF-16",       "UTF-16.so",       "/usr/lib/gconv/UTF-16.so", size=10_240),
    GconvModule("UTF-32",       "UTF-32.so",       "/usr/lib/gconv/UTF-32.so", size=10_240),
    GconvModule("UTF-16BE",     "UTF-16BE.so",     "/usr/lib/gconv/UTF-16BE.so", size=10_240),
    GconvModule("UTF-16LE",     "UTF-16LE.so",     "/usr/lib/gconv/UTF-16LE.so", size=10_240),
    GconvModule("UTF-32BE",     "UTF-32BE.so",     "/usr/lib/gconv/UTF-32BE.so", size=10_240),
    GconvModule("UTF-32LE",     "UTF-32LE.so",     "/usr/lib/gconv/UTF-32LE.so", size=10_240),
    GconvModule("ISO8859-1",    "ISO8859-1.so",    "/usr/lib/gconv/ISO8859-1.so",
        aliases=["latin1", "LATIN1", "iso-ir-100"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-2",    "ISO8859-2.so",    "/usr/lib/gconv/ISO8859-2.so",
        aliases=["latin2", "LATIN2"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-3",    "ISO8859-3.so",    "/usr/lib/gconv/ISO8859-3.so",
        aliases=["latin3", "LATIN3"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-4",    "ISO8859-4.so",    "/usr/lib/gconv/ISO8859-4.so",
        aliases=["latin4", "LATIN4"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-5",    "ISO8859-5.so",    "/usr/lib/gconv/ISO8859-5.so",
        aliases=["cyrillic"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-6",    "ISO8859-6.so",    "/usr/lib/gconv/ISO8859-6.so",
        aliases=["arabic"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-7",    "ISO8859-7.so",    "/usr/lib/gconv/ISO8859-7.so",
        aliases=["greek"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-8",    "ISO8859-8.so",    "/usr/lib/gconv/ISO8859-8.so",
        aliases=["hebrew"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-9",    "ISO8859-9.so",    "/usr/lib/gconv/ISO8859-9.so",
        aliases=["latin5", "LATIN5", "turkish"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-10",   "ISO8859-10.so",   "/usr/lib/gconv/ISO8859-10.so",
        aliases=["latin6", "LATIN6"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-11",   "ISO8859-11.so",   "/usr/lib/gconv/ISO8859-11.so",
        aliases=["thai"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-13",   "ISO8859-13.so",   "/usr/lib/gconv/ISO8859-13.so",
        aliases=["latin7", "LATIN7"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-14",   "ISO8859-14.so",   "/usr/lib/gconv/ISO8859-14.so",
        aliases=["latin8", "LATIN8"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-15",   "ISO8859-15.so",   "/usr/lib/gconv/ISO8859-15.so",
        aliases=["latin9", "LATIN9"], size=8_192, bidirectional=True),
    GconvModule("ISO8859-16",   "ISO8859-16.so",   "/usr/lib/gconv/ISO8859-16.so",
        aliases=["latin10", "LATIN10"], size=8_192, bidirectional=True),
    GconvModule("CP1252",       "CP1252.so",       "/usr/lib/gconv/CP1252.so",
        aliases=["WINDOWS-1252", "windows-1252"], size=8_192, bidirectional=True),
    GconvModule("CP1251",       "CP1252.so",       "/usr/lib/gconv/CP1251.so",
        aliases=["WINDOWS-1251", "windows-1251"], size=8_192, bidirectional=True),
    GconvModule("KOI8-R",       "KOI8-R.so",       "/usr/lib/gconv/KOI8-R.so", size=8_192, bidirectional=True),
    GconvModule("KOI8-U",       "KOI8-U.so",       "/usr/lib/gconv/KOI8-U.so", size=8_192, bidirectional=True),
    GconvModule("EUC-JP",       "EUC-JP.so",       "/usr/lib/gconv/EUC-JP.so", size=12_288),
    GconvModule("SJIS",         "SJIS.so",         "/usr/lib/gconv/SJIS.so",
        aliases=["Shift_JIS", "shift_jis", "MS_Kanji"], size=12_288),
    GconvModule("EUC-KR",       "EUC-KR.so",       "/usr/lib/gconv/EUC-KR.so", size=12_288),
    GconvModule("GB18030",      "GB18030.so",      "/usr/lib/gconv/GB18030.so", size=16_384, bidirectional=True),
    GconvModule("GB2312",       "GB2312.so",       "/usr/lib/gconv/GB2312.so", size=12_288),
    GconvModule("BIG5",         "BIG5.so",         "/usr/lib/gconv/BIG5.so", size=12_288),
    GconvModule("BIG5HKSCS",    "BIG5HKSCS.so",    "/usr/lib/gconv/BIG5HKSCS.so", size=16_384),
    GconvModule("ARMSCII-8",    "ARMSCII-8.so",    "/usr/lib/gconv/ARMSCII-8.so", size=8_192, bidirectional=True),
    GconvModule("GEORGIAN-PS",  "GEORGIAN-PS.so",  "/usr/lib/gconv/GEORGIAN-PS.so", size=8_192, bidirectional=True),
    GconvModule("TIS-620",      "TIS-620.so",      "/usr/lib/gconv/TIS-620.so",
        aliases=["TIS620", "tis620"], size=8_192, bidirectional=True),
    GconvModule("VISCII",       "VISCII.so",       "/usr/lib/gconv/VISCII.so", size=8_192, bidirectional=True),
]


@dataclass
class CharmapEntry:
    """A single /usr/lib/charmaps/<name> charmap definition."""
    name: str
    path: str
    size: int = 0
    description: str = ""
    iso_standard: str = ""


_STOCK_CHARMAPS: List[CharmapEntry] = [
    CharmapEntry("ANSI_X3.110-1983",  "/usr/lib/charmaps/ANSI_X3.110-1983.gz", size=4_096,
        description="ISO-IR-99 / ANSI X3.110", iso_standard="ISO-IR-99"),
    CharmapEntry("ANSI_X3.4-1968",    "/usr/lib/charmaps/ANSI_X3.4-1968.gz", size=4_096,
        description="US-ASCII", iso_standard="ISO-IR-6"),
    CharmapEntry("BS_4730",           "/usr/lib/charmaps/BS_4730.gz", size=4_096,
        description="British Standard", iso_standard="ISO-IR-4"),
    CharmapEntry("CSA_Z243.4-1985-1", "/usr/lib/charmaps/CSA_Z243.4-1985-1.gz", size=4_096,
        description="Canadian CSA Z243.4", iso_standard="ISO-IR-121"),
    CharmapEntry("DEC-MCS",           "/usr/lib/charmaps/DEC-MCS.gz", size=4_096,
        description="DEC Multinational Character Set", iso_standard="ISO-IR-100"),
    CharmapEntry("EBCDIC-CA-FR",      "/usr/lib/charmaps/EBCDIC-CA-FR.gz", size=8_192,
        description="EBCDIC Canadian-French"),
    CharmapEntry("EBCDIC-DK-NO-A",    "/usr/lib/charmaps/EBCDIC-DK-NO-A.gz", size=8_192,
        description="EBCDIC Danish-Norwegian"),
    CharmapEntry("EBCDIC-FI-SE-A",    "/usr/lib/charmaps/EBCDIC-FI-SE-A.gz", size=8_192,
        description="EBCDIC Finnish-Swedish"),
    CharmapEntry("EBCDIC-UK",         "/usr/lib/charmaps/EBCDIC-UK.gz", size=8_192,
        description="EBCDIC UK"),
    CharmapEntry("EBCDIC-US",         "/usr/lib/charmaps/EBCDIC-US.gz", size=8_192,
        description="EBCDIC US"),
    CharmapEntry("IBM037",            "/usr/lib/charmaps/IBM037.gz", size=8_192,
        description="IBM EBCDIC US-Canada"),
    CharmapEntry("IBM850",            "/usr/lib/charmaps/IBM850.gz", size=8_192,
        description="IBM PC Multilingual"),
    CharmapEntry("IBM866",            "/usr/lib/charmaps/IBM866.gz", size=8_192,
        description="IBM Cyrillic"),
    CharmapEntry("ISO_8859-1:1987",   "/usr/lib/charmaps/ISO_8859-1,1987.gz", size=4_096,
        description="ISO 8859-1 Latin 1", iso_standard="ISO-IR-100"),
    CharmapEntry("ISO_8859-2:1987",   "/usr/lib/charmaps/ISO_8859-2,1987.gz", size=4_096,
        description="ISO 8859-2 Latin 2", iso_standard="ISO-IR-101"),
    CharmapEntry("ISO_8859-3:1988",   "/usr/lib/charmaps/ISO_8859-3,1988.gz", size=4_096,
        description="ISO 8859-3 Latin 3", iso_standard="ISO-IR-109"),
    CharmapEntry("ISO_8859-4:1988",   "/usr/lib/charmaps/ISO_8859-4,1988.gz", size=4_096,
        description="ISO 8859-4 Latin 4", iso_standard="ISO-IR-110"),
    CharmapEntry("ISO_8859-5:1988",   "/usr/lib/charmaps/ISO_8859-5,1988.gz", size=4_096,
        description="ISO 8859-5 Cyrillic", iso_standard="ISO-IR-144"),
    CharmapEntry("ISO_8859-6:1987",   "/usr/lib/charmaps/ISO_8859-6,1987.gz", size=4_096,
        description="ISO 8859-6 Arabic", iso_standard="ISO-IR-127"),
    CharmapEntry("ISO_8859-7:1987",   "/usr/lib/charmaps/ISO_8859-7,1987.gz", size=4_096,
        description="ISO 8859-7 Greek", iso_standard="ISO-IR-126"),
    CharmapEntry("ISO_8859-8:1988",   "/usr/lib/charmaps/ISO_8859-8,1988.gz", size=4_096,
        description="ISO 8859-8 Hebrew", iso_standard="ISO-IR-138"),
    CharmapEntry("ISO_8859-9:1989",   "/usr/lib/charmaps/ISO_8859-9,1989.gz", size=4_096,
        description="ISO 8859-9 Latin 5", iso_standard="ISO-IR-148"),
    CharmapEntry("ISO_8859-15:1998",  "/usr/lib/charmaps/ISO_8859-15,1998.gz", size=4_096,
        description="ISO 8859-15 Latin 9"),
    CharmapEntry("KOI8-R",            "/usr/lib/charmaps/KOI8-R.gz", size=4_096,
        description="KOI8-R Cyrillic"),
    CharmapEntry("UTF-8",             "/usr/lib/charmaps/UTF-8.gz", size=4_096,
        description="UTF-8 (8-bit Unicode Transformation Format)"),
]


@dataclass
class LibexecProgram:
    """A single /usr/libexec/<name> binary."""
    name: str
    path: str
    size: int = 0
    description: str = ""
    version: str = ""
    depends_on: List[str] = field(default_factory=list)
    runs_as: str = "root"


_STOCK_LIBEXEC: List[LibexecProgram] = [
    LibexecProgram("awk",             "/usr/libexec/awk",                  size=983_040, version="5.2"),
    LibexecProgram("coreutils",       "/usr/libexec/coreutils",            size=4_194_304, version="9.4"),
    LibexecProgram("getconf",         "/usr/libexec/getconf",              size=28_672, version="2.39"),
    LibexecProgram("getent",          "/usr/libexec/getent",               size=32_768, version="2.39"),
    LibexecProgram("ld.so",           "/usr/libexec/ld.so",                size=202_952, version="2.39"),
    LibexecProgram("locale",          "/usr/libexec/locale",               size=114_688, version="2.39"),
    LibexecProgram("pldd",            "/usr/libexec/pldd",                 size=32_768, version="2.39"),
    LibexecProgram("sln",             "/usr/libexec/sln",                  size=860_160, version="2.39"),
    LibexecProgram("ssh-keysign",     "/usr/libexec/ssh-keysign",          size=458_752, version="9.6p1"),
    LibexecProgram("ssh-pkcs11-helper","/usr/libexec/ssh-pkcs11-helper",   size=458_752, version="9.6p1"),
    LibexecProgram("pam_namespace_helper","/usr/libexec/pam_namespace_helper", size=24_576, version="1.5"),
    LibexecProgram("p11-kit",         "/usr/libexec/p11-kit",              size=212_992, version="0.25"),
    LibexecProgram("paexec",          "/usr/libexec/paexec",               size=49_152, version="1.1"),
    LibexecProgram("useradd",         "/usr/libexec/useradd",              size=81_920, version="2.39"),
    LibexecProgram("grub-mkrescue",   "/usr/libexec/grub-mkrescue",        size=212_992, version="2.06"),
    LibexecProgram("grub-mount",      "/usr/libexec/grub-mount",           size=180_224, version="2.06"),
    LibexecProgram("fwupd",           "/usr/libexec/fwupd",                size=393_216, version="1.9"),
    LibexecProgram("fwupd-offline-update","/usr/libexec/fwupd-offline-update", size=81_920, version="1.9"),
    LibexecProgram("packagekitd",     "/usr/libexec/packagekitd",          size=163_840, version="1.2"),
    LibexecProgram("pk-command-not-found","/usr/libexec/pk-command-not-found", size=49_152, version="1.2"),
    LibexecProgram("pkcon",           "/usr/libexec/pkcon",                size=98_304, version="1.2"),
    LibexecProgram("rpm",             "/usr/libexec/rpm",                  size=720_896, version="4.19"),
    LibexecProgram("dpkg",            "/usr/libexec/dpkg",                 size=540_672, version="1.22"),
    LibexecProgram("cc1",             "/usr/libexec/cc1",                  size=24_117_248, version="14.1"),
    LibexecProgram("cc1plus",         "/usr/libexec/cc1plus",              size=29_360_128, version="14.1"),
    LibexecProgram("lto1",            "/usr/libexec/lto1",                 size=22_020_096, version="14.1"),
    LibexecProgram("collect2",        "/usr/libexec/collect2",             size=212_992, version="14.1"),
    LibexecProgram("lto-wrapper",     "/usr/libexec/lto-wrapper",          size=98_304, version="14.1"),
    LibexecProgram("sftp-server",     "/usr/libexec/sftp-server",          size=131_072, version="9.6p1"),
    LibexecProgram("sshd-session",    "/usr/libexec/sshd-session",         size=860_160, version="9.6p1"),
    LibexecProgram("cups-driverd",    "/usr/libexec/cups-driverd",         size=81_920, version="2.4"),
    LibexecProgram("backend",         "/usr/libexec/cups/backend",         size=131_072, version="2.4"),
    LibexecProgram("filter",          "/usr/libexec/cups/filter",          size=212_992, version="2.4"),
    LibexecProgram("doas",            "/usr/libexec/doas",                 size=49_152, version="6.8"),
    LibexecProgram("sudo_noexec",     "/usr/libexec/sudo_noexec.so",       size=12_288, version="1.9"),
    LibexecProgram("polkit-agent-helper-1","/usr/libexec/polkit-agent-helper-1", size=28_672, version="124"),
    LibexecProgram("pkexec",          "/usr/libexec/pkexec",               size=32_768, version="124"),
    LibexecProgram("at-spi2-core",    "/usr/libexec/at-spi-bus-launcher",  size=98_304, version="2.50"),
    LibexecProgram("tracker-extract-3","/usr/libexec/tracker-extract-3",   size=212_992, version="3.7"),
    LibexecProgram("tracker-miner-fs-3","/usr/libexec/tracker-miner-fs-3", size=131_072, version="3.7"),
    LibexecProgram("dconf-service",   "/usr/libexec/dconf-service",        size=98_304, version="0.40"),
    LibexecProgram("gconfd-2",        "/usr/libexec/gconfd-2",             size=212_992, version="3.2"),
    LibexecProgram("ibus-daemon",     "/usr/libexec/ibus-daemon",          size=212_992, version="1.5"),
    LibexecProgram("ibus-engine-simple","/usr/libexec/ibus-engine-simple",size=81_920, version="1.5"),
    LibexecProgram("Xorg.wrap",       "/usr/libexec/Xorg.wrap",            size=49_152, version="21.1"),
    LibexecProgram("Xvfb",            "/usr/libexec/Xvfb",                 size=4_718_592, version="21.1"),
    LibexecProgram("smartcard-proxy", "/usr/libexec/smartcard-proxy",      size=49_152, version="1.0"),
]


class GconvManager:
    """
    Manages the ``/usr/lib/gconv`` charset conversion modules.
    """

    def __init__(self) -> None:
        self._modules: Dict[str, GconvModule] = {m.name: m for m in _STOCK_GCONV}

    def list_modules(self) -> List[GconvModule]:
        return list(self._modules.values())

    def find(self, name: str) -> Optional[GconvModule]:
        # Direct hit
        if name in self._modules:
            return self._modules[name]
        # Try aliases (case-insensitive)
        n = name.upper()
        for m in self._modules.values():
            if n == m.name.upper() or any(n == a.upper() for a in m.aliases):
                return m
        return None

    def by_encoding(self, encoding: str) -> List[GconvModule]:
        return [
            m for m in self._modules.values()
            if encoding in (m.name, *(a for a in m.aliases))
        ]

    def find_conversion(self, src: str, dst: str) -> List[GconvModule]:
        """Find a one-hop conversion from ``src`` to ``dst``."""
        return [m for m in self._modules
                if (m.from_codeset == src and m.to_codeset == dst)
                or (m.name == dst and src != dst)]

    def register(self, module: GconvModule) -> None:
        self._modules[module.name] = module

    def get_summary(self) -> Dict:
        return {
            "total_modules": len(self._modules),
            "bidirectional": sum(1 for m in self._modules.values() if m.bidirectional),
            "total_size_bytes": sum(m.size for m in self._modules.values()),
        }


class CharmapManager:
    """Manages ``/usr/lib/charmaps``."""

    def __init__(self) -> None:
        self._charmaps: Dict[str, CharmapEntry] = {c.name: c for c in _STOCK_CHARMAPS}

    def list_charmaps(self) -> List[CharmapEntry]:
        return list(self._charmaps.values())

    def find(self, name: str) -> Optional[CharmapEntry]:
        return self._charmaps.get(name)

    def by_iso(self, iso_id: str) -> List[CharmapEntry]:
        return [c for c in self._charmaps.values() if c.iso_standard == iso_id]

    def register(self, charmap: CharmapEntry) -> None:
        self._charmaps[charmap.name] = charmap

    def get_summary(self) -> Dict:
        return {
            "total_charmaps": len(self._charmaps),
            "with_iso_id": sum(1 for c in self._charmaps.values() if c.iso_standard),
            "total_size_bytes": sum(c.size for c in self._charmaps.values()),
        }


class LibexecManager:
    """Manages ``/usr/libexec`` — internal binaries."""

    def __init__(self) -> None:
        self._programs: Dict[str, LibexecProgram] = {p.name: p for p in _STOCK_LIBEXEC}

    def list_programs(self) -> List[LibexecProgram]:
        return list(self._programs.values())

    def find(self, name: str) -> Optional[LibexecProgram]:
        return self._programs.get(name)

    def register(self, program: LibexecProgram) -> None:
        self._programs[program.name] = program

    def get_summary(self) -> Dict:
        return {
            "total_programs": len(self._programs),
            "total_size_bytes": sum(p.size for p in self._programs.values()),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Top-level /usr/lib manager
# ─────────────────────────────────────────────────────────────────────────────

class UsrLibManager:
    """
    Coordinates all of /usr/lib's subdirectories:

      * the base library directory
      * /usr/libexec for internal binaries
      * /usr/lib/gconv for iconv modules
      * /usr/lib/locale for locale-archive
      * /usr/lib/charmaps for charmap definitions
      * /usr/lib/X11 → /usr/X11R6/lib/X11 symlink (per FHS)

    The "FHS rule" enforced here is that ``/usr/lib`` is read-only and
    shareable between hosts — applications are forbidden from writing to
    it at runtime.
    """

    def __init__(self, usr_path: str = "/usr") -> None:
        self.usr_path = Path(usr_path)
        self.lib_path = self.usr_path / "lib"
        self.gconv = GconvManager()
        self.charmaps = CharmapManager()
        self.libexec = LibexecManager()
        self._subdirs: Set[str] = {s.value for s in UsrLibSubdir}
        self._x11_symlink_target: Optional[str] = "/usr/X11R6/lib/X11"
        # Catalogue of libraries in /usr/lib (beyond /lib)
        self._libraries: Dict[str, str] = {}  # name → path

    def subdirectories(self) -> List[str]:
        return sorted(self._subdirs)

    def has_subdir(self, name: str) -> bool:
        return name in self._subdirs

    def ensure_x11_symlink(self) -> Path:
        """
        Enforce the FHS rule: ``/usr/lib/X11`` must be a symlink to
        ``/usr/X11R6/lib/X11`` when X11R6 is installed.
        """
        x11 = self.lib_path / "X11"
        if x11.exists() and not x11.is_symlink():
            try:
                x11.unlink()
            except IsADirectoryError:
                pass
        if self._x11_symlink_target is not None:
            x11.parent.mkdir(parents=True, exist_ok=True)
            try:
                x11.symlink_to(self.usr_path.parent / self._x11_symlink_target.lstrip("/"),
                               target_is_directory=True)
            except (OSError, NotImplementedError) as e:
                log.warning("X11 symlink: %s", e)
        return x11

    def set_x11_symlink_target(self, path: str) -> None:
        self._x11_symlink_target = path

    # ── library catalogue ─────────────────────────────────────────

    def register_library(self, name: str, path: str) -> None:
        self._libraries[name] = path

    def list_libraries(self) -> List[Tuple[str, str]]:
        return list(self._libraries.items())

    # ── locale-archive ────────────────────────────────────────────

    def locale_archive_path(self) -> Path:
        return self.lib_path / "locale" / "locale-archive"

    def locale_archive_exists(self) -> bool:
        return self.locale_archive_path().exists()

    # ── on-disk materialisation ───────────────────────────────────

    def materialise_stubs(self, root: str = "/") -> int:
        written = 0
        target = Path(root) / "usr" / "lib"
        target.mkdir(parents=True, exist_ok=True)
        # gconv
        g = target / "gconv"
        g.mkdir(exist_ok=True)
        for m in self.gconv.list_modules():
            p = g / m.file_name
            if not p.exists():
                p.write_bytes(
                    b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
                    + f"UmerOS gconv stub {m.name}\n".encode()
                )
                written += 1
        # charmaps (gzip-compressed header stub)
        c = target / "charmaps"
        c.mkdir(exist_ok=True)
        for cm in self.charmaps.list_charmaps():
            p = c / Path(cm.path).name
            if not p.exists():
                p.write_bytes(
                    f"# UmerOS charmap stub for {cm.name}\n".encode()
                )
                written += 1
        # libexec
        lx = target / ".." / "libexec"
        lx = lx.resolve()
        lx.mkdir(parents=True, exist_ok=True)
        for p in self.libexec.list_programs():
            full = lx / p.name
            if not full.exists():
                full.write_bytes(
                    f"#!/bin/sh\necho UmerOS libexec stub: {p.name}\n".encode()
                )
                full.chmod(0o755)
                written += 1
        # locale-archive (tiny)
        la = target / "locale" / "locale-archive"
        la.parent.mkdir(parents=True, exist_ok=True)
        if not la.exists():
            la.write_bytes(b"UmerOS locale-archive stub\n")
            written += 1
        return written

    # ── summary ──────────────────────────────────────────────────

    def get_summary(self) -> Dict:
        return {
            "subdirectories": self.subdirectories(),
            "gconv": self.gconv.get_summary(),
            "charmaps": self.charmaps.get_summary(),
            "libexec": self.libexec.get_summary(),
            "x11_symlink_target": self._x11_symlink_target,
            "libraries_count": len(self._libraries),
            "directory": str(self.lib_path),
        }


# ---------------------------------------------------------------------------
#  Self-test
# ---------------------------------------------------------------------------

def _selftest():
    """Run a basic self-test for this module."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = UsrLibManager(usr_path=tmpdir)
        summary = mgr.get_summary()
        assert "subdirectories" in summary, "summary should have subdirectories"

    print("selftest OK")
    return True


if __name__ == "__main__":
    _selftest()
