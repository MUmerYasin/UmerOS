"""
Umer OS /compatibility/dll_search — Windows DLL search order
============================================================

Pure-Python implementation of the Win32 *DLL search order* used by
``LoadLibrary`` / ``LoadLibraryEx``.

The default search order (Windows XP / Server 2003) was:

1. The directory from which the application loaded.
2. The current directory.
3. The Windows system directory.
4. The 16-bit system directory.
5. The Windows directory.
6. The ``PATH`` directories.

Since Windows Vista, **Safe DLL Search Mode** (``SafeDllSearchMode``)
is the default and the order is:

1. The directory from which the application loaded.
2. The Windows system directory.
3. The 16-bit system directory.
4. The Windows directory.
5. The current directory.
6. The ``PATH`` directories.

``LoadLibraryEx`` further allows the caller to request *only* a
subset of those locations via the ``dwFlags`` argument:

* ``LOAD_WITH_ALTERED_SEARCH_PATH``  — start the search at the
  directory of the loaded DLL rather than the application.
* ``LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR``  — restrict to the directory of
  the loaded DLL.
* ``LOAD_LIBRARY_SEARCH_APPLICATION_DIR``  — restrict to the
  application directory.
* ``LOAD_LIBRARY_SEARCH_USER_DIRS``  — restrict to the user's
  per-application ``%LOCALAPPDATA%\\<app>`` directory.
* ``LOAD_LIBRARY_SEARCH_SYSTEM32``  — restrict to ``%WINDIR%\\System32``.
* ``LOAD_LIBRARY_SEARCH_DEFAULT_DIRS``  — application dir + System32
  + 16-bit System + Windows dir.

This module encodes the above in a single :class:`DllSearchPath`
dataclass plus a :func:`find_dll` function that walks the search list
and returns the first hit (or ``None``).

References
----------

* https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-loadlibraryexa
* https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-search-order

Author:  Umer OS Project
Licence: GPL-3.0
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Tuple

log = logging.getLogger("UmerOS.Compat.DllSearch")


# ---------------------------------------------------------------------------
# Win32 LoadLibraryEx flags
# ---------------------------------------------------------------------------

DONT_RESOLVE_DLL_REFERENCES         = 0x00000001
LOAD_LIBRARY_AS_DATAFILE            = 0x00000002
LOAD_WITH_ALTERED_SEARCH_PATH       = 0x00000008
LOAD_IGNORE_CODE_AUTHZ_LEVEL        = 0x00000010
LOAD_LIBRARY_AS_IMAGE_RESOURCE      = 0x00000020
LOAD_LIBRARY_AS_DATAFILE_EXCLUSIVE  = 0x00000040
LOAD_LIBRARY_REQUIRE_SIGNED_TARGET  = 0x00000080
LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR    = 0x00000100
LOAD_LIBRARY_SEARCH_APPLICATION_DIR = 0x00000200
LOAD_LIBRARY_SEARCH_USER_DIRS       = 0x00000400
LOAD_LIBRARY_SEARCH_SYSTEM32        = 0x00000800
LOAD_LIBRARY_SEARCH_DEFAULT_DIRS    = 0x00001000
LOAD_LIBRARY_SAFE_CURRENT_DIR       = 0x00002000
LOAD_LIBRARY_SEARCH_PATH            = 0x00004000

# ---------------------------------------------------------------------------
# Search locations
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SearchLocation:
    """A single directory in the search path."""
    kind: str               # "application", "system32", "system16", "windows",
                            # "current", "path", "user-dirs", "dll-load"
    path: str

    def __str__(self) -> str:
        return f"({self.kind}:{self.path})"


@dataclass
class DllSearchPath:
    """The ordered list of directories the loader will try.

    The class is constructed from a *minimal* set of high-level
    inputs (the application directory, the Windows directory, the
    current directory, and the ``PATH``).  The exact ordering depends
    on the ``safe_dll_search_mode`` flag and on the optional
    ``search_flags`` argument that the caller can pass to
    :meth:`make_sequence`.
    """

    application_dir: Optional[str] = None
    system32_dir: Optional[str] = None
    system16_dir: Optional[str] = None
    windows_dir: Optional[str] = None
    current_dir: Optional[str] = None
    path_dirs: Tuple[str, ...] = ()
    user_dirs: Tuple[str, ...] = ()
    dll_load_dir: Optional[str] = None
    safe_dll_search_mode: bool = True

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    @classmethod
    def from_environment(cls,
                         application_dir: str,
                         *,
                         system32_dir: str = r"C:\Windows\System32",
                         windows_dir: str = r"C:\Windows",
                         current_dir: Optional[str] = None,
                         path_env: Optional[str] = None,
                         user_dirs: Sequence[str] = (),
                         safe_dll_search_mode: bool = True,
                         ) -> "DllSearchPath":
        """Build a search path from the static environment.

        The 16-bit system directory is conventionally
        ``systemroot\\System``; we add it automatically when a Windows
        directory is given.
        """
        return cls(
            application_dir=os.path.abspath(application_dir),
            system32_dir=os.path.abspath(system32_dir),
            system16_dir=os.path.join(os.path.abspath(windows_dir), "System"),
            windows_dir=os.path.abspath(windows_dir),
            current_dir=os.path.abspath(current_dir) if current_dir else None,
            path_dirs=tuple(
                os.path.abspath(p)
                for p in (path_env or os.environ.get("PATH", "")).split(
                    os.pathsep)
                if p
            ),
            user_dirs=tuple(os.path.abspath(p) for p in user_dirs),
            safe_dll_search_mode=safe_dll_search_mode,
        )

    # ------------------------------------------------------------------
    # Sequence generation
    # ------------------------------------------------------------------

    def make_sequence(self, *, search_flags: int = 0) -> List[SearchLocation]:
        """Return the ordered list of search locations.

        ``search_flags`` follows the ``LoadLibraryEx`` convention.
        When ``LOAD_WITH_ALTERED_SEARCH_PATH`` is set, the search
        starts at :attr:`dll_load_dir` instead of the application
        directory (this is how the loader finds a DLL when only its
        path, not its name, is given).
        """
        # Restrictive search flag sets.
        if search_flags & LOAD_LIBRARY_SEARCH_DEFAULT_DIRS:
            return self._build_default_dirs_only()
        if search_flags & LOAD_LIBRARY_SEARCH_SYSTEM32:
            return self._locations(("system32",))
        if search_flags & LOAD_LIBRARY_SEARCH_USER_DIRS:
            return self._locations_user_dirs()
        if search_flags & LOAD_LIBRARY_SEARCH_APPLICATION_DIR:
            return self._locations(("application",))
        if search_flags & LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR:
            return self._locations(("dll-load",))

        # Default order depends on SafeDllSearchMode + altered path.
        start_dir = self.dll_load_dir if (
            search_flags & LOAD_WITH_ALTERED_SEARCH_PATH
            and self.dll_load_dir) else self.application_dir
        return self._default_sequence(start_dir)

    # ------------------------------------------------------------------
    # Sequence builders (private)
    # ------------------------------------------------------------------

    def _default_sequence(self, start_dir: Optional[str]
                          ) -> List[SearchLocation]:
        if self.safe_dll_search_mode:
            # Modern order: app, system32, system16, windows, current, path.
            kinds = ("application", "system32", "system16", "windows",
                     "current", "path")
        else:
            # Legacy XP order: app, current, system32, system16,
            # windows, path.
            kinds = ("application", "current", "system32", "system16",
                     "windows", "path")
        first_index = 0
        if start_dir and start_dir == self.dll_load_dir:
            # ``LOAD_WITH_ALTERED_SEARCH_PATH``: prepend the DLL's dir.
            return [SearchLocation("dll-load", start_dir)] + \
                self._locations(kinds, skip_first=True)
        return self._locations(kinds)

    def _build_default_dirs_only(self) -> List[SearchLocation]:
        return self._locations(("application", "system32", "system16",
                                "windows"))

    def _locations_user_dirs(self) -> List[SearchLocation]:
        return self._locations(("application", "user-dirs"))

    def _locations(self, kinds: Sequence[str], *,
                   skip_first: bool = False) -> List[SearchLocation]:
        out: List[SearchLocation] = []
        if not skip_first:
            for k in kinds:
                if k == "application":
                    if self.application_dir:
                        out.append(SearchLocation("application",
                                                  self.application_dir))
                elif k == "system32":
                    if self.system32_dir:
                        out.append(SearchLocation("system32",
                                                  self.system32_dir))
                elif k == "system16":
                    if self.system16_dir:
                        out.append(SearchLocation("system16",
                                                  self.system16_dir))
                elif k == "windows":
                    if self.windows_dir:
                        out.append(SearchLocation("windows",
                                                  self.windows_dir))
                elif k == "current":
                    if self.current_dir:
                        out.append(SearchLocation("current",
                                                  self.current_dir))
                elif k == "path":
                    for p in self.path_dirs:
                        out.append(SearchLocation("path", p))
                elif k == "user-dirs":
                    for u in self.user_dirs:
                        out.append(SearchLocation("user-dirs", u))
                elif k == "dll-load":
                    if self.dll_load_dir:
                        out.append(SearchLocation("dll-load",
                                                  self.dll_load_dir))
        else:
            # skip_first is a hack to support ``LOAD_WITH_ALTERED_SEARCH_PATH``
            # which prepends the DLL dir then continues from "system32".
            for k in ("system32", "system16", "windows", "current", "path"):
                for loc in self._locations([k]):
                    out.append(loc)
        return out

    # ------------------------------------------------------------------
    # Convenience: produce the candidate file names tried for a DLL name
    # ------------------------------------------------------------------

    @staticmethod
    def candidate_names(name: str) -> Tuple[str, ...]:
        """Return the file-name variants the loader tries for ``name``.

        Win32 first tries the literal name (with any extension), then
        appends ``.dll`` when no extension was provided.
        """
        if not name:
            return ()
        if "." in name:
            return (name,)
        return (name + ".dll", name + ".DLL")


# ---------------------------------------------------------------------------
# find_dll
# ---------------------------------------------------------------------------

def find_dll(name: str,
             search_path: DllSearchPath,
             *,
             search_flags: int = 0,
             ) -> Optional[Tuple[SearchLocation, str]]:
    """Walk ``search_path`` and return the first match for ``name``.

    The result is ``(location, absolute_path)`` where ``location``
    records which entry of the search order produced the match.  The
    function returns ``None`` if no directory contains a candidate.
    """
    for location in search_path.make_sequence(search_flags=search_flags):
        for candidate in DllSearchPath.candidate_names(name):
            full = os.path.join(location.path, candidate)
            if os.path.isfile(full):
                return (location, os.path.abspath(full))
    return None


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        app = os.path.join(tmp, "app")
        sys32 = os.path.join(tmp, "Windows", "System32")
        win = os.path.join(tmp, "Windows")
        for d in (app, sys32, win):
            os.makedirs(d, exist_ok=True)
        # Drop a "kernel32.dll" in three places.
        with open(os.path.join(app, "kernel32.dll"), "wb") as f:
            f.write(b"app-version")
        with open(os.path.join(sys32, "kernel32.dll"), "wb") as f:
            f.write(b"sys32-version")
        with open(os.path.join(win, "kernel32.dll"), "wb") as f:
            f.write(b"win-version")

        sp = DllSearchPath(
            application_dir=app,
            system32_dir=sys32,
            system16_dir=os.path.join(win, "System"),
            windows_dir=win,
            current_dir=app,
            path_dirs=(),
            safe_dll_search_mode=True,
        )
        # Safe mode: app first.
        loc, path = find_dll("kernel32.dll", sp)
        if loc is None or "app" not in loc.path:
            return False
        with open(path, "rb") as f:
            if f.read() != b"app-version":
                return False
        # Legacy mode: same result if only one path matches each kind.
        sp.safe_dll_search_mode = False
        loc, path = find_dll("kernel32.dll", sp)
        if "app" not in loc.path:
            return False
        sp.safe_dll_search_mode = True

        # Restrictive flag: SYSTEM32 only -> finds the sys32 version.
        loc, _ = find_dll("kernel32.dll", sp,
                          search_flags=LOAD_LIBRARY_SEARCH_SYSTEM32)
        if loc is None or loc.kind != "system32":
            return False

        # APPLICATION_DIR only.
        loc, _ = find_dll("kernel32.dll", sp,
                          search_flags=LOAD_LIBRARY_SEARCH_APPLICATION_DIR)
        if loc is None or loc.kind != "application":
            return False

        # No extension -> candidate_names produces ``foo.dll`` etc.
        loc, path = find_dll("kernel32", sp)
        if loc is None:
            return False

        # Missing DLL returns None.
        loc = find_dll("does-not-exist.dll", sp)
        if loc is not None:
            return False

    # from_environment quick smoke test.
    sp2 = DllSearchPath.from_environment(
        application_dir="C:/MyApp",
        system32_dir="C:/Windows/System32",
        windows_dir="C:/Windows",
        current_dir="C:/MyApp",
        path_env="C:/Tools;C:/Other",
        safe_dll_search_mode=True,
    )
    if sp2.application_dir != "C:\\MyApp":
        return False
    if len(sp2.path_dirs) != 2:
        return False
    seq = sp2.make_sequence()
    kinds = [l.kind for l in seq]
    if kinds[:5] != ["application", "system32", "system16", "windows",
                     "current"]:
        return False
    if kinds[5] != "path" or kinds.count("path") != 2:
        return False
    # Legacy.
    sp2.safe_dll_search_mode = False
    kinds2 = [l.kind for l in sp2.make_sequence()]
    if kinds2[:2] != ["application", "current"]:
        return False
    if kinds2[2:5] != ["system32", "system16", "windows"]:
        return False
    if kinds2[5] != "path" or kinds2.count("path") != 2:
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _selftest() else 1)
