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
UmerOS /mnt - /etc/fstab Parser and Writer
===========================================

Parses and writes the ``/etc/fstab`` file that defines static
filesystem information for the system.  Each line has six fields:

    <device>  <mount point>  <type>  <options>  <dump>  <pass>

This is the central configuration for:

* Automatic mounts at boot (``mount -a``)
* User-mountable filesystems (``user`` option)
* Filesystem check order (``pass`` field)
* Backup frequency (``dump`` field)

/mnt interaction:

    /mnt is provided so that the system administrator may temporarily
    mount a filesystem as needed.  The content of this directory is a
    local issue and should not affect the manner in which any program
    is run.

fstab entries with mount points under /mnt define what the admin
can temporarily mount using ``mount /mnt/<name>``.

Author:  Umer OS Project
License: GPL-3.0 (GNU General Public License Version 3)
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Sequence

log = logging.getLogger("UmerOS.Mnt.Fstab")

# [FIX H166] Gate the privileged write of /etc/fstab behind the zero-trust
# capability bridge (core/capability_gate). fstab is boot-critical static
# filesystem config; rewriting it must require the `fs.admin` capability when a
# CapabilityManager is wired (fail-closed). When no manager is wired the gate
# stays permissive (warning) so existing flows keep working.
try:
    from core.capability_gate import gate, CAP_FS_ADMIN
except Exception:  # pragma: no cover - standalone fallback
    import sys
    _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _proj not in sys.path:
        sys.path.insert(0, _proj)
    from core.capability_gate import gate, CAP_FS_ADMIN


# ---------------------------------------------------------------------------
# fstab field constants
# ---------------------------------------------------------------------------

class DumpFrequency(int, Enum):
    """Backup frequency for the ``dump`` field."""
    NO_BACKUP = 0
    BACKUP = 1
    EXCLUDE = 2


class FsckPass(int, Enum):
    """Filesystem check order for the ``pass`` field.

    0 = skip, 1 = root filesystem first, 2+ = checked after 1.
    """
    SKIP = 0
    ROOT_FIRST = 1


# ---------------------------------------------------------------------------
# Fstab entry
# ---------------------------------------------------------------------------

@dataclass
class FstabEntry:
    """One line of ``/etc/fstab``.

    Attributes:
        device:       Block device path (``/dev/sda1``) or special
                      name (``swap``, ``tmpfs``, ``UUID=...``).
        mount_point:  Absolute path where the filesystem is mounted.
        fstype:       Filesystem type string (``ext4``, ``vfat``,
                      ``nfs``, etc.).
        options:      Comma-separated mount options string.
        dump:         Backup frequency (0 or 1).
        pass_num:     Filesystem check order (0, 1, or 2+).
        _raw_line:    Original source line (preserved for round-trip).
        _line_num:    Line number in the source file (for diagnostics).
    """

    device: str
    mount_point: str
    fstype: str
    options: str = "defaults"
    dump: int = 0
    pass_num: int = 0
    _raw_line: str = ""
    _line_num: int = 0

    # -- Derived properties --------------------------------------------------

    @property
    def is_noauto(self) -> bool:
        """True if this entry should NOT be mounted at boot."""
        return "noauto" in self.options_list

    @property
    def is_user_mount(self) -> True:
        """True if non-root users may mount this filesystem."""
        return "user" in self.options_list or "users" in self.options_list

    @property
    def is_readonly(self) -> bool:
        """True if the ``ro`` option is set."""
        return "ro" in self.options_list

    @property
    def is_nosuid(self) -> bool:
        return "nosuid" in self.options_list

    @property
    def is_nodev(self) -> bool:
        return "nodev" in self.options_list

    @property
    def is_noexec(self) -> bool:
        return "noexec" in self.options_list

    @property
    def options_list(self) -> List[str]:
        """Split ``options`` string into a list."""
        return [o.strip() for o in self.options.split(",") if o.strip()]

    @property
    def is_under_mnt(self) -> bool:
        """True if the mount point is under ``/mnt``."""
        return self.mount_point.startswith("/mnt/")

    @property
    def is_swap(self) -> bool:
        return self.fstype == "swap"

    @property
    def is_network(self) -> bool:
        """True for network filesystem types."""
        return self.fstype in ("nfs", "nfs4", "cifs", "smbfs", "sshfs", "fuse.sshfs")

    # -- Methods -------------------------------------------------------------

    def to_line(self) -> str:
        """Render as an fstab-formatted line."""
        return (
            f"{self.device}\t{self.mount_point}\t{self.fstype}\t"
            f"{self.options}\t{self.dump}\t{self.pass_num}"
        )

    def as_dict(self) -> dict:
        return {
            "device": self.device,
            "mount_point": self.mount_point,
            "fstype": self.fstype,
            "options": self.options,
            "dump": self.dump,
            "pass_num": self.pass_num,
            "is_noauto": self.is_noauto,
            "is_user_mount": self.is_user_mount,
            "is_readonly": self.is_readonly,
            "is_under_mnt": self.is_under_mnt,
            "is_network": self.is_network,
        }

    def __repr__(self) -> str:
        return (
            f"FstabEntry(device={self.device!r}, "
            f"mount_point={self.mount_point!r}, "
            f"fstype={self.fstype!r})"
        )


# ---------------------------------------------------------------------------
# fstab class
# ---------------------------------------------------------------------------

class Fstab:
    """In-memory representation of ``/etc/fstab``.

    Provides parsing, querying, modification, and serialization.

    Usage::

        fstab = Fstab.from_file("/etc/fstab")
        mnt_entries = fstab.list_under("/mnt")
        fstab.add(FstabEntry("/dev/sdb1", "/mnt/usb", "vfat",
                             "user,noauto,uid=1000,gid=100,umask=022",
                             0, 0))
        fstab.write_file("/etc/fstab")
    """

    def __init__(self, entries: Optional[List[FstabEntry]] = None) -> None:
        self._entries: List[FstabEntry] = list(entries or [])
        self._comments: List[str] = []
        self._header: str = ""
        self._source_path: Optional[str] = None

    # -- Factory -------------------------------------------------------------

    @classmethod
    def from_file(cls, path: str | Path) -> Fstab:
        """Parse an fstab file from disk."""
        path = str(path)
        fstab = cls()
        fstab._source_path = path

        try:
            with open(path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
        except FileNotFoundError:
            log.warning("fstab file not found: %s", path)
            return fstab
        except PermissionError:
            log.error("Permission denied reading fstab: %s", path)
            return fstab

        for i, raw_line in enumerate(lines, 1):
            line = raw_line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                if line.startswith("#"):
                    fstab._comments.append(line)
                continue

            entry = _parse_line(line, line_num=i)
            if entry is not None:
                fstab._entries.append(entry)

        log.info("Parsed %d entries from %s", len(fstab._entries), path)
        return fstab

    @classmethod
    def from_string(cls, text: str) -> Fstab:
        """Parse fstab content from a string (useful for testing)."""
        fstab = cls()
        for i, raw_line in enumerate(text.splitlines(), 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                # [FIX H168] Capture comments here too so a round-trip through
                # from_string() -> to_string() no longer silently drops them.
                if line.startswith("#"):
                    fstab._comments.append(line)
                continue
            entry = _parse_line(line, line_num=i)
            if entry is not None:
                fstab._entries.append(entry)
        return fstab

    # -- Queries -------------------------------------------------------------

    @property
    def entries(self) -> List[FstabEntry]:
        """All entries (read-only view)."""
        return list(self._entries)

    def list_under(self, prefix: str = "/mnt") -> List[FstabEntry]:
        """Return entries whose mount point is under *prefix*."""
        return [e for e in self._entries if e.mount_point.startswith(prefix)]

    def find_by_mount(self, mount_point: str) -> Optional[FstabEntry]:
        """Look up an entry by its mount point."""
        for e in self._entries:
            if e.mount_point == mount_point:
                return e
        return None

    def find_by_device(self, device: str) -> List[FstabEntry]:
        """Look up entries by device path (may be multiple)."""
        return [e for e in self._entries if e.device == device]

    def find_by_fstype(self, fstype: str) -> List[FstabEntry]:
        return [e for e in self._entries if e.fstype == fstype]

    def find_noauto(self) -> List[FstabEntry]:
        """Return entries that will NOT be auto-mounted."""
        return [e for e in self._entries if e.is_noauto]

    def find_user_mounts(self) -> List[FstabEntry]:
        """Return entries that allow non-root mounting."""
        return [e for e in self._entries if e.is_user_mount]

    def find_network(self) -> List[FstabEntry]:
        """Return network filesystem entries."""
        return [e for e in self._entries if e.is_network]

    def find_swap(self) -> List[FstabEntry]:
        return [e for e in self._entries if e.is_swap]

    def find_by_fsck_order(self) -> List[FstabEntry]:
        """Entries sorted by fsck pass number (skipped entries last)."""
        return sorted(self._entries, key=lambda e: (e.pass_num == 0, e.pass_num))

    # -- Modification --------------------------------------------------------

    def add(self, entry: FstabEntry) -> None:
        """Add a new entry.  Duplicates by mount_point are rejected."""
        if self.find_by_mount(entry.mount_point):
            raise ValueError(
                f"fstab already has an entry for {entry.mount_point}"
            )
        self._entries.append(entry)
        log.info("fstab add: %s", entry)

    def remove(self, mount_point: str) -> Optional[FstabEntry]:
        """Remove an entry by mount point.  Returns removed entry."""
        for i, e in enumerate(self._entries):
            if e.mount_point == mount_point:
                removed = self._entries.pop(i)
                log.info("fstab remove: %s", removed)
                return removed
        return None

    def update(self, mount_point: str, **kwargs) -> Optional[FstabEntry]:
        """Update fields on an existing entry.

        Supported kwargs: device, fstype, options, dump, pass_num.
        """
        entry = self.find_by_mount(mount_point)
        if entry is None:
            return None
        for key, val in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, val)
        log.info("fstab update: %s", entry)
        return entry

    # -- Serialization -------------------------------------------------------

    def to_string(self) -> str:
        """Render the fstab as a string.

        [FIX H168] Comments and the header captured by ``from_file`` /
        ``from_string`` are preserved (they used to be dropped on write,
        destroying operator documentation in the boot-critical
        ``/etc/fstab``). Entry lines follow the comment block.
        """
        parts: List[str] = []
        if self._header:
            parts.append(self._header)
        parts.extend(self._comments)
        for e in self._entries:
            parts.append(e.to_line())
        rendered = "\n".join(p for p in parts if p != "")
        return rendered + "\n" if rendered else ""

    def write_file(self, path: str | Path, backup: bool = True) -> None:
        """Write the fstab to disk.

        If *backup* is True, the existing file is renamed to
        ``<path>.bak`` before writing.
        """
        # [FIX H166] Writing /etc/fstab is a privileged, boot-critical operation;
        # require the fs.admin capability (fail-closed when a manager is wired).
        gate.require(CAP_FS_ADMIN)

        path = str(path)
        if backup and os.path.exists(path):
            bak = path + ".bak"
            try:
                os.replace(path, bak)
                log.info("fstab backup: %s -> %s", path, bak)
            except OSError as exc:
                log.error("Failed to backup fstab: %s", exc)

        content = self.to_string()
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            log.info("Wrote %d entries to %s", len(self._entries), path)
        except PermissionError:
            log.error("Permission denied writing fstab: %s", path)
            raise

    # -- Stats ---------------------------------------------------------------

    @property
    def stats(self) -> Dict[str, int]:
        """Summary counts."""
        return {
            "total": len(self._entries),
            "noauto": len(self.find_noauto()),
            "user_mounts": len(self.find_user_mounts()),
            "network": len(self.find_network()),
            "swap": len(self.find_swap()),
            "under_mnt": len(self.list_under("/mnt")),
        }


# ---------------------------------------------------------------------------
# Line parser
# ---------------------------------------------------------------------------

def _parse_line(line: str, line_num: int = 0) -> Optional[FstabEntry]:
    """Parse a single non-comment fstab line.

    Fields are whitespace-separated (tabs or spaces).  The options
    field may contain commas but not whitespace.
    """
    # Split on whitespace (2+ whitespace chars separate fields)
    parts = re.split(r"\s{2,}", line.strip())
    if len(parts) < 4:
        # Try splitting on single whitespace for compact format
        parts = line.strip().split()
    if len(parts) < 4:
        log.warning(
            "fstab line %d: too few fields (%d): %s",
            line_num, len(parts), line.strip(),
        )
        return None

    device = parts[0]
    mount_point = parts[1]
    fstype = parts[2]
    options = parts[3] if len(parts) > 3 else "defaults"
    dump = int(parts[4]) if len(parts) > 4 else 0
    pass_num = int(parts[5]) if len(parts) > 5 else 0

    if not mount_point.startswith("/"):
        log.warning(
            "fstab line %d: mount point %r does not start with /",
            line_num, mount_point,
        )

    return FstabEntry(
        device=device,
        mount_point=mount_point,
        fstype=fstype,
        options=options,
        dump=dump,
        pass_num=pass_num,
        _raw_line=line,
        _line_num=line_num,
    )


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def make_fstab_entry(
    device: str,
    mount_point: str,
    fstype: str,
    *,
    options: str = "defaults",
    dump: int = 0,
    pass_num: int = 0,
) -> FstabEntry:
    """Quick constructor for an :class:`FstabEntry`."""
    return FstabEntry(
        device=device,
        mount_point=mount_point,
        fstype=fstype,
        options=options,
        dump=dump,
        pass_num=pass_num,
    )


def make_user_mount(
    device: str,
    mount_point: str,
    fstype: str,
    *,
    uid: Optional[int] = None,
    gid: Optional[int] = None,
    umask: Optional[str] = None,
    ro: bool = False,
) -> FstabEntry:
    """Create a user-mountable fstab entry.

    This is the TLDP-recommended way to let non-root users mount
    devices::

        /dev/fd0 /floppy msdos user,noauto 0 0
    """
    opts = ["user", "noauto", "nosuid", "nodev"]
    if ro:
        opts.append("ro")
    if uid is not None:
        opts.append(f"uid={uid}")
    if gid is not None:
        opts.append(f"gid={gid}")
    if umask is not None:
        opts.append(f"umask={umask}")

    return FstabEntry(
        device=device,
        mount_point=mount_point,
        fstype=fstype,
        options=",".join(opts),
        dump=0,
        pass_num=0,
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Validate fstab parsing and serialization."""
    sample = (
        "# /etc/fstab\n"
        "# <device> <mount> <type> <options> <dump> <pass>\n"
        "/dev/sda1 / ext4 defaults 0 1\n"
        "/dev/sda2 none swap sw 0 0\n"
        "tmpfs /tmp tmpfs defaults,noexec,nosuid,nodev 0 0\n"
        "/dev/fd0 /mnt/floppy msdos user,noauto 0 0\n"
        "/dev/sdb1 /mnt/usb vfat user,noauto,uid=1000,gid=100 0 0\n"
        "server:/share /mnt/nfs nfs noauto,soft,intr 0 0\n"
    )

    fstab = Fstab.from_string(sample)

    # Should parse 6 entries.
    if len(fstab.entries) != 6:
        print(f"Expected 6 entries, got {len(fstab.entries)}")
        return False

    # Check root entry.
    root = fstab.find_by_mount("/")
    if root is None:
        print("Root entry not found")
        return False
    if root.fstype != "ext4":
        print(f"Root fstype: expected ext4, got {root.fstype}")
        return False

    # Check noauto entries.
    noauto = fstab.find_noauto()
    if len(noauto) != 3:
        print(f"Expected 3 noauto, got {len(noauto)}")
        return False

    # Check user mounts.
    user_mounts = fstab.find_user_mounts()
    if len(user_mounts) != 2:
        print(f"Expected 2 user mounts, got {len(user_mounts)}")
        return False

    # Check under /mnt.
    mnt = fstab.list_under("/mnt")
    if len(mnt) != 3:
        print(f"Expected 3 /mnt entries, got {len(mnt)}")
        return False

    # Check network mounts.
    net = fstab.find_network()
    if len(net) != 1:
        print(f"Expected 1 network mount, got {len(net)}")
        return False

    # Round-trip test.
    output = fstab.to_string()
    fstab2 = Fstab.from_string(output)
    if len(fstab2.entries) != 6:
        print(f"Round-trip failed: {len(fstab2.entries)} entries")
        return False

    # Add/remove test.
    fstab.add(make_fstab_entry("/dev/sdc1", "/mnt/test", "ext4"))
    if fstab.find_by_mount("/mnt/test") is None:
        print("Add failed")
        return False
    fstab.remove("/mnt/test")
    if fstab.find_by_mount("/mnt/test") is not None:
        print("Remove failed")
        return False

    # User mount helper test.
    user_entry = make_user_mount(
        "/dev/fd0", "/mnt/dosfloppy", "msdos",
        uid=1000, gid=100,
    )
    if not user_entry.is_user_mount:
        print("make_user_mount: is_user_mount is False")
        return False
    if not user_entry.is_noauto:
        print("make_user_mount: is_noauto is False")
        return False
    if "uid=1000" not in user_entry.options:
        print("make_user_mount: uid not in options")
        return False

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("fstab selftest:", "OK" if _selftest() else "FAIL")
