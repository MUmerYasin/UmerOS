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
UmerOS /media - Mount/Unmount Operations
==========================================

Provides mount, unmount, and remount operations with data-integrity
safety checks, busy-device handling, and read-only support.

FHS/TLDP reference:
    Before one can use a filesystem, it has to be *mounted*.
    When a filesystem no longer needs to be mounted, it can be
    unmounted with *umount*.  Because of disk caching, the data is
    not necessarily written to the media until you unmount it.

Modules
-------
- ``mount()`` / ``unmount()`` / ``remount()`` - core operations.
- ``is_mounted()`` - check current mount state.
- ``get_mount_options()`` - read active mount options.
- ``sync_mount()`` - flush pending writes before unmount.

Quick start::

    from media.mount_ops import mount, unmount, is_mounted

    mount("/dev/sdb1", "/media/usb0", fs_type="vfat")
    assert is_mounted("/media/usb0")
    unmount("/media/usb0")
"""

from __future__ import annotations

import errno
import logging
import os
import platform
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum, unique
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .media_types import MediaType

log = logging.getLogger("UmerOS.Media.MountOps")


# ---------------------------------------------------------------------------
#  Result types
# ---------------------------------------------------------------------------

@unique
class MountError(Enum):
    """Possible mount/unmount error codes."""
    OK = "ok"
    DEVICE_NOT_FOUND = "device_not_found"
    MOUNT_POINT_MISSING = "mount_point_missing"
    PERMISSION_DENIED = "permission_denied"
    BUSY = "busy"
    INVALID_FS_TYPE = "invalid_fs_type"
    READ_ONLY_FS = "read_only_fs"
    ALREADY_MOUNTED = "already_mounted"
    NOT_MOUNTED = "not_mounted"
    SYNC_FAILED = "sync_failed"
    IO_ERROR = "io_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class MountResult:
    """Result of a mount or unmount operation."""
    success: bool
    error: MountError = MountError.OK
    message: str = ""
    mount_point: str = ""
    device_path: str = ""
    fs_type: str = ""
    options: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def summary(self) -> str:
        """One-line human-readable summary."""
        if self.success:
            return f"Mounted {self.device_path} at {self.mount_point} ({self.fs_type})"
        return f"Mount failed [{self.error.value}]: {self.message}"


# ---------------------------------------------------------------------------
#  /proc/mounts helpers
# ---------------------------------------------------------------------------

def _read_proc_mounts() -> List[Dict[str, str]]:
    """Parse /proc/mounts (or simulate on Windows)."""
    mounts: List[Dict[str, str]] = []
    proc = Path("/proc/mounts")
    if not proc.exists():
        return mounts
    try:
        text = proc.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return mounts
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            mounts.append({
                "device": parts[0],
                "mount_point": parts[1],
                "fstype": parts[2],
                "options": parts[3],
            })
    return mounts


def _is_mounted_real(path: str) -> bool:
    """Check if *path* is a mount point via /proc/mounts."""
    real = os.path.realpath(path)
    for entry in _read_proc_mounts():
        if os.path.realpath(entry["mount_point"]) == real:
            return True
    return False


def _get_mount_info_real(path: str) -> Optional[Dict[str, str]]:
    """Look up mount entry for *path*."""
    real = os.path.realpath(path)
    for entry in _read_proc_mounts():
        if os.path.realpath(entry["mount_point"]) == real:
            return entry
    return None


# ---------------------------------------------------------------------------
#  Simulation layer (cross-platform / testing)
# ---------------------------------------------------------------------------

# In-memory mount table for simulation mode
_sim_mounts: Dict[str, Dict[str, Any]] = {}


def _sim_is_mounted(path: str) -> bool:
    return os.path.normpath(path) in _sim_mounts


def _sim_mount(
    device: str,
    mount_point: str,
    fs_type: str = "auto",
    options: Optional[List[str]] = None,
) -> MountResult:
    key = os.path.normpath(mount_point)
    if key in _sim_mounts:
        return MountResult(
            success=False,
            error=MountError.ALREADY_MOUNTED,
            message=f"{mount_point} is already mounted",
            device_path=device,
            mount_point=mount_point,
        )
    _sim_mounts[key] = {
        "device": device,
        "fstype": fs_type,
        "options": options or [],
        "mounted_at": time.time(),
    }
    log.info("SIM mount %s -> %s (%s)", device, mount_point, fs_type)
    return MountResult(
        success=True,
        device_path=device,
        mount_point=mount_point,
        fs_type=fs_type,
        options=options or [],
    )


def _sim_unmount(mount_point: str, *, sync: bool = True) -> MountResult:
    key = os.path.normpath(mount_point)
    entry = _sim_mounts.pop(key, None)
    if entry is None:
        return MountResult(
            success=False,
            error=MountError.NOT_MOUNTED,
            message=f"{mount_point} is not mounted",
            mount_point=mount_point,
        )
    log.info("SIM unmount %s (sync=%s)", mount_point, sync)
    return MountResult(
        success=True,
        mount_point=mount_point,
        device_path=entry.get("device", ""),
        fs_type=entry.get("fstype", ""),
    )


def _sim_remount(
    mount_point: str,
    options: List[str],
) -> MountResult:
    key = os.path.normpath(mount_point)
    entry = _sim_mounts.get(key)
    if entry is None:
        return MountResult(
            success=False,
            error=MountError.NOT_MOUNTED,
            message=f"{mount_point} is not mounted",
            mount_point=mount_point,
        )
    entry["options"] = options
    log.info("SIM remount %s opts=%s", mount_point, options)
    return MountResult(
        success=True,
        mount_point=mount_point,
        device_path=entry.get("device", ""),
        fs_type=entry.get("fstype", ""),
        options=options,
    )


# ---------------------------------------------------------------------------
#  Real mount/unmount 
# ---------------------------------------------------------------------------

def _run_cmd(cmd: List[str], timeout: int = 30) -> Tuple[int, str, str]:
    """Run a command; returns (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out: {cmd[0]}"
    except OSError as exc:
        return -1, "", str(exc)


def _real_mount(
    device: str,
    mount_point: str,
    fs_type: str = "auto",
    options: Optional[List[str]] = None,
) -> MountResult:
    """Mount using the system mount(8) command."""
    start = time.monotonic()
    mp = os.path.realpath(mount_point) if os.path.exists(mount_point) else mount_point

    if not os.path.exists(mp):
        try:
            os.makedirs(mp, mode=0o755, exist_ok=True)
        except OSError as exc:
            return MountResult(
                success=False,
                error=MountError.MOUNT_POINT_MISSING,
                message=f"Cannot create mount point: {exc}",
                device_path=device,
                mount_point=mp,
            )

    cmd = ["mount"]
    if fs_type and fs_type != "auto":
        cmd.extend(["-t", fs_type])
    if options:
        cmd.extend(["-o", ",".join(options)])
    cmd.extend([device, mp])

    rc, stdout, stderr = _run_cmd(cmd)
    elapsed = (time.monotonic() - start) * 1000

    if rc == 0:
        return MountResult(
            success=True,
            device_path=device,
            mount_point=mp,
            fs_type=fs_type,
            options=options or [],
            duration_ms=elapsed,
        )

    # Classify error
    err = MountError.UNKNOWN
    if "Permission denied" in stderr or "must be superuser" in stderr:
        err = MountError.PERMISSION_DENIED
    elif "wrong fs type" in stderr or "unknown filesystem" in stderr:
        err = MountError.INVALID_FS_TYPE
    elif "already mounted" in stderr:
        err = MountError.ALREADY_MOUNTED
    elif "not a block device" in stderr and "Not a directory" in stderr:
        err = MountError.DEVICE_NOT_FOUND

    return MountResult(
        success=False,
        error=err,
        message=stderr.strip() or f"mount returned {rc}",
        device_path=device,
        mount_point=mp,
        fs_type=fs_type,
        duration_ms=elapsed,
    )


def _real_unmount(mount_point: str, *, sync: bool = True) -> MountResult:
    """Unmount using the system umount(8) command."""
    start = time.monotonic()
    mp = os.path.realpath(mount_point) if os.path.exists(mount_point) else mount_point

    if sync:
        # Flush pending writes
        _run_cmd(["sync"], timeout=10)

    cmd = ["umount"]
    if sync:
        cmd.append("-l")   # lazy unmount if busy
    cmd.append(mp)

    rc, stdout, stderr = _run_cmd(cmd)
    elapsed = (time.monotonic() - start) * 1000

    if rc == 0:
        return MountResult(
            success=True,
            mount_point=mp,
            duration_ms=elapsed,
        )

    err = MountError.UNKNOWN
    if "Permission denied" in stderr or "must be superuser" in stderr:
        err = MountError.PERMISSION_DENIED
    elif "not mounted" in stderr:
        err = MountError.NOT_MOUNTED
    elif "busy" in stderr or "target is busy" in stderr:
        err = MountError.BUSY

    return MountResult(
        success=False,
        error=err,
        message=stderr.strip() or f"umount returned {rc}",
        mount_point=mp,
        duration_ms=elapsed,
    )


def _real_remount(mount_point: str, options: List[str]) -> MountResult:
    """Remount with new options."""
    start = time.monotonic()
    mp = os.path.realpath(mount_point) if os.path.exists(mount_point) else mount_point

    cmd = ["mount", "-o", "remount," + ",".join(options), mp]
    rc, stdout, stderr = _run_cmd(cmd)
    elapsed = (time.monotonic() - start) * 1000

    if rc == 0:
        return MountResult(
            success=True,
            mount_point=mp,
            options=options,
            duration_ms=elapsed,
        )
    return MountResult(
        success=False,
        error=MountError.UNKNOWN,
        message=stderr.strip() or f"remount returned {rc}",
        mount_point=mp,
        duration_ms=elapsed,
    )


# ---------------------------------------------------------------------------
#  Auto-detect simulation vs real
# ---------------------------------------------------------------------------

_use_simulation = platform.system() != "Linux" or not os.path.exists("/proc/mounts")


def set_simulation(value: bool) -> None:
    """Force simulation mode on or off (for testing)."""
    global _use_simulation
    _use_simulation = value


def get_sim_mounts() -> Dict[str, Dict[str, Any]]:
    """Return a copy of the simulated mount table (for testing)."""
    return dict(_sim_mounts)


def clear_sim_mounts() -> None:
    """Clear all simulated mounts (for testing)."""
    _sim_mounts.clear()


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

def is_mounted(path: str) -> bool:
    """Check if *path* is currently a mount point.

    Args:
        path: Directory path to check.

    Returns:
        True if the path is mounted.
    """
    if _use_simulation:
        return _sim_is_mounted(path)
    return _is_mounted_real(path)


def get_mount_options(path: str) -> Optional[Dict[str, str]]:
    """Get mount information for *path*.

    Returns:
        Dict with keys ``device``, ``fstype``, ``options`` or None.
    """
    if _use_simulation:
        key = os.path.normpath(path)
        entry = _sim_mounts.get(key)
        if entry is None:
            return None
        return {
            "device": entry.get("device", ""),
            "fstype": entry.get("fstype", ""),
            "options": ",".join(entry.get("options", [])),
        }
    return _get_mount_info_real(path)


def sync_mount(path: str) -> bool:
    """Flush pending writes for a mounted filesystem.

    Calls ``sync(8)`` to ensure all buffered data is written to disk.
    """
    if _use_simulation:
        log.info("SIM sync for %s", path)
        return True
    rc, _, _ = _run_cmd(["sync"], timeout=10)
    return rc == 0


def mount(
    device: str,
    mount_point: str,
    *,
    fs_type: str = "auto",
    options: Optional[List[str]] = None,
    create_dir: bool = True,
) -> MountResult:
    """Mount *device* at *mount_point*.

    Args:
        device: Kernel device node (e.g. ``"/dev/sdb1"``).
        mount_point: Target directory.
        fs_type: Filesystem type (``"auto"`` for auto-detect).
        options: Extra mount options.
        create_dir: Create mount point if missing.

    Returns:
        ``MountResult`` with success status and details.
    """
    mp = os.path.normpath(mount_point)

    if create_dir and not os.path.exists(mp):
        try:
            os.makedirs(mp, mode=0o755, exist_ok=True)
        except OSError as exc:
            return MountResult(
                success=False,
                error=MountError.MOUNT_POINT_MISSING,
                message=f"Cannot create mount point: {exc}",
                device_path=device,
                mount_point=mp,
            )

    if _use_simulation:
        return _sim_mount(device, mp, fs_type, options)

    return _real_mount(device, mp, fs_type, options)


def unmount(
    mount_point: str,
    *,
    sync: bool = True,
    lazy: bool = False,
    force: bool = False,
) -> MountResult:
    """Unmount a mounted filesystem.

    Follows TLDP guidance: always unmount before removing media.

    Args:
        mount_point: Directory to unmount.
        sync: Flush pending writes first.
        lazy: Use lazy unmount if device is busy.
        force: Force unmount (dangerous).

    Returns:
        ``MountResult`` with success status.
    """
    mp = os.path.normpath(mount_point)

    if _use_simulation:
        return _sim_unmount(mp, sync=sync)

    # Sync first if requested
    if sync:
        sync_mount(mp)

    start = time.monotonic()
    cmd = ["umount"]
    if force:
        cmd.append("-f")
    elif lazy:
        cmd.append("-l")
    cmd.append(mp)

    rc, stdout, stderr = _run_cmd(cmd)
    elapsed = (time.monotonic() - start) * 1000

    if rc == 0:
        return MountResult(success=True, mount_point=mp, duration_ms=elapsed)

    err = MountError.UNKNOWN
    if "busy" in stderr or "target is busy" in stderr:
        err = MountError.BUSY
    elif "not mounted" in stderr:
        err = MountError.NOT_MOUNTED
    elif "Permission denied" in stderr:
        err = MountError.PERMISSION_DENIED

    return MountResult(
        success=False,
        error=err,
        message=stderr.strip() or f"umount returned {rc}",
        mount_point=mp,
        duration_ms=elapsed,
    )


def remount(
    mount_point: str,
    options: List[str],
) -> MountResult:
    """Remount with new options.

    Useful for switching between read-only and read-write modes.
    """
    mp = os.path.normpath(mount_point)

    if _use_simulation:
        return _sim_remount(mp, options)

    return _real_remount(mp, options)


def mount_status() -> List[Dict[str, str]]:
    """Return all current mount entries."""
    if _use_simulation:
        result = []
        for path, info in _sim_mounts.items():
            result.append({
                "device": info.get("device", ""),
                "mount_point": path,
                "fstype": info.get("fstype", ""),
                "options": ",".join(info.get("options", [])),
            })
        return result
    return _read_proc_mounts()


def _selftest() -> bool:
    """Run self-diagnostics.  Returns True on success."""
    set_simulation(True)
    clear_sim_mounts()

    # Test mount
    r = mount("/dev/sda1", "/media/test0", fs_type="vfat")
    assert r.success, r.message
    assert is_mounted("/media/test0")

    # Test double mount
    r2 = mount("/dev/sda2", "/media/test0", fs_type="ext4")
    assert not r2.success
    assert r2.error == MountError.ALREADY_MOUNTED

    # Test get mount options
    info = get_mount_options("/media/test0")
    assert info is not None
    assert info["fstype"] == "vfat"

    # Test remount
    r3 = remount("/media/test0", ["ro", "noatime"])
    assert r3.success

    # Test unmount
    r4 = unmount("/media/test0", sync=False)
    assert r4.success
    assert not is_mounted("/media/test0")

    # Test unmount of non-mounted
    r5 = unmount("/media/test0")
    assert not r5.success
    assert r5.error == MountError.NOT_MOUNTED

    # Test mount_status
    mount("/dev/sdb1", "/media/test1")
    mount("/dev/sdb2", "/media/test2")
    status = mount_status()
    assert len(status) >= 2

    clear_sim_mounts()
    return True
