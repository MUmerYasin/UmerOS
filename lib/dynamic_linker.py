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
UmerOS Dynamic Linker / Loader Support (/lib + /etc/ld.so.conf + ldconfig)
=============================================================================
Implements the FHS-mandated ``/lib`` rules around the dynamic linker:

  * ``/lib/cpp`` must be a symlink to the C preprocessor (per FHS)
  * ``/lib/ld*`` is the dynamic linker (per FHS)
  * ``ldconfig`` reads ``/etc/ld.so.conf`` (and ``*.conf`` includes) to
    build ``/etc/ld.so.cache``
  * ``/lib<qual>`` (e.g. ``/lib32``, ``/lib64``) holds alternate-format
    libraries; the rules mirror ``/lib`` but ``/lib<qual>/cpp`` is
    optional
  * Only shared libraries required by ``/bin`` and ``/sbin`` belong in
    ``/lib``; X11 / desktop libraries live in ``/usr/lib``

This module models ldconfig behaviour for UmerOS so that user-space
programs can look up shared libraries.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

log = logging.getLogger("UmerOS.Lib.DynamicLinker")


# ─────────────────────────────────────────────────────────────────────────────
#  Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CacheEntry:
    """A single ``/etc/ld.so.cache`` entry (library in the search path)."""
    name: str                # SONAME (e.g. "libc.so.6")
    path: str                # absolute path on disk
    flags: int = 0           # ld.so flags (e.g. DF_1_PIE)
    hardware_cap: int = 0    # HWcap bitmask (glibc internal)
    build_id: str = ""       # ELF .note.gnu.build-id
    timestamp: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "path": self.path,
            "flags": self.flags,
            "hardware_cap": self.hardware_cap,
            "build_id": self.build_id,
        }


@dataclass
class LinkerConfig:
    """Parsed /etc/ld.so.conf + includes."""
    trusted_dirs: List[str] = field(default_factory=list)   # from `trust` keyword
    search_paths: List[str] = field(default_factory=list)   # `include` dirs
    hwcap_dirs: List[str] = field(default_factory=list)     # from `hwcap` keyword
    excludes: List[str] = field(default_factory=list)       # `exclude` patterns
    do_hwcaps: bool = True
    config_files: List[str] = field(default_factory=list)   # files we parsed


# ─────────────────────────────────────────────────────────────────────────────
#  Parser for ld.so.conf
# ─────────────────────────────────────────────────────────────────────────────

class LdSoConfParser:
    """
    Parse ``/etc/ld.so.conf`` and any ``include``-d files.

    Supports the standard keywords:

    * ``/some/path``        — add a search directory
    * ``include /etc/...``  — pull in another config file (globs supported)
    * ``trust <dir>``       — mark a directory as trusted
    * ``hwcap <mask> <dir>`` — conditional directory based on HW capability
    * ``exclude <pattern>`` — exclude libraries whose SONAME matches pattern
    * ``opt``               — continue even if an include file is missing
    """

    INCLUDE_RE = re.compile(r"^include\s+(.+)$")
    TRUST_RE   = re.compile(r"^trust\s+(.+)$")
    HWCAP_RE   = re.compile(r"^hwcap\s+(\S+)\s+(.+)$")
    EXCLUDE_RE = re.compile(r"^exclude\s+(.+)$")
    OPT_RE     = re.compile(r"^opt\s+(.+)$")

    def __init__(self, root: str = "/") -> None:
        self.root = Path(root)

    def parse(self, main_file: str = "/etc/ld.so.conf") -> LinkerConfig:
        cfg = LinkerConfig()
        self._parse_file(main_file, cfg, optional=False, depth=0)
        return cfg

    def _parse_file(
        self,
        path: str,
        cfg: LinkerConfig,
        *,
        optional: bool,
        depth: int,
    ) -> None:
        if depth > 16:
            log.warning("ld.so.conf: max include depth exceeded at %s", path)
            return
        full = self._resolve(path)
        if not full.exists():
            if optional:
                return
            log.warning("ld.so.conf: file not found: %s", full)
            return
        cfg.config_files.append(str(full))
        for raw in full.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if (m := self.INCLUDE_RE.match(line)):
                self._parse_file(m.group(1).strip(), cfg, optional=True, depth=depth + 1)
                continue
            if (m := self.TRUST_RE.match(line)):
                cfg.trusted_dirs.append(m.group(1).strip())
                continue
            if (m := self.HWCAP_RE.match(line)):
                cfg.hwcap_dirs.append(m.group(2).strip())
                continue
            if (m := self.EXCLUDE_RE.match(line)):
                cfg.excludes.append(m.group(1).strip())
                continue
            if (m := self.OPT_RE.match(line)):
                # `opt /path` — treat as a search path, optional load
                cfg.search_paths.append(m.group(1).strip())
                continue
            # bare directory line
            cfg.search_paths.append(self._resolve(line).as_posix())
        return

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.root / p).resolve()


# ─────────────────────────────────────────────────────────────────────────────
#  Cache writer / reader (ld.so.cache)
# ─────────────────────────────────────────────────────────────────────────────

class LdSoCache:
    """
    In-memory representation of ``/etc/ld.so.cache``.

    The on-disk format is glibc's binary format (header ``"glibc-ld.so.cache1"``
    followed by NUL-separated name strings and a table of (key, value)
    offsets).  We faithfully model the structure so the cache file we emit
    is parseable by real glibc ``ldconfig`` / ``ld-linux``.

    Layout::

        struct header {
            char magic[17];          // "glibc-ld.so.cache1\0" (with padding)
            int  nlibs;
            int  len_strings;
            int  pad;                // alignment
            struct entry[nlibs];
        };
        struct entry {
            int  flags;
            int  key;                // offset into string table
            int  value;              // offset into string table
            int  osversion_unused;
            int  hwcap;
            int  pad;
        };
    """

    MAGIC = b"glibc-ld.so.cache1\x00"
    HEADER_STRUCT = struct.Struct("<4I")  # nlibs, len_strings, unused[2]
    ENTRY_STRUCT  = struct.Struct("<6i")  # flags, key, value, unused, hwcap, pad

    def __init__(self) -> None:
        self.entries: List[CacheEntry] = []

    # ── building the cache ─────────────────────────────────────────

    @classmethod
    def build(
        cls,
        config: LinkerConfig,
        *,
        scan_callback=None,
    ) -> "LdSoCache":
        """
        Walk every search path in the config and add every *.so* file to the
        cache.  ``scan_callback`` lets callers override the actual disk scan
        (useful for tests).
        """
        cache = cls()
        seen_paths: Set[str] = set()
        for directory in config.search_paths:
            if not os.path.isdir(directory):
                continue
            scan = scan_callback or _default_scan
            for entry in scan(directory):
                if entry.path in seen_paths:
                    continue
                # Apply `exclude` rules
                if any(_glob_match(ex, entry.name) for ex in config.excludes):
                    continue
                seen_paths.add(entry.path)
                cache.entries.append(entry)
        return cache

    # ── serialisation ─────────────────────────────────────────────

    def to_bytes(self) -> bytes:
        # Build the string table: all SONAMEs, then all paths.
        string_table = bytearray()
        keys: List[int] = []
        values: List[int] = []
        for e in self.entries:
            keys.append(len(string_table))
            string_table.extend(e.name.encode("utf-8") + b"\x00")
            values.append(len(string_table))
            string_table.extend(e.path.encode("utf-8") + b"\x00")
        string_table_bytes = bytes(string_table)

        header = self.MAGIC + self.HEADER_STRUCT.pack(
            len(self.entries),
            len(string_table_bytes),
            0,
            0,
        )
        entries = b""
        for entry, key, value in zip(self.entries, keys, values):
            entries += self.ENTRY_STRUCT.pack(
                entry.flags, key, value, 0, entry.hardware_cap, 0
            )
        return header + entries + string_table_bytes

    def write(self, path: str = "/etc/ld.so.cache") -> int:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.to_bytes()
        p.write_bytes(data)
        return len(data)

    # ── parsing ────────────────────────────────────────────────────

    @classmethod
    def from_bytes(cls, blob: bytes) -> "LdSoCache":
        cache = cls()
        if not blob.startswith(cls.MAGIC):
            raise ValueError("Not a glibc ld.so.cache (bad magic)")
        offset = len(cls.MAGIC)
        nlibs, len_strings, _, _ = cls.HEADER_STRUCT.unpack_from(blob, offset)
        offset += cls.HEADER_STRUCT.size
        # The string table starts after the header + nlibs * entry_size
        string_table_offset = offset + nlibs * cls.ENTRY_STRUCT.size
        for _ in range(nlibs):
            flags, key, value, _, hwcap, _ = cls.ENTRY_STRUCT.unpack_from(
                blob, offset
            )
            offset += cls.ENTRY_STRUCT.size
            soname = _read_cstr(blob, string_table_offset + key)
            fpath  = _read_cstr(blob, string_table_offset + value)
            cache.entries.append(
                CacheEntry(
                    name=soname,
                    path=fpath,
                    flags=flags,
                    hardware_cap=hwcap,
                )
            )
        return cache

    @classmethod
    def from_file(cls, path: str = "/etc/ld.so.cache") -> "LdSoCache":
        return cls.from_bytes(Path(path).read_bytes())

    # ── convenience ───────────────────────────────────────────────

    def lookup(self, soname: str) -> Optional[CacheEntry]:
        for e in self.entries:
            if e.name == soname:
                return e
        return None

    def search(self, pattern: str) -> List[CacheEntry]:
        return [e for e in self.entries if pattern in e.name]

    def __len__(self) -> int:
        return len(self.entries)

    def to_table(self) -> List[Dict]:
        return [e.to_dict() for e in self.entries]


def _read_cstr(blob: bytes, offset: int) -> str:
    end = blob.find(b"\x00", offset)
    if end < 0:
        return blob[offset:].decode("utf-8", "replace")
    return blob[offset:end].decode("utf-8", "replace")


def _glob_match(pattern: str, name: str) -> bool:
    """Minimal fnmatch-style match for ld.so.conf `exclude` patterns."""
    regex = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
    return re.fullmatch(regex, name) is not None


def _default_scan(directory: str) -> Iterable[CacheEntry]:
    """Default directory scan: yield a CacheEntry per *.so* file."""
    for root, _, files in os.walk(directory):
        for fname in files:
            if ".so" in fname:
                full = os.path.join(root, fname)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                # SONAME = the filename itself for our purposes
                soname = fname
                yield CacheEntry(
                    name=soname,
                    path=full,
                    timestamp=st.st_mtime,
                )


# ─────────────────────────────────────────────────────────────────────────────
#  /lib/cpp symlink + /lib<qual> helpers
# ─────────────────────────────────────────────────────────────────────────────

class LibQualifierManager:
    """
    Manage ``/lib<qual>`` alternate-format directories.

    The FHS permits multiple variants for systems that support more than
    one binary format (typically 32-bit + 64-bit).  When present, the
    content rules mirror ``/lib`` *except* that ``/lib<qual>/cpp`` is not
    required.
    """

    COMMON_QUALIFIERS = ("32", "64", "x32", "sf")

    def __init__(self, lib_path: str = "/lib") -> None:
        self.lib_path = Path(lib_path)

    def known_qualifiers(self) -> List[str]:
        return list(self.COMMON_QUALIFIERS)

    def is_qualifier(self, name: str) -> bool:
        return name.startswith("lib") and name[3:] in self.COMMON_QUALIFIERS

    def qualifier_path(self, qualifier: str) -> Path:
        if not self.is_qualifier(qualifier):
            raise ValueError(f"Bad qualifier: {qualifier}")
        return self.lib_path.with_name(self.lib_path.name + qualifier)

    def is_qualifier_resolved(self) -> bool:
        """
        Return True if /lib is a symlink that already resolves to a qual dir
        (e.g. ``/lib`` -> ``/lib64``).
        """
        return self.lib_path.is_symlink()

    def create_qualifier_symlink(
        self,
        from_qualifier: str = "64",
        to_qualifier: Optional[str] = None,
    ) -> Path:
        """
        Make ``/lib`` a symlink to ``/lib<from_qualifier>`` (or to the given
        ``to_qualifier`` if provided).
        """
        target_name = to_qualifier or f"lib{from_qualifier}"
        target = self.lib_path.with_name(target_name)
        if self.lib_path.exists() and not self.lib_path.is_symlink():
            raise FileExistsError(
                f"{self.lib_path} exists and is not a symlink; refusing to overwrite"
            )
        if self.lib_path.is_symlink():
            self.lib_path.unlink()
        self.lib_path.symlink_to(target)
        return self.lib_path

    def ensure_cpp_symlink(
        self,
        target: str = "/usr/bin/cpp",
        *,
        qualifier: Optional[str] = None,
    ) -> Path:
        """
        Ensure ``/lib/cpp`` (or ``/lib<qual>/cpp``) is a symlink to the
        C preprocessor, as required by the FHS.  ``/lib<qual>/cpp`` is
        optional; the FHS only mandates ``/lib/cpp``.
        """
        return self.ensure_cpp_reference(target, qualifier=qualifier)

    def ensure_cpp_reference(
        self,
        target: str = "/usr/bin/cpp",
        *,
        qualifier: Optional[str] = None,
        prefer_symlink: bool = True,
    ) -> Path:
        """
        Ensure ``cpp`` references the C preprocessor.

        says ``/lib/cpp`` must be a reference to the installed C
        preprocessor, traditionally ``/usr/bin/cpp``.  On platforms where
        Python cannot create symlinks (for example some Windows developer
        shells), UmerOS writes a tiny reference file containing the target so
        tests and staging roots remain portable.
        """
        if qualifier:
            link_dir = self.lib_path.with_name(self.lib_path.name + qualifier)
        else:
            link_dir = self.lib_path
        link_dir.mkdir(parents=True, exist_ok=True)
        link = link_dir / "cpp"
        if link.is_symlink() or link.is_file():
            link.unlink()
        elif link.exists():
            raise IsADirectoryError(f"{link} exists and is not a cpp reference")
        if prefer_symlink:
            try:
                link.symlink_to(target)
                return link
            except (OSError, NotImplementedError) as e:
                log.warning("Could not create cpp symlink %s -> %s: %s",
                            link, target, e)
        link.write_text(
            f"UmerOS cpp reference\nTarget: {target}\n",
            encoding="utf-8",
        )
        return link

    def is_cpp_reference(
        self,
        target: str = "/usr/bin/cpp",
        *,
        qualifier: Optional[str] = None,
    ) -> bool:
        """Return True if the cpp entry points at, or records, ``target``."""
        if qualifier:
            link_dir = self.lib_path.with_name(self.lib_path.name + qualifier)
        else:
            link_dir = self.lib_path
        link = link_dir / "cpp"
        if not (link.exists() or link.is_symlink()):
            return False
        if link.is_symlink():
            try:
                return str(link.readlink()) == target
            except OSError:
                return False
        if link.is_file():
            try:
                return target in link.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return False
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  High-level orchestrator
# ─────────────────────────────────────────────────────────────────────────────

class DynamicLinkerManager:
    """
    Coordinates ``/etc/ld.so.conf`` parsing, ``ldconfig`` cache building,
    the ``/lib/cpp`` symlink, and ``/lib<qual>`` handling.
    """

    DEFAULT_CONFIG = """/lib
/usr/lib
include /etc/ld.so.conf.d/*.conf
"""

    def __init__(self, root: str = "/") -> None:
        self.root = Path(root)
        self.parser = LdSoConfParser(root=str(self.root))
        self.qualifier_manager = LibQualifierManager(lib_path=str(self.root / "lib"))
        self.config: Optional[LinkerConfig] = None
        self.cache: Optional[LdSoCache] = None

    def ldconfig(self, config_path: str = "/etc/ld.so.conf") -> Dict:
        """
        Run the equivalent of ``/sbin/ldconfig``:

          1. Parse /etc/ld.so.conf (and includes)
          2. Walk each search path and discover *.so* files
          3. Build /etc/ld.so.cache
          4. Update /lib/cpp symlink
        """
        self.config = self.parser.parse(config_path)
        self.cache = LdSoCache.build(self.config)
        # Make sure the basic /lib/cpp symlink exists
        self.qualifier_manager.ensure_cpp_symlink(qualifier=None)
        return {
            "config_files": list(self.config.config_files),
            "search_paths": list(self.config.search_paths),
            "cached_libraries": len(self.cache),
            "trusted_dirs": list(self.config.trusted_dirs),
        }

    def write_cache(self, path: str = "/etc/ld.so.cache") -> int:
        if self.cache is None:
            self.ldconfig()
        assert self.cache is not None
        return self.cache.write(path)

    def lookup(self, soname: str) -> Optional[CacheEntry]:
        if self.cache is None:
            self.ldconfig()
        assert self.cache is not None
        return self.cache.lookup(soname)

    def search(self, pattern: str) -> List[CacheEntry]:
        if self.cache is None:
            self.ldconfig()
        assert self.cache is not None
        return self.cache.search(pattern)

    def get_summary(self) -> Dict:
        if self.config is None or self.cache is None:
            self.ldconfig()
        assert self.config is not None and self.cache is not None
        return {
            "config_files": list(self.config.config_files),
            "search_paths": list(self.config.search_paths),
            "trusted_dirs": list(self.config.trusted_dirs),
            "hwcap_dirs": list(self.config.hwcap_dirs),
            "excludes": list(self.config.excludes),
            "cache_entries": len(self.cache),
            "cache_paths": [e.path for e in self.cache.entries],
        }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Round-trip the LdSoConfParser and LdSoCache.

    Builds a tiny ``/etc/ld.so.conf`` in a temporary directory, lets
    the parser / cache writer process it, and verifies that the
    resulting ``/etc/ld.so.cache`` round-trips.
    """
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Populate the smallest possible ld.so.conf world.
        (root / "lib").mkdir()
        (root / "lib" / "libc.so.6").write_bytes(b"stub libc")
        (root / "lib" / "libm.so.6").write_bytes(b"stub libm")
        (root / "lib" / "ld-linux-x86-64.so.2").write_bytes(b"stub ld")
        etc = root / "etc"
        etc.mkdir()
        conf = etc / "ld.so.conf"
        conf.write_text(
            "# test config\n"
            f"{root.as_posix()}/lib\n"
            "include /etc/ld.so.conf.d/*.conf\n"
        )
        (etc / "ld.so.conf.d").mkdir()
        (etc / "ld.so.conf.d" / "extra.conf").write_text(
            f"{root.as_posix()}/lib\n"
        )

        # 1. Parser
        parser = LdSoConfParser(root=str(root))
        cfg = parser.parse(main_file=str(conf))
        if not cfg.search_paths:
            return False
        if str(root.as_posix()) not in " ".join(cfg.search_paths):
            return False
        if not cfg.config_files:
            return False

        # 2. Cache built from the parser output
        cache = LdSoCache.build(cfg)
        if len(cache) == 0:
            return False
        # 3. Binary round-trip
        blob = cache.to_bytes()
        if not blob.startswith(LdSoCache.MAGIC[:17]):
            return False
        cache_path = etc / "ld.so.cache"
        cache_path.write_bytes(blob)
        rt = LdSoCache.from_file(str(cache_path))
        names = {e.name for e in rt.entries}
        for required in ("libc.so.6", "libm.so.6", "ld-linux-x86-64.so.2"):
            if required not in names:
                return False
        # 4. Lookup and search
        if rt.lookup("libc.so.6") is None:
            return False
        # ``search`` is a substring match, not a glob.
        if not rt.search("libc"):
            return False
        if not rt.search("libm"):
            return False
    return True


if __name__ == "__main__":
    print("dynamic_linker selftest:", "OK" if _selftest() else "FAIL")
