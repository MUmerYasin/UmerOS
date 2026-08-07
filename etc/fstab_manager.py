"""
UmerOS /etc/fstab and Filesystem Table Manager.

Manages fstab, mtab, and crypttab for system filesystem configuration.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ────────────────────────────────────────────────────────────────
# Path constants
# ────────────────────────────────────────────────────────────────

FSTAB: str = "/etc/fstab"
MTAB: str = "/etc/mtab"  # symlink to /proc/self/mounts
CRYPTTAB: str = "/etc/crypttab"
FSTAB_BACKUP: str = "/etc/fstab.old"

# ────────────────────────────────────────────────────────────────
# Common mount options
# ────────────────────────────────────────────────────────────────

FSTAB_OPTIONS: List[str] = [
    "defaults",
    "ro",
    "rw",
    "noauto",
    "auto",
    "exec",
    "noexec",
    "dev",
    "nodev",
    "suid",
    "nosuid",
    "noatime",
    "relatime",
    "atime",
    "sync",
    "async",
    "dirsync",
    "nodiratime",
    "diratime",
    "nofail",
    "fail",
    "noflush",
    "flush",
    "lazytime",
    "nolazytime",
    "discard",
    "nodiscard",
    "commit=",
    "data=",
    "journal_path=",
    "barrier=",
    "nobarrier",
    "errors=continue",
    "errors=remount-ro",
    "errors=panic",
    "user",
    "nouser",
    "users",
    "x-systemd.automount",
    "x-systemd.idle-timeout=",
    "x-systemd.device-timeout=",
    "x-systemd.mount-timeout=",
    "x-systemd.requires=",
    "x-systemd.wants=",
    "x-systemd.type=",
    "bind",
    "rbind",
    "move",
    "MS_BIND",
    "MS_MOVE",
    "MS_REC",
    "remount",
    "mount=",
    "uid=",
    "gid=",
    "umask=",
    "dmask=",
    "fmask=",
    "shortname=",
    "iocharset=",
    "codepage=",
    "conv=binary",
    "conv=text",
    "conv=auto",
    "noconv",
    "tz=",
    "showexec",
    "noshowexec",
    "dotsOK",
    "nocheck",
    "check",
    "posix",
    "noperm",
    "nodev",
    "utf8",
    "shortname=lower",
    "shortname=win95",
    "shortname=winnt",
    "shortname=vfat",
]


# ────────────────────────────────────────────────────────────────
# Exceptions
# ────────────────────────────────────────────────────────────────


class FstabError(Exception):
    """Base exception for fstab manager errors."""


class FstabParseError(FstabError):
    """Raised when an fstab line cannot be parsed."""


class FstabValidationError(FstabError):
    """Raised when fstab validation fails."""


class CrypttabParseError(FstabError):
    """Raised when a crypttab line cannot be parsed."""


# ────────────────────────────────────────────────────────────────
# Data model
# ────────────────────────────────────────────────────────────────


@dataclass
class FstabEntry:
    """Represents a single fstab entry."""

    device: str
    mountpoint: str
    fstype: str = "auto"
    options: List[str] = field(default_factory=lambda: ["defaults"])
    dump: int = 0
    pass_num: int = 0
    comment: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device": self.device,
            "mountpoint": self.mountpoint,
            "fstype": self.fstype,
            "options": list(self.options),
            "dump": self.dump,
            "pass_num": self.pass_num,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FstabEntry:
        return cls(
            device=data.get("device", ""),
            mountpoint=data.get("mountpoint", ""),
            fstype=data.get("fstype", "auto"),
            options=data.get("options", ["defaults"]),
            dump=data.get("dump", 0),
            pass_num=data.get("pass_num", 0),
            comment=data.get("comment", ""),
        )

    def to_line(self) -> str:
        opts = ",".join(self.options) if isinstance(self.options, list) else self.options
        parts = [self.device, self.mountpoint, self.fstype, opts, str(self.dump), str(self.pass_num)]
        return " ".join(parts)


@dataclass
class CrypttabEntry:
    """Represents a single crypttab entry."""

    name: str
    device: str
    keyfile: str = "none"
    options: str = "luks"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "device": self.device,
            "keyfile": self.keyfile,
            "options": self.options,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CrypttabEntry:
        return cls(
            name=data.get("name", ""),
            device=data.get("device", ""),
            keyfile=data.get("keyfile", "none"),
            options=data.get("options", "luks"),
        )

    def to_line(self) -> str:
        return f"{self.name} {self.device} {self.keyfile} {self.options}"


# ────────────────────────────────────────────────────────────────
# Main manager
# ────────────────────────────────────────────────────────────────


class FstabManager:
    """
    Manages /etc/fstab, /etc/mtab, and /etc/crypttab.

    Provides methods to read, write, validate, backup, and restore
    filesystem mount tables used by UmerOS.
    """

    def __init__(
        self,
        fstab: str = FSTAB,
        mtab: str = MTAB,
        crypttab: str = CRYPTTAB,
    ) -> None:
        """
        Initialise the FstabManager.

        Parameters
        ----------
        fstab : str
            Path to the fstab file.
        mtab : str
            Path to the mtab file (usually a symlink to /proc/self/mounts).
        crypttab : str
            Path to the crypttab file.
        """
        self.fstab_path = Path(fstab)
        self.mtab_path = Path(mtab)
        self.crypttab_path = Path(crypttab)
        self.backup_dir = self.fstab_path.parent / "fstab_backups"

    # ── Fstab read / write ──────────────────────────────────────

    def _parse_fstab_file(self, path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        Parse an fstab-formatted file into a list of dicts.

        Each line may be preceded by ``# comment`` lines and inline comments
        are preserved. Blank lines and pure-comment lines are skipped.
        """
        target = path or self.fstab_path
        entries: List[Dict[str, Any]] = []

        if not target.exists():
            return entries

        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise FstabParseError(f"Cannot read {target}: {exc}") from exc

        pending_comment: str = ""
        for raw_line in text.splitlines():
            line = raw_line.rstrip()

            # Skip blank lines
            if not line.strip():
                pending_comment = ""
                continue

            # Full-line comment – accumulate for the next real entry
            if line.lstrip().startswith("#"):
                pending_comment = line.lstrip()[1:].strip()
                continue

            # Split inline comment (everything after first # not preceded by \\)
            comment = ""
            if "#" in line:
                idx = line.rfind("#")
                # Simple heuristic: treat trailing #… as inline comment
                candidate = line[idx:].strip()
                # Must have whitespace before the # to be a comment, not option
                if idx > 0 and line[idx - 1] in (" ", "\t"):
                    comment = candidate[1:].strip()
                    line = line[:idx].rstrip()

            parts = line.split()
            if len(parts) < 4:
                raise FstabParseError(
                    f"Line in {target} has fewer than 4 fields: {raw_line!r}"
                )

            device = parts[0]
            mountpoint = parts[1]
            fstype = parts[2]
            options = parts[3].split(",") if parts[3] else ["defaults"]

            dump = int(parts[4]) if len(parts) > 4 else 0
            pass_num = int(parts[5]) if len(parts) > 5 else 0

            entries.append(
                {
                    "device": device,
                    "mountpoint": mountpoint,
                    "fstype": fstype,
                    "options": options,
                    "dump": dump,
                    "pass_num": pass_num,
                    "comment": comment or pending_comment,
                }
            )
            pending_comment = ""

        return entries

    def _write_fstab_file(self, entries: List[Dict[str, Any]], path: Optional[Path] = None) -> None:
        """Serialise entry dicts back to an fstab file."""
        target = path or self.fstab_path
        lines: List[str] = []
        for entry in entries:
            e = FstabEntry.from_dict(entry)
            line = e.to_line()
            if e.comment:
                line += f"  # {e.comment}"
            lines.append(line)

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as exc:
            raise FstabError(f"Cannot write {target}: {exc}") from exc

    def get_fstab(self) -> List[Dict[str, Any]]:
        """Return parsed fstab entries as a list of dicts."""
        return self._parse_fstab_file()

    def set_fstab(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Overwrite the fstab file with *entries* (backs up first).

        Returns
        -------
        dict
            ``{"success": bool, "backup_path": str, "entry_count": int}``
        """
        backup_path = self.backup_fstab()
        self._write_fstab_file(entries)
        return {
            "success": True,
            "backup_path": str(backup_path),
            "entry_count": len(entries),
        }

    def add_entry(
        self,
        device: str,
        mountpoint: str,
        fstype: str = "auto",
        options: Optional[List[str]] = None,
        dump: int = 0,
        pass_num: int = 0,
    ) -> Dict[str, Any]:
        """
        Append a new mount entry to fstab.

        Returns
        -------
        dict
            ``{"success": bool, "entry": dict}``
        """
        entries = self.get_fstab()

        # Prevent duplicate (device, mountpoint) pairs
        for existing in entries:
            if existing["device"] == device and existing["mountpoint"] == mountpoint:
                return {
                    "success": False,
                    "error": (
                        f"Entry already exists for device={device} mountpoint={mountpoint}"
                    ),
                    "existing": existing,
                }

        new_entry = {
            "device": device,
            "mountpoint": mountpoint,
            "fstype": fstype,
            "options": options if options is not None else ["defaults"],
            "dump": dump,
            "pass_num": pass_num,
            "comment": "",
        }
        entries.append(new_entry)
        backup_path = self.backup_fstab()
        self._write_fstab_file(entries)
        return {
            "success": True,
            "entry": new_entry,
            "backup_path": str(backup_path),
        }

    def remove_entry(
        self, device: Optional[str] = None, mountpoint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Remove the first matching entry from fstab.

        At least one of *device* or *mountpoint* must be supplied.

        Returns
        -------
        dict
            ``{"success": bool, "removed": dict|None, "entry_count": int}``
        """
        if device is None and mountpoint is None:
            return {"success": False, "error": "Provide device and/or mountpoint"}

        entries = self.get_fstab()
        removed: Optional[Dict[str, Any]] = None
        new_entries: List[Dict[str, Any]] = []

        for entry in entries:
            match = True
            if device is not None and entry["device"] != device:
                match = False
            if mountpoint is not None and entry["mountpoint"] != mountpoint:
                match = False
            if match and removed is None:
                removed = entry
                continue
            new_entries.append(entry)

        if removed is None:
            return {"success": False, "error": "No matching entry found"}

        backup_path = self.backup_fstab()
        self._write_fstab_file(new_entries)
        return {
            "success": True,
            "removed": removed,
            "entry_count": len(new_entries),
            "backup_path": str(backup_path),
        }

    def update_entry(self, device: str, **kwargs: Any) -> Dict[str, Any]:
        """
        Update fields of an existing entry identified by *device*.

        Recognised keyword arguments: mountpoint, fstype, options, dump,
        pass_num, comment.

        Returns
        -------
        dict
            ``{"success": bool, "updated": dict}``
        """
        entries = self.get_fstab()
        updated: Optional[Dict[str, Any]] = None

        for i, entry in enumerate(entries):
            if entry["device"] == device:
                for key in ("mountpoint", "fstype", "options", "dump", "pass_num", "comment"):
                    if key in kwargs:
                        entry[key] = kwargs[key]
                entries[i] = entry
                updated = entry
                break

        if updated is None:
            return {"success": False, "error": f"No entry found for device={device}"}

        backup_path = self.backup_fstab()
        self._write_fstab_file(entries)
        return {"success": True, "updated": updated, "backup_path": str(backup_path)}

    def get_entry_by_device(self, device: str) -> Optional[Dict[str, Any]]:
        """Return the first fstab entry whose device matches *device*."""
        for entry in self.get_fstab():
            if entry["device"] == device:
                return entry
        return None

    def get_entry_by_mountpoint(self, mp: str) -> Optional[Dict[str, Any]]:
        """Return the first fstab entry whose mountpoint matches *mp*."""
        for entry in self.get_fstab():
            if entry["mountpoint"] == mp:
                return entry
        return None

    # ── Validation ──────────────────────────────────────────────

    def validate_fstab(self) -> Dict[str, Any]:
        """
        Run a set of basic validation checks on the current fstab.

        Returns a dict with ``{"valid": bool, "errors": list, "warnings": list}``.
        """
        errors: List[str] = []
        warnings: List[str] = []
        entries = self.get_fstab()

        if not entries:
            warnings.append("fstab is empty")

        mountpoints_seen: List[str] = []
        devices_seen: List[str] = []

        for idx, entry in enumerate(entries):
            line_num = idx + 1
            mp = entry["mountpoint"]
            dev = entry["device"]

            # Check root mount
            if mp == "/":
                has_root = True

            # Duplicate mountpoints
            if mp in mountpoints_seen:
                warnings.append(
                    f"Line {line_num}: duplicate mountpoint '{mp}'"
                )
            mountpoints_seen.append(mp)

            # Duplicate devices (not necessarily an error for bind mounts)
            if dev in devices_seen:
                warnings.append(
                    f"Line {line_num}: duplicate device '{dev}'"
                )
            devices_seen.append(dev)

            # Validate mountpoint starts with / (unless swap)
            if entry["fstype"] != "swap" and not mp.startswith("/"):
                errors.append(
                    f"Line {line_num}: mountpoint '{mp}' does not start with /"
                )

            # Validate fstype
            if entry["fstype"] not in (
                "auto", "ext2", "ext3", "ext4", "xfs", "btrfs", "zfs",
                "swap", "vfat", "ntfs", "ntfs-3g", "reiserfs", "jfs",
                "reiser4", "proc", "sysfs", "devpts", "tmpfs", "none",
                "cifs", "nfs", "nfs4", "fuseblk", "fuse.sshfs", "fuse.veracrypt",
                "fuse.gvfsd-fuse", "fuse.pikaur", "squashfs", "udf",
                "iso9660", "overlay", "bind", "fuse-overlayfs", "f2fs",
                "apfs", "exfat", "hfs", "hfsplus", "crfs", "debugfs",
                "tracefs", "securityfs", "pstore", "bpf", "cgroup",
                "cgroup2", "hugetlbfs", "mqueue", "autofs", "rpc_pipefs",
                "nfsd", "configfs", "fuseblk", "drvfs", "9p",
            ):
                warnings.append(
                    f"Line {line_num}: uncommon fstype '{entry['fstype']}'"
                )

            # Validate dump is 0 or 1
            if entry["dump"] not in (0, 1):
                errors.append(
                    f"Line {line_num}: dump field should be 0 or 1, got {entry['dump']}"
                )

            # Validate pass_num is 0-2 for non-swap
            if entry["fstype"] != "swap" and entry["pass_num"] not in (0, 1, 2):
                errors.append(
                    f"Line {line_num}: pass_num should be 0-2, got {entry['pass_num']}"
                )

        # Root is required
        has_root = "/" in mountpoints_seen
        if not has_root:
            errors.append("No root (/) mount defined in fstab")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "entry_count": len(entries),
        }

    # ── Backup / restore ────────────────────────────────────────

    def backup_fstab(self) -> Path:
        """
        Create a timestamped backup of the current fstab.

        Returns the backup path.
        """
        if not self.fstab_path.exists():
            return Path(FSTAB_BACKUP)

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"fstab.{ts}"
        shutil.copy2(str(self.fstab_path), str(backup_path))

        # Also keep the legacy fallback
        shutil.copy2(str(self.fstab_path), FSTAB_BACKUP)

        return backup_path

    def restore_fstab(self, backup_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Restore fstab from a backup file.

        Parameters
        ----------
        backup_path : str, optional
            Explicit backup file.  When *None*, the most recent backup in
            the backup directory is used, falling back to ``/etc/fstab.old``.

        Returns
        -------
        dict
            ``{"success": bool, "restored_from": str}``
        """
        source: Optional[Path] = None

        if backup_path:
            source = Path(backup_path)
            if not source.exists():
                return {"success": False, "error": f"Backup not found: {source}"}
        else:
            # Try latest in backup dir
            if self.backup_dir.exists():
                backups = sorted(self.backup_dir.glob("fstab.*"), reverse=True)
                if backups:
                    source = backups[0]

            # Fall back to /etc/fstab.old
            if source is None:
                old = Path(FSTAB_BACKUP)
                if old.exists():
                    source = old

        if source is None:
            return {"success": False, "error": "No backup found to restore from"}

        # Validate the backup before restoring
        try:
            test_entries = self._parse_fstab_file(source)
            validation = self.validate_fstab()  # current – we'll check backup
        except FstabParseError as exc:
            return {"success": False, "error": f"Backup is corrupt: {exc}"}

        try:
            shutil.copy2(str(source), str(self.fstab_path))
        except OSError as exc:
            return {"success": False, "error": f"Restore failed: {exc}"}

        return {"success": True, "restored_from": str(source)}

    # ── mtab ────────────────────────────────────────────────────

    def get_mtab(self) -> List[Dict[str, Any]]:
        """
        Read currently-mounted filesystems from ``/proc/self/mounts``.

        Falls back to ``/etc/mtab`` if the proc file is unavailable.

        Returns
        -------
        list of dict
            Keys: device, mountpoint, fstype, options.
        """
        source = Path("/proc/self/mounts")
        if not source.exists():
            source = self.mtab_path

        if not source.exists():
            return []

        try:
            text = source.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []

        entries: List[Dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 4:
                entries.append(
                    {
                        "device": parts[0],
                        "mountpoint": parts[1],
                        "fstype": parts[2],
                        "options": parts[3].split(","),
                    }
                )
        return entries

    # ── crypttab ────────────────────────────────────────────────

    def _parse_crypttab_file(self, path: Optional[Path] = None) -> List[Dict[str, Any]]:
        """
        Parse a crypttab file into a list of dicts.

        Each line: ``name device keyfile options``
        """
        target = path or self.crypttab_path
        entries: List[Dict[str, Any]] = []

        if not target.exists():
            return entries

        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise CrypttabParseError(f"Cannot read {target}: {exc}") from exc

        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()  # strip comments
            if not line:
                continue

            parts = line.split()
            if len(parts) < 3:
                raise CrypttabParseError(
                    f"Line in {target} has fewer than 3 fields: {raw_line!r}"
                )

            entries.append(
                {
                    "name": parts[0],
                    "device": parts[1],
                    "keyfile": parts[2],
                    "options": parts[3] if len(parts) > 3 else "luks",
                }
            )

        return entries

    def get_crypttab(self) -> List[Dict[str, Any]]:
        """Return parsed crypttab entries."""
        return self._parse_crypttab_file()

    def set_crypttab(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Overwrite crypttab with *entries*.

        Returns
        -------
        dict
            ``{"success": bool, "entry_count": int}``
        """
        lines: List[str] = []
        for entry in entries:
            e = CrypttabEntry.from_dict(entry)
            lines.append(e.to_line())

        try:
            self.crypttab_path.parent.mkdir(parents=True, exist_ok=True)
            self.crypttab_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as exc:
            return {"success": False, "error": f"Cannot write crypttab: {exc}"}

        return {"success": True, "entry_count": len(entries)}

    def add_crypttab_entry(
        self, name: str, device: str, keyfile: str = "none", options: str = "luks"
    ) -> Dict[str, Any]:
        """Append an entry to crypttab."""
        entries = self.get_crypttab()
        for existing in entries:
            if existing["name"] == name:
                return {
                    "success": False,
                    "error": f"Crypttab entry '{name}' already exists",
                    "existing": existing,
                }

        new_entry = {"name": name, "device": device, "keyfile": keyfile, "options": options}
        entries.append(new_entry)
        result = self.set_crypttab(entries)
        result["entry"] = new_entry
        return result

    def remove_crypttab_entry(self, name: str) -> Dict[str, Any]:
        """Remove a crypttab entry by name."""
        entries = self.get_crypttab()
        removed: Optional[Dict[str, Any]] = None
        new_entries: List[Dict[str, Any]] = []

        for entry in entries:
            if entry["name"] == name and removed is None:
                removed = entry
                continue
            new_entries.append(entry)

        if removed is None:
            return {"success": False, "error": f"No crypttab entry named '{name}'"}

        result = self.set_crypttab(new_entries)
        result["removed"] = removed
        return result

    # ── Filesystem info ─────────────────────────────────────────

    def get_filesystem_info(self, device: str) -> Dict[str, Any]:
        """
        Return filesystem information for *device* using ``df``.

        Returns a dict with size, used, available, mountpoint, fstype.
        """
        try:
            result = subprocess.run(
                ["df", "-BM", "--output=source,size,used,avail,target,fstype", device],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return {"error": f"df failed: {result.stderr.strip()}"}

            lines = result.stdout.strip().splitlines()
            if len(lines) < 2:
                return {"error": "No output from df"}

            # Header: Filesystem 1M-blocks Used Available Use% Mounted
            # We asked for custom output so second line has the data
            data = lines[1].split()
            if len(data) < 6:
                return {"error": "Unexpected df output format"}

            return {
                "device": data[0],
                "size": data[1],
                "used": data[2],
                "available": data[3],
                "mountpoint": data[4],
                "fstype": data[5],
            }
        except FileNotFoundError:
            return {"error": "df command not found"}
        except subprocess.TimeoutExpired:
            return {"error": "df command timed out"}

    def list_mounted_filesystems(self) -> List[Dict[str, Any]]:
        """
        List all mounted filesystems with size information.

        Combines mtab data with ``df`` output.
        """
        mtab = self.get_mtab()
        result: List[Dict[str, Any]] = []

        for mount in mtab:
            info: Dict[str, Any] = dict(mount)
            try:
                df = subprocess.run(
                    ["df", "-BM", "--output=size,used,avail", mount["mountpoint"]],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if df.returncode == 0:
                    lines = df.stdout.strip().splitlines()
                    if len(lines) >= 2:
                        parts = lines[1].split()
                        if len(parts) >= 3:
                            info["size"] = parts[0]
                            info["used"] = parts[1]
                            info["available"] = parts[2]
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

            result.append(info)

        return result

    # ── Presets ─────────────────────────────────────────────────

    def get_common_presets(self) -> Dict[str, Dict[str, Any]]:
        """
        Return preset mount configurations for common mountpoints.

        Returns
        -------
        dict
            Mapping of mountpoint name → preset configuration dict.
        """
        return {
            "/": {
                "fstype": "ext4",
                "options": ["defaults", "errors=remount-ro"],
                "dump": 0,
                "pass_num": 1,
                "description": "Root filesystem",
            },
            "/home": {
                "fstype": "ext4",
                "options": ["defaults", "noatime"],
                "dump": 0,
                "pass_num": 2,
                "description": "User home directories",
            },
            "/boot": {
                "fstype": "ext4",
                "options": ["defaults", "noatime"],
                "dump": 0,
                "pass_num": 1,
                "description": "Boot partition (kernel, initramfs)",
            },
            "/boot/efi": {
                "fstype": "vfat",
                "options": ["defaults", "umask=0077", "noatime"],
                "dump": 0,
                "pass_num": 1,
                "description": "EFI System Partition (ESP)",
            },
            "/tmp": {
                "fstype": "tmpfs",
                "options": ["defaults", "noatime", "noexec", "nodev", "nosuid", "size=2G"],
                "dump": 0,
                "pass_num": 0,
                "description": "Temporary files (RAM-backed)",
            },
            "swap": {
                "fstype": "swap",
                "options": ["defaults"],
                "dump": 0,
                "pass_num": 0,
                "description": "Swap partition",
            },
            "/var": {
                "fstype": "ext4",
                "options": ["defaults", "noatime", "nodev", "nosuid"],
                "dump": 0,
                "pass_num": 2,
                "description": "Variable data (logs, caches)",
            },
            "/var/tmp": {
                "fstype": "tmpfs",
                "options": ["defaults", "noatime", "noexec", "nodev", "nosuid", "size=1G"],
                "dump": 0,
                "pass_num": 0,
                "description": "Persistent temporary files",
            },
            "/dev/shm": {
                "fstype": "tmpfs",
                "options": ["defaults", "noexec", "nodev", "nosuid", "size=50%"],
                "dump": 0,
                "pass_num": 0,
                "description": "POSIX shared memory",
            },
            "/run": {
                "fstype": "tmpfs",
                "options": ["defaults", "noexec", "nodev", "nosuid", "mode=0755"],
                "dump": 0,
                "pass_num": 0,
                "description": "Runtime state (PID files, sockets)",
            },
            "/proc": {
                "fstype": "proc",
                "options": ["defaults", "nosuid", "noexec", "nodev"],
                "dump": 0,
                "pass_num": 0,
                "description": "Process information pseudo-filesystem",
            },
            "/sys": {
                "fstype": "sysfs",
                "options": ["defaults", "nosuid", "noexec", "nodev", "ro"],
                "dump": 0,
                "pass_num": 0,
                "description": "Kernel/sysfs pseudo-filesystem",
            },
            "/dev": {
                "fstype": "devtmpfs",
                "options": ["defaults", "nosuid", "noexec", "mode=0755"],
                "dump": 0,
                "pass_num": 0,
                "description": "Device nodes pseudo-filesystem",
            },
        }

    # ── Status / export ─────────────────────────────────────────

    def export_status(self) -> Dict[str, Any]:
        """
        Return a comprehensive status dict of all managed tables.

        Includes fstab entries, crypttab entries, mounted filesystems,
        validation results, and file metadata.
        """
        fstab_entries = self.get_fstab()
        crypttab_entries = self.get_crypttab()
        mounted = self.get_mtab()
        validation = self.validate_fstab()

        fstab_meta: Dict[str, Any] = {}
        if self.fstab_path.exists():
            stat = self.fstab_path.stat()
            fstab_meta = {
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "permissions": oct(stat.st_mode)[-3:],
            }

        crypttab_meta: Dict[str, Any] = {}
        if self.crypttab_path.exists():
            stat = self.crypttab_path.stat()
            crypttab_meta = {
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "permissions": oct(stat.st_mode)[-3:],
            }

        backup_list: List[str] = []
        if self.backup_dir.exists():
            backup_list = sorted(
                str(p.name) for p in self.backup_dir.glob("fstab.*")
            )

        return {
            "fstab": {
                "path": str(self.fstab_path),
                "meta": fstab_meta,
                "entries": fstab_entries,
                "validation": validation,
            },
            "crypttab": {
                "path": str(self.crypttab_path),
                "meta": crypttab_meta,
                "entries": crypttab_entries,
            },
            "mtab": {
                "path": str(self.mtab_path),
                "mounted_count": len(mounted),
            },
            "backups": backup_list,
            "snapshot_time": datetime.now().isoformat(),
        }

    def backup_all(self, backup_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a full backup of fstab and crypttab to *backup_path*.

        Parameters
        ----------
        backup_path : str, optional
            Directory to write backups into.  Defaults to
            ``<fstab_parent>/fstab_backups/<timestamp>/``.

        Returns
        -------
        dict
            ``{"success": bool, "backed_up": list}``
        """
        if backup_path:
            dest = Path(backup_path)
        else:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = self.backup_dir / ts

        dest.mkdir(parents=True, exist_ok=True)
        backed_up: List[str] = []

        for src in (self.fstab_path, self.crypttab_path):
            if src.exists():
                dst = dest / src.name
                shutil.copy2(str(src), str(dst))
                backed_up.append(str(dst))

        return {"success": True, "backed_up": backed_up, "destination": str(dest)}


# ────────────────────────────────────────────────────────────────
# Convenience helpers
# ────────────────────────────────────────────────────────────────


def create_manager(
    fstab: str = FSTAB,
    mtab: str = MTAB,
    crypttab: str = CRYPTTAB,
) -> FstabManager:
    """Factory function to create an FstabManager with default paths."""
    return FstabManager(fstab=fstab, mtab=mtab, crypttab=crypttab)


def validate_mount_options(options_str: str) -> Tuple[bool, List[str]]:
    """
    Validate a comma-separated mount options string.

    Returns
    -------
    (bool, list)
        ``True`` if valid; otherwise ``False`` and a list of invalid options.
    """
    opts = [o.strip() for o in options_str.split(",") if o.strip()]
    invalid: List[str] = []

    # Options that accept a value (key=value)
    valued_prefixes = (
        "commit=", "data=", "journal_path=", "errors=", "mount=", "uid=",
        "gid=", "umask=", "dmask=", "fmask=", "shortname=", "iocharset=",
        "codepage=", "tz=", "size=", "mode=", "nr_blocks=", "nr_inodes=",
        "x-systemd.", "x-gvfs.",
    )

    for opt in opts:
        # Check for key=value options
        if "=" in opt:
            key = opt.split("=", 1)[0]
            if any(opt.startswith(vp) for vp in valued_prefixes) or key in (
                "commit", "data", "journal_path", "errors", "mount",
                "uid", "gid", "umask", "dmask", "fmask", "shortname",
                "iocharset", "codepage", "tz", "size", "mode",
                "nr_blocks", "nr_inodes", "x-systemd", "x-gvfs",
            ):
                continue
            # Check if key is a known option that takes a value
            if opt in FSTAB_OPTIONS:
                continue
            invalid.append(opt)
            continue

        if opt not in FSTAB_OPTIONS:
            invalid.append(opt)

    return len(invalid) == 0, invalid


# ────────────────────────────────────────────────────────────────
# CLI entry point
# ────────────────────────────────────────────────────────────────


def main() -> None:
    """Minimal CLI for inspecting and validating fstab/crypttab."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="UmerOS /etc/fstab and crypttab manager",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    sub.add_parser("show", help="Display fstab entries")
    sub.add_parser("show-crypttab", help="Display crypttab entries")
    sub.add_parser("show-mtab", help="Display mounted filesystems")
    sub.add_parser("validate", help="Validate fstab")
    sub.add_parser("presets", help="Show common mount presets")
    sub.add_parser("status", help="Full system status")
    sub.add_parser("backup", help="Backup fstab and crypttab")

    args = parser.parse_args()
    mgr = create_manager()

    if args.command == "show":
        print(json.dumps(mgr.get_fstab(), indent=2))

    elif args.command == "show-crypttab":
        print(json.dumps(mgr.get_crypttab(), indent=2))

    elif args.command == "show-mtab":
        print(json.dumps(mgr.get_mtab(), indent=2))

    elif args.command == "validate":
        result = mgr.validate_fstab()
        print(json.dumps(result, indent=2))

    elif args.command == "presets":
        print(json.dumps(mgr.get_common_presets(), indent=2))

    elif args.command == "status":
        print(json.dumps(mgr.export_status(), indent=2))

    elif args.command == "backup":
        result = mgr.backup_all()
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
