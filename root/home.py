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
Umer OS /root - home directory manager
=====================================
Manages the system administrator (``root``) home directory.

/root reference spells out three requirements that drive
this module:

1. ``/root`` is the *recommended* home directory of the system
   administrator - it is *not* under ``/home`` because ``/home`` is
   often on a different partition and would be inaccessible when
   only ``/`` is mounted (e.g. during recovery, single-user mode,
   or a missing NFS mount).

2. If root's home directory cannot be located, it **must default
   to** ``/`` so that ``cd ~`` and friends keep working.

3. ``/root`` should not contain subdirectories for mail or other
   applications; mail for administrative roles (root, postmaster,
   webmaster) should be forwarded to an appropriate user.

The :class:`RootHomeManager` is the entry point.  It knows how to
resolve root's home from ``/etc/passwd`` (UID 0) with the documented
fallbacks, how to ensure the directory exists with the FHS-mandated
permissions (``0700``), and how to inventory what is inside so a
caller can warn about mail/ application subdirs.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3) 
"""

from __future__ import annotations

import logging
import os
import shutil
import stat
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Structured passwd entry type hint - never executed at runtime.
    class _PwdModule:
        struct_passwd = object
        def getpwnam(self, name: str) -> object: ...
    pwd: _PwdModule = None  # type: ignore[assignment]
else:
    try:
        import pwd
    except ImportError:
        pwd = None  # type: ignore[assignment]
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger("UmerOS.Root.Home")


# ---------------------------------------------------------------------------
# Constants from the /root reference
# ---------------------------------------------------------------------------

#: Conventional location of root's home directory.  The FSSTND only
#: *recommends* this path; the user is free to put it elsewhere, but
#: ``/root`` is the universal default.
DEFAULT_ROOT_HOME: str = "/root"

#: UID of the system administrator account.
ROOT_UID: int = 0

#: FHS-mandated permissions: only root may read, write, or enter.
#: This is the historical default; some hardened distros tighten it
#: further to ``0500`` to disallow even ``ls``.
ROOT_HOME_MODE: int = 0o700

#: Subdirectories that the /root page warns against.  If any of
#: these exist inside root's home, the audit flags them so an
#: operator can decide whether they are stale.
DISCOURAGED_SUBDIRS: Tuple[str, ...] = (
    "Mail",
    "mail",
    "Maildir",
    ".cache",
    "www",
    "html",
    "public_html",
    "tmp",
    ".local",
    ".config",
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RootHomeInfo:
    """A snapshot of root's home state."""

    path: str
    exists: bool
    uid: int
    gid: int
    mode: int
    size_bytes: int
    file_count: int
    subdirs: List[str] = field(default_factory=list)
    discouraged_subdirs: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    resolved_from: str = ""   # "passwd" | "env" | "default" | "fallback-/"
    passwd_entry: Optional[str] = None
    as_of: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {
            "path":               self.path,
            "exists":             self.exists,
            "uid":                self.uid,
            "gid":                self.gid,
            "mode":               oct(self.mode),
            "size_bytes":         self.size_bytes,
            "file_count":         self.file_count,
            "subdirs":            list(self.subdirs),
            "discouraged_subdirs": list(self.discouraged_subdirs),
            "issues":             list(self.issues),
            "resolved_from":      self.resolved_from,
            "passwd_entry":       self.passwd_entry,
            "as_of":              self.as_of,
        }


# ---------------------------------------------------------------------------
# Passwd helper
# ---------------------------------------------------------------------------

class _PasswdFallback:
    """Lightweight stand-in for ``pwd.struct_passwd`` when the ``pwd``
    module is unavailable (Windows)."""
    __slots__ = ("pw_name", "pw_passwd", "pw_uid", "pw_gid",
                 "pw_gecos", "pw_dir", "pw_shell")

    def __init__(self, name: str, passwd: str, uid: int, gid: int,
                 gecos: str, home: str, shell: str) -> None:
        self.pw_name = name
        self.pw_passwd = passwd
        self.pw_uid = uid
        self.pw_gid = gid
        self.pw_gecos = gecos
        self.pw_dir = home
        self.pw_shell = shell


def find_root_passwd_entry(passwd_path: str = "/etc/passwd") -> Optional[object]:
    """Return the ``/etc/passwd`` row whose UID is 0, or None.

    Falls back to :func:`pwd.getpwnam` if the file is missing or
    unreadable - on most systems root is always in the database.
    """
    if os.path.isfile(passwd_path):
        try:
            with open(passwd_path, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(":")
                    if len(parts) < 7:
                        continue
                    try:
                        uid = int(parts[2])
                    except ValueError:
                        continue
                    if uid == ROOT_UID:
                        return _PasswdFallback(
                            name=parts[0], passwd=parts[1],
                            uid=int(parts[2]), gid=int(parts[3]),
                            gecos=parts[4], home=parts[5], shell=parts[6],
                        )
        except OSError as exc:
            log.warning("could not read %s: %s", passwd_path, exc)
    # Fallback to pwd database (Unix only).
    if pwd is not None:
        try:
            return pwd.getpwnam("root")
        except KeyError:
            pass
    return None


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

@dataclass
class RootHomeResolver:
    """Resolves the canonical path of root's home directory.

    Resolution order (per FSSTND + the fallback rule):

    1. ``/etc/passwd`` UID 0 row's ``pw_dir`` field, if it is set and
       not the empty string.
    2. The ``HOME`` environment variable, if it is set and root is
       the effective user.
    3. :data:`DEFAULT_ROOT_HOME` (``/root``).
    4. **Fallback** - if none of the above are reachable, return
       ``/`` (per the FSSTND: "If the home directory of the root
       account is not stored on the root partition it will be
       necessary to make certain it will default to / if it can
       not be located.").

    The resolver is a small object so a test can ask "what would
    ``~root`` resolve to?" without touching the filesystem.
    """

    default_path: str = DEFAULT_ROOT_HOME
    passwd_path: str = "/etc/passwd"
    fallback_path: str = "/"

    def resolve(self, *, env: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
        """Return ``(path, source)`` where ``source`` is one of
        ``"passwd"``, ``"env"``, ``"default"``, ``"fallback-/"``.
        """
        # 1. /etc/passwd
        entry = find_root_passwd_entry(self.passwd_path)
        if entry is not None and entry.pw_dir:
            return entry.pw_dir, "passwd"

        # 2. Environment
        env_map = env if env is not None else os.environ
        if env_map.get("HOME") and self._looks_root_env():
            return env_map["HOME"], "env"

        # 3. Default
        if os.path.isdir(self.default_path):
            return self.default_path, "default"

        # 4. Fallback
        return self.fallback_path, "fallback-/"

    @staticmethod
    def _looks_root_env() -> bool:
        """True when the current process is running as root."""
        try:
            return os.geteuid() == 0
        except (AttributeError, OSError):
            # Windows: treat the absence of ``geteuid`` as "not root".
            return False


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class RootHomeManager:
    """High-level manager for root's home directory.

    Combines the resolver, the FHS audit, and the bootstrap helper
    in one place so the rest of the runtime does not have to wire
    them up by hand.
    """

    def __init__(self,
                 default_path: str = DEFAULT_ROOT_HOME,
                 passwd_path: str = "/etc/passwd",
                 expected_mode: int = ROOT_HOME_MODE) -> None:
        self.default_path = default_path
        self.passwd_path = passwd_path
        self.expected_mode = expected_mode
        self.resolver = RootHomeResolver(
            default_path=default_path,
            passwd_path=passwd_path,
        )

    # -- resolution -------------------------------------------------------

    def resolve(self) -> Tuple[str, str]:
        return self.resolver.resolve()

    # -- audit ------------------------------------------------------------

    def audit(self, path: Optional[str] = None) -> RootHomeInfo:
        """Return a :class:`RootHomeInfo` for ``path`` (default: resolved)."""
        if path is None:
            path, source = self.resolve()
        else:
            source = "explicit"
        info = RootHomeInfo(
            path=path,
            exists=False,
            uid=ROOT_UID,
            gid=0,
            mode=0,
            size_bytes=0,
            file_count=0,
            resolved_from=source,
        )
        root = Path(path)
        if not root.exists():
            info.issues.append(f"{path} does not exist")
            return info
        info.exists = True
        try:
            st = root.stat()
        except OSError as exc:
            info.issues.append(f"stat failed: {exc}")
            return info
        info.uid = st.st_uid
        info.gid = st.st_gid
        info.mode = stat.S_IMODE(st.st_mode)
        info.size_bytes = st.st_size

        # Inventory.
        files = 0
        subdirs: List[str] = []
        discouraged: List[str] = []
        try:
            for entry in root.iterdir():
                if entry.is_dir() and not entry.is_symlink():
                    subdirs.append(entry.name)
                    if entry.name in DISCOURAGED_SUBDIRS:
                        discouraged.append(entry.name)
                elif entry.is_file():
                    files += 1
        except OSError as exc:
            info.issues.append(f"listdir failed: {exc}")
        info.file_count = files
        info.subdirs = sorted(subdirs)
        info.discouraged_subdirs = sorted(discouraged)

        # Permissions.
        if info.mode != self.expected_mode:
            # Some hardened systems tighten to 0500; accept anything
            # that does not grant access to "other".
            if info.mode & 0o007:
                info.issues.append(
                    f"mode is {oct(info.mode)} (allows access to 'other'); "
                    f"expected at most {oct(self.expected_mode)}"
                )
            else:
                info.issues.append(
                    f"mode is {oct(info.mode)}; default is {oct(self.expected_mode)} "
                    "(non-fatal, but FHS recommends 0700)"
                )

        # Owner.
        if info.uid != ROOT_UID:
            info.issues.append(
                f"owned by uid {info.uid}, expected 0 (root)"
            )

        # Discouraged subdirs.
        if discouraged:
            info.issues.append(
                f"contains discouraged subdir(s): {', '.join(discouraged)} "
                "(/root recommends against mail/applications here)"
            )

        # /etc/passwd entry.
        entry = find_root_passwd_entry(self.passwd_path)
        if entry is not None:
            info.passwd_entry = (
                f"{entry.pw_name}:x:{entry.pw_uid}:{entry.pw_gid}:"
                f"{entry.pw_gecos}:{entry.pw_dir}:{entry.pw_shell}"
            )
            if entry.pw_dir and entry.pw_dir != path:
                info.issues.append(
                    f"resolved home {path!r} does not match /etc/passwd "
                    f"({entry.pw_dir!r})"
                )

        return info

    # -- bootstrap --------------------------------------------------------

    def ensure(self, path: Optional[str] = None) -> RootHomeInfo:
        """Create the directory if it does not exist and tighten its
        permissions to the FHS-recommended value.

        Returns the resulting :class:`RootHomeInfo`.
        """
        if path is None:
            path, _ = self.resolve()
        root = Path(path)
        if not root.exists():
            try:
                root.mkdir(parents=True, exist_ok=False)
                log.info("created root home at %s", path)
            except OSError as exc:
                log.error("could not create %s: %s", path, exc)
                raise
        try:
            os.chmod(path, self.expected_mode)
        except OSError as exc:
            log.warning("could not chmod %s: %s", path, exc)
        return self.audit(path)

    # -- subdir helpers ---------------------------------------------------

    def list_subdirs(self, path: Optional[str] = None) -> List[str]:
        if path is None:
            path, _ = self.resolve()
        root = Path(path)
        if not root.is_dir():
            return []
        return sorted(
            e.name for e in root.iterdir()
            if e.is_dir() and not e.is_symlink()
        )

    def discouraged_subdirs(self, path: Optional[str] = None) -> List[str]:
        subdirs = set(self.list_subdirs(path))
        return sorted(d for d in DISCOURAGED_SUBDIRS if d in subdirs)

    # -- summary ----------------------------------------------------------

    def render_table(self, info: RootHomeInfo) -> str:
        lines = [
            "Umer OS /root summary",
            "=" * 50,
            f"  path:               {info.path}",
            f"  exists:             {info.exists}",
            f"  resolved_from:      {info.resolved_from}",
            f"  owner uid/gid:      {info.uid}/{info.gid}",
            f"  mode:               {oct(info.mode) if info.mode else 'n/a'}",
            f"  file_count:         {info.file_count}",
            f"  subdirs:            {', '.join(info.subdirs) or '(none)'}",
            f"  discouraged:        {', '.join(info.discouraged_subdirs) or '(none)'}",
        ]
        if info.passwd_entry:
            lines.append(f"  /etc/passwd:        {info.passwd_entry}")
        if info.issues:
            lines.append("")
            lines.append("  issues:")
            for issue in info.issues:
                lines.append(f"    - {issue}")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    import tempfile
    # 1. Resolver.
    r = RootHomeResolver(default_path="/nope")
    path, source = r.resolve(env={})
    # Without any /etc/passwd and without env, it should still
    # produce *some* answer - either a default or the fallback.
    if not path:
        return False
    if source not in ("passwd", "env", "default", "fallback-/"):
        return False

    # 2. Audit (happy path).
    with tempfile.TemporaryDirectory() as tmp:
        root_home = Path(tmp) / "root"
        root_home.mkdir()
        root_home.chmod(ROOT_HOME_MODE)
        # Create a discouraged subdir to trigger the warning.
        (root_home / "Mail").mkdir()
        mgr = RootHomeManager(
            default_path=str(root_home),
            passwd_path=str(Path(tmp) / "passwd"),
        )
        info = mgr.audit(path=str(root_home))
        if not info.exists:
            return False
        if "Mail" not in info.discouraged_subdirs:
            return False
        if not any("discouraged" in i for i in info.issues):
            return False
        # 3. Bootstrap (no-op because the dir already exists).
        info2 = mgr.ensure(path=str(root_home))
        if not info2.exists:
            return False
        # 4. Render table.
        text = mgr.render_table(info2)
        if "Umer OS /root summary" not in text:
            return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("home selftest:", "OK" if _selftest() else "FAIL")
