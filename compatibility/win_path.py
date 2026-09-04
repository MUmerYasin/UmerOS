"""
Umer OS /compatibility/win_path — DOS path translation
====================================================

Windows uses a *DOS-style* path scheme that differs from POSIX in
several important ways:

* **Drive letters**   ``C:``, ``D:`` ... each is the root of a
  separate filesystem.  We map them to a configurable directory
  under the Umer OS *compat root* (default ``/compat``).
* **Separator**        backslash (``\\``) is the canonical
  separator, although Windows also accepts forward slashes.
* **Case-insensitivity** by default (per-volume).
* **Long path prefix**  ``\\\\?\\`` bypasses MAX_PATH and disables
  parsing; ``\\\\\\\\?\\`` is the UNC long-path prefix.
* **8.3 short names**  ``PROGRA~1`` style.  Optional in modern
  Windows but still emitted by some installers.
* **Drive-relative**   ``\\foo`` is the *root-relative* path on the
  *current* drive.
* **Volume GUID paths** ``\\\\?\\Volume{GUID}\\`` -- we map these
  to ``/compat/volumes/<guid>``.
* **UNC paths**        ``\\\\server\\share\\path`` -- we map these
  to ``/compat/unc/<server>/<share>/<path>``.

This module implements a single :class:`DosPathMapper` that converts
back and forth between DOS and POSIX paths, with knobs for the
compat root, the default drive, and short-name handling.

References
----------

* https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file
* https://learn.microsoft.com/en-us/dotnet/standard/io/file-path-formats

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import os
import re
from typing import Iterable, List, Optional, Tuple


# --- Path-string classification -----------------------------------------

_DRIVE_RE = re.compile(r"^([A-Za-z]):(.*)$")
_UNC_RE = re.compile(r"^\\\\([^\\]+)\\([^\\]+)(?:\\(.*))?$")
_VOL_GUID_RE = re.compile(r"^\\\\\?\\Volume\{([0-9A-Fa-f-]+)\}\\(.*)$")
_LONG_PATH_RE = re.compile(r"^\\\\\?\\(.*)$")


class DosPathError(ValueError):
    """Raised when a DOS path cannot be translated."""


class DosPathMapper:
    """Translate between DOS-style paths and POSIX paths.

    Args:
        compat_root: Directory under which the Windows filesystem
                     tree lives.  Defaults to ``/compat``; on Windows
                     hosts (where ``/compat`` is meaningless) the
                     mapper falls back to ``C:/compat`` so tests can
                     still run.
        default_drive: Drive used when a path is *not* drive-qualified
                     (e.g. ``\\foo`` or ``foo\\bar``).  Defaults to ``C``.
        case_sensitive: Whether the target filesystem is case-sensitive.
                     Defaults to ``False`` (Windows default).
        enable_short_names: Whether to generate / accept 8.3 short
                     names.  Off by default (we just normalise).
    """

    def __init__(
        self,
        compat_root: Optional[str] = None,
        *,
        default_drive: str = "C",
        case_sensitive: bool = False,
        enable_short_names: bool = False,
    ) -> None:
        if compat_root is None:
            if os.name == "nt":
                compat_root = r"C:\compat"
            else:
                compat_root = "/compat"
        self.compat_root = os.path.abspath(compat_root)
        self.default_drive = default_drive.upper()
        self.case_sensitive = case_sensitive
        self.enable_short_names = enable_short_names
        self._short_map: dict = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_separators(p: str) -> str:
        """Convert all separators to backslash and collapse ``./``."""
        p = p.replace("/", "\\")
        # Strip trailing separator (except for the root).
        if len(p) > 3 and p.endswith("\\"):
            p = p[:-1]
        return p

    @staticmethod
    def _is_absolute_posix(p: str) -> bool:
        return p.startswith("/") or (os.name == "nt" and p.startswith("\\"))

    # ------------------------------------------------------------------
    # DOS -> POSIX
    # ------------------------------------------------------------------

    def to_posix(self, dos_path: str) -> str:
        """Translate ``dos_path`` (e.g. ``C:\\Windows\\System32``) to POSIX.

        Raises:
            DosPathError: on a syntactically-invalid DOS path.
        """
        if not dos_path:
            raise DosPathError("empty DOS path")
        p = self._normalise_separators(dos_path)
        if not self.case_sensitive:
            p = p.lower()  # we don't lowercase drive letter here

        # 1. Long path prefix: ``\\?\X:\foo`` or ``\\?\UNC\server\share\foo``
        m = _LONG_PATH_RE.match(p)
        if m:
            inner = p[4:]
            # Recurse on the inner (drive / UNC) path.
            if _DRIVE_RE.match(inner):
                return self.to_posix(inner)
            if inner.startswith("\\UNC\\"):
                return self.to_posix("\\\\" + inner[5:])
            return self.to_posix(inner)

        # 2. Volume GUID path
        m = _VOL_GUID_RE.match(p)
        if m:
            guid, rest = m.group(1), m.group(2)
            rest = rest.replace("\\", "/")
            return os.path.join(self.compat_root, "volumes", guid, rest)

        # 3. UNC: ``\\server\share\rest``
        m = _UNC_RE.match(p)
        if m:
            server, share, rest = m.group(1), m.group(2), m.group(3) or ""
            rest = rest.replace("\\", "/")
            return os.path.join(self.compat_root, "unc", server, share,
                               rest.lstrip("\\/"))

        # 4. Drive-relative: ``C:foo`` means drive + working-dir + foo.
        m = re.match(r"^([A-Za-z]):([^\\].*)?$", p)
        if m:
            drive, rest = m.group(1).upper(), (m.group(2) or "")
            cwd = self._drive_cwd.get(drive, "\\")
            return self.to_posix(f"{drive}:{cwd.rstrip('\\\\')}\\{rest}")

        # 5. Drive-qualified absolute: ``C:\foo``
        m = _DRIVE_RE.match(p)
        if m:
            drive, rest = m.group(1).upper(), m.group(2)
            rest = rest.lstrip("\\").replace("\\", "/")
            return os.path.join(self.compat_root, drive, rest) if rest \
                else os.path.join(self.compat_root, drive)

        # 6. Root-relative on default drive: ``\foo``
        if p.startswith("\\"):
            rest = p.lstrip("\\").replace("\\", "/")
            return os.path.join(self.compat_root, self.default_drive, rest)

        # 7. Relative path
        cwd = self._drive_cwd.get(self.default_drive, "\\")
        return self.to_posix(f"{self.default_drive}:{cwd}\\{p}")

    # ------------------------------------------------------------------
    # POSIX -> DOS
    # ------------------------------------------------------------------

    def to_dos(self, posix_path: str) -> str:
        """Translate a POSIX path under ``compat_root`` back to DOS form."""
        p = os.path.abspath(posix_path)
        root = self.compat_root.rstrip("\\/").rstrip("/")
        rel = os.path.relpath(p, root)
        if rel.startswith(".."):
            raise DosPathError(
                f"path '{posix_path}' is not under compat root {self.compat_root}"
            )
        parts = rel.replace("\\", "/").split("/")
        if not parts or parts == ["."]:
            return f"{self.default_drive}:\\"
        head, *tail = parts
        if head == "volumes" and tail:
            return f"\\\\?\\Volume{{{tail[0]}}}\\" + "\\".join(tail[1:])
        if head == "unc" and len(tail) >= 2:
            return f"\\\\{tail[0]}\\{tail[1]}" + (
                "\\" + "\\".join(tail[2:]) if len(tail) > 2 else "\\"
            )
        drive = head.upper()
        rest = "\\".join(tail)
        if not self.case_sensitive:
            drive = drive.upper()
        return f"{drive}:\\{rest}" if rest else f"{drive}:\\"

    # ------------------------------------------------------------------
    # Per-drive CWD (only used for path-relative DOS paths)
    # ------------------------------------------------------------------

    _drive_cwd: dict = {}

    def set_drive_cwd(self, drive: str, cwd: str) -> None:
        """Set the *current working directory* for a specific drive.

        Used when translating drive-relative paths like ``C:foo.txt``.
        """
        self._drive_cwd[drive.upper()] = self._normalise_separators(cwd)

    # ------------------------------------------------------------------
    # Path manipulation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def split_drive(p: str) -> Tuple[str, str]:
        """Return ``(drive, path)`` for a DOS path (or ``('', p)``)."""
        m = _DRIVE_RE.match(p)
        if m:
            return m.group(1).upper(), m.group(2)
        return "", p

    @staticmethod
    def split_root(p: str) -> Tuple[str, str]:
        """Return ``(root, rest)`` where root is ``C:\\`` (or ``\\\\UNC\\...``)."""
        m = _UNC_RE.match(p)
        if m:
            return f"\\\\{m.group(1)}\\{m.group(2)}\\", m.group(3) or ""
        m = _DRIVE_RE.match(p)
        if m:
            return f"{m.group(1).upper()}:\\", m.group(2)
        if p.startswith("\\"):
            return "\\", p.lstrip("\\")
        return "", p

    @staticmethod
    def has_long_path_prefix(p: str) -> bool:
        return bool(_LONG_PATH_RE.match(p))

    # ------------------------------------------------------------------
    # 8.3 short-name handling (optional)
    # ------------------------------------------------------------------

    def register_short_name(self, dos_path: str, short: str) -> None:
        """Map a long DOS path to an 8.3 short name."""
        if not self.enable_short_names:
            return
        key = self._normalise_separators(dos_path).lower()
        self._short_map[key] = short

    def short_name(self, dos_path: str) -> str:
        """Return the registered 8.3 short name, or the path itself."""
        if not self.enable_short_names:
            return dos_path
        key = self._normalise_separators(dos_path).lower()
        return self._short_map.get(key, dos_path)


# ---------------------------------------------------------------------------
# Convenience helpers (module-level)
# ---------------------------------------------------------------------------

_DEFAULT_MAPPER = DosPathMapper()


def dos_to_posix(path: str) -> str:
    """Translate a DOS path using the default :data:`_DEFAULT_MAPPER`."""
    return _DEFAULT_MAPPER.to_posix(path)


def posix_to_dos(path: str) -> str:
    """Translate a POSIX path using the default :data:`_DEFAULT_MAPPER`."""
    return _DEFAULT_MAPPER.to_dos(path)


def normalise_dos_path(path: str) -> str:
    """Canonicalise a DOS path: backslash separators, no trailing sep."""
    return DosPathMapper._normalise_separators(path)


__all__ = [
    "DosPathError",
    "DosPathMapper",
    "dos_to_posix",
    "posix_to_dos",
    "normalise_dos_path",
]
