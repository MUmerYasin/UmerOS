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
Umer OS /root - /etc/passwd integration
======================================
The :mod:`root.home` resolver already knows how to read ``/etc/passwd``
to find root's home directory.  This module wraps that lookup with
a tiny adapter so the rest of the runtime can:

* parse any passwd-style file (UID lookup, GECOS, shell),
* validate the root entry against expectations,
* build a *proposed* root entry when bootstrapping a fresh
  filesystem (e.g. inside an installer).

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License v3)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    class _PwdModule:
        struct_passwd = object
        def getpwnam(self, name: str) -> object: ...
    pwd: _PwdModule = None  # type: ignore[assignment]
else:
    try:
        import pwd
    except ImportError:
        pwd = None  # type: ignore[assignment]
from pathlib import Path
from typing import Iterable, List, Optional

# Gate privileged /etc/passwd writes behind the zero-trust capability
# bridge. `PasswdManager.write` (and `CanonicalRootBuilder.upsert`, which calls
# it) rewrites the system passwd file, so they must require the `sys.admin`
# capability when a CapabilityManager is wired (fail-closed).
try:
    from core.capability_gate import gate, CAP_SYS_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    import sys
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_SYS_ADMIN

log = logging.getLogger("UmerOS.Root.Passwd")

#: ``/etc/passwd`` is world-readable by design -- it holds no hashes (those
#: live in ``/etc/shadow``) and every program needs to resolve names.
PASSWD_MODE: int = 0o644

#: The ``.bak`` copy is the same account database and has no operational
#: reason to be readable, so it is owner-only.
BACKUP_MODE: int = 0o600


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PasswdEntry:
    """One row of /etc/passwd."""

    name: str
    password: str
    uid: int
    gid: int
    gecos: str
    home: str
    shell: str

    def as_line(self) -> str:
        return f"{self.name}:{self.password}:{self.uid}:{self.gid}:{self.gecos}:{self.home}:{self.shell}"

    @classmethod
    def from_struct(cls, pw: pwd.struct_passwd) -> "PasswdEntry":
        return cls(
            name=pw.pw_name,
            password=pw.pw_passwd,
            uid=pw.pw_uid,
            gid=pw.pw_gid,
            gecos=pw.pw_gecos,
            home=pw.pw_dir,
            shell=pw.pw_shell,
        )

    @classmethod
    def from_line(cls, line: str) -> "PasswdEntry":
        parts = line.rstrip("\n").split(":")
        if len(parts) != 7:
            raise ValueError(f"expected 7 colon-separated fields, got {len(parts)}")
        return cls(
            name=parts[0],
            password=parts[1],
            uid=int(parts[2]),
            gid=int(parts[3]),
            gecos=parts[4],
            home=parts[5],
            shell=parts[6],
        )


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class PasswdManager:
    """Tiny helper around the local ``/etc/passwd`` file."""

    def __init__(self, path: str = "/etc/passwd") -> None:
        self.path = Path(path)

    def read(self) -> List[PasswdEntry]:
        if not self.path.is_file():
            return []
        out: List[PasswdEntry] = []
        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            try:
                out.append(PasswdEntry.from_line(line))
            except ValueError as exc:
                log.warning("skipping malformed passwd line: %s", exc)
        return out

    def find(self, *, uid: Optional[int] = None, name: Optional[str] = None) -> Optional[PasswdEntry]:
        if uid is None and name is None:
            raise ValueError("must supply uid or name")
        # Try the pwd database first (Unix only).
        if pwd is not None:
            try:
                if uid == 0 or name == "root":
                    pw = pwd.getpwnam("root")
                    return PasswdEntry.from_struct(pw)
            except KeyError:
                pass
        # Fall back to the file.
        for entry in self.read():
            if uid is not None and entry.uid == uid:
                return entry
            if name is not None and entry.name == name:
                return entry
        return None

    def find_root(self) -> Optional[PasswdEntry]:
        return self.find(uid=0)

    def write(self, entries: Iterable[PasswdEntry], *,
              backup: bool = True) -> None:
        """Replace the file with ``entries``.  Optional owner-only backup.

        When ``backup`` is true and the file exists, the previous contents are
        copied to ``<path>.bak`` at ``BACKUP_MODE`` (0600) before the rewrite --
        see :meth:`_write_backup`.  The file itself is then written and set to
        ``PASSWD_MODE`` (0644).
        """
        # Require the system-admin capability before rewriting the
        # privileged passwd file.  Enforced fail-closed when a CapabilityManager
        # is wired; permissive (warning) when running standalone.
        gate.require(CAP_SYS_ADMIN)
        if backup and self.path.is_file():
            self._write_backup()
        body = "\n".join(e.as_line() for e in entries) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(body, encoding="utf-8")
        try:
            self.path.chmod(PASSWD_MODE)
        except OSError as exc:
            log.warning("could not chmod %s to %s: %s", self.path, oct(PASSWD_MODE), exc)

    def _write_backup(self) -> Path:
        """Copy the current file to ``<path>.bak`` with owner-only permissions.

        ``Path.write_bytes`` creates the copy under the process umask, which
        typically leaves ``/etc/passwd.bak`` at 0644 -- world-readable.  The
        contents are the same account database (names, UIDs, GECOS, home
        directories, shells), and although there are no hashes in it, a backup
        has no operational reason to be readable and tends to outlive the edit
        that created it, so it is written at ``BACKUP_MODE`` instead.

        The copy stays beside its source: a restore is then a rename, and the
        conventional ``/etc/passwd.bak`` location keeps it auditable.  The
        containing directory's mode is the caller's responsibility.

        Returns:
            The path of the backup that was written.
        """
        bak = self.path.with_suffix(self.path.suffix + ".bak")
        payload = self.path.read_bytes()
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        # Windows opens descriptors in text mode by default, which would rewrite
        # every b"\n" in the payload as b"\r\n" -- turning a CRLF source into
        # "\r\r\n" and breaking the byte-identical-copy property this backup
        # exists for.  O_BINARY is a no-op on POSIX.
        flags |= getattr(os, "O_BINARY", 0)
        fd = os.open(bak, flags, BACKUP_MODE)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        try:
            os.chmod(bak, BACKUP_MODE)
        except OSError as exc:
            log.warning("could not chmod %s to %s: %s", bak, oct(BACKUP_MODE), exc)
        log.info("backed up %s to %s", self.path, bak)
        return bak


# ---------------------------------------------------------------------------
# Builder - "canonical" root entry
# ---------------------------------------------------------------------------

@dataclass
class CanonicalRootBuilder:
    """Generate the canonical ``/etc/passwd`` root row for UmerOS.

    Centralises the *values* so the installer, the runtime, and
    the audit all agree on what "a root account" looks like.
    """

    home: str = "/root"
    shell: str = "/bin/bash"
    gecos: str = "root"
    gid: int = 0
    password: str = "x"  # shadow

    def build(self) -> PasswdEntry:
        return PasswdEntry(
            name="root",
            password=self.password,
            uid=0,
            gid=self.gid,
            gecos=self.gecos,
            home=self.home,
            shell=self.shell,
        )

    def upsert(self, manager: PasswdManager) -> PasswdEntry:
        # Require the system-admin capability before upserting the
        # root entry (which rewrites /etc/passwd via PasswdManager.write).
        gate.require(CAP_SYS_ADMIN)
        canonical = self.build()
        existing = manager.find_root()
        if existing is None:
            entries = manager.read()
            entries.append(canonical)
            manager.write(entries)
            return canonical
        if existing.home != canonical.home or existing.shell != canonical.shell:
            entries = manager.read()
            for i, e in enumerate(entries):
                if e.uid == 0:
                    entries[i] = canonical
                    break
            manager.write(entries)
        return canonical


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    import tempfile
    mgr = PasswdManager()
    # Round-trip a synthetic line.
    line = "root:x:0:0:root:/root:/bin/bash"
    e = PasswdEntry.from_line(line)
    if e.uid != 0 or e.home != "/root" or e.shell != "/bin/bash":
        return False
    if e.as_line() != line:
        return False
    # from_struct (Unix only).
    if pwd is not None:
        pw = pwd.struct_passwd(("root", "x", "0", "0", "root", "/root", "/bin/bash"))
        e2 = PasswdEntry.from_struct(pw)
        if e2.uid != 0 or e2.home != "/root":
            return False
    # File round-trip.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "passwd"
        mgr = PasswdManager(path=str(path))
        mgr.write([
            PasswdEntry("root", "x", 0, 0, "root", "/root", "/bin/bash"),
            PasswdEntry("nobody", "x", 65534, 65534, "nobody", "/nonexistent", "/usr/sbin/nologin"),
        ])
        entries = mgr.read()
        if len(entries) != 2:
            return False
        if mgr.find(uid=0).name != "root":
            return False
        if mgr.find(name="nobody").uid != 65534:
            return False
        # Builder upserts a fresh file.
        builder = CanonicalRootBuilder(home="/root", shell="/bin/zsh")
        canonical = builder.upsert(mgr)
        if canonical.shell != "/bin/zsh":
            return False
        # Backup file should exist.
        if not (Path(tmp) / "passwd.bak").is_file():
            return False
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("passwd selftest:", "OK" if _selftest() else "FAIL")
