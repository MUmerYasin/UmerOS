"""
UmerOS /mnt - Temporary Mount Point Management
===============================================

Provides lifecycle management for temporary mount points under
``/mnt/``.  The TLDP spec says:

    /mnt is the system administrator's temporary mount point.

This module handles:

* Creating temporary mount point directories under ``/mnt``.
* Naming conventions (e.g., ``/mnt/<device-short-name>``).
* Cleanup of stale/empty mount points.
* Validation that paths are within ``/mnt/``.
* Auto-naming when the admin provides no explicit name.

FHS 3.0 compliance:

    The content of this directory is a local issue and should not
    affect the manner in which any program is run.  Installation
    programs must not use this directory.

This module ensures:

1. Mount points are created only under ``/mnt/``.
2. Mount points are proper directories (not files or symlinks).
3. No leftover stale mount points remain after unmount.

Author:  Umer OS Project
Licence: Apache 2.0
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

log = logging.getLogger("UmerOS.Mnt.MountPoint")

# Base directory for temporary admin mounts
MNT_ROOT = "/mnt"


# ---------------------------------------------------------------------------
# Mount point record
# ---------------------------------------------------------------------------

@dataclass
class MountPoint:
    """Metadata for a temporary mount point under ``/mnt/``.

    Attributes:
        path:           Absolute path (e.g. ``/mnt/usb``).
        purpose:        Human-readable description.
        device:         Block device mounted here (if any).
        fstype:         Filesystem type (if known).
        created_at:     Creation timestamp.
        mounted_at:     When the filesystem was mounted (None = not mounted).
        is_permanent:   If True, survive cleanup sweeps.
    """
    path: str
    purpose: str = ""
    device: str = ""
    fstype: str = ""
    created_at: float = field(default_factory=time.time)
    mounted_at: Optional[float] = None
    is_permanent: bool = False

    @property
    def name(self) -> str:
        """Short name relative to /mnt/."""
        p = self.path.rstrip("/")
        if p.startswith(MNT_ROOT + "/"):
            return p[len(MNT_ROOT) + 1:]
        # Fallback: use the last path component
        return Path(p).name

    @property
    def is_mounted(self) -> bool:
        return self.mounted_at is not None

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    def as_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "name": self.name,
            "purpose": self.purpose,
            "device": self.device,
            "fstype": self.fstype,
            "created_at": self.created_at,
            "mounted_at": self.mounted_at,
            "is_permanent": self.is_permanent,
            "is_mounted": self.is_mounted,
            "age_seconds": self.age_seconds,
        }


# ---------------------------------------------------------------------------
# Mount point manager
# ---------------------------------------------------------------------------

class MountPointManager:
    """Manages temporary mount points under ``/mnt/``.

    Usage::

        mgr = MountPointManager("/mnt")
        mp = mgr.create("usb", purpose="USB flash drive")
        # ... mount filesystem to mp.path ...
        mp.mounted_at = time.time()
        # ... use filesystem ...
        mgr.mark_unmounted(mp.path)
        mgr.remove(mp.path)

    Features:

    * Enforces ``/mnt/`` prefix (no escaping).
    * Auto-generates unique names from device paths.
    * Tracks lifecycle: created → mounted → unmounted → removed.
    * Cleans stale mount points older than a threshold.
    """

    def __init__(
        self,
        mnt_root: str | Path = MNT_ROOT,
        *,
        max_age_seconds: float = 86400.0,   # 24 hours default
        enforce_prefix: bool = True,
    ) -> None:
        self._mnt_root = str(mnt_root).rstrip("/")
        self._max_age = max_age_seconds
        self._enforce_prefix = enforce_prefix
        self._points: Dict[str, MountPoint] = {}
        self._scan_existing()

    # -- Scan ----------------------------------------------------------------

    def _scan_existing(self) -> None:
        """Discover existing directories under /mnt/."""
        root = Path(self._mnt_root)
        if not root.is_dir():
            log.warning("mnt root does not exist: %s", self._mnt_root)
            return

        for entry in root.iterdir():
            if entry.is_dir() and entry.name not in (".", ".."):
                if entry.name not in self._points:
                    self._points[entry.name] = MountPoint(
                        path=str(entry),
                        purpose="(existing)",
                    )

        log.debug("Scanned %d mount points under %s", len(self._points), self._mnt_root)

    # -- Validation ----------------------------------------------------------

    def _validate_path(self, path: str) -> None:
        """Ensure *path* is within the mnt root."""
        if not self._enforce_prefix:
            return
        norm = os.path.normpath(path)
        if not norm.startswith(self._mnt_root + "/") and norm != self._mnt_root:
            raise MountPointError(
                f"Mount point {path!r} is not under {self._mnt_root}"
            )

    def _validate_name(self, name: str) -> None:
        """Check that a name is safe for use as a directory."""
        if not re.match(r"^[a-zA-Z0-9._-]+$", name):
            raise MountPointError(
                f"Invalid mount point name: {name!r} "
                f"(only alphanumeric, dot, dash, underscore allowed)"
            )

    # -- Create --------------------------------------------------------------

    def create(
        self,
        name: str | None = None,
        *,
        device: str = "",
        fstype: str = "",
        purpose: str = "",
        mode: int = 0o755,
    ) -> MountPoint:
        """Create a new temporary mount point under ``/mnt/``.

        If *name* is None, one is generated from the device path.

        Returns:
            The new :class:`MountPoint`.

        Raises:
            MountPointError: If the path already exists or is invalid.
        """
        if name is None:
            name = self._auto_name(device)

        self._validate_name(name)
        path = f"{self._mnt_root}/{name}"

        self._validate_path(path)

        if path in [mp.path for mp in self._points.values()]:
            raise MountPointError(f"Mount point already exists: {path}")

        # Create directory
        try:
            os.makedirs(path, mode=mode, exist_ok=False)
            log.info("Created mount point: %s", path)
        except FileExistsError:
            raise MountPointError(f"Path already exists: {path}")
        except PermissionError:
            raise MountPointError(f"Permission denied creating: {path}")

        mp = MountPoint(
            path=path,
            purpose=purpose,
            device=device,
            fstype=fstype,
        )
        self._points[name] = mp
        return mp

    def _auto_name(self, device: str) -> str:
        """Generate a name from a device path.

        Examples:
            ``/dev/sdb1`` → ``sdb1``
            ``/dev/nvme0n1p2`` → ``nvme0n1p2``
            ``server:/share`` → ``nfs-server-share``
            ``UUID=abc-def`` → ``uuid-abc-def``
        """
        if device.startswith("UUID="):
            return "uuid-" + device[5:].replace("-", "")[:20]
        if device.startswith("LABEL="):
            return "label-" + device[6:].lower().replace(" ", "-")[:20]
        if device.startswith("/"):
            # Local block device — use basename
            name = os.path.basename(device)
            return re.sub(r"[^a-zA-Z0-9._-]", "", name) or "unknown"
        if ":" in device:
            # Network mount like server:/share
            clean = device.replace("/", "-").replace(":", "-")
            return "nfs-" + clean.strip("-")[:20]
        # Block device without path (e.g. "sdb1")
        name = os.path.basename(device)
        return re.sub(r"[^a-zA-Z0-9._-]", "", name) or "unknown"

    # -- Mark state ----------------------------------------------------------

    def mark_mounted(self, path: str) -> Optional[MountPoint]:
        """Record that a mount point is now mounted."""
        mp = self._find_by_path(path)
        if mp:
            mp.mounted_at = time.time()
            log.info("Marked mounted: %s", path)
        return mp

    def mark_unmounted(self, path: str) -> Optional[MountPoint]:
        """Record that a mount point has been unmounted."""
        mp = self._find_by_path(path)
        if mp:
            mp.mounted_at = None
            log.info("Marked unmounted: %s", path)
        return mp

    # -- Remove --------------------------------------------------------------

    def remove(self, path: str, *, force: bool = False) -> bool:
        """Remove a mount point directory.

        If *force* is True, removes even if the directory is non-empty.

        Returns True if removed, False otherwise.
        """
        mp = self._find_by_path(path)
        if mp is None:
            log.warning("Mount point not tracked: %s", path)
            return False

        if mp.is_permanent and not force:
            log.warning("Refusing to remove permanent mount point: %s", path)
            return False

        dirpath = Path(path)
        if not dirpath.exists():
            log.info("Mount point already gone: %s", path)
            self._remove_tracking(path)
            return True

        try:
            # Try clean removal first
            os.rmdir(path)
            log.info("Removed mount point: %s", path)
        except OSError:
            if force:
                import shutil
                shutil.rmtree(path)
                log.info("Force-removed mount point: %s", path)
            else:
                log.warning("Mount point not empty: %s (use force=True)", path)
                return False

        self._remove_tracking(path)
        return True

    def _remove_tracking(self, path: str) -> None:
        norm = os.path.normpath(path)
        for name, mp in list(self._points.items()):
            if os.path.normpath(mp.path) == norm:
                del self._points[name]
                break

    # -- Query ---------------------------------------------------------------

    def _find_by_path(self, path: str) -> Optional[MountPoint]:
        norm = os.path.normpath(path)
        for mp in self._points.values():
            if os.path.normpath(mp.path) == norm:
                return mp
        return None

    @property
    def points(self) -> List[MountPoint]:
        return list(self._points.values())

    @property
    def mounted(self) -> List[MountPoint]:
        return [mp for mp in self._points.values() if mp.is_mounted]

    @property
    def unmounted(self) -> List[MountPoint]:
        return [mp for mp in self._points.values() if not mp.is_mounted]

    @property
    def stale(self) -> List[MountPoint]:
        """Mount points that are empty, unmounted, and older than max_age."""
        result: List[MountPoint] = []
        for mp in self._points.values():
            if mp.is_permanent:
                continue
            if mp.is_mounted:
                continue
            dirpath = Path(mp.path)
            if dirpath.exists() and any(dirpath.iterdir()):
                continue  # not empty
            if mp.age_seconds > self._max_age:
                result.append(mp)
        return result

    # -- Cleanup -------------------------------------------------------------

    def cleanup_stale(self, *, dry_run: bool = False) -> List[str]:
        """Remove stale mount points.

        Returns a list of removed paths.
        """
        removed: List[str] = []
        for mp in self.stale:
            if dry_run:
                log.info("[dry-run] Would remove stale: %s", mp.path)
                removed.append(mp.path)
                continue
            if self.remove(mp.path):
                removed.append(mp.path)
        return removed

    def cleanup_empty(self, *, exclude: Optional[Sequence[str]] = None) -> List[str]:
        """Remove empty, unmounted directories under /mnt/.

        Args:
            exclude: Names to preserve (e.g., ``["usb", "floppy"]``).

        Returns list of removed paths.
        """
        exclude_set = set(exclude or [])
        removed: List[str] = []

        root = Path(self._mnt_root)
        if not root.is_dir():
            return removed

        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if entry.name in exclude_set:
                continue
            mp = self._find_by_path(str(entry))
            if mp and mp.is_permanent:
                continue
            if mp and mp.is_mounted:
                continue

            # Only remove empty dirs
            if not any(entry.iterdir()):
                try:
                    entry.rmdir()
                    log.info("Removed empty dir: %s", entry)
                    removed.append(str(entry))
                    self._remove_tracking(str(entry))
                except OSError as exc:
                    log.warning("Failed to remove %s: %s", entry, exc)

        return removed

    # -- Stats ---------------------------------------------------------------

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "total": len(self._points),
            "mounted": len(self.mounted),
            "unmounted": len(self.unmounted),
            "stale": len(self.stale),
        }


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class MountPointError(Exception):
    """Raised on mount point validation/creation failures."""
    pass


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> bool:
    """Validate mount point management."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mnt = os.path.join(tmpdir, "mnt")
        os.makedirs(mnt)

        mgr = MountPointManager(mnt, enforce_prefix=False)

        # Auto-name from device
        name = mgr._auto_name("/dev/sdb1")
        if name != "sdb1":
            print(f"auto_name failed: {name}")
            return False

        name = mgr._auto_name("UUID=abc-def-123")
        if name != "uuid-abcdef123":
            print(f"auto_name UUID failed: {name}")
            return False

        name = mgr._auto_name("server:/share")
        if name != "nfs-server--share":
            print(f"auto_name NFS failed: {name}")
            return False

        # Create
        mp = mgr.create("usb", device="/dev/sdb1", purpose="USB drive")
        if not os.path.isdir(mp.path):
            print(f"Mount point not created: {mp.path}")
            return False
        if mp.name != "usb":
            print(f"Name wrong: {mp.name}")
            return False

        # Double create
        try:
            mgr.create("usb")
            print("Double create should raise")
            return False
        except MountPointError:
            pass

        # Mark mounted/unmounted
        mgr.mark_mounted(mp.path)
        if not mp.is_mounted:
            print("is_mounted should be True")
            return False
        mgr.mark_unmounted(mp.path)
        if mp.is_mounted:
            print("is_mounted should be False after unmount")
            return False

        # Remove
        if not mgr.remove(mp.path):
            print("Remove failed")
            return False
        if os.path.exists(mp.path):
            print("Directory should be gone")
            return False

        # Stale cleanup
        mp2 = mgr.create("temp")
        time.sleep(0.01)
        mgr._max_age = 0  # Everything is stale
        stale = mgr.cleanup_stale()
        if len(stale) != 1:
            print(f"Expected 1 stale, got {len(stale)}")
            return False

        # Cleanup empty
        mp3 = mgr.create("empty")
        removed = mgr.cleanup_empty()
        if len(removed) != 1:
            print(f"Expected 1 removed, got {len(removed)}")
            return False

        # Stats
        if mgr.stats["total"] != 0:
            print(f"Expected 0 total, got {mgr.stats['total']}")
            return False

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("mount_point selftest:", "OK" if _selftest() else "FAIL")
