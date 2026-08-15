"""
Umer OS /root - /etc/passwd integration
======================================
The :mod:`root.home` resolver already knows how to read ``/etc/passwd``
to find root's home directory.  This module wraps that lookup with
a tiny adapter so the rest of the runtime can:

* parse any passwd-style file (UID lookup, GECOS, shell),
* validate the root entry against FHS / TLDP expectations,
* build a *proposed* root entry when bootstrapping a fresh
  filesystem (e.g. inside an installer).

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import pwd
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

log = logging.getLogger("UmerOS.Root.Passwd")


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
        # Try the pwd database first.
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
        """Replace the file with ``entries``.  Optional backup."""
        if backup and self.path.is_file():
            bak = self.path.with_suffix(self.path.suffix + ".bak")
            bak.write_bytes(self.path.read_bytes())
        body = "\n".join(e.as_line() for e in entries) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(body, encoding="utf-8")
        try:
            self.path.chmod(0o644)
        except OSError:
            pass


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
    # from_struct
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
